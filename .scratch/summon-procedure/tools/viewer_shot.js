// 真 Chrome(CDP,零 npm 依賴)開拆解頁截圖(summon-procedure 票 04):
// 卡片拆解打 59400890(滅びの黒魔術師),截召喚條件句(效果外文本 0-2)那一塊(原文加框架表,2560 寬),斷言有一列類別是召喚手續的 除外、
// 樣式是 f-proc(不落到效果的 f-eff);再開具名查詢總覽,斷言表頭位置欄照 POSITIONS 排(召喚手續最後)、
// 目錄樹每列的格數 = 名 + 位置數 + 合計 + 長條、合計格不是召喚手續那一格。CDP 骨架同 .scratch/drawer-lock/tools/drawer_browser.js。
// 用法:node .scratch/summon-procedure/tools/viewer_shot.js(先跑 report.py、prepare_view.py 產 view_*.js)
// 結果寫 tools/results/viewer_shot.txt 與兩張 png;有違規 exit 1。
'use strict';
const { spawn } = require('child_process');
const http = require('http');
const os = require('os');
const path = require('path');
const fs = require('fs');

const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const ET = path.resolve(__dirname, '..', '..', 'effect-tokenize');
const PAGE = 'file:///' + path.join(ET, 'viewer.html').replace(/\\/g, '/');
const RESULTS = path.join(__dirname, 'results');
const PORT = 9334;
const CARD = 59400890;
const PROCEDURE = '召喚手續';

const lines = [];
const log = (...a) => { const s = a.join(' '); lines.push(s); console.log(s); };
const problems = [];
const bad = s => { problems.push(s); log('  !! ' + s); };
const sleep = ms => new Promise(r => setTimeout(r, ms));
const getJson = url => new Promise((res, rej) => {
  http.get(url, r => { let s = ''; r.on('data', d => { s += d; }); r.on('end', () => res(JSON.parse(s))); }).on('error', rej);
});

const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'viewer-'));
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, `--user-data-dir=${profile}`,
  '--window-size=1400,1000', '--allow-file-access-from-files', 'about:blank'], { stdio: 'ignore' });

async function connect() {
  let targets;
  for (let i = 0; i < 50 && !targets; i++) {
    try { targets = await getJson(`http://127.0.0.1:${PORT}/json`); } catch (e) { await sleep(200); }
  }
  const ws = new WebSocket(targets.find(t => t.type === 'page').webSocketDebuggerUrl);
  await new Promise(r => { ws.onopen = r; });
  let id = 0;
  const waiting = new Map();
  const errors = [];
  ws.onmessage = m => {
    const d = JSON.parse(m.data);
    if (d.id) { waiting.get(d.id)(d); waiting.delete(d.id); }
    if (d.method === 'Runtime.exceptionThrown') errors.push(d.params.exceptionDetails.exception.description);
    if (d.method === 'Log.entryAdded' && d.params.entry.level === 'error') errors.push(d.params.entry.text);
  };
  const send = (method, params) => new Promise(r => {
    const n = ++id;
    waiting.set(n, r);
    ws.send(JSON.stringify({ id: n, method, params }));
  });
  const ev = async code => {
    const r = await send('Runtime.evaluate', { expression: code, returnByValue: true, awaitPromise: true });
    if (r.result.exceptionDetails) throw new Error(code.slice(0, 200) + ' → ' + JSON.stringify(r.result.exceptionDetails));
    return r.result.result.value;
  };
  await send('Runtime.enable');
  await send('Log.enable');
  await send('Page.enable');
  return { ws, send, ev, errors };
}

async function waitFor(ev, code, what) {
  for (let i = 0; i < 200; i++) {
    if (await ev(code)) return;
    await sleep(100);
  }
  throw new Error('等不到 ' + what);
}

async function shot(send, ev, selector, file) {
  const rect = JSON.parse(await ev(`(()=>{const el=document.querySelector(${JSON.stringify(selector)});
    el.scrollIntoView({block:'start'});const r=el.getBoundingClientRect();
    return JSON.stringify({x:r.left+scrollX,y:r.top+scrollY,w:r.width,h:Math.min(r.height,1800)});})()`));
  const r = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true,
    clip: { x: rect.x, y: rect.y, width: rect.w, height: rect.h, scale: 1 } });
  fs.writeFileSync(path.join(RESULTS, file), Buffer.from(r.result.data, 'base64'));
  log('截圖 ' + path.join(RESULTS, file));
}

