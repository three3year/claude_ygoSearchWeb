/**
 * action_zones.test.js — 接縫三:動作搜尋的從、到、段類別、極性(action-search-web 票 09)
 *
 * 跑法:`node --test script/web/`
 *
 * 與 action.test.js 同一個沙箱:載入 `web/` 底下真實的前端檔,餵合成的卡片資料與
 * 一份小的動作索引(`action_fixture.js`)。測的是條件進去、命中的卡出來,以及介面選項換成
 * 的列查詢(spec「玩家介面」的對應表);不斷言 DOM 結構與 CSS class。
 */
'use strict';

const test = require('node:test');
const assert = require('node:assert');
const harness = require('./frontend_harness.js');
const { actionData } = require('./action_fixture.js');

/* ── 從、到 ─────────────────────────────────────────────── */

const ZONE_CARDS = [
  { id: 401, segs: [{ acts: ['特殊召喚'], lines: [{ from: [['墓地', '我方']], to: [['場上', '我方'], ['怪獸區', '我方']] }] }] },
  { id: 402, segs: [{ acts: ['特殊召喚'], lines: [{ from: [['墓地', '對手']], to: [['場上', '我方']] }] }] },
  { id: 403, segs: [{ acts: ['特殊召喚'], lines: [{ from: [['手牌', '我方']], to: [['場上', '我方']] }] }] },
  // 推得的從:玩家介面不算
  { id: 404, segs: [{ acts: ['特殊召喚'], lines: [{ from: [['墓地', '我方']], fromInferred: true }] }] },
  // 從、到分在同一段的兩條線上:要落在同一條線才算
  { id: 405, segs: [{ acts: ['特殊召喚'], lines: [{ from: [['墓地', '我方']] }, { to: [['手牌', '我方']] }] }] },
  // 做動作的一方那條線不算;物件表裡找不到的線不算
  { id: 406, segs: [{ acts: ['特殊召喚'], lines: [{ doer: true, from: [['墓地', '我方']] }] }] },
  { id: 407, segs: [{ acts: ['特殊召喚'], lines: [{ obj: false, from: [['墓地', '我方']] }] }] },
  { id: 408, segs: [{ acts: ['送墓'], lines: [{ from: [['場上', null]], to: [['墓地', '我方']] }] }] },
  { id: 409, segs: [{ acts: ['加入手牌'], lines: [{ from: [['牌組', '我方']], to: [['手牌', '我方']] }] }] },
  // 子區域:線上寫牌組頂,產物裡上位區域牌組也在
  { id: 410, segs: [{ acts: ['加入手牌'], lines: [{ from: [['牌組頂', '我方'], ['牌組', '我方']], to: [['手牌', '我方']] }] }] },
];
const zoneBox = harness.load({
  cards: ZONE_CARDS.map(c => ({ id: c.id, n: `卡${c.id}`, c: 'm' })),
  action: actionData(ZONE_CARDS),
});
const zoneIds = act => harness.ids(zoneBox, {}, act);

test('從:選區域得到從那裡做動作的卡;可以再指定哪一方', () => {
  assert.deepStrictEqual(zoneIds({ actions: ['特殊召喚'], from: { zone: '墓地' } }), [401, 402, 405]);
  assert.deepStrictEqual(zoneIds({ actions: ['特殊召喚'], from: { zone: '墓地', side: '對手' } }), [402]);
  assert.deepStrictEqual(zoneIds({ actions: ['特殊召喚'], from: { zone: '墓地', side: '我方' } }), [401, 405]);
});

test('到:選區域分得開送去墓地、加入手牌', () => {
  assert.deepStrictEqual(zoneIds({ to: { zone: '墓地' } }), [408]);
  assert.deepStrictEqual(zoneIds({ to: { zone: '手牌' } }), [405, 409, 410]);
  assert.deepStrictEqual(zoneIds({ actions: ['加入手牌'], to: { zone: '手牌', side: '對手' } }), []);
});

test('從和到要落在同一條線上', () => {
  // 405 的從墓地與到手牌在兩條線上
  assert.deepStrictEqual(zoneIds({ from: { zone: '墓地' }, to: { zone: '手牌' } }), []);
  assert.deepStrictEqual(zoneIds({ from: { zone: '牌組' }, to: { zone: '手牌' } }), [409, 410]);
  assert.deepStrictEqual(zoneIds({ from: { zone: '墓地', side: '我方' }, to: { zone: '場上' } }), [401]);
});

test('推得的從、到不算命中;做動作的一方、物件找不到的線也不算', () => {
  // 404 推得、406 做動作的一方、407 物件找不到:三張都從我方墓地
  const hit = zoneIds({ actions: ['特殊召喚'], from: { zone: '墓地', side: '我方' } });
  assert.ok(!hit.includes(404) && !hit.includes(406) && !hit.includes(407), String(hit));
});

