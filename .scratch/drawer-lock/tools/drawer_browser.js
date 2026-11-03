// 真 Chrome(CDP,零 npm 依賴)走抽屜:依畫面逐顆點可按的鈕,斷言每顆都有結果、灰與鎖住的按了標籤不變。
// drawer-lock 票 04 從 drawer-values 的同名工具(票 05)複製,加:目錄點帶子的詞元節點只展開、最後一列加標籤與排除、
// 過濾框;從目錄點具名查詢和網址開的是同一張標籤;鎖住的欄只留一行(按不掉、不帶 ×、沒有選單與輸入框、
// 說明「由 X 決定」、和目錄列述詞相同);貼網址重開仍鎖、只改位置重開仍鎖、另加一欄重開不鎖(規格使用者故事 22、23、26)。
// 用法:node .scratch/drawer-lock/tools/drawer_browser.js [desktop|phone|both,預設 both] [具名查詢名…]
// 結果寫進 tools/results/drawer_browser.txt(也印到 stdout);有違規時 exit 1。需要本機 Chrome(路徑寫在 CHROME)。
// 點擊走 CDP 的真輸入:桌面滑鼠、手機觸控 tap;選單(玩家、區域)原生彈窗開不了,改設 value 再發 change;
'use strict';
const { spawn } = require('child_process');
const http = require('http');
const os = require('os');
const path = require('path');
const fs = require('fs');

const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const PAGE = 'file:///' + path.resolve(__dirname, '..', '..', '..', 'web', 'index.html').replace(/\\/g, '/');
const OUT = path.join(__dirname, 'results', 'drawer_browser.txt');
const PORT = 9333;
const WIDTHS = {
  desktop: { width: 1400, height: 1000, deviceScaleFactor: 1, mobile: false },
  phone: { width: 390, height: 844, deviceScaleFactor: 3, mobile: true },
};
const DEFAULT_TAGS = ['破壊', '破壊@相手フィールド', '特殊召喚←墓地', '破壊:モンスター', '破壊(耐性)'];
const CATALOG_LEMMA = '破壊';
const LOCK_HINT = name => `由 ${name} 決定`;
const OUTSIDE_WORD = '存在しない語';

const which = process.argv[2] || 'both';
const tagNames = process.argv.length > 3 ? process.argv.slice(3) : DEFAULT_TAGS;
const lines = [];
const log = (...a) => { const s = a.join(' '); lines.push(s); console.log(s); };
const problems = [];
const bad = s => { problems.push(s); log('  !! ' + s); };

