/**
 * drawer-options.test.js — 抽屜選項:選值鈕的隱藏與灰色(drawer-values 票 02)
 *
 * 跑法:`node --test script/web/drawer-options.test.js`
 *
 * 接縫:條件模型 `Cond.drawerOptions(標籤)` → 分組 → 欄 → 值與狀態(亮、鎖住、可按、灰)。
 * 經 harness 載入真前端程式,框表是手寫的小表;全語料核對用真 data.js 與 `Engine.runQuery` 的張數。
 * 區域三欄(票 03)與中心詞兩欄(票 04)的例子各在自己的檔。
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
    玩家: ['自分', '相手'],
    區域: ['墓地', '場上'],
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
  frame('破壊', { 位置: '效果', 極性: '肯定', 施事者: '自分', 動作對象: '非此卡', 態: '他動' }),
  frame('破壊', { 位置: '代價', 極性: '肯定', 施事者: '相手', 動作對象: '此卡' }),
  frame('破壊', { 位置: '效果', 極性: '否定', 否定形: '受身', 動作對象: '此卡' }),
  frame('破壊', { 位置: '條件', 極性: '可能' }),
  frame('ドロー', { 位置: '效果', 極性: '肯定' }),
];
const CARDS = FRAMES.map((_, n) => ({ id: n + 1, n: '卡' + n, c: 'm', tx: ['①。'], fr: [[n]] }));

const row = (name, cards) => ({ name, path: [name], predicate: { 詞元: name, 極性: POLAR }, cards });
const CATALOG = [
  row('破壊', { 代價: 1, 效果: 2, 條件: 1 }),
  row('ドロー', { 代價: 0, 效果: 1, 條件: 0 }),
];

const box = harness.load({ cards: CARDS, frames: FRAMES, vocab: { frame: FRAME_VOCAB, catalog: CATALOG } });
const cond = (fn, ...args) => harness.cond(box, fn, ...args);
const tagAt = name => cond('tagAt', name, false);

function chips(tag) {
  const out = {};
  for (const { group, fields } of cond('drawerOptions', tag)) {
    out[group] = {};
    for (const f of fields) {
      out[group][f.field] = f.kind !== 'values' ? f.kind
        : Object.fromEntries(f.values.map(v => [v.value, v.state]));
    }
  }
  return out;
}

test('只列詞元有的值:破壊 沒有的施事者 此卡、態 受身、否定形 不可能 不列,整欄沒有值的不列', () => {
  assert.deepStrictEqual(chips(tagAt('破壊')), {
    常用: {
      位置: { 代價: '可按', 效果: '鎖住', 條件: '可按' },
      極性: { 肯定: '亮', 否定: '可按', 可能: '亮' },
      動作對象: { 此卡: '灰', 非此卡: '可按' },
      施事者: { 自分: '可按', 相手: '灰' },
    },
    進階: {
      態: { 他動: '可按' },
      否定形: { 受身: '灰' },
    },
  });
});

test('欄全空不列、進階全空不列組:ドロー 只剩位置與極性', () => {
  assert.deepStrictEqual(chips(tagAt('ドロー')), {
    常用: {
      位置: { 效果: '鎖住' },
      極性: { 肯定: '亮', 可能: '亮' },
    },
  });
});

const toggle = (tag, field, value) => cond('toggleValue', tag, field, value);

test('灰色依其他欄:施事者 相手 只在代價位,加上代價位後可按', () => {
  const tag = tagAt('破壊');
  assert.deepStrictEqual(chips(tag).常用.施事者, { 自分: '可按', 相手: '灰' });
  const withCost = toggle(tag, '位置', '代價');
  assert.deepStrictEqual(chips(withCost).常用.施事者, { 自分: '可按', 相手: '可按' });
  assert.deepStrictEqual(chips(withCost).常用.位置, { 代價: '亮', 效果: '亮', 條件: '可按' });
});

test('同欄已選一值:另一值本身沒命中仍是灰,不看按下去的張數', () => {
  const mine = toggle(tagAt('破壊'), '施事者', '自分');
  assert.deepStrictEqual(chips(mine).常用.施事者, { 自分: '亮', 相手: '灰' });
});

test('其他欄含位置與極性:判位置的鈕看極性,判極性的鈕看位置', () => {
  const onlyDenied = toggle(toggle(toggle(tagAt('破壊'), '極性', '否定'), '極性', '肯定'), '極性', '可能');
  assert.deepStrictEqual(chips(onlyDenied).常用.極性, { 肯定: '可按', 否定: '鎖住', 可能: '灰' });
  assert.deepStrictEqual(chips(onlyDenied).常用.位置, { 代價: '灰', 效果: '鎖住', 條件: '灰' });
  const atCondition = toggle(toggle(tagAt('破壊'), '位置', '條件'), '位置', '效果');
  assert.deepStrictEqual(chips(atCondition).常用.極性, { 肯定: '亮', 否定: '灰', 可能: '亮' });
});

test('否定形:預設極性下是灰,加極性否定後可按;詞元沒有否定形整欄不列', () => {
  const tag = tagAt('破壊');
  assert.deepStrictEqual(chips(tag).進階.否定形, { 受身: '灰' });
  assert.deepStrictEqual(chips(toggle(tag, '極性', '否定')).進階.否定形, { 受身: '可按' });
  assert.strictEqual(chips(toggle(tagAt('ドロー'), '極性', '否定')).進階, undefined);
});

test('亮著的值一律列出:詞元沒有的值(網址帶進來)照列、亮著,可關', () => {
  const odd = toggle(tagAt('ドロー'), '施事者', '此卡');
  assert.deepStrictEqual(chips(odd).常用.施事者, { 此卡: '亮' });
  assert.deepStrictEqual(toggle(odd, '施事者', '此卡'), tagAt('ドロー'));
});

test('位置、極性最後一顆鎖住,兩顆亮著時都不鎖', () => {
  const tag = tagAt('破壊');
  assert.strictEqual(chips(tag).常用.位置.效果, '鎖住');
  const only = toggle(tag, '極性', '肯定');
  assert.deepStrictEqual(chips(only).常用.極性, { 肯定: '可按', 否定: '可按', 可能: '鎖住' });
  assert.deepStrictEqual(toggle(only, '極性', '可能'), only);
});

test('還原:鎖住後還原回來源那一列,極性解鎖', () => {
  const back = cond('restore', toggle(tagAt('破壊'), '極性', '肯定'));
  assert.deepStrictEqual(back, tagAt('破壊'));
  assert.deepStrictEqual(chips(back).常用.極性, { 肯定: '亮', 否定: '可按', 可能: '亮' });
});

test('包含與排除得到同一份選項', () => {
  const tag = toggle(tagAt('破壊'), '施事者', '自分');
  assert.deepStrictEqual(cond('drawerOptions', cond('setEx', tag, true)), cond('drawerOptions', tag));
});

test('全語料:75 張單詞標籤,可按的鈕加上去有卡、灰鈕只留它沒卡、隱藏的值放開位置與極性仍沒卡', t => {
  const data = harness.realData();
  if (!data) {
    t.skip('缺 web/data.js,略過全語料對照');
    return;
  }
  const real = harness.load(data);
  const countOf = tag => harness.ids(real, harness.cond(real, 'soloQuery', tag)).length;
  const withOnly = (tag, field, value) => ({ ...tag, pred: { ...tag.pred, [field]: [value] } });
  const single = data.vocab.catalog.filter(row => row.predicate &&
    Object.keys(row.predicate).every(field => field === '詞元' || field === '極性'));
  const wrong = [];
  const seen = { 可按: 0, 灰: 0, 隱藏: 0 };
  for (const row of single) {
    const tag = harness.cond(real, 'tagAt', row.path.join('›'), false);
    const fields = harness.cond(real, 'drawerOptions', tag).flatMap(g => g.fields)
      .filter(f => f.kind === 'values');
    const listed = new Map(fields.map(f => [f.field, f.values.map(v => v.value)]));
    for (const { field, values } of fields) {
      for (const { value, state } of values) {
        if (state === '可按') {
          seen.可按++;
          const n = countOf(harness.cond(real, 'toggleValue', tag, field, value));
          if (n === 0) wrong.push(`${row.name} ${field}=${value} 可按但 0 張`);
        } else if (state === '灰') {
          seen.灰++;
          const n = countOf(withOnly(tag, field, value));
          if (n !== 0) wrong.push(`${row.name} ${field}=${value} 灰但 ${n} 張`);
        }
      }
    }
    for (const field of ['位置', '極性', '動作對象', '施事者', '數量類', '方式類', '態', '否定形', '中心詞類', '修飾語類']) {
      for (const value of data.vocab.frame.domains[field]) {
        if ((listed.get(field) || []).indexOf(value) >= 0) continue;
        seen.隱藏++;
        const n = countOf({ ex: false, pred: { 詞元: tag.pred.詞元, [field]: [value] } });
        if (n !== 0) wrong.push(`${row.name} ${field}=${value} 隱藏但放開位置與極性有 ${n} 張`);
      }
    }
  }
  t.diagnostic(`可按 ${seen.可按}、灰 ${seen.灰}、隱藏 ${seen.隱藏}`);
  assert.strictEqual(single.length, 75);
  assert.deepStrictEqual(wrong, []);
});
