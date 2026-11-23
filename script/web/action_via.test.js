/**
 * action_via.test.js — 接縫三(前端查詢引擎)的經引用(action-search-web 票 14)
 *
 * 跑法:`node --test script/web/`
 *
 * 與 action.test.js 同一個沙箱與小索引(`action_fixture.js`),卡多了引用列:自己沒寫這個
 * 動作、但引用的別張卡的效果有寫的卡,也在清單裡(特定、泛用、經引用的聯集,不分組)。
 * 判法照 Python 的 `row_match`(票 04):直接命中先算,沿引用列展開到底、走到走過的卡就停;
 * 泛用引用固定關。Python 與前端是否一致由「兩邊答案一致」守住。
 */
'use strict';

const test = require('node:test');
const assert = require('node:assert');
const harness = require('./frontend_harness.js');
const { actionData } = require('./action_fixture.js');

const card = (id, extra) => ({ id, n: `卡${id}`, c: 'm', ...extra });

test('直接沒命中、但引用的卡命中的卡,出現在清單裡', () => {
  const data = actionData([
    { id: 401, segs: [{ acts: ['特殊召喚'] }], refs: [{ to: [402] }] },
    { id: 402, segs: [{ acts: ['破壞'] }] },
  ]);
  const box = harness.load({ cards: [card(401), card(402)], action: data });
  assert.deepStrictEqual(harness.ids(box, {}, { actions: ['破壞'] }), [401, 402]);
  // 引用的卡沒有這個動作:不收
  assert.deepStrictEqual(harness.ids(box, {}, { actions: ['特殊召喚'] }), [401]);
});

test('被引用卡只看指定的部分:命中段在別的區塊不算', () => {
  const data = actionData([
    { id: 411, segs: [], refs: [{ to: [412], part: { 412: [1] } }] },
    { id: 412, blocks: 2, segs: [{ block: 0, acts: ['返回'] }, { block: 1, acts: ['儀式召喚'] }] },
  ]);
  const box = harness.load({ cards: [card(411), card(412)], action: data });
  assert.deepStrictEqual(harness.ids(box, {}, { actions: ['儀式召喚'] }), [411, 412]);
  assert.deepStrictEqual(harness.ids(box, {}, { actions: ['返回'] }), [412]);
});

test('引用的卡自己也是經引用:展開到底', () => {
  const data = actionData([
    { id: 421, segs: [], refs: [{ to: [422] }] },
    { id: 422, segs: [], refs: [{ to: [423] }] },
    { id: 423, segs: [{ acts: ['破壞'] }] },
  ]);
  const box = harness.load({ cards: [card(421), card(422), card(423)], action: data });
  assert.deepStrictEqual(harness.ids(box, {}, { actions: ['破壞'] }), [421, 422, 423]);
});

test('引用循環:查詢停得下來,環上的卡沒命中就不收', () => {
  const data = actionData([
    { id: 431, segs: [], refs: [{ to: [432] }] },
    { id: 432, segs: [], refs: [{ to: [431] }] },
    { id: 433, segs: [], refs: [{ to: [433] }] },              // 引用自己
    { id: 434, segs: [], refs: [{ to: [431, 435] }] },         // 一條走進環、一條走到命中
    { id: 435, segs: [{ acts: ['破壞'] }] },
  ]);
  const box = harness.load({ cards: [431, 432, 433, 434, 435].map(id => card(id)), action: data });
  assert.deepStrictEqual(harness.ids(box, {}, { actions: ['破壞'] }), [434, 435]);
  assert.deepStrictEqual(harness.ids(box, {}, { actions: ['除外'] }), []);
});

test('走到這條路上走過的卡就停:回到走過的卡的另一部分不算', () => {
  // 441 引用 442 的區塊 0;442 的區塊 0 引用 443;443 引用 442 的區塊 1(有破壞)。
  // 從 441 走:441 → 442(區塊 0)→ 443 → 442 已走過,停;所以 441 不收。
  // 從 443 走:443 → 442 的區塊 1 命中,收。442 直接命中。
  const data = actionData([
    { id: 441, segs: [], refs: [{ to: [442], part: { 442: [0] } }] },
    { id: 442, blocks: 2, segs: [{ block: 1, acts: ['破壞'] }], refs: [{ block: 0, to: [443] }] },
    { id: 443, segs: [], refs: [{ to: [442], part: { 442: [1] } }] },
  ]);
  const box = harness.load({ cards: [card(441), card(442), card(443)], action: data });
  assert.deepStrictEqual(harness.ids(box, {}, { actions: ['破壞'] }), [442, 443]);
});

test('泛用引用的列不展開', () => {
  const data = actionData([
    { id: 451, segs: [], refs: [{ to: [452], generic: true }] },
    { id: 452, segs: [{ acts: ['破壞'] }] },
  ]);
  const box = harness.load({ cards: [card(451), card(452)], action: data });
  assert.deepStrictEqual(harness.ids(box, {}, { actions: ['破壞'] }), [452]);
});

test('候選卡寫成位元集的引用列照樣展開', () => {
  const data = actionData([
    { id: 461, segs: [], refs: [{ to: [470], bits: true }] },
    ...Array.from({ length: 8 }, (_, i) => ({ id: 462 + i, segs: [] })),
    { id: 470, segs: [{ acts: ['破壞'] }] },          // 位置 9:落在第二個位元組
  ]);
  const box = harness.load({ cards: data.ids.map(id => card(id)), action: data });
  assert.deepStrictEqual(harness.ids(box, {}, { actions: ['破壞'] }), [461, 470]);
});

