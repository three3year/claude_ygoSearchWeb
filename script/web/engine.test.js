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
  // 誘發的必發與選發各一句:怪獸側組合鈕(spec-optional-combo)的對照組——
  // 同一張卡兩顆組合鈕各中一句,「同句成立」從命中行分得出來
  {
    id: 20105, n: '儀式怪獸樣本卡', c: 'm', s: ['ritual', 'effect'],
    at: 'light', r: 'fairy', lv: 6, atk: 2000, df: 1700,
    tx: ['①：這張卡儀式召喚成功時發動。把對方場上1張卡破壞。',
         '②：這張卡被解放的場合發動。可以從牌組抽1張卡。'],
    k: ['t', 't'], o: ['m', 'o'],
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
  // 四行各一種 role:素材指定由 textMat 開關決定掃不掃,召喚條件與使用次數限制照掃
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

  // 跨類型魔陷效果(ADR-0010):怪獸「當作裝備魔法卡」的效果句 kind 是 se,
  // 自身卡片種類與值不一致——「裝備魔法卡效果」按鈕唯一該收的形狀
  {
    id: 20113, n: '裝備怪獸樣本卡', c: 'm', s: ['effect'],
    at: 'wind', r: 'warrior', lv: 3, atk: 900, df: 600,
    tx: ['①：選場上1隻怪獸，把這張卡當作攻擊力上升500的裝備卡裝備。'],
    k: ['se'],
  },
  // 本類:裝備魔法卡自己的裝備魔法卡效果是卡片種類的重言,按鈕不收
  {
    id: 20114, n: '裝備魔法樣本卡', c: 's', s: ['equip'],
    tx: ['①：裝備怪獸的攻擊力上升500。'],
    k: ['se'],
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
           items: [item('normal', '通常'), item('quick', '速攻'),
                   item('equip', '裝備'), item('ritual', '儀式')] },
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
                  item('sr', '儀式魔法卡效果'), item('se', '裝備魔法卡效果'),
                  item('sp', '靈擺魔法卡效果'), item('tn', '通常陷阱卡效果'),
                  item('tc', '永續陷阱卡效果')],
          groups: [{ zh: '怪獸側', codes: ['x', 'c', 'q', 't', 'i'] },
                   { zh: '跨類型魔陷效果',
                     codes: ['sn', 'sr', 'se', 'sp', 'tn', 'tc'] }],
          // 本類對應(ADR-0010):跨類型排除照它判,由值域正典宣告、隨 VOCAB 出去
          own: { sn: 's:normal', sr: 's:ritual', se: 's:equip',
                 sp: 'm:pendulum', tn: 't:normal', tc: 't:continuous' } },
  // 承載關係與怪獸側組合鈕都住在值域正典(CONTEXT.md「必發/選發」、
  // spec-optional-combo):只有誘發即時(2速)、誘發(1速)與魔陷卡效果十值承載;
  // 組合鈕 = 「同一句是該效果類型且帶該值」,由 combos 宣告命中規則
  optional: { zh: '必發/選發',
              items: [item('m', '必發'), item('o', '選發'),
                      item('qm', '誘發即時(必發)'), item('qo', '誘發即時(選發)'),
                      item('tm', '誘發(必發)'), item('to', '誘發(選發)')],
              groups: [{ zh: '全部', codes: ['m', 'o'] },
                       { zh: '怪獸側', codes: ['qm', 'qo', 'tm', 'to'] }],
              combos: { qm: 'q:m', qo: 'q:o', tm: 't:m', to: 't:o' },
              carriers: ['q', 't', 'sn', 'sr', 'se', 'sp', 'tn', 'tc'] },
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

test('效果文關鍵字預設不掃 role = 素材指定 的行', () => {
  // 574 張融合怪獸的素材寫法會把真正的答案淹掉,所以預設不掃
  assert.deepStrictEqual(ids({ text: '融合' }), []);
  assert.deepStrictEqual(ids({ text: '惡魔族' }), []);
  // 「怪獸」出現在四張卡的素材行裡,一張都不該因此命中
  assert.deepStrictEqual(ids({ text: '怪獸' }),
                         [20102, 20104, 20106, 20107, 20108, 20113, 20114]);
  // 副作用:效果文框搜「青眼白龍」撈不到把它寫在素材行的融合怪獸(開關才撈得到)
  assert.deepStrictEqual(ids({ text: '青眼白龍' }), []);
  assert.deepStrictEqual(ids({ name: '青眼白龍' }), [89631139]);
});

