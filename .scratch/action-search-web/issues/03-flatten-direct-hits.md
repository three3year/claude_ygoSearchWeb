# 03: 攤平成列,新的比對路徑先做直接命中

Status: resolved

**What to build:** 查詢判斷多一條「先攤平成列、再比對列」的路徑,和舊的讀法並存;直接命中(特定、泛用兩組)在兩條路徑上結果相同。這是「先加新的、搬過去、再刪舊的」的第一步。

- 攤平:卡片結構加卡片總表 → 完整的列。每條對象線一列,沒有線的段以段為一列;同一段的列互相認得。每一欄是解讀完的值:動作詞展開上位詞、子區域算在上位區域內、推得的值分得出來、物件換成候選卡(小心同一物件在不同線上位置條件不同)。
- 新的比對只讀列,不讀卡片結構。
- 這張票要比得出的現有查詢欄:動作詞、從、到、指定卡、給條件、取對象(含「受方是被取對象的物件的段也算」)、段類別、區塊種類、條件段開關、推得終點開關、極性、只查泛用、被改的屬性。回傳的命中段與特定、泛用、全部三組照舊。
- 未解析組、經引用、代替留給票 04。
- `run_query` 的呼叫方式與回傳形狀不變;這張票做完時舊路徑仍是預設,新路徑可以指定。
- 附一支全庫新舊比對的工具:給一批查詢,兩條路徑各跑一次,列出每個查詢、每一組的差異。
- 候選卡要先算好還是用到才算,由實作者定;在全庫上呼叫查詢不能因為攤平而慢到不能用。

- 規格:需要你決定的「Q0」「Q9」;實作決策「動作索引」(列的單位、欄位表、完整的列另有哪些欄)、「查詢判斷」。
- 欄位表來自原型(分支 `prototype/action-player-ui`),只當參考;原型的攤平是粗略版。

**Blocked by:** 02

**Status:** ready-for-agent

- [x] 解讀卡片結構的程式集中在攤平;新的比對不碰卡片結構
- [x] 現有查詢測試改走新路徑時,只涉及直接命中的全部通過;還沒過的逐條列在 Comments 並註明屬於未解析組、經引用或代替
- [x] 全庫新舊比對:一批涵蓋上面每個查詢欄的查詢,特定與泛用兩組逐張相同;查詢清單與結果記在 Comments
- [x] 舊路徑仍是預設,既有測試不改、全綠
- [x] 回報全庫攤平一次、查詢一次各花多久,記在 Comments

## Comments

### 實作(2026-11-23)

- 新模組兩個,票 04 接著往裡加:
  - `script/action_structure/action_rows.py`(攤平):`flatten(structures, cards)` → `ActionIndex`。每條對象線一列,沒有線的段以段為一列;同一段的列共用段序號 `seq`。列的欄:卡、段 id、段序號、頂層區塊 id 與區塊種類、段類別、極性、是不是做代替的段、動作詞(上位詞已展開)、被改的屬性;線的欄:做動作的一方(`_is_doer`)、取對象(含「受方是被取對象的物件」)、從、到(區域含全部上位區域、方、推得值另標)、物件(是不是泛用物件、候選卡)。未結構化的段不出列;解析不出的段、引用節點、代替的連結留給票 04。
  - `script/action_structure/row_match.py`(比對):`match_rows(index, query)`,只讀列;回傳與 `run_query` 同形。未解析組、經引用先回空的,命中的被代替段還沒有 `replaced_by`。
- 候選卡:**用到才算**。每條線的候選卡在第一次被「指定卡」「給條件」問到時呼叫 `CandidateCards.of_line` 算,存成卡片總表位置的位元集(Python int),同一份攤平裡算過的不再算,內容相同的共用一份。指定卡 = 那張卡(別號照總表對到主卡)的位置在不在位元集裡;給條件 = 滿足查詢條件的卡(位元集)與候選卡有交集。代入用的卡(`CardView`)由攤平帶著,給條件時對它求查詢條件。
- `run_query(structures, cards, query, path="structure")`:預設仍是舊的讀法;`path="rows"`(`action_query.PATH_ROWS`)改走攤平 + 比對,其他值拋 ValueError。舊的讀法沒有改(`action_query.py` 只加了 `path` 參數與兩個常數)。
- 新測試 `test_action_rows.py`(10 個,走 `run_query(..., path="rows")`):泛用組、只查泛用、命中段、條件段開關與段類別、從(子區域、方)、推得終點開關、指定卡對線的候選卡、給條件、做動作的線不比、認不得的路徑。
- 兩支工具(README 有寫):
  - `run_tests_on_rows.py`:現有測試檔不改,把 `run_query` 的預設路徑換成 rows 再跑全部測試;`--parity` 則每次查詢兩條路徑都跑,直接命中(特定、泛用組與每張卡的命中段)不同就失敗。
  - `compare_query_paths.py`:全庫新舊比對(下面)。

