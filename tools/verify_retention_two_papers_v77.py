"""Recheck the paper endpoint, figure pixels, matched historical errors and revision lock."""
import csv, json, re, subprocess, sys
from pathlib import Path
import numpy as np
from pypdf import PdfReader
import pdfplumber
from retention_two_papers_v77 import ROOT, BASE, OUT, TEA, OIL, sha, save

def read(p):return json.loads(p.read_text(encoding='utf-8'))
def git(*cmd):return subprocess.check_output(['git','-c',f'safe.directory={ROOT.as_posix()}',*cmd],cwd=ROOT)
def main(folder):
    early=read(OUT/'early_only.json');lock=read(OUT/'locked_diagnostic.json');parents='6afdc9e28984e46b64ba3b2f74b3bc30e832502f';files={s['doi']:folder/s['filename'] for s in read(OUT/'source_receipts.json')};assert all(sha(files[r['doi']])==r['sha256'] for r in read(OUT/'source_receipts.json'))
    for name,rev in [('locked_diagnostic.json',parents),('early_only.json',lock['early_commit'])]:assert git('show',f'{rev}:{(OUT/name).relative_to(ROOT).as_posix()}')==(OUT/name).read_bytes()
    assert sha(OUT/'early_only.json')==lock['early_sha256'];p=PdfReader(files[TEA]);s=' '.join(p.pages[9].extract_text().split());y=float(re.search(r'GKN8 also showed consistent behavior.*?high retention of\s*([\d.]+)\s*%',s).group(1));assert y==99.4
    a=np.asarray(p.pages[8].images[0].image.convert('RGB')); yy=[]
    for pix in range(1194,1201):
        idx=np.where(a[430:520,pix].max(axis=1)<100)[0]+430;yy.append((idx[0]+idx[-1])/2)
    cap=lambda ry:85-(ry-22.5)*30/762.5
    init=early['pixel_axes']['initial_center_y'];end=float(np.median(yy));ratio=100*cap(end)/cap(init);band=[100*cap(end+3)/cap(init-3),100*cap(end-3)/cap(init+3)];assert band[0]<=y<=band[1]
    pred=lock['outputs'][0]; names=('p64','p67','training_source_mean','early_persistence','early_linear');err={k:abs(pred[k]-y) for k in names};assert err['p64']==err['p67'] and err['p64']>2 and err['early_persistence']<0.1
    p64=next(BASE.glob('第六十四轮*')); hp=read(p64/'predictions.json')['koh_1_to_6m_mild_early']['baselines']['early_persistence'];q=read(next(BASE.glob('第六十七轮*'))/'diagnostic_10000.json')['predictions'];src={r['row_id']:r for r in read(next(BASE.glob('第五十九轮*'))/'input_snapshot.json')['3E']};last={r['row_id']:r for r in hp};old=[];n_matched=0
    for r in q:
        arow=src[r['row_id']]; mol=arow['static_features']['concentration_mol_L'];
        if not 2<=mol<=6:continue
        n_matched+=1
        if arow['features']['target_cycle_count']!=1000:continue
        other=last[r['row_id']];assert r['observed']==other['observed'];old.append(dict(row_id=r['row_id'],source=r['source_family'],truth=r['observed'],p67=r['predicted'],persistence=other['predicted']))
    assert n_matched==20 and len(old)==2 and len(set(q['source'] for q in old))==1;assert all(abs(r['p67']-r['truth'])<abs(r['persistence']-r['truth']) for r in old)
    # Store the author's distinct statements without assigning the same test to another sample.
    for txt in ['100.5 %','101.6 %','99.4 %']:assert txt in s
    other=[dict(sample='CKN8',retention_pct=100.5,source='p10 body / p9 Fig 9',route='separate reference carbon'),dict(sample='CZN8',retention_pct=101.6,source='p10 body / p9 Fig 9',route='separate reference carbon'),dict(sample='GZN8',retention_pct=99,approximate=True,source='p9 body; p10 Table 5 and conclusions',route='text only for cycling; no same-name early trace; 1 A/g comparison row is not confirmed cycling current')];
    facts=list(csv.DictReader((OUT/'auxiliary_facts.csv').open(encoding='utf-8')));assert len(facts)==132;assert sum(q['role']=='separate_device_cycling' for q in facts)==3
    oilratio=20.95/22.52*100; assert abs(oilratio-93.01)<0.05
    save('reveal_and_checks.json',dict(prediction_lock_commit=parents,remote_main_verified_at_lock=True,observed_pct=y,author_value_resolution_pp=0.1,graph_read_pct=ratio,graph_read_envelope_pct=band,graph_terminal_center_y=end,graph_endpoint_capacitance_F_g=cap(end),author_minus_graph_pp=y-ratio,predictions_pct={k:pred[k] for k in names},absolute_error_pp=err,other_unpaired_or_reference_retention=other,old_same_horizon_rows=old,old_same_horizon_mae_pp={m:float(np.mean([abs(v[m]-v['truth']) for v in old])) for m in ['p67','persistence']},oil_ratio_from_rounded_capacitances=oilratio,auxiliary_fact_rows=len(facts),new_3e_diagnostic_sources=1,new_fully_blind_sources=0,new_fits_after_unsealing=0,strict_independent_sources_total=1,strict_high_BET_independent_sources_total=0,independent_r2=None,model_promoted=False,formal_acceptance=False,scope='Inputs and predictions frozen. Supplementary source-level check only: near-target proxy read during study identity check; no reclassification as strict blind.',scope_reading_caveat='Approximate graphical marker edges overlap; uncertainty band is pixel sensitivity, not a statistical confidence interval.'))
if __name__=='__main__':main(Path(sys.argv[1]))
