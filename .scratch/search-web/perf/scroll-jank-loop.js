/**
 * scroll-jank-loop.js — 中鍵自動捲動卡頓的回饋迴圈(diagnosing-bugs Phase 1)
 *
 * 症狀:結果頁中鍵快速捲動時「一卡一卡」。
 * 路徑保真:headful + CDP 送真的中鍵按下/滑鼠下移,觸發瀏覽器**原生 autoscroll**
 * (renderer 主執行緒驅動,主執行緒一忙就直接掉幀);量測 rAF 幀間隔。
 * 訊號:長幀(> LONG_MS)比例超過門檻即紅。
 *
 * 用法:先在本資料夾 `npm init -y && npm i puppeteer-core`(node_modules 已被
 *       .gitignore 擋掉),再 node scroll-jank-loop.js [flags]
 *       測試用卡圖 pic.jpg 缺少時會自動抓一張。
 *   --browser=edge|chrome   預設 edge(使用者的預設瀏覽器)
 *   --per=100               每頁筆數(50/100/200/500)
 *   --realnet               不攔截,打真實 jsdelivr CDN(每 run 停用快取=冷載)
 *   --cpu=1                 CPU 節流倍率
 *   --eager                 圖片全改即時載入(對照組)
 *   --runs=3 --threshold=0.08 --secs=8
 * 綠 = exit 0,紅 = exit 1。
 */
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const puppeteer = require('puppeteer-core');

const BROWSERS = {
  chrome: 'C:/Program Files/Google/Chrome/Application/chrome.exe',
  edge: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
};
const SITE = 'file:///' + path.resolve(__dirname, '../../../web/index.html')
  .replace(/\\/g, '/');
const PIC_FILE = path.join(__dirname, 'pic.jpg');
if (!fs.existsSync(PIC_FILE)) {
  require('node:child_process').execFileSync('curl', ['-s', '-o', PIC_FILE,
    'https://cdn.jsdelivr.net/gh/salix5/query-data@master/pics/89631139.jpg']);
}
const PIC = fs.readFileSync(PIC_FILE);

const NET_MS = 40;
const LONG_MS = 33.4;    // 超過兩個 60Hz vsync = 掉幀,肉眼就是「卡一下」

const arg = (name, dflt) => {
  const m = process.argv.find(a => a.startsWith(`--${name}=`));
  return m ? m.split('=')[1] : dflt;
};
const RUNS = +arg('runs', 3);
const THRESHOLD = +arg('threshold', 0.08);
const CPU_RATE = +arg('cpu', 1);
const SECS = +arg('secs', 8);
const PER = arg('per', '100');
const PULL = +arg('pull', 260);
const BROWSER = arg('browser', 'edge');
const REALNET = process.argv.includes('--realnet');
const EAGER = process.argv.includes('--eager');
const NO_CV = process.argv.includes('--no-cv'); // 歸因用:關掉 content-visibility

function stats(deltas, travelled) {
  const sorted = [...deltas].sort((a, b) => a - b);
  const pct = p => sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * p))];
  const long = deltas.filter(d => d > LONG_MS);
  return {
    frames: deltas.length, longFrames: long.length,
    longRatio: long.length / deltas.length,
    p50: pct(0.50), p95: pct(0.95), max: sorted[sorted.length - 1], travelled,
  };
}

