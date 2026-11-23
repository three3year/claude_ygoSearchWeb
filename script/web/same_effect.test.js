/**
 * same_effect.test.js — 接縫三(前端查詢引擎)的同一個效果與命中的效果句(action-search-web 票 16)
 *
 * 跑法:`node --test script/web/`
 *
 * 與 action.test.js 同一個沙箱:載入 `web/` 底下真實的前端檔,餵合成的卡片資料與一份小的
 * 動作索引(`action_fixture.js`;段的 clause 是對回的效果句序號,null 是對不回)。
 * 測的是條件進去、命中的卡與每張卡命中的效果句出來;不斷言 DOM 結構與 CSS class,
 * 底色的樣子走站主人工驗收(票 16 的 Comments)。
 */
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
  // 誘發即時效果本身會破壞
  { id: 401, n: '即時破壞', c: 'm', s: ['effect'],
    tx: ['①：對手發動時，破壞對手場上1張卡。', '②：把墓地1張卡除外。'],
    k: ['q', 'i'], o: ['o', ''] },
  // 破壞在啟動效果,誘發即時效果不破壞
  { id: 402, n: '啟動破壞', c: 'm', s: ['effect'],
    tx: ['①：對手發動時，把對手場上1張卡除外。', '②：破壞墓地以外的1張卡。'],
    k: ['q', 'i'], o: ['m', ''] },
  // 破壞那一段對不回效果
  { id: 403, n: '對不回', c: 'm', s: ['effect'],
    tx: ['①：對手發動時，把對手場上1張卡除外。', '②：破壞1張卡。'],
    k: ['q', 'i'], o: ['o', ''] },
  // 兩個效果都破壞
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
  // 402 的誘發即時效果不破壞(破壞在啟動效果),不命中
  assert.deepStrictEqual(ids({ kind: { q: 1 } }, DESTROY), [401, 403]);
  assert.deepStrictEqual(ids({ kind: { i: 1 } }, DESTROY), [402, 403, 404]);
  assert.deepStrictEqual(ids({ kind: { i: 1 } }, { actions: ['除外'] }), [401]);
});

test('效果文關鍵字加動作條件:落在同一個效果', () => {
  // 「墓地」在 401 的除外效果、402 和 404 的破壞效果;403 卡上沒有「墓地」
  assert.deepStrictEqual(ids({ text: '墓地' }, DESTROY), [402, 404]);
  assert.deepStrictEqual(ids({ text: '墓地' }, { actions: ['除外'] }), [401]);
});

test('必發/選發加動作條件:落在同一個效果', () => {
  // 必發的是 402 的除外效果、404 的破壞效果
  assert.deepStrictEqual(ids({ opt: { m: 1 } }, DESTROY), [404]);
  assert.deepStrictEqual(ids({ opt: { m: 1 } }, { actions: ['除外'] }), [402]);
  assert.deepStrictEqual(ids({ opt: { o: 1 } }, DESTROY), [401, 403]);
});

test('動作命中的段沒有對回效果時當作符合', () => {
  // 403 的破壞段對不回效果:誘發即時、啟動、選發都算它符合
  for (const q of [{ kind: { q: 1 } }, { kind: { i: 1 } }, { opt: { o: 1 } }, { text: '對手' }]) {
    assert.ok(ids(q, DESTROY).includes(403), JSON.stringify(q));
  }
  // 句層條件本身沒有命中任何效果句時照樣不命中
  assert.deepStrictEqual(ids({ text: '墓地' }, DESTROY).includes(403), false);
  assert.deepStrictEqual(ids({ kind: { t: 1 } }, DESTROY), [404]);
});

const rowsOf = (q, act) => Object.fromEntries(
  harness.search(sandbox, q, act).map(e => [e.id, e.rows]));

test('引擎輸出每張卡命中的效果句:句層條件和動作落在同一句的那幾句', () => {
  assert.deepStrictEqual(rowsOf({ kind: { i: 1 } }, DESTROY), { 402: [1], 403: [], 404: [1] });
  assert.deepStrictEqual(rowsOf({ text: '對手' }, DESTROY), { 401: [0], 403: [], 404: [0] });
  // 沒有動作條件時,命中的效果句照舊只看句層條件
  assert.deepStrictEqual(rowsOf({ text: '對手' }), { 401: [0], 402: [0], 403: [0], 404: [0] });
});

test('只有動作條件時也輸出命中的效果句;對不回效果的段不標', () => {
  assert.deepStrictEqual(rowsOf({}, DESTROY), { 401: [0], 402: [1], 403: [], 404: [0, 1] });
  assert.deepStrictEqual(rowsOf({ cat: { m: 1 } }, { actions: ['除外'] }),
                         { 401: [1], 402: [0], 403: [0] });
  // 命中的效果句整個加底色,不標到字:動作條件不帶要標的字
  assert.deepStrictEqual(harness.marks(sandbox, {}, DESTROY), [{ type: 'action' }]);
  assert.deepStrictEqual(harness.marks(sandbox, { text: '對手' }, DESTROY),
                         [{ type: 'text', value: '對手' }, { type: 'action' }]);
});

test('沒有動作條件時,命中標示不變', () => {
  assert.deepStrictEqual(harness.marks(sandbox, {}), []);
  assert.deepStrictEqual(harness.marks(sandbox, { cat: { m: 1 } }, { actions: [] }), []);
  assert.ok(harness.search(sandbox, { cat: { m: 1 } }).every(e => e.rows === null));
});
