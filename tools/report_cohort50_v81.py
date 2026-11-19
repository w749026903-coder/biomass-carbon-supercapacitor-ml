"""Audit scored folds independently and create the self-contained visual report."""
from pathlib import Path
import collections,csv,html,json,math,sqlite3,sys
import numpy as np
from sklearn.metrics import mean_absolute_error,mean_squared_error,r2_score
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.cohort50_models_v81 import ROOT,OUT,DEST,read,dump,collect,encode
import warnings
def main():
    esc=html.escape
    s=read(OUT/'results.json'); pred=read(OUT/'predictions.json'); plan=read(OUT/'plan.json');inp=read(OUT/'inputs.json')
    assert collect()==inp
    paper=list(csv.DictReader((DEST/'50篇文献清单.csv').open(encoding='utf-8-sig')));roster={r['DOI'] for r in paper}
    assert len(roster)==len(paper)==50
    warnings_by_task=collections.Counter()
    def sc(rs,m):
        y=np.array([r['y'] for r in rs]);p=np.array([r['pred'][m] for r in rs]);assert np.isfinite(p).all()
        c=collections.Counter(r['doi'] for r in rs);w=np.array([1/c[r['doi']] for r in rs]);cov=np.cov(y,p,aweights=w,ddof=0);return dict(r=float(cov[0,1]/np.sqrt(cov[0,0]*cov[1,1])),R2=float(r2_score(y,p,sample_weight=w)),MAE=float(mean_absolute_error(y,p,sample_weight=w)),RMSE=float(np.sqrt(mean_squared_error(y,p,sample_weight=w))))
    ncheck=0
    for t,rs in pred.items():
        ir=inp[t];truth={r['id']:(r['doi'],r['y']) for r in ir};assert len(rs)==len(ir)==len(truth);assert {r['id']:(r['doi'],r['y']) for r in rs}==truth
        for source in {r['doi'] for r in rs}:
            assert source in roster;train=[r for r in ir if r['doi']!=source and r['train']];test=[r for r in ir if r['doi']==source]
            with warnings.catch_warnings(record=True) as seen:
                warnings.simplefilter('always');X,Z=encode(train,test)
            assert all('invalid value encountered in sqrt' in str(item.message) for item in seen)
            warnings_by_task[t]+=len(seen);assert np.isfinite(X).all() and np.isfinite(Z).all()
        for k in rs[0]['pred']:
            assert all(math.isclose(s['scores'][t][k][m],v,rel_tol=1e-9,abs_tol=1e-10) for m,v in sc(rs,k).items());ncheck+=4
    aa={r['id'] for r in pred['direct_A']};bb={r['id'] for r in pred['early_B']};matched=aa&bb
    pair={t:sc([r for r in pred[t] if r['id'] in matched],'blend') for t in ('direct_A','early_B')}; papers=len({r['doi'] for r in pred['early_B'] if r['id'] in matched})
    assert papers==24 and len(matched)==30 and set(x['doi'] for x in pred['protocol50'])==roster
    names={'protocol50':'保持率：四项基本工况','direct_A':'保持率：八项材料与工况','early_B':'保持率：前20%曲线','specific_C':'比电容：材料与工况','rate_C':'较高电流下的比电容：已知1 A/g的比电容','BET':'BET比表面积：制备与独立表征'}
    units=plan['units']; alts={'ridge':'岭回归','RF':'随机森林','GB':'梯度提升','blend':'固定组合','fold_mean':'训练均值','measured_anchor':'实测起点直接沿用'}
    def tb(headers,rows):
        return '<table><thead><tr>'+''.join('<th>'+h+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+str(v)+'</td>' for v in r)+'</tr>' for r in rows)+'</tbody></table>'
    def fmt(x):return f'{x:.3f}'
    score_rows=[];md=[]
    for t,title in names.items():
        v=s['scores'][t]['blend'];n,d,tr=plan['coverage'][t];best=max(['ridge','RF','GB','blend'],key=lambda k:s['scores'][t][k]['r']);bv=s['scores'][t][best]['r']; rr=[title,f'{d} / {n}',fmt(v['r']),fmt(v['R2']),f"{v['MAE']:.2f}",f"{v['RMSE']:.2f}",units[t],f'{alts[best]} {bv:.3f}'];score_rows.append(rr);md.append('| '+' | '.join(rr)+' |')
    old=read(next(DEST.parent.glob('第七十九*/results.json')))['metrics']['mild18']
    obs='在同一批有两套输入的24篇、30条终点上，固定组合的材料工况预测 r＝%.3f、MAE＝%.2f 个百分点；早期曲线预测 r＝%.3f、MAE＝%.2f 个百分点。两者各自训练所用的论文范围不同，这证明在共同测试记录上后者表现更好，仍不能单独量化增加早期输入的因果贡献。'%(pair['direct_A']['r'],pair['direct_A']['MAE'],pair['early_B']['r'],pair['early_B']['MAE'])
    insight='50篇基本工况压力测试中，37篇可提供拟合数据，每次预测一篇时排除该篇全部记录。其余论文只接受预测。单列的敏感性记录含读图约186%的保持率，固定组合对这一条预测约96%，这会显著影响RMSE。此记录不训练、不裁到100%，也不因误差大而剔除。'
    hist=f"历史上，较窄的18篇温和早期曲线组曾有 r＝{old['r']:.4f}、R²＝{old['r2']:.4f}、MAE＝{old['mae']:.2f}个百分点。它说明这个小范围值得继续，不代表50篇已达标。没有一篇新盲测用于本轮。不同目标的MAE单位不同，不能横向排大小。"
    nexts='先补已有论文的曲线：19篇尚未进入早期曲线模型，其中7篇至少有一条记录满足1–6 M KOH、1–10 A/g、1000–10000圈的基本条件。优先核AHPC-850图4d、CMC-ZnK-800图8d、SAC-2图2f；确认前三成之前的图点时，实际只准入前20%内至少三个可定位点，排除库仑效率与双电极面板。能进几篇取决于原图，不能预先承诺。若目标是同一套温和工况下实测50篇，目前仅29篇具备对应基本条件，至少还缺21篇符合条件的论文，即使原图全部读得清也一样。'
    nexts=nexts.replace('确认前三成之前的图点时，实际只准入','只准入')
    head=['任务','论文 / 记录','Pearson r','预测R²','MAE','RMSE','误差单位','本轮算法中最高r（探索）'];title='固定50篇文献后的首次多模型比较'
    details='岭回归、随机森林、稳健梯度提升，以及在看分数前固定的岭回归与随机森林各半组合。每篇作为整体留出、每篇等权。50篇先锁定，再锁定算法；所有结果均是开发比较。看过多个模型后的最高值只能用于提出下一步假设。表格主列统一报告预设组合。模型输入从未使用论文编号、样品名或未来测量。BET预测排除同次吸附实验衍生的面积和孔容。倍率比电容的1 A/g实测值是合法的额外输入，不是长期循环起点。'
    stages='第80轮冻结50篇；第81轮完成480次拟合（160个任务×留篇组合，每组3种算法，固定组合无需另拟合）；本次交付复核所有逐条预测、来源和评分，未以复核增加拟合轮数。'
    tasks={t:{r['doi'] for r in v} for t,v in pred.items()}; htmlrows=[];paperindex=[]
    for r in paper:
        d=r['DOI']; uses=[names[t] for t in names if d in tasks[t]];paperindex.append(dict(doi=d,title=r['题名'],scored_in=uses));htmlrows.append([r['序号'],f'<a href="https://doi.org/{esc(d)}">{esc(d)}</a><br>{esc(r["题名"])}',esc(r['样品']),esc('；'.join(uses)),esc(r['下一步'])])
    report='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+title+'</title><style>body{font:16px/1.7 system-ui,"Microsoft YaHei",sans-serif;background:#f1f6f4;color:#17352e;max-width:1160px;margin:auto;padding:3vw}h1{font-size:clamp(23px,3vw,41px);line-height:1.2}h2{margin-top:36px}section{background:white;padding:20px;margin:16px 0;border-radius:10px;overflow-x:auto}table{border-collapse:collapse;text-align:left;width:100%;font-size:14px}td,th{padding:8px;border-bottom:1px solid #d6e5df}th{background:#edf6f2}a{color:#116c62}input{padding:8px;width:min(80%,450px)}</style><h1>'+title+'</h1><p>2026-11-20 · 生物质衍生碳电极 · 文献名单先于计算冻结</p><section><strong>50篇均有三电极保持率终点；目前没有一个新任务同时显示约50篇覆盖和 r＞0.90。</strong><p>'+stages+'</p>'+tb(head,score_rows)+'</section><section><h2>同一批论文再比一次</h2><p>'+obs+'</p><p>'+insight+'</p><p>'+hist+'</p></section><section><h2>下一批最有价值的工作</h2><p>'+nexts+'</p></section><section><details><summary>训练方法、指标和完整模型成绩</summary><p>'+details+'</p>'+tb(['任务','算法','r','R²','MAE','RMSE'],[[names[t],alts[k],*[fmt(v[m]) for m in ('r','R2','MAE','RMSE')]] for t,score in s['scores'].items() for k,v in score.items() if k in alts])+'</details></section><section><h2>锁定的50篇及实际用途</h2><input id="q" placeholder="输入 DOI、题名或样品名"><div id="papers">'+tb(['编号','DOI和题名','样品','实际评分的任务','核图安排'],htmlrows)+'</div></section><script>q.oninput=()=>document.querySelectorAll("#papers tbody tr").forEach(row=>row.hidden=!row.textContent.toLowerCase().includes(q.value.toLowerCase()))</script></html>'
    (OUT/'50篇文献与模型结果.html').write_text(report,encoding='utf-8')
    (OUT/'README.md').write_text('# '+title+'\n\n'+stages+' [逐篇名单与结果（可检索）](50篇文献与模型结果.html)。\n\n| '+' | '.join(head)+' |\n|'+'---|'*len(head)+'\n'+'\n'.join(md)+'\n\n'+details+'\n\n'+obs+'\n\n'+insight+'\n\n'+hist+'\n\n'+nexts+'\n\n分折编码复核：部分折中常数列加权方差引发标准化开方警告；检查每个折的编码矩阵与每条预测均为有限值，各个模型的指标已独立复算。见[audit.json](audit.json)、[冻结计划](plan.json)、[逐条预测](predictions.json)。\n',encoding='utf-8')
    dump(OUT/'audit.json',dict(metric_checks=ncheck,folds=sum(len(z) for z in tasks.values()),all_encodings_and_predictions_finite=True,scaler_sqrt_warning_counts=dict(warnings_by_task),matched_ids=sorted(matched),matched_counts=[len(matched),papers],matched_scores=pair,source_index=paperindex))
    print(ncheck,pair,warnings_by_task)
if __name__=='__main__':main()