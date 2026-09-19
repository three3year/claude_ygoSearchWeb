# 02 — 拆後端翻新工具

**What to build:** 程式碼庫不再含只為翻新流程服務的後端工具:反向檢查工具、網頁審核台、子批擬稿詞彙表機檢殼(薄殼)三者移除。卡文詞彙表系統其餘部分(核心模組、全庫掃描工具、測試、詞彙表文件)屬勘誤產生鏈,一行不動。

**Blocked by:** None — can start immediately。

**Status:** ready-for-human

- [x] 反向檢查工具、審核台、擬稿機檢殼三者已刪除
- [x] 卡文詞彙表核心模組、全庫掃描工具、其測試與詞彙表文件無任何變更
- [x] 全 repo 無殘留的程式碼層引用(過程目錄內的引用由票 03 隨目錄清除,不在本票範圍)
- [x] 既有測試套件全綠

## Comments

2026-09-19 執行完畢:刪除 `script/text_rewrite/`(check_reverse.py、build_review_page.py、render_check.js)與 `script/text_glossary/check_draft.py`;三者互相引用之外全 repo 無程式碼層引用(已 grep 驗證)。卡文詞彙表核心模組/全庫掃描/測試/詞彙表文件零變更(verify_texts.py 僅票01 授權的去參數)。測試全綠。
