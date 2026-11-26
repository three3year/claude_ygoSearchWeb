'use strict';
/* 動作搜尋兩份人工驗收清單,在真 Chrome 裡自動跑(雙擊開啟、經伺服器開啟各一遍)。
   跑法(repo 根):node .scratch/action-search-coverage/browser-acceptance/run.js
   輸出:同資料夾的 result.md 與 shots/。可重跑(每次清掉舊截圖)。
   只讀網站;「載入時機 5」會把 web/action-data.js 暫時改名,做完(含出錯時)一定改回。 */

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const http = require('node:http');
const { spawn, execSync } = require('node:child_process');

const PW = path.join(os.homedir(), 'AppData/Roaming/npm/node_modules/@playwright/mcp/node_modules/playwright');
const { chromium } = require(PW);
const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';

const { Recorder, Site, OUT, SHOTS } = require('./lib');
const webList = require('./steps-web');
const covList = require('./steps-coverage');

const ROOT = path.join(__dirname, '..', '..', '..');
const ACTION_SRC = path.join(ROOT, 'web', 'action-data.js');
const ACTION_TMP = ACTION_SRC + '.acceptance-renamed';

const MODES = { file: '雙擊開啟', server: '經伺服器' };
const LISTS = {
  web: { title: '第 1 份:動作搜尋網站(.scratch/action-search-web/manual-acceptance.md)', mod: webList },
  cov: { title: '第 2 份:方的涵蓋與卡名包含(.scratch/action-search-coverage/manual-acceptance.md)', mod: covList },
};

/* 任何情況下都把 action-data.js 改回來 */
function restoreActionData() {
  if (fs.existsSync(ACTION_TMP) && !fs.existsSync(ACTION_SRC)) fs.renameSync(ACTION_TMP, ACTION_SRC);
}
process.on('exit', restoreActionData);
process.on('SIGINT', () => { restoreActionData(); process.exit(130); });

/* 動作索引第一次載入、結果區、狀態行的每次變動都記下來(載入中那一瞬間的畫面) */
const OBSERVER = `
window.__obs = { results: [], status: [] };
document.addEventListener('DOMContentLoaded', () => {
  const r = document.getElementById('results');
  const s = document.getElementById('actionStatus');
  if (r) new MutationObserver(() => window.__obs.results.push(r.textContent))
    .observe(r, { childList: true, subtree: true, characterData: true });
  if (s) new MutationObserver(() => window.__obs.status.push(s.textContent))
    .observe(s, { childList: true, subtree: true, characterData: true, attributes: true });
});`;

function waitHttp(url, ms) {
  const end = Date.now() + ms;
  return new Promise((resolve, reject) => {
    const tryOnce = () => {
      http.get(url, res => { res.resume(); resolve(); }).on('error', () => {
        if (Date.now() > end) reject(new Error('伺服器沒起來')); else setTimeout(tryOnce, 200);
      });
    };
    tryOnce();
  });
}

function portFree(port) {
  return new Promise(resolve => {
    http.get(`http://127.0.0.1:${port}/`, res => { res.resume(); resolve(false); })
      .on('error', () => resolve(true));
  });
}

/* ---------- 版面檢查 ---------- */

async function overflow(site) {
  return site.page.evaluate(() => {
    const sb = document.getElementById('sidebar');
    const r = sb.getBoundingClientRect();
    const cs = getComputedStyle(sb);
    const right = r.right - parseFloat(cs.borderRightWidth);
    const left = r.left + parseFloat(cs.borderLeftWidth);
    const name = el => el.tagName.toLowerCase() + (el.id ? '#' + el.id : '')
      + (el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\s+/).join('.') : '')
      + (el.textContent ? `「${el.textContent.trim().slice(0, 12)}」` : '');
    const bad = [];
    sb.querySelectorAll('*').forEach(el => {
      if (el.closest('[hidden]')) return;
      const b = el.getBoundingClientRect();
      if (!b.width && !b.height) return;
      if (b.right > right + 0.5 || b.left < left - 0.5) bad.push(`${name(el)} 右緣 ${b.right.toFixed(1)} > 側欄 ${right.toFixed(1)}`);
    });
    return { bad, sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth,
             sbw: Math.round(r.width), sbScroll: sb.scrollWidth - sb.clientWidth };
  });
}

