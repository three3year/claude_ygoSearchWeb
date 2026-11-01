# claude_ygoSearchWeb

## Git

只 commit 到本地分支,**永遠不要 git push**(即使未來設定了遠端,也須使用者明確要求才能 push)。

工作樹的建置輸入(gitignore 的 `data/sources/`、tokens.json、基準檔)用 `python script/dev/worktree_bootstrap.py <工作樹路徑> --build` 複製進去;入版控的建置產物怎麼重生、怎麼合併見 `docs/agents/build-products.md`。

審查程式用 `CODING_STANDARDS.md`(判斷性規則;機械規則在 `.scratch/effect-tokenize/test_lint.py`)。

## Agent skills

### Issue tracker

Issues live as local markdown files under `.scratch/<feature>/` in this repo. See `docs/agents/issue-tracker.md`.

### Triage labels

Default label vocabulary (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### 派子代理的模型

實作票、審查、合併各用哪個 `model`,見 `docs/agents/subagent-models.md`。

### Domain docs

Single-context: one `GLOSSARY.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.`CONTEXT.md` 為舊名(v1.3.0 前的 skill),現僅轉址到 `GLOSSARY.md`。
