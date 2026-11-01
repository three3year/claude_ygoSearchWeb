/**
 * filter_tags.test.js — 左側條件標籤與 OR 區(predicate-ui 票 05)
 *
 * 跑法:`node --test script/web/filter_tags.test.js`
 *
 * 接縫:條件模型(左側條件 → 標籤;兩區 → 含 `q.or` 的引擎查詢)、`Hash`(`actOr`、`or`)、
 * 「網址 → `Hash.parse` → 條件模型 → `runQuery`」這條使用者開網址走的路。全部經 harness 載入
 * 真前端程式;拖曳、跳到左邊、× 走側欄控制項是 DOM,在真瀏覽器走(票 Comments)。
 */
'use strict';

const test = require('node:test');
const assert = require('node:assert');
const harness = require('./frontend_harness.js');

const POLAR = ['肯定', '可能'];
const pred = extra => ({ 極性: POLAR, ...extra });
const counts = (代價, 效果, 條件) => ({ 代價, 效果, 條件 });

const items = pairs => Object.keys(pairs).map(code => ({ code, zh: pairs[code] }));
const VOCAB = {
  cat: { zh: '大類', items: items({ m: '怪獸', s: '魔法', t: '陷阱' }) },
  kind: { zh: '效果類型', items: items({ q: '速攻', i: '起動' }) },
  sub_m: { zh: '怪獸子類型', items: items({ fusion: '融合', xyz: '超量' }) },
  sub_s: { zh: '魔法子類型', items: items({ quick: '速攻', field: '場地' }) },
  attr: { zh: '屬性', items: items({ light: '光', dark: '闇' }) },
  ban_o: { zh: 'OCG 禁限', items: items({ f: '禁止', l: '限制' }) },
  catalog: [
    { name: '破壊', path: ['破壊'], cards: counts(5, 30, 20), predicate: pred({ 詞元: '破壊' }) },
    { name: 'ドロー', path: ['ドロー'], cards: counts(0, 9, 1), predicate: pred({ 詞元: 'ドロー' }) },
    { name: '対象とする', path: ['対象とする'], cards: counts(0, 0, 3),
      predicate: pred({ 詞元: '対象とする' }) },
  ],
};

const box = harness.load({ vocab: VOCAB });
const cond = (fn, ...args) => harness.cond(box, fn, ...args);
const tagAt = (path, ex) => cond('tagAt', path, !!ex);
const side = q => cond('sideTags', q);
const brief = list => list.map(t => [t.key, t.label, t.val]);

/* ── 左側條件 → 標籤 ── */

test('左側條件 → 標籤:沒有條件就沒有標籤;空字串與 nameLang、textMat 不算條件', () => {
  assert.deepStrictEqual(side({ name: '', nameLang: 'ja', code: '', text: '', textMat: 1 }), []);
});

test('左側條件 → 標籤:同一軸併成一張,包含在前、排除帶 −,標籤內維持 OR', () => {
  assert.deepStrictEqual(brief(side({ attr: { dark: -1, light: 1 }, kind: { q: 1, i: 1 } })), [
    ['kind', '效果類型', '速攻、起動'],
    ['attr', '屬性', '光、−闇'],
  ]);
  assert.deepStrictEqual(side({ kind: { q: 1, i: 1 } })[0].part, { kind: { q: 1, i: 1 } });
});

test('左側條件 → 標籤:大類不寫軸名,只寫值', () => {
  assert.deepStrictEqual(brief(side({ cat: { m: 1, s: 1 } })), [['cat', '', '怪獸、魔法']]);
});

test('左側條件 → 標籤:選了子類型不另列大類,子類型標籤帶著大類', () => {
  const tags = side({ cat: { m: 1 }, sub: { 'm:fusion': 1 } });
  assert.deepStrictEqual(brief(tags), [['sub:m', '怪獸子類型', '融合']]);
  assert.deepStrictEqual(tags[0].part, { sub: { 'm:fusion': 1 }, cat: { m: 1 } });
});

