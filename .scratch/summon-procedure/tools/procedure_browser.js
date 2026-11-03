// 真 Chrome(CDP,零 npm 依賴)走召喚手續的使用者入口(summon-procedure 票 06,規格 Testing Decisions 的真瀏覽器一條):
// 從目錄加「除外」→ 新標籤位置只亮效果 → 抽屜按亮召喚手續,毀滅的黑魔術師(59400890)在結果、命中句是召喚條件那句、
// 句尾標「召喚手續:」→ 關掉效果只留召喚手續,同上 → 貼網址重開(網址、條件列、張數、抽屜位置鈕、命中句不變)
// → 再從目錄加 リリース,新標籤仍只亮效果、原標籤不變。每個狀態量版面(頁面、條件列、抽屜的橫向溢出,
// 元素超出視埠、句尾標籤超出卡片;每種寬度先塞一個超寬塊自檢量得到),收 console 錯誤。給 main 的匯出目錄時,另用同一支 Chrome 開 main 與本分支的
// web/index.html 同一批舊網址,比張數、條件列與第一頁卡片。CDP 骨架與點擊同 .scratch/drawer-lock/tools/drawer_browser.js。
// 用法:node .scratch/summon-procedure/tools/procedure_browser.js [desktop|phone|both,預設 both] [main 的匯出目錄]
// 結果寫 tools/results/procedure_browser.txt(也印 stdout)與每種寬度兩張 png(Page.captureScreenshot);有違規時 exit 1。
'use strict';
const { spawn } = require('child_process');
const http = require('http');
const os = require('os');
const path = require('path');
const fs = require('fs');

const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const fileUrl = root => 'file:///' + path.resolve(root, 'web', 'index.html').replace(/\\/g, '/');
const PAGE = fileUrl(path.resolve(__dirname, '..', '..', '..'));
const RESULTS = path.join(__dirname, 'results');
const OUT = path.join(RESULTS, 'procedure_browser.txt');
const PORT = 9335;
const WIDTHS = {
  desktop: { width: 1400, height: 1000, deviceScaleFactor: 1, mobile: false },
  phone: { width: 390, height: 844, deviceScaleFactor: 3, mobile: true },
};
const FILTER_TOGGLE = '#btnFilters';
const LEMMA = '除外';
const SECOND = 'リリース';
const CARD = 59400890;
const PROCEDURE = '召喚手續';
const EFFECT = '效果';
const ONLY_PROCEDURE_HASH = '#act=' + ['詞元:除外', '位置:召喚手續', '極性:肯定~可能']
  .map(pair => pair.split(':').map(s => s.split('~').map(encodeURIComponent).join('~')).join(':')).join(';');
const OLD_URLS = [
  'act=' + ['詞元:破壊', '位置:代價~效果', '極性:肯定~可能', '動作對象:非此卡'].join(';'),
  'act=' + ['詞元:除外', '位置:效果~條件', '極性:肯定~可能'].join(';'),
  'act=' + ['詞元:リリース', '位置:代價~效果~條件', '極性:肯定~可能'].join(';'),
  'act=' + encodeURIComponent('區域移動›除外'),
];
const encodeOld = h => h.split(/([=;])/).map(part => (/^[=;]$/.test(part) || part.includes('%') ? part
  : part.split(':').map(s => s.split('~').map(encodeURIComponent).join('~')).join(':'))).join('');

const which = ['desktop', 'phone', 'both'].includes(process.argv[2]) ? process.argv[2] : 'both';
const mainRoot = process.argv.slice(2).find(a => !['desktop', 'phone', 'both'].includes(a));
const lines = [];
const log = (...a) => { const s = a.join(' '); lines.push(s); console.log(s); };
const problems = [];
const bad = s => { problems.push(s); log('  !! ' + s); };
const sleep = ms => new Promise(r => setTimeout(r, ms));
const getJson = url => new Promise((res, rej) => {
  http.get(url, r => { let s = ''; r.on('data', d => { s += d; }); r.on('end', () => res(JSON.parse(s))); }).on('error', rej);
});
const q = s => JSON.stringify(s);