test('子區域算在上位區域內;索引裡沒有的區域沒有卡命中', () => {
  assert.deepStrictEqual(zoneIds({ from: { zone: '牌組頂' } }), [410]);
  assert.deepStrictEqual(zoneIds({ from: { zone: '牌組' } }), [409, 410]);
  assert.deepStrictEqual(zoneIds({ from: { zone: '不存在的區域' } }), []);
});

test('從、到換成列查詢的 from_zones、to_zones;沒指定方時只比區域', () => {
  const rq = harness.rowQuery(zoneBox, { actions: ['特殊召喚'], from: { zone: '墓地', side: '對手' },
                                         to: { zone: '場上' } });
  assert.deepStrictEqual(rq.from_zones, [{ zone: '墓地', side: '對手' }]);
  assert.deepStrictEqual(rq.to_zones, [{ zone: '場上', side: null }]);
  assert.ok(!('from_zones' in harness.rowQuery(zoneBox, { actions: ['破壞'] })));
});

/* ── 段類別三個勾選、極性三選一 ─────────────────────────────
   介面選項換成列查詢(spec「玩家介面」對應表):勾效果 → 效果、召喚手續、限制;勾代價 → 代價;
   勾觸發條件 → 加上 條件(連同條件段開關,Python 的開關關著時會把 條件 從段類別拿掉)。
   極性:會做 → 做、可以、必須;限制 → 不能、只能;抗性 → 不會。 */

const KIND_CARDS = [
  { id: 501, segs: [{ kind: '效果', acts: ['破壞'] }] },
  { id: 502, segs: [{ kind: '召喚手續', acts: ['破壞'] }] },
  { id: 503, segs: [{ kind: '代價', acts: ['破壞'] }] },
  { id: 504, segs: [{ kind: '條件', acts: ['破壞'] }] },          // 相手がモンスターを破壊した時
  { id: 505, segs: [{ kind: '效果', pol: '不會', acts: ['破壞'] }] },   // 効果では破壊されない
  { id: 506, segs: [{ kind: '效果', pol: '不能', acts: ['破壞'] }] },
  { id: 507, segs: [{ kind: '效果', pol: '只能', acts: ['破壞'] }] },
  { id: 508, segs: [{ kind: '限制', pol: '不能', acts: ['通常召喚'] }] },  // このカードは通常召喚できない
  { id: 509, segs: [{ kind: '效果', pol: '可以', acts: ['破壞'] }] },
  { id: 510, segs: [{ kind: '條件', pol: '不會', acts: ['破壞'] }] },
];
const kindBox = harness.load({
  cards: KIND_CARDS.map(c => ({ id: c.id, n: `卡${c.id}`, c: 'm' })),
  action: actionData(KIND_CARDS),
});
const kindIds = act => harness.ids(kindBox, {}, act);
const rq = act => harness.rowQuery(kindBox, act);

test('段類別的勾選換成列查詢的段類別', () => {
  assert.deepStrictEqual(rq({ actions: ['破壞'], kinds: ['eff'] }).kinds, ['效果', '召喚手續', '限制']);
  assert.deepStrictEqual(rq({ actions: ['破壞'], kinds: ['cost'] }).kinds, ['代價']);
  const all = rq({ actions: ['破壞'], kinds: ['eff', 'cost', 'cond'] });
  assert.deepStrictEqual(all.kinds, ['效果', '召喚手續', '限制', '代價', '條件']);
  assert.strictEqual(all.include_condition, true);
  // 預設(勾效果與代價)的列查詢與票 08 相同
  assert.deepStrictEqual(rq({ actions: ['破壞'], kinds: ['cost', 'eff'] }),
                         { actions: ['破壞'], kinds: ['效果', '召喚手續', '限制', '代價'],
                           polarities: ['做', '可以', '必須'] });
});

test('極性三選一換成列查詢的極性', () => {
  assert.deepStrictEqual(rq({ actions: ['破壞'] }).polarities, ['做', '可以', '必須']);
  assert.deepStrictEqual(rq({ actions: ['破壞'], pol: 'limit' }).polarities, ['不能', '只能']);
  assert.deepStrictEqual(rq({ actions: ['破壞'], pol: 'resist' }).polarities, ['不會']);
});

test('預設勾效果與代價:勾「觸發條件」才查到條件段', () => {
  assert.deepStrictEqual(kindIds({ actions: ['破壞'] }), [501, 502, 503, 509]);
  assert.deepStrictEqual(kindIds({ actions: ['破壞'], kinds: ['eff', 'cost', 'cond'] }),
                         [501, 502, 503, 504, 509]);
  assert.deepStrictEqual(kindIds({ actions: ['破壞'], kinds: ['cond'] }), [504]);
  assert.deepStrictEqual(kindIds({ actions: ['破壞'], kinds: ['cost'] }), [503]);
});

