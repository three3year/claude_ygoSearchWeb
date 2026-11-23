'use strict';

const test = require('node:test');
const assert = require('node:assert');
const harness = require('./frontend_harness.js');
const { actionData } = require('./action_fixture.js');

const CARDS = [
  { id: 401, n: '破壞自己', c: 'm' },
  { id: 402, n: '破壞我方場上的卡', c: 'm' },
  { id: 403, n: '破壞的一方', c: 'm' },
  { id: 404, n: '物件判不了', c: 's' },
  { id: 405, n: '代不進去', c: 's' },
  { id: 406, n: '黑魔導', nj: 'ブラック・マジシャン', c: 'm' },
  { id: 407, n: '黑魔導女孩', nj: 'ブラック・マジシャン・ガール', c: 'm' },
  { id: 408, n: '沒有物件', c: 's' },
  { id: 409, n: '代入時異同判不了', c: 's' },
];

const ACTION = actionData([
  { id: 401, segs: [{ acts: ['破壞'], lines: [{ obj: 'self' }] }] },
  { id: 402, segs: [{ acts: ['破壞'], lines: [{ obj: [401, 402, 403, 406] }] }] },
  { id: 403, segs: [{ acts: ['破壞'], lines: [{ doer: true, obj: 'self' },
                                              { obj: [406, 407] }] }] },
  { id: 404, segs: [{ acts: ['破壞'], lines: [{ obj: 'undecidable' }] }],
    unres: [{ acts: ['破壞'], reason: true, substituting: true }] },
  { id: 405, segs: [{ acts: ['破壞'], lines: [{ obj: 'unsub' }] }] },
  { id: 406, segs: [{ acts: ['破壞'], lines: [{ obj: 'self' }, { obj: [407] }] }] },
  { id: 408, segs: [{ acts: ['破壞'], lines: [{ obj: null }] }] },
  { id: 409, segs: [{ acts: ['破壞'], lines: [{ obj: 'undecidable' }] }],
    unres: [{ acts: ['破壞'], reason: false, substituting: true }] },
], CARDS.map(c => c.id));

const sandbox = harness.load({ cards: CARDS, meta: {}, action: ACTION });
const ids = act => harness.ids(sandbox, {}, act);

test('這張卡自己:只命中物件是此卡的線', () => {
  assert.deepStrictEqual(ids({ actions: ['破壞'], target: 'this_card' }), [401, 406]);
  assert.deepStrictEqual(ids({ actions: ['破壞'] }), [401, 402, 403, 404, 405, 406, 408, 409]);
});

test('指定一張卡:這張卡在線的候選卡裡就命中(此卡的線是那張卡自己)', () => {
  assert.deepStrictEqual(ids({ actions: ['破壞'], target: { card: 407 } }), [403, 406]);
  assert.deepStrictEqual(ids({ actions: ['破壞'], target: { card: 406 } }), [402, 403, 406]);
  assert.deepStrictEqual(ids({ actions: ['破壞'], target: { card: 402 } }), [402]);
  assert.deepStrictEqual(ids({ actions: ['破壞'], target: { card: 405 } }), []);
});

test('物件判不了的線不命中,算進無法確認:指定卡看代入卡時、這張卡自己看不代入卡時', () => {
  const unsure = act => harness.unsure(sandbox, {}, act);
  assert.deepStrictEqual(unsure({ actions: ['破壞'], target: 'this_card' }), [404]);
  assert.deepStrictEqual(unsure({ actions: ['破壞'], target: { card: 407 } }), [404, 409]);
  assert.deepStrictEqual(unsure({ actions: ['破壞'] }), []);
});

test('被動作的卡換成列查詢:這張卡自己、指定卡各一個鍵', () => {
  assert.strictEqual(harness.rowQuery(sandbox, { actions: ['破壞'], target: 'this_card' }).this_card,
                     true);
  assert.strictEqual(harness.rowQuery(sandbox, { actions: ['破壞'], target: { card: 406 } }).card,
                     406);
  const plain = harness.rowQuery(sandbox, { actions: ['破壞'] });
  assert.ok(!('this_card' in plain) && !('card' in plain));
});

test('卡名的建議清單:名字短的排前面', () => {
  assert.deepStrictEqual(harness.cardSuggest(sandbox, '黑魔導').map(c => c.id), [406, 407]);
  assert.deepStrictEqual(harness.cardSuggest(sandbox, 'ブラック').map(c => c.id), [406, 407]);
  assert.deepStrictEqual(harness.cardSuggest(sandbox, '破壞').map(c => c.id), [401, 403, 402]);
  assert.deepStrictEqual(harness.cardSuggest(sandbox, ''), []);
  assert.deepStrictEqual(harness.cardSuggest(sandbox, '沒有這張'), []);
});

const EMPTY_Q = { name: '', nameLang: 'zh', code: '', text: '' };
const DOM_SORT = { key: 'dom', dir: '' };

test('被動作的卡跟著查詢狀態存進瀏覽紀錄,還原後相同', () => {
  for (const act of [{ actions: ['破壞'], target: 'this_card' },
                     { actions: ['破壞'], target: { card: 406 } }]) {
    const st = { q: EMPTY_Q, sort: DOM_SORT, act };
    const saved = JSON.parse(JSON.stringify(harness.savedState(sandbox, st.q, st.sort, act)));
    assert.deepStrictEqual(harness.restoreSaved(sandbox, saved), st, JSON.stringify(act));
  }
});

test('瀏覽紀錄裡認不得的被動作的卡忽略,其餘照常還原', () => {
  const good = { q: EMPTY_Q, sort: DOM_SORT, act: { actions: ['破壞'] } };
  for (const target of ['自己', 'self', 'SELF', 1, [], {}, { card: '406' }, { card: 1.5 }, { card: -1 },
                        { cond: {} }, null]) {
    assert.deepStrictEqual(
      harness.restoreSaved(sandbox, { ...good, act: { actions: ['破壞'], target } }), good,
      JSON.stringify(target));
  }
});

test('只指定被動作的卡、沒有選動作詞也是一組動作條件', () => {
  const act = { actions: [], target: 'this_card' };
  assert.deepStrictEqual(ids(act), [401, 406]);
  assert.deepStrictEqual(harness.restoreSaved(sandbox, { q: EMPTY_Q, sort: DOM_SORT, act }),
                         { q: EMPTY_Q, sort: DOM_SORT, act: { target: 'this_card' } });
});

test('摺疊鈕的生效條件數:被動作的卡算一條', () => {
  assert.strictEqual(harness.critCount(sandbox, EMPTY_Q, { actions: ['破壞'], target: 'this_card' }), 2);
  assert.strictEqual(harness.critCount(sandbox, EMPTY_Q, { target: { card: 406 } }), 1);
  assert.strictEqual(harness.critCount(sandbox, EMPTY_Q, { actions: ['破壞'] }), 1);
});
