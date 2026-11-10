# 01: 零行為改變的重整

**What to build:** 里程碑二 code review 留下的結構性重整,一次做完,讓後面各張規則票不再擠在同兩個大模組裡改:各動作的填格函式搬進各自模組;反向檢查的段模板分流改成表;填格函式共用的參數包成子句 context;以及隱性契約改成明寫的結構——狀態原子代入規則、區塊狀態的主題三態、原述語字面串接後再拆、段模板的期間分流、傷害字幹黏著「を」。產物逐位元組不變。

- 規格:實作決策「重整票」;需要你決定的「重整票裡「置く/取り除く 改成字幹假朋友表」這一項怎麼辦?」(那一項不在本票,在票 02)。
- 背景:里程碑二摘要「code review 沒修的結構性重整什麼時候做?」與「code review」一節。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [x] 重建後 `data/action_structure.json` 與改前逐位元組相同;兩次建置逐位元組相同
- [x] 覆蓋報告與反向檢查報告的數字與改前相同
- [x] 既有各組測試全綠,不新增行為測試
- [x] 上列五項隱性契約各自在 Comments 記「改前靠什麼成立、改後寫在哪」
- [x] 「置く/取り除く 改成字幹假朋友表」沒有做進本票

## Comments

### 實作紀錄(2026-11-10,分支 as/01)

守門(每搬一步各跑一次,最後再跑一次):

- 測試:`python -X utf8 -m unittest discover -s script/action_structure` 495 個全綠;沒有新增或修改任何測試檔。
- 產物:`build_structure.py -o <暫存檔>` 重建後與 `data/action_structure.json` `cmp` 相同(md5 1ee4dd010327a41c1d78746aac5838c5),前後建了多次都相同。
- 報告:`build_report.py`、`build_reverse_check.py` 重跑後 `coverage.md`、`reverse_check.md` 的 git blob 與整合分支相同(工作樹只有換行差異,已還原)。
- 回歸工具:`passdump.py` 用整合分支的程式與本分支的程式各跑一次(同一份產物),兩份輸出逐位元組相同;`regress.py` 報「改前通過、改後不通過」0 張、「改前不通過、改後通過」0 張。
- 另外對照了查詢:`m2_compare.py` 的輸出與改前的程式逐位元組相同;指定卡與只給條件的代入查詢(8 個動作詞 × 指定卡、屬性/種族/大類條件、泛用組、取對象加全部極性)改前改後的結果見本節末「查詢對照」。

模組怎麼拆(原 `segment_extract.py` 1,807 行、`reverse_check.py` 1,265 行;拆完各 359、448 行;拆出的模組最大的是 `simple_clause.py` 568 行):

- 各句型一個模組,填格 `fill_clause` 與句型模板 `render_clause` 成對:`simple_clause`(簡單子句)、`existence_clause`(存在前提)、`battle_clause`(戰鬥)、`stat_modify`(性質變更)、`damage`、`draw`;素材行 `material_line`、「〜として扱う」`treat_as`。
- 子句各格的字面,抽取與模板成對:`noun_phrase`(修飾語、頭名詞 ↔ 條件式)、`zone_phrase`(區域)、`quantity`(數量)、`agent_phrase`(誰)、`cause_phrase`(原因)、`predicate_literal`(原述語字面)。
- `block_state`:`BlockState`(物件短語 → 物件、目前位置、主語)、推得表、位置自動規則、`ClauseContext`。
- `object_render`、`segment_history`:反向檢查的物件模板與「這一段之前的段」。
- `segment_extract` 只留句子層級的規則與句型分派表 `CLAUSE_FORMS`;`reverse_check` 只留段模板的分流表、整段的框架、段外殘留與報告。
- 填格函式共用的參數(段、區塊狀態、句子起點、承襲的時機)包成 `block_state.ClauseContext`;原本另外傳的段類別 `kind` 改成由段讀(填格當下兩者一定相同)。
- 反向檢查的段模板分流:`render_segment` 的 if 鏈改成 `WHOLE_TEMPLATES`(整段模板 3 列)與 `CLAUSE_TEMPLATES`(子句模板 7 列)兩張表。

順手做的(都不改行為):`reverse_check` 自己重複的一份 `_iter_nodes` 改用 `structure_shape.iter_nodes`;`segment_extract` 一個沒用到的 import 拿掉;各模組 docstring 與 GLOSSARY、README 指到的程式位置跟著改;`segment_extract` 的總說明分到各模組的 docstring。

### 五項隱性契約

1. **狀態原子代入規則**
   - 改前:`action_query.eval_condition` 的 if 鏈照原子名各自回 True/False(位置、控制方、表示形式、被裝備者、以此卡為對象 → True;同一張 → False;曾被特殊召喚看出發地),哪些算泛用原子另列一個常數 `GENERIC_ATOMS`;原子定義在 `condition_atoms`,「代入時任何卡都算、但不是泛用原子」只寫在各原子的說明文字裡。加一個狀態原子要記得改這三處。
   - 改後:`action_query.STATE_ATOMS` 一張表,一列一個原子:代入判法 `fits` 與是否泛用 `generic`。`eval_condition` 查表,`GENERIC_ATOMS` 由表推出。`condition_atoms` 的 docstring 與 GLOSSARY「條件式」指到這張表。
