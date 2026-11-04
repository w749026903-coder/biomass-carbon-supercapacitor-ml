"""Lock source-isolated NC-3 predictions before revealing its author endpoint."""

from pathlib import Path
import json
import math
import re
import subprocess
import sys
import warnings
import xml.etree.ElementTree as ET

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.prepare_small_sample_routes import read, write, sha, now
from tools.retention_corrected2e_v13 import environment
from tools.retention_shape_v4 import Encoder, estimator, expressed, weights
from tools.retention_suaeda_case_v16 import BASE, P14

P13 = BASE / '第十三轮_MK9纠错复验_20261104'
P21 = BASE / '第二十一轮_DDHPC双电极来源扩充_20261105'
P22 = BASE / '第二十二轮_外部验证来源盲态预留_20261105'
P23 = BASE / '第二十三轮_花椒壳早期盲态输入_20261105'
OUT = BASE / '第二十四轮_花椒壳外部预测锁定_20261105'
DOI = '10.1039/c9ra08319g'
ROUTES = {'early20':'.2','early10':'.1'}
GIT = ['git','-c',f'safe.directory={ROOT.as_posix()}']


def training_data():
    return {'early20':read(P21/'input_snapshot.json')['rows'],
            'early10':read(P13/'input_snapshot.json')['B_2E_early10']}


def blind_inputs():
    data = read(P23/'blind_early_input.json')
    evidence = read(P23/'verification.json')
    assert sha(P23/'blind_early_input.json') == evidence['evidence_hashes']['blind_early_input.json']
    assert data['source']['doi'] == DOI and data['source']['terminal_label'] is None
    assert data['terminal_values_exposed_for_this_candidate'] == evidence['candidate_terminal_label_exposed'] == 0
    return data


def freeze():
    assert not OUT.exists()
    blind = blind_inputs()
    training = training_data()
    rows = {k:[r['row_id'] for r in rr] for k,rr in training.items()}
    sources = {k:sorted({r['source_family'] for r in rr}) for k,rr in training.items()}
    assert [(len(rows[k]),len(sources[k])) for k in ROUTES] == [(29,23),(23,18)]
    assert all(blind['source']['source_family'] not in ss for ss in sources.values())
    assert read(P13/'completion.json')['status'] == 'complete_verified'
    assert read(P21/'verification.json')['status'] == 'verified'
    design = read(P21/'training_plan.json')
    assert design['environment'] == environment() and len(design['configurations']) == 8
    sealed_source = next(x for x in read(P22/'structural_screen.json')['results'] if x['doi']==DOI)
    guard = [Path(__file__),BASE/'research_goal.json',P13/'input_snapshot.json',P13/'completion.json',
             P14/'training_plan.json',P21/'input_snapshot.json',P21/'training_plan.json',P21/'verification.json',
             P22/'structural_screen.json',P23/'blind_early_input.json',P23/'verification.json',
             *(ROOT/f for f in ('data/current_retention_research.json','data/current_training_latest.json',
                               'tools/retention_v3_optimizer.py','tools/retention_shape_v4.py','tools/run_small_sample_routes.py'))]
    OUT.mkdir()
    plan = dict(frozen_at=now(),doi=DOI,sample=blind['source']['sample'],system='2E',target_cycle_count=5000,
                environment=environment(),protected={p.relative_to(ROOT).as_posix():sha(p) for p in guard},
                train_rows=rows,train_sources=sources,configurations=design['configurations'],primary=design['primary'],
                primary_window='early20',secondary_window='early10',planned_fits=16,author_label_accessed=False,
                endpoints_at_freeze=0,external_sources_accepted=0,
                criteria=read(BASE/'research_goal.json')['criteria'],
                comparison='Fixed eight configurations from P21, same fit rule. Early20 trains on P21; early10 uses P13 approved six-field inputs. Both windows have different eligible training pools.',
                test='One prospective source-excluded case, provisional lab independence. Only per-case errors and three baselines. R2/aggregate gates undefined for a single endpoint.',
                author_locator='Fig. 8(C) and linked electrochemical performance paragraph.',
                sealed_xml=dict(path=sealed_source['sealed_cache'],sha256=sealed_source['sha256']),
                reveal_gate='Exact predictions and pre-reveal verification must be in a verified origin/main commit before XML terminal access. No refitting after reveal.')
    write(OUT/'training_plan.json',plan)
    write(OUT/'freeze_receipt.json',dict(plan_sha256=sha(OUT/'training_plan.json'),fits=0,terminal_values=0))


def checked():
    path = OUT/'training_plan.json'
    plan = read(path)
    assert sha(path) == read(OUT/'freeze_receipt.json')['plan_sha256']
    assert all(sha(ROOT/p)==h for p,h in plan['protected'].items())
    assert environment()==plan['environment']
    return plan