### 現有查詢測試改走新路徑

- `run_tests_on_rows.py --parity`:954 個全過,也就是現有測試的**每一次查詢**,直接命中(特定、泛用組與命中段)新舊都相同。
- `run_tests_on_rows.py`(結果整個換成新路徑):954 個裡 38 個測試方法沒過(含 subTest 共 59 failures、10 errors),全部屬於還沒搬的三種。分類的做法:新路徑的結果補上舊路徑的某一部分(未解析組/經引用組/`replaced_by`)後再跑,補哪一部分就過的歸哪一類;38 個都只要補一部分就過。
  - 代替(4):`test_detach.LightDragonTest.test_replacement_detach_hits_with_replacement`、`test_golden.MagistusFlameTest.test_replaced_destruction_is_reachable_from_the_replacing_segment`、`test_leave_field.ChainDogTest.test_leaving_points_at_the_banish`、`test_leave_field.JetWarriorTest.test_leaving_hits_with_the_replacement_switch_and_points_at_the_banish`
  - 經引用(5):`test_effect_reference` 的 `BlackPantherTest.test_switch_on_destroy_hits_via_generic_reference`、`FreshiaTest.test_destroy_puts_freshia_in_via_group_not_hit_groups`、`FreshiaTest.test_via_lists_trap_cards_with_their_hit_segments`、`HoshiaiTest.test_ritual_summon_hits_via_ritual_spell`、`PartNotFoundTest.test_whole_card_is_looked_at`
  - 未解析組(29):
    - `test_action_query.UnparsedGroupTest`:`test_card_without_official_text_is_in_unparsed_group_with_reason`、`test_object_unparsed_blocks_hit_and_goes_to_unparsed_group`、`test_segment_with_action_literal_but_unparsed_goes_to_unparsed_group`
    - `test_anaphora_this_card.ChaosSorcererTest.test_a_reference_with_nothing_to_point_at_is_listed_as_unparsed`
    - `test_clause_fronts_m3b.OwnEffectCauseTest.test_own_effect_without_matching_source_is_unparsed`
    - `test_continuative_split.ShapeSplitTest.test_subjectless_right_half_after_unparsed_left_without_topic_is_unparsed`
    - `test_damage_recover.CauseWrittenTwiceTest.test_unparsed_reason_says_written_twice`
    - `test_detach.MaterialAttachedIsOutOfScopeTest.test_attached_segment_stays_unparsed`
    - `test_effect_reference.ShasmatisTest.test_unparsed_reference_sentence_follows_unparsed_group_rule`
    - `test_end_phase_timing_ritual.TurnPhaseFormsTest.test_forms_outside_this_rule_stay_unparsed`(2 個 subTest)
    - `test_equip_to_this_card.EquipToThisCardTest.test_equip_with_a_normal_monster_misses_millennium_eyes`
    - `test_flip.FlipIsNotFlipSummonOrFlipMonsterTest.test_flip_monster_literal_is_not_the_flip_action`
    - `test_leave_field.ElidedSubjectTest.test_without_a_topic_this_card_is_not_assumed`
    - `test_move_then_summon`:`ReleasedMonsterIsNotSummonedTest.test_release_hits_with_the_released_monster`、`SummonHalfOfASpellTest.test_no_earlier_summon_leaves_the_summon_half_unparsed`
    - `test_names_archetypes.ArchetypeConditionTest.test_unknown_quoted_name_goes_to_unparsed_group_and_coverage`
    - `test_resistance_restriction.LockTest.test_mukouka_is_negate`
    - `test_small_fixes`:`CannotRemoveTest.test_cannot_remove_condition_is_unparsed`、`SingleSameDifferentTest` 的 `test_mask_change_single_same_attribute_is_undecidable`、`test_revive_single_same_name_target_is_undecidable`、`test_sanctuary_single_same_name_material_is_undecidable`
    - `test_small_forms`:`LifePointPaymentTest.test_formula_amount_stays_unparsed`、`PlaceAndRemoveStemTest.test_unparsed_place_and_remove_forms_are_listed`
    - `test_summon_words`:`SummonPerformedLiteralTest.test_each_kind_of_summon_performed_goes_to_its_own_action`(31 個 subTest)、`SummonPerformedLiteralTest.test_ritual_summon_performed_is_not_listed_under_summon`、`UnparsedGroupLiteralTest.test_other_summons_and_summon_condition_are_not_the_bare_summon`、`UnparsedGroupLiteralTest.test_unparsed_bare_summon_is_not_silently_dropped`
    - `test_xyz_material`:`AttachAsXyzMaterialTest.test_unresolved_object_lists_the_attach_segment_as_unparsed`、`StackUnderTheRestatedXyzMonsterTest.test_owner_reference_that_only_finds_the_stacked_card_is_unresolved`
