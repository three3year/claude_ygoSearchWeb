# 03: 召喚手續框的施事者與動作對象

**What to build:** 召喚手續框的兩條專門規則,讓「施事者=自分」與動作對象「此卡/非此卡」的查詢對召喚手續判得對。施事者一律 自分(來源 預設、標推得,不看主題與主語;封閉表不加新值)。動作對象的發動位置是所屬召喚條件的召喚來源:寫了照寫的區域,沒寫時主牌組怪獸算手牌、額外牌組怪獸(融合、S、X、連結)算額外牌組,發動位置來源另記一個值(寫明的召喚來源/推得的召喚來源)、建置報告分項列;召喚手續框不算此卡自己移動。召喚手續的 重ねる 一律此卡,理由另記一個值。同一句其他框架的判定不變。見規格「兩條專門規則」與召喚來源、重ねる 的決定。

**Blocked by:** 02

**Status:** resolved

- [x] 分詞鏈接縫單元例子:「このカードは…をリリースして」施事者 自分(來源 預設、推得);召喚來源沒寫的主牌組怪獸「自分フィールドのモンスターを全てリリースした場合」動作對象 非此卡;額外牌組怪獸同句也是 非此卡;寫了來源的照寫;沒寫主題的 重ねる 是 此卡
- [x] 全語料召喚手續框:施事者全是 自分;動作對象 非此卡 208、此卡 68、皆非 7(與規格 Further Notes 相同;不同時逐框記進 Comments 再交)
- [x] 下游基準剝框重編後:既有框架的動作對象與回指逐框差異 0;剝鍵 digest ok
- [x] 匯出檔與目錄:三個位置的張數與雜湊 0 差異;召喚手續格隨動作對象變的只有帶動作對象欄的具名查詢(列出變動列記進 Comments)
- [x] 參考評估器與 JS 評估器全語料對拍 0 不符;重跑全鏈與網站建置 exit 0;各全套通過

## Comments

