# 03: 述詞評估器對上參考評估器(卡層)

**What to build:** `Engine.runQuery` 接受 `q.preds = {inc: [述詞…], ex: [述詞…]}`,述詞用字面值寫,形狀與目錄、夾具相同。語意同參考評估器:同欄多值 OR、欄間 AND、同一框成立、沒寫的欄不看、空述詞全中;中心詞尾綴;區域沒寫玩家不看玩家;中心詞類/數量類/修飾語類各自看受事者片語任一段。包含述詞之間卡層 AND,可跨句;排除述詞看全卡、優先於包含;有任何述詞時沒有 `fr` 的卡不中。值不在表內就是不中;不認得的欄丟錯。流程照規格:每個述詞編成整數碼集合、掃框表得命中表、逐卡只查表。

對照同票交付:Python 用建置的同一支編碼函式產生編碼夾具入版控(`test_webindex` 守它與參考評估器的夾具同步);harness 的 `load` 多接框表;node 測試讀編碼夾具、經 `runQuery` 跑(一例包成一張一句一框的卡);另一條 node 測試讀真 data.js 與真匯出檔做全語料對照。不另匯出評估器內部函式。

句層條件並用、`hits` 與 `marks` 是票 04 的事;本票的 `rows` 可先照「命中框所在句的聯集」。

**Blocked by:** 02

**Status:** resolved

- [x] 夾具三段全過:96 例、3 雜湊、小語料張數
- [x] 編碼夾具與參考評估器夾具不同步時 `test_webindex` 失敗
- [x] 全語料:目錄 261 列 × 三個位置,張數與雜湊和匯出檔逐列相同(大類、中類以子節點聯集算);不符時測試列出查詢與位置
- [x] `runQuery` 例子:卡層 AND 可跨句、排除優先、只有排除、舊式卡文不中、未知值不中、不認得的欄丟錯
- [x] 舊 `q.act` 系列的既有測試全過
- [x] 建置產物文件表加編碼夾具與重生方法

## Comments

2026-11-01 交件(基準 predicate-index 30fcafc)。

- **評估器**:`web/js/engine.js` 的 `runQuery` 多讀 `q.preds`。每個述詞編成一組欄檢查,掃 `window.FRAMES` 得一張命中表(`Uint8Array`),逐卡只查表。沒有另外匯出內部函式。沒帶 `q.preds`、或 inc/ex 都是空的查詢,路徑與改前相同,網站行為不變;`web/data.js` 沒動。
- **編碼夾具**:`script/web/encode_fixture.py`(純函式 `encoded_fixture(夾具, 值域)` 加薄殼)產生 `script/web/predicate-fixture-encoded.json`,用建置的同一支 `frame_tables`/`encode_frame`。值域讀 `data/action_frames.json`:票 02 Comments 寫的 `doc["值域"]` 若指參考評估器夾具就不成立,那份夾具沒有這欄。
- **夾具三段**:`script/web/predicate.test.js`,96 例、3 雜湊、小語料 4 述詞 × 三個位置全過。
- **全語料**:目錄 261 列 × 三個位置 = 783 格,張數與雜湊 0 不符。其中 237 列走述詞 711 次查詢,24 列是大類、中類,以底下具名查詢的聯集算。基準:入版控的 `web/data.js` 與 `data/action_frames.json`。
- **守門會紅(一次性變異驗證,改完還原)**:
  | 改壞的地方 | 紅的測試 |
  |---|---|
  | 夾具改一例期望、夾具改一個框列值 | `test_committed_fixture_matches_the_reference_fixture` |
  | `SCALAR_KEYS` 改錯一鍵、`REGION_KEYS` 對調兩欄 | `test_frame_keys_copy_stays_equal_to_the_reference_evaluator` |
  | 中心詞改比前綴 | 96 例、全語料(列出 27 格的查詢與位置) |
  | 區域沒寫玩家仍比玩家 | 96 例、全語料(列出 129 格) |
  | 排除只看第一句 | 合成例子 3 條;全語料抓不到,它不跑排除 |
  | 修飾語位元差一 | 96 例;全語料抓不到,目錄述詞沒有修飾語類 |
- **耗時**(真資料、node vm 內、30 次中位數,測量時機器同時有其他工作,不是乾淨基準):無條件 24.1 ms;1 述詞 62.9、3 述詞 76.5、5 述詞 41.2、只比中心詞 31.6。數字的順序不隨述詞數遞增,雜訊不小。比規格原型(8.7、15.0、19.6、12.4)慢,一個已知原因是 runQuery 含逐卡的 `paramHit` 等既有成本(原型沒有),其餘沒有再拆。全語料測試整輪約 34 秒,規格估原型約 5.5 秒;規格不斷言耗時。正式數字留給票 05 在乾淨環境量,也要量真瀏覽器,不只 node vm。
- **測試**:script/web 175 條通過(新增 `EncodedFixtureTest` 4 條);node 186 條通過(新增 `predicate.test.js` 14 條,舊 `q.act` 系列在 `engine.test.js` 全過);effect-tokenize 1,056 條通過、skip 3。其他 `script/*` 套件沒跑,本票沒動它們。`node --test script/web/` 在這台機器上把目錄當模組而失敗,跑法是明確檔名:`node --test script/web/engine.test.js script/web/render.test.js script/web/predicate.test.js`。
- **票面外**:同步測試除了 `SCALAR_KEYS`,也守 `REGION_KEYS`、`PHRASE_KEYS` 與 `predicate.EXPORT_PATH` 相同(同一張對照,多兩行)。`.gitattributes` 給編碼夾具加 `merge=ours`,對齊建置產物文件的合併規則。README 的檔案表加兩列。
- **留給票 04**:
  - 述詞與句層條件並用還沒做對:目前 `q.text` 等只在卡層把關,命中句直接換成述詞的聯集,沒有限制在通過句層條件的句上,也沒看 `fl`。
  - `marks` 還沒有 `pred`,結果還沒有 `hits`,harness 的 driver 也還沒回 `hits`。
  - 例子放 `predicate.test.js`;框內容借編碼夾具的框列,卡手寫(見檔內 `box`)。夾具的框列名要新增時改參考評估器夾具再重生。
