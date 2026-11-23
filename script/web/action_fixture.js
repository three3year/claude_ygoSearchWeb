/**
 * action_fixture.js — 接縫三測試用的小動作索引(零 npm 依賴)
 *
 * 把讀得懂的描述 `[{ id, segs: [{ kind, pol, acts, replacing, clause }], unres: [未解析的來源] }]`
 * 寫成
 * `web/action-data.js` 的格式(`script/action_structure/action_index.py` 的模組說明)。
 * 測試只寫「這張卡有哪些段、段裡有哪些動作詞」,不手抄編碼;格式由 Python 的建置
 * 產出、前端讀回,兩邊是否一致由「兩邊答案一致」的 Python 測試守住。
 */
'use strict';

function vocabOf(values) {
  return Array.from(new Set(values)).sort();
}

/* 未解析的來源的旗標(`action_index.py` 的 U_*)。 */
const U_REPLACING = 1, U_REASON = 4, U_REASON_SUBSTITUTING = 8, U_REFERENCE = 16;

/* 未解析的來源的預設:效果段、極性「做」、代不代入卡都判不了。引用節點沒有段類別與極性。 */
function unresOf(raw) {
  const u = { kind: '效果', pol: '做', acts: [], replacing: false, reference: false,
              reason: true, substituting: true, ...raw };
  if (u.reference) { u.kind = null; u.pol = null; }
  return u;
}

/**
 * cards:[{ id, segs: [{ kind = '效果', pol = '做', acts = [], replacing = false, clause = null }],
 *          unres: [{ kind = '效果', pol = '做', acts = [], replacing = false,
 *                    reference = false, reason = true, substituting = true }] }]
 *   clause:段對回的效果句序號(前端索引 `tx` 的位置),null 是對不回(票 07 的「效果」格)。
 *   unres 是未解析的來源(票 15):acts 是原文字面的動作詞;reason / substituting 是
 *   不代入卡時 / 代入卡(指定卡、給條件)時判不判得了(true = 判不了,進未解析組);
 *   reference 是解析不出的引用節點。
 * ids:前端索引的卡號順序(省略時照 cards)。noText:無官方日文的卡號。
 */
function actionData(cards, ids, noText) {
  cards = cards.map(c => ({ segs: [], unres: [], ...c }));
  const segs = cards.flatMap(c => c.segs.map(s => ({ kind: '效果', pol: '做', acts: [], ...s })));
  const unres = cards.flatMap(c => c.unres.map(unresOf));
  const actions = vocabOf(segs.flatMap(s => s.acts).concat(unres.flatMap(u => u.acts)));
  const kinds = vocabOf(segs.map(s => s.kind).concat(unres.map(u => u.kind).filter(k => k)));
  const polarities = vocabOf(segs.map(s => s.pol).concat(unres.map(u => u.pol).filter(p => p)));
  const rows = {};
  segs.forEach(s => s.acts.forEach(a => { rows[a] = (rows[a] || 0) + (s.rows || 1); }));
  return {
    ids: ids || cards.map(c => c.id),
    actions: actions.map(a => [a, rows[a] || 0]),
    zones: [],
    sides: [],
    kinds,
    polarities,
    blockKinds: ['編號效果'],
    noText: noText || [],
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
      c.unres.map(raw => {
        const u = unresOf(raw);
        return [u.kind === null ? null : kinds.indexOf(u.kind),
                u.pol === null ? null : polarities.indexOf(u.pol), 0,
                (u.replacing ? U_REPLACING : 0) | (u.reason ? U_REASON : 0)
                  | (u.substituting ? U_REASON_SUBSTITUTING : 0) | (u.reference ? U_REFERENCE : 0),
                u.acts.map(a => actions.indexOf(a)).sort((x, y) => x - y)];
      }),
      [],
      c.segs.map(s => (s.clause == null ? null : s.clause)),
    ]),
  };
}

module.exports = { actionData };
