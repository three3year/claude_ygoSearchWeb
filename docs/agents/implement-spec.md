# implement-spec 在本 repo 的慣例

主會話跑 `/mattpocock-skills:implement-spec` 時照這份做;模型選法另見 `subagent-models.md`。

## 工作樹

- 每張票一個工作樹 `.worktrees/as-NN`、分支 `as/NN`,從整合分支開。
- `data/sources/`(faq_info.json、三個 cdb)被 gitignore:開完工作樹先從主工作樹 `cp` 過去。專案 hook 擋建連結,只能複製。

## 建置產物

- 票分支只 commit 程式、測試、票檔、GLOSSARY、README;重建後的產物(`data/action_structure.json` 等一卡一行的大檔)與全庫報告**不 commit**。
- 合進整合分支時由主會話重建一次、確認兩次逐位元組相同,再 commit 產物與報告。

依據:2026-11-07 action-structure 12 張票各 commit 一份 30MB 產物,`.git` 鬆散物件 522MB。

## 收尾:清 scratchpad

最後一動:產物與報告 commit 進整合分支後,主會話刪掉 scratchpad(系統提示的 Scratchpad directory)裡超過 10 MB 的檔。子代理共用這個 scratchpad,它們留的產物快照也在這裡。

```sh
find <scratchpad> -type f -size +10M -delete
find <scratchpad> -type f -size +10M    # 列出為空才算完成
```

腳本、審查意見、報告等小檔留著,resume 時還用得到。

依據:2026-11 action-structure m2、m3 與 action-search-web 的 implement-spec session 在 scratchpad 留下約 20 GB 產物快照。
