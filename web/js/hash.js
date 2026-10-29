'use strict';

const Hash = (() => {
const { VOCAB } = Util;

const TEXTS = ['name', 'code', 'text'];
const LANG = 'nameLang';

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
const DEFAULT_LANG = Query.LANGS[0].v;
const DEFAULT_SORT = Sort.KEYS[0].key;

const PARAM_NAMES = [].concat(
  TEXTS, ['textMat', LANG, 'sort', 'dir'],
  SCHEMA.tri.map(a => a.key),
  SCHEMA.range.map(f => f.key),
  SCHEMA.range.map(f => f.unknown).filter(Boolean)
);

/* 被轉傳端動過手腳的段分隔符:`&` 被多編一次成 `%26`(信箱、聊天軟體的連結
   包裝),或手打網址時輸入法吐出全形 `＆`/`＝`(瀏覽器會把它們編成
   `%EF%BC%86`/`%EF%BC%9D`)。不認回來的話,後面的整串條件會黏進文字欄位——
   效果文變成「墓地%…&kind=q,i」,一張卡都搜不到。
   只在後面跟著「認得的參數名＋等號」時才視同 `&`:自家 stringify 把文字裡的
   `=` 編成 `%3D`,所以真的想搜「A&kind=B」這種字面的網址不會被誤拆。 */
const MANGLED_SEP = new RegExp(
  '(?:%26|%EF%BC%86|＆)(' + PARAM_NAMES.join('|') + ')(?:=|＝|%EF%BC%9D)', 'gi');

function langOf(v) {
  return (Query.LANGS.find(l => l.v === v) || Query.LANGS[0]).v;
}

function sortOf(s) {
  const spec = Sort.specOf((s || {}).key);
  const dir = (s || {}).dir;
  return { key: spec.key,
           dir: spec.dir ? (dir === 'asc' || dir === 'desc' ? dir : spec.dir) : '' };
}

function numText(v) {
  return v == null ? '' : String(v);
}

function stringify(state) {
  const st = state || {};
  const q = st.q || {};
  const parts = [];
  TEXTS.forEach(key => {
    const v = String(q[key] == null ? '' : q[key]).trim();
    if (v) parts.push(key + '=' + encodeURIComponent(v));
  });
  if (q.textMat) parts.push('textMat=1');
  if (langOf(q[LANG]) !== DEFAULT_LANG) parts.push(LANG + '=' + langOf(q[LANG]));
  SCHEMA.tri.forEach(ax => {
    const sel = q[ax.key];
    if (!sel) return;
    const codes = ax.codes.filter(c => sel[c])
      .map(c => (sel[c] < 0 ? '-' : '') + c);
    if (codes.length) parts.push(ax.key + '=' + codes.join(','));
  });
  SCHEMA.range.forEach(f => {
    const r = q[f.key];
    if (r && (r.min != null || r.max != null)) {
      parts.push(f.key + '=' + numText(r.min) + '-' + numText(r.max));
    }
    const u = f.unknown && q[f.unknown];
    if (u) parts.push(f.unknown + '=' + (u < 0 ? '-1' : '1'));
  });
  const sort = sortOf(st.sort);
  if (sort.key !== DEFAULT_SORT) {
    parts.push('sort=' + sort.key);
    if (sort.dir !== Sort.specOf(sort.key).dir) parts.push('dir=' + sort.dir);
  }
  return parts.join('&');
}

/* 壞掉的百分比編碼會讓 `decodeURIComponent` 丟例外。最常見的壞法是網址在轉傳
   途中被解碼過一次(聊天軟體、信箱把 `%25` 還原成 `%` 再交給瀏覽器,瀏覽器只把
   中文編回去、裸 `%` 留著)——把不成對的 `%` 補回 `%25` 再解一次,萬用字元就
   救得回來。補救後仍解不開的才忽略該段:**一段壞掉不該讓整頁崩掉**,其餘條件
   照常生效(過期的網址通常只有一段對不上)。 */
function dec(v) {
  try { return decodeURIComponent(v); } catch (e) {}
  try { return decodeURIComponent(String(v).replace(/%(?![0-9A-Fa-f]{2})/g, '%25')); }
  catch (e) { return null; }
}

function toNum(s) {
  const t = String(s).trim();
  return t === '' || isNaN(+t) ? null : +t;
}

function toRange(v) {
  const i = v.indexOf('-');
  if (i < 0) return null;
  const min = toNum(v.slice(0, i)), max = toNum(v.slice(i + 1));
  return min == null && max == null ? null : { min, max };
}

function toTri(v, ax) {
  const sel = {};
  v.split(',').forEach(token => {
    const ex = token.charAt(0) === '-';
    const code = ex ? token.slice(1) : token;
    if (ex && ax.states === 2) return;
    if (code && ax.codes.indexOf(code) >= 0) sel[code] = ex ? -1 : 1;
  });
  return Object.keys(sel).length ? sel : null;
}

function parse(hash) {
  const q = { name: '', nameLang: DEFAULT_LANG, code: '', text: '' };
  const raw = {};
  String(hash == null ? '' : hash).replace(/^#/, '')
    .replace(MANGLED_SEP, '&$1=').split('&').forEach(seg => {
    const i = seg.indexOf('=');
    if (i < 0) return;
    const key = seg.slice(0, i);
    if (!key) return;
    const v = dec(seg.slice(i + 1));
    if (v == null) return;
    if (TEXTS.indexOf(key) >= 0) { q[key] = v.trim(); return; }
    if (key === 'textMat') { if (v === '1') q.textMat = 1; return; }
    if (key === LANG) { q[LANG] = langOf(v); return; }
    if (key === 'sort' || key === 'dir') { raw[key] = v; return; }
    const ax = SCHEMA.tri.find(a => a.key === key);
    if (ax) {
      const sel = toTri(v, ax);
      if (sel) q[key] = sel;
      return;
    }
    const range = SCHEMA.range.find(f => f.key === key);
    if (range) {
      const r = toRange(v);
      if (r) q[key] = r;
      return;
    }
    const unknown = SCHEMA.range.find(f => f.unknown === key);
    if (unknown && (v === '1' || v === '-1')) q[key] = +v;
  });
  return { q, sort: sortOf({ key: raw.sort, dir: raw.dir }) };
}

function canon(hash) {
  return stringify(parse(hash));
}

  return Object.freeze({ stringify, parse, canon });
})();
