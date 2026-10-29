'use strict';

(() => {
const { DB, META, $, fmtTime } = Util;

let applied = '';

let appliedQuery = null;

function run() {
  appliedQuery = Query.read();
  Query.summarize(appliedQuery);
  View.render(Engine.runQuery(DB, appliedQuery));
}

function push() {
  const hash = Hash.stringify({ q: appliedQuery, sort: View.sort() });
  applied = hash;
  if (hash === String(location.hash).replace(/^#/, '')) return;
  location.hash = hash;           // 指派即 pushState 語意:上一頁回得到前一次
}

function search() {
  View.setPage(1);
  run();
  push();
  Query.collapse();
  window.scrollTo(0, 0);
}

function restore() {
  const state = Hash.parse(location.hash);
  Query.write(state.q);
  View.setSort(state.sort.key, state.sort.dir);
  View.setPage(1);
  if (Query.count(state.q)) { run(); return; }
  appliedQuery = state.q;
  Query.summarize(appliedQuery);
  View.render(null);
}

function onHashChange() {
  const hash = Hash.canon(location.hash);
  if (hash === applied) return;
  applied = hash;
  restore();
}

function init() {
  $('dbInfo').textContent =
    `${META.cards || DB.length} 張卡・${META.clauses || 0} 個效果句`;
  if (META.data_updated_at) {
    const updated = $('dataUpdated');
    updated.textContent = `資料更新時間：${fmtTime(META.data_updated_at)}`;
    updated.hidden = false;
  }
  Query.init();
  View.initAltArt();
  View.initEffKind();
  View.initOgToggle();
  View.initSort(push);
  $('btnSearch').addEventListener('click', search);
  $('btnClear').addEventListener('click', () => Query.clear());
  $('perPage').addEventListener('change', e => {
    View.setPerPage(+e.target.value);
    View.render();
  });
  $('sidebar').addEventListener('keydown', e => {
    if (e.key === 'Enter' && e.target.tagName === 'INPUT') search();
  });
  window.addEventListener('hashchange', onHashChange);
  applied = Hash.canon(location.hash);
  restore();
}

document.addEventListener('DOMContentLoaded', init);
})();
