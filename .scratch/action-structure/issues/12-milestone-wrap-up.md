# 12: 里程碑收尾

**What to build:** 站主拿到第一個里程碑的完整交付:10 張標準卡的查詢斷言全過、整張通過反向檢查;三份全庫報告(覆蓋、反向檢查、區塊邊界)以最新規則重出,站主看完決定下一步(前端、LLM 補欄、哪類未解析優先補)。

- 不設數字門檻;交付報告與摘要,不做新功能。
- 摘要列:各報告的主要數字、未解析與反向檢查不通過的前幾大原因與張數、建議的下一步候選。

**Blocked by:** 03, 07, 08, 09, 11

**Status:** resolved

- [ ] 10 張標準卡的全部斷言通過、整張通過反向檢查(全庫產物逐張 `check_card` 核對;各票斷言的站主核可:**待核可**,清單在摘要「待核可的查詢斷言」)
- [x] 三份全庫報告重出,同一輸入兩次產出相同
- [x] 全建置鏈與既有各組測試全綠
- [x] 摘要交站主(`report/milestone-1-summary.md`;站主看完決定下一步:**待站主**)

## Comments

### 2026-11-07 票 12 實作(as/12)

**驗收**:測試 action_structure 244(原 243 + 本票 1)、card_list 66、faq_info 43、tag_card 379、text_format 55、text_glossary 37、web 104、`node --test` 121,全綠。全建置鏈(`build_archetypes.py` 不帶 `--fetch` → `build_structure.py` → `build_report.py` → `build_reverse_check.py` → `build_block_boundaries.py` → `stats/old_style_phrases.py`)跑兩次,產物與五份報告逐位元組相同。10 張標準卡 + 白き森のリゼット 在全庫產物(`load_structures` 讀回)上逐張 `check_card` 全部通過;各卡測試夾具的卡文與官方 DB 文本逐字相同。

**修了一個讀回漏洞**(實作決定,請站主留意):第一次逐張核對時 滅びの黒魔術師 在全庫產物上不通過(「被改的屬性無模板:視為」),記憶體建置卻通過。`load_structures` 沒補回修飾段被改屬性的區域(side、side_source)、prefix、also、suffix、items[].tail,以及階段前提的 side、字段原子的 setcodes、分歧前提的區域;全庫 170 張讀回不等,反向檢查多報 130 段。只改讀回、產物位元組不變;修後全庫讀回不等 0 張,反向檢查通過 17,091 → 17,220。新增往返測試 `test_card_structure.test_treat_as_and_phase_premise_survive_the_round_trip`。

**與整合分支已 commit 的報告差異**:`coverage.md`、`block_boundaries.md`、`archetypes.md` 相同;`reverse_check.md` 只差上面的讀回漏洞;`old_style_phrases.md` 在整合分支上沒在票 09 之後重跑(「後」欄停在票 08 合併時),本票刷新。

**摘要**:`.scratch/action-structure/report/milestone-1-summary.md`(各報告主要數字、標準卡狀態、未解析優先順序、各票待核可斷言與請站主留意的實作決定、留給之後的事)。新增統計腳本 `stats/milestone_stats.py`(整張通過張數、只差一種原因、常用動作查詢的命中/未解析、述語解析不出的寫法粗篩),只印 stdout。

### 2026-11-07 code review 後留給站主裁決的事(as/review)

code review(Standards + Spec)修正已做的不列;下列是實作者判過、spec 沒明寫或與 spec 字面不同的決定,本輪**不改程式**,請站主裁決。每條附位置。

1. **做代替的段也被「代替」閘門擋**(`script/action_structure/action_query.py:558-562 segment_in_scope`):spec 只說被代替段在查詢含「代替」時才看;票 08 票面寫「② 只在查詢含代替時命中」,實作照票面把做代替的段(`replaces` 有值、「代わりに〜」)也一起擋。要不要讓做代替的段預設可查?
2. **泛用原子加「表示形式」**(`action_query.py:58 GENERIC_ATOMS`):spec 的泛用定義只有大類、位置、控制方;實作者把表側/裏側視為區域狀態,也算泛用(票 06)。
3. **字段中文名配不到時退而數全部卡**(`archetype_table.py:139-146`,110 筆,`report/archetypes.md`「用全部卡配對」一節有標):同 setcode 的卡都沒引用字段名時用全部卡的成對;配錯的要寫補丁。
4. **「EXデッキの」位置原子寫進初始位置**(`segment_extract.py:548-553 new_object`,票 06):名詞修飾的位置原子同時當物件初始位置,後續段「從」沒寫時由此繼承。
5. **「卡片發動」= 魔陷第一個無編號區塊**(`block_split.py:50、247-251`,票 09):舊式魔陷的整段卡文、新式魔陷前言的「このカードを発動するターン、〜」都算卡片發動,之後的「また、」區塊與①②③是編號效果。
6. **極性「可以」只收永續許可(直接攻撃),「〜できる」記 可選+做**(`segment_fields.py:80-93 PERMISSION_ACTIONS / resolve_polarity`,票 08/10):故事 12「可以」預設不命中與段表「可選」格的界線——「このカードは手札から特殊召喚できる」現在是可選的「做」、預設命中。
7. **繼承自推得值也歸推得開關**(`segment_extract.py:764-766`,票 01):「從」繼承的目前位置若當初是推得的,`inferred` 跟著 True,開關關時不算。
8. **註解與 docstring 標點**:CODING_STANDARDS 要全形標點,全庫既有慣例是半形(逗號、括號);本輪不改,請決定是改標準還是改碼。
9. **「未解析/解析不出」界線**:本輪照 spec 的用法統一(整張卡、查詢結果組 → 未解析;區塊/段/物件/格/原子 → 解析不出,GLOSSARY 兩詞條已分工);站主若要單一詞再改。
10. **未結構化的段不列未解析組**(`action_query.py:574-577 segment_hit_lines`、docstring 第 34 行,Spec 27 本輪新加):「〜処理を繰り返す」那一句依 spec 只寫第一輪、不是解析不出,查詢不命中也不列未解析組;「」裡的字面(「〜を全て破壊する」処理)不會被查到。要不要改成列進未解析組?

**本輪不修、列開放事項**(code review 第二節第 15 條、第四節第 29 條):

- 條件式 `op` 的 if 串四處(`action_query.py:288-348 eval_condition`、`reverse_check.py:84-112 _render_atom`、`condition_atoms.py:66-127 parse_modifier`、`premise.py:182-228 render_premise`)、Data Clumps(`seg, card, objects, names, self_id` 一路傳)、`segment_extract.py`(1,052 行)與 `reverse_check.py`(826 行)過大。
- Spec 缺口:內嵌效果「我方」重新綁定與「」となる;條件式 召喚方式/持ち主/裝備或連結/可為物件Y的素材 原子;`段已執行` 抽取;性質變更後後續段讀改後屬性;時機 立即/每次X 與期間 持續/該戰鬥 句型。