test('左側條件 → 標籤:兩個大類只有一個選了子類型時,另一個留在大類標籤', () => {
  const tags = side({ cat: { m: 1, s: 1 }, sub: { 'm:xyz': -1 } });
  assert.deepStrictEqual(brief(tags), [['cat', '', '魔法'], ['sub:m', '怪獸子類型', '−超量']]);
  assert.deepStrictEqual(tags[0].part, { cat: { s: 1 } });
});

test('左側條件 → 標籤:各大類的子類型是各自一張', () => {
  const tags = side({ cat: { m: 1, s: 1 }, sub: { 'm:xyz': 1, 's:quick': 1 } });
  assert.deepStrictEqual(brief(tags), [
    ['sub:m', '怪獸子類型', '超量'],
    ['sub:s', '魔法子類型', '速攻'],
  ]);
  assert.deepStrictEqual(tags[1].part, { sub: { 's:quick': 1 }, cat: { s: 1 } });
});

test('左側條件 → 標籤:數字範圍四種寫法,未知值(?)併在同一張', () => {
  const val = r => side({ atk: r })[0].val;
  assert.strictEqual(val({ min: 2000, max: null }), '≥2000');
  assert.strictEqual(val({ min: null, max: 1000 }), '≤1000');
  assert.strictEqual(val({ min: 1000, max: 2000 }), '1000〜2000');
  assert.strictEqual(val({ min: 1500, max: 1500 }), '1500');
  const both = side({ atk: { min: 2000, max: null }, atkq: 1 })[0];
  assert.deepStrictEqual([both.key, both.label, both.val], ['atk', '攻擊力', '≥2000 ?']);
  assert.deepStrictEqual(both.part, { atk: { min: 2000, max: null }, atkq: 1 });
  assert.strictEqual(side({ dfq: -1 })[0].val, '−?');
});

test('左側條件 → 標籤:密碼、卡名、效果文在最前面,比法寫在標籤上但不進片段', () => {
  const tags = side({ text: '墓地', textMat: 1, name: '龍', nameLang: 'ja', code: '123', cat: { m: 1 } });
  assert.deepStrictEqual(brief(tags), [
    ['code', '密碼', '123'],
    ['name', '卡名(日)', '龍'],
    ['text', '效果文', '墓地(含素材行)'],
    ['cat', '', '怪獸'],
  ]);
  assert.deepStrictEqual(tags[1].part, { name: '龍' });
  assert.deepStrictEqual(tags[2].part, { text: '墓地' });
  assert.strictEqual(side({ name: '龍', nameLang: 'zh' })[0].label, '卡名');
});

test('左側條件 → 標籤:值域沒有的代碼寫代碼本身,不崩', () => {
  assert.strictEqual(side({ attr: { wind: 1 } })[0].val, 'wind');
});

/* ── 兩區 → 引擎查詢 ── */

const CARDS = [
  { id: 1, c: 'm', at: 'light', atk: 2500, e: [] },
  { id: 2, c: 'm', at: 'dark', atk: 2500, e: [] },
  { id: 3, c: 'm', at: 'light', atk: 100, e: [] },
  { id: 4, c: 'm', at: 'dark', atk: 100, e: [] },
  { id: 5, c: 's', e: [] },
].map(c => ({ n: '卡' + c.id, ...c }));
const live = harness.load({ cards: CARDS, vocab: VOCAB });
const liveCond = (fn, ...args) => harness.cond(live, fn, ...args);

const moveSide = (st, ...keys) => keys.reduce((s, k) => cond('moveSide', s, k, 'or'), st);

test('兩區 → 引擎查詢:都在 AND 時等於原本的查詢,沒有 or 這一欄', () => {
  const q = { name: '龍', nameLang: 'zh', cat: { m: 1 }, atk: { min: 2000, max: null } };
  assert.deepStrictEqual(cond('toQuery', cond('add', cond('empty'), tagAt('破壊')), q), {
    ...q,
    preds: { inc: [{ 詞元: '破壊', 極性: POLAR, 位置: ['效果'] }], ex: [] },
  });
});

