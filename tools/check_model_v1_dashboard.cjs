// Isolated local Edge QA; reuse the existing bundled Playwright, no installs or user profile.
const fs=require('node:fs');
const path=require('node:path');
const {createRequire}=require('node:module');
const {pathToFileURL}=require('node:url');
const {chromium}=createRequire(process.env.CODEX_NODE_MODULES+'/package.json')('playwright');

(async()=>{
 const folder=path.resolve(process.argv[2]);
 const shots=path.join(folder,'output','playwright');
 fs.mkdirSync(shots,{recursive:true});
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 const page=await browser.newPage({viewport:{width:1440,height:1100}});
 const errors=[];page.on('pageerror',error=>errors.push(error.message));
 await page.goto('http://127.0.0.1:8767/',{waitUntil:'networkidle'});
 await page.getByText('v1.0训练完成 · 性能验收未通过',{exact:true}).waitFor();
 const actual=JSON.parse(fs.readFileSync(path.join(folder,'progress.json'),'utf8'));
 const desktop=await page.evaluate(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,
   progress:document.querySelector('progress').value,charts:document.querySelectorAll('svg.recharts-surface').length,
   bars:document.querySelectorAll('.recharts-bar-rectangle').length,points:document.querySelectorAll('.recharts-scatter-symbol').length,
   candidates:document.querySelectorAll('.v1-candidates tbody tr').length,
   pendingBuild:document.body.innerText.includes('Creating dashboard'),
   missingGlyphs:document.body.innerText.includes('undefined')}));
 if(desktop.progress!==581||desktop.charts<3||desktop.bars<5||desktop.points<7||desktop.candidates!==25||desktop.pendingBuild||desktop.missingGlyphs||desktop.scrollWidth>desktop.width)
   throw Error('Desktop mismatch: '+JSON.stringify(desktop));
 await page.screenshot({path:path.join(shots,'desktop.png'),fullPage:true});
 for(const variant of ['selected','source_mean','legacy_mlp_noI','ridge_core_noI_100','ridge_material_noI_100']){
   await page.locator('.v1-filter select').selectOption(variant);
   if(await page.locator('.v1-records tbody tr').count()!==7)throw Error('Prediction count: '+variant);
   const expected=actual.predictions.find(r=>r.variant===variant);
   const cells=await page.locator('.v1-records tbody tr').first().locator('td').allTextContents();
   if(Math.abs(Number(cells[2])-expected.predicted)>.006)throw Error('Wrong filtered prediction: '+variant);
 }
 await page.locator('.v1-filter select').selectOption('selected');
 await page.setViewportSize({width:390,height:844});
 await page.waitForFunction(()=>Array.from(document.querySelectorAll('svg.recharts-surface')).every(svg=>svg.getBoundingClientRect().width<=innerWidth));
 const mobile=await page.evaluate(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,
   charts:Array.from(document.querySelectorAll('svg.recharts-surface')).map(x=>({width:x.getBoundingClientRect().width,height:x.getBoundingClientRect().height}))}));
 if(mobile.scrollWidth>mobile.width||mobile.charts.some(c=>c.width<100||c.width>mobile.width||c.height<100))throw Error('Mobile overflow or missing chart: '+JSON.stringify(mobile));
 await page.screenshot({path:path.join(shots,'mobile.png'),fullPage:true});
 const offline=await browser.newPage();offline.on('pageerror',error=>errors.push(error.message));
 await offline.goto(pathToFileURL(path.join(folder,'模型v1.0训练结果.html')).href,{waitUntil:'networkidle'});
 await offline.getByText('离线结果快照',{exact:true}).waitFor();
 if(await offline.locator('.v1-records tbody tr').count()!==7||await offline.locator('progress').getAttribute('value')!=='581')throw Error('Offline snapshot mismatch');
 await browser.close();
 if(errors.length)throw Error(JSON.stringify(errors));
 const report={passed:true,browser:'isolated headless Microsoft Edge',desktop,mobile,
   all_five_prediction_filters_checked:true,offline_snapshot_checked:true,javascript_errors:errors,
   integrated_browser_control:'CUA failed to write kernel assets; no integrated-browser inspection claimed.'};
 fs.writeFileSync(path.join(folder,'dashboard_visual_verification.json'),JSON.stringify(report,null,2)+'\n');
 process.stdout.write(JSON.stringify(report));
})().catch(error=>{process.stderr.write(error.stack+'\n');process.exitCode=1;});
