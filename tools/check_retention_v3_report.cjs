const fs=require('node:fs'),path=require('node:path'),{pathToFileURL}=require('node:url'),{createRequire}=require('node:module');
const{chromium}=createRequire(process.env.CODEX_NODE_MODULES+'/package.json')('playwright');
(async()=>{const root=path.resolve('保持率达标研究_v3_主线与近优组合_20261030'),browser=await chromium.launch({headless:true,channel:'msedge'});try{
 const page=await browser.newPage({viewport:{width:1360,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));await page.goto(pathToFileURL(path.join(root,'研究进度.html')).href);await page.evaluate(()=>document.fonts.ready);const text=await page.locator('body').innerText();
 for(const s of ['目标继续active','6324＋20','72＋12','0.916','16条/11来源','审计限制'])if(!text.includes(s))throw Error('Missing '+s);
 if(await page.locator('tbody tr').count()!==12)throw Error('Expected12 primary/family/combination/reference rows');
 for(const href of await page.locator('a').evaluateAll(xs=>xs.map(x=>x.getAttribute('href'))))if(!fs.existsSync(path.resolve(root,decodeURIComponent(href))))throw Error('Missing link '+href);
 const desktop=await page.evaluate(()=>({width:innerWidth,content:document.documentElement.scrollWidth}));if(desktop.width!==desktop.content)throw Error('Desktop overflow');await page.screenshot({path:path.join(root,'研究进度预览.png'),fullPage:true});await page.setViewportSize({width:390,height:844});const mobile=await page.evaluate(()=>({width:innerWidth,content:document.documentElement.scrollWidth}));if(mobile.width!==mobile.content)throw Error('Mobile overflow');if(errors.length)throw Error(errors.join('\n'));
 const result={status:'passed',desktop,mobile,comparison_rows:12,local_links_exist:true,browser_errors:errors};fs.writeFileSync(path.join(root,'版式核验.json'),JSON.stringify(result,null,2)+'\n');process.stdout.write(JSON.stringify(result)+'\n');
 }finally{await browser.close();}})().catch(e=>{process.stderr.write(e.stack+'\n');process.exitCode=1});
