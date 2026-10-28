"""Source-bridge progress, complete usage export and next main-source queue."""
from pathlib import Path
import collections,csv,html,io,json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.extract_opb_main_v5 import OUT,DB,BASE,EIDS,read,write,sha
from data.training_store import open_training_datasets

def report():
    assert not(OUT/'merge_manifest.json').exists()
    s=read(OUT/'summary.json')
    with open_training_datasets(DB,sha(DB))as d:
        for name,only in [('all_fact_usage.csv',False),('unconnected_numeric_queue.csv',True)]:
            stream=io.StringIO(newline='');fields=['fact_id','doi','sample_name','material_stage','field_name','value','unit','source_path','source_sha256','locator','disposition','task_receipts'];w=csv.DictWriter(stream,fieldnames=fields,lineterminator='\n');w.writeheader()
            for rr,uu,disp in d.connection.execute('select f.record_json,u.record_json,u.disposition from facts f join usage_ledger u using(fact_id)order by f.fact_id'):
                f=json.loads(rr);u=json.loads(uu)
                if only and(f['value']is None or u['uses']):continue
                row={k:f.get(k)for k in fields};row.update(disposition=disp,task_receipts=len(u['uses']));w.writerow(row)
            (OUT/name).write_text(stream.getvalue(),encoding='utf-8-sig')
        old=read(BASE/'main3e_unlinked_priorities.json');pending=[r for r in old['next_review_records']if r['endpoint_id']not in EIDS.values()];groups=collections.defaultdict(list)
        for r in pending:groups[r['doi']].append(r)
        queue=dict(main3e_rows=47,linked_rows=21,unlinked_rows=26,unlinked_main_source_families=len(groups),next_review_records=pending,
          priority_sources=[dict(doi=doi,main_rows=len(rs),samples=sorted({r['sample_name']for r in rs}),local_sources=rs[0]['local_sources'])for doi,rs in sorted(groups.items(),key=lambda x:(-len(x[1]),x[0]))])
        write(OUT/'main3e_unlinked_priorities.json',queue)
        main={r['row_id']:r for r in d.rows('cycle:reported_3e')};details=[]
        for sample,eid in EIDS.items():
            r=main[eid];details.append(dict(endpoint_id=eid,sample=sample,retention_pct=r['target'],BET_m2_g=r['features']['BET_m2_g'],new_nonmissing_cells=len(r['v5_material_evidence']['added_nonmissing_fields']),existing_attested_cells=len(r['v5_material_evidence']['existing_values_attested']),new_fields=r['v5_material_evidence']['added_nonmissing_fields']))
        write(OUT/'main_feature_changes.json',details)
        write(OUT/'main_feature_coverage.json',d.feature_coverage('cycle:reported_3e'))
        ck=len({json.loads(r[0])['doi']for r in d.connection.execute('select record_json from facts')});write(OUT/'coverage_counts.json',dict(registered_sources=s['reviewed_sources'],material_fact_sources=ck,main_joined_rows=21,main_total_rows=47,unlinked_main_rows=26,whole_paper_completion_claimed=False))
    rows=''.join('<tr><td>'+html.escape(r['sample'])+'</td><td>'+str(r['retention_pct'])+'</td><td>'+str(r['BET_m2_g'])+'</td><td>+'+str(r['new_nonmissing_cells'])+'</td><td>'+str(r['existing_attested_cells'])+'</td></tr>'for r in details)
    page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>主训练集文献关联 · OPB系列</title><style>body{font:16px/1.7 system-ui,"Microsoft YaHei",sans-serif;background:#f2f5f1;color:#233a31;margin:0}main{max-width:1100px;padding:24px;margin:auto}.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.card,section{padding:20px;background:white;border:1px solid #dce5dd;border-radius:12px;margin:18px 0}.card{margin:0}.card strong{display:block;font-size:28px;color:#207154}h1{line-height:1.3}.table{overflow:auto}table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:10px;border-bottom:1px solid #e1e7e1;white-space:nowrap}li{margin:9px 0}a{color:#256c54}.muted{color:#65776c}code{overflow-wrap:anywhere}@media(max-width:650px){main{padding:14px}.cards{grid-template-columns:repeat(2,1fr)}.card{padding:12px}h1{font-size:26px}}</style><main><p class="muted">2026-10-28 · 全量目标active · 本轮拟合0</p><h1>优先补齐主训练记录：OPB系列关联完成</h1><div class="cards"><div class="card"><strong>21 / 47</strong>规范材料关联，原17条</div><div class="card"><strong>+60</strong>主集非空特征单元</div><div class="card"><strong>44</strong>已有单元补充原文回执</div><div class="card"><strong>70.11%</strong>3,391 / 4,837数值接入</div></div>
<section><h2>这次直接补的是主任务</h2><p>核对本地U002原文表1、制备与电化学方法、Raman段落及循环图文，把OPBNP、OPB、OPNP、OPC接到各自材料。原有BET、孔体积、Raman比值和循环工况已经在用；已有非空值全部保留，新增值和证据分别计数，不把同一物性别名当新信息。</p><div class="table"><table><thead><tr><th>样品</th><th>保持率%，未改</th><th>既有BET m²/g</th><th>新增非空单元</th><th>已有单元补证</th></tr></thead><tbody>ROWS</tbody></table></div><p>四行属于同一DOI，仍是同一来源家族；主集47条/34来源不变，不是新增4篇独立文献。</p></section>
<section><h2>新增可用信息与边界</h2><ul><li>新增Raman D/G峰位、明确的前驱体/掺杂剂投料、水热前搅拌、KOH浸渍、预干燥、酸洗及最终干燥温度。共同工况按作者明确对照程序绑定，不给未报告的“过夜”编时长。</li><li>1–2mg/cm²保存为电极负载下界/上界。精确点值仍未知，没有填1.5；这两个工况字段不拿来预测材料自身BET等本征属性。</li><li>KOH比例3指KOH对水热产物的质量比，不是对初始橙皮；没有凭初始2g橙皮推算KOH质量。</li><li>HK微孔体积方法保留；600°C/3h属于共同煅烧与KOH活化步骤，不拆成两个独立热处理。新增60个单元包括8个区间边界，不能当60个独立物理参数。</li></ul></section>
<section><h2>新增数据与未解决问题</h2><p>本批114项事实中110为数值，104项有实际输入/辅助目标回执；新8条普通三电极GCD报告。普通用途216行/32来源，与含图用途394行/32来源嵌套，不能相加成610独立实验。父版本原始行、目标、冻结与旧模型均保留。</p><p>XPS百分比按C/O/N/B/P对应关系保存，但质量/原子基准未明示，不填入原子百分比字段。BET沿用表1的1774.8，并保留引言774.8异文与选择依据；未声称作者已更正。SI本次未取得，设备电容公式、其余倍率及SIB数据按用途分别暂存，不变成新的循环准入。</p></section>
<section><h2>下一批优先已有本地原文</h2><p>主集仍有26条记录、25个来源待规范桥接，均已有本地原文索引。下一批先ALPC-800两工况（10.1021/acssusresmgt.3c00028），核读U024正文及SUP_139本地SI，再处理其它主体系缺口、固定37待证与未完成表图。</p><p>当前入口：<code>data.training_store.open_training_datasets()</code>，只读连接受SHA保护的父版本。更新的只是有前后哈希与证据的派生输入；原始事实不覆写。累计数值接入率不等于整篇文献利用率、独立样本数或已拟合使用率。</p></section>
<section><h2>证据与核验</h2><p><a href="README.md">调用说明</a> · <a href="main_feature_changes.json">逐行特征变化</a> · <a href="overlay_changes.json">更新前后与出处</a> · <a href="pdf_primary_verification.json">独立PDF数值复核</a> · <a href="unconnected_numeric_queue.csv">未接入队列</a> · <a href="verification.json">数据核验</a></p><p>本批无新模型拟合、无新循环准入。目标继续执行，不声称全部论文已完成。</p></section></main></html>'''
    (OUT/'主训练集关联与数据进度.html').write_text(page.replace('ROWS',rows),encoding='utf8')
    print('Primary main-task report and next26-row queue saved.')

if __name__=='__main__':report()