const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'procedure-'));
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`,
  `--user-data-dir=${profile}`, '--window-size=1400,1000', 'about:blank'], { stdio: 'ignore' });

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
    if (d.method === 'Runtime.consoleAPICalled' && d.params.type === 'error') {
      errors.push(d.params.args.map(a => a.value || a.description).join(' '));
    }
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

function page({ send, ev }, phone) {
  const snap = async () => JSON.parse(await ev(`JSON.stringify({hash:location.hash,
    res:document.getElementById('resultInfo').textContent,
    strip:[...document.querySelectorAll('#condStrip .strip-tag')].map(t=>t.textContent.replace(/[×⇄]/g,'').replace(/\\s+/g,' ').trim()).join(' / '),
    name:(document.querySelector('.drawer-name')||{}).textContent||'',
    open:!document.getElementById('condDrawer').hidden})`));
  const count = s => { const m = /共 ([\d,]+) 張/.exec(s.res); return m ? +m[1].replace(/,/g, '') : 0; };
  const tap = async sel => {
    const at = JSON.parse(await ev(`(()=>{const el=document.querySelector(${q(sel)});if(!el)return 'null';
      el.scrollIntoView({block:'center'});const r=el.getBoundingClientRect();const x=r.left+r.width/2,y=r.top+r.height/2;
      const hit=document.elementFromPoint(x,y);return JSON.stringify({x,y,ok:!!hit&&(hit===el||el.contains(hit))});})()`));
    if (!at) throw new Error('找不到 ' + sel);
    if (!at.ok) bad(`點不到(被蓋住):${sel}`);
    if (phone) {
      await send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x: at.x, y: at.y }] });
      await send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
    } else {
      await send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: at.x, y: at.y });
      await send('Input.dispatchMouseEvent', { type: 'mousePressed', x: at.x, y: at.y, button: 'left', clickCount: 1 });
      await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: at.x, y: at.y, button: 'left', clickCount: 1 });
    }
  };
  const settle = async before => {
    for (let i = 0; i < 40; i++) {
      await sleep(25);
      const s = await snap();
      if (s.hash !== before) return s;
    }
    return snap();
  };
  const type = text => send('Input.insertText', { text });
  return { snap, count, tap, settle, type };
}

async function waitLoaded(ev) {
  for (let i = 0; i < 100; i++) {
    await sleep(200);
    if (await ev(`typeof Hash !== 'undefined' && document.readyState === 'complete'`)) break;
  }
  await sleep(300);
}

async function filterPanel(ctx) {
  return JSON.parse(await ctx.ev(`(()=>{const b=document.querySelector(${q(FILTER_TOGGLE)});
    return JSON.stringify({collapsible:b.offsetHeight>0,collapsed:b.getAttribute('aria-expanded')!=='true'});})()`));
}

async function setFilterPanel(ctx, p, open) {
  const panel = await filterPanel(ctx);
  if (panel.collapsible && panel.collapsed === open) await p.tap(FILTER_TOGGLE);
}

const catPick = key => `#catalogNav .cat-node[data-key=${q(key)}] > .cat-row > .cat-pick`;

async function addFromCatalog(ctx, p, name) {
  const { ev } = ctx;
  await setFilterPanel(ctx, p, true);
  await p.tap('#catalogNav .cat-filter');
  await p.type(name);
  await sleep(200);
  const key = await ev(`(()=>{const li=[...document.querySelectorAll('#catalogNav .cat-node')].find(li=>!li.hidden&&
    li.querySelector(':scope > .cat-row .cat-pick[data-path]')&&li.querySelector(':scope > .cat-row .cat-pick > span').textContent===${q(name)});
    return li?li.dataset.key:null;})()`);
  if (!key) { bad(`目錄找不到 ${name}`); return null; }
  const before = await p.snap();
  await p.tap(catPick(key));
  const s = await p.settle(before.hash);
  await ev(`(()=>{const i=document.querySelector('#catalogNav .cat-filter');i.value='';i.dispatchEvent(new Event('input',{bubbles:true}));})()`);
  await setFilterPanel(ctx, p, false);
  return { key, snap: s };
}

async function openDrawer(ctx, p, i) {
  await p.tap(`#condStrip .strip-tag[data-i="${i}"] .strip-lemma`);
  for (let k = 0; k < 20 && !(await p.snap()).open; k++) await sleep(50);
  return p.snap();
}

