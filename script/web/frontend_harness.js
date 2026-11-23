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
  if (!__actionIndex && window.ACTION_DATA) __actionIndex = Action.prepare(window.ACTION_DATA);
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
  });
}
;function __rowQuery(json) { return JSON.stringify(Action.rowQuery(JSON.parse(json))); }
;function __axes() { return JSON.stringify(Query.axes()); }
;function __nextState(json) {
  var a = JSON.parse(json);
  return Query.nextState(a.st, a.states);
}
;function __optAvail(json) { return JSON.stringify(Query.optionalAvailable(JSON.parse(json))); }
;function __critCount(json) { var a = JSON.parse(json); return Query.count(a.q, a.act); }
;function __actionOptions() { return JSON.stringify(Action.options(__index())); }
;function __zoneOptions() { return JSON.stringify(Action.zoneOptions(__index())); }
;function __toggleKind(json) { var a = JSON.parse(json); return JSON.stringify(Action.toggleKind(a.kinds, a.kind)); }
;function __axisCounts(json) { return JSON.stringify(Query.axisCounts(JSON.parse(json))); }
;function __treeCounts(json) { return JSON.stringify(Query.treeCounts(JSON.parse(json))); }
;function __expandedAxes(json) { return JSON.stringify(Query.expandedAxes(JSON.parse(json))); }
;function __sortedIds(json) {
  var a = JSON.parse(json);
  var result = Engine.runQuery(window.CARD_DATA, a.query || {});
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
;function __cardHtml(json) { return View.cardHtml(JSON.parse(json), null); }
`;

/**
 * 載入前端程式碼,回傳沙箱。
 * fixture:{ cards, vocab, meta, action } —— 合成的 window.CARD_DATA / VOCAB / META,
 * 與動作索引 window.ACTION_DATA。action 是物件(測試照描述寫的小索引)或
 * `action-data.js` 的全文(Python 建置的產物,照網站載入它的方式在沙箱裡執行)。
 * 動作索引不在 index.html 的 `<script>` 裡(第一次打開動作搜尋才載入),所以另外餵。
 */
function load({ cards = [], vocab = {}, meta = {}, action = null } = {}) {
  const sandbox = {
    console, setTimeout, clearTimeout,
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

/**
 * 接縫 3:(查詢條件, 動作條件) → [{ id, rows }],rows 是該卡命中的效果句索引(沒有句層
 * 條件時為 null)。動作條件省略即沒有動作條件——那時引擎不碰動作索引。
 */
function search(sandbox, query, act) {
  return runQuery(sandbox, query, act).cards;
}

/** 只要命中的卡片密碼清單(順序即引擎回傳序) */
function ids(sandbox, query, act) {
  return search(sandbox, query, act).map(e => e.id);
}

/** 生效中的句層條件(呈現層照它寫命中行的 badge) */
function marks(sandbox, query, act) {
  return runQuery(sandbox, query, act).marks;
}

/**
 * 動作條件換成的列查詢(鍵名與值照 Python 的 `run_query`):「兩邊答案一致」的測試把它
 * 交給 Python,兩邊比的是同一個問題。
 */
function rowQuery(sandbox, act) {
  return JSON.parse(sandbox.__rowQuery(JSON.stringify(act || null)));
}

/**
 * 動作詞的選項:`{ shown, more }`,依列數排,前面一批直接顯示、其餘收在「更多」。
 * 與 `axes()` 同一個理由:沙箱裡沒有真的 DOM,區塊只是照這份清單擺按鈕。
 */
function actionOptions(sandbox) {
  return JSON.parse(sandbox.__actionOptions());
}

/** 從、到的區域選項(票 09):索引的區域表依列數排。 */
function zoneOptions(sandbox) {
  return JSON.parse(sandbox.__zoneOptions());
}

/** 段類別勾選點一下之後的勾選(票 09):只剩一個勾著時不能取消。 */
function toggleKind(sandbox, kinds, kind) {
  return JSON.parse(sandbox.__toggleKind(JSON.stringify({ kinds, kind })));
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

/**
 * 還原展開判定(票14):`查詢條件 → 該展開的區塊鍵清單`。還原查詢時 DOM 照這份
 * 清單開軸——有已選條件的軸連同**祖先鏈**,以及連動出現的必發/選發軸。
 */
function expandedAxes(sandbox, q) {
  return JSON.parse(sandbox.__expandedAxes(JSON.stringify(q || {})));
}

/**
 * 命中的卡片密碼清單,**照 key/dir 排序後**的順序(key 省略即預設的領域序)。
 *
 * 走的是搜尋 → 排序這條真實的路徑:排序吃的是接縫 3 的回傳形狀,而不是另外
 * 拼一份卡片陣列——「排序切換不重跑搜尋」在這裡看得到,重排的輸入就是同一份結果。
 */
function sortedIds(sandbox, query, key, dir) {
  return JSON.parse(sandbox.__sortedIds(
    JSON.stringify({ query: query || {}, key: key || '', dir: dir || '' })));
}

/** 排序選單的鍵清單(選單的選項由它生成,比較函式也由它決定取哪個欄位) */
function sortKeys(sandbox) {
  return JSON.parse(sandbox.__sortKeys());
}

/**
 * 存進瀏覽紀錄的查詢狀態(action-search-web 票01):`(條件, 排序, 動作條件) → 那一筆存的物件`。
 * 寫入時機與 `popstate` 測不到(沙箱裡沒有瀏覽紀錄),走人工驗收。
 */
function savedState(sandbox, q, sort, act) {
  return JSON.parse(sandbox.__saved(JSON.stringify({ q: q || {}, sort: sort || {},
                                                     act: act || null })));
}

/**
 * 從瀏覽紀錄的一筆還原成 `{ q, sort, act }`(q 就是接縫 3 吃的查詢條件形狀;沒有動作條件
 * 時沒有 act)。
 * raw 可能是舊版網站寫的、甚至不是物件:認不得的欄位或值忽略,其餘照常還原。
 */
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

module.exports = { load, search, ids, marks, rowQuery, actionOptions, axes, optionalAvailable, nextState,
                   critCount, axisCounts, treeCounts, expandedAxes,
                   sortedIds, sortKeys, savedState, restoreSaved, cardHtml };
module.exports.zoneOptions = zoneOptions;          // 票 09
module.exports.toggleKind = toggleKind;            // 票 09
