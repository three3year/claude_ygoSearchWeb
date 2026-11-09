# 01: 形狀前置

**What to build:** 把後面各票要共用的結構形狀一次改好,行為不變:對象線「到」的 `form` 從字串改成三槽物件 `{treat, display, order}`(既有「好きな順番で」搬到 `order`、「装備魔法カード扱いで」搬到 `treat`;`display` 帶 `text` 與 `alternatives: [{face, position}]`);性質變更的 `modified.attr` 改成清單、`form` 值域加「增」「減」、加選填 `limit`(`{cmp, text}`);段的 `duration` 允許出現在任何段並加選填 `range`(整回合/發動後);`amount` 加算式形狀 `{"kind": "算式", "text"}` 與選填 `cmp`。這票只改形狀與搬家,不收新句型。

- 規格:實作決策「段的格」「對象線與放置形式」;數據出處 F(放置形式字面次數)。
- 工廠函式與 GLOSSARY「結構鍵名」對照表同步改;「對象線」「性質變更」「期間」詞條補新欄。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] 全庫重建,既有里程碑一全部測試(含標準卡斷言)全綠
- [ ] 反向檢查全庫結果與重建前相同(通過/不通過段數與原因逐段相同;`form` 搬家後模板照新槽寫回)
- [ ] 結構產物裡 `form` 只出現新形狀;舊字串形狀一處不留
- [ ] 同一輸入建兩次逐位元組相同
- [ ] GLOSSARY 結構鍵名表、對象線、性質變更、期間詞條更新
