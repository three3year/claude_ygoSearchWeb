# 04 sync_errata_texts 重跑對「to 內含 from」的勘誤二次追加

Status: ready-for-agent

## 問題

`script/tag_card/sync_errata_texts.py` 的冪等假設是「已同步的紀錄找不到
原文子字串就跳過」(檔頭 docstring)。但補寫型勘誤的 `to` 內含 `from`
(如 text-errata#02:「那隻怪獸變成表側攻擊表示。」→ 同句+「此效果在
對手回合也能發動。」),同步後的文字**仍含** `from`,重跑就再 replace
一次,句尾句子重複追加。

2026-08-24 實測(text-errata#03 進站時全表重跑):`data/tag_cards.json`
的 94997874 兩行效果句被二次追加「此效果在對手回合也能發動。」
(當場以 git 還原、改用只含新勘誤的 `--errata` 檔定向同步繞過;
現行資料無殘留)。拆句表未中招是因為該卡拆句紀錄的雜湊防線先擋下,
非機制保證。

## 修法方向(擇一,實作時定)

- 同步前先查 `to` 是否已存在於該句(`to != from` 且 `to in text` 即視為
  已同步跳過)——`to` 內含 `from` 的補寫型勘誤即冪等。
  注意 `to` 是 `from` 子字串的刪字型勘誤(#01、#03)本就靠
  「找不到 from 即跳過」冪等,兩型互補。
- 或:同步時以 `cards.json` 勘誤後卡文為基準比對,已一致即跳過。

## 驗收

- `python script/tag_card/sync_errata_texts.py` 對現行四筆+任意新勘誤
  重跑 N 次,三表逐位元組不變。
- `test_sync_errata.py` 補一條「to 內含 from 重跑不重複追加」的迴歸測試。
