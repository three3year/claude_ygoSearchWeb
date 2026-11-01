# 02: 框架進前端索引

**What to build:** 建置讀匯出檔,讓每張涵蓋卡在 data.js 裡帶動作框架:`fr`(與 `tx` 對齊的框號清單,有無就是涵蓋與否)、`fl`(● 子句指到領起句的句序號,沒有 ● 子句的卡不帶)、框表(`window.FRAMES`,一框一行)、`VOCAB.frame`(詞元表、中心詞表、各封閉類值域、涵蓋卡數)、`VOCAB.catalog`(目錄 261 列的名、路徑、述詞、三個位置的張數,不帶雜湊)、META 的框架部分雜湊與匯出檔來源雜湊、建置報告新節(涵蓋卡數、句數、框數、唯一框數、中心詞數)。編碼照規格「索引形狀」段:框元組欄序、列舉碼 0 表示沒有值、區域對一個整數、段四欄、尾端空值截掉、框表依第一次出現編號、中心詞表依次數遞減。`manner_value` 與 `統計` 不進索引。

過時或不合的輸入讓建置失敗,五類都列全部違反處:匯出檔版本不符;原文雜湊過時;卡面雜湊過時;框列或目錄述詞含值域外的值、目錄述詞含不認得的欄;涵蓋卡的 ● 子句找不到領起句。舊欄、`VOCAB.acat`、舊匯出檔照舊,網站行為不變。

編碼要是一支可重用的純函式,票 03 的編碼夾具會用同一支。

**Blocked by:** 01

**Status:** resolved

- [x] `build_index` 接縫的測試:`fr` 對齊與涵蓋規則(沒有框的句與卡帶空清單、舊式卡文不帶)、`fl` 指到領起句且沒有 ● 子句時不帶、三個位置都進、同內容的框共用一號、VOCAB 新部分
- [x] 五類建置失敗各一條測試
- [x] 不帶匯出檔(合成測試)時索引不帶框架部分,既有測試不受影響;舊欄逐值不變
- [x] 同輸入建置兩次 data.js 逐位元組相同
- [x] 真資料重建 `web/data.js` 通過全部建置檢查;舊六欄與 `VOCAB.acat` 與重建前相同(比對結果記進 Comments)——**舊六欄對「入版控的舊檔」有 754 張不同,原因是舊檔本來就過時,見 Comments「舊欄比對」;對同輸入的改前程式 0 差異**
- [x] 真資料的體積記進 Comments,與規格 Further Notes 的 D 舊欄並存數字(+896,339 / +239,651,卡片段含框表)差異要說明
- [x] node 測試與 script/web 測試全過

## Comments

2026-11-01 交件(基準 predicate-index 755772f)。