const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'drawer-'));
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`,
  `--user-data-dir=${profile}`, '--window-size=1400,1000', 'about:blank'], { stdio: 'ignore' });

const sleep = ms => new Promise(r => setTimeout(r, ms));
const getJson = url => new Promise((res, rej) => {
  http.get(url, r => { let s = ''; r.on('data', d => { s += d; }); r.on('end', () => res(JSON.parse(s))); }).on('error', rej);
});
const median = xs => { const s = xs.slice().sort((a, b) => a - b); return s[Math.floor(s.length / 2)]; };
const q = s => JSON.stringify(s);

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
    note:(document.querySelector('.drawer-note span')||{}).textContent||'',
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
  const settle = async (before, expectChange) => {
    for (let i = 0; i < (expectChange ? 40 : 1); i++) {
      await sleep(expectChange ? 15 : (phone ? 150 : 40));
      const s = await snap();
      if (!expectChange || s.hash !== before) return s;
    }
    return snap();
  };
  const choose = (field, sel, value) => ev(`(()=>{const s=document.querySelector('#condDrawer [data-field=${q(field)}] ${sel}');
    s.value=${q(value)};s.dispatchEvent(new Event('change',{bubbles:true}));})()`);
  const enter = async () => {
    const key = { key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13, nativeVirtualKeyCode: 13 };
    await send('Input.dispatchKeyEvent', Object.assign({ type: 'keyDown', text: '\r' }, key));
    await send('Input.dispatchKeyEvent', Object.assign({ type: 'keyUp' }, key));
  };
  const type = text => send('Input.insertText', { text });
  return { snap, count, tap, settle, choose, enter, type };
}

async function openTag(ctx, p, name) {
  const { ev } = ctx;
  const hash = await ev(`(()=>{const row=VOCAB.catalog.find(r=>r.predicate&&r.name===${q(name)});
    return Hash.stringify({q:{},cond:Object.assign(Cond.empty(),{and:[Cond.tagAt(row.path.join(Cond.SEP),false)]}),sort:{}});})()`);
  await ev(`location.hash=${q(hash)}`);
  await sleep(300);
  await p.tap('#condStrip .strip-tag:not(.side) .strip-lemma');
  for (let i = 0; i < 20 && !(await p.snap()).open; i++) await sleep(50);
  return p.snap();
}

async function restore(ctx, p, base, label) {
  let s = await p.snap();
  if (s.hash === base.hash) return;
  await p.tap('#condDrawer [data-act=restore]');
  s = await p.settle(s.hash, true);
  if (s.hash !== base.hash) {
    bad(`${label}:還原後網址不是原樣 ${decodeURIComponent(s.hash)}`);
    await openTag(ctx, p, base.tagName);
  }
}

async function sweepChips(ctx, p, base) {
  const { ev } = ctx;
  const chips = JSON.parse(await ev(`JSON.stringify([...document.querySelectorAll('#condDrawer .drawer-chip')].map(c=>({
    f:c.closest('[data-field]').dataset.field,v:c.dataset.v,on:c.classList.contains('on'),dis:c.disabled,title:c.title,
    act:c.hasAttribute('data-act')})))`));
  const tally = { 可按: 0, 亮: 0, 灰: 0, 鎖住: 0, 鎖住的欄: 0, 亮關掉0張: 0 };
  for (const c of chips) {
    const sel = `#condDrawer [data-field=${q(c.f)}] .drawer-chip[data-v=${q(c.v)}]`;
    const kind = c.dis ? (c.on ? (c.act ? '鎖住' : '鎖住的欄') : '灰') : (c.on ? '亮' : '可按');
    tally[kind]++;
    const before = await p.snap();
    await p.tap(sel);
    const s = await p.settle(before.hash, !c.dis);
    const n = p.count(s);
    if (!s.open) bad(`${c.f}=${c.v}:按了抽屜關了`);
    if (c.dis) {
      const still = await ev(`(()=>{const el=document.querySelector(${q(sel)});return el?el.classList.contains('on'):null;})()`);
      if (s.hash !== before.hash || still !== c.on) bad(`${c.f}=${c.v}(${kind}):按了標籤變了`);
      const want = { 灰: '目前條件下沒有結果', 鎖住: '至少要留一個', 鎖住的欄: LOCK_HINT(base.tagName) }[kind];
      if (c.title !== want) bad(`${c.f}=${c.v}(${kind}):提示是「${c.title}」`);
    } else {
      if (s.hash === before.hash) bad(`${c.f}=${c.v}(${kind}):按了沒反應`);
      if (kind === '可按' && n === 0) bad(`${c.f}=${c.v}:可按但 0 張`);
      if (kind === '亮' && n === 0) tally.亮關掉0張++;
    }
    log(`  ${kind} ${c.f}=${c.v}`.padEnd(28), c.dis ? '標籤不變' : `${n.toLocaleString()} 張 | ${s.name}`);
    await restore(ctx, p, base, `${c.f}=${c.v}`);
  }
  return tally;
}

async function regionMenus(ctx) {
  return JSON.parse(await ctx.ev(`JSON.stringify([...document.querySelectorAll('#condDrawer [data-field]')]
    .filter(b=>b.querySelector('[data-act=add-region]')).map(b=>({f:b.dataset.field,
    player:b.querySelector('[data-act=pick-player]').value,
    players:[...b.querySelectorAll('[data-act=pick-player] option')].map(o=>({v:o.value,dis:o.disabled})),
    zones:[...b.querySelectorAll('[data-act=add-region] option')].slice(1).map(o=>({v:o.value,dis:o.disabled}))})))`));
}

