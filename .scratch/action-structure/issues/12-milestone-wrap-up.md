# 12: 里程碑收尾

**What to build:** 站主拿到第一個里程碑的完整交付:10 張標準卡的查詢斷言全過、整張通過反向檢查;三份全庫報告(覆蓋、反向檢查、區塊邊界)以最新規則重出,站主看完決定下一步(前端、LLM 補欄、哪類未解析優先補)。

- 不設數字門檻;交付報告與摘要,不做新功能。
- 摘要列:各報告的主要數字、未解析與反向檢查不通過的前幾大原因與張數、建議的下一步候選。

**Blocked by:** 03, 07, 08, 09, 11

**Status:** ready-for-agent

- [x] 10 張標準卡的全部斷言通過、整張通過反向檢查(全庫產物逐張 `check_card` 核對;各票斷言的站主核可:**待核可**,清單在摘要「待核可的查詢斷言」)
- [x] 三份全庫報告重出,同一輸入兩次產出相同
- [x] 全建置鏈與既有各組測試全綠
- [x] 摘要交站主(`report/milestone-1-summary.md`;站主看完決定下一步:**待站主**)

## Comments

### 2026-11-07 票 12 實作(as/12)

**驗收**:測試 action_structure 244(原 243 + 本票 1)、card_list 66、faq_info 43、tag_card 379、text_format 55、text_glossary 37、web 104、`node --test` 121,全綠。全建置鏈(`build_archetypes.py` 不帶 `--fetch` → `build_structure.py` → `build_report.py` → `build_reverse_check.py` → `build_block_boundaries.py` → `stats/old_style_phrases.py`)跑兩次,產物與五份報告逐位元組相同。10 張標準卡 + 白き森のリゼット 在全庫產物(`load_structures` 讀回)上逐張 `check_card` 全部通過;各卡測試夾具的卡文與官方 DB 文本逐字相同。

**修了一個讀回漏洞**(實作決定,請站主留意):第一次逐張核對時 滅びの黒魔術師 在全庫產物上不通過(「被改的屬性無模板:視為」),記憶體建置卻通過。`load_structures` 沒補回修飾段被改屬性的區域(side、side_source)、prefix、also、suffix、items[].tail,以及階段前提的 side、字段原子的 setcodes、分歧前提的區域;全庫 170 張讀回不等,反向檢查多報 130 段。只改讀回、產物位元組不變;修後全庫讀回不等 0 張,反向檢查通過 17,091 → 17,220。新增往返測試 `test_card_structure.test_treat_as_and_phase_premise_survive_the_round_trip`。

**與整合分支已 commit 的報告差異**:`coverage.md`、`block_boundaries.md`、`archetypes.md` 相同;`reverse_check.md` 只差上面的讀回漏洞;`old_style_phrases.md` 在整合分支上沒在票 09 之後重跑(「後」欄停在票 08 合併時),本票刷新。

**摘要**:`.scratch/action-structure/report/milestone-1-summary.md`(各報告主要數字、標準卡狀態、未解析優先順序、各票待核可斷言與請站主留意的實作決定、留給之後的事)。新增統計腳本 `stats/milestone_stats.py`(整張通過張數、只差一種原因、常用動作查詢的命中/未解析、述語解析不出的寫法粗篩),只印 stdout。
