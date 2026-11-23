/**
 * action_agent.test.js — 接縫三:動作條件的「誰」與「含不限定的」(action-search-web 票 10)
 *
 * 跑法:`node --test script/web/`
 *
 * 與 action.test.js 同一個沙箱與小索引寫法(`action_fixture.js`,段多帶 `agent`)。
 * 段的誰是三種之一:寫明的(我方、對手、雙方各自)、算我方、不限定(攤平時定好,
 * 見 `script/action_structure/action_rows.py` 的 `agent_of`)。前端只比對,不判段類別或被動句。
 * 規則與 Python 的 `run_query` 相同,兩邊一致由 `test_web_parity.py` 守住。
 */
'use strict';

const test = require('node:test');
const assert = require('node:assert');
const harness = require('./frontend_harness.js');
const { actionData } = require('./action_fixture.js');

const CARDS = [401, 402, 403, 404, 405, 406, 407].map(id => ({ id, n: `卡${id}`, c: 'm' }));

const ACTION = actionData([
  { id: 401, segs: [{ acts: ['抽牌'], agent: '我方' }] },
  { id: 402, segs: [{ acts: ['抽牌'], agent: '對手' }] },
  { id: 403, segs: [{ acts: ['抽牌'], agent: '雙方各自' }] },
  { id: 404, segs: [{ acts: ['抽牌'], agent: '算我方' }] },
  { id: 405, segs: [{ acts: ['抽牌'], agent: '不限定' }] },
  // 誰比的是段:對手寫在沒有抽牌的那一段
  { id: 406, segs: [{ acts: ['特殊召喚'], agent: '對手' }, { acts: ['抽牌'], agent: '不限定' }] },
  { id: 407, segs: [{ acts: ['特殊召喚'], agent: '對手' }] },
]);

const sandbox = harness.load({ cards: CARDS, action: ACTION });
const ids = act => harness.ids(sandbox, {}, act);

test('誰選我方:寫明我方、雙方各自、算我方命中;對手與不限定不命中', () => {
  assert.deepStrictEqual(ids({ actions: ['抽牌'], agent: '我方' }), [401, 403, 404]);
});

test('誰選對手:寫明對手、雙方各自命中;算我方與不限定不命中', () => {
  assert.deepStrictEqual(ids({ actions: ['抽牌'], agent: '對手' }), [402, 403]);
});

test('勾「含不限定的」:不限定的段也命中;算我方不是不限定,查對手照樣不命中', () => {
  assert.deepStrictEqual(ids({ actions: ['抽牌'], agent: '我方', unrestricted: true }),
                         [401, 403, 404, 405, 406]);
  assert.deepStrictEqual(ids({ actions: ['抽牌'], agent: '對手', unrestricted: true }),
                         [402, 403, 405, 406]);
});

test('誰比的是段:對手寫在另一段時不命中', () => {
  assert.deepStrictEqual(ids({ actions: ['抽牌'], agent: '對手' }).indexOf(406), -1);
  assert.deepStrictEqual(ids({ actions: ['特殊召喚'], agent: '對手' }), [406, 407]);
});

test('沒選誰:結果與以前相同,勾不勾「含不限定的」都一樣', () => {
  const all = [401, 402, 403, 404, 405, 406];
  assert.deepStrictEqual(ids({ actions: ['抽牌'] }), all);
  assert.deepStrictEqual(ids({ actions: ['抽牌'], unrestricted: true }), all);
});

test('介面到查詢:誰換成 agent,「含不限定的」換成不限定開關', () => {
  const base = harness.rowQuery(sandbox, { actions: ['抽牌'] });
  assert.strictEqual('agent' in base, false);
  assert.strictEqual('include_unrestricted' in base, false);
  assert.deepStrictEqual(harness.rowQuery(sandbox, { actions: ['抽牌'], agent: '對手',
                                                     unrestricted: true }),
                         { ...base, agent: '對手', include_unrestricted: true });
});

/* ── 瀏覽紀錄與摺疊鈕 ───────────────────────────────────── */

const EMPTY_Q = { name: '', nameLang: 'zh', code: '', text: '' };
const DOM_SORT = { key: 'dom', dir: '' };

test('誰與「含不限定的」跟著存進瀏覽紀錄,還原後相同', () => {
  const st = { q: EMPTY_Q, sort: DOM_SORT,
               act: { actions: ['抽牌'], agent: '對手', unrestricted: true } };
  const saved = JSON.parse(JSON.stringify(harness.savedState(sandbox, st.q, st.sort, st.act)));
  assert.deepStrictEqual(harness.restoreSaved(sandbox, saved), st);
});

test('瀏覽紀錄裡認不得的誰或開關值忽略,其餘照常還原', () => {
  const good = { q: EMPTY_Q, sort: DOM_SORT, act: { actions: ['抽牌'] } };
  for (const act of [{ actions: ['抽牌'], agent: '雙方各自' },
                     { actions: ['抽牌'], agent: 'me' },
                     { actions: ['抽牌'], agent: ['我方'] },
                     { actions: ['抽牌'], unrestricted: 1 },
                     { actions: ['抽牌'], unrestricted: false }]) {
    assert.deepStrictEqual(harness.restoreSaved(sandbox, { ...good, act }), good,
                           JSON.stringify(act));
  }
});

test('摺疊鈕的條件數:選了誰多算一條;「含不限定的」不另算', () => {
  assert.strictEqual(harness.critCount(sandbox, EMPTY_Q, { actions: ['抽牌'], agent: '我方' }), 2);
  assert.strictEqual(harness.critCount(sandbox, EMPTY_Q,
                                       { actions: ['抽牌'], agent: '我方', unrestricted: true }), 2);
  assert.strictEqual(harness.critCount(sandbox, EMPTY_Q, { actions: ['抽牌'], unrestricted: true }),
                     1);
});
