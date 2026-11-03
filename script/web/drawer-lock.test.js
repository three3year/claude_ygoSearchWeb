/**
 * drawer-lock.test.js — 鎖住的欄:區域欄(drawer-lock 票 02)
 *
 * 跑法:`node --test script/web/drawer-lock.test.js`
 *
 * 接縫:條件模型 `Cond.drawerOptions(標籤)`、`addValue`/`removeValue`/`toggleValue`、`tagAt`、`fromPairs`。
 * 經 harness 載入真前端程式,框表是手寫的小表。
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

const frame = (詞元, fields) => harness.frame(FRAME_VOCAB, { 詞元, ...fields });

const FRAMES = [
  frame('破壊', { 位置: '效果', 極性: '肯定', 施事者: '自分', 動作對象: '非此卡', 所在: ['相手.場上'] }),
  frame('破壊', { 位置: '代價', 極性: '肯定', 施事者: '相手', 所在: ['相手.場上'] }),
  frame('破壊', { 位置: '效果', 極性: '肯定', 施事者: '此卡', 所在: ['自分.墓地'] }),
  frame('破壊', { 位置: '效果', 極性: '否定', 態: '受身', 否定形: '受身', 所在: ['相手.場上'] }),
  frame('破壊', { 位置: '效果', 極性: '肯定', 來源: ['自分.手牌'], 所在: ['相手.場上'] }),
  frame('破壊', { 位置: '效果', 極性: '肯定', 來源: ['相手.墓地'], 所在: ['自分.墓地'] }),
  frame('ドロー', { 位置: '效果', 極性: '肯定' }),
];
const CARDS = FRAMES.map((_, n) => ({ id: n + 1, n: '卡' + n, c: 'm', tx: ['①。'], fr: [[n]] }));

const LEAF = '破壊@相手フィールド';
const AT_ENEMY_FIELD = [['相手', '場上']];
const row = (name, path, predicate, cards) => ({ name, path, predicate: { 極性: POLAR, ...predicate }, cards });
const CATALOG = [
  row('破壊', ['破壊'], { 詞元: '破壊' }, { 代價: 1, 效果: 5, 條件: 0 }),
  row(LEAF, ['破壊', LEAF], { 詞元: '破壊', 所在: AT_ENEMY_FIELD }, { 代價: 1, 效果: 3, 條件: 0 }),
  row('破壊(耐性)', ['破壊(耐性)'], { 詞元: '破壊', 極性: ['否定'], 否定形: ['受身'] }, { 代價: 0, 效果: 1, 條件: 0 }),
  row('ドロー', ['ドロー'], { 詞元: 'ドロー' }, { 代價: 0, 效果: 1, 條件: 0 }),
];

const box = harness.load({ cards: CARDS, frames: FRAMES, vocab: { frame: FRAME_VOCAB, catalog: CATALOG } });
const cond = (fn, ...args) => harness.cond(box, fn, ...args);
const tagAt = path => cond('tagAt', path, false);
const leafTag = () => tagAt('破壊›' + LEAF);

/* 選值欄 → {值: 狀態};區域欄鎖住 → ['鎖住', 來源名字, 項];沒鎖 → {玩家: [狀態, {區域: 狀態}]}。 */
function drawer(tag) {
  const out = {};
  for (const { group, fields } of cond('drawerOptions', tag)) {
    out[group] = {};
    for (const f of fields) {
      if (f.kind === 'values') out[group][f.field] = Object.fromEntries(f.values.map(v => [v.value, v.state]));
      else if (f.lock) out[group][f.field] = ['鎖住', f.lock, f.items];
      else if (f.kind === 'region') {
        out[group][f.field] = Object.fromEntries(f.players.map(p => [p.value || '*',
          [p.state, Object.fromEntries(p.zones.map(z => [z.value, z.state]))]]));
      } else out[group][f.field] = f.kind;
    }
  }
  return out;
}

test('條件葉標籤:鎖住的區域欄只帶鎖住的項與來源名字,不帶玩家與區域選單', () => {
  const option = cond('drawerOptions', leafTag()).flatMap(g => g.fields).find(f => f.field === '所在');
  assert.deepStrictEqual(option, { field: '所在', kind: 'region', lock: LEAF, items: AT_ENEMY_FIELD });
});

test('其他欄只列 詞元+鎖住的欄 出現過的值:施事者 此卡、來源 墓地 只在別的所在,不列;施事者 相手 只在代價位,仍灰', () => {
  assert.deepStrictEqual(drawer(leafTag()), {
    常用: {
      位置: { 代價: '可按', 效果: '鎖住' },
      極性: { 肯定: '亮', 否定: '可按', 可能: '亮' },
      來源: { '*': ['可按', { 手牌: '可按' }], 自分: ['可按', { 手牌: '可按' }] },
      所在: ['鎖住', LEAF, AT_ENEMY_FIELD],
      動作對象: { 非此卡: '可按' },
      施事者: { 自分: '可按', 相手: '灰' },
    },
    進階: {
      態: { 受身: '灰' },
      否定形: { 受身: '灰' },
    },
  });
});