test('兩區 → 引擎查詢:OR 區的左側條件從主查詢拿走,一張標籤一個片段', () => {
  const q = { cat: { m: 1 }, atk: { min: 2000, max: null }, attr: { light: 1 } };
  const st = moveSide(cond('empty'), 'atk', 'attr');
  assert.deepStrictEqual(cond('toQuery', st, q), {
    cat: { m: 1 },
    or: [{ attr: { light: 1 } }, { atk: { min: 2000, max: null } }],
  });
});

test('兩區 → 引擎查詢:OR 區的動作標籤各成一個片段,排除放進片段的 ex', () => {
  const st = [tagAt('破壊'), tagAt('ドロー', true)]
    .reduce((s, t) => cond('add', s, t, 'or'), cond('empty'));
  const got = cond('toQuery', st, {});
  assert.ok(!('preds' in got));
  assert.deepStrictEqual(got.or, [
    { preds: { inc: [{ 詞元: '破壊', 極性: POLAR, 位置: ['效果'] }], ex: [] } },
    { preds: { inc: [], ex: [{ 詞元: 'ドロー', 極性: POLAR, 位置: ['效果'] }] } },
  ]);
});

test('兩區 → 引擎查詢:片段順序是左側條件再動作標籤,AND 區的述詞留在主查詢', () => {
  const base = cond('add', cond('add', cond('empty'), tagAt('破壊')), tagAt('ドロー'), 'or');
  const got = cond('toQuery', moveSide(base, 'text'), { text: '墓地' });
  assert.deepStrictEqual(got.preds.inc.map(p => p.詞元), ['破壊']);
  assert.deepStrictEqual(got.or.map(f => Object.keys(f)), [['text'], ['preds']]);
  assert.ok(!('text' in got));
});

test('兩區 → 引擎查詢:效果文、卡名換到 OR 區時 textMat、nameLang 留在主查詢', () => {
  const q = { name: '龍', nameLang: 'ja', text: '墓地', textMat: 1 };
  assert.deepStrictEqual(cond('toQuery', moveSide(cond('empty'), 'name', 'text'), q), {
    nameLang: 'ja', textMat: 1,
    or: [{ name: '龍' }, { text: '墓地' }],
  });
});

test('兩區 → 引擎查詢:子類型換到 OR 區,帶著的大類一起走,另一個大類留下', () => {
  const q = { cat: { m: 1, s: 1 }, sub: { 'm:xyz': 1 } };
  assert.deepStrictEqual(cond('toQuery', moveSide(cond('empty'), 'sub:m'), q), {
    cat: { s: 1 },
    or: [{ sub: { 'm:xyz': 1 }, cat: { m: 1 } }],
  });
});

test('兩區 → 引擎查詢:OR 區沒有對應標籤的鍵不算,不送空片段', () => {
  const st = moveSide(cond('empty'), 'atk', 'cat');
  assert.deepStrictEqual(cond('toQuery', st, { text: 'x' }), { text: 'x' });
  assert.deepStrictEqual(cond('toQuery', st, { cat: { m: 1 }, sub: { 'm:xyz': 1 } }),
                         { cat: { m: 1 }, sub: { 'm:xyz': 1 } });
});

test('兩區 → 引擎:ATK 2000 以上或光屬性,大類留在 AND', () => {
  const q = { cat: { m: 1 }, atk: { min: 2000, max: null }, attr: { light: 1 } };
  const st = moveSide(liveCond('empty'), 'atk', 'attr');
  assert.deepStrictEqual(harness.ids(live, liveCond('toQuery', st, q)), [1, 2, 3]);
});

test('兩區 → 引擎:同樣的條件全在 AND 時是交集', () => {
  const q = { cat: { m: 1 }, atk: { min: 2000, max: null }, attr: { light: 1 } };
  assert.deepStrictEqual(harness.ids(live, liveCond('toQuery', liveCond('empty'), q)), [1]);
});

