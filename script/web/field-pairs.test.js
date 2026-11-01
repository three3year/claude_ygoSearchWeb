/**
 * field-pairs.test.js — 抽屜改欄位與網址的欄位對(predicate-ui 票 04)
 *
 * 跑法:`node --test script/web/field-pairs.test.js`
 *
 * 接縫:條件模型(抽屜的欄位與值、改欄位、認回具名查詢、標籤提示)與 `Hash`(欄位對 ⇄ 標籤)。
 * 抽屜的 DOM 走真瀏覽器(規格 Testing Decisions)。目錄與值域是手寫的小表,只有全語料例子用
 * 真 data.js。
 */
'use strict';

const test = require('node:test');
const assert = require('node:assert');
const harness = require('./frontend_harness.js');

const POLAR = ['肯定', '可能'];
const counts = (代價, 效果, 條件) => ({ 代價, 效果, 條件 });
const HEADS = Array.from({ length: 320 }, (_, i) => '中心詞' + i);

const VOCAB = {
  frame: {
    lemmas: ['ドロー', '対象とする', '特殊召喚', '破壊'],
    heads: HEADS,
    domains: {
      位置: ['代價', '效果', '條件'],
      極性: ['肯定', '否定', '可能'],
      玩家: ['自分', '相手', 'お互い', '相對', '無'],
      區域: ['場上', '墓地', '手牌', '牌組', '除外', '靈擺區', '額外牌組'],
      動作對象: ['此卡', '非此卡'],
      施事者: ['自分', '相手', 'お互い', '此卡', '其他卡'],
      數量類: ['定數', '上限'],
      方式類: ['手段:效果', '其他'],
      態: ['他動', '自動', '受身'],
      否定形: ['受身', '不可能'],
      中心詞類: ['卡', '其他'],
      修飾語類: ['種族', '其他'],
    },
  },
  catalog: [
    { name: '破壊', path: ['破壊'], cards: counts(5, 30, 20),
      predicate: { 詞元: '破壊', 極性: POLAR } },
    { name: '破壊:モンスター', path: ['破壊', '破壊:モンスター'], cards: counts(1, 9, 0),
      predicate: { 詞元: '破壊', 極性: POLAR, 受事者中心詞: ['モンスター'] } },
    { name: '特殊召喚←墓地', path: ['召喚', '特殊召喚←墓地'], cards: counts(0, 12, 1),
      predicate: { 詞元: '特殊召喚', 極性: POLAR, 來源: [[null, '墓地']] } },
    { name: '対象とする', path: ['対象とする'], cards: counts(0, 0, 3396),
      predicate: { 詞元: '対象とする', 極性: POLAR } },
  ],
};

const box = harness.load({ vocab: VOCAB });
const cond = (fn, ...args) => harness.cond(box, fn, ...args);
const tagAt = (path, ex) => cond('tagAt', path, !!ex);
const DESTROY = '破壊';
const REVIVE = '召喚›特殊召喚←墓地';

/* ── 抽屜的欄位與值 ── */

test('抽屜欄位:分常用與進階,涵蓋 詞元 以外的 15 欄', () => {
  assert.deepStrictEqual(cond('drawerGroups'), {
    常用: ['位置', '極性', '來源', '目的', '所在', '動作對象', '施事者', '受事者中心詞'],
    進階: ['目的中心詞', '數量類', '方式類', '態', '否定形', '中心詞類', '修飾語類'],
  });
});

test('抽屜的值:封閉欄的值就是值域', () => {
  assert.deepStrictEqual(cond('editor', '動作對象'), { kind: 'values', values: ['此卡', '非此卡'] });
  assert.deepStrictEqual(cond('editor', '位置'), { kind: 'values', values: ['代價', '效果', '條件'] });
});

test('抽屜的值:區域欄的玩家選單列出 相對、無,不限玩家是 null 排在最前面', () => {
  assert.deepStrictEqual(cond('editor', '來源'), {
    kind: 'region',
    players: [null, '自分', '相手', 'お互い', '相對', '無'],
    zones: VOCAB.frame.domains.區域,
  });
});

test('抽屜的值:中心詞自由輸入,候選是中心詞表前 300 個', () => {
  const editor = cond('editor', '受事者中心詞');
  assert.strictEqual(editor.kind, 'text');
  assert.strictEqual(editor.candidates.length, 300);
  assert.strictEqual(editor.candidates[299], '中心詞299');
});

