/**
 * predicate.test.js — 述詞評估器(`Engine.runQuery` 的 `q.preds`、`q.or`)的測試
 * (predicate-index 票 03、04、predicate-ui 票 01;規格 Testing Decisions)
 *
 * 跑法:`node --test script/web/predicate.test.js`
 *
 * 三段:編碼夾具(參考評估器的例子、雜湊、小語料張數,由 encode_fixture.py 產生)、合成資料的 runQuery 例子
 * (卡層、句層條件、領起句、hits、marks、OR 區)、真 data.js 對真匯出檔的全語料對照。都只走 runQuery,
 * 不斷言編碼內部。
 */
'use strict';

const test = require('node:test');
const assert = require('node:assert');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const harness = require('./frontend_harness.js');

const FIXTURE = JSON.parse(fs.readFileSync(path.join(__dirname, 'predicate-fixture-encoded.json'), 'utf8'));
const POSITIONS = ['代價', '效果', '條件', '召喚手續'];

/* 卡集合雜湊:規格同 predicate.cards_hash。雜湊不進瀏覽器,只有對照要用,所以在測試裡。 */
function cardsHash(ids) {
  const sorted = Array.from(ids).sort((a, b) => a - b);
  return crypto.createHash('sha1').update(sorted.join(',')).digest('hex').slice(0, 16);
}

const include = (...preds) => ({ preds: { inc: preds } });

test('夾具例子:一例包成一張一句一框的卡,命中與否同參考評估器', () => {
  const frames = [], cards = [];
  FIXTURE.例子.forEach((ex, n) => {
    cards.push({ id: n + 1, tx: ['句'], fr: [[frames.length]] });
    frames.push(FIXTURE.框列[ex.框列]);
  });
  const box = harness.load({ cards, frames, vocab: { frame: FIXTURE.vocab } });
  assert.ok(FIXTURE.例子.length > 0);
  const wrong = FIXTURE.例子.filter((ex, n) =>
    harness.ids(box, include(ex.述詞)).includes(n + 1) !== ex.命中).map(ex => ex.名);
  assert.deepStrictEqual(wrong, []);
});

test('夾具雜湊:卡集合雜湊的算法同參考評估器', () => {
  assert.ok(FIXTURE.雜湊.length > 0);
  for (const ex of FIXTURE.雜湊) assert.strictEqual(cardsHash(ex.卡), ex.雜湊, ex.名);
});

test('夾具小語料:每個述詞四個位置的卡與雜湊同參考評估器', () => {
  const frames = [], byCard = new Map();
  for (const line of FIXTURE.張數.句) {
    if (!byCard.has(line.card)) byCard.set(line.card, { id: line.card, tx: [], fr: [] });
    const c = byCard.get(line.card);
    c.tx.push(line.index);
    c.fr.push(line.frames.map(f => frames.push(f) - 1));
  }
  const box = harness.load({ cards: Array.from(byCard.values()), frames, vocab: { frame: FIXTURE.vocab } });
  assert.ok(FIXTURE.張數.例子.length > 0);
  for (const ex of FIXTURE.張數.例子) {
    for (const pos of POSITIONS) {
      const got = harness.ids(box, include({ ...ex.述詞, 位置: pos })).sort((a, b) => a - b);
      assert.deepStrictEqual(got, ex.張數[pos].卡, `${ex.名} @${pos}`);
      assert.strictEqual(cardsHash(got), ex.張數[pos].雜湊, `${ex.名} @${pos}`);
    }
  }
});

/* ── runQuery 例子:框內容借夾具的編碼框列,卡是手寫的 ── */
const DESTROY = 0, DRAW = 1, DISCARD = 2;
const FRAMES = ['破壊@相手フィールド', 'ドロー', '捨てる(代價)'].map(name => FIXTURE.框列[name]);
const HAS_DESTROY = { 詞元: '破壊' }, HAS_DRAW = { 詞元: 'ドロー' }, HAS_DISCARD = { 詞元: '捨てる' };
const DESTROY_AND_DRAW = 1, DESTROY_ONLY = 2, DISCARD_ONLY = 3, NO_FRAMES = 4, OLD_STYLE = 5;
const box = harness.load({
  frames: FRAMES,
  vocab: { frame: FIXTURE.vocab },
  cards: [
    { id: DESTROY_AND_DRAW, tx: ['一', '二', '三'], fr: [[DESTROY], [], [DRAW]] },
    { id: DESTROY_ONLY, tx: ['一', '二'], fr: [[], [DESTROY]] },
    { id: DISCARD_ONLY, tx: ['一'], fr: [[DISCARD]] },
    { id: NO_FRAMES, tx: ['一'], fr: [[]] },
    { id: OLD_STYLE, tx: ['舊式卡文'] },
  ],
});
const ids = q => harness.ids(box, q);
const rowsOnly = q => harness.search(box, q).map(({ id, rows }) => ({ id, rows }));
const COVERED = [DESTROY_AND_DRAW, DESTROY_ONLY, DISCARD_ONLY, NO_FRAMES];

