'use strict';

const test = require('node:test');
const assert = require('node:assert');
const harness = require('./frontend_harness.js');
const { actionData } = require('./action_fixture.js');

const CARDS = [
  { id: 501, n: '龍族怪獸', nj: 'ドラゴン', c: 'm', s: ['effect'], at: 'dark', r: 'dragon', lv: 4 },
  { id: 502, n: '戰士怪獸', nj: 'ＥＭウォリアー', c: 'm', s: ['effect'], at: 'light', r: 'warrior',
    lv: 8 },
  { id: 503, n: '超量龍', nj: 'エクシーズ・ドラゴン', c: 'm', s: ['effect', 'xyz'], at: 'dark',
    r: 'dragon', lv: 4 },
  { id: 504, n: '連結龍', c: 'm', s: ['effect', 'link'], at: 'dark', r: 'dragon', lk: 2 },
  { id: 505, n: '魔法卡', nj: 'マジック', c: 's', s: ['normal'] },
  { id: 511, n: '特殊召喚怪獸', c: 's', s: ['normal'] },
  { id: 512, n: '特殊召喚戰士', c: 's', s: ['normal'] },
  { id: 513, n: '破壞魔法', c: 't', s: ['normal'] },
  { id: 514, n: '特殊召喚自己的龍', c: 'm', s: ['effect'], at: 'fire', r: 'dragon', lv: 7 },
  { id: 515, n: '物件判不了', c: 's', s: ['normal'] },
  { id: 516, n: '特殊召喚超量', c: 's', s: ['normal'] },
];

const ACTION = actionData([
  { id: 511, segs: [{ acts: ['特殊召喚'], lines: [{ obj: [501, 502, 503, 504, 514] }] }] },
  { id: 512, segs: [{ acts: ['特殊召喚'], lines: [{ obj: [502] }] }] },
  { id: 513, segs: [{ acts: ['破壞'], lines: [{ obj: [505] }] }] },
  { id: 514, segs: [{ acts: ['特殊召喚'], lines: [{ obj: 'self' }] }] },
  { id: 515, segs: [{ acts: ['特殊召喚'], lines: [{ obj: 'undecidable' }] }],
    unres: [{ acts: ['特殊召喚'], reason: false, substituting: true }] },
  { id: 516, segs: [{ acts: ['特殊召喚'], lines: [{ obj: [503] }] }] },
], CARDS.map(c => c.id), [], [{ code: 0x10, zh: '龍騎', members: [501, 503] },
                               { code: 0x1010, zh: '龍騎士', members: [503] }]);

const sandbox = harness.load({ cards: CARDS, meta: {}, action: ACTION });
const ids = act => harness.ids(sandbox, {}, act);
const given = (condition, actions) => ({ actions: actions || ['特殊召喚'], target: { condition } });

test('種族:滿足條件的卡在線的候選卡裡就命中(此卡的線看這張卡自己)', () => {
  assert.deepStrictEqual(ids(given({ race: 'dragon' })), [511, 514, 516]);
  assert.deepStrictEqual(ids(given({ race: 'warrior' })), [511, 512]);
});

test('大類、屬性:各自生效', () => {
  assert.deepStrictEqual(ids(given({ cat: 's' }, ['破壞'])), [513]);
  assert.deepStrictEqual(ids(given({ cat: 'm' }, ['破壞'])), []);
  assert.deepStrictEqual(ids(given({ attr: 'light' })), [511, 512]);
  assert.deepStrictEqual(ids(given({ attr: 'fire' })), [511, 514]);
});

test('等級:下限、上限;超量與連結怪獸沒有等級', () => {
  assert.deepStrictEqual(ids(given({ lvMin: 5 })), [511, 512, 514]);
  assert.deepStrictEqual(ids(given({ lvMax: 4 })), [511]);
  assert.deepStrictEqual(ids(given({ lvMin: 7, lvMax: 7 })), [511, 514]);
});

test('字段:成員照動作索引的字段成員表', () => {
  assert.deepStrictEqual(ids(given({ set: 0x10 })), [511, 516]);
  assert.deepStrictEqual(ids(given({ set: 0x1010 })), [511, 516]);
  assert.deepStrictEqual(ids(given({ set: 0x99 })), []);
});

test('卡名包含:日文名、中文名都比,全形英數當半形', () => {
  assert.deepStrictEqual(ids(given({ name: 'ドラゴン' })), [511, 516]);
  assert.deepStrictEqual(ids(given({ name: '戰士' })), [511, 512]);
  assert.deepStrictEqual(ids(given({ name: 'EMウォ' })), [511, 512]);
  assert.deepStrictEqual(ids(given({ name: '沒有這張' })), []);
});

test('同時給多項時取且', () => {
  assert.deepStrictEqual(ids(given({ race: 'dragon', lvMax: 4 })), [511]);
  assert.deepStrictEqual(ids(given({ race: 'dragon', attr: 'fire' })), [511, 514]);
  assert.deepStrictEqual(ids(given({ race: 'warrior', name: 'ドラゴン' })), []);
});