test('抽屜的值:全語料每一欄都有值可選,值域不是空的', t => {
  const data = harness.realData();
  if (!data) { t.skip('沒有 web/data.js,請先跑 script/web/build_index.py'); return; }
  const real = harness.load({ vocab: data.vocab });
  const groups = harness.cond(real, 'drawerGroups');
  const fields = groups.常用.concat(groups.進階);
  assert.strictEqual(fields.length, 15);
  for (const field of fields) {
    const e = harness.cond(real, 'editor', field);
    const size = (e.values || e.zones || e.candidates).length;
    assert.ok(size > 0, field);
  }
});

/* ── 改欄位 ── */

test('改欄位:封閉欄切換多值,值序照值域;原標籤不變', () => {
  const tag = tagAt(DESTROY);
  const one = cond('toggleValue', tag, '動作對象', '非此卡');
  const two = cond('toggleValue', one, '動作對象', '此卡');
  assert.deepStrictEqual(one.pred.動作對象, ['非此卡']);
  assert.deepStrictEqual(two.pred.動作對象, ['此卡', '非此卡']);
  assert.strictEqual(tag.pred.動作對象, undefined);
});

test('改欄位:全部關掉就是沒寫,不留空清單', () => {
  const on = cond('toggleValue', tagAt(DESTROY), '施事者', '相手');
  assert.ok(!('施事者' in cond('toggleValue', on, '施事者', '相手').pred));
});

test('改欄位:極性全關是不限,短句寫出來', () => {
  const none = cond('toggleValue', cond('toggleValue', tagAt(DESTROY), '極性', '肯定'), '極性', '可能');
  assert.ok(!('極性' in none.pred));
  assert.strictEqual(cond('sentence', none), '破壊 極性 不限');
});

test('改欄位:位置全關視同三個位置都看,明寫三個值', () => {
  const none = cond('toggleValue', tagAt(DESTROY), '位置', '效果');
  assert.deepStrictEqual(none.pred.位置, ['代價', '效果', '條件']);
  assert.strictEqual(cond('sentence', none), '代價或效果或條件位 破壊');
});

test('改欄位:位置可以改成條件,標籤短句跟著變', () => {
  const tag = cond('toggleValue', cond('toggleValue', tagAt(DESTROY), '位置', '條件'), '位置', '效果');
  assert.deepStrictEqual(tag.pred.位置, ['條件']);
  assert.strictEqual(cond('sentence', tag), '條件位 破壊');
});

test('改欄位:區域項帶玩家與不看玩家是兩個值,排在區域順序上,重複不多一個', () => {
  let tag = cond('addValue', tagAt(REVIVE), '來源', ['自分', '除外']);
  tag = cond('addValue', tag, '來源', [null, '除外']);
  tag = cond('addValue', tag, '來源', ['相對', '手牌']);
  tag = cond('addValue', tag, '來源', [null, '除外']);
  assert.deepStrictEqual(tag.pred.來源,
    [[null, '墓地'], ['相對', '手牌'], [null, '除外'], ['自分', '除外']]);
  assert.strictEqual(cond('sentence', tag), '特殊召喚 從 墓地或相對:手札或除外或自分除外');
});

test('改欄位:區域項刪到沒有就是沒寫', () => {
  const tag = cond('removeValue', tagAt(REVIVE), '來源', [null, '墓地']);
  assert.ok(!('來源' in tag.pred));
});

test('改欄位:中心詞自由輸入,修掉空白,空字串不算,表外的字也收', () => {
  let tag = cond('addValue', tagAt(DESTROY), '受事者中心詞', '  表外的字 ');
  tag = cond('addValue', tag, '受事者中心詞', '   ');
  tag = cond('addValue', tag, '受事者中心詞', '表外的字');
  assert.deepStrictEqual(tag.pred.受事者中心詞, ['表外的字']);
  assert.deepStrictEqual(cond('values', tag, '受事者中心詞'), ['表外的字']);
});

test('包含、排除切換:只換 ex,述詞與來源不變', () => {
  const ex = cond('setEx', tagAt(REVIVE), true);
  assert.deepStrictEqual(ex, tagAt(REVIVE, true));
  assert.strictEqual(cond('sentence', ex), '沒有 特殊召喚 從 墓地');
  assert.deepStrictEqual(cond('setEx', ex, false), tagAt(REVIVE));
});

