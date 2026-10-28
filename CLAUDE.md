# claude_ygoSearchWeb

## Git

只 commit 到本地分支,**永遠不要 git push**(即使未來設定了遠端,也須使用者明確要求才能 push)。

## Agent skills

### Issue tracker

Issues live as local markdown files under `.scratch/<feature>/` in this repo. See `docs/agents/issue-tracker.md`.

### Triage labels

Default label vocabulary (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `GLOSSARY.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.`CONTEXT.md` 為舊名(v1.3.0 前的 skill),現僅轉址到 `GLOSSARY.md`。
