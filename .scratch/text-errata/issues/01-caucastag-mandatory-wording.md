# 01 侵入魔 巨角「可以」誤譯勘誤 + 顯示原文切換鈕

Status: resolved

依 `../spec.md` 全部七條決定一次實作:

- [x] `data/text_errata.json`:第一筆勘誤(84488827,刪「可以」)
- [x] `cardlist.build_card_list` 套用勘誤,失配即建置失敗;CLI 接線
- [x] 同步腳本更新拆句表/標記表的 `text_zh` 與雜湊(判定欄位不動)
- [x] `webindex` 對被勘誤的卡產出原文欄位 `og`(逆向套用驗證)
- [x] 前端:密碼右邊「顯示原文」鈕,逐卡切換純文字原文
- [x] ADR-0011、CONTEXT.md 詞條
- [x] 重建 cards.json / clause_splits.json / tag_cards.json / web/data.js

## Comments

2026-08-17 完成。驗證:勘誤套用 1 筆、差值報告只有 84488827 desc;
拆句表雜湊重算、標記表雜湊不變(判定基礎是日文);build_tag_cards 重跑
零退回、輸出與同步結果逐位元一致;build_index 全檢查通過,data.js 該卡
`tx` 已修正、`og` 帶原文。四套 Python 測試 + engine.test.js(93)全過。
