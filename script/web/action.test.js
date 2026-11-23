/**
 * action.test.js — 接縫三(前端查詢引擎)的動作條件(action-search-web 票 08)
 *
 * 跑法:`node --test script/web/`
 *
 * 與 engine.test.js 同一個沙箱:載入 `web/` 底下真實的前端檔,餵合成的卡片資料與
 * 一份小的動作索引(`action_fixture.js` 照描述寫成產物的格式)。測的是條件進去、
 * 命中的卡出來;不斷言 DOM 結構與 CSS class。索引第一次載入的時機、載入中的顯示
 * 與區塊的版面走站主人工驗收(票 08 的 Comments)。
 */
'use strict';

const test = require('node:test');
const assert = require('node:assert');
const harness = require('./frontend_harness.js');
const { actionData } = require('./action_fixture.js');

const item = (code, zh) => ({ code, zh });

const VOCAB = {
  cat: { zh: '大類', items: [item('m', '怪獸'), item('s', '魔法'), item('t', '陷阱')] },
  race: { zh: '種族', items: [item('dragon', '龍族'), item('fiend', '惡魔族')] },
};

const CARDS = [
  { id: 101, n: '破壞龍', c: 'm', s: ['effect'], r: 'dragon', lv: 8 },
  { id: 102, n: '破壞惡魔', c: 'm', s: ['effect'], r: 'fiend', lv: 4 },
  { id: 103, n: '破壞與除外', c: 's', s: ['normal'] },
  { id: 104, n: '分段的破壞與除外', c: 't', s: ['normal'] },
  { id: 105, n: '沒有動作的卡', c: 'm', s: ['normal'], r: 'dragon', lv: 4 },
];

const ACTION = actionData([
  { id: 101, segs: [{ acts: ['破壞'] }] },
  { id: 102, segs: [{ kind: '代價', acts: ['破壞'] }] },
  { id: 103, segs: [{ acts: ['破壞', '除外'] }] },
  { id: 104, segs: [{ acts: ['破壞'] }, { acts: ['除外'] }] },
]);

const sandbox = harness.load({ cards: CARDS, vocab: VOCAB, meta: {}, action: ACTION });
const ids = (q, act) => harness.ids(sandbox, q || {}, act);

test('選一個動作詞:得到卡文裡有這個動作的卡', () => {
  assert.deepStrictEqual(ids({}, { actions: ['破壞'] }), [101, 102, 103, 104]);
  assert.deepStrictEqual(ids({}, { actions: ['除外'] }), [103, 104]);
});

test('選兩個動作詞:只命中同一段裡兩個都有的卡', () => {
  // 104 有破壞也有除外,但分在兩段
  assert.deepStrictEqual(ids({}, { actions: ['破壞', '除外'] }), [103]);
  // 選的順序不影響
  assert.deepStrictEqual(ids({}, { actions: ['除外', '破壞'] }), [103]);
});

test('動作條件和卡片條件取且', () => {
  assert.deepStrictEqual(ids({ race: { dragon: 1 } }, { actions: ['破壞'] }), [101]);
  assert.deepStrictEqual(ids({ cat: { m: 1 } }, { actions: ['除外'] }), []);
  assert.deepStrictEqual(ids({ name: '分段' }, { actions: ['除外'] }), [104]);
});

test('沒有動作條件時結果與現在相同,而且不碰動作索引', () => {
  const plain = harness.load({ cards: CARDS, vocab: VOCAB, meta: {} });   // 沒有動作索引
  for (const q of [{}, { race: { dragon: 1 } }, { name: '破壞' }]) {
    const before = harness.ids(plain, q);
    assert.deepStrictEqual(ids(q), before, JSON.stringify(q));
    // 動作條件空著(沒選任何動作詞)等於沒有動作條件;索引沒載入也照常查
    assert.deepStrictEqual(harness.ids(plain, q, { actions: [] }), before, JSON.stringify(q));
    assert.deepStrictEqual(harness.ids(plain, q, {}), before, JSON.stringify(q));
  }
});

test('索引裡沒有的動作詞:沒有卡命中', () => {
  assert.deepStrictEqual(ids({}, { actions: ['不存在的動作'] }), []);
  assert.deepStrictEqual(ids({}, { actions: ['破壞', '不存在的動作'] }), []);
});

/* 玩家介面的預設(spec「玩家介面」對應表):這張票還沒有段類別與極性的選項,
   比對用勾「效果」「代價」、極性「會做」。 */
const DEFAULTS = actionData([
  { id: 201, segs: [{ kind: '效果', acts: ['破壞'] }] },
  { id: 202, segs: [{ kind: '召喚手續', acts: ['破壞'] }] },
  { id: 203, segs: [{ kind: '限制', pol: '做', acts: ['破壞'] }] },
  { id: 204, segs: [{ kind: '代價', acts: ['破壞'] }] },
  { id: 205, segs: [{ kind: '條件', acts: ['破壞'] }] },
  { id: 206, segs: [{ kind: '被代替', acts: ['破壞'] }] },
  { id: 207, segs: [{ kind: '修飾', acts: ['破壞'] }] },
  { id: 208, segs: [{ kind: '效果', replacing: true, acts: ['破壞'] }] },
  { id: 211, segs: [{ pol: '可以', acts: ['破壞'] }] },
  { id: 212, segs: [{ pol: '必須', acts: ['破壞'] }] },
  { id: 213, segs: [{ pol: '不能', acts: ['破壞'] }] },
  { id: 214, segs: [{ pol: '只能', acts: ['破壞'] }] },
  { id: 215, segs: [{ pol: '不會', acts: ['破壞'] }] },
]);
const DEFAULT_CARDS = [201, 202, 203, 204, 205, 206, 207, 208, 211, 212, 213, 214, 215]
  .map(id => ({ id, n: `卡${id}`, c: 'm' }));

