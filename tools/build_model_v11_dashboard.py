"""Author reviewed rows for the sequential optimization dashboard, without fitting."""
from pathlib import Path
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'模型逐项优化_v1.1_20261022'
sys.path.insert(0,str(ROOT))
from tools.train_model_v1 import read,write


def build():
    progress=read(RUN/'progress.json');result=read(RUN/'results.json')
    names={'v1_1_nested':'v1.1正值目标与内层选型','v1_recipe_same_cohort':'v1.0配方·同批来源重评','source_mean':'来源等权均值参照'}
    statuses=read(RUN/'optimization_checklist.json')
    for item in statuses['steps']:
        if item['id']==4:item['status']='complete'
        if item['id']==5:item['status']='implemented'
    write(RUN/'optimization_checklist.json',statuses)
    metrics=[dict(r,label=names[r['variant']]) for r in result['metrics']]
    predictions=[dict(p,observed_ratio=p['observed_pct']/100,predicted_ratio=p['predicted_pct']/100,
        error_pp=p['predicted_pct']-p['observed_pct'],absolute_error_pp=abs(p['predicted_pct']-p['observed_pct']))
        for p in read(RUN/'reviewed_predictions.json')]
    units=read(RUN/'unit_audit.json')
    examples=[{'type':'author_reported_3e','sample_name':r['sample_name'],'retention_pct':r['retention_pct'],
        'retention_ratio':r['retention_pct']/100.,'meaning':'原文报告高于初始参照；保留原值'} for r in units['above100_main_rows']]
    examples.append({'type':'v1.0_prediction','sample_name':'稻草AC·旧模型预测','retention_pct':101.23917325206921,
        'retention_ratio':1.0123917325206921,'meaning':'实际83.54%；预测高估17.70个百分点，不能当作活化证据'})
    support=[]
    for field,values in read(RUN/'semantic_coverage.json')['field_source_support'].items():
        support += [{'field':field,'category':category,'sources':count} for category,count in values.items()]
    queries={'status':[{k:v for k,v in progress.items() if k not in ['events','metrics','predictions']}],
        'progress':progress['events'],'metrics':metrics,'predictions':predictions,
        'checklist':statuses['steps'],'units':examples,'semantic_support':support}
    source={'provider':'Local frozen experiment and own-source literature audit',
        'files':[(RUN/p).relative_to(ROOT).as_posix() for p in ['training_plan.json','evaluation.sqlite','unit_audit.json','critical_source_review.json','semantic_feature_evidence.json','results.json','verification.json']],
        'executedAt':progress['updated_at'],'description':'同一42条/30已使用来源的探索性嵌套验证；保持率百分数与比例明确分开。',
        'caveats':['非新的独立检验；不把本轮4.75与旧7来源的6.88直接比较。','原文可超过100%；预测超过100%不证明活化。','工程与数值核验通过不表示科学精度达标；无单样品校准区间。'],
        'evidenceFlow':[{'title':'审查','detail':'277观察273有数值，五重点样品原文复核；保持原标签/冻结/来源。'},
                        {'title':'特征','detail':'三类语义源自v0.14已审方法；数值至少5训练来源，语义类别至少3训练来源才独立编码。'},
                        {'title':'实验','detail':'8候选，30外层来源留一；每外层5折内层选型，固定旧Ridge与均值参照；1301次拟合。'}],
        'metricDefinitions':[{'label':'保持率百分数','definition':'100×给定循环点电容/作者初始参照电容，不是概率。'},
                            {'label':'保持率比例','definition':'保持率百分数÷100；101.24%=1.0124。'},
                            {'label':'来源等权MAE','definition':'先计算每来源内平均绝对误差，再对来源平均，单位百分点。'}]}
    target=RUN/'dashboard/src/data.json'
    snapshot=read(target) if target.exists() else {'surface':'dashboard','filters':[],'status':'reviewed'}
    snapshot.update(title='循环保持率 · v1.1逐项优化',generatedAt=progress['updated_at'],buildStatus='complete',
        queries={key:{'rows':value,'source':dict(source,description=source['description']+' '+key)} for key,value in queries.items()})
    output=target if target.exists() else RUN/'dashboard_snapshot.json'
    write(output,snapshot);print(json.dumps({'snapshot':str(output),'queries':{k:len(v) for k,v in queries.items()}},ensure_ascii=False))


if __name__=='__main__':build()
