'use strict';

const Saved = (() => {
const { VOCAB, isObj } = Util;

const TEXTS = ['name', 'code', 'text'];

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

function snapshot(q, sort, act) {
  return restore({ q, sort, act });
}

  return Object.freeze({ snapshot, restore });
})();