test('狀態:replaceAt 換第 i 張,原狀態不變', () => {
  const st = cond('add', cond('add', cond('empty'), tagAt(DESTROY)), tagAt(REVIVE));
  const edited = cond('setEx', tagAt(DESTROY), true);
  const next = cond('replaceAt', st, 0, edited);
  assert.deepStrictEqual(cond('tags', next), [edited, tagAt(REVIVE)]);
  assert.deepStrictEqual(cond('tags', st), [tagAt(DESTROY), tagAt(REVIVE)]);
});

/* ── 改自 X、還原、提示 ── */

test('改自:沒改過沒有;改了欄位是來源名;位置不是預設也算改過', () => {
  assert.strictEqual(cond('editedFrom', tagAt(DESTROY)), null);
  assert.strictEqual(cond('editedFrom', tagAt('対象とする')), null);
  assert.strictEqual(cond('editedFrom', cond('toggleValue', tagAt(DESTROY), '動作對象', '此卡')), '破壊');
  assert.strictEqual(cond('editedFrom', cond('toggleValue', tagAt(DESTROY), '位置', '條件')), '破壊');
});

test('改自:包含、排除切換不算改過', () => {
  assert.strictEqual(cond('editedFrom', tagAt(DESTROY, true)), null);
});

test('改自:改回原樣回到沒有,多值順序不影響', () => {
  const back = cond('toggleValue', cond('toggleValue', tagAt(DESTROY), '動作對象', '此卡'), '動作對象', '此卡');
  assert.strictEqual(cond('editedFrom', back), null);
  const pol = cond('toggleValue', cond('toggleValue', tagAt(DESTROY), '極性', '肯定'), '極性', '肯定');
  assert.deepStrictEqual(pol.pred.極性, ['肯定', '可能']);
  assert.strictEqual(cond('editedFrom', pol), null);
});

test('還原:回到來源那一列的樣子,包含、排除不動', () => {
  const edited = cond('toggleValue', cond('toggleValue', tagAt(REVIVE, true), '動作對象', '此卡'), '位置', '條件');
  assert.deepStrictEqual(cond('restore', edited), tagAt(REVIVE, true));
});

test('改成另一個具名查詢:認得新的,來源還是原本那列,還原回原本那列', () => {
  const tag = cond('addValue', tagAt(DESTROY), '受事者中心詞', 'モンスター');
  assert.strictEqual(cond('named', tag).name, '破壊:モンスター');
  assert.strictEqual(cond('editedFrom', tag), '破壊');
  assert.deepStrictEqual(cond('restore', tag), tagAt(DESTROY));
});

test('提示:具名查詢名;不是具名查詢時「改自 X」;都不是就空字串', () => {
  assert.strictEqual(cond('note', tagAt(DESTROY)), '破壊');
  assert.strictEqual(cond('note', cond('toggleValue', tagAt(DESTROY), '位置', '條件')), '破壊');
  assert.strictEqual(cond('note', cond('toggleValue', tagAt(DESTROY), '動作對象', '此卡')), '改自 破壊');
  assert.strictEqual(cond('note', { ex: false, origin: null, pred: { 詞元: 'ドロー', 位置: ['效果'] } }), '');
});

test('單張張數的查詢:只看這張標籤的述詞,排除標籤也算有 X 的卡', () => {
  const tag = cond('toggleValue', tagAt(DESTROY, true), '動作對象', '此卡');
  assert.deepStrictEqual(cond('soloQuery', tag), { preds: { inc: [tag.pred], ex: [] } });
});

/* ── 網址:標籤 → 欄位對 ── */

const stateOf = (...tags) => tags.reduce((st, t) => cond('add', st, t), cond('empty'));
const hashOf = (...tags) => harness.hash(box, { cond: stateOf(...tags) });
const parsedTags = str => {
  const st = harness.parseHash(box, str).cond;
  return st ? cond('tags', st) : [];
};
const e = encodeURIComponent;
const pair = (field, ...vals) => e(field) + ':' + vals.map(e).join('~');
const edit = (tag, field, value) => cond('toggleValue', tag, field, value);
const NON_SELF = edit(tagAt(DESTROY), '動作對象', '非此卡');

