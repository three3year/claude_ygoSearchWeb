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
    cards: raw.cards.map(([id, , segments, , , clauses]) => ({
      id,
      segments: segments.map(([seg, , kind, polarity, replacing, actions], i) =>
        ({ id: seg, kind, polarity, replacing: !!replacing, actions,
           clause: clauseAt(clauses, i) })),
    })),
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

/* 列查詢 → 命中的卡:Map(卡號 → 命中的段)。判法照 `row_match`:段類別、極性在範圍裡,
   查詢的動作詞全部在同一段裡。做代替的段只在查詢含代替時看(玩家介面不看代替)。
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
  return hits;
}

  return Object.freeze({ condOf, count, rowQuery, prepare, options, match });
})();
