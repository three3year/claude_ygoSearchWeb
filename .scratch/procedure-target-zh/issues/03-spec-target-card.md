# 寫規格乙:針對卡片

Type: task
Mode: HITL
Status: resolved
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

## Answer

2026-11-05:規格 `.scratch/target-card/spec.md`(ready-for-agent,鏡像見同資料夾 mirrors.json),票 `.scratch/target-card/issues/01`〜`08`(段的條件共用模組與 ADR 0020 → 針對卡片一路查得到 → 回指與目的片語 / 字段對照表(審核關卡)/ 抽屜欄與標記 → 目錄選擇窗 → 兩條 LLM 抽驗 → 交件)。

to-spec 細節站主全照建議定案:段的條件建置期 Python 解析、JS 只比;回指目標存目標的段;字段用卡名包含加站主核可的三欄對照表;卡名中心詞比全名;抽出段的條件模組與動作對象共用,區間與屬性段兩個錯一起修(另跟著變:卡名全名、魔法・罠 卡種候選、未知比較詞比不了),patient 尺逐框確認後重凍;只有卡面參數比不了的標「部分條件未比對」;子類型 効果 不算有寫條件;目的片語去區域段、とする/なる 不算、方位詞取主人;召喚手續 重ねる 照常比;選擇窗用詞元索引加框→卡反查;網址欄 針對卡片、針對模式;抽驗卡 黑魔導、スカーライト、ホープ・ザ・ライトニング、閃刀姫－カガリ、瞬間融合;寫 ADR 0020。

實算(原型 `.scratch/target-card/tools/`,輸出在 `tools/results/`):data.js gzip 段的條件 +84 KB、回指目標的段 +39 KB;選擇窗 18〜37 ms 對逐列 runQuery 0.7〜1.6 s。定案時七支原型重跑核過,見規格 Further Notes。
