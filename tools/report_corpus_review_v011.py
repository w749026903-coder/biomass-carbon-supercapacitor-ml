"""Source/test utilization and component-task reconciliation, without admissions."""
from pathlib import Path
import collections,csv,importlib.util,json,sqlite3,sys
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'全库复检与特征补提取_20261021'
RELEASE=ROOT/'循环稳定性数据库_v0.11_全库复检与材料特征_20261021'


def read(path):return json.loads(path.read_text('utf-8'))


def write(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n','utf-8')


def csv_write(path,rows,fields):
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)


def main():
    if (RELEASE/'merge_manifest.json').exists():
        raise FileExistsError('Do not overwrite sealed utilization/component reports.')
    spec=importlib.util.spec_from_file_location('_v011_report_api',RELEASE/'ml_data.py');api=importlib.util.module_from_spec(spec);sys.modules[spec.name]=api;spec.loader.exec_module(api)
    c=sqlite3.connect((OUT/'full_corpus_search_native.sqlite').as_uri()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row
    with api.Database() as db:
        rows=db.fetch('all_review').rows;by_identity=collections.defaultdict(list);tests=[]
        for row in rows:
            by_identity[row['identity_key']].append(row)
            fields=[f for f in db.contract['core_features'] if f!='reference_electrode' or row['system']=='3E']
            missing=[f for f in fields if row.get(f) is None]
            approved=row['admission_profiles_v11']
            if approved:reason='已逐测试准入:'+','.join(approved)
            elif missing:reason='核心字段待补:'+','.join(missing)
            else:reason='核心字段齐备仍未准入；逐项核对范围、标签、基线、冲突与复用关系'
            tests.append({'endpoint_id':row['endpoint_id'],'doi':row['identity_key'].removeprefix('doi:'),'sample':row['sample_name'],'system':row['system'],'method':row['method'],'cycle_count':row.get('cycle_count'),'retention_pct':row.get('retention_pct'),'retention_relation':row.get('retention_relation'),'admitted_profiles':','.join(approved),'missing_core_fields':','.join(missing),'current_disposition':reason,'open_issues':json.dumps(row.get('open_issues',[]),ensure_ascii=False),'evidence_entry':'db.evidence(endpoint_id); db.holds(endpoint_id)'})
        csv_write(OUT/'逐测试利用与待补证据.csv',tests,list(tests[0]))
        material_counts=collections.Counter(m['doi'] for file in ['reviewed_curation.json','reviewed_materials_xml.json','reviewed_materials_pdf.json'] for m in read(OUT/file)['reviewed_materials'])
        sources=[]
        for identity in c.execute('select * from identities order by identity_key'):
            key=identity['identity_key'];linked=[dict(r) for r in c.execute('select distinct s.* from sources s join identity_sources i using(sha256) where i.identity_key=?',(key,))]
            native=[s for s in linked if s['scan_state']=='native_text_searched']
            metadata=[json.loads(r[0]) for r in c.execute('select metadata_json from identity_metadata_v11 where identity_key=?',(key,))]
            years={str(d['year']) for m in metadata for d in m['dates'] if d.get('year')}
            years|={str(r['source_year']) for r in by_identity[key] if r.get('source_year') is not None}
            types={m['article_type'] for m in metadata if m.get('article_type')}
            data=by_identity[key];three=sum('reported_3e' in r['admission_profiles_v11'] for r in data);two=sum('reported_2e' in r['admission_profiles_v11'] for r in data)
            if three:status='已有3E准入；本轮材料特征复检'
            elif two:status='已有2E准入；按配置独立使用'
            elif any(r['system']=='3E' for r in data):status='已有3E观察待逐测试审查'
            elif data:status='已有结构化观察；保持当前范围/缺证/敏感性处置'
            elif types & {'review-article','systematic-review','meta-analysis'}:status='综述或方法资料；不直接作为本研究实验标签'
            elif years and all(y.isdigit() and int(y)<2023 for y in years):status='已检索；当前年份范围外资料'
            elif not native:status='未关联可检索原生内容；待获取或身份核对'
            else:status='已全文/表格检索；尚未逐测试科学终审'
            sources.append({'identity_key':key,'doi':identity['doi'],'title':identity['title'] or next((m['title'] for m in metadata if m.get('title')),''),'identity_basis':identity['basis'],'year_candidates':','.join(sorted(years)),'article_type_candidates':','.join(sorted(types)),'native_source_contents':len(native),'formats':','.join(sorted({s['format'] for s in linked})),'structured_observations':len(data),'reported_3e_records':three,'reported_2e_records':two,'reviewed_materials':material_counts[identity['doi']],'disposition':status,'status_boundary':'来源盘点/书目线索不是新增科学准入'})
        csv_write(OUT/'逐来源科学利用与去向.csv',sources,list(sources[0]))
        review3=[r for r in rows if r['system']=='3E'];pending3=[r for r in review3 if 'reported_3e' not in r['admission_profiles_v11']]
        summary={'catalog_identity_entries_not_verified_paper_count':len(sources),'source_dispositions':dict(collections.Counter(s['disposition'] for s in sources)),
                 'all_structured_observations':len(rows),'3E_review_records':len(review3),'3E_review_source_groups':len({r['source_group'] for r in review3}),
                 '3E_pending_records':len(pending3),'3E_pending_core_missing':{f:sum(r.get(f) is None for r in pending3) for f in db.contract['core_features']},
                 '3E_pending_complete_core_records':[r['endpoint_id'] for r in pending3 if all(r.get(f) is not None for f in db.contract['core_features'])],
                 'reported_3e_records':len(db.fetch().rows),'reported_3e_source_groups':len({r['source_group'] for r in db.fetch().rows}),'model_fits':0}
        write(OUT/'utilization_summary.json',summary)
    old_tasks=list(csv.DictReader((ROOT/'新增文献整理_20261020/95项下载任务对账.csv').open(encoding='utf-8-sig',newline='')))
    task_rows=[]
    for old in old_tasks:
        doi=old['DOI'].lower();key='doi:'+doi
        components=[dict(r) for r in c.execute('select distinct s.format,s.path,s.sha256,s.scan_state,i.role from sources s join identity_sources i using(sha256) where i.identity_key=?',(key,))]
        main=[s for s in components if s['format']=='pdf' and s['role']=='main' and s['scan_state']=='native_text_searched']
        si=[s for s in components if s['role'] in ['supplementary_agent_title_authors_verified','supplementary_package_verified_href','supplementary_verified_receipt'] and s['scan_state']=='native_text_searched']
        si_candidates=[s for s in components if s['role'].lower() in ['si','supplement'] and s['format'] in ['pdf','docx','zip']]
        need_si=old['需要下载']=='已声明SI';have_main=old['本批正文取得']=='True' or bool(main)
        if need_si:status='已取得身份核对SI；不等于科学准入' if si else '已有SI候选先核身份' if si_candidates else '缺已声明SI'
        else:status='正文PDF已有；SI存在性另核' if have_main else '缺正文PDF'
        task_rows.append({'task_id':old['编号'],'doi':doi,'title':old['题名'],'requested_component':old['需要下载'],'current_status':status,'main_pdf_available':have_main,'identity_verified_SI_available':bool(si),'existing_SI_candidates':len(si_candidates),'matched_paths':json.dumps(sorted({s['path'] for s in main+si+si_candidates}),ensure_ascii=False),'request_detail':old['排序理由']})
    priority=[('10.1016/j.biombioe.2026.109160','NCHU20','原文明确引用SI TableS1/S3；需NCHU20自身孔结构和元素分析，不能借NCHU40的6.2wt%N'),('10.1016/j.jenvman.2025.125582','NPC-700-6','SI TableS2、FigS2及初始XPS组成；不使用50000圈后表征作为预测输入'),('10.1016/j.biombioe.2026.109168','CCL-K2CO3-1-700','SI TableS3/S4/S5；区分初始XPS原子百分比与元素分析质量百分比')]
    for doi,sample,detail in priority:
        task_rows.append({'task_id':'FEATURE_SI:'+sample,'doi':doi,'title':sample,'requested_component':'自身论文的原始SI','current_status':'正文已在本地；本轮未找到关联SI','main_pdf_available':True,'identity_verified_SI_available':False,'existing_SI_candidates':0,'matched_paths':'[]','request_detail':detail})
    csv_write(OUT/'需补资料_DOI与组件明细.csv',task_rows,list(task_rows[0]))
    write(OUT/'component_reconciliation_summary.json',{'previous_tasks':95,'previous_task_status_counts':dict(collections.Counter(t['current_status'] for t in task_rows[:95])),'new_targeted_SI_requests':3,'unverified_candidate_is_not_completed_component':True,'scientific_admissions_from_reconciliation':0})
    lines=['# 需补资料：优先补已有论文的SI','','这轮先转化已有全文。以下三项正文已经在本地，需要对应原始SI；不是重复索取正文。已对项目及外部文献库和112份压缩包内容去重对账，未发现这三项已关联的SI。','','| DOI | 样品 | 所需组件/用途 |','| --- | --- | --- |']
    lines += ['| '+doi+' | '+sample+' | '+detail+' |' for doi,sample,detail in priority]
    lines += ['','另有4条AHPC同篇样品循环观察已暂存，需要核实各自归一化参照适用性；不额外要求精确第1圈，也不把已存在的AHPC-850曲线当作其它样品的原始曲线。原论文DOI为10.3390/molecules31132329，正文已具备；不能断言作者另有可下载SI。','','旧95项任务的当前组件候选及缺件见[完整对账](需补资料_DOI与组件明细.csv)。正文、SI、身份核实和逐测试准入是不同状态。']
    (OUT/'需补资料_DOI清单.md').write_text('\n'.join(lines)+'\n','utf-8')
    c.close();print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
