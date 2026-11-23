'use strict';

/* 動作條件與動作索引(action-search-web 票 08 起)。

   - 動作條件:玩家介面填的東西,`{ actions: [動作詞…], target }`;之後的票各往這裡加一個欄位
     (段類別、極性、從/到、誰…),各自在 condOf、count、rowQuery 加一行。
     `target` 是被動作的卡(票 12):'self'(這張卡自己)或 `{ card: 卡號 }`(指定一張卡);
     一個欄位只放得下一種,三者擇一由形狀保證(給條件由票 13 加)。
   - 列查詢:動作條件換成比對列用的查詢,鍵名與值照 Python 的 `run_query`(`row_match`)。
     玩家介面不露出的選項在這裡用固定值;「兩邊答案一致」的測試把同一份列查詢交給
     `run_query`,所以兩邊比的是同一個問題。
   - 動作索引:`web/action-data.js` 的 `window.ACTION_DATA`(格式見
     `script/action_structure/action_index.py`);prepare 讀成比對用的形狀,match 只比對列,
     不解讀卡片結構。 */
const Action = (() => {

/* 玩家介面的段類別與極性(spec「玩家介面」的對應表)。這張票還沒有這兩個選項,
   比對用預設:勾效果與代價、極性「會做」。召喚手續、限制跟著效果算。 */
const KINDS = { eff: ['效果', '召喚手續', '限制'], cost: ['代價'] };
const POLARITIES = { do: ['做', '可以', '必須'] };

/* 「更多」以外直接顯示的動作詞數:常用的一屏看得完,其餘收起來。 */
const SHOWN_WORDS = 14;

const isObj = v => v != null && typeof v === 'object' && !Array.isArray(v);

/* 被動作的卡的正規形:'self' 或 `{ card: 正整數卡號 }`;其餘(舊版網站存的、壞掉的)是 null。 */
const TARGET_SELF = 'self';
function targetOf(raw) {
  if (raw === TARGET_SELF) return TARGET_SELF;
  if (isObj(raw) && Number.isInteger(raw.card) && raw.card > 0) return { card: raw.card };
  return null;
}

/* 正規形:同一組條件只有一種寫法(動作詞去重、照字串排),瀏覽紀錄比得出「這次搜尋與
   上一筆相同」。認不得的欄位或值忽略;一個欄位都沒有就是 null(沒有動作條件)。 */
function condOf(raw) {
  if (!isObj(raw)) return null;
  const out = {};
  const actions = Array.isArray(raw.actions) ? Array.from(new Set(
    raw.actions.filter(a => typeof a === 'string' && a.trim()).map(a => a.trim()))).sort() : [];
  if (actions.length) out.actions = actions;
  const target = targetOf(raw.target);
  if (target) out.target = target;
  return Object.keys(out).length ? out : null;
}

/* 生效中的動作條件數(窄螢幕摺疊鈕上的數字):一個欄位算一條,動作詞選幾個都是一條。 */
function count(cond) {
  const c = condOf(cond);
  return c ? Object.keys(c).length : 0;
}

function rowQuery(cond) {
  const c = condOf(cond) || {};
  const rq = {
    actions: c.actions || [],
    kinds: KINDS.eff.concat(KINDS.cost),
    polarities: POLARITIES.do,
  };
  if (c.target === TARGET_SELF) rq.this_card = true;
  else if (c.target) rq.card = c.target.card;
  return rq;
}

/* 卡名的建議清單(指定一張卡):中文名、日文名、英文名或別名含輸入字的卡,名字短的排前面
   (比的是對上的那個名字;同長照前端索引的順序),最多 `limit` 張。 */
const SUGGESTIONS = 12;
function suggest(db, text, limit) {
  const word = String(text || '').trim().toLowerCase();
  if (!word) return [];
  const found = [];
  db.forEach((c, i) => {
    const hit = [c.n, c.nj, c.ne, c.ax]
      .filter(n => typeof n === 'string' && n.toLowerCase().indexOf(word) >= 0);
    if (hit.length) found.push({ c, i, len: Math.min(...hit.map(n => n.length)) });
  });
  return found.sort((a, b) => a.len - b.len || a.i - b.i)
    .slice(0, limit || SUGGESTIONS)
    .map(f => ({ id: f.c.id, n: f.c.n, nj: f.c.nj || '' }));
}

/* 段對回的效果句序號(前端索引 `tx` 的位置,票 07 的「效果」格);對不回或舊產物沒有這格是 null。 */
function clauseAt(clauses, i) {
  const c = clauses && clauses[i];
  return c == null ? null : c;
}

/* 線的旗標與物件的種類碼(`action_index.py` 的 FLAG_DOER、OBJECT_CODES;沒寫種類是候選卡集合)。 */
const FLAG_DOER = 1;
const OBJECT_THIS = 1;

/* 線:做動作的一方、物件(null = 沒有物件;否則候選卡集合的鍵與種類)。 */
function lineOf([flags, , , obj]) {
  return { doer: !!(flags & FLAG_DOER),
           obj: obj === 0 ? null : { set: obj[1], kind: obj[2] || 0 } };
}

const B64 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';

/* 候選卡集合 → 測「前端位置 p 在不在裡面」的函式。清單是位置的陣列;位元集是 base64
   (第 i 位 = 位置 i,little-endian)。不靠 atob:node 的測試沙箱沒有它。 */
function memberTest(value) {
  if (Array.isArray(value)) {
    const set = new Set(value);
    return p => set.has(p);
  }
  const bytes = [];
  let bits = 0, acc = 0;
  for (const ch of value) {
    const v = B64.indexOf(ch);
    if (v < 0) continue;                    // '=' 補位
    acc = ((acc << 6) | v) & 0xffff;
    bits += 6;
    if (bits >= 8) { bits -= 8; bytes.push((acc >> bits) & 0xff); }
  }
  return p => (((bytes[p >> 3] || 0) >> (p & 7)) & 1) === 1;
}

/* 產物 → 比對用的形狀:值的清單換成「值 → 位置」,段只留比對要用的欄。 */
function prepare(raw) {
  const at = list => new Map(list.map((v, i) => [v, i]));
  const tests = new Map();
  return {
    cardAt: at(raw.ids),
    /* 候選卡集合 `key` 裡有沒有前端位置 p 的卡;集合用到才讀。 */
    inSet(key, p) {
      if (!tests.has(key)) tests.set(key, memberTest(raw.sets[key]));
      return tests.get(key)(p);
    },
    words: raw.actions,
    actionAt: at(raw.actions.map(a => a[0])),
    kindAt: at(raw.kinds),
    polarityAt: at(raw.polarities),
    cards: raw.cards.map(([id, , segments, unresolved, , clauses]) => ({
      id,
      segments: segments.map(([seg, , kind, polarity, replacing, actions, lines], i) =>
        ({ id: seg, kind, polarity, replacing: !!replacing, actions,
           lines: (lines || []).map(lineOf), clause: clauseAt(clauses, i) })),
      unresolved: (unresolved || []).map(([kind, polarity, , flags, actions]) =>
        ({ kind, polarity, flags, actions })),
    })),
    noText: raw.noText || [],
  };
}

/* 動作詞的選項:依列數排(同列數照索引的順序),前面一批直接顯示、其餘收在「更多」。
   0 列的詞只出現在解析不出的段的字面裡,選了也沒有卡命中,不列。 */
function options(index) {
  const words = index.words.filter(w => w[1] > 0)
    .map((w, i) => ({ word: w[0], rows: w[1], i }))
    .sort((a, b) => b.rows - a.rows || a.i - b.i)
    .map(w => w.word);
  return { shown: words.slice(0, SHOWN_WORDS), more: words.slice(SHOWN_WORDS) };
}

function positions(map, values) {
  return values.map(v => map.get(v));
}

/* 線的條件(照 `row_match._line_matches`):列查詢有線的條件時回「一條線符合嗎」,沒有時回
   null(不比線)。做動作的線不比;這張卡自己只認物件是此卡的線(條件式剛好讓這張卡滿足的
   不算);指定卡是那張卡在線的候選卡裡。沒有物件、判不了、代不進去的線都不符。 */
function lineTest(index, rq) {
  if (rq.this_card) return line => !line.doer && !!line.obj && line.obj.kind === OBJECT_THIS;
  if (rq.card != null) {
    const p = index.cardAt.get(rq.card);
    return line => !line.doer && !!line.obj && p !== undefined && index.inSet(line.obj.set, p);
  }
  return null;
}

/* 列查詢 → 命中的卡:Map(卡號 → 命中的段)。判法照 `row_match`:段類別、極性在範圍裡,
   查詢的動作詞全部在同一段裡,有線的條件時段裡要有一條線符合(`lineTest`)。
   做代替的段只在查詢含代替時看(玩家介面不看代替)。索引裡沒有的動作詞沒有卡命中。 */
function match(index, rq) {
  const hits = new Map();
  const wanted = positions(index.actionAt, rq.actions);
  if (wanted.some(a => a === undefined)) return hits;
  const kinds = new Set(positions(index.kindAt, rq.kinds));
  const polarities = new Set(positions(index.polarityAt, rq.polarities));
  const lineOk = lineTest(index, rq);
  for (const card of index.cards) {
    for (const seg of card.segments) {
      if (seg.replacing || !kinds.has(seg.kind) || !polarities.has(seg.polarity)) continue;
      if (!wanted.every(a => seg.actions.indexOf(a) >= 0)) continue;
      if (lineOk && !seg.lines.some(lineOk)) continue;
      if (!hits.has(card.id)) hits.set(card.id, []);
      hits.get(card.id).push(seg);
    }
  }
  return hits;
}

/* 未解析的來源的旗標(`action_index.py` 的 U_*)。 */
const U_REPLACING = 1, U_REASON = 4, U_REASON_SUBSTITUTING = 8, U_REFERENCE = 16;

/* 列查詢 → 未解析組的卡號(Set)。判法照 `row_match._unparsed`:無官方日文的卡一律列;
   查詢有動作詞時,沒命中(不在 found 裡)的卡裡,字面含查詢的全部動作詞、在這個查詢下
   判不了的未解析的來源。段類別、極性(與代替)的篩選照樣生效,引用節點不看這兩欄;
   誰、受方、原因、從、到這些欄未解析的來源沒有,不比。查詢要代入卡(指定卡、給條件)時
   看「代入卡時判不了」的旗標,物件判不了的線在這時才判不了。這張卡自己不代入卡(與 Python
   相同),看「不代入卡時判不了」的旗標:物件解析不出、引用的物件找不到的線照樣算(票 12)。
   found:命中的卡(有 `has` 就好),任一段命中的卡只在命中的清單。 */
function unsure(index, rq, found) {
  const out = new Set(index.noText.filter(id => !found.has(id)));
  if (!rq.actions.length) return out;
  const wanted = positions(index.actionAt, rq.actions);
  if (wanted.some(a => a === undefined)) return out;
  const kinds = new Set(positions(index.kindAt, rq.kinds));
  const polarities = new Set(positions(index.polarityAt, rq.polarities));
  const substituting = rq.card != null || rq.condition != null;
  const reason = substituting ? U_REASON_SUBSTITUTING : U_REASON;
  for (const card of index.cards) {
    if (found.has(card.id)) continue;
    for (const u of card.unresolved) {
      if (!(u.flags & reason) || !wanted.every(a => u.actions.indexOf(a) >= 0)) continue;
      if (!(u.flags & U_REFERENCE)) {
        if (u.flags & U_REPLACING && !rq.replacement) continue;
        if (!kinds.has(u.kind) || !polarities.has(u.polarity)) continue;
      }
      out.add(card.id);
      break;
    }
  }
  return out;
}

  return Object.freeze({ condOf, count, rowQuery, suggest, prepare, options, match, unsure });
})();
