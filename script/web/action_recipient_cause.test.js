/**
 * action_recipient_cause.test.js — 接縫三:動作條件的「受方」與「原因」(action-search-web 票 11)
 *
 * 跑法:`node --test script/web/`
 *
 * 與 action_agent.test.js 同一個沙箱與小索引寫法(`action_fixture.js`,段多帶 `recipient`、`cause`)。
 * 段的受方是玩家的方或 null(受方是卡、沒有受方);原因是 [種類, 方或 null]、
 * 沒寫原因的被動句 ['不限定', null]、主動句 null(攤平時定好,見
 * `script/action_structure/action_rows.py` 的 `recipient_of`、`cause_of`)。前端只比對。
 * 規則與 Python 的 `run_query` 相同,兩邊一致由 `test_web_parity.py` 守住。
 */
'use strict';

const test = require('node:test');
const assert = require('node:assert');
const harness = require('./frontend_harness.js');
const { actionData } = require('./action_fixture.js');

const IDS = [501, 502, 503, 504, 511, 512, 513, 514, 515, 516, 517, 518, 519];
const CARDS = IDS.map(id => ({ id, n: `卡${id}`, c: 'm' }));

const ACTION = actionData([
  // 受方
  { id: 501, segs: [{ acts: ['傷害'], recipient: '對手' }] },
  { id: 502, segs: [{ acts: ['傷害'], recipient: '我方' }] },
  { id: 503, segs: [{ acts: ['傷害'], recipient: '雙方各自' }] },
  { id: 504, segs: [{ acts: ['裝備'] }] },                       // 受方是卡:null
  // 原因(破壞的條件段)
  { id: 511, segs: [{ kind: '條件', acts: ['破壞'], cause: ['戰鬥', null] }] },
  { id: 512, segs: [{ kind: '條件', acts: ['破壞'], cause: ['戰鬥或效果', null] }] },
  { id: 513, segs: [{ kind: '條件', acts: ['破壞'], cause: ['戰鬥以外', null] }] },
  { id: 514, segs: [{ kind: '條件', acts: ['破壞'], cause: ['不限定', null] }] },
  { id: 515, segs: [{ acts: ['破壞'] }] },                       // 主動句沒寫原因
  { id: 516, segs: [{ pol: '不會', acts: ['破壞'], cause: ['效果', '對手'] }] },
  { id: 517, segs: [{ pol: '不會', acts: ['破壞'], cause: ['效果', null] }] },
  { id: 518, segs: [{ kind: '條件', acts: ['特殊召喚'], cause: ['作為素材', null] }] },
  // 原因比的是段:戰鬥寫在另一段
  { id: 519, segs: [{ kind: '條件', acts: ['特殊召喚'], cause: ['戰鬥', null] },
                    { kind: '條件', acts: ['破壞'], cause: ['不限定', null] }] },
]);

const sandbox = harness.load({ cards: CARDS, action: ACTION });
const ids = act => harness.ids(sandbox, {}, act);
const COND = ['eff', 'cost', 'cond'];

test('受方選對手:寫對手、雙方各自的命中;我方與受方是卡的不命中', () => {
  assert.deepStrictEqual(ids({ actions: ['傷害'], recipient: '對手' }), [501, 503]);
  assert.deepStrictEqual(ids({ actions: ['傷害'], recipient: '我方' }), [502, 503]);
  assert.deepStrictEqual(ids({ actions: ['裝備'], recipient: '我方' }), []);
  assert.deepStrictEqual(ids({ actions: ['裝備'] }), [504]);
});

test('原因選戰鬥:寫戰鬥與戰鬥或效果的命中;戰鬥以外、主動句沒寫的不命中', () => {
  assert.deepStrictEqual(ids({ actions: ['破壞'], kinds: COND, cause: { kind: '戰鬥' } }),
                         [511, 512]);
});

test('原因選效果:戰鬥或效果、戰鬥以外都算效果', () => {
  assert.deepStrictEqual(ids({ actions: ['破壞'], kinds: COND, cause: { kind: '效果' } }),
                         [512, 513]);
});

test('沒寫原因的被動句要勾「含不限定的」才命中;主動句勾了也不命中', () => {
  assert.deepStrictEqual(
    ids({ actions: ['破壞'], kinds: COND, cause: { kind: '戰鬥' }, unrestricted: true }),
    [511, 512, 514, 519]);
});

