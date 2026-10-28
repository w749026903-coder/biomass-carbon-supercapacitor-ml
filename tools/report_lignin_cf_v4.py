"""Usage receipts and a human-readable progress report for the v4 overlay."""
from pathlib import Path
import collections,csv,html,io,json,sqlite3,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.extract_lignin_cf_v4 import OUT,DB,BASE,read,write,sha
from data.training_catalog import open_training_datasets

def report():
    assert not(OUT/'merge_manifest.json').exists()
    s=read(OUT/'summary.json');reports=read(OUT/'capacity_reports.json')
    with open_training_datasets(DB,sha(DB))as d:
        for name,only_unconnected in [('all_fact_usage.csv',False),('unconnected_numeric_queue.csv',True)]:
            stream=io.StringIO(newline='');fields=['fact_id','doi','sample_name','material_stage','field_name','value','unit','source_path','source_sha256','locator','disposition','task_receipts'];w=csv.DictWriter(stream,fieldnames=fields,lineterminator='\n');w.writeheader()
            for rr,uu,disp in d.connection.execute('select f.record_json,u.record_json,u.disposition from facts f join usage_ledger u using(fact_id)order by f.fact_id'):
                f=json.loads(rr);u=json.loads(uu)
                if only_unconnected and(f['value']is None or u['uses']):continue
                row={k:f.get(k)for k in fields};row.update(disposition=disp,task_receipts=len(u['uses']));w.writerow(row)
            (OUT/name).write_text(stream.getvalue(),encoding='utf-8-sig')
        by=collections.defaultdict(collections.Counter)
        for rr,uu in d.connection.execute('select f.record_json,u.record_json from facts f join usage_ledger u using(fact_id)'):
            f=json.loads(rr);u=json.loads(uu);a=by[f['doi']];a['facts']+=1;a['numeric']+=f['value']is not None;a['connected']+=bool(u['uses'])
        source_rows=[dict(doi=doi,**v,numeric_connection_rate=v['connected']/v['numeric']if v['numeric']else None,whole_paper_complete=False)for doi,v in sorted(by.items())];write(OUT/'source_fact_utilization.json',source_rows)
    storage=dict(parent_bytes=(BASE/'training_data_v3.sqlite').stat().st_size,extension_bytes=DB.stat().st_size,
      avoided_new_full_database_copy_bytes=(BASE/'training_data_v3.sqlite').stat().st_size-DB.stat().st_size,
      description='Avoided duplicate allocation, not deletion or released disk space; parent v3 is required and SHA-pinned.')
    write(OUT/'storage_receipt.json',storage)
    rows=''.join('<tr><td>'+html.escape(r['sample_name'])+'</td><td>'+('电极CV'if r['kind']=='electrode_CV_F_g'else'器件GCD')+'</td><td>'+str(r['value'])+'</td><td>'+html.escape(r['unit'])+'</td><td>'+('10mV/s'if r['kind']=='electrode_CV_F_g'else str(r['conditions']['reported_current_mA_g'])+'mA/g')+'</td></tr>'for r in reports if r['kind']in ['electrode_CV_F_g','gel_device_GCD_mF_g'])
    page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>文献利用目标 · 木质素碳布与凝胶</title><style>body{font:16px/1.7 system-ui,"Microsoft YaHei",sans-serif;margin:0;background:#f3f5f1;color:#243a32}main{max-width:1120px;padding:24px;margin:auto}h1{line-height:1.35}.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.card,section{padding:20px;background:white;border:1px solid #dce5dd;border-radius:12px;margin:18px 0}.card{margin:0}.card strong{display:block;color:#206e55;font-size:28px}.table{overflow:auto}table{border-collapse:collapse;width:100%;font-size:14px}th,td{text-align:left;padding:9px;border-bottom:1px solid #e1e8e2;white-space:nowrap}a{color:#216a53}img{max-width:100%;height:auto}code{overflow-wrap:anywhere}.muted{color:#64796c}li{margin:9px 0}@media(max-width:650px){main{padding:14px}.cards{grid-template-columns:repeat(2,1fr)}.card{padding:12px}h1{font-size:26px}}</style><main><p class="muted">2026-10-28 · 总体目标执行中 · 本批新增拟合0</p><h1>继续利用已有文献：木质素涂层碳布与凝胶器件</h1><div class="cards"><div class="card"><strong>+140</strong>材料/制备事实，113数值</div><div class="card"><strong>+109</strong>数值实际接入</div><div class="card"><strong>34</strong>可调用电容报告行</div><div class="card"><strong>69.54%</strong>累计3,287 / 4,727</div></div>
<section><h2>原文读到了什么</h2><p>已核读正文67个段落范围、三张主结果表和试剂表、六页补充材料及SI TableS1，区分商用碳布、木质素涂层电极、独立木质素材料和凝胶器件。18项登记包含10电极、2独立木质素材料、3凝胶器件和3项待核TGA样品绑定，不是18个独立来源。</p><p>39条原始电容报告中，34条进入分用途输入；3条木质素归一化值及2条弯折后CV报告仅作审查。另有9条弯折前EIS响应输入，按原文保存Rs、Rs+Rct和器件有效电导率，未当成纯电解质电导。全部来自一个来源家族，不能独立验证跨来源预测。</p></section>
<section><h2>避免了几类严重误用</h2><ul><li>99%是弯折后恢复，不是循环保持率。图7D是绝对电容衰减，纵轴mF/g；这里只读10个有界位置，不从首点猜归一化基线。</li><li>表3的电流是mA/g，0.15mA/g明确换算为0.00015A/g；原始单位、公式核对和换算回执同时保存，不能误当0.15A/g。</li><li>复合碳布BET测量不稳定，不能套用独立木质素的0.3576或0.3439m²/g。普通生物质碳主集没有混入商用碳布或凝胶。</li><li>正文TGA样品名与SI的C后缀有矛盾，三项真实负载量保留但不擅自绑定；原始归一化电容仍可审查，不直接作为统一质量口径。</li><li>预测电容的输入没有放入其放电时间，避免把C=I·Δt/ΔV里的目标公式直接泄漏给模型。被引旧器件不算本篇新实验，并与前作一起隔离。</li></ul></section>
<section><h2>新增明确用途的CV/GCD报告</h2><div class="table"><table><thead><tr><th>样品</th><th>方法</th><th>原值</th><th>原单位</th><th>工况</th></tr></thead><tbody>ROWS</tbody></table></div><p>水系三电极CV、凝胶器件CV的质量/面积口径、器件GCD和绝对循环电容曲线分别调用，不合并成统一保持率标签。</p></section>
<section><h2>绝对电容曲线与读取边界</h2><img src="evidence/Figure7D_absolute_Csp_review.png" alt="原Figure7D局部：黑色为绝对电容，红色为库仑效率"><p>黑色曲线按名义10、20、30、40、50、60、70、80、90、99圈读取；圈号区间约±2、纵值读取容差±4mF/g，不是作者SD或独立重复实验。近原点的无标签标记不作为第1圈数据。没有将曲线转成保持率百分比，也没有据此新增循环准入。</p></section>
<section><h2>本地数据库与进度</h2><p>本批SQLite仅约EXTENSION_MB MB，以只读方式连接受SHA保护的v3，不再复制约51MB旧库。所有历史版本和原文保留；这是避免重复分配，不是删除历史释放空间。当前入口为<code>data.training_catalog.open_training_datasets()</code>，旧入口仍可重现原版。</p><p>主三电极47/34、双电极31/25、原37待证和历史冻结保持；本轮新增训练0、循环准入0。数值接入率仅指已提取材料事实的回执，不代表全部论文已利用完或模型已学会。尚有1440项数值未进预测输入，243项非点/空值；本文其余曲线与全库队列继续处理。</p><p><a href="README.md">调用说明</a> · <a href="new_facts.json">事实与原值</a> · <a href="capacity_reports.json">电容报告</a> · <a href="unconnected_numeric_queue.csv">未接入队列</a> · <a href="scientific_issues.json">争议与用途边界</a> · <a href="verification.json">独立核验</a></p></section></main></html>'''
    (OUT/'文献接续与数据库进度.html').write_text(page.replace('ROWS',rows).replace('EXTENSION_MB',f'{DB.stat().st_size/1_000_000:.2f}'),encoding='utf8')
    print('v4 overlay report and complete usage exports saved.')

if __name__=='__main__':report()
