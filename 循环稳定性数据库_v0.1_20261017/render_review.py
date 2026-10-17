"""Generate a local read-only review page, priority list, and executed SQL notebook."""
import html,json,pathlib,re,sqlite3,uuid
ROOT=pathlib.Path(__file__).resolve().parent
c=sqlite3.connect((ROOT/'cycling_v0_1.sqlite').as_uri()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row
def query(sql):return [dict(r) for r in c.execute(sql)]
def esc(v):return html.escape('—' if v is None else str(v))
def local(p,label):return '<a href="'+pathlib.Path(p).as_uri()+'">'+esc(label)+'</a>'
papers=query('SELECT * FROM papers ORDER BY category,paper_id')
records=query('SELECT * FROM endpoint_review ORDER BY paper_id,material_id,cycle_test_id,cycle_count')
materials=query('SELECT m.*,count(e.record_id) endpoints FROM materials m JOIN cycling_tests t USING(material_id) JOIN cycling_endpoints e USING(cycle_test_id) GROUP BY m.material_id ORDER BY m.paper_id,m.material_id')
issues=query('SELECT * FROM issues ORDER BY CASE severity WHEN \'high\' THEN 0 ELSE 1 END,paper_id,record_id,issue_id')
primary=query('SELECT * FROM primary_screening_candidates ORDER BY paper_id,cycle_count')
primary_ids={r['record_id'] for r in primary}
summary=json.loads((ROOT/'数据库核验与覆盖摘要.json').read_text(encoding='utf-8'))
systems={'2E_symmetric':'两电极对称','3E':'三电极','2E_symmetric_gel':'两电极对称凝胶','2E_same_carbon_mass_unbalanced':'同碳材料/质量不平衡','Zn_hybrid':'锌混合体系','Li_half_cell':'锂半电池','2E_asymmetric':'两电极非对称','2E_asymmetric_gel':'非对称凝胶','system_pending':'体系待核','2E_as_reported':'两电极（原文口径）'}
categories={'A':'优先提取','B':'分体系/限定字段','C':'待核/冻结','D':'方法/背景','E':'范围外'}
def table(headers,rows):return '<div class="scroll"><table><thead><tr>'+''.join('<th>'+h+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join(rows)+'</tbody></table></div>'
def tr(cells,search,kind=''):return '<tr data-kind="'+html.escape(kind,quote=True)+'" data-search="'+html.escape(search.lower(),quote=True)+'">'+''.join('<td>'+x+'</td>' for x in cells)+'</tr>'
paperrows=[]
for r in papers:
 paperrows.append(tr([esc(r['paper_id']),esc(r['year']),esc(categories[r['category']]),local(r['main_path'],r['title']),esc(r['doi']),esc(r['main_format']),esc(r['archive_restrictions'])],json.dumps(r,ensure_ascii=False),r['category']))
recordrows=[]
for r in records:
 relation={'eq':'','approx':'约','gt':'>'}[r['retention_relation']]
 val='—' if r['retention_pct'] is None else relation+str(r['retention_pct'])
 status='冲突/待核' if r['conflict'] else ('主体系优先核录' if r['record_id'] in primary_ids else '分体系/待核')
 pages=json.loads(r['evidence_pages_json']);loc=('PDF页 '+','.join(map(str,pages))) if pages else (r['evidence_locator'] or '见原始文献')
 detail=local(r['evidence_path'],'打开出处')+'<br>'+esc(loc)+'<details><summary>备注和准入状态</summary><p>'+esc(r['note'])+'</p><p>待逐记录终审；未准入训练</p></details>'
 recordrows.append(tr([esc(r['record_id']),esc(r['sample_name']),esc(systems.get(r['system'],r['system'])),esc(r['method']),esc(r['cycle_count']),esc(val),esc(r['current_density_A_g']),esc(r['electrolyte']),esc(r['concentration_value'])+' '+esc(r['concentration_unit']),esc(r['voltage_lower_V'])+' ～ '+esc(r['voltage_upper_V']),esc(r['BET_m2_g']),esc(r['total_pore_volume_cm3_g']),esc(status),detail],json.dumps(r,ensure_ascii=False),'primary' if r['record_id'] in primary_ids else ('conflict' if r['conflict'] else 'other')))
materialrows=[tr([esc(r['material_id']),esc(r['paper_id']),esc(r['sample_name']),esc(r['endpoints']),'暂定论文内身份，跨文献独立性待审'],json.dumps(r,ensure_ascii=False)) for r in materials]
issuerows=[tr([esc(r['paper_id']),esc(r['record_id']),esc(r['code']),esc(r['description']),esc(r['scope'])],json.dumps(r,ensure_ascii=False)) for r in issues]
panes=[('records','循环终点',table(['记录编号','原样品名','体系','方法','循环次数','保持率 %','循环电流 A/g','电解液','浓度及单位','电压 V','BET m²/g','总孔体积 cm³/g','当前状态','原始记录与出处'],recordrows)),('papers','文献',table(['编号','年份','分类','题名/原文','DOI','正文格式','使用限制'],paperrows)),('materials','材料',table(['材料编号','论文','原样品名','关联终点数','身份状态'],materialrows)),('issues','待核问题',table(['论文','记录','问题编号','具体内容','范围'],issuerows))]
head='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>循环稳定性数据库 v0.1</title><style>
*{box-sizing:border-box}body{font:14px/1.65 "Microsoft YaHei",sans-serif;color:#23313d;background:#fff;margin:24px}h1{font-size:25px;margin-bottom:8px}.summary{font-size:17px;padding:12px 0;border-bottom:2px solid #344e5c}.note{color:#56636c;max-width:1100px}nav{display:flex;gap:8px;margin:20px 0 10px}button,input,select{font:inherit;padding:7px 12px;border:1px solid #c6cfd4;background:white;border-radius:3px}button[aria-selected="true"]{background:#294957;color:white}input{width:380px;max-width:100%}.toolbar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:12px}a{color:#175b83}.scroll{overflow:auto;max-height:70vh;border:1px solid #d8dfe3}table{border-collapse:collapse;width:100%;min-width:1100px}th,td{padding:9px 11px;border-bottom:1px solid #dfe5e8;text-align:left;vertical-align:top}th{background:#edf2f5;position:sticky;top:0;z-index:1;white-space:nowrap}tr:nth-child(even){background:#fafcfd}td:first-child{white-space:nowrap}details{min-width:170px}details p{max-width:420px}footer{margin-top:18px;color:#5c6770}section[hidden],tr[hidden]{display:none}@media print{nav,.toolbar{display:none}.scroll{overflow:visible;max-height:none}body{margin:8px;font-size:10px}th{position:static}}
</style><h1>循环稳定性数据库 v0.1</h1><p class="summary">126篇文献 · 67个暂定材料编号 · 83次循环测试 · 89个候选终点 · 0条正式训练记录</p><p class="note">本地只读查看。89个终点来自51篇论文，不是89个独立样本。空白表示当前尚未配对，不能当成0或原文没有报告。主体系优先核录12终点/10材料/10篇，仍需终审；234条待核事项可重复关联同一记录。</p><p><a href="README.md">数据库说明</a>　<a href="建模思路.md">随机森林 / XGBoost / MLP比较思路</a>　<a href="cycling_v0_1.sqlite">SQLite数据库</a>　<a href="所需文献与补录队列.md">优先核录文献</a></p>'''
nav='<nav aria-label="数据表">'+''.join(f'<button type="button" data-tab="{id}" aria-selected="{str(i==0).lower()}">{title}</button>' for i,(id,title,_) in enumerate(panes))+'</nav>'
body=''
for i,(ident,title,t) in enumerate(panes):
 select='<select aria-label="筛选" class="kind"><option value="">全部状态</option><option value="primary">主体系优先核录</option><option value="conflict">冲突/待核</option><option value="other">其他体系/待核</option></select>' if ident=='records' else ''
 body+=f'<section id="{ident}" '+('hidden' if i else '')+'><div class="toolbar"><input type="search" aria-label="搜索'+title+'" placeholder="搜索编号、样品、DOI或问题">'+select+'<span class="count"></span></div>'+t+'</section>'
script='''<script>
function filter(p){const q=p.querySelector('input').value.toLowerCase(),s=p.querySelector('select');let n=0;for(const r of p.querySelectorAll('tbody tr')){const ok=r.dataset.search.includes(q)&&(!s||!s.value||r.dataset.kind===s.value);r.hidden=!ok;if(ok)n++;}p.querySelector('.count').textContent='显示 '+n+' 条';}
for(const p of document.querySelectorAll('section')){p.querySelector('input').addEventListener('input',()=>filter(p));if(p.querySelector('select'))p.querySelector('select').addEventListener('change',()=>filter(p));filter(p);}
for(const b of document.querySelectorAll('nav button'))b.addEventListener('click',()=>{for(const x of document.querySelectorAll('nav button'))x.setAttribute('aria-selected',String(x===b));for(const p of document.querySelectorAll('section'))p.hidden=p.id!==b.dataset.tab;});
</script></html>'''
(ROOT/'数据库查看.html').write_text(head+nav+body+'<footer>2026-10-17 · 未训练模型 · 不上传数据 · 原文文件保持不变</footer>'+script,encoding='utf-8')

queue=['# 所需文献与优先核录队列','','当前主体系优先核录12终点，来自10篇和10个暂定材料。这是条件筛查，不是准入名单。126篇已登记文献保留目录身份；51篇目前有循环候选，不能用总论文数代替可训练来源数。','','先核下表，按原文补基线、电流质量分母、成品范围与来源独立性；有缺字段的查SI。不要因保持率高低改变优先级。','','| 论文 | DOI | 样品 | 尚需先解决 |','|---|---|---|---|']
by_p={}
for r in primary:by_p.setdefault(r['paper_id'],[]).append(r)
for ident,rs in by_p.items():
 needs=['基线、循环电流质量分母、来源独立性终审']
 for key,label in [('current_density_A_g','循环电流'),('concentration_value','电解液浓度'),('voltage_lower_V','电压下限'),('voltage_upper_V','电压上限'),('total_pore_volume_cm3_g','总孔体积')]:
  if any(r[key] is None for r in rs):needs.append(label+'尚未配对')
 if ident=='SRC123':needs.append('2016年前作材料/曲线复用待核')
 if ident=='R106':needs.append('同论文FMCA有硅，FMC也应独立查成品组成，不能沿用另一个样品的值')
 queue.append('| '+ident+' | '+str(rs[0]['doi'])+' | '+rs[0]['sample_name']+' | '+'；'.join(needs)+' |')
queue+=['','其他来源仍保留在数据库中：三电极另设子集；CV、凝胶、金属、半电池、近似/下限标签和冲突来源分开核审。主队列比先前宽口径数量少，是因为这里明确限定两电极对称、GCD、精确点值和当前范围条件，不是删掉旧数据。','','待用户补正文仍为N003、N006、N007、N008。清单在上一级循环稳定性文献补充_20261017/需用户下载清单.md。本轮不重复要求下载已归档正文。']
(ROOT/'所需文献与补录队列.md').write_text('\n'.join(queue)+'\n',encoding='utf-8')

# An inspectable notebook with outputs computed from this database now, not invented.
queries=[('层级计数',"SELECT 'papers' name,count(*) n FROM papers UNION ALL SELECT 'materials',count(*) FROM materials UNION ALL SELECT 'cycling_tests',count(*) FROM cycling_tests UNION ALL SELECT 'endpoints',count(*) FROM cycling_endpoints UNION ALL SELECT 'training_ready',count(*) FROM training_ready"),('主体系队列',"SELECT paper_id,count(*) endpoints,count(distinct material_id) materials FROM primary_screening_candidates GROUP BY paper_id ORDER BY paper_id"),('原值和标签类型',"SELECT retention_relation,count(*) n,sum(retention_pct>100) above100 FROM cycling_endpoints GROUP BY retention_relation"),('外键核验','PRAGMA foreign_key_check')]
cells=[{'cell_type':'markdown','metadata':{},'id':uuid.uuid4().hex[:8],'source':['# 数据库复核\n','此笔记本仅查询当前版本数据库；已保存的输出来自本次实际SQLite查询。无训练。']}]
setup="import pathlib,sqlite3,json\nROOT=pathlib.Path("+repr(str(ROOT))+ ")\nc=sqlite3.connect((ROOT/'cycling_v0_1.sqlite').as_uri()+'?mode=ro',uri=True)\nc.row_factory=sqlite3.Row\n"
for i,(label,sql) in enumerate(queries,1):
 code=(setup if i==1 else '')+'# '+label+'\nsql='+repr(sql)+'\nprint(json.dumps([dict(r) for r in c.execute(sql)],ensure_ascii=False,indent=2))\n'
 result=query(sql)
 cells.append({'cell_type':'code','metadata':{},'id':uuid.uuid4().hex[:8],'source':code.splitlines(keepends=True),'execution_count':i,'outputs':[{'output_type':'stream','name':'stdout','text':[json.dumps(result,ensure_ascii=False,indent=2)+'\n']}]})
nb={'cells':cells,'metadata':{'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'},'language_info':{'name':'python','version':'3.12'}},'nbformat':4,'nbformat_minor':5}
(ROOT/'数据库复核.ipynb').write_text(json.dumps(nb,ensure_ascii=False,indent=2),encoding='utf-8')
assert len(paperrows)==126 and len(recordrows)==89 and len(materialrows)==67 and len(issuerows)==234
assert len(re.findall('<tr data-kind=',head+nav+body))==516
print('Review page: 126 papers, 89 endpoints, 67 materials, 234 issues. Notebook: 4 executed read-only queries.')