/* ── 狀態 ── */

test('狀態:新標籤預設進 AND;tags 是 AND 再 OR,tagsIn 各區', () => {
  const st = cond('add', cond('add', cond('empty'), tagAt('破壊'), 'or'), tagAt('ドロー'));
  assert.deepStrictEqual(cond('tags', st).map(t => t.origin), ['ドロー', '破壊']);
  assert.deepStrictEqual(cond('tagsIn', st, 'and').map(t => t.origin), ['ドロー']);
  assert.deepStrictEqual(cond('tagsIn', st, 'or').map(t => t.origin), ['破壊']);
});

test('狀態:moveAt 用 tags 的編號換區,接在那一區最後;已在那區就原樣', () => {
  const st = [tagAt('破壊'), tagAt('ドロー')].reduce((s, t) => cond('add', s, t), cond('empty'));
  const moved = cond('moveAt', st, 0, 'or');
  assert.deepStrictEqual(cond('tagsIn', moved, 'and').map(t => t.origin), ['ドロー']);
  assert.deepStrictEqual(cond('tagsIn', moved, 'or').map(t => t.origin), ['破壊']);
  assert.deepStrictEqual(cond('moveAt', moved, 1, 'and').and.map(t => t.origin), ['ドロー', '破壊']);
  assert.deepStrictEqual(cond('moveAt', moved, 1, 'or'), moved);
  assert.deepStrictEqual(cond('moveAt', st, 9, 'or'), st);
});

test('狀態:removeAt 跨兩區編號', () => {
  const st = cond('add', cond('add', cond('empty'), tagAt('破壊')), tagAt('ドロー'), 'or');
  assert.deepStrictEqual(cond('tags', cond('removeAt', st, 1)).map(t => t.origin), ['破壊']);
  assert.deepStrictEqual(cond('tags', cond('removeAt', st, 0)).map(t => t.origin), ['ドロー']);
  assert.deepStrictEqual(cond('tagsIn', cond('removeAt', st, 0), 'or').map(t => t.origin), ['ドロー']);
});

test('狀態:同一張標籤已在另一區也不重複;已用路徑兩區都算', () => {
  const st = cond('add', cond('empty'), tagAt('破壊'), 'or');
  assert.deepStrictEqual(cond('add', st, tagAt('破壊')), st);
  assert.deepStrictEqual(cond('usedPaths', st), ['破壊']);
});

test('狀態:左側條件的區由鍵記,換回 AND 就拿掉', () => {
  const st = cond('moveSide', cond('empty'), 'atk', 'or');
  assert.strictEqual(cond('sideZone', st, 'atk'), 'or');
  assert.strictEqual(cond('sideZone', st, 'text'), 'and');
  assert.strictEqual(cond('sideZone', cond('moveSide', st, 'atk', 'and'), 'atk'), 'and');
  assert.deepStrictEqual(cond('moveSide', st, 'atk', 'or'), st);
});

test('狀態:左側條件清掉後 syncSide 忘記它的區,再選一次回 AND;順序跟著標籤順序', () => {
  const st = cond('moveSide', cond('moveSide', cond('empty'), 'atk', 'or'), 'attr', 'or');
  const q = { atk: { min: 1, max: null }, attr: { light: 1 } };
  assert.deepStrictEqual(cond('syncSide', st, q).orSide, ['attr', 'atk']);
  const gone = cond('syncSide', st, { attr: { light: 1 } });
  assert.strictEqual(cond('sideZone', gone, 'atk'), 'and');
  assert.strictEqual(cond('sideZone', gone, 'attr'), 'or');
});

test('狀態:isEmpty 看兩區與 OR 區的左側條件', () => {
  assert.strictEqual(cond('isEmpty', cond('empty')), true);
  assert.strictEqual(cond('isEmpty', cond('add', cond('empty'), tagAt('破壊'), 'or')), false);
  assert.strictEqual(cond('isEmpty', cond('moveSide', cond('empty'), 'atk', 'or')), false);
});

