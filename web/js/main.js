'use strict';

/* 主流程:條件一變就重查(規格 4 票 02)。離散操作立刻重查、歷史留一筆;打字與數字範圍
   延遲 150 ms、改寫目前這一筆;重查回第 1 頁、不捲動。動作標籤的狀態在這裡,左側條件的
   狀態在側欄 DOM,兩者由條件模型組成引擎查詢。 */
(() => {
const { DB, META, $, fmtTime } = Util;

const TYPING_DELAY_MS = 150;

let cond = Cond.empty();
let applied = '';
let typingTimer = null;

function currentHash() {
  return Hash.stringify({ q: Query.read(), cond, sort: View.sort() });
}

function sameAsAddress(hash) {
  return hash === String(location.hash).replace(/^#/, '');
}

function pushEntry() {
  const hash = applied = currentHash();
  if (!sameAsAddress(hash)) location.hash = hash;   // 指派即留一筆歷史:上一頁回得到前一次
}

function replaceEntry() {
  const hash = applied = currentHash();
  if (!sameAsAddress(hash)) location.replace('#' + hash);
}

/* 沒有條件時不跑引擎:結果區顯示提示字,不是列出全部卡。 */
function show() {
  const side = Query.read();
  const n = Query.count(side) + Cond.tags(cond).length;
  Strip.render(cond);
  Query.markUsed(Cond.usedPaths(cond));
  Query.summarize(n);
  View.render(n ? Engine.runQuery(DB, Cond.toQuery(cond, side)) : null);
}

function requery(record) {
  clearTimeout(typingTimer);
  View.setPage(1);
  show();
  record();
}

function requerySoon() {
  clearTimeout(typingTimer);
  typingTimer = setTimeout(() => requery(replaceEntry), TYPING_DELAY_MS);
}

function setCond(next) {
  cond = next;
  requery(pushEntry);
}

function restore() {
  clearTimeout(typingTimer);
  const state = Hash.parse(location.hash);
  cond = state.cond || Cond.empty();
  Strip.closeDrawer();
  Query.write(state.q);
  View.setSort(state.sort.key, state.sort.dir);
  View.setPage(1);
  show();
}

function onHashChange() {
  const hash = Hash.canon(location.hash);
  if (hash === applied) return;
  applied = hash;
  restore();
}

function initSidebarEvents() {
  const sidebar = $('sidebar');
  sidebar.addEventListener('click', e => {
    if (e.target.closest('.tri, .axis-clear, #fNameLang')) requery(pushEntry);
  });
  sidebar.addEventListener('input', e => {
    if (e.target.matches('#fName, #fId, #fText, .range-in')) requerySoon();
  });
  sidebar.addEventListener('change', e => {
    if (e.target.id === 'fTextMat') requery(pushEntry);
  });
  sidebar.addEventListener('keydown', e => {
    if (e.key !== 'Enter' || !e.target.matches('#fName, #fId, #fText, .range-in')) return;
    requery(replaceEntry);
    Query.collapse();
  });
}

function init() {
  $('dbInfo').textContent =
    `${META.cards || DB.length} 張卡・${META.clauses || 0} 個效果句`;
  if (META.data_updated_at) {
    const updated = $('dataUpdated');
    updated.textContent = `資料更新時間：${fmtTime(META.data_updated_at)}`;
    updated.hidden = false;
  }
  Query.init({ onPick: (path, ex) => setCond(Cond.add(cond, Cond.tagAt(path, ex))) });
  Strip.init({
    onRemove: i => setCond(Cond.removeAt(cond, i)),
    onEdit: (i, tag) => setCond(Cond.replaceAt(cond, i, tag)),
    countOf: tag => Engine.runQuery(DB, Cond.soloQuery(tag)).cards.length,
  });
  View.initAltArt();
  View.initEffKind();
  View.initOgToggle();
  View.initSort(pushEntry);
  $('btnSearch').addEventListener('click', () => {
    requery(pushEntry);
    Query.collapse();
  });
  $('btnClear').addEventListener('click', () => {
    Query.clear();
    setCond(Cond.empty());
  });
  $('perPage').addEventListener('change', e => {
    View.setPerPage(+e.target.value);
    View.render();
  });
  initSidebarEvents();
  window.addEventListener('hashchange', onHashChange);
  applied = Hash.canon(location.hash);
  restore();
}

document.addEventListener('DOMContentLoaded', init);
})();
