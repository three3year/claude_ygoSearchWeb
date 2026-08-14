/**
 * util.js — 共用工具與常數表(DOM 快捷、esc、值域中文表)
 *
 * 載入順序:data -> util -> sort -> engine -> query -> render -> main
 * (見 index.html 的 <script> 順序)。
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
/* 宣告序本身(碼的順序)。**領域序排序的比較序就是它**——排序另抄一份順序表的話,
   在正典裡調一個種族的位置,按鈕會動而畫面上的順序不會動(sort.js)。 */
function codesOf(name) {
  return ((VOCAB[name] || {}).items || []).map(e => e.code);
}
const CAT_ZH = zhTable('cat');
const KIND_ZH = zhTable('kind');
const ATTR_ZH = zhTable('attr');
const RACE_ZH = zhTable('race');
const ROLE_ZH = zhTable('role');
const OPT_ZH = zhTable('optional');
const OT_ZH = zhTable('ot');
/* 連結標記的中文就是箭頭字元(↖↑↗…),宣告序就是九宮格由左上到右下的讀法 */
const LM_ZH = zhTable('lm');
const LM_CODES = codesOf('lm');
/* 子類型一側一份:同一個碼在怪獸側是儀式怪獸、在魔法側是儀式魔法,
   讀哪一份由卡片的大類決定(CONTEXT.md「卡片子類型」) */
const SUB_ZH = { m: zhTable('sub_m'), s: zhTable('sub_s'), t: zhTable('sub_t') };

const $ = id => document.getElementById(id);

function esc(s) {
  return String(s).replace(/[&<>"]/g, m =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[m]));
}

/* 卡片密碼顯示時補零成 8 位(卡面左下角就是 8 位數) */
const pad8 = id => String(id).padStart(8, '0');

/* 密碼 → 卡片。異圖切換要從點下去的那張卡取回異圖清單,線性掃 14,207 筆
   在每次點擊上都做一遍是沒必要的浪費。 */
const INDEX = new Map(DB.map(c => [c.id, c]));
const byId = id => INDEX.get(+id);

  return Object.freeze({
    DB, META, VOCAB,
    CAT_ZH, KIND_ZH, ATTR_ZH, RACE_ZH, ROLE_ZH, OPT_ZH, OT_ZH, LM_ZH, LM_CODES,
    SUB_ZH,
    zhTable, codesOf, $, esc, pad8, byId,
  });
})();