test('勾了素材行開關(textMat),素材指定行照掃', () => {
  // 2026-08-21 使用者裁示:原本的固定規則改成效果文框旁的勾選開關
  assert.deepStrictEqual(ids({ text: '融合', textMat: 1 }), [20109]);
  assert.deepStrictEqual(ids({ text: '惡魔族', textMat: 1 }), [20109]);
  assert.deepStrictEqual(ids({ text: '怪獸', textMat: 1 }),
                         [84013237, 20101, 20102, 20104, 20106, 20107, 20108,
                          20109, 20113, 20114]);
  assert.deepStrictEqual(ids({ text: '青眼白龍', textMat: 1 }), [23995346]);
  assert.deepStrictEqual(rowsOf({ text: '青眼白龍', textMat: 1 }, 23995346), [0]);
  // 開關只影響素材行:非素材行的命中兩種狀態一樣
  assert.deepStrictEqual(ids({ text: '墓地', textMat: 1 }), [20107, 20108]);
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
                  20101, 20102, 20103, 20105, 20109, 20110, 20111, 20113];
const NON_MONSTERS = [483, 10000, 20104, 20106, 20107, 20108, 20112, 20114];

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
                         [2511, 20101, 20102, 20103, 20105, 20109, 20110, 20111,
                          20113]);
  assert.deepStrictEqual(ids({ sub: { 'm:effect': 1, 'm:link': -1 } }),
                         [2511, 20102, 20103, 20105, 20109, 20110, 20111, 20113]);
  // 排除寫在包含前面或後面都一樣(不能只在寫法順序上成立)
  assert.deepStrictEqual(ids({ sub: { 'm:link': -1, 'm:effect': 1 } }),
                         [2511, 20102, 20103, 20105, 20109, 20110, 20111, 20113]);
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
  assert.deepStrictEqual(ids({ atk: { max: 1200 } }), [2511, 20101, 20113]);
  assert.deepStrictEqual(ids({ df: { min: 0, max: 2000 } }),
                         [2511, 84013237, 20102, 20105, 20109, 20113]);
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
  assert.deepStrictEqual(ids({ cat: { m: 1 }, text: '怪獸' }), [20102, 20113]);
  assert.deepStrictEqual(ids({ cat: { m: 1 }, text: '怪獸', textMat: 1 }),
                         [84013237, 20101, 20102, 20109, 20113]);
  assert.deepStrictEqual(ids({ name: '青眼', race: { dragon: 1 }, lv: { min: 10 } }),
                         [23995346]);
});

/* ── 效果類型與必發/選發軸(票06) ──────────────────────
   [[效果標記表]]花了 20 多張判定票判出來的效果類型,到這一票才有使用者。
   句層耦合是這一段的核心:效果文關鍵字與效果類型**必須命中同一個效果句**。 */

test('效果類型可篩選,軸內 OR、軸間 AND、三態排除', () => {
  assert.deepStrictEqual(ids({ kind: { q: 1 } }), [2511, 20110, 20111]);
  assert.deepStrictEqual(ids({ kind: { i: 1 } }), [20102, 20103, 20110]);
  assert.deepStrictEqual(ids({ kind: { q: 1, i: 1 } }),
                         [2511, 20102, 20103, 20110, 20111]);
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
  assert.deepStrictEqual(rowsOf({ kind: { se: 1 } }, 20113), [0]);
  // 沒有效果句的純通常怪獸不被效果類型條件命中(故事文不是效果)
  assert.deepStrictEqual(ids({ kind: { x: 1 } }).includes(46986414), false);
});

/* ── 跨類型魔陷效果(ADR-0010) ──────────────────────────
   魔陷十值的成員 = 帶該值效果句、且自身[[卡片種類]]與該值**不一致**的卡。
   本類卡(裝備魔法卡之於裝備魔法卡效果)是卡片種類的重言——「所有裝備魔法卡」
   歸子類型軸,這個軸只答「誰以別的卡種做出這種效果」。一致對應由值域正典宣告
   (`VOCAB.kind.own`),引擎不自帶第二份表。 */

test('跨類型才是成員:本類卡不被自己的效果類型命中', () => {
  // 怪獸當作裝備卡(跨類型)命中;裝備魔法卡自身(本類)不命中
  assert.deepStrictEqual(ids({ kind: { se: 1 } }), [20113]);
  // 全庫只剩本類卡的值:條件設出來就是零結果(建置期會把這種按鈕拿掉)
  assert.deepStrictEqual(ids({ kind: { sr: 1 } }), []);
  assert.deepStrictEqual(ids({ kind: { tn: 1 } }), []);
  assert.deepStrictEqual(ids({ kind: { sn: 1 } }), []);
  assert.deepStrictEqual(ids({ kind: { tc: 1 } }), []);
});

test('靈擺怪獸之於靈擺魔法卡效果算本類', () => {
  // 20102 是靈擺怪獸,靈擺效果句的 kind 是 sp——照字面比對(怪獸卡≠靈擺魔法卡)
  // 它會命中,而那會讓 sp 鈕變回「全部有靈擺效果的靈擺怪獸」
  assert.deepStrictEqual(ids({ kind: { sp: 1 } }), []);
});

test('排除態同用新定義:本類卡的效果句不受該值的排除影響', () => {
  // 排除「裝備魔法卡效果」擋的是**跨類型**的 se 句:20113 唯一一句被擋 → 不命中;
  // 裝備魔法卡(20114)自身的 se 句不在成員裡,照常通過
  const out = ids({ kind: { se: -1 } });
  assert.strictEqual(out.includes(20113), false);
  assert.strictEqual(out.includes(20114), true);
});

test('跨類型也走句層耦合:關鍵字與效果類型命中同一句', () => {
  // 20113 與 20114 的效果文都寫著「裝備」,但 se 的成員只有跨類型那張
  assert.deepStrictEqual(ids({ text: '裝備' }), [20113, 20114]);
  assert.deepStrictEqual(ids({ text: '裝備', kind: { se: 1 } }), [20113]);
  assert.deepStrictEqual(rowsOf({ text: '裝備', kind: { se: 1 } }, 20113), [0]);
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
  assert.deepStrictEqual(ids({ opt: { m: 1 } }), [20105, 20112]);
  assert.deepStrictEqual(ids({ opt: { o: 1 } }), [20105, 20110, 20111, 20112]);
  assert.deepStrictEqual(rowsOf({ opt: { m: 1 } }, 20112), [0]);
  assert.deepStrictEqual(rowsOf({ opt: { o: 1 } }, 20112), [1]);
  // 永續效果不承載這個屬性:「永續效果是必發」永遠零結果(所以 UI 不讓它設出來)
  assert.deepStrictEqual(ids({ kind: { c: 1 } }), [20109]);
  assert.deepStrictEqual(ids({ kind: { c: 1 }, opt: { m: 1 } }), []);
  // 承載型的效果類型但這一句沒有值:不被必發命中,也不被「排除必發」排掉
  assert.deepStrictEqual(ids({ opt: { m: 1 } }).includes(20101), false);
  assert.deepStrictEqual(rowsOf({ kind: { t: 1 }, opt: { m: -1 } }, 20101), [1]);
});