async function sweepRegions(ctx, p, base) {
  const tally = { 區域: 0, 灰區域: 0, 灰玩家: 0 };
  for (const menu of await regionMenus(ctx)) {
    log(`  ${menu.f} 玩家 ${menu.players.map(o => (o.dis ? '~' : '') + (o.v || '不限')).join(' ')}`);
    for (const player of menu.players) {
      if (player.dis) { tally.灰玩家++; continue; }
      await p.choose(menu.f, '[data-act=pick-player]', player.v);
      const now = (await regionMenus(ctx)).find(m => m.f === menu.f);
      if (now.player !== player.v) bad(`${menu.f}:換玩家 ${player.v} 後選單是 ${now.player}`);
      log(`    ${player.v || '不限'}:${now.zones.map(o => (o.dis ? '~' : '') + o.v).join(' ')}`);
      for (const zone of now.zones) {
        if (zone.dis) { tally.灰區域++; continue; }
        tally.區域++;
        const before = await p.snap();
        await p.choose(menu.f, '[data-act=add-region]', zone.v);
        const s = await p.settle(before.hash, true);
        const n = p.count(s);
        if (n === 0) bad(`${menu.f}=${player.v || '不限'}・${zone.v}:可選但 0 張`);
        log(`      ${zone.v} → ${n.toLocaleString()} 張 | ${s.name}`);
        const kept = (await regionMenus(ctx)).find(m => m.f === menu.f);
        if (kept.player !== player.v) bad(`${menu.f}:加入區域重畫後玩家變成 ${kept.player}`);
        await restore(ctx, p, base, `${menu.f}=${zone.v}`);
        await p.choose(menu.f, '[data-act=pick-player]', player.v);
      }
    }
    await p.choose(menu.f, '[data-act=pick-player]', '');
  }
  return tally;
}

async function sweepHeads(ctx, p, base) {
  const { ev } = ctx;
  const fields = JSON.parse(await ev(`JSON.stringify([...document.querySelectorAll('#condDrawer [data-act=add-text]')]
    .map(i=>({f:i.closest('[data-field]').dataset.field,cands:[...i.list.options].map(o=>o.value)})))`));
  const tally = { 候選: 0, 清單外: 0 };
  for (const { f, cands } of fields) {
    const input = `#condDrawer [data-field=${q(f)}] input`;
    let zero = 0, min = Infinity;
    for (const w of cands) {
      tally.候選++;
      const before = await p.snap();
      await p.tap(input);
      await p.type(w);
      await p.enter();
      const s = await p.settle(before.hash, true);
      const n = p.count(s);
      min = Math.min(min, n);
      if (n === 0) { zero++; bad(`${f}=${w}:候選但 0 張`); }
      await restore(ctx, p, base, `${f}=${w}`);
    }
    log(`  ${f} 候選 ${cands.length} 個逐一挑:0 張 ${zero} 個,最少 ${min === Infinity ? '-' : min} 張`);
    for (const how of ['Enter', '離開框']) {
      tally.清單外++;
      const before = await p.snap();
      await p.tap(input);
      await p.type(OUTSIDE_WORD);
      if (how === 'Enter') await p.enter();
      else await p.tap(`#condDrawer [data-field=${q(f)}] .drawer-label`);
      const s = await p.settle(before.hash, false);
      const left = await ev(`document.querySelector(${q(input)}).value`);
      if (s.hash !== before.hash || left) bad(`${f}:清單外的字 ${how} 後標籤變了或框沒清(框「${left}」)`);
      log(`  ${f} 清單外的字 ${how}:標籤${s.hash === before.hash ? '不變' : '變了'},框「${left}」`);
    }
  }
  return tally;
}

async function negationScenario(ctx, p, base) {
  const { ev } = ctx;
  const neg = () => ev(`JSON.stringify([...document.querySelectorAll('#condDrawer [data-field="否定形"] .drawer-chip')].map(c=>(c.disabled?'~':'')+c.dataset.v))`);
  const before = await neg();
  await p.tap(`#condDrawer [data-field="極性"] .drawer-chip[data-v="否定"]`);
  await p.settle(base.hash, true);
  const after = JSON.parse(await neg());
  log(`  否定形 預設極性 ${before} → 加極性否定 ${JSON.stringify(after)}`);
  const open = after.find(v => !v.startsWith('~'));
  if (!open || !JSON.parse(before).every(v => v.startsWith('~'))) bad('否定形:預設極性下不是全灰,或加否定後沒有可按的');
  if (open) {
    const s0 = await p.snap();
    await p.tap(`#condDrawer [data-field="否定形"] .drawer-chip[data-v=${q(open)}]`);
    const s = await p.settle(s0.hash, true);
    log(`  按 否定形=${open} → ${p.count(s).toLocaleString()} 張 | ${s.name}`);
    if (!p.count(s)) bad(`否定形=${open}:0 張`);
  }
  await restore(ctx, p, base, '否定形');
}

