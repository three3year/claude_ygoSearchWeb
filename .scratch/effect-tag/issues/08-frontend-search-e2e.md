# 08 — 前端搜尋端到端

**What to build:** 牌手在站上能用動作 tag 搜卡:索引匯出句層 tag 短碼(陣列的陣列形狀)、查詢引擎句層條件新增 tag 軸(三態、與 kind/必發選發同句耦合)、側欄自值域正典長出類別三態鈕+區域移動起點/終點下拉、hash 序列化、結果命中標記。demo:搜「牌組→手牌」得到正確卡表且命中句有標記。

**Blocked by:** 07 — 首批 tags 已在資料中。

**Status:** resolved(2026-09-20)

- [x] Engine.runQuery 行為測試:tag 三態、排除優先、句層耦合、marks
- [x] 前端 harness 測試綠;零建置紀律不變
- [x] hash 分享往返(stringify/parse/canon)含 tag 軸
- [x] 已貼範圍標示(第一期僅新式卡)在 UI 有說明

完成紀錄:索引匯出句層 `tg`(短碼陣列的陣列,槽位序由正典 slots 宣告)與 `tm`;引擎新增 tag/timing 三態軸(排除優先、與 kind/必發選發同句耦合)與區域移動起點/終點下拉(成本位不命中);側欄兩軸由正典長出、含範圍說明;hash 含 tag/timing/mvf/mvt 往返;命中列 badge 顯示 tag 內容與時機。前端 128 測試綠(node --test)。demo:mvf=d&mvt=h 命中檢索句並標記。