- 預設路徑(舊):`python -X utf8 -m unittest discover -s script/action_structure` 954 個全綠(既有 944 個未改,加新的 10 個)。

### 全庫新舊比對

- `python -X utf8 script/action_structure/compare_query_paths.py`:同一份 `data/action_structure.json` 與 `data/cards.json`,全庫攤平一次、候選卡全部先算好,45 個查詢兩條路徑各跑一次,逐張比特定、泛用、全部三組,另比每張卡的命中段。
- 結果:**45 個查詢全部相同**(三組逐張相同,命中段也相同),結束碼 0。
- 查詢清單與各組張數(張數是舊路徑的;秒數是這台機器上單次查詢,新路徑不含攤平與候選卡):

| 名稱 | 查詢 | 張數(舊) | 新舊 | 舊(秒) | 新(秒) |
|---|---|---|---|---|---|
| 空查詢 | `{}` | 特定 10587 泛用 1273 全部 11860 | 相同 | 0.35 | 0.12 |
| 動作詞 破壞 | `{"actions": ["破壞"]}` | 特定 914 泛用 1269 全部 2183 | 相同 | 0.63 | 0.11 |
| 動作詞 特殊召喚(含下位詞) | `{"actions": ["特殊召喚"]}` | 特定 4659 泛用 100 全部 4759 | 相同 | 0.70 | 0.11 |
| 多個動作詞同一段 | `{"actions": ["無效", "破壞"]}` | 特定 28 泛用 136 全部 164 | 相同 | 0.79 | 0.04 |
| 多個動作詞(無同段) | `{"actions": ["破壞", "特殊召喚"]}` | 特定 0 泛用 0 全部 0 | 相同 | 1.00 | 0.05 |
| 從 牌組 | `{"actions": ["特殊召喚"], "from_zones": ["牌組"]}` | 特定 938 泛用 7 全部 945 | 相同 | 0.74 | 0.05 |
| 從 對手的墓地 | `{"actions": ["特殊召喚"], "from_zones": [{"zone": "墓地", "side": "對手"}]}` | 特定 8 泛用 21 全部 29 | 相同 | 0.77 | 0.08 |
| 從 場上(含子區域) | `{"actions": ["破壞"], "from_zones": ["場上"]}` | 特定 364 泛用 1128 全部 1492 | 相同 | 0.40 | 0.04 |
| 從 牌組頂 | `{"actions": ["送墓"], "from_zones": ["牌組頂"]}` | 特定 6 泛用 103 全部 109 | 相同 | 0.55 | 0.04 |
| 到 牌組 | `{"actions": ["返回"], "to_zones": ["牌組"]}` | 特定 411 泛用 187 全部 598 | 相同 | 0.50 | 0.03 |
| 到 我方的場上 | `{"actions": ["特殊召喚"], "to_zones": [{"zone": "場上", "side": "我方"}]}` | 特定 103 泛用 42 全部 145 | 相同 | 0.61 | 0.04 |
| 到 墓地(推得終點關) | `{"actions": ["解放"], "to_zones": ["墓地"]}` | 特定 0 泛用 0 全部 0 | 相同 | 0.56 | 0.03 |
| 到 墓地(推得終點開) | `{"actions": ["解放"], "to_zones": ["墓地"], "include_inferred": true}` | 特定 772 泛用 135 全部 907 | 相同 | 0.32 | 0.04 |
| 從+到 推得終點開 | `{"actions": ["送墓"], "from_zones": ["手牌"], "to_zones": ["墓地"], "include_inferred": true}` | 特定 305 泛用 158 全部 463 | 相同 | 0.57 | 0.04 |
| 指定卡 ブラック・マジシャン | `{"actions": ["特殊召喚"], "card": 46986414}` | 特定 98 泛用 192 全部 290 | 相同 | 2.88 | 0.05 |
| 指定卡 異圖密碼 | `{"actions": ["特殊召喚"], "card": 46986415}` | 特定 98 泛用 192 全部 290 | 相同 | 2.29 | 0.05 |
| 指定卡 青眼の白龍 破壞 | `{"actions": ["破壞"], "card": 89631139}` | 特定 165 泛用 1061 全部 1226 | 相同 | 2.03 | 0.04 |
| 指定卡 灰流うらら 從手牌捨棄 | `{"actions": ["捨棄"], "card": 14558127, "from_zones": ["手牌"]}` | 特定 14 泛用 441 全部 455 | 相同 | 0.70 | 0.04 |
| 指定卡 無動作詞 | `{"card": 46986414}` | 特定 985 泛用 4013 全部 4998 | 相同 | 4.11 | 0.07 |
| 給條件 卡名包含 | `{"actions": ["特殊召喚"], "condition": {"op": "卡名包含", "text": "ブラック・マジシャン"}}` | 特定 210 泛用 169 全部 379 | 相同 | 2.96 | 0.06 |
| 給條件 字段 | `{"actions": ["加入手牌"], "condition": {"op": "字段", "setcodes": [4258]}}` | 特定 67 泛用 27 全部 94 | 相同 | 1.75 | 0.05 |
| 給條件 怪獸且等級≤4 從手牌 | `{"actions": ["特殊召喚"], "from_zones": ["手牌"], "condition": {"op": "且", "args": [{"op": "大類", "value": "怪獸"}, {"op": "屬性比較", "attr": "等級", "cmp": "≤", "value": 4}]}}` | 特定 1275 泛用 67 全部 1342 | 相同 | 6.55 | 0.06 |
| 給條件 種族 屬性 | `{"actions": ["除外"], "condition": {"op": "且", "args": [{"op": "屬性比較", "attr": "種族", "cmp": "=", "value": "ドラゴン族"}, {"op": "屬性比較", "attr": "屬性", "cmp": "=", "value": "光"}]}}` | 特定 144 泛用 411 全部 555 | 相同 | 1.30 | 0.06 |
| 給條件 魔法 破壞 | `{"actions": ["破壞"], "condition": {"op": "大類", "value": "魔法"}}` | 特定 134 泛用 914 全部 1048 | 相同 | 3.86 | 0.04 |
| 取對象 破壞 | `{"actions": ["破壞"], "targeting": true}` | 特定 173 泛用 643 全部 816 | 相同 | 0.51 | 0.03 |
| 取對象 裝備(受方是被取對象的物件) | `{"actions": ["裝備"], "targeting": true}` | 特定 121 泛用 4 全部 125 | 相同 | 0.50 | 0.03 |
| 取對象 性質變更 | `{"actions": ["性質變更"], "targeting": true}` | 特定 100 泛用 101 全部 201 | 相同 | 0.52 | 0.03 |
| 取對象+從 墓地 | `{"actions": ["特殊召喚"], "targeting": true, "from_zones": ["墓地"]}` | 特定 619 泛用 50 全部 669 | 相同 | 0.57 | 0.04 |
| 段類別 代價 | `{"actions": ["捨棄"], "kinds": ["代價"]}` | 特定 315 泛用 268 全部 583 | 相同 | 0.49 | 0.03 |
| 段類別 召喚手續 | `{"actions": ["解放"], "kinds": ["召喚手續"]}` | 特定 80 泛用 13 全部 93 | 相同 | 0.28 | 0.02 |
| 段類別 限制+極性 不能 | `{"actions": ["特殊召喚"], "kinds": ["限制"], "polarities": ["不能"]}` | 特定 107 泛用 0 全部 107 | 相同 | 0.48 | 0.02 |
| 區塊種類 召喚條件 | `{"actions": ["特殊召喚"], "block_kinds": ["召喚條件"]}` | 特定 249 泛用 1 全部 250 | 相同 | 0.14 | 0.02 |
| 區塊種類 靈擺效果 | `{"actions": ["破壞"], "block_kinds": ["靈擺效果"]}` | 特定 74 泛用 23 全部 97 | 相同 | 0.13 | 0.02 |
| 條件段開關 | `{"actions": ["特殊召喚"], "include_condition": true}` | 特定 5593 泛用 192 全部 5785 | 相同 | 0.38 | 0.06 |
| 條件段開關+段類別 條件 | `{"actions": ["破壞"], "include_condition": true, "kinds": ["條件"]}` | 特定 1276 泛用 100 全部 1376 | 相同 | 0.41 | 0.03 |
| 條件段開關 關+段類別 條件 | `{"actions": ["破壞"], "kinds": ["條件"]}` | 特定 0 泛用 0 全部 0 | 相同 | 0.46 | 0.02 |
| 極性 不會 | `{"actions": ["破壞"], "kinds": ["效果", "限制", "修飾"], "polarities": ["不會"]}` | 特定 561 泛用 50 全部 611 | 相同 | 0.42 | 0.02 |
| 極性 不能、只能 | `{"actions": ["發動"], "kinds": ["限制", "效果"], "polarities": ["不能", "只能"]}` | 特定 113 泛用 124 全部 237 | 相同 | 0.44 | 0.02 |
| 只查泛用 破壞 | `{"actions": ["破壞"], "generic_only": true}` | 特定 0 泛用 1269 全部 1269 | 相同 | 0.32 | 0.04 |
| 只查泛用 從墓地除外 | `{"actions": ["除外"], "from_zones": ["墓地"], "generic_only": true}` | 特定 0 泛用 170 全部 170 | 相同 | 0.43 | 0.04 |
| 被改的屬性 攻擊力 增 | `{"actions": ["性質變更"], "modified": {"attr": "攻擊力", "form": "增"}}` | 特定 1226 泛用 89 全部 1315 | 相同 | 0.51 | 0.05 |
| 被改的屬性 傷害 數值 0 | `{"modified": {"attr": "傷害", "form": "數值", "value": 0}, "kinds": ["效果", "修飾"]}` | 特定 115 泛用 0 全部 115 | 相同 | 0.61 | 0.04 |
| 被改的屬性 卡名 | `{"modified": {"attr": "卡名"}, "kinds": ["效果", "修飾"]}` | 特定 105 泛用 0 全部 105 | 相同 | 0.94 | 0.07 |
| 合併:從墓地+給條件+取對象 | `{"actions": ["特殊召喚"], "from_zones": ["墓地"], "condition": {"op": "大類", "value": "怪獸"}, "targeting": true}` | 特定 600 泛用 50 全部 650 | 相同 | 3.21 | 0.08 |
| 合併:指定卡+到+推得 | `{"actions": ["送墓"], "card": 89631139, "to_zones": ["墓地"], "include_inferred": true}` | 特定 84 泛用 373 全部 457 | 相同 | 1.61 | 0.07 |

