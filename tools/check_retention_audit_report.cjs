const fs=require('node:fs'),path=require('node:path'),{pathToFileURL}=require('node:url'),{createRequire}=require('node:module');
const{chromium}=createRequire(process.env.CODEX_NODE_MODULES+'/package.json')('playwright');
(async()=>{
 const root=path.resolve('小样本方向预研_20261029/审计补充'),browser=await chromium.launch({headless:true,channel:'msedge'});
 try{
  const page=await browser.newPage({viewport:{width:1360,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(pathToFileURL(path.join(root,'指标与基线补充.html')).href);await page.evaluate(()=>document.fonts.ready);
  const text=await page.locator('body').innerText();for(const s of ['MAPE','0.21','11.84','新增拟合0次','模型尚未达标','五个对比均未满足'])if(!text.includes(s))throw Error('Missing '+s);
  if(await page.locator('tbody tr').count()!==5)throw Error('Expected five preselected comparisons');
  const desktop=await page.evaluate(()=>({width:innerWidth,content:document.documentElement.scrollWidth}));if(desktop.width!==desktop.content)throw Error('Desktop overflow');
  for(const href of await page.locator('a').evaluateAll(xs=>xs.map(x=>x.getAttribute('href'))))if(!fs.existsSync(path.resolve(root,decodeURIComponent(href))))throw Error('Missing local link '+href);
  await page.screenshot({path:path.join(root,'指标补充预览.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});const mobile=await page.evaluate(()=>({width:innerWidth,content:document.documentElement.scrollWidth}));if(mobile.width!==mobile.content)throw Error('Mobile overflow');
  if(errors.length)throw Error(errors.join('\n'));
  const result={status:'passed',desktop,mobile,comparison_rows:5,local_links_exist:true,browser_errors:errors};fs.writeFileSync(path.join(root,'版式核验.json'),JSON.stringify(result,null,2)+'\n');process.stdout.write(JSON.stringify(result)+'\n');
 }finally{await browser.close();}
})().catch(e=>{process.stderr.write(e.stack+'\n');process.exitCode=1});
