'use strict';

const test = require('node:test');
const assert = require('node:assert');
const harness = require('./frontend_harness.js');
const { actionData } = require('./action_fixture.js');

const item = (code, zh) => ({ code, zh });

const VOCAB = {
  cat: { zh: '大類', items: [item('m', '怪獸'), item('s', '魔法'), item('t', '陷阱')] },
  kind: { zh: '效果類型',
          items: [item('q', '誘發即時效果(2速)'), item('t', '誘發效果(1速)'),
                  item('i', '啟動效果')] },
  optional: { zh: '必發/選發',
              items: [item('m', '必發'), item('o', '選發')],
              carriers: ['q', 't'] },
};

const CARDS = [
  { id: 401, n: '即時破壞', c: 'm', s: ['effect'],
    tx: ['①：對手發動時，破壞對手場上1張卡。', '②：把墓地1張卡除外。'],
    k: ['q', 'i'], o: ['o', ''] },
  { id: 402, n: '啟動破壞', c: 'm', s: ['effect'],
    tx: ['①：對手發動時，把對手場上1張卡除外。', '②：破壞墓地以外的1張卡。'],
    k: ['q', 'i'], o: ['m', ''] },
  { id: 403, n: '對不回', c: 'm', s: ['effect'],
    tx: ['①：對手發動時，把對手場上1張卡除外。', '②：破壞1張卡。'],
    k: ['q', 'i'], o: ['o', ''] },
  { id: 404, n: '兩次破壞', c: 'm', s: ['effect'],
    tx: ['①：對手發動時，破壞對手場上1張卡。', '②：破壞墓地以外的1張卡。'],
    k: ['t', 'i'], o: ['m', ''] },
];

const ACTION = actionData([
  { id: 401, segs: [{ acts: ['破壞'], clause: 0 }, { acts: ['除外'], clause: 1 }] },
  { id: 402, segs: [{ acts: ['除外'], clause: 0 }, { acts: ['破壞'], clause: 1 }] },
  { id: 403, segs: [{ acts: ['除外'], clause: 0 }, { acts: ['破壞'], clause: null }] },
  { id: 404, segs: [{ acts: ['破壞'], clause: 0 }, { acts: ['破壞'], clause: 1 }] },
]);

const sandbox = harness.load({ cards: CARDS, vocab: VOCAB, meta: {}, action: ACTION });
const ids = (q, act) => harness.ids(sandbox, q, act);
const DESTROY = { actions: ['破壞'] };

test('效果類型加動作條件:只命中那個效果本身有這個動作的卡', () => {
  assert.deepStrictEqual(ids({ kind: { q: 1 } }, DESTROY), [401, 403]);
  assert.deepStrictEqual(ids({ kind: { i: 1 } }, DESTROY), [402, 403, 404]);
  assert.deepStrictEqual(ids({ kind: { i: 1 } }, { actions: ['除外'] }), [401]);
});

test('效果文關鍵字加動作條件:落在同一個效果', () => {
  assert.deepStrictEqual(ids({ text: '墓地' }, DESTROY), [402, 404]);
  assert.deepStrictEqual(ids({ text: '墓地' }, { actions: ['除外'] }), [401]);
});

test('必發/選發加動作條件:落在同一個效果', () => {
  assert.deepStrictEqual(ids({ opt: { m: 1 } }, DESTROY), [404]);
  assert.deepStrictEqual(ids({ opt: { m: 1 } }, { actions: ['除外'] }), [402]);
  assert.deepStrictEqual(ids({ opt: { o: 1 } }, DESTROY), [401, 403]);
});

test('動作命中的段沒有對回效果時當作符合', () => {
  for (const q of [{ kind: { q: 1 } }, { kind: { i: 1 } }, { opt: { o: 1 } }, { text: '對手' }]) {
    assert.ok(ids(q, DESTROY).includes(403), JSON.stringify(q));
  }
  assert.deepStrictEqual(ids({ text: '墓地' }, DESTROY).includes(403), false);
  assert.deepStrictEqual(ids({ kind: { t: 1 } }, DESTROY), [404]);
});

const rowsOf = (q, act) => Object.fromEntries(
  harness.search(sandbox, q, act).map(e => [e.id, e.rows]));

test('引擎輸出每張卡命中的效果句:句層條件和動作落在同一句的那幾句', () => {
  assert.deepStrictEqual(rowsOf({ kind: { i: 1 } }, DESTROY), { 402: [1], 403: [], 404: [1] });
  assert.deepStrictEqual(rowsOf({ text: '對手' }, DESTROY), { 401: [0], 403: [], 404: [0] });
  assert.deepStrictEqual(rowsOf({ text: '對手' }), { 401: [0], 402: [0], 403: [0], 404: [0] });
});

test('只有動作條件時也輸出命中的效果句;對不回效果的段不標', () => {
  assert.deepStrictEqual(rowsOf({}, DESTROY), { 401: [0], 402: [1], 403: [], 404: [0, 1] });
  assert.deepStrictEqual(rowsOf({ cat: { m: 1 } }, { actions: ['除外'] }),
                         { 401: [1], 402: [0], 403: [0] });
  assert.deepStrictEqual(harness.marks(sandbox, {}, DESTROY), [{ type: 'action' }]);
  assert.deepStrictEqual(harness.marks(sandbox, { text: '對手' }, DESTROY),
                         [{ type: 'text', value: '對手' }, { type: 'action' }]);
});

test('沒有動作條件時,命中標示不變', () => {
  assert.deepStrictEqual(harness.marks(sandbox, {}), []);
  assert.deepStrictEqual(harness.marks(sandbox, { cat: { m: 1 } }, { actions: [] }), []);
  assert.ok(harness.search(sandbox, { cat: { m: 1 } }).every(e => e.rows === null));
});
