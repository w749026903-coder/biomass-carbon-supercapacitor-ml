// Local offline visual and interaction verification using the existing runtime.
const fs=require('node:fs'),path=require('node:path'),{pathToFileURL}=require('node:url');
const {createRequire}=require('node:module');
const {chromium}=createRequire(process.env.CODEX_NODE_MODULES+'/package.json')('playwright');
(async()=>{
 const dir=path.resolve('全量文献训练数据接入_v2_质量与覆盖_20261028');
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(pathToFileURL(path.join(dir,'文献利用与质量结果.html')).href);
  const before=await page.locator('#features tbody tr:visible').count();
  if(before!==122)throw Error('Incorrect field count '+before);
  await page.getByRole('button',{name:'只看覆盖示例条件通过字段'}).click();
  const after=await page.locator('#features tbody tr:visible').count();if(after!==30)throw Error('Coverage filter failed');
  await page.getByRole('button',{name:'显示全部字段'}).click();
  const desktop=await page.evaluate(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,title:document.title,sourceRows:document.querySelectorAll('section')[3].querySelectorAll('tbody tr').length}));
  if(desktop.scrollWidth>desktop.width||desktop.sourceRows!==65)throw Error('Desktop layout/count mismatch '+JSON.stringify(desktop));
  for(const href of await page.locator('a').evaluateAll(links=>links.map(a=>a.getAttribute('href'))))if(!fs.existsSync(path.join(dir,decodeURIComponent(href))))throw Error('Missing link '+href);
  await page.screenshot({path:path.join(dir,'desktop_quality.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});
  const mobile=await page.evaluate(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth}));
  if(mobile.scrollWidth>mobile.width||errors.length)throw Error('Mobile/page error '+JSON.stringify({mobile,errors}));
  await page.screenshot({path:path.join(dir,'mobile_quality.png'),fullPage:true});
  fs.writeFileSync(path.join(dir,'report_visual_verification.json'),JSON.stringify({passed:true,desktop,mobile,filter_counts:[before,after,before],local_links_verified:6,browser_errors:errors},null,2)+'\n');
  process.stdout.write(JSON.stringify({passed:true,desktop,mobile,filtered:after})+'\n');
 }finally{await browser.close();}
})().catch(e=>{process.stderr.write(e.stack+'\n');process.exitCode=1});
