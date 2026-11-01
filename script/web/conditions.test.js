/**
 * conditions.test.js — 條件模型、目錄導覽、網址的動作標籤(predicate-ui 票 02)
 *
 * 跑法:`node --test script/web/conditions.test.js`
 *
 * 接縫:條件模型(目錄列 → 標籤 → 引擎查詢、短句)、`Acat.catalog`(目錄 → 導覽樹)、
 * `Hash`(葉路徑 ⇄ 標籤)。全部經 harness 載入真前端程式;目錄是手寫的小目錄,
 * 只有區域對照用真 data.js 的值域。全語料 237 個具名查詢在 predicate.test.js。
 */
'use strict';

const test = require('node:test');
const assert = require('node:assert');
const harness = require('./frontend_harness.js');

const POLAR = ['肯定', '可能'];
const pred = extra => ({ 極性: POLAR, ...extra });
const counts = (代價, 效果, 條件) => ({ 代價, 效果, 條件 });

const REVIVE = '召喚›特殊召喚›特殊召喚←墓地';
const CATALOG = [
  { name: '召喚', path: ['召喚'], predicate: null, cards: counts(0, 50, 9) },
  { name: '特殊召喚', path: ['召喚', '特殊召喚'], cards: counts(0, 40, 7),
    predicate: pred({ 詞元: '特殊召喚' }) },
  { name: '特殊召喚←墓地', path: REVIVE.split('›'), cards: counts(0, 12, 1),
    predicate: pred({ 詞元: '特殊召喚', 來源: [[null, '墓地']] }) },
  { name: '召喚', path: ['召喚'], cards: counts(0, 3, 2),
    predicate: pred({ 詞元: '召喚' }) },
  { name: '規則改寫', path: ['規則改寫'], predicate: null, cards: counts(0, 8, 0) },
  { name: 'にする:種族', path: ['規則改寫', 'にする', 'にする:種族'], cards: counts(0, 8, 0),
    predicate: pred({ 詞元: 'にする', 受事者中心詞: ['種族'] }) },
  { name: '破壊', path: ['破壊'], cards: counts(5, 30, 20),
    predicate: pred({ 詞元: '破壊' }) },
  { name: '破壊@自分墓地', path: ['破壊', '破壊@自分墓地'], cards: counts(0, 2, 0),
    predicate: pred({ 詞元: '破壊', 所在: [['自分', '墓地']] }) },
  { name: '破壊できない', path: ['破壊', '破壊できない'], cards: counts(0, 4, 0),
    predicate: { 詞元: '破壊', 極性: ['否定'], 否定形: ['不可能'] } },
  { name: '対象とする', path: ['対象とする'], cards: counts(0, 0, 3396),
    predicate: pred({ 詞元: '対象とする' }) },
  { name: '取り除く', path: ['取り除く'], cards: counts(10, 6, 0),
    predicate: pred({ 詞元: '取り除く' }) },
  { name: '取り除く@お互いのフィールド', path: ['取り除く', '取り除く@お互いのフィールド'],
    cards: counts(10, 0, 0),
    predicate: pred({ 詞元: '取り除く', 所在: [['お互い', '場上']] }) },
];

const box = harness.load({ vocab: { catalog: CATALOG } });
const cond = (fn, ...args) => harness.cond(box, fn, ...args);
const tagAt = (path, ex) => cond('tagAt', path, !!ex);
const withTags = (...tags) => tags.reduce((st, t) => cond('add', st, t), cond('empty'));

/* ── 目錄列 → 標籤 ── */

test('目錄列 → 標籤:述詞複製一份,帶效果位預設,記來源名', () => {
  assert.deepStrictEqual(tagAt(REVIVE), {
    ex: false,
    origin: '特殊召喚←墓地',
    pred: { 詞元: '特殊召喚', 極性: POLAR, 來源: [[null, '墓地']], 位置: ['效果'] },
  });
});

test('目錄列 → 標籤:排除標籤只差 ex', () => {
  assert.strictEqual(tagAt('破壊', true).ex, true);
  assert.deepStrictEqual(tagAt('破壊', true).pred, tagAt('破壊').pred);
});

test('目錄列 → 標籤:效果位 0 張帶有張數的位置(對象とする 條件、取り除く@ 代價)', () => {
  assert.deepStrictEqual(tagAt('対象とする').pred.位置, ['條件']);
  assert.deepStrictEqual(tagAt('取り除く›取り除く@お互いのフィールド').pred.位置, ['代價']);
});

test('目錄列 → 標籤:效果位有張數時不看其他位置(代價多也是效果)', () => {
  assert.deepStrictEqual(tagAt('取り除く').pred.位置, ['效果']);
});

