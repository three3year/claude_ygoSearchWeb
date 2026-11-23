/**
 * frontend_harness.js — 接縫 3 的沙箱載入器(零 npm 依賴)
 *
 * 接縫 3:`查詢條件 -> (命中卡片密碼清單, 每張卡的命中效果句索引)`。
 *
 * 依 `web/index.html` 的 `<script src>` 順序,在 `node:vm` 沙箱裡載入 **web/ 底下
 * 真實的前端程式碼**——不是測試專用的複製品,測試通過才代表網站真的會那樣跑。
 * 拆檔或改載入順序時這裡自動跟著走,因為順序是從 HTML 讀來的。
 *
 * 唯一跳過的是 `data.js`:它是建置期的產物(7.5 MB 真實索引)而不是前端程式碼,
 * 接縫測試餵的是合成資料集。前端檔案因此不必為了可測而加 `module.exports`
 * 之類的東西——production 碼保持乾淨(零建置協定,ADR-0007)。
 */
'use strict';

const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const WEB = path.join(__dirname, '..', '..', 'web');
const DATA = 'data.js';

/* 最小 DOM stub:前端模組在載入時只是定義函式,真正碰 DOM 的是各自的 init(),
   而 init() 掛在 DOMContentLoaded 上、沙箱裡不會觸發。stub 存在只是讓萬一有人
   在模組頂層查了元素時不會炸開。 */
function stubEl() {
  return {
    classList: { add() {}, remove() {}, toggle() {}, contains: () => false },
    style: {}, dataset: {}, value: '', checked: false,
    textContent: '', innerHTML: '', hidden: false, offsetTop: 0,
    addEventListener() {}, removeEventListener() {},
    appendChild() {}, removeChild() {}, setAttribute() {},
    querySelector: () => null, querySelectorAll: () => [],
    closest: () => null, focus() {}, scrollIntoView() {},
  };
}

function scriptSrcs() {
  const html = fs.readFileSync(path.join(WEB, 'index.html'), 'utf8');
  const re = /<script\s+src="([^"]+)"/g;
  const srcs = [];
  let m;
  while ((m = re.exec(html)) !== null) srcs.push(m[1]);
  return srcs;
}

/* 驅動函式與前端程式同作用域,把接縫的回傳值壓成 JSON——Set 與物件跨 realm
   帶出去要看 prototype 臉色,字串不必。 */
const DRIVER = `
;var __actionIndex = null;
;function __index() {
  if (!__actionIndex && window.ACTION_DATA) __actionIndex = Action.prepare(window.ACTION_DATA, window.CARD_DATA);
  return __actionIndex;
}
;function __runQuery(json) {
  var a = JSON.parse(json);
  var result = Engine.runQuery(window.CARD_DATA, a.q, a.act, a.act ? __index() : null);
  return JSON.stringify({
    cards: result.cards.map(function (e) {
      return {
        id: e.card.id,
        rows: e.rows ? Array.from(e.rows).sort(function (a, b) { return a - b; }) : null,
      };
    }),
    marks: result.marks,
    unsure: result.unsure,
  });
}
;function __rowQuery(json) { return JSON.stringify(Action.rowQuery(JSON.parse(json), __index())); }
;function __axes() { return JSON.stringify(Query.axes()); }
;function __nextState(json) {
  var a = JSON.parse(json);
  return Query.nextState(a.st, a.states);
}
;function __optAvail(json) { return JSON.stringify(Query.optionalAvailable(JSON.parse(json))); }
;function __critCount(json) { var a = JSON.parse(json); return Query.count(a.q, a.act); }
;function __actionOptions() { return JSON.stringify(Action.options(__index())); }
;function __cardSuggest(text) { return JSON.stringify(Action.suggest(window.CARD_DATA, text)); }
;function __conditionOptions() { return JSON.stringify(Action.conditionOptions()); }
;function __archetypeSuggest(text) { return JSON.stringify(Action.archetypeSuggest(__index(), text)); }
;function __zoneOptions() { return JSON.stringify(Action.zoneOptions(__index())); }
;function __causeOptions() { return JSON.stringify(Action.causeOptions(__index())); }
;function __toggleKind(json) { var a = JSON.parse(json); return JSON.stringify(Action.toggleKind(a.kinds, a.kind)); }
;function __axisCounts(json) { return JSON.stringify(Query.axisCounts(JSON.parse(json))); }
;function __treeCounts(json) { return JSON.stringify(Query.treeCounts(JSON.parse(json))); }
;function __expandedAxes(json) { return JSON.stringify(Query.expandedAxes(JSON.parse(json))); }
;function __sortedIds(json) {
  var a = JSON.parse(json);
  var result = Engine.runQuery(window.CARD_DATA, a.query || {}, a.act, a.act ? __index() : null);
  return JSON.stringify(Sort.sort(result.cards, a.key, a.dir)
    .map(function (e) { return e.card.id; }));
}
;function __sortKeys() { return JSON.stringify(Sort.KEYS); }
;function __saved(json) {
  var a = JSON.parse(json);
  return JSON.stringify(Saved.snapshot(a.q, a.sort, a.act));
}
;function __restore(json) { return JSON.stringify(Saved.restore(JSON.parse(json))); }
;function __fmtTime(v) { return Util.fmtTime(v); }
;function __unsureText(n) { return View.unsureText(n); }
;function __cardHtml(json) { return View.cardHtml(JSON.parse(json), null); }
`;

