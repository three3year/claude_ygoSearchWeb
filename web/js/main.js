'use strict';

(() => {
const { DB, META, $, fmtTime } = Util;

/* 目前這一筆瀏覽紀錄存的查詢狀態(正規形的 JSON)。搜尋與它相同時不新增一筆,
   上一頁才不會停在同一個查詢上。 */
let applied = '';

let appliedQuery = null;

let appliedAct = null;

/* 每次查詢一個序號:索引載入中又按了搜尋,載完只跑最後那一次。 */
let runs = 0;

/* 帶動作條件、動作索引還沒載完:先顯示載入中,載完自動查。載入失敗時動作條件不生效,
   其他條件照常(區塊裡有說明)。 */
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

/* 索引載入失敗時動作條件不生效:摺疊鈕上的條件數也不算它。 */
function show() {
  const index = ActionPanel.index();
  const act = index && appliedAct;
  Query.summarize(appliedQuery, act);
  View.render(Engine.runQuery(DB, appliedQuery, act, index));
}

/* 網址不帶任何參數:不給第三個引數,網址維持原樣。雙擊開啟(file://)也能用。 */
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

/* 舊版網站把條件寫在網址上(`#attr=dark…`),那種網址不解讀:顯示首頁、把參數
   清掉。只換網址、保留這一筆存的狀態——重新整理時狀態還在。 */
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
