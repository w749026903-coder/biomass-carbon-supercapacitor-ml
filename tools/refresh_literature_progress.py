"""Refresh the same local dashboard from verified SQLite; never changes science data."""
from pathlib import Path
import argparse,datetime,json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from data.literature_v2 import open_literature_database
from data.cycling_db import open_database

LABELS={'BET_surface_area_m2_g':'BET比表面积','micropore_area_reported_m2_g':'报告微孔面积','microporosity_reported_pct':'报告微孔率（基准未知）','micropore_volume_cm3_g':'微孔容','pore_width_nm':'孔宽','mesopore_volume_cm3_g':'介孔容','total_pore_volume_cm3_g':'总孔容','BJH_pore_diameter_nm':'BJH孔径','Raman_ID_IG':'Raman强度比ID/IG','BET_m2_g':'BET比表面积','XRD_d002_nm':'XRD层间距d002','average_pore_width_nm':'平均孔宽','average_pore_diameter_nm':'平均孔径','mesopore_surface_area_m2_g':'介孔面积','micropore_surface_area_m2_g':'微孔面积','reported_N2_pore_volume_cm3_g':'报告氮吸附孔容','reported_mesopore_surface_area_m2_g':'报告介孔面积','reported_mesopore_surface_fraction_pct':'报告介孔面积占比','reported_mesopore_volume_fraction_pct':'报告介孔孔容占比','reported_micropore_surface_area_m2_g':'报告微孔面积','reported_pore_size_nm':'报告孔尺寸','reported_pore_width_nm':'报告孔宽','reported_total_surface_area_m2_g':'报告总比表面积'}
def label(f):
    if f.startswith('XPS_'):return 'XPS '+f[4:].replace('_at_pct',' 原子百分比')
    if f.startswith('EDS_'):return 'EDS '+f[4:].replace('_reported_pct',' 百分比（口径未知）')
    return LABELS.get(f,f)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--build-status',choices=['creating','updating','complete'],default='updating');args=ap.parse_args()
    target=ROOT/'文献提取进度/src/data.json';existing=json.loads(target.read_text('utf8'))
    pointer=json.loads((ROOT/'data/current_literature.json').read_text('utf8'));folder=ROOT/pointer['directory'];summary=json.loads((folder/'summary.json').read_text('utf8'))
    now=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(timespec='seconds');queries={}
    def query(key,rows,tables,sql,definition,caveats=()):
        queries[key]=dict(rows=rows,source=dict(label='本地已核验文献证据层 '+pointer['version'],executedAt=now,tables=tables,sql=sql,
          files=[{'name':pointer['database_file']},{'name':'summary.json'},{'name':'verification.json'}],
          metricDefinitions=[dict(field='count',label='计数口径',definition=definition)],caveats=list(caveats),
          evidenceFlow=['读取当前文献层指针并核验SQLite SHA256。','只读API/SQL生成所列完整快照行；不联网刷新原文，不写回数据库。','筛选与导出保留相同记录、单位和限定；工程核验不解除科学冻结。']))
    with open_literature_database() as db:
        facts=db.facts();caps=db.capacitances()
        for r in facts:r.update(parameter=label(r['field_name']),quantity=r['value'],evidence=r['locator'],status_label='低于误差，空值' if r['value'] is None else ('冲突冻结' if 'conflict' in r['review_status'] else '已提取，未准入'))
        for r in caps:r.update(quantity=r['value'],evidence=r['locator'],status_label='未报告' if r['value'] is None else ('竞争证据冻结' if 'conflict' in r['status'] else '已提取，未准入'))
        query('material_facts',facts,['material_facts','materials','table_source_links','source_documents'],
          'SELECT f.*,m.doi,m.sample_name,d.path,d.sha256,l.locator FROM material_facts f JOIN materials m USING(material_key) JOIN table_source_links l USING(table_key) JOIN source_documents d USING(document_key);',
          '材料×参数×自身表单元；受限值为null，不同测法不拼成一个参数。',['训练资格均为0；source_path返回该单元实际正文或SI。'])
        query('capacitances',caps,['capacitance_observations','materials','table_source_links'],
          'SELECT x.*,m.doi,m.sample_name,l.locator FROM capacitance_observations x JOIN materials m USING(material_key) JOIN table_source_links l USING(table_key);',
          '材料×方法×电解液×工况×自身报告表单元，F/g与F/cm³分开。',['41记录含39数值、2未报告；含8条EIS分表复述/竞争和1条合成碳参考，不能视为41独立样本。','CV5mV/s、GCD0.5A/g绑定自身Fig6；EIS无扫描速率。'])
        queue=[dict(r) for r in db.connection.execute('select * from raw_table_queue order by review_state,previous_role,table_id')]
        for r in queue:r.update(state='未进入本流程处理' if r['review_state']=='automatic_candidate_unreviewed' else '已处理指定范围',role='比较/汇总候选' if 'comparison' in r['previous_role'] else '自身/上下文待核')
        query('table_queue',queue,['raw_table_queue'],'SELECT * FROM raw_table_queue ORDER BY review_state,previous_role,table_id;',
          '一个自动候选可能合并两张真实表，不能等同样本。',['已处理只指声明范围，不代表整篇或全部参数完成。','历史725项材料属性另存，其中171项同源线索尚不等于表单元匹配。'])
        state_names={'has_current_observation_not_full_utilization_proof':'匹配现有观察','native_content_without_normalized_DOI_observation_match':'原生内容未匹配观察','metadata_or_non_native_content_needs_identity_review':'身份/内容待核'}
        states=[dict(category=state_names[r[0]],count=r[1]) for r in db.connection.execute('select work_state,count(*) from identity_inventory group by work_state')]
        query('identity_states',states,['identity_inventory'],'SELECT work_state,COUNT(*) AS count FROM identity_inventory GROUP BY work_state;',
          '目录身份条目，包括版本/SI/综述/参考体系；不是独立合格论文数。')
        sql='SELECT s.doi,s.title,COUNT(DISTINCT m.material_key) AS materials,COUNT(DISTINCT f.fact_id) AS cells,COUNT(DISTINCT CASE WHEN f.value IS NOT NULL THEN f.fact_id END) AS numeric_facts FROM reviewed_sources s LEFT JOIN materials m USING(doi) LEFT JOIN material_facts f USING(material_key) GROUP BY s.doi;'
        sources=[dict(r) for r in db.connection.execute(sql)]
        for r in sources:r.update(batch='批次02' if r['doi'] in ['10.1021/acsenvironau.3c00048','10.3390/molecules29225413'] else '批次01',scope='合成碳方法参考' if r['doi']=='10.3390/molecules29225413' else '材料/测试候选待用途审查')
        query('source_summary',sources,['reviewed_sources','materials','material_facts'],sql,'按DOI汇总数值单元，不是训练样本。',['六来源仅完成指定表格范围，尚未称全文全部利用。'])
        issue_labels={'reported_XPS_sum':'XPS合计限定','surface_partition_inconsistent':'孔面积分项不符','body_table_disagreement':'正文与表数值竞争','author_ratio_vs_volumes':'报告比例与孔容不符','reported_precision_variants':'数值精度表述不同','cycling_configuration_electrolyte_and_current_roles':'循环协议绑定冲突','own_table_conflict':'酸碱EIS表值冲突','element_label_binding_energy_conflict':'XPS元素标签与能量冲突','percentage_basis_not_explicit':'百分比基准未知','control_alias_not_merged':'无活化对照别名未合并'}
        actions={'PC800_XPS':'原值合计99.7%，不补元素、不归一化。','corn_cob_BET':'表1770与正文1705并存，标准面积待定。','corn_cob_volume_ratio':'孔容和报告比例并存，不用计算值覆盖。','corn_grain_precision':'保留各处精度，不能算作三次测量。','corn_husk_surface':'分项面积超过总量，隔离且不换列。','purple_EIS_AC5':'保留酸/碱四个竞争值，不自动交换列。','purple_XPS_AC30':'保留元素标签与能量冲突，C/O标准值冻结。','purple_control_alias':'SI无活化对照单独保存，别名不自动合并。','purple_microporosity':'微孔率基准未知，不猜面积比或体积比。','purple_cycle_protocol':'保留配置、电解液及电流角色竞争，循环标准条件留空。'}
        issues=[dict(doi=r['doi'],sample=r['sample_name'],issue=issue_labels.get(r['issue'].get('kind'),r['issue'].get('kind')),action=actions[r['issue_id']],details=json.dumps(r['issue'],ensure_ascii=False)) for r in db.issues()]
        query('issues',issues,['scientific_issues'],'SELECT * FROM scientific_issues;','每个争议/限定项，不是独立样本。',['保留双方原值与出处，不以性能或新版本择值。'])
    with open_database() as cycling:main_rows=cycling.fetch('reported_3e').rows
    fixed=json.loads((ROOT/'docs/DATA_CORRECTION_GOAL.json').read_text('utf8'))
    active=json.loads((ROOT/'docs/LITERATURE_EXTRACTION_GOAL.json').read_text('utf8'))
    overview=[dict(summary,goal_status=active['app_goal_status_last_confirmed'],formal_main_rows=len(main_rows),formal_main_sources=len({r['source_group'] for r in main_rows}),fixed_goal_records=fixed['fixed_record_count'],fixed_resolved=fixed['scientifically_resolved_in_goal'],fixed_pending=fixed['current_pending'])]
    query('overview',overview,['summary.json','docs/LITERATURE_EXTRACTION_GOAL.json','cycling_v0_19.sqlite'],
      'SELECT COUNT(*) FROM materials; SELECT COUNT(*) FROM material_facts WHERE value IS NOT NULL; SELECT COUNT(*) FROM capacitance_observations WHERE value IS NOT NULL;',
      '新增文献层累计157个材料数值；循环主集43/31仍不变；原39条中38待证。',['历史725项与本页新增层重叠未完全对账，不能直接相加。'])
    progress=[dict(batch='批次01',numeric_facts=88,materials=15),dict(batch='批次02',numeric_facts=summary['cumulative_numeric_material_facts'],materials=summary['cumulative_materials'])]
    query('batch_progress',progress,['literature_pool_v1.summary.json','literature_pool_v2.summary.json'],
      'SELECT COUNT(*) FROM material_facts WHERE value IS NOT NULL; -- 分别读取两个封版版本',
      '同一证据层两个批次的累计快照88→157，不内插每日进度。')
    result=dict(id=existing['id'],surface='dashboard',title='文献提取与补正进度',generatedAt=now,status='reviewed_local_snapshot',buildStatus=args.build_status,filters=[],queries=queries)
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(dict(snapshot=str(target.relative_to(ROOT)),queries={k:len(v['rows']) for k,v in queries.items()},buildStatus=args.build_status),ensure_ascii=False))
if __name__=='__main__':main()
