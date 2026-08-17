/**
 * main.js — 主流程(把條件側欄接上引擎、呈現層與網址)
 *
 * **資料流單向**:側欄(唯一可變真相)→ Query.read() → Engine.runQuery(純函式)
 * → 產物 → View.render(無內部記憶)。沒有「上次查詢的中間結果」這種全域——
 * 要重畫就重跑一次導出。
 *
 * 網址是這條路的**兩端**:按搜尋時條件寫進 `#hash`(一行網址就能把「所有暗屬性的
 * 誘發即時特招」丟給別人),而帶條件的網址一開就還原條件並自動跑那個搜尋——
 * 收到連結的人看到的是結果而不是空表單。編解碼住 hash.js,這裡只管時機。
 *
 * 空條件是合法的條件:按「搜尋」時不擋,列出全部 14,207 張。但**一開站不自動跑
 * 它**——起始畫面是一句「設定條件後按搜尋」而不是一批沒有人問過的卡(引擎照樣
 * 導得出全部,不列是呈現層的決定;想純逛的人按空條件的「搜尋」即可)。
 */
'use strict';

(() => {
const { DB, META, $ } = Util;

/**
 * 目前畫面對應的網址狀態,**正規形**。
 *
 * 自己寫進 `#hash` 會觸發 `hashchange`,沒擋掉就會再跑一次搜尋(同一次搜尋跑兩遍)。
 * 擋的方式是記下自己寫了什麼、事件來的時候比一次:
 *
 * - **比正規形而不是原字串**:瀏覽器對 hash 的百分比編碼各有各的作法(有的原樣
 *   留著中文、有的編起來),讀回來的字串不見得與寫進去的一模一樣。
 * - **不用布林旗標**:寫進去的值與現況相同時瀏覽器根本不發事件,旗標會留到下一次
 *   使用者真的按上一頁時把那一次吃掉——而那是個看不出原因的「上一頁沒反應」。
 */
let applied = '';

/* **畫面上這批結果是哪一組條件跑出來的。** 網址寫的是它,而不是側欄當下的樣子:
   側欄可以領先畫面(打了字還沒按搜尋),而那時換一下排序就會把還沒生效的條件寫進
   網址——收到連結的人得到的結果與分享的人看到的不是同一批。這不是「上次查詢的中間
   結果」,只是那一次的條件本身;結果仍然每次重跑。 */
let appliedQuery = null;

/* 讀側欄 → 跑引擎 → 重畫。這是唯一一條產生結果的路徑。 */
function run() {
  appliedQuery = Query.read();
  // 摺疊鈕寫的是**這批結果的條件數**而不是側欄當下的樣子,與網址同一條規則:
  // 打了字還沒按搜尋時,鈕面上的數字仍然對應畫面上這批卡
  Query.summarize(appliedQuery);
  View.render(Engine.runQuery(DB, appliedQuery));
}

/* 網址寫的是「查了什麼」與「怎麼排」;分頁位置與每頁筆數不進去(那是這一頁
   看到哪,不是查詢本身)。 */
function push() {
  const hash = Hash.stringify({ q: appliedQuery, sort: View.sort() });
  applied = hash;                 // 先記下來:指派 hash 會同步觸發 hashchange
  // 比的是**網址列上那個字串本身**而不是它的正規形:一模一樣就不必寫(寫了也
  // 只是多一個一模一樣的歷史項),不一樣就寫——手改過或過期的網址因此在按下
  // 搜尋之後收斂成正規形,而不是留在網址列上說著另一件事
  if (hash === String(location.hash).replace(/^#/, '')) return;
  location.hash = hash;           // 指派即 pushState 語意:上一頁回得到前一次
}

/* 搜尋。分頁位置歸 1:上一次翻到第 37 頁,新條件只有 12 張的話,留在第 37 頁
   看到的會是一片空白。**網址只在這裡(與換排序時)寫一次**——打字的時候不寫,
   否則每一個 keystroke 都會塞一項進瀏覽器歷史。 */
function search() {
  View.setPage(1);
  run();
  push();
  // 搜尋完就把條件區收起來:窄螢幕上它佔滿整屏,不收的話按下搜尋之後捲回頂端
  // 看到的是自己剛設好的條件,而不是結果。桌機上這是個空動作(側欄常駐)。
  Query.collapse();
  window.scrollTo(0, 0);   // 立刻跳,不做捲動動畫(與換頁同一條裁示)
}

/* 網址 → 側欄 → 結果。壞掉或過期的段在 Hash.parse 那裡就被忽略了,
   這裡拿到的一定是還原得回去的形狀。

   **零條件的網址不自動搜尋**,畫面是起始提示:一開站(或上一頁退回無條件的網址)
   就吐 14,207 張的第一頁,使用者拿到的是一批與自己無關的卡。判的是**條件數**而
   不是「hash 是不是空字串」——只帶排序或卡名語言的網址一樣沒有問任何問題。
   「列出全部」因此成為一次刻意的動作:按空條件的「搜尋」,空條件在 search()
   那裡照舊放行。 */
function restore() {
  const state = Hash.parse(location.hash);
  Query.write(state.q);
  View.setSort(state.sort.key, state.sort.dir);
  View.setPage(1);
  if (Query.count(state.q)) { run(); return; }
  appliedQuery = state.q;         // 排序在起始畫面被換過時,網址寫得出正確的條件段
  Query.summarize(appliedQuery);
  View.render(null);              // null = 還沒查過,呈現層畫起始提示
}

/* 別人改的網址(上一頁/下一頁、貼一個新連結進網址列)才重跑;自己剛寫進去的
   那一個在這裡被擋掉,所以一次搜尋只跑一次。 */
function onHashChange() {
  const hash = Hash.canon(location.hash);
  if (hash === applied) return;
  applied = hash;
  restore();
}

function init() {
  const built = META.built_at ? `・建置於 ${META.built_at}` : '';
  $('dbInfo').textContent =
    `${META.cards || DB.length} 張卡・${META.clauses || 0} 個效果句${built}`;
  Query.init();
  View.initAltArt();
  View.initEffKind();
  // 換排序也更新網址:分享出去的連結講的是「我現在看到的這一頁」,而
  // 「最高攻擊力的暗屬性誘發即時」這個問題的答案有一半在排序上
  View.initSort(push);
  $('btnSearch').addEventListener('click', search);
  // 清除條件後直接重搜:條件是空的,結果就是全部——把畫面留在上一次的結果上,
  // 使用者會以為條件還在
  $('btnClear').addEventListener('click', () => { Query.clear(); search(); });
  $('perPage').addEventListener('change', e => {
    View.setPerPage(+e.target.value);   // 換每頁筆數會回到第 1 頁
    View.render();
  });
  // 在條件側欄的輸入框按 Enter = 搜尋(分頁器的頁碼框不在側欄裡,不受影響)
  $('sidebar').addEventListener('keydown', e => {
    if (e.key === 'Enter' && e.target.tagName === 'INPUT') search();
  });
  window.addEventListener('hashchange', onHashChange);
  // 開站時**讀**網址而不是寫:帶條件的連結一開就還原條件並自動搜尋,
  // 沒帶條件時停在起始提示(不自動列出全部)。載入不留歷史項。
  applied = Hash.canon(location.hash);
  restore();
}

document.addEventListener('DOMContentLoaded', init);
})();
