"""Read-only local datasets, field evidence and full-text lookup. Python stdlib only."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import collections,hashlib,json,math,sqlite3

class DataNotReady(ValueError):pass
class StaleCacheError(RuntimeError):pass

@dataclass
class Dataset:
    profile:str
    rows:list[dict]
    features:list[str]
    training_authorized:bool=False
    note:str='Preparation only; loading data never authorizes a model fit.'
    def fingerprint(self):
        return hashlib.sha256(json.dumps({'profile':self.profile,'features':self.features,'rows':self.rows},ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    def source_folds(self,folds=5):
        """Return indices grouped by available study provenance; no estimator is run."""
        groups=sorted({x['source_group'] for x in self.rows})
        if not 2<=folds<=len(groups):raise ValueError('Need at least two available source groups and folds<=groups.')
        buckets=[set(groups[i::folds]) for i in range(folds)]
        return [{'train':[i for i,x in enumerate(self.rows) if x['source_group'] not in g],'test':[i for i,x in enumerate(self.rows) if x['source_group'] in g]} for g in buckets]
    def feature_matrix(self):
        """Validated profile-specific raw inputs; never fits or imputes anything."""
        reported=self.profile.startswith('reported_')
        if self.profile not in ('strict_2e','strict_3e','reported_3e','reported_2e','reported_2e_residue','reported_2e_approx'):raise DataNotReady('Review/proposal profiles cannot be exported as an admitted training matrix.')
        if not self.rows:raise DataNotReady('No records passed this profile. Inspect review_3e and evidence; no fallback to pending rows.')
        X=[];y=[];groups=[]
        for row in self.rows:
            relations=('eq','approx') if self.profile=='reported_2e_approx' else ('eq',)
            if row.get('metric_kind')!='capacitance_retention' or row.get('retention_relation') not in relations:raise DataNotReady('Wrong target or disallowed label relation.')
            expected='3E' if self.profile in ('strict_3e','reported_3e') else '2E_symmetric'
            if row.get('system')!=expected or row.get('method')!='GCD':raise DataNotReady('Dataset system/method does not match its declared profile.')
            if reported and (row.get('admission_status')!='approved_for_reported_protocol' or row.get('eligible')!=1):raise DataNotReady('Reported-profile admission missing.')
            if row.get('source_year') is None or not 2023<=row['source_year']<=2026 or row['cycle_count']<1000:raise DataNotReady('Publication year or cycling length outside the declared research cohort.')
            values=[row.get(f) for f in self.features]
            if any(v is None or isinstance(v,str) and not v.strip() or isinstance(v,float) and not math.isfinite(v) for v in values):raise DataNotReady('Missing or nonfinite core input; no implicit zero filling.')
            categorical={'electrolyte','reference_electrode'}
            if any(not isinstance(row[f],str) for f in self.features if f in categorical):raise DataNotReady('Categorical input must retain its reported text identity.')
            if any(not isinstance(row[f],(int,float)) or isinstance(row[f],bool) or not math.isfinite(row[f]) for f in self.features if f not in categorical):raise DataNotReady('Numeric feature has an invalid type.')
            if not isinstance(row['retention_pct'],(int,float)) or not math.isfinite(row['retention_pct']):raise DataNotReady('Nonfinite target.')
            current='reported_current_A_g' if reported else 'canonical_current_A_g'
            if row['cycle_count']<=0 or row[current]<=0 or row['concentration_mol_L']<=0 or row['BET_m2_g']<=0:raise DataNotReady('Nonpositive physical core input.')
            if row['cycle_voltage_upper_V']<=row['cycle_voltage_lower_V'] or row['retention_pct']<0:raise DataNotReady('Invalid voltage interval or negative retention.')
            X.append(values);y.append(row['retention_pct']);groups.append(row['source_group'])
        return {'X':X,'y':y,'groups':groups,'sample_weight':[r['source_weight'] for r in self.rows],'feature_names':self.features,'training_authorized':False,'current_semantics':'author_reported_protocol_descriptor' if reported else 'canonical_physical_current'}

class Database:
    def __init__(self,path=None):
        self.root=Path(__file__).resolve().parent
        self.path=Path(path).resolve() if path else self.root/'cycling_v0_6.sqlite'
        self.contract=json.loads((self.root/'data_contract.json').read_text(encoding='utf-8'))
        self.conn=sqlite3.connect(self.path.as_uri()+'?mode=ro',uri=True);self.conn.row_factory=sqlite3.Row
        self.conn.execute('PRAGMA query_only=ON');self._check_cache()
    def _check_cache(self):
        saved=dict(self.conn.execute('select * from feature_cache_meta'))
        last=self.conn.execute('select max(selection_id) from field_selection_history').fetchone()[0]
        count=self.conn.execute('select count(*) from field_selection').fetchone()[0]
        if saved.get('selection_history_max_id')!=str(last) or saved.get('selected_fields')!=str(count):raise StaleCacheError('Field review changed; rebuild and validate the cache before reading datasets.')
    def close(self):self.conn.close()
    def __enter__(self):return self
    def __exit__(self,*args):self.close()
    def fetch(self,profile=None,year_min=None,year_max=None):
        self._check_cache()
        profile=profile or self.contract['default_profile']
        if profile in self.contract['profiles']:
            rows=[json.loads(r[0]) for r in self.conn.execute('select row_json from reported_training_rows_v06 where profile=? order by source_group,endpoint_id',(profile,))]
            rows=[r for r in rows if (year_min is None or r['source_year']>=int(year_min)) and (year_max is None or r['source_year']<=int(year_max))]
            counts=collections.Counter(r['source_group'] for r in rows)
            for r in rows:
                r['source_weight']=1/counts[r['source_group']]
                a=self.conn.execute('select reason,evidence_json from reported_profile_admissions_v06 where profile=? and endpoint_id=?',(profile,r['endpoint_id'])).fetchone()
                r['profile_review']={'reason':a[0],'evidence':json.loads(a[1])}
            return Dataset(profile,rows,list(self.contract['profiles'][profile]['features']))
        if profile not in ('strict_2e','strict_3e','review_3e','review_3e_all','all_review','proposal_2e'):raise ValueError('Unknown dataset profile: '+str(profile))
        features=list(self.contract['canonical_core_features']);args=[]
        if profile=='proposal_2e':
            sql="select r.*,r.validation_group_id as source_group,p.year as source_year from training_rows_r4 r join papers p using(paper_id) where r.profile='literature_core7_exact'"
            features=[('reported_current_A_g' if f=='canonical_current_A_g' else f) for f in features]
        else:
            sql='select f.* from model_feature_cache f where 1=1'
            if profile=='review_3e':sql+=" and exists(select 1 from endpoint_aliases a where a.endpoint_id=f.endpoint_id and a.namespace='TE')"
            elif profile=='review_3e_all':sql+=" and f.system='3E'"
            elif profile.startswith('strict_'):
                table='training_ready_2e' if profile=='strict_2e' else 'training_ready_3e'
                sql+=' and f.endpoint_id in(select endpoint_id from '+table+')'
        if year_min is not None:sql+=' and source_year>=?';args.append(int(year_min))
        if year_max is not None:sql+=' and source_year<=?';args.append(int(year_max))
        sql+=' order by source_group,'+('record_id' if profile=='proposal_2e' else 'endpoint_id')
        rows=[dict(x) for x in self.conn.execute(sql,args)]
        if profile=='proposal_2e':
            for x in rows:x['concentration_mol_L']=x['concentration_value'];x['cycle_voltage_lower_V']=x['voltage_lower_V'];x['cycle_voltage_upper_V']=x['voltage_upper_V']
        counts=collections.Counter(x['source_group'] for x in rows)
        for x in rows:x['source_weight']=1/counts[x['source_group']]
        if profile in ('all_review','review_3e','review_3e_all'):features=[('reported_current_A_g' if f=='canonical_current_A_g' else f) for f in features]
        return Dataset(profile,rows,features)
    def evidence(self,endpoint_id,field=None):
        sql='select o.*,case when s.observation_id is not null then 1 else 0 end as currently_selected from field_observations o left join field_selection s on s.observation_id=o.observation_id where o.endpoint_id=?';args=[endpoint_id]
        if field is not None:sql+=' and o.field_name=?';args.append(field)
        return [dict(x) for x in self.conn.execute(sql+' order by o.observation_id',args)]
    def by_alias(self,namespace,alias):
        row=self.conn.execute('select endpoint_id from endpoint_aliases where namespace=? and alias=?',(namespace,alias)).fetchone()
        return dict(self.conn.execute('select * from model_feature_cache where endpoint_id=?',(row[0],)).fetchone()) if row else None
    def search(self,query,doi=None,limit=10):
        words=str(query).split()
        if not words:return []
        expression=' AND '.join('"'+word.replace('"','""')+'"' for word in words)
        sql='select distinct s.segment_id,s.source_id,s.locator,s.section_kind,s.text,p.identity_key,l.doi from source_search f join source_segments s on s.segment_id=f.rowid join paper_documents p using(source_id) join literature_registry l using(identity_key) where source_search match ?';args=[expression]
        if doi is not None:sql+=' and l.doi=?';args.append(str(doi).lower().removeprefix('https://doi.org/'))
        sql+=' limit ?';args.append(max(1,min(int(limit),100)))
        return [dict(x) for x in self.conn.execute(sql,args)]
    def queue(self,status=None):
        sql='select q.*,l.doi,l.title,r.disposition as current_disposition,r.reason as current_review_reason,r.remaining_work from extraction_queue q join literature_registry l using(identity_key) left join paper_source_reviews r using(identity_key)';args=[]
        if status:sql+=' where q.status=?';args.append(status)
        return [dict(x) for x in self.conn.execute(sql+' order by priority,status,identity_key',args)]

    def claims(self,doi=None,limit=100):
        sql='select n.*,l.doi,s.locator,a.decision as reviewed_decision,a.reason as reviewed_reason from native_measurement_claims n join literature_registry l using(identity_key) join source_segments s using(segment_id) left join native_claim_adjudications a using(claim_id) where 1=1';args=[]
        if doi:sql+=' and l.doi=?';args.append(str(doi).lower())
        sql+=' order by claim_id limit ?';args.append(max(1,min(int(limit),1000)))
        return [dict(x) for x in self.conn.execute(sql,args)]

    def admission_checks(self,endpoint_id,profile=None):
        """Inspect preparation gates. A pass on one criterion is not admission."""
        if profile in self.contract['profiles']:
            rows=[dict(x) for x in self.conn.execute('select * from reported_profile_admissions_v06 where endpoint_id=? and profile=?',(endpoint_id,profile))]
            for row in rows:row['evidence']=json.loads(row.pop('evidence_json'))
            return rows
        sql='select * from record_admission_checks where endpoint_id=?';args=[endpoint_id]
        if profile is not None:
            if profile not in ('canonical_2e','canonical_3e'):raise ValueError('Use canonical_2e or canonical_3e.')
            sql+=' and profile=?';args.append(profile)
        rows=[dict(x) for x in self.conn.execute(sql+' order by profile,criterion',args)]
        for row in rows:row['evidence']=json.loads(row.pop('evidence_json'))
        return rows

    def paper_reviews(self,doi=None,disposition=None):
        sql='select r.*,l.doi,l.title from paper_source_reviews r join literature_registry l using(identity_key) where 1=1';args=[]
        if doi:sql+=' and l.doi=?';args.append(str(doi).lower().removeprefix('https://doi.org/'))
        if disposition:sql+=' and r.disposition=?';args.append(disposition)
        return [dict(x) for x in self.conn.execute(sql+' order by r.identity_key',args)]

    def review_summary(self):
        self._check_cache()
        return {'records':self.conn.execute('select count(*) from model_endpoints').fetchone()[0],
                'default_profile':self.contract['default_profile'],
                'reported_profiles':[dict(x) for x in self.conn.execute('select profile,count(*) as records,count(distinct source_group) as source_groups from reported_training_rows_v06 group by profile')],
                'strict_2e':self.conn.execute('select count(*) from training_ready_2e').fetchone()[0],
                'strict_3e':self.conn.execute('select count(*) from training_ready_3e').fetchone()[0],
                'bounded_paper_reviews':self.conn.execute('select count(*) from paper_source_reviews').fetchone()[0],
                'relevant_profile_outcomes':[dict(x) for x in self.conn.execute('select preparation_gate_status,count(*) as records from v05_relevant_admission group by preparation_gate_status')],
                'training_authorized':False}

    def holds(self,endpoint_id):
        row=self.conn.execute('select legacy_record_id from model_endpoints where endpoint_id=?',(endpoint_id,)).fetchone()
        if row is None:return {}
        inherited=[dict(x) for x in self.conn.execute("select b.*,bs.affects_core7 from record_blockers b left join blocker_scopes bs using(record_id,code) where b.record_id=? and b.status='open'",(row[0],))] if row[0] else []
        issues=[dict(x) for x in self.conn.execute('select i.* from extraction_issues i left join extraction_issue_resolutions r using(issue_id) where i.endpoint_id=? and r.issue_id is null',(endpoint_id,))]
        return {'legacy_blockers':inherited,'current_open_issues':issues,'historical_canonical_admission':[dict(x) for x in self.conn.execute('select * from admission_reviews where endpoint_id=?',(endpoint_id,))], 'reported_profile_admission':[dict(x) for x in self.conn.execute('select * from reported_profile_admissions_v06 where endpoint_id=?',(endpoint_id,))],'reported_issue_scope':[dict(x) for x in self.conn.execute('select * from reported_issue_dispositions_v06 where endpoint_id=?',(endpoint_id,))]}
