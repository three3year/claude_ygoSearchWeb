# 08: 刪舊鏈與舊工具

**What to build:** 分詞鏈少跑兩步,歸葉程式、舊匯出檔、舊樹檔和只為它們存在的工具都不在了,抽驗工具改讀目錄繼續能用。清單以 predicate-index 票 05 Comments「要刪的舊東西」的匯出與基準、分詞鏈兩段與七條出入為準,加上規格「刪除」段與「刪歸葉程式後,仍 import 它的舊工具怎麼辦?」的決定。

**Blocked by:** 07

**Status:** resolved

- [x] 刪掉前先記下最後一個 commit,寫進 Comments,票 09 記進地圖
- [x] `test_04_patient.py` 依賴的夾具與接縫先搬到留下的檔,再刪 `test_export.py`、`test_categories.py`
- [x] `llm_check.py` 與 `test_10_llm_check.py` 的歸組與 `tree.md` 改讀目錄與 `frame_queries.json`,不再 import 歸葉程式;跑一次產出批次檔確認能用
- [x] 刪 `categories.py`、`export_categories.py`、`category_tree.json`、`catalog-mapping.json`、`data/action_categories.json`、`export-digest.json`;`downstream_baseline.py` 的 `export` 尺與相關測試、`run_chain.STEPS` 兩步、`.gitignore` 條目跟著拿掉;`export_common.py` 留
- [x] 刪 `compile_dry_run.py`、`project.py`、`evaluate.js`、`compare_dry_run.py`、`rewrite_tree.py` 與兩個舊工具的 `results` 目錄;本規格的 `measure_ui.js`、`old_nodes.js` 也刪,輸出留著
- [x] `.gitattributes` 與建置產物表拿掉對應條目;`test_lint` 的舊模組規則與 `test_copies_of_chain_tables_stay_equal` 的比對對象依清單處理;留下的模組還提到舊程式的註解改掉
- [x] 舊票、舊規格、`catalog.json` 與 `llm-check/summary.md` 裡提到的路徑不回頭改
- [x] 全鏈重跑 exit 0;`data/action_frames.json` md5 不變(8e359d78f3a0a6e53d47e9f68e92e36b);`data/action_categories.json` 不再產生;剝鍵、回指、動作對象基準差異 0
- [x] 全 repo 沒有 import 或讀取已刪檔案的程式(搜尋結果記進 Comments);effect-tokenize 全套與 script/* 全過

## Comments

2026-11-02 交件。**刪除前最後一個 commit:`6dd3fcc`**(開工時的 `predicate-ui` tip;地圖 Notes 已記)。舊路徑要看用 `git show 6dd3fcc:<路徑>`。建置輸入用 `worktree_bootstrap.py --build` 複製;`data/cards.json`、`data/tag_cards.json` 已是 LF,md5 與 digest 相同,不必蓋。

### 數字

- 全鏈 `run_chain.py` exit 0,四步:分詞、框架、目錄、框列匯出。`data/action_frames.json` md5 **8e359d78f3a0a6e53d47e9f68e92e36b** 不變;`data/action_categories.json`、`frame_categories.json`、`card_categories.json` 都不再產生。
- 基準都真的比到(digest 守門 ok,不是略過):剝鍵差異 0、底線鍵 0(e43cc838…);動作對象差異 0(225c4c7a…);回指差異 0(dc03f6b9…)。
- `build_index.py`:全部檢查通過,「內容沒變,不動」,`web/data.js` 沒變。`report.py` 重跑 `report.md` 沒變。
- effect-tokenize **895 OK、skip 0**(動工前 1,056、skip 1)。node `script/web/` 八個檔 **339 pass / 0 fail / 0 skip**。script/web **167**、card_list 66、faq_info 43、tag_card 469、text_format 55,全 OK。
- 紅燈:`test_10_llm_check`(15 條 error)、`test_run_chain`(1)、`test_downstream_baseline`(6)都先看到失敗才改程式。

### 全 repo 搜尋

`git grep -nE` 比 `categories\.py|export_categories|import categories|from categories|category_tree|catalog-mapping|action_categories|export-digest|frame_categories|card_categories|compile_dry_run|compare_dry_run|rewrite_tree|evaluate\.js|tools/project|measure_ui|old_nodes\.js|test_export|test_categories|tools/results`,範圍 `*.py`、`*.js`、`*.html`、`.gitattributes`、`.gitignore`。命中 4 行,沒有一行是 import 或讀檔:

- `test_04_patient.py` 檔頭:說明例子從哪搬來。
- `test_vocab.py` 兩行、`test_webindex.py` 一行:測試名 `test_export_*`,同名不同物。
- `test_webindex.py:1340`:`assertNotIn("action_categories.json", text)`,守 data.js 不帶舊來源(票 07)。

文件(GLOSSARY、README、ADR-0018)的舊路徑留給票 09;舊票、舊規格、`catalog.json` 說明、`llm-check/summary.md` 照規格不改。

### `llm_check.py`

跑一次 CLI 確認能用(臨時 round,看過就刪,沒入版控):

| 指令 | 結果 |
|---|---|
| `categories --round 99 --seed 20261102` | 1,235 個框架(沒命中 50)切 8 批,`tree.md` 列整本目錄 237 個具名查詢 |
| `queries --round 99 --seed 20261101` | 100 張切 4 批,另寫 `catalog.md`;框列帶「命中=」「動作對象=」,沒有「較舊歸葉」 |
| `recheck --line categories --from 2`、`recheck --line queries --from 2` | 舊輪的 sample.json 讀得進、批次檔寫得出 |

`report --line categories` 由 `test_category_report_shows_the_current_hits` 跑過。

### 規格沒定、這張自己決定的

- **`test_export.py` 的動作對象例子搬進 `test_04_patient.py`,不跟著刪**。規格只要求搬夾具與接縫,但 `patient.py` 留著,這 109 條是它的行為回歸。接縫換成框列匯出的 `patient_mode`,期望值由腳本把葉名換成動作詞元(`破壊@フィールド` → `破壊`),斷言形狀不變;搬完全過,沒改任何期望值的判定。檔案因此長到 875 行。沒搬的 11 條是舊匯出專屬(葉號、樹、序列化),`test_05_export_frames` 已有對應的就不補;靈擺段的鍵由 `test_04_patient` 的 `section="pendulum"` 例子走到。`test_categories.py` 154 條全刪:都在測歸葉與舊樹。
- **`queries` 線改成依命中來由分層**。舊分層是「命中集合與舊歸葉」的差異,沒有舊歸葉就算不出來。新層:動作對象變動、取自來源、回指回填、中心詞、區域、詞元節點,配額 17/17/17/17/16/16 共 100。母體(卡數,一張卡歸第一個符合的層):164、774、2,135、2,546、1,924、273。舊的「尾綴」層沒有對應,它講的是舊子字串比對漏掉的卡。`PATIENT_CHANGED` 留著當一層。
- **`categories` 線**:每個具名查詢抽 5 個(含帶子的詞元節點,舊的只抽葉),沒命中的抽 50 個。批次依命中的第一個詞元節點分組。錯誤類型改成 誤收/漏收/述詞語意,成因改成 規則/目錄 或 框架抽取,與 `queries` 線用詞一致;舊輪 meta 自帶的類型不受影響。
- `test_07_catalog` 的對應表兩條刪掉,留一條守 237 個具名查詢。
- `test_copies_of_chain_tables_stay_equal` 不再比 `SUB_INDEX`:留下的分詞鏈沒有這條正則。另開 `test_sub_index_reads_the_index_the_chain_writes`,用 `export_common.owner` 組的 index 餵 `SUB_INDEX`,比抄一份正則更直接。
- `CODING_STANDARDS.md` 的全語料測試範本原指 `test_categories`,改指 `test_v4.TestCorpus`;地圖 Notes 的「相關程式」清單拿掉已刪的檔。

### 偏離

- 票面寫「票 09 記進地圖」;派工要求本票先寫進地圖,已寫。票 09 的「地圖 Decisions 補票 08 記下的刪除前 commit」只剩交件註記要補。
- 無其他偏離。`export_common.py` 留著;`splits_complement` 查過還有 `predicate.py` 在用,留著。
- 只在註解改掉舊程式:`catalog.py`、`catalog_hits.py`、`export_common.py`、`export_frames.py`、`negation.py`、`patient.py`、`places.py`、`frames.py`、`webindex.py`。
