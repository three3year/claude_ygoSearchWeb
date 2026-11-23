# 05: 刪掉舊讀法

**What to build:** 查詢判斷只剩「攤平再比對」一條路徑。解讀卡片結構的程式只有攤平一處,之後規則補了新形狀只改那裡。

- 刪掉直接讀卡片結構的舊比對,以及切換新舊路徑的開關,不留相容層。
- 只給舊路徑用的函式一併刪掉;被別處(反向檢查、報告)用到的留著。
- 全庫新舊比對的工具已經完成任務:刪掉,或改成不依賴舊路徑的形式,由實作者定並在 Comments 說明。
- 模組開頭的說明更新成新的結構。

- 規格:需要你決定的「Q9」;實作決策「查詢判斷」最後一條;使用者故事 54。
- 前提:票 04 的全庫新舊比對結果已記在它的 Comments。

**Blocked by:** 04

**Status:** ready-for-agent

- [x] 舊的比對路徑與切換開關已刪除,沒有殘留只給它用的程式
- [x] `run_query` 的呼叫方式與回傳形狀不變
- [x] 現有查詢測試不改、全綠;既有各組測試全綠
- [x] 模組說明已更新

## Comments

### 實作(2026-11-23)

`run_query(structures, cards, query)` 只剩攤平(`action_rows.index_of`)+ 比對(`row_match.match_rows`)一條路徑;`path` 參數與 `PATH_STRUCTURE`、`PATH_ROWS` 刪掉,不留相容層。`action_query.py` 從 1034 行剩 623 行。

**刪掉的(只給舊路徑用)**,都在 `action_query.py`:舊的 `run_query` 本體、`_Expansion`(舊的經引用展開)、`segment_hit_lines`、`segment_in_scope`、`replaced_by`、`_unparsed_references`、`action_literals`、`literal_has_actions`、`zones_match`、`_as_zone`、`_position_sensitive`;`_Judge` 的 `object_matches`、`query_matches`、`exists_cache` 與建構子的 `query` 參數(`card_fits` 從來不看查詢)。

**搬家的**(原本被新模組從 `action_query` 借用,現在放到唯一用它的地方,名字不變):
- 攤平 `action_rows.py`:`segment_actions`、`_is_doer`(與 `SYMMETRIC_ACTION`)、`incomplete_reason`、`_object_incomplete_reason`(與 `REASON_REF_MISSING`、`REASON_SAME_DIFFERENT`)、`_has_stem`。都是解讀卡片結構的,攤平之外沒人用。
- 比對 `row_match.py`:`_normalise`(查詢鍵的預設值與正規化,與 `DEFAULT_KINDS`、`MODIFIED_KEYS`)、`modified_matches`、`VIA_GROUP`、`VIA_GENERIC`。
- 候選卡 `candidate_cards.py`:`_referenced_names`(舊路徑刪掉後只剩它用)。

**留在 `action_query.py` 的**:模組說明(查詢鍵、回傳形狀、經引用與未解析組的規則)、`run_query`,與條件式判斷(`CardView`、`eval_condition`、`card_attr`、`STATE_ATOMS`、`same_different_*`、`is_generic`、`is_this_card`、`_Judge`、`resolve_references`)。條件式判斷被候選卡、比對「給條件」與建置第二輪(`card_structure` 的 `resolve_references`)共用,GLOSSARY 也指著這些名字,所以不另開模組。`candidate_cards` 仍從這裡 import `_Judge`、`_compared_values`、`_fold`、`_name_text`:`CandidateCards` 是 `_Judge` 的子類、同一套判法換算法,屬於同一族,不搬。`action_rows` 與 `candidate_cards` 都 import 這個模組,所以 `run_query` 在函式裡才 import 攤平與比對(避免循環)。反向檢查、報告沒有用到任何刪掉的東西。

**模組說明**:`action_query` 開頭改寫成兩步的結構(攤平是唯一解讀卡片結構的地方,比對只讀列)與這個模組留下的條件式判斷;`row_match` 開頭補一句查詢鍵的預設值在這裡。README 的檔案表(`action_query`、`action_rows`/`row_match` 兩列)跟著改;GLOSSARY「做動作的一方」那行的 `action_query._is_doer` 改成 `action_rows._is_doer`。

**兩支新舊比對工具刪掉**:`compare_query_paths.py`、`run_tests_on_rows.py` 只能拿新路徑比舊路徑,舊路徑沒了就沒有東西可比;新舊全庫比對結果已記在票 04。改成不依賴舊路徑的形式(例如存一份結果當快照)等於另做回歸測試,這張票不做。README 的建置步驟裡兩條指令一併刪掉。

**測試的改動**(都在票 03 新增的 `test_action_rows.py`,只動開關):
- 刪掉 `RowsPathTest.test_unknown_path_is_rejected`(只驗 `path` 給錯值會拋錯,開關沒了)。
- 兩個 helper 與 `test_the_doer_line_is_not_the_card_acted_on` 呼叫 `run_query` 時拿掉 `path="rows"`;斷言不變。模組說明改成不提 `path`。
- 其餘測試檔一行沒動。

### 驗證

- `python -X utf8 -m unittest discover -s script/action_structure`:956 個全綠(票 04 的 957 個減掉上面刪的 1 個)。
- 其他各組:`script/card_list`、`faq_info`、`tag_card`、`text_format`、`web` 的 unittest 全綠;`node --test` 113 個全過。
- 全庫工具(票 04 跑過的五支),改動前後各跑一次,stdout 逐位元組相同(`cmp`):

| 工具 | 輸出位元組 | 前後 |
|---|---|---|
| `.scratch/action-structure/stats/milestone_stats.py` | 3285 | 相同 |
| `.scratch/action-structure-m2/stats/m2_compare.py` | 2094 | 相同 |
| `.scratch/action-structure-m3/stats/m3_compare.py` | 4837 | 相同 |
| `.scratch/action-structure-m3/stats/m3_condition_only.py` | 840 | 相同 |
| `.scratch/action-structure-m3/stats/m3_rechecks.py` | 2941 | 相同 |

- `_Judge` 改了建構子,`resolve_references` 另驗一次:讀 `data/action_structure.json`,把 28 個解析出的引用節點的候選卡與 `any` 清掉,重跑 `resolve_references`,序列化後與原產物逐位元組相同。