async function onePass(browser) {
  const page = await browser.newPage();
  const cdp = await page.createCDPSession();
  if (REALNET) {
    await cdp.send('Network.enable');
    await cdp.send('Network.setCacheDisabled', { cacheDisabled: true }); // 每 run 冷載
  } else {
    await page.setRequestInterception(true);
    page.on('request', req => {
      if (req.url().includes('/pics/')) {
        setTimeout(() => req.respond({
          status: 200, contentType: 'image/jpeg', body: PIC,
        }).catch(() => {}), NET_MS);
      } else req.continue().catch(() => {});
    });
  }
  if (CPU_RATE > 1) {
    await cdp.send('Emulation.setCPUThrottlingRate', { rate: CPU_RATE });
  }

  await page.goto(SITE, { waitUntil: 'domcontentloaded', timeout: 60000 });
  if (NO_CV) {
    await page.addStyleTag({ content:
      '.card { content-visibility: visible !important; }' });
  }
  await page.waitForSelector('#btnSearch');
  await page.select('#perPage', PER);
  await page.click('#btnSearch');
  await page.waitForSelector('#results article.card');
  if (EAGER) {                     // 對照組:懶載入拿掉,其餘一切相同
    await page.evaluate(() => document.querySelectorAll('img[loading=lazy]')
      .forEach(i => { i.loading = 'eager'; }));
  }
  // 首屏安定下來再開始量,量的才是「捲動」而不是「載入」
  await new Promise(r => setTimeout(r, 1200));

  await page.evaluate(() => {
    window.__frames = [];
    window.__stop = false;
    let last = performance.now();
    const step = () => {
      const now = performance.now();
      window.__frames.push(now - last);
      last = now;
      if (!window.__stop) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  });

  // 中鍵按下 → 滑鼠往下拉 PULL px → 停住:原生 autoscroll 以固定速度捲
  const vp = await page.evaluate(() => ({ w: innerWidth, h: innerHeight }));
  const cx = Math.floor(vp.w / 2), cy = 300;
  await cdp.send('Input.dispatchMouseEvent', {
    type: 'mousePressed', x: cx, y: cy, button: 'middle', buttons: 4, clickCount: 1 });
  for (let i = 1; i <= 10; i++) {
    await cdp.send('Input.dispatchMouseEvent', {
      type: 'mouseMoved', x: cx, y: cy + PULL * i / 10, button: 'middle', buttons: 4 });
    await new Promise(r => setTimeout(r, 15));
  }
  const y0 = await page.evaluate(() => window.scrollY);
  await new Promise(r => setTimeout(r, SECS * 1000));
  const y1 = await page.evaluate(() => window.scrollY);
  await cdp.send('Input.dispatchMouseEvent', {
    type: 'mouseReleased', x: cx, y: cy + PULL, button: 'middle', buttons: 0, clickCount: 1 });

  const deltas = await page.evaluate(() => { window.__stop = true; return window.__frames; });
  await page.close();
  if (y1 - y0 < 500) throw new Error(
    `autoscroll 沒有動(scrollY ${y0} → ${y1})——中鍵路徑沒觸發,量測無效`);
  return stats(deltas.slice(2), y1 - y0);
}

(async () => {
  const browser = await puppeteer.launch({
    executablePath: BROWSERS[BROWSER],
    headless: false,
    defaultViewport: null,          // 用真實視窗大小(最大化)
    args: ['--no-first-run', '--disable-extensions', '--start-maximized',
           '--window-position=0,0'],
  });
  console.log(`config: browser=${BROWSER} per=${PER} cpu=${CPU_RATE}x ` +
    `${REALNET ? 'realnet(cold)' : `mocknet(${NET_MS}ms)`}${EAGER ? ' eager' : ''}`);
  const runs = [];
  for (let i = 0; i < RUNS; i++) {
    const s = await onePass(browser);
    runs.push(s);
    console.log(`run ${i + 1}: frames=${s.frames} long=${s.longFrames} ` +
      `(${(s.longRatio * 100).toFixed(1)}%) p50=${s.p50.toFixed(1)}ms ` +
      `p95=${s.p95.toFixed(1)}ms max=${s.max.toFixed(0)}ms travelled=${s.travelled}px`);
  }
  await browser.close();
  const med = [...runs].sort((a, b) => a.longRatio - b.longRatio)[Math.floor(RUNS / 2)];
  const verdict = med.longRatio > THRESHOLD ? 'RED' : 'GREEN';
  console.log(`median longRatio=${(med.longRatio * 100).toFixed(1)}% ` +
    `threshold=${(THRESHOLD * 100).toFixed(0)}% → ${verdict}`);
  process.exit(verdict === 'RED' ? 1 : 0);
})().catch(e => { console.error(e); process.exit(2); });
