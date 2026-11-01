# 05: 交件

**What to build:** 整合分支上全部合併並重跑,確認網站行為沒變、新引擎對上全語料,把給規格 4 的東西交出去。

- 全套重跑:effect-tokenize 全套、node 測試、script/* 五套;分詞鏈全鏈與索引建置;鏈重跑後 `data/` 無意外差異、舊匯出檔 md5 不變、剝鍵與回指、動作對象基準差異 0。
- 實測:1〜5 個述詞的耗時(真引擎、真 data.js)與 data.js 最終體積,記進 Comments,對照規格 Further Notes 的原型數字。
- 文件:GLOSSARY 前端索引條(`fr`、`fl`、框表、VOCAB 新部分、體積實測)、值域正典條例外段(封閉類值域隨匯出檔)、框架述詞條(JS 評估器已對上;● 子句評估時也看領起句的框);ADR-0018 Consequences 補「索引用框表」與「舊欄留到規格 4 切換」兩句;建置產物文件表核對。
- 給規格 4 的對照寫進本票 Comments:查詢與結果形狀(`q.preds`、`rows`、`hits`、`marks`)、VOCAB 新部分、述詞沒寫 位置 就是三個位置都看(卡片要帶預設)、要刪的舊東西清單(抄自 named-queries 票 11 Comments,加 `actSel/actRows` 與舊軸 UI,對照現況核對)。
- 地圖 Decisions so far 的「寫規格 3」補交件註記;地圖票「寫規格 4」補讀哪裡。

**Blocked by:** 04

**Status:** resolved

- [x] 全套測試與全部基準比對通過,數字寫進 Comments
- [x] 實測耗時與體積寫進 Comments
- [x] 網站手動開一次:現行類別樹、含代價、動作對象、舊網址、句尾標籤照舊——**動作對象不符合規格字面**:此卡、非此卡在 754 張卡上會變,見 Comments「網站行為」;其餘照舊
- [x] GLOSSARY 三條、ADR-0018 兩句、建置產物文件
- [x] 給規格 4 的對照與要刪清單
- [x] 地圖與地圖票更新

## Comments

2026-11-01 交件(基準 predicate-index a7a0343;工作樹用 `worktree_bootstrap.py --build` 複製建置輸入,再從主 repo 複製 LF 版 `data/cards.json`、`data/tag_cards.json`,兩檔 git 視為無變更、沒進 commit)。

### 網站行為

**給站主的結論:不符合。** 規格「網站行為逐位元組不變」在「動作對象」篩選上不成立:整合分支併上去後,284 個節點裡,選此卡時 19 個、選非此卡時 98 個節點的命中卡會變(加含代價 20、101 個),涉及 754 張卡。不選動作對象(不限)時,類別樹、含代價、舊網址、句尾標籤全部照舊。

- **原因**:入版控的舊 `web/data.js` 是 2026-10-30 建的,比規格 2 舊。`data/action_categories.json` 在 named-queries 票 03(f47a8f8)與四題裁定(6efe830)改過動作對象,之後網站沒重建。票 02 重建把這批落差一起帶進來。程式沒改舊欄:對同輸入、改前的建置程式,舊欄差異 0(票 02 Comments)。
- **逐欄**(舊 = 755772f 的 data.js,新 = 本分支;本票重算,與票 02 相同):`ae` 0、`ac` 0、`aes` 387、`aen` 749、`acs` 1、`acn` 6,聯集 754 張;其他欄 0 差異;`VOCAB.acat` 相同、節點 284 個順序相同。例:黑之魔導強化(111280)的葉 160 從非此卡移到此卡。
- **影響**(新舊兩份 web/ 各載入真 data.js,284 節點逐一跑查詢、比命中卡與命中句;舊網址解析抽 3 條,新舊相同):

  | 查詢 | 卡集合不同的節點 | 只差命中句 | 命中合計(卡·節點)舊 → 新 | 涉及卡 |
  |---|---|---|---|---|
  | 包含,不限 | 0 | 0 | 66,993 → 66,993 | 0 |
  | 包含,含代價 | 0 | 0 | 75,073 → 75,073 | 0 |
  | 排除,不限 | 0 | 0 | 2,153,035 → 2,153,035 | 0 |
  | 包含,此卡 | 19 | 1 | 13,600 → 14,521 | 387 |
  | 包含,非此卡 | 98 | 0 | 43,585 → 43,409 | 749 |
  | 包含,此卡+含代價 | 20 | 1 | 17,646 → 18,565 | 388 |
  | 包含,非此卡+含代價 | 101 | 0 | 47,884 → 47,726 | 753 |
  | 排除,此卡 | 19 | 0 | 2,206,428 → 2,205,507 | 386 |
  | 排除,非此卡 | 98 | 0 | 2,176,443 → 2,176,619 | 743 |

  全部 14,207 張卡的 HTML(無條件,含句尾標籤):0 張不同。帶 mark 的 HTML 只抽了一組(特殊召喚+含代價):不限 4,028 張全同;此卡 1,596 同、2 不同、新檔少 1 張;非此卡 2,663 同、2 不同、新檔多 1 張。「其他軸」只抽了無條件與卡名 2 種,相同;沒逐軸比,理由是非動作類別欄 0 差異、`engine.js` 沒有述詞的路徑不變(票 03、04 Comments)。
- **沒處理**:欠的重建和本規格綁在同一個 data.js。要把它拆開、或要這批結果不進站,都得站主決定;本票沒動。

**網站手動開一次**(`python -m http.server` 起現行 web/,Playwright 的瀏覽器 Chrome/156 實際點;同時起一份 755772f 的 web/ 對照)。console 只有 `favicon.ico` 404 一筆(新舊都有)。

| 操作 | 看到什麼(現行) | 755772f |
|---|---|---|
| 開頁 | 頂列「14207 張卡・34390 個效果句」;軸標題「動作類別 涵蓋 7817 / 14207 張」 | 節點相同 |
| 類別樹 | 點標題展開;13 個大類、284 個節點;展開 召喚 › 特殊召喚 看到 6 片葉;過濾框打 墓地 留 33 個節點並展開祖先 | 節點相同;過濾框邏輯沒動,未另開 |
| 點葉搜尋 | 點 特殊召喚←墓地、搜尋:網址 `#act=召喚›特殊召喚›特殊召喚←墓地`,共 663 張第 1/7 頁,軸上數字 1;首張 異色眼弧靈擺龍 | 全節點比對相同 |
| 含代價 | 勾選後網址多 `actCost=1`,仍 663 張;句尾出現 `代價:除外←フィールド` 等標籤 | 全節點比對相同 |
| 動作對象 | 此卡:`actPat=self`,112 張;非此卡:`actPat=nonself`,**548 張** | 非此卡 **547 張**,就是上節那批差異;此卡未以同組條件開舊站 |
| 舊網址 | 直接開 `#act=…特殊召喚←墓地,-破壊,不存在的節點&actCost=1&actPat=self`:葉為包含、破壊 為排除、不存在的節點安靜忽略,含代價勾上、此卡亮起、軸自動展開、數字 2,110 張 | 110 張、狀態相同,但首頁 `act-hit` 標籤 **101 個**(現行 100 個) |
| 句尾標籤 | 命中句黃底,句尾列該句的葉,命中的葉有框(`title` 本次搜尋命中);代價位帶 `代價:` 前綴 | 無條件 HTML 全同 |

### 全套與基準

| 項目 | 結果 |
|---|---|
| `run_chain.py` 全鏈 | exit 0,90.5 秒;之後 `git diff data/` 無內容差 |
| `data/action_frames.json` | 8e359d78f3a0a6e53d47e9f68e92e36b(不變;版本 2) |
| 舊匯出檔 `data/action_categories.json` | 443390e281f82a15a8efa6e90eefbd2b(不變,digest ok) |
| `frames.json` / `frame_queries.json` | 13fd923af331d8d82307a08369b15375 / ead887bb2cb9d068fa38240ea8d7dcfa |
| 剝鍵 `baseline_diff.py` | digest ok(e43cc838…),差異 0、底線鍵 0 |
| 動作對象 `downstream_baseline.py patient` | digest ok(225c4c7a…),差異 0 |
| 回指 `downstream_baseline.py anaphora` | digest ok(dc03f6b9…),差異 0 |
| 舊匯出 `downstream_baseline.py export` | digest ok |
| `build_index.py` 兩次 | 全部檢查通過,五類框架問題各 0;兩次只差 `built_at`,對入版控的檔也只差這一行(已還原,不 commit) |
| `encode_fixture.py` 重生 | md5 ac0f2e60… 不變 |
| effect-tokenize 全套 | **1,056 條 OK,skip 0** |
| node(engine、render、predicate) | **205 pass / 0 fail / 0 skip**,含全語料 783 格 5.4 秒 |
| `script/*` 五套 | card_list 66、faq_info 43、tag_card 469、text_format 55、web 175,全 OK |
| 第六套 `script/text_glossary`(票面沒列,順手跑) | 37 OK |

- **skip 0 的條件**:票 01、04 記的 2〜3 個 skip 是 digest 守門因 CRLF 的 `cards.json` 略過。這次用 LF 版,md5 98d3c3f6… 與 digest 相同,守門全部真的比了。
- 目錄 261 列 × 三個位置與匯出檔相同由上面全語料測試守;本票沒改語意,沒有另跑變異驗證。

### 實測

方法:`Engine.runQuery`、真 data.js,述詞與原型相同(`tools/measure_eval.js` 的 A〜E)。單位 ms,一輪 31 次取中位;瀏覽器 3 輪、node 4 輪,列各輪中位的範圍。機器未隔離,有其他工作時會波動。

| 查詢 | 命中張 | 瀏覽器(Chrome/156) | node vm | 規格原型(node,D) |
|---|---|---|---|---|
| 無條件 | 14,207 | 8.1〜8.6 | 17.4〜27.6 | — |
| 1 述詞 | 1,346 | 4.5〜5.1 | 11.2〜14.8 | 8.7 |
| 2 述詞 | 23 | 2.7〜3.1 | 6.0〜7.7 | — |
| 3 述詞 | 7 | 3.6〜4.0 | 6.7〜9.6 | 15.0 |
| 4 述詞 | 1 | 4.0〜4.8 | 7.3〜10.8 | — |
| 5 述詞 | 1 | 4.2〜4.7 | 7.6〜11.4 | 19.6 |
| 只比中心詞(モンスター、魔法) | 6,548 | 12.2〜16.7 | 32.8〜47.7 | 12.4 |
| 只有排除 | 6,471 | 7.9〜10.6 | 24.3〜27.0 | — |

- 瀏覽器單次最差:述詞 7.7、只比中心詞 21.2、只有排除 13.6,都在一次按鍵的預算內,不需要倒排索引(story 26)。命中張數與原型相同(1,346 / 7 / 1 / 6,548)。
- 數字不隨述詞數遞增:1 述詞比 2、3 述詞慢,命中張數也多得多。推論是耗時跟著要組結果的卡走,而不是述詞數,這點沒有 profile。3、5 述詞比原型快、只比中心詞在 node 比原型慢,原因都沒拆;只比中心詞的已知成本是 `paramHit`(票 03、04),另外原型沒有 `rows`、`hits`。原型與本表不同時段量,不要只看比值。
- node vm 比瀏覽器慢 2〜3 倍,票 03、04 的 vm 數字因此偏高,與這裡的瀏覽器欄不能比。
- 全語料測試 783 格單跑 5.4 秒,規格估原型約 5.5 秒;票 03 記約 34 秒、票 04 記約 8 秒,量法不同,不互比。

**體積**(本分支 data.js 與票 02 建的相同,只差 `built_at`):整檔 **9,326,221 / gzip 2,258,289**;動手前 8,314,689 / 1,995,554,**+1,011,532 / +262,735**。卡片段(含框表)+921,851 / +245,366,對規格 D 舊欄並存 +896,339 / +239,651 多 25,512 / 5,715,逐項來源在票 02 Comments(`fl`、框表換行、鍵序、欠的 754 張)。刪舊六欄後卡片段依規格約 +318,911 / +79,104(沒實測,舊欄還在)。

### 給規格 4 的對照

**查詢**:`q.preds = {inc: [述詞…], ex: [述詞…]}`,空或沒有就不是條件。述詞是字面值物件,欄名是參考評估器 16 欄(詞元、位置、極性、否定形、態、來源、目的、所在、受事者中心詞、目的中心詞、中心詞類、數量類、修飾語類、施事者、方式類、動作對象),形狀與 `VOCAB.catalog[k].predicate` 相同:值是單值或清單(同欄多值 OR);區域項 `[玩家或 null, 區域]`,`null` 不看玩家,`相對`、`無` 是值。

- **述詞沒寫 位置 就是三個位置都看**(規格裁定)。點 破壊 會連條件位一起算,所以卡片一定要帶預設,目錄列的張數才對得上;引擎不會替你補。
- 不認得的欄**丟錯**(`不認得的欄:亂寫`),未知值是不中。網址層要先濾掉未知參數,不能把它們送進引擎。
- 空述詞 `{}` 是全中,但卡要有框:7,817 張涵蓋卡只中 7,816,**誤捕(4227096)整張沒有框**。只用排除述詞時它照算涵蓋。

**結果**:`Engine.runQuery → {cards: [{card, rows, hits?}], marks}`。

- `rows`:命中句索引,語意同現行;只有排除述詞且沒有其他句層條件時是 `null`。
- `hits[k]` 是 `rows[k]` 那句的 `[述詞序號, 框所在句, 框序號]` 清單,只有包含述詞時才帶。框所在句 ≠ `rows[k]` 就是領起句的框。框序號是框所在句 `fr` 清單的序號,與匯出框列原文順序一致。真資料例:`{id: 35699, rows: [2], hits: [[[0,2,4],[1,2,0]]]}`。
- `marks` 多 `{type: 'pred'}`,只有包含述詞時才有。
- 領起句的框命中時,通過句層條件的領起句與它每個 ● 子句都是命中句,所以命中句可能比框所在的句多。

**票 04 自定的三件事**(規格沒寫死,規格 4 要用時以這裡為準,細節見票 04 Comments):

1. **述詞與舊 `q.act` 並用的命中句**:兩者各看通過句層條件的句,都過才中;命中句取聯集,只因舊軸命中的句 `hits[k]` 是空清單。沒選「述詞只看舊軸縮過的句」,那會變成同句才過。隨舊軸刪除,目前介面也不送 `q.preds`。
2. **`pred` mark 只有包含述詞才有**:只有排除時掛 mark 的話 `rows` 就不再沿用其他條件的結果。
3. **`hits[k]` 內的順序**:依 `[述詞序號, 框所在句, 框序號]` 由小到大;領起句一定在 ● 子句之前,所以它的框排在前。

**VOCAB 新部分**:

- `VOCAB.frame = {lemmas, heads, domains, covered}`:詞元表 118(字典序)、中心詞表 1,068(次數遞減)、`domains` 12 張(值序是宣告序;**鍵序是字典序不是宣告序**,要照宣告順序擺欄得另定)、`covered` 7,817。
- `VOCAB.catalog` 261 列 `{name, path, predicate, cards: {代價, 效果, 條件}}`,不帶雜湊;**大類、中類 24 列 `predicate` 是 `null`**,要由子節點算聯集;其餘 237 列極性已補明文。
- `window.FRAMES`、`fr`、`fl`、`META.frame_digest`、`META.sources["action_frames.json"]`:給引擎與建置,介面不必讀。

**接點**:`render.js` 的 `badgeText` 遇到沒對應的 type 顯示 type 字面,`pred` 要給標籤;`manner_value` 沒進索引,要顯示得從匯出加。

**要刪的舊東西**(抄自 named-queries 票 11 Comments,加 `actSel/actRows` 與舊軸 UI,逐項對照現況核對過)。程式都在,除非另註。

- 匯出與基準:`data/action_categories.json`、`export-digest.json`、`downstream_baseline.py` 的 `export` 尺與 `EXPORT`、`test_downstream_baseline.py` 的舊匯出檔測試。
- 分詞鏈:`categories.py`、`export_categories.py`(`export_common.py` 留給 `export_frames`)、`category_tree.json`、`catalog-mapping.json`(只剩歷史用途,可刪可留);`run_chain.STEPS` 兩步、`test_run_chain.py` 的步驟清單;`.gitignore` 的 `frame_categories.json`、`card_categories.json` 與註解;`test_categories.py`、`test_export.py`。
- 網站建置:`build_index.py` 的 `DEFAULT_CATEGORIES`、`--categories`、三個 `category_*` 報告列;`webindex.py` 的 `_attach_categories`、`_SPARSE_CATEGORY_FIELDS`、`_CATEGORY_GROUPS`、`category_*` 檢查、`VOCAB.acat`、`META.acat_digest`、`META.sources["action_categories.json"]`;`test_webindex.py` 動作類別段。舊欄 `ae/ac/aes/aen/acs/acn`。
- 前端:`web/js/acat.js` 與 `index.html` 第 116 行;`engine.js` 的 `PAT_FIELDS`、`patMode`、`modeLeaves`、`actSel`、`actLeaves`、`anyIn`、`actExcluded`、`actRows`、`runQuery` 的舊軸分支與 `act` mark,及匯出的 `modeLeaves`、`patMode`;`query.js` 的 `{act, dom: 'acat'}` 與 `actNodeHtml`、`patHtml`、`actAxisHtml` 等舊軸 UI(含代價、動作對象 radiogroup、過濾框);`hash.js` 的 `ACT`、`ACT_COST`、`ACT_PAT`;`render.js` 的舊 `act` 句尾標籤(第 31、257〜266 行,規格 4 改寫不是直接刪);`style.css` 的 `.act*`。
- 測試與 harness:`frontend_harness.js` 的 `__acatFilter`、`acatFilter`;`engine.test.js`、`render.test.js` 的動作類別段(搜尋關鍵字命中 156 / 13 行,部分是述詞線以外的合成資料,要逐條看)。
- 文件:`build-products.md` 的 action_categories 列與 export digest、`GLOSSARY` 前端索引條的舊段與動作類別第三版段的舊樹檔、README(第 115、119、135〜141、180、188、199 行)、`test_webindex.EncodedFixtureTest.test_copies_of_chain_tables_stay_equal` 比對 `export_categories.SUB_INDEX` 那一行(刪檔時比對對象搬到留下的模組或拿掉)。「規格 3 切換」的舊註解已在下面 Code review 修正改成規格 4。

與票 11 清單的出入,**先看這幾條**:

1. **更正 `vocab.py` 那項不要刪**:票 11 寫「`vocab.py` entry("ae") 等」,實際 `entry("ae", "全效果")`、`entry("ac", "發動")` 是舊 tag 值域(耐性內容、無效對象),與索引欄同名不同物;索引欄的名字在 `webindex.py`。
2. **更正路徑**:`rewrite_tree.py` 在 `.scratch/named-queries/tools/`,不在 effect-tokenize。
3. **`_acat_digest` 已改名 `_content_digest`、`_export_stale` 共用**(票 02):這兩個留給框架部分,不要跟著刪;`category_stale` 這個呼叫才刪。
4. **`test_04_patient.py` 依賴 `test_export`**(票 11 寫「刪前確認」,確認了):`from test_export import DRAGON, SPELL, XYZ, clause, export, modes, wipe`,其中 `export` 走舊匯出。要先把夾具與接縫搬到新地方,才能刪 `test_export.py`。
5. **`llm_check.py` 是模組頂 `import categories`**,不只 `queries` 子命令讀 `frame_categories.json`;批次檔歸組與 `tree.md` 也讀它,不是拿掉一格就好。`test_10_llm_check.py` 的略過條件要跟著改。
6. **票 11 沒列的 import**:`.scratch/frame-predicate-search/tools/compile_dry_run.py`、`project.py`、`.scratch/named-queries/tools/compare_dry_run.py`、`rewrite_tree.py` 都 import `categories`;前兩者與第三者的結果檔(`tools/results/*`、`compare-v4.md`)在 `build-products.md` 表上算可重生。刪歸葉程式後它們跑不動,規格 4 要定:工具與結果轉成歷史(表上拿掉)或改寫。
7. **`patient.py`、`negation.py`、`places.py`、`catalog.py` 的註解**提到舊程式,邏輯不依賴;`catalog.py` 內給舊程式共用的常數(`PLAYER_LABEL` 等)要看刪後還有沒有人讀;`test_lint.py` 的 `OLD_CLASSIFIER_MODULES` 與它那條規則隨之退場。

### 文件與地圖

GLOSSARY:前端索引條加框架段、值域正典條例外段補封閉類、框架述詞條改 JS 評估器已對上與 ● 子句;動作類別第三版段「規格 3 刪」改規格 4。ADR-0018:切換點改規格 4,加索引用框表、舊欄留到規格 4 切換兩條。`build-products.md`:表加 `web/data.js`(票 02 留的),三處「規格 3」改規格 4,並寫明 `web/data.js` 不在 `.gitattributes`。README:分詞鏈步驟、索引輸入、`FRAMES` 三處(票面沒列,事實已不對就順手改)。地圖 Decisions「寫規格 3」補交件註記;地圖票 07 補讀哪裡。

### 偏離與沒做的

- 上面「不符合」那一條。**CODING_STANDARDS 要求偏離規格指到 `llm-check/summary.md`,這裡只寫在本票 Comments**:那是審核關卡 md,要改得走鏡像重發;票面沒要求,留給站主決定要不要補。
- 全節點比對只比動作類別軸;其他軸只抽無條件與卡名(見上)。
- `.gitattributes` 沒給 `web/data.js` 加 `eol=lf merge=ours`:票面只要文件核對,照現況記進文件。
- 一次性腳本與截圖在 session scratchpad,沒入版控。規格 Further Notes 的 `measure.txt` 是原型工具的輸出,本票沒重跑;本票實測走真引擎。

### Code review 修正

2026-11-01,review 基準 ee10d32..a50079d。行為問題先補失敗測試(紅)再修。

**守門**:改完重跑 `run_chain.py`(exit 0)、`build_index.py`、`encode_fixture.py`:`data/action_frames.json` 8e359d78…、`data/action_categories.json` 443390e2… 都不變,`web/data.js` 內容相同(建置印「內容沒變,不動」,md5 前後相同、`git diff` 空),編碼夾具 `git diff` 空。effect-tokenize **1,056 OK、skip 0**;node(engine、render、predicate)**205 pass / 0 fail / 0 skip**,含全語料 783 格;script/web **186 OK**(+11);card_list 66、faq_info 43、tag_card 469、text_format 55。

**行為**

- S1:`print_checks` 去掉 `limit`,全部違反處都印;`print_invariant` 同型的 `[:20]` 一併拿掉。
- S2:`predicate_problems` 遇到 null、數字、物件值,或項不是字串、殘缺區域對,列違反處;`frame_problems` 遇到殘缺區域對或整欄不是清單同樣列。詞元與中心詞沒有值域,但項非字串也擋(JS 的 `endsWith` 不該吃到)。
- S3:`_attach_frames` 先算領起句再判值域問題,兩類都列;`fl` 仍只在編得出框時才掛。
- S4:`webindex.keep_built_at`:既有檔除 `built_at` 那一行外相同就不動檔。比對走文字模式,CRLF 的 checkout 也算相同(這時連檔都不重寫,`git status` 乾淨)。內容有變才寫新時間。測試在 CLI 接縫(`BuiltAtTest`),`build_index.py` 檔頭原寫「不納入自動測試」跟著改。`print_report` 的 `file=sys.stdout` 預設值綁死匯入時的 stdout,改成 `None`。
- S5:ADR-0018 改成值域隨匯出檔;`build-products.md` 的 data.js 列、GLOSSARY 的建置時間定義跟著 S4 改。

**標準**

- H1:`frameindex` 六個對照常數收成一張 `EXPORT_PATH`(排列即元組序),`SCALAR_KEYS` 等全由它推得。**留不掉的**:`EXPORT_PATH` 本身與 `DOMAIN_PLAYER/ZONE`、`FIELD_LEMMA`、`FIELD_MODIFIERS`——匯出檔的值域只帶值、不帶框列鍵對照,而且版本與匯出檔逐位元組不動是本次守門;玩家與區域是讀值域的入口鍵。同步測試整張比 `predicate.EXPORT_PATH`,另守 `DOMAIN_*`、`FRAME_EXPORT_VERSION`、`SUB_INDEX`;再一條守值域每個封閉類都編得進元組。
- H2:`EXPORT_PATH`、`DOMAIN_*`、`FRAME_EXPORT_VERSION`、`_CATALOG_INDEX_KEYS`、`SUB_INDEX`、`FRAME_CHECK_LABELS`、`engine.js` 的槽位表與 `FRAME_CHECKS` 補來源與日期。`SUB_INDEX` 的來源只寫到 ADR-0015 與 2026-10,沒查到確切裁定日。
- H3:`run_chain.py`、`export_categories.py`、`catalog.py`、`test_downstream_baseline.py`、`test_lint.py`、`rewrite_tree.py` 的註解改規格 4;`build-products.md` 那三處票 05 已改。

**判斷題,修了的**:`SUB_INDEX` 正則取代 `BULLET_MARK` 與 `rsplit`,`-●甲` 這種尾巴不再算 ● 子句(真資料無此例);`_BuildState` 收參數團,兩支附掛共用一個 `cards_by_id`;`FRAME_CHECK_LABELS` 一份給檢查鍵、問題清單、報告,報告的標籤因此多了「請重跑分詞鏈」;`orphan_bullets` → `frame_orphan_options`;`_cut` 去參數;`engine.js` 槽位具名、`someInSlot`、拿掉 `|| []` 與 `FRAMES`、`FRAME_VOCAB` 的預設值;`encode_fixture` 常數改 `REFERENCE_FIXTURE`、`FRAME_EXPORT`、`ENCODED_FIXTURE`;96、3 改讀夾具自身,`test_webindex` 整段比對 `例子`。用詞:`frames` 只留給框表(`index["frames"]`、`window.FRAMES`、harness),整份匯出檔是 `frame_export`(`build_index` 參數、CLI `--frame-export`),報告節是 `frame_stats`。

**沒修的**

- `part["table"]` 的鍵名:`_content_digest` 連鍵一起雜湊,改名會動 `META.frame_digest`,`web/data.js` 就變了,違反本次守門。留一行註解;刪舊欄那波 data.js 本來就會變,規格 4 可順手改。
- 歷史紀錄裡的「規格 3 切換」:`.scratch/named-queries/spec.md`、其票、`frame-predicate-search/issues/05` 是當時的裁定,切換點的改動記在本規格第一題,不回頭改。`llm-check/summary.md` 第 302、311、329、912 行也還寫規格 3:它是審核關卡 md,要改得走鏡像重發,留給站主決定。

### 偏離的指向

「網站行為」節的偏離已寫進規格「需要你決定的」的「動作對象篩選在 754 張卡上會變,接受嗎?」,等站主裁定。

2026-11-01 站主裁定:(a)接受,不改程式。