/* ── 怪獸側組合鈕(spec-optional-combo) ─────────────────
   組合鈕 = 「同一[[效果句]]是該效果類型**且**帶該值」的單一條件,與全部組的
   必發/選發同一軸。命中規則由值域正典的 combos 宣告,引擎不自帶第二份表。 */

test('組合鈕的包含:同一句是該效果類型且帶該值才命中', () => {
  assert.deepStrictEqual(ids({ opt: { tm: 1 } }), [20105]);
  assert.deepStrictEqual(rowsOf({ opt: { tm: 1 } }, 20105), [0]);
  assert.deepStrictEqual(ids({ opt: { to: 1 } }), [20105]);
  assert.deepStrictEqual(rowsOf({ opt: { to: 1 } }, 20105), [1]);
  assert.deepStrictEqual(ids({ opt: { qo: 1 } }), [20110, 20111]);
  // 全庫沒有 q+必發 的句子(真實資料也只有 16 張):零結果是資料的形狀,不是壞
  assert.deepStrictEqual(ids({ opt: { qm: 1 } }), []);
  // 效果類型不合的不命中:20112 的必發句是通常陷阱卡效果,不是誘發
  assert.deepStrictEqual(ids({ opt: { tm: 1 } }).includes(20112), false);
  // 承載型效果類型但這一句沒有值:組合的包含同樣碰不到它(20101 的誘發句無值)
  assert.deepStrictEqual(ids({ opt: { to: 1 } }).includes(20101), false);
});

test('組合鈕的排除:這一句不是「該類型且該值」', () => {
  // 全部必發包含+怪獸側必發排除 = 魔陷側必發(spec 不補魔陷側組的理由)
  assert.deepStrictEqual(ids({ opt: { m: 1, tm: -1 } }), [20112]);
  assert.deepStrictEqual(rowsOf({ opt: { m: 1, tm: -1 } }, 20112), [0]);
  // 排除 tm 不擋 t+選發(20105 ②)也不擋 q+選發(20110 ①、20111)
  assert.deepStrictEqual(ids({ opt: { o: 1, tm: -1 } }),
                         [20105, 20110, 20111, 20112]);
  // 排除 to 不擋 q+選發,擋的只有 t+選發那一句(20105 因此整卡不中)
  assert.deepStrictEqual(ids({ opt: { o: 1, to: -1 } }), [20110, 20111, 20112]);
  // 無值的句子不被組合的排除擋(20101 的誘發句無值,排除 to 之後照樣通過 kind 條件)
  assert.deepStrictEqual(rowsOf({ kind: { t: 1 }, opt: { to: -1 } }, 20101), [1]);
});

test('組合鈕與效果文關鍵字同句耦合', () => {
  // 20105 ① 有「破壞」且是 t+必發;② 有「抽1張」但是 t+選發
  assert.deepStrictEqual(ids({ text: '破壞', opt: { tm: 1 } }), [20105]);
  assert.deepStrictEqual(rowsOf({ text: '破壞', opt: { tm: 1 } }, 20105), [0]);
  // 關鍵字在 ①、組合在 ②:不同句不命中
  assert.deepStrictEqual(ids({ text: '破壞', opt: { to: 1 } }), []);
});

test('組合鈕與效果類型軸的細粒度矛盾不設防:誠實零結果', () => {
  // 同一句不可能同時是誘發即時與誘發——組可見時設出這種矛盾,句層 AND 給零
  assert.deepStrictEqual(ids({ kind: { q: 1 }, opt: { tm: 1 } }), []);
  // 一致的組合照常運作
  assert.deepStrictEqual(ids({ kind: { t: 1 }, opt: { tm: 1 } }), [20105]);
});

test('必發/選發與效果文也走同一個效果句', () => {
  assert.deepStrictEqual(ids({ text: '除外', opt: { o: 1 } }), [20111]);
  assert.deepStrictEqual(ids({ text: '除外', opt: { m: 1 } }), []);
});

