/**
 * conditions.test.js — 條件模型、目錄導覽、網址的動作標籤(predicate-ui 票 02)
 *
 * 跑法:`node --test script/web/conditions.test.js`
 *
 * 接縫:條件模型(目錄列 → 標籤 → 引擎查詢、短句)、`Acat`(目錄 → 導覽樹)、
 * `Hash`(葉路徑 ⇄ 標籤)。全部經 harness 載入真前端程式;目錄是手寫的小目錄,
 * 只有區域對照用真 data.js 的值域。全語料 237 個具名查詢在 predicate.test.js。
 */
'use strict';

const test = require('node:test');
const assert = require('node:assert');
const { execFileSync } = require('node:child_process');
const path = require('node:path');
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
  { name: 'P召喚', path: ['召喚', 'P召喚'], cards: counts(0, 6, 0),
    predicate: pred({ 詞元: 'P召喚' }) },
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
  /* 真目錄 LP・ダメージ、表示形式、規則改寫也是這樣:子節點排在父節點前面。 */
  { name: '倍にする', path: ['LP', 'ダメージ', '倍にする'], cards: counts(0, 33, 0),
    predicate: pred({ 詞元: '倍にする' }) },
  { name: 'ダメージ', path: ['LP', 'ダメージ'], cards: counts(1, 70, 6),
    predicate: pred({ 詞元: 'ダメージ' }) },
  { name: 'LP', path: ['LP'], predicate: null, cards: counts(1, 90, 6) },
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

/* 條件模型抄了述詞與目錄的幾張封閉表(瀏覽器讀不到 Python)。抄本和來源不一致不會報錯,只會短句寫錯字、
   抽屜少一種編輯器,所以這裡從來源讀值,從條件模型看得到的輸出比。 */
const EFFECT_TOKENIZE = path.join(__dirname, '..', '..', '.scratch', 'effect-tokenize');

function sourceTables() {
  const code = 'import json, sys; sys.path.insert(0, sys.argv[1]); import catalog, predicate; print(json.dumps({' +
    '"regionFields": predicate.REGION_FIELDS, "headFields": predicate.HEAD_FIELDS, ' +
    '"zones": catalog.ZONE_LABEL, "players": catalog.PLAYER_LABEL, "polarity": catalog.DEFAULT_POLARITY}))';
  try {
    return JSON.parse(execFileSync('python', ['-c', code, EFFECT_TOKENIZE], { encoding: 'utf8' }));
  } catch (e) {
    return null;
  }
}

const SOURCE = sourceTables();
const realData = harness.realData();
const realBox = realData && harness.load(realData);
const SKIP_SOURCE = '缺 python 或 web/data.js,比不了抄本與來源';
const sentenceOf = pred => harness.cond(realBox, 'sentence',
  { ex: false, origin: null, pred: { 詞元: '破壊', 位置: ['效果'], 極性: POLAR, ...pred } });

test('抄本對來源:區域日文名等於 catalog.ZONE_LABEL,涵蓋值域每個區域', t => {
  if (!SOURCE || !realBox) { t.skip(SKIP_SOURCE); return; }
  const zones = realData.vocab.frame.domains.區域;
  assert.deepStrictEqual(Array.from(zones).sort(), Object.keys(SOURCE.zones).sort());
  for (const zone of zones) {
    assert.strictEqual(sentenceOf({ 所在: [[null, zone]] }), '破壊 在 ' + SOURCE.zones[zone], zone);
  }
});

test('抄本對來源:玩家前綴等於 catalog.PLAYER_LABEL', t => {
  if (!SOURCE || !realBox) { t.skip(SKIP_SOURCE); return; }
  assert.ok(Object.keys(SOURCE.players).length > 0);
  for (const player of Object.keys(SOURCE.players)) {
    assert.strictEqual(sentenceOf({ 所在: [[player, '墓地']] }), `破壊 在 ${SOURCE.players[player]}墓地`, player);
  }
});

test('抄本對來源:區域欄與中心詞欄等於 predicate 的兩張表,抽屜照它選編輯器', t => {
  if (!SOURCE || !realBox) { t.skip(SKIP_SOURCE); return; }
  const kinds = {};
  for (const row of realData.vocab.catalog.filter(r => r.predicate)) {
    const tag = harness.cond(realBox, 'tagAt', row.path.join('›'), false);
    harness.cond(realBox, 'drawerOptions', tag).forEach(g => g.fields.forEach(f => { kinds[f.field] = f.kind; }));
  }
  const fieldsOf = kind => Object.keys(kinds).filter(f => kinds[f] === kind).sort();
  assert.deepStrictEqual(fieldsOf('region'), SOURCE.regionFields.slice().sort());
  assert.deepStrictEqual(fieldsOf('text'), SOURCE.headFields.slice().sort());
});

