"""Document this fixed experiment and export compact reusable results; no fitting."""
from pathlib import Path
import csv
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
RUN = ROOT / '模型v1.0_来源留出训练_20261022'


def read(path):
    return json.loads(path.read_text('utf-8'))


def write_json(path, value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def edit_preserving_eol(path, transform):
    blob = path.read_bytes()
    newline = '\r\n' if b'\r\n' in blob else '\n'
    text = blob.decode('utf-8').replace('\r\n','\n')
    revised = transform(text)
    if revised != text:
        path.write_bytes(revised.replace('\n',newline).encode('utf-8'))


def finish():
    import joblib
    result, verification, plan = [read(RUN / file) for file in ['results.json','verification.json','training_plan.json']]
    assert verification['passed'] and not verification['performance_gate_passed']
    inputs = read(RUN / 'data_snapshot.json')['records']
    predictions = read(RUN / 'reserved_predictions.json')
    with (RUN / 'reserved_predictions.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        fields = ['variant','candidate','endpoint_id','source_group','sample_name','observed','predicted','absolute_error','warnings']
        writer = csv.DictWriter(stream,fieldnames=fields)
        writer.writeheader()
        for row in predictions:
            record = {f:row.get(f) for f in fields}
            record.update(absolute_error=abs(row['predicted']-row['observed']),warnings='; '.join(row['warnings']))
            writer.writerow(record)
    with (RUN / 'development_metrics.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        rows = result['selection']['development_scores']
        writer = csv.DictWriter(stream,fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    coefficients = []
    for artifact in ['evaluated_development_model.joblib','model_v1_0.joblib']:
        model = joblib.load(RUN / artifact)
        names = []
        for item in model.encoder.schema:
            if item['kind'] == 'categorical':
                names += [item['field']+'='+v for v in item['vocabulary']]+[item['field']+'=<UNKNOWN>']
            elif item['enabled']:
                names.append(item['field'])
                if item['missing_indicator']:
                    names.append(item['field']+'=<MISSING>')
        assert len(names)==len(model.estimator.coef_)
        coefficients.append({'artifact':artifact,'intercept_retention_pct':float(model.center+model.scale*model.estimator.intercept_),
            'coefficients':[{'encoded_field':name,'retention_pp_per_encoded_unit':float(value*model.scale)} for name,value in zip(names,model.estimator.coef_)],
            'interpretation':'Associational standardized-input coefficients, not causal material-design effects.'})
    write_json(RUN / 'model_coefficients.json',coefficients)
    card = {'model_version':'1.0', 'run_id':plan['run_id'], 'status':'exploratory_performance_gate_failed',
        'selected_specification':result['selection']['specification'],
        'scientific_reliability_approved':False, 'model_files':verification['model_hashes'],
        'primary_target':'capacitance_retention_pct at specified cycle_count and reported protocol',
        'material_scope':'biomass-derived porous carbon', 'system':'three electrode', 'method':'GCD',
        'data_version':'0.14', 'data_fingerprint':plan['dataset_fingerprint'],
        'evaluated_fit':{'rows':35,'sources':23,'artifact':'evaluated_development_model.joblib'},
        'final_research_fit':{'rows':42,'sources':30,'artifact':'model_v1_0.joblib','independent_test_available':False},
        'reserved_primary_metrics':next(x for x in result['reserved_metrics'] if x['variant']=='selected'),
        'current_feature_used':False, 'optional_material_features_used_in_selected_model':False,
        'optional_material_features_compared':True, 'labels_clipped':False,
        'warning_policy':'Missing core inputs, wrong electrode system, wrong GCD method and <1000 cycles rejected; unseen categories/out-of-training numeric ranges flagged. In-range does not mean accurate.',
        'uncertainty':'No calibrated individual prediction interval; bootstrap scores are conditional and based on7sources.',
        'distribution':'Authorized project Git repository only; no inference service or public model hosting.',
        'limitations':result['limits']}
    write_json(RUN / 'model_card.json',card)
    environment = read(RUN / 'environment.json')['versions']
    (RUN / 'requirements-lock.txt').write_text('\n'.join(f'{name}=={version}' for name,version in environment.items())+'\n',encoding='utf-8')
    report = '''# 循环保持率模型 v1.0（研究版）

模型、预测调用、可视化和复现记录已完成，但本轮**没有通过可靠泛化的性能验收**。版本号代表一套可调用的研究交付，不代表精度已经达标。

直接打开[可视化结果](模型v1.0训练结果.html)。本地预览运行时可访问 http://127.0.0.1:8767/ 。图表、5种方案筛选、逐材料预测、开发集25方案和实际进度均来自运行日志；离线页保存完整结果。

## 数据、计划与真实训练

用户本轮明确授权重新训练并创建v1.0。使用v0.14已准入三电极主集42条/30来源，目标为给定圈数与作者报告工况下的电容保持率。数据库、原文、冻结与旧实验不改。

先按DOI与旧v0.10快照求差，固定7个此前未参加旧模型拟合/评分的来源；其余35条/23来源用于留一来源交叉验证选型。新增7来源的标签在原文审查时已见过，不称为前瞻盲测或完全未接触的外部验证。开发CV用于选择，不能作为独立精度结论。

拟合前固定[training_plan.json](training_plan.json)与输入快照。比较23个学习器配置及2个常数参照：Ridge、RBF核岭、浅层ExtraTrees、小型MLP、原去电流MLP配方。共581任务，其中534次实际估计器拟合，0收敛警告，用时21.45秒。没有在看过留出成绩后加候选或换模型。

材料制备信息进入11个候选，逐折实际启用过15种有足够来源支持的材料/制备字段，含孔体积、孔径、微孔面积、Raman、明确原子N/O、负载、活化和预碳化参数；碳化温度仅部分训练折满足门槛。每字段至少5个训练来源；未知值以训练折来源等权均值填补，并附缺失标记。未把模糊XPS百分比当at%，未把工序混在一起，未用论文ID作预测特征。

## 固定留出检验

开发集按来源等权MAE选中去电流核心参数Ridge，alpha=10；开发CV MAE为3.266。这是选型分数。模型没有被强制使用更多字段，材料候选最好开发MAE3.325，未胜过核心候选。

| 7来源检验方案 | MAE（百分点） | RMSE | R² |
|---|---:|---:|---:|
| v1.0开发集选定模型 | 6.876 | 8.952 | -1.727 |
| 来源等权均值参照 | 5.926 | 7.278 | -0.802 |
| 原去电流MLP配方，同一开发集重训 | 6.929 | 9.876 | -2.319 |
| 预定Ridge100，仅核心 | 6.227 | 7.859 | -1.102 |
| 预定Ridge100，加入材料制备 | 6.216 | 7.919 | -1.134 |

选定模型MAE的描述性95%区间为[3.03,11.31]；相对均值ΔMAE=+0.950，区间[-0.424,2.605]；相对原MLPΔ=-0.053，区间[-1.291,1.043]。5000次配对来源bootstrap仅基于7篇，未计重新拟合不确定性，不能包装成单样品预测区间。两种Ridge100是预先固定的对照，不因其留出成绩更低而事后替换主模型。

新检验来源更难：来源等权标签均值96.26%→91.40%，低于91%的来源从开发2/23变为留出4/7。OAC623实际85.50、预测98.52；稻草AC实际83.54、预测101.24，两项占86.06%平方误差。NaOH在开发集中未见。模型不能稳定地区分这些来源；分布差异和低标签来源稀少有直接证据，但不能把唯一原因归结为文献数量、某一个参数或论文权重。

新增材料参数确实被用于实验，但本轮没有可靠增益。相同Ridge100配置加入材料后的留出MAE仅降0.010个百分点，不能据此宣称有效。原来的2.85分数来自31条/23来源旧评估，与本轮7来源新检验不直接可比。

## 模型文件与调用

- [model_v1_0.joblib](model_v1_0.joblib)：按已经选定配方，用全部42条/30来源重训的研究模型。**这份全量模型尚无独立精度检验**。
- [evaluated_development_model.joblib](evaluated_development_model.joblib)：只用35条/23来源拟合，能复现上表v1.0留出成绩。
- [model_card.json](model_card.json)、[model_schema.json](model_schema.json)：状态、用途、变量定义、编码/缺失处理、训练范围及文件哈希。原子百分比与质量百分比、3E与2E继续分开。
- [model_coefficients.json](model_coefficients.json)：两个模型的实际系数，只作关联解释，不作因果设计依据。
- [inference_example.json](inference_example.json)：合规字段示例。全量模型已经训练过该示例，调用仅验证接口。

在仓库根目录使用已有项目环境，无需安装依赖：

```powershell
& '循环稳定性数据库_v0.2_20261017/.venv/Scripts/python.exe' -B tools/predict_model_v1.py --model '模型v1.0_来源留出训练_20261022/model_v1_0.joblib' --input '模型v1.0_来源留出训练_20261022/inference_example.json'
```

核心字段应按模型schema定义提供。电解液与参比用训练词表的字符串；A/g仍是作者口径。字段齐全、范围内或没有警告均不代表预测可靠。本轮选定模型去电流是开发集的选择结果，不是重新否定未知电流分母的经验用途。不要把2E、非水系、CV或未准入来源直接传入此模型；不要加载不可信的joblib。

## 验证、复现与后续

[verification.json](verification.json)覆盖所有581任务、逐折来源隔离与字段统计、独立指标和配对区间重算、模型序列化/预测复现、607项旧封版载荷及32个原件。核验正确不表示预测性能达标。桌面1440px、390px窄屏、3图、全部5筛选及离线快照由隔离Edge核验；内置CUA控制启动失败，未声称通过内置浏览器检查。

[evaluation.sqlite](evaluation.sqlite)保留可恢复的逐任务审计；[development_metrics.csv](development_metrics.csv)、[reserved_predictions.csv](reserved_predictions.csv)可直接分析。依赖版本见[requirements-lock.txt](requirements-lock.txt)，代码与输入哈希见[frozen_run_hashes.json](frozen_run_hashes.json)。完成目录拒绝覆盖；重现需新建目录并审查冻结计划，不能原位重跑一次性prepare或修改旧结果。

接下来应补独立低保持率来源及现有来源中可区分低稳定性的材料/制备证据，积累真正的新检验来源。本轮7来源以后已使用，不得再称为未接触检验集。没有充分新证据前，不继续围绕这7篇追分，也不发布推理服务。

方法接口依据：[来源分组验证](https://scikit-learn.org/1.7/modules/cross_validation.html#cross-validation-iterators-for-grouped-data)、[核岭与样本权重](https://scikit-learn.org/1.7/modules/generated/sklearn.kernel_ridge.KernelRidge.html)、[MLP权重与参数](https://scikit-learn.org/1.7/modules/generated/sklearn.neural_network.MLPRegressor.html)。接口文档不能代替本项目科学准入规则。
'''
    (RUN / 'README.md').write_text(report,encoding='utf-8')
    knowledge = '''# v1.0模型：新增来源检验与失败结果（2026-10-22）

本页记录本项目的有界实验，不把小样本结果推广为普遍建模规则。证据为[冻结计划](../../模型v1.0_来源留出训练_20261022/training_plan.json)、[结果](../../模型v1.0_来源留出训练_20261022/results.json)、[诊断](../../模型v1.0_来源留出训练_20261022/diagnosis.json)及[逐任务审计](../../模型v1.0_来源留出训练_20261022/evaluation.sqlite)。

用户本轮授权新的适配v1.0模型，覆盖本轮旧的只筹备边界。主集42条/30来源不变；此前未用于模型拟合/评分的7来源按与旧来源DOI求差预留，另35条/23来源做LOSO选型。原文审查已经接触这些标签，因此不是完全盲测。训练折编码、支持数、目标尺度和权重均不读取留出来源。

候选同时比较核心与材料制备参数、报告电流与去电流；每可选字段要求5个训练来源，不能用同论文多行凑支持数。源均衡统计先在每来源内平均，再对来源平均。XPS只有明确at%及原有严格原子字段进入N/O原子特征；wt%另列；工序不合并。11种材料候选已经实际训练，不能因赢家仍是核心参数就声称新提取数据没被使用。

开发选定Ridge核心去电流alpha10，CV MAE3.266；7来源检验MAE6.876，原MLP同一开发集重训6.929，来源均值5.926。相对均值Δ+0.950、描述性95%区间[-0.424,2.605]；相对MLPΔ-0.053、区间[-1.291,1.043]。534次实际拟合、581任务、0收敛警告。这不能宣称误差改进成立，更不能拿旧31条的2.85直接比较。

开发与检验来源等权标签均值96.26%和91.40%；低于91%的来源占比2/23和4/7。OAC623、稻草AC占86.06%平方误差；NaOH训练未见。它们支持分布变化和低标签来源薄弱这一观察，不能证明唯一因果归因。添加材料参数的Ridge100同配方对照只降低0.010个百分点MAE，证据不足。来源权重已均衡，问题不等同于某一大论文贡献过多行。

全42条重训模型已经保存，配方不因检验成绩改变；它包含原检验7来源，不能把35条训练模型的留出精度冒称为这份全量模型的独立验证。训练分数另存为resubstitution。模型为研究调用版，性能门槛未通过，无校准单样品区间，不发布服务。

后续：这7个来源已消耗为检验资料，不能再次称为新检验。继续搜集/审查独立困难来源及可辨别稳定性的自身证据；新实验应固定新计划与独立检验边界，不能围绕已看过的7篇追分。未知电流质量分母的经验用途决策保持；去电流仅是本次开发选择，不重新开启已决门槛。

接口依据：[分组验证](https://scikit-learn.org/1.7/modules/cross_validation.html#cross-validation-iterators-for-grouped-data)、[KernelRidge](https://scikit-learn.org/1.7/modules/generated/sklearn.kernel_ridge.KernelRidge.html)。本项目选择、观测结果与库接口事实分别记录，不能把接口文档当作科学效果保证。
'''
    (ROOT / 'docs/knowledge/v1模型与新增来源检验_20261022.md').write_text(knowledge,encoding='utf-8')
    heading='## 当前模型 v1.0：有界训练与新增来源检验（2026-10-22）'
    state_text=heading+'''

[v1.0报告与调用](../模型v1.0_来源留出训练_20261022/README.md)已完成：v0.14主集42条/30来源，35条/23旧来源LOSO选型，7新增来源固定留出；25候选/参照、581任务、534次实际拟合，0收敛警告。开发集选定去电流核心Ridge alpha10；材料制备参数已用于11个候选，逐折支持至少5来源。

留出MAE6.876、RMSE8.952、R²=-1.727；同一开发集原MLP6.929、均值5.926。性能门槛未通过，不能声称改进可靠。开发与检验低于91%的来源2/23对4/7，OAC623/稻草AC占86.06%平方误差。原文审查见过标签，7来源并非前瞻盲测，后续也不能再称全新检验。

[可视化结果](../模型v1.0_来源留出训练_20261022/模型v1.0训练结果.html)保存真实进度和5方案筛选；本地8767预览已建。分别保存35条已评估模型和42条全量研究模型；后者没有独立精度检验，不发布服务。独立核验所有任务/指标/折内变换、607项旧载荷、32原件、序列化和浏览器交互。数据库指针仍v0.14，原标签/成员/冻结/旧实验保持。

接续先读[知识与经验](knowledge/v1模型与新增来源检验_20261022.md)。本轮已结束，不原位重跑prepare/train；保留冻结计划和已使用检验来源记录。优先补独立低保持率来源及现有自身材料证据，后续实验另定计划，不能根据本轮留出成绩继续调参。

'''
    edit_preserving_eol(ROOT/'docs/CURRENT_STATE.md', lambda t:t if heading in t else t.replace('## 当前数据库 v0.14',state_text+'## 当前数据库 v0.14',1))
    root_text='''## 当前模型 v1.0（2026-10-22）

[训练报告与调用](模型v1.0_来源留出训练_20261022/README.md)、[可视化进度与结果](模型v1.0_来源留出训练_20261022/模型v1.0训练结果.html)：534次实际拟合；35条/23来源选型、7来源检验，最终42条/30来源研究模型另存。新参数已经进入11种候选；选定核心去电流Ridge，留出MAE6.88，原MLP6.93、均值5.93，**性能门槛未通过**，不宣称可靠改进。数据库继续使用下方v0.14，旧实验与原文保持。

'''
    edit_preserving_eol(ROOT/'README.md', lambda t:t if '## 当前模型 v1.0' in t else t.replace('## 当前数据库 v0.14',root_text+'## 当前数据库 v0.14',1))
    row='| 最新模型 v1.0 | [报告与调用](../模型v1.0_来源留出训练_20261022/README.md)、[交互结果](../模型v1.0_来源留出训练_20261022/模型v1.0训练结果.html) | 534次拟合/581任务；35条23来源选型、7来源检验，MAE6.88差于均值5.93；性能未过关。42条全量研究权重另存、无独立精度检验；旧7来源不再是新检验 |\n'
    edit_preserving_eol(ROOT/'docs/WORKSPACE_MEMORY.md',lambda t:t if '| 最新模型 v1.0 |' in t else t.replace('|---|---|---|\n','|---|---|---|\n'+row,1).replace('| 当前模型诊断 |','| 历史模型诊断 |'))
    entry='17. [v1.0模型、来源预留、参数候选利用与未通过的性能检验](knowledge/v1模型与新增来源检验_20261022.md)\n\n'
    edit_preserving_eol(ROOT/'docs/KNOWLEDGE_BASE.md',lambda t:t if entry in t else t.replace('## 当前有效结论',entry+'## 当前有效结论',1))
    decision='''
## 2026-10-22：v1.0新模型授权与结果

用户明确要求重新训练、可调整模型安排并创建适配本项目的v1.0。本轮授权对应模型v1.0_来源留出训练_20261022/training_plan.json：有界候选、整来源选型、7新增来源固定检验及42条全量研究模型。534次拟合完成，性能门槛未通过，未发布服务；已用检验来源不能再次称全新。全量重训模型没有独立检验，35条模型的检验成绩不得转嫁。旧封版数据库授权字段保留历史。后续新实验仍须新计划和独立检验边界。详见[v1知识记录](v1模型与新增来源检验_20261022.md)。
'''
    edit_preserving_eol(ROOT/'docs/knowledge/建模用途决策.md',lambda t:t if '## 2026-10-22：v1.0新模型授权与结果' in t else t+decision)
    agent_line='- 2026-10-22用户明确授权重新训练并创建适配v1.0；本轮冻结计划见`模型v1.0_来源留出训练_20261022/training_plan.json`。534次拟合/581任务已完成，7新增来源检验MAE6.88，差于均值5.93，性能门槛未通过；全42条研究权重与35条已评估权重分开。已用7来源不得再称全新检验，不根据其成绩继续追加候选。后续新实验另定计划，不覆盖旧数据或结果，不发布服务。\n'
    edit_preserving_eol(ROOT/'AGENTS.md',lambda t:t if agent_line in t else t.replace('- 后续检索优先三电极；',agent_line+'- 后续检索优先三电极；',1))
    print(json.dumps({'documented':True,'fits_added':0,'model_version':'1.0','performance_gate':False},ensure_ascii=False))


if __name__ == '__main__':
    finish()
