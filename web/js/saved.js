'use strict';

/* 存在瀏覽紀錄裡的查詢狀態(action-search-web 票01):`{ q, sort, act }`。
   網址不帶任何參數;每次搜尋把狀態存進瀏覽紀錄新增的那一筆,上一頁、下一頁、
   重新整理從那一筆還原。
   那一筆可能是舊版網站寫的(欄位改名、值域變了),甚至不是本站寫的:還原時
   **認不得的欄位或值忽略,其餘照常還原**——一個欄位對不上不該讓整頁壞掉。
   動作條件(票08)是 `{ q, sort }` 旁邊的 `act`,正規形由 `Action.condOf` 定;沒有動作條件
   時不寫這個鍵,舊的一筆沒有它就是沒有那組條件。 */
const Saved = (() => {
const { VOCAB } = Util;

const TEXTS = ['name', 'code', 'text'];

/* 每條條件軸的合法碼跟著按鈕走(分組聯集,沒有分組才看 items):UI 做不出來
   的狀態還原不回來。被建置期拿掉按鈕的值(ADR-0010)因此視同未知碼。 */
function schema() {
  const tri = [], range = [];
  Query.FIELDS.forEach(f => {
    if (f.group) return;
    if (!f.tri) { range.push({ key: f.range, unknown: f.unknown || '' }); return; }
    const dom = VOCAB[f.dom] || {};
    const source = (dom.groups || []).length
      ? dom.groups.reduce((all, g) => all.concat(g.codes), [])
      : (dom.items || []).map(it => it.code);
    const codes = source.map(code => (f.side ? f.side + ':' : '') + code);
    const ax = tri.find(a => a.key === f.tri);
    if (ax) ax.codes = ax.codes.concat(codes);
    else tri.push({ key: f.tri, codes, states: f.states || 3 });
  });
  return { tri, range };
}

const SCHEMA = schema();

const isObj = v => v != null && typeof v === 'object' && !Array.isArray(v);

function langOf(v) {
  return (Query.LANGS.find(l => l.v === v) || Query.LANGS[0]).v;
}

function sortOf(s) {
  const st = isObj(s) ? s : {};
  const spec = Sort.specOf(st.key);
  const dir = st.dir;
  return { key: spec.key,
           dir: spec.dir ? (dir === 'asc' || dir === 'desc' ? dir : spec.dir) : '' };
}

/* 碼照宣告序取:同一組條件只有一種寫法,比得出「這次搜尋與上一筆相同」。 */
function triOf(v, ax) {
  if (!isObj(v)) return null;
  const sel = {};
  ax.codes.forEach(code => {
    if (v[code] === 1 || (v[code] === -1 && ax.states === 3)) sel[code] = v[code];
  });
  return Object.keys(sel).length ? sel : null;
}

const numOf = v => (typeof v === 'number' && isFinite(v) ? v : null);

function rangeOf(v) {
  if (!isObj(v)) return null;
  const min = numOf(v.min), max = numOf(v.max);
  return min == null && max == null ? null : { min, max };
}

function queryOf(raw) {
  const src = isObj(raw) ? raw : {};
  const q = {};
  TEXTS.forEach(key => {
    q[key] = typeof src[key] === 'string' ? src[key].trim() : '';
  });
  q.nameLang = langOf(src.nameLang);
  if (src.textMat === 1) q.textMat = 1;
  SCHEMA.tri.forEach(ax => {
    const sel = triOf(src[ax.key], ax);
    if (sel) q[ax.key] = sel;
  });
  SCHEMA.range.forEach(f => {
    const r = rangeOf(src[f.key]);
    if (r) q[f.key] = r;
    const u = f.unknown && src[f.unknown];
    if (u === 1 || u === -1) q[f.unknown] = u;
  });
  return q;
}

function restore(raw) {
  const st = isObj(raw) ? raw : {};
  const out = { q: queryOf(st.q), sort: sortOf(st.sort) };
  const act = Action.condOf(st.act);
  if (act) out.act = act;
  return out;
}

/* 存進去的就是還原後的正規形:兩筆相同的查詢存成同一個樣子。 */
function snapshot(q, sort, act) {
  return restore({ q, sort, act });
}

  return Object.freeze({ snapshot, restore });
})();
