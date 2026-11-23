'use strict';

/* 動作條件與動作索引(action-search-web 票 08 起)。

   - 動作條件:玩家介面填的東西,`{ actions: [動作詞…], from, to: { zone, side }, kinds: [勾選],
     pol }`(從起的四個是票 09);之後的票各往這裡加一個欄位(誰…),各自在 condOf、count、
     rowQuery 加一行。
   - 列查詢:動作條件換成比對列用的查詢,鍵名與值照 Python 的 `run_query`(`row_match`)。
     玩家介面不露出的選項在這裡用固定值;「兩邊答案一致」的測試把同一份列查詢交給
     `run_query`,所以兩邊比的是同一個問題。
   - 動作索引:`web/action-data.js` 的 `window.ACTION_DATA`(格式見
     `script/action_structure/action_index.py`);prepare 讀成比對用的形狀,match 只比對列,
     不解讀卡片結構。 */
const Action = (() => {

/* 玩家介面的段類別三個勾選與極性三選一(spec「玩家介面」的對應表;票 09)。召喚手續、限制
   跟著效果算。預設勾效果與代價、極性「會做」;正規形不寫預設值。 */
const KINDS = { eff: ['效果', '召喚手續', '限制'], cost: ['代價'], cond: ['條件'] };
const KIND_KEYS = Object.keys(KINDS);
const DEFAULT_KINDS = ['eff', 'cost'];
const POLARITIES = { do: ['做', '可以', '必須'], limit: ['不能', '只能'], resist: ['不會'] };
const DEFAULT_POL = 'do';

/* 「更多」以外直接顯示的動作詞數:常用的一屏看得完,其餘收起來。 */
const SHOWN_WORDS = 14;

const isObj = v => v != null && typeof v === 'object' && !Array.isArray(v);

/* 從、到可以再指定的方(票 09):玩家介面只問我方或對手。 */
const SIDES = ['我方', '對手'];
/* 產物的區域碼 = 區域位置 × 8 + 方的位置(`action_index.SIDE_SLOTS`)。 */
const SIDE_SLOTS = 8;

/* 從、到的正規形:`{ zone }` 或 `{ zone, side }`;區域不是字串就整欄不算,方認不得就不限。 */
function zoneOf(raw) {
  if (!isObj(raw) || typeof raw.zone !== 'string' || !raw.zone.trim()) return null;
  const z = { zone: raw.zone.trim() };
  if (SIDES.indexOf(raw.side) >= 0) z.side = raw.side;
  return z;
}

/* 正規形:同一組條件只有一種寫法(動作詞去重、照字串排),瀏覽紀錄比得出「這次搜尋與
   上一筆相同」。認不得的欄位或值忽略;一個欄位都沒有就是 null(沒有動作條件)。 */
function condOf(raw) {
  if (!isObj(raw)) return null;
  const c = {};
  const actions = Array.isArray(raw.actions) ? Array.from(new Set(
    raw.actions.filter(a => typeof a === 'string' && a.trim()).map(a => a.trim()))).sort() : [];
  if (actions.length) c.actions = actions;
  const from = zoneOf(raw.from);
  if (from) c.from = from;
  const to = zoneOf(raw.to);
  if (to) c.to = to;
  const kinds = kindsOf(raw.kinds);
  if (kinds.join() !== DEFAULT_KINDS.join()) c.kinds = kinds;
  if (raw.pol !== DEFAULT_POL && POLARITIES[raw.pol]) c.pol = raw.pol;
  return Object.keys(c).length ? c : null;
}

/* 生效中的動作條件數(窄螢幕摺疊鈕上的數字):一個欄位算一條,動作詞選幾個都是一條。 */
function count(cond) {
  const c = condOf(cond);
  return c ? Object.keys(c).length : 0;
}

/* 段類別勾選的正規形:照 KIND_KEYS 的順序;認不得的勾選忽略,一個都沒有就是預設
   (介面不讓全部取消,舊紀錄或壞掉的值才會走到這裡)。 */
function kindsOf(raw) {
  const kinds = Array.isArray(raw) ? KIND_KEYS.filter(k => raw.indexOf(k) >= 0) : [];
  return kinds.length ? kinds : DEFAULT_KINDS;
}

/* 從、到換成 `run_query` 的 from_zones / to_zones:沒指定方時只比區域。 */
const zoneQuery = z => [{ zone: z.zone, side: z.side || null }];

function rowQuery(cond) {
  const c = condOf(cond) || {};
  const kinds = kindsOf(c.kinds);
  const rq = {
    actions: c.actions || [],
    kinds: kinds.flatMap(k => KINDS[k]),
    polarities: POLARITIES[c.pol || DEFAULT_POL],
  };
  // Python 的條件段開關關著時會把 條件 從段類別拿掉,所以勾觸發條件要連開關一起開
  if (kinds.indexOf('cond') >= 0) rq.include_condition = true;
  if (c.from) rq.from_zones = zoneQuery(c.from);
  if (c.to) rq.to_zones = zoneQuery(c.to);
  return rq;
}

/* 線:[旗標, 從, 到, 物件];從、到是 0 或 [推得, 區域碼…],物件是 0(找不到)或 [泛用, 集合鍵]。 */
function lineOf([flags, from, to, obj]) {
  const position = p => (p === 0 ? null : { inferred: !!p[0], codes: p.slice(1) });
  return { doer: !!(flags & 1), from: position(from), to: position(to), object: obj !== 0 };
}

/* 產物 → 比對用的形狀:值的清單換成「值 → 位置」,段只留比對要用的欄。 */
function prepare(raw) {
  const at = list => new Map(list.map((v, i) => [v, i]));
  return {
    words: raw.actions,
    zones: raw.zones,
    actionAt: at(raw.actions.map(a => a[0])),
    kindAt: at(raw.kinds),
    polarityAt: at(raw.polarities),
    zoneAt: at(raw.zones.map(z => z[0])),
    sideAt: at(raw.sides),
    cards: raw.cards.map(([id, , segments]) => ({
      id,
      segments: segments.map(([seg, , kind, polarity, replacing, actions, lines]) =>
        ({ id: seg, kind, polarity, replacing: !!replacing, actions, lines: lines.map(lineOf) })),
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

/* 從、到的區域選項:索引的區域表依列數排(同列數照索引的順序)。 */
function zoneOptions(index) {
  return index.zones.map((z, i) => ({ zone: z[0], rows: z[1], i }))
    .sort((a, b) => b.rows - a.rows || a.i - b.i)
    .map(z => z.zone);
}

/* 段類別勾選點一下:勾上或取消;只剩一個勾著時不能取消(spec 第二題,裁定 (a))。 */
function toggleKind(kinds, kind) {
  const now = kindsOf(kinds);
  if (now.indexOf(kind) < 0) return kindsOf(now.concat(kind));
  return now.length > 1 ? now.filter(k => k !== kind) : now;
}

function positions(map, values) {
  return values.map(v => map.get(v));
}

/* 從、到的查詢 → 這一欄要的區域碼判斷;索引裡沒有的區域或方什麼都不中。
   推得的值不算(玩家介面的推得終點開關固定關)。 */
function zoneTest(index, want) {
  if (!want) return null;
  const fits = want.map(({ zone, side }) => {
    const z = index.zoneAt.get(zone);
    const s = side == null ? null : index.sideAt.get(side);
    if (z === undefined || s === undefined) return () => false;
    return s === null
      ? code => Math.floor(code / SIDE_SLOTS) === z
      : code => code === z * SIDE_SLOTS + s;
  });
  return pos => !!pos && !pos.inferred && pos.codes.some(code => fits.some(f => f(code)));
}

/* 線的條件(從、到…)要落在同一條線上:做動作的一方那條線、物件表裡找不到的線不算
   (照 `row_match._line_matches`)。沒有線的條件時回 null,段不必看線。 */
function lineTest(index, rq) {
  const from = zoneTest(index, rq.from_zones);
  const to = zoneTest(index, rq.to_zones);
  if (!from && !to) return null;
  return line => !line.doer && line.object
    && (!from || from(line.from)) && (!to || to(line.to));
}

/* 列查詢 → 命中的卡:Map(卡號 → 命中的段)。判法照 `row_match`:段類別、極性在範圍裡,
   查詢的動作詞全部在同一段裡。做代替的段只在查詢含代替時看(玩家介面不看代替)。
   索引裡沒有的動作詞沒有卡命中。 */
function match(index, rq) {
  const hits = new Map();
  const wanted = positions(index.actionAt, rq.actions);
  if (wanted.some(a => a === undefined)) return hits;
  const kinds = new Set(positions(index.kindAt, rq.include_condition
    ? rq.kinds : rq.kinds.filter(k => k !== '條件')));
  const polarities = new Set(positions(index.polarityAt, rq.polarities));
  const lineFits = lineTest(index, rq);
  for (const card of index.cards) {
    for (const seg of card.segments) {
      if (seg.replacing || !kinds.has(seg.kind) || !polarities.has(seg.polarity)) continue;
      if (!wanted.every(a => seg.actions.indexOf(a) >= 0)) continue;
      if (lineFits && !seg.lines.some(lineFits)) continue;
      if (!hits.has(card.id)) hits.set(card.id, []);
      hits.get(card.id).push(seg);
    }
  }
  return hits;
}

  return Object.freeze({ condOf, count, rowQuery, prepare, options, match,
    SIDES, DEFAULT_KINDS, DEFAULT_POL, zoneOptions, toggleKind });
})();
