# 寫規格 3:索引與述詞評估器

Type: task
Mode: HITL
Status: resolved
Blocked by: —(05、01 已 resolved;2026-11-01 解鎖;規格 2 同日交件,見 Comments 末條)
Map: ../map.md

## Question

跑 `/mattpocock-skills:to-spec` 再 `/mattpocock-skills:to-tickets`(spec.md 先過 `review-mirror`)。範圍:build_index.py 讀新匯出檔,每句標記句帶框架清單、每框帶全部封閉類欄位加中心詞字面(字典編碼),三個位置都進;VOCAB 帶各欄值域與具名查詢目錄;建置期檢查(雜湊、未知值、具名查詢編得出來);engine.js 的述詞評估器——述詞內同欄多值 OR、述詞間卡層 AND、排除述詞卡層優先、句層條件(效果類型、必發/選發、效果文、舊式卡文不中)照現行、命中句與命中框回傳給顯示;舊的 ae/ac/aes/acs/aen/acn 與 actSel/actRows 退場。索引編碼依「索引體積與評估器速度實測」的數字定。

to-spec 裡要順手定的細節:條件位框架的述詞語意(対象とする、存在 當可搜動作?條件框的施事者/受事者怎麼讀、領起句條件複製給 ● 子句與否)、具名查詢編譯在建置期還是前端載入時、評估結果的句層回傳形狀。

答案記 spec.md 與 issues/ 的路徑。

- 2026-11-01(wayfinder,票 05 交件):規格 2 已寫完切票(`.scratch/named-queries/`),本票解鎖。寫規格 3 時讀——匯出檔 `data/action_frames.json` 的框列欄與目錄(張數、卡集合雜湊)、參考評估器與夾具(規格 2 票 05/06/08)、要刪的舊東西清單(規格 2 票 11 Comments);索引編碼數字在票 01 Answer。規格 2 的 implement 還沒做,規格 3 可先寫、票等規格 2 交件後再動。
- 2026-11-01(named-queries 票 11 交件):規格 2 已交件(整合分支 `named-queries`,票 01〜11 全部 resolved),本票的 Blocked by 全部 resolved、解鎖。寫規格 3 時讀 [named-queries 票 11 Comments「給規格 3 的對照」](../../named-queries/issues/11-handoff.md):匯出檔的欄與值域(`predicate.FIELDS`/`EXPORT_PATH`/`DOMAIN`,框列鍵 `FRAME_KEYS`、版本 1)、目錄 260 列的張數與雜湊(算法含逗號分隔)、夾具 `.scratch/effect-tokenize/predicate-fixture.json`(96 條例子 + 雜湊 + 張數)、中間產物 `frame_queries.json`、要刪的舊東西清單(舊匯出檔、歸葉程式、舊匯出、舊索引欄位 ae/ac/aes/aen/acs/acn、VOCAB.acat 的葉號、舊樹檔、frame_categories/card_categories、test_categories/test_export、engine.js 的 actSel/actRows);未決三題在 `.scratch/effect-tokenize/llm-check/summary.md`「需要你決定的」(対象とする 進目錄、態空看主語、全部類比對順序與 以下の効果),規格 3 to-spec 要先裁或帶進去。

## Answer

2026-11-01 resolved。規格 `.scratch/predicate-index/spec.md`(ready-for-agent;鏡像 https://claude.ai/artifact/NTeWXqMQc4WLHa1Tbf6UWC )與 `.scratch/predicate-index/issues/` 5 張票。八題裁定都在規格「需要你決定的」。與本票原範圍不同的一處:舊欄、`actSel/actRows` 與舊鏈**不在規格 3 退場**,留到規格 4 介面切換同一波刪(站主裁定);本票「to-spec 裡要順手定的細節」都已定——條件位框不特別處理、領起句的框 ● 子句也看、具名查詢述詞已在匯出檔明文、前端查詢時才編成整數碼、結果回傳 `rows` 加 `hits`。索引編碼改選框表 D(真實匯出檔實測,票 01 的 C +270 KB gz、D +79 KB gz)。
