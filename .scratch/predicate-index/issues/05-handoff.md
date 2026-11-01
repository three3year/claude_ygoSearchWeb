# 05: 交件

**What to build:** 整合分支上全部合併並重跑,確認網站行為沒變、新引擎對上全語料,把給規格 4 的東西交出去。

- 全套重跑:effect-tokenize 全套、node 測試、script/* 五套;分詞鏈全鏈與索引建置;鏈重跑後 `data/` 無意外差異、舊匯出檔 md5 不變、剝鍵與回指、動作對象基準差異 0。
- 實測:1〜5 個述詞的耗時(真引擎、真 data.js)與 data.js 最終體積,記進 Comments,對照規格 Further Notes 的原型數字。
- 文件:GLOSSARY 前端索引條(`fr`、`fl`、框表、VOCAB 新部分、體積實測)、值域正典條例外段(封閉類值域隨匯出檔)、框架述詞條(JS 評估器已對上;● 子句評估時也看領起句的框);ADR-0018 Consequences 補「索引用框表」與「舊欄留到規格 4 切換」兩句;建置產物文件表核對。
- 給規格 4 的對照寫進本票 Comments:查詢與結果形狀(`q.preds`、`rows`、`hits`、`marks`)、VOCAB 新部分、述詞沒寫 位置 就是三個位置都看(卡片要帶預設)、要刪的舊東西清單(抄自 named-queries 票 11 Comments,加 `actSel/actRows` 與舊軸 UI,對照現況核對)。
- 地圖 Decisions so far 的「寫規格 3」補交件註記;地圖票「寫規格 4」補讀哪裡。

**Blocked by:** 04

**Status:** ready-for-agent

- [ ] 全套測試與全部基準比對通過,數字寫進 Comments
- [ ] 實測耗時與體積寫進 Comments
- [ ] 網站手動開一次:現行類別樹、含代價、動作對象、舊網址、句尾標籤照舊
- [ ] GLOSSARY 三條、ADR-0018 兩句、建置產物文件
- [ ] 給規格 4 的對照與要刪清單
- [ ] 地圖與地圖票更新
