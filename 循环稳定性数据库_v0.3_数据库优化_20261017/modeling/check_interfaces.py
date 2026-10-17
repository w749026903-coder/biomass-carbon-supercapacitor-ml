"""Executable synthetic regression checks. Never supplies research training rows."""
import copy
import json
import pathlib
import sqlite3
import sys
import unittest
from prepare_dataset import ROOT, CONTRACT, preflight, validate_rows, connect
from benchmark_engine import (run_benchmark, source_disjoint, candidates_for, validate_config,
                              weights_for, splitter, make_model)

OUTPUT = ROOT/'modeling'/(sys.argv[1] if len(sys.argv)>1 else 'synthetic_interface_checks')

def synthetic_rows(groups=4, constant=False, empty_bet=False):
    rows = []
    for group in range(groups):
        for node in range(1+group%3):
            rows.append({'_synthetic':True,'record_id':f'SYNTH_{group}_{node}',
                'paper_id':f'SYNTH_P{group}','material_id':f'SYNTH_M{group}','cycle_test_id':f'SYNTH_T{group}',
                'study_group':f'SYNTH_G{group}','system':'2E_symmetric','method':'GCD','conflict':0,
                'retention_relation':'eq','cycle_count':1000*(node+1),'retention_pct':90. if constant else 88.+group-node,
                'current_density_A_g':1.+group,'electrolyte':f'UNIQUE_CATEGORY_{group}',
                'concentration_value':1.+group,'concentration_unit':'M','voltage_lower_V':0.,'voltage_upper_V':1.,
                'BET_m2_g':None if empty_bet or group==1 else 500.+group*100,'total_pore_volume_cm3_g':None if group==2 else 0.3+group/10})
    return rows

def small_config():
    cfg = copy.deepcopy(CONTRACT)
    cfg['split']['folds_up_to'] = 2
    cfg['tuning']['inner_group_folds_up_to'] = 2
    cfg['tuning']['candidate_budget_per_model'] = 2
    cfg['tuning']['budget_by_model'] = {'ridge':2}
    return cfg

