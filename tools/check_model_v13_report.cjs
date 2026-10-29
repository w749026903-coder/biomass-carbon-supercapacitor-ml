const fs=require('node:fs'),path=require('node:path'),{pathToFileURL}=require('node:url'),{createRequire}=require('node:module');
const{chromium}=createRequire(process.env.CODEX_NODE_MODULES+'/package.json')('playwright');
(async()=>{
 const brief=path.resolve('项目进展简报_训练后_20261029'),run=path.resolve('模型v1.3_新数据与辅助学习_20261029');
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(pathToFileURL(path.join(brief,'项目进展简报.html')).href);await page.evaluate(()=>document.fonts.ready);
  const text=await page.locator('main').innerText();for(const v of ['4.9249','0.1386','1,147','1,072','5,197','3,727','508','747','未通过'])if(!text.includes(v))throw Error('Missing '+v);
  if(await page.locator('section').count()!==2)throw Error('Expected two report sections');
  const desktop=await page.evaluate(()=>({width:innerWidth,content:document.documentElement.scrollWidth}));if(desktop.width!==desktop.content)throw Error('Desktop overflow');
  await page.screenshot({path:path.join(brief,'桌面预览.png')});
  await page.pdf({path:path.join(brief,'项目进展简报.pdf'),format:'A4',preferCSSPageSize:true,printBackground:true,displayHeaderFooter:true,headerTemplate:'<span></span>',footerTemplate:'<div style="width:100%;text-align:center;font-size:9px;color:#777">项目训练后简报 · 2026-10-29 · <span class="pageNumber"></span> / <span class="totalPages"></span></div>'});
  await page.setViewportSize({width:390,height:844});const mobile=await page.evaluate(()=>({width:innerWidth,content:document.documentElement.scrollWidth}));if(mobile.width!==mobile.content)throw Error('Mobile overflow');await page.screenshot({path:path.join(brief,'手机预览.png')});
  for(const href of await page.locator('a').evaluateAll(xs=>xs.map(x=>x.getAttribute('href'))))if(!fs.existsSync(path.resolve(brief,decodeURIComponent(href))))throw Error('Missing brief link '+href);
  await page.setViewportSize({width:1440,height:1000});await page.goto(pathToFileURL(path.join(run,'训练结果.html')).href);
  if(!await page.locator('img').evaluateAll(xs=>xs.length===2&&xs.every(x=>x.complete&&x.naturalWidth>0)))throw Error('Scientific charts');
  await page.locator('summary').click();if(!await page.getByText('跨任务不可相加。74来源组',{exact:false}).isVisible())throw Error('Auxiliary details');
  for(const href of await page.locator('a').evaluateAll(xs=>xs.map(x=>x.getAttribute('href'))))if(!fs.existsSync(path.resolve(run,decodeURIComponent(href))))throw Error('Missing run link '+href);
  await page.screenshot({path:path.join(run,'训练结果预览.png')});
  if(errors.length)throw Error(errors.join('\n'));
  const result={passed:true,desktop,mobile,two_scientific_figures_loaded:true,auxiliary_details_expand_passed:true,browser_errors:errors,pdf_exported:true};
  fs.writeFileSync(path.join(brief,'版式核验.json'),JSON.stringify(result,null,2)+'\n');process.stdout.write(JSON.stringify(result)+'\n');
 }finally{await browser.close();}
})().catch(e=>{process.stderr.write(e.stack+'\n');process.exitCode=1});
