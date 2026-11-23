'use strict';

/* 動作條件與動作索引(action-search-web 票 08 起)。

   - 動作條件:玩家介面填的東西,`{ actions: [動作詞…] }`;之後的票各往這裡加一個欄位
     (段類別、極性、從/到、誰…),各自在 condOf、count、rowQuery 加一行。
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

/* 正規形:同一組條件只有一種寫法(動作詞去重、照字串排),瀏覽紀錄比得出「這次搜尋與
   上一筆相同」。認不得的欄位或值忽略;一個欄位都沒有就是 null(沒有動作條件)。 */
function condOf(raw) {
  if (!isObj(raw) || !Array.isArray(raw.actions)) return null;
  const actions = Array.from(new Set(
    raw.actions.filter(a => typeof a === 'string' && a.trim()).map(a => a.trim()))).sort();
  return actions.length ? { actions } : null;
}

/* 生效中的動作條件數(窄螢幕摺疊鈕上的數字):一個欄位算一條,動作詞選幾個都是一條。 */
function count(cond) {
  const c = condOf(cond);
  return c ? 1 : 0;
}

function rowQuery(cond) {
  const c = condOf(cond) || { actions: [] };
  return {
    actions: c.actions,
    kinds: KINDS.eff.concat(KINDS.cost),
    polarities: POLARITIES.do,
  };
}

/* 段對回的效果句序號(前端索引 `tx` 的位置,票 07 的「效果」格);對不回或舊產物沒有這格是 null。 */
function clauseAt(clauses, i) {
  const c = clauses && clauses[i];
  return c == null ? null : c;
}

/* 產物 → 比對用的形狀:值的清單換成「值 → 位置」,段只留比對要用的欄。 */
function prepare(raw) {
  const at = list => new Map(list.map((v, i) => [v, i]));
  return {
    words: raw.actions,
    actionAt: at(raw.actions.map(a => a[0])),
    kindAt: at(raw.kinds),
    polarityAt: at(raw.polarities),
    cards: raw.cards.map(([id, , segments, unresolved, , clauses]) => ({
      id,
      segments: segments.map(([seg, block, kind, polarity, replacing, actions], i) =>
        ({ id: seg, block, kind, polarity, replacing: !!replacing, actions,
           clause: clauseAt(clauses, i) })),
      unresolved: (unresolved || []).map(([kind, polarity, , flags, actions]) =>
        ({ kind, polarity, flags, actions })),
    })),
    noText: raw.noText || [],
    refs: references(raw),
  };
}

/* 引用列(票 14):卡號 → 它的引用列 [{ block, generic, key, part, clause }];
   候選卡集合用到才解碼(泛用引用的集合上千張,固定關,不解碼)。
   指定的部分:`parts[part]` 列了的候選卡只看那幾個區塊,沒列的看整張(blocksOf 回 null)。 */
function references(raw) {
  const of = new Map();
  for (const [id, , , , refs] of raw.cards) {
    if (refs && refs.length) {
      of.set(id, refs.map(([block, generic, key, part, clause]) =>
        ({ block, generic: !!generic, key, part, clause })));
    }
  }
  const parts = raw.parts.map(([, entries]) =>
    new Map(entries.map(([p, blocks]) => [raw.ids[p], blocks])));
  const decoded = new Map();
  return {
    of,
    blocksOf: (id, part) => parts[part].get(id) || null,
    candidates(key) {
      if (!decoded.has(key)) decoded.set(key, decodeSet(raw.sets[key], raw.ids));
      return decoded.get(key);
    },
  };
}