test('包含述詞:命中框所在的句是命中句', () => {
  assert.deepStrictEqual(rowsOnly(include(HAS_DESTROY)),
                         [{ id: DESTROY_AND_DRAW, rows: [0] }, { id: DESTROY_ONLY, rows: [1] }]);
});

test('包含述詞之間是卡層 AND,可跨句,命中句是聯集', () => {
  assert.deepStrictEqual(rowsOnly(include(HAS_DESTROY, HAS_DRAW)),
                         [{ id: DESTROY_AND_DRAW, rows: [0, 2] }]);
});

test('一個包含述詞沒有命中框,整張卡不中', () => {
  assert.deepStrictEqual(ids(include(HAS_DESTROY, HAS_DISCARD)), []);
});

test('排除述詞優先於包含', () => {
  assert.deepStrictEqual(ids({ preds: { inc: [HAS_DESTROY], ex: [HAS_DRAW] } }), [DESTROY_ONLY]);
  assert.deepStrictEqual(ids({ preds: { inc: [HAS_DESTROY], ex: [HAS_DESTROY] } }), []);
});

test('排除述詞看全卡:命中框在哪句都算', () => {
  assert.deepStrictEqual(ids({ preds: { ex: [HAS_DRAW, HAS_DISCARD] } }), [DESTROY_ONLY, NO_FRAMES]);
});

test('只有排除述詞:涵蓋但沒有框的卡照中,命中句沿用其他條件的結果', () => {
  assert.deepStrictEqual(harness.search(box, { preds: { ex: [HAS_DESTROY] } }),
                         [{ id: DISCARD_ONLY, rows: null }, { id: NO_FRAMES, rows: null }]);
});

test('舊式卡文:有任何述詞就不中,沒有述詞不受影響', () => {
  assert.deepStrictEqual(ids(include({})), [DESTROY_AND_DRAW, DESTROY_ONLY, DISCARD_ONLY]);
  assert.deepStrictEqual(ids({ preds: { ex: [{ 詞元: '不在語料的詞元' }] } }), COVERED);
  assert.ok(ids({}).includes(OLD_STYLE));
  assert.ok(ids({ preds: { inc: [], ex: [] } }).includes(OLD_STYLE));
});

test('值不在表內就是不中', () => {
  for (const pred of [{ 詞元: '不在語料的詞元' }, { 位置: '手札' }, { 所在: [[null, '天上']] },
                      { 所在: [['隔壁', '場上']] }, { 受事者中心詞: '不在語料的詞' }, { 修飾語類: '顏色' }]) {
    assert.deepStrictEqual(ids(include(pred)), [], JSON.stringify(pred));
  }
});

test('同欄有一個值不在表內,其他值照常比', () => {
  assert.deepStrictEqual(ids(include({ 詞元: ['不在語料的詞元', '捨てる'] })), [DISCARD_ONLY]);
});

test('不認得的欄丟錯,包含與排除都是', () => {
  for (const field of ['顏色', 'constructor']) {
    assert.throws(() => ids(include({ [field]: 'x' })), /不認得的欄/);
    assert.throws(() => ids({ preds: { ex: [{ [field]: 'x' }] } }), /不認得的欄/);
  }
});

/* ── 句層條件(票 04):包含述詞只算通過效果類型、必發選發、效果文的句;排除看全卡。 ── */
const KIND_A = { a: 1 };
const TWO_KINDS = 11, ACROSS_KINDS = 12, EX_ON_OTHER_KIND = 13, OPT_AND_TEXT = 14;
const clauseBox = harness.load({
  frames: FRAMES,
  vocab: { frame: FIXTURE.vocab },
  cards: [
    { id: TWO_KINDS, tx: ['一', '二'], k: ['a', 'b'], fr: [[DESTROY], [DESTROY]] },
    { id: ACROSS_KINDS, tx: ['一', '二'], k: ['a', 'b'], fr: [[DESTROY], [DRAW]] },
    { id: EX_ON_OTHER_KIND, tx: ['一', '二'], k: ['a', 'b'], fr: [[DESTROY], [DISCARD]] },
    { id: OPT_AND_TEXT, tx: ['甲', '乙'], k: ['c', 'c'], o: ['m', 'o'], fr: [[DESTROY], [DESTROY]] },
  ],
});
const clauseHits = q => harness.search(clauseBox, q);
const rowsOf = (results, id) => (results.find(e => e.id === id) || {}).rows;

