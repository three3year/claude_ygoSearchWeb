# 03 — footer 三行與頂部建置時間下架

**What to build:** 訪客在頁尾看到三行純文字聲明:來源一段(效果類型依官方 QA
判定・中文卡片資料與卡圖來源於查牌網・日文/英文卡名資料來源於
ygopro-database・Master Duel 稀有度來源於 Master Duel Meta・Genesys 點數
來源於 YGOPRODeck)、「資料更新時間：2026-08-17 19:41 (UTC+8)」(全形冒號)一行、
KONAMI 詳盡版免責一行(定稿文案見 spec)。META 缺資料更新時間欄位時第二行
整行消失。頂部資訊列不再顯示「建置於…」,只留卡數與效果句數。手機寬度下
來源段自動換行、不出橫向捲軸。

**Blocked by:** 02 — 建置管線把資料更新時間寫進 META(footer 讀的欄位由它產出)。

**Status:** done

- [x] 時間格式化為純函式:`2026-08-17T19:41:03+0800` → `2026-08-17 19:41 (UTC+8)`
- [x] 壞輸入(空值、非字串、缺 offset 等非預期形狀)原樣返回,不出 NaN/Invalid Date
- [x] footer 三行如 spec 定稿文案,純文字、無外部連結
- [x] META 無資料更新時間欄位 → 第二行整行不出現(HTML 預設 hidden,main.js 只在有值時解開)
- [x] 頂部資訊列移除「建置於…」;卡數與效果句數照舊
- [x] 手機寬度 footer 不撐爆版面(一般文字自然換行,小字置中)
- [x] 測試走前端接縫 3 harness:DRIVER 加 `__fmtTime` 鉤子驗格式與壞輸入
- [x] 重建 data.js 後於 headless Chrome 實看 footer:三行齊、時間行
      「資料更新時間:2026-08-08 17:57 (UTC+8)」、頂部無建置時間
