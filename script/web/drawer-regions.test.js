/**
 * drawer-regions.test.js — 抽屜選項:區域三欄的玩家與區域選單(drawer-values 票 03)
 *
 * 跑法:`node --test script/web/drawer-regions.test.js`
 *
 * 接縫:條件模型 `Cond.drawerOptions(標籤)` 的區域欄 → 玩家清單(含狀態)與每個玩家的區域清單(含狀態)、
 * 已加入的項。經 harness 載入真前端程式,框表是手寫的小表。
 */
'use strict';

const test = require('node:test');
const assert = require('node:assert');
const harness = require('./frontend_harness.js');

const POLAR = ['肯定', '可能'];
const FRAME_VOCAB = {
  lemmas: ['ドロー', '破壊'],
  heads: [],
  domains: {
    位置: ['代價', '效果', '條件'],
    極性: ['肯定', '否定', '可能'],
    玩家: ['自分', '相手', 'お互い'],
    區域: ['墓地', '場上', '手牌'],
    動作對象: ['此卡', '非此卡'],
    施事者: ['自分', '相手', '此卡'],
    方式類: ['手段:效果', '其他'],
    態: ['他動', '受身'],
    否定形: ['受身', '不可能'],
    數量類: ['定數', '上限'],
    中心詞類: ['卡', '其他'],
    修飾語類: ['種族', '其他'],
  },
};

/* 框元組:[詞元, 位置, 極性, 態, 否定形, 施事者, 方式類, 動作對象, [來源對], [目的對], [所在對]]
   (欄序見 frameindex.py;列舉欄 +1,0 是沒有值;區域對 = 玩家序號 × 區域數 + 區域序號) */
const SCALARS = ['位置', '極性', '態', '否定形', '施事者', '方式類', '動作對象'];
const REGIONS = ['來源', '目的', '所在'];
const { 玩家: PLAYERS, 區域: ZONES } = FRAME_VOCAB.domains;
const regionCode = text => {
  const [player, zone] = text.split('.');
  return PLAYERS.indexOf(player) * ZONES.length + ZONES.indexOf(zone);
};
const frame = (lemma, fields) => [FRAME_VOCAB.lemmas.indexOf(lemma)]
  .concat(SCALARS.map(field => FRAME_VOCAB.domains[field].indexOf(fields[field]) + 1))
  .concat(REGIONS.map(field => (fields[field] || []).map(regionCode)));

const FRAMES = [
  frame('破壊', { 位置: '效果', 極性: '肯定', 施事者: '自分', 來源: ['自分.墓地'] }),
  frame('破壊', { 位置: '代價', 極性: '肯定', 來源: ['相手.場上'] }),
  frame('破壊', { 位置: '效果', 極性: '肯定', 施事者: '相手', 來源: ['相手.墓地'] }),
  frame('ドロー', { 位置: '效果', 極性: '肯定' }),
];
const CARDS = FRAMES.map((_, n) => ({ id: n + 1, n: '卡' + n, c: 'm', tx: ['①。'], fr: [[n]] }));

const row = (name, cards) => ({ name, path: [name], predicate: { 詞元: name, 極性: POLAR }, cards });
const CATALOG = [
  row('破壊', { 代價: 1, 效果: 2, 條件: 0 }),
  row('ドロー', { 代價: 0, 效果: 1, 條件: 0 }),
];

const box = harness.load({ cards: CARDS, frames: FRAMES, vocab: { frame: FRAME_VOCAB, catalog: CATALOG } });
const cond = (fn, ...args) => harness.cond(box, fn, ...args);
const tagAt = name => cond('tagAt', name, false);
const toggle = (tag, field, value) => cond('toggleValue', tag, field, value);

