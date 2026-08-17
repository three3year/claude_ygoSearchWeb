/**
 * engine.js — 搜尋判定核心(接縫 3:查詢條件 → 命中卡片 + 每張卡的命中效果句索引)
 *
 * **這一層是全站正確性的核心,而且是純的**:不碰 DOM、不讀全域可變狀態。卡片資料
 * 由呼叫端以參數注入(`db`)而不從 `Util.DB` 抓——注入之後這幾個函式可以餵數十張
 * 合成卡單獨測,不必載入 7.5 MB 的真實索引(`script/web/engine.test.js`)。
 * 唯一的例外與 sort.js 相同:載入期讀一次 `Util.VOCAB`(唯讀的建置產物,不是
 * 可變狀態)取[[值域正典]]宣告的本類對應——測試沙箱逐 fixture 注入它,所以
 * 這一份也測得到。
 *
 * 回傳值帶「每張卡的命中效果句索引」(`rows`)而不只是卡片清單。**句層的語意只能
 * 從命中位置驗證**——光看命中了哪些卡,分不出引擎是真的逐句比對還是碰巧兩個條件
 * 都在同一張卡上成立。標亮畫在 rows 上,票06 的句層耦合也接在同一個位置。
 *
 * 條件分兩層:
 * - **卡層**(卡名、卡片密碼、卡片參數)—— 整張卡通過或不通過。
 * - **句層**(效果文關鍵字、[[效果類型]]、[[必發/選發]])—— 逐[[效果句]]獨立
 *   比對,一張卡只要存在一個效果句滿足**全部**句層條件即命中,那一句進 `rows`。
 *
 * 句層條件之間取**效果句層級的交集**(票06):一張卡的 ① 是誘發即時但不含關鍵字、
 * ② 含關鍵字但是啟動效果,**不算命中**。使用者問的是「一個會做某件事的誘發即時
 * 效果」,而不是「這張卡某處有這四個字、另一處有個誘發即時」——這是本站與一般
 * 查卡站的分水嶺,而一般查卡站做不到是因為它們沒有效果句層級的結構。
 */
'use strict';