test('已經直接命中的卡不重複列;經引用的卡照樣要滿足卡片條件', () => {
  const data = actionData([
    { id: 481, segs: [{ acts: ['破壞'] }], refs: [{ to: [483] }] },
    { id: 482, segs: [], refs: [{ to: [483] }] },
    { id: 483, segs: [{ acts: ['破壞'] }] },
  ]);
  const cards = [card(481, { c: 't' }), card(482, { c: 's' }), card(483, { c: 's' })];
  const box = harness.load({ cards, action: data });
  assert.deepStrictEqual(harness.ids(box, {}, { actions: ['破壞'] }), [481, 482, 483]);
  assert.deepStrictEqual(harness.ids(box, { cat: { s: 1 } }, { actions: ['破壞'] }), [482, 483]);
  assert.deepStrictEqual(harness.ids(box, { cat: { t: 1 } }, { actions: ['破壞'] }), [481]);
});

test('清單不分組、不加經引用的標記;經引用的卡照現有規則排序', () => {
  const data = actionData([
    { id: 491, segs: [{ acts: ['破壞'] }] },
    { id: 492, segs: [], refs: [{ to: [491] }] },
    { id: 493, segs: [{ acts: ['破壞'] }] },
  ]);
  // 前端索引的順序:經引用的 492 夾在中間;494 沒命中
  const cards = [card(493, { n: '丙', atk: 500 }), card(494, { n: '丁', atk: 2000 }),
                 card(492, { n: '乙', atk: 3000 }), card(491, { n: '甲', atk: 1000 })];
  const box = harness.load({ cards, action: data });
  const act = { actions: ['破壞'] };
  assert.deepStrictEqual(harness.ids(box, {}, act), [493, 492, 491]);
  // 標記與只有直接命中時相同(票 16 的動作底色),沒有分組或經引用的標記
  const direct = harness.load({ cards, action: actionData([
    { id: 491, segs: [{ acts: ['破壞'] }] }, { id: 493, segs: [{ acts: ['破壞'] }] }]) });
  assert.deepStrictEqual(harness.marks(box, {}, act), harness.marks(direct, {}, act));
  assert.deepStrictEqual(harness.sortedIds(box, {}, 'atk', 'desc', act), [492, 491, 493]);
  assert.deepStrictEqual(harness.sortedIds(box, {}, 'atk', 'asc', act), [493, 491, 492]);
});

/* ── 和票 16(同一個效果、標出命中的效果)的接法 ────────────────
   經引用的命中算在引用節點所在的效果上(spec「效果對應」)。 */

const KIND_VOCAB = {
  kind: { zh: '效果類型', items: [{ code: 'q', zh: '誘發即時效果(2速)' },
                                   { code: 'i', zh: '啟動效果' }] },
};

test('經引用的命中算在引用節點所在的效果上:標出那一句、和句層條件取同一句', () => {
  const data = actionData([
    // 501 的 ② 引用 503;502 的 ① 引用 503;503 有破壞
    { id: 501, segs: [{ acts: ['除外'], clause: 0 }], refs: [{ to: [503], clause: 1 }] },
    { id: 502, segs: [], refs: [{ to: [503], clause: 0 }] },
    { id: 503, segs: [{ acts: ['破壞'], clause: 0 }] },
    // 504 的引用節點對不回效果
    { id: 504, segs: [], refs: [{ to: [503], clause: null }] },
  ]);
  const cards = [
    { id: 501, n: '②引用', c: 't', tx: ['①：除外。', '②：同一效果。'], k: ['q', 'i'] },
    { id: 502, n: '①引用', c: 't', tx: ['①：同一效果。', '②：抽牌。'], k: ['q', 'i'] },
    { id: 503, n: '被引用', c: 't', tx: ['①：破壞。'], k: ['i'] },
    { id: 504, n: '對不回', c: 't', tx: ['①：同一效果。'], k: ['q'] },
  ];
  const box = harness.load({ cards, vocab: KIND_VOCAB, meta: {}, action: data });
  const destroy = { actions: ['破壞'] };
  const rows = q => harness.search(box, q, destroy).map(e => [e.id, e.rows]);
  // 只有動作條件:經引用的卡標引用節點所在的那一句;對不回的不標
  assert.deepStrictEqual(rows({}), [[501, [1]], [502, [0]], [503, [0]], [504, []]]);
  // 效果類型「誘發即時效果」:502 的 ① 是誘發即時、引用節點也在 ①;501 的 ② 是啟動效果
  assert.deepStrictEqual(rows({ kind: { q: 1 } }), [[502, [0]], [504, []]]);
  // 504 沒有啟動效果的句:句層條件本身沒命中,照樣不命中
  assert.deepStrictEqual(rows({ kind: { i: 1 } }), [[501, [1]], [503, [0]]]);
});


/* ── 和票 15(無法確認的張數)的接法 ──────────────────────── */

test('經引用命中的卡不算無法確認', () => {
  // 511 有一段解析不出、字面含破壞,但經引用 512 命中:只在命中的清單(Python 的未解析組同樣不收)
  const data = actionData([
    { id: 511, unres: [{ acts: ['破壞'] }], refs: [{ to: [512] }] },
    { id: 512, segs: [{ acts: ['破壞'] }] },
    { id: 513, unres: [{ acts: ['破壞'] }] },
  ]);
  const box = harness.load({ cards: [card(511), card(512), card(513)], action: data });
  const destroy = { actions: ['破壞'] };
  assert.deepStrictEqual(harness.ids(box, {}, destroy), [511, 512]);
  assert.deepStrictEqual(harness.unsure(box, {}, destroy), [513]);
});
