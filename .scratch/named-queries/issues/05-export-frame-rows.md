# 05: 匯出新檔的框列

**What to build:** 分詞鏈多寫一份 `data/action_frames.json`(入版控、一句一行、決定性):頂層 說明、版本(整數)、目錄(本票先空清單)、卡面(同現行雜湊)、句——每句標記句一列(卡片密碼、段落、index、原文雜湊)加框列清單,框架對標記句的規則同現行、對不到即匯出失敗。框列的欄:詞元、位置、極性、態、否定形、來源/目的/所在的結構化值((玩家, 區域) 清單,含轉欄與回指回填寫進的、記號不匯)、施事者、方式類、表示形式值、受事者片語(對象→主語→主題第一個有值的欄)與目的片語各一個段清單(每段:中心詞、中心詞類、數量類、修飾語類集合)、動作對象(此卡/非此卡,皆非不帶);三個位置都匯;全部可選鍵、只在有值時帶;字面不匯。統計(動作對象框數與理由)照帶。舊匯出照常產、逐位元組不變;索引建置不動。

**Blocked by:** 04

**Status:** resolved

- [x] 匯出接縫測試:合成卡經真的組裝、框架抽取進匯出,斷言框列每個欄(含動作對象)、原文/卡面雜湊、對不到標記句的問題清單
- [x] 同輸入兩次逐位元組相同;鍵名沿用 frames.json 與封閉表模組的拼法;玩家拼法 自分/相手/お互い/相對/無
- [x] 重跑鏈加這一步;建置產物文件加一列與重生指令;舊匯出檔不變
- [x] 全語料數字寫進 Comments:句數、框數分位置、各欄有值的框數

## Comments