/* 區域欄壓成 {欄: {玩家(不限寫成 *): [狀態, {區域: 狀態}]}};沒列的欄不出現。 */
function regions(tag) {
  const out = {};
  for (const { fields } of cond('drawerOptions', tag)) {
    for (const f of fields.filter(f => f.kind === 'region')) {
      out[f.field] = Object.fromEntries(f.players.map(p => [p.value || '*',
        [p.state, Object.fromEntries(p.zones.map(z => [z.value, z.state]))]]));
    }
  }
  return out;
}

test('隱藏:玩家只列詞元在這一欄有的(不限一律列),區域只列詞元有的(任何玩家);詞元沒有的欄不列', () => {
  const menus = regions(tagAt('破壊'));
  assert.deepStrictEqual(Object.keys(menus), ['來源']);
  assert.deepStrictEqual(Object.keys(menus.來源), ['*', '自分', '相手']);
  for (const [, zones] of Object.values(menus.來源)) assert.deepStrictEqual(Object.keys(zones), ['墓地', '場上']);
  assert.deepStrictEqual(regions(tagAt('ドロー')), {});
});

test('灰色依玩家:效果位只有 自分・墓地 與 相手・墓地,場上對每個玩家都灰', () => {
  assert.deepStrictEqual(regions(tagAt('破壊')).來源, {
    '*': ['可按', { 墓地: '可按', 場上: '灰' }],
    自分: ['可按', { 墓地: '可按', 場上: '灰' }],
    相手: ['可按', { 墓地: '可按', 場上: '灰' }],
  });
});

test('灰色依其他欄:施事者 自分 後 相手 沒有區域命中,玩家也灰;加代價位後 相手・場上 可按', () => {
  const mine = toggle(tagAt('破壊'), '施事者', '自分');
  assert.deepStrictEqual(regions(mine).來源, {
    '*': ['可按', { 墓地: '可按', 場上: '灰' }],
    自分: ['可按', { 墓地: '可按', 場上: '灰' }],
    相手: ['灰', { 墓地: '灰', 場上: '灰' }],
  });
  const withCost = toggle(toggle(tagAt('破壊'), '位置', '代價'), '施事者', '自分');
  assert.deepStrictEqual(regions(withCost).來源.相手, ['灰', { 墓地: '灰', 場上: '灰' }]);
  assert.deepStrictEqual(regions(toggle(tagAt('破壊'), '位置', '代價')).來源, {
    '*': ['可按', { 墓地: '可按', 場上: '可按' }],
    自分: ['可按', { 墓地: '可按', 場上: '灰' }],
    相手: ['可按', { 墓地: '可按', 場上: '可按' }],
  });
});

test('同欄已加入的項不擋自己這一欄:加了 自分・墓地,相手・墓地 仍可按', () => {
  const tag = cond('addValue', tagAt('破壊'), '來源', ['自分', '墓地']);
  assert.deepStrictEqual(regions(tag).來源.相手, ['可按', { 墓地: '可按', 場上: '灰' }]);
});

/* 已加入的項:抽屜選項的 items,和 Cond.values 同序。 */
const itemsOf = (tag, field) => cond('drawerOptions', tag).flatMap(g => g.fields)
  .filter(f => f.field === field).map(f => f.items)[0];

test('已加入的項照列:詞元沒有的項(網址帶進來)也列,這一欄沒有可列的玩家與區域仍畫出來', () => {
  const odd = cond('addValue', tagAt('破壊'), '來源', ['お互い', '手牌']);
  assert.deepStrictEqual(itemsOf(odd, '來源'), [['お互い', '手牌']]);
  assert.deepStrictEqual(Object.keys(regions(odd).來源), ['*', '自分', '相手']);
  const draw = cond('addValue', tagAt('ドロー'), '所在', [null, '墓地']);
  assert.deepStrictEqual(itemsOf(draw, '所在'), [[null, '墓地']]);
  assert.deepStrictEqual(regions(draw), { 所在: { '*': ['灰', {}] } });
});

test('包含與排除同一份選項', () => {
  const tag = toggle(tagAt('破壊'), '施事者', '自分');
  assert.deepStrictEqual(regions(cond('setEx', tag, true)), regions(tag));
});