test('欄位對:規格的例子,欄序固定、值用 ~ 接、逐個編碼', () => {
  const tag = edit(NON_SELF, '位置', '代價');
  assert.strictEqual(hashOf(tag), 'act=' + [
    pair('詞元', '破壊'), pair('位置', '代價', '效果'), pair('極性', '肯定', '可能'),
    pair('動作對象', '非此卡'),
  ].join(';'));
});

test('欄位對:效果位不寫位置,不限極性不寫極性', () => {
  const tag = edit(edit(NON_SELF, '極性', '肯定'), '極性', '可能');
  assert.strictEqual(hashOf(tag), 'act=' + pair('詞元', '破壊') + ';' + pair('動作對象', '非此卡'));
});

test('欄位對:排除在開頭加 -', () => {
  assert.ok(hashOf(cond('setEx', NON_SELF, true)).startsWith('act=-' + e('詞元') + ':'));
});

test('欄位對:位置不是預設就要寫,対象とする 反過來是效果位才要展開', () => {
  assert.strictEqual(hashOf(edit(tagAt(DESTROY), '位置', '條件')).split(';')[1],
    pair('位置', '效果', '條件'));
  const effect = edit(edit(tagAt('対象とする'), '位置', '效果'), '位置', '條件');
  assert.deepStrictEqual(effect.pred.位置, ['效果']);
  assert.strictEqual(hashOf(effect),
    'act=' + pair('詞元', '対象とする') + ';' + pair('極性', '肯定', '可能'));
});

test('欄位對:改的先後不影響網址', () => {
  const a = edit(edit(tagAt(DESTROY), '動作對象', '非此卡'), '施事者', '相手');
  const b = edit(edit(tagAt(DESTROY), '施事者', '相手'), '動作對象', '非此卡');
  assert.strictEqual(hashOf(a), hashOf(b));
});

test('欄位對:區域項 玩家.區域,不看玩家只寫區域,值序照區域', () => {
  const tag = cond('addValue', cond('removeValue', tagAt(REVIVE), '來源', [null, '墓地']), '來源', [null, '除外']);
  const both = cond('addValue', tag, '來源', ['自分', '墓地']);
  assert.ok(hashOf(both).includes(pair('來源', '自分.墓地', '除外')), hashOf(both));
});

test('改回原樣回到葉路徑', () => {
  const back = edit(NON_SELF, '動作對象', '非此卡');
  assert.strictEqual(hashOf(back), 'act=' + e(DESTROY));
  const pos = edit(edit(tagAt(DESTROY), '位置', '條件'), '位置', '條件');
  assert.strictEqual(hashOf(pos), 'act=' + e(DESTROY));
});

test('改成另一個具名查詢:網址是那一列的葉路徑', () => {
  const tag = cond('addValue', tagAt(DESTROY), '受事者中心詞', 'モンスター');
  assert.strictEqual(hashOf(tag), 'act=' + e('破壊›破壊:モンスター'));
});

test('兩張標籤改到一模一樣:網址只寫一次,canon 不變', () => {
  const st = cond('replaceAt', stateOf(tagAt(DESTROY), NON_SELF), 1, tagAt(DESTROY));
  const hash = harness.hash(box, { cond: st });
  assert.strictEqual(hash, 'act=' + e(DESTROY));
  assert.strictEqual(harness.canonHash(box, hash), hash);
});

/* ── 網址:往返 ── */

test('往返:述詞、排除都不變,canon 冪等', () => {
  const tag = cond('setEx', edit(edit(NON_SELF, '位置', '條件'), '施事者', '相手'), true);
  const hash = hashOf(tagAt(REVIVE), tag);
  const back = parsedTags(hash);
  assert.strictEqual(back.length, 2);
  assert.strictEqual(back[1].ex, true);
  assert.strictEqual(cond('sentence', back[1]), cond('sentence', tag));
  assert.strictEqual(harness.canonHash(box, hash), hash);
});

test('往返:沒寫位置是效果,沒寫極性是不限', () => {
  const [tag] = parsedTags('act=' + pair('詞元', '破壊') + ';' + pair('施事者', '相手'));
  assert.deepStrictEqual(tag.pred.位置, ['效果']);
  assert.ok(!('極性' in tag.pred));
  assert.strictEqual(cond('sentence', tag), '破壊 由 相手 極性 不限');
});

