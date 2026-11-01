# 建置產物與工作樹

## 入版控的建置產物(程式寫出,不手改)

| 檔 | 重生指令 |
|---|---|
| `data/action_frames.json` | `python .scratch/effect-tokenize/run_chain.py`(或 frames.py → catalog_hits.py → export_frames.py 三步;框列匯出與具名查詢目錄欄,ADR-0018,索引建置 `--frame-export` 讀它;catalog_hits.py 另寫 gitignore 的 `frame_queries.json`——每框命中的具名查詢,拆解頁與 LLM 抽驗讀) |
| `web/data.js` | `python script/web/build_index.py`(在 `run_chain.py` 之後跑;讀標記表、卡片總表、兩份匯出檔。既有檔除 META 的 `built_at` 外內容相同就不動檔,所以同輸入重跑逐位元組相同;內容有變才取時鐘寫新時間) |
| `script/web/predicate-fixture-encoded.json` | `python script/web/encode_fixture.py`(參考評估器夾具 `predicate-fixture.json` 的編碼形狀,用建置的同一支編碼函式,值域讀 `data/action_frames.json`;node 測試 `predicate.test.js` 讀它。夾具、編碼或值域改了沒重生,`test_webindex.EncodedFixtureTest` 會失敗) |
| `.scratch/named-queries/tools/results/compare-v4.md` | `python .scratch/named-queries/tools/compare_dry_run.py`(目錄張數對照編譯試跑,逐葉歸因;要先有 frames.json 與 data/action_frames.json) |
| `data/action_categories.json` | `python .scratch/effect-tokenize/run_chain.py`(或 frames.py → categories.py → export_categories.py 三步;過渡期照產,規格 4 切換後刪) |
| `.scratch/effect-tokenize/report.md` | `python .scratch/effect-tokenize/report.py` |
| `.scratch/frame-predicate-search/tools/results/*` | `python .scratch/frame-predicate-search/tools/compile_dry_run.py --heads v4` |
| `.scratch/effect-tokenize/baseline-digest.json` | `python .scratch/effect-tokenize/baseline_diff.py --freeze`(只在刻意改既有欄之後) |
| `.scratch/effect-tokenize/patient-digest.json`、`anaphora-digest.json`、`export-digest.json` | `python .scratch/effect-tokenize/downstream_baseline.py <patient|anaphora|export> --freeze`(只在確認差異是要的之後;見下「下游基準」) |

- `run_chain.py` 的順序:分詞 → 框架 → 目錄(`catalog_hits.py`)→ 框列匯出 → 類別 → 類別匯出,任一步失敗停下。具名查詢目錄 `.scratch/effect-tokenize/catalog.json` 與對應表 `catalog-mapping.json` 是手改的來源檔(入版控),不是產物;`category_tree.json` 凍結、只給過渡期的 類別 → 類別匯出 讀,規格 4 一起刪。
- 換行:這些檔寫 LF,`.gitattributes` 讓工作樹也是 LF;`git status` 顯示它們 M 時先 `git diff`,內容為空就是沒變。例外:`web/data.js` 不在 `.gitattributes`,工作樹依 `core.autocrlf` 走。
- 合併:它們宣告 `merge=ours`,合併時取本分支版、合併完**重生**,不手解衝突。每個 clone 要註冊一次驅動:`git config merge.ours.driver true`。例外:`web/data.js` 沒宣告 `merge=ours`,有衝突時同樣取一邊、合併完重生。

## 不入版控的建置輸入

`data/sources/`(下載來源)、`.scratch/effect-tokenize/tokens.json`、`.scratch/effect-tokenize/baseline/`(剝鍵基準 `frames.json`、下游基準 `patient.json`/`anaphora.json`)。工作樹要用時複製進去:

    python script/dev/worktree_bootstrap.py <工作樹路徑> --build

複製,永遠不建 junction/symlink(`.claude/hooks/guard_links.py` 會擋;原因見該檔)。

## 字面欄不變的守門

`test_v4.TestCorpus` 把 frames.json 剝掉第四版論元的新鍵後取 md5,和 `baseline-digest.json` 記的比;語料(tokens.json)變了就略過並印原因。刻意改既有欄(新一版論元)時重新凍結:先確認差異是要的,再 `baseline_diff.py --freeze`。

## 下游基準(named-queries 票 01)

動作對象與回指改讀論元片語之前,先把現值凍結、改讀後逐框比對(`downstream_baseline.py`,三把尺):

| 尺 | 凍結的值 | 基準檔(gitignore) | digest(入版控) |
|---|---|---|---|
| `patient` | 每個動作框架的動作對象 (判定值, 理由) | `baseline/patient.json` | `patient-digest.json`(tokens、cards、值的 md5) |
| `anaphora` | 每個動作框架的整個回指欄(含 moving) | `baseline/anaphora.json` | `anaphora-digest.json`(tokens、值的 md5) |
| `export` | `data/action_categories.json` 整檔(過渡期不變) | 無 | `export-digest.json`(tokens、cards、檔的 md5) |

- 比對:`python .scratch/effect-tokenize/downstream_baseline.py <尺>`——先印 digest 守門,有基準檔再逐框列差異
  (卡片密碼、段落、句序、框序、子句字面、前後值);`test_downstream_baseline.TestCorpus` 跑同一件事,缺輸入時略過並印原因。
- 重新凍結:差異逐卡確認「改讀後更對」之後 `--freeze`;語料(tokens.json)或卡面(cards.json)變了 digest 守門會略過並要求重新凍結。
  動作對象的理由碼改名不必重凍,填 `downstream_baseline.WHY_ALIASES`(舊 → 新)。
- 基準檔在主 repo 凍結一次,工作樹由 `worktree_bootstrap.py` 複製;沒有基準檔時只剩 digest 守門。
