/**
 * engine.js — 搜尋判定核心(接縫 3:查詢條件 → 命中卡片 + 每張卡的命中效果句索引)
 *
 * **這一層是全站正確性的核心,而且是純的**:不碰 DOM、不讀全域可變狀態。卡片資料
 * 由呼叫端以參數注入(`db`)而不從 `Util.DB` 抓——注入之後這幾個函式可以餵數十張
 * 合成卡單獨測,不必載入 7.5 MB 的真實索引(`script/web/engine.test.js`)。
 *
 * 回傳值帶「每張卡的命中效果句索引」(`rows`)而不只是卡片清單。票03 的卡名軸是
 * 卡層條件、還沒有人寫進 rows,但這個位置現在就存在:票04 的命中標亮與票06 的
 * 句層耦合都掛在它上面,而**那兩個語意只能從命中位置驗證**——光看命中了哪些卡,
 * 分不出引擎是真的做了同句交集還是碰巧兩個條件都在同一張卡上成立。
 */
'use strict';

const Engine = (() => {

/* 純數字輸入才額外比對卡片密碼。前後空白在呼叫端就修掉了,這裡只認光禿禿的數字 */
const DIGITS = /^\d+$/;

/* `%` 萬用字元:語意是「這幾段依序出現」(青眼%龍 = 先有青眼、後面某處有龍),
   段與段之間、頭尾都可以有別的字。空關鍵字沒有段,一律通過。 */
function likeParts(kw) {
  return String(kw == null ? '' : kw).split('%').filter(Boolean);
}

function likeMatch(text, parts) {
  let pos = 0;
  for (const p of parts) {
    const i = text.indexOf(p, pos);
    if (i < 0) return false;
    pos = i + p.length;
  }
  return true;
}

/* 卡名比對。lang:zh(預設)/ja/en,比對對應語言的卡名。
   中文與日文模式**同時比對 `※` 別名**(117 張):別名是同一張卡的另一種中文譯名,
   用舊譯名找卡的人也該找得到(沿用 oldProject engine.js:249-251 的行為)。
   純數字輸入**額外**比對卡片密碼與異圖密碼——額外而不是取代,卡名裡真的有數字的
   卡(No.39)不會因為輸入是數字就搜不到。 */
function nameHit(c, kw, lang) {
  const raw = String(kw == null ? '' : kw).trim();
  const parts = likeParts(raw);
  if (!parts.length) return true;
  if (DIGITS.test(raw) && idHit(c, raw)) return true;
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

/**
 * 接縫 3。q:查詢條件(欄位缺席即該軸未設,不必先補齊)。
 * 回傳 { cards: [{ card, rows }] } —— rows 是該卡命中的效果句索引集合,
 * 沒有任何句層條件時為 null。
 *
 * 軸間 AND:每個軸各自否決,全部通過才進結果。
 */
function runQuery(db, q) {
  q = q || {};
  const cards = [];
  for (const c of db) {
    if (q.name && !nameHit(c, q.name, q.nameLang)) continue;
    cards.push({ card: c, rows: null });
  }
  return { cards };
}

  /* 對外只有接縫本身:比對函式關在閉包裡,改寫比對語意時不必先查有沒有別人在用。
     票04 的關鍵字上色要用到 likeParts/likeMatch,屆時再開。 */
  return Object.freeze({ runQuery });
})();
