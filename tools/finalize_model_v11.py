"""Document sequential improvements, preserve limitations, and seal task-owned outputs."""
from pathlib import Path
import csv,json,subprocess,sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.train_model_v1 import read,write,sha
from tools.finalize_model_v1 import edit_preserving_eol
RUN=ROOT/'模型逐项优化_v1.1_20261022'


def finish():
    verification=read(RUN/'verification.json');visual=read(RUN/'dashboard_visual_verification.json')
    assert verification['passed'] and visual['passed']
    results=read(RUN/'results.json');review=read(RUN/'output_review.json')
    raw=read(RUN/'outer_predictions.json');annotated=read(RUN/'reviewed_predictions.json')
    assert all(a['predicted_pct']==b['predicted_pct'] and a['observed_pct']==b['observed_pct'] for a,b in zip(raw,annotated))
    checklist=read(RUN/'optimization_checklist.json')
    # The page says implemented; rendered verification is recorded separately without modifying its snapshot.
    checklist.update(rendered_verification_passed=True,model_accuracy_improvement_established=False)
    write(RUN/'optimization_checklist.json',checklist)
    rows=[dict(r,observed_ratio=r['observed_pct']/100,predicted_ratio=r['predicted_pct']/100,
        error_pp=r['predicted_pct']-r['observed_pct']) for r in annotated]
    fields=['variant','endpoint_id','source_group','sample_name','observed_pct','observed_ratio','predicted_pct','predicted_ratio','error_pp','input_warnings']
    with (RUN/'predictions.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
        for row in rows:
            d={k:row.get(k) for k in fields};d['input_warnings']='; '.join(d['input_warnings']);writer.writerow(d)
    card={'model_version':'1.1','status':'exploratory_accuracy_gate_not_passed','scientific_reliability_approved':False,
        'data_version':'v0.14','rows':42,'sources':30,'selected_specification':results['selected_specification'],
        'output_units':{'predicted_retention_pct':'percent','predicted_retention_ratio':'dimensionless pct/100'},
        'target_parameterization':'log(retention_pct/100), inverse100*exp; positive, no upper cap',
        'upper_clipping':False,'legitimate_main_observations_above100':[101.35,106.3,109.2],
        'primary_metrics':results['metrics'][0],'validation':results['evaluation'],
        'fresh_independent_validation_available':False,'final_all_data_model_has_own_independent_test':False,
        'material_semantic_candidates_selected_in_outer_folds':17,'total_outer_folds':30,
        'final_model_uses_material_semantic_block':results['new_semantic_features_used_in_selected_model'],
        'reliable_design_value':None,'calibrated_prediction_interval':None,
        'model_sha256':results['model_sha256'],'source_mean_baseline_mae':results['metrics'][2]['mae'],
        'note':'All sources already used; small descriptive gain versus old recipe is not established. Correct units and positive numbers do not imply reliable prediction.'}
    write(RUN/'model_card.json',card)
    (RUN/'README.md').write_text('''# v1.1逐项优化：保持率单位、语义特征与预测解释

前5项已实施并核验；独立困难来源、剩余样品审查与可靠精度尚未解决。入口：[双单位交互面板](v1.1逐项优化结果.html)、[逐项清单](optimization_checklist.json)、[模型说明](model_card.json)。这是研究改进版，性能验收未通过。

## 1. 单位与大于1

保持率比例R=给定循环点电容/作者初始参照电容，百分数=100×R。截图101.24是101.24%，对应1.0124；保持率不是概率，有证据时可以超过1。原文CCL109.2%、NPC106.3%、CA-AA101.35%都保留。CA-AA的3E101.35与2E102分开，不能用摘要器件值替换。

这不替旧模型预测辩护：稻草AC真实83.54%，旧预测101.24%，高估17.70个百分点。预测高于初始值不能当作真实活化证据。此前仅表头标%不够醒目，新页每个保持率单元格同时显示百分数、比例。

[单位审查](unit_audit.json)覆盖277观察、273个有数值保持率；没有负值，也没有0<数值≤1的明显比例误填信号。4个空值保持为空。全审查集20条大于100，其中包括未准入/冻结观察；该扫描不证明20条全部有效。主集3条大于100已按自身证据核查，未截断为100。

## 2. 逐样品原文复核

[五重点样品复核](critical_source_review.json)保存原件路径、哈希、定位和解释。CCL主文明确初始值109.2%；NPC先下降再回升至106.3%；CA-AA自身3E101.35区别于器件；稻草AC自身83.54区别于AC-ZnO89.98和库仑效率75；OAC85.5等于损失14.5，不能误读成0.855%。现行核心、标签、成员、冻结与数据库指针保持。

## 3. 把已有方法信息转成语义特征

42条/30来源补齐三个可追溯的候选字段：活化剂类别、活化工艺状态、原料来源类别。源自v0.14已经核读的自身方法，见[逐记录证据](semantic_feature_evidence.json)及[类别来源支持](semantic_coverage.json)。不把没有写单独活化等同于明确未活化，不从CCL/AMFS缩写猜物种，不用样品ID或标签定义类别，未猜活化剂配比。

新类别仅在训练折有至少3个来源时独立编码，稀有/未知单列；可选数值仍要求至少5个训练来源，均值、尺度、缺失填充和支持数只读训练折。磷酸类只有2来源，部分类别只有1来源，多行不能凑独立支持。已有32项数值候选与新语义一起参与材料块，不能把整个块的表现归因于某个语义字段。

拟合前发现芝麻残渣与锯末两个明确原料漏入分类词表，已纠正，保留[最初计划与修订记录](planning_history/amendment_record.json)。修订发生在0次估计器拟合时，没有因看过新成绩修改类别。

## 4. 正值目标与相同来源对照

[固定计划](training_plan.json)：8个候选，30折外层来源留一、各5折内层选型。目标log(保持率比例)，反变换100×exp；保证输出为正，保留超过100%的可能，不做上限截断。所有42条原值包括增长样品保持，不排除困难标签。1301次实际拟合、1332任务、0收敛警告，约23秒。

| 同一42条/30来源评估 | MAE（百分点） | RMSE | R² |
|---|---:|---:|---:|
| v1.1正值目标与内层选型 | 4.752 | 6.273 | -0.232 |
| 固定v1.0配方在同批来源重评 | 4.775 | 6.204 | -0.205 |
| 来源等权均值参照 | 4.370 | 5.836 | -0.067 |

v1.1相对旧配方ΔMAE=-0.024，描述性95%区间[-0.425,0.389]，不能确认改善；相对均值+0.382，仍未胜过简单参照。全部来源已经看过，语义设计也受到旧误差诊断启发，本轮不是新的独立检验。不能声称从旧7来源的6.88“降到4.75”，因为评估对象不同。

材料/语义块在17/30个外层训练选择中被采用，说明它确实参与了选择与留出预测；全42条最终配方仍选核心去电流Ridge100。没有证明材料块或某个新语义字段的单独收益。结果见[results.json](results.json)、[逐折审计](evaluation.sqlite)、[原始预测](outer_predictions.json)。

本轮42条交叉验证预测恰好都不超过100%，这是本批数据与配方的结果，不是新增了100%上限；模型对未来输入仍可能给出大于100%的研究预测。真实增长样品仍可能被低估。

## 5. 预测解释、调用与验证

[模型权重](model_v1_1.joblib)是全42条重训研究模型，没有自己的独立检验。工程调用明确输出predicted_retention_pct与predicted_retention_ratio，保留above_initial_reference、输入支持警告及reliable_for_design=false。CLI另外给出reliable_design_value=null。没有校准单样品预测区间，不能把没有范围警告视为可靠。

```powershell
& '循环稳定性数据库_v0.2_20261017/.venv/Scripts/python.exe' -B tools/predict_model_v11.py --model '模型逐项优化_v1.1_20261022/model_v1_1.joblib' --input '模型逐项优化_v1.1_20261022/inference_example.json'
```

示例是全量模型已训练过的记录，只验证接口。只加载可信项目模型；3E、GCD、>=1000圈及核心工况需明确给出。输入百分数与比例不可混用，未知电流质量分母的既定经验用途继续有效。

[verification.json](verification.json)149159项独立检查覆盖逐折来源隔离、训练统计/类别支持、标签与单位、配对区间复算、序列化、295个旧v1.0载荷和32原件。后处理提示只用保存的训练折schema，不改原始预测或分数，见[output_review.json](output_review.json)。桌面/390px窄屏、3图、3筛选、全部42条风险状态、单位与离线页通过隔离Edge检查；临时预览服务检查后关闭。

## 6. 仍需完成的数据与科学问题

独立低保持率来源、不同活化剂/电解液的来源支持，以及剩余表图/SI提取不足仍未解决。另定位同一CA论文3个自身样品及BET/保持率，见[候选清单](additional_sample_candidates.json)；它们没有自动入库，也不能算3个新来源。后续须逐测试完成共同协议、窗口、参比、残留/材料和去重审查，再版本化合并。不能把本轮工程改动或数值变正包装成精度已达标，也不围绕已看过的分数无限追加候选。

科学出处：[CA论文自身3E与2E循环保持率](https://pubs.rsc.org/en/content/articlehtml/2024/ra/d3ra07014j)。CCL/NPC等原件见本轮critical_source_review的本地定位。接口方法：[按来源分组验证](https://scikit-learn.org/1.7/modules/cross_validation.html#cross-validation-iterators-for-grouped-data)。
''',encoding='utf-8')
    knowledge='''# 保持率单位与逐项优化经验（2026-10-22）

证据：[v1.1报告](../../模型逐项优化_v1.1_20261022/README.md)、[单位审查](../../模型逐项优化_v1.1_20261022/unit_audit.json)、[原文复核](../../模型逐项优化_v1.1_20261022/critical_source_review.json)、[固定计划](../../模型逐项优化_v1.1_20261022/training_plan.json)。

保持率不是概率，比例R=C(N)/Cref、百分数=100R；101.24%=1.0124。主集确有101.35、106.3、109.2%的作者观测，保留原值，不统一裁至100。预测高于初始参照只是一种模型输出，不能当作真实活化证据；稻草AC旧预测101.24对实测83.54仍是严重高估。单元格同时标%与比例，接口用两个明确字段，不能只给无单位数字。

全库277观察中273有数值，扫描未见负数或0<值≤1的明显比例混入信号；这不是全部标签正确的证明。全审查集20个>100包含未准入记录；仅本轮重点自身证据完成明确复核。CA-AA3E101.35与器件102、稻草AC83.54与AC-ZnO89.98/库仑效率75分别保留。

方法字符串不是不能利用。将已审活化剂、工艺状态、原料来源投影为三类语义候选，保留原词、证据、未知。没有说明单独活化不等于明确无活化，缩写不猜物种，未经核读不补配比。数值至少5训练来源、语义类别至少3训练来源才编码；同篇多行不增加来源支持。拟合前发现两项分类漏词，保留修订前计划/输入，0次新拟合时修正，不按成绩改词表。

用户授权逐项优化后，固定8候选及正值目标，完成1301次拟合/1332任务。log(R)反变换保证正值但不设上限。探索性嵌套来源验证在同一42条/30已使用来源上比较：v1.1 MAE4.752、原配方4.775、均值4.370；差异相对原配方区间[-0.425,0.389]，未证明精度改善。不得把旧7来源6.88与本轮4.75直接比较。语义材料块在17/30外层训练选择中使用；全量最终仍选核心去电流Ridge100，不宣称语义单独收益。

模型的工程正确、数值为正、输入范围内与预测准确是不同层次。保留raw研究预测，明确reliable_for_design=false、CLI推荐值null、无校准单样品区间。后处理只能根据保存的训练折schema补支持警告，不能改分数或冒称重新验证。全量重训权重不继承不存在的独立检验。

独立困难来源和剩余自身表图/SI仍须继续处理；同论文3个CA新样品只是待审候选，不自动入库、不算新来源。旧数据库、冻结与旧实验保留。来源：[CA论文](https://pubs.rsc.org/en/content/articlehtml/2024/ra/d3ra07014j)。
'''
    (ROOT/'docs/knowledge/保持率单位与逐项优化_20261022.md').write_text(knowledge,encoding='utf-8')
    heading='## 当前模型 v1.1：保持率单位与逐项优化（2026-10-22）'
    state=heading+'''

[本轮报告与调用](../模型逐项优化_v1.1_20261022/README.md)、[双单位交互面板](../模型逐项优化_v1.1_20261022/v1.1逐项优化结果.html)：277观察/273数值单位扫描、5重点样品原文复核、42条三类语义投影已完成。101.24%=比例1.0124；主集3条真实>100保留，未统一上限截断。旧预测稻草AC高估仍被明确标识。

新固定实验8候选、30外层/5内层来源验证，1301次拟合/1332任务、0警告。相同42条/30已用来源：v1.1 MAE4.752，原配方4.775，均值4.370；改进区间跨0，精度未达标，不可与旧7来源6.88直接比较。正值输出无100上限；语义材料块在17/30外层选择中使用，最终全量仍选核心去电流Ridge100。

每个保持率数值明确%与比例，接口返回可靠性false、CLI设计推荐值null，无单样品校准区间。149159项核验、295旧v1载荷和32原件保护；桌面/窄屏、3图、3筛选和离线通过，临时预览检查后关闭。新权重为42条研究重训，无新独立检验；数据库仍v0.14，不覆盖v1.0。

接续：读[单位与优化经验](knowledge/保持率单位与逐项优化_20261022.md)及本轮清单。前5项实现；独立困难来源、更多表图/SI及同论文3个CA候选逐测试准入尚未完成。不要原位重跑prepare/amend/train，不根据本轮外层成绩追加候选，不把正值或工程通过当性能通过。

'''
    edit_preserving_eol(ROOT/'docs/CURRENT_STATE.md',lambda text:text if heading in text else text.replace('## 当前模型 v1.0',state+'## 历史模型 v1.0',1))
    short='''## 当前模型 v1.1：单位与逐项优化（2026-10-22）

[报告与调用](模型逐项优化_v1.1_20261022/README.md)、[双单位交互页](模型逐项优化_v1.1_20261022/v1.1逐项优化结果.html)：保持率明确显示%和比例，原文3条>100保留；三类工艺/原料语义候选、正值目标、风险输出已实现。1301次拟合，同批42条/30来源MAE4.752、旧配方4.775、均值4.370，**精度未达标**。不与旧7来源6.88直接比较；数据库仍v0.14，旧结果保持。

'''
    edit_preserving_eol(ROOT/'README.md',lambda text:text if '## 当前模型 v1.1' in text else text.replace('## 当前模型 v1.0',short+'## 历史模型 v1.0',1))
    entry='18. [保持率百分数/比例、真实增长与预测错误、语义投影和有界优化经验](knowledge/保持率单位与逐项优化_20261022.md)\n\n'
    edit_preserving_eol(ROOT/'docs/KNOWLEDGE_BASE.md',lambda text:text if entry in text else text.replace('## 当前有效结论',entry+'## 当前有效结论',1))
    row='| 最新模型 v1.1 | [报告与调用](../模型逐项优化_v1.1_20261022/README.md)、[双单位结果](../模型逐项优化_v1.1_20261022/v1.1逐项优化结果.html) | 前5项实现；273数值单位审查、三类语义/正值模型、1301拟合；同批MAE4.752仍差于均值4.370，精度未达标，独立困难来源与候选准入仍需处理 |\n'
    edit_preserving_eol(ROOT/'docs/WORKSPACE_MEMORY.md',lambda text:text if '| 最新模型 v1.1 |' in text else text.replace('|---|---|---|\n','|---|---|---|\n'+row,1).replace('| 最新模型 v1.0 |','| 历史模型 v1.0 |'))
    line='- 2026-10-22用户授权“列出改进地方，一个一个优化”。v1.1计划见`模型逐项优化_v1.1_20261022/training_plan.json`：单位/5样品/语义/正值目标与风险提示完成，1301拟合/1332任务。同批42条30来源MAE4.752、旧配方4.775、均值4.370，未证明精度改善；均为已用来源探索，不是新独立测试。保持率不是概率，真实>100不裁至100；模型预测增长不当作实验证据。独立困难来源和候选入库仍需处理，不围绕已看分数追加调参。\n'
    edit_preserving_eol(ROOT/'AGENTS.md',lambda text:text if line in text else text.replace('- 后续检索优先三电极；',line+'- 后续检索优先三电极；',1))
    decision='''
## 2026-10-22：逐项优化与保持率单位

用户进一步授权列清单逐项优化。本轮v1.1限定单位/重点原文/语义投影、正值目标和同批来源嵌套对照，1301拟合完成，精度未达标。比例与百分数均明确输出；保持率可以高于1，不统一裁100%，预测高值不当实验证据。所有来源已使用，不包装独立测试；后续新实验仍固定计划。原数据及v1.0保持，详见[本轮知识](保持率单位与逐项优化_20261022.md)。
'''
    edit_preserving_eol(ROOT/'docs/knowledge/建模用途决策.md',lambda text:text if '## 2026-10-22：逐项优化与保持率单位' in text else text+decision)
    duplicate=RUN/'dashboard/.data-app-offline/exports/v1.1逐项优化结果.html';delivered=RUN/'v1.1逐项优化结果.html'
    if duplicate.exists():
        assert sha(duplicate)==sha(delivered);size=duplicate.stat().st_size;duplicate.unlink()
        write(RUN/'workspace_cleanup.json',{'deleted_path':duplicate.relative_to(ROOT).as_posix(),'bytes_released':size,
            'preserved_path':delivered.relative_to(ROOT).as_posix(),'sha256':sha(delivered),'originals_deleted':0,
            'basis':'Only this task byte-identical ignored export removed after delivered HTML passed rendered verification.'})
    paths=['models/v1_1/__init__.py','models/v1_1/model.py']+[p.relative_to(ROOT).as_posix() for p in (ROOT/'tools').glob('*model_v11*') if p.is_file()]
    for file in RUN.rglob('*'):
        if not file.is_file() or file.name=='run_manifest.json':continue
        relative=file.relative_to(ROOT).as_posix()
        ignored=subprocess.run(['git','-c','safe.directory='+ROOT.as_posix(),'check-ignore','--quiet',relative],cwd=ROOT,capture_output=True)
        if ignored.returncode==1:paths.append(relative)
        elif ignored.returncode!=0:raise RuntimeError('Ignore check failed')
    payloads=[{'path':p,'bytes':(ROOT/p).stat().st_size,'sha256':sha(ROOT/p)} for p in sorted(set(paths))]
    write(RUN/'run_manifest.json',{'run_id':'retention-v1.1-sequential-20261022','local_work_complete':True,
        'first_five_improvement_steps_implemented':True,'all_scientific_gaps_resolved':False,'scientific_reliability_approved':False,
        'actual_estimator_fits':1301,'tasks':1332,'verification_checks':149159,'old_v1_payloads_protected':295,
        'original_files_protected':32,'upper_clipping':False,'source_database_unchanged':True,'outputs':payloads})
    print(json.dumps({'sealed':len(payloads),'bytes':sum(r['bytes'] for r in payloads),'accuracy_gate':False},ensure_ascii=False))


if __name__=='__main__':finish()
