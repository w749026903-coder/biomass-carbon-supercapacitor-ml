// Verify the completed semantic-correction report without contacting a website.
const fs = require('fs');
const path = require('path');
const { pathToFileURL, fileURLToPath } = require('url');
const { chromium } = require(path.join(process.env.CODEX_NODE_MODULES, 'playwright'));
const root = path.resolve(__dirname, '..');
const base = path.join(root, '保持率达标研究_v3_主线与近优组合_20261030');
const batch = path.join(base, '第十一轮_双电极原文曲线补充', 'batch5_指标纠错_20261031');
const check = (ok, message) => { if (!ok) throw Error(message); };
(async () => {
  const browser = await chromium.launch({channel: 'msedge', headless: true});
  const errors = [], views = [];
  try {
    for (const [filename, secondary] of [['研究进度.html', false], ['第十二轮_扩充双电极来源验证/训练结果与科学复核.html', true]]) {
      for (const width of [1360, 390]) {
        const page = await browser.newPage({viewport: {width, height: width === 1360 ? 1000 : 844}});
        page.on('pageerror', error => errors.push(String(error)));
        await page.goto(pathToFileURL(path.join(base, filename)).href);
        await page.locator('img').evaluateAll(imgs => Promise.all(imgs.map(i => i.decode())));
        const state = await page.evaluate(() => ({
          text: document.body.innerText,
          viewport: innerWidth, content: document.documentElement.scrollWidth,
          rows: document.querySelectorAll('tbody tr').length,
          details: document.querySelectorAll('details').length,
          media: [...document.images].map(i => ({url: i.src, width: i.naturalWidth})),
          links: [...document.querySelectorAll('a')].map(a => a.href),
        }));
        for (const text of ['目标继续active', '6400次拟合', '65% / 79.3%', '63917', '原20%', '尚未重新拟合', '完整持续目标']) check(state.text.includes(text), 'Missing ' + text);
        check(state.content <= state.viewport + 1, 'Horizontal overflow');
        check(state.rows === 2 && state.details === 1, 'Wrong table or disclosure');
        for (const m of state.media) check(m.width > 0, 'Broken image');
        for (const u of [...state.links, ...state.media.map(m => m.url)]) {
          check(u.startsWith('file:'), 'Report unexpectedly requires remote website');
          check(fs.existsSync(fileURLToPath(u)), 'Missing local target: ' + u);
        }
        await page.locator('summary').click();
        check(await page.locator('details').evaluate(e => e.open), 'Disclosure did not open');
        await page.locator('summary').click();
        check(!await page.locator('details').evaluate(e => e.open), 'Disclosure did not close');
        if (!secondary && width === 1360) {
          await page.evaluate(() => scrollTo(0, 0));
          await page.screenshot({path: path.join(base, '研究进度预览.png'), fullPage: true});
          await page.screenshot({path: path.join(batch, 'dashboard_review.png')});
        }
        views.push({file: filename, width, content: state.content, rows: state.rows, details: state.details, local_links: state.links.length, images: state.media.length});
        await page.close();
      }
    }
    check(errors.length === 0, 'Browser errors');
    const result = {status: 'passed', report_scope: 'P12 complete; MK9 semantic correction; no corrected-data retraining yet', views, comparison_rows: 2, toggles_checked: 4, local_links_exist: true, image_decoding_verified: true, browser_errors: errors};
    fs.writeFileSync(path.join(base, '版式核验.json'), JSON.stringify(result, null, 2) + '\n');
    process.stdout.write(JSON.stringify(result) + '\n');
  } finally { await browser.close(); }
})().catch(error => { process.stderr.write(String(error) + '\n'); process.exitCode = 1; });