(async () => {
  const { ws, send, ev, errors } = await connect();
  // 拆解頁框架表欄多,寬螢幕才看得到整列(窄了內容欄會擠成直排)
  await send('Emulation.setDeviceMetricsOverride', { width: 2560, height: 1400, deviceScaleFactor: 1, mobile: false });
  log('頁面 ' + PAGE);
  await send('Page.navigate', { url: PAGE });
  await waitFor(ev, `!!document.querySelector('input[type=search]')`, '卡片拆解分頁');

  // 卡片拆解:打卡號(純數字且相符時直接開卡)
  await ev(`(()=>{const i=document.querySelector('input[type=search]');i.value='${CARD}';
    i.dispatchEvent(new Event('input',{bubbles:true}));})()`);
  await waitFor(ev, `!!document.querySelector('table.frames')`, '框架表');
  await sleep(300);
  const blocks = JSON.parse(await ev(`JSON.stringify([...document.querySelectorAll('table.frames')].map(t=>{
    const box=t.closest('.sent-block,section,div');return {head:(box.textContent||'').slice(0,40),
    rows:[...t.querySelectorAll('tbody tr:not(.clause)')].map(tr=>[...tr.children].slice(0,3).map(td=>td.textContent.trim()).join(' | ')),
    proc:[...t.querySelectorAll('.chip.f-proc')].map(c=>c.closest('tr').textContent.replace(/\\s+/g,' ').slice(0,80))};}))`));
  const withProc = blocks.filter(b => b.proc.length);
  log(`卡 ${CARD}:框架表 ${blocks.length} 張,帶召喚手續 chip 的 ${withProc.length} 張`);
  withProc.forEach(b => b.proc.forEach(p => log('  召喚手續列:' + p)));
  if (!withProc.some(b => b.proc.some(p => p.includes('除外')))) bad('召喚條件句沒有 除外 的召喚手續框');
  const effLabelled = Number(await ev(`[...document.querySelectorAll('table.frames .chip.f-eff')].filter(c=>c.textContent.trim()===${JSON.stringify(PROCEDURE)}).length`));
  if (effLabelled) bad(`召喚手續 chip 落到效果樣式 ${effLabelled} 顆`);
  const colors = JSON.parse(await ev(`JSON.stringify(['f-cost','f-eff','f-cond','f-proc'].map(c=>{
    const s=document.createElement('span');s.className='chip '+c;document.body.appendChild(s);
    const v=getComputedStyle(s).backgroundColor;s.remove();return [c,v];}))`));
  log('chip 底色:' + colors.map(c => c.join(' ')).join('、'));
  if (new Set(colors.map(c => c[1])).size !== colors.length) bad('位置 chip 底色有重複');
  await ev(`(()=>{const c=document.querySelector('table.frames .chip.f-proc');c.closest('.rec').setAttribute('id','procShot');})()`);
  // 頁面 .wrap 限寬 1060px,框架表 17 欄擠成直排;截圖時(只在這支工具裡)放開限寬,讓整列一行看得到
  await ev(`(()=>{const st=document.createElement('style');st.textContent='.wrap{max-width:none}';document.head.appendChild(st);})()`);
  await sleep(200);
  await shot(send, ev, '#procShot', `viewer_${CARD}_procedure.png`);
  const legend = await ev(`document.querySelector('.legend').textContent.replace(/\\s+/g,' ').trim()`);
  log('圖例:' + legend.slice(0, 60));
  if (!legend.includes(PROCEDURE)) bad('圖例沒有召喚手續');

  // 具名查詢總覽
  await ev(`[...document.querySelectorAll('#tabs button')].find(b=>/具名查詢/.test(b.textContent)).click()`);
  await waitFor(ev, `!!document.querySelector('.ctree .chead')`, '具名查詢總覽');
  await sleep(300);
  const head = JSON.parse(await ev(`JSON.stringify([...document.querySelectorAll('.ctree .chead span')].map(s=>s.textContent))`));
  log('總覽表頭:' + head.join(' | '));
  if (head[head.length - 3] !== PROCEDURE) bad('總覽位置欄的最後一個不是召喚手續:' + head.join(','));
  const tree = JSON.parse(await ev(`(()=>{const s=document.querySelector('.ctree details>summary');
    const cells=[...s.children];const top=cells.filter(c=>!c.classList.contains('cbarw')).map(c=>c.getBoundingClientRect().top);
    return JSON.stringify({n:cells.length,oneLine:Math.max(...top)-Math.min(...top)<4,
      text:cells.map(c=>c.textContent).join(' | ')});})()`));
  log(`目錄第一列 ${tree.n} 格、同一行 ${tree.oneLine}:${tree.text}`);
  if (tree.n !== head.length) bad(`目錄列格數 ${tree.n} ≠ 表頭 ${head.length}`);
  if (!tree.oneLine) bad('目錄列換行(grid 欄數不夠)');
  await ev(`document.querySelector('.ctree').setAttribute('id','treeShot')`);
  await shot(send, ev, '#treeShot', 'viewer_overview_tree.png');

  log('console 錯誤 ' + errors.length + (errors.length ? ':' + errors.join(' / ') : ''));
  errors.forEach(e => bad('console:' + e));
  log('違規 ' + problems.length);
  fs.writeFileSync(path.join(RESULTS, 'viewer_shot.txt'), lines.join('\n') + '\n');
  ws.close();
  chrome.kill();
  process.exit(problems.length ? 1 : 0);
})().catch(e => { console.error(e); chrome.kill(); process.exit(2); });