/* ── 網址 ── */

const EMPTY_Q = { name: '', nameLang: 'zh', code: '', text: '' };
const DOM_SORT = { key: 'dom', dir: '' };
const hashOf = (st, extra) => harness.hash(box, { q: { ...EMPTY_Q, ...extra }, cond: st, sort: DOM_SORT });
const parsed = str => harness.parseHash(box, str);
const enc = encodeURIComponent;
/* 兩區都有同一張的狀態:目錄點列(Cond.add)做不出來,只有換區、改標籤、開網址會走到。 */
const inZones = (fn, and, or) => {
  const put = zone => (st, tag) => fn('addInZone', st, tag, zone);
  return or.reduce(put('or'), and.reduce(put('and'), fn('empty')));
};

test('網址:OR 區動作標籤寫 actOr,路徑與排除同 act', () => {
  const st = cond('add', cond('add', cond('add', cond('empty'), tagAt('対象とする')),
                              tagAt('破壊'), 'or'), tagAt('ドロー', true), 'or');
  assert.strictEqual(hashOf(st), `act=${enc('対象とする')}&actOr=${enc('破壊')},-${enc('ドロー')}`);
  assert.deepStrictEqual(parsed(hashOf(st)).cond, st);
});

test('網址:or 列出 OR 區的左側條件鍵,既有左側參數不變', () => {
  const extra = { cat: { m: 1 }, sub: { 'm:xyz': 1 }, atk: { min: 2000, max: null }, text: '墓地' };
  const st = cond('moveSide', cond('moveSide', cond('moveSide', cond('empty'),
    'text', 'or'), 'atk', 'or'), 'sub:m', 'or');
  const h = hashOf(st, extra);
  assert.strictEqual(h, `text=${enc('墓地')}&cat=m&sub=m:xyz&or=text,sub:m,atk&atk=2000-`);
  const back = parsed(h);
  assert.strictEqual(back.q.text, '墓地');
  assert.deepStrictEqual(back.q.atk, { min: 2000, max: null });
  assert.deepStrictEqual(back.cond.orSide, ['text', 'sub:m', 'atk']);
  assert.deepStrictEqual(cond('toQuery', back.cond, back.q).or.length, 3);
});

test('網址:or 的未知鍵與沒有對應條件的鍵忽略,其餘照常', () => {
  const back = parsed('atk=2000-&or=atk,nope,text,sub:m');
  assert.deepStrictEqual(back.cond.orSide, ['atk']);
  assert.ok(!('cond' in parsed('text=x&or=nope,atk')));
  assert.strictEqual(harness.canonHash(box, 'text=x&or=nope,atk'), 'text=x');
});

test('網址:選了子類型時 or=cat 對不到標籤,忽略', () => {
  const back = parsed('cat=m&sub=m:xyz&or=cat');
  assert.ok(!('cond' in back));
});

test('網址:or 的順序與寫在哪一段都不影響;canon 冪等', () => {
  const raw = `or=atk,text&text=a&atk=1-`;
  const once = harness.canonHash(box, raw);
  assert.strictEqual(once, 'text=a&or=text,atk&atk=1-');
  assert.strictEqual(harness.canonHash(box, once), once);
  assert.deepStrictEqual(parsed(raw).cond, parsed(once).cond);
});

test('網址:同一張標籤同時寫在 act 與 actOr,兩區都留(Story 28);canon 冪等', () => {
  const raw = `actOr=${enc('破壊')}&act=${enc('破壊')}`;
  const back = parsed(raw);
  assert.deepStrictEqual(cond('tagsIn', back.cond, 'and').map(t => t.origin), ['破壊']);
  assert.deepStrictEqual(cond('tagsIn', back.cond, 'or').map(t => t.origin), ['破壊']);
  const once = harness.canonHash(box, raw);
  assert.strictEqual(once, `act=${enc('破壊')}&actOr=${enc('破壊')}`);
  assert.strictEqual(harness.canonHash(box, once), once);
});