- 2026-11-01 實作(分支 wt/05-export,基於 f18bca5=票 01/02/04 交件)。全部在 `.scratch/effect-tokenize/`。**新模組 `export_frames.py`**(不 import categories/export_categories):`export(sentences, faces=None)` → (文件, 問題清單)、`serialize(doc)` 一句一行、`main()` 寫 `data/action_frames.json`(入版控,LF;`.gitattributes` 的 `*.json text eol=lf` 已涵蓋)。**共用部分抽成 `export_common.py`**:`text_hash`、`FACE_FIELDS`/`card_face`/`face_hash`、`owner`(框架對標記句)、`Stats`、`print_stats`、`load_sentences`/`load_faces`;`export_categories.py` 改 import 它們(名字仍在它的命名空間,`downstream_baseline`/`test_export`/`test_04_patient` 的 `export_categories.card_face` 照用),是純搬移——舊匯出檔 md5 aa682ce9b1741fcba654fa8c70245da7 與 export-digest 相同、全鏈後 `git diff data/action_categories.json` 空。
- **檔形狀**:頂層 `說明`、`版本`(整數,`VERSION = 1`)、`目錄`(本票 `[]`)、`統計`(`Stats.doc()` 同舊檔,另加 `位置`:匯出框數分代價/效果/條件)、`卡面`(`[卡片密碼, 雜湊]` 一列一行,同算法)、`句`(一列一行:`card`、`section`、`index`、`hash`、`frames`)。**框列鍵(模組頂 `FRAME_KEYS`,匯出序)**:`action`、`position`、`polarity`、`voice`、`negation`、`regions`(`{source|goal|place: [[玩家, 區域]…]}`,frames.json 的結構化值照抄——含轉欄與回指回填寫進的,`transfer`/`region_backfill` 記號不匯;空欄不帶)、`agent`、`manner_kind`、`manner_value`、`phrases`(`{patient: [段…], goal: [段…]}`;`patient` 取 `PATIENT_SOURCES = (object, subject, topic)` 第一個有片語的欄,`goal` 取目的片語;段的鍵 `SEGMENT_KEYS`:`head`、`head_kind`、`quantity`=數量類字串、`modifiers`=修飾語類去重清單依 `closed_values.MODIFIER_KINDS` 表序)、`patient_mode`(此卡/非此卡;皆非不帶)。全部只在有值時帶,字面(子句、整段、修飾語字面、數量字面)不匯;玩家拼法即 closed_values 的 自分/相手/お互い/相對/無。三個位置都匯。對不到標記句 → 問題「框架對不到標記句(選項 n):(卡, 段落, 句序, 框序)」、不寫檔。
- **全語料數字**(frames.json md5 aca2f99db313617924c83d1e7eccce9b,與整合分支相同):標記句 24,599(卡 7,817 張);框列 46,732——代價 3,734、效果 26,687、條件 16,311。各欄有值的框數:action/position/polarity 46,732、voice 10,780、negation 3,088、regions 32,195、agent 25,145、manner_kind 3,807、manner_value 1,202、phrases 45,316、patient_mode 32,113(此卡 8,807、非此卡 23,306;皆非 14,619 不帶)。檔 13.8MB、32,426 行;`export_frames.py` 重跑兩次 md5 c1c93eeb7553f3df656829fcbcb2156d 相同,`run_chain.py` 全鏈(tokenize → frames → export_frames → categories → export_categories)重跑後仍是同一個 md5;匯出一步約 6 秒。
- **重跑鏈**:`run_chain.STEPS` 變成 分詞 → 框架 → **框列匯出** → 類別 → 類別匯出(規格總則是 框架 → 目錄 → 匯出;票 08 的目錄那一步插在 框架 與 框列匯出 之間,docstring 寫明);`test_run_chain` 兩條預期跟著改。`docs/agents/build-products.md` 表加 `data/action_frames.json` 一列(重生指令 run_chain.py 或 frames.py → export_frames.py)。`.scratch/effect-tokenize/.gitignore` 不用動(新檔在 data/ 且入版控)。
- **測試**:`test_05_export_frames.py` 14 條(接縫 `export_frames.export`/`serialize`,合成卡經 `tokenize.assemble` + `frames.extract`;每個欄各一條例子含動作對象讀卡面、拆開/沒拆的選項、對不到標記句的問題清單、效果外文本/只有約束的句框列空、頂層鍵與版本/空目錄/卡面雜湊/統計、序列化一句一行可 roundtrip、兩次逐位元組相同);第一條先紅(沒有模組)再綠。effect-tokenize 全套 938 條、node 172、script/* 五套 66/43/469/55/136 通過;`downstream_baseline.py` 三把尺 patient 差異 0(04aba2fc…)/anaphora 差異 0(6536cac4…)/export ok(aa682ce9…);`baseline_diff.py` 剝鍵差異 0、底線鍵 0、digest ok;frames.py/patient.py/anaphora.py 都沒動。
- **假設(規格沒寫死、照 (a) 與票面做;要改都是一行)**:(1)施事者只匯 `agent`,不匯 `agent_source`/`agent_inferred`——規格 2 匯出段的欄只列「施事者」(規格 1 handoff 的對照列了三個鍵,那是「有什麼可讀」);述詞要分「推得的施事者」時再加欄。(2)數量類空的段(引用量 …の数だけ)不帶 `quantity`——規格只說數量類;動作對象那一欄已把它算成選擇類,述詞不必自己看。(3)動作對象的鍵名 `patient_mode`(frames.json 沒有這個欄可沿用;取 GLOSSARY「動作對象 (Action Patient Mode)」與 `patient.Verdict.mode`),受事者片語的鍵名 `patient`。(4)`統計` 計全部匯出的動作框架(三個位置),口徑比舊匯出的「帶葉的效果位/代價位框架」寬,所以數字與舊檔不同(舊 此卡 8,806…是帶葉的子集);位置放在 `目錄` 之後、`卡面` 之前(同舊檔「統計在卡面前」的慣例)。(5)`modifiers` 是集合但 JSON 沒有集合,寫成封閉表序的清單。
- **給票 06/08 的接點**:述詞字彙模組接 `export_frames.FRAME_KEYS`/`PHRASE_KEYS`/`SEGMENT_KEYS`/`PATIENT_SOURCES`(鍵名)與 `closed_values` 的表(值域);評估器讀的框列就是 `句[].frames[]` 的每個 dict。目錄列預留 `CATALOG_KEYS = ("name", "path", "predicate", "cards", "hash")`(名、路徑、述詞或空、三個位置的張數、卡集合雜湊);`export()` 回傳的 `目錄` 現在是 `[]`,票 08 把目錄列清單填進去即可,`serialize` 的一列一行對空清單寫 `[]`、非空時每列一行。`版本` 欄位語意變時 `VERSION` 加一(目錄加欄不算框列語意變,是否加版本由票 08 定)。
- 未決:無。