function load({ cards = [], vocab = {}, meta = {}, action = null } = {}) {
  const sandbox = {
    console, setTimeout, clearTimeout, atob,
    document: {
      getElementById: () => stubEl(),
      querySelector: () => null,
      querySelectorAll: () => [],
      createElement: () => stubEl(),
      addEventListener() {},
      body: stubEl(),
    },
    addEventListener() {},
    scrollTo() {},
    scrollY: 0, innerHeight: 800,
  };
  sandbox.window = sandbox;          // window.CARD_DATA 等一律掛沙箱 global
  sandbox.CARD_DATA = cards;
  sandbox.VOCAB = vocab;
  sandbox.META = meta;
  vm.createContext(sandbox);
  if (typeof action === 'string') vm.runInContext(action, sandbox, { filename: 'action-data.js' });
  else if (action) sandbox.ACTION_DATA = action;
  for (const src of scriptSrcs()) {
    if (src === DATA) continue;
    const code = fs.readFileSync(path.join(WEB, src), 'utf8');
    vm.runInContext(code, sandbox, { filename: src });
  }
  vm.runInContext(DRIVER, sandbox, { filename: '__driver__' });
  return sandbox;
}

function runQuery(sandbox, query, act) {
  return JSON.parse(sandbox.__runQuery(JSON.stringify({ q: query, act: act || null })));
}

function search(sandbox, query, act) {
  return runQuery(sandbox, query, act).cards;
}

/** 只要命中的卡片密碼清單(順序即引擎回傳序) */
function ids(sandbox, query, act) {
  return search(sandbox, query, act).map(e => e.id);
}

function unsure(sandbox, query, act) {
  return runQuery(sandbox, query, act).unsure;
}

/** 生效中的句層條件(呈現層照它寫命中行的 badge) */
function marks(sandbox, query, act) {
  return runQuery(sandbox, query, act).marks;
}

function rowQuery(sandbox, act) {
  return JSON.parse(sandbox.__rowQuery(JSON.stringify(act || null)));
}

function actionOptions(sandbox) {
  return JSON.parse(sandbox.__actionOptions());
}

function zoneOptions(sandbox) {
  return JSON.parse(sandbox.__zoneOptions());
}

function causeOptions(sandbox) {
  return JSON.parse(sandbox.__causeOptions());
}

function toggleKind(sandbox, kinds, kind) {
  return JSON.parse(sandbox.__toggleKind(JSON.stringify({ kinds, kind })));
}

function cardSuggest(sandbox, text) {
  return JSON.parse(sandbox.__cardSuggest(text));
}

/**
 * 分類類條件的按鈕清單。**這是「按鈕由值域正典生成」唯一測得到的形狀**——沙箱裡
 * 沒有真的 DOM,而 DOM 那一層只是照這份清單擺按鈕。值域多一個成員,這裡就多一顆。
 */
function axes(sandbox) {
  return JSON.parse(sandbox.__axes());
}

