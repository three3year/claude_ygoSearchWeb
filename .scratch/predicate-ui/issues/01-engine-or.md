# 01: 引擎的 OR

**What to build:** `Engine.runQuery` 接受 `q.or = [條件片段…]`:AND 區全部成立,再加 OR 區任一成立。片段的形狀是查詢本身的子集(左側條件的鍵、`preds`)。聯集、命中句、命中框都由引擎合併,介面只要送一個查詢。見規格「引擎的 OR」段與「OR 區在哪裡算?」的決定。工作在新整合分支 `predicate-ui`(基於 `predicate-index`)上開始。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] 每個片段與主查詢合併成一個分支,卡命中任一分支就中;結果依資料順序
- [ ] `rows` 取各分支聯集後排序,`hits[k]` 與 `marks` 合併去重;任一分支 `rows` 是 `null` 時以有句的分支為準,全是 `null` 才是 `null`
- [ ] 述詞序號是整個查詢的編號:先主查詢的 `preds.inc`,再依片段順序接各片段的 `preds.inc`
- [ ] 例子都走 `runQuery`:兩個分支聯集、AND 加 OR、排除標籤在 OR、左側條件在 OR、句層條件在 OR、述詞序號跨分支、`rows` 有 `null` 的分支、`hits` 去重
- [ ] 沒有 `q.or` 或它是空的時行為不變:夾具與全語料 783 格照過
- [ ] node 測試全過
