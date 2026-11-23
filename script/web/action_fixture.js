/**
 * action_fixture.js — 接縫三測試用的小動作索引(零 npm 依賴)
 *
 * 把讀得懂的描述 `[{ id, segs: [{ kind, pol, acts, replacing, lines }] }]` 寫成
 * `web/action-data.js` 的格式(`script/action_structure/action_index.py` 的模組說明)。
 * 測試只寫「這張卡有哪些段、段裡有哪些動作詞」,不手抄編碼;格式由 Python 的建置
 * 產出、前端讀回,兩邊是否一致由「兩邊答案一致」的 Python 測試守住。
 */
'use strict';

function vocabOf(values) {
  return Array.from(new Set(values)).sort();
}

/* 物件的種類碼(action_index.py:種類只在不是候選卡集合時寫)。 */
const OBJECT_CODES = { self: 1, undecidable: 2, unsub: 3 };

/**
 * cards:[{ id, segs: [{ kind = '效果', pol = '做', acts = [], replacing = false, lines = [] }] }]
 *   線:{ doer = false, obj }。obj 是 null(沒有物件)、'self'(此卡,集合是這張卡)、
 *   'undecidable'(判不了)、'unsub'(代不進去),或候選卡的卡號陣列(候選卡集合)。
 * ids:前端索引的卡號順序(省略時照 cards)。
 */
function actionData(cards, ids) {
  ids = ids || cards.map(c => c.id);
  const sets = {};
  const setKey = members => {
    const positions = members.map(id => ids.indexOf(id)).filter(p => p >= 0).sort((a, b) => a - b);
    const key = `k${positions.join('_')}`;
    sets[key] = positions;
    return key;
  };
  const lineOf = (owner, line) => {
    const obj = line.obj === undefined ? null : line.obj;
    let encoded = 0;
    if (Array.isArray(obj)) encoded = [0, setKey(obj)];
    else if (obj === 'self') encoded = [0, setKey([owner]), OBJECT_CODES.self];
    else if (obj) encoded = [0, setKey([]), OBJECT_CODES[obj]];
    return [line.doer ? 1 : 0, 0, 0, encoded];
  };
  const segs = cards.flatMap(c => c.segs.map(s => ({ kind: '效果', pol: '做', acts: [], ...s })));
  const actions = vocabOf(segs.flatMap(s => s.acts));
  const kinds = vocabOf(segs.map(s => s.kind));
  const polarities = vocabOf(segs.map(s => s.pol));
  const rows = {};
  segs.forEach(s => s.acts.forEach(a => { rows[a] = (rows[a] || 0) + (s.rows || 1); }));
  return {
    ids,
    actions: actions.map(a => [a, rows[a]]),
    zones: [],
    sides: [],
    kinds,
    polarities,
    blockKinds: ['編號效果'],
    noText: [],
    parts: [],
    archetypes: [],
    sets,
    cards: cards.map(c => [
      c.id, [0],
      c.segs.map((raw, i) => {
        const s = { kind: '效果', pol: '做', acts: [], ...raw };
        return [`b0.s${i}`, 0, kinds.indexOf(s.kind), polarities.indexOf(s.pol),
                s.replacing ? 1 : 0, s.acts.map(a => actions.indexOf(a)).sort((x, y) => x - y),
                (s.lines || []).map(line => lineOf(c.id, line))];
      }),
      [], [],
    ]),
  };
}

module.exports = { actionData };
