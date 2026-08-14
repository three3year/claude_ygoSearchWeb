/**
 * sort.js — 排序(預設的領域序 + 排序選單的單鍵排序)
 *
 * **這一層是純的**:比較函式只看卡片物件,不碰 DOM、不讀查詢條件。排序因此
 * 與搜尋完全解耦——換一個排序鍵不必重跑引擎,重排已經有的那份結果就好。
 *
 * 預設的**領域序**是七層比較(沿用 oldProject 的 `cmpCards`):
 * 大類 → 靈擺卡排後 → [[卡片子類型]]序 → 等級/階級/連結值**高到低** →
 * 屬性序 → 種族序 → [[卡片密碼]]升序。
 *
 * **第 1、3、5、6 層的比較序直接取自 `window.VOCAB` 的宣告序,這裡沒有第二份
 * 順序表**(ADR-0008)。oldProject 的 `RACES = VOCAB.race.map(e => e.zh)` 旁註著
 * 「與宣告序同一份」,就是這個做法;而它的 `kindOrder` / `SPELL_SUB_ORDER` 仍是
 * 手抄的第二份——在正典裡把儀式移到融合前面,那一份不會跟著動,而畫面上的順序
 * 與按鈕的順序會從此對不起來,不報錯也不白屏。
 */
'use strict';

