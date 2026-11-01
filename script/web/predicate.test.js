/**
 * predicate.test.js — 述詞評估器(`Engine.runQuery` 的 `q.preds`)的測試
 * (predicate-index 票 03、04;規格 Testing Decisions)
 *
 * 跑法:`node --test script/web/predicate.test.js`
 *
 * 三段:編碼夾具(參考評估器的 96 例、3 雜湊、小語料張數,由 encode_fixture.py 產生)、合成資料的 runQuery 例子
 * (卡層、句層條件、領起句、hits、marks、與舊 q.act 並用)、真 data.js 對真匯出檔的全語料對照。都只走 runQuery,
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
const POSITIONS = ['代價', '效果', '條件'];

/* 卡集合雜湊:規格同 predicate.cards_hash。雜湊不進瀏覽器,只有對照要用,所以在測試裡。 */
function cardsHash(ids) {
  const sorted = Array.from(ids).sort((a, b) => a - b);
  return crypto.createHash('sha1').update(sorted.join(',')).digest('hex').slice(0, 16);
}

const include = (...preds) => ({ preds: { inc: preds } });

test('夾具 96 例:一例包成一張一句一框的卡,命中與否同參考評估器', () => {
  const frames = [], cards = [];
  FIXTURE.例子.forEach((ex, n) => {
    cards.push({ id: n + 1, tx: ['句'], fr: [[frames.length]] });
    frames.push(FIXTURE.框列[ex.框列]);
  });
  const box = harness.load({ cards, frames, vocab: { frame: FIXTURE.vocab } });
  assert.strictEqual(FIXTURE.例子.length, 96);
  const wrong = FIXTURE.例子.filter((ex, n) =>
    harness.ids(box, include(ex.述詞)).includes(n + 1) !== ex.命中).map(ex => ex.名);
  assert.deepStrictEqual(wrong, []);
});

test('夾具 3 雜湊:卡集合雜湊的算法同參考評估器', () => {
  assert.strictEqual(FIXTURE.雜湊.length, 3);
  for (const ex of FIXTURE.雜湊) assert.strictEqual(cardsHash(ex.卡), ex.雜湊, ex.名);
});

test('夾具小語料:每個述詞三個位置的卡與雜湊同參考評估器', () => {
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

/* ── 舊 q.act 系列過渡期照舊(票 04):與述詞並用時兩者都要過,各自只看通過句層條件的句。 ── */
const ACT_NODE = '破壊';
const ACT_ON_FIRST = 31, ACT_ONLY = 32, PRED_ONLY = 33, ACT_ON_OTHER_KIND = 34;
const actBox = harness.load({
  frames: FRAMES,
  vocab: { frame: FIXTURE.vocab, acat: { leaves: ['破壊'], covered: 4, tree: [[ACT_NODE, 0, []]] } },
  cards: [
    { id: ACT_ON_FIRST, tx: ['一', '二'], k: ['a', 'a'], ae: [[0], []], fr: [[], [DRAW]] },
    { id: ACT_ONLY, tx: ['一'], k: ['a'], ae: [[0]], fr: [[DESTROY]] },
    { id: PRED_ONLY, tx: ['一'], k: ['a'], ae: [[]], fr: [[DRAW]] },
    { id: ACT_ON_OTHER_KIND, tx: ['一', '二'], k: ['a', 'b'], ae: [[], [0]], fr: [[DRAW], []] },
  ],
});

test('述詞與舊 q.act 並用時兩者都要過', () => {
  assert.deepStrictEqual(harness.ids(actBox, { act: { [ACT_NODE]: 1 } }),
                         [ACT_ON_FIRST, ACT_ONLY, ACT_ON_OTHER_KIND]);
  assert.deepStrictEqual(harness.ids(actBox, include(HAS_DRAW)), [ACT_ON_FIRST, PRED_ONLY, ACT_ON_OTHER_KIND]);
  assert.deepStrictEqual(harness.ids(actBox, { act: { [ACT_NODE]: 1 }, ...include(HAS_DRAW) }),
                         [ACT_ON_FIRST, ACT_ON_OTHER_KIND]);
});

test('述詞與舊 q.act 並用:命中句是兩者的聯集,只因舊軸命中的句 hits 是空清單', () => {
  const [hit] = harness.search(actBox, { act: { [ACT_NODE]: 1 }, ...include(HAS_DRAW) });
  assert.deepStrictEqual(hit, { id: ACT_ON_FIRST, rows: [0, 1], hits: [[], [[0, 1, 0]]] });
});

test('述詞與舊 q.act 並用:句層條件對兩者都生效', () => {
  assert.deepStrictEqual(harness.ids(actBox, { kind: KIND_A, act: { [ACT_NODE]: 1 }, ...include(HAS_DRAW) }),
                         [ACT_ON_FIRST]);
});

test('述詞與舊 q.act 並用:marks 兩種都有', () => {
  assert.deepStrictEqual(harness.marks(actBox, { act: { [ACT_NODE]: 1 }, ...include(HAS_DRAW) }).map(m => m.type),
                         ['act', 'pred']);
});

/* ── 全語料:真 data.js + 真匯出檔。大類、中類以底下具名查詢的聯集算(catalog.Catalog.members 的語意)。 ── */
test('全語料:目錄每列 × 三個位置,張數與雜湊同匯出檔', t => {
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
