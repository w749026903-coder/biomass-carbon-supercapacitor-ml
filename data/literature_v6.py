"""Read-only SI evidence and explicitly reviewed, separate DES reported-mean inputs."""
import json
from data.literature_v4 import LiteratureDatabaseV4
GLY='10.1021/acsomega.3c00816'
DES_PREDICTORS=('BET_surface_area_m2_g','micropore_volume_cm3_g','mesopore_volume_cm3_g','total_pore_volume_cm3_g','XPS_C_at_pct','XPS_N_at_pct','XPS_O_at_pct','Raman_ID_IG','XRD_d002_nm','carbonization_temperature_C','carbonization_duration_h','current_A_g','temperature_C','initial_cycle_voltage_lower_V','initial_cycle_voltage_upper_V')

class LiteratureDatabaseV6(LiteratureDatabaseV4):
    def diffraction_peaks(self,doi=None):
        return [dict(r,record=json.loads(r['record_json'])) for r in self.connection.execute('''
          select p.*,m.doi,m.sample_name,d.path as source_path,d.sha256 as source_sha256,l.locator
          from diffraction_peaks_v6 p join materials m using(material_key)
          join table_source_links l using(table_key) join source_documents d using(document_key)
          where (? is null or m.doi=?) order by m.doi,m.sample_name,p.peak_id''',(doi,doi))]

    def report_variants(self,metric=None):
        return [dict(r,conditions=json.loads(r['conditions_json'])) for r in self.connection.execute('''
          select v.*,m.doi,m.sample_name,d.path as source_path,d.sha256 as source_sha256
          from report_variants_v6 v join materials m using(material_key)
          join source_documents d using(document_key)
          where (? is null or metric=?) order by variant_id''',(metric,metric))]

    def eis_fits(self,doi=GLY):
        result=[]
        for item in self.outcomes():
            record=item['record']
            if record.get('extraction_batch')!='v6' or not record.get('fit_parameter'):continue
            mat=self.connection.execute('select doi,sample_name from materials where material_key=?',(item['material_key'],)).fetchone()
            if doi is not None and mat['doi']!=doi:continue
            result.append(dict(item,doi=mat['doi'],sample_name=mat['sample_name']))
        return result

    def capacitances(self,doi=None,sample=None,method=None,electrolyte=None):
        rows=super().capacitances(doi,sample,method,electrolyte)
        decisions={r['observation_id']:dict(r) for r in self.connection.execute('select * from capacitance_current_decisions_v6')}
        for row in rows:
            if row['observation_id'] not in decisions:continue
            decision=decisions[row['observation_id']]
            row['reported_current_raw_A_g']=row['current_A_g']
            row['current_A_g']=decision['selected_current_A_g']
            row['current_binding_decision']=json.loads(decision['decision_json'])
            row['status']='v6_current_axis_caption_correction_original_prose_retained'
        return rows

    def des_reported_inputs(self,target='retention'):
        if target not in ['retention','capacitance']:raise ValueError('Use retention or capacitance; never concatenate targets.')
        result=[]
        own=[r for r in self.capacitances(doi=GLY) if r['table_key']==GLY+'#tbl3']
        cycles={r['material_key']:r['record'] for r in self.tests() if r['candidate_id'].startswith('LP5_GC') and r['candidate_id']!='LP5_GCprototype'}
        fields=['BET_surface_area_m2_g','micropore_volume_cm3_g','mesopore_volume_cm3_g','total_pore_volume_cm3_g','XPS_C_at_pct','XPS_N_at_pct','XPS_O_at_pct','Raman_ID_IG','XRD_d002_nm']
        for cap in own:
            record=cycles[cap['material_key']]
            row=dict(doi=GLY,source_group='doi:'+GLY,sample_name=cap['sample_name'],target_name='DES_3e_retention_pct_mean' if target=='retention' else 'DES_3e_initial_capacitance_F_g_mean',target_value=record['retention_pct'] if target=='retention' else cap['value'],target_reported_uncertainty=record['reported_retention_uncertainty'] if target=='retention' else cap['conditions']['reported_uncertainty'],uncertainty_type='author±; SD/SEM/confidence level not assumed',cycle_count=1000 if target=='retention' else 1,current_A_g=1,temperature_C=30,electrolyte='ethaline_ChCl_EG_1to2',DES_ChCl_to_EG_molar_ratio='1:2',electrolyte_concentration_mol_L=None,reference_electrode='silver_wire_pseudoreference',initial_cycle_voltage_lower_V=0,initial_cycle_voltage_upper_V=1,later_cycle_window_directly_shown=False,formal_training_admitted=False,preparation_view_only=True,source_path=cap['source_path'],source_sha256=cap['source_sha256'],locator='OwnTable3 + originalFig10 first-cycleGCD + SIphysicalp3-4')
            review=self.connection.execute('select review_json from purpose_reviews_v6 where observation_id=? and purpose=? and eligible=1',(cap['observation_id'],'reported_DES_3e_'+target+'_mean')).fetchone()
            if not review:raise RuntimeError('No explicit DES-purpose admission for this row.')
            row.pop('formal_training_admitted');row.pop('preparation_view_only')
            row.update(row_id=cap['observation_id']+'#'+target,observation_id=cap['observation_id'],material_key=cap['material_key'],physical_sample_group=GLY+'#'+cap['sample_name'],physical_test_group=GLY+'#'+cap['sample_name']+'#3E_liquid_DES_1000cycles_1Ag')
            row.update(purpose='reported_DES_3e_'+target+'_mean',purpose_reviewed_input_ready=True,ordinary_aqueous_cycling_admitted=False,current_cycling_database_membership=False,training_authorized=False,purpose_review=json.loads(review[0]),electrolyte_concentration_status='not_applicable_as_aqueous_molarity; neatDEScompositiongiven',DES_hydrogen_bond_donor='ethylene_glycol',DES_hydrogen_bond_acceptor='choline_chloride')
            if target=='retention':
                row.update(cycle_voltage_lower_V=0,cycle_voltage_upper_V=1,cycle_window_review='Own first-cycleGCD for each sample + Table3same row/first-cycleC/1000cycleretention/common30Cethaline1A/g protocol. Accepted under existingreportpurpose table+commonprotocol rule; latercyclesnotindependentlyplotted.')
            grouped={}
            for f in self.facts(doi=GLY,sample=cap['sample_name']):grouped.setdefault(f['field_name'],[]).append(f)
            row['material_evidence_states']={};row['material_evidence']={}
            for field in fields:
                evidence=grouped.get(field,[]);values={f['value'] for f in evidence if f['value'] is not None and 'conflict' not in f['review_status']}
                row[field]=next(iter(values)) if len(values)==1 else None
                row[field+'_is_missing']=row[field] is None
                row['material_evidence_states'][field]=[f['review_status'] for f in evidence] or ['not_reported_for_this_sample']
                row['material_evidence'][field]=[{k:f[k] for k in ['fact_id','value','raw_value','unit','method','review_status','source_path','source_sha256','locator','row_ordinal','column_ordinal']} for f in evidence]
            stages=self.synthesis(doi=GLY,sample=cap['sample_name'])[0]['stages'];carbon=next(s for s in stages if s['stage']=='carbonization')
            row['carbonization_temperature_C']=carbon['temperature_C'];row['carbonization_duration_h']=carbon['duration_h']
            row['source_balanced_weight']=1/len(own)
            row['protocol_evidence']=[dict(d) for d in self.connection.execute("select document_key,path,sha256,role from source_documents where document_key in ('Glycogen','Glycogen_SI','Glycogen_Fig10') order by document_key")]
            row['limitations']='OneDOI only; samples share preparation/test source. No external-source fold possible. EISfitresponses and same-testretention/capacitance labels are not material predictors. ReportedA/g massbasis not physically unified.'
            result.append(row)
        return result

    def des_model_inputs(self,target='retention'):
        """Typed, un-imputed matrix. IDs, other outcomes and author± stay outside X."""
        rows=self.des_reported_inputs(target)
        names=list(DES_PREDICTORS)
        if target=='retention':names+=['cycle_count','cycle_voltage_lower_V','cycle_voltage_upper_V']
        return dict(purpose=rows[0]['purpose'],feature_names=names,
          X=[[r[k] for k in names] for r in rows],
          missing_mask=[[r[k] is None for k in names] for r in rows],
          y=[r['target_value'] for r in rows],
          author_plus_minus=[r['target_reported_uncertainty'] for r in rows],
          groups=[r['source_group'] for r in rows],
          sample_groups=[r['physical_sample_group'] for r in rows],
          row_ids=[r['row_id'] for r in rows],weights=[r['source_balanced_weight'] for r in rows],
          independent_source_groups=1,external_source_fold_possible=False,
          training_authorized=False,ordinary_aqueous_cycling_admitted=False,
          imputation='None; optional nulls remain null. Any future fitting/encoding must use training-fold evidence only.')

    def des_candidate_inputs(self,target='retention'):
        """Compatibility alias; readiness is explicit and purpose-specific in every row."""
        return self.des_reported_inputs(target)

def open_literature_database(database=None,expected_sha256=None):
    return LiteratureDatabaseV6(database,expected_sha256)