test('句層條件縮命中句:同卡兩句,只有通過效果類型的句算', () => {
  const results = clauseHits({ kind: KIND_A, preds: { inc: [HAS_DESTROY] } });
  assert.deepStrictEqual(rowsOf(results, TWO_KINDS), [0]);
});

test('必發選發、效果文也是句層條件', () => {
  assert.deepStrictEqual(rowsOf(clauseHits({ opt: { o: 1 }, preds: { inc: [HAS_DESTROY] } }), OPT_AND_TEXT), [1]);
  assert.deepStrictEqual(rowsOf(clauseHits({ text: '甲', preds: { inc: [HAS_DESTROY] } }), OPT_AND_TEXT), [0]);
});

test('包含述詞的框都不在通過句層條件的句上,卡不中', () => {
  const results = clauseHits({ kind: { b: 1 }, preds: { inc: [{ 詞元: '破壊' }] } });
  assert.deepStrictEqual(results.map(e => e.id), [TWO_KINDS]);
  assert.deepStrictEqual(rowsOf(results, TWO_KINDS), [1]);
});

test('卡層 AND 跨句:其中一個述詞只在沒過句層條件的句上命中,卡不中', () => {
  const pair = { inc: [HAS_DESTROY, HAS_DRAW] };
  assert.deepStrictEqual(rowsOf(clauseHits({ preds: pair }), ACROSS_KINDS), [0, 1]);
  assert.strictEqual(rowsOf(clauseHits({ kind: KIND_A, preds: pair }), ACROSS_KINDS), undefined);
});

test('排除述詞不受句層條件限制:排除的框在沒過句層條件的句上,卡仍不中', () => {
  const results = clauseHits({ kind: KIND_A, preds: { inc: [HAS_DESTROY], ex: [HAS_DISCARD] } });
  assert.strictEqual(rowsOf(results, EX_ON_OTHER_KIND), undefined);
  assert.deepStrictEqual(rowsOf(results, TWO_KINDS), [0]);
});

test('只有排除述詞:命中句沿用其他條件的結果,不帶 hits,marks 沒有 pred', () => {
  const q = { kind: KIND_A, preds: { ex: [HAS_DISCARD] } };
  const results = clauseHits(q);
  assert.deepStrictEqual(results, [{ id: TWO_KINDS, rows: [0] }, { id: ACROSS_KINDS, rows: [0] }]);
  assert.deepStrictEqual(harness.marks(clauseBox, q), [{ type: 'kind' }]);
});

/* ── 領起句(票 04):● 子句評估時也看領起句的框;領起句看不到 ● 子句的框。 ──
   框所在句不等於 rows[k] 就是領起句的框。 */
const LEAD = 21, LEAD_BOTH = 22, PLAIN_ORDER = 23;
const leadBox = harness.load({
  frames: FRAMES,
  vocab: { frame: FIXTURE.vocab },
  cards: [
    { id: LEAD, tx: ['領起', '●一', '●二'], k: ['b', 'a', 'c'], fl: [-1, 0, 0], fr: [[DISCARD], [DRAW], []] },
    { id: LEAD_BOTH, tx: ['領起', '●一'], fl: [-1, 0], fr: [[DESTROY], [DRAW, DESTROY]] },
    { id: PLAIN_ORDER, tx: ['一', '二'], fr: [[], [DRAW, DESTROY]] },
  ],
});
const leadCard = (q, id) => harness.search(leadBox, q).find(e => e.id === id);

test('● 子句通過效果類型、領起句沒通過:領起句的框仍命中,命中句只有該 ● 子句,框所在句是領起句', () => {
  assert.deepStrictEqual(leadCard({ kind: KIND_A, preds: { inc: [HAS_DISCARD] } }, LEAD),
                         { id: LEAD, rows: [1], hits: [[[0, 0, 0]]] });
});

test('領起句通過、● 子句沒通過:命中句只有領起句', () => {
  assert.deepStrictEqual(leadCard({ kind: { b: 1 }, preds: { inc: [HAS_DISCARD] } }, LEAD),
                         { id: LEAD, rows: [0], hits: [[[0, 0, 0]]] });
});

test('沒有句層條件:領起句框命中時,領起句與每個 ● 子句都是命中句', () => {
  assert.deepStrictEqual(leadCard(include(HAS_DISCARD), LEAD),
                         { id: LEAD, rows: [0, 1, 2], hits: [[[0, 0, 0]], [[0, 0, 0]], [[0, 0, 0]]] });
});

