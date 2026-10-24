"""Seal the verified v0.15 local batch and promote the stable pointer once."""
from pathlib import Path
import collections,csv,json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'tools')]
from inspect_existing_sources_v015 import BATCH,read,sha
from build_existing_sources_v015 import OUT,write

def main():
    if (OUT/'merge_manifest.json').exists():raise FileExistsError('Already sealed; verify instead of re-finalizing.')
    stats=read(BATCH/'coverage_and_dispositions.json');verification=read(OUT/'verification.json')
    assert verification['passed'] and stats['model_fits']==0
    remaining=read(BATCH/'remaining_pending_records.json');grouped=collections.defaultdict(list)
    for r in remaining:grouped[r['source_group']].append(r)
    def need(issues):
        actions=[];joined=' '.join(issues).lower()
        if 'bet' in joined:actions.append('自身样品数值BET表或原始吸附分析报告；不借其它样品/复合物值')
        if 'current' in joined or 'a_g' in joined:actions.append('可绑定到该循环测试的恒流A/g与实验程序；不借倍率表征电流')
        if any(x in joined for x in ['window','potential','scale','reference','calomel','hghgo']):actions.append('实际循环GCD上下限和参比/电位标尺，或方法引用正式正文')
        if any(x in joined for x in ['peer_review','published_version','year']):actions.append('正式期刊全文与书目身份/年份，逐值核对预印本与刊本')
        if any(x in joined for x in ['fe_state','metal','k_f','salt','scope']):actions.append('成品化学态、残留/去除或物相证据，按既有材料范围裁定')
        if any(x in joined for x in ['retention','label','pct','sample_identity','concentration','1m_vs6m','10_vs20','cycle_count']):actions.append('作者勘误、同一终点/样品/协议的原始数据或明确补充说明；保留竞争原值')
        return '；'.join(dict.fromkeys(actions)) or '按逐条open_issues取得可绑定的原始证据'
    with (BATCH/'需补原始证据.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['source_group','endpoint_count','samples','endpoint_ids','open_issues','next_evidence','local_scope']);w.writeheader()
        for group,rs in sorted(grouped.items()):
            issues=list(dict.fromkeys(i for r in rs for i in r['open_issues']))
            w.writerow(dict(source_group=group,endpoint_count=len(rs),samples='; '.join(r['sample_name'] for r in rs),endpoint_ids='; '.join(r['endpoint_id'] for r in rs),open_issues='; '.join(issues),next_evidence=need(issues),local_scope='本轮仅复核已有文件；未重新访问出版社，不声称不存在SI或勘误'))
    receipt={'schemaVersion':1,'items':[
        {'id':'feature-coverage','title':'已有材料特征补齐与方法纠错','queries':[{'id':'fixed-cohort','source':{'label':'v0.15固定主集核验','files':[{'label':'coverage_and_dispositions.json'},{'label':'field_changes.json'}],
            'metricDefinitions':[{'label':'可选字段覆盖率','definition':'覆盖率是在固定42条三电极记录的原18项可选字段中，非空单元占756个单元的比例。'}],
            'filters':['固定42条主集记录','原18项可选字段'],
            'caveats':['额外候选与4处已有值纠错不计入21个新增非空单元。','本轮没有训练，不能据此宣称误差改善。']},
            'columns':[{'field':'version','label':'版本'},{'field':'nonmissing','label':'非空单元'},{'field':'coverage_pct','label':'覆盖率（%）'}],
            'rows':[{'version':'v0.14','nonmissing':299,'coverage_pct':round(100*299/756,2)},{'version':'v0.15','nonmissing':320,'coverage_pct':round(100*320/756,2)}],
            'methods':[{'language':'calculation','code':'299 / 756 * 100 = 39.5503%\n320 / 756 * 100 = 42.3280%\n新增非空单元 = 320 - 299 = 21'}]}]},
        {'id':'pending-review','title':'41条逐项处置及剩余缺证','queries':[{'id':'dispositions','source':{'label':'逐测试复核台账','files':[{'label':'41条逐项处置.csv'},{'label':'reviewed_curation.json'}],
            'filters':['固定41条原待补证记录'], 'caveats':['39条仍待证；本轮新增准入0条，主集仍42条/30来源。','范围外两条保留原文和原值，没有删除历史数据。']},
            'columns':[{'field':'status','label':'处置结果'},{'field':'records','label':'记录数'}],
            'rows':[{'status':'确认现行范围外','records':2},{'status':'已补部分缺项，仍待证','records':2},{'status':'关键缺证或冲突仍在','records':37}]}]}
    ]}
    write(BATCH/'sources_receipt.json',receipt)
    # Keep original evidence images, all used/referenced by the render record.
    write(BATCH/'storage_review.json',dict(new_original_downloads=0,full_text_index_copies=0,temporary_or_failed_downloads_created=0,
        evidence_render_files=len(list((BATCH/'evidence_images').glob('*.png'))),render_files_retained_as_evidence=True,deleted_bytes=0,
        rationale='No disposable task cache or failed downloads were created; originals and evidence are retained.'))
    outputs=[]
    for folder in [BATCH,OUT]:
        for p in sorted(folder.rglob('*')):
            if p.is_file():outputs.append(dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),bytes=p.stat().st_size))
    for name in ['inspect_existing_sources_v015.py','curate_existing_sources_v015.py','build_existing_sources_v015.py','verify_existing_sources_v015.py','finalize_existing_sources_v015.py']:
        p=ROOT/'tools'/name;outputs.append(dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),bytes=p.stat().st_size))
    manifest=dict(schema='evidence_review_delivery_v1',version='v0.15',local_review_complete=True,ready_for_training_inputs=True,
        all_records_admitted=False,all_scientific_questions_resolved=False,model_fits=0,new_admissions=0,
        fixed_pending_reviewed=41,current_pending=39,outside_scope_decided=2,ready_for_merge=True,
        reviewer='Codex agent targeted original-source review; not independent expert sign-off',
        parent_database_sha256=read(BATCH/'baseline_inventory.json')['parent_pointer']['sha256'],database_sha256=sha(OUT/'cycling_v0_15.sqlite'),
        verification_checks=verification['check_count'],cohorts=stats['cohorts'],outputs=outputs)
    write(OUT/'merge_manifest.json',manifest)
    pointer=dict(version_directory=OUT.name,database_file='cycling_v0_15.sqlite',sha256=manifest['database_sha256'],
        parent_database_file='循环稳定性数据库_v0.14_主集参数精提取_20261022/cycling_v0_14.sqlite',default_profile='reported_3e',
        stage='existing_table_figure_SI_fields_method_correction_and_fixed41_dispositions',ready_for_training_inputs=True,
        research_training_authorized=False,all_records_admitted=False)
    write(ROOT/'data/current_database.json',pointer)
    print(json.dumps(dict(sealed_outputs=len(outputs),database_sha256=pointer['sha256'],pending_sources=len(grouped),pending_records=39,checks=verification['check_count']),ensure_ascii=False))
if __name__=='__main__':main()
