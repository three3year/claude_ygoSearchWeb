# 寫規格 2:下游改讀與匯出

Type: task
Mode: HITL
Status: open
Blocked by: 04, 02
Map: ../map.md

## Question

跑 `/mattpocock-skills:to-spec` 再 `/mattpocock-skills:to-tickets`(spec.md 先過 `review-mirror`)。範圍:patient.py、anaphora.py、places.py 改讀論元片語與結構化區域欄、刪正則式,動作對象全語料結果不變或逐卡說明;export_categories.py 改匯出每句的框架與欄位(含此卡/非此卡為每框一欄、三個位置都匯)、沿用原文與卡面參數雜湊;categories.py 的歸葉退場,類別樹改為具名查詢目錄、建置期機械編譯成述詞、編不出來的列清單;「全語料沒有命中的具名查詢不留」的檢查;拆解頁與草案、檢驗摘要三個鏡像的去留。

to-spec 裡要順手定的細節:具名查詢來源檔形狀(沿用 category_tree.json 葉條件編譯,還是改寫成直接寫述詞欄位的目錄檔;以「具名查詢編譯試跑」的三張清單為依據)、極性類耐性/限制怎麼用欄位表達、玩家「相對」、開葉門檻要不要留、匯出檔格式與版本號。

答案記 spec.md 與 issues/ 的路徑。

## Comments

- 2026-10-31(wayfinder,票 02 交件):編譯規則與三張清單在 [02 的 Answer](02-named-query-compile-dry-run.md#answer);寫規格 2 時要定——「全語料沒有命中的具名查詢不留」算哪些位置(只算效果位時 取り除く@お互いのフィールド 是空的,算三位置就不空);若規格 1 不把 から 搬進所在,非移動類詞元的所在葉要編成「所在=X 或 來源=X」;規格 1 換成片語中心詞後重跑 tools/compile_dry_run.py 確認關鍵詞葉張數。
