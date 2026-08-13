/**
 * test_engine.js — 接縫 3(前端查詢引擎)的測試
 *
 * 跑法:`node --test script/web/`
 *
 * 用 node 內建能力(`node:test` + `node:vm`),零 npm 依賴、不進 `package.json`
 * ——專案維持零安裝,任何人 clone 下來不裝東西就能驗證(零建置協定,ADR-0007)。
 *
 * 餵的是**合成資料集**(數十張卡,涵蓋各種邊界),跑的是 `web/` 底下真實的前端
 * 程式碼:先例是 oldProject 的 `scripts/audit/frontend_parity.js`。
 *
 * 測的是接縫的外部行為——條件進去、命中的卡片密碼與效果句索引出來。不斷言 DOM
 * 結構、不斷言 CSS class 名稱(那些是實作細節,重構就會壞而且壞得沒有意義)。
 */
'use strict';

const test = require('node:test');
const assert = require('node:assert');
const harness = require('./frontend_harness.js');

/* ── 合成資料集 ────────────────────────────────────────────
   欄位形狀與 `web/data.js` 一致:空值省略而不是寫 null,值一律短碼。 */

const CARDS = [
  {
    id: 46986414, al: [46986430, 36996508],
    n: '黑魔導', nj: 'ブラック・マジシャン', ne: 'Dark Magician',
    c: 'm', s: ['normal'], at: 'dark', r: 'spellcaster', lv: 7,
    atk: 2500, df: 2100,
    d: '究極的攻擊魔術師。',
  },
  {
    id: 89631139,
    n: '青眼白龍', nj: '青眼の白龍', ne: 'Blue-Eyes White Dragon',
    c: 'm', s: ['normal'], at: 'light', r: 'dragon', lv: 8,
    atk: 3000, df: 2500,
    d: '以高攻擊力著稱的傳說之龍。',
  },
  {
    id: 23995346,
    n: '青眼究極龍', nj: '青眼の究極竜', ne: 'Blue-Eyes Ultimate Dragon',
    c: 'm', s: ['fusion'], at: 'light', r: 'dragon', lv: 12,
    atk: 4500, df: 3800,
    tx: ['「青眼白龍」＋「青眼白龍」＋「青眼白龍」'],
    k: ['x'], ro: ['mat'],
  },
  {
    id: 2511,
    n: '拉比麗斯的狂時鐘', nj: '白銀の城の狂時計', ne: 'Labrynth Cooclock',
    ax: '白銀之城的狂時鐘',
    c: 'm', s: ['effect'], at: 'dark', r: 'fiend', lv: 1, atk: 0, df: 0,
    tx: ['這個卡名的①②效果1回合各能使用1次。', '①：將此卡從手牌捨棄可以發動。'],
    k: ['x', 'q'], ro: ['limit', ''],
  },
  {
    id: 84013237,
    n: 'No.39 希望皇 霍普', nj: 'No.39 希望皇ホープ', ne: 'Number 39: Utopia',
    c: 'm', s: ['xyz'], at: 'light', r: 'warrior', lv: 4, atk: 2500, df: 2000,
    tx: ['等級4怪獸×2'],
    k: ['x'], ro: ['mat'],
  },
  {
    id: 483,
    n: '平行瞬移', nj: 'パラレル・テレポート', ne: 'Parallel Teleport',
    c: 's', s: ['quick'],
    tx: ['這個卡名的卡在1回合只能發動1張。'],
    k: ['x'], ro: ['limit'],
  },
  // 只有中文卡名的卡(日/英欄位缺席):語言切換不得因此爆掉
  { id: 10000, n: '無名的試作卡', c: 't', s: ['normal'], tx: ['①：什麼都不做。'], k: ['tn'] },
];

const VOCAB = {
  cat: { zh: '大類', items: [{ code: 'm', zh: '怪獸' }, { code: 's', zh: '魔法' },
                             { code: 't', zh: '陷阱' }] },
  kind: { zh: '效果類型', items: [{ code: 'x', zh: '效果外文本' }, { code: 'q', zh: '誘發即時效果(2速)' },
                                  { code: 'tn', zh: '通常陷阱卡效果' }] },
  role: { zh: 'role', items: [{ code: 'mat', zh: '素材指定' }, { code: 'limit', zh: '使用次數限制' }] },
};

const META = {
  cards: CARDS.length,
  clauses: CARDS.reduce((n, c) => n + (c.tx || []).length, 0),
};

const sandbox = harness.load({ cards: CARDS, vocab: VOCAB, meta: META });
const ids = q => harness.ids(sandbox, q);
const ALL = CARDS.map(c => c.id);

/* ── 空條件 ───────────────────────────────────────────── */

test('空條件列出全部,不擋', () => {
  assert.deepStrictEqual(ids({}), ALL);
  assert.deepStrictEqual(ids({ name: '' }), ALL);
  // 只打了萬用字元等於沒有條件
  assert.deepStrictEqual(ids({ name: '%' }), ALL);
});

