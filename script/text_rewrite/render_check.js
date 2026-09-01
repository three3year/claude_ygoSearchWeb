// 審核台 HTML 的冒煙測試:抽出頁面內嵌的 JS,套一個最小 DOM stub **真的跑一遍**,
// 確認每一張卡都 render 得出來。
//
// 為什麼需要:`build_review_page.py` 只把 JSON 塞進模板,不會執行模板裡的 JS——
// 產得出檔不代表頁面打得開。2026-08-28 換四欄時 Python 側欄位改了名
// (`modernJa` → `jaFaq`)、模板的 JS 沒跟著改,`c.modernJa.length` 對 undefined
// 取值丟例外,`renderStream()` 死在第一張卡,**整頁空白但建置全綠**,是站主
// 回報才發現的。這支把那個沉默失效換成吵鬧失效。
//
// 零相依(只用 node 內建),改完審核台就跑一次:
//     node script/text_rewrite/render_check.js .scratch/text-rewrite/review-41-monster-03.html
// 失敗時 exit code 1。
const fs = require("fs");
const path = process.argv[2];
if (!path) {
  console.error("用法: node render_check.js <審核台.html>");
  process.exit(2);
}
const html = fs.readFileSync(path, "utf8");

const dataText = /<script id="data" type="application\/json">([\s\S]*?)<\/script>/
  .exec(html)[1];
const blocks = [...html.matchAll(/<script>\n([\s\S]*?)<\/script>/g)].map(m => m[1]);
const js = blocks[blocks.length - 1];

function mkEl(tag) {
  return {
    tagName: tag, dataset: {}, style: {}, _html: "", _text: "",
    classList: { add() {}, remove() {} },
    get innerHTML() { return this._html; }, set innerHTML(v) { this._html = v; },
    get textContent() { return this._text; }, set textContent(v) { this._text = v; },
    setAttribute() {}, removeAttribute() {}, getAttribute() { return ""; },
    addEventListener() {}, appendChild() {}, insertBefore() {}, remove() {},
    querySelector() { return null; }, querySelectorAll() { return []; },
    closest() { return null; }, select() {}, matches() { return false; },
  };
}
const store = {};
const nodes = { data: { textContent: dataText } };
globalThis.localStorage = {
  getItem: k => (k in store ? store[k] : null),
  setItem: (k, v) => { store[k] = v; },
};
globalThis.navigator = {};
globalThis.document = {
  getElementById(id) { return nodes[id] || (nodes[id] = mkEl("div")); },
  querySelectorAll() { return []; },
  createElement: mkEl,
};

eval(js);

const stream = document.getElementById("stream").innerHTML;
const index = document.getElementById("index").innerHTML;
if (!stream || stream.length < 1000) {
  console.error(`FAIL ${path}: stream 沒有內容(${stream.length} bytes)`);
  process.exit(1);
}
if (!index || index.length < 500) {
  console.error(`FAIL ${path}: index 沒有內容(${index.length} bytes)`);
  process.exit(1);
}
const cards = JSON.parse(dataText).cards;
const missing = new Set();
for (const c of cards) {
  if (!stream.includes(`id="c${c.no}"`)) missing.add(c.no);
}
if (missing.size) {
  console.error(`FAIL ${path}: 缺卡 ${[...missing].join(",")}`);
  process.exit(1);
}
console.log(`OK ${path} — ${cards.length} 卡、stream ${stream.length} bytes`);