/* 候選卡集合 → 卡號:位置的清單,或位元集(第 i 位 = 位置 i,little-endian,base64)。 */
function decodeSet(value, ids) {
  if (Array.isArray(value)) return value.map(p => ids[p]);
  const bytes = atob(value);
  const out = [];
  for (let i = 0; i < bytes.length; i++) {
    const b = bytes.charCodeAt(i);
    for (let k = 0; k < 8; k++) if (b >> k & 1) out.push(ids[i * 8 + k]);
  }
  return out;
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

/* 列查詢 → 命中的卡:Map(卡號 → 命中的段;經引用的卡是引到命中的引用列,見 viaHits)。
   判法照 `row_match`:段類別、極性在範圍裡,查詢的動作詞全部在同一段裡。
   做代替的段只在查詢含代替時看(玩家介面不看代替)。
   索引裡沒有的動作詞沒有卡命中。 */
function match(index, rq) {
  const hits = new Map();
  const wanted = positions(index.actionAt, rq.actions);
  if (wanted.some(a => a === undefined)) return hits;
  const kinds = new Set(positions(index.kindAt, rq.kinds));
  const polarities = new Set(positions(index.polarityAt, rq.polarities));
  for (const card of index.cards) {
    for (const seg of card.segments) {
      if (seg.replacing || !kinds.has(seg.kind) || !polarities.has(seg.polarity)) continue;
      if (!wanted.every(a => seg.actions.indexOf(a) >= 0)) continue;
      if (!hits.has(card.id)) hits.set(card.id, []);
      hits.get(card.id).push(seg);
    }
  }
  for (const [id, refs] of viaHits(index, hits)) hits.set(id, refs);
  return hits;
}

/* 未解析的來源的旗標(`action_index.py` 的 U_*)。 */
const U_REPLACING = 1, U_REASON = 4, U_REASON_SUBSTITUTING = 8, U_REFERENCE = 16;

/* 列查詢 → 未解析組的卡號(Set)。判法照 `row_match._unparsed`:無官方日文的卡一律列;
   查詢有動作詞時,沒命中(不在 found 裡)的卡裡,字面含查詢的全部動作詞、在這個查詢下
   判不了的未解析的來源。段類別、極性(與代替)的篩選照樣生效,引用節點不看這兩欄;
   誰、受方、原因、從、到這些欄未解析的來源沒有,不比。查詢要代入卡(指定卡、給條件)時
   看「代入卡時判不了」的旗標,物件判不了的線在這時才判不了。
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

/* ── 經引用(票 14)────────────────────────────────────────
   直接沒命中、有引用列的卡,沿引用列展開到底(被引用卡指定的部分裡有命中段就算),
   走到這條路上走過的卡就停;判法照 Python 的 `row_match._Expansion`。泛用引用固定關。
   命中的卡回「引到命中的引用列」:經引用的命中算在引用節點所在的效果上(`clause`)。
   被引用卡指定的部分看的是它的命中段;之後加區塊種類篩選時,被篩掉的段仍要算進
   blockHits(Python 同樣不看查詢的區塊種類),起點卡的引用列才照區塊種類篩。 */
function viaHits(index, direct) {
  const blockHits = new Map();
  for (const [id, segs] of direct) blockHits.set(id, new Set(segs.map(s => s.block)));
  const out = new Map();
  for (const [id, refs] of index.refs.of) {
    if (direct.has(id)) continue;
    const led = refs.filter(ref => leads(index, blockHits, ref, new Set([id])));
    if (led.length) {
      out.set(id, led.map(ref => ({ via: true, block: ref.block, clause: ref.clause })));
    }
  }
  return out;
}

/* 這條引用列走不走得到命中段;visiting 是這條路上走過的卡。 */
function leads(index, blockHits, ref, visiting) {
  if (ref.generic) return false;
  return index.refs.candidates(ref.key).some(cid =>
    !visiting.has(cid) && reaches(index, blockHits, cid, ref.part, visiting));
}

function reaches(index, blockHits, cid, part, visiting) {
  const blocks = index.refs.blocksOf(cid, part);
  const inPart = block => blocks === null || blocks.indexOf(block) >= 0;
  const hit = blockHits.get(cid);
  if (hit && Array.from(hit).some(inPart)) return true;
  const refs = (index.refs.of.get(cid) || []).filter(ref => inPart(ref.block));
  if (!refs.length) return false;
  visiting.add(cid);
  const found = refs.some(ref => leads(index, blockHits, ref, visiting));
  visiting.delete(cid);
  return found;
}

  return Object.freeze({ condOf, count, rowQuery, prepare, options, match, unsure });
})();
