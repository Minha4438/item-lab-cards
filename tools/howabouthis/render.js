// HTML → 1080x1350 PNG.  node render.js '[["a.html","a.png"], ...]'
let playwright;
try { playwright = require('playwright'); } catch { playwright = require('/opt/node22/lib/node_modules/playwright'); }
const jobs = JSON.parse(process.argv[2]);
(async () => {
  const b = await playwright.chromium.launch();
  const p = await b.newPage({ viewport: { width: 1080, height: 1350 } });
  for (const [html, out] of jobs) {
    await p.goto(require('url').pathToFileURL(html).href);  // 윈도우 경로(C:\\...)도 처리
    await p.waitForFunction(() => document.body.dataset.ready === '1', null, { timeout: 15000 });
    await p.screenshot({ path: out });
  }
  await b.close();
})().catch(e => { console.error(e); process.exit(1); });
