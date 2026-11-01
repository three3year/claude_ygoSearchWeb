/**
 * predicate.test.js — 述詞評估器(`Engine.runQuery` 的 `q.preds`)的測試
 * (predicate-index 票 03;規格 Testing Decisions)
 *
 * 跑法:`node --test script/web/predicate.test.js`
 *
 * 三段:編碼夾具(參考評估器的 96 例、3 雜湊、小語料張數,由 encode_fixture.py 產生)、合成資料的 runQuery 例子、
 * 真 data.js 對真匯出檔的全語料對照。都只走 runQuery,不斷言編碼內部。
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
const COVERED = [DESTROY_AND_DRAW, DESTROY_ONLY, DISCARD_ONLY, NO_FRAMES];

test('包含述詞:命中框所在的句是命中句', () => {
  assert.deepStrictEqual(harness.search(box, include(HAS_DESTROY)),
                         [{ id: DESTROY_AND_DRAW, rows: [0] }, { id: DESTROY_ONLY, rows: [1] }]);
});

test('包含述詞之間是卡層 AND,可跨句,命中句是聯集', () => {
  assert.deepStrictEqual(harness.search(box, include(HAS_DESTROY, HAS_DRAW)),
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
