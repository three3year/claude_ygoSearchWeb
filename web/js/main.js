/**
 * main.js — 主流程(把條件側欄接上引擎與呈現層)
 *
 * **資料流單向**:側欄(唯一可變真相)→ Query.read() → Engine.runQuery(純函式)
 * → 產物 → View.render(無內部記憶)。沒有「上次查詢的中間結果」這種全域——
 * 要重畫就重跑一次導出。
 *
 * 空條件是合法的條件:一開站就是這個狀態,列出全部 14,207 張(不擋)。
 * 網址狀態(`#hash`)是票08,這裡還沒有。
 */
'use strict';

(() => {
const { DB, META, $ } = Util;

/* 搜尋 = 讀側欄 → 跑引擎 → 重畫。分頁位置歸 1:上一次翻到第 37 頁,新條件
   只有 12 張的話,留在第 37 頁看到的會是一片空白。 */
function search() {
  View.setPage(1);
  View.render(Engine.runQuery(DB, Query.read()));
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function init() {
  const built = META.built_at ? `・建置於 ${META.built_at}` : '';
  $('dbInfo').textContent =
    `${META.cards || DB.length} 張卡・${META.clauses || 0} 個效果句${built}`;
  Query.init();
  View.initAltArt();
  $('btnSearch').addEventListener('click', search);
  // 清除條件後直接重搜:條件是空的,結果就是全部——把畫面留在上一次的結果上,
  // 使用者會以為條件還在
  $('btnClear').addEventListener('click', () => { Query.clear(); search(); });
  $('perPage').addEventListener('change', e => {
    View.setPerPage(+e.target.value);   // 換每頁筆數會回到第 1 頁
    View.render();
  });
  // 在條件側欄的輸入框按 Enter = 搜尋(分頁器的頁碼框不在側欄裡,不受影響)
  $('sidebar').addEventListener('keydown', e => {
    if (e.key === 'Enter' && e.target.tagName === 'INPUT') search();
  });
  search();
}

document.addEventListener('DOMContentLoaded', init);
})();
