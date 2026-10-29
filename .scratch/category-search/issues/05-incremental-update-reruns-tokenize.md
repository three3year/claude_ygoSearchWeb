# 05: 差值更新流程加重跑分詞鏈

**What to build:** 站主跑差值更新時,重建網站資料之前會先重跑分詞鏈(分詞 → 框架 → 類別 → 匯出),新卡與勘誤不會讓類別過時、也不會讓索引建置因雜湊對不上而擋住。來源:spec「資料更新」;ADR-0017。

**Blocked by:** 01

**Status:** resolved

- [x] 差值更新的腳本(或它呼叫的步驟)在重建網站資料前執行分詞鏈全鏈與類別匯出;任一步失敗就停下並說明是哪一步。
- [x] 差值更新的文件(README 的更新步驟)補上這一步與「不重跑時索引建置會因類別過時而失敗」的說明。
- [x] 既有的差值更新測試照舊通過;若流程是可測的純函式,補一條「步驟順序含分詞鏈」的例子。
- [x] 實跑一次(或以 --no-write/乾跑)確認順序與耗時,記在本票 Comments。

## Comments

2026-10-30 實作(/implement):

- 差值更新不是一支腳本,而是 README 列的一串指令(update_cards → 標記表判定與合併 → build_index);分詞鏈要在標記表更新**之後**才有意義,所以不掛進 update_cards.py,另立 `.scratch/effect-tokenize/run_chain.py`(分詞 → 框架 → 類別 → 匯出,任一步 exit 非 0 即停並說是哪一步),README「查卡網站」一節與 GLOSSARY「差值更新」補上順序與「不重跑時索引建置會因類別過時而失敗」。
- 步驟順序與失敗即停是純函式 `run_chain.run(runner)`,`test_run_chain.py` 兩條。
- 實跑一次(現行資料):總計 22 秒——分詞 5 秒、框架 13 秒、類別 3 秒、匯出 2 秒;重跑後 data/action_categories.json 與入版控的版本逐位元組相同。script/card_list 的差值更新測試照舊通過。
