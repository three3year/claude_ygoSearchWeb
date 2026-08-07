# 01 — 全量建置:繁中卡片總表最小路徑

**What to build:** 執行一個建置指令,輸入本地的 `cards.cdb`,產出繁中欄位齊全的 `cards.json` 卡片總表。總表遵守收錄規則(只收 8 位數卡片密碼、排除衍生物)、同名異圖卡合併為主卡一筆(異圖密碼進 `alt_ids`),輸出鍵序與排序穩定,並印出建置報告(收錄數、排除數與原因分類、alias 例外清單)。核心為「來源 cdb → 總表結構」的純函式,下載與檔案讀寫在薄殼中。

**Blocked by:** None — can start immediately

**Status:** ready-for-agent

- [ ] 對真實 `cards.cdb` 執行後產出 `cards.json`,欄位含 id、alt_ids、name_zh、desc、type、atk、def、level、race、attribute、scale、link_marker、setcode、ot(name_ja/name_en 先為空字串)
- [ ] 9 位數暫時編號的卡不會出現在總表(以 fixture 驗證)
- [ ] `type` 含 `0x4000` 位元的衍生物不會出現在總表(以 fixture 驗證;不得誤用 `0x4000000`)
- [ ] 同名 alias 條目合併進主卡且 `alt_ids` 正確;alias 指向不同卡名的例外不合併並列入報告(以 fixture 驗證)
- [ ] 等級/靈擺刻度/Link 值自 cdb 複合 level 欄位正確拆出(以 fixture 驗證)
- [ ] 同輸入執行兩次,輸出逐位元組相同
- [ ] 測試不碰網路,fixture cdb 於測試內以 sqlite3 程式化建立
