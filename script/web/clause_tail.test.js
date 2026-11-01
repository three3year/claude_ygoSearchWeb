/**
 * clause_tail.test.js — 命中句的句尾標籤(predicate-ui 票 03;規格「句尾標籤」段)
 *
 * 跑法:`node --test script/web/clause_tail.test.js`
 *
 * 接縫:`View.cardHtml`。例子走整條路:目錄列 → 標籤 → `Cond.toQuery` → `Engine.runQuery`,
 * 序號對照是 `Cond.hitLabels` 依同一份查詢組的,斷言只看每句 HTML 去掉標記後的字。
 */
'use strict';

const test = require('node:test');
const assert = require('node:assert');
const harness = require('./frontend_harness.js');

const FRAME_VOCAB = {
  lemmas: ['破壊', '特殊召喚', '捨てる'],
  heads: [],
  domains: {
    位置: ['代價', '效果', '條件'],
    極性: ['肯定', '可能', '否定'],
    玩家: ['自分', '相手'],
    區域: ['墓地', '場上'],
  },
};

/* 框元組:[詞元, 位置, 極性, 態, 否定形, 施事者, 方式類, 動作對象, [來源對…]](欄序見 frameindex.py) */
const frame = (lemma, position, sources) => [
  FRAME_VOCAB.lemmas.indexOf(lemma),
  FRAME_VOCAB.domains.位置.indexOf(position) + 1,
  1, 0, 0, 0, 0, 0,
  ...(sources ? [sources] : []),
];

const GRAVE_ANY = [0, 2];  // 自分墓地、相手墓地的區域對
const FRAMES = [
  frame('破壊', '效果'),                  // 0
  frame('特殊召喚', '效果', GRAVE_ANY),   // 1
  frame('捨てる', '代價'),                // 2
  frame('破壊', '條件'),                  // 3
  frame('特殊召喚', '條件'),              // 4
];

const CARDS = [
  { id: 1, n: '一般', c: 'm', tx: ['①破壞。', '②特召。', '③沒框。'], fr: [[0], [1], []] },
  { id: 2, n: '同句兩個述詞', c: 'm', tx: ['①破壞與特召。'], fr: [[0, 1]] },
  { id: 3, n: '代價位', c: 'm', tx: ['①捨棄。'], fr: [[2]] },
  { id: 4, n: '條件位', c: 'm', tx: ['①若破壞。'], fr: [[3]] },
  { id: 5, n: '領起句', c: 'm', tx: ['①破壞,以下效果:', '●甲。', '●破壞。'], fr: [[0], [], [0]], fl: [-1, 0, 0] },
  { id: 6, n: '領起句在條件位', c: 'm', tx: ['①若破壞,以下效果:', '●甲。'], fr: [[3], []], fl: [-1, 0] },
  { id: 7, n: '只有效果文', c: 'm', tx: ['①丙。'], fr: [[]] },
  { id: 8, n: '主查詢與片段同句', c: 'm', tx: ['①捨棄後破壞。'], fr: [[2, 0]] },
  { id: 9, n: '兩個分支各中一句', c: 'm', tx: ['①破壞。', '②丙。'], fr: [[0], []] },
];

const POLAR = ['肯定', '可能'];
const row = (name, predicate, cards) => ({ name, path: [name], predicate, cards });
const CATALOG = [
  row('破壊', { 詞元: '破壊', 極性: POLAR }, { 代價: 0, 效果: 9, 條件: 9 }),
  row('捨てる', { 詞元: '捨てる', 極性: POLAR }, { 代價: 9, 效果: 0, 條件: 0 }),
  row('特殊召喚←墓地', { 詞元: '特殊召喚', 極性: POLAR, 來源: [[null, '墓地']] }, { 代價: 0, 效果: 9, 條件: 0 }),
];

const box = harness.load({
  cards: CARDS, frames: FRAMES, vocab: { frame: FRAME_VOCAB, catalog: CATALOG },
});
const cond = (fn, ...args) => harness.cond(box, fn, ...args);
const tag = name => cond('tagAt', name, false);
const queryOf = (...tags) => cond('toQuery', tags.reduce((st, t) => cond('add', st, t), cond('empty')), {});

const textOf = out => out.replace(/<[^>]+>/g, '');

