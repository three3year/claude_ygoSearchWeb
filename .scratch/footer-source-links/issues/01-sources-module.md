# 01: 來源模組（先整理，行為不變）

**What to build:** 外部站的網址集中到一個新的前端來源模組，之後的頁尾連結（票 02）與現有的卡片連結都從這裡取網址。這張票做完，訪客看不出任何差別：卡名照樣連到查牌網單卡頁，縮圖與異圖輪播照樣顯示，網址逐字跟改動前相同。規格見 `.scratch/footer-source-links/spec.md` 的 Implementation Decisions 前三條與「來源清單」表。

對照參照實作：同 ark-keyword 把網址集中在獨立的來源模組（`core/sources.ts`），而且也收結果卡連到的外部站（規格 Q13、Q15、Q16）。與 ark 不同的是建置腳本不共用：本站建置是 Python，ark 的建置腳本從同一份來源模組衍生下載位置。

**Blocked by:** None (can start immediately)

**Status:** resolved

- [x] 新增前端來源模組，照零建置協定（ADR-0007）寫成掛在全域的 IIFE，在呈現模組之前載入。script 標籤寫成 `<script src="…">`，`src` 是第一個屬性。
- [x] 模組公開頁尾來源清單，五項依現行頁尾順序，連結文字、站名、網址與規格「來源清單」表逐字相符。
- [x] 模組公開單卡頁網址函式：輸入卡片密碼，輸出查牌網首頁網址加 `?code=<卡片密碼>`。查牌網首頁網址在模組內只定義一次，清單與這個函式共用。
- [x] 模組公開卡圖網址函式：輸入卡片密碼，輸出卡圖網址，與現行逐字相同。
- [x] 呈現模組拿掉卡圖與查牌網兩個網址常數，卡名連結、卡片縮圖、異圖輪播三處改呼叫來源模組。
- [x] index.html 說明載入順序的註解已更新，列入來源模組。
- [x] 既有前端測試全過：`node --test script/web/engine.test.js script/web/render.test.js`。
- [x] 在 headless 瀏覽器實際開頁面：搜一張有異圖的卡，確認卡名連結的 href、縮圖的 src、切換異圖後的 src，都跟改動前（main）逐字相同。

## Comments

- 實看驗收（2026-11-11，headless Chrome + playwright-core）：同一台本機伺服器並排放 main 版與本票版的 `web/`，各開 `#code=89631139`（青眼白龍，本卡加 16 張異圖）。卡名連結 href 兩邊都是 `https://salix5.github.io/query/?code=89631139`；縮圖 src 起始 `https://cdn.jsdelivr.net/gh/salix5/query-data@master/pics/89631139.jpg`，按下一張兩次、上一張三次（含繞回最後一張 89631155）的六個 src 序列，以及預載發出的 11 個卡圖請求網址，兩邊逐字相同；本票版沒有頁面錯誤。
- 頁尾來源清單另用 node vm 載入模組，與規格「來源清單」表五列的連結文字、站名、網址逐字比對相符。
- 來源模組名 `Sources`，公開 `FOOTER`、`cardPageUrl(id)`、`cardImageUrl(id)`；載入順序排在 hash.js（網址）之後、render.js（呈現）之前。
