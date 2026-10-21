// Verify actual evaluated values in an isolated, unauthenticated browser.
const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { createRequire } = require('node:module');
const runtimeRequire = createRequire(process.env.CODEX_NODE_MODULES + '/package.json');
const { chromium } = runtimeRequire('playwright');

(async () => {
  const folder = path.resolve(process.argv[2]);
  const result = JSON.parse(fs.readFileSync(path.join(folder, 'results.json'), 'utf8'));
  const browser = await chromium.launch({ headless: true, channel: 'msedge' });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('http://127.0.0.1:8766/', { waitUntil: 'networkidle' });
  await page.getByText('本轮验证完成', { exact: true }).waitFor();
  const desktop = await page.evaluate(() => ({
    width: innerWidth, scrollWidth: document.documentElement.scrollWidth,
    charts: document.querySelectorAll('svg.recharts-surface').length,
    visibleBars: document.querySelectorAll('.recharts-bar-rectangle').length,
    progress: document.querySelector('progress').value,
    bodyText: document.body.innerText,
  }));
  if (desktop.progress !== result.evaluation_tasks || desktop.scrollWidth > desktop.width ||
      desktop.charts < 3 || desktop.visibleBars !== result.metrics.length ||
      !desktop.bodyText.includes(result.actual_estimator_fits + '次') ||
      !desktop.bodyText.includes('未超过首轮最低MAE2.85')) throw Error('Desktop review failed.');
  delete desktop.bodyText;
  await page.screenshot({ path: path.join(folder, 'dashboard_desktop.png'), fullPage: true });
  await page.locator('.training-filter select').selectOption('nested_linear');
  const first = JSON.parse(fs.readFileSync(path.join(folder, 'predictions.json'), 'utf8')).find(r => r.variant === 'nested_linear');
  const cells = await page.locator('.training-records tbody tr').first().locator('td').allTextContents();
  if (Math.abs(Number(cells[2]) - first.predicted) > .006) throw Error('Filtered prediction does not match saved output.');
  if (await page.locator('.training-records tbody tr').count() !== 31) throw Error('Filtered count wrong.');
  await page.setViewportSize({ width: 390, height: 844 });
  const mobile = await page.evaluate(() => ({ width: innerWidth, scrollWidth: document.documentElement.scrollWidth }));
  if (mobile.scrollWidth > mobile.width) throw Error('Mobile page overflow.');
  await page.screenshot({ path: path.join(folder, 'dashboard_mobile.png'), fullPage: true });
  const offline = await browser.newPage();
  offline.on('pageerror', error => errors.push(error.message));
  await offline.goto(pathToFileURL(path.join(folder, '诊断与改进结果.html')).href);
  await offline.getByText('已保存的完整结果快照', { exact: true }).waitFor();
  if (Number(await offline.locator('progress').getAttribute('value')) !== result.evaluation_tasks) throw Error('Offline completion missing.');
  if (await offline.locator('a[href="./results.json"]').count() !== 1) throw Error('Offline result link missing.');
  await browser.close();
  if (errors.length) throw Error(errors.join('\n'));
  const report = { passed: true, browser: 'isolated headless Microsoft Edge', desktop, mobile,
    real_prediction_filter_verified: true, filtered_records: 31, offline_snapshot_and_links_verified: true,
    javascript_errors: errors, integrated_browser_unavailable: 'CUA kernel could not start; isolated headless browser used.' };
  fs.writeFileSync(path.join(folder, 'dashboard_visual_verification.json'), JSON.stringify(report, null, 2) + '\n');
  process.stdout.write(JSON.stringify(report));
})().catch(e => { process.stderr.write(e.stack + '\n'); process.exitCode = 1; });
