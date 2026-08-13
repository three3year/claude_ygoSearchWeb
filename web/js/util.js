/**
 * util.js — 共用工具與常數表(DOM 快捷、esc、值域中文表)
 *
 * 載入順序:data -> util -> render -> main(見 index.html 的 <script> 順序)。
 *
 * 模組介面凍結:內部關在閉包裡,外面只看得到 Util 這個凍結物件。零建置協定
 * (ADR-0007)下沒有模組系統,顯式掛載的介面就是唯一的邊界。
 */
'use strict';

const Util = (() => {

const DB = window.CARD_DATA || [];
const META = window.META || {};
const VOCAB = window.VOCAB || {};

/* 碼 → 中文一律由 window.VOCAB 導出(值域正典住建置期,ADR-0008)。
   在這裡手抄一份的話,新增一個種族時 VOCAB 有、這裡沒有,那批卡在畫面上就
   沒有名字——與「漏一個碼、某批卡從搜尋結果消失」是同一個失效模式。 */
function zhTable(name) {
  const table = {};
  ((VOCAB[name] || {}).items || []).forEach(e => { table[e.code] = e.zh; });
  return table;
}
const CAT_ZH = zhTable('cat');
const KIND_ZH = zhTable('kind');

const $ = id => document.getElementById(id);

function esc(s) {
  return String(s).replace(/[&<>"]/g, m =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[m]));
}

/* 卡片密碼顯示時補零成 8 位(卡面左下角就是 8 位數) */
const pad8 = id => String(id).padStart(8, '0');

  return Object.freeze({
    DB, META, VOCAB, CAT_ZH, KIND_ZH, zhTable, $, esc, pad8,
  });
})();