test('預設的段類別:效果(含召喚手續、限制)與代價;條件、被代替、修飾、做代替的段不算', () => {
  const box = harness.load({ cards: DEFAULT_CARDS, vocab: VOCAB, meta: {}, action: DEFAULTS });
  const hit = harness.ids(box, {}, { actions: ['破壞'] });
  assert.deepStrictEqual(hit.filter(id => id < 210), [201, 202, 203, 204]);
});

test('預設的極性「會做」:做、可以、必須;不能、只能、不會不算', () => {
  const box = harness.load({ cards: DEFAULT_CARDS, vocab: VOCAB, meta: {}, action: DEFAULTS });
  const hit = harness.ids(box, {}, { actions: ['破壞'] });
  assert.deepStrictEqual(hit.filter(id => id > 210), [211, 212]);
});

/* ── 動作詞的選項 ─────────────────────────────────────────
   選項由動作索引帶的表生成(HTML 不手抄):依列數排,前面一批直接顯示,其餘收在「更多」。 */

test('動作詞的選項依列數排,前面一批直接顯示、其餘在「更多」', () => {
  const words = Array.from({ length: 20 }, (_, i) => `動作${String(i).padStart(2, '0')}`);
  // 列數:動作00 最少、動作19 最多;另有一個只出現在解析不出的段裡、0 列的詞
  const data = actionData([{ id: 301, segs: words.map((w, i) => ({ acts: [w], rows: i + 1 })) }]);
  data.actions.push(['只在字面', 0]);
  const box = harness.load({ cards: [{ id: 301, n: '卡' }], action: data });
  const opts = harness.actionOptions(box);
  const all = opts.shown.concat(opts.more);
  assert.deepStrictEqual(all, words.slice().reverse());
  assert.ok(opts.shown.length > 0 && opts.more.length > 0);
  // 0 列的詞選了也不會有卡命中,不列
  assert.ok(all.indexOf('只在字面') < 0);
});

test('列數相同時照索引的順序排(每次一樣)', () => {
  const data = actionData([{ id: 301, segs: [{ acts: ['乙', '甲', '丙'] }] }]);
  const box = harness.load({ cards: [{ id: 301, n: '卡' }], action: data });
  const opts = harness.actionOptions(box);
  assert.deepStrictEqual(opts.shown.concat(opts.more), data.actions.map(a => a[0]));
});

/* ── 瀏覽紀錄與摺疊鈕 ───────────────────────────────────── */

const EMPTY_Q = { name: '', nameLang: 'zh', code: '', text: '' };
const DOM_SORT = { key: 'dom', dir: '' };

test('動作條件跟著查詢狀態存進瀏覽紀錄,還原後相同', () => {
  const st = { q: { ...EMPTY_Q, cat: { s: 1 } }, sort: DOM_SORT,
               act: { actions: ['破壞', '除外'] } };
  const saved = JSON.parse(JSON.stringify(harness.savedState(sandbox, st.q, st.sort, st.act)));
  assert.deepStrictEqual(harness.restoreSaved(sandbox, saved), st);
  // 還原出來的條件查得到同一批卡
  const back = harness.restoreSaved(sandbox, saved);
  assert.deepStrictEqual(ids(back.q, back.act), [103]);
  // 沒有動作條件的一筆長得和以前一樣(票 01 寫的舊紀錄照常還原)
  assert.deepStrictEqual(harness.savedState(sandbox, EMPTY_Q, DOM_SORT, null),
                         { q: EMPTY_Q, sort: DOM_SORT });
  assert.deepStrictEqual(harness.savedState(sandbox, EMPTY_Q, DOM_SORT, { actions: [] }),
                         { q: EMPTY_Q, sort: DOM_SORT });
});

test('瀏覽紀錄裡的動作條件:認不得的欄位或值忽略,其餘照常還原', () => {
  const good = { q: EMPTY_Q, sort: DOM_SORT, act: { actions: ['破壞'] } };
  for (const act of [{ actions: ['破壞'], zzz: 1 },
                     { actions: ['破壞', 3, null, '', ' '] },
                     { actions: ['破壞', '破壞'] },
                     { actions: [' 破壞 '] }]) {
    assert.deepStrictEqual(harness.restoreSaved(sandbox, { ...good, act }), good,
                           JSON.stringify(act));
  }
  const none = { q: EMPTY_Q, sort: DOM_SORT };
  for (const act of [null, 'actions=破壞', 42, [], {}, { actions: '破壞' }, { actions: [] }]) {
    assert.deepStrictEqual(harness.restoreSaved(sandbox, { ...none, act }), none,
                           JSON.stringify(act));
  }
});

test('摺疊鈕的生效條件數把動作條件算進去', () => {
  assert.strictEqual(harness.critCount(sandbox, EMPTY_Q, { actions: ['破壞'] }), 1);
  // 動作詞選幾個都是一條條件
  assert.strictEqual(harness.critCount(sandbox, { ...EMPTY_Q, race: { dragon: 1 } },
                                       { actions: ['破壞', '除外'] }), 2);
  assert.strictEqual(harness.critCount(sandbox, EMPTY_Q, { actions: [] }), 0);
  assert.strictEqual(harness.critCount(sandbox, EMPTY_Q, null), 0);
});
