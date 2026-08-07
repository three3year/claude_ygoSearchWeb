# 06 — Genesys 點數整合

**What to build:** 總表每張卡新增 `genesys_points` 欄位(整數;官方點數表未列點的卡為 0)。資料來自 YGOPRODeck API 全量 dump(`misc_info.genesys_points`,以卡片密碼對齊;主卡沒對到時嘗試異圖密碼)。一鍵更新殼把 YGOPRODeck 抓取納入來源下載,萃取成本地小 JSON 後交管線整合;報告輸出列點卡數。

**Blocked by:** 02 — 日英卡名整合

**Status:** resolved

- [x] 總表卡片含 `genesys_points` 欄位,值以密碼從 Genesys 來源對齊(以 fixture 驗證)
- [x] 主卡密碼沒對到、但異圖密碼有對到時,採用異圖的點數(以 fixture 驗證)
- [x] 來源未列點的卡欄位為 0,不影響收錄(以 fixture 驗證)
- [x] 不給 Genesys 來源時行為與現況相同(欄位 0、報告無 Genesys 段)
- [x] 報告輸出 Genesys 列點卡數
- [x] 一鍵更新殼下載 YGOPRODeck 全量並萃取 {密碼: 點數} 為本地 JSON,離線模式沿用既有檔
- [x] 自動化測試不實際連網
- [x] 對真實資料執行,記錄實際列點數

## Comments

2026-08-07 來源驗證:YGOPRODeck `cardinfo.php?misc=yes` 全量 14,478 筆約 24MB,
`misc_info.genesys_points` 以密碼為主鍵直接對齊(Pot of Greed=30 驗證正確);
未列點的卡無此欄位,語意即 0 點。salix5 的 genesys_point.json(889 筆)為 cid 鍵,不採用。

2026-08-07 實作完成:真實資料 703 張非 0 點(來源命中 14,203/14,207);
陷阱:genesys_points 只在 API 帶 format=genesys 參數時才出現,已修正 URL 並留註解。
抽查:強欲之壺 30、落雷 2、青眼白龍 0。冪等驗證通過。
