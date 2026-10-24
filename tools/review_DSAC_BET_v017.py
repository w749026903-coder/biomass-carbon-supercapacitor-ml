"""Arithmetic BET consistency audit of the provided adsorption points.

This does not create a replacement author-reported surface area or train an ML
model. Test every contiguous adsorption range, including two-point ranges, so
failure is not manufactured by a newly chosen minimum point-count threshold.
"""
from pathlib import Path
import hashlib,json,math,re,zipfile
ROOT=Path(__file__).resolve().parents[1];BATCH=ROOT/'持续补正_v017_20261024'
MEMBER='DSAC/BET/DS.txt'
def fit(points):
    x=[p['relative_pressure'] for p in points];q=[p['volume_adsorbed_cc'] for p in points]
    y=[a/(b*(1-a)) for a,b in zip(x,q)];xm=sum(x)/len(x);ym=sum(y)/len(y)
    slope=sum((a-xm)*(b-ym) for a,b in zip(x,y))/sum((a-xm)**2 for a in x);intercept=ym-slope*xm
    C=1+slope/intercept if intercept else None;qm=1/(slope+intercept) if slope+intercept else None
    transform=[n*(1-p) for n,p in zip(q,x)]
    increasing=all(b>=a for a,b in zip(transform,transform[1:]))
    p_observed=None
    if qm is not None:
        for i in range(len(q)-1):
            if q[i]<=qm<=q[i+1] and q[i+1]!=q[i]:p_observed=x[i]+(qm-q[i])*(x[i+1]-x[i])/(q[i+1]-q[i]);break
    p_theory=1/(math.sqrt(C)+1) if C is not None and C>0 else None
    criteria=dict(positive_C=C is not None and C>0,
        increasing_q_times_one_minus_p=increasing,
        monolayer_uptake_in_selected_range=qm is not None and min(q)<=qm<=max(q),
        monolayer_pressure_agreement_20pct=p_observed is not None and p_theory is not None and abs(p_theory-p_observed)<=.2*p_observed)
    return dict(points=len(points),relative_pressure_min=x[0],relative_pressure_max=x[-1],slope=slope,intercept=intercept,C=C,qm_sample_cc=qm,
        observed_monolayer_pressure=p_observed,theoretical_monolayer_pressure=p_theory,criteria=criteria,all_criteria_pass=all(criteria.values()))
def main():
    archive=BATCH/'retrieved/DSAC_author_data.zip'
    with archive.open('rb') as f:zipsha=hashlib.file_digest(f,'sha256').hexdigest()
    assert zipsha=='a3003f413d6103e658df9af9884e1d95a885730d06ffdab5440867f979d8c9d8'
    with zipfile.ZipFile(archive) as z:raw=z.read(MEMBER)
    s=raw.decode('cp1252');points=[]
    for line in s.splitlines():
        fields=line.split()
        if len(fields)!=8:continue
        try:vals=[float(x) for x in fields]
        except ValueError:continue
        points.append(dict(relative_pressure=vals[2],volume_adsorbed_cc=vals[3]))
    peak=max(range(len(points)),key=lambda i:points[i]['relative_pressure']);ads=points[:peak+1]
    assert len(points)==26 and len(ads)==13 and all(a['relative_pressure']<b['relative_pressure'] for a,b in zip(ads,ads[1:]))
    windows=[]
    for i in range(len(ads)-1):
        for j in range(i+2,len(ads)+1):windows.append(dict(start_point=i+1,end_point=j,**fit(ads[i:j])))
    assert len(windows)==78
    author_range=fit(ads[:7])
    # Independent control: the raw point audit must reproduce the reported
    # negativeC for the visible author fit range0.045..0.297, not only reject it.
    assert abs(author_range['C']-(-63.443))<.1,author_range['C']
    output=dict(archive_path=archive.relative_to(ROOT).as_posix(),archive_sha256=zipsha,member=MEMBER,
        member_sha256=hashlib.sha256(raw).hexdigest(),provided_points=points,adsorption_points=ads,
        windows_tested=len(windows),passing_ranges=[w for w in windows if w['all_criteria_pass']],
        author_reported_C=-63.443,recomputed_author_range=author_range,
        criteria_source='https://pubs.rsc.org/en/content/articlehtml/2022/ta/d1ta08021k',
        result='No tested contiguous range of the supplied adsorption branch satisfies allfour examined consistency criteria.',
        limits=['Only the supplied rounded26-point export reviewed; unprovided lower-pressure measurements cannot be reconstructed.',
            'Two-point fits were also included; no conclusion depends on a new minimum-three-point gate.',
            'No replacement BET, temperature, cycle reference or target is selected.',
            'This is a measurement-analysis quality flag; review current reported-protocol purpose separately and do not add a universal C-reporting requirement.'],
        BET_diagnostic_regressions=len(windows),ML_model_fits=0,windows=windows)
    assert not output['passing_ranges']
    p=BATCH/'DSAC_BET_consistency_audit.json'
    if (ROOT/'循环稳定性数据库_v0.17_原图标签补正_20261024/merge_manifest.json').exists():
        assert json.loads(p.read_text('utf8'))==output,'Sealed BET diagnostic differs; preserve it and investigate.'
    else:p.write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n','utf8')
    print(json.dumps(dict(raw_points=len(points),adsorption_points=len(ads),ranges_tested=len(windows),passing_ranges=0,recomputed_reported_C=author_range['C'],minimum_measured_relative_pressure=ads[0]['relative_pressure'],ML_model_fits=0),ensure_ascii=False))
if __name__=='__main__':main()
