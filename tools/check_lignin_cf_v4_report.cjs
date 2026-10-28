const fs=require('node:fs'),path=require('node:path'),{pathToFileURL}=require('node:url');
const {createRequire}=require('node:module');
const {chromium}=createRequire(process.env.CODEX_NODE_MODULES+'/package.json')('playwright');
(async()=>{
 const dir=path.resolve('全量文献训练数据接入_v4_木质素碳布与凝胶_20261028'),s=JSON.parse(fs.readFileSync(path.join(dir,'summary.json'),'utf8'));
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(pathToFileURL(path.join(dir,'文献接续与数据库进度.html')).href);await page.waitForFunction(()=>Array.from(document.images).every(i=>i.complete&&i.naturalWidth>0));
  if(await page.locator('tbody tr').count()!==18)throw Error('Expected 10 electrode CV and8 device GCD rows');
  const cards=await page.locator('.card strong').allTextContents();if(cards[0]!=='+'+s.new_material_facts||cards[1]!=='+'+s.additional_connected_numeric_facts)throw Error('Wrong counts');
  for(const href of await page.locator('a').evaluateAll(a=>a.map(x=>x.getAttribute('href'))))if(!fs.existsSync(path.join(dir,decodeURIComponent(href))))throw Error('Missing link '+href);
  const desktop=await page.evaluate(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,title:document.title}));if(desktop.width!==desktop.scrollWidth)throw Error('Desktop overflow');
  await page.screenshot({path:path.join(dir,'desktop_progress.png'),fullPage:true});await page.setViewportSize({width:390,height:844});
  const mobile=await page.evaluate(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth}));if(mobile.width!==mobile.scrollWidth||errors.length)throw Error('Mobile layout or browser error');
  await page.screenshot({path:path.join(dir,'mobile_progress.png'),fullPage:true});fs.writeFileSync(path.join(dir,'report_visual_verification.json'),JSON.stringify({passed:true,desktop,mobile,cards,rows:18,images_loaded:1,verified_links:6,browser_errors:errors},null,2)+'\n');
  process.stdout.write(JSON.stringify({passed:true,desktop,mobile,cards})+'\n');
 }finally{await browser.close();}
})().catch(e=>{process.stderr.write(e.stack+'\n');process.exitCode=1});