async function closeDrawer(ctx, p) {
  if (!(await p.snap()).open) return;
  await p.tap('#condDrawer [data-act=close]');
  for (let k = 0; k < 20 && (await p.snap()).open; k++) await sleep(50);
}

async function positionChips(ctx) {
  return JSON.parse(await ctx.ev(`JSON.stringify([...document.querySelectorAll('#condDrawer [data-field="位置"] .drawer-chip')]
    .map(c=>({v:c.dataset.v,on:c.classList.contains('on'),last:c.classList.contains('last'),dis:c.disabled,title:c.title})))`));
}

const chipText = chips => chips.map(c => (c.on ? '[' + c.v + (c.last ? '·最後一個' : '') + ']' : c.v)).join(' ');

function checkOnlyEffect(chips, label) {
  const on = chips.filter(c => c.on).map(c => c.v);
  const eff = chips.find(c => c.v === EFFECT);
  if (on.length !== 1 || on[0] !== EFFECT || !eff.last || !eff.dis) bad(`${label}:新標籤位置不是只亮效果(${chipText(chips)})`);
}

async function togglePosition(ctx, p, value) {
  const before = await p.snap();
  await p.tap(`#condDrawer [data-field="位置"] .drawer-chip[data-v=${q(value)}]`);
  return p.settle(before.hash);
}

async function layout(ctx, label) {
  const found = await measure(ctx);
  log(`  版面(${label}):${found.out.length ? found.out.length + ' 處' : '0 處'}`);
  found.out.forEach(s => bad(`版面(${label}):${s}`));
}

// 量法自檢:塞一個兩倍視埠寬的塊,量得到才算這把尺有用;量完拿掉。
async function probeLayout(ctx) {
  await ctx.ev(`(()=>{const d=document.createElement('div');d.id='layoutProbe';d.style.width=(2*innerWidth)+'px';d.style.height='4px';
    document.getElementById('results').appendChild(d);})()`);
  const found = await measure(ctx);
  await ctx.ev(`document.getElementById('layoutProbe').remove()`);
  log(`  量法自檢(塞一個兩倍視埠寬的塊):量到 ${found.out.length} 處`);
  if (!found.out.length) bad('量法自檢:塞了超寬的塊卻量不到違規');
}

async function measure(ctx) {
  return JSON.parse(await ctx.ev(`(()=>{const vw=document.documentElement.clientWidth;const out=[];
    const desc=el=>el.tagName.toLowerCase()+(el.id?'#'+el.id:'')+(el.className&&typeof el.className==='string'?'.'+el.className.trim().split(/\\s+/).join('.'):'');
    const doc=document.documentElement.scrollWidth-vw;if(doc>0)out.push('頁面橫向溢出 '+doc+'px');
    for(const id of ['condStrip','condDrawer','results']){const el=document.getElementById(id);
      if(el&&!el.hidden&&el.getClientRects().length){const d=el.scrollWidth-el.clientWidth;if(d>1)out.push('#'+id+' 橫向溢出 '+d+'px');}}
    const clipped=el=>{for(let a=el.parentElement;a&&a!==document.body;a=a.parentElement){
      if(getComputedStyle(a).overflowX!=='visible'){const r=a.getBoundingClientRect();return r.left>=-1&&r.right<=vw+1;}}return false;};
    let n=0;for(const el of document.body.querySelectorAll('*')){const r=el.getBoundingClientRect();
      if(!r.width||!r.height||getComputedStyle(el).visibility==='hidden')continue;
      if((r.right>vw+1||r.left<-1)&&!clipped(el)){if(n<8)out.push('超出視埠 '+desc(el)+' left '+r.left.toFixed(0)+' right '+r.right.toFixed(0)+'(視埠 '+vw+')');n++;}}
    if(n>8)out.push('超出視埠另 '+(n-8)+' 個');
    for(const t of document.querySelectorAll('#results .tail-tag')){const c=t.closest('article.card').getBoundingClientRect();
      const r=t.getBoundingClientRect();if(r.right>c.right+1||r.left<c.left-1)out.push('句尾標籤超出卡片 '+t.textContent);}
    return JSON.stringify({vw,out});})()`));
}