test('● 子句自己的框不往上算,也不算給兄弟句', () => {
  assert.deepStrictEqual(leadCard(include(HAS_DRAW), LEAD), { id: LEAD, rows: [1], hits: [[[0, 1, 0]]] });
});

test('● 子句的框與領起句的框同一個述詞都命中:依框所在句、框序號排', () => {
  assert.deepStrictEqual(leadCard(include(HAS_DESTROY), LEAD_BOTH),
                         { id: LEAD_BOTH, rows: [0, 1], hits: [[[0, 0, 0]], [[0, 0, 0], [0, 1, 1]]] });
});

test('hits:述詞序號是 inc 裡的序號,框序號是框所在句 fr 清單的序號,依述詞序排', () => {
  assert.deepStrictEqual(leadCard(include(HAS_DESTROY, HAS_DRAW), PLAIN_ORDER),
                         { id: PLAIN_ORDER, rows: [1], hits: [[[0, 1, 1], [1, 1, 0]]] });
});

test('領起句的框也算進卡層 AND:● 子句過了句層條件,兩個述詞分別靠領起句與自己的框', () => {
  assert.deepStrictEqual(leadCard({ kind: KIND_A, preds: { inc: [HAS_DISCARD, HAS_DRAW] } }, LEAD),
                         { id: LEAD, rows: [1], hits: [[[0, 0, 0], [1, 1, 0]]] });
});

test('排除述詞看全卡,領起句的框在沒過句層條件的句上一樣擋', () => {
  assert.strictEqual(leadCard({ kind: KIND_A, preds: { inc: [HAS_DRAW], ex: [HAS_DISCARD] } }, LEAD), undefined);
});

test('marks:有包含述詞才有 pred,排在其他條件之後', () => {
  assert.deepStrictEqual(harness.marks(leadBox, { kind: KIND_A, preds: { inc: [HAS_DRAW] } }),
                         [{ type: 'kind' }, { type: 'pred' }]);
  assert.deepStrictEqual(harness.marks(leadBox, { preds: { ex: [HAS_DRAW] } }), []);
  assert.deepStrictEqual(harness.marks(leadBox, {}), []);
});

/* ── 舊軸已刪(predicate-ui 票 07):引擎只剩述詞一套。資料還帶舊欄、VOCAB 還帶舊樹,查詢還帶 q.act,都不是條件。 ── */
const staleBox = harness.load({
  frames: FRAMES,
  vocab: { frame: FIXTURE.vocab, acat: { leaves: ['破壊'], covered: 2, tree: [['破壊', 0, []]] } },
  cards: [
    { id: 31, tx: ['一'], k: ['a'], ae: [[0]], fr: [[DESTROY]] },
    { id: 32, tx: ['一'], k: ['a'], ae: [[]], fr: [[DRAW]] },
  ],
});

test('舊的 q.act、actCost、actPat 不是條件:結果與 marks 同沒有條件', () => {
  for (const act of [1, -1]) {
    const q = { act: { 破壊: act }, actCost: 1, actPat: 'self' };
    assert.deepStrictEqual(harness.search(staleBox, q), harness.search(staleBox, {}));
    assert.deepStrictEqual(harness.marks(staleBox, q), []);
  }
});

/* ── OR 區(predicate-ui 票 01):每個片段與主查詢合併成一個分支,卡命中任一分支就中。 ──
   述詞序號是整個查詢的編號:先主查詢的 inc,再依片段順序接各片段的 inc。 */
const exPreds = (...preds) => ({ preds: { ex: preds } });
const MONSTER_DESTROY_DRAW = 41, MONSTER_DESTROY = 42, SPELL_DRAW = 43, SPELL_DISCARD = 44, OLD_MONSTER = 45,
      DESTROY_WITH_DISCARD = 46, DESTROY_TWO_KINDS = 47, NO_ACTION_KIND_AB = 48, MATERIAL_TEXT = 49;
