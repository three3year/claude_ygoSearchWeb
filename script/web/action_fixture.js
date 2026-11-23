/**
 * action_fixture.js — 接縫三測試用的小動作索引(零 npm 依賴)
 *
 * 把讀得懂的描述 `[{ id, segs: [{ kind, pol, acts, replacing }] }]` 寫成
 * `web/action-data.js` 的格式(`script/action_structure/action_index.py` 的模組說明)。
 * 測試只寫「這張卡有哪些段、段裡有哪些動作詞」,不手抄編碼;格式由 Python 的建置
 * 產出、前端讀回,兩邊是否一致由「兩邊答案一致」的 Python 測試守住。
 */
'use strict';

function vocabOf(values) {
  return Array.from(new Set(values)).sort();
}

/* 位置的清單 → 位元集(第 i 位 = 位置 i,little-endian,base64),與建置產出的大集合同一寫法。 */
function bitset(positions) {
  const bytes = Buffer.alloc(Math.floor(Math.max(-1, ...positions) / 8) + 1);
  positions.forEach(p => { bytes[p >> 3] |= 1 << (p & 7); });
  return bytes.toString('base64');
}

/**
 * cards:[{ id, blocks = 1, segs: [{ kind = '效果', pol = '做', acts = [], replacing = false,
 *          block = 0 }], refs: [引用列] }]
 *   blocks:頂層區塊數;段的 block 是它在第幾個區塊。
 *   引用列(票 14):{ block = 0, to: [被引用的卡號], generic = false, part = {}, clause = null,
 *                     bits = false }
 *     part:被引用卡號 → 指定的部分是它的哪幾個區塊;沒列的卡看整張。
 *     bits:候選卡寫成位元集(大集合的寫法);否則寫位置的清單。
 * ids:前端索引的卡號順序(省略時照 cards)。
 */
function actionData(cards, ids) {
  const segs = cards.flatMap(c => c.segs.map(s => ({ kind: '效果', pol: '做', acts: [], ...s })));
  const actions = vocabOf(segs.flatMap(s => s.acts));
  const kinds = vocabOf(segs.map(s => s.kind));
  const polarities = vocabOf(segs.map(s => s.pol));
  const rows = {};
  segs.forEach(s => s.acts.forEach(a => { rows[a] = (rows[a] || 0) + (s.rows || 1); }));
  const order = ids || cards.map(c => c.id);
  const sets = {};
  const parts = [];
  const reference = r => {
    const ref = { block: 0, generic: false, part: {}, clause: null, ...r };
    const key = `r${Object.keys(sets).length}`;
    const positions = ref.to.map(id => order.indexOf(id)).sort((x, y) => x - y);
    sets[key] = ref.bits ? bitset(positions) : positions;
    parts.push([{ part: `部分${parts.length}` },
                Object.keys(ref.part).map(id => [order.indexOf(Number(id)), ref.part[id]])
                  .sort((x, y) => x[0] - y[0])]);
    return [ref.block, ref.generic ? 1 : 0, key, parts.length - 1, ref.clause];
  };
  const lines = cards.map(c => [
    c.id, new Array(c.blocks || 1).fill(0),
    c.segs.map((raw, i) => {
      const s = { kind: '效果', pol: '做', acts: [], block: 0, ...raw };
      return [`b${s.block}.s${i}`, s.block, kinds.indexOf(s.kind), polarities.indexOf(s.pol),
              s.replacing ? 1 : 0, s.acts.map(a => actions.indexOf(a)).sort((x, y) => x - y),
              []];
    }),
    [], (c.refs || []).map(reference),
  ]);
  return {
    ids: order,
    actions: actions.map(a => [a, rows[a]]),
    zones: [],
    sides: [],
    kinds,
    polarities,
    blockKinds: ['編號效果'],
    noText: [],
    parts,
    archetypes: [],
    sets,
    cards: lines,
  };
}

module.exports = { actionData };
