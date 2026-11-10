# 01: 形狀前置

**What to build:** 把後面各票要共用的結構形狀一次改好,行為不變:對象線「到」的 `form` 從字串改成三槽物件 `{treat, display, order}`(既有「好きな順番で」搬到 `order`、「装備魔法カード扱いで」搬到 `treat`;`display` 帶 `text` 與 `alternatives: [{face, position}]`);性質變更的 `modified.attr` 改成清單、`form` 值域加「增」「減」、加選填 `limit`(`{cmp, text}`);段的 `duration` 允許出現在任何段並加選填 `range`(整回合/發動後);`amount` 加算式形狀 `{"kind": "算式", "text"}` 與選填 `cmp`。這票只改形狀與搬家,不收新句型。

- 規格:實作決策「段的格」「對象線與放置形式」;數據出處 F(放置形式字面次數)。
- 工廠函式與 GLOSSARY「結構鍵名」對照表同步改;「對象線」「性質變更」「期間」詞條補新欄。

**Blocked by:** None (can start immediately)

**Status:** resolved

- [x] 全庫重建,既有里程碑一全部測試(含標準卡斷言)全綠
- [x] 反向檢查全庫結果與重建前相同(通過/不通過段數與原因逐段相同;`form` 搬家後模板照新槽寫回)
- [x] 結構產物裡 `form` 只出現新形狀;舊字串形狀一處不留
- [x] 同一輸入建兩次逐位元組相同
- [x] GLOSSARY 結構鍵名表、對象線、性質變更、期間詞條更新

## Comments

實作者註記(2026-11-09,m2/01):

- 驗收怎麼量的:改前在 ffe6e5c 全庫建一次並跑反向檢查存底;改後重建兩次 `cmp` 逐位元組相同;用舊程式讀舊產物、新程式讀新產物各列出全部不通過項(卡、區塊、段、原因、detail、rendered、original),兩份 46,359 筆逐位元組相同,報告 md 亦相同(通過 17,220、不通過 45,591、未結構化 5)。
- 產物裡 `to.form` 14 處全是新形狀:`order` 好きな順番で 8、`treat` 装備魔法カード扱いで(、)6;字串形狀 0。性質變更段 21 段的 `modified.attr` 都是清單。
- 修飾段(「〜として扱う」,152 段)的 `modified` 是另一種形狀(`attr` 是 字段/卡名/大類…單值),這票沒動;GLOSSARY 性質變更詞條已註明。
- `order` 照現行字面位置寫在**區域前**(現有 8 處都是「好きな順番でデッキの一番下に」);spec 說 order 寫在述語前,目前沒有那種寫法被抽出,收「〜表示で」句型那票開 display 槽時一併處理。`display` 只有形狀,反向檢查遇到有值丟「放置形式無模板:display」。
- 新值域(`modified.form` 增/減、`limit`、`duration.range`、持續/該戰鬥、`amount` 算式與 `cmp`)只定形狀與常數(`structure_shape.MODIFY_ATTRS`、`MODIFY_FORMS`、`DURATION_KINDS`、`DURATION_RANGES`、`AMOUNT_FORMULA`、`PLACEMENT_TREAT_KINDS`、`FACES`、`BATTLE_POSITIONS`),沒有抽取;算式數量現有模板本來就丟「無模板」。
- 新測試在接縫二(`test_reverse_check.PlacementFormTest`、`ModifiedAttrTest`):三槽各寫回、treat 種類與字面對不上是無模板、attr 清單單項寫回、兩項無模板。
