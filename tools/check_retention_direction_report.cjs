const fs=require('node:fs'),path=require('node:path'),{pathToFileURL}=require('node:url'),{createRequire}=require('node:module');
const{chromium}=createRequire(process.env.CODEX_NODE_MODULES+'/package.json')('playwright');
(async()=>{
 const run=path.resolve('小样本方向预研_20261029/保持率固定输入输出');
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 try{
  const page=await browser.newPage({viewport:{width:1360,height:1000}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto(pathToFileURL(path.join(run,'保持率方向预研报告.html')).href);await page.evaluate(()=>document.fonts.ready);
  const text=await page.locator('main').innerText();
  for(const v of ['251','电容保持率','参比电极','MAE ≤ 2','同化学系列','10.1','尚未达到'])if(!text.includes(v))throw Error('Missing '+v);
  const desktop=await page.evaluate(()=>({width:innerWidth,content:document.documentElement.scrollWidth}));if(desktop.width!==desktop.content)throw Error('Desktop overflow');
  if(!await page.locator('img').evaluateAll(xs=>xs.length===1&&xs.every(x=>x.complete&&x.naturalWidth>0)))throw Error('Scientific chart');
  await page.screenshot({path:path.join(run,'报告预览.png'),fullPage:true});
  await page.locator('summary').click();if(!await page.getByText('缺预测，不可比较',{exact:false}).isVisible())throw Error('Failure coverage details');
  await page.setViewportSize({width:390,height:844});
  const mobile=await page.evaluate(()=>({width:innerWidth,content:document.documentElement.scrollWidth}));if(mobile.width!==mobile.content)throw Error('Mobile overflow');
  if(errors.length)throw Error(errors.join('\n'));
  const receipt={status:'passed',desktop,mobile,scientific_chart_loaded:true,failure_coverage_visible:true,browser_errors:errors};fs.writeFileSync(path.join(run,'版式核验.json'),JSON.stringify(receipt,null,2)+'\n');process.stdout.write(JSON.stringify(receipt)+'\n');
 }finally{await browser.close();}
})().catch(e=>{process.stderr.write(e.stack+'\n');process.exitCode=1;});
