// Final-build check after translating only two candidate evidence display strings.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),crypto=require('node:crypto');
const {createRequire}=require('node:module');
const {chromium}=createRequire(process.env.CODEX_NODE_MODULES+'/package.json')('playwright');
(async()=>{
 const app=path.resolve('文献提取进度'),read=p=>JSON.parse(fs.readFileSync(path.join(app,p),'utf8'));
 const manifest=read('dist/data-app-build.json'),wording=read('output/wording_review_v24.json'),qa=read('dashboard_visual_verification.json');
 assert.equal(qa.passed,true);assert.deepEqual(qa.build_manifest,wording.prior_full_workflow_build_manifest);
 assert.equal(crypto.createHash('sha256').update(fs.readFileSync(path.join(app,'src/data.json'))).digest('hex'),wording.new_source_sha256);
 assert.equal(manifest.snapshot.sha256,wording.new_source_sha256);assert.equal(manifest.runtimeSha256,qa.build_manifest.runtimeSha256);
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 try{
  const p=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];p.on('pageerror',e=>errors.push(e.message));
  await p.goto('http://127.0.0.1:8770/?view=1&tab=dashboard',{waitUntil:'networkidle'});
  const block=id=>p.locator(`[data-component-id="${id}"]`),candidate=block('batch24-candidates-table');
  await candidate.getByText(/of 2 results/).first().waitFor();assert.match(await candidate.innerText(),/器件原图未取得/);assert.match(await candidate.innerText(),/自身表1约81%及图4/);
  assert.match(await block('batch24-inputs-table').innerText(),/of 18 results/);assert.match(await block('inspection24-table').innerText(),/of 4 results/);assert.match(await block('material-numbers').innerText(),/4,?459/);assert.match(await block('pending-corrections').innerText(),/37/);
  assert.equal(await p.locator('svg.recharts-surface').count(),8);await candidate.screenshot({path:path.join(app,'output/playwright/batch24-candidates.png')});
  const desktop=await p.evaluate(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth}));assert.ok(desktop.scrollWidth<=desktop.width);
  await p.setViewportSize({width:390,height:900});await candidate.scrollIntoViewIfNeeded();
  const mobile=await p.evaluate(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth}));assert.ok(mobile.scrollWidth<=mobile.width);
  await candidate.screenshot({path:path.join(app,'output/playwright/batch24-candidates-mobile.png')});assert.equal(errors.length,0);
  qa.full_workflow_build_manifest=qa.build_manifest;qa.build_manifest=manifest;
  qa.final_build_smoke={passed:true,scope:'Only two evidence display strings translated; rawrecords, numericfacts, masks, filters and queries otherwise unchanged. Full workflow applies to prior exact snapshot; this final build checked on desktop/mobile.',wording_review:'output/wording_review_v24.json',desktop,mobile,charts:8,inputs24:18,inspection24:4,candidates24:2,pending_original:37,javascript_errors:errors};
  fs.writeFileSync(path.join(app,'dashboard_visual_verification.json'),JSON.stringify(qa,null,2)+'\n');console.log(JSON.stringify(qa.final_build_smoke));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
