"""Read-only v0.11 snapshots and own-source material evidence; no fitting."""
from pathlib import Path
import collections
import hashlib
import importlib.util
import json
import math
import re
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT / '循环稳定性数据库_v0.10_原文精细补证_20261021'
NAME = '_cycling_v010_parent_for_v011'
if NAME not in sys.modules:
    spec = importlib.util.spec_from_file_location(NAME, PARENT / 'ml_data.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[NAME] = module
    spec.loader.exec_module(module)
base = sys.modules[NAME]
Dataset = base.Dataset
DataNotReady = base.DataNotReady


class Database(base.Database):
    def __init__(self, path=None):
        folder = Path(__file__).resolve().parent
        contract = json.loads((folder / 'data_contract.json').read_text('utf-8'))
        with (PARENT / 'cycling_v0_10.sqlite').open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != contract['parent_database_sha256']:
                raise RuntimeError('Immutable v0.10 fingerprint changed.')
        super().__init__(PARENT / 'cycling_v0_10.sqlite')
        self.root = folder
        self.contract = contract
        self.path = Path(path).resolve() if path else folder / contract['database_file']
        self.delta_v11 = sqlite3.connect(self.path.as_uri() + '?mode=ro', uri=True)
        self.delta_v11.row_factory = sqlite3.Row
        self.delta_v11.execute('PRAGMA query_only=ON')
        self.decisions_v11 = {r['endpoint_id']: json.loads(r['review_json']) for r in self.delta_v11.execute('select * from test_reviews_v11')}

    def close(self):
        if hasattr(self, 'delta_v11'):
            self.delta_v11.close()
        super().close()

    def fetch(self, profile=None, year_min=None, year_max=None):
        profile = profile or self.contract['default_profile']
        if profile in self.contract['profiles']:
            sql = 'select r.row_json from review_rows_v11 r join profile_membership_v11 p using(endpoint_id) where p.profile=?'
            args = [profile]
            features = self.contract['profiles'][profile]['features']
        elif profile in ['all_review', 'review_3e_all', 'incoming_review']:
            sql = 'select row_json from review_rows_v11'
            args = []
            features = self.contract['core_features']
        else:
            return super().fetch(profile, year_min, year_max)
        rows = [json.loads(r[0]) for r in self.delta_v11.execute(sql, args)]
        if profile == 'review_3e_all':
            rows = [r for r in rows if r['system'] == '3E']
        elif profile == 'incoming_review':
            rows = [r for r in rows if r['endpoint_id'].startswith('incoming:')]
        rows = [r for r in rows if (year_min is None or r['source_year'] is not None and r['source_year'] >= int(year_min))
                and (year_max is None or r['source_year'] is not None and r['source_year'] <= int(year_max))]
        counts = collections.Counter(r['source_group'] for r in rows)
        for row in rows:
            row['source_weight'] = 1 / counts[row['source_group']]
        return Dataset(profile, sorted(rows, key=lambda r: (r['source_group'], r['endpoint_id'])), list(features))

    def by_endpoint(self, endpoint_id):
        row = self.delta_v11.execute('select row_json from review_rows_v11 where endpoint_id=?', (endpoint_id,)).fetchone()
        if not row:
            return None
        result = json.loads(row[0])
        result.pop('source_weight', None)  #Weights only have meaning within db.fetch(profile).
        return result

    def by_alias(self, namespace, alias):
        old = super().by_alias(namespace, alias)
        return self.by_endpoint(old['endpoint_id']) if old else None

    def incoming_tests(self, document_id=None):
        if not hasattr(self, 'delta_v11'):
            return super().incoming_tests(document_id)
        rows = [json.loads(r[0]) for r in self.delta_v11.execute("select row_json from review_rows_v11 where endpoint_id like 'incoming:%' order by endpoint_id")]
        if document_id:
            rows = [r for r in rows if r['document_id'] == document_id]
        for row in rows:
            row.pop('source_weight', None)
        return rows

    def material_properties(self, material_key=None, selected_only=True):
        sql = '''select p.*,e.path,e.sha256,e.locator,e.excerpt,e.stage
                 from material_properties_v11 p join document_evidence_v11 e using(evidence_id) where 1=1'''
        args = []
        if material_key:
            sql += ' and p.material_key=?'
            args.append(material_key)
        if selected_only:
            sql += " and p.status='selected_agent_source_review'"
        result = [dict(r) for r in self.delta_v11.execute(sql + ' order by p.material_key,p.field_name', args)]
        for r in result:
            r['value'] = json.loads(r['value_json'])
            r['reviewer'] = 'Codex agent original-source review; no human review claimed'
        return result

    def evidence(self, endpoint_id, field=None):
        old = super().evidence(endpoint_id, field)
        row = self.delta_v11.execute('select row_json from review_rows_v11 where endpoint_id=?', (endpoint_id,)).fetchone()
        if row:
            material_key = json.loads(row[0]).get('material_key_v11')
            for e in self.material_properties(material_key) if material_key else []:
                systems = json.loads(e['applies_to_systems_json'])
                if systems and json.loads(row[0])['system'] not in systems:
                    continue
                if field and e['field_name'] != field:
                    continue
                old.append({'endpoint_id': endpoint_id, 'selected': 1, 'review_version': 'v0.11', **e})
        case = self.decisions_v11.get(endpoint_id)
        if case:
            for e in case.get('evidence', []):
                for f in e.get('fields', []):
                    if field and field != f:
                        continue
                    value = case['after'].get(f)
                    if f == 'material_scope':
                        value = {'status': 'own_source_biomass_porous_carbon_reviewed', 'basis': case.get('gate_dispositions', {}).get('material_checked')}
                    old.append({'endpoint_id': endpoint_id, 'field_name': f, 'selected': 1,
                                'value_json': json.dumps(value, ensure_ascii=False), 'excerpt_kind': 'agent_source_evidence_summary', 'review_version': 'v0.11', **e})
        return old

    def holds(self, endpoint_id):
        case = self.decisions_v11.get(endpoint_id)
        if not case:
            return super().holds(endpoint_id)
        return {'open_issues': case.get('open_issues', []), 'approved_profiles': case['approved_profiles'],
                'gate_dispositions': case.get('gate_dispositions', {}), 'caveats': case.get('caveats', []),
                'previous_holds': super().holds(endpoint_id) if case.get('before') else None,
                'review_version': 'v0.11'}

    def admission_checks(self, endpoint_id, profile=None):
        case = self.decisions_v11.get(endpoint_id)
        if not case:
            return super().admission_checks(endpoint_id, profile)
        return [{'endpoint_id': endpoint_id, 'profile': p, 'status': 'approved_for_reported_protocol' if p in case['approved_profiles'] else 'pending_or_outside',
                 'evidence': case['evidence'], 'caveats': case.get('caveats', []), 'review_version': 'v0.11'}
                for p in ([profile] if profile else self.contract['profiles'])]

    def full_review_queue(self):
        return [r for r in self.fetch('all_review').rows if not r.get('admission_profiles_v11')]

    def material_matrix(self, profile=None, extra_features=None):
        """Validated core plus sparse pre-cycling features; None is never filled here.

        Encoding/imputation must use a training split, e.g. material_feature_inputs_v011.
        XPS reported percentages retain explicit/unspecified basis as a categorical flag.
        """
        ds = self.fetch(profile)
        core = ds.feature_matrix()
        extras = list(extra_features if extra_features is not None else self.contract['model_material_features'])
        allowed = self.contract.get('extra_material_feature_whitelist', self.contract['model_material_features'])
        if len(set(extras)) != len(extras) or set(extras) - set(allowed):
            raise DataNotReady('Only declared pre-cycling material predictors are allowed.')
        names = ds.features + [f for f in extras if f not in ds.features]
        X = [[r.get(f) for f in names] for r in ds.rows]
        categorical = {'electrolyte', 'reference_electrode', 'XPS_percentage_basis'}
        for values in X:
            for name, value in zip(names, values):
                if value is None:
                    continue
                if name in categorical:
                    if not isinstance(value, str) or not value:
                        raise DataNotReady('Invalid categorical material descriptor.')
                elif isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                    raise DataNotReady('Invalid numeric material descriptor.')
        return {'profile': ds.profile, 'X': X, 'y': core['y'], 'groups': core['groups'],
                'endpoint_ids': [r['endpoint_id'] for r in ds.rows], 'feature_names': names,
                'categorical_features': sorted(categorical & set(names)),
                'missing_mask': [[v is None for v in values] for values in X],
                'source_folds': ds.source_folds(len(set(core['groups']))),
                'sample_weight': core['sample_weight'], 'imputed': False, 'estimators_fitted': 0,
                'current_semantics': core['current_semantics'],
                'scientific_limits': self.contract['material_feature_limits']}

    def search_corpus(self, query, doi=None, limit=20):
        expression = ' AND '.join('"' + w.replace('"', '""') + '"' for w in str(query).split())
        if not expression:
            return []
        path = ROOT / self.contract['corpus_search_database']
        with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as connection:
            connection.row_factory = sqlite3.Row
            sql = '''select distinct h.*,s.path,s.format from hit_search f
                     join evidence_hits h on h.hit_id=f.rowid join sources s using(sha256)
                     where hit_search match ?'''
            args = [expression]
            if doi:
                sql += ' and exists(select 1 from identity_sources i where i.sha256=h.sha256 and i.identity_key=?)'
                args.append('doi:' + str(doi).lower().removeprefix('doi:').removeprefix('https://doi.org/'))
            sql += ' order by h.hit_id limit ?'
            args.append(int(limit))
            return [dict(r) for r in connection.execute(sql, args)]

    def search_native(self, query, doi=None, limit=10):
        """Full native text, including text outside the nine automatic cue themes."""
        words = str(query).split()
        expression = ' AND '.join('"' + w.replace('"', '""') + '"' for w in words)
        if not expression:
            return []
        path = ROOT / self.contract['corpus_search_database']
        with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as connection:
            connection.row_factory = sqlite3.Row
            sql = '''select m.*,s.path,s.format from full_native_fts_v11 f
                     join full_native_map_v11 m on m.map_id=f.rowid
                     join sources s on s.sha256=m.source_sha256 where full_native_fts_v11 match ?'''
            args = [expression]
            if doi:
                sql += ' and exists(select 1 from identity_sources i where i.sha256=m.source_sha256 and i.identity_key=?)'
                args.append('doi:' + str(doi).lower().removeprefix('doi:').removeprefix('https://doi.org/'))
            sql += ' order by m.map_id limit ?'; args.append(int(limit))
            result = []
            for row in connection.execute(sql, args).fetchall():
                row = dict(row); key = json.loads(row['upstream_key_json'])
                if row['provider'] == 'v08_source_segments':
                    text = self.conn.execute('select text from source_segments where segment_id=?', (key['segment_id'],)).fetchone()[0]
                elif row['provider'] == 'v07_candidate_segments':
                    text = self.conn.execute('select text from candidate_source_segments_v07 where segment_id=?', (key['segment_id'],)).fetchone()[0]
                elif row['provider'] == 'v08_incoming_pages':
                    text = self.conn.execute('select text from incoming_pages_v08 where document_id=? and page_number=?', (key['document_id'], key['page_number'])).fetchone()[0]
                elif row['provider'] == 'v11_new_native_segments':
                    text = connection.execute('select text from new_native_segments where sha256=? and locator=?', (key['sha256'], key['locator'])).fetchone()[0]
                else:
                    raise RuntimeError('Unknown full-text provenance provider.')
                if hashlib.sha256(text.encode()).hexdigest() != row['content_sha256']:
                    raise RuntimeError('Upstream text fingerprint changed.')
                match = re.search('|'.join(re.escape(w) for w in words), text, re.I)
                start = max(0, match.start() - 200) if match else 0
                row['excerpt'] = text[start:start + 1400]
                row['training_eligible'] = 0
                row['status'] = 'native_search_match_not_test_admission'
                result.append(row)
            return result

    def search_tables(self, query, doi=None, limit=20):
        expression = ' AND '.join('"' + w.replace('"', '""') + '"' for w in str(query).split())
        if not expression:
            return []
        path = ROOT / self.contract['corpus_search_database']
        with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as connection:
            connection.row_factory = sqlite3.Row
            sql = '''select r.row_ordinal,r.cells_json,r.row_text,t.*,s.path
                     from raw_table_search_v11 f join raw_table_rows_v11 r on r.row_id=f.rowid
                     join raw_tables_v11 t using(table_id) join sources s on s.sha256=t.source_sha256
                     where raw_table_search_v11 match ?'''
            args = [expression]
            if doi:
                sql += ' and exists(select 1 from identity_sources i where i.sha256=t.source_sha256 and i.identity_key=?)'
                args.append('doi:' + str(doi).lower().removeprefix('doi:').removeprefix('https://doi.org/'))
            sql += ' order by t.table_id,r.row_ordinal limit ?'; args.append(int(limit))
            return [dict(r) for r in connection.execute(sql, args)]
