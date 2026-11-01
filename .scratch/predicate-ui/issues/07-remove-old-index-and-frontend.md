# 07: 刪舊欄與前端舊路徑

**What to build:** 網站只剩述詞一套搜尋:引擎、前端、索引建置都不再碰舊動作類別,data.js 變小。清單以 predicate-index 票 05 Comments「要刪的舊東西」的網站建置、前端、測試與 harness 三段為準,並先看它列的七條出入。分詞鏈與舊工具在票 08,舊匯出檔這張還在、只是建置不再讀。

**Blocked by:** 03, 04, 05

**Status:** ready-for-agent

- [ ] 引擎的舊軸函式、`q.act` 分支、`act` mark 與相關匯出都刪掉;`Acat` 只留目錄導覽
- [ ] 建置不再讀舊匯出檔:舊六欄 `ae/ac/aes/aen/acs/acn`、`VOCAB.acat`、`META.acat_digest`、參數與檢查、報告列都刪掉;`_content_digest`、`_export_stale` 留給框架部分
- [ ] `vocab.py` 的同名舊 tag 值域不刪;`part["table"]` 順手改名
- [ ] 舊樣式、harness 的舊驅動函式、`engine.test.js` 與 `render.test.js` 的舊段逐條看過:動作類別線的刪,述詞線以外的合成資料保留
- [ ] data.js 重建:舊欄、`VOCAB.acat` 不在檔內;其餘欄與 `fr`、`fl`、框表除了 digest 外相同(比對方法與結果記進 Comments);同輸入建置兩次逐位元組相同
- [ ] 全語料 783 格與 237 個具名查詢照過;體積實測記進 Comments,對照規格 Further Notes 的估計
- [ ] node 測試與 script/web 全過;真瀏覽器桌面開一次,console 無錯
