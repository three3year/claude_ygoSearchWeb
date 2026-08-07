# 01 — 一般卡抽取管線 + 建置薄殼

**What to build:** 對官方 Q&A 快取跑一個指令,就得到一份依 cid 排序的整合 JSON:每張一般卡含 cid、日文卡名、卡片文字、補足情報與更新日期;無補足情報的卡照收(缺該欄);內文 `<br>` 轉 `\n`、其餘標記剝除、HTML entity 解碼。同時列印統計報告雛形(收錄數、無補足數)。靈擺卡此階段僅出 card_info 部分。

**Blocked by:** None — can start immediately.

**Status:** done

- [x] 純函式管線:吃 (cid, HTML 字串) 序列,回傳 (entries, report),不碰網路與檔案系統
- [x] 一般卡:card_text、supplement、supplement_date、name_ja 正確抽出
- [x] 無補足情報的卡收錄且省略 supplement 欄位
- [x] 內文清洗:`<br>`→`\n`、去標記、entity 解碼、修剪空白
- [x] CLI 薄殼掃描快取目錄 → 寫出依 cid 升冪排序的單一 JSON
- [x] unittest 以合成 HTML 片段覆蓋上述行為