test('網址:AND 有 A、OR 有 A 與 B,往返後標籤與兩區不變(Story 28)', () => {
  const a = tagAt('破壊'), b = tagAt('ドロー');
  const st = inZones(cond, [a], [a, b]);
  const h = hashOf(st);
  assert.strictEqual(h, `act=${enc('破壊')}&actOr=${enc('破壊')},${enc('ドロー')}`);
  assert.deepStrictEqual(parsed(h).cond, st);
  assert.deepStrictEqual(cond('toQuery', parsed(h).cond, {}), cond('toQuery', st, {}));
});

test('網址:同一區內重複收成一張,包含與排除是兩張', () => {
  const raw = `act=${enc('破壊')},${enc('破壊')},-${enc('破壊')}&actOr=${enc('ドロー')},${enc('ドロー')}`;
  const once = harness.canonHash(box, raw);
  assert.strictEqual(once, `act=${enc('破壊')},-${enc('破壊')}&actOr=${enc('ドロー')}`);
  assert.strictEqual(harness.canonHash(box, once), once);
  const a = tagAt('破壊');
  const twice = cond('moveAt', inZones(cond, [a], [a]), 1, 'and');
  assert.strictEqual(cond('tags', twice).length, 2);
  assert.strictEqual(hashOf(twice), `act=${enc('破壊')}`);
});

test('目錄點列的規則不變:標籤已在另一區,再點不多一張,網址的規則不影響它', () => {
  const st = cond('add', cond('empty'), tagAt('破壊'), 'or');
  assert.deepStrictEqual(cond('add', st, tagAt('破壊'), 'and'), st);
  assert.deepStrictEqual(cond('add', cond('add', cond('empty'), tagAt('破壊')), tagAt('破壊'), 'or'),
                         cond('add', cond('empty'), tagAt('破壊')));
});

test('網址:actOr 的未知路徑、壞百分比安靜忽略,全部壞掉就沒有 cond', () => {
  const back = parsed(`actOr=%E0%A4%A,${enc('不存在')},-${enc('破壊')}&text=abc`);
  assert.deepStrictEqual(cond('tags', back.cond).map(t => [t.origin, t.ex]), [['破壊', true]]);
  assert.ok(!('cond' in parsed(`actOr=${enc('不存在')}`)));
});

test('網址:轉傳弄壞的段分隔符認得 actOr、or(PARAM_NAMES 有這兩個)', () => {
  const back = parsed(`text=a%26or=text%26actOr=${enc('破壊')}`);
  assert.strictEqual(back.q.text, 'a');
  assert.deepStrictEqual(back.cond.orSide, ['text']);
  assert.deepStrictEqual(cond('tagsIn', back.cond, 'or').map(t => t.origin), ['破壊']);
});

test('網址:OR 區往返後引擎查詢相同', () => {
  const extra = { cat: { m: 1 }, atk: { min: 2000, max: null }, attr: { light: 1 } };
  const st = cond('moveSide', cond('add', cond('empty'), tagAt('破壊'), 'or'), 'attr', 'or');
  const back = parsed(hashOf(st, extra));
  assert.deepStrictEqual(cond('toQuery', back.cond, back.q).or,
                         cond('toQuery', st, { ...EMPTY_Q, ...extra }).or);
});

test('句尾短句:OR 區的動作標籤接在 AND 區後面,序號跨片段對得上', () => {
  const st = cond('add', cond('add', cond('add', cond('empty'), tagAt('破壊', true)),
                              tagAt('対象とする')), tagAt('ドロー'), 'or');
  const q = cond('toQuery', cond('moveSide', st, 'text', 'or'), { text: '墓地' });
  assert.deepStrictEqual(cond('hitLabels', q), ['対象とする', 'ドロー']);
});

/* ── 全語料:使用者貼網址走的路 ── */