const orBox = harness.load({
  frames: FRAMES,
  vocab: { frame: FIXTURE.vocab },
  cards: [
    { id: MONSTER_DESTROY_DRAW, c: 'm', at: 'L', atk: 2500, tx: ['一', '二'], k: ['a', 'b'], fr: [[DESTROY], [DRAW]] },
    { id: MONSTER_DESTROY, c: 'm', at: 'D', atk: 1000, tx: ['一'], k: ['a'], fr: [[DESTROY]] },
    { id: SPELL_DRAW, c: 's', tx: ['一'], k: ['b'], fr: [[DRAW]] },
    { id: SPELL_DISCARD, c: 's', tx: ['一', '二'], k: ['a', 'b'], fr: [[DISCARD], []] },
    { id: OLD_MONSTER, c: 'm', at: 'D', atk: 3000, nj: '和名', tx: ['舊式卡文'] },
    { id: DESTROY_WITH_DISCARD, c: 's', tx: ['一'], k: ['a'], fr: [[DESTROY, DISCARD]] },
    { id: DESTROY_TWO_KINDS, c: 's', tx: ['一', '二'], k: ['a', 'b'], fr: [[DESTROY], [DESTROY]] },
    { id: NO_ACTION_KIND_AB, c: 's', tx: ['甲', '乙'], k: ['a', 'b'], fr: [[], []] },
    { id: MATERIAL_TEXT, c: 'm', atk: 0, tx: ['素材字', '效果字'], ro: ['mat', ''], fr: [[], []] },
  ],
});
const orSearch = q => harness.search(orBox, q);
const orIds = q => harness.ids(orBox, q);

test('OR:兩個分支聯集,結果依資料順序;命中句與 hits 併起來,序號接著片段順序', () => {
  assert.deepStrictEqual(orSearch({ or: [include(HAS_DRAW), include(HAS_DESTROY)] }), [
    { id: MONSTER_DESTROY_DRAW, rows: [0, 1], hits: [[[1, 0, 0]], [[0, 1, 0]]] },
    { id: MONSTER_DESTROY, rows: [0], hits: [[[1, 0, 0]]] },
    { id: SPELL_DRAW, rows: [0], hits: [[[0, 0, 0]]] },
    { id: DESTROY_WITH_DISCARD, rows: [0], hits: [[[1, 0, 0]]] },
    { id: DESTROY_TWO_KINDS, rows: [0, 1], hits: [[[1, 0, 0]], [[1, 1, 0]]] },
  ]);
});

test('OR:AND 區全部成立,再加 OR 區任一成立', () => {
  assert.deepStrictEqual(orSearch({ ...include(HAS_DESTROY), or: [include(HAS_DRAW), include(HAS_DISCARD)] }), [
    { id: MONSTER_DESTROY_DRAW, rows: [0, 1], hits: [[[0, 0, 0]], [[1, 1, 0]]] },
    { id: DESTROY_WITH_DISCARD, rows: [0], hits: [[[0, 0, 0], [2, 0, 1]]] },
  ]);
});

test('OR:述詞序號跨分支,主查詢多個述詞、片段重複同一個述詞各有各的號', () => {
  const q = { ...include(HAS_DESTROY, HAS_DRAW), or: [include(HAS_DISCARD), include(HAS_DESTROY)] };
  assert.deepStrictEqual(orSearch(q), [
    { id: MONSTER_DESTROY_DRAW, rows: [0, 1], hits: [[[0, 0, 0], [3, 0, 0]], [[1, 1, 0]]] },
  ]);
});

test('OR:排除標籤是一個分支,要卡上沒有 X;排除不佔述詞序號', () => {
  const q = { ...include(HAS_DESTROY), or: [exPreds(HAS_DRAW), include(HAS_DISCARD)] };
  assert.deepStrictEqual(orSearch(q), [
    { id: MONSTER_DESTROY, rows: [0], hits: [[[0, 0, 0]]] },
    { id: DESTROY_WITH_DISCARD, rows: [0], hits: [[[0, 0, 0], [1, 0, 1]]] },
    { id: DESTROY_TWO_KINDS, rows: [0, 1], hits: [[[0, 0, 0]], [[0, 1, 0]]] },
  ]);
});

test('OR:全是排除分支時命中句是 null,marks 沒有 pred;同時有兩者的卡與舊式卡文不中', () => {
  const q = { or: [exPreds(HAS_DESTROY), exPreds(HAS_DRAW)] };
  assert.deepStrictEqual(orSearch(q), [MONSTER_DESTROY, SPELL_DRAW, SPELL_DISCARD, DESTROY_WITH_DISCARD,
    DESTROY_TWO_KINDS, NO_ACTION_KIND_AB, MATERIAL_TEXT].map(id => ({ id, rows: null })));
  assert.deepStrictEqual(harness.marks(orBox, q), []);
});

