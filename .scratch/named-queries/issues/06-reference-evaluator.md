# 06: 參考評估器與夾具

**What to build:** 一個純 Python 函式:(述詞, 匯出的框列)→ 命中與否。述詞的欄:詞元、位置、極性、否定形、態、來源/目的/所在((玩家或不限, 區域) 清單,任一項命中)、受事者中心詞(尾綴,任一段任一值)、目的中心詞、中心詞類、數量類、修飾語類、施事者、方式類、動作對象;欄間 AND、同欄多值 OR、全部在同一框上;述詞沒寫的欄不看。讀的是票 05 匯出的框列,與規格 3 的 JS 評估器同一份輸入。例子夾具(述詞 × 框列 → 真假)一張 JSON 入版控:每個欄一組正反例、同欄多值、不看玩家、尾綴不中前綴(モンスター 不中 モンスターカード)、空述詞;Python 測試讀它,規格 3 的 node 測試讀同一張。

**Blocked by:** 05

**Status:** resolved

- [x] 評估器讀匯出框列,不讀 frames.json 的框架
- [x] 夾具 JSON 入版控,Python 測試逐條跑;夾具格式寫在檔內說明
- [x] 述詞字彙(欄名與值域)只有一份,目錄(票 07)與匯出(票 05)都 import 它
- [x] 既有全部測試照過

## Comments

- 2026-11-01 實作(分支 wt/06-evaluator,基於 36231c7=票 01〜05 全部)。全部在 `.scratch/effect-tokenize/`。**新模組 `predicate.py`**(述詞字彙 + 參考評估器;不 import frames/categories/patient——詞元檢查要用補語不併判準時才在函式內延後 import frames):
  - 字彙:`FIELDS` 16 個述詞欄名(GLOSSARY「框架述詞」條的詞:詞元、位置、極性、否定形、態、來源、目的、所在、受事者中心詞、目的中心詞、中心詞類、數量類、修飾語類、施事者、方式類、動作對象;常數 `FIELD_*`);`EXPORT_PATH` 述詞欄 ↔ 匯出鍵路徑一張表(詞元→action … 來源→regions.source、受事者中心詞→phrases.patient[].head、中心詞類/數量類/修飾語類→phrases.patient[].head_kind/quantity/modifiers、目的中心詞→phrases.goal[].head、動作對象→patient_mode);`DOMAIN` 每欄值域直接是封閉表物件(closed_values 的 NEGATION_FORMS/AGENTS/MANNER_KINDS/HEAD_KINDS/QUANTITY_KINDS/MODIFIER_KINDS/PATIENT_MODES、constraints.POSITIONS、極性三值 `POLARITIES`、action_lemmas.VOICES);區域欄玩家 closed_values.PLAYERS + None(不限)、區域 ZONES。**匯出鍵名 `FRAME_KEYS`/`PHRASE_KEYS`/`SEGMENT_KEYS` 搬進這裡**(拼法一字不改),`export_frames.py` 改 import(匯出檔 md5 f95b67f37a6945fa4679974acfd8ede5 重跑前後相同)。`此卡/非此卡` 原本只在 patient.py 定義,搬成 `closed_values.PATIENT_MODES`、patient.py 改 `SELF, NONSELF = PATIENT_MODES`(值域不抄第二份;patient 的三把尺差異 0)。
  - 評估器:`matches(述詞, 框列)` → bool;`matcher(述詞)` → 編好的判定函式(全語料用,依 FIELDS 序先比詞元);`problems(述詞)` → 違反字彙清單(不認得的欄、值不在值域、區域項形狀、玩家/區域值域、中心詞非空字串、詞元不是正規詞元——沿用 action_lemmas.normalize 與 frames.splits_complement 判準)。語意:欄間 AND、同欄多值 OR、全在同一框列;沒寫的欄不看、空述詞全中、框列沒鍵就不中;每欄值是清單、單一字串等於一項;區域項 [玩家或 null, 區域],null 不看玩家,相對/無 是值;中心詞尾綴;中心詞類/數量類/修飾語類看受事者片語任一段、各欄獨立不要求同一段。
  - 張數輔助(票 08 用,本票不寫進匯出檔):`card_sets(述詞清單, 句列)` → 每個述詞 `{代價/效果/條件: 卡集合}`;`cards_hash(卡集合)` → 密碼依數值排序、逗號連寫、sha1 前 16 碼。實測 250 述詞 × 24,599 句 4.8 秒。對照數字:破壊:モンスター 效果 605(規格尾綴口徑 609→605 ✓)、破壊(耐性) 效果 658、特殊召喚←墓地 1,228、加える:デッキ→手札 1,473、取り除く@お互いのフィールド 代價 10/效果 0(規格「不留」口徑的例子 ✓);空集合雜湊 da39a3ee5e6b4b0d。
