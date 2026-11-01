# 寫規格 4:介面與網址

Type: task
Mode: HITL
Status: claimed
Blocked by: 06, 03
Map: ../map.md

## Question

跑 `/mattpocock-skills:to-spec` 再 `/mattpocock-skills:to-tickets`(spec.md 先過 `review-mirror`)。範圍:query.js 的側欄——類別樹改為具名查詢目錄導覽,點葉填入一張述詞卡,卡上欄位可改、可加、可刪,新增空白卡,排除卡;「含代價」勾選與「動作對象」全軸 radiogroup 退場(成為卡上欄位);hash.js——沒改過的具名查詢用葉路徑、改過的展開成欄位對,多張卡、排除、多值的寫法,未知參數安靜忽略;render.js——句尾標籤與命中強調;acat.js 改讀目錄。以「述詞卡與樹導覽的靜態原型」為基礎。

to-spec 裡要順手定的細節:句尾標籤在不互斥下顯示什麼(使用者述詞命中的框、所有命中的具名查詢、或命中框的詞元)、hash 的分隔符與葉名/字面裡 › : | ; 的轉義、卡名改了之後怎麼顯示、手機寬度的摺疊。

答案記 spec.md 與 issues/ 的路徑。

- 2026-11-01(wayfinder,票 06 resolved):規格 3 裁定舊欄與舊鏈留到規格 4 切換,**本票範圍多一批刪除**:舊匯出檔、歸葉程式、舊匯出、舊樹檔、`ae/ac/aes/aen/acs/acn`、`VOCAB.acat`、`actSel/actRows`、舊軸 UI 與相關測試(清單起點在 named-queries 票 11 Comments,規格 3 交件票會核對)。另外引擎的述詞沒寫 位置 就是三個位置都看,卡片要帶預設;命中句會包含領起句框繼承到的 ● 子句,`hits` 的框所在句分得出自己的或繼承的。
- 2026-11-01(規格 3 交件):寫規格前讀 [predicate-index 票 05 Comments](../../predicate-index/issues/05-handoff.md)「給規格 4 的對照」:查詢與結果形狀(`q.preds`、`rows`、`hits`、`marks`)、VOCAB 新部分、`pred` mark 還沒有標籤、票 04 自定的三件事、核對過的要刪清單(比 named-queries 票 11 多幾項、更正兩項;`.scratch/*/tools/` 三支工具與 `llm_check.py` 也 import 舊歸葉程式,要先定它們的去留)。整合分支 `predicate-index`。站主可能要的決定:切換前是否先發布一次重建過的 data.js(同票 Comments「網站行為」)。
- 2026-11-01(票 03 resolved):介面照[原型票 Answer](03-predicate-card-prototype.md),**本票 Question 的範圍要跟著改**:沒有空白卡;標籤分 AND、OR 兩區,引擎與 hash 要支援 OR;卡上不改詞元;句尾標籤已定 a;條件一變就重查。
