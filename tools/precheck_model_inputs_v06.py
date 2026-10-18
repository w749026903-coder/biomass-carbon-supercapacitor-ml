"""Construct interfaces in the existing project ML environment; never fit."""
from pathlib import Path
import importlib.metadata,importlib.util,json
from prepare_training_inputs_v06 import VERSION

def check():
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.neural_network import MLPRegressor
    from xgboost import XGBRegressor
    spec=importlib.util.spec_from_file_location('_v06_preprocessing',VERSION/'preprocessing.py')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    contract=json.loads((VERSION/'data_contract.json').read_text(encoding='utf-8'))
    checks=[]
    for profile in ['reported_3e','reported_2e']:
        for scale in [False,True]:
            transformer=mod.make_preprocessor(contract['profiles'][profile]['features'],scale)
            assert not hasattr(transformer,'transformers_')
            checks.append({'profile':profile,'scale_numeric':scale,'constructed_unfitted':True})
    for cls in [RandomForestRegressor,MLPRegressor,XGBRegressor]:
        estimator=cls(random_state=20261018)
        assert not any(k in estimator.__dict__ for k in ['estimators_','coefs_','_Booster'])
        checks.append({'estimator':cls.__name__,'constructed_unfitted':True})
    return {'environment':'existing_v02_project_venv','versions':{k:importlib.metadata.version(k) for k in ['numpy','scipy','scikit-learn','xgboost']},'checks':checks,'estimator_fits':0,'new_packages_installed':False}

if __name__=='__main__':
    import sys
    result=check()
    if '--write-report' in sys.argv:(VERSION/'模型预检查.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))
