/**
 * head-options.test.js — 抽屜選項:中心詞兩欄只能挑清單(drawer-values 票 04)
 *
 * 跑法:`node --test script/web/head-options.test.js`
 *
 * 接縫:條件模型 `Cond.drawerOptions(標籤)` 的中心詞欄(`{field, kind: 'text', candidates}`)。
 * 經 harness 載入真前端程式,框表是手寫的小表。收字(清單外的字不收)在 typed_commit.test.js。
 */
'use strict';

const test = require('node:test');
const assert = require('node:assert');
const harness = require('./frontend_harness.js');

const POLAR = ['肯定', '可能'];
const HEADS = ['モンスター', 'カード', '魔法', '罠', '効果モンスター', '手札'];
const DOMAINS = {
  位置: ['代價', '效果', '條件'],
  極性: ['肯定', '否定', '可能'],
  玩家: ['自分', '相手'],
  區域: ['墓地', '場上'],
  施事者: ['自分', '相手'],
  動作對象: ['此卡', '非此卡'],
  方式類: ['其他'],
  態: ['他動'],
  否定形: ['受身'],
  數量類: ['定數'],
  中心詞類: ['卡'],
  修飾語類: ['種族'],
};

function frameOf(vocab, lemma, { 位置, 極性, 施事者, 受事者 = [], 目的 = [] }) {
  const code = (field, v) => vocab.domains[field].indexOf(v) + 1;
  const segs = words => words.map(w => [vocab.heads.indexOf(w), 0, 0, 0]);
  return [vocab.lemmas.indexOf(lemma), code('位置', 位置), code('極性', 極性), 0, 0,
    施事者 ? code('施事者', 施事者) : 0, 0, 0, [], [], [], segs(受事者), segs(目的)];
}

const row = (name, cards) => ({ name, path: [name], predicate: { 詞元: name, 極性: POLAR }, cards });

function load(heads, frames) {
  const vocab = { lemmas: ['ドロー', '破壊'], heads, domains: DOMAINS };
  const list = frames(vocab);
  const cards = list.map((_, n) => ({ id: n + 1, n: '卡' + n, c: 'm', tx: ['①。'], fr: [[n]] }));
  const catalog = [row('破壊', { 代價: 1, 效果: 4, 條件: 0 }), row('ドロー', { 代價: 0, 效果: 1, 條件: 0 })];
  return harness.load({ cards, frames: list, vocab: { frame: vocab, catalog } });
}

const box = load(HEADS, vocab => [
  frameOf(vocab, '破壊', { 位置: '效果', 極性: '肯定', 施事者: '自分', 受事者: ['カード', '魔法'] }),
  frameOf(vocab, '破壊', { 位置: '效果', 極性: '肯定', 施事者: '相手', 受事者: ['モンスター'], 目的: ['手札'] }),
  frameOf(vocab, '破壊', { 位置: '代價', 極性: '肯定', 受事者: ['罠'] }),
  frameOf(vocab, '破壊', { 位置: '效果', 極性: '否定', 受事者: ['効果モンスター'] }),
  frameOf(vocab, 'ドロー', { 位置: '效果', 極性: '肯定' }),
]);
const cond = (fn, ...args) => harness.cond(box, fn, ...args);
const tagAt = (name, ex) => cond('tagAt', name, !!ex);

function heads(tag, on = box) {
  const out = {};
  for (const { fields } of harness.cond(on, 'drawerOptions', tag)) {
    for (const f of fields) if (f.kind === 'text') out[f.field] = f.candidates;
  }
  return out;
}

test('候選只列其他欄成立的框上出現過的中心詞,依中心詞表順序', () => {
  assert.deepStrictEqual(heads(tagAt('破壊')), {
    受事者中心詞: ['モンスター', 'カード', '魔法'],
    目的中心詞: ['手札'],
  });
});

test('其他欄跟著縮:施事者 自分 只剩那個框上的中心詞;放開位置才有的 罠 照樣不列', () => {
  const tag = cond('addValue', tagAt('破壊'), '施事者', '自分');
  assert.deepStrictEqual(heads(tag).受事者中心詞, ['カード', '魔法']);
});

test('加了極性否定:否定框上的 効果モンスター 才列', () => {
  const tag = cond('addValue', tagAt('破壊'), '極性', '否定');
  assert.deepStrictEqual(heads(tag).受事者中心詞, ['モンスター', 'カード', '魔法', '効果モンスター']);
});

test('已加入的詞不重複列;它自己這一欄不擋其他候選', () => {
  const tag = cond('addValue', tagAt('破壊'), '受事者中心詞', 'カード');
  assert.deepStrictEqual(heads(tag).受事者中心詞, ['モンスター', '魔法']);
});

test('詞元在這一欄沒有中心詞、也沒有已加入的詞:整欄不列', () => {
  assert.deepStrictEqual(heads(tagAt('ドロー')), {});
});

test('網址帶進來的清單外的詞:照列這一欄(已加入的項),刪得掉', () => {
  const tag = cond('addValue', tagAt('ドロー'), '受事者中心詞', '乙');
  assert.deepStrictEqual(heads(tag), { 受事者中心詞: [] });
  assert.deepStrictEqual(cond('values', tag, '受事者中心詞'), ['乙']);
  assert.strictEqual(cond('removeValue', tag, '受事者中心詞', '乙').pred.受事者中心詞, undefined);
});

test('包含與排除同一份候選', () => {
  assert.deepStrictEqual(heads(tagAt('破壊', true)), heads(tagAt('破壊')));
});

test('沒有 300 個上限:一個詞元 320 個中心詞全列', () => {
  const many = Array.from({ length: 320 }, (_, i) => '中心詞' + i);
  const big = load(many, vocab => [frameOf(vocab, '破壊', { 位置: '效果', 極性: '肯定', 受事者: many })]);
  assert.deepStrictEqual(heads(harness.cond(big, 'tagAt', '破壊', false), big).受事者中心詞, many);
});
