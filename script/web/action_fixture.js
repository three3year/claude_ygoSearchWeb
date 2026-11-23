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

/* 線的描述(票 09):{ from, to, fromInferred, toInferred, doer, obj = true };
   from、to 是 [[區域, 方]…](方可以是 null),省略就是沒有;obj 為 false 時物件表裡找不到。
   區域照產物的寫法列,上位區域要自己寫進去(建置時算上位區域的事由 Python 測)。 */
const LINE_DEFAULTS = { doer: false, obj: true };

function lineZones(line) {
  return [].concat(line.from || [], line.to || []);
}

/**
 * cards:[{ id, segs: [{ kind = '效果', pol = '做', acts = [], replacing = false, lines = [] }] }]
 * ids:前端索引的卡號順序(省略時照 cards)。
 */
function actionData(cards, ids) {
  const segs = cards.flatMap(c => c.segs.map(s => ({ kind: '效果', pol: '做', acts: [], ...s })));
  const actions = vocabOf(segs.flatMap(s => s.acts));
  const kinds = vocabOf(segs.map(s => s.kind));
  const polarities = vocabOf(segs.map(s => s.pol));
  const lineList = segs.flatMap(s => s.lines || []);
  const zones = vocabOf(lineList.flatMap(l => lineZones(l).map(z => z[0])));
  const sides = vocabOf(lineList.flatMap(l => lineZones(l).map(z => z[1])));
  const zoneRows = {};
  lineList.forEach(l => new Set(lineZones(l).map(z => z[0]))
    .forEach(z => { zoneRows[z] = (zoneRows[z] || 0) + 1; }));
  const position = (list, inferred) => (list
    ? [inferred ? 1 : 0, ...list.map(([z, s]) => zones.indexOf(z) * 8 + sides.indexOf(s))
      .sort((x, y) => x - y)]
    : 0);
  const line = raw => {
    const l = { ...LINE_DEFAULTS, ...raw };
    return [l.doer ? 1 : 0, position(l.from, l.fromInferred), position(l.to, l.toInferred),
            l.obj ? [0, 'k'] : 0];
  };
  const rows = {};
  segs.forEach(s => s.acts.forEach(a => { rows[a] = (rows[a] || 0) + (s.rows || 1); }));
  return {
    ids: ids || cards.map(c => c.id),
    actions: actions.map(a => [a, rows[a]]),
    zones: zones.map(z => [z, zoneRows[z]]),
    sides,
    kinds,
    polarities,
    blockKinds: ['編號效果'],
    noText: [],
    parts: [],
    archetypes: [],
    sets: { k: [] },
    cards: cards.map(c => [
      c.id, [0],
      c.segs.map((raw, i) => {
        const s = { kind: '效果', pol: '做', acts: [], ...raw };
        return [`b0.s${i}`, 0, kinds.indexOf(s.kind), polarities.indexOf(s.pol),
                s.replacing ? 1 : 0, s.acts.map(a => actions.indexOf(a)).sort((x, y) => x - y),
                (s.lines || []).map(line)];
      }),
      [], [],
    ]),
  };
}

module.exports = { actionData };
