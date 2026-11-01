# 08: 刪舊鏈與舊工具

**What to build:** 分詞鏈少跑兩步,歸葉程式、舊匯出檔、舊樹檔和只為它們存在的工具都不在了,抽驗工具改讀目錄繼續能用。清單以 predicate-index 票 05 Comments「要刪的舊東西」的匯出與基準、分詞鏈兩段與七條出入為準,加上規格「刪除」段與「刪歸葉程式後,仍 import 它的舊工具怎麼辦?」的決定。

**Blocked by:** 07

**Status:** ready-for-agent

- [ ] 刪掉前先記下最後一個 commit,寫進 Comments,票 09 記進地圖
- [ ] `test_04_patient.py` 依賴的夾具與接縫先搬到留下的檔,再刪 `test_export.py`、`test_categories.py`
- [ ] `llm_check.py` 與 `test_10_llm_check.py` 的歸組與 `tree.md` 改讀目錄與 `frame_queries.json`,不再 import 歸葉程式;跑一次產出批次檔確認能用
- [ ] 刪 `categories.py`、`export_categories.py`、`category_tree.json`、`catalog-mapping.json`、`data/action_categories.json`、`export-digest.json`;`downstream_baseline.py` 的 `export` 尺與相關測試、`run_chain.STEPS` 兩步、`.gitignore` 條目跟著拿掉;`export_common.py` 留
- [ ] 刪 `compile_dry_run.py`、`project.py`、`evaluate.js`、`compare_dry_run.py`、`rewrite_tree.py` 與兩個舊工具的 `results` 目錄;本規格的 `measure_ui.js`、`old_nodes.js` 也刪,輸出留著
- [ ] `.gitattributes` 與建置產物表拿掉對應條目;`test_lint` 的舊模組規則與 `test_copies_of_chain_tables_stay_equal` 的比對對象依清單處理;留下的模組還提到舊程式的註解改掉
- [ ] 舊票、舊規格、`catalog.json` 與 `llm-check/summary.md` 裡提到的路徑不回頭改
- [ ] 全鏈重跑 exit 0;`data/action_frames.json` md5 不變(8e359d78f3a0a6e53d47e9f68e92e36b);`data/action_categories.json` 不再產生;剝鍵、回指、動作對象基準差異 0
- [ ] 全 repo 沒有 import 或讀取已刪檔案的程式(搜尋結果記進 Comments);effect-tokenize 全套與 script/* 全過