class InterfaceChecks(unittest.TestCase):
    def test_01_zero_real_admission_and_no_fit(self):
        report = preflight()
        self.assertEqual(report['approved_rows'],0)
        self.assertFalse(report['training_performed'])

    def test_02_candidate_rejected(self):
        with self.assertRaisesRegex(ValueError,'admission'):
            validate_rows(synthetic_rows())

    def test_03_label_never_imputed(self):
        rows = synthetic_rows();rows[0]['retention_pct'] = None
        with self.assertRaisesRegex(ValueError,'retention_pct'):
            validate_rows(rows,require_admission=False)

    def test_04_invalid_required_values_rejected(self):
        for field,value in [('current_density_A_g',float('nan')),('voltage_upper_V',-1.),('cycle_count',1000.2),('electrolyte','')]:
            rows = synthetic_rows();rows[0][field] = value
            with self.subTest(field=field),self.assertRaises(ValueError):
                validate_rows(rows,require_admission=False)

    def test_05_real_repeated_node_guard(self):
        with connect() as c:
            rows = [dict(x) for x in c.execute("SELECT * FROM endpoint_review WHERE paper_id='R107' ORDER BY record_id")]
        self.assertGreaterEqual(len(rows),2)
        with self.assertRaisesRegex(ValueError,'leakage'):
            source_disjoint(rows[:1],rows[1:])

    def test_06_identity_group_consistency(self):
        rows = synthetic_rows();rows[1]['material_id'] = rows[0]['material_id']
        with self.assertRaisesRegex(ValueError,'multiple source groups'):
            validate_rows(rows,require_admission=False)

    def test_07_config_budget_seed_and_folds(self):
        import numpy as np
        cfg = small_config();specs = validate_config(cfg)
        self.assertEqual(len(candidates_for('random_forest',cfg,specs)),2)
        cfg['tuning']['candidate_budget_per_model'] = 3
        self.assertEqual(len(candidates_for('random_forest',cfg,specs)),3)
        g = np.array([f'G{i}' for i in range(10)])
        cfg['split']['folds_up_to'] = 3
        self.assertEqual(len(list(splitter(10,3,cfg).split(np.zeros((10,1)),groups=g))),3)
        cfg['split']['random_state'] = 71
        model = make_model('random_forest',specs['random_forest']['default'],1,2,cfg,specs)
        self.assertEqual(model.named_steps['estimator'].random_state,71)
        cfg['mlp_policy']['solver'] = 'adam';cfg['mlp_policy']['small_networks'] = [[3]]
        self.assertEqual(validate_config(cfg)['mlp']['grid']['hidden_layer_sizes'],[[3]])
        cfg['tuning']['candidate_budget_per_model'] = 0
        with self.assertRaises(ValueError):validate_config(cfg)

    def test_08_source_weight_totals_equal(self):
        import numpy as np
        g = np.array(['a','b','b','c','c','c']);w = weights_for(g)
        self.assertTrue(np.allclose([w[g==s].sum() for s in ['a','b','c']],2.))

    def test_09_forbidden_feature_and_random_early_stop_rejected(self):
        cfg = small_config();cfg['feature_sets']['protocol_only'].append('retention_pct')
        with self.assertRaisesRegex(ValueError,'Forbidden'):validate_config(cfg)
        cfg = small_config();cfg['mlp_policy']['early_stopping'] = True
        with self.assertRaisesRegex(ValueError,'forbidden'):validate_config(cfg)

    def test_10_full_nested_all_five_models_and_reproducibility(self):
        import numpy as np
        cfg = small_config()
        a = run_benchmark(synthetic_rows(),OUTPUT/'nested_a','plus_BET_pore',cfg,synthetic=True)
        b = run_benchmark(synthetic_rows(),OUTPUT/'nested_b','plus_BET_pore',cfg,synthetic=True)
        self.assertEqual(set(a),set(CONTRACT['models']))
        self.assertEqual(a,b)
        audit = json.loads((OUTPUT/'nested_a/fit_group_audit.json').read_text())
        self.assertTrue(any(x['context']['phase']=='inner' for x in audit))
        self.assertTrue(all(not set(x['train_groups']) & set(x['test_groups']) for x in audit))
        for name,result in a.items():
            self.assertEqual(len(result['folds']),2)
            self.assertTrue(all(len(f['inner_search'])<=2 for f in result['folds']))

    def test_11_constant_label_empty_BET_unknown_category_and_tiny_groups(self):
        result = run_benchmark(synthetic_rows(groups=2,constant=True,empty_bet=True),OUTPUT/'tiny_constant_empty_BET','plus_BET',small_config(),synthetic=True)
        for model,r in result.items():
            self.assertIsNone(r['pooled_R2'])
            self.assertTrue(all(f['selection_policy']=='predeclared_default_insufficient_inner_groups' for f in r['folds']))

    def test_12_preserve_previous_output(self):
        with self.assertRaises(FileExistsError):
            run_benchmark(synthetic_rows(),OUTPUT/'nested_a','plus_BET',small_config(),synthetic=True)

    def test_13_synthetic_label_required_and_one_group_refused(self):
        rows = synthetic_rows();rows[0]['_synthetic'] = False
        with self.assertRaisesRegex(ValueError,'Synthetic'):
            run_benchmark(rows,OUTPUT/'invalid_marker','plus_BET',small_config(),synthetic=True)
        with self.assertRaisesRegex(ValueError,'two groups'):
            run_benchmark(synthetic_rows(groups=1),OUTPUT/'invalid_group','plus_BET',small_config(),synthetic=True)

    def test_14_fit_failure_recorded(self):
        from unittest.mock import patch
        with patch('benchmark_engine.make_model',side_effect=RuntimeError('synthetic_injected_failure')):
            with self.assertRaisesRegex(RuntimeError,'synthetic_injected_failure'):
                run_benchmark(synthetic_rows(),OUTPUT/'injected_failure','protocol_only',small_config(),synthetic=True)
        status = json.loads((OUTPUT/'injected_failure/completion.json').read_text())
        self.assertEqual(status['status'],'failed')

    def test_15_preprocessing_and_target_statistics_train_only(self):
        import numpy as np
        cfg = small_config();specs=validate_config(cfg)
        model=make_model('mlp',specs['mlp']['default'],1,2,cfg,specs)
        X=np.array([[1.,'a'],[3.,'a'],[np.nan,'b']],dtype=object)
        y=np.array([70.,80.,90.])
        model.fit(X,y,estimator__sample_weight=weights_for(['a','a','b']))
        self.assertAlmostEqual(model.transformer_.mean_[0],80.)
        imputer=model.regressor_.named_steps['features'].named_transformers_['numeric'].named_steps['imputer']
        self.assertAlmostEqual(imputer.statistics_[0],2.)
        before=imputer.statistics_.copy()
        pred=model.predict(np.array([[99999.,'previously_unseen']],dtype=object))
        self.assertTrue(np.isfinite(pred).all())
        self.assertTrue(np.array_equal(before,imputer.statistics_))

    def test_16_weighted_mean_is_source_balanced(self):
        import numpy as np
        cfg=small_config();specs=validate_config(cfg)
        model=make_model('mean_baseline',{},1,2,cfg,specs)
        X=np.array([[1.,'a'],[2.,'b'],[3.,'b'],[4.,'b']],dtype=object)
        model.fit(X,np.array([20.,100.,100.,100.]),estimator__sample_weight=weights_for(['a','b','b','b']))
        self.assertAlmostEqual(model.predict(X[:1])[0],60.)

if __name__ == '__main__':
    OUTPUT.mkdir(exist_ok=False)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(InterfaceChecks)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    summary = {'kind':'SYNTHETIC_INTERFACE_CHECK_NOT_RESEARCH','tests_run':result.testsRun,
               'passed':result.wasSuccessful(),'failures':len(result.failures),'errors':len(result.errors),
               'research_training_performed':False}
    (OUTPUT/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    sys.exit(0 if result.wasSuccessful() else 1)