test('目錄列 → 標籤:大類同路徑的詞元節點 召喚 認得到,中類、未知路徑不成標籤', () => {
  assert.strictEqual(tagAt('召喚').origin, '召喚');
  assert.strictEqual(tagAt('召喚').pred.詞元, '召喚');
  assert.strictEqual(tagAt('規則改寫'), null);
  assert.strictEqual(tagAt('規則改寫›にする'), null);
  assert.strictEqual(tagAt('不存在›節點'), null);
});

test('目錄沒有載入時,路徑都不成標籤', () => {
  const bare = harness.load({ vocab: {} });
  assert.strictEqual(harness.cond(bare, 'tagAt', '破壊', false), null);
});

/* ── 標籤 → 引擎查詢 ── */

test('標籤 → 引擎查詢:包含、排除分到 preds.inc、preds.ex,位置照帶', () => {
  const st = withTags(tagAt('破壊'), tagAt('破壊›破壊できない', true), tagAt('対象とする'));
  assert.deepStrictEqual(cond('toQuery', st, {}), {
    preds: {
      inc: [
        { 詞元: '破壊', 極性: POLAR, 位置: ['效果'] },
        { 詞元: '対象とする', 極性: POLAR, 位置: ['條件'] },
      ],
      ex: [{ 詞元: '破壊', 極性: ['否定'], 否定形: ['不可能'], 位置: ['效果'] }],
    },
  });
});

test('標籤 → 引擎查詢:左側條件原樣併進去;沒有標籤就沒有 preds 這一欄', () => {
  const side = { name: '龍', nameLang: 'zh', cat: { m: 1 } };
  assert.deepStrictEqual(cond('toQuery', cond('empty'), side), side);
  assert.deepStrictEqual(cond('toQuery', withTags(tagAt('破壊')), side).cat, { m: 1 });
  assert.strictEqual(cond('toQuery', withTags(tagAt('破壊')), side).name, '龍');
});

/* ── 狀態 ── */

test('狀態:新標籤接在最後,removeAt 刪第 i 張,原狀態不變', () => {
  const one = withTags(tagAt('破壊'));
  const two = cond('add', one, tagAt('対象とする'));
  assert.deepStrictEqual(cond('tags', two).map(t => t.origin), ['破壊', '対象とする']);
  assert.deepStrictEqual(cond('tags', one).map(t => t.origin), ['破壊']);
  assert.deepStrictEqual(cond('tags', cond('removeAt', two, 0)).map(t => t.origin), ['対象とする']);
});

test('狀態:一模一樣的標籤不重複;同一列的包含與排除是兩張', () => {
  const st = withTags(tagAt('破壊'), tagAt('破壊'), tagAt('破壊', true));
  assert.deepStrictEqual(cond('tags', st).map(t => t.ex), [false, true]);
});

test('狀態:已用路徑列出條件列上的具名查詢,包含與排除都算', () => {
  const st = withTags(tagAt(REVIVE), tagAt('対象とする', true));
  assert.deepStrictEqual(cond('usedPaths', st), [REVIVE, '対象とする']);
  assert.deepStrictEqual(cond('usedPaths', cond('empty')), []);
});

/* ── 認具名查詢 ── */

test('認具名查詢:不看位置,其餘欄相同就是', () => {
  const tag = tagAt('破壊');
  assert.strictEqual(cond('named', tag).name, '破壊');
  assert.strictEqual(cond('named', { ...tag, pred: { ...tag.pred, 位置: ['代價', '條件'] } }).name, '破壊');
  assert.strictEqual(cond('named', { ...tag, pred: { ...tag.pred, 詞元: ['破壊'], 位置: [] } }).name, '破壊');
});

test('認具名查詢:其他欄不同就不是;排除標籤也認得', () => {
  const tag = tagAt('破壊');
  assert.strictEqual(cond('named', { ...tag, pred: { ...tag.pred, 動作對象: ['此卡'] } }), null);
  assert.strictEqual(cond('named', { ...tag, pred: { 詞元: '破壊', 位置: ['效果'] } }), null);
  assert.strictEqual(cond('named', tagAt('破壊', true)).name, '破壊');
});

test('認具名查詢:改回原樣認得回去,同欄多值順序不影響', () => {
  const tag = tagAt('破壊');
  const reversed = { ...tag, pred: { ...tag.pred, 極性: ['可能', '肯定'] } };
  assert.strictEqual(cond('named', reversed).name, '破壊');
});