test('OR:左側條件在 OR 區,舊式卡文只要過左側條件也中', () => {
  assert.deepStrictEqual(orSearch({ or: [{ atk: { min: 2000 } }, { attr: { D: 1 } }] }),
                         [MONSTER_DESTROY_DRAW, MONSTER_DESTROY, OLD_MONSTER].map(id => ({ id, rows: null })));
  assert.deepStrictEqual(orIds({ cat: { m: 1 }, or: [{ atk: { max: 1000 } }, { attr: { L: 1 } }] }),
                         [MONSTER_DESTROY_DRAW, MONSTER_DESTROY, MATERIAL_TEXT]);
});

test('OR:左側條件與述詞各一個分支,只因左側條件中的卡命中句是 null', () => {
  assert.deepStrictEqual(orSearch({ or: [{ atk: { min: 3000 } }, include(HAS_DRAW)] }), [
    { id: MONSTER_DESTROY_DRAW, rows: [1], hits: [[[0, 1, 0]]] },
    { id: SPELL_DRAW, rows: [0], hits: [[[0, 0, 0]]] },
    { id: OLD_MONSTER, rows: null },
  ]);
});

test('OR:片段與主查詢有同一個鍵時兩邊都要成立,片段不蓋掉主查詢', () => {
  assert.deepStrictEqual(orIds({ cat: { m: 1 }, or: [{ cat: { s: 1 } }] }), []);
});

test('OR:句層條件在 OR 區,主查詢的述詞也只看過該片段的句', () => {
  assert.deepStrictEqual(orSearch({ ...include(HAS_DESTROY), or: [{ kind: { b: 1 } }] }),
                         [{ id: DESTROY_TWO_KINDS, rows: [1], hits: [[[0, 1, 0]]] }]);
});

test('OR:兩個句層片段,命中句取聯集、排序', () => {
  const results = orSearch({ or: [{ text: '乙' }, { kind: { a: 1 } }] });
  assert.deepStrictEqual(results.find(e => e.id === NO_ACTION_KIND_AB), { id: NO_ACTION_KIND_AB, rows: [0, 1] });
  assert.deepStrictEqual(results.find(e => e.id === SPELL_DISCARD), { id: SPELL_DISCARD, rows: [0] });
  assert.strictEqual(results.find(e => e.id === SPELL_DRAW), undefined);
});

test('OR:效果文、卡名放 OR 區時,比法(素材句、語言)照主查詢', () => {
  assert.deepStrictEqual(orSearch({ or: [{ text: '素材' }] }), []);
  assert.deepStrictEqual(orSearch({ textMat: 1, or: [{ text: '素材' }] }), [{ id: MATERIAL_TEXT, rows: [0] }]);
  assert.deepStrictEqual(orIds({ nameLang: 'ja', or: [{ name: '和名' }] }), [OLD_MONSTER]);
});

test('OR:rows 有 null 的分支時以有句的分支為準,與分支順序無關;全是 null 的卡才是 null', () => {
  const expected = [
    { id: MONSTER_DESTROY_DRAW, rows: [0], hits: [[[0, 0, 0]]] },
    { id: MONSTER_DESTROY, rows: [0], hits: [[[0, 0, 0]]] },
    { id: SPELL_DISCARD, rows: null },
    { id: DESTROY_WITH_DISCARD, rows: [0], hits: [[[0, 0, 0]]] },
    { id: DESTROY_TWO_KINDS, rows: [0, 1], hits: [[[0, 0, 0]], [[0, 1, 0]]] },
    { id: NO_ACTION_KIND_AB, rows: null },
    { id: MATERIAL_TEXT, rows: null },
  ];
  assert.deepStrictEqual(orSearch({ or: [exPreds(HAS_DRAW), include(HAS_DESTROY)] }), expected);
  assert.deepStrictEqual(orSearch({ or: [include(HAS_DESTROY), exPreds(HAS_DRAW)] }), expected);
});

test('OR:兩個分支命中同一框,hits 只留一筆', () => {
  const q = { ...include(HAS_DESTROY), or: [{ text: '一' }, { kind: { a: 1 } }] };
  assert.deepStrictEqual(orSearch(q), [MONSTER_DESTROY_DRAW, MONSTER_DESTROY, DESTROY_WITH_DISCARD, DESTROY_TWO_KINDS]
    .map(id => ({ id, rows: [0], hits: [[[0, 0, 0]]] })));
});

test('OR:同一句帶主查詢與兩個片段的述詞,hits 依序號排、主查詢的框只留一筆', () => {
  const sameLine = harness.load({
    frames: FRAMES,
    vocab: { frame: FIXTURE.vocab },
    cards: [{ id: 1, tx: ['一'], fr: [[DESTROY, DRAW, DISCARD]] }],
  });
  assert.deepStrictEqual(harness.search(sameLine, { ...include(HAS_DESTROY), or: [include(HAS_DRAW), include(HAS_DISCARD)] }),
                         [{ id: 1, rows: [0], hits: [[[0, 0, 0], [1, 0, 1], [2, 0, 2]]] }]);
});

