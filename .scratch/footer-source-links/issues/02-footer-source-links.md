# 02: 頁尾資料來源改成連結

**What to build:** 訪客在頁尾第二行看到 `資料來源：中文卡文、卡圖 · 日英卡名、日文卡文 · MD 稀有度、MD 禁限 · Genesys 點數、OCG/TCG 禁限 · 效果類型`，五段各是一個連結，在新分頁開啟該來源的網站，懸停時顯示「資料來源：<站名>」。頁尾字級變大、對比提高，連結用強調色。第一行的資料更新時間、置中、貼齊視窗底都跟現在一樣。規格見 `.scratch/footer-source-links/spec.md`。

對照參照實作（規格「與 ark-keyword 的對照」表，各列都經使用者選過）：
- 同 ark：連結開新分頁並加 `noopener noreferrer`（Q2）、用資料當連結文字（Q3）、項目間用「 · 」分隔（Q10）、字級 0.82rem 與次要文字色、連結用 `--accent`（Q6）。
- 與 ark 不同：
  - 兩行而不是一行（Q1）。
  - 「資料來源：」前綴（Q3）。
  - 項目內用「、」，ark 用「與」（Q9）。
  - 懸停提示用全形冒號、寫站名，ark 用半形冒號、寫 GitHub 資料庫名（Q11、Q12）。
  - 置中（Q7）、內距 4px 且貼齊視窗底（Q8）。
  - 不寫自動測試（Q14、Q17）。

**Blocked by:** 01 — 來源模組（頁尾依它的清單組出來）

**Status:** resolved

- [x] 頁面骨架的第二行改成空段落，由主流程在初始化時依來源清單填入：開頭是純文字「資料來源：」，後接五個連結，連結之間以「 · 」分隔。
- [x] 每個連結開新分頁（`target="_blank"`），並帶 `rel="noopener noreferrer"`。
- [x] 每個連結的懸停提示是瀏覽器原生 `title`，內容為「資料來源：<站名>」，全形冒號。
- [x] 連結文字與站名以文字節點或 `textContent` 寫入，不拼接 HTML 字串。
- [x] 第一行資料更新時間不變：META 有欄位時顯示 `資料更新時間：YYYY-MM-DD HH:mm (UTC+8)`，沒有欄位時整行隱藏。
- [x] 頁尾字級改為 0.82rem，文字顏色改用 `--text-dim`；頁尾連結顏色用 `--accent`，底線用瀏覽器預設。
- [x] 置中、上下內距 4px、左右 20px、上框線、內容不滿一屏時貼齊視窗底，都維持現狀。
- [x] 兩段過時的註解已更新：index.html 頁尾上方說「唯一動態的是第一行」那段，以及樣式表頁尾規則上方說「兩行小字」那段。
- [x] 既有前端測試全過：`node --test script/web/engine.test.js script/web/render.test.js`。
- [x] 在 headless 瀏覽器實際開頁面驗收：
  - 第二行的字面與分隔符號跟規格逐字相同。
  - 五個連結的網址與規格「來源清單」表相符，都帶 `target` 與 `rel`。
  - 懸停提示文字正確。
  - 字級與顏色已套用。
  - 手機寬度（360px）沒有水平捲動，來源行會自動換行。
  - 還沒搜尋時，頁尾貼齊視窗底。

## Comments

- 實看驗收（2026-11-11，headless Chrome + playwright-core，本機 `python -m http.server` 綁 checkout-port 給的 4848，綁不到即失敗）：改動前同一支驗收腳本 10 項失敗，改動後 24 項全過，無頁面錯誤。
  - 第二行 textContent 與規格逐字相同；第一個子節點是純文字「資料來源：」。
  - 五個連結的文字、href 與「來源清單」表相符，都帶 `target="_blank"`、`rel="noopener noreferrer"`，`title` 為「資料來源：<站名>」。
  - 1280×800：頁尾 computed 字級 13.12px（0.82 × 根字級 16px）、文字色 rgb(169, 176, 193)（`--text-dim`）、連結色 rgb(78, 161, 255)（`--accent`）、底線 underline；置中、內距 4px 20px、上框線 1px solid；未搜尋時頁尾底邊 = 視窗高 800。
  - 360×640：scrollWidth = clientWidth = 360，來源行高 63px（約三行）。
  - 資料更新時間：有欄位顯示「資料更新時間：2026-08-23 02:04 (UTC+8)」；攔截 data.js 拿掉 `data_updated_at` 後該行 hidden、display none。
  - `#code=89631139` 卡名連結與卡圖網址與改動前相同。