test('沒有鎖住欄的標籤照舊只看詞元:破壊 列出施事者 此卡、來源 相手・墓地', () => {
  const options = drawer(tagAt('破壊')).常用;
  assert.deepStrictEqual(options.施事者, { 自分: '可按', 相手: '灰', 此卡: '可按' });
  assert.deepStrictEqual(Object.keys(options.來源), ['*', '自分', '相手']);
  assert.deepStrictEqual(Object.keys(options.來源['*'][1]), ['墓地', '手牌']);
});

const lockOf = (tag, field) => (cond('drawerOptions', tag).flatMap(g => g.fields).find(f => f.field === field) || {}).lock;

test('鎖住的欄改不動:addValue、removeValue、toggleValue 回傳原標籤;否定形這類選值欄同樣', () => {
  const tag = leafTag();
  assert.deepStrictEqual(cond('addValue', tag, '所在', ['自分', '墓地']), tag);
  assert.deepStrictEqual(cond('removeValue', tag, '所在', ['相手', '場上']), tag);
  assert.deepStrictEqual(cond('toggleValue', tag, '所在', ['相手', '場上']), tag);
  assert.deepStrictEqual(cond('toggleValue', tag, '所在', [null, '墓地']), tag);
  const resist = tagAt('破壊(耐性)');
  assert.deepStrictEqual(cond('toggleValue', resist, '否定形', '受身'), resist);
  assert.deepStrictEqual(cond('addValue', resist, '否定形', '不可能'), resist);
});

test('鎖住的標籤其他欄照常改;還原、切換包含/排除不影響鎖', () => {
  const mine = cond('toggleValue', leafTag(), '施事者', '自分');
  assert.deepStrictEqual(mine.pred.施事者, ['自分']);
  assert.strictEqual(lockOf(mine, '所在'), LEAF);
  assert.deepStrictEqual(cond('addValue', mine, '所在', ['自分', '墓地']), mine);
  assert.strictEqual(lockOf(cond('restore', mine), '所在'), LEAF);
  assert.strictEqual(lockOf(cond('setEx', mine, true), '所在'), LEAF);
});

test('從詞元節點加的標籤不鎖;自己改成和條件葉一樣也不鎖,剛加的項拿得掉', () => {
  assert.strictEqual(lockOf(tagAt('破壊'), '所在'), undefined);
  const same = cond('addValue', tagAt('破壊'), '所在', ['相手', '場上']);
  assert.deepStrictEqual(same.pred, leafTag().pred);
  assert.strictEqual(lockOf(same, '所在'), undefined);
  assert.ok(drawer(same).常用.所在['*']);
  assert.deepStrictEqual(cond('removeValue', same, '所在', ['相手', '場上']), tagAt('破壊'));
});

const pairsOf = tag => cond('toPairs', tag);

test('讀網址:欄位等於條件葉就鎖(寫路徑與寫欄位對都一樣);另加一欄不鎖;只差位置仍鎖', () => {
  assert.strictEqual(lockOf(cond('fromPairs', pairsOf(leafTag()), false), '所在'), LEAF);
  const fromLemma = cond('addValue', tagAt('破壊'), '所在', ['相手', '場上']);
  assert.strictEqual(lockOf(cond('fromPairs', pairsOf(fromLemma), false), '所在'), LEAF);
  const extra = cond('toggleValue', leafTag(), '施事者', '自分');
  assert.strictEqual(lockOf(cond('fromPairs', pairsOf(extra), false), '所在'), undefined);
  const moved = cond('toggleValue', cond('toggleValue', leafTag(), '位置', '代價'), '位置', '效果');
  assert.deepStrictEqual(moved.pred.位置, ['代價']);
  assert.strictEqual(lockOf(cond('fromPairs', pairsOf(moved), true), '所在'), LEAF);
});

test('網址往返:條件葉標籤只寫路徑,讀回來仍鎖;舊網址的欄位對照樣讀進來、查到的卡不變', () => {
  const st = { cond: { and: [leafTag()], or: [], orSide: [] } };
  const hash = harness.hash(box, st);
  assert.strictEqual(hash, 'act=' + encodeURIComponent('破壊›' + LEAF));
  const [back] = harness.parseHash(box, hash).cond.and;
  assert.strictEqual(lockOf(back, '所在'), LEAF);
  const pairs = 'act=' + [['詞元', '破壊'], ['所在', '相手.場上'], ['極性', '肯定', '可能']]
    .map(([f, ...v]) => encodeURIComponent(f) + ':' + v.map(encodeURIComponent).join('~')).join(';');
  const [old] = harness.parseHash(box, pairs).cond.and;
  assert.strictEqual(lockOf(old, '所在'), LEAF);
  assert.deepStrictEqual(harness.ids(box, cond('soloQuery', old)), harness.ids(box, cond('soloQuery', leafTag())));
});

test('包含與排除同一份選項', () => {
  const tag = cond('toggleValue', leafTag(), '施事者', '自分');
  assert.deepStrictEqual(cond('drawerOptions', cond('setEx', tag, true)), cond('drawerOptions', tag));
});