test('抄本對來源:catalog.DEFAULT_POLARITY 是短句不寫的預設極性', t => {
  if (!SOURCE || !realBox) { t.skip(SKIP_SOURCE); return; }
  assert.strictEqual(sentenceOf({ 極性: SOURCE.polarity }), '破壊');
  assert.strictEqual(sentenceOf({ 極性: SOURCE.polarity.slice(0, 1) }).includes('極性'), true);
});

/* ── 目錄導覽樹 ── */

const nodeOf = key => harness.catalogNode(box, key);

test('目錄樹:根是路徑只有一段的節點,依目錄順序', () => {
  assert.deepStrictEqual(harness.catalogRoots(box), ['召喚', '規則改寫', '破壊', '対象とする', '取り除く', 'LP']);
});

test('目錄樹:缺的路徑補純導覽節點,沒有張數也不成標籤', () => {
  const nav = nodeOf('規則改寫›にする');
  assert.strictEqual(nav.name, 'にする');
  assert.strictEqual(nav.path, '');
  assert.strictEqual(nav.count, null);
  assert.deepStrictEqual(nav.kids, ['規則改寫›にする›にする:種族']);
  assert.ok(nodeOf('規則改寫').kids.includes('規則改寫›にする'));
});

test('目錄樹:詞元節點 召喚 掛在同路徑的大類 召喚 底下、排在大類所有子的最後,葉路徑仍是 召喚', () => {
  const top = nodeOf('召喚');
  assert.strictEqual(top.path, '');
  assert.deepStrictEqual(top.kids.slice(0, -1), ['召喚›特殊召喚', '召喚›P召喚']);
  const lemma = nodeOf(top.kids[top.kids.length - 1]);
  assert.strictEqual(lemma.name, '召喚');
  assert.strictEqual(lemma.path, '召喚');
  assert.deepStrictEqual(lemma.kids, []);
});

test('目錄樹:帶子的詞元節點只展開,自己以同名列在子的最後,帶原本的葉路徑與張數', () => {
  const lemma = nodeOf('破壊');
  assert.strictEqual(lemma.path, '');
  assert.deepStrictEqual(lemma.count, { text: '30', zero: false });
  assert.deepStrictEqual(lemma.kids.slice(0, -1), ['破壊›破壊@自分墓地', '破壊›破壊できない']);
  const last = nodeOf(lemma.kids[lemma.kids.length - 1]);
  assert.strictEqual(last.name, '破壊');
  assert.strictEqual(last.parent, '破壊');
  assert.strictEqual(last.path, '破壊');
  assert.deepStrictEqual(last.count, { text: '30', zero: false });
  assert.deepStrictEqual(last.kids, []);
  assert.deepStrictEqual(tagAt(last.path), tagAt('破壊'));
});

test('目錄樹:沒有子的詞元節點不變', () => {
  assert.deepStrictEqual(nodeOf('対象とする'), { key: '対象とする', name: '対象とする', parent: '', kids: [],
                                             path: '対象とする', count: { text: '條件 3396', zero: true } });
});

test('目錄樹:父節點的列排在子節點後面時,補好的節點接回那一列;那一列仍排在子的最後', () => {
  assert.deepStrictEqual(nodeOf('LP'), { key: 'LP', name: 'LP', parent: '', kids: ['LP›ダメージ'],
                                         path: '', count: { text: '90', zero: false } });
  const lemma = nodeOf('LP›ダメージ');
  assert.strictEqual(lemma.path, '');
  assert.deepStrictEqual(lemma.count, { text: '70', zero: false });
  assert.strictEqual(lemma.kids[0], 'LP›ダメージ›倍にする');
  const last = nodeOf(lemma.kids[1]);
  assert.strictEqual(lemma.kids.length, 2);
  assert.strictEqual(last.name, 'ダメージ');
  assert.strictEqual(last.path, 'LP›ダメージ');
});

