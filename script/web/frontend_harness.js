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
;function __runQuery(json) {
  var result = Engine.runQuery(window.CARD_DATA, JSON.parse(json));
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
;function __axes() { return JSON.stringify(Query.axes()); }
`;

/**
 * 載入前端程式碼,回傳沙箱。
 * fixture:{ cards, vocab, meta } —— 合成的 window.CARD_DATA / VOCAB / META。
 */
function load({ cards = [], vocab = {}, meta = {} } = {}) {
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
  for (const src of scriptSrcs()) {
    if (src === DATA) continue;
    const code = fs.readFileSync(path.join(WEB, src), 'utf8');
    vm.runInContext(code, sandbox, { filename: src });
  }
  vm.runInContext(DRIVER, sandbox, { filename: '__driver__' });
  return sandbox;
}

/** 接縫 3:查詢條件 → [{ id, rows }],rows 是該卡命中的效果句索引(沒有句層條件時為 null) */
function search(sandbox, query) {
  return JSON.parse(sandbox.__runQuery(JSON.stringify(query))).cards;
}

/** 只要命中的卡片密碼清單(順序即引擎回傳序) */
function ids(sandbox, query) {
  return search(sandbox, query).map(e => e.id);
}

/** 生效中的句層條件(呈現層照它寫命中行的 badge) */
function marks(sandbox, query) {
  return JSON.parse(sandbox.__runQuery(JSON.stringify(query))).marks;
}

/**
 * 分類類條件的按鈕清單。**這是「按鈕由值域正典生成」唯一測得到的形狀**——沙箱裡
 * 沒有真的 DOM,而 DOM 那一層只是照這份清單擺按鈕。值域多一個成員,這裡就多一顆。
 */
function axes(sandbox) {
  return JSON.parse(sandbox.__axes());
}

module.exports = { load, search, ids, marks, axes };