- **夾具 `.scratch/effect-tokenize/predicate-fixture.json`**(入版控;node 測試可用相對路徑 `../../.scratch/effect-tokenize/predicate-fixture.json` 讀):頂層 `說明`(格式寫在檔內)、`版本`(= export_frames.VERSION,測試守)、`框列`(16 個具名框列,形狀同 action_frames.json 句[].frames[])、`例子` **96 條**(名/述詞/框列名/命中:空述詞 2、每欄正反例與多值、不看玩家、相對與無、欄不互通、尾綴 モンスター 中 効果モンスター 不中 モンスターカード、任一段、三條裁定——詞元節點 極性 [肯定,可能]、耐性 否定形 [受身,不成不受]、限制 [不可能]——與一般否定、欄間 AND、具名查詢與使用者述詞各幾條)、`雜湊` 3 條(卡清單 → 雜湊)、`張數`(4 句小語料 × 4 述詞 → 三個位置的卡清單與雜湊)。
- **測試 `test_06_evaluator.py` 16 條**(先紅——沒有模組——再綠):夾具逐條(subTest 96 條)、版本、框列只用匯出鍵、夾具述詞過字彙檢查、雜湊例、張數例;字彙一致性(export_frames 的鍵 `is` predicate 的、每欄路徑落在 FRAME_KEYS/REGION_KEYS/PHRASE_KEYS/SEGMENT_KEYS、值域是封閉表物件、problems 各型一條、不認得的欄 raise);接縫(合成卡經組裝→框架抽取→框列匯出的框列拿來評估:具名查詢中/一欄不中/耐性讀否定形);全語料(讀 data/action_frames.json,缺檔 skipTest:空述詞命中框數 = 統計.位置、四條裁定述詞各有卡、取り除く@お互い 效果位 0)。effect-tokenize 全套 976 條、node 172、script/* 66/43/469/55/136 全過;downstream_baseline 三把尺差異 0、舊匯出不變;`data/action_frames.json` 不變。
- **假設 / 偏離**:(1)雜湊「連寫」加了逗號分隔(12,345 與 123,45 才不同串);規格 3 的 JS 照夾具的 `雜湊` 例重算。(2)極性省略 = 不看極性;「省略=肯定與可能」是目錄的預設,票 07 載入目錄時補成明文清單再交給評估器(評估器不替目錄猜)。(3)單一字串視為一項清單(規格說詞元單值),JS 要同樣處理(夾具有例)。(4)`manner_value`(表示形式值)沒有述詞欄——GLOSSARY 與規格的述詞欄表都沒列,要查表示形式值時加一欄即可(EXPORT_PATH 加一列)。(5)中心詞類/數量類/修飾語類只看受事者片語(GLOSSARY「受事者的中心詞與中心詞類」),目的片語只比目的中心詞。
- **給票 07/08 的接點**:目錄檔的述詞就用 `predicate.FIELDS` 的欄名與 `DOMAIN` 的值;載入時逐述詞 `predicate.problems()`(空清單才過);命名規則對 FIELDS 的子集寫(本規格:詞元/極性/否定形/來源/目的/所在/受事者中心詞/目的中心詞)。命中:`matcher(述詞)` 編一次、對每框列呼叫;張數與雜湊:`card_sets(目錄述詞清單, doc["句"])` 後 `cards_hash(sets[位置])`,寫進 `export_frames.CATALOG_KEYS` 的 cards/hash;「不留」= 三個位置集合全空。規格 3 的 JS 評估器:讀同一張夾具跑 `例子`/`雜湊`/`張數` 三段,語意照 predicate.py 檔頭。
- 未決:無。