test('OR:只因沒有包含述詞的分支命中的句,hits 是空清單', () => {
  const results = orSearch({ or: [include(HAS_DESTROY), { text: '二' }] });
  assert.deepStrictEqual(results.find(e => e.id === MONSTER_DESTROY_DRAW),
                         { id: MONSTER_DESTROY_DRAW, rows: [0, 1], hits: [[[0, 0, 0]], []] });
});

test('OR:領起句的框跨分支照常併,hits 內依序號、框所在句排', () => {
  assert.deepStrictEqual(leadCard({ or: [include(HAS_DISCARD), include(HAS_DRAW)] }, LEAD),
                         { id: LEAD, rows: [0, 1, 2], hits: [[[0, 0, 0]], [[0, 0, 0], [1, 1, 0]], [[0, 0, 0]]] });
});

test('OR:marks 同種只留一筆,順序與沒有 OR 時相同', () => {
  assert.deepStrictEqual(
    harness.marks(orBox, { or: [{ kind: { a: 1 } }, { kind: { b: 1 } }, { text: '甲' }, { text: '甲' }, include(HAS_DRAW)] }),
    [{ type: 'text', value: '甲' }, { type: 'kind' }, { type: 'pred' }]);
});

test('OR:片段的述詞有不認得的欄一樣丟錯', () => {
  assert.throws(() => orIds({ or: [include({ 顏色: 'x' })] }), /不認得的欄/);
  assert.throws(() => orIds({ or: [exPreds({ constructor: 'x' })] }), /不認得的欄/);
});

test('OR:沒有 q.or 或它是空的,結果與 marks 都相同', () => {
  for (const q of [{}, include(HAS_DESTROY), exPreds(HAS_DESTROY), { kind: KIND_A, ...include(HAS_DRAW) },
                   { text: '一' }, { cat: { m: 1 } }]) {
    const withEmpty = { ...q, or: [] };
    assert.deepStrictEqual(orSearch(withEmpty), orSearch(q), JSON.stringify(q));
    assert.deepStrictEqual(harness.marks(orBox, withEmpty), harness.marks(orBox, q), JSON.stringify(q));
  }
});

test('OR:空片段沒有多的條件,該分支就是主查詢', () => {
  assert.deepStrictEqual(orIds({ cat: { m: 1 }, or: [{}] }),
                         [MONSTER_DESTROY_DRAW, MONSTER_DESTROY, OLD_MONSTER, MATERIAL_TEXT]);
});

/* ── 全語料:真 data.js + 真匯出檔。大類、中類以底下具名查詢的聯集算(catalog.Catalog.members 的語意)。 ── */
test('全語料 OR:每個具名查詢放在單一片段,效果位張數與雜湊同匯出檔;兩片段的卡等於各自查詢的聯集', t => {
  const exportFile = path.join(__dirname, '..', '..', 'data', 'action_frames.json');
  const data = harness.realData();
  if (!data || !fs.existsSync(exportFile)) {
    t.skip('缺 web/data.js 或 data/action_frames.json,略過全語料對照');
    return;
  }
  const named = JSON.parse(fs.readFileSync(exportFile, 'utf8')).目錄.filter(row => row.predicate);
  const real = harness.load(data);
  const inEffect = row => include({ ...row.predicate, 位置: '效果' });
  const wrong = [];
  named.forEach((row, n) => {
    const got = harness.ids(real, { or: [inEffect(row)] });
    if (got.length !== row.cards.效果 || cardsHash(got) !== row.hash.效果) {
      wrong.push(`${row.path.join('/')}:${got.length} 張 ${cardsHash(got)},匯出 ${row.cards.效果} 張 ${row.hash.效果}`);
    }
    if (n % 10) return;  // 成對比對抽樣:單片段已逐列比過,這裡只守聯集,每列都跑要多十幾秒
    const other = named[(n + 1) % named.length];
    const union = new Set([...harness.ids(real, inEffect(row)), ...harness.ids(real, inEffect(other))]);
    const both = harness.ids(real, { or: [inEffect(row), inEffect(other)] });
    if (cardsHash(both) !== cardsHash(union)) wrong.push(`${row.path.join('/')} 或 ${other.path.join('/')}:聯集不同`);
  });
  assert.strictEqual(named.length, 237);
  assert.deepStrictEqual(wrong, []);
});