- 2026-11-03 實作(分支 wt/03-agent-patient):
  - **施事者**(`agent.mark`):位置是 `constraints.POS_PROCEDURE` 的框架開頭直接給 自分、來源 預設、`agent_inferred`,不走 (1)〜(4)——不看主題與主語、不要求帶對象(重ねる 沒有對象)。施事者封閉表沒加值。
  - **動作對象**(`patient.judge_sentence`):照現行算完整句的發動位置後,只把召喚手續框的那一格換成 `patient._summon_source_launch(frames_, frame, face)`——所屬召喚條件 = 同句(`sentence`)、`span` 包住本框的 限制·召喚條件 約束框架;它的 `source` 經 `regions.zones_of` 得區域(寫明的召喚來源);沒寫(或 `zones_of` 解不出)時依卡面 `type` 位元:融合|S|X|L(讀 `_MONSTER_TYPE_BITS`,ADR-0008)→ 額外牌組,其餘 → 手牌(推得的召喚來源);區域值取 `places.ZONE_TERMS`。同句其他框架的發動位置不動;召喚手續框不在 `_self_move_zones` 的位置內,天生不算此卡自己移動。
  - **沒寫來源又沒有卡面**(主會話定):發動位置區域不明——`Launch(zones=None, 推得的召喚來源)`,`_all_class` 對 None 讓每個區域都搆得到、其餘條件都對得上時停在 皆非(理由 全部類區域不明)。全語料召喚手續框的卡都有卡面(0 框走到這條),只在沒給卡面的呼叫(測試、`judge_sentence` 預設)用到。
  - **重ねる**(`patient.judge` 開頭):位置 召喚手續、動作 重ねる → 此卡,理由 `WHY_PROCEDURE_OVERLAY` = 召喚手續的疊放,不走受事者判定。效果位的 重ねる 照現行(反例測試)。
  - **封閉表**:發動位置來源收成模組頂 `patient.LAUNCH_SOURCES`(既有五種 + 寫明的召喚來源、推得的召喚來源);理由沒有集中封閉表(既有就是 `WHY_*` 模組頂常數),新理由放在同一塊。兩者經 `Verdict` → `export_common.Stats` 自動進匯出 `統計.理由`、`統計.發動位置` 與建置報告 `print_stats` 分項列(run_chain 輸出:發動位置 寫明的召喚來源 28、推得的召喚來源 35;其中皆非 各 3)。
  - **全語料召喚手續框 283 框**:施事者 **自分 283**(預設、推得;票 02 現行口徑 空 244、此卡 39)。動作對象 **非此卡 208、此卡 68、皆非 7**(與規格 Further Notes 相同;票 02 現行口徑 非此卡 160、皆非 90、此卡 33)。理由:非此卡 選擇類 145、全部類區域對不上 57、此卡以外 5、回指選擇類 1;此卡 召喚手續的疊放 68;皆非 全部類含此卡 5、全部類區域不明 1、不是卡 1。沒有卡面的框 0。
  - **守門**(剝框重編):剝鍵 digest ok(e43cc838…)、patient ok(225c4c7a…)、anaphora ok(dc03f6b9…),都沒重凍——同句既有框架的動作對象與回指逐框 0 差異。匯出檔 `export_diff.py` digest ok(剝完 97f37d0e… 不變)。
  - **匯出與目錄**:對 HEAD(48d4ad8)的 `data/action_frames.json`:目錄 261 列逐列 0 差異(三個位置與召喚手續格的張數、雜湊都沒變);句列只變 271 句(含召喚手續框的句,框列的 agent 與 patient_mode)。召喚手續格隨動作對象變的列 **0 列**:目錄沒有任何具名查詢用 動作對象 或 施事者 欄,所以本票的改動碰不到目錄的張數。
  - **建置**:`run_chain.py` exit 0、`build_index.py` exit 0(全部檢查通過);`encode_fixture.py` 重跑編碼夾具不變。重生 `data/action_frames.json`、`web/data.js`、`report.md`(施事者小節說明字串改)。
  - **文字**:`agent.py` 檔頭與報告小節說明、`viewer.html` 施事者推得的 title 與註解(票 04 交代)加「召喚手續位一律 自分」;GLOSSARY 發動位置條、論元條施事者 (4) 加召喚手續的兩條規則(2026-11-03)。
  - **測試**:新檔 `test_procedure_rules.py` 10 例——施事者 2 例(このカードは…をリリースして アドバンス召喚、沒對象的 重ねる 都是 自分/預設/推得);發動位置 5 例(主牌組/額外牌組沒寫來源「自分フィールドのモンスターを全てリリース」非此卡、額外牌組寫「墓地から」時墓地全部 皆非、對照沒寫時 非此卡、沒卡面 皆非、統計分項寫明/推得各 1);重ねる 2 例(沒主題的 重ねる 此卡、效果位 重ねる 反例照受事者規則)。其中 5 例對改前的 patient.py 會失敗(已實跑確認)。
  - **數字**:effect-tokenize 928 OK(skipped 3);script card_list 66、faq_info 43、tag_card 469、text_format 55、web 169 全 OK;node `script/web/*.test.js` 411 pass / 0 fail(含參考評估器與 JS 評估器全語料對拍)。
  - **給票 05 抽驗**:框列鍵 `agent`/`agent_source`/`agent_inferred`、`patient_mode`;判定理由與發動位置來源從 `patient.judge_sentence(frames, face, section)` 回的 `Verdict.why` / `Verdict.launch`(只在全部類理由時有值)取;所屬召喚條件與發動位置是 `patient._summon_source_launch`;常數 `patient.WHY_PROCEDURE_OVERLAY`、`patient.LAUNCH_SUMMON_WRITTEN`、`patient.LAUNCH_SUMMON_INFERRED`。
- 2026-11-03 合入 summon-procedure(含票 04 a897ffc)後:無衝突;report.md 重生(merge=ours 取本分支版後重跑),全鏈 exit 0、網站建置「內容沒變,不動」、編碼夾具不變。effect-tokenize 936 OK(skipped 3)、script 五套全 OK、node 411 pass / 0 fail。
