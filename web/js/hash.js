/**
 * hash.js — 網址狀態(查詢條件＋排序 ⇄ `#hash`)
 *
 * **這一層是純的**:字串進、狀態出,不碰 DOM、不讀 `location`、不寫歷史。寫入的
 * 時機與 `hashchange` 的處理歸主流程(main.js),而編解碼本身在這裡——分享出去的
 * 網址在對方那邊還原成同一個查詢,靠的全是這一對函式,所以它們測得到
 * (`script/web/engine.test.js` 的往返測試)。
 *
 * **參數名就是查詢條件的鍵名,條件軸由 `Query.FIELDS` 導出**(ADR-0008 的同一條
 * 理由):加一個條件軸時網址自動認得它。抄一份對照表在這裡的話,新軸會安靜地
 * 不進網址——分享出去的連結少了一個條件,而收到連結的人不會知道少了什麼。
 *
 * 三條編碼語意:
 *
 * - **三態**:`attr=-light,dark` —— `-` 前綴是排除,沒有前綴是包含,不寫就是未選。
 *   三個狀態都寫得出來,才回得來(未選也是一個狀態,而它的寫法是「不出現」)。
 * - **範圍**:`atk=2500-` / `atk=-3000` / `atk=1000-2000` —— 只給一邊照樣是條件。
 *   這幾個參數都不是負數,所以中間那個 `-` 不會有第二種讀法。
 * - **可省略的一律省略**:預設語言、預設排序方向、未選的碼。網址短一點,而且
 *   同一個狀態只有一種寫法——`canon()` 因此問得出「這兩個網址是不是同一件事」。
 *
 * 分頁位置與每頁筆數**不進網址**:那是「這一頁看到哪」而不是「查了什麼」,
 * 把它們寫進去的話,分享出去的連結會連對方該從第幾頁開始看都替他決定了。
 */
'use strict';