/**
 * 「必發/選發」的兩組條件在目前的效果類型選擇下各自出不出得來
 * (Story 25、spec-optional-combo);回傳與 VOCAB.optional.groups 對齊的布林陣列。
 * 與 `axes()` 同一個理由:沙箱裡沒有真的 DOM,而 DOM 那一層只是照這個答案
 * 決定要不要收起那一軸——規則本身是純的,所以測得到。
 */
function optionalAvailable(sandbox, kindSel) {
  return JSON.parse(sandbox.__optAvail(JSON.stringify(kindSel || null)));
}

/**
 * 狀態循環規則(票12):`(目前狀態, 態數) → 下一個狀態`。
 * 態數是軸宣告的一部分(`axes()` 的 `states`),DOM 那一層照這條規則循環——
 * 兩態軸(大類)永遠碰不到排除,而這件事在宣告與規則上都測得到。
 */
function nextState(sandbox, st, states) {
  return sandbox.__nextState(JSON.stringify({ st, states }));
}

/**
 * 生效中的條件數(票09:窄螢幕的側欄摺起來之後,摺疊鈕上寫的就是它)。
 * 與 `optionalAvailable()` 同一個理由:規則是純的,DOM 那一層只是把數字寫上去。
 */
function critCount(sandbox, q, act) {
  return sandbox.__critCount(JSON.stringify({ q: q || {}, act: act || null }));
}

/**
 * 逐軸已選數(票13):`查詢條件 → { 區塊鍵: 點了幾顆 }`。軸摺疊之後標題列寫的
 * 就是它——收起的軸看不見裡面,數字讓條件保持可見。規則是純的,DOM 只照答案寫。
 */
function axisCounts(sandbox, q) {
  return JSON.parse(sandbox.__axisCounts(JSON.stringify(q || {})));
}

/**
 * 子樹已選數(檔案總管式內縮):`查詢條件 → { 區塊鍵: 自己+後代點了幾顆 }`。
 * 父軸標題列寫的是它——大類收著也看得出整棵子樹裡藏著幾條條件。
 */
function treeCounts(sandbox, q) {
  return JSON.parse(sandbox.__treeCounts(JSON.stringify(q || {})));
}

function expandedAxes(sandbox, q) {
  return JSON.parse(sandbox.__expandedAxes(JSON.stringify(q || {})));
}

function sortedIds(sandbox, query, key, dir, act) {
  return JSON.parse(sandbox.__sortedIds(
    JSON.stringify({ query: query || {}, key: key || '', dir: dir || '', act: act || null })));
}

/** 排序選單的鍵清單(選單的選項由它生成,比較函式也由它決定取哪個欄位) */
function sortKeys(sandbox) {
  return JSON.parse(sandbox.__sortKeys());
}

function savedState(sandbox, q, sort, act) {
  return JSON.parse(sandbox.__saved(JSON.stringify({ q: q || {}, sort: sort || {},
                                                     act: act || null })));
}

function restoreSaved(sandbox, raw) {
  return JSON.parse(sandbox.__restore(JSON.stringify(raw === undefined ? null : raw)));
}

/**
 * 呈現縫:`{ card, rows } → 一張卡的 HTML 字串`(spec banlist)。
 * 沙箱裡沒有真的 DOM,測得到的是字面——render.test.js 斷言使用者看得到的
 * 文字,不斷言 markup。
 */
function cardHtml(sandbox, entry) {
  return sandbox.__cardHtml(JSON.stringify(entry));
}

function unsureText(sandbox, n) {
  return sandbox.__unsureText(n);
}

module.exports = { load, search, ids, unsure, unsureText, marks, rowQuery, actionOptions, cardSuggest, axes, optionalAvailable, nextState,
                   critCount, axisCounts, treeCounts, expandedAxes,
                   sortedIds, sortKeys, savedState, restoreSaved, cardHtml };
module.exports.zoneOptions = zoneOptions;
module.exports.toggleKind = toggleKind;
module.exports.causeOptions = causeOptions;

function conditionOptions(sandbox) {
  return JSON.parse(sandbox.__conditionOptions());
}

function archetypeSuggest(sandbox, text) {
  return JSON.parse(sandbox.__archetypeSuggest(text));
}

module.exports.conditionOptions = conditionOptions;
module.exports.archetypeSuggest = archetypeSuggest;
