# 03 — cid→卡片密碼對接

**What to build:** 整合 JSON 每筆多出 password 欄:由快取目錄中 ygoprodeck 資料檔的 konami_id 建 cid→卡片密碼對應表;對不到的 cid 保留 null 並列入報告清單。完成後可直接以卡片密碼 join 卡片總表。

**Blocked by:** 01 — 一般卡抽取管線 + 建置薄殼。

**Status:** done

- [x] 管線接受 cid→密碼對應表參數,entries 補 password 欄
- [x] 對不到密碼者 password 為 null,且 cid 列入 report 清單
- [x] CLI 薄殼從 ygoprodeck 資料檔建表(konami_id ↔ id)
- [x] unittest 覆蓋對得到/對不到兩種情況