const Sort = (() => {
const { VOCAB, codesOf } = Util;

/* 靈擺自己是第 2 層,所以不參與第 3 層的卡框序。不排除的話,靈擺融合與靈擺通常
   會因為兩者的卡框序都取到「靈擺」而併成一團——第 2 層已經把靈擺整批挪到後面了,
   第 3 層要問的是這張靈擺卡是哪一種卡框。 */
const PENDULUM = 'pendulum';

/* 短碼 → 宣告序的名次。**沒登記的碼(以及沒有這個參數的卡)一律殿後**:魔法卡
   沒有屬性,它不該插進七個屬性中間的任何一格。 */
function ranker(codes) {
  const order = {};
  codes.forEach((code, i) => { order[code] = i; });
  const last = codes.length;
  return code => (code in order ? order[code] : last);
}

function domainRanker(name) {
  return ranker(codesOf(name));
}

/**
 * [[卡片子類型]]的比較序 = **卡框**的宣告序。
 *
 * 卡框取值域的**第一個分組**(怪獸側的「卡框」;魔法/陷阱側沒有分組,全體都是
 * 卡框)。協調、反轉、卡通那些「能力」子類型不參與:協調同步怪獸的卡框是同步,
 * 拿能力來排的話它會從同步那一團裡被抽出來,排到卡通後面去。
 *
 * 一張卡帶多個卡框碼時取**宣告序最後**的那一個:融合效果怪獸的 `s` 是
 * 「效果＋融合」,而它該跟其他融合怪獸站在一起,不是跟效果怪獸。通常與效果不會
 * 並存,特殊召喚法的卡框彼此也不會並存,所以「最後一個」就是那張卡的卡框。
 */
function frameRanker(name) {
  const dom = VOCAB[name] || {};
  const groups = dom.groups || [];
  const codes = (groups.length ? groups[0].codes : codesOf(name))
    .filter(code => code !== PENDULUM);
  const rank = ranker(codes);
  const last = codes.length;
  return subs => {
    let best = -1;
    for (const code of subs) {
      const i = rank(code);
      if (i < last && i > best) best = i;   // i === last 代表不是卡框碼
    }
    return best < 0 ? last : best;
  };
}

const CAT_RANK = domainRanker('cat');
const ATTR_RANK = domainRanker('attr');
const RACE_RANK = domainRanker('race');
const FRAME_RANK = { m: frameRanker('sub_m'), s: frameRanker('sub_s'),
                     t: frameRanker('sub_t') };

function frameOf(c) {
  const rank = FRAME_RANK[c.c];
  return rank ? rank(c.s || []) : 0;
}

function isPendulum(c) {
  return (c.s || []).indexOf(PENDULUM) >= 0 ? 1 : 0;
}

/* 第 4 層:連結怪獸拿連結值,其餘拿等級/階級,兩者都沒有的(魔法陷阱)排在
   全部數值之後——高到低的比較裡,「沒有」比 0 還低。 */
function levelOf(c) {
  if (c.lk != null) return c.lk;
  return c.lv != null ? c.lv : -1;
}

/**
 * 一張卡的領域序鍵:七層比較的名次,由高位到低位。等級那一層取負數,
 * 「高到低」因此與其餘六層一樣是小的在前,整條鍵只有一種讀法。
 *
 * 算一次就存起來:比較函式要跑 O(n log n) 次,而 14,207 張卡全表排序時
 * 那是二十萬次——每次都重算四個值域的名次要 55 ms,存下來是 15 ms。
 * 索引是唯讀的建置產物,卡片物件不會變,所以這份快取不會過期。
 */
const domKeys = new WeakMap();

function domKey(c) {
  let key = domKeys.get(c);
  if (!key) {
    key = [CAT_RANK(c.c), isPendulum(c), frameOf(c), -levelOf(c),
           ATTR_RANK(c.at), RACE_RANK(c.r), c.id];
    domKeys.set(c, key);
  }
  return key;
}

/** 領域序(七層)。回傳值同 Array#sort 的比較函式。 */
function cmpDomain(a, b) {
  const ka = domKey(a), kb = domKey(b);
  for (let i = 0; i < ka.length; i++) {
    if (ka[i] !== kb[i]) return ka[i] - kb[i];
  }
  return 0;                             // 最後一層是卡片密碼,只有同一張卡才走得到
}

/**
 * 排序選單。`dir` 兼兩用:空字串代表這個鍵沒有方向(領域序是固定的七層比較),
 * 有值時是**切換到這個鍵時的預設方向**——問「最高攻擊力的暗屬性怪獸是哪張」的人
 * 選了攻擊力就該看到最高的那張,不必再點一次方向。
 *
 * 這張表是選單與比較函式的**同一份**來源:選單的選項由它生成,鍵值的取法也由它
 * 決定。分成兩份的話,加一個排序鍵會變成「選單有這個選項但排序沒反應」。
 */
const KEYS = [
  { key: 'dom', zh: '領域序', dir: '' },
  { key: 'atk', zh: '攻擊力', dir: 'desc' },
  { key: 'df', zh: '守備力', dir: 'desc' },
  { key: 'lv', zh: '等級／階級', dir: 'desc' },
  { key: 'n', zh: '卡名', dir: 'asc' },
  { key: 'id', zh: '卡片密碼', dir: 'asc' },
];

/* 攻守的 `?` 以負的哨兵值存在索引裡,而「沒有這個參數」是欄位缺席——**兩者在
   數值排序裡都不是數值**,一律回 null 由比較函式挑到最後去。`?` 當成 0 排的話,
   83 張攻擊力未知的怪獸會混進攻 0 那一團,而那是一個看不出來的錯。 */
function stat(v) {
  return v == null || v < 0 ? null : v;
}

const VALUE = {
  atk: c => stat(c.atk),
  df: c => stat(c.df),
  // 等級/階級只認 `lv`:連結怪獸沒有等級,LINK-3 是連結值、是另一個參數
  // (欄位的有無由大類與子類型決定,見 CONTEXT.md「前端索引」),所以連結怪獸
  // 在這個鍵上是空值而不是等級 3
  lv: c => (c.lv == null ? null : c.lv),
  // 卡名比的是**碼點序**而不是 localeCompare:後者的結果隨環境的 ICU 版本與
  // locale 而變,同一份資料在兩台裝置上會排出不同的順序,而分享出去的網址
  // (票08)講的就是「同一個查詢在你那邊也長這樣」。排的是站上顯示的繁中卡名。
  n: c => (c.n == null ? null : c.n),
  id: c => c.id,
};

function specOf(key) {
  return KEYS.find(k => k.key === key) || KEYS[0];
}

/**
 * 單鍵排序的比較函式。兩條性質是刻意的:
 *
 * - **空值一律殿後**,升序降序都是。位置一致而且不插進數值之間——「攻擊力升序」
 *   的第一張該是攻 0 的怪獸,不是 2,858 張沒有攻擊力的魔法卡。
 * - **降序就是升序的反轉**。方向連決勝的[[卡片密碼]]一起翻,所以同鍵值的那幾張
 *   在兩個方向下也是互為反轉;有值的那一批與空值的那一批各自反轉,兩批的前後
 *   關係不變(空值永遠在後)。
 *
 * 決勝一律落到卡片密碼,而密碼是唯一鍵——比較函式因此是**全序**,排序結果不靠
 * `Array#sort` 是不是穩定排序,同一份輸入排幾次都是同一個順序。
 */
function comparator(key, dir) {
  const spec = specOf(key);
  if (!spec.dir) return cmpDomain;
  const sign = dir === 'desc' ? -1 : 1;
  const value = VALUE[spec.key];
  return (a, b) => {
    const va = value(a), vb = value(b);
    if (va == null || vb == null) {
      if (va != null) return -1;
      if (vb != null) return 1;
      return sign * (a.id - b.id);
    }
    if (va !== vb) return va < vb ? -sign : sign;
    return sign * (a.id - b.id);
  };
}

/** 接縫 3 的回傳形狀(`[{ card, rows }]`)照 key/dir 排序,回傳新陣列(不就地改)。 */
function sort(entries, key, dir) {
  const cmp = comparator(key, dir);
  return entries.slice().sort((x, y) => cmp(x.card, y.card));
}

  /* 對外只有選單要的那張表、鍵的查法與排序本身;比較函式關在閉包裡
     (排序這件事沒有第二種入口,呈現層拿得到 comparator 也只會拿去做同一件事) */
  return Object.freeze({ KEYS, specOf, sort });
})();
