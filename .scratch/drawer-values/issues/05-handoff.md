# 05: 交件

**What to build:** 在使用者跑的入口(真 Chrome,桌面與手機寬)確認抽屜按不出意外的 0 張,數字與規格一致,全套測試通過。見規格 Solution 的驗收與 Testing Decisions 的真瀏覽器段。

**Blocked by:** 01, 02, 03, 04

**Status:** ready-for-agent

- [ ] `tools/drawer_browser.js` 改成依抽屜畫面逐顆點可按的鈕:每顆都有結果;灰與鎖住的按了標籤不變;結果寫進 `tools/results/`
- [ ] 真 Chrome 桌面寬與手機寬(390 px)各走一輪:破壊、特殊召喚、一張否定的具名查詢(如 破壊できない)、一張帶區域的具名查詢;含按極性否定後否定形變可按、區域選單換玩家、中心詞挑清單與打清單外的字、貼網址重開;console 無錯
- [ ] `tools/press_stats.js` 加一段「只按抽屜選項裡可按的鈕」:全部具名查詢上 0 張的次數為 0;舊兩段照跑,三段結果記進 Comments
- [ ] 抽屜重畫耗時(瀏覽器)記進 Comments
- [ ] 全套測試通過:node 測試、effect-tokenize、script 五套
- [ ] 規格 Further Notes 補交件註記