2. **區塊狀態的主題三態**
   - 改前:`BlockState.topic` 用三種型別表達三態——`None`(沒有)、哨兵物件 `TOPIC_UNKNOWN`(判不了)、`(短語, 句子起點)` 元組(待建);`segment_extract._hold_topic` 與 `parse_sentence` 直接寫屬性,`elided_subject` 用 `is None`、`is TOPIC_UNKNOWN` 判。
   - 改後:`block_state.Topic(state, phrase, sentence_start)`,狀態值 `TOPIC_NONE`、`TOPIC_PENDING`、`TOPIC_UNKNOWN`,三態各代表什麼寫在常數上方;只由 `BlockState.start_sentence`、`hold_topic`、`lose_topic` 寫,`elided_subject` 讀。
3. **原述語字面串接後再拆**
   - 改前:抽取端在 `_fill_clause` 裡就地寫 `(取對象字面) + (選んで) + 述語`;反向檢查端的 `_render_predicate`、`_targeted_earlier` 各自用 `synonyms.split_targeting`、`split_select` 照同一個順序拆。串的順序、拆的順序、「拆到取對象字面就不再拆 選んで」只靠兩邊各自寫對。
   - 改後:`predicate_literal.join_predicate_literal` 與 `split_predicate_literal` 成對放在一起(拆出來是 `PredicateLiteral` 三截),兩邊只走這一對。「取對象字面與 選んで 都寫的句子拆不回、所以沒有模板」這個既有行為寫在 `split_predicate_literal` 的 docstring。
4. **段模板的期間分流**
   - 改前:`render_segment` 裡散在四處的條件——動作詞不是性質變更才驗句中期間是不是述語前寫得出的字面;存在前提、傷害、帶施事線的段有句中期間就丟無模板;抽牌分支再丟一次;性質變更模板自己再呼叫一次 `split_duration`;傷害模板另吃一個參數。哪個模板收哪種期間要讀完整個函式才知道。
   - 改後:`reverse_check.CLAUSE_TEMPLATES` 每一列的 `inner_duration` 欄寫明句中期間的去向(`INNER_OWN` 模板自己寫、`INNER_BEFORE_PREDICATE` 述語前、`INNER_NONE` 不收),`render_segment` 照欄位分流;性質變更模板改由參數拿句中期間。
   - 一處細項字面會不同,只發生在抽取不會產生的結構:同時帶票 10 的存在前提與動作詞 性質變更 的段,改前報「前提無模板:存在」,改後若有句中期間會先報「期間無模板:句中」。兩者都是無模板;全庫報告無差異。
5. **傷害字幹黏著「を」**
   - 改前:同義表的傷害字幹連受詞寫成「ダメージを与え」「ダメージを受け」(查詢未解析組比字面時,單獨的「与え」「受け」會誤中),傷害句型卻把「ダメージを」切在述語外;`_fill_damage` 與 `_render_damage` 各自拿 `damage.DAMAGE_OBJECT` 接回去再查表(回復不接)。「ダメージを」在 `synonyms` 的字幹與 `damage` 的常數各寫一次。
   - 改後:`synonyms.DAMAGE_OBJECT` 一處定義,字幹由它拼;查表前接回去只走 `damage.parse_damage_predicates(pred, recover)`,抽取與模板共用。

### 沒改、照舊留著的事(給站主知道,不需要現在裁定)

- 存在前提與抽牌兩個模板不吃「このカード指誰」(`self_id`):內嵌效果的區塊裡,這兩種段的「このカード」一律照物件0 寫。改前就是這樣(函式呼叫時沒把 `self_id` 傳下去),這張票照原樣保留,在 `CLAUSE_TEMPLATES` 的註解寫明。全庫有沒有段因此不通過沒有量。
- `stat_modify` 的模板借用 `simple_clause.render_from`(對象線的「從」怎麼寫),是句型模組之間唯一的一條依賴。

### 查詢對照

產物逐位元組相同只守得到抽取;反向檢查報告守模板;查詢判斷(這張票動了 `eval_condition` 的狀態原子)另外對照:

- 做法:同一份 `data/action_structure.json` 與 `data/cards.json`,分別用整合分支的程式(`git archive action-structure-m3 script/action_structure` 解到 repo 外)與本分支的程式跑同一批查詢,比 `run_query` 結果的 JSON。對照腳本沒有進版控。
- 查詢 232 個:8 個動作詞(破壞、特殊召喚、除外、加入手牌、送墓、裝備、返回、性質變更)各配 29 個——指定卡 24 張(卡片總表依卡號每 700 張取一張 21 張,加 3 張額外牌組怪獸;開條件段與推得)、只給條件 3 種(屬性 闇、種族 ドラゴン、大類 魔法)、只查泛用組、只看取對象加代替加全部極性。
- 結果:232 個查詢的結果全部逐位元組相同。`m2_compare.py`(只給動作詞的 22 個查詢與段、反向檢查的總數字)的輸出也相同。
