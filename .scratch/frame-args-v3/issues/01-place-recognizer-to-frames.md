# 01 — 區域辨識下移到框架線

**What to build:** 「一段字面是不是區域、是哪個區域、帶哪個玩家」的辨識只有一份,放在框架線,類別線改用它。這是前置重構:框架與類別的輸出逐位元組不變,之後的票(受事者區域切分)才能在框架線裡判斷片語開頭是不是區域。

**Blocked by:** None — can start immediately

**Status:** resolved

- [x] 區域辨識(地點字面 → 玩家+區域清單,含複合字面、限定語剝除、狀態寫法)搬到框架線,類別線改用同一份,不留兩份
- [x] 類別線既有測試與框架線既有測試全數通過,沒有改任何預期值
- [x] 全語料重跑:frames.json、frame_categories.json、card_categories.json 與修前逐位元組相同

## Comments

- 2026-10-17 實作:區域辨識(玩家前綴、區域詞表、複合字面分隔、括號/牌組頂底/描述尾巴、除外されている、限定語剝除,與 `parse_place`)整段搬到框架線的新模組 `effect-tokenize/places.py`;`categories.py` 改 `from places import parse_place`,原本那份刪掉,不留兩份(`ZONE_LABEL` 是葉名用的日文區域名,留在類別線)。test_frames、test_categories 等全套 250 條照舊通過、沒改預期值;全語料重跑 frames.json、frame_categories.json、card_categories.json 與修前逐位元組相同。
