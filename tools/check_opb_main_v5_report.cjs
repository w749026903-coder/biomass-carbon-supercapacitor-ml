const fs=require('node:fs'),path=require('node:path'),{pathToFileURL}=require('node:url');
const {createRequire}=require('node:module');
const {chromium}=createRequire(process.env.CODEX_NODE_MODULES+'/package.json')('playwright');
(async()=>{
 const dir=path.resolve('全量文献训练数据接入_v5_OPB主集关联_20261028');const s=JSON.parse(fs.readFileSync(path.join(dir,'summary.json'),'utf8'));
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 try{
  const p=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];p.on('pageerror',e=>errors.push(e.message));await p.goto(pathToFileURL(path.join(dir,'主训练集关联与数据进度.html')).href);
  if(await p.locator('tbody tr').count()!==4)throw Error('Four source-linked rows required');const cards=await p.locator('.card strong').allTextContents();
  if(cards[0]!==s.main3e_material_links+' / 47'||cards[1]!=='+'+s.additional_main3e_nonmissing_cells||cards[2]!==String(s.main3e_existing_cells_attested))throw Error('Wrong metrics');
  for(const href of await p.locator('a').evaluateAll(a=>a.map(x=>x.getAttribute('href'))))if(!fs.existsSync(path.join(dir,decodeURIComponent(href))))throw Error('Missing link '+href);
  const desktop=await p.evaluate(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth}));if(desktop.width!==desktop.scrollWidth)throw Error('Desktop overflow');await p.screenshot({path:path.join(dir,'desktop_progress.png'),fullPage:true});
  await p.setViewportSize({width:390,height:844});const mobile=await p.evaluate(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth}));if(mobile.width!==mobile.scrollWidth||errors.length)throw Error('Mobile overflow/error');await p.screenshot({path:path.join(dir,'mobile_progress.png'),fullPage:true});
  fs.writeFileSync(path.join(dir,'report_visual_verification.json'),JSON.stringify({passed:true,desktop,mobile,cards,rows:4,verified_links:6,browser_errors:errors},null,2)+'\n');process.stdout.write(JSON.stringify({passed:true,desktop,mobile,cards})+'\n');
 }finally{await browser.close();}
})().catch(e=>{process.stderr.write(e.stack+'\n');process.exitCode=1});