def predict():
    plan = checked()
    blind = blind_inputs()
    with (OUT/'run_claim.json').open('x',encoding='utf-8') as claim:
        json.dump(dict(started_at=now(),plan_sha256=sha(OUT/'training_plan.json')),claim)
    result = {}
    for route,train in training_data().items():
        assert plan['train_rows'][route] == [r['row_id'] for r in train]
        assert plan['train_sources'][route] == sorted({r['source_family'] for r in train})
        assert blind['source']['source_family'] not in plan['train_sources'][route]
        f = blind['windows'][str(float(ROUTES[route]))]['features']
        last = f['last_early_retention_pct']
        test = dict(features=f,static_features=blind['source']['static_features'],last_early=last)
        w = weights(train)
        delta = np.array([r['target']-r['last_early'] for r in train])
        mu = float(np.average(delta,weights=w))
        sd = float(np.sqrt(np.average((delta-mu)**2,weights=w))) or 1.
        fits = []
        for c in plan['configurations']:
            e = dict(config_id=c['id'],family=c['family'],target_center=mu,target_scale=sd)
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter('always')
                try:
                    x = [expressed(r,c,'six') for r in train]
                    enc = Encoder().fit(x)
                    model = estimator(c)
                    mass = w*len(train)
                    kw = {'sample_weight':mass}
                    if c['kind']=='GPR':
                        model.set_params(alpha=c['parameters']['alpha']/mass)
                        kw = {}
                    model.fit(enc.transform(x),(delta-mu)/sd,**kw)
                    p = float(model.predict(enc.transform([expressed(test,c,'six')]))[0]*sd+mu+last)
                    assert math.isfinite(p)
                    e.update(status='complete',prediction_pct=p,encoder=enc.schema)
                except Exception as exc:
                    e.update(status='failed',error=repr(exc))
            e['warnings'] = [str(v.message) for v in caught]
            fits.append(e)
        linear = last+f['early_retention_slope_per_1000_cycles']*(f['target_cycle_count']-f['early_observed_cycle_count'])/1000.
        baselines = dict(training_mean=float(np.average([r['target'] for r in train],weights=w)),
                         early_persistence=last,early_linear=linear)
        result[route] = dict(train_rows=len(train),train_sources=len(plan['train_sources'][route]),fits=fits,baselines=baselines)
    events = [e for v in result.values() for e in v['fits']]
    assert len(events)==16
    write(OUT/'predictions_locked.json',dict(status='before_author_endpoint_access',predicted_at=now(),
          plan_sha256=sha(OUT/'training_plan.json'),blind_input_sha256=sha(P23/'blind_early_input.json'),
          terminal_label=None,external_sources_accepted=0,results=result,fits=16,
          failures=sum(e['status']=='failed' for e in events),warnings=sum(len(e['warnings']) for e in events)))


def git_bytes(*args):
    return subprocess.check_output([*GIT,*args],cwd=ROOT)


def reveal(lock_commit):
    plan = checked()
    assert re.fullmatch('[0-9a-f]{40}',lock_commit)
    remote_args = ['-c','http.proxy=http://127.0.0.1:7890','-c','https.proxy=http://127.0.0.1:7890',
                   '-c','http.version=HTTP/1.1','-c','http.sslBackend=openssl']
    assert git_bytes(*remote_args,'ls-remote','--exit-code','origin','refs/heads/main').split()[0].decode()==lock_commit
    locked = OUT/'predictions_locked.json'
    pre = OUT/'pre_reveal_verification.json'
    assert read(pre)['predictions_sha256']==sha(locked) and read(pre)['terminal_values_exposed']==0
    for path in (locked,pre):
        assert git_bytes('show',lock_commit+':'+path.relative_to(ROOT).as_posix())==path.read_bytes()
    prediction = read(locked)
    assert prediction['terminal_label'] is None and prediction['failures']==0
    source = ROOT/plan['sealed_xml']['path']
    assert sha(source)==plan['sealed_xml']['sha256']
    with (OUT/'reveal_claim.json').open('x',encoding='utf-8') as claim:
        json.dump(dict(started_at=now(),verified_remote_lock_commit=lock_commit,predictions_sha256=sha(locked)),claim)
    root = ET.parse(source).getroot()
    vals = []
    for p in root.findall('./body//p'):
        if not any('fig8' in (x.get('rid') or '').split() for x in p.findall('.//xref')):
            continue
        text = ' '.join(''.join(p.itertext()).split())
        found = re.search(r'Fig\.\s*8C,\s*still retaining\s+(\d+(?:\.\d+)?)\s*%\s+capacitance after\s+5000\s+times of charge/discharge',text,re.I)
        if found:
            vals.append(found[1])
    label, = vals
    truth = float(label)
    assert truth>0
    results = {}
    for route,data in prediction['results'].items():
        methods = [dict(config_id=e['config_id'],prediction_pct=e['prediction_pct'],abs_error_pp=abs(e['prediction_pct']-truth)) for e in data['fits']]
        base = {k:dict(prediction_pct=p,abs_error_pp=abs(p-truth)) for k,p in data['baselines'].items()}
        results[route] = dict(methods=methods,baselines=base,primary=next(e for e in methods if e['config_id']==plan['primary']))
    write(OUT/'case_result.json',dict(status='one_prospective_case_scored',doi=DOI,sample=plan['sample'],cycle_count=5000,
         original_author_text_value=label,author_retention_pct=truth,source_locator=plan['author_locator'],
         sealed_xml_sha256=sha(source),predictions_lock_commit=lock_commit,locked_predictions_sha256=sha(locked),
         results=results,r2=None,external_sources_accepted=0,goal_achieved=False,refits_after_reveal=0))


if __name__ == '__main__':
    if sys.argv[1]=='reveal':
        reveal(sys.argv[2])
    else:
        {'freeze':freeze,'predict':predict}[sys.argv[1]]()