test('條件一項都沒填時等於不指定', () => {
  const plain = ids({ actions: ['特殊召喚'] });
  assert.deepStrictEqual(ids(given({})), plain);
  assert.deepStrictEqual(ids(given({ name: '  ', cat: 'x', lvMin: -1 })), plain);
  assert.deepStrictEqual(harness.rowQuery(sandbox, given({})),
                         harness.rowQuery(sandbox, { actions: ['特殊召喚'] }));
});

test('物件判不了的線不命中,算進無法確認(給條件要代入卡)', () => {
  assert.ok(ids(given({ race: 'dragon' })).indexOf(515) < 0);
  assert.deepStrictEqual(harness.unsure(sandbox, {}, given({ race: 'dragon' })), [515]);
  assert.deepStrictEqual(harness.unsure(sandbox, {}, { actions: ['特殊召喚'] }), []);
});

test('給條件換成列查詢的 condition:一項是原子本身,多項是「且」', () => {
  assert.deepStrictEqual(harness.rowQuery(sandbox, given({ race: 'dragon' })).condition,
                         { op: '屬性比較', attr: '種族', cmp: '=', value: 'ドラゴン族' });
  const rq = harness.rowQuery(sandbox, given({ name: ' ドラゴン ', set: 0x10, lvMax: 4, lvMin: 1,
                                               race: 'warrior', attr: 'light', cat: 'm' }));
  assert.deepStrictEqual(rq.condition, { op: '且', args: [
    { op: '大類', value: '怪獸' },
    { op: '屬性比較', attr: '屬性', cmp: '=', value: '光' },
    { op: '屬性比較', attr: '種族', cmp: '=', value: '戦士族' },
    { op: '屬性比較', attr: '等級', cmp: '≥', value: 1 },
    { op: '屬性比較', attr: '等級', cmp: '≤', value: 4 },
    { op: '字段', setcodes: [0x10] },
    { op: '卡名包含', text: 'ドラゴン' },
  ] });
  assert.ok(!('card' in rq) && !('this_card' in rq));
});

const EMPTY_Q = { name: '', nameLang: 'zh', code: '', text: '' };
const DOM_SORT = { key: 'dom', dir: '' };

test('給條件跟著查詢狀態存進瀏覽紀錄,還原後相同', () => {
  for (const condition of [{ race: 'dragon' },
                           { cat: 'm', attr: 'dark', race: 'dragon', lvMin: 1, lvMax: 4,
                             set: 0x10, name: 'ドラゴン' }]) {
    const act = given(condition);
    const st = { q: EMPTY_Q, sort: DOM_SORT, act };
    const saved = JSON.parse(JSON.stringify(harness.savedState(sandbox, st.q, st.sort, act)));
    assert.deepStrictEqual(harness.restoreSaved(sandbox, saved), st, JSON.stringify(condition));
  }
});

test('瀏覽紀錄裡認不得的條件值忽略,其餘照常還原', () => {
  const raw = given({ race: 'dragon', attr: '闇', cat: 'monster', lvMin: '4', lvMax: 1.5,
                      set: '0x10', name: 3, extra: 1 });
  assert.deepStrictEqual(harness.restoreSaved(sandbox, { q: EMPTY_Q, sort: DOM_SORT, act: raw }),
                         { q: EMPTY_Q, sort: DOM_SORT, act: given({ race: 'dragon' }) });
  assert.deepStrictEqual(
    harness.restoreSaved(sandbox, { q: EMPTY_Q, sort: DOM_SORT, act: given({ race: 'x' }) }),
    { q: EMPTY_Q, sort: DOM_SORT, act: { actions: ['特殊召喚'] } });
});

test('摺疊鈕的生效條件數:給條件不論幾項都算一條', () => {
  assert.strictEqual(harness.critCount(sandbox, EMPTY_Q, given({ race: 'dragon', lvMax: 4 })), 2);
  assert.strictEqual(harness.critCount(sandbox, EMPTY_Q, { target: { condition: { cat: 'm' } } }),
                     1);
  assert.strictEqual(harness.critCount(sandbox, EMPTY_Q, { target: { condition: {} } }), 0);
});

test('大類、屬性、種族的選項由值域正典生成', () => {
  const item = (code, zh) => ({ code, zh });
  const vocab = {
    cat: { zh: '大類', items: [item('t', '陷阱'), item('m', '怪獸')] },
    attr: { zh: '屬性', items: [item('dark', '闇'), item('light', '光')] },
    race: { zh: '種族', items: [item('dragon', '龍族'), item('warrior', '戰士族')] },
  };
  const box = harness.load({ cards: CARDS, vocab, meta: {}, action: ACTION });
  assert.deepStrictEqual(harness.conditionOptions(box), {
    cat: vocab.cat.items, attr: vocab.attr.items, race: vocab.race.items });
});

test('字段的建議清單來自索引的字段成員表:名字短的排前面', () => {
  assert.deepStrictEqual(harness.archetypeSuggest(sandbox, '龍騎'),
                         [{ code: 0x10, zh: '龍騎' }, { code: 0x1010, zh: '龍騎士' }]);
  assert.deepStrictEqual(harness.archetypeSuggest(sandbox, '士'), [{ code: 0x1010, zh: '龍騎士' }]);
  assert.deepStrictEqual(harness.archetypeSuggest(sandbox, ''), []);
});