test('效果類型條件掃得到素材指定行,效果文關鍵字看 textMat 開關', () => {
  // 不掃素材行是**關鍵字**的預設,不是「素材行不存在」:效果類型照樣看得到它
  assert.deepStrictEqual(rowsOf({ kind: { x: 1 } }, 20109), [0, 1, 2]);
  assert.deepStrictEqual(ids({ kind: { x: 1 }, text: '融合' }), []);
  // 勾了開關,素材行同樣走句層耦合
  assert.deepStrictEqual(ids({ kind: { x: 1 }, text: '融合', textMat: 1 }), [20109]);
  assert.deepStrictEqual(rowsOf({ kind: { x: 1 }, text: '融合', textMat: 1 }, 20109),
                         [0]);
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

test('必發/選發的兩組各自只在承載的效果類型被選時出得來(粒度是組)', () => {
  // 回傳與 VOCAB.optional.groups 對齊的布林陣列:[全部, 怪獸側]
  const avail = sel => harness.optionalAvailable(sandbox, sel);
  // 一顆效果類型都沒選:「必發」「誘發(必發)」自己就是有結果的條件,兩組都在
  assert.deepStrictEqual(avail(null), [true, true]);
  assert.deepStrictEqual(avail({}), [true, true]);
  // 選的全是不承載的類型 → 兩組都收(「永續效果是必發」永遠零結果)
  assert.deepStrictEqual(avail({ c: 1 }), [false, false]);
  assert.deepStrictEqual(avail({ c: 1, i: 1, x: 1 }), [false, false]);
  // 誘發即時/誘發是兩組共同的承載者:都出得來
  assert.deepStrictEqual(avail({ q: 1 }), [true, true]);
  assert.deepStrictEqual(avail({ c: 1, t: 1 }), [true, true]);
  // 魔陷值只承載「全部」組:怪獸側組收起(「通常陷阱卡效果 + 誘發(必發)」
  // 是同一句不可能成立的條件,組粒度的連動隱藏把它擋在門外)
  assert.deepStrictEqual(avail({ tn: 1 }), [true, false]);
  assert.deepStrictEqual(avail({ se: 1, c: 1 }), [true, false]);
  // 排除不是「已選」:排除永續效果之後,命中的句子仍然可能是承載型的
  assert.deepStrictEqual(avail({ c: -1 }), [true, true]);
  assert.deepStrictEqual(avail({ q: -1 }), [true, true]);
  assert.deepStrictEqual(avail({ tn: 1, t: -1 }), [true, false]);
});

/* ── 按鈕由值域正典生成 ────────────────────────────────
   沙箱裡沒有真的 DOM,而 DOM 那一層只是照這份清單擺按鈕——清單是這條性質
   測得到的形狀(ADR-0008)。 */

test('分類類條件的按鈕清單由 window.VOCAB 導出', () => {
  const axes = harness.axes(sandbox);
  assert.deepStrictEqual(axes.map(a => a.key + '/' + a.side),
                         ['cat/', 'kind/', 'opt/', 'sub/m', 'sub/s', 'sub/t',
                          'attr/', 'race/', 'lm/', 'rarity/', 'ot/']);
  // 效果類型十六值分怪獸側與跨類型魔陷效果兩組呈現(Story 23、ADR-0010):
  // 十六顆鈕排在一起時,使用者要看得出哪些是同一個維度的東西
  assert.deepStrictEqual(axes.find(a => a.key === 'kind').groups.map(g => g.zh),
                         ['怪獸側', '跨類型魔陷效果']);
  const race = axes.find(a => a.key === 'race');
  // 軸標題也來自值域(HTML 連軸叫什麼名字都不知道)
  assert.strictEqual(race.zh, VOCAB.race.zh);
  assert.deepStrictEqual(race.groups[0].items.map(i => i.code),
                         VOCAB.race.items.map(i => i.code));
  // 有分組的值域照分組排,沒有分組的整批一組、組名留空
  assert.deepStrictEqual(axes.find(a => a.side === 'm').groups.map(g => g.zh), ['卡框']);
  assert.deepStrictEqual(race.groups.map(g => g.zh), ['']);
});

test('必發/選發軸由 VOCAB 長出兩組六顆(spec-optional-combo)', () => {
  const opt = harness.axes(sandbox).find(a => a.key === 'opt');
  assert.deepStrictEqual(opt.groups.map(g => g.zh), ['全部', '怪獸側']);
  assert.deepStrictEqual(opt.groups[0].items.map(i => i.code), ['m', 'o']);
  assert.deepStrictEqual(opt.groups[1].items.map(i => i.code),
                         ['qm', 'qo', 'tm', 'to']);
  // 鈕面由正典的中文宣告而來,省略「效果」與速度標注
  assert.deepStrictEqual(opt.groups[1].items.map(i => i.zh),
                         ['誘發即時(必發)', '誘發即時(選發)',
                          '誘發(必發)', '誘發(選發)']);
  assert.strictEqual(opt.states, 3);
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

/* ── 大類兩態(票12) ────────────────────────────────────
   大類只有三值,排除某一類等同勾選其餘兩類——排除態是冗餘的,而且誤入排除態
   會讓子類組整組收起。態數是**軸宣告的一部分**(不是點擊處理裡的大類特例):
   DOM 那一層照宣告循環,所以宣告與循環規則都是純的、測得到。 */

test('態數是軸宣告的一部分:大類兩態,其餘軸三態', () => {
  const axes = harness.axes(sandbox);
  assert.strictEqual(axes.find(a => a.key === 'cat').states, 2);
  // 其他每一軸(含子類型三段)都維持三態——兩態化只發生在宣告了 2 的軸上
  axes.filter(a => a.key !== 'cat').forEach(a => {
    assert.strictEqual(a.states, 3, a.key + '/' + a.side);
  });
});

test('怪獸參數軸掛在大類「怪獸」的連動上(宣告可測)', () => {
  // 屬性/種族/連結標記是怪獸才有的參數(範圍軸的等級/攻守等同理,但 axes()
  // 只列三態軸):大類沒選怪獸時它們藏著——宣告寫在軸清單上,DOM 照它藏
  const axes = harness.axes(sandbox);
  ['attr', 'race', 'lm'].forEach(k =>
    assert.strictEqual(axes.find(a => a.key === k).mon, true, k));
  // 全卡種通用的軸不掛:效果類型、必發/選發、大類自己、稀有度、OCG・TCG
  ['kind', 'opt', 'cat', 'rarity', 'ot'].forEach(k =>
    assert.strictEqual(axes.find(a => a.key === k).mon, false, k));
});

test('狀態循環照宣告走:兩態兩次點擊回到未選,三態維持三段', () => {
  const next = (st, states) => harness.nextState(sandbox, st, states);
  // 兩態:未選 ⇄ 選取,永遠碰不到排除
  assert.strictEqual(next('', 2), 'in');
  assert.strictEqual(next('in', 2), '');
  // 三態:未選 → 包含 → 排除 → 未選
  assert.strictEqual(next('', 3), 'in');
  assert.strictEqual(next('in', 3), 'ex');
  assert.strictEqual(next('ex', 3), '');
});

/* ── 排序 ──────────────────────────────────────────────
   排序與搜尋解耦:比較函式只看卡片物件,重排走的是同一份已經命中的結果。
   下面每一條都跑「查詢 → 排序」這條真實的路徑(harness.sortedIds)。 */

const sorted = (key, dir, q) => harness.sortedIds(sandbox, q || {}, key, dir);

/* 主資料集裡沒有這幾個參數的卡。攻守的空值有兩種來源,兩種都不是數值:
   非怪獸根本沒有那個欄位,而 20103 的攻守是 `?`(負的哨兵值)。 */
const NO_ATK = [483, 10000, 20103, 20104, 20106, 20107, 20108, 20112, 20114];
const NO_DF = [483, 10000, 20101, 20103, 20104, 20106, 20107, 20108, 20112,
               20114];
const NO_LV = [483, 10000, 20101, 20104, 20106, 20107, 20108, 20112, 20114];

test('預設是領域序:七層比較', () => {
  // 大類(怪獸→魔法→陷阱)→ 卡框序 → 靈擺排後 → 等級高到低 → 屬性 → 種族 → 密碼。
  // 怪獸側:通常(青眼 lv8、黑魔導 lv7)→ 效果(lv10、5、5、1)→ 效果靈擺 →
  // 融合(lv12、8)→ 儀式 → 超量 → 連結;20110/20111 同屬性同種族同等級,由密碼決勝。
  const DOMAIN = [
    89631139, 46986414,                     // 通常怪獸,等級高到低
    20103, 20110, 20111, 20113, 2511,       // 效果怪獸
    20102,                                  // 效果靈擺(靈擺是卡框內的平手條件,不離開效果那一團)
    23995346, 20109,                        // 融合
    20105,                                  // 儀式
    84013237,                               // 超量
    20101,                                  // 連結
    20107, 20108, 483, 20114, 20106,        // 魔法:通常 → 速攻 → 裝備 → 儀式
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
            item('pendulum', '靈擺'), item('tuner', '協調')],
    groups: [{ zh: '卡框', codes: ['normal', 'effect', 'synchro', 'pendulum'] },
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

test('靈擺是卡框內的平手條件:同步靈擺站在同步那一團的最後', () => {
  const cards = [
    mon(1, ['effect'], 'earth', 'warrior'),
    mon(2, ['effect', 'pendulum'], 'earth', 'warrior'),
    mon(3, ['effect', 'synchro'], 'earth', 'warrior'),
    mon(4, ['effect', 'synchro', 'pendulum'], 'earth', 'warrior'),
  ];
  const box = harness.load({ cards, vocab: ORDER_VOCAB, meta: {} });
  // 卡框先分團(效果 → 同步),團內非靈擺在前、靈擺在後——同步靈擺不會
  // 因為卡框取到宣告序最後的「靈擺」而離開同步那一團
  assert.deepStrictEqual(harness.sortedIds(box, {}, 'dom', ''), [1, 2, 3, 4]);
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
  // 4500 → 3000 → 2800 → 2500 兩張 → 2000 → 1800 兩張 → 1500 → 1200 → 0。
  // 平手落回預設序:攻 2500 的通常怪獸(46986414)站在超量(84013237)前,
  // 攻 1800 的兩張(20110/20111)整條預設序同到密碼才分勝負
  assert.deepStrictEqual(sorted('atk', 'desc').slice(0, 11),
    [23995346, 89631139, 20109, 46986414, 84013237, 20105, 20110, 20111,
     20102, 20101, 20113]);
  assert.deepStrictEqual(sorted('atk', 'asc').slice(0, 3), [2511, 20113, 20101]);
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
  // 守 2200 的兩張(20110/20111)平手,照預設序由密碼分勝負
  assert.deepStrictEqual(sorted('df', 'desc').slice(0, 5),
                         [23995346, 89631139, 20110, 20111, 46986414]);
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

test('方向只翻主鍵:同鍵值那一團的內部順序不隨方向變,空值永遠在後', () => {
  const has = id => NO_ATK.indexOf(id) < 0;
  const atkOf = id => CARDS.find(c => c.id === id).atk;
  const asc = sorted('atk', 'asc');
  const desc = sorted('atk', 'desc');
  // 有值的一批:同攻擊力分團,升序的團整批反過來就是降序——團的順序翻了,
  // 團內(預設序)一字不差
  const groups = [];
  for (const id of asc.filter(has)) {
    const g = groups[groups.length - 1];
    if (g && atkOf(g[0]) === atkOf(id)) g.push(id);
    else groups.push([id]);
  }
  assert.deepStrictEqual(desc.filter(has), groups.slice().reverse().flat());
  // 空值那一批整個是「同鍵值的一團」:兩個方向下順序相同(預設序),而且都在最後
  assert.deepStrictEqual(desc.filter(id => !has(id)), asc.filter(id => !has(id)));
});

test('排序穩定:相同鍵值的卡順序不隨執行、不隨輸入順序變動', () => {
  // 平手落回預設序,最終決勝在領域序末層的卡片密碼(唯一鍵),比較函式因此是
  // 全序——排序結果不靠 Array#sort 是不是穩定排序,輸入順序也影響不了它
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

test('排序選單的鍵清單:預設(領域序)沒有方向,單鍵各帶預設方向', () => {
  const keys = harness.sortKeys(sandbox);
  assert.deepStrictEqual(keys.map(k => k.key), ['dom', 'atk', 'df', 'lv', 'n', 'id']);
  // 第一筆是預設的排序(領域序),選單上叫「預設」,而且它沒有方向可切
  assert.strictEqual(keys[0].zh, '預設');
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
         text: '墓地%特殊召喚', textMat: 1 },
    sort: DOM_SORT },
  // 大類是兩態軸(票12):只有正選,沒有排除
  { q: { ...EMPTY_Q, cat: { m: 1, s: 1 },
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

test('素材行開關進網址:勾了寫 textMat=1,沒勾不寫、壞值不留殘骸', () => {
  const h = hashOf({ q: { ...EMPTY_Q, text: '融合', textMat: 1 }, sort: DOM_SORT });
  assert.strictEqual(h, 'text=' + encodeURIComponent('融合') + '&textMat=1');
  assert.deepStrictEqual(parseHash(h).q, { ...EMPTY_Q, text: '融合', textMat: 1 });
  assert.strictEqual(hashOf({ q: { ...EMPTY_Q, text: '融合' }, sort: DOM_SORT }),
                     'text=' + encodeURIComponent('融合'));
  assert.ok(!('textMat' in parseHash('textMat=9').q));
  assert.ok(!('textMat' in parseHash('textMat=').q));
});

test('兩態軸的排除值在網址還原時被丟掉(票12:大類讀不出排除)', () => {
  // 大類兩態化之後,`cat=-t` 這種手改出來的段還原不成任何 UI 做得出來的狀態,
  // 與「值不在值域裡」同一個下場:丟掉該碼,其餘照常
  const st = parseHash('cat=m,-t&attr=dark');
  assert.deepStrictEqual(st.q.cat, { m: 1 });
  assert.deepStrictEqual(st.q.attr, { dark: 1 });
  // 整段都是排除時,連 cat 這個鍵都不留(空殼不算條件)
  assert.ok(!('cat' in parseHash('cat=-m,-t').q));
  // 三態軸不受影響:排除照常還原
  assert.deepStrictEqual(parseHash('attr=-light').q.attr, { light: -1 });
});

test('組合鈕的碼進出網址(spec-optional-combo)', () => {
  // 條件軸由 Query.FIELDS 導出、合法碼跟著分組走:組合碼自動是合法碼
  const st = { q: { ...EMPTY_Q, opt: { qo: 1, tm: -1 } }, sort: DOM_SORT };
  assert.strictEqual(hashOf(st), 'opt=qo,-tm');
  assert.deepStrictEqual(parseHash(hashOf(st)), st);
  // 全部組與怪獸側組同一個參數(同一軸),照宣告序寫
  const both = { q: { ...EMPTY_Q, opt: { m: 1, tm: -1 } }, sort: DOM_SORT };
  assert.strictEqual(hashOf(both), 'opt=m,-tm');
  // 不在值域裡的碼照舊被丟掉
  assert.deepStrictEqual(parseHash('opt=zz,tm').q.opt, { tm: 1 });
  assert.ok(!('opt' in parseHash('opt=zz').q));
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

test('被建置期拿掉按鈕的效果類型值,網址視同未知碼忽略', () => {
  // 建置期把跨類型 0 張的值從**分組**拿掉、留在 items 當顯示詞彙表(ADR-0010)
  // ——網址的合法碼跟著按鈕(分組聯集)走,不跟顯示詞彙表走。「UI 做不出來的
  // 狀態還原不回來」,與兩態軸丟排除段同一條規則
  const trimmed = {
    ...VOCAB,
    kind: { ...VOCAB.kind,
            groups: [{ zh: '怪獸側', codes: ['x', 'c', 'q', 't', 'i'] },
                     { zh: '跨類型魔陷效果', codes: ['se'] }] },
  };
  const box = harness.load({ cards: CARDS, vocab: trimmed, meta: META });
  // 按鈕也跟著分組走:sp 沒有鈕,se 還在
  const kindAxis = harness.axes(box).find(a => a.key === 'kind');
  assert.deepStrictEqual(kindAxis.groups[1].items.map(i => i.code), ['se']);
  // 網址帶著被拿掉的值:那一個碼丟掉,其餘照常
  const st = harness.parseHash(box, 'kind=sp,se&attr=dark');
  assert.deepStrictEqual(st.q.kind, { se: 1 });
  assert.deepStrictEqual(st.q.attr, { dark: 1 });
  assert.ok(!('kind' in harness.parseHash(box, 'kind=sp').q));
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
  // 素材行開關同理:它只修飾效果文那一格怎麼比,不是一條會篩掉卡的條件
  assert.strictEqual(critCount({ ...EMPTY_Q, textMat: 1 }), 0);
  assert.strictEqual(critCount({ ...EMPTY_Q, text: '融合', textMat: 1 }), 1);
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

/* ── 逐軸已選數(票13) ──────────────────────────────────
   參數軸摺疊之後,收起的軸看不見自己設了什麼——標題列因此寫著該軸的已選數。
   critCount 數的是「幾條條件」(整軸算一條),這裡數的是「這一軸點了幾顆」,
   兩個數字答的是不同的問題。鍵是**畫面上的區塊**:子類型三段各自一個標題列,
   所以共用的 sub 軸物件照大類前綴拆回三份,誰的選擇誰計數。 */

const axisCounts = q => harness.axisCounts(sandbox, q);

test('逐軸已選數:三態軸數點亮的鈕,排除也算', () => {
  const c = axisCounts({ ...EMPTY_Q, attr: { dark: 1, light: -1 },
                         race: { dragon: 1 } });
  assert.strictEqual(c.attr, 2);
  assert.strictEqual(c.race, 1);
  // 沒點的軸是 0(標題列因此不顯示數字)
  assert.strictEqual(c.cat, 0);
  assert.strictEqual(c.kind, 0);
});

test('逐軸已選數:子類型三段共用一個軸物件,各自數自己那一側', () => {
  const c = axisCounts({ ...EMPTY_Q, cat: { m: 1, s: 1 },
                         sub: { 'm:fusion': 1, 'm:normal': -1, 's:quick': 1 } });
  assert.strictEqual(c.sub_m, 2);
  assert.strictEqual(c.sub_s, 1);
  assert.strictEqual(c.sub_t, 0);
  assert.strictEqual(c.cat, 2);
});

test('逐軸已選數:範圍與攻守 `?` 落在同一個區塊,各算一筆', () => {
  const c = axisCounts({ ...EMPTY_Q, atk: { min: 2500, max: null }, atkq: 1,
                         sc: { min: 0, max: 0 } });
  assert.strictEqual(c.atk, 2);
  // 刻度 0 是真的值,不是「沒設」
  assert.strictEqual(c.sc, 1);
  assert.strictEqual(c.df, 0);
  // 兩邊都空的範圍(壞網址的殘骸)不算
  assert.strictEqual(axisCounts({ ...EMPTY_Q,
    lv: { min: null, max: null } }).lv, 0);
});

test('分組區塊(卡框/能力):具名分組發自己的鍵,計數與展開都認它', () => {
  // 怪獸子類型的具名分組升級成摺疊區塊,顯示方式與屬性/種族一致——
  // 查詢上仍是同一個 sub 軸,分組鍵只是同一批選擇的分組視圖
  const q = { ...EMPTY_Q, cat: { m: 1 },
              sub: { 'm:fusion': 1, 'm:normal': -1 } };
  const c = axisCounts(q);
  // 測試 VOCAB 的 sub_m 只有一個具名分組「卡框」(序 0):兩顆都在裡面
  assert.strictEqual(c['sub_m/0'], 2);
  assert.strictEqual(c.sub_m, 2);
  // 分組視圖不進父子彙總(否則同一批選擇被算兩次)
  assert.strictEqual(harness.treeCounts(sandbox, q).sub_m, 2);
  // 組內有條件 → 分組區塊連同祖先鏈一起開
  assert.deepStrictEqual(expanded(q), ['cat', 'sub_m', 'sub_m/0']);
  // 組內沒條件 → 分組區塊不開
  assert.deepStrictEqual(
    expanded({ ...EMPTY_Q, cat: { m: 1 } }).indexOf('sub_m/0'), -1);
});

test('子樹已選數:父軸彙總後代,葉軸等於逐軸數(檔案總管內縮)', () => {
  const q = { ...EMPTY_Q, cat: { m: 1 }, sub: { 'm:fusion': 1 },
              attr: { dark: 1, light: 1 }, atk: { min: 2500, max: null } };
  const t = harness.treeCounts(sandbox, q);
  // 葉軸:與 axisCounts 同數
  assert.strictEqual(t.attr, 2);
  assert.strictEqual(t.atk, 1);
  // 怪獸子類型 = 自己 1 + 八個參數軸(attr 2 + atk 1)
  assert.strictEqual(t.sub_m, 4);
  // 大類 = 子類組三段的子樹;「怪獸」那一側子樹有已選,自己那顆是路、不計
  // (2026-08-22 使用者裁示:怪獸+獸族該寫 1,不是 2)
  assert.strictEqual(t.cat, 4);
  // 樹外的軸不受影響
  assert.strictEqual(t.kind, 0);
  // 子樹空著時大類自己就是最後一顆鈕,照計(收起也要看得見它)
  assert.strictEqual(harness.treeCounts(
    sandbox, { ...EMPTY_Q, cat: { m: 1 } }).cat, 1);
  // 另一側沒有子樹條件時,那一側照計:魔法(sub_s 空)+獸族 → 2
  assert.strictEqual(harness.treeCounts(
    sandbox, { ...EMPTY_Q, cat: { m: 1, s: 1 },
               race: { dragon: 1 } }).cat, 2);
  // 空條件全零
  const empty = harness.treeCounts(sandbox, EMPTY_Q);
  Object.keys(empty).forEach(k => assert.strictEqual(empty[k], 0, k));
});

test('逐軸已選數:空條件全零,涵蓋每一個生成的區塊', () => {
  const c = axisCounts(EMPTY_Q);
  const keys = Object.keys(c);
  // 區塊鍵 = 三態軸的值域名 + 範圍軸的欄位名,一塊一鍵
  ['kind', 'optional', 'cat', 'sub_m', 'sub_s', 'sub_t', 'attr', 'race',
   'lv', 'lk', 'sc', 'atk', 'df', 'lm', 'rarity', 'gy', 'ot']
    .forEach(k => assert.ok(keys.indexOf(k) >= 0, k));
  keys.forEach(k => assert.strictEqual(c[k], 0, k));
});

/* ── 還原展開判定(票14,2026-08-17 改檔案總管規矩) ──────
   網址還原時哪些軸該展開是一條純規則:有已選條件的軸**連同祖先鏈**(軸是巢狀
   的,屬性住在 怪獸子類型 住在 大類 裡,祖先不開誰也看不到葉軸),加上承載的
   效果類型帶出的必發/選發。連動出現但自己沒條件的軸**不**展開(節點收著出現,
   要看再點開)。展開動作本身是 DOM(走人工驗收),判定在這裡測。 */

const expanded = q => harness.expandedAxes(sandbox, q);

test('還原展開:有條件的軸連同祖先鏈,空條件是空集合', () => {
  assert.deepStrictEqual(expanded(EMPTY_Q), []);
  // 種族藏在 怪獸子類型 藏在 大類 裡:三層一起開
  assert.deepStrictEqual(expanded({ ...EMPTY_Q, race: { dragon: 1 } }),
                         ['cat', 'sub_m', 'race']);
  // 排除也是條件:收到連結的人要看得到「不要龍族」設在哪
  assert.deepStrictEqual(expanded({ ...EMPTY_Q, race: { dragon: -1 } }),
                         ['cat', 'sub_m', 'race']);
  assert.deepStrictEqual(expanded({ ...EMPTY_Q, atk: { min: 2500, max: null } }),
                         ['cat', 'sub_m', 'atk']);
  // 攻守 `?` 落在攻守自己的區塊
  assert.deepStrictEqual(expanded({ ...EMPTY_Q, dfq: -1 }),
                         ['cat', 'sub_m', 'df']);
});

test('還原展開:連動出現但自己沒條件的子類組不展開(收著出現)', () => {
  assert.deepStrictEqual(expanded({ ...EMPTY_Q, cat: { m: 1 } }), ['cat']);
  assert.deepStrictEqual(expanded({ ...EMPTY_Q, cat: { m: 1, t: 1 } }), ['cat']);
  // 子類自己有條件才開,連同祖先
  assert.deepStrictEqual(
    expanded({ ...EMPTY_Q, cat: { s: 1 }, sub: { 's:quick': 1 } }),
    ['cat', 'sub_s']);
});

test('還原展開:承載的效果類型連動帶出必發/選發', () => {
  assert.deepStrictEqual(expanded({ ...EMPTY_Q, kind: { q: 1 } }),
                         ['kind', 'optional']);
  // 不承載的類型(永續效果)帶不出來——那一組在畫面上根本是藏著的
  assert.deepStrictEqual(expanded({ ...EMPTY_Q, kind: { c: 1 } }), ['kind']);
  // 排除不是已選(與 optionalAvailable 同一條規則)
  assert.deepStrictEqual(expanded({ ...EMPTY_Q, kind: { q: -1 } }), ['kind']);
  // 必發/選發自己有條件當然展開
  assert.deepStrictEqual(expanded({ ...EMPTY_Q, opt: { m: 1 } }), ['optional']);
});

test('條件數在網址走一趟之後不變(分享的連結在手機上摺著開)', () => {
  for (const st of STATES) {
    assert.strictEqual(critCount(parseHash(hashOf(st)).q), critCount(st.q),
                       JSON.stringify(st.q));
  }
  // 加一條條件軸,摺疊鈕自動算得到它——條件數不必跟著 FIELDS 抄第二份
  assert.strictEqual(critCount(parseHash('attr=dark&lv=4-&sort=atk').q), 2);
});

/* ── 資料更新時間的顯示格式(footer 票03) ─────────────────── */

test('資料更新時間:ISO+0800 → 人可讀的 UTC+8 形式', () => {
  assert.strictEqual(sandbox.__fmtTime('2026-08-08T17:57:00+0800'),
                     '2026-08-08 17:57 (UTC+8)');
  // 秒數捨去、T 換空白
  assert.strictEqual(sandbox.__fmtTime('2026-08-17T19:41:03+0800'),
                     '2026-08-17 19:41 (UTC+8)');
});

test('資料更新時間:非預期形狀原樣返回,不出 NaN/Invalid Date', () => {
  // 顯示固定 UTC+8,別的偏移也算非預期形狀(管線整條都以 +0800 記錄)
  for (const bad of ['腐敗資料', '', '2026-08-08', '17:57 (UTC+8)',
                     '2026-01-01T00:00:00+0900',
                     '2026-01-01T23:59:59-0500']) {
    assert.strictEqual(sandbox.__fmtTime(bad), bad);
  }
  // 欄位整個不是字串(META 形狀改變)也原樣返回,由呼叫端決定顯不顯示
  assert.strictEqual(sandbox.__fmtTime(null), null);
  assert.strictEqual(sandbox.__fmtTime(undefined), undefined);
  assert.strictEqual(sandbox.__fmtTime(12345), 12345);
});