test('目錄樹:「已用」照葉路徑標,一條葉路徑只落在一個節點', () => {
  const all = [];
  const walk = key => {
    const n = nodeOf(key);
    all.push(n);
    n.kids.forEach(walk);
  };
  harness.catalogRoots(box).forEach(walk);
  const owners = all.filter(n => n.path === '破壊').map(n => n.key);
  assert.deepStrictEqual(owners, [nodeOf('破壊').kids.slice(-1)[0]]);
  const paths = all.map(n => n.path).filter(Boolean);
  assert.strictEqual(new Set(paths).size, paths.length);
});

test('目錄樹全語料:帶子的詞元節點 25 個只展開、同名列在最後;大類 召喚 的詞元節點 召喚 也在最後', t => {
  const data = harness.realData();
  if (!data) { t.skip('沒有 web/data.js,請先跑 script/web/build_index.py'); return; }
  const real = harness.load(data);
  const all = [];
  const walk = key => {
    const n = harness.catalogNode(real, key);
    all.push(n);
    n.kids.forEach(walk);
  };
  harness.catalogRoots(real).forEach(walk);
  assert.strictEqual(data.vocab.catalog.length, 261);
  assert.strictEqual(all.length, 263 + 25);
  assert.deepStrictEqual(all.filter(n => !n.count).map(n => n.key).sort(),
                         ['表示形式›にする', '規則改寫›にする'].sort());
  const lasts = all.filter(n => n.key.includes('#'));
  assert.deepStrictEqual(lasts.map(n => n.name).sort(), [
    '召喚', '特殊召喚', '加える', '戻す', '置く', '破壊', '無効にする', '融合素材とする', 'X素材とする',
    '重ねる', '素材とする', 'S素材とする', '取り除く', '得る', '選ぶ', '確認', '見せる', 'めくる', '指定',
    '行う', '破壊(耐性)', '無効にする(耐性)', '発動(限制)', '特殊召喚(限制)', '対象にする(限制)', '使用(限制)',
  ].sort());
  for (const last of lasts) {
    const parent = harness.catalogNode(real, last.parent);
    assert.strictEqual(parent.kids[parent.kids.length - 1], last.key, last.key);
    assert.strictEqual(last.name, parent.name, last.key);
    assert.deepStrictEqual(last.kids, [], last.key);
    if (parent.parent || parent.name !== '召喚') {
      assert.strictEqual(parent.path, '', last.key);
      assert.deepStrictEqual(parent.count, last.count, last.key);
    }
  }
  assert.strictEqual(lasts.find(n => n.parent === '召喚').path, '召喚');
  assert.deepStrictEqual(all.filter(n => n.path && n.kids.length), []);
  assert.strictEqual(all.filter(n => n.path).length, 237);
  assert.deepStrictEqual(all.filter(n => n.count && n.count.zero).map(n => n.count.text).sort(),
                         ['代價 10', '條件 3396'].sort());
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

test('目錄過濾:打帶子的詞元節點名字,節點展開、同名的最後一列看得到', () => {
  const f = harness.catalogFilter(box, '破壊');
  const last = nodeOf('破壊').kids.slice(-1)[0];
  assert.ok(f.open.includes('破壊'));
  assert.ok(f.visible.includes(last));
  const g = harness.catalogFilter(box, 'ダメージ');
  assert.ok(g.open.includes('LP›ダメージ'));
  assert.ok(g.visible.includes(nodeOf('LP›ダメージ').kids.slice(-1)[0]));
});

test('目錄過濾全語料:子名不含父名的 破壊(耐性),打父名時展開、最後一列看得到', t => {
  const data = harness.realData();
  if (!data) { t.skip('沒有 web/data.js,請先跑 script/web/build_index.py'); return; }
  const real = harness.load(data);
  const roots = harness.catalogRoots(real);
  const find = (keys, name) => {
    for (const k of keys) {
      const n = harness.catalogNode(real, k);
      if (n.name === name && n.kids.length) return n;
      const hit = find(n.kids, name);
      if (hit) return hit;
    }
    return null;
  };
  const resist = find(roots, '破壊(耐性)');
  assert.ok(resist.kids.slice(0, -1).some(k => !harness.catalogNode(real, k).name.includes('破壊(耐性)')));
  const f = harness.catalogFilter(real, '破壊(耐性)');
  assert.ok(f.open.includes(resist.key));
  assert.ok(f.visible.includes(resist.kids[resist.kids.length - 1]));
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

const procCounts = (代價, 效果, 條件, 召喚手續) => ({ 代價, 效果, 條件, 召喚手續 });
const PROC_CATALOG = [
  { name: 'リリース', path: ['リリース'], cards: procCounts(0, 0, 0, 7), predicate: pred({ 詞元: 'リリース' }) },
  { name: '見せる', path: ['見せる'], cards: procCounts(0, 0, 4, 2), predicate: pred({ 詞元: '見せる' }) },
  { name: '捨てる', path: ['捨てる'], cards: procCounts(3, 0, 4, 2), predicate: pred({ 詞元: '捨てる' }) },
  { name: '除外', path: ['除外'], cards: procCounts(1, 5, 1, 9), predicate: pred({ 詞元: '除外' }) },
];
const procBox = harness.load({ vocab: { catalog: PROC_CATALOG } });

test('召喚手續:新標籤預設效果;效果位 0 張時依序取 代價、條件、召喚手續 第一個有張數的', () => {
  const positionOf = name => harness.cond(procBox, 'tagAt', name, false).pred.位置;
  assert.deepStrictEqual(positionOf('除外'), ['效果']);
  assert.deepStrictEqual(positionOf('捨てる'), ['代價']);
  assert.deepStrictEqual(positionOf('見せる'), ['條件']);
  assert.deepStrictEqual(positionOf('リリース'), ['召喚手續']);
});

test('召喚手續:只在召喚手續有張數的列,目錄樹灰字標「召喚手續 N」', () => {
  assert.deepStrictEqual(harness.catalogNode(procBox, 'リリース').count, { text: '召喚手續 7', zero: true });
  assert.deepStrictEqual(harness.catalogNode(procBox, '除外').count, { text: '5', zero: false });
});

const realTag = (real, lemma) => {
  const row = harness.cond(real, 'named', { pred: { 詞元: lemma, 極性: POLAR } });
  return harness.cond(real, 'tagAt', row.path.join('›'), false);
};
const positionChips = (real, tag) => {
  const field = harness.cond(real, 'drawerOptions', tag)
    .flatMap(g => g.fields).find(f => f.field === '位置');
  return field.values.map(v => v.value);
};

test('召喚手續全語料:抽屜位置欄 除外 四顆、破壊 沒有召喚手續', t => {
  if (!realBox) { t.skip('沒有 web/data.js,請先跑 script/web/build_index.py'); return; }
  const real = realBox;
  assert.deepStrictEqual(positionChips(real, realTag(real, '除外')), ['代價', '效果', '條件', '召喚手續']);
  assert.ok(!positionChips(real, realTag(real, '破壊')).includes('召喚手續'));
});

test('召喚手續全語料:網址「位置:召喚手續」讀寫來回不變;舊網址的位置不多出召喚手續', t => {
  if (!realBox) { t.skip('沒有 web/data.js,請先跑 script/web/build_index.py'); return; }
  const real = realBox;
  const rc = (fn, ...args) => harness.cond(real, fn, ...args);
  const banish = realTag(real, '除外');
  const onlyProc = rc('toggleValue', rc('toggleValue', banish, '位置', '召喚手續'), '位置', '效果');
  assert.deepStrictEqual(onlyProc.pred.位置, ['召喚手續']);
  const state = rc('add', rc('empty'), onlyProc);
  const h = harness.hash(real, { cond: state });
  assert.ok(h.includes(encodeURIComponent('位置') + ':' + encodeURIComponent('召喚手續')), h);
  const back = harness.parseHash(real, h).cond;
  assert.deepStrictEqual(rc('tags', back).map(t => [t.origin, t.pred.位置]), [['除外', ['召喚手續']]]);
  assert.strictEqual(harness.hash(real, { cond: back }), h);
  assert.strictEqual(harness.canonHash(real, h), h);
  const leaf = harness.parseHash(real, 'act=' + encodeURIComponent(rc('leafPath', banish)));
  assert.deepStrictEqual(rc('tags', leaf.cond)[0].pred.位置, ['效果']);
  const three = rc('toggleValue', rc('toggleValue', banish, '位置', '代價'), '位置', '條件');
  const h3 = harness.hash(real, { cond: rc('add', rc('empty'), three) });
  assert.deepStrictEqual(rc('tags', harness.parseHash(real, h3).cond)[0].pred.位置, ['代價', '效果', '條件']);
});
