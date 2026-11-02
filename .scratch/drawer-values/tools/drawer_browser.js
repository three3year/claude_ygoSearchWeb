// 真 Chrome(CDP,零 npm 依賴):開一張標籤的抽屜,逐顆點選值鈕,讀畫面上的結果數與抽屜張數,再按還原。
// 用法:node .scratch/drawer-values/tools/drawer_browser.js [標籤路徑,預設 破壊] > .scratch/drawer-values/tools/results/drawer_browser.txt
// 需要本機 Chrome(路徑寫在 CHROME);每列:欄=值、按後鈕是否亮、結果區文字、抽屜張數、抽屜是否開著、短句。
'use strict';
const { spawn } = require('child_process');
const http = require('http');
const os = require('os');
const path = require('path');
const fs = require('fs');

const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const PAGE = 'file:///F:/AiProject/claude_ygoSearchWeb/web/index.html';
const PORT = 9333;
const tagPath = process.argv[2] || '破壊';

const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'drawer-'));
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`,
  `--user-data-dir=${profile}`, '--window-size=1400,1000', 'about:blank'], { stdio: 'ignore' });

const sleep = ms => new Promise(r => setTimeout(r, ms));
const getJson = url => new Promise((res, rej) => {
  http.get(url, r => { let s = ''; r.on('data', d => { s += d; }); r.on('end', () => res(JSON.parse(s))); }).on('error', rej);
});

async function main() {
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
    if (r.result.exceptionDetails) throw new Error(JSON.stringify(r.result.exceptionDetails));
    return r.result.result.value;
  };
  await send('Runtime.enable');
  await send('Log.enable');
  await send('Page.enable');
  await send('Page.navigate', { url: PAGE });
  for (let i = 0; i < 100; i++) {
    await sleep(300);
    if (await ev(`typeof Hash !== 'undefined' && document.readyState === 'complete'`)) break;
  }
  const hash = await ev(`Hash.stringify({q:{},cond:Object.assign(Cond.empty(),{and:[Cond.tagAt(${JSON.stringify(tagPath)},false)]}),sort:{}})`);
  await ev(`location.hash=${JSON.stringify(hash)}`);
  await sleep(1500);
  await ev(`document.querySelector('#condStrip .strip-tag:not(.side)').click()`);
  await sleep(300);
  const read = `JSON.stringify({res:document.getElementById('resultInfo').textContent,
    note:(document.querySelector('.drawer-note span')||{}).textContent,
    cards:document.querySelectorAll('#results > *').length,
    open:!document.getElementById('condDrawer').hidden,
    name:(document.querySelector('.drawer-name')||{}).textContent})`;
  console.log('起始', await ev(read));
  const chips = JSON.parse(await ev(`JSON.stringify([...document.querySelectorAll('#condDrawer .drawer-chip')].map(c=>[c.closest('[data-field]').dataset.field,c.dataset.v,c.classList.contains('on')]))`));
  const chipSel = (f, v) => `document.querySelector('#condDrawer [data-field=${JSON.stringify(f)}] .drawer-chip[data-v=${JSON.stringify(v)}]')`;
  for (const [f, v] of chips) {
    await ev(`${chipSel(f, v)}.click()`);
    await sleep(30);
    const after = JSON.parse(await ev(read));
    const on = await ev(`${chipSel(f, v)}?${chipSel(f, v)}.classList.contains('on'):null`);
    console.log(`${f}=${v}`.padEnd(20), `on:${on}`, `| ${after.res} | 抽屜 ${after.note} | 開:${after.open} | ${after.name}`);
    await ev(`(document.querySelector('#condDrawer [data-act=restore]')||{click(){}}).click()`);
    await sleep(30);
  }
  console.log('還原', await ev(read));
  console.log('console 錯誤', errors);
  ws.close();
}

main().catch(e => { console.error(e); }).finally(() => { chrome.kill(); });
