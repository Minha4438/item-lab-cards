const { chromium } = require(process.env.PLAYWRIGHT_PATH || 'playwright');
const jobs = require(__dirname + '/jobs.json');
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1080, height: 1350 } });
  for (const [html, out] of jobs) {
    await p.goto('file://' + html);
    await p.evaluate(() => document.fonts.ready);
    await p.waitForTimeout(150);
    await p.screenshot({ path: out });
  }
  await b.close();
})();