test('全語料:目錄每列 × 四個位置,張數與雜湊同匯出檔', t => {
  const exportFile = path.join(__dirname, '..', '..', 'data', 'action_frames.json');
  const data = harness.realData();
  if (!data || !fs.existsSync(exportFile)) {
    t.skip('缺 web/data.js 或 data/action_frames.json,略過全語料對照');
    return;
  }
  const catalog = JSON.parse(fs.readFileSync(exportFile, 'utf8')).目錄;
  const real = harness.load(data);
  const named = catalog.filter(row => row.predicate);
  const hitsOf = new Map(named.map(row => [row, Object.fromEntries(POSITIONS.map(pos =>
    [pos, harness.ids(real, include({ ...row.predicate, 位置: pos }))]))]));
  const under = (row, other) => row.path.every((step, n) => other.path[n] === step);
  const wrong = [];
  for (const row of catalog) {
    const sources = row.predicate ? [row] : named.filter(other => under(row, other));
    for (const pos of POSITIONS) {
      const got = new Set(sources.flatMap(source => hitsOf.get(source)[pos]));
      if (got.size !== row.cards[pos] || cardsHash(got) !== row.hash[pos]) {
        wrong.push(`${row.path.join('/')} @${pos}:${got.size} 張 ${cardsHash(got)},匯出 ${row.cards[pos]} 張 ${row.hash[pos]}`);
      }
    }
  }
  assert.strictEqual(catalog.length, 261);
  assert.deepStrictEqual(wrong, []);
});

/* summon-procedure 票 02:召喚條件的手續步驟以位置 召喚手續 進索引。毀滅的黑魔術師(59400890)的除外寫在召喚條件
   (效果外文本第二句),只有位置帶 召喚手續 的述詞命中它。 */
test('真 data.js:除外、位置 召喚手續 命中毀滅的黑魔術師的召喚條件句;位置 效果 不中', t => {
  const data = harness.realData();
  if (!data) {
    t.skip('缺 web/data.js,略過全語料對照');
    return;
  }
  const real = harness.load(data);
  const DARK_MAGICIAN = 59400890;
  const card = Array.from(data.cards).find(c => c.id === DARK_MAGICIAN);
  const hit = harness.search(real, include({ 詞元: '除外', 位置: ['召喚手續'] })).find(e => e.id === DARK_MAGICIAN);
  assert.ok(hit, '除外@召喚手續 沒命中 59400890');
  assert.deepStrictEqual(hit.rows.map(row => card.tx[row].includes('除外，可以從額外牌組特殊召喚')), [true]);
  assert.ok(!harness.ids(real, include({ 詞元: '除外', 位置: ['效果'] })).includes(DARK_MAGICIAN));
});

/* 規格 4 票 02:具名查詢走使用者的入口——葉路徑 → Hash.parse → 條件模型 → runQuery。
   效果位 0 張的兩個查詢帶的位置是規格裁定,寫死在這裡,不用條件模型自己的規則算。 */
test('真 data.js:舊欄、VOCAB.acat、META.acat_digest 都不在,舊匯出檔不是來源', t => {
  const data = harness.realData();
  if (!data) {
    t.skip('缺 web/data.js,略過全語料對照');
    return;
  }
  const OLD = ['ae', 'ac', 'aes', 'aen', 'acs', 'acn'];
  assert.deepStrictEqual(Array.from(data.cards).filter(c => OLD.some(field => field in c)).map(c => c.id), []);
  assert.ok(!('acat' in data.vocab));
  assert.ok(!('acat_digest' in data.meta));
  assert.deepStrictEqual(Object.keys(data.meta.sources).sort(), ['action_frames.json', 'cards.json', 'tag_cards.json']);
});

test('全語料:237 個具名查詢經網址與條件模型,張數等於目錄裡該標籤所帶位置的張數', t => {
  const data = harness.realData();
  if (!data) {
    t.skip('缺 web/data.js,略過全語料對照');
    return;
  }
  const NOT_EFFECT = { 対象とする: '條件', '取り除く@お互いのフィールド': '代價' };
  const real = harness.load(data);
  const named = data.vocab.catalog.filter(row => row.predicate);
  const wrong = [];
  for (const row of named) {
    const state = harness.parseHash(real, 'act=' + encodeURIComponent(row.path.join('›')));
    const q = harness.cond(real, 'toQuery', state.cond, state.q);
    const pos = NOT_EFFECT[row.name] || '效果';
    const got = harness.ids(real, q).length;
    if (got !== row.cards[pos]) wrong.push(`${row.name} @${pos}:${got} 張,目錄 ${row.cards[pos]} 張`);
  }
  assert.strictEqual(named.length, 237);
  assert.deepStrictEqual(wrong, []);
});
