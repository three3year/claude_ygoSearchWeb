# 寫規格乙:針對卡片

Type: task
Mode: HITL
Status: open
Blocked by: 02
Map: ../map.md

## Question

跑 `/mattpocock-skills:to-spec` 再 `/mattpocock-skills:to-tickets`(spec.md 先過 `review-mirror`)。決定照[三項需求的設計決定](01-grill-three-requirements.md)的「乙」段,不重問。排在甲之後:甲改了匯出格式與位置,乙在它之上再加。

範圍:匯出修飾語的值與回指目標的段;回指線解目的片語(只記目標、不回填);參考評估器 `predicate.py` 與 JS 評估器都加 針對卡片 欄(兩種模式),夾具對上;字段人工對照表;抽屜的針對卡片欄(中文卡名自動完成、網址記卡片密碼);結果卡片的鈕與目錄選擇窗;句尾「部分條件未比對」;兩輪 LLM 抽驗。

to-spec 裡要順手定的細節:

- 匯出形狀:修飾語值怎麼編(數值欄位/比較/數字、種族屬性用 vocab 碼還是日文)、回指目標存段還是先行框索引、data.js 體積實測。
- 字段「卡名包含」的誤中先量,再定對照表的格式與住處。
- 比對器在 JS 重寫還是由建置期預算(卡 × 框太大,大概只能 JS)、與 `_segment_blocker` 的對照方式。
- 目錄選擇窗 261 列逐列算張數的實測耗時。
- 5 張抽驗卡的確切名單(都要在涵蓋範圍內)。

答案記 spec.md 與 issues/ 的路徑。