const Hash = (() => {
const { VOCAB } = Util;

/* 自由文字欄位。參數名與查詢條件的鍵名同一個字,網址上看到 `name=` 的人不必
   先查一份對照表——少一份對照表就少一個會漂掉的東西。 */
const TEXTS = ['name', 'code', 'text'];
const LANG = 'nameLang';

/* 條件軸的參數表,**由 `Query.FIELDS` 導出**。子類型的三段(怪獸/魔法/陷阱)在
   查詢條件裡本來就是同一個軸(碼帶大類前綴),所以在網址上也是同一個參數。 */
function schema() {
  const tri = [], range = [];
  Query.FIELDS.forEach(f => {
    if (f.group) return;   // 僅摺疊分組的父層(禁限)沒有條件,不進網址
    if (!f.tri) { range.push({ key: f.range, unknown: f.unknown || '' }); return; }
    // 合法碼跟著**按鈕**走:有分組的值域取分組聯集——建置期把跨類型 0 張的
    // 效果類型值從分組拿掉、items 留作顯示詞彙表(ADR-0010),那種值在網址上
    // 視同未知碼。「UI 做不出來的狀態還原不回來」,與兩態軸丟排除段同一條規則。
    const dom = VOCAB[f.dom] || {};
    const source = (dom.groups || []).length
      ? dom.groups.reduce((all, g) => all.concat(g.codes), [])
      : (dom.items || []).map(it => it.code);
    const codes = source.map(code => (f.side ? f.side + ':' : '') + code);
    // 側分段軸(sub)的態數只讀**第一段**的宣告:三段是同一個軸,態數不該不同。
    // 若要把側分段軸兩態化,FIELDS 三段都要改——這裡不會替你合併第二段之後的宣告
    const ax = tri.find(a => a.key === f.tri);
    if (ax) ax.codes = ax.codes.concat(codes);
    else tri.push({ key: f.tri, codes, states: f.states || 3 });
  });
  return { tri, range };
}

const SCHEMA = schema();
const DEFAULT_LANG = Query.LANGS[0].v;
const DEFAULT_SORT = Sort.KEYS[0].key;

/* ── 正規化 ───────────────────────────────────────────── */

function langOf(v) {
  return (Query.LANGS.find(l => l.v === v) || Query.LANGS[0]).v;
}

/* 排序狀態的合法形狀由 `Sort.KEYS` 決定:認不得的鍵回領域序,沒有方向的鍵
   一律空方向,有方向的鍵給了怪值時回那個鍵的預設方向。「領域序＋降序」這種
   還原不回任何東西的組合因此進不來。 */
function sortOf(s) {
  const spec = Sort.specOf((s || {}).key);
  const dir = (s || {}).dir;
  return { key: spec.key,
           dir: spec.dir ? (dir === 'asc' || dir === 'desc' ? dir : spec.dir) : '' };
}

/* ── 序列化 ───────────────────────────────────────────── */

function numText(v) {
  return v == null ? '' : String(v);
}

/** `{ q, sort }` → `#hash` 的內容(不含開頭的 `#`)。空條件是空字串。 */
function stringify(state) {
  const st = state || {};
  const q = st.q || {};
  const parts = [];
  TEXTS.forEach(key => {
    const v = String(q[key] == null ? '' : q[key]).trim();
    if (v) parts.push(key + '=' + encodeURIComponent(v));
  });
  // 素材行開關:勾了才寫,與其他預設值同一條「可省略的一律省略」
  if (q.textMat) parts.push('textMat=1');
  if (langOf(q[LANG]) !== DEFAULT_LANG) parts.push(LANG + '=' + langOf(q[LANG]));
  SCHEMA.tri.forEach(ax => {
    const sel = q[ax.key];
    if (!sel) return;
    // 走**值域的宣告序**而不是使用者的點擊順序:同一組條件不論是怎麼點出來的,
    // 網址都是同一個字串,兩個人因此比得出來查的是不是同一件事
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

/* ── 解析 ─────────────────────────────────────────────── */

/* 壞掉的百分比編碼會讓 `decodeURIComponent` 丟例外。**一段壞掉不該讓整頁崩掉**
   ——那一段忽略,其餘條件照常生效(過期的網址通常只有一段對不上)。 */
function dec(v) {
  try { return decodeURIComponent(v); } catch (e) { return null; }
}

function toNum(s) {
  const t = String(s).trim();
  return t === '' || isNaN(+t) ? null : +t;
}

/* `min-max`,兩邊都可以空。兩邊都讀不出數字時回 null(這一段當作沒設)。 */
function toRange(v) {
  const i = v.indexOf('-');
  if (i < 0) return null;
  const min = toNum(v.slice(0, i)), max = toNum(v.slice(i + 1));
  return min == null && max == null ? null : { min, max };
}

/* 三態的碼清單。**不在值域裡的碼直接丟掉**:值域改過之後的舊網址(某個碼沒了)
   不該讓頁面崩掉,也不該變成一個沒有人選得出來的條件。兩態軸(大類,票12)的
   排除段同一個下場——`cat=-t` 還原不成任何 UI 做得出來的狀態。 */
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

/**
 * `#hash` → `{ q, sort }`。`q` 就是接縫 3 吃的查詢條件形狀(側欄吐出來的那一個),
 * 所以還原不必再翻譯一次。
 *
 * 認不得的欄位名、不在值域裡的值、讀不出數字的範圍**一律忽略該段**而不是丟例外:
 * 網址是使用者手上會被改到、也會過期的東西,而壞掉的一段不值得一片白畫面。
 */
function parse(hash) {
  const q = { name: '', nameLang: DEFAULT_LANG, code: '', text: '' };
  const raw = {};
  String(hash == null ? '' : hash).replace(/^#/, '').split('&').forEach(seg => {
    const i = seg.indexOf('=');
    if (i < 0) return;
    const key = seg.slice(0, i);
    if (!key) return;   // `=1` 這種沒有欄位名的段:比對不到任何一軸,別讓它進 q
    const v = dec(seg.slice(i + 1));
    if (v == null) return;
    if (TEXTS.indexOf(key) >= 0) { q[key] = v.trim(); return; }
    // 素材行開關只有「開」寫得出來(`textMat=1`),別的值視同壞段忽略
    if (key === 'textMat') { if (v === '1') q.textMat = 1; return; }
    if (key === LANG) { q[LANG] = langOf(v); return; }
    if (key === 'sort' || key === 'dir') { raw[key] = v; return; }
    const ax = SCHEMA.tri.find(a => a.key === key);
    if (ax) {
      const sel = toTri(v, ax);
      // 讀不出任何一個碼時不動原本的值:壞掉的一段不該把好的那一段也擦掉
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

/**
 * 網址的**正規形**:解析一遍再寫回去。
 *
 * 主流程靠它認出「這個 `hashchange` 是不是我自己剛寫進去的」。直接比字串不行——
 * 瀏覽器對 hash 的百分比編碼各有各的作法(有的原樣留著中文、有的編起來),自己
 * 寫進去的那一個讀回來會長得不一樣,於是被當成別人改的而重跑一次搜尋。
 */
function canon(hash) {
  return stringify(parse(hash));
}

  return Object.freeze({ stringify, parse, canon });
})();
