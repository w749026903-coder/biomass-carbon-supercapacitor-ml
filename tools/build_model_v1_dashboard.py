"""Refresh authored v1.0 dashboard data from completed local logs; never fit."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / '模型v1.0_来源留出训练_20261022'


def read(path):
    return json.loads(path.read_text('utf-8'))


def build_snapshot():
    state = read(RUN / 'progress.json')
    data_path = RUN / 'dashboard/src/data.json'
    snapshot = read(data_path)
    label = {'selected':'v1.0选定模型','source_mean':'来源等权均值','legacy_mlp_noI':'原去电流MLP',
             'ridge_core_noI_100':'Ridge100·核心参数','ridge_material_noI_100':'Ridge100·加入材料制备'}
    scores = [dict(s, label=label[s['variant']], mae_low=s['vs_mean']['mae_ci_low'], mae_high=s['vs_mean']['mae_ci_high']) for s in state['metrics']]
    status = {k:v for k,v in state.items() if k not in ['events','metrics','predictions','candidates']}
    rows = {'status':[status], 'progress':state['events'], 'metrics':scores,
            'predictions':[dict(p,absolute_error=abs(p['predicted']-p['observed'])) for p in state['predictions']],
            'candidates':sorted(state['candidates'],key=lambda r:r['mae']), 'diagnosis':[read(RUN / 'diagnosis.json')]}
    source = {'provider':'Local reproducible Python / SQLite experiment',
        'files':[(RUN / p).relative_to(ROOT).as_posix() for p in ['training_plan.json','evaluation.sqlite','results.json','reserved_predictions.json','diagnosis.json']],
        'description':'v0.14三电极报告工况：开发35条/23来源；预留7条/7新增来源检验；最终42条模型另存。',
        'executedAt':state['updated_at'], 'caveats':['留出来源未参加旧模型拟合和评分，但原文审查已接触标签，并非前瞻盲测。',
            '开发CV用于选型；留出MAE6.88高于均值参照5.93，性能门槛未通过。','留出分数属于35条训练模型；全42条重训模型没有独立检验。'],
        'evidenceFlow':[{'title':'输入冻结','detail':'training_plan.json及frozen_run_hashes.json保存数据、代码、候选与来源切分。'},
                        {'title':'实际训练','detail':'evaluation.sqlite保存581条任务，534次完成的估计器拟合；每个来源总权重1。'},
                        {'title':'独立复算','detail':'tools/verify_model_v1.py独立复算指标、来源bootstrap及逐折统计；不重新拟合。'}],
        'metricDefinitions':[{'label':'来源等权MAE','definition':'先计算各来源内平均绝对误差，再对来源平均；单位为保持率百分点。'},
                            {'label':'95%描述性区间','definition':'7个检验来源5000次重采样；不包含重新拟合，不是单样品预测区间。'}]}
    snapshot.update(title='循环保持率模型 v1.0', generatedAt=state['updated_at'], buildStatus='complete',
                    queries={key:{'rows':value,'source':dict(source,description=source['description']+' '+key)} for key,value in rows.items()})
    data_path.write_text(json.dumps(snapshot,ensure_ascii=False,indent=2,allow_nan=False)+'\n', encoding='utf-8')
    print(json.dumps({'snapshot':str(data_path),'queries':{k:len(v) for k,v in rows.items()}},ensure_ascii=False))


if __name__ == '__main__':
    build_snapshot()