test('往返:三個位置都看要明寫,讀回來還是三個', () => {
  const hash = hashOf(edit(tagAt(DESTROY), '位置', '效果'));
  assert.ok(hash.includes(pair('位置', '代價', '效果', '條件')), hash);
  assert.deepStrictEqual(parsedTags(hash)[0].pred.位置, ['代價', '效果', '條件']);
});

test('往返:相對、無 的區域項與不看玩家都讀得回來', () => {
  const items = [[null, '場上'], ['相對', '墓地'], ['無', '除外'], ['お互い', '除外']];
  const tag = items.reduce((t, it) => cond('addValue', t, '所在', it), tagAt(DESTROY));
  assert.deepStrictEqual(parsedTags(hashOf(tag))[0].pred.所在,
    [[null, '場上'], ['相對', '墓地'], ['お互い', '除外'], ['無', '除外']]);
});

for (const word of ['a:b', 'a;b', 'a,b', 'a~b', 'a›b', 'a|b', ':;,~›|', '-a', 'a.b', '100%', 'a&act=b', 'a=b', 'a b', '#a', '%7E']) {
  test('轉義:中心詞含 ' + word + ' 往返不變', () => {
    const tag = cond('addValue', edit(tagAt(DESTROY), '位置', '條件'), '受事者中心詞', word);
    const hash = hashOf(tag, tagAt(REVIVE));
    const back = parsedTags(hash);
    assert.strictEqual(back.length, 2, hash);
    assert.deepStrictEqual(back[0].pred.受事者中心詞, [word]);
    assert.strictEqual(harness.canonHash(box, hash), hash);
  });
}

test('轉義:值裡的分隔符都編掉,~ 也補編', () => {
  const hash = hashOf(cond('addValue', tagAt(DESTROY), '受事者中心詞', ':;,~›|'));
  assert.ok(hash.endsWith(e('受事者中心詞') + ':%3A%3B%2C%7E%E2%80%BA%7C'), hash);
});

test('同欄多值:值用 ~ 分開,中心詞各自讀回來', () => {
  const tag = cond('addValue', cond('addValue', tagAt(DESTROY), '受事者中心詞', 'b~c'), '受事者中心詞', 'a');
  assert.deepStrictEqual(parsedTags(hashOf(tag))[0].pred.受事者中心詞, ['a', 'b~c']);
});

/* ── 網址:解析安靜忽略 ── */

const DESTROY_PAIR = pair('詞元', '破壊');
const sentenceOf = str => parsedTags(str).map(t => cond('sentence', t));

test('解析:不認得的欄忽略,不會送進引擎', () => {
  for (const field of ['亂寫', '__proto__', 'constructor']) {
    const hash = 'act=' + DESTROY_PAIR + ';' + pair(field, 'x') + ';' + pair('施事者', '相手');
    const st = harness.parseHash(box, hash);
    assert.deepStrictEqual(Object.keys(cond('tags', st.cond)[0].pred).sort(), ['位置', '施事者', '詞元'].sort());
    assert.doesNotThrow(() => harness.search(box, cond('toQuery', st.cond, st.q)));
  }
});

test('解析:值域外的值忽略,同一欄其餘的值留著', () => {
  const [tag] = parsedTags('act=' + DESTROY_PAIR + ';' + pair('施事者', '相手', '亂寫') + ';' + pair('態', '亂寫'));
  assert.deepStrictEqual(tag.pred.施事者, ['相手']);
  assert.ok(!('態' in tag.pred));
});

test('解析:位置全是值域外的值,等於沒寫,是效果', () => {
  assert.deepStrictEqual(parsedTags('act=' + DESTROY_PAIR + ';' + pair('位置', '亂寫'))[0].pred.位置, ['效果']);
});

test('解析:區域項的玩家或區域不在值域就掉那一項', () => {
  const [tag] = parsedTags('act=' + DESTROY_PAIR + ';' +
    pair('來源', '亂寫.墓地', '自分.亂寫', '.墓地', '亂寫', '自分.墓地.除外', '相手.手牌'));
  assert.deepStrictEqual(tag.pred.來源, [['相手', '手牌']]);
});