async function cardCheck(site) {
  return site.page.evaluate(() => {
    const area = document.querySelector('.results-area').getBoundingClientRect();
    const bad = [];
    const cards = [...document.querySelectorAll('#results article.card')];
    cards.forEach(a => {
      const r = a.getBoundingClientRect();
      const img = a.querySelector('.card-img').getBoundingClientRect();
      const body = a.querySelector('.card-body').getBoundingClientRect();
      const id = a.dataset.cid;
      if (r.width <= 0) bad.push(`${id} 卡片寬 0`);
      if (img.width <= 0 || img.right > r.right + 0.5 || img.left < r.left - 0.5) bad.push(`${id} 圖片溢出卡片`);
      if (body.width < 100 || body.right > r.right + 0.5) bad.push(`${id} 卡文區寬 ${Math.round(body.width)}`);
      if (r.right > area.right + 0.5) bad.push(`${id} 卡片超出結果區`);
      if (a.scrollWidth > a.clientWidth + 1) bad.push(`${id} 卡片內容橫向溢出`);
    });
    return { n: cards.length, bad, cardW: cards.length ? Math.round(cards[0].getBoundingClientRect().width) : 0 };
  });
}

/* ---------- 主流程 ---------- */

async function main() {
  fs.mkdirSync(SHOTS, { recursive: true });
  for (const f of fs.readdirSync(SHOTS)) fs.unlinkSync(path.join(SHOTS, f));
  restoreActionData();

  const port = execSync(`node "${path.join(os.homedir(), '.claude/scripts/checkout-port.mjs')}" acceptance`).toString().trim();
  const server = spawn('python', ['-m', 'http.server', port, '--directory', 'web', '--bind', '127.0.0.1'],
    { cwd: ROOT, stdio: 'ignore' });
  const bases = {
    file: 'file:///' + path.join(ROOT, 'web', 'index.html').replace(/\\/g, '/').replace(/^[a-z]:/, d => d.toUpperCase()),
    server: `http://127.0.0.1:${port}/`,
  };
  const rec = new Recorder();
  const consoleLog = [];
  const layouts = [];
  let browser;
  const started = new Date();
  try {
    await waitHttp(bases.server, 15000);
    browser = await chromium.launch({ executablePath: CHROME });
    const version = browser.version();

    for (const mode of Object.keys(MODES)) {
      if (process.env.MODE && mode !== process.env.MODE) continue;
      const newSite = async () => {
        const context = await browser.newContext({ viewport: { width: 1400, height: 900 } });
        await context.addInitScript(OBSERVER);
        const page = await context.newPage();
        const site = new Site(page, bases[mode], rec, mode);
        site.context = context;
        site.reqs = [];
        site.errs = [];
        page.on('request', r => site.reqs.push(r.url()));
        page.on('console', m => {
          if (m.type() !== 'error') return;
          const e = { mode, step: rec.cur ? `${rec.cur.list} ${rec.cur.id}` : '', text: m.text(),
                      url: (m.location() || {}).url || '' };
          site.errs.push(e);
          consoleLog.push(e);
        });
        page.on('pageerror', err => {
          const e = { mode, step: rec.cur ? `${rec.cur.list} ${rec.cur.id}` : '', text: 'pageerror: ' + err.message, url: '' };
          site.errs.push(e);
          consoleLog.push(e);
        });
        site.actionRequests = () => site.reqs.filter(u => /\/action-data\.js$/.test(u));
        site.errors = () => site.errs;
        return site;
      };

      for (const list of Object.keys(LISTS)) {
        const S = { rec, overflow };
        for (const [secName, fn] of LISTS[list].mod.sections) {
          if (process.env.SECTION && !process.env.SECTION.split(',').includes(secName)) continue;
          let current = null;
          const run = async (id, did, expect, body, opts = {}) => {
            rec.begin(mode, list, id, did, expect);
            const step = rec.cur;
            if (!current) current = await newSite();
            try {
              await body(current);
            } catch (err) {
              step.error = String(err && err.stack || err).split('\n').slice(0, 3).join(' | ');
              try { step.shots.push(await current.shot(`error-${list}-${id.replace(/\s+/g, '')}`)); } catch (_) { /* 截不到就算了 */ }
            } finally {
              restoreActionData();
            }
            if (opts.expectLoadFail) {
              current.errs.forEach(e => { if (/action-data\.js/.test(e.url) || /ERR_FILE_NOT_FOUND|404/.test(e.text)) e.expected = '載入時機 5 故意讓 action-data.js 載不到'; });
            }
            if (!opts.keep) { await current.context.close(); current = null; }
          };
          await fn(S, run);
          if (current) await current.context.close();
        }
      }

      /* 版面:三種寬度 */
      for (const width of (process.env.SECTION && !process.env.SECTION.includes('版面') ? [] : [1400, 820, 390])) {
        rec.begin(mode, 'layout', `版面 ${width}`, `${width} 寬:搜「破壞+除外」,動作搜尋展開「更多」、給條件(龍族、字段建議、卡名包含),再切指定一張卡(建議清單)`,
          '側欄內元素右緣不超出側欄、頁面沒有橫向捲動、結果卡片沒被擠爆');
        const step = rec.cur;
        const site = await newSite();
        const out = { mode, width };
        try {
          await site.page.setViewportSize({ width, height: 2400 });
          await site.open();
          const mobile = width <= 720;
          if (mobile) await site.page.click('#btnFilters');
          await site.openAction();
          await site.words(['破壞', '除外']);
          await site.searchOnly();
          if (mobile) await site.page.click('#btnFilters');
          await site.page.click('#actionFields button[data-more]');
          await site.target('cond');
          await site.givenBtn('race', '龍族');
          await site.page.fill('#actionSetInput', '黑');
          await site.givenName('ブラック・マジシャン・ガール');
          const o1 = await overflow(site);
          const cards = await cardCheck(site);
          out.full = await site.shot(`layout-${width}-full`, { fullPage: true });
          out.box = await site.shot(`layout-${width}-actionbox`, { locator: site.page.locator('#actionBox') });
          await site.target('card');
          await site.page.fill('#actionCardInput', '黑魔導');
          const o2 = await overflow(site);
          out.card = await site.shot(`layout-${width}-cardpick`, { locator: site.page.locator('#actionBox') });
          out.sbw = o1.sbw;
          rec.note(`側欄寬 ${o1.sbw}px;卡片寬 ${cards.cardW}px`);
          rec.check('給條件時側欄內元素不超出', '0 個', o1.bad.slice(0, 5).join(';') || '0 個', !o1.bad.length);
          rec.check('指定一張卡時側欄內元素不超出', '0 個', o2.bad.slice(0, 5).join(';') || '0 個', !o2.bad.length);
          rec.check('側欄沒有自己的橫向捲動', '0', String(Math.max(o1.sbScroll, o2.sbScroll)), o1.sbScroll <= 0 && o2.sbScroll <= 0);
          rec.check('頁面沒有橫向捲動', `scrollWidth ≤ ${o1.cw}`, `${o1.sw} / ${o2.sw}`, o1.sw <= o1.cw && o2.sw <= o2.cw);
          rec.check('結果卡片沒被擠爆', `${cards.n} 張都正常`, cards.bad.slice(0, 5).join(';') || `${cards.n} 張都正常`, cards.n > 0 && !cards.bad.length);
          const wantW = width === 1400 ? 400 : width === 820 ? 280 : null;
          if (wantW) rec.eq('側欄寬度', `${wantW}px`, `${o1.sbw}px`);
          rec.look(`${width} 寬全頁:版面是否順眼`, out.full);
          rec.look(`${width} 寬:給條件的種族 26 顆按鈕在側欄(寬 ${o1.sbw}px)的樣子`, out.box);
          rec.look(`${width} 寬:指定一張卡的輸入框與建議清單`, out.card);
          out.o1 = o1; out.o2 = o2; out.cards = cards;
        } catch (err) {
          step.error = String(err && err.stack || err).split('\n').slice(0, 3).join(' | ');
        }
        layouts.push(out);
        await site.context.close();
      }
    }

    write(rec, { consoleLog, layouts, version, port, started, bases });
  } finally {
    if (browser) await browser.close();
    server.kill();
    restoreActionData();
    await new Promise(r => setTimeout(r, 500));
    const free = await portFree(port);
    console.log(`伺服器已關:${free};action-data.js 在原位:${fs.existsSync(ACTION_SRC)}`);
  }
}

