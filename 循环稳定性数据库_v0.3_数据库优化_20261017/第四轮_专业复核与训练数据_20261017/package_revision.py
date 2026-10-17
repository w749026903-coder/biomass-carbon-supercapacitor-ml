"""Package read-only preflight notebook, clean matrices, report and bounded merge manifest."""
from pathlib import Path
import contextlib, csv, hashlib, io, json, sys

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'modeling'))
from prepare_dataset import CONTRACT, connect, load_ready, preflight

def dump(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    pre=preflight()
    num=CONTRACT['required_conditions']+['BET_m2_g']
    for profile in CONTRACT['label_relations_by_profile']:
        rows=load_ready(profile)
        matrix=[{k:r[k] for k in ['record_id',*num,'total_pore_volume_cm3_g','retention_pct','retention_relation',
                                  'study_group','source_weight','current_denominator_status']} for r in rows]
        with (ROOT/'exports'/f'{profile}_训练矩阵.csv').open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(matrix[0]));w.writeheader();w.writerows(matrix)
    # A valid notebook with cell outputs executed in one namespace; no Jupyter/kernel installation claimed.
    cells=[]
    def markdown(text):cells.append({'cell_type':'markdown','metadata':{},'source':text.splitlines(True)})
    markdown('''# 循环稳定性训练数据预检

输出：指定循环次数与工况的电容保持率。默认七项输入见模型合同。

电流使用文献报告值，质量分母未知状态保留；本笔记本不拟合模型、不显示研究预测精度。
主集8条；含无机组分敏感性集10条；再含近似数值敏感性集11条。三者嵌套，不相加。

各代码单元已通过同一 Python 命名空间依次执行并保存输出；未使用原生 Jupyter 内核执行器。
可在具备本项目依赖的 Jupyter 环境中重新执行。路径仅用于读取此版本数据库。
''')
    code=[
        "from pathlib import Path\nimport sys, json\nROOT = Path("+repr(str(ROOT))+ ")\nsys.path.insert(0, str(ROOT/'modeling'))\nfrom prepare_dataset import load_ready, preflight, CONTRACT\nprint(json.dumps(preflight(), ensure_ascii=False, indent=2))\n",
        "rows = load_ready()\nfor r in rows:\n    print(r['record_id'], r['cycle_count'], r['retention_pct'], r['reported_current_A_g'], r['electrolyte'], r['concentration_value'], r['voltage_lower_V'], r['voltage_upper_V'], r['BET_m2_g'])\nprint('输入列:', CONTRACT['required_conditions'] + ['BET_m2_g'])\nprint('目标列: retention_pct; 不能作为输入')\n",
        "plans = json.loads((ROOT/'modeling/分组验证计划_未拟合.json').read_text(encoding='utf-8'))\nfor profile, folds in plans.items():\n    for fold in folds:\n        assert not set(fold['train_groups']) & set(fold['test_groups'])\n        assert len(fold['test_groups']) == 1\n    print(profile, '留一来源折数:', len(folds), '研究拟合次数:0')\nassert all(r['canonical_current_A_g'] is None for r in rows)\nprint('未知质量分母未被伪填；无目标插补；本笔记本不调用 fit。')\n"
    ]
    ns={'__name__':'__notebook__'}
    for i,source in enumerate(code,1):
        out=io.StringIO()
        with contextlib.redirect_stdout(out):exec(compile(source,f'notebook_cell_{i}','exec'),ns)
        cells.append({'cell_type':'code','execution_count':i,'metadata':{},'source':source.splitlines(True),
                      'outputs':[{'output_type':'stream','name':'stdout','text':out.getvalue().splitlines(True)}]})
    markdown('''## 如何解读

八个来源可以检查数据接口并开展探索性验证，但循环次数与材料/来源仍然纠缠，不能宣称已经学到完整退化轨迹。
稀有电解液在留出来源时可能成为未见类别；编码器能处理并不等于模型能可靠外推。
质量分母未知、温度与负载缺失都影响解释；按来源分组不能消除这些因素。

研究训练保持关闭。合成数据接口结果位于独立的 SYNTHETIC_INTERFACE_CHECK_NOT_RESEARCH 目录，不能作为论文性能。
''')
    notebook={'nbformat':4,'nbformat_minor':5,'metadata':{'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'},
                  'language_info':{'name':'python','version':sys.version.split()[0]},
                  'execution_method':'Sequential compile/exec in one namespace; stdout captured; no native Jupyter executor.'},'cells':cells}
    for i,cell in enumerate(cells):cell['id']='r4-'+str(i+1)
    dump(ROOT/'训练数据只读预检.ipynb',notebook)
    with connect() as c:
        coverage=dict(c.execute('''SELECT COUNT(BET_m2_g) AS BET,COUNT(total_pore_volume_cm3_g) AS total_pore,
                    COUNT(N_at_pct) AS N_at,COUNT(O_at_pct) AS O_at,COUNT(N_wt_pct) AS N_wt,COUNT(O_wt_pct) AS O_wt,
                    COUNT(mass_loading_mg_cm2) AS loading FROM modeling_effective_inputs''').fetchone())
        coverage['material_observation_events']=c.execute('SELECT COUNT(*) FROM material_observations').fetchone()[0]
    dump(ROOT/'现有表征字段覆盖_按端点计数.json',coverage)
    verified=json.loads((ROOT/'核验结果_r4.json').read_text('utf-8'))
    report='''# 第四轮数据交付说明

预测输出保持为：给定循环次数与测试工况的电容保持率。

本轮先重新学习测试规范、老化机理与相关建模论文，并重新核对原文，修正了此前把“必须统一到两片总质量”当作全部保持率数据准入前提的做法。没有猜质量分母，也没有改作者的电流和保持率。

## 可以直接读取的数据

| 用途 | 端点 | 材料 | 来源 | 标签/材料边界 |
|---|---:|---:|---:|---|
| 文献报告工况主集 `literature_core7_exact` | 8 | 8 | 8 | 作者精确报告点；按既有材料范围 |
| 含所报告无机组分的敏感性集 `literature_residue_sensitivity` | 10 | 9 | 9 | 增加 R112 同一曲线的两个节点，保留硅标记 |
| 再含近似数值的敏感性集 `literature_approx_sensitivity` | 11 | 10 | 10 | 增加 R020 AC 对照约89%，保留 approx |
| 严格统一物理电流口径子集 | 0 | 0 | 0 | 当前仍缺明确电流质量分母 |

前三个集嵌套，不相加；默认训练视图是8条的主集。这里“可训练”指能开展文献报告条件的探索性回归，不代表统一物理应力已经确定。与原先严格口径相比，发生的是输入含义和适用用途的明确修订，不能称作解决了8条电流分母缺证。

七项输入已经写入合同与代码：

1. 计划循环次数 `cycle_count`，模型内取 log10。
2. 文献报告循环电流 `reported_current_A_g`，保持原 A/g 数值。
3. 电解液种类 `electrolyte`。
4. 摩尔浓度 `concentration_value`，只对可精确换算的单位归一为 mol/L。
5. 器件循环电压下限 `voltage_lower_V`。
6. 器件循环电压上限 `voltage_upper_V`。
7. 循环前成品 BET `BET_m2_g`。

总孔容 `total_pore_volume_cm3_g` 为可选第八项，主集缺2条，不强行填实测值。R091印刷单位疑点仍屏蔽。主集每条七项输入与目标均齐全，没有填补目标或必需输入。CSV中 record_id、study_group、source_weight、关系和质量分母状态为追溯/划分/权重信息，不作为模型特征。

## 现有数据如何全部保留利用

126篇、141个来源文件、67个暂定材料、83个暂定测试、89个循环端点均保留。全部89端点有单行用途总表，以及按三个数据用途分别生成的267条准入判断。原有134条材料表征观察与字段证据全部导出，未因稀疏而删除。

按端点统计，现有 BET49条、有效总孔容35条、XPS N原子百分比7条/O原子百分比10条、N质量百分比1条/O质量百分比1条、负载4条。它们不是独立材料数，不能跨方法、样品或百分比口径乱拼；化学/制备信息可继续用于结构补充与后续模型扩展。

最大敏感性集仍有78条未进入本轮回归。它们按三电极、CV循环、凝胶、混合/半电池、不平衡质量、复合材料/范围待定以及实际缺证保留用途，不混入默认主集。部分记录只是继承此前复核并重新分配用途，未声称全部89条本轮都完成了全文逐字段审核。

重点暂缓项：SRC028六样品的器件电解液归属及GCD图负电压轴与两电极方法冲突；SRC112缺两电极自己的电解液与浓度；R107两万圈端点缺自身有效电压窗口；SRC123前作数据关联未结；R106缺循环电流；R012是mol/kg浓度，不能写成mol/L；近似“接近100%”、下界、缺失目标和配对冲突不改造成精确点值。

## 如何查看与复核

先看 `专业学习与数据修订依据.md`，再看 `prediction_input_contract.json`。`exports/` 内有三组训练矩阵与完整追溯数据。`cycling_v0_3r4.sqlite` 中 `training_ready` 为默认8条，`training_rows_r4` 包含按 profile 区分的三个集；不要不加 profile 过滤就合并训练。`training_ready_canonical_current` 保留原严格视图，`profile_admissions_r4` 单独记录新用途，旧 admissions 不伪改。

`训练数据只读预检.ipynb` 已顺序执行并保存输出，不拟合模型。命令行可在本项目原有机器学习环境执行 `modeling/prepare_dataset.py` 读取预检。模型合同暂关闭研究拟合。

默认使用留一论文来源验证，主集8折，两个扩展集9折和10折；每来源总权重一致。R112的两点在同组，不能跨折。编码、缩放与可选孔容插补在训练折完成。预设同样本去电流、去BET、加孔容对照，不按测试分数选择最有利数据用途。

## 验证与局限

本轮通过 **{checks} 项核验**。原141个来源文件和379个上轮产物指纹全部一致，原始标签、作者电流、旧审核记录均保留。五种模型接口仅使用完全人工合成数据完成15次拟合，无警告；研究数据拟合次数为0，因此没有模型精度结果。

8个来源仍很少，尤其缺少同材料在不同循环次数、不同工况的独立观察；大多数材料只有一个端点。部分电解液只有一个来源，留出该来源时会出现未见类别。不能由此宣称学到普遍退化轨迹、工况因果效应或可靠外推精度。未知电流质量分母、温度和负载缺失也未被分组验证消除。

本轮数据达到的是有明确用途和局限的探索性训练输入标准；并未把所有可得记录都宣称为高质量训练点。后续增加有效数据应继续取证、补多工况/多端点和独立来源，不能通过改标签、推断缺失条件或放松真实冲突来增加数量。
'''.format(checks=verified['checks_count'])
    (ROOT/'第四轮数据交付说明.md').write_text(report,encoding='utf-8')
    # Enumerate files after all substantive outputs; the manifest does not hash itself.
    files=[{'path':str(p.relative_to(ROOT)),'sha256':sha(p),'bytes':p.stat().st_size}
           for p in sorted(ROOT.rglob('*')) if p.is_file() and p.name!='merge_manifest.json' and '__pycache__' not in p.parts]
    manifest={'task_role':'database','revision':'v0.3r4','output_directory':str(ROOT),
              'target_unchanged':'capacitance_retention_pct_at_requested_cycles_and_protocol',
              'default_profile':'literature_core7_exact','preflight':pre,
              'validation_summary':{k:v for k,v in verified.items() if k!='checks'},
              'ready_for_merge':True,'merge_authority':'other designated merge task; no merge executed',
              'scientific_objective_all_available_records_admitted':False,
              'bounded_deliverable_complete':True,'research_training_performed':False,
              'proposed_contract_changes':[
                  'Use reported_current_A_g as literal literature-protocol covariate; unknown physical denominator retained; canonical subset remains separate.',
                  'Default profile8; explicitly nested residue10 and numeric-approx11 sensitivities. Legacy admissions unchanged.',
                  'Prepare leave-one-source-out folds; same-cohort omit-current sensitivity; fixed defaults for initial exploratory comparisons.'
              ],
              'unresolved':['Unknown cycling current mass denominators','Small and unevenly distributed sources/limited repeated horizons',
                            'SRC028 protocol/electrolyte inconsistency','SRC112 device electrolyte missing','R10720000 own window missing',
                            'SRC123 predecessor association','Other78 endpoints not qualified for largest present profile; see full disposition export'],
              'artifacts':files}
    dump(ROOT/'merge_manifest.json',manifest)
    print(json.dumps({'packaged_files':len(files),'notebook_executed_cells':len(code),'research_fit_calls':0},ensure_ascii=False))

if __name__=='__main__':main()
