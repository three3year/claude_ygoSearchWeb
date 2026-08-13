/**
 * main.js — 主流程(把索引接上呈現層、綁畫面上的控制項)
 *
 * 這一票還沒有搜尋:列出索引裡的全部卡片就是全部的行為。條件表單、網址狀態與
 * 排序各自是後面的票,主流程屆時在這裡長出來。
 */
'use strict';

(() => {
const { DB, META, $ } = Util;

function init() {
  const built = META.built_at ? `・建置於 ${META.built_at}` : '';
  $('dbInfo').textContent =
    `${META.cards || DB.length} 張卡・${META.clauses || 0} 個效果句${built}`;
  $('perPage').addEventListener('change', e => {
    View.setPerPage(+e.target.value);   // 換每頁筆數會回到第 1 頁
    View.render();
  });
  View.initAltArt();
  View.render(DB);
}

document.addEventListener('DOMContentLoaded', init);
})();