test('葉路徑:只有位置是該列預設的具名查詢才有', () => {
  const tag = tagAt('破壊');
  assert.strictEqual(cond('leafPath', tag), '破壊');
  assert.strictEqual(cond('leafPath', tagAt('対象とする')), '対象とする');
  assert.strictEqual(cond('leafPath', { ...tag, pred: { ...tag.pred, 位置: ['條件'] } }), null);
  assert.strictEqual(cond('leafPath', { ...tag, pred: { ...tag.pred, 動作對象: ['此卡'] } }), null);
});

/* ── 短句 ── */

test('短句:效果位與肯定+可能不寫', () => {
  assert.strictEqual(cond('sentence', tagAt('破壊')), '破壊');
});

test('短句:排除寫「沒有」', () => {
  assert.strictEqual(cond('sentence', tagAt('破壊', true)), '沒有 破壊');
});

test('短句:位置不是效果時寫在最前面,接在「沒有」後面', () => {
  assert.strictEqual(cond('sentence', tagAt('対象とする')), '條件位 対象とする');
  assert.strictEqual(cond('sentence', tagAt('対象とする', true)), '沒有 條件位 対象とする');
});

test('短句:區域用日文,不看玩家只寫區域,有玩家連在前面', () => {
  assert.strictEqual(cond('sentence', tagAt(REVIVE)), '特殊召喚 從 墓地');
  assert.strictEqual(cond('sentence', tagAt('破壊›破壊@自分墓地')), '破壊 在 自分墓地');
  assert.strictEqual(cond('sentence', tagAt('取り除く›取り除く@お互いのフィールド')),
                     '代價位 取り除く 在 お互いのフィールド');
});

test('短句:其餘欄依固定順序加連接字,極性不是預設時寫在最後', () => {
  const tag = { ex: false, origin: null,
    pred: { 極性: ['否定'], 否定形: ['不可能'], 受事者中心詞: ['モンスター'], 目的: [['相手', '手牌']],
            來源: [['自分', '牌組'], [null, '墓地']], 詞元: '加える', 位置: ['效果'] } };
  assert.strictEqual(cond('sentence', tag),
    '加える 從 自分デッキ或墓地 到 相手手札 對象是 モンスター 否定形 不可能 極性 否定');
});

test('短句:句子片段給條件列分欄,每段記它的欄名', () => {
  assert.deepStrictEqual(cond('sentenceParts', tagAt(REVIVE)), [
    { field: '詞元', glue: '', text: '特殊召喚' },
    { field: '來源', glue: '從', text: '墓地' },
  ]);
});

test('區域對照涵蓋值域每個區域', t => {
  const data = harness.realData();
  if (!data) { t.skip('沒有 web/data.js,請先跑 script/web/build_index.py'); return; }
  const JA = { 場上: 'フィールド', 墓地: '墓地', 手牌: '手札', 牌組: 'デッキ',
               除外: '除外', 靈擺區: 'Pゾーン', 額外牌組: 'EXデッキ' };
  const zones = data.vocab.frame.domains.區域;
  assert.ok(zones.length > 0);
  for (const zone of zones) {
    const tag = { ex: false, origin: null, pred: { 詞元: '破壊', 所在: [[null, zone]], 位置: ['效果'], 極性: POLAR } };
    assert.strictEqual(cond('sentence', tag), '破壊 在 ' + JA[zone], zone);
  }
});

/* ── 目錄導覽樹 ── */

const nodeOf = key => harness.catalogNode(box, key);

test('目錄樹:根是路徑只有一段的節點,依目錄順序', () => {
  assert.deepStrictEqual(harness.catalogRoots(box), ['召喚', '規則改寫', '破壊', '対象とする', '取り除く']);
});

test('目錄樹:缺的路徑補純導覽節點,沒有張數也不成標籤', () => {
  const nav = nodeOf('規則改寫›にする');
  assert.strictEqual(nav.name, 'にする');
  assert.strictEqual(nav.path, '');
  assert.strictEqual(nav.count, null);
  assert.deepStrictEqual(nav.kids, ['規則改寫›にする›にする:種族']);
  assert.ok(nodeOf('規則改寫').kids.includes('規則改寫›にする'));
});

test('目錄樹:詞元節點 召喚 掛在同路徑的大類 召喚 底下,葉路徑仍是 召喚', () => {
  const top = nodeOf('召喚');
  assert.strictEqual(top.path, '');
  assert.strictEqual(top.kids.length, 2);
  const lemma = nodeOf(top.kids[1]);
  assert.strictEqual(lemma.name, '召喚');
  assert.strictEqual(lemma.path, '召喚');
  assert.deepStrictEqual(lemma.kids, []);
});

test('目錄樹:每列顯示效果位張數,大類沿用目錄列', () => {
  assert.deepStrictEqual(nodeOf('破壊').count, { text: '30', zero: false });
  assert.deepStrictEqual(nodeOf('召喚').count, { text: '50', zero: false });
});