/* 跑查詢,回傳 卡 id → 每句的字(原文加句尾),句界用卡文原文切。 */
function clausesAfter(q, cards = CARDS, sandbox = box) {
  const labels = cond('hitLabels', q);
  const marks = harness.marks(sandbox, q);
  const out = new Map();
  for (const hit of harness.search(sandbox, q)) {
    const card = cards.find(c => c.id === hit.id);
    const text = textOf(harness.cardHtmlHl(sandbox, { ...hit, card }, marks, labels));
    const starts = card.tx.map(t => text.indexOf(t));
    out.set(hit.id, card.tx.map((_, i) => text.slice(starts[i], starts[i + 1]).trim()));
  }
  return out;
}

test('命中句句尾列命中的述詞,文字是短句;沒命中的句不列', () => {
  const clauses = clausesAfter(queryOf(tag('破壊'))).get(1);
  assert.deepStrictEqual(clauses, ['①破壞。破壊', '②特召。', '③沒框。']);
});

test('每個述詞一個標籤,只列這一句命中的述詞', () => {
  const q = queryOf(tag('破壊'), tag('特殊召喚←墓地'));
  assert.deepStrictEqual(clausesAfter(q).get(1),
    ['①破壞。破壊', '②特召。特殊召喚 從 墓地', '③沒框。']);
  assert.deepStrictEqual(clausesAfter(q).get(2), ['①破壞與特召。破壊特殊召喚 從 墓地']);
});

test('位置前綴:代價位寫 代價:,效果不寫', () => {
  assert.deepStrictEqual(clausesAfter(queryOf(tag('捨てる'))).get(3), ['①捨棄。代價:捨てる']);
});

test('位置前綴取命中框的位置,不是標籤帶的位置;短句不再重複位置', () => {
  const both = { preds: { inc: [{ 詞元: '破壊', 極性: POLAR, 位置: ['效果', '條件'] }] } };
  assert.deepStrictEqual(clausesAfter(both).get(1), ['①破壞。破壊', '②特召。', '③沒框。']);
  assert.deepStrictEqual(clausesAfter(both).get(4), ['①若破壞。條件:破壊']);
  const onlyCondition = { preds: { inc: [{ 詞元: '破壊', 極性: POLAR, 位置: ['條件'] }] } };
  assert.deepStrictEqual(clausesAfter(onlyCondition).get(4), ['①若破壞。條件:破壊']);
});

test('框所在句不是這一句:標籤加 ↑領起句;這一句自己也有框就不算繼承', () => {
  assert.deepStrictEqual(clausesAfter(queryOf(tag('破壊'))).get(5),
    ['①破壞,以下效果:破壊', '●甲。破壊 ↑領起句', '●破壞。破壊']);
});

test('↑領起句 的位置前綴取領起句那個框的位置', () => {
  const q = { preds: { inc: [{ 詞元: '破壊', 極性: POLAR, 位置: ['條件'] }] } };
  assert.deepStrictEqual(clausesAfter(q).get(6), ['①若破壞,以下效果:條件:破壊', '●甲。條件:破壊 ↑領起句']);
});

test('↑領起句 帶說明提示,自己句的標籤沒有', () => {
  const q = queryOf(tag('破壊'));
  const [hit] = harness.search(box, q).filter(e => e.id === 5);
  const html = harness.cardHtmlHl(box, { ...hit, card: CARDS.find(c => c.id === 5) },
                                  harness.marks(box, q), cond('hitLabels', q));
  assert.strictEqual((html.match(/title="命中的框在領起句,此 ● 子句繼承"/g) || []).length, 1);
});

test('述詞序號跨分支:先主查詢,再依片段順序,標籤對得回述詞', () => {
  const pred = name => cond('tagAt', name, false).pred;
  const q = { preds: { inc: [pred('破壊')] },
              or: [{ preds: { inc: [pred('捨てる')] } }, { preds: { inc: [pred('特殊召喚←墓地')] } }] };
  assert.deepStrictEqual(cond('hitLabels', q), ['破壊', '捨てる', '特殊召喚 從 墓地']);
  assert.deepStrictEqual(clausesAfter(q).get(8), ['①捨棄後破壞。破壊代價:捨てる']);
  assert.deepStrictEqual(clausesAfter(q).get(2), ['①破壞與特召。破壊特殊召喚 從 墓地']);
});