async function findCard(ctx, p) {
  const { ev } = ctx;
  const sel = `#results article.card[data-cid="${CARD}"]`;
  for (let k = 0; k < 80; k++) {
    if (await ev(`!!document.querySelector(${q(sel)})`)) return { page: k + 1, sel };
    const more = await ev(`(()=>{const b=document.querySelector('#pagerTop button:last-of-type');
      return !!b&&!b.classList.contains('cur')&&!!document.querySelector('#pagerTop button.cur')&&
        +b.dataset.p>+document.querySelector('#pagerTop button.cur').dataset.p;})()`);
    if (!more) return null;
    await p.tap('#pagerTop button:last-of-type');
    await sleep(150);
  }
  return null;
}

async function hitSentences(ctx, sel) {
  return JSON.parse(await ctx.ev(`JSON.stringify([...document.querySelectorAll(${q(sel + ' p.eff.hit')})].map(e=>({ei:+e.dataset.ei,
    cond:e.classList.contains('role-cond'),kinds:[...e.querySelectorAll('.eff-kind')].map(k=>k.textContent),
    tails:[...e.querySelectorAll('.tail-tag')].map(t=>t.textContent),text:e.textContent.slice(0,40)})))`));
}

async function checkCard(ctx, p, label, effectToo) {
  const at = await findCard(ctx, p);
  if (!at) { bad(`${label}:結果裡沒有 ${CARD}`); return null; }
  const hits = await hitSentences(ctx, at.sel);
  log(`  ${label}:${CARD} 在第 ${at.page} 頁;命中句 ${hits.map(h => `#${h.ei}${h.cond ? '(召喚條件)' : ''} 句尾「${h.tails.join('、')}」`).join(';')}`);
  const proc = hits.filter(h => h.cond && h.kinds.includes('召喚條件'));
  if (proc.length !== 1) bad(`${label}:命中句裡召喚條件那句 ${proc.length} 句`);
  else if (!proc[0].tails.some(t => t.startsWith(PROCEDURE + ':') && t.includes(LEMMA))) bad(`${label}:召喚條件那句的句尾沒有「${PROCEDURE}:${LEMMA}」(${proc[0].tails.join('、')})`);
  if (!effectToo && hits.length !== proc.length) bad(`${label}:只看召喚手續卻有召喚條件以外的命中句`);
  if (hits.some(h => !h.cond && h.tails.some(t => t.startsWith(PROCEDURE + ':')))) bad(`${label}:召喚條件以外的句標了召喚手續`);
  return { at, hits };
}

async function shot(ctx, file, sel) {
  if (sel) await ctx.ev(`document.querySelector(${q(sel)}).scrollIntoView({block:'center'})`);
  await sleep(200);
  const r = await ctx.send('Page.captureScreenshot', { format: 'png' });
  fs.writeFileSync(path.join(RESULTS, file), Buffer.from(r.result.data, 'base64'));
  log(`  截圖 ${file}`);
}

async function reopen(ctx, p, href) {
  await ctx.send('Page.navigate', { url: 'about:blank' });
  await sleep(300);
  await ctx.send('Page.navigate', { url: href });
  await waitLoaded(ctx.ev);
}

async function run(ctx, width) {
  const { send, ev, errors } = ctx;
  const phone = width === 'phone';
  await send('Emulation.setDeviceMetricsOverride', WIDTHS[width]);
  await send('Emulation.setTouchEmulationEnabled', { enabled: phone, maxTouchPoints: phone ? 5 : 1 });
  await send('Page.navigate', { url: PAGE });
  await waitLoaded(ev);
  const p = page(ctx, phone);
  const errorsBefore = errors.length;
  const started = Date.now();
  log(`\n==== ${width}(${WIDTHS[width].width}×${WIDTHS[width].height}${phone ? ',觸控' : ''})====`);
  await probeLayout(ctx);
  await layout(ctx, '首頁');

  log(`\n-- 從目錄加 ${LEMMA}`);
  const added = await addFromCatalog(ctx, p, LEMMA);
  if (!added) return;
  const leaf = '#act=' + encodeURIComponent(added.key);
  log(`  目錄列 ${added.key};網址 ${decodeURIComponent(added.snap.hash)};${added.snap.res};條件列「${added.snap.strip}」`);
  if (added.snap.hash !== leaf) bad(`加 ${LEMMA}:網址不是只寫葉路徑 ${decodeURIComponent(added.snap.hash)}`);
  const effectOnly = p.count(added.snap);
  let s = await openDrawer(ctx, p, 0);
  let chips = await positionChips(ctx);
  log(`  抽屜位置欄:${chipText(chips)}`);
  const positions = JSON.parse(await ev('JSON.stringify(VOCAB.frame.domains.位置)'));
  if (chips.map(c => c.v).join() !== positions.join()) bad(`位置鈕不是值域的 ${positions.length} 顆 ${positions.join('、')}`);
  checkOnlyEffect(chips, `${LEMMA} 新標籤`);
  await layout(ctx, '抽屜打開');

  log(`\n-- 按亮 ${PROCEDURE}`);
  s = await togglePosition(ctx, p, PROCEDURE);
  chips = await positionChips(ctx);
  log(`  位置欄:${chipText(chips)};${s.res};條件列「${s.strip}」;網址 ${decodeURIComponent(s.hash)}`);
  if (!chips.find(c => c.v === PROCEDURE).on || !chips.find(c => c.v === EFFECT).on) bad(`按亮 ${PROCEDURE}:效果與召喚手續沒有都亮`);
  if (!s.strip.includes(`${EFFECT}或${PROCEDURE}位 ${LEMMA}`)) bad(`按亮 ${PROCEDURE}:條件列短句不對「${s.strip}」`);
  if (p.count(s) <= effectOnly) bad(`按亮 ${PROCEDURE}:張數沒有變多(${effectOnly} → ${p.count(s)})`);
  await layout(ctx, `抽屜 效果+${PROCEDURE}`);
  await closeDrawer(ctx, p);
  await checkCard(ctx, p, `效果+${PROCEDURE}`, true);
  await layout(ctx, `結果 效果+${PROCEDURE}`);

  log(`\n-- 關掉 ${EFFECT},只留 ${PROCEDURE}`);
  await ev(`window.scrollTo(0,0)`);
  await openDrawer(ctx, p, 0);
  s = await togglePosition(ctx, p, EFFECT);
  chips = await positionChips(ctx);
  log(`  位置欄:${chipText(chips)};${s.res};條件列「${s.strip}」;網址 ${decodeURIComponent(s.hash)}`);
  const procChip = chips.find(c => c.v === PROCEDURE);
  if (chips.filter(c => c.on).length !== 1 || !procChip.on || !procChip.last) bad(`只留 ${PROCEDURE}:位置欄不對(${chipText(chips)})`);
  if (s.hash !== ONLY_PROCEDURE_HASH) bad(`只留 ${PROCEDURE}:網址 ${decodeURIComponent(s.hash)} ≠ ${decodeURIComponent(ONLY_PROCEDURE_HASH)}`);
  if (!s.strip.includes(`${PROCEDURE}位 ${LEMMA}`) || s.strip.includes(EFFECT)) bad(`只留 ${PROCEDURE}:條件列短句不對「${s.strip}」`);
  await shot(ctx, `procedure_${width}_drawer.png`, '#condDrawer');
  await layout(ctx, `抽屜 只${PROCEDURE}`);
  await closeDrawer(ctx, p);
  const only = await checkCard(ctx, p, `只${PROCEDURE}`, false);
  if (only) await shot(ctx, `procedure_${width}_card.png`, `${only.at.sel} p.eff.hit.role-cond`);
  await layout(ctx, `結果 只${PROCEDURE}`);

  log(`\n-- 貼網址重開`);
  const was = Object.assign(await p.snap(), { href: await ev('location.href'), hits: only && only.hits });
  await reopen(ctx, p, was.href);
  const now = Object.assign(await p.snap(), { href: await ev('location.href') });
  log(`  ${now.res};條件列「${now.strip}」`);
  if (now.href !== was.href || now.strip !== was.strip || now.res !== was.res) {
    bad(`貼網址重開不同:${JSON.stringify({ href: decodeURIComponent(was.href), strip: was.strip, res: was.res })} → `
      + JSON.stringify({ href: decodeURIComponent(now.href), strip: now.strip, res: now.res }));
  }
  const again = await checkCard(ctx, p, '重開後', false);
  if (again && JSON.stringify(again.hits) !== JSON.stringify(was.hits)) bad('貼網址重開:命中句或句尾不同');
  await ev(`window.scrollTo(0,0)`);
  await openDrawer(ctx, p, 0);
  const reChips = await positionChips(ctx);
  log(`  重開後位置欄:${chipText(reChips)}`);
  if (chipText(reChips) !== chipText(chips)) bad(`貼網址重開:位置欄 ${chipText(chips)} → ${chipText(reChips)}`);
  await closeDrawer(ctx, p);
  await layout(ctx, '重開後');

  log(`\n-- 再從目錄加 ${SECOND}`);
  await ev(`window.scrollTo(0,0)`);
  const second = await addFromCatalog(ctx, p, SECOND);
  if (second) {
    log(`  ${second.snap.res};條件列「${second.snap.strip}」`);
    if (!second.snap.strip.startsWith(`${PROCEDURE}位 ${LEMMA}`)) bad(`加 ${SECOND} 後原標籤變了「${second.snap.strip}」`);
    await openDrawer(ctx, p, 1);
    const c2 = await positionChips(ctx);
    log(`  ${SECOND} 抽屜位置欄:${chipText(c2)}`);
    checkOnlyEffect(c2, `${SECOND} 新標籤`);
    await layout(ctx, `加 ${SECOND}`);
    await closeDrawer(ctx, p);
  }
  log(`\n  console 錯誤 ${errors.length - errorsBefore}${errors.length > errorsBefore ? ':' + errors.slice(errorsBefore).join(' | ') : ''}`);
  log(`  共 ${((Date.now() - started) / 1000).toFixed(0)} 秒`);
  if (errors.length > errorsBefore) bad(`${width}:console 有錯`);
}

async function firstPage(ctx, href) {
  await reopen(ctx, null, href);
  return JSON.parse(await ctx.ev(`JSON.stringify({res:document.getElementById('resultInfo').textContent,
    strip:[...document.querySelectorAll('#condStrip .strip-tag')].map(t=>t.textContent.replace(/[×⇄]/g,'').replace(/\\s+/g,' ').trim()).join(' / '),
    cards:[...document.querySelectorAll('#results article.card')].map(a=>a.dataset.cid).join(',')})`));
}

async function oldUrls(ctx) {
  const mainPage = fileUrl(path.resolve(mainRoot));
  log(`\n==== 舊網址:main(${mainPage})與本分支同一網址,桌面寬 ====`);
  await ctx.send('Emulation.setDeviceMetricsOverride', WIDTHS.desktop);
  await ctx.send('Emulation.setTouchEmulationEnabled', { enabled: false, maxTouchPoints: 1 });
  const errorsBefore = ctx.errors.length;
  for (const raw of OLD_URLS) {
    const hash = '#' + encodeOld(raw);
    const a = await firstPage(ctx, mainPage + hash);
    const b = await firstPage(ctx, PAGE + hash);
    const same = a.res === b.res && a.strip === b.strip && a.cards === b.cards;
    log(`  ${decodeURIComponent(hash)}:main ${a.res}「${a.strip}」;分支 ${b.res}「${b.strip}」;第一頁卡片${a.cards === b.cards ? '相同' : '不同'}`);
    if (!same) bad(`舊網址 ${decodeURIComponent(hash)}:main 與本分支不同`);
  }
  log(`  console 錯誤 ${ctx.errors.length - errorsBefore}`);
  if (ctx.errors.length > errorsBefore) bad('舊網址:console 有錯');
}

async function main() {
  const ctx = await connect();
  log(`頁面 ${PAGE}`);
  for (const width of which === 'both' ? ['desktop', 'phone'] : [which]) await run(ctx, width);
  if (mainRoot) await oldUrls(ctx);
  log(`\n違規 ${problems.length}${problems.length ? ':\n' + problems.join('\n') : ''}`);
  ctx.ws.close();
}

main().catch(e => { console.error(e); problems.push(String(e)); })
  .finally(() => {
    chrome.kill();
    fs.writeFileSync(OUT, lines.join('\n') + '\n');
    process.exitCode = problems.length ? 1 : 0;
  });
