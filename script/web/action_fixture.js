/**
 * action_fixture.js — 接縫三測試用的小動作索引(零 npm 依賴)
 *
 * 把讀得懂的描述 `[{ id, segs: [{ kind, pol, acts, replacing, agent }] }]` 寫成
 * `web/action-data.js` 的格式(`script/action_structure/action_index.py` 的模組說明)。
 * 測試只寫「這張卡有哪些段、段裡有哪些動作詞」,不手抄編碼;格式由 Python 的建置
 * 產出、前端讀回,兩邊是否一致由「兩邊答案一致」的 Python 測試守住。
 */
'use strict';

function vocabOf(values) {
  return Array.from(new Set(values)).sort();
}

/**
 * cards:[{ id, segs: [{ kind = '效果', pol = '做', acts = [], replacing = false,
 *                       agent = '算我方' }] }]
 * ids:前端索引的卡號順序(省略時照 cards)。
 */
function actionData(cards, ids) {
  const segs = cards.flatMap(c => c.segs.map(s => ({ kind: '效果', pol: '做', acts: [], ...s })));
  const actions = vocabOf(segs.flatMap(s => s.acts));
  const kinds = vocabOf(segs.map(s => s.kind));
  const polarities = vocabOf(segs.map(s => s.pol));
  const agents = vocabOf(segs.map(s => s.agent || '算我方'));
  const rows = {};
  segs.forEach(s => s.acts.forEach(a => { rows[a] = (rows[a] || 0) + (s.rows || 1); }));
  return {
    ids: ids || cards.map(c => c.id),
    actions: actions.map(a => [a, rows[a]]),
    zones: [],
    sides: [],
    kinds,
    polarities,
    blockKinds: ['編號效果'],
    agents,
    noText: [],
    parts: [],
    archetypes: [],
    sets: {},
    cards: cards.map(c => [
      c.id, [0],
      c.segs.map((raw, i) => {
        const s = { kind: '效果', pol: '做', acts: [], ...raw };
        return [`b0.s${i}`, 0, kinds.indexOf(s.kind), polarities.indexOf(s.pol),
                s.replacing ? 1 : 0, s.acts.map(a => actions.indexOf(a)).sort((x, y) => x - y),
                []];
      }),
      [], [],
      c.segs.map(() => null),
      c.segs.map(s => agents.indexOf(s.agent || '算我方')),
    ]),
  };
}

module.exports = { actionData };