const Engine = (() => {
const { VOCAB } = Util;

/* 密碼比對只認光禿禿的數字(前後空白在 runQuery 就修掉了) */
const DIGITS = /^\d+$/;

/* 跨類型魔陷效果(ADR-0010):魔陷十值的成員 = 帶該值效果句、且自身[[卡片種類]]
   與該值**不一致**的卡。一致對應(值 → 本類的大類+子類型)由[[值域正典]]宣告、
   隨 `VOCAB.kind.own` 出去——在這裡抄一份的話,正典多一個對應時排除會安靜地
   不生效(ADR-0008 的同一個失效模式)。 */
const KIND_OWN = {};
for (const code in (VOCAB.kind || {}).own || {}) {
  const pair = VOCAB.kind.own[code];
  const i = pair.indexOf(':');
  KIND_OWN[code] = { c: pair.slice(0, i), s: pair.slice(i + 1) };
}

/* 效果文關鍵字**不掃 `role = 素材指定` 的行**(2,358 行):搜「融合」時,574 張融合
   怪獸的素材寫法會把真正的答案淹掉。[[效果標記表]]逐句判過 `role`,所以這件事做得
   準,而一般查卡站做不到。固定規則,不提供開關。
   已知副作用(spec 已記):效果文框搜「青眼白龍」不會撈到把它寫在素材行的融合怪獸,
   但卡名框搜得到本尊。召喚條件與使用次數限制照樣掃——「不能通常召喚」「1回合只能
   使用1次」是使用者確實會查的限制文字。 */
const ROLE_MAT = 'mat';

/* 關鍵字欄位的正規化:缺席、null 與只有空白都是「這一軸沒設」。空白在這裡一次
   修完,判定函式因此不必各自防禦,也不會對 14,207 張卡各 trim 一遍。 */
function term(v) {
  return String(v == null ? '' : v).trim();
}

/* `%` 萬用字元:語意是「這幾段依序出現」(青眼%龍 = 先有青眼、後面某處有龍),
   段與段之間、頭尾都可以有別的字。空關鍵字沒有段,一律通過。 */
function likeParts(kw) {
  return kw.split('%').filter(Boolean);
}

/* 各段在字串裡的位置。**標亮用的區間與命中判定出自同一次走訪**——呈現層自己再
   比對一次的話兩份會漂開,而漂開的形狀是「這一行被標亮了但沒有一個字上色」。
   任一段找不到即回傳空陣列(部分命中不是命中)。 */
function likeRanges(text, parts) {
  const out = [];
  let pos = 0;
  for (const p of parts) {
    const i = text.indexOf(p, pos);
    if (i < 0) return [];
    out.push([i, i + p.length]);
    pos = i + p.length;
  }
  return out;
}

function likeMatch(text, parts) {
  return likeRanges(text, parts).length === parts.length;
}

/* 卡名比對。lang:zh(預設)/ja/en,比對對應語言的卡名。
   中文與日文模式**同時比對 `※` 別名**(117 張):別名是同一張卡的另一種中文譯名,
   用舊譯名找卡的人也該找得到(沿用 oldProject engine.js:249-251 的行為)。
   **只比對卡名**:卡片密碼是另一個欄位的事,這裡打 `39` 得到的是「No.39 希望皇
   霍普」而不是某張密碼含 39 的卡。 */
function nameHit(c, kw, lang) {
  const parts = likeParts(kw);
  if (!parts.length) return true;
  if (lang === 'ja') {
    return (!!c.nj && likeMatch(c.nj, parts)) || (!!c.ax && likeMatch(c.ax, parts));
  }
  if (lang === 'en') {
    // 英文卡名不分大小寫:牌表上抄來的字不必連大小寫都對
    const lower = parts.map(p => p.toLowerCase());
    return !!c.ne && likeMatch(c.ne.toLowerCase(), lower);
  }
  return likeMatch(c.n, parts) || (!!c.ax && likeMatch(c.ax, parts));
}

/* 卡片密碼:完全相等才算,不做子字串——`4698` 不是任何一張卡的密碼,把它當前綴
   比對只會冒出一堆使用者沒問的卡。數值比較,顯示時補的那幾個 0 抄回來照樣命中。
   異圖密碼也認:拿到的是異圖卡面時查得到本尊(異圖是同一張卡)。 */
function idHit(c, digits) {
  const n = Number(digits);
  return c.id === n || (!!c.al && c.al.indexOf(n) >= 0);
}

/* 三態鈕的判定。**軸內 OR**(屬性選暗+光是兩者皆可),**排除優先**——同一軸同時
   被包含與排除時以排除為準,因為排除是使用者明說「不要這個」。看得出差別的是
   多值的軸:子類型同時選「效果」包含與「靈擺」排除時,靈擺效果怪獸出局。
   `sel` 是 短碼 → 1(包含)/ -1(排除);沒有這一軸的條件時傳 null。 */
function triHit(values, sel) {
  if (!sel) return true;
  let wanted = false, got = false;
  for (const code in sel) {
    const has = values.indexOf(code) >= 0;
    if (sel[code] < 0) {
      if (has) return false;   // 排除掃完才算數:命中包含就提早回傳的話,排在後面
    } else {                   // 的排除條件會被跳過,排除優先就只在寫法順序上成立
      wanted = true;
      if (has) got = true;
    }
  }
  return !wanted || got;
}

/* 範圍條件。**沒有這個參數的卡不被命中**:罠モンスター(cdb 帶怪獸參數的 79 張
   魔陷卡)在索引裡根本沒有等級與攻守,魔法卡也沒有——「沒有」不是 0。
   `?` 同理:它以負的哨兵值存在索引裡,與 0 是不同的東西,不得被數值範圍納入
   (要找 `?` 的人有獨立條件,見 unknownHit)。 */
function rangeHit(v, r) {
  if (!r || (r.min == null && r.max == null)) return true;
  if (v == null || v < 0) return false;
  if (r.min != null && v < r.min) return false;
  if (r.max != null && v > r.max) return false;
  return true;
}

/* 攻守 `?` 的獨立條件(攻 83 張、守 54 張)。1 = 只要 `?`,-1 = 排除 `?`。
   連結怪獸沒有守備欄,那是「沒有這個參數」而不是 `?`,所以它不會被「守備 `?`」
   撈到——索引裡根本沒有 `df` 這個鍵。 */
function unknownHit(v, want) {
  if (!want) return true;
  const isUnknown = v != null && v < 0;
  return want > 0 ? isUnknown : !isUnknown;
}

/* 子類型的短碼**在同一側內唯一、跨側重複**(cdb 位元 0x80 在怪獸側是儀式怪獸、
   在魔法側是儀式魔法)。條件因此帶大類前綴 `m:fusion`:不帶前綴的話「選儀式」
   會把儀式魔法一起撈進來;而三側各自成一軸的話「融合怪獸或速攻魔法」會變成
   軸間 AND、永遠零筆——子類型是**一個**軸,三組按鈕是它的三段。 */
function subCodes(c) {
  return (c.s || []).map(s => c.c + ':' + s);
}

/* 卡片參數軸。**沒有這個欄位的卡不被該條件命中**是這一段的骨幹:罠モンスター的
   種族是它變成怪獸之後的形態、寫在效果文的括號裡而不是印在卡面上,索引裡因此
   沒有那五個欄位(CONTEXT.md「卡片子類型」、card-list 票07)。搜「岩石族」得到的
   是真的印著岩石族的怪獸——這不是這裡特判掉的,是索引的形狀本來就沒有。 */
function paramHit(c, q) {
  return triHit(c.c ? [c.c] : [], q.cat)
    && triHit(subCodes(c), q.sub)
    && triHit(c.at ? [c.at] : [], q.attr)
    && triHit(c.r ? [c.r] : [], q.race)
    && triHit(c.lm || [], q.lm)
    && triHit(c.ra ? [c.ra] : [], q.rarity)
    && triHit(c.ot ? [c.ot] : [], q.ot)
    && rangeHit(c.lv, q.lv)
    && rangeHit(c.lk, q.lk)
    && rangeHit(c.sc, q.sc)
    && rangeHit(c.atk, q.atk)
    && rangeHit(c.df, q.df)
    && rangeHit(c.gy, q.gy)
    && unknownHit(c.atk, q.atkq)
    && unknownHit(c.df, q.dfq);
}

/* 一句的短碼,包成 triHit 吃的陣列形狀。沒有值的句子是空陣列——**「不承載」不是
   一個值**:22,942 個效果句不承載[[必發/選發]],它們不該被「必發」命中,也不該被
   「排除必發」排掉(排除的是必發,不是「沒有這個屬性」)。 */
function codeAt(arr, i) {
  const code = arr && arr[i];
  return code ? [code] : [];
}

/* 一句的[[效果類型]]短碼。**本類卡的該值效果句視同無值**(ADR-0010):裝備魔法卡
   自己的裝備魔法卡效果是卡片種類的重言,包含態收不到它、排除態也不擋它——與
   「不承載不是一個值」同一個形狀。怪獸側六類沒有本類對應,一律原樣。 */
function kindAt(c, i) {
  const code = c.k && c.k[i];
  if (!code) return [];
  const own = KIND_OWN[code];
  if (own && c.c === own.c && (c.s || []).indexOf(own.s) >= 0) return [];
  return [code];
}

/* 空的條件物件等於沒設。這一層在句層特別要緊:記成「有設」的話,一張卡會單純
   因為**有效果句**就整批被標亮,而使用者一顆鈕都沒點。 */
function sel(o) {
  return o && Object.keys(o).length ? o : null;
}

/* 句層條件:**逐[[效果句]]獨立比對,而且是同一句**。「墓地%手牌」只在同一個效果裡
   同時出現才算命中;效果文關鍵字與[[效果類型]]/[[必發/選發]]並用時同樣要落在同一句。
   回傳命中的效果句索引;一句都沒中即這張卡不命中。
   三態排除在這一層的語意是**這一句不是那個類型**,而不是「這張卡沒有那種句子」
   ——同一顆鈕在同一個軸上不能有兩種語意,而句層的單位是句。 */
function clauseRows(c, parts, kindSel, optSel) {
  const tx = c.tx || [];
  const rows = [];
  for (let i = 0; i < tx.length; i++) {
    if (kindSel && !triHit(kindAt(c, i), kindSel)) continue;
    if (optSel && !triHit(codeAt(c.o, i), optSel)) continue;
    if (parts.length) {
      // 不掃素材指定行是**關鍵字**的規則,不是「素材行不存在」:找效果外文本的
      // 人照樣看得到它,被淹掉的只有關鍵字搜尋(見上方 ROLE_MAT)
      if (c.ro && c.ro[i] === ROLE_MAT) continue;
      if (!likeMatch(tx[i], parts)) continue;
    }
    rows.push(i);
  }
  return rows;
}

/**
 * 接縫 3。q:查詢條件(欄位缺席即該軸未設,不必先補齊)。
 * 回傳 { cards: [{ card, rows }], marks } ——
 *   `rows` 是該卡命中的效果句索引陣列,沒有任何句層條件時為 null。
 *   `marks` 是生效中的句層條件,呈現層照它寫命中行的 badge:每一個 row 都滿足
 *   **全部**句層條件(那正是句層耦合的定義),所以「因為哪些條件而中」對整批
 *   rows 是同一組,不必逐行再記一次。
 *
 * 軸間 AND:每個軸各自否決,全部通過才進結果。
 */
function runQuery(db, q) {
  q = q || {};
  const name = term(q.name);
  // 卡片密碼自成一軸,只認密碼、不比對卡名。非數字的輸入不命中任何卡而不是被
  // 忽略——「打了條件卻當作沒打」會讓使用者以為結果是這個條件篩出來的。
  const code = term(q.code);
  const codeOk = DIGITS.test(code);
  const text = term(q.text);
  const textParts = likeParts(text);
  const kindSel = sel(q.kind);
  const optSel = sel(q.opt);
  // 生效中的句層條件。效果文帶關鍵字本身(每一行都一樣),效果類型與必發/選發
  // 只報「這個條件生效中」——badge 上寫的是**那一行自己的值**,而那逐行不同。
  const marks = [];
  if (textParts.length) marks.push({ type: 'text', value: text });
  if (kindSel) marks.push({ type: 'kind' });
  if (optSel) marks.push({ type: 'opt' });
  const cards = [];
  for (const c of db) {
    if (name && !nameHit(c, name, q.nameLang)) continue;
    if (code && !(codeOk && idHit(c, code))) continue;
    if (!paramHit(c, q)) continue;
    let rows = null;
    if (marks.length) {
      rows = clauseRows(c, textParts, kindSel, optSel);
      if (!rows.length) continue;
    }
    cards.push({ card: c, rows });
  }
  return { cards, marks };
}

  /* 對外是接縫本身,加上關鍵字比對的兩個函式——**呈現層的行內上色必須用引擎這一份**,
     自己再寫一份比對就會有「標亮了卻沒上色」的漂移。其餘比對函式關在閉包裡。 */
  return Object.freeze({ runQuery, likeParts, likeRanges });
})();
