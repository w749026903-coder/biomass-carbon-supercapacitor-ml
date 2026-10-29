const fs=require('node:fs'),path=require('node:path'),{pathToFileURL}=require('node:url'),{createRequire}=require('node:module');
const{chromium}=createRequire(process.env.CODEX_NODE_MODULES+'/package.json')('playwright');
(async()=>{
 const root=path.resolve('保持率双路线预研_v2_20261029'),browser=await chromium.launch({headless:true,channel:'msedge'});
 try{
  const page=await browser.newPage({viewport:{width:1360,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(pathToFileURL(path.join(root,'双路线保持率预研报告.html')).href);await page.evaluate(()=>document.fonts.ready);
  let body=await page.locator('body').innerText();for(const s of ['还没有模型全面达标','0.908','439次','19条 / 13来源','预定线性主方案','只有8个来源','不能把0.246与0.908之差全归因于模型进步'])if(!body.includes(s))throw Error('Missing '+s);
  const rows=await page.locator('table').first().locator('tbody tr').count();if(rows!==7)throw Error('Expected7 primary/declared candidate comparisons');
  const desktop=await page.evaluate(()=>({width:innerWidth,content:document.documentElement.scrollWidth}));if(desktop.width!==desktop.content)throw Error('Desktop overflow');
  for(const href of await page.locator('a').evaluateAll(xs=>xs.map(x=>x.getAttribute('href'))))if(!fs.existsSync(path.resolve(root,decodeURIComponent(href))))throw Error('Missing link '+href);
  for(const img of await page.locator('img').evaluateAll(xs=>xs.map(x=>({src:x.getAttribute('src'),ok:x.complete&&x.naturalWidth>0}))))if(!img.ok)throw Error('Broken image '+img.src);
  await page.screenshot({path:path.join(root,'报告预览.png'),fullPage:true});
  await page.locator('details').evaluate(el=>el.open=true);if(await page.locator('table').nth(1).locator('tbody tr').count()!==48)throw Error('Expected12 A +36 B metric rows');
  await page.setViewportSize({width:390,height:844});const mobile=await page.evaluate(()=>({width:innerWidth,content:document.documentElement.scrollWidth}));if(mobile.width!==mobile.content)throw Error('Mobile overflow');
  if(errors.length)throw Error(errors.join('\n'));
  const result={status:'passed',desktop,mobile,primary_comparison_rows:7,all_model_comparison_rows:48,local_links_exist:true,figure_loaded:true,browser_errors:errors};fs.writeFileSync(path.join(root,'版式核验.json'),JSON.stringify(result,null,2)+'\n');process.stdout.write(JSON.stringify(result)+'\n');
 }finally{await browser.close();}
})().catch(e=>{process.stderr.write(e.stack+'\n');process.exitCode=1});