test('解析:詞元不在詞元表、沒有詞元的標籤整張忽略,其餘條件照常', () => {
  const hash = 'act=' + [pair('詞元', '亂寫'), pair('施事者', '相手'), e(DESTROY)].join(',') + '&name=abc';
  const st = harness.parseHash(box, hash);
  assert.deepStrictEqual(cond('tags', st.cond), [tagAt(DESTROY)]);
  assert.strictEqual(st.q.name, 'abc');
});

test('解析:壞掉的段沒有冒號、整段空白都不崩', () => {
  assert.deepStrictEqual(sentenceOf('act=' + DESTROY_PAIR + ';;沒有冒號;:;'), ['破壊 極性 不限']);
  assert.deepStrictEqual(sentenceOf('act=:'), []);
  assert.deepStrictEqual(sentenceOf('act=;'), []);
});

test('解析:壞百分比編碼不崩,值壞掉掉那個值,欄名壞掉掉那一欄,詞元壞掉掉整張', () => {
  assert.deepStrictEqual(parsedTags('act=' + DESTROY_PAIR + ';' + e('受事者中心詞') + ':%E3%81~ok')[0].pred.受事者中心詞, ['ok']);
  assert.deepStrictEqual(Object.keys(parsedTags('act=' + DESTROY_PAIR + ';%E3%81:x')[0].pred).sort(), ['位置', '詞元'].sort());
  assert.deepStrictEqual(parsedTags('act=' + e('詞元') + ':%E3%81'), []);
});

/* ── 網址:重新載入後的來源 ── */

test('重新載入:改過的標籤沒有來源,沒有「改自 X」與還原', () => {
  const [tag] = parsedTags(hashOf(NON_SELF));
  assert.strictEqual(tag.origin, null);
  assert.strictEqual(cond('editedFrom', tag), null);
  assert.strictEqual(cond('note', tag), '');
  assert.deepStrictEqual(cond('restore', tag), tag);
});

test('重新載入:欄位等於具名查詢、只差位置,認得來源,可以還原', () => {
  const [tag] = parsedTags(hashOf(edit(tagAt(DESTROY), '位置', '條件')));
  assert.strictEqual(tag.origin, '破壊');
  assert.strictEqual(cond('editedFrom', tag), '破壊');
  assert.deepStrictEqual(cond('restore', tag), tagAt(DESTROY));
});

test('重新載入:欄位對等於具名查詢且位置是預設,canon 收成葉路徑,沒有改自', () => {
  const hash = 'act=' + DESTROY_PAIR + ';' + pair('極性', '可能', '肯定');
  assert.strictEqual(harness.canonHash(box, hash), 'act=' + e(DESTROY));
  const [tag] = parsedTags(hash);
  assert.strictEqual(tag.origin, '破壊');
  assert.strictEqual(cond('editedFrom', tag), null);
});

test('重新載入:改自 A 的標籤若等於具名查詢 B,重開後來源是 B', () => {
  const tag = cond('addValue', tagAt(DESTROY), '受事者中心詞', 'モンスター');
  const [back] = parsedTags(hashOf(tag));
  assert.strictEqual(back.origin, '破壊:モンスター');
  assert.strictEqual(cond('editedFrom', back), null);
});

/* ── 全語料 ── */

test('全語料:237 個具名查詢改到代價位走欄位對往返,張數等於目錄的代價位張數', t => {
  const data = harness.realData();
  if (!data) { t.skip('沒有 web/data.js,請先跑 script/web/build_index.py'); return; }
  const real = harness.load(data);
  const rows = data.vocab.catalog.filter(row => row.predicate);
  assert.strictEqual(rows.length, 237);
  const rcond = (fn, ...args) => harness.cond(real, fn, ...args);
  const wrong = [];
  for (const row of rows) {
    const tag = rcond('tagOf', row, false);
    tag.pred.位置 = ['代價'];
    const hash = harness.hash(real, { cond: rcond('add', rcond('empty'), tag) });
    const st = harness.parseHash(real, hash);
    const [back] = rcond('tags', st.cond);
    const n = harness.ids(real, rcond('toQuery', st.cond, {})).length;
    if (back.origin !== row.name || n !== row.cards.代價 || harness.canonHash(real, hash) !== hash) {
      wrong.push([row.name, back.origin, n, row.cards.代價]);
    }
  }
  assert.deepStrictEqual(wrong, []);
});
