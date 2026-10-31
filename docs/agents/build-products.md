# 建置產物與工作樹

## 入版控的建置產物(程式寫出,不手改)

| 檔 | 重生指令 |
|---|---|
| `data/action_categories.json` | `python .scratch/effect-tokenize/run_chain.py`(或 frames.py → categories.py → export_categories.py 三步) |
| `.scratch/effect-tokenize/report.md` | `python .scratch/effect-tokenize/report.py` |
| `.scratch/frame-predicate-search/tools/results/*` | `python .scratch/frame-predicate-search/tools/compile_dry_run.py --heads v4` |
| `.scratch/effect-tokenize/baseline-digest.json` | `python .scratch/effect-tokenize/baseline_diff.py --freeze`(只在刻意改既有欄之後) |

- 換行:這些檔寫 LF,`.gitattributes` 讓工作樹也是 LF;`git status` 顯示它們 M 時先 `git diff`,內容為空就是沒變。
- 合併:它們宣告 `merge=ours`,合併時取本分支版、合併完**重生**,不手解衝突。每個 clone 要註冊一次驅動:`git config merge.ours.driver true`。

## 不入版控的建置輸入

`data/sources/`(下載來源)、`.scratch/effect-tokenize/tokens.json`、`.scratch/effect-tokenize/baseline/`。工作樹要用時複製進去:

    python script/dev/worktree_bootstrap.py <工作樹路徑> --build

複製,永遠不建 junction/symlink(`.claude/hooks/guard_links.py` 會擋;原因見該檔)。

## 字面欄不變的守門

`test_v4.TestCorpus` 把 frames.json 剝掉第四版論元的新鍵後取 md5,和 `baseline-digest.json` 記的比;語料(tokens.json)變了就略過並印原因。刻意改既有欄(新一版論元)時重新凍結:先確認差異是要的,再 `baseline_diff.py --freeze`。
