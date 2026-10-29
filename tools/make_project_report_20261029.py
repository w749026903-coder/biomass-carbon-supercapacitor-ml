"""Read-only project audit and a plain-language report; no fitting or data writes."""
from pathlib import Path
import base64, collections, datetime, hashlib, html, json, math, re, sqlite3, sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from data.training_latest import open_training_datasets

OUT = ROOT / '项目进展报告_20261029'
RELEASE = ROOT / '全量文献训练数据接入_v7_药渣与地肤主集_20261029'
MODEL = ROOT / '模型v1.2_来源隔离再训练_20261028'
INDEX = ROOT / '全库复检与特征补提取_20261021/full_corpus_search_native.sqlite'

def read(p):
    return json.loads(p.read_text(encoding='utf-8-sig'))

def sha(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def write(p, value):
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def main():
    OUT.mkdir(exist_ok=True)
    pointer = read(ROOT / 'data/current_training_latest.json')
    assert pointer['directory'] == RELEASE.name, 'This dated report must use its reviewed release.'
    summary = read(RELEASE / 'summary.json')
    manifest = read(RELEASE / 'merge_manifest.json')
    assert manifest['ready_for_explicit_purpose_inputs'] and not manifest['all_literature_complete']
    for item in manifest['outputs']:
        assert sha(ROOT / item['path']) == item['sha256'], item['path']
    c = sqlite3.connect(INDEX.as_uri() + '?mode=ro', uri=True)
    identities = c.execute('select count(*) from identities').fetchone()[0]
    all_dois = c.execute("select count(distinct nullif(doi,'')) from identities").fetchone()[0]
    rows = c.execute("select distinct x.identity_key,x.role,s.sha256,s.format,s.path from identity_sources x join sources s using(sha256) where role in ('main','main_XML_metadata')").fetchall()
    files = {}; linked = collections.defaultdict(set)
    for identity, role, expected, fmt, name in rows:
        if expected not in files:
            p = Path(name)
            assert p.is_file() and sha(p) == expected, name
            if fmt == 'pdf':
                with p.open('rb') as f:
                    assert f.read(4) == b'%PDF'
                state = 'primary_pdf_link'
            else:
                assert fmt == 'xml'
                e = ET.parse(p).getroot()
                body_chars = sum(len(''.join(n.itertext()).strip()) for n in e.iter() if n.tag.split('}')[-1] == 'body')
                assert body_chars >= 1000, name
                state = 'xml_with_body_ge_1000_chars'
            name_for_receipt = str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p)
            files[expected] = dict(path=name_for_receipt, sha256=expected, format=fmt, state=state)
        linked[identity].add(expected)
    assert len(linked) == 420 and len(files) == 432
    primary_dois = c.execute("select count(distinct nullif(i.doi,'')) from identities i join identity_sources x using(identity_key) where x.role in ('main','main_XML_metadata')").fetchone()[0]
    c.close()
    with open_training_datasets(RELEASE / pointer['database_file'], pointer['sha256']) as d:
        q = d.connection
        counts = dict(total_facts=q.execute('select count(*) from facts').fetchone()[0],
                      numeric_facts=q.execute('select sum(numeric) from facts').fetchone()[0],
                      connected=q.execute('select count(distinct fact_id) from fact_uses').fetchone()[0],
                      registered_sources=q.execute('select count(*) from sources').fetchone()[0],
                      material_fact_sources=q.execute("select count(distinct json_extract(record_json,'$.doi')) from facts").fetchone()[0],
                      materials=q.execute('select count(*) from materials').fetchone()[0],
                      cycle_observations=q.execute('select count(*) from cycle_records').fetchone()[0])
        assert counts == dict(total_facts=5476, numeric_facts=5197, connected=3727, registered_sources=72,
                              material_fact_sources=68, materials=506, cycle_observations=287)
        tasks = {}
        for name in ['cycle:reported_3e', 'cycle:reported_2e', 'capacity:3e_reported', 'capacity:3e_with_graph',
                     'material:ordinary_biomass_pretest:BET_surface_area_m2_g', 'capacity:2e_device']:
            rs = d.rows(name)
            tasks[name] = dict(rows=len(rs), source_families=len({x['source_family'] for x in rs}))
            assert tasks[name]['rows'] == summary['task_counts'][name]['rows']
        main_rows = d.rows('cycle:reported_3e')
        maximum_source_rows = max(collections.Counter(x['source_family'] for x in main_rows).values())
        assert maximum_source_rows == 5
        bridged = sum(x['material_key'] is not None for x in main_rows)
        assert bridged == 25
        graph_ids = {x['row_id'] for x in d.rows('capacity:3e_with_graph')}
        assert {x['row_id'] for x in d.rows('capacity:3e_reported')} <= graph_ids
        ledger = dict(q.execute('select disposition,count(*) from usage_ledger group by disposition').fetchall())
        assert sum(ledger.values()) == 5476
    predictions = read(MODEL / 'outer_predictions.json')
    results = read(MODEL / 'results.json')
    family_n = collections.Counter(x['source_group'] for x in predictions)
    weights = [1 / family_n[x['source_group']] for x in predictions]
    y = [x['observed_pct'] for x in predictions]
    sw = sum(weights); mean_y = sum(w*v for w, v in zip(weights, y)) / sw
    variance = sum(w*(v-mean_y)**2 for w, v in zip(weights, y)) / sw
    calculated = {}
    for variant, field in [('nested', 'predicted_pct'), ('source_mean', 'source_mean_pct'), ('source_median', 'source_median_pct')]:
        errors = [x[field]-x['observed_pct'] for x in predictions]
        mse = sum(w*e*e for w, e in zip(weights, errors)) / sw
        metrics = dict(mae=sum(w*abs(e) for w, e in zip(weights, errors)) / sw, rmse=math.sqrt(mse), r2=1-mse/variance)
        reference = next(x for x in results['metrics'] if x['variant'] == variant)
        assert all(abs(metrics[k]-reference[k]) < 1e-10 for k in metrics)
        calculated[variant] = metrics
    assert len(predictions) == 47 and len(family_n) == 34
    assert sha(MODEL / 'model_v1_2.joblib') == results['model_sha256']
    assert sha(MODEL / 'training_plan.json') == results['plan_sha256']
    assert not results['reliable_for_design'] and not results['descriptive_acceptance_passed']
    coverage = read(RELEASE / 'main_feature_coverage.json')
    fields = [('BET比表面积', 'BET_m2_g'), ('总孔容', 'total_pore_volume_cm3_g'), ('Raman结构比值', 'Raman_ID_IG'),
              ('电极面负载', 'mass_loading_mg_cm2'), ('XPS氮原子比例', 'XPS_N_atomic_pct_v15'), ('XPS氧原子比例', 'XPS_O_atomic_pct_v15')]
    coverage_rows = [(label, next(x for x in coverage if x['field'] == field)) for label, field in fields]
    sources = ['data/current_training_latest.json', str((RELEASE/'summary.json').relative_to(ROOT)),
               str((RELEASE/'merge_manifest.json').relative_to(ROOT)), str((RELEASE/'main_feature_coverage.json').relative_to(ROOT)),
               str((MODEL/'results.json').relative_to(ROOT)), str((MODEL/'outer_predictions.json').relative_to(ROOT)),
               str((MODEL/'training_plan.json').relative_to(ROOT)), str(INDEX.relative_to(ROOT))]
    audit = dict(audited_at=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(timespec='seconds'),
                 scope='Current sealed v7 inputs and frozen v1.2 model; corpus identity inventory is the 20261021 index freshly checked, not a newly rebuilt entire library census.',
                 literature_inventory=dict(catalog_entries=identities, catalog_distinct_DOIs=all_dois,
                                           identity_entries_with_primary_content=len(linked), primary_linked_distinct_DOIs=primary_dois,
                                           unique_primary_files=len(files), file_formats=dict(collections.Counter(x['format'] for x in files.values())),
                                           paper_count_not_fully_scientifically_deduplicated=True,
                                           later_SI_and_other_unindexed_additions_not_in_census=True,
                                           checked_files=list(files.values())),
                 counts=counts, task_counts=tasks, main_material_links=bridged, maximum_main_rows_one_source=maximum_source_rows,
                 unique_numeric_input_connection_rate=3727/5197, remaining_numeric=1470, nonpoint_or_missing=279,
                 ledger_dispositions=ledger, latest_main_feature_coverage=[dict(label=label, **row)for label,row in coverage_rows],
                 model_metrics_independently_recomputed=calculated, evaluated_rows=47, evaluated_sources=34,
                 new_model_fits=0, latest_features_not_yet_retrained=True, database_v8_in_progress_not_counted=True,
                 verification_commands=[dict(command='tools/verify_yzpc_kochia_v7.py', checks=68594, status='passed'),
                                        dict(command='tools/verify_model_v12.py', checks=26259, status='passed', estimator_fits_during_verification=0)],
                 source_file_sha256={name:sha(ROOT/name) for name in sources})
    write(OUT/'统计核验.json', audit)

    sections = []
    sections.append(('项目进展概况', '''目前已经建起了“论文原文—数据证据—训练输入—模型评估”的工作流程，完成过初步训练，也保留了能追查来源的数据库。现阶段最扎实的成果是资料和数据基础；预测能力仍处于探索阶段，还不能可靠地指导新材料配方。

研究范围是生物质衍生多孔碳超级电容器，纤维形貌只是其中一类。主要预测目标是：给定材料、测试条件和循环次数，预测电容还剩初始参照的百分之多少。比电容、孔结构等作为分别管理的相关任务。

| 项目 | 当前数量 | 用大白话解释 |
|---|---:|---|
| 有正文关联的文献条目 | 420条，约400篇规模 | 按既有全库索引，本次重新确认文件和哈希；包含综述、背景与不同体系，并非全部适用主模型 |
| 对应的正文文件 | 432份 | 223份PDF、209份含正文XML；一篇有不同格式，不能按文件数直接算论文数 |
| 已复核登记的来源 | 72个 | 其中68个已进入材料/制备事实库，均未宣称整篇提取完毕 |
| 材料与制备事实 | 5,476项 | 包括材料参数、制备条件以及明确保留的未知值；不等于5,476个样品 |
| 其中明确的数值事实 | 5,197项 | 另有279项非单一点值或缺失事实 |
| 已接入训练输入的数值 | 3,727项，71.71% | 在输入特征或辅助目标中有实际调用回执；尚不等于都参与过拟合 |
| 尚未接入的数值 | 1,470项 | 分别记录方法不明、争议、阶段未关联、用途待定或仅属测量注记等原因 |

这里的5,197项专指材料与制备事实口径，不是把所有电化学结果表简单相加后的总数。比电容、循环和阻抗等还在各自的报告或训练视图中管理，不能混算成独立实验。'''))
    cov_table = '\n'.join(f'| {label} | {row["nonmissing_rows"]}/47 | {row["source_families"]} |'for label,row in coverage_rows)
    sections.append(('现有数据能怎样使用', '''数据库中的数字已经按用途接入，可直接生成对应任务的训练矩阵，并能追溯到论文、样品、材料阶段和测试条件。下表中的不同任务会共享论文和材料，数量不能相加。

| 可调用任务 | 数据行数 / 来源组数 | 使用范围 |
|---|---:|---|
| 三电极循环保持率主集 | 47 / 34 | 已完成模型v1.2评估的核心任务 |
| 双电极循环保持率 | 31 / 25 | 单独建模，未混入主集 |
| 普通三电极比电容 | 229 / 35 | 可用于比电容探索性建模 |
| 加入有界读图的三电极比电容 | 434 / 35 | 包含上面的229行，新增205个图读条件；需要保留读图误差 |
| 普通材料BET属性任务 | 266 / 51 | 预测比表面积的辅助研究任务；排除与目标同测量块的输入 |
| 口径明确的双电极器件比电容 | 7 / 2 | 来源很少，主要用于流程验证 |

47条主记录中，25条已与新版材料库建立规范关联，还剩22条。剩余记录原来已有的BET和测试工况仍在使用，不能说这些论文完全没有被利用。自v1.2训练后累计增加237个非空主集特征单元；“一个单元”是某条记录补上一个字段，共享条件、配方比例和区间边界不等于同等数量的独立新参数。

当前v7主集的关键参数覆盖如下。这是最新数据库的情况，不是旧模型训练时的覆盖：

| 参数 | 有值记录数 | 覆盖来源组数 |
|---|---:|---:|
''' + cov_table + '''

能否训练的判断：已经具备开展小样本、探索性回归实验的条件；仍不足以据此声称能可靠预测未见论文或指导材料设计。现有规模也不支持从头训练大模型。单靠达到某个论文篇数，不能保证预测好，必须同时看独立来源、关键字段和留出检验。

71.71%是“已抽取材料数值的接入率”，不是“整篇文献利用率”。目前还没有足够的逐表、逐图、逐SI完结证据，给出全库整篇利用率会造成误导。'''))
    metrics_table = '\n'.join('| '+label+' | '+' | '.join(f'{calculated[key][k]:.4f}'for k in ['mae','rmse','r2'])+' |'for label,key in [('现有模型v1.2','nested'),('只猜训练来源均值','source_mean'),('只猜训练来源中位数','source_median')])
    sections.append(('模型现状：能跑通，但预测还不够好', '''最近一次正式留档实验是2026年10月28日的模型v1.2。它是小样本回归模型，最终研究权重采用带正则化的岭回归，并不是已经训练完成的大语言模型。预先固定比较5个候选，完成560次拟合；最终启用25个数值字段和6个类别字段。

验证方式是“每次留出一整个论文来源”，用其他来源训练，再预测未参与本折训练的来源。同一篇论文里的多个样品或工况不拆到两边，所有数据处理只在训练来源中完成，各来源总权重相同。这样更接近“遇到新论文还会不会预测”的问题，但这些来源此前已经用于探索，仍不属于全新的外部测试。[分组验证说明](https://scikit-learn.org/stable/modules/cross_validation.html#cross-validation-iterators-for-grouped-data)

| 同口径方案 | MAE / 百分点 | RMSE / 百分点 | R² |
|---|---:|---:|---:|
''' + metrics_table + '''

MAE为5.1509个百分点，可以理解为平均偏差约5.15个百分点。例如实测保持率90%，预测95%，就是偏了5个百分点；这不是相对误差5%，也不表示每条都能落在±5.15之内。

RMSE为6.9087个百分点，对少数严重预测错的样品更敏感，比均值参照有所降低。但模型MAE几乎等于直接猜均值，尚未证明稳定的实用收益。

R²为0.0955。R²越接近1越好，0通常对应按总体均值作常数预测，负值也可能出现。这里的0.0955表明模型对留出样本差异的刻画仍弱，不能读成“准确率9.55%”。表中均值参照用的是各折训练来源均值，因此它的留出R²不必恰好为0。[R²定义](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.r2_score.html)

相对均值的MAE差为+0.0019个百分点，描述性95%范围为−0.4519到+0.4476，跨过0。本轮预设门槛要求同时优于均值、中位数，且这个范围的上界低于0，结果没有通过。这个范围不是未来单个样品的预测区间。

| 典型留出样品 | 实测保持率 | 模型预测 | 说明 |
|---|---:|---:|---|
| AC-700C | 62.20% | 91.64% | 对明显衰减预测过于乐观 |
| CCL-K₂CO₃-1-700 | 109.20% | 96.36% | 未充分识别循环活化后的增长 |
| NPC-700-6 | 106.30% | 94.18% | 同样向中间值收缩 |

保持率超过100%可以是原文报告的真实现象，不应为使数据“好看”强行裁到100%。模型预测值也不能反过来充当实验证据。

尤其需要说明：v1.2没有使用后来v1至v7新增的全部训练接入层，也没有开展辅助学习。因此3,727项“已经接通可调用”不能说成“已经被当前权重全部学过”；最近的数据整理是否提高模型精度，仍需下一轮独立留档实验验证。'''))
    sections.append(('主要问题与下一步改进顺序', '''第一，已有文献还没有吃透。这是实际存在的工作缺口，不能全部归因于文献不足。现有420条正文关联条目中，材料事实库覆盖68个来源，很多自身表格、对照样品、倍率曲线和补充材料仍待逐项核读。文献范围不同，以上数量也不能直接相除当成严格利用率。

第二，可用循环标签和跨来源证据仍少。5,197项材料数值并没有变成5,197条循环寿命实验：孔结构、表面组成或比电容，不能冒充循环保持率。主集仍是47条、34个来源，少数关键字段覆盖更稀疏。由此推断模型稳定性受限，但还不能用现有结果判定“唯一原因就是缺数据”。

第三，实验之间差异大。三电极与双电极、原料与最终碳、不同电解液、测试电流和循环次数必须区分。相同百分数未必代表相同条件下的稳定性。把这些差异混在一起，样本看似增加，学习目标反而会变得模糊。

第四，模型对极端情况处理不好。它倾向预测九成多，难以同时识别严重衰减和循环活化增长。木粉、CCL、NPC三个来源合计约占来源加权平方误差的51.4%。应追查材料特征、条件与标签证据，不应删除这些困难来源来换取高分。

第五，新增数据与旧模型之间还缺一轮可检验的衔接。数据库已经改进，但效果尚未验证。接下来要比较“旧输入”和“最新输入”在同一来源隔离计划下的表现，才能判断提取工作到底带来了多少帮助。

| 优先级 | 建议执行的工作 | 完成时要看到的结果 |
|---|---|---|
| 1 | 先补现有主集22条记录的材料关联，继续OAC623、AMFS等本地原文 | 新增字段能逐项回到原文；已有值只补证，不重复算新增 |
| 2 | 核完未接入的1,470项数值和已读来源剩余表、图、SI | 合适的接入对应任务；仅属误差、注记或未决冲突的明确保留原因，不强求100%接入 |
| 3 | 逐项处理原37条待补证记录 | 找到证据才增加准入；确实未报告或不可访问的明确列出，不编造补齐 |
| 4 | 先做数据覆盖诊断，再冻结下一轮有限实验计划 | 对比旧/新输入；评估精简特征、材料与测试条件；所有辅助任务也整来源隔离 |
| 5 | 将比电容作为并行研究任务，循环稳定性主线继续推进 | 229条/35来源与含图434条分别评估，不把电容当寿命；辅助学习是否有益由试验判定 |
| 6 | 针对真正缺口再补论文，争取新的来源或实际实验检验 | 优先关键条件完整、覆盖衰减/增长和不同工艺；预留未用于选模的来源 |

不建议马上反复调参或换更复杂模型。应先让已有论文真正变成同口径、可追溯的输入。下一轮再看按来源留出的MAE、RMSE、R²和学习曲线，判断继续加来源是否仍带来收益。学习曲线是拟议诊断，本报告没有运行新的训练。[学习曲线说明](https://scikit-learn.org/stable/modules/learning_curve.html)

建议把进展同时看成四张账：已有多少正文；有多少样品和字段被核实；有多少独立来源能进入具体任务；相对简单参照是否在留出检验中稳定改善。不能只靠文件数量、提取数字总量或一次高R²判断项目成功。'''))
    sections.append(('可向导师直接汇报的表述与核验依据', '''我们目前已经整理出约400篇规模的文献储备，现有索引中420条条目能够定位到正文。材料与制备事实库累计有5,197项明确数值，其中3,727项已进入可调用的训练输入，接入率约71.7%。循环保持率主模型实际评估了47条测试、34个来源，R²约0.096，平均绝对误差约5.15个百分点，与直接猜均值基本持平，因此目前还是研究原型。后续重点是继续挖掘已有论文的表格、曲线和补充材料，补齐关键特征并增加有效来源，再用严格的来源隔离实验检验新增数据是否真正提高预测能力。

本报告统计截止2026年10月29日，采用已封版训练输入v7和已完成模型v1.2。正在核读的v8没有计入成果。全量文献利用目标继续进行，没有声称全部补正或正式预测能力达标。

文献条目数来自2026年10月21日的全库身份索引，本次对其正文路径、文件哈希、PDF文件头及XML正文存在性重新核验。索引有480条总身份条目、463个不同DOI；其中420条有正文关联，对应403个不同DOI及17条无DOI身份。它是可复核的文献储备口径，并非新完成的全目录科学去重普查，后续尚未重建入索引的附件或新增文件不在这个分母中。PDF内容与身份是否每篇都匹配、是否适用本研究，还要逐篇科学审查。

本次只读复核通过：v7数据库68,594项检查，模型v1.2共26,259项检查；模型留出指标另由47条逐记录预测重新计算。432份索引正文文件的SHA均匹配。检查数量只是核验过程的记录，不代表模型性能或文献完整率。

主要项目依据：当前数据入口、v7统计/字段覆盖/封版清单、模型v1.2冻结计划/结果/逐记录预测、全库正文索引。报告旁的《统计核验.json》保存本次统计、计算口径和文件指纹。模型图沿用已封版v1.2留出预测，没有使用最新数据重新拟合。

[项目GitHub仓库](https://github.com/w749026903-coder/biomass-carbon-supercapacitor-ml)'''))
    title = '生物质衍生多孔碳超级电容器：项目进展报告'
    md = '# '+title+'\n\n2026年10月29日 · 数据v7 / 模型v1.2 · 面向项目汇报\n\n'
    md += '\n\n'.join('## '+name+'\n\n'+text for name,text in sections)
    (OUT/'项目进展报告.md').write_text(md+'\n', encoding='utf-8')

    def inline(s):
        s = html.escape(s)
        return re.sub(r'\[([^\]]+)\]\((https://[^)]+)\)', lambda m:'<a href="'+m[2]+'">'+m[1]+'</a>', s)

    def render(text):
        blocks = []
        for part in text.strip().split('\n\n'):
            if part.startswith('|'):
                lines = part.splitlines(); rows = [[v.strip()for v in ln.strip('|').split('|')]for ln in lines]
                header = '<thead><tr>'+''.join('<th>'+inline(v)+'</th>'for v in rows[0])+'</tr></thead>'
                body = '<tbody>'+''.join('<tr>'+''.join('<td>'+inline(v)+'</td>'for v in row)+'</tr>'for row in rows[2:])+'</tbody>'
                blocks.append('<div class="table-wrap"><table>'+header+body+'</table></div>')
            else:
                blocks.append('<p>'+inline(part)+'</p>')
        return ''.join(blocks)

    graphic = base64.b64encode((MODEL/'figures/heldout_predictions.svg').read_bytes()).decode()
    css = '''*{box-sizing:border-box}body{margin:0;background:#f1f2ef;color:#1e2a31;font-family:"Microsoft YaHei","Noto Sans CJK SC",sans-serif;font-size:16px;line-height:1.85}main{max-width:1030px;margin:28px auto;background:white;padding:48px 58px}header{border-bottom:3px solid #23534b;padding-bottom:22px}h1{font-size:30px;line-height:1.5;margin:8px 0 18px}h2{font-size:23px;line-height:1.5;color:#184c43;margin:36px 0 16px}p{margin:14px 0}a{color:#125d86;overflow-wrap:anywhere}.meta{font-size:14px;color:#60716e}.table-wrap{overflow-x:auto;margin:20px 0}table{border-collapse:collapse;width:100%;font-size:14px;line-height:1.65}th,td{padding:10px 12px;border-bottom:1px solid #d9e1dc;text-align:left;vertical-align:top}th{background:#eaf1ed;color:#204b43}td:nth-child(2){font-variant-numeric:tabular-nums}figure{margin:26px 0}figure img{width:100%;height:auto}figcaption{font-size:13px;color:#53635d}nav{display:flex;gap:14px;flex-wrap:wrap;margin-top:20px}button{font:inherit;background:#22594e;color:white;border:0;border-radius:4px;padding:7px 17px;cursor:pointer}footer{border-top:1px solid #cbd6d0;margin-top:30px;padding-top:16px;font-size:13px;color:#52645d}@media(max-width:650px){main{padding:24px 18px;margin:0}h1{font-size:25px}h2{font-size:21px}table{min-width:510px}td,th{padding:9px}}@media print{@page{size:A4;margin:17mm 15mm}body{background:white;font-size:10.3pt;line-height:1.75}main{margin:0;padding:0;max-width:none}h1{font-size:22pt}h2{font-size:15pt;break-after:avoid;margin-top:24px}p{orphans:3;widows:3}table{font-size:9pt;min-width:0!important}th,td{padding:6px 7px}thead{display:table-header-group}tr{break-inside:avoid}.table-wrap{overflow:visible}nav{display:none}figure{break-inside:avoid}a{color:inherit;text-decoration:none}.pagebreak{break-before:page}footer{font-size:9pt}}'''
    markup = '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+title+'</title><style>'+css+'</style></head><body><main><header><p class="meta">2026年10月29日 · 数据v7 / 模型v1.2 · 面向项目汇报</p><h1>'+title+'</h1><p>数据基础逐步完善，预测能力仍需验证。</p><nav><button onclick="window.print()">打印 / 保存PDF</button><a href="项目进展报告.pdf">下载PDF</a><a href="项目进展报告.md">文字版</a><a href="统计核验.json">统计依据</a></nav></header>'
    for i,(name,text) in enumerate(sections):
        markup += '<section'+(' class="pagebreak"' if i in [1,2,3,4] else '')+'><h2>'+str(i+1)+'．'+name+'</h2>'+render(text)
        if i == 4:
            markup += '<figure><img alt="模型v1.2按来源留出的实测和预测对照" src="data:image/svg+xml;base64,'+graphic+'"><figcaption>模型v1.2的来源留出预测。图来自已封版实验，非本次新增训练。</figcaption></figure>'
        markup += '</section>'
    markup += '<footer>数据与模型版本分别固定；数据库接入率、独立样本数、模型实测表现分开报告。</footer></main></body></html>'
    (OUT/'项目进展报告.html').write_text(markup, encoding='utf-8')
    print(json.dumps(dict(report_directory=str(OUT), primary_entries=420, files_checked=432, database=counts, model_metrics=calculated, new_fits=0),ensure_ascii=False))

if __name__ == '__main__':
    main()