/* ---------- 寫 result.md ---------- */

const STATUS_ZH = { pass: '過', fail: '**不過**', na: '無法自動', error: '**腳本錯誤**' };
const cell = s => String(s == null ? '' : s).replace(/\|/g, '\\|').replace(/\n/g, ' ');

function write(rec, { consoleLog, layouts, version, port, started, bases }) {
  const L = [];
  const head = execSync('git log -1 --format="%h %s"', { cwd: ROOT }).toString().trim();
  const dirty = execSync('git status --short web', { cwd: ROOT }).toString().trim();
  L.push('# 動作搜尋 瀏覽器自動驗收結果', '');
  L.push(`- 跑的時間:${started.toLocaleString('zh-TW', { hour12: false })}`);
  L.push(`- Chrome ${version}(headless,Playwright 驅動),腳本 \`.scratch/action-search-coverage/browser-acceptance/run.js\``);
  L.push(`- 網站:main 工作樹的 \`web/\`(HEAD ${head};工作樹改動:${dirty ? dirty.replace(/\n/g, '、') : '無'})`);
  L.push(`- 雙擊開啟:\`${bases.file}\`;經伺服器:\`${bases.server}\`(\`python -m http.server ${port} --directory web --bind 127.0.0.1\`,跑完已關)`);
  L.push('- 張數讀畫面上的「共 N 張」與「另有 N 張無法確認」;卡在不在用畫面翻頁(每頁 500 筆)收集每張卡的卡片密碼(`data-cid`)比對。');
  L.push('- 第 1 份清單「動作、從、到」3 的對手改為 83 張、「被動作的卡」8 改為 1,260 張(第 2 份清單開頭的說明)。');
  L.push('');

  const steps = rec.steps;
  const byKey = {};
  steps.forEach(s => { (byKey[`${s.list}|${s.id}`] = byKey[`${s.list}|${s.id}`] || []).push(s); });

  // 總覽
  L.push('## 總覽', '');
  L.push('| 清單 | 開法 | 步數 | 過 | 不過 | 無法自動 | 腳本錯誤 |', '|---|---|---:|---:|---:|---:|---:|');
  const tot = { n: 0, pass: 0, fail: 0, na: 0, error: 0 };
  for (const list of ['web', 'cov', 'layout']) {
    for (const mode of Object.keys(MODES)) {
      const ss = steps.filter(s => s.list === list && s.mode === mode);
      const c = { pass: 0, fail: 0, na: 0, error: 0 };
      ss.forEach(s => { c[rec.status(s)]++; });
      tot.n += ss.length; Object.keys(c).forEach(k => { tot[k] += c[k]; });
      const name = list === 'layout' ? '版面(三種寬度)' : list === 'web' ? '第 1 份' : '第 2 份';
      L.push(`| ${name} | ${MODES[mode]} | ${ss.length} | ${c.pass} | ${c.fail} | ${c.na} | ${c.error} |`);
    }
  }
  L.push(`| **合計** | | ${tot.n} | ${tot.pass} | ${tot.fail} | ${tot.na} | ${tot.error} |`, '');
  const partial = steps.filter(s => rec.status(s) === 'pass' && s.checks.some(c => c.kind === 'na'));
  if (partial.length) {
    L.push('「過」裡有部分檢查無法自動的步驟(其餘檢查都過):', '');
    const seen = new Set();
    partial.forEach(s => {
      const k = `${s.list}|${s.id}`;
      if (seen.has(k)) return;
      seen.add(k);
      s.checks.filter(c => c.kind === 'na').forEach(c => L.push(`- ${s.list === 'web' ? '第 1 份' : '第 2 份'} ${s.id}「${c.name}」:${c.actual}`));
    });
    L.push('');
  }

  // 不過
  const bad = steps.filter(s => ['fail', 'error'].includes(rec.status(s)));
  L.push('## 不過與腳本錯誤', '');
  if (!bad.length) L.push('(沒有)');
  bad.forEach(s => {
    const fails = s.checks.filter(c => c.kind === 'fail').map(c => `${c.name}:期望 ${c.expected},實際 ${c.actual}`);
    L.push(`- ${s.list} ${s.id}(${MODES[s.mode]}):${s.error ? '腳本錯誤 ' + s.error : fails.join(';')}${s.shots.length ? `(截圖 ${s.shots.join('、')})` : ''}`);
  });
  L.push('');

  // 版面
  L.push('## 版面檢查', '');
  L.push('| 開法 | 寬 | 側欄寬 | 側欄內超出(給條件/指定卡) | 頁面橫向捲動(scrollWidth/clientWidth) | 卡片 | 全頁截圖 |', '|---|---:|---:|---|---|---|---|');
  layouts.forEach(o => {
    if (!o.o1) { L.push(`| ${MODES[o.mode]} | ${o.width} | | 腳本錯誤 | | | |`); return; }
    L.push(`| ${MODES[o.mode]} | ${o.width} | ${o.sbw}px | ${o.o1.bad.length}/${o.o2.bad.length} 個 | ${o.o1.sw}/${o.o1.cw}、${o.o2.sw}/${o.o2.cw} | ${o.cards.n} 張,異常 ${o.cards.bad.length} | ${o.full} |`);
  });
  L.push('');

  // 請站主看
  L.push('## 請站主看', '', '主觀項目,腳本不判過或不過;截圖在 `shots/`。', '');
  rec.looks.forEach(l => {
    L.push(`- [${MODES[l.mode]}] ${l.list === 'layout' ? '版面' : l.list === 'web' ? '第 1 份' : '第 2 份'} ${l.id}:${l.desc} — \`${l.shot}\``);
  });
  L.push('');

  // Console
  L.push('## Console', '');
  const unexpected = consoleLog.filter(e => !e.expected);
  const isExternal = e => /^https?:\/\//.test(e.url) && !e.url.includes('127.0.0.1');
  const js = unexpected.filter(e => !isExternal(e));
  const ext = unexpected.filter(isExternal);
  L.push(`- 網站本身的紅字(JS 錯誤、站內資源載入失敗,不含預期的):${js.length} 則`);
  js.slice(0, 30).forEach(e => L.push(`  - [${MODES[e.mode]}] ${e.step}:${e.text} ${e.url}`));
  L.push(`- 外部資源(卡圖 CDN 等)載入失敗:${ext.length} 則`);
  const hosts = {};
  ext.forEach(e => { const h = e.url.split('/')[2]; hosts[h] = (hosts[h] || 0) + 1; });
  Object.keys(hosts).forEach(h => L.push(`  - ${h}:${hosts[h]} 則`));
  const exp = consoleLog.filter(e => e.expected);
  L.push(`- 預期的紅字(載入時機 5 故意讓 action-data.js 載不到):${exp.length} 則`);
  exp.forEach(e => L.push(`  - [${MODES[e.mode]}] ${e.text} ${e.url}`));
  L.push('');

  // 逐步
  L.push('## 逐步結果', '');
  for (const list of ['web', 'cov', 'layout']) {
    L.push(`### ${list === 'layout' ? '版面(三種寬度)' : LISTS[list].title}`, '');
    const ids = [];
    steps.filter(s => s.list === list).forEach(s => { if (!ids.includes(s.id)) ids.push(s.id); });
    for (const id of ids) {
      const runs = byKey[`${list}|${id}`];
      const f = runs.find(s => s.mode === 'file');
      const sv = runs.find(s => s.mode === 'server');
      const first = f || sv;
      L.push(`#### ${id} — 雙擊:${f ? STATUS_ZH[rec.status(f)] : '—'};伺服器:${sv ? STATUS_ZH[rec.status(sv)] : '—'}`, '');
      L.push(`- 做了什麼:${first.did}`, `- 期望:${first.expect}`);
      runs.forEach(s => { if (s.error) L.push(`- **腳本錯誤**(${MODES[s.mode]}):${s.error}`); });
      L.push('', '| 檢查 | 期望 | 雙擊開啟 | 經伺服器 |', '|---|---|---|---|');
      const names = [];
      runs.forEach(s => s.checks.forEach(c => { if (!names.includes(c.name)) names.push(c.name); }));
      const mark = c => (!c ? '—' : c.kind === 'pass' ? `✓ ${c.actual}` : c.kind === 'fail' ? `✗ ${c.actual}` : `無法自動:${c.actual}`);
      names.forEach(n => {
        const cf = f && f.checks.find(c => c.name === n);
        const cs = sv && sv.checks.find(c => c.name === n);
        L.push(`| ${cell(n)} | ${cell((cf || cs).expected)} | ${cell(mark(cf))} | ${cell(mark(cs))} |`);
      });
      const notes = [];
      runs.forEach(s => s.notes.forEach(n => notes.push(`(${MODES[s.mode]})${n}`)));
      const shots = [];
      runs.forEach(s => s.shots.forEach(x => shots.push(x)));
      if (notes.length) { L.push(''); notes.forEach(n => L.push(`- ${n}`)); }
      if (shots.length) L.push('', `截圖:${shots.map(x => `\`${x}\``).join('、')}`);
      L.push('');
    }
  }
  fs.writeFileSync(path.join(OUT, 'result.md'), L.join('\n'), 'utf8');
  console.log(`寫好 result.md;總步數 ${tot.n}:過 ${tot.pass}、不過 ${tot.fail}、無法自動 ${tot.na}、腳本錯誤 ${tot.error}`);
}

main().catch(err => { console.error(err); restoreActionData(); process.exitCode = 1; });
