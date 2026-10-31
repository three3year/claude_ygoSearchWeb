# 寫規格 3:索引與述詞評估器

Type: task
Mode: HITL
Status: open
Blocked by: 05, 01
Map: ../map.md

## Question

跑 `/mattpocock-skills:to-spec` 再 `/mattpocock-skills:to-tickets`(spec.md 先過 `review-mirror`)。範圍:build_index.py 讀新匯出檔,每句標記句帶框架清單、每框帶全部封閉類欄位加中心詞字面(字典編碼),三個位置都進;VOCAB 帶各欄值域與具名查詢目錄;建置期檢查(雜湊、未知值、具名查詢編得出來);engine.js 的述詞評估器——述詞內同欄多值 OR、述詞間卡層 AND、排除述詞卡層優先、句層條件(效果類型、必發/選發、效果文、舊式卡文不中)照現行、命中句與命中框回傳給顯示;舊的 ae/ac/aes/acs/aen/acn 與 actSel/actRows 退場。索引編碼依「索引體積與評估器速度實測」的數字定。

to-spec 裡要順手定的細節:條件位框架的述詞語意(対象とする、存在 當可搜動作?條件框的施事者/受事者怎麼讀、領起句條件複製給 ● 子句與否)、具名查詢編譯在建置期還是前端載入時、評估結果的句層回傳形狀。

答案記 spec.md 與 issues/ 的路徑。