test('目錄樹:效果位 0 張灰字標有張數的位置', () => {
  assert.deepStrictEqual(nodeOf('対象とする').count, { text: '條件 3396', zero: true });
  assert.deepStrictEqual(nodeOf('取り除く›取り除く@お互いのフィールド').count, { text: '代價 10', zero: true });
});

test('目錄過濾:留名字含字面的節點與祖先,祖先展開', () => {
  assert.deepStrictEqual(harness.catalogFilter(box, '墓地'), {
    visible: ['召喚', '召喚›特殊召喚', REVIVE, '破壊', '破壊›破壊@自分墓地'].sort(),
    open: ['召喚', '召喚›特殊召喚', '破壊'].sort(),
  });
});

test('目錄過濾:命中節點底下的子節點留著可展開;空字面不過濾', () => {
  const f = harness.catalogFilter(box, '特殊召喚');
  assert.ok(f.visible.includes(REVIVE));
  assert.strictEqual(harness.catalogFilter(box, ''), null);
  assert.strictEqual(harness.catalogFilter(box, '  '), null);
  assert.deepStrictEqual(harness.catalogFilter(box, '沒有這個'), { visible: [], open: [] });
});

/* ── 網址 ── */

const EMPTY_Q = { name: '', nameLang: 'zh', code: '', text: '' };
const DOM_SORT = { key: 'dom', dir: '' };
const hashOf = (st, extra) => harness.hash(box, { q: { ...EMPTY_Q, ...extra }, cond: st, sort: DOM_SORT });
const parsed = str => harness.parseHash(box, str);

test('網址:沒改過的標籤寫葉路徑,排除加 -,照條件列順序', () => {
  const st = withTags(tagAt('対象とする'), tagAt(REVIVE, true));
  assert.strictEqual(hashOf(st),
    'act=' + encodeURIComponent('対象とする') + ',-' + encodeURIComponent(REVIVE));
});

test('網址:葉路徑往返相等,位置預設跟著目錄列', () => {
  const st = withTags(tagAt(REVIVE), tagAt('破壊', true), tagAt('対象とする'));
  const back = parsed(hashOf(st));
  assert.deepStrictEqual(back.cond, st);
  assert.deepStrictEqual(cond('tags', back.cond)[2].pred.位置, ['條件']);
});

test('網址:動作標籤和左側條件並存,互不影響', () => {
  const h = hashOf(withTags(tagAt('破壊')), { text: '墓地', atk: { min: 2000, max: null } });
  const back = parsed(h);
  assert.strictEqual(back.q.text, '墓地');
  assert.deepStrictEqual(back.q.atk, { min: 2000, max: null });
  assert.deepStrictEqual(cond('tags', back.cond).map(t => t.origin), ['破壊']);
});

test('網址:沒有標籤就沒有 act,解析結果也不帶 cond', () => {
  assert.strictEqual(hashOf(cond('empty')), '');
  assert.ok(!('cond' in parsed('text=abc')));
});

test('網址:canon 冪等,重複的標籤收成一張', () => {
  const raw = 'act=' + encodeURIComponent('破壊') + ',' + encodeURIComponent('破壊') + '&text=abc';
  const once = harness.canonHash(box, raw);
  assert.strictEqual(once, 'text=abc&act=' + encodeURIComponent('破壊'));
  assert.strictEqual(harness.canonHash(box, once), once);
});

test('網址:未知路徑、大類路徑安靜忽略,其餘條件照常', () => {
  const raw = 'act=' + ['不存在', '規則改寫', '破壊'].map(encodeURIComponent).join(',') + '&text=abc';
  const back = parsed(raw);
  assert.deepStrictEqual(cond('tags', back.cond).map(t => t.origin), ['破壊']);
  assert.strictEqual(back.q.text, 'abc');
  assert.ok(!('cond' in parsed('act=' + encodeURIComponent('不存在'))));
});

test('網址:舊的 actCost、actPat 忽略,canon 後消失', () => {
  const raw = 'act=' + encodeURIComponent('破壊') + '&actCost=1&actPat=self';
  const back = parsed(raw);
  assert.deepStrictEqual(Object.keys(back.q).sort(), Object.keys(EMPTY_Q).sort());
  assert.strictEqual(harness.canonHash(box, raw), 'act=' + encodeURIComponent('破壊'));
});

test('網址:壞百分比編碼不崩,那一段安靜忽略', () => {
  const back = parsed('act=%E0%A4%A,' + encodeURIComponent('破壊'));
  assert.deepStrictEqual(cond('tags', back.cond).map(t => t.origin), ['破壊']);
});