test('回傳值帶每張卡的命中效果句索引欄位', () => {
  // 票03 還沒有句層條件,rows 因此是 null——但欄位存在,票04/06 接得上
  const hits = harness.search(sandbox, { name: '青眼' });
  assert.deepStrictEqual(hits.map(e => e.id), [89631139, 23995346]);
  assert.ok(hits.every(e => 'rows' in e));
});

/* ── 卡名軸:中文 ─────────────────────────────────────── */

test('中文卡名比對是子字串', () => {
  assert.deepStrictEqual(ids({ name: '青眼' }), [89631139, 23995346]);
  assert.deepStrictEqual(ids({ name: '黑魔導' }), [46986414]);
  assert.deepStrictEqual(ids({ name: '不存在的卡' }), []);
});

test('% 萬用字元:頭、尾、中間、多個', () => {
  assert.deepStrictEqual(ids({ name: '青眼%龍' }), [89631139, 23995346]);
  assert.deepStrictEqual(ids({ name: '%究極龍' }), [23995346]);
  assert.deepStrictEqual(ids({ name: '青眼%' }), [89631139, 23995346]);
  assert.deepStrictEqual(ids({ name: '青%究%龍' }), [23995346]);
  // 順序有意義:反過來寫就不該命中
  assert.deepStrictEqual(ids({ name: '龍%青眼' }), []);
});

/* ── 卡名軸:語言切換 ─────────────────────────────────── */

test('日文模式比對日文卡名', () => {
  assert.deepStrictEqual(ids({ name: '青眼', nameLang: 'ja' }), [89631139, 23995346]);
  assert.deepStrictEqual(ids({ name: 'ブラック', nameLang: 'ja' }), [46986414]);
  // 中文卡名在日文模式下不該被比對到
  assert.deepStrictEqual(ids({ name: '黑魔導', nameLang: 'ja' }), []);
});

test('英文模式比對英文卡名且大小寫不敏感', () => {
  assert.deepStrictEqual(ids({ name: 'Blue-Eyes', nameLang: 'en' }), [89631139, 23995346]);
  assert.deepStrictEqual(ids({ name: 'blue-eyes', nameLang: 'en' }), [89631139, 23995346]);
  assert.deepStrictEqual(ids({ name: 'DARK MAGICIAN', nameLang: 'en' }), [46986414]);
  assert.deepStrictEqual(ids({ name: '青眼', nameLang: 'en' }), []);
});

test('日/英卡名缺席的卡不會讓語言切換爆掉', () => {
  assert.deepStrictEqual(ids({ name: '試作', nameLang: 'ja' }), []);
  assert.deepStrictEqual(ids({ name: '試作', nameLang: 'en' }), []);
  assert.deepStrictEqual(ids({ name: '試作' }), [10000]);
});

test('中文與日文模式同時比對 ※ 別名,英文模式不比對', () => {
  assert.deepStrictEqual(ids({ name: '白銀之城', nameLang: 'zh' }), [2511]);
  assert.deepStrictEqual(ids({ name: '白銀之城', nameLang: 'ja' }), [2511]);
  assert.deepStrictEqual(ids({ name: '白銀之城', nameLang: 'en' }), []);
  // 別名也吃萬用字元
  assert.deepStrictEqual(ids({ name: '白銀%狂時鐘' }), [2511]);
});

/* ── 卡名軸:卡片密碼 ─────────────────────────────────── */

test('純數字輸入額外比對卡片密碼', () => {
  assert.deepStrictEqual(ids({ name: '46986414' }), [46986414]);
  assert.deepStrictEqual(ids({ name: '2511' }), [2511]);
  // 顯示時補零成 8 位,照著抄回來也要找得到
  assert.deepStrictEqual(ids({ name: '00002511' }), [2511]);
});

test('純數字輸入命中異圖密碼,得到的是本尊', () => {
  assert.deepStrictEqual(ids({ name: '46986430' }), [46986414]);
  assert.deepStrictEqual(ids({ name: '36996508' }), [46986414]);
});

test('卡片密碼比對不分語言', () => {
  assert.deepStrictEqual(ids({ name: '46986430', nameLang: 'ja' }), [46986414]);
  assert.deepStrictEqual(ids({ name: '46986430', nameLang: 'en' }), [46986414]);
});

test('密碼比對是「額外」而不是「取代」:數字照樣比對卡名', () => {
  // 卡名裡真的有數字的卡(No.39)不能因為輸入是純數字就搜不到
  assert.deepStrictEqual(ids({ name: '39' }), [84013237]);
});

test('數字要完全相等才算密碼命中,不是子字串', () => {
  // 4698 是 46986414 的前綴,但那不是任何一張卡的密碼
  assert.deepStrictEqual(ids({ name: '4698' }), []);
});
