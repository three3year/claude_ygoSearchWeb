# 04: 交件

**What to build:** 在使用者跑的入口(真 Chrome,桌面與手機寬)確認目錄只展開、最後一列加標籤,鎖住的標籤抽屜乾淨且按不出意外的 0 張,數字與規格一致,全套測試通過。見規格 Solution 的驗收與 Testing Decisions 的真瀏覽器段。

**Blocked by:** 01, 02, 03

**Status:** ready-for-agent

- [ ] 真 Chrome 桌面寬與手機寬(390 px)各走一輪:點 破壊 只展開、最後一列加標籤與排除;破壊@相手フィールド、特殊召喚←墓地、破壊:モンスター、破壊(耐性) 的抽屜——鎖住那一行按不掉、說明文字對、可按的鈕都有結果;貼網址重開仍鎖;console 無錯
- [ ] 真瀏覽器腳本(drawer-values 的 `drawer_browser.js` 改寫或本功能 tools 另寫)結果寫進本功能 `tools/results/`
- [ ] `press_stats.js` 第三段照跑,0 張 0 次;鎖住的值按了標籤不變;結果記進 Comments
- [ ] `lock_stats.js` 重跑:鎖住後條件葉與耐性/限制的灰鈕數和規格 Further Notes 對得上(實作後應只剩「仍灰」那些),結果記進 Comments
- [ ] 全套測試通過:node 測試、effect-tokenize、script 五套
- [ ] 規格 Further Notes 補交件註記
