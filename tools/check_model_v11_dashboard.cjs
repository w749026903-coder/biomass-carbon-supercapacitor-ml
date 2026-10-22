// Isolated local rendering and interaction checks; ephemeral localhost server is closed.
const fs=require('node:fs');const path=require('node:path');const http=require('node:http');
const {createRequire}=require('node:module');const {pathToFileURL}=require('node:url');
const {chromium}=createRequire(process.env.CODEX_NODE_MODULES+'/package.json')('playwright');

(async()=>{
 const folder=path.resolve(process.argv[2]);const shots=path.join(folder,'output','playwright');fs.mkdirSync(shots,{recursive:true});
 const server=http.createServer((req,res)=>{
  if(req.url==='/'){res.writeHead(302,{Location:'/dashboard/dist/index.html'});res.end();return;}
  const relative=decodeURIComponent(new URL(req.url,'http://127.0.0.1').pathname).replace(/^\//,'');
  const file=path.resolve(folder,relative);
  if(!file.startsWith(path.join(folder,'dashboard','dist')+path.sep)){res.writeHead(404);res.end();return;}
  fs.readFile(file,(error,bytes)=>{if(error){res.writeHead(404);res.end();return;}
   res.setHeader('Content-Type',file.endsWith('.json')?'application/json; charset=utf-8':'text/html; charset=utf-8');res.end(bytes);});
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 let browser;
 try{
  browser=await chromium.launch({headless:true,channel:'msedge'});
  const page=await browser.newPage({viewport:{width:1440,height:1100}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:'+server.address().port+'/',{waitUntil:'networkidle'});
  await page.getByText('本轮优化实验完成 · 精度尚未达标',{exact:true}).waitFor();
  const actual=JSON.parse(fs.readFileSync(path.join(folder,'reviewed_predictions.json'),'utf8'));
  const desktop=await page.evaluate(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,
   progress:document.querySelector('progress').value,charts:document.querySelectorAll('svg.recharts-surface').length,
   steps:document.querySelectorAll('[data-component-id="optimization-checklist"] tbody tr').length,
   reviewRows:document.querySelectorAll('.prediction-records tbody tr').length,
   percentages:Array.from(document.querySelectorAll('.unit-examples .pct')).map(x=>x.textContent),
   ratios:Array.from(document.querySelectorAll('.unit-examples .ratio')).map(x=>x.textContent)}));
  if(desktop.progress!==1332||desktop.charts<3||desktop.reviewRows!==42||desktop.scrollWidth>desktop.width)throw Error('Desktop geometry: '+JSON.stringify(desktop));
  if(!desktop.percentages.includes('101.24%')||!desktop.ratios.includes('比例1.0124')||!desktop.percentages.includes('109.20%'))throw Error('Units not explicit');
  await page.screenshot({path:path.join(shots,'desktop.png'),fullPage:true});
  for(const variant of ['v1_1_nested','v1_recipe_same_cohort','source_mean']){
   await page.locator('.prediction-filter select').selectOption(variant);
   const rows=page.locator('.prediction-records tbody tr');if(await rows.count()!==42)throw Error('Missing filtered records');
   const expected=actual.find(r=>r.variant===variant);
   const predicted=await rows.first().locator('td').nth(2).locator('.pct').innerText();
   const ratio=await rows.first().locator('td').nth(2).locator('.ratio').innerText();
   if(Math.abs(parseFloat(predicted)-expected.predicted_pct)>.006||Math.abs(Number(ratio.replace('比例',''))-expected.predicted_pct/100)>.000051)throw Error('Percentage/ratio filter mismatch');
   if(await page.locator('.prediction-records .reliability').count()!==42)throw Error('Missing per-record reliability status');
  }
  await page.locator('.prediction-filter select').selectOption('v1_1_nested');
  await page.setViewportSize({width:390,height:844});
  await page.waitForFunction(()=>Array.from(document.querySelectorAll('svg.recharts-surface')).every(x=>x.getBoundingClientRect().width<=innerWidth));
  const mobile=await page.evaluate(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,
   chartWidths:Array.from(document.querySelectorAll('svg.recharts-surface')).map(x=>x.getBoundingClientRect().width)}));
  if(mobile.scrollWidth>mobile.width||mobile.chartWidths.some(w=>w<100||w>390))throw Error('Mobile overflow');
  await page.screenshot({path:path.join(shots,'mobile.png'),fullPage:true});
  const offline=await browser.newPage();offline.on('pageerror',e=>errors.push(e.message));
  await offline.goto(pathToFileURL(path.join(folder,'v1.1逐项优化结果.html')).href,{waitUntil:'networkidle'});
  await offline.getByText('101.24% = 比例1.0124。保持率不是概率；高于初始参照时可以超过100%。',{exact:true}).waitFor();
  if(await offline.locator('.prediction-records tbody tr').count()!==42)throw Error('Offline predictions missing');
  if(errors.length)throw Error(JSON.stringify(errors));
  const report={passed:true,browser:'isolated headless Microsoft Edge',desktop,mobile,
   all_three_filters_and_dual_units_checked:true,legitimate_above100_values_preserved:true,
   reliability_status_checked_on_all42_rows:true,offline_snapshot_checked:true,javascript_errors:errors,
   temporary_preview_server_closed_on_exit:true};
  fs.writeFileSync(path.join(folder,'dashboard_visual_verification.json'),JSON.stringify(report,null,2)+'\n');process.stdout.write(JSON.stringify(report));
 }finally{if(browser)await browser.close();await new Promise(resolve=>server.close(resolve));}
})().catch(e=>{process.stderr.write(e.stack+'\n');process.exitCode=1;});