- 「到 墓地(推得終點關)」「多個動作詞(無同段)」「條件段開關 關+段類別 條件」三個是 0 張的對照組(推得值、同段、條件段閘門不放行)。
- 代替(`replacement`)、泛用引用開關(`generic_reference`)不在這張票的查詢欄裡,沒列;未解析組、經引用組新路徑還是空的,不比。

### 時間(站主這台機器,`compare_query_paths.py` 第二次跑,沒有其他程序同時跑)

| | 秒 |
|---|---|
| 讀卡片結構與卡片總表 | 約 4 |
| 全庫攤平一次(45,302 列,不含候選卡) | 0.8 |
| 候選卡全部算好(全部對象線) | 27.3 |
| 45 個查詢合計:舊路徑 | 50.3 |
| 45 個查詢合計:新路徑(候選卡已算好) | 2.1 |

- 單次查詢:舊路徑 0.3 到 8 秒(指定卡、給條件最慢);新路徑攤平好之後每個查詢 0.04 到 0.25 秒。
- `run_query(..., path="rows")` 每次呼叫都重新攤平(不跨呼叫快取),候選卡只算查詢用得到的線:全庫冷呼叫一次,「破壞」1.0 秒(舊 0.3 秒),「特殊召喚 + 指定ブラック・マジシャン」10.9 秒(舊 1.9 秒),「特殊召喚 + 給條件 卡名包含」11.5 秒(舊 2.3 秒)。多個查詢共用一次攤平(`flatten` 一次、`match_rows` 多次)時,候選卡全庫只算一次。
- 第一次跑(與測試同時跑)攤平 2.0 秒、候選卡 52.2 秒、45 個查詢舊 91.6 秒 新 4.2 秒,結果同樣 0 差異。

### 留給站主 / 後續

- 冷呼叫 `run_query(path="rows")` 帶指定卡或給條件時約 11 秒,比舊路徑慢(舊的只對那一張卡判)。票 06 建置索引時候選卡全部預先算(約 27 秒),網站不受影響;Python 這邊在票 04 刪舊路徑前若要更快,可以讓 `run_query` 快取攤平結果,或比對時只對要問的那張卡判。
