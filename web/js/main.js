'use strict';

(() => {
const { DB, META, $, fmtTime } = Util;

let applied = '';

let appliedQuery = null;

let appliedAct = null;

let runs = 0;

function run() {
  appliedQuery = Query.read();
  appliedAct = ActionPanel.read();
  Query.summarize(appliedQuery, appliedAct);
  const seq = ++runs;
  if (appliedAct && !ActionPanel.index() && !ActionPanel.failed()) {
    View.renderLoading();
    ActionPanel.load().then(() => { if (seq === runs) show(); });
    return;
  }
  show();
}

function show() {
  const index = ActionPanel.index();
  const act = index && appliedAct;
  Query.summarize(appliedQuery, act);
  View.render(Engine.runQuery(DB, appliedQuery, act, index));
}

function push() {
  const state = Saved.snapshot(appliedQuery, View.sort(), appliedAct);
  const json = JSON.stringify(state);
  if (json === applied) return;
  applied = json;
  history.pushState(state, '');
}

function search() {
  View.setPage(1);
  run();
  push();
  Query.collapse();
  window.scrollTo(0, 0);
}

function restore(raw) {
  const state = Saved.restore(raw);
  applied = JSON.stringify(state);
  Query.write(state.q);
  ActionPanel.write(state.act);
  View.setSort(state.sort.key, state.sort.dir);
  View.setPage(1);
  if (Query.count(state.q, state.act)) { run(); return; }
  runs++;
  appliedQuery = state.q;
  appliedAct = null;
  Query.summarize(appliedQuery);
  View.render(null);
}

function clearUrl() {
  if (!location.search && !location.hash) return;
  history.replaceState(history.state, '', location.href.split(/[?#]/)[0]);
}

function renderSources() {
  const line = $('dataSources');
  line.append('資料來源：');
  Sites.FOOTER.forEach((s, i) => {
    if (i) line.append(' · ');
    const a = document.createElement('a');
    a.href = s.url;
    a.target = '_blank';
    a.rel = Sites.LINK_REL;
    a.title = `資料來源：${s.site}`;
    a.textContent = s.label;
    line.append(a);
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
  renderSources();
  Query.init();
  ActionPanel.init();
  View.initAltArt();
  View.initEffKind();
  View.initOgToggle();
  View.initSort(push);
  $('btnSearch').addEventListener('click', search);
  $('btnClear').addEventListener('click', () => { Query.clear(); ActionPanel.clear(); });
  $('perPage').addEventListener('change', e => {
    View.setPerPage(+e.target.value);
    View.render();
  });
  $('sidebar').addEventListener('keydown', e => {
    if (e.key === 'Enter' && e.target.tagName === 'INPUT') search();
  });
  window.addEventListener('popstate', e => { clearUrl(); restore(e.state); });
  clearUrl();
  restore(history.state);
}

document.addEventListener('DOMContentLoaded', init);
})();
