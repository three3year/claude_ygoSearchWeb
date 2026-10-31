# 建置產物與工作樹

## 入版控的建置產物(程式寫出,不手改)

| 檔 | 重生指令 |
|---|---|
| `data/action_frames.json` | `python .scratch/effect-tokenize/run_chain.py`(或 frames.py → export_frames.py 兩步;框列匯出,ADR-0018,規格 3 的索引建置讀它) |
| `data/action_categories.json` | `python .scratch/effect-tokenize/run_chain.py`(或 frames.py → categories.py → export_categories.py 三步;過渡期照產,規格 3 切換後刪) |
| `.scratch/effect-tokenize/report.md` | `python .scratch/effect-tokenize/report.py` |
| `.scratch/frame-predicate-search/tools/results/*` | `python .scratch/frame-predicate-search/tools/compile_dry_run.py --heads v4` |
| `.scratch/effect-tokenize/baseline-digest.json` | `python .scratch/effect-tokenize/baseline_diff.py --freeze`(只在刻意改既有欄之後) |
| `.scratch/effect-tokenize/patient-digest.json`、`anaphora-digest.json`、`export-digest.json` | `python .scratch/effect-tokenize/downstream_baseline.py <patient|anaphora|export> --freeze`(只在確認差異是要的之後;見下「下游基準」) |

- 換行:這些檔寫 LF,`.gitattributes` 讓工作樹也是 LF;`git status` 顯示它們 M 時先 `git diff`,內容為空就是沒變。
- 合併:它們宣告 `merge=ours`,合併時取本分支版、合併完**重生**,不手解衝突。每個 clone 要註冊一次驅動:`git config merge.ours.driver true`。

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
