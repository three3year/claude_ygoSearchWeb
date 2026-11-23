/**
 * action_fixture.js — 接縫三測試用的小動作索引(零 npm 依賴)
 *
 * 把讀得懂的描述 `[{ id, segs: [{ kind, pol, acts, replacing, clause, agent, recipient, cause }],
 * unres: [未解析的來源],
 * refs: [引用列] }]` 寫成
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

/* 線的描述(票 09):{ from, to, fromInferred, toInferred, doer, obj = true };
   from、to 是 [[區域, 方]…](方可以是 null),省略就是沒有;obj 為 false 或 null 時物件表裡
   找不到(沒有物件),true 是有物件、候選卡集合是空的。票 12 的物件種類:'self'(此卡,集合是
   這張卡)、'undecidable'(判不了)、'unsub'(代不進去),或候選卡的卡號陣列(候選卡集合)。
   區域照產物的寫法列,上位區域要自己寫進去(建置時算上位區域的事由 Python 測)。 */
const LINE_DEFAULTS = { doer: false, obj: true };

function lineZones(line) {
  return [].concat(line.from || [], line.to || []);
}

/* 物件的種類碼(`action_index.OBJECT_CODES`:種類只在不是候選卡集合時寫)。 */
const OBJECT_CODES = { self: 1, undecidable: 2, unsub: 3 };

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
 * cards:[{ id, blocks = 1,
 *          segs: [{ kind = '效果', pol = '做', acts = [], replacing = false, clause = null,
 *                   block = 0, lines = [線的描述], agent = '算我方', recipient = null,
 *                   cause = null }],
 *          unres: [{ kind = '效果', pol = '做', acts = [], replacing = false,
 *                    reference = false, reason = true, substituting = true }],
 *          refs: [引用列] }]
 *   blocks:頂層區塊數;段的 block 是它在第幾個區塊。
 *   clause:段對回的效果句序號(前端索引 `tx` 的位置),null 是對不回(票 07 的「效果」格)。
 *   agent:段的誰(票 10):我方、對手、雙方各自、算我方、不限定。
 *   recipient:段的受方(票 11):我方、對手、雙方各自,null 是受方是卡或沒有受方。
 *   cause:段的原因(票 11):[種類, 方或 null];沒寫原因的被動句 ['不限定', null],主動句 null。
 *   unres 是未解析的來源(票 15):acts 是原文字面的動作詞;reason / substituting 是
 *   不代入卡時 / 代入卡(指定卡、給條件)時判不判得了(true = 判不了,進未解析組);
 *   reference 是解析不出的引用節點。
 *   引用列(票 14):{ block = 0, to: [被引用的卡號], generic = false, part = {}, clause = null,
 *                     bits = false }
 *     part:被引用卡號 → 指定的部分是它的哪幾個區塊;沒列的卡看整張。
 *     clause:引用節點所在的效果句序號。
 *     bits:候選卡寫成位元集(大集合的寫法);否則寫位置的清單。
 * ids:前端索引的卡號順序(省略時照 cards)。noText:無官方日文的卡號。
 */
function actionData(cards, ids, noText) {
  cards = cards.map(c => ({ segs: [], unres: [], ...c }));
  const segs = cards.flatMap(c => c.segs.map(s => ({ kind: '效果', pol: '做', acts: [], ...s })));
  const unres = cards.flatMap(c => c.unres.map(unresOf));
  const actions = vocabOf(segs.flatMap(s => s.acts).concat(unres.flatMap(u => u.acts)));
  const kinds = vocabOf(segs.map(s => s.kind).concat(unres.map(u => u.kind).filter(k => k)));
  const polarities = vocabOf(segs.map(s => s.pol).concat(unres.map(u => u.pol).filter(p => p)));
  const agents = vocabOf(segs.map(s => s.agent || '算我方'));
  const rows = {};
  segs.forEach(s => s.acts.forEach(a => { rows[a] = (rows[a] || 0) + (s.rows || 1); }));
  const lineList = segs.flatMap(s => s.lines || []);
  const zones = vocabOf(lineList.flatMap(l => lineZones(l).map(z => z[0])));
  // 方的清單和建置一樣 null 排最前;受方與原因的方也在這份清單裡(票 11)
  const sides = [null].concat(vocabOf(lineList.flatMap(l => lineZones(l).map(z => z[1]))
    .concat(segs.map(s => s.recipient), segs.map(s => s.cause && s.cause[1]))
    .filter(v => v != null)));
  const causes = [null].concat(vocabOf(segs.filter(s => s.cause).map(s => s.cause[0])));
  const causeRows = {};
  segs.forEach(s => { const k = s.cause ? s.cause[0] : null; causeRows[k] = (causeRows[k] || 0) + 1; });
  const causeCode = c => causes.indexOf(c ? c[0] : null) * 8 + sides.indexOf(c ? c[1] : null);
  const zoneRows = {};
  lineList.forEach(l => new Set(lineZones(l).map(z => z[0]))
    .forEach(z => { zoneRows[z] = (zoneRows[z] || 0) + 1; }));
  const position = (list, inferred) => (list
    ? [inferred ? 1 : 0, ...list.map(([z, s]) => zones.indexOf(z) * 8 + sides.indexOf(s))
      .sort((x, y) => x - y)]
    : 0);
  const order = ids || cards.map(c => c.id);
  const sets = { k: [] };            // 線的物件(票 09 只看物件在不在)
  const setOf = members => {
    const positions = members.map(id => order.indexOf(id)).filter(p => p >= 0)
      .sort((x, y) => x - y);
    const key = positions.length ? `k${positions.join('_')}` : 'k';
    sets[key] = positions;
    return key;
  };
  const objectOf = (owner, obj) => {
    if (!obj) return 0;
    if (Array.isArray(obj)) return [0, setOf(obj)];
    if (obj === 'self') return [0, setOf([owner]), OBJECT_CODES.self];
    if (OBJECT_CODES[obj]) return [0, 'k', OBJECT_CODES[obj]];
    return [0, 'k'];
  };
  const line = (owner, raw) => {
    const l = { ...LINE_DEFAULTS, ...raw };
    return [l.doer ? 1 : 0, position(l.from, l.fromInferred), position(l.to, l.toInferred),
            objectOf(owner, l.obj)];
  };
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
              (s.lines || []).map(raw => line(c.id, raw))];
    }),
    c.unres.map(raw => {
      const u = unresOf(raw);
      return [u.kind === null ? null : kinds.indexOf(u.kind),
              u.pol === null ? null : polarities.indexOf(u.pol), 0,
              (u.replacing ? U_REPLACING : 0) | (u.reason ? U_REASON : 0)
                | (u.substituting ? U_REASON_SUBSTITUTING : 0) | (u.reference ? U_REFERENCE : 0),
              u.acts.map(a => actions.indexOf(a)).sort((x, y) => x - y)];
    }),
    (c.refs || []).map(reference),
    c.segs.map(s => (s.clause == null ? null : s.clause)),
    c.segs.map(s => agents.indexOf(s.agent || '算我方')),
    c.segs.map(s => sides.indexOf(s.recipient == null ? null : s.recipient)),
    c.segs.map(s => causeCode(s.cause)),
  ]);
  return {
    ids: order,
    actions: actions.map(a => [a, rows[a] || 0]),
    zones: zones.map(z => [z, zoneRows[z]]),
    sides,
    kinds,
    polarities,
    blockKinds: ['編號效果'],
    agents,
    causes: causes.map(k => [k, causeRows[k] || 0]),
    noText: noText || [],
    parts,
    archetypes: [],
    sets,
    cards: lines,
  };
}

module.exports = { actionData };
