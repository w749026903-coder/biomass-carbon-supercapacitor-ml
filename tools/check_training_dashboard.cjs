// Local CLI smoke check; isolated browser context, no account/profile access.
const fs = require('node:fs');
const path = require('node:path');
const { createRequire } = require('node:module');
const runtimeRequire = createRequire(process.env.CODEX_NODE_MODULES + '/package.json');
const { chromium } = runtimeRequire('playwright');

(async () => {
  const folder = path.resolve(process.argv[2]);
  const browser = await chromium.launch({ headless: true, channel: 'msedge' });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('http://127.0.0.1:8765/', { waitUntil: 'networkidle' });
  await page.getByText('本轮训练与验证已完成', { exact: true }).waitFor();
  const desktop = await page.evaluate(() => ({
    width: innerWidth, scrollWidth: document.documentElement.scrollWidth,
    charts: document.querySelectorAll('svg.recharts-surface').length,
    visibleBars: document.querySelectorAll('.recharts-bar-rectangle').length,
    progress: document.querySelector('progress').value,
    secondaryTextColor: getComputedStyle(document.querySelector('.training-note')).color,
    creatingText: document.body.innerText.includes('Creating dashboard'),
  }));
  if (desktop.progress !== 161 || desktop.scrollWidth > desktop.width || desktop.creatingText || desktop.charts < 3) throw Error('Desktop review failed: ' + JSON.stringify(desktop));
  await page.screenshot({ path: path.join(folder, 'dashboard_desktop.png'), fullPage: true });
  await page.locator('.training-filter select').selectOption('MLP/no_current');
  const first = JSON.parse(fs.readFileSync(path.join(folder, 'predictions.json'), 'utf8')).find(r => r.variant === 'MLP/no_current');
  const cells = await page.locator('.training-records tbody tr').first().locator('td').allTextContents();
  if (Math.abs(Number(cells[3]) - first.predicted) > .006) throw Error('Prediction filter did not update actual values.');
  if (await page.locator('.training-records tbody tr').count() !== 31) throw Error('Filtered row count wrong.');
  await page.setViewportSize({ width: 390, height: 844 });
  const mobile = await page.evaluate(() => ({ width: innerWidth, scrollWidth: document.documentElement.scrollWidth }));
  if (mobile.scrollWidth > mobile.width) throw Error('Mobile page overflow.');
  await page.screenshot({ path: path.join(folder, 'dashboard_mobile.png'), fullPage: true });
  const offline = await browser.newPage();
  await offline.goto(require('node:url').pathToFileURL(path.join(folder, '训练进度与结果.html')).href);
  await offline.getByText('已保存的完整结果快照 · 离线查看', { exact: true }).waitFor();
  if (await offline.locator('progress').getAttribute('value') !== '161') throw Error('Offline completion missing.');
  const resultLink = await offline.locator('a[href="./results.json"]').count();
  if (resultLink !== 1) throw Error('Offline result link is not relative.');
  await browser.close();
  if (errors.length) throw Error(errors.join('\n'));
  const report = { passed: true, browser: 'isolated headless Microsoft Edge', desktop, mobile,
    real_prediction_filter_verified: true, filtered_records: 31, offline_snapshot_and_links_verified: true, javascript_errors: errors,
    integrated_browser_unavailable: 'CUA kernel startup failed in this environment; local isolated headless verification succeeded.' };
  fs.writeFileSync(path.join(folder, 'dashboard_visual_verification.json'), JSON.stringify(report, null, 2) + '\n');
  process.stdout.write(JSON.stringify(report));
})().catch(e => { process.stderr.write(e.stack + '\n'); process.exitCode = 1; });
