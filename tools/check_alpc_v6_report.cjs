const fs=require('node:fs'),path=require('node:path'),{pathToFileURL}=require('node:url');
const{createRequire}=require('node:module');const{chromium}=createRequire(process.env.CODEX_NODE_MODULES+'/package.json')('playwright');
(async()=>{
 const dir=path.resolve('全量文献训练数据接入_v6_ALPC主集与补充表_20261029'),s=JSON.parse(fs.readFileSync(path.join(dir,'summary.json'),'utf8'));
 const b=await chromium.launch({headless:true,channel:'msedge'});
 try{
  const p=await b.newPage({viewport:{width:1440,height:1000}}),errors=[];p.on('pageerror',e=>errors.push(e.message));await p.goto(pathToFileURL(path.join(dir,'ALPC文献与主集质量进度.html')).href);
  const cards=await p.locator('.card strong').allTextContents();if(cards[0]!=='23 / 47'||cards[1]!==`+${s.additional_main3e_nonmissing_cells}`||cards[2]!==String(s.main3e_existing_cells_attested)||cards[3]!==`${(s.numeric_fact_connection_rate*100).toFixed(2)}%`)throw Error('Metric mismatch');
  if(await p.locator('section').first().locator('tbody tr').count()!==2)throw Error('Two main rows required');
  const links=await p.locator('a').evaluateAll(a=>a.map(x=>x.getAttribute('href')));for(const h of links)if(!fs.existsSync(path.join(dir,decodeURIComponent(h))))throw Error('Missing '+h);
  await p.locator('#rates summary').click();if(await p.locator('#rates tbody tr:visible').count()!==30)throw Error('Expansion must show30 markers');await p.locator('#rates summary').click();
  const desktop=await p.evaluate(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth}));if(desktop.width!==desktop.scrollWidth)throw Error('Desktop overflow');await p.screenshot({path:path.join(dir,'desktop_progress.png'),fullPage:true});
  await p.setViewportSize({width:390,height:844});const mobile=await p.evaluate(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth}));if(mobile.width!==mobile.scrollWidth||errors.length)throw Error('Mobile overflow/browser error');await p.screenshot({path:path.join(dir,'mobile_progress.png'),fullPage:true});
  const r={passed:true,desktop,mobile,cards,main_rows:2,graph_rows:30,graph_expand_collapse_passed:true,verified_links:links.length,browser_errors:errors};fs.writeFileSync(path.join(dir,'report_visual_verification.json'),JSON.stringify(r,null,2)+'\n');process.stdout.write(JSON.stringify(r)+'\n');
 }finally{await b.close();}
})().catch(e=>{process.stderr.write(e.stack+'\n');process.exitCode=1});