test('排除述詞不佔序號、沒有標籤', () => {
  const pred = name => cond('tagAt', name, false).pred;
  assert.deepStrictEqual(cond('hitLabels', { preds: { inc: [pred('破壊')], ex: [pred('捨てる')] } }), ['破壊']);
  assert.deepStrictEqual(cond('hitLabels', {}), []);
});

test('只有排除述詞:沒有句尾標籤', () => {
  const q = queryOf(cond('tagAt', '破壊', true));
  assert.deepStrictEqual(clausesAfter(q).get(3), ['①捨棄。']);
});

test('pred mark 不出徽章文字', () => {
  const clauses = clausesAfter(queryOf(tag('破壊'))).get(1);
  assert.ok(!clauses[0].includes('pred'));
  const entry = { ...harness.search(box, queryOf(tag('破壊'))).find(e => e.id === 1), card: CARDS[0] };
  const out = textOf(harness.cardHtmlHl(box, entry, [{ type: 'pred' }], ['破壊']));
  assert.ok(!out.includes('pred'));
});

test('只因左側條件的分支命中:rows 是 null、marks 有 pred,沒有句尾標籤', () => {
  const q = { or: [{ preds: { inc: [tag('破壊').pred] } }, { cat: { m: 1 } }] };
  const entry = harness.search(box, q).find(e => e.id === 3);
  assert.strictEqual(entry.rows, null);
  assert.ok(harness.marks(box, q).some(m => m.type === 'pred'));
  assert.deepStrictEqual(clausesAfter(q).get(3), ['①捨棄。']);
});

test('只因沒有包含述詞的分支命中的句:沒有 hits 或 hits 是空清單,命中句沒有句尾標籤', () => {
  const q = { or: [{ preds: { inc: [tag('破壊').pred] } }, { text: '丙' }] };
  const results = harness.search(box, q);
  assert.strictEqual(results.find(e => e.id === 7).hits, undefined);
  assert.deepStrictEqual(clausesAfter(q).get(7), ['①丙。']);
  assert.deepStrictEqual(results.find(e => e.id === 9).hits[1], []);
  assert.deepStrictEqual(clausesAfter(q).get(9), ['①破壞。破壊', '②丙。']);
});

test('沒有條件:句尾沒有標籤', () => {
  const out = textOf(harness.cardHtml(box, { card: CARDS[0], rows: null }));
  assert.ok(out.includes('①破壞。'));
  assert.ok(!out.includes('破壊'));
});

test('全語料:對象とする 只標 條件:;取り除く@ 只標 代價:;領起句繼承看得到 ↑領起句', t => {
  const data = harness.realData();
  if (!data || !data.vocab.catalog) {
    t.skip('缺 web/data.js,略過全語料對照');
    return;
  }
  const real = harness.load(data);
  const byId = new Map(data.cards.map(c => [c.id, c]));
  const realCond = (fn, ...args) => harness.cond(real, fn, ...args);
  const texts = path => {
    const q = realCond('toQuery', realCond('add', realCond('empty'), realCond('tagAt', path, false)), {});
    const labels = realCond('hitLabels', q), marks = harness.marks(real, q);
    return harness.search(real, q).map(e => ({
      e, html: harness.cardHtmlHl(real, { ...e, card: byId.get(e.id) }, marks, labels),
    }));
  };
  const rowOf = name => data.vocab.catalog.find(r => r.name === name && r.predicate);
  const target = texts(rowOf('対象とする').path.join('›'));
  assert.strictEqual(target.length, 3396);
  assert.ok(target.every(({ html }) => html.includes('條件:対象とする')));
  const removed = texts(rowOf('取り除く@お互いのフィールド').path.join('›'));
  assert.strictEqual(removed.length, 10);
  assert.ok(removed.every(({ html }) => html.includes('代價:')));
  const leadRows = target.filter(({ e }) => e.hits.some((list, k) =>
    list.length && list.every(hit => hit[1] !== e.rows[k])));
  assert.ok(leadRows.length > 0);
  assert.ok(leadRows.every(({ html }) => html.includes('↑領起句')));
});
