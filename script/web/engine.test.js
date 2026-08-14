/**
 * engine.test.js — 接縫 3(前端查詢引擎)的測試
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
   欄位形狀與 `web/data.js` 一致:空值省略而不是寫 null,值一律短碼。
   前七張是票03 留下的卡名/密碼樣本;`20101` 起是票04/05 的邊界樣本。 */

const CARDS = [
  {
    id: 46986414, al: [46986430, 36996508],
    n: '黑魔導', nj: 'ブラック・マジシャン', ne: 'Dark Magician',
    c: 'm', s: ['normal'], at: 'dark', r: 'spellcaster', lv: 7,
    atk: 2500, df: 2100, ra: 'UR', ot: 'b',
    d: '究極的攻擊魔術師。',
  },
  {
    id: 89631139,
    n: '青眼白龍', nj: '青眼の白龍', ne: 'Blue-Eyes White Dragon',
    c: 'm', s: ['normal'], at: 'light', r: 'dragon', lv: 8,
    atk: 3000, df: 2500, ra: 'UR', ot: 'b', gy: 15,
    d: '以高攻擊力著稱的傳說之龍。',
  },
  {
    id: 23995346,
    n: '青眼究極龍', nj: '青眼の究極竜', ne: 'Blue-Eyes Ultimate Dragon',
    c: 'm', s: ['fusion'], at: 'light', r: 'dragon', lv: 12,
    atk: 4500, df: 3800, ra: 'SR',
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

  // 連結怪獸:連結值存 `lk`,**沒有 `df` 這個鍵**——那是「沒有這個參數」而不是 `?`
  {
    id: 20101, n: '連結樣本卡', c: 'm', s: ['link', 'effect'],
    at: 'wind', r: 'cyberse', lk: 2, lm: ['L', 'R'], atk: 1200, ot: 'o',
    tx: ['連結怪獸以外的怪獸2隻', '①：這張卡連結召喚成功的場合發動。'],
    k: ['x', 't'], ro: ['mat', ''],
  },
  // 靈擺怪獸:刻度 0 是真的值(28 張),不是空
  {
    id: 20102, n: '靈擺樣本卡', c: 'm', s: ['pendulum', 'effect'],
    at: 'fire', r: 'pyro', lv: 4, sc: 0, atk: 1500, df: 1000, ra: 'N',
    tx: ['①：靈擺區域的這張卡發動。', '①：這張卡在怪獸區域時發動。'],
    k: ['sp', 'i'], pz: [0],
  },
  // 攻守都是 `?`:哨兵值為負,與 0 是不同的東西
  {
    id: 20103, n: '不定樣本卡', c: 'm', s: ['effect'],
    at: 'divine', r: 'divine_beast', lv: 10, atk: -2, df: -2,
    tx: ['①：支付基本分決定攻擊力。'], k: ['i'],
  },
  // 罠モンスター:怪獸參數寫在效果文的括號裡,索引裡**沒有**那五個欄位(card-list 票07)
  {
    id: 20104, n: '岩石陷阱樣本卡', c: 't', s: ['continuous'],
    tx: ['①：這張卡以效果怪獸卡（岩石族・地・星4・攻1000／守1000）的身分特殊召喚。'],
    k: ['tc'],
  },
  // 儀式:同一個短碼在怪獸側與魔法側是兩件事(cdb 位元 0x80 兩邊都有)
  {
    id: 20105, n: '儀式怪獸樣本卡', c: 'm', s: ['ritual', 'effect'],
    at: 'light', r: 'fairy', lv: 6, atk: 2000, df: 1700,
    tx: ['①：這張卡儀式召喚成功時發動。'], k: ['t'],
  },
  {
    id: 20106, n: '儀式魔法樣本卡', c: 's', s: ['ritual'], ot: 't', gy: 5,
    tx: ['①：把手牌的儀式怪獸1隻儀式召喚。'], k: ['sr'],
  },
  // 句層耦合:同一句裡同時出現 vs 散落在兩句
  {
    id: 20107, n: '同句樣本卡', c: 's', s: ['normal'],
    tx: ['①：把手牌1張捨棄，從墓地特殊召喚1隻怪獸。'], k: ['sn'],
  },
  {
    id: 20108, n: '異句樣本卡', c: 's', s: ['normal'],
    tx: ['①：把手牌1張捨棄。', '②：從墓地特殊召喚1隻怪獸。'], k: ['sn', 'sn'],
  },
  // 四行各一種 role:素材指定不掃,召喚條件與使用次數限制照掃
  {
    id: 20109, n: '素材樣本卡', c: 'm', s: ['fusion', 'effect'],
    at: 'dark', r: 'fiend', lv: 8, atk: 2800, df: 2000,
    tx: ['融合怪獸1隻＋惡魔族怪獸1隻', '這張卡不能通常召喚。',
         '這個卡名的①效果1回合只能使用1次。', '①：這張卡攻擊力上升500。'],
    k: ['x', 'x', 'x', 'c'], ro: ['mat', 'cond', 'limit', ''],
  },

  // 票06 的核心對照組:① 是誘發即時但不含關鍵字、② 含關鍵字但是啟動效果。
  // 整段卡文比對的話這張會中,句層耦合則不中——這正是分水嶺。
  {
    id: 20110, n: '耦合異句樣本卡', c: 'm', s: ['effect'],
    at: 'water', r: 'fiend', lv: 5, atk: 1800, df: 2200,
    tx: ['①：對手把卡發動時可以發動。', '②：把對手場上1張卡除外。'],
    k: ['q', 'i'], o: ['o', ''],
  },
  // 同一句同時滿足:命中,而且命中效果句索引指向那一句
  {
    id: 20111, n: '耦合同句樣本卡', c: 'm', s: ['effect'],
    at: 'water', r: 'fiend', lv: 5, atk: 1800, df: 2200,
    tx: ['①：對手把卡發動時，把對手場上1張卡除外。'],
    k: ['q'], o: ['o'],
  },
  // 必發與選發各一句(通常陷阱卡效果承載這個屬性)
  {
    id: 20112, n: '必發樣本卡', c: 't', s: ['normal'],
    tx: ['①：這張卡被破壞的場合必須發動。', '②：這張卡發動後可以追加處理。'],
    k: ['tn', 'tn'], o: ['m', 'o'],
  },
];

const item = (code, zh) => ({ code, zh });

const VOCAB = {
  cat: { zh: '大類', items: [item('m', '怪獸'), item('s', '魔法'), item('t', '陷阱')] },
  sub_m: {
    zh: '怪獸子類型',
    items: [item('normal', '通常'), item('effect', '效果'), item('fusion', '融合'),
            item('ritual', '儀式'), item('xyz', '超量'), item('pendulum', '靈擺'),
            item('link', '連結')],
    groups: [{ zh: '卡框', codes: ['normal', 'effect', 'fusion', 'ritual', 'xyz',
                                   'pendulum', 'link'] }],
  },
  sub_s: { zh: '魔法子類型',
           items: [item('normal', '通常'), item('quick', '速攻'), item('ritual', '儀式')] },
  sub_t: { zh: '陷阱子類型',
           items: [item('normal', '通常'), item('continuous', '永續')] },
  attr: { zh: '屬性',
          items: [item('earth', '地'), item('water', '水'), item('fire', '炎'),
                  item('wind', '風'), item('light', '光'), item('dark', '闇'),
                  item('divine', '神')] },
  race: { zh: '種族',
          items: [item('warrior', '戰士族'), item('spellcaster', '魔法使族'),
                  item('fairy', '天使族'), item('fiend', '惡魔族'),
                  item('pyro', '炎族'), item('rock', '岩石族'),
                  item('dragon', '龍族'), item('cyberse', '電子界族'),
                  item('divine_beast', '幻神獸族')] },
  kind: { zh: '效果類型',
          items: [item('x', '效果外文本'), item('c', '永續效果'),
                  item('q', '誘發即時效果(2速)'), item('t', '誘發效果(1速)'),
                  item('i', '啟動效果'), item('sn', '通常魔法卡效果'),
                  item('sr', '儀式魔法卡效果'), item('sp', '靈擺魔法卡效果'),
                  item('tn', '通常陷阱卡效果'), item('tc', '永續陷阱卡效果')],
          groups: [{ zh: '怪獸側', codes: ['x', 'c', 'q', 't', 'i'] },
                   { zh: '魔陷卡效果', codes: ['sn', 'sr', 'sp', 'tn', 'tc'] }] },
  // 承載關係住在值域正典(CONTEXT.md「必發/選發」):只有誘發即時(2速)、
  // 誘發(1速)與魔陷卡效果十值承載,永續效果與啟動效果不承載
  optional: { zh: '必發/選發', items: [item('m', '必發'), item('o', '選發')],
              carriers: ['q', 't', 'sn', 'sr', 'sp', 'tn', 'tc'] },
  role: { zh: '效果外文本種別',
          items: [item('mat', '素材指定'), item('cond', '召喚條件'),
                  item('limit', '使用次數限制')] },
  lm: { zh: '連結標記',
        items: [item('TL', '↖'), item('T', '↑'), item('TR', '↗'), item('L', '←'),
                item('R', '→'), item('BL', '↙'), item('B', '↓'), item('BR', '↘')] },
  rarity: { zh: 'MD 稀有度',
            items: [item('N', 'N'), item('R', 'R'), item('SR', 'SR'), item('UR', 'UR')] },
  ot: { zh: 'OCG・TCG',
        items: [item('o', 'OCG 限定'), item('t', 'TCG 限定'), item('b', '兩者')] },
};

const META = {
  cards: CARDS.length,
  clauses: CARDS.reduce((n, c) => n + (c.tx || []).length, 0),
};

const sandbox = harness.load({ cards: CARDS, vocab: VOCAB, meta: META });
const ids = q => harness.ids(sandbox, q);
const rowsOf = (q, id) => (harness.search(sandbox, q).find(e => e.id === id) || {}).rows;
const ALL = CARDS.map(c => c.id);

/* ── 空條件 ───────────────────────────────────────────── */

test('空條件列出全部,不擋', () => {
  assert.deepStrictEqual(ids({}), ALL);
  assert.deepStrictEqual(ids({ name: '' }), ALL);
  assert.deepStrictEqual(ids({ name: '   ' }), ALL);
  // 只打了萬用字元等於沒有條件
  assert.deepStrictEqual(ids({ name: '%' }), ALL);
  assert.deepStrictEqual(ids({ text: '%' }), ALL);
});

test('關鍵字前後的空白不影響比對', () => {
  assert.deepStrictEqual(ids({ name: ' 青眼 ' }), [89631139, 23995346]);
  assert.deepStrictEqual(ids({ code: ' 46986430 ' }), [46986414]);
  assert.deepStrictEqual(ids({ text: ' 墓地 ' }), [20107, 20108]);
});

test('回傳值帶每張卡的命中效果句索引欄位', () => {
  // 卡層條件不寫 rows(卡名軸沒有「命中哪一句」可言),但欄位一律存在
  const hits = harness.search(sandbox, { name: '青眼' });
  assert.deepStrictEqual(hits.map(e => e.id), [89631139, 23995346]);
  assert.ok(hits.every(e => 'rows' in e && e.rows === null));
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

test('卡名框只比對卡名,不比對卡片密碼', () => {
  // 密碼是另一個欄位的事(2026-08-14 使用者裁示,推翻 spec Story 3)
  assert.deepStrictEqual(ids({ name: '46986414' }), []);
  assert.deepStrictEqual(ids({ name: '46986430' }), []);
  assert.deepStrictEqual(ids({ name: '00002511' }), []);
  // 卡名裡真的有數字的卡照樣比對得到:拿掉的是密碼比對,不是數字比對
  assert.deepStrictEqual(ids({ name: '39' }), [84013237]);
});

/* ── 卡片密碼軸 ───────────────────────────────────────── */

test('卡片密碼軸比對密碼與異圖密碼', () => {
  assert.deepStrictEqual(ids({ code: '46986414' }), [46986414]);
  assert.deepStrictEqual(ids({ code: '2511' }), [2511]);
  // 顯示時補零成 8 位,照著抄回來也要找得到
  assert.deepStrictEqual(ids({ code: '00002511' }), [2511]);
});

test('卡片密碼軸命中異圖密碼,得到的是本尊', () => {
  assert.deepStrictEqual(ids({ code: '46986430' }), [46986414]);
  assert.deepStrictEqual(ids({ code: '36996508' }), [46986414]);
});

test('密碼要完全相等才算,不是子字串', () => {
  // 4698 是 46986414 的前綴,但那不是任何一張卡的密碼
  assert.deepStrictEqual(ids({ code: '4698' }), []);
});

test('卡片密碼軸只認密碼,不比對卡名', () => {
  // 卡名框搜 39 撈得到 No.39,密碼軸不該有這個副作用
  assert.deepStrictEqual(ids({ code: '39' }), []);
  assert.deepStrictEqual(ids({ code: '青眼' }), []);
});

test('卡片密碼軸不受卡名語言影響', () => {
  assert.deepStrictEqual(ids({ code: '46986430', nameLang: 'ja' }), [46986414]);
  assert.deepStrictEqual(ids({ code: '46986430', nameLang: 'en' }), [46986414]);
});

test('密碼軸空白等於沒設,非數字則不命中任何卡', () => {
  assert.deepStrictEqual(ids({ code: '' }), ALL);
  assert.deepStrictEqual(ids({ code: '   ' }), ALL);
  // 「打了條件卻當作沒打」會讓使用者以為結果是這個條件篩出來的
  assert.deepStrictEqual(ids({ code: '4698-6414' }), []);
});

test('卡名軸與密碼軸並用是 AND', () => {
  assert.deepStrictEqual(ids({ name: '黑魔導', code: '46986414' }), [46986414]);
  assert.deepStrictEqual(ids({ name: '青眼', code: '46986414' }), []);
});

/* ── 效果文軸:逐效果句獨立比對(票04) ────────────────────
   這是這個站與一般查卡站的分水嶺:一般查卡站對整段卡文做關鍵字比對,
   分不出「同一個效果做了兩件事」與「兩件事散落在兩個無關的效果」。 */

test('效果文關鍵字在同一句裡同時滿足才算命中', () => {
  // 20107 兩個詞在同一句;20108 一句一個——整段卡文比對的話兩張都會中
  assert.deepStrictEqual(ids({ text: '手牌%墓地' }), [20107]);
  assert.deepStrictEqual(ids({ text: '手牌' }), [2511, 20106, 20107, 20108]);
  assert.deepStrictEqual(ids({ text: '墓地' }), [20107, 20108]);
});

test('命中效果句索引指向正確的那一句', () => {
  assert.deepStrictEqual(rowsOf({ text: '墓地' }, 20108), [1]);
  assert.deepStrictEqual(rowsOf({ text: '手牌' }, 20108), [0]);
  assert.deepStrictEqual(rowsOf({ text: '手牌%墓地' }, 20107), [0]);
  // 多句命中就多個索引;沒命中的句子不進去(標亮只落在真正命中的那幾行)
  assert.deepStrictEqual(rowsOf({ text: '攻擊力' }, 20109), [3]);
  assert.deepStrictEqual(rowsOf({ text: '這張卡' }, 20109), [1, 3]);
});

test('效果文框的 % 萬用字元語意同卡名框', () => {
  assert.deepStrictEqual(ids({ text: '把手牌%捨棄' }), [20107, 20108]);
  assert.deepStrictEqual(ids({ text: '%捨棄' }), [2511, 20107, 20108]);
  // 順序有意義
  assert.deepStrictEqual(ids({ text: '墓地%手牌' }), []);
});

test('效果文關鍵字不掃 role = 素材指定 的行', () => {
  // 574 張融合怪獸的素材寫法會把真正的答案淹掉,所以固定不掃
  assert.deepStrictEqual(ids({ text: '融合' }), []);
  assert.deepStrictEqual(ids({ text: '惡魔族' }), []);
  // 「怪獸」出現在四張卡的素材行裡,一張都不該因此命中
  assert.deepStrictEqual(ids({ text: '怪獸' }),
                         [20102, 20104, 20106, 20107, 20108]);
  // 已知副作用:效果文框搜「青眼白龍」撈不到把它寫在素材行的融合怪獸
  assert.deepStrictEqual(ids({ text: '青眼白龍' }), []);
  assert.deepStrictEqual(ids({ name: '青眼白龍' }), [89631139]);
});

test('召喚條件與使用次數限制的行照樣掃', () => {
  assert.deepStrictEqual(ids({ text: '不能通常召喚' }), [20109]);
  assert.deepStrictEqual(rowsOf({ text: '不能通常召喚' }, 20109), [1]);
  assert.deepStrictEqual(ids({ text: '1回合' }), [2511, 483, 20109]);
  assert.deepStrictEqual(rowsOf({ text: '1回合' }, 20109), [2]);
});

test('沒有效果句的卡不被效果文條件命中', () => {
  // 純通常怪獸只有故事文,那不是效果——搜效果文搜不到它是對的
  assert.deepStrictEqual(ids({ text: '魔術師' }), []);
  assert.deepStrictEqual(ids({ name: '黑魔導' }), [46986414]);
});

test('生效中的句層條件回報得出來(呈現層照它寫命中行的 badge)', () => {
  assert.deepStrictEqual(harness.marks(sandbox, { text: '墓地' }),
                         [{ type: 'text', value: '墓地' }]);
  assert.deepStrictEqual(harness.marks(sandbox, {}), []);
  assert.deepStrictEqual(harness.marks(sandbox, { name: '青眼' }), []);
});

test('效果文軸與卡層軸並用是 AND', () => {
  assert.deepStrictEqual(ids({ text: '墓地', name: '同句' }), [20107]);
  assert.deepStrictEqual(ids({ text: '墓地', name: '青眼' }), []);
  assert.deepStrictEqual(ids({ text: '手牌', cat: { s: 1 } }), [20106, 20107, 20108]);
});

/* ── 卡片參數軸:三態(票05) ──────────────────────────── */

const MONSTERS = [46986414, 89631139, 23995346, 2511, 84013237,
                  20101, 20102, 20103, 20105, 20109, 20110, 20111];
const NON_MONSTERS = [483, 10000, 20104, 20106, 20107, 20108, 20112];

test('三態的三種狀態各自的結果', () => {
  assert.deepStrictEqual(ids({}), ALL);                    // 未選
  assert.deepStrictEqual(ids({ cat: { m: 1 } }), MONSTERS); // 包含
  assert.deepStrictEqual(ids({ cat: { m: -1 } }), NON_MONSTERS); // 排除
  // 空的條件物件等於沒設(全部沒選時 read() 不該把整個軸變成零結果)
  assert.deepStrictEqual(ids({ cat: {} }), ALL);
});

test('同一軸同時包含與排除時排除優先', () => {
  // 子類型是多值的,同一張卡可以同時中包含與排除——那時以排除為準
  assert.deepStrictEqual(ids({ sub: { 'm:effect': 1 } }),
                         [2511, 20101, 20102, 20103, 20105, 20109, 20110, 20111]);
  assert.deepStrictEqual(ids({ sub: { 'm:effect': 1, 'm:link': -1 } }),
                         [2511, 20102, 20103, 20105, 20109, 20110, 20111]);
  // 排除寫在包含前面或後面都一樣(不能只在寫法順序上成立)
  assert.deepStrictEqual(ids({ sub: { 'm:link': -1, 'm:effect': 1 } }),
                         [2511, 20102, 20103, 20105, 20109, 20110, 20111]);
});

test('軸內 OR、軸間 AND', () => {
  assert.deepStrictEqual(ids({ attr: { dark: 1 } }), [46986414, 2511, 20109]);
  assert.deepStrictEqual(ids({ attr: { dark: 1, light: 1 } }),
                         [46986414, 89631139, 23995346, 2511, 84013237, 20105, 20109]);
  assert.deepStrictEqual(ids({ attr: { light: 1 }, race: { dragon: 1 } }),
                         [89631139, 23995346]);
  assert.deepStrictEqual(ids({ attr: { dark: 1 }, race: { dragon: 1 } }), []);
});

test('子類型的短碼帶大類前綴:儀式怪獸與儀式魔法不互撈', () => {
  assert.deepStrictEqual(ids({ sub: { 'm:ritual': 1 } }), [20105]);
  assert.deepStrictEqual(ids({ sub: { 's:ritual': 1 } }), [20106]);
  // 子類型是**一個**軸的三段:跨側多選是 OR,不是永遠零筆的 AND
  assert.deepStrictEqual(ids({ sub: { 'm:fusion': 1, 's:quick': 1 } }),
                         [23995346, 483, 20109]);
  // 大類軸與子類型軸之間仍是 AND
  assert.deepStrictEqual(ids({ cat: { m: 1 }, sub: { 's:ritual': 1 } }), []);
});

/* ── 卡片參數軸:範圍與 `?` ───────────────────────────── */

test('範圍條件的邊界與只給一邊', () => {
  assert.deepStrictEqual(ids({ lv: { min: 8 } }),
                         [89631139, 23995346, 20103, 20109]);
  assert.deepStrictEqual(ids({ lv: { max: 1 } }), [2511]);
  assert.deepStrictEqual(ids({ lv: { min: 4, max: 4 } }), [84013237, 20102]);
  assert.deepStrictEqual(ids({ lv: { min: 12, max: 12 } }), [23995346]);
  assert.deepStrictEqual(ids({ lv: { min: 13 } }), []);
  // 兩邊都空等於沒設,不該把「沒有等級」的卡全部濾掉
  assert.deepStrictEqual(ids({ lv: {} }), ALL);
});

test('等級軸不撈連結怪獸,連結值軸只撈連結怪獸', () => {
  // 連結值存在 `lk`、等級存在 `lv`,兩個欄位不共用
  assert.deepStrictEqual(ids({ lk: { min: 1 } }), [20101]);
  assert.deepStrictEqual(ids({ lv: { min: 1 } }).includes(20101), false);
});

test('靈擺刻度 0 是真的值而不是空', () => {
  assert.deepStrictEqual(ids({ sc: { min: 0, max: 0 } }), [20102]);
  assert.deepStrictEqual(ids({ sc: { min: 1 } }), []);
});

test('攻守 `?` 不被數值範圍納入', () => {
  assert.deepStrictEqual(ids({ atk: { min: 2500 } }),
                         [46986414, 89631139, 23995346, 84013237, 20109]);
  // `?` 以負的哨兵值存,當成 0 的話這一條會把它撈進來
  assert.deepStrictEqual(ids({ atk: { min: 0, max: 0 } }), [2511]);
  assert.deepStrictEqual(ids({ atk: { max: 1200 } }), [2511, 20101]);
  assert.deepStrictEqual(ids({ df: { min: 0, max: 2000 } }),
                         [2511, 84013237, 20102, 20105, 20109]);
});

test('攻守 `?` 有獨立條件', () => {
  assert.deepStrictEqual(ids({ atkq: 1 }), [20103]);
  assert.deepStrictEqual(ids({ atkq: -1 }), ALL.filter(id => id !== 20103));
  assert.deepStrictEqual(ids({ dfq: 1 }), [20103]);
});

test('連結怪獸的守備不算 `?`', () => {
  // 20101 沒有 `df` 這個鍵:那是「沒有這個參數」,不是不明
  assert.deepStrictEqual(ids({ dfq: 1 }).includes(20101), false);
  assert.deepStrictEqual(ids({ dfq: -1 }).includes(20101), true);
  assert.deepStrictEqual(ids({ df: { min: 0 } }).includes(20101), false);
});

test('罠モンスター不被種族/屬性/等級/攻守條件命中', () => {
  // 20104 的效果文寫著「岩石族・地・星4・攻1000／守1000」,但那是它變成怪獸之後的
  // 參數,索引裡根本沒有這五個欄位(card-list 票07)——想找它的人用效果文關鍵字
  assert.deepStrictEqual(ids({ race: { rock: 1 } }), []);
  assert.deepStrictEqual(ids({ attr: { earth: 1 } }), []);
  assert.deepStrictEqual(ids({ lv: { min: 4, max: 4 } }).includes(20104), false);
  assert.deepStrictEqual(ids({ atk: { min: 1000, max: 1000 } }), []);
  assert.deepStrictEqual(ids({ text: '岩石族' }), [20104]);
});

/* ── 卡片參數軸:連結標記與三個印刷面欄位 ───────────────── */

test('連結標記可篩選', () => {
  assert.deepStrictEqual(ids({ lm: { L: 1 } }), [20101]);
  assert.deepStrictEqual(ids({ lm: { TL: 1 } }), []);
  assert.deepStrictEqual(ids({ lm: { L: 1, TL: 1 } }), [20101]);   // 軸內 OR
  assert.deepStrictEqual(ids({ lm: { L: -1 } }), ALL.filter(id => id !== 20101));
});

test('MD 稀有度、Genesys 點數、OCG・TCG 三個條件', () => {
  assert.deepStrictEqual(ids({ rarity: { UR: 1 } }), [46986414, 89631139]);
  assert.deepStrictEqual(ids({ rarity: { UR: 1, N: 1 } }), [46986414, 89631139, 20102]);
  // MD 未實裝不是值域成員(它是「沒有這個欄位」):四種全排除就是那一批
  assert.deepStrictEqual(ids({ rarity: { N: -1, R: -1, SR: -1, UR: -1 } }),
                         ALL.filter(id => ![46986414, 89631139, 23995346, 20102]
                           .includes(id)));
  assert.deepStrictEqual(ids({ ot: { o: 1 } }), [20101]);
  assert.deepStrictEqual(ids({ ot: { t: 1 } }), [20106]);
  assert.deepStrictEqual(ids({ gy: { min: 1 } }), [89631139, 20106]);
  assert.deepStrictEqual(ids({ gy: { min: 6 } }), [89631139]);
});

test('參數軸與關鍵字軸並用是 AND', () => {
  assert.deepStrictEqual(ids({ attr: { light: 1 }, atk: { min: 3000 } }),
                         [89631139, 23995346]);
  assert.deepStrictEqual(ids({ cat: { m: 1 }, text: '怪獸' }), [20102]);
  assert.deepStrictEqual(ids({ name: '青眼', race: { dragon: 1 }, lv: { min: 10 } }),
                         [23995346]);
});

/* ── 效果類型與必發/選發軸(票06) ──────────────────────
   [[效果標記表]]花了 20 多張判定票判出來的效果類型,到這一票才有使用者。
   句層耦合是這一段的核心:效果文關鍵字與效果類型**必須命中同一個效果句**。 */

test('效果類型可篩選,軸內 OR、軸間 AND、三態排除', () => {
  assert.deepStrictEqual(ids({ kind: { q: 1 } }), [2511, 20110, 20111]);
  assert.deepStrictEqual(ids({ kind: { sr: 1 } }), [20106]);
  assert.deepStrictEqual(ids({ kind: { sr: 1, tc: 1 } }), [20104, 20106]);
  // 排除是**這一句不是那個類型**,不是「這張卡沒有那個類型的句子」——句層條件的
  // 排除同樣落在效果句上,否則同一個軸會有兩種語意
  assert.deepStrictEqual(ids({ kind: { i: -1 } }).includes(20103), false);
  assert.deepStrictEqual(ids({ kind: { i: -1 } }).includes(20110), true);
  // 空的條件物件等於沒設
  assert.deepStrictEqual(ids({ kind: {} }), ALL);
});

test('效果類型的命中效果句索引指向那一句', () => {
  assert.deepStrictEqual(rowsOf({ kind: { q: 1 } }, 2511), [1]);
  assert.deepStrictEqual(rowsOf({ kind: { i: 1 } }, 20110), [1]);
  assert.deepStrictEqual(rowsOf({ kind: { tn: 1 } }, 20112), [0, 1]);
  // 沒有效果句的純通常怪獸不被效果類型條件命中(故事文不是效果)
  assert.deepStrictEqual(ids({ kind: { x: 1 } }).includes(46986414), false);
});

test('句層耦合:效果文關鍵字與效果類型必須命中同一個效果句', () => {
  // 20110 的 ① 是誘發即時但不含關鍵字、② 含關鍵字但是啟動效果 → 不命中
  assert.deepStrictEqual(ids({ text: '除外' }), [20110, 20111]);
  assert.deepStrictEqual(ids({ kind: { q: 1 } }), [2511, 20110, 20111]);
  assert.deepStrictEqual(ids({ text: '除外', kind: { q: 1 } }), [20111]);
  // 命中效果句索引指向同時滿足的那一句
  assert.deepStrictEqual(rowsOf({ text: '除外', kind: { q: 1 } }, 20111), [0]);
  // 反過來配:② 是啟動效果且含關鍵字,那一句同時滿足
  assert.deepStrictEqual(ids({ text: '除外', kind: { i: 1 } }), [20110]);
  assert.deepStrictEqual(rowsOf({ text: '除外', kind: { i: 1 } }, 20110), [1]);
});

test('必發/選發可篩選,且只在承載的效果類型上生效', () => {
  assert.deepStrictEqual(ids({ opt: { m: 1 } }), [20112]);
  assert.deepStrictEqual(ids({ opt: { o: 1 } }), [20110, 20111, 20112]);
  assert.deepStrictEqual(rowsOf({ opt: { m: 1 } }, 20112), [0]);
  assert.deepStrictEqual(rowsOf({ opt: { o: 1 } }, 20112), [1]);
  // 永續效果不承載這個屬性:「永續效果是必發」永遠零結果(所以 UI 不讓它設出來)
  assert.deepStrictEqual(ids({ kind: { c: 1 } }), [20109]);
  assert.deepStrictEqual(ids({ kind: { c: 1 }, opt: { m: 1 } }), []);
  // 承載型的效果類型但這一句沒有值:不被必發命中,也不被「排除必發」排掉
  assert.deepStrictEqual(ids({ opt: { m: 1 } }).includes(20101), false);
  assert.deepStrictEqual(rowsOf({ kind: { t: 1 }, opt: { m: -1 } }, 20101), [1]);
});

test('必發/選發與效果文也走同一個效果句', () => {
  assert.deepStrictEqual(ids({ text: '除外', opt: { o: 1 } }), [20111]);
  assert.deepStrictEqual(ids({ text: '除外', opt: { m: 1 } }), []);
});

test('效果類型條件掃得到素材指定行,效果文關鍵字仍然不掃', () => {
  // 不掃素材行是**關鍵字**的規則(574 張融合怪獸的素材寫法會淹掉答案),
  // 不是「素材行不存在」——找效果外文本的人要看得到它
  assert.deepStrictEqual(rowsOf({ kind: { x: 1 } }, 20109), [0, 1, 2]);
  assert.deepStrictEqual(ids({ kind: { x: 1 }, text: '融合' }), []);
  assert.deepStrictEqual(rowsOf({ kind: { x: 1 }, text: '召喚' }, 20109), [1]);
});

test('句層條件回報得出來,多條件並用時三種都在', () => {
  assert.deepStrictEqual(harness.marks(sandbox, { kind: { q: 1 } }),
                         [{ type: 'kind' }]);
  assert.deepStrictEqual(harness.marks(sandbox, { opt: { m: 1 } }),
                         [{ type: 'opt' }]);
  assert.deepStrictEqual(
    harness.marks(sandbox, { text: '除外', kind: { q: 1 }, opt: { o: 1 } }),
    [{ type: 'text', value: '除外' }, { type: 'kind' }, { type: 'opt' }]);
  // 一顆鈕都沒點的軸不算生效中的條件
  assert.deepStrictEqual(harness.marks(sandbox, { kind: {} }), []);
});

test('必發/選發那一組條件只在承載它的效果類型被選時出得來', () => {
  const avail = sel => harness.optionalAvailable(sandbox, sel);
  // 一顆效果類型都沒選:「必發」自己就是有結果的條件,不必先選滿承載的那幾顆
  assert.strictEqual(avail(null), true);
  assert.strictEqual(avail({}), true);
  // 選的全是不承載的類型 → 收起來(「永續效果是必發」永遠零結果)
  assert.strictEqual(avail({ c: 1 }), false);
  assert.strictEqual(avail({ c: 1, i: 1, x: 1 }), false);
  // 只要有一個承載就出得來(軸內是 OR)
  assert.strictEqual(avail({ q: 1 }), true);
  assert.strictEqual(avail({ c: 1, q: 1 }), true);
  // 排除不是「已選」:排除永續效果之後,命中的句子仍然可能是承載型的
  assert.strictEqual(avail({ c: -1 }), true);
  assert.strictEqual(avail({ q: -1 }), true);
});

/* ── 按鈕由值域正典生成 ────────────────────────────────
   沙箱裡沒有真的 DOM,而 DOM 那一層只是照這份清單擺按鈕——清單是這條性質
   測得到的形狀(ADR-0008)。 */

test('分類類條件的按鈕清單由 window.VOCAB 導出', () => {
  const axes = harness.axes(sandbox);
  assert.deepStrictEqual(axes.map(a => a.key + '/' + a.side),
                         ['kind/', 'opt/', 'cat/', 'sub/m', 'sub/s', 'sub/t',
                          'attr/', 'race/', 'lm/', 'rarity/', 'ot/']);
  // 效果類型十六值分怪獸側與魔陷卡效果兩組呈現(Story 23):十六顆鈕排在一起時,
  // 使用者要看得出哪些是同一個維度的東西
  assert.deepStrictEqual(axes.find(a => a.key === 'kind').groups.map(g => g.zh),
                         ['怪獸側', '魔陷卡效果']);
  const race = axes.find(a => a.key === 'race');
  // 軸標題也來自值域(HTML 連軸叫什麼名字都不知道)
  assert.strictEqual(race.zh, VOCAB.race.zh);
  assert.deepStrictEqual(race.groups[0].items.map(i => i.code),
                         VOCAB.race.items.map(i => i.code));
  // 有分組的值域照分組排,沒有分組的整批一組、組名留空
  assert.deepStrictEqual(axes.find(a => a.side === 'm').groups.map(g => g.zh), ['卡框']);
  assert.deepStrictEqual(race.groups.map(g => g.zh), ['']);
});

test('在值域正典裡加一個種族,按鈕自動多一顆', () => {
  const grown = {
    ...VOCAB,
    race: { zh: '種族', items: [...VOCAB.race.items, item('slime', '史萊姆族')] },
  };
  const box = harness.load({ cards: CARDS, vocab: grown, meta: META });
  const before = harness.axes(sandbox).find(a => a.key === 'race');
  const after = harness.axes(box).find(a => a.key === 'race');
  assert.strictEqual(after.groups[0].items.length,
                     before.groups[0].items.length + 1);
  assert.deepStrictEqual(after.groups[0].items.at(-1), { code: 'slime', zh: '史萊姆族' });
});

/* ── 排序 ──────────────────────────────────────────────
   排序與搜尋解耦:比較函式只看卡片物件,重排走的是同一份已經命中的結果。
   下面每一條都跑「查詢 → 排序」這條真實的路徑(harness.sortedIds)。 */

const sorted = (key, dir, q) => harness.sortedIds(sandbox, q || {}, key, dir);

/* 主資料集裡沒有這幾個參數的卡。攻守的空值有兩種來源,兩種都不是數值:
   非怪獸根本沒有那個欄位,而 20103 的攻守是 `?`(負的哨兵值)。 */
const NO_ATK = [483, 10000, 20103, 20104, 20106, 20107, 20108, 20112];
const NO_DF = [483, 10000, 20101, 20103, 20104, 20106, 20107, 20108, 20112];
const NO_LV = [483, 10000, 20101, 20104, 20106, 20107, 20108, 20112];

test('預設是領域序:七層比較', () => {
  // 大類(怪獸→魔法→陷阱)→ 靈擺排後 → 卡框序 → 等級高到低 → 屬性 → 種族 → 密碼。
  // 怪獸側:通常(青眼 lv8、黑魔導 lv7)→ 效果(lv10、5、5、1)→ 融合(lv12、8)
  // → 儀式 → 超量 → 連結 → 靈擺;20110/20111 同屬性同種族同等級,由密碼決勝。
  const DOMAIN = [
    89631139, 46986414,                     // 通常怪獸,等級高到低
    20103, 20110, 20111, 2511,              // 效果怪獸
    23995346, 20109,                        // 融合
    20105,                                  // 儀式
    84013237,                               // 超量
    20101,                                  // 連結
    20102,                                  // 靈擺(第 2 層把它挪到怪獸的最後)
    20107, 20108, 483, 20106,               // 魔法:通常 → 速攻 → 儀式
    10000, 20112, 20104,                    // 陷阱:通常 → 永續
  ];
  assert.deepStrictEqual(sorted('dom', ''), DOMAIN);
  // 沒指定排序鍵時就是這個順序(預設值也住在 KEYS 的第一筆)
  assert.deepStrictEqual(sorted('', ''), DOMAIN);
});

test('領域序的大類序取自 window.VOCAB 的宣告序,不是程式裡的第二份表', () => {
  const flipped = {
    ...VOCAB,
    cat: { zh: '大類', items: [item('t', '陷阱'), item('s', '魔法'), item('m', '怪獸')] },
  };
  const box = harness.load({ cards: CARDS, vocab: flipped, meta: META });
  const before = sorted('dom', '');
  const after = harness.sortedIds(box, {}, 'dom', '');
  // 三個大類的區塊整批換位置,區塊內部的順序一個字都沒動
  const block = cat => before.filter(id => CARDS.find(c => c.id === id).c === cat);
  assert.deepStrictEqual(after, [...block('t'), ...block('s'), ...block('m')]);
});

/* 卡框序與屬性/種族序的專用樣本:主資料集沒有協調怪獸,而「『能力』子類型不參與
   卡框序」正是這一層最容易寫錯的地方——協調同步怪獸該站在同步那一團裡。 */
const ORDER_VOCAB = {
  cat: { zh: '大類', items: [item('m', '怪獸')] },
  sub_m: {
    zh: '怪獸子類型',
    items: [item('normal', '通常'), item('effect', '效果'), item('synchro', '同步'),
            item('tuner', '協調')],
    groups: [{ zh: '卡框', codes: ['normal', 'effect', 'synchro'] },
             { zh: '能力', codes: ['tuner'] }],
  },
  sub_s: { zh: '魔法子類型', items: [item('normal', '通常')] },
  sub_t: { zh: '陷阱子類型', items: [item('normal', '通常')] },
  attr: { zh: '屬性', items: [item('earth', '地'), item('water', '水')] },
  race: { zh: '種族', items: [item('warrior', '戰士族'), item('dragon', '龍族')] },
};
const mon = (id, s, at, r) =>
  ({ id, n: 'card' + id, c: 'm', s, at, r, lv: 5, atk: 1000, df: 1000 });
const ORDER_CARDS = [
  mon(1, ['effect', 'synchro', 'tuner'], 'earth', 'warrior'),
  mon(2, ['effect'], 'earth', 'warrior'),
  mon(3, ['effect'], 'water', 'warrior'),
  mon(4, ['effect'], 'earth', 'dragon'),
  mon(5, ['effect', 'tuner'], 'earth', 'warrior'),
];

test('卡框序不被「能力」子類型搶走,屬性序在種族序之前', () => {
  const box = harness.load({ cards: ORDER_CARDS, vocab: ORDER_VOCAB, meta: {} });
  // 效果(2/3/4/5)→ 同步(1);效果那一團先比屬性(地在水前)再比種族。
  // 5 是協調效果怪獸:協調在宣告序上排在同步後面,拿它來排的話 5 會掉到最後。
  assert.deepStrictEqual(harness.sortedIds(box, {}, 'dom', ''), [2, 5, 4, 3, 1]);
});

test('領域序的屬性序取自 window.VOCAB 的宣告序', () => {
  const flipped = {
    ...ORDER_VOCAB,
    attr: { zh: '屬性', items: [item('water', '水'), item('earth', '地')] },
  };
  const box = harness.load({ cards: ORDER_CARDS, vocab: flipped, meta: {} });
  assert.deepStrictEqual(harness.sortedIds(box, {}, 'dom', ''), [3, 2, 5, 4, 1]);
});

test('攻擊力升降序', () => {
  // 4500 → 3000 → 2800 → 2500 兩張 → 2000 → 1800 兩張 → 1500 → 1200 → 0
  assert.deepStrictEqual(sorted('atk', 'desc').slice(0, 11),
    [23995346, 89631139, 20109, 84013237, 46986414, 20105, 20111, 20110,
     20102, 20101, 2511]);
  assert.deepStrictEqual(sorted('atk', 'asc').slice(0, 3), [2511, 20101, 20102]);
});

test('空值一律殿後,不插進數值之間', () => {
  // 攻擊力:非怪獸沒有這個欄位,20103 的攻擊力是 `?`——兩種都不是數值,
  // 而 `?` 當 0 排的話它會混進攻 0 那一團裡,是一個看不出來的錯
  const tail = (out, empty) => out.slice(-empty.length).slice().sort((a, b) => a - b);
  for (const dir of ['asc', 'desc']) {
    assert.deepStrictEqual(tail(sorted('atk', dir), NO_ATK), NO_ATK);
    assert.deepStrictEqual(tail(sorted('df', dir), NO_DF), NO_DF);
    // 等級只認 `lv`:連結怪獸(20101)沒有等級,LINK-2 是連結值、是另一個參數
    assert.deepStrictEqual(tail(sorted('lv', dir), NO_LV), NO_LV);
  }
});

test('守備力與等級的順序', () => {
  assert.deepStrictEqual(sorted('df', 'desc').slice(0, 5),
                         [23995346, 89631139, 20111, 20110, 46986414]);
  assert.deepStrictEqual(sorted('lv', 'desc').slice(0, 5),
                         [23995346, 20103, 89631139, 20109, 46986414]);
});

test('卡名排序照卡名而不是密碼', () => {
  const asc = sorted('n', 'asc');
  // ASCII 的卡名排在漢字前面(No.39 希望皇 霍普)
  assert.strictEqual(asc[0], 84013237);
  // 同前綴的兩張照第三個字:白 < 究
  assert.ok(asc.indexOf(89631139) < asc.indexOf(23995346));
  assert.deepStrictEqual(sorted('n', 'desc'), asc.slice().reverse());
});

test('卡片密碼升降序', () => {
  const asc = CARDS.map(c => c.id).sort((a, b) => a - b);
  assert.deepStrictEqual(sorted('id', 'asc'), asc);
  assert.deepStrictEqual(sorted('id', 'desc'), asc.slice().reverse());
});

test('升降序對稱:有值與空值兩批各自反轉,空值永遠在後', () => {
  const has = id => NO_ATK.indexOf(id) < 0;
  const asc = sorted('atk', 'asc');
  const desc = sorted('atk', 'desc');
  assert.deepStrictEqual(desc.filter(has), asc.filter(has).slice().reverse());
  assert.deepStrictEqual(desc.filter(id => !has(id)),
                         asc.filter(id => !has(id)).slice().reverse());
});

test('排序穩定:相同鍵值的卡順序不隨執行、不隨輸入順序變動', () => {
  // 決勝一律落到卡片密碼(唯一鍵),比較函式因此是全序——排序結果不靠
  // Array#sort 是不是穩定排序,輸入順序也影響不了它
  const box = harness.load({ cards: CARDS.slice().reverse(), vocab: VOCAB, meta: META });
  for (const [key, dir] of [['dom', ''], ['atk', 'desc'], ['atk', 'asc'],
                            ['lv', 'desc'], ['n', 'asc']]) {
    assert.deepStrictEqual(harness.sortedIds(box, {}, key, dir), sorted(key, dir));
    assert.deepStrictEqual(sorted(key, dir), sorted(key, dir));
  }
});

test('排序不改變命中集合:重排的輸入就是同一份搜尋結果', () => {
  const q = { cat: { m: 1 }, text: '發動' };
  const asc = (a, b) => a - b;
  const hit = ids(q).slice().sort(asc);
  for (const [key, dir] of [['dom', ''], ['atk', 'desc'], ['n', 'asc']]) {
    assert.deepStrictEqual(sorted(key, dir, q).slice().sort(asc), hit);
  }
});

test('排序選單的鍵清單:領域序沒有方向,單鍵各帶預設方向', () => {
  const keys = harness.sortKeys(sandbox);
  assert.deepStrictEqual(keys.map(k => k.key), ['dom', 'atk', 'df', 'lv', 'n', 'id']);
  // 第一筆是預設的排序(領域序),而且它沒有方向可切
  assert.strictEqual(keys[0].dir, '');
  // 其餘各有中文名與預設方向:問「最高攻擊力的是哪張」的人選了攻擊力就該看到最高的
  assert.ok(keys.slice(1).every(k => k.zh && (k.dir === 'asc' || k.dir === 'desc')));
  assert.strictEqual(keys.find(k => k.key === 'atk').dir, 'desc');
  assert.strictEqual(keys.find(k => k.key === 'n').dir, 'asc');
});

/* ── 網址狀態(票08) ─────────────────────────────────────
   編解碼是純的,所以測得到:條件物件進去、字串出來、再解析回來還是同一個物件。
   **往返正是分享出去的網址的全部內容**——在對方那邊還原不回同一個查詢的話,
   這一票就沒有做到任何事。寫入時機、`hashchange` 與瀏覽器歷史測不到(沙箱裡
   沒有 location 也沒有歷史),走人工驗收。 */

const hashOf = st => harness.hash(sandbox, st);
const parseHash = h => harness.parseHash(sandbox, h);
const canon = h => harness.canonHash(sandbox, h);

/* 空條件的正規形:三個關鍵字框空著、卡名語言是預設的中文、排序是領域序。
   側欄什麼都沒設時 `Query.read()` 吐的就是這個形狀。 */
const EMPTY_Q = { name: '', nameLang: 'zh', code: '', text: '' };
const DOM_SORT = { key: 'dom', dir: '' };

/* 涵蓋各種條件形狀:三態的包含與排除、跨側的子類型、只給一邊的範圍、刻度 0、
   攻守 `?` 的兩個方向、卡名語言、排序鍵與方向。 */
const STATES = [
  { q: { ...EMPTY_Q }, sort: DOM_SORT },
  { q: { ...EMPTY_Q, name: '青眼%龍', nameLang: 'ja', code: '46986414',
         text: '墓地%特殊召喚' },
    sort: DOM_SORT },
  { q: { ...EMPTY_Q, cat: { m: 1, t: -1 },
         sub: { 'm:fusion': 1, 'm:normal': -1, 's:quick': 1 },
         attr: { dark: 1, light: 1 }, race: { dragon: -1 } },
    sort: { key: 'atk', dir: 'desc' } },
  { q: { ...EMPTY_Q, kind: { q: 1, i: -1 }, opt: { m: 1 },
         lv: { min: 4, max: null }, lk: { min: null, max: 3 },
         sc: { min: 0, max: 0 }, atk: { min: 2500, max: null }, atkq: 1,
         df: { min: null, max: 2000 }, dfq: -1 },
    sort: { key: 'lv', dir: 'asc' } },
  { q: { ...EMPTY_Q, lm: { L: 1, R: -1 }, rarity: { UR: 1 }, ot: { o: -1 },
         gy: { min: 5, max: 20 } },
    sort: { key: 'n', dir: 'asc' } },
];

test('任意條件組合序列化後再解析回來相等(往返,含三態排除)', () => {
  for (const st of STATES) {
    assert.deepStrictEqual(parseHash(hashOf(st)), st);
    // 字串那一側也要是正規形:同一個狀態只有一種寫法,兩份網址因此比得出來
    assert.strictEqual(canon(hashOf(st)), hashOf(st));
  }
});

test('條件經過網址一趟回來,引擎得到同一批卡', () => {
  // 往返相等的意義在這裡:解析出來的 q 就是接縫 3 吃的形狀,不必再翻譯一次
  const q = { name: '青眼', cat: { m: 1 }, attr: { light: 1 },
              atk: { min: 2000, max: null } };
  const back = parseHash(hashOf({ q, sort: DOM_SORT })).q;
  assert.ok(ids(q).length);              // 空集合的相等問不出東西
  assert.deepStrictEqual(ids(back), ids(q));
});

test('三態的三個狀態雙向可編碼', () => {
  const h = hashOf({ q: { ...EMPTY_Q, attr: { dark: 1, light: -1 } }, sort: DOM_SORT });
  // 排除帶 `-` 前綴;碼照值域的宣告序寫(光在闇之前)
  assert.strictEqual(h, 'attr=-light,dark');
  const back = parseHash(h).q.attr;
  assert.deepStrictEqual(back, { light: -1, dark: 1 });
  // 未選的碼不進網址,也不會在還原時變成「未選」以外的東西
  assert.ok(!('earth' in back));
});

test('網址不隨點擊順序而變', () => {
  // 碼照宣告序寫而不是照使用者點出來的順序:同一組條件只有一個網址,
  // 兩個人比得出來查的是不是同一件事
  const of = attr => hashOf({ q: { ...EMPTY_Q, attr }, sort: DOM_SORT });
  assert.strictEqual(of({ dark: 1, light: 1 }), of({ light: 1, dark: 1 }));
});

test('排序狀態進網址,預設的領域序不寫', () => {
  const st = sort => hashOf({ q: EMPTY_Q, sort });
  assert.strictEqual(st({ key: 'dom', dir: '' }), '');
  // 方向與該鍵的預設方向相同時省略——網址短一點,而解析時補得回來
  assert.strictEqual(st({ key: 'atk', dir: 'desc' }), 'sort=atk');
  assert.strictEqual(st({ key: 'atk', dir: 'asc' }), 'sort=atk&dir=asc');
  assert.deepStrictEqual(parseHash('sort=atk').sort, { key: 'atk', dir: 'desc' });
  // 領域序沒有方向:硬寫一個進去也還原不成「領域序＋降序」那種不存在的狀態
  assert.deepStrictEqual(parseHash('sort=dom&dir=desc').sort, DOM_SORT);
});

test('空條件的網址是空的', () => {
  assert.strictEqual(hashOf({ q: EMPTY_Q, sort: DOM_SORT }), '');
  assert.deepStrictEqual(parseHash(''), { q: EMPTY_Q, sort: DOM_SORT });
  assert.deepStrictEqual(parseHash('#'), { q: EMPTY_Q, sort: DOM_SORT });
});

test('壞掉或過期的網址不讓頁面崩掉,忽略該段條件', () => {
  const good = 'name=' + encodeURIComponent('青眼') + '&attr=dark';
  const bad = [
    'zzz=1',                     // 認不得的欄位名
    'attr=nosuchattr',           // 值不在值域裡
    'attr=',                     // 空值
    'attr=-',                    // 只有一個減號
    'cat=m:fusion',              // 帶了不該有的側前綴
    'sub=fusion',                // 子類型少了大類前綴(跨側重複的碼因此認不得)
    'lv=abc', 'lv=', 'atk=x-y',  // 壞掉的範圍
    'atkq=9',                    // 三態以外的值
    'sort=nosuchkey', 'dir=sideways',
    'name=%E9%9D',               // 壞掉的百分比編碼
    'noequalsign', '', '%', '=1',
  ];
  for (const seg of bad) {
    const st = parseHash(good + '&' + seg);
    // 壞掉的那一段被忽略,其餘條件照常生效
    assert.deepStrictEqual(st.q.name, '青眼', seg);
    assert.deepStrictEqual(st.q.attr, { dark: 1 }, seg);
    assert.deepStrictEqual(st.sort, DOM_SORT, seg);
    // 而且忽略是真的忽略:壞掉的段不在條件物件裡留下任何殘骸
    assert.deepStrictEqual(st, parseHash(good), seg);
  }
});

test('正規化過的網址認得出是同一個狀態(自寫的 hash 不重跑搜尋)', () => {
  const st = { q: { ...EMPTY_Q, name: '青眼', text: '墓地' },
               sort: { key: 'atk', dir: 'desc' } };
  const written = hashOf(st);
  // 瀏覽器對 hash 的百分比編碼各有各的作法(有的原樣留著、有的編起來),
  // 拿字串直接比會把自己剛寫進去的那一個看成別人改的——那就是同一次搜尋跑兩遍
  const raw = decodeURIComponent(written);
  assert.notStrictEqual(raw, written);
  assert.strictEqual(canon(raw), written);
  assert.strictEqual(canon('#' + written), written);
  // 段的順序不同、寫了可省略的預設值,都收斂到同一個字串
  assert.strictEqual(
    canon('nameLang=zh&sort=atk&dir=desc&text=' + encodeURIComponent('墓地')
          + '&name=' + encodeURIComponent('青眼')),
    written);
});

/* ── 窄螢幕的條件摘要(票09) ───────────────────────────────
   手機上側欄是**摺起來**的,而摺起來就看不見自己設了什麼——摺疊鈕上因此寫著
   還有幾條條件在生效。數字算錯不會報錯也不會白屏,只是使用者拿著一批被篩過、
   卻沒有任何理由的結果,所以這條規則測得到:它是純的,DOM 那一層只是寫上去。
   版面本身(斷點、摺疊、單欄卡片)不測,走人工驗收(spec 的 Testing Decisions)。 */

const critCount = q => harness.critCount(sandbox, q);

test('條件數:空條件是 0,卡名語言不是一條條件', () => {
  assert.strictEqual(critCount({}), 0);
  assert.strictEqual(critCount(EMPTY_Q), 0);
  // 語言只是「卡名那一格拿哪一種卡名比」,算進去的話清空條件之後鈕面仍寫著 1
  assert.strictEqual(critCount({ ...EMPTY_Q, nameLang: 'ja' }), 0);
  assert.strictEqual(critCount({ ...EMPTY_Q, name: '青眼', nameLang: 'ja' }), 1);
});

test('條件數算的是軸,不是點亮的按鈕', () => {
  // 屬性點三顆是一條條件(軸內 OR),寫成 3 會看起來像三道篩子
  assert.strictEqual(critCount({ ...EMPTY_Q, attr: { dark: 1, light: 1, water: 1 } }), 1);
  // 排除也是設了條件
  assert.strictEqual(critCount({ ...EMPTY_Q, attr: { dark: -1 } }), 1);
  // 一顆都沒點的軸不算(壞掉的網址解出來的空殼同理)
  assert.strictEqual(critCount({ ...EMPTY_Q, attr: {} }), 0);
  assert.strictEqual(critCount({ ...EMPTY_Q, name: '青眼', text: '墓地',
                                 cat: { m: 1 }, race: { dragon: 1 } }), 4);
});

test('條件數:只給一邊的範圍與攻守 `?` 各自算一條', () => {
  assert.strictEqual(critCount({ ...EMPTY_Q, atk: { min: 2500, max: null } }), 1);
  assert.strictEqual(critCount({ ...EMPTY_Q, atk: { min: null, max: 2500 } }), 1);
  // 刻度 0 與「攻擊力 0 以上」是真的值,不是「沒設」
  assert.strictEqual(critCount({ ...EMPTY_Q, sc: { min: 0, max: 0 } }), 1);
  assert.strictEqual(critCount({ ...EMPTY_Q, atk: { min: 0, max: null } }), 1);
  // 兩邊都空的範圍(壞網址的殘骸)不算
  assert.strictEqual(critCount({ ...EMPTY_Q, atk: { min: null, max: null } }), 0);
  // `?` 是第三種值、與數值範圍分開的一條
  assert.strictEqual(critCount({ ...EMPTY_Q, atk: { min: 2500, max: null }, atkq: 1 }), 2);
  assert.strictEqual(critCount({ ...EMPTY_Q, dfq: -1 }), 1);
});

test('條件數在網址走一趟之後不變(分享的連結在手機上摺著開)', () => {
  for (const st of STATES) {
    assert.strictEqual(critCount(parseHash(hashOf(st)).q), critCount(st.q),
                       JSON.stringify(st.q));
  }
  // 加一條條件軸,摺疊鈕自動算得到它——條件數不必跟著 FIELDS 抄第二份
  assert.strictEqual(critCount(parseHash('attr=dark&lv=4-&sort=atk').q), 2);
});
