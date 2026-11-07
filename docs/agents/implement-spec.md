# implement-spec 在本 repo 的慣例

主會話跑 `/mattpocock-skills:implement-spec` 時照這份做;模型選法另見 `subagent-models.md`。

## 工作樹

- 每張票一個工作樹 `.worktrees/as-NN`、分支 `as/NN`,從整合分支開。
- `data/sources/`(faq_info.json、三個 cdb)被 gitignore:開完工作樹先從主工作樹 `cp` 過去。專案 hook 擋建連結,只能複製。

## 建置產物

- 票分支只 commit 程式、測試、票檔、GLOSSARY、README;重建後的產物(`data/action_structure.json` 等一卡一行的大檔)與全庫報告**不 commit**。
- 合進整合分支時由主會話重建一次、確認兩次逐位元組相同,再 commit 產物與報告。

依據:2026-11-07 action-structure 12 張票各 commit 一份 30MB 產物,`.git` 鬆散物件 522MB。
