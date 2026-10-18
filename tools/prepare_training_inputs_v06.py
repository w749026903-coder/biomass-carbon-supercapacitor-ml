"""Export reviewed inputs and group-safe splits. Does not fit any estimator."""
from pathlib import Path
import argparse,csv,hashlib,importlib.util,json,sys
ROOT=Path(__file__).resolve().parents[1]
VERSION=ROOT/'循环稳定性数据库_v0.6_报告工况训练就绪_20261018'

def module():
    spec=importlib.util.spec_from_file_location('_v06_export_api',VERSION/'ml_data.py')
    mod=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mod;spec.loader.exec_module(mod)
    return mod

def dump(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def export(output):
    """New directory only; raw categorical columns are deliberately not encoded here."""
    output=Path(output).resolve()
    if ROOT not in output.parents:raise ValueError('Output must remain within the project.')
    output.mkdir(exist_ok=False,parents=True)
    report={}
    with module().Database() as db:
        for profile,spec in db.contract['profiles'].items():
            ds=db.fetch(profile);matrix=ds.feature_matrix();groups=sorted(set(matrix['groups']))
            folds=ds.source_folds(len(groups))
            rows=[]
            for row in ds.rows:
                record={k:row.get(k) for k in ['endpoint_id','identity_key','source_group','source_year','system','method','retention_relation','retention_pct','source_weight']+ds.features}
                record.update({'current_denominator_status':row.get('current_denominator_status'),'physical_current_harmonized':False,'baseline_reference':row.get('baseline_reference',row.get('baseline_json')),'profile_review':row['profile_review'],'caveats_json':row.get('caveats_json')})
                rows.append(record)
            dump(output/(profile+'.json'),{'profile':profile,'dataset_fingerprint':ds.fingerprint(),'matrix':matrix,'rows':rows,'leave_one_source_out':folds,'research_training_performed':False})
            columns=['endpoint_id','source_group']+ds.features+['retention_pct','retention_relation','source_weight']
            with (output/(profile+'.csv')).open('w',encoding='utf-8-sig',newline='') as f:
                w=csv.DictWriter(f,fieldnames=columns,extrasaction='ignore');w.writeheader();w.writerows(rows)
            report[profile]={'rows':len(rows),'source_groups':len(groups),'features':len(ds.features),'loso_folds':len(folds),'dataset_fingerprint':ds.fingerprint()}
        dump(output/'preprocessing_contract.json',{
            'numeric':['cycle_count','reported_current_A_g','concentration_mol_L','cycle_voltage_lower_V','cycle_voltage_upper_V','BET_m2_g'],
            'categorical':['electrolyte','reference_electrode'],
            'reference_electrode':'3E only; never represent missing 2E reference as a numeric zero',
            'protocol':'Split by unified source group first. Fit encoders/scalers only on the training fold. Transform held-out sources with that fitted training-fold preprocessing. Hyperparameter selection, if later authorized, needs nested group splits.',
            'unseen_category':'One-hot handle_unknown=ignore; log unknown-category/domain-shift rates per held-out fold.',
            'optional_pores':'Not included in core matrices. Printed-unit ambiguity and missing values stay masked; any future imputation must be trained inside a training fold.',
            'sample_weight':'Each source has total weight 1 within the profile; all endpoints from a source stay in one fold.',
            'sensitivity':'2E core is a subset of residue, which is a subset of approximate. These datasets must not be concatenated or counted as independent samples.',
            'no_fits_executed':True})
        dump(output/'cohort_summary.json',report)
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    print(json.dumps(export(parser.parse_args().output),ensure_ascii=False))
