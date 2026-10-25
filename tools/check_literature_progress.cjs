// Isolated browser checks for the local literature extraction snapshot.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {createRequire}=require('node:module');
const {chromium}=createRequire(process.env.CODEX_NODE_MODULES+'/package.json')('playwright');
(async()=>{
 const app=path.resolve('文献提取进度'),out=path.join(app,'output','playwright');fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 try{
  const ctx=await browser.newContext({viewport:{width:1440,height:1050},permissions:['clipboard-read','clipboard-write']});
  const p=await ctx.newPage(),errors=[];p.setDefaultTimeout(6000);p.on('pageerror',e=>errors.push(e.message));
  await p.goto('http://127.0.0.1:8770/?view=1&tab=dashboard',{waitUntil:'networkidle'});
  const component=id=>p.locator(`[data-component-id="${id}"]`);
  const material=component('material-evidence'),cap=component('capacitance-evidence');
  const expectCount=async(block,n)=>assert.match(await block.innerText(),new RegExp(`of ${n} results`));
  const choose=async(label,value)=>{await p.getByRole('button').filter({hasText:label}).click();await p.getByRole('menuitemradio',{name:value,exact:true}).click();};
  await expectCount(material,161);await expectCount(cap,41);await expectCount(component('full-table-queue'),959);
  assert.equal(await p.locator('svg.recharts-surface').count(),2);
  assert.doesNotMatch(await p.locator('body').innerText(),/Creating dashboard|Updating dashboard|reported_mesopore_surface_area/);
  const desktop=await p.evaluate(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,charts:[...document.querySelectorAll('svg.recharts-surface')].map(e=>({width:e.getBoundingClientRect().width,height:e.getBoundingClientRect().height}))}));
  assert.ok(desktop.scrollWidth<=desktop.width);assert.ok(desktop.charts.every(x=>x.width>200&&x.height>150));
  await p.screenshot({path:path.join(out,'desktop.png'),fullPage:true});
  await choose(/论文 DOI/,'10.1021/acsenvironau.3c00048');await expectCount(material,53);await expectCount(cap,40);
  await choose(/比电容方法/,'GCD');await expectCount(material,53);await expectCount(cap,8);
  assert.equal(await cap.locator('tbody tr').count(),8);
  assert.ok((await cap.locator('tbody tr').allTextContents()).every(x=>x.includes('GCD')&&x.includes('0.50')));
  await cap.getByRole('button',{name:'比电容 · 每种工况分别记录 actions',exact:true}).click();
  await p.locator('[role="menu"]').getByText('Copy data',{exact:true}).click();
  const clipboard=await p.evaluate(()=>navigator.clipboard.readText());
  assert.ok(clipboard.includes('GCD')&&!clipboard.includes('EIS')&&!clipboard.includes('CV'));
  await cap.getByRole('button',{name:'比电容 · 每种工况分别记录 actions',exact:true}).click();
  await p.locator('[role="menu"]').getByText('View data source',{exact:true}).click();
  assert.ok(await p.getByText('SQL query',{exact:true}).count());
  assert.ok(await p.getByText('Evidence flow',{exact:true}).count());
  await p.getByText('Data preview',{exact:true}).click();
  await p.screenshot({path:path.join(out,'filtered-source.png')});
  await p.keyboard.press('Escape');
  await choose(/比电容方法/,'All');await choose(/论文 DOI/,'10.3390/nano16161035');await expectCount(material,27);
  assert.equal(await cap.locator('tbody tr').count(),0);assert.match(await cap.innerText(),/No .*data|No .*results|0 results/i);
  await choose(/论文 DOI/,'All');await expectCount(material,161);await expectCount(cap,41);
  await component('full-table-queue').getByPlaceholder('Search data').fill('no_such_literature_record_20261025');
  assert.match(await component('full-table-queue').innerText(),/No .*data|No .*results|0 results/i);
  await component('full-table-queue').getByPlaceholder('Search data').fill('');await expectCount(component('full-table-queue'),959);
  await p.setViewportSize({width:390,height:844});await p.locator('.progress-intro').scrollIntoViewIfNeeded();
  const mobile=await p.evaluate(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,chartWidths:[...document.querySelectorAll('svg.recharts-surface')].map(e=>e.getBoundingClientRect().width)}));
  assert.ok(mobile.scrollWidth<=mobile.width);assert.ok(mobile.chartWidths.every(w=>w>100&&w<=390));
  await p.screenshot({path:path.join(out,'mobile.png'),fullPage:true});
  assert.equal(errors.length,0);
  const result={passed:true,browser:'isolated headless Microsoft Edge',desktop,mobile,chart_count:2,
   doi_scope_checked:[{doi:'10.1021/acsenvironau.3c00048',material_cells:53,capacitance_reports:40},{doi:'10.3390/nano16161035',material_cells:27,capacitance_reports:0}],
   method_filter_GCD8_and_material_scope_unchanged:true,source_inspector_and_scoped_copy_checked:true,scoped_copy_characters:clipboard.length,
   empty_scope_and_search_checked:true,all_reset_reconciled:true,javascript_errors:errors,scientific_goal_complete:false};
  fs.writeFileSync(path.join(app,'dashboard_visual_verification.json'),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify(result));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
