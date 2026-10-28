// Local ReportLab SVG/HTML checks using the repository's existing Playwright runtime.
const fs=require('node:fs'),path=require('node:path'),http=require('node:http');
const {createRequire}=require('node:module');
const {chromium}=createRequire(process.env.CODEX_NODE_MODULES+'/package.json')('playwright');
(async()=>{
 const folder=path.resolve(process.argv[2]), output=path.join(folder,'output','playwright');fs.mkdirSync(output,{recursive:true});
 const server=http.createServer((req,res)=>{
  const name=decodeURIComponent(new URL(req.url,'http://localhost').pathname).replace(/^\//,'');const file=path.resolve(folder,name);
  if(!file.startsWith(folder+path.sep)){res.writeHead(404);res.end();return;}
  fs.readFile(file,(err,b)=>{if(err){res.writeHead(404);res.end();return;}res.setHeader('Content-Type',file.endsWith('.json')?'application/json; charset=utf-8':file.endsWith('.svg')?'image/svg+xml':file.endsWith('.png')?'image/png':'text/html; charset=utf-8');res.end(b);});
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));let browser;
 try{
  browser=await chromium.launch({headless:true,channel:'msedge'});const page=await browser.newPage({viewport:{width:1440,height:1050}});let errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:'+server.address().port+'/'+encodeURIComponent('模型v1.2训练结果.html'),{waitUntil:'networkidle'});
  await page.getByText('本次训练已完成',{exact:true}).waitFor();await page.waitForFunction(()=>Array.from(document.querySelectorAll('#plots img')).every(x=>x.complete&&x.naturalWidth>0));
  const actual=JSON.parse(fs.readFileSync(path.join(folder,'results.json'),'utf8'));
  const desktop=await page.evaluate(()=>({progress:document.querySelector('progress').value,rows:document.querySelectorAll('#records tr').length,metrics:document.querySelectorAll('#metrics tr').length,width:innerWidth,scrollWidth:document.documentElement.scrollWidth,images:Array.from(document.querySelectorAll('#plots img')).map(i=>i.naturalWidth),mae:document.querySelector('#mae').textContent,verdict:document.querySelector('#verdict').textContent}));
  if(desktop.progress!==560||desktop.rows!==47||desktop.metrics!==3||desktop.scrollWidth>desktop.width||Number(desktop.mae)!==Number(actual.metrics[0].mae.toFixed(3)))throw Error('Wrong desktop data or layout: '+JSON.stringify(desktop));
  await page.screenshot({path:path.join(output,'desktop.png'),fullPage:true});
  await page.locator('#search').fill('not_a_real_sample');if(await page.locator('#records tr').count()!==0)throw Error('Search did not filter');await page.locator('#search').fill('');
  await page.locator('#sort').selectOption('observed');const first=await page.locator('#records tr').first().locator('td').nth(1).innerText();if(Number(first)!==62.2)throw Error('Sort failed');
  await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(output,'mobile.png'),fullPage:true});
  const mobile=await page.evaluate(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,rows:document.querySelectorAll('#records tr').length}));
  if(mobile.scrollWidth>mobile.width||mobile.rows!==47||errors.length)throw Error('Mobile layout or browser errors: '+JSON.stringify({mobile,errors}));
  fs.writeFileSync(path.join(folder,'report_visual_verification.json'),JSON.stringify({passed:true,desktop,mobile,search_and_sort_passed:true,plot_SVGs_loaded:4,browser_errors:errors,screenshots:['output/playwright/desktop.png','output/playwright/mobile.png']},null,2)+'\n');
  process.stdout.write(JSON.stringify({passed:true,desktop,mobile,errors})+'\n');
 }finally{if(browser)await browser.close();await new Promise(resolve=>server.close(resolve));}
})().catch(e=>{process.stderr.write(e.stack+'\n');process.exitCode=1});