test('極性「抗性」查得到「不會」、「限制」查得到「不能」「只能」;預設的「會做」都不命中它們', () => {
  assert.deepStrictEqual(kindIds({ actions: ['破壞'], pol: 'resist' }), [505]);
  assert.deepStrictEqual(kindIds({ actions: ['破壞'], pol: 'limit' }), [506, 507]);
  // 召喚條件區塊裡的限制段跟著「效果」算
  assert.deepStrictEqual(kindIds({ actions: ['通常召喚'], pol: 'limit' }), [508]);
  assert.deepStrictEqual(kindIds({ actions: ['通常召喚'] }), []);
  assert.deepStrictEqual(kindIds({ actions: ['破壞'], pol: 'resist', kinds: ['eff', 'cost', 'cond'] }),
                         [505, 510]);
});

test('只剩一個勾選時不能取消', () => {
  assert.deepStrictEqual(harness.toggleKind(kindBox, ['eff', 'cost'], 'cost'), ['eff']);
  assert.deepStrictEqual(harness.toggleKind(kindBox, ['eff'], 'eff'), ['eff']);
  assert.deepStrictEqual(harness.toggleKind(kindBox, ['cond'], 'cond'), ['cond']);
  assert.deepStrictEqual(harness.toggleKind(kindBox, ['eff'], 'cond'), ['eff', 'cond']);
  assert.deepStrictEqual(harness.toggleKind(kindBox, ['cond', 'eff'], 'cost'), ['eff', 'cost', 'cond']);
});

test('區域的選項由索引的表生成,依列數排', () => {
  // 列數:墓地 7、場上 4、手牌 4、牌組 2、怪獸區 1、牌組頂 1;同列數照索引的順序
  assert.deepStrictEqual(harness.zoneOptions(zoneBox),
                         ['墓地', '場上', '手牌', '牌組', '怪獸區', '牌組頂']);
});

/* ── 瀏覽紀錄與摺疊鈕 ───────────────────────────────────── */

const EMPTY_Q = { name: '', nameLang: 'zh', code: '', text: '' };
const DOM_SORT = { key: 'dom', dir: '' };

test('從、到、段類別、極性跟著查詢狀態存進瀏覽紀錄,還原後相同', () => {
  const act = { actions: ['特殊召喚'], from: { zone: '墓地', side: '對手' }, to: { zone: '場上' },
                kinds: ['eff', 'cond'], pol: 'resist' };
  const st = { q: EMPTY_Q, sort: DOM_SORT, act };
  const saved = JSON.parse(JSON.stringify(harness.savedState(zoneBox, st.q, st.sort, st.act)));
  assert.deepStrictEqual(harness.restoreSaved(zoneBox, saved), st);
});

test('預設值不寫進動作條件:勾效果與代價、極性「會做」等於沒選', () => {
  const none = { q: EMPTY_Q, sort: DOM_SORT };
  for (const act of [{ kinds: ['eff', 'cost'], pol: 'do' }, { kinds: ['cost', 'eff'] }, { pol: 'do' }]) {
    assert.deepStrictEqual(harness.savedState(zoneBox, EMPTY_Q, DOM_SORT, act), none,
                           JSON.stringify(act));
  }
  const withWord = harness.savedState(zoneBox, EMPTY_Q, DOM_SORT,
                                      { actions: ['破壞'], kinds: ['eff', 'cost'], pol: 'do' });
  assert.deepStrictEqual(withWord.act, { actions: ['破壞'] });
});

test('瀏覽紀錄裡認不得的從、到、段類別、極性忽略', () => {
  const good = { q: EMPTY_Q, sort: DOM_SORT, act: { actions: ['破壞'] } };
  for (const extra of [{ from: '墓地' }, { from: { side: '我方' } }, { to: { zone: 3 } },
                       { kinds: [] }, { kinds: ['zzz'] }, { kinds: 'eff' }, { pol: 'zzz' },
                       { pol: 3 }]) {
    const act = { actions: ['破壞'], ...extra };
    assert.deepStrictEqual(harness.restoreSaved(zoneBox, { ...good, act }), good,
                           JSON.stringify(extra));
  }
  // 方認不得:只留區域;段類別裡認不得的那個拿掉
  assert.deepStrictEqual(
    harness.restoreSaved(zoneBox, { ...good, act: { from: { zone: ' 墓地 ', side: '雙方' },
                                                    kinds: ['cond', 'zzz'] } }).act,
    { from: { zone: '墓地' }, kinds: ['cond'] });
});

test('摺疊鈕的生效條件數:從、到、段類別、極性不是預設時各算一條', () => {
  assert.strictEqual(harness.critCount(zoneBox, EMPTY_Q,
    { actions: ['破壞'], from: { zone: '墓地' }, to: { zone: '手牌' } }), 3);
  assert.strictEqual(harness.critCount(zoneBox, EMPTY_Q,
    { actions: ['破壞'], kinds: ['eff', 'cond'], pol: 'resist' }), 3);
  assert.strictEqual(harness.critCount(zoneBox, EMPTY_Q,
    { actions: ['破壞'], kinds: ['eff', 'cost'], pol: 'do' }), 1);
});