- **編碼函式**:`script/web/frameindex.py`(新模組,不 import webindex 也不 import 分詞鏈)。`frame_tables(框列清單, 值域) → FrameTables`(`.lemmas`、`.heads` 就是 VOCAB.frame 那兩張)、`encode_frame(框列, 表) → 框元組`;值域外的值 `KeyError`,不靜靜變 0。`frame_problems(框列, 值域)`、`predicate_problems(述詞, 值域)` 列違反處。索引部分在 `webindex._attach_frames`;`build_index` 多一個 `frames=` 參數,薄殼多 `--frames`。
- **索引形狀裡票面沒定的名字**:`VOCAB.frame = {lemmas, heads, domains, covered}`;META 鍵 `frame_digest`(框表、VOCAB.frame、VOCAB.catalog 一起算);`window.FRAMES` 放在 META 之後,因為 `compile_dry_run` 的 `project.py` 與 `measure_index.py` 以 `window.VOCAB`、`window.META` 切段。報告鍵 `report["frames"]`。`_acat_digest` 改名 `_content_digest`、`_category_stale` 改名 `_export_stale`(兩邊共用;`acat_digest` 值不變)。
- **五類檢查**:`checks` 的 `frame_version`、`frame_stale`、`frame_face_stale`、`frame_unknown_values`、`frame_orphan_bullets`。版本不符就不往下讀(舊版沒有值域);有值域外的值就不編碼;其餘照常跑完,好列全部違反處,這兩種情況 `report["frames"]` 是 None。缺 `action` 或段缺 `head` 也算 `frame_unknown_values`(編不出元組,建置不崩)。詞元與中心詞沒有值域,不算違反:真資料目錄述詞的詞元全在詞元表內(0 個不在)。
- **真資料建置**:全部檢查通過,五類各 0 筆。涵蓋 7,817 張、24,599 句、46,732 框、唯一框 12,048、中心詞 1,068、詞元 118;目錄 261 列、不帶雜湊、四欄與匯出相同;`fl` 445 張卡、● 子句 824、領起句 449,`fl` 全指到同段落、去掉最後一段的句。數字與規格 Further Notes 全同。`fr` 與 `tx` 不對齊 0 張。沒有框的句 7,624 = 規格的空框句 7,620 + 涵蓋卡上不在匯出的句 4。
- **逐框解回**(一次性比對,不入版控):把 data.js 的 `fr` + `FRAMES` + VOCAB.frame 解回框列,逐句和匯出檔比(`manner_value` 除外):46,732 框,不符 0 句;框號依第一次出現遞增。
- **決定性**:同輸入建兩次,全檔 26,290 行只差 `built_at` 一行;`built_at` 由薄殼給,其餘逐位元組相同。測試 `test_same_input_serializes_byte_for_byte` 固定 `built_at`。
- **舊欄比對**(要站主知道的一件事):
  - 對**同輸入、改前程式**(`git archive predicate-index` 的 `script/web` 跑同一批輸入):卡行 14,207 張裡 6,390 張逐位元組相同、7,817 張只多 `fr`/`fl`,其他差異 0;VOCAB 舊行全相同(只多 `catalog`、`frame`);META 只差 `built_at`、`frame_digest`、`sources` 多一鍵。本票沒動舊欄。
  - 對**入版控的舊 data.js**:VOCAB(含 `acat`)全相同;舊六欄 754 張不同,其他欄 0 差異。逐欄不同張數:`ae` 0、`ac` 0、`aes` 387、`aen` 749、`acs` 1、`acn` 6(類別樹不變,只有動作對象的欄變)。帶欄卡數:`ae` 7,817→7,817、`ac` 3,190→3,190、`aes` 3,488→3,710、`aen` 7,199→7,216、`acs` 1,424→1,423、`acn` 1,720→1,726。原因:入版控的 data.js 是 2026-10-30 建的(META `action_categories.json` 4d49b806),而 `data/action_categories.json` 在 named-queries 票 03(f47a8f8)與四題裁定(6efe830)改過、之後沒重建網站。這次重建把這批落差一起帶進來:**現行側欄的「動作對象」篩選在這 754 張上會變**(變成舊匯出檔現在說的值),規格「網站行為不變」指本票不改行為,這批是欠的重建,不是新改動。要拆開的話得先另 commit 一次只重建舊欄的 data.js。
- **體積**(規格方法:各段分開 gzip -9,卡片段含框表,對入版控舊檔 8,296,543 / 1,991,027):實際 **+921,851 / +245,366**;規格 D 舊欄並存 +896,339 / +239,651,多 +25,512 / +5,715。逐項:
  | 來源 | raw | gz |
  |---|---|---|
  | 舊六欄補上過時的 754 張(上一項) | +5,311 | +1,193 |
  | `fl` 欄(原型沒有;獨立 gzip 是規格的 597,行內實測) | +8,156 | +2,959 |
  | 框表一框一行(原型單行) | +12,045 | +426 |
  | 鍵序(`fr` 排在舊欄之後,原型排在前) | 0 | +1,153 |
  gz 不可加,逐項相加與總差有 16 bytes 落差。整檔 8,314,689 / 1,995,554 → 9,326,221 / 2,258,289(+1,011,532 / +262,735,含 VOCAB 新部分):VOCAB.frame 36,133 / 11,445(中心詞表 33,751 / 10,475、詞元表 1,527 / 622、值域 809 / 441)、catalog 53,431 / 5,261。data.js 真實載入約多 0.26 MB gz,規格估 +240 KB 加 VOCAB 約 +16 KB,相符。
- **測試**:script/web 171 條通過(新增 `FrameEncodingTest` 5 條、`FramesInIndexTest` 30 條,先紅後綠);node 172 條通過;effect-tokenize 1,056 條通過、skip 3(本票沒動分詞鏈)。data.js 在 node vm 載入可讀,網站 JS 沒動。
- **工作樹注意**:工作樹 checkout 出來的 `data/tag_cards.json` 也是 CRLF(同 `cards.json`),META 的來源雜湊會變成 5bb79bb7;從主 repo 複製 LF 版後是 54a40857,與舊 META 相同,入版控的 data.js 是這樣建的。git 視兩個檔無變更,沒進 commit。
- **留給票 03**:`from frameindex import encode_frame, frame_tables`;夾具一例包成一卡時用 `frame_tables(夾具全部框列, doc["值域"])`。harness 的 `load` 要多接框表(`window.FRAMES`);`fr`/`fl`/`VOCAB.frame.domains` 的碼是值域序號加一,區域對不加一。`frameindex.SCALAR_KEYS` 是框列鍵 ↔ 述詞欄的對照(`script/web` 不 import 分詞鏈,所以有這一份),票 03 的編碼夾具同步測試順便守它與 `predicate.EXPORT_PATH` 相同最省。
- **留給票 05**:GLOSSARY 前端索引條的體積寫 9.33 MB、gzip 2.26 MB;`docs/agents/build-products.md` 還沒提 `web/data.js`。
