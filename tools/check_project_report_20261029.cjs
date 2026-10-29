const fs = require('node:fs');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const {createRequire} = require('node:module');
const {chromium} = createRequire(process.env.CODEX_NODE_MODULES + '/package.json')('playwright');

(async () => {
  const dir = path.resolve('项目进展报告_20261029');
  const browser = await chromium.launch({headless: true, channel: 'msedge'});
  try {
    const page = await browser.newPage({viewport: {width: 1440, height: 1000}});
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    await page.goto(pathToFileURL(path.join(dir, '项目进展报告.html')).href);
    await page.evaluate(() => document.fonts.ready);
    const text = await page.locator('main').innerText();
    for (const value of ['420', '5,197', '3,727', '71.71%', '5.1509', '6.9087', '0.0955', '没有通过']) {
      if (!text.includes(value)) throw Error('Missing reviewed statistic ' + value);
    }
    if (await page.locator('section').count() !== 5) throw Error('Report sections');
    if (!await page.locator('figure img').evaluate(img => img.complete && img.naturalWidth > 0)) throw Error('Frozen model figure missing');
    const desktop = await page.evaluate(() => ({width: innerWidth, content: document.documentElement.scrollWidth}));
    if (desktop.width !== desktop.content) throw Error('Desktop overflow');
    await page.screenshot({path: path.join(dir, '报告桌面预览.png')});
    await page.pdf({path: path.join(dir, '项目进展报告.pdf'), format: 'A4', printBackground: true,
      preferCSSPageSize: true, displayHeaderFooter: true, headerTemplate: '<span></span>',
      footerTemplate: '<div style="font-size:9px;width:100%;text-align:center;color:#777">项目进展报告 · 2026-10-29　<span class="pageNumber"></span> / <span class="totalPages"></span></div>'});
    await page.setViewportSize({width: 390, height: 844});
    const mobile = await page.evaluate(() => ({width: innerWidth, content: document.documentElement.scrollWidth}));
    if (mobile.width !== mobile.content || errors.length) throw Error('Mobile overflow or JS error');
    await page.screenshot({path: path.join(dir, '报告手机预览.png')});
    for (const href of await page.locator('a').evaluateAll(xs => xs.map(x => x.getAttribute('href')))) {
      if (!/^https:\/\//.test(href) && !fs.existsSync(path.join(dir, decodeURIComponent(href)))) throw Error('Missing report link: ' + href);
    }
    const result = {passed: true, desktop, mobile, reviewed_statistics_present: true,
      frozen_figure_loaded: true, pdf_exported: true, browser_errors: errors};
    fs.writeFileSync(path.join(dir, '版式核验.json'), JSON.stringify(result, null, 2) + '\n');
    process.stdout.write(JSON.stringify(result) + '\n');
  } finally { await browser.close(); }
})().catch(e => {process.stderr.write(e.stack + '\n'); process.exitCode = 1;});