const data = harness.realData();
const real = data && harness.load(data);
const fromUrl = str => {
  const st = harness.parseHash(real, str);
  return harness.ids(real, harness.cond(real, 'toQuery', st.cond || harness.cond(real, 'empty'), st.q));
};
const sorted = list => list.slice().sort((a, b) => a - b);

test('全語料:從墓地或從除外特殊召喚(Story 18)等於兩張各自的聯集', t => {
  if (!data) { t.skip('沒有 web/data.js,請先跑 script/web/build_index.py'); return; }
  const [grave, banish] = ['特殊召喚←墓地', '特殊召喚←除外'].map(n => enc(`召喚›特殊召喚›${n}`));
  const both = fromUrl(`actOr=${grave},${banish}`);
  const one = fromUrl(`act=${grave}`), other = fromUrl(`act=${banish}`);
  assert.strictEqual(one.length, 1228);
  assert.strictEqual(other.length, 195);
  assert.ok(both.length > one.length && both.length < one.length + other.length);
  assert.deepStrictEqual(sorted(both), sorted(Array.from(new Set(one.concat(other)))));
});

test('全語料:ATK 2000 以上或光屬性(Story 19),大類在 AND', t => {
  if (!data) { t.skip('沒有 web/data.js,請先跑 script/web/build_index.py'); return; }
  const both = fromUrl('cat=m&attr=light&atk=2000-&or=atk,attr');
  const one = fromUrl('cat=m&atk=2000-'), other = fromUrl('cat=m&attr=light');
  const inter = fromUrl('cat=m&atk=2000-&attr=light');
  assert.ok(inter.length > 0);
  assert.strictEqual(both.length, one.length + other.length - inter.length);
  assert.deepStrictEqual(sorted(both), sorted(Array.from(new Set(one.concat(other)))));
});

test('全語料:AND 有 破壊、OR 有 破壊 與 アップ:レベル,重開網址張數不變(Story 28,審查重現 1618 張)', t => {
  if (!data) { t.skip('沒有 web/data.js,請先跑 script/web/build_index.py'); return; }
  const rcond = (fn, ...args) => harness.cond(real, fn, ...args);
  const rows = data.vocab.catalog.filter(row => row.predicate);
  const pathOf = name => rows.find(row => row.name === name).path.join('›');
  const a = rcond('tagAt', pathOf('破壊'), false), b = rcond('tagAt', pathOf('アップ:レベル'), false);
  const st = inZones(rcond, [a], [a, b]);
  assert.strictEqual(harness.ids(real, rcond('toQuery', st, {})).length, 1618);
  const h = harness.hash(real, { cond: st });
  assert.strictEqual(fromUrl(h).length, 1618);
  assert.strictEqual(fromUrl(`act=${enc(pathOf('破壊'))}&actOr=${enc(pathOf('破壊'))},${enc(pathOf('アップ:レベル'))}`).length, 1618);
});

test('全語料:每個具名查詢同時在 AND 與 OR 區(OR 區多一張下一列),往返後標籤、兩區、張數相同', t => {
  if (!data) { t.skip('沒有 web/data.js,請先跑 script/web/build_index.py'); return; }
  const rcond = (fn, ...args) => harness.cond(real, fn, ...args);
  const rows = data.vocab.catalog.filter(row => row.predicate);
  const wrong = [];
  rows.forEach((row, i) => {
    const a = rcond('tagAt', row.path.join('›'), false);
    const b = rcond('tagAt', rows[(i + 1) % rows.length].path.join('›'), false);
    const st = inZones(rcond, [a], [a, b]);
    const h = harness.hash(real, { cond: st });
    const back = harness.parseHash(real, h).cond;
    const same = JSON.stringify(back) === JSON.stringify(st) && harness.canonHash(real, h) === h &&
      fromUrl(h).length === harness.ids(real, rcond('toQuery', st, {})).length;
    if (!same) wrong.push(row.name);
  });
  assert.deepStrictEqual(wrong, []);
});
