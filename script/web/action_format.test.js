'use strict';

/* 動作索引自己帶拆碼的規則(`format`)與給條件的值(`givenValues`),前端照索引讀(ADR-0008:
   正典只有建置期那一份)。這裡故意換一套數字,前端答案不變才算讀的是索引。 */

const test = require('node:test');
const assert = require('node:assert');
const harness = require('./frontend_harness.js');
const { actionData } = require('./action_fixture.js');

const CARDS = [
  { id: 601, n: '從對手墓地特殊召喚', c: 's' },
  { id: 602, n: '破壞自己', c: 'm', at: 'dark', r: 'dragon', lv: 4 },
  { id: 603, n: '破壞的一方', c: 'm' },
  { id: 604, n: '判不了', c: 's' },
  { id: 605, n: '光戰士', c: 'm', at: 'light', r: 'warrior', lv: 4 },
];
const SEGMENTS = [
  { id: 601, segs: [{ acts: ['特殊召喚'], lines: [{ from: [['墓地', '對手']], obj: [602] }] }] },
  { id: 602, segs: [{ acts: ['破壞'], lines: [{ obj: 'self' }] }] },
  { id: 603, segs: [{ acts: ['破壞'], lines: [{ doer: true, obj: [602] }, { obj: [605] }] }] },
  { id: 604, segs: [{ acts: ['破壞'], lines: [{ obj: 'undecidable' }] }],
    unres: [{ acts: ['破壞'], reason: false, substituting: true }] },
];
const OTHER_FORMAT = {
  sideSlots: 16,
  lineFlags: { doer: 4, targeting: 8 },
  objectKinds: { thisCard: 7, undecidable: 5, unsubstitutable: 6 },
  unresolvedFlags: { replacing: 64, block: 128, reason: 256, reasonSubstituting: 512,
                     reference: 1024 },
};
const QUERIES = [
  { actions: ['特殊召喚'], from: { zone: '墓地', side: '對手' } },
  { actions: ['特殊召喚'], from: { zone: '墓地', side: '我方' } },
  { actions: ['破壞'], target: 'this_card' },
  { actions: ['破壞'], target: { card: 602 } },
  { actions: ['破壞'], target: { card: 605 } },
];

function answers(format) {
  const box = harness.load({ cards: CARDS,
                             action: actionData(SEGMENTS, CARDS.map(c => c.id), [], [],
                                                { format }) });
  return QUERIES.map(act => ({ ids: harness.ids(box, {}, act),
                               unsure: harness.unsure(box, {}, act) }));
}

test('方的格數、線與未解析來源的旗標、物件種類碼都照索引的 format 拆', () => {
  const usual = answers(undefined);
  assert.deepStrictEqual(usual.map(a => a.ids), [[601], [], [602], [602], [603]]);
  assert.deepStrictEqual(usual[3].unsure, [604]);
  assert.deepStrictEqual(answers(OTHER_FORMAT), usual);
});

test('給條件換成條件式的值照索引的 givenValues', () => {
  const given = { cat: [['m', '怪物']], attr: [['dark', '闇屬性']], race: [['dragon', '龍']] };
  const items = codes => ({ items: codes.map(code => ({ code, zh: code })) });
  const vocab = { cat: items(['m']), attr: items(['dark']), race: items(['dragon']) };
  const box = harness.load({ cards: CARDS, vocab,
                             action: actionData(SEGMENTS, CARDS.map(c => c.id), [], [],
                                                { given }) });
  const act = { actions: ['破壞'], target: { condition: { cat: 'm', attr: 'dark', race: 'dragon' } } };
  assert.deepStrictEqual(harness.rowQuery(box, act).condition, { op: '且', args: [
    { op: '大類', value: '怪物' },
    { op: '屬性比較', attr: '屬性', cmp: '=', value: '闇屬性' },
    { op: '屬性比較', attr: '種族', cmp: '=', value: '龍' },
  ] });
  assert.deepStrictEqual(harness.ids(box, {}, act), [602]);
});
