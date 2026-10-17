"""Readable handoff, executable read-only notebook, and signed scoped deliverables."""
from pathlib import Path
import sqlite3,json,csv,hashlib,contextlib,io,sys

ROOT=Path(__file__).resolve().parent
PARENT=ROOT.parent/'第二轮_全量利用与输入定稿_20261017'
sys.stdout.reconfigure(encoding='utf-8')
summary=json.loads((ROOT/'准入闭环结果.json').read_text('utf-8'))
checks=json.loads((ROOT/'核验结果_r3.json').read_text('utf-8'))
c=sqlite3.connect((ROOT/'cycling_v0_3r3.sqlite').as_uri()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
rows=[dict(r) for r in c.execute('SELECT e.record_id,e.paper_id,e.doi,e.sample_name,e.cycle_count,e.retention_pct,e.current_density_A_g,d.primary_disposition,m.* FROM endpoint_effective_review e JOIN admission_decisions_r3 d USING(record_id) JOIN mass_definition_audits m USING(record_id) ORDER BY e.record_id')]
questions=[]
for r in rows:
    extra=''
    if r['record_id']=='R107_CY02':extra='另需20000次对应的循环窗口，不能借用10000次节点。'
    if r['paper_id']=='SRC123':extra='另需与2016前作的批次/曲线关联证据；前作全文仍未取得。'
    questions.append({'record_id':r['record_id'],'DOI':r['doi'],'sample':r['sample_name'],
      'cycles':r['cycle_count'],'reported_current_A_g':r['current_density_A_g'],
      'current_denominator':'待来源确认：双片总活性质量，还是指定单片活性质量',
      'positive_active_mass_mg':None,'negative_active_mass_mg':None,
      'direct_source_or_author_statement':None,'canonical_current_A_g':None,
      'required_evidence':r['remaining_required_evidence'],'additional_gap':extra,
      'current_review_locator':r['current_basis_evidence']+'; '+r['capacitance_basis_separately_reported']})
with (ROOT/'仅剩关键缺证_待补信息.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(questions[0]));w.writeheader();w.writerows(questions)
(ROOT/'仅剩关键缺证_待补信息.json').write_text(json.dumps(questions,ensure_ascii=False,indent=2),'utf-8')

contract=json.loads((PARENT/'prediction_input_contract.json').read_text('utf-8'))
contract.update(schema_version='retention-input-contract-v1.1-scoped-r3',
 training_view='training_ready',optional_pore_view='training_ready_pore',
 admission_policy='Strict canonical current basis; field-scoped optional issues masked before use; missing definitions remain blocked.',
 scientific_admission_count=summary['training_ready'],training_authorized=False)
contract['r3_clarifications']=[
 'Core7 does not require optional pore volume. Uncertain values are masked, not silently repaired.',
 'The optional pore variant uses the same admitted cohort; missing values remain allowed for later fold-only imputation.',
 'Baseline may be the author plotted start normalized to100pct, with exact cycle index retained as unknown.',
 'Independence_checked denotes a bounded source and grouping review, not statistical independence of same-paper endpoints.',
 'Freeze clearance addresses explicit record scope/conflict holds; missing current or window is still blocked by its own gate.',
 'Eligibility never follows merely from the existence of seven numeric/categorical inputs.']
(ROOT/'prediction_input_contract.json').write_text(json.dumps(contract,ensure_ascii=False,indent=2),'utf-8')

table='\n'.join(f'| {r["record_id"]} | {r["sample_name"]} | {r["cycle_count"]} | {r["retention_pct"]:g} | {r["current_density_A_g"]:g} | '+('电流分母；对应20k循环窗口' if r['record_id']=='R107_CY02' else '电流分母；2016前作关联' if r['paper_id']=='SRC123' else '电流分母')+' |' for r in rows)
report=f'''# 第三轮逐条准入核查结果

日期：2026-10-17。输出始终是循环稳定性：给定计划循环次数和测试条件下的电容保持率。本轮没有拟合研究模型。

## 当前结果

尚未达到用户要求的“全部可得数据均正式准入”。本轮能由取得的材料解决的输入/审核缺口已经写入第三轮库；严格七输入主模型正式准入仍为0。不能把审查完成、字段齐全、程序通过或无重复DOI当成正式准入。

| 主候选10条的检查 | 第二轮通过 | 第三轮通过 |
|---|---:|---:|
| 来源/材料归属 | 10/10 | 10/10 |
| 测试协议 | 8/10 | 9/10 |
| 保持率基准 | 5/10 | 10/10 |
| 来源关联及验证分组审查 | 0/10 | 9/10 |
| 专项冻结范围解除 | 0/10 | 9/10 |
| 循环电流质量分母 | 0/10 | 0/10 |
| 七项输入原始值非空 | 8/10 | 9/10 |
| 正式准入 | 0/10 | 0/10 |

“来源分组审查通过”仅指可得资料范围内已审查关联并形成分组；并不证明绝对独立。同文多终点仍同组。专项冻结解除也不替代电流定义等独立检查。

## 已解决的具体问题

1. 修复可选孔体积问题拖住整个七输入主模型的逻辑。R091印刷单位疑点仍开放，模型侧强制把该孔体积置空。八输入扩展也保留该记录在相同队列中，待将来仅在训练折内处理缺失。不会拿不可靠的0.68直接用，也不会擅改印刷单位。
2. 取得并核验四份真实补充材料：R091、R111、SRC035及R104。R111/SRC035来自出版方静态附件；R091来自Springer；R104通过Europe PMC取得与DOI匹配的补充PDF。检索元数据、ZIP及附件不重复计作论文。
3. R111新SI FigS3A/B显示同一ACK-700器件0–1V，已补齐器件协议。它是同一器件的协议关联证据，不声称取得了循环仪原始日志。
4. SRC035新SI TableS1明确O-PC-700的总孔体积0.53cm³/g，微孔体积0.40另列。已补总孔体积并关闭“缺SI查不到孔体积”。表S2的物种内部百分比没有当成全材料元素含量。
5. 五条基准从原图核实：R093 Fig8e、R103 Fig7c、R104 Fig10a、R111 Fig5F、SRC035 Fig8g。接受作者图示100%起始归一化，精确循环编号仍为未知，不捏造cycle1。
6. 对8篇/9条候选完成可得语料范围来源分组审查。126篇规范化DOI、题名和正文SHA无重复，只作为诊断的一部分；结合原文制备、样品对应和跨文样品提及核查。R091缩写在R041命中的是其他HPCS复合材料；SRC035/SRC124的共同单位/作者被记录，但材料分别是桂花O-PC和棉浆MHDHPC。R107两条终点强制同组。SRC123与2016前作仍不判独立。
7. 从原文同名成品表征补齐11条终点BET、合计11条终点总孔体积，并补R020/SRC112器件窗口；这些终点中的近似标签、金属残余和其他限制均未因此解除。R020单片电流措辞位于非对称段，未借给对称AC循环。

## 当前每条主候选还缺什么

| 记录 | 样品 | 循环次数 | 保持率/% | 原报电流/A·g⁻¹ | 阻碍 |
|---|---|---:|---:|---:|---|
{table}

其中8条已经只剩电流归一化这个关键缺口。R107_CY02还缺20k节点对应窗口；SRC123_CY02还缺前作关联结论。R091不可靠的孔体积已不再作为整条记录的阻碍。

电流的共同问题是：文章定义了电容公式中的单片或双片质量，但没有足够明确地把该质量与循环试验的A/g定义对应。R104另有“current-to-mass ratio”措辞，但与后续电容式的m仍不足以唯一核定循环分母。不能从电容式、能量式、放电时间、一般习惯或“负载相近”反推出分母，更不能为了增加行数一律除以2。

## 可得数据的范围与用途

数据库保留126篇、141份登记来源、67个暂定材料、83个暂定测试、89个正式候选终点；原有3条恢复信息继续隔离暂存。BET覆盖49终点/37材料/30篇，总孔体积35/27/21。这些是字段覆盖，不是训练样本数。

全部89条有实时准入判定。其中29条原分流为水系对称GCD候选：10条本轮完成重点准入核查，另外19条受短循环、非点值标签、材料范围、冲突等约束，仍不进入当前主模型。其余60条按三电极、CV、凝胶、混合器件、复合材料或待定体系保留；不能改名混入主体系。本轮未对这60条宣称全部逐字段终审。

材料表征原始观测和证据继续保存供扩展分析使用。“全量利用”不等于把不同输出定义、器件体系和不可靠字段强行合成一个训练表。

## 到达现有证据边界后的处理

`仅剩关键缺证_待补信息.csv`已列出每条DOI、循环电流、缺少的定义、单片质量待填位置以及其他阻碍；没有向作者发送任何消息。

要继续转为正式准入，需要可引用的原始方法说明、原始测试配置或作者明确说明：该循环电流的A/g究竟以双片总活性质量还是指定单片质量归一化。只有单片口径和两片活性质量/明确等质量定义都成立时才可换算。没有这些证据，继续调算法、填更多BET/N/O或反复检索同一PDF不会使该条满足当前严格口径。

SRC123的2016前作全文仍未取得；R001前作NIMS仓库在本机正常证书校验下访问失败，未关闭证书校验，未假称读过曲线。它们保留具体访问限制，不写成作者未报告或已经确认复用。

## 核验与使用

{checks['passed']}项核验通过，包括SQLite完整性、外键、原始记录与标签不变、历史保留、310份父版本文件和137份原始来源哈希不变，以及内存合成夹具的正反准入回归。合成数据只在内存中构造，不写入正式库、不拟合模型，也不当成新增准入样本。

`training_ready`是当前七输入主模型唯一正式导出视图，已补齐BET和电流规范口径等硬条件。`modeling_effective_inputs`先屏蔽不可靠可选值；`training_ready_pore`沿用同一正式队列。未认识的新阻碍默认阻挡。

执行顺序：`apply_evidence_r3.py`与`settle_field_evidence_r3.py`均为已执行的一次性增量，禁止重跑；`finalize_admission_r3.py`只重建本版本派生视图和导出；`verify_r3.py`只读真实库，并在内存中做回归。所有研究训练仍未授权，也未执行。

本版本只修改自己的第三轮副本。前两轮、原始文献、共同协作契约、文献对话成果和合并发布区均未修改。发起对话合并时需审查本轮规则澄清；本轮manifest交付就绪不表示全量科学准入已经实现。
'''
(ROOT/'逐条准入结果与剩余证据.md').write_text(report,'utf-8')
(ROOT/'README.md').write_text('''# 第三轮逐条准入闭环

当前正式准入：0。已完成能从当前取得资料中确认的重点补证与规则修正，尚未达到全量正式准入。

- 主报告：逐条准入结果与剩余证据.md
- 当前数据库：cycling_v0_3r3.sqlite
- 逐项状态：exports/主候选10条逐项检查.csv
- 待补定义：仅剩关键缺证_待补信息.csv
- 正式输出：exports/正式准入七输入.csv（仅表头，不能拿候选导出冒充正式数据）
- 复核：准入闭环只读复核.ipynb、核验结果_r3.json

七输入：计划循环次数、循环电流密度、电解液、摩尔浓度、器件电压下限/上限、循环前成品N2-BET。总孔体积为可选扩展。输出仍是循环稳定性对应的电容保持率。

一次性增量脚本已执行，禁止重跑。原始记录与全部旧版本保留。研究训练未执行。
''','utf-8')
(ROOT/'进度与交接.md').write_text(f'''# 第三轮接续

用户要求按顺序解决准入阻碍，直至可得数据正式准入。当前未达成全量正式准入；已取得4份SI并完成10条主候选重点核查，9条完成有限范围来源分组，五条基准通过，R111窗口和SRC035总孔体积补齐。当前8条只缺电流分母，另1条还缺窗口、1条还缺前作关联。

主报告、SQLite、字段证据、逐条阻碍和待填清单均在本目录。计数：126篇/141来源/67暂定材料/83暂定测试/89正式候选终点；231审查事件、285变更、134材料观测。48项核验通过；0研究拟合。原始137来源和310份父版本文件保持不变。

不要把重跑脚本或放宽分母要求当成补证。`apply_evidence_r3.py`、`settle_field_evidence_r3.py`禁止重跑。派生视图和导出可以用finalize重建；verify真实库只读，回归夹具仅内存。r3字段级可选问题会屏蔽值而不阻挡主模型；未知问题默认阻挡。

绝不借电容公式的质量推断循环电流分母；不把R020非对称段的分母借给对称AC；不把R107一万次窗口借给两万次；不把精确基线循环号缺失继续列作独立阻碍。来源分组通过是限定可得资料的审查，不宣称绝对独立。SRC123前作依旧未核清。

仅在取得具体原始说明/作者明确说明后逐条补电流定义和必要的质量换算。当前所有真实循环电流数值及mass_basis均与父库一致；没有为了非零而填入规范分母。

本目录为独立可审查交付；未改其他对话成果/共同契约/合并区。manifest科学目标达成false、交付就绪true是不同含义。发起对话仍需统一合并审查。
''','utf-8')

# Notebook needs only Python stdlib. In this environment nbformat/nbclient are absent,
# so validate the notebook structure and execute each code cell sequentially in one namespace.
nb={'nbformat':4,'nbformat_minor':5,'metadata':{'kernelspec':{'name':'python3','display_name':'Python3','language':'python'},'language_info':{'name':'python','version':'3'}},'cells':[]}
def md(text):nb['cells'].append({'cell_type':'markdown','id':f'cell-{len(nb["cells"])+1}','metadata':{},'source':text.splitlines(keepends=True)})
def code(text):nb['cells'].append({'cell_type':'code','id':f'cell-{len(nb["cells"])+1}','metadata':{},'source':text.splitlines(keepends=True),'execution_count':None,'outputs':[]})
md('''# 循环稳定性准入只读复核

当前正式准入0；8条只缺电流质量口径，另2条还涉及窗口或前作。七输入、科学标准和输出不变。数值覆盖不等于正式样本数。

## 范围与方法

仅只读查询本目录SQLite及核验文件，不下载、不写数据库、不训练。来源、审查出处及取得的新SI见主报告和external_sources。精确基线圈号未知保持未知；同文数据同组；可选孔体积疑点屏蔽。没有把不同DOI当成绝对独立的证明。
''')
code(f'''from pathlib import Path
import sqlite3, json
root = Path.cwd()
if not (root / 'cycling_v0_3r3.sqlite').exists():
    root = Path({str(ROOT)!r})
connection = sqlite3.connect((root / 'cycling_v0_3r3.sqlite').as_uri() + '?mode=ro', uri=True)
connection.row_factory = sqlite3.Row
print('正式候选终点:', connection.execute('SELECT count(*) FROM cycling_endpoints').fetchone()[0])
print('正式准入:', connection.execute('SELECT count(*) FROM training_ready').fetchone()[0])
''')
md('## 主候选检查结果\n\n分母已核和数值非空是两项不同检查。')
code('''flags = ['source_checked', 'material_checked', 'protocol_checked', 'baseline_checked', 'mass_basis_checked', 'independence_checked', 'freeze_cleared']
for flag in flags:
    passed = connection.execute(f'SELECT sum({flag}), count(*) FROM admissions WHERE record_id IN (SELECT record_id FROM primary_screening_candidates)').fetchone()
    print(f'{flag}: {passed[0]}/{passed[1]}')
''')
md('## 逐条剩余阻碍\n\n完整字段及出处见exports和mass_definition_audits。')
code('''query = """SELECT e.record_id,d.primary_disposition FROM endpoint_effective_review e
JOIN admission_decisions_r3 d USING(record_id)
WHERE e.record_id IN (SELECT record_id FROM primary_screening_candidates) ORDER BY e.record_id"""
for row in connection.execute(query):
    print(row['record_id'], row['primary_disposition'])
''')
md('## 核验与限制\n\n下面是数据完整性和工程回归结果，不是预测精度。')
code('''assert connection.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
assert not connection.execute('PRAGMA foreign_key_check').fetchall()
verification = json.loads((root / '核验结果_r3.json').read_text('utf-8'))
print('核验通过:', verification['passed'], '失败:', verification['failed'])
print('真实研究拟合:', verification['research_fits'])
for field in ['BET_m2_g', 'total_pore_volume_cm3_g']:
    counts = connection.execute(f'SELECT count(*),count(DISTINCT material_id),count(DISTINCT paper_id) FROM endpoint_effective_review WHERE {field} IS NOT NULL').fetchone()
    print(field, '字段覆盖(终点/材料/论文):', tuple(counts))
connection.close()
''')
md('''## 结论与证据入口

现有材料已支持更多字段和审核决定，但无法替作者定义未明确的循环电流分母；正式准入仍为0。需要取得可引用的归一化说明，不能靠调参或统一除2解除。

[逐条报告](逐条准入结果与剩余证据.md)；[待补信息](仅剩关键缺证_待补信息.csv)；[核验结果](核验结果_r3.json)。本文件四个只读Python单元按顺序实际执行并保存输出；未使用Jupyter内核执行器，未安装任何环境依赖。
''')
env={};count=0
for cell in nb['cells']:
    if cell['cell_type']=='code':
        count+=1;buf=io.StringIO()
        with contextlib.redirect_stdout(buf):exec(compile(''.join(cell['source']),'<r3_readonly_notebook>','exec'),env)
        cell['execution_count']=count;cell['outputs']=[{'output_type':'stream','name':'stdout','text':buf.getvalue().splitlines(keepends=True)}]
assert nb['nbformat']==4 and len({x['id'] for x in nb['cells']})==len(nb['cells'])
assert all(x['execution_count'] and x['outputs'] for x in nb['cells'] if x['cell_type']=='code')
(ROOT/'准入闭环只读复核.ipynb').write_text(json.dumps(nb,ensure_ascii=False,indent=2),'utf-8')
print('Notebook:4 read-only Python cells executed sequentially; native Jupyter executor not installed.')
c.close()

base=json.loads((ROOT.parent.parent/'并行协作契约_v1_20261017.json').read_text('utf-8'))
manifest={'schema_version':'parallel-preparation-v1','task_role':'database','date':'2026-10-17',
 'baseline_database_sha256':base['baseline']['database_sha256'],
 'baseline_model_contract_sha256':base['baseline']['model_contract_sha256'],
 'direct_parent_database':str(PARENT/'cycling_v0_3r2.sqlite'),'direct_parent_database_sha256':sha(PARENT/'cycling_v0_3r2.sqlite'),
 'ready_for_merge':True,'scientific_objective_achieved':False,'training_ready_count':0,
 'checks':{'passed':checks['passed'],'failed':checks['failed'],'research_fits':0,'notebook_python_cells_executed':4,'native_jupyter_executor_used':False},
 'unresolved_issues':['10 primary records lack a uniquely established cycling-current denominator;8 have only this remaining core gap.',
 'R107_CY02 still lacks its20k endpoint voltage evidence.','SRC123_CY02 predecessor linkage remains unresolved.',
 'Other tracks remain separate; no claim that all89 endpoints underwent full field-level review.'],
 'proposed_contract_changes':['Scope optional pore issues to the field, mask unsafe values before use;core7 is not blocked by them.',
 'Keep same admitted cohort for optional pore extension;no complete-case cohort switching.',
 'Accept documented author plotted-start normalization without inventing an exact baseline cycle.',
 'Define independence_checked as bounded provenance/grouping review, with same-paper endpoints grouped and known prior ambiguities held.',
 'Separate explicit record freeze clearance from missing input-definition gates;both still enforced.',
 'Harden SQL training export with BET, canonical current basis, molar units, reviewed groups and date/system predicates.'],
 'outputs':[]}
for p in sorted(ROOT.rglob('*')):
    if p.is_file() and p.name!='merge_manifest.json':manifest['outputs'].append({'path':str(p),'sha256':sha(p),'role':'database_evidence_and_admission_closure'})
(ROOT/'merge_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),'utf-8')
print('Packaged',len(manifest['outputs']),'artifacts; scientific objective remains unachieved.')