test('原因的方:段沒寫方的命中,寫了方要相同', () => {
  const resist = { actions: ['破壞'], pol: 'resist' };
  assert.deepStrictEqual(ids({ ...resist, cause: { kind: '效果', side: '對手' } }), [516, 517]);
  assert.deepStrictEqual(ids({ ...resist, cause: { kind: '效果', side: '我方' } }), [517]);
});

test('其餘種類寫什麼比什麼;原因比的是段', () => {
  assert.deepStrictEqual(ids({ actions: ['特殊召喚'], kinds: COND, cause: { kind: '作為素材' } }),
                         [518]);
  assert.deepStrictEqual(ids({ actions: ['破壞'], kinds: COND, cause: { kind: '戰鬥' } })
    .indexOf(519), -1);
});

test('沒選受方、原因:結果與以前相同', () => {
  assert.deepStrictEqual(ids({ actions: ['傷害'] }), [501, 502, 503]);
  assert.deepStrictEqual(ids({ actions: ['破壞'], kinds: COND }),
                         [511, 512, 513, 514, 515, 519]);
});

test('原因的選項由索引的表生成,不列戰鬥或效果、戰鬥以外與沒寫的兩種', () => {
  // 列數:戰鬥 2(511、519)、效果 2(516、517)、作為素材 1;同列數照索引的順序(字串排序)
  assert.deepStrictEqual(harness.causeOptions(sandbox), ['戰鬥', '效果', '作為素材']);
});

test('介面到查詢:受方換成 recipient,原因換成 cause({ kind, side })', () => {
  const base = harness.rowQuery(sandbox, { actions: ['破壞'] });
  assert.strictEqual('recipient' in base, false);
  assert.strictEqual('cause' in base, false);
  assert.deepStrictEqual(
    harness.rowQuery(sandbox, { actions: ['破壞'], recipient: '對手',
                                cause: { kind: '效果', side: '對手' }, unrestricted: true }),
    { ...base, recipient: '對手', cause: { kind: '效果', side: '對手' },
      include_unrestricted: true });
  assert.deepStrictEqual(harness.rowQuery(sandbox, { actions: ['破壞'], cause: { kind: '戰鬥' } }),
                         { ...base, cause: { kind: '戰鬥' } });
});

/* ── 瀏覽紀錄與摺疊鈕 ───────────────────────────────────── */

const EMPTY_Q = { name: '', nameLang: 'zh', code: '', text: '' };
const DOM_SORT = { key: 'dom', dir: '' };

test('受方與原因跟著存進瀏覽紀錄,還原後相同', () => {
  const st = { q: EMPTY_Q, sort: DOM_SORT,
               act: { actions: ['破壞'], recipient: '對手',
                      cause: { kind: '效果', side: '我方' }, unrestricted: true } };
  const saved = JSON.parse(JSON.stringify(harness.savedState(sandbox, st.q, st.sort, st.act)));
  assert.deepStrictEqual(harness.restoreSaved(sandbox, saved), st);
});

test('瀏覽紀錄裡認不得的受方或原因忽略;原因認不得的方只丟方', () => {
  const good = { q: EMPTY_Q, sort: DOM_SORT, act: { actions: ['破壞'] } };
  for (const act of [{ actions: ['破壞'], recipient: '雙方各自' },
                     { actions: ['破壞'], recipient: ['對手'] },
                     { actions: ['破壞'], cause: '戰鬥' },
                     { actions: ['破壞'], cause: { kind: '' } },
                     { actions: ['破壞'], cause: { kind: '不限定' } },
                     { actions: ['破壞'], cause: { side: '對手' } }]) {
    assert.deepStrictEqual(harness.restoreSaved(sandbox, { ...good, act }), good,
                           JSON.stringify(act));
  }
  assert.deepStrictEqual(
    harness.restoreSaved(sandbox, { ...good,
                                    act: { actions: ['破壞'], cause: { kind: '戰鬥', side: 'x' } } }),
    { ...good, act: { actions: ['破壞'], cause: { kind: '戰鬥' } } });
});

test('摺疊鈕的條件數:受方、原因各多算一條', () => {
  assert.strictEqual(harness.critCount(sandbox, EMPTY_Q,
                                       { actions: ['破壞'], recipient: '我方',
                                         cause: { kind: '戰鬥', side: '對手' } }), 3);
});