async function typedThenChip(ctx, p, base) {
  const { ev } = ctx;
  const pick = JSON.parse(await ev(`(()=>{const i=document.querySelector('#condDrawer [data-act=add-text]');
    const c=document.querySelector('#condDrawer .drawer-chip:not(.on):not(:disabled)');
    return JSON.stringify(i&&c&&{f:i.closest('[data-field]').dataset.field,w:i.list.options[0]&&i.list.options[0].value,
      cf:c.closest('[data-field]').dataset.field,cv:c.dataset.v});})()`));
  if (!pick || !pick.w) return;
  await p.tap(`#condDrawer [data-field=${q(pick.f)}] input`);
  await p.type(pick.w);
  await p.tap(`#condDrawer [data-field=${q(pick.cf)}] .drawer-chip[data-v=${q(pick.cv)}]`);
  await p.settle(base.hash, true);
  await sleep(100);
  const s2 = await p.snap();
  const grayNow = await ev(`(()=>{const c=document.querySelector(${q(`#condDrawer [data-field=${q(pick.cf)}] .drawer-chip[data-v=${q(pick.cv)}]`)});return !!c&&c.disabled&&!c.classList.contains('on');})()`);
  const hasWord = s2.name.indexOf(pick.w) >= 0;
  const hasChip = s2.name.indexOf(pick.cv.split(':').pop()) >= 0;
  log(`  框裡打 ${pick.w} 直接按 ${pick.cf}=${pick.cv}${grayNow ? '(收字後變灰)' : ''} → ${p.count(s2).toLocaleString()} 張 | ${s2.name}`);
  if (!hasWord || hasChip === grayNow) bad(`框裡有字直接按鈕:字要收進來,鈕照收字後的狀態生效(${s2.name})`);
  await restore(ctx, p, base, '打字後按鈕');
}

/* 鎖住的欄:抽屜裡帶沒有 data-act 的鈕的欄(鎖住那一行的鈕不能切換)。 */
async function lockedRows(ctx) {
  return JSON.parse(await ctx.ev(`JSON.stringify([...document.querySelectorAll('#condDrawer [data-field]')]
    .filter(b=>b.querySelector('.drawer-chip:not([data-act])')).map(b=>({f:b.dataset.field,
    items:[...b.querySelectorAll('.drawer-chip')].map(c=>({v:c.dataset.v,text:c.textContent,dis:c.disabled,
      locked:c.classList.contains('on')&&c.classList.contains('locked'),title:c.title,act:c.hasAttribute('data-act')})),
    menus:b.querySelectorAll('select').length,inputs:b.querySelectorAll('input,datalist').length,
    xs:b.querySelectorAll('.strip-x,[data-act=drop]').length})))`));
}

const lockedSummary = rows => rows.map(r => `${r.f}=${r.items.map(i => i.v).join('/')}`).join('、') || '無';

/* 鎖住那一行對目錄列述詞(詞元、極性以外的欄,區域項畫成「玩家或不限・區域」):欄與值都相同、每顆按不掉、
   樣式同按不掉的鈕、說明「由 X 決定」、沒有選單、輸入框、×。 */
async function checkLocked(ctx, name) {
  const want = JSON.parse(await ctx.ev(`(()=>{const row=VOCAB.catalog.find(r=>r.predicate&&r.name===${q(name)});
    const out={};Object.keys(row.predicate).filter(k=>k!=='詞元'&&k!=='極性').forEach(k=>{
      out[k]=[].concat(row.predicate[k]).map(v=>Array.isArray(v)?(v[0]||'不限')+'・'+v[1]:String(v));});
    return JSON.stringify(out);})()`));
  const rows = await lockedRows(ctx);
  log(`  鎖住的欄:${lockedSummary(rows)}(目錄列 ${Object.keys(want).map(k => k + '=' + want[k].join('/')).join('、') || '無'})`);
  const got = {};
  rows.forEach(r => { got[r.f] = r.items.map(i => i.v).sort(); });
  const norm = o => JSON.stringify(Object.keys(o).sort().map(k => [k, o[k].slice().sort()]));
  if (norm(got) !== norm(want)) bad(`${name}:鎖住的欄和目錄列不同 ${norm(got)} ≠ ${norm(want)}`);
  rows.forEach(r => {
    if (r.menus || r.inputs || r.xs) bad(`${name} ${r.f}:鎖住的欄還有選單 ${r.menus}、輸入框 ${r.inputs}、× ${r.xs}`);
    r.items.forEach(i => {
      if (i.act || !i.dis || !i.locked || i.title !== LOCK_HINT(name) || i.text !== i.v) {
        bad(`${name} ${r.f}=${i.v}:鎖住的鈕樣子不對 ${JSON.stringify(i)}`);
      }
    });
  });
  return rows;
}

async function polarityRow(ctx) {
  return ctx.ev(`[...document.querySelectorAll('#condDrawer [data-field="極性"] .drawer-chip')].map(c=>(c.disabled?'~':'')+c.dataset.v).join(' ')`);
}

async function reload(ctx, p, href) {
  const { send, ev } = ctx;
  await send('Page.navigate', { url: 'about:blank' });
  await sleep(300);
  await send('Page.navigate', { url: href });
  for (let i = 0; i < 100; i++) {
    await sleep(200);
    if (await ev(`typeof Hash !== 'undefined' && document.readyState === 'complete'`)) break;
  }
  await sleep(300);
  await p.tap('#condStrip .strip-tag:not(.side) .strip-lemma');
  for (let i = 0; i < 20 && !(await p.snap()).open; i++) await sleep(50);
}

/* 貼網址重開:原樣重開仍鎖(故事 22);只改位置重開仍鎖(故事 26);另加一欄重開條件、張數相同,但不鎖(故事 23)。 */
async function reopenScenario(ctx, p, base) {
  const { ev } = ctx;
  const name = base.tagName;
  const strip = `[...document.querySelectorAll('#condStrip .strip-tag')].map(t=>t.textContent.replace(/\\s+/g,' ').trim()).join(' / ')`;
  const state = async () => ({ href: await ev('location.href'), strip: await ev(strip), res: (await p.snap()).res,
    locked: lockedSummary(await lockedRows(ctx)) });
  const openChip = (fields, inside) => ev(`(()=>{const c=[...document.querySelectorAll('#condDrawer .drawer-chip:not(.on):not(:disabled)')]
    .find(c=>${q(fields)}.includes(c.closest('[data-field]').dataset.field)===${inside});
    return c?JSON.stringify({f:c.closest('[data-field]').dataset.field,v:c.dataset.v}):null;})()`);
  const cases = [['原樣', null, false], ['只改位置', ['位置'], true], ['另加一欄', ['位置', '極性'], false]];
  for (const [label, fields, inside] of cases) {
    if (fields) {
      const c = await openChip(fields, inside);
      if (!c) { log(`  貼網址重開(${label}):沒有可按的鈕,跳過`); continue; }
      const { f, v } = JSON.parse(c);
      const before = await p.snap();
      await p.tap(`#condDrawer [data-field=${q(f)}] .drawer-chip[data-v=${q(v)}]`);
      await p.settle(before.hash, true);
      log(`  貼網址重開(${label}):先按 ${f}=${v}`);
    }
    const was = await state();
    await reload(ctx, p, was.href);
    const now = await state();
    log(`  貼網址重開(${label}):${now.strip} | ${now.res} | 鎖住 ${now.locked}`);
    if (now.href !== was.href || now.strip !== was.strip || now.res !== was.res) {
      bad(`貼網址重開(${label})不同:${JSON.stringify(was)} → ${JSON.stringify(now)}`);
    }
    const stillLocked = (await lockedRows(ctx)).some(r => r.items.some(i => i.title === LOCK_HINT(name)));
    const shouldLock = label !== '另加一欄' && was.locked !== '無';
    if (stillLocked !== shouldLock) bad(`貼網址重開(${label}):鎖住應為 ${shouldLock},實際 ${stillLocked}(重開前 ${was.locked})`);
    if (label !== '另加一欄' && now.locked !== was.locked) bad(`貼網址重開(${label}):鎖住的欄變了 ${was.locked} → ${now.locked}`);
    await reload(ctx, p, base.href);
  }
}

/* 手機寬時篩選條件收在摺疊鈕裡,目錄要先打開。 */
async function sidebar(ctx, p, open) {
  const st = await ctx.ev(`(()=>{const b=document.getElementById('btnFilters');return b.offsetHeight>0?b.getAttribute('aria-expanded'):'wide';})()`);
  if (st !== 'wide' && (st === 'true') !== open) await p.tap('#btnFilters');
}

const catPick = key => `#catalogNav .cat-node[data-key=${q(key)}] > .cat-row > .cat-pick`;

async function catalogState(ctx, key) {
  return JSON.parse(await ctx.ev(`(()=>{const li=document.querySelector('#catalogNav .cat-node[data-key=${q(key).replace(/'/g, "\\'")}]');
    const row=li.querySelector(':scope > .cat-row');const tog=row.querySelector('.cat-tog');
    const kids=[...li.querySelectorAll(':scope > .cat-kids > .cat-node')];const pick=row.querySelector('.cat-pick');
    return JSON.stringify({open:!!tog&&tog.getAttribute('aria-expanded')==='true',
      kidsShown:!!li.querySelector(':scope > .cat-kids:not([hidden])'),hidden:li.hidden,
      path:pick.dataset.path||'',minus:!!row.querySelector('.cat-minus'),
      used:!pick.querySelector('.cat-used').hidden,
      kids:kids.map(k=>({key:k.dataset.key,name:k.querySelector(':scope > .cat-row .cat-pick > span').textContent,
        path:k.querySelector(':scope > .cat-row .cat-pick').dataset.path||'',hidden:k.hidden}))});})()`));
}

const tagCount = ctx => ctx.ev(`document.querySelectorAll('#condStrip .strip-tag:not(.side)').length`);

/* 目錄:大類、中類一路點下去只展開;點 破壊 只展開、沒有 −;它的最後一列同名、帶葉路徑與 −;點最後一列加標籤、
   「已用」只標最後一列;點 − 加排除;大類 召喚 的最後一列是 召喚;過濾框打 破壊 時父節點展開、最後一列看得到。 */
async function catalogScenario(ctx, p) {
  const { ev } = ctx;
  log(`\n-- 目錄:${CATALOG_LEMMA}`);
  await ev(`location.hash=${q(await ev(`Hash.stringify({q:{},cond:Cond.empty(),sort:{}})`))}`);
  await sleep(300);
  await sidebar(ctx, p, true);
  const chain = JSON.parse(await ev(`(()=>{const find=(keys,trail)=>{for(const k of keys){const n=Acat.node(k);const t=trail.concat([k]);
    if(n.name===${q(CATALOG_LEMMA)}&&n.kids.length)return t;const r=find(n.kids,t);if(r)return r;}return null;};
    return JSON.stringify(find(Acat.roots,[]));})()`));
  for (const key of chain) {
    const before = await p.snap();
    await p.tap(catPick(key));
    const s = await p.settle(before.hash, false);
    const st = await catalogState(ctx, key);
    const tags = await tagCount(ctx);
    log(`  點 ${key.split('›').pop()}:${st.open ? '展開' : '沒展開'},網址${s.hash === before.hash ? '不變' : '變了'},標籤 ${tags} 張,`
      + `葉路徑${st.path ? '有' : '無'},−${st.minus ? '有' : '無'}`);
    if (!st.open || !st.kidsShown || s.hash !== before.hash || tags || st.path || st.minus) bad(`目錄點 ${key}:不是只展開`);
  }
  const lemmaKey = chain[chain.length - 1];
  const st = await catalogState(ctx, lemmaKey);
  const last = st.kids[st.kids.length - 1];
  log(`  ${CATALOG_LEMMA} 的子:${st.kids.map(k => k.name).join('、')}`);
  if (!last || last.name !== CATALOG_LEMMA || !last.path) bad(`${CATALOG_LEMMA}:最後一列不是同名、帶葉路徑的列`);
  const lastSt = await catalogState(ctx, last.key);
  if (!lastSt.minus) bad(`${CATALOG_LEMMA}:最後一列沒有 −`);

  let before = await p.snap();
  await p.tap(catPick(last.key));
  let s = await p.settle(before.hash, true);
  const usedLast = (await catalogState(ctx, last.key)).used, usedParent = (await catalogState(ctx, lemmaKey)).used;
  log(`  點最後一列 ${CATALOG_LEMMA}:標籤 ${await tagCount(ctx)} 張,${s.res},已用 最後一列 ${usedLast}、父列 ${usedParent}`);
  if (s.hash === before.hash || (await tagCount(ctx)) !== 1 || !p.count(s) || !usedLast || usedParent) bad('點最後一列:沒加標籤或已用標錯');
  await ev(`location.hash=${q(await ev(`Hash.stringify({q:{},cond:Cond.empty(),sort:{}})`))}`);
  await sleep(300);
  before = await p.snap();
  await p.tap(`#catalogNav .cat-node[data-key=${q(last.key)}] > .cat-row > .cat-minus`);
  s = await p.settle(before.hash, true);
  const exNow = await ev(`document.querySelectorAll('#condStrip .strip-tag.ex').length`);
  log(`  清除後點最後一列的 −:標籤 ${await tagCount(ctx)} 張(排除 ${exNow}),${s.res}`);
  if (s.hash === before.hash || (await tagCount(ctx)) !== 1 || exNow !== 1 || !p.count(s)) bad('點最後一列的 −:沒加排除標籤或 0 張');

  const summon = JSON.parse(await ev(`(()=>{const k=Acat.roots.find(k=>Acat.node(k).name==='召喚')
    ||[...document.querySelectorAll('#catalogNav .cat-node')].map(li=>li.dataset.key).find(k=>Acat.node(k).name==='召喚'&&!Acat.node(k).path);
    const n=Acat.node(k);const last=Acat.node(n.kids[n.kids.length-1]);return JSON.stringify({key:k,last:last.name,path:!!last.path});})()`));
  log(`  大類 召喚 的最後一列:${summon.last}(葉路徑${summon.path ? '有' : '無'})`);
  if (summon.last !== '召喚' || !summon.path) bad('大類 召喚 的最後一列不是 召喚');

  await ev(`location.hash=${q(await ev(`Hash.stringify({q:{},cond:Cond.empty(),sort:{}})`))}`);
  await sleep(300);
  for (const key of chain.slice().reverse()) if ((await catalogState(ctx, key)).open) await p.tap(catPick(key));
  await p.tap('#catalogNav .cat-filter');
  await p.type(CATALOG_LEMMA);
  await sleep(200);
  const f1 = await catalogState(ctx, lemmaKey), f2 = await catalogState(ctx, last.key);
  log(`  過濾框打 ${CATALOG_LEMMA}:父列${f1.hidden ? '藏' : '看得到'}、${f1.open ? '展開' : '收合'};最後一列${f2.hidden ? '藏' : '看得到'}`);
  if (f1.hidden || !f1.open || f2.hidden) bad(`過濾 ${CATALOG_LEMMA}:父列沒展開或最後一列看不到`);
  await ev(`(()=>{const i=document.querySelector('#catalogNav .cat-filter');i.value='';i.dispatchEvent(new Event('input',{bubbles:true}));})()`);
  await sidebar(ctx, p, false);
}

/* 從目錄點具名查詢(過濾框找到那一列再點)加的標籤,網址和直接開網址的那張相同。 */
async function pickFromCatalog(ctx, p, name) {
  const { ev } = ctx;
  await ev(`location.hash=${q(await ev(`Hash.stringify({q:{},cond:Cond.empty(),sort:{}})`))}`);
  await sleep(300);
  await sidebar(ctx, p, true);
  await p.tap('#catalogNav .cat-filter');
  await p.type(name);
  await sleep(200);
  const key = await ev(`(()=>{const li=[...document.querySelectorAll('#catalogNav .cat-node')].find(li=>!li.hidden&&
    li.querySelector(':scope > .cat-row .cat-pick[data-path]')&&li.querySelector(':scope > .cat-row .cat-pick > span').textContent===${q(name)});
    return li?li.dataset.key:null;})()`);
  if (!key) { bad(`目錄找不到 ${name}`); return null; }
  const before = await p.snap();
  await p.tap(catPick(key));
  const s = await p.settle(before.hash, true);
  await ev(`(()=>{const i=document.querySelector('#catalogNav .cat-filter');i.value='';i.dispatchEvent(new Event('input',{bubbles:true}));})()`);
  await sidebar(ctx, p, false);
  return s.hash;
}

async function timing(ctx, name) {
  return JSON.parse(await ctx.ev(`(()=>{const sel=c=>'#condDrawer [data-field="'+c.f+'"] .drawer-chip[data-v="'+c.v+'"]';
    const c0=document.querySelector('#condDrawer .drawer-chip:not(.on):not(:disabled)');
    const c={f:c0.closest('[data-field]').dataset.field,v:c0.dataset.v};const click=[];
    for(let i=0;i<10;i++){const t=performance.now();document.querySelector(sel(c)).click();click.push(performance.now()-t);}
    const row=VOCAB.catalog.find(r=>r.predicate&&r.name===${q(name)});const tag=Cond.tagAt(row.path.join(Cond.SEP),false);
    const opt=[];for(let i=0;i<10;i++){const t=performance.now();Cond.drawerOptions(tag);opt.push(performance.now()-t);}
    const m=xs=>xs.sort((a,b)=>a-b)[xs.length>>1];return JSON.stringify({chip:c.f+'='+c.v,click:m(click),options:m(opt)});})()`));
}

async function run(ctx, width) {
  const { send, ev, errors } = ctx;
  const phone = width === 'phone';
  await send('Emulation.setDeviceMetricsOverride', WIDTHS[width]);
  await send('Emulation.setTouchEmulationEnabled', { enabled: phone, maxTouchPoints: phone ? 5 : 1 });
  await send('Page.navigate', { url: PAGE });
  for (let i = 0; i < 100; i++) {
    await sleep(300);
    if (await ev(`typeof Hash !== 'undefined' && document.readyState === 'complete'`)) break;
  }
  const p = page(ctx, phone);
  const errorsBefore = errors.length;
  const started = Date.now();
  log(`\n==== ${width}(${WIDTHS[width].width}×${WIDTHS[width].height}${phone ? ',觸控' : ''})====`);
  const sum = [];
  await catalogScenario(ctx, p);
  for (const name of tagNames) {
    const fromCatalog = await pickFromCatalog(ctx, p, name);
    const base = Object.assign(await openTag(ctx, p, name), { tagName: name, href: await ctx.ev('location.href') });
    log(`
-- ${name}:從目錄點的網址${fromCatalog === base.hash ? '和直接開的相同' : '不同 ' + decodeURIComponent(fromCatalog)}`);
    if (fromCatalog !== base.hash) bad(`${name}:從目錄點的網址和直接開的不同`);
    log(`\n-- ${name}:${base.res} | 抽屜 ${base.note} | 開:${base.open}`);
    if (!base.open) { bad(`${name}:抽屜沒開`); continue; }
    const t0 = Date.now();
    const locked = await checkLocked(ctx, name);
    const polarity = await polarityRow(ctx);
    log(`  極性:${polarity}`);
    if (locked.some(r => r.f === '否定形') && polarity !== '~否定') bad(`${name}:否定形鎖住時極性欄應只剩按不掉的 否定,實際 ${polarity}`);
    const chips = await sweepChips(ctx, p, base);
    const regions = await sweepRegions(ctx, p, base);
    const heads = await sweepHeads(ctx, p, base);
    if (name === '破壊') await negationScenario(ctx, p, base);
    await typedThenChip(ctx, p, base);
    const time = await timing(ctx, name);
    await restore(ctx, p, base, '耗時');
    log(`  重畫耗時(10 次中位):點 ${time.chip} 到畫完 ${time.click.toFixed(1)} ms;Cond.drawerOptions ${time.options.toFixed(1)} ms`);
    await reopenScenario(ctx, p, base);
    sum.push({ name, locked, chips, regions, heads, time, sec: (Date.now() - t0) / 1000 });
  }
  log(`\n摘要(${width}):`);
  for (const s of sum) {
    log(`  ${s.name}:鎖住的欄 ${lockedSummary(s.locked)};可按 ${s.chips.可按}、亮 ${s.chips.亮}(關掉 0 張 ${s.chips.亮關掉0張})、灰 ${s.chips.灰}、`
      + `鎖住 ${s.chips.鎖住}、鎖住的欄的鈕 ${s.chips.鎖住的欄};`
      + `區域 ${s.regions.區域}(灰區域 ${s.regions.灰區域}、灰玩家 ${s.regions.灰玩家});中心詞候選 ${s.heads.候選}、清單外 ${s.heads.清單外};`
      + `點鈕到畫完 ${s.time.click.toFixed(1)} ms、抽屜選項 ${s.time.options.toFixed(1)} ms;走完 ${s.sec.toFixed(0)} 秒`);
  }
  log(`  console 錯誤 ${errors.length - errorsBefore}${errors.length > errorsBefore ? ':' + errors.slice(errorsBefore).join(' | ') : ''}`);
  log(`  共 ${((Date.now() - started) / 1000).toFixed(0)} 秒`);
  if (errors.length > errorsBefore) bad(`${width}:console 有錯`);
}

async function main() {
  const ctx = await connect();
  log(`頁面 ${PAGE}`);
  for (const width of which === 'both' ? ['desktop', 'phone'] : [which]) await run(ctx, width);
  log(`\n違規 ${problems.length}${problems.length ? ':\n' + problems.join('\n') : ''}`);
  ctx.ws.close();
}

main().catch(e => { console.error(e); problems.push(String(e)); })
  .finally(() => {
    chrome.kill();
    fs.writeFileSync(OUT, lines.join('\n') + '\n');
    process.exitCode = problems.length ? 1 : 0;
  });
