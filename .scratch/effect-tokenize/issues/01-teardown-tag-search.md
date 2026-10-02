# 01 — 拆除票:分類表兩維搜尋下架+索引剔除

**What to build:** 搜尋介面撤出分類表兩維——動作維(21 動作類別鈕+分組、區域移動起點/終點、位置/對象方鈕)與觸發時機軸,連同對應命中 badge;`web/data.js` 前端索引不再寫入動作 tag 與觸發時機資料;VOCAB 不再輸出對應值域(鈕由 VOCAB 生成,ADR-0008 機制不變,值域不出鈕自然消失)。保留:效果類型(跨類型魔陷效果)軸、必發/選發軸(含怪獸側組合)。`data/tag_cards.json` 本體、規則層、遮蔽測試資產、tag seal 全部保留不動——只停前端出口。CONTEXT.md 受影響詞條同步改寫(效果標記表「網站進階查詢的核心依據」定位、效果 Tag、分類表、動作類別、槽位、觸發時機,註記 2026-10-01 搜尋撤出與重推導決策、指回 effect-tokenize spec)。相關測試(engine/render/hash/query、test_vocab、test_webindex)同步修正,主 seal 需全綠。

**Blocked by:** None — can start immediately.

**Status:** resolved

---

## 追記(2026-10-01 實作完成)

**建置期**:

- `script/web/vocab.py`:新增 `FRONTEND_WITHDRAWN`(動作類別 `tag`、觸發時機 `timing`、全部 21 類槽位值域),`export()` 整組跳過、tag 的 `slots` 宣告不再隨 VOCAB 出去。值域本身保留——`problems()` 自檢、`tag_code`、`tag_digest` 原樣,tag seal 與規則層照舊讀得到。
- `script/web/webindex.py`:`_entry` 不再寫 `tg` / `tm`;`timing_on_non_carrier` 承載檢查、`_tag_category_counts` / `_drop_untagged_tag_categories`(tag 開貼統計與按鈕退場)一併移除;census 只數前端值域。正典外 tag 的把關歸 tag seal,web 建置不重複設閘。

**前端**(`web/js/`、`web/style.css`):

- `engine.js`:tag 槽位解碼、tag 層 AND(`tagMeets` / `tagCatsAt`)、區域移動 `mvHit`、`timingAt` 與 runQuery 對應條件/marks 全拆。
- `query.js`:FIELDS 移除 tag / timing 兩軸,`tagExtraHtml`(起點/終點下拉+位置/對象方槽位鈕+說明文字)、`slotAxes`、`timingAvailable` / `syncTiming` 與 read/write/clear/axisCounts 的對應處理全拆。
- `hash.js`:`mvf` / `mvt` / `tgp` / `tgs` 與 `tag` / `timing` 參數編解碼移除;舊網址帶這些參數時走既有的「認不得的欄位名一律忽略該段」規則——安靜略過、不報錯、不留殘骸(engine.test.js 有專測)。
- `render.js`:`tagBadge` 與 tag / timing 的 badge 字面(MARK_ZH)移除。
- `style.css`:`.tag-mv-row` / `select.tag-mv` / `.tag-slot-row` / `.tag-scope-note` 專屬樣式區塊整段刪除。
- 保留不動:效果類型(跨類型魔陷效果)軸、必發/選發軸(含怪獸側四顆組合鈕)、其他卡片參數軸、`index.html` 零改動。

**測試**:

- `frontend_harness.js` 移除 `__slotAxes` / `__timingAvail` 驅動;`engine.test.js` 刪 TAG_CARDS 沙箱與 tag/時機/槽位全部測試、axes 清單更新、新增「舊網址帶已拆參數安靜忽略」測試;`render.test.js` 刪 tag badge 測試與 fixture;`test_vocab.py` 新增「已撤出值域不出 export、正典本身保留」測試(正典 tag 自檢測試照留——那是保留功能);`test_webindex.py` 的 TagAxisTest 改寫為拆除語意(索引無 `tg`/`tm`、VOCAB 無 tag 值域、正典外 tag 不再倒 web 建置、timing 檢查與 tag_census 退場)。

**索引重建**:`PYTHONIOENCODING=utf-8 python script/web/build_index.py`(讀本地檔,本就離線;決定性建置,diff 除 META 的 `built_at` 與 `vocab_digest` 外只少欄位)。`web/data.js` 8,500,809 → 7,724,303 bytes(−776,506,−9.1%;gzip 約 1.83 MB),14,258 → 14,234 行(少掉 tag/timing/槽位 24 行 VOCAB)。

**CONTEXT.md**:效果標記表(核心依據定位改寫)、效果 Tag、分類表、動作類別、槽位(搜尋語意敘述下架)、觸發時機六詞條各加 2026-10-01 狀態註記:搜尋介面已撤出、舊線停工、動作類別將以[[效果文分詞]]線重新推導(指向 `.scratch/effect-tokenize/spec.md`);詞條定義本體保留。「效果文分詞」詞條未動。

**測試結果**:

- 六組 Python 測試全綠:card_list 66、faq_info 43、tag_card 469、text_format 55、text_glossary 37、web 115(合計 785)。
- 前端測試全綠:`node --test script/web/engine.test.js script/web/render.test.js` 122 pass / 0 fail。
- 主 seal:`seal_report.py` 15/15 全數成立。
- tag seal:`tag_seal_report.py` 90/90 全數成立(讀 tag_cards.json,不經前端,如預期不受影響)。
