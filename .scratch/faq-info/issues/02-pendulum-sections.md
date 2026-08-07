# 02 — 靈擺卡雙區塊支援

**What to build:** 靈擺卡的 pen_info 區塊被完整抽出:pen_effect、pen_supplement、pen_supplement_date 三欄,與怪獸效果的補足情報分開;非靈擺卡不出現這些欄位;報告加計靈擺卡數。

**Blocked by:** 01 — 一般卡抽取管線 + 建置薄殼。

**Status:** done

- [x] 靈擺卡三欄正確抽出,與 card_info 補足互不混淆
- [x] 只有 pen_info 而無 pen 補足的卡:pen_effect 有值、pen_supplement 省略
- [x] 非靈擺卡完全不含 pen_* 欄位
- [x] 報告含靈擺卡數
- [x] unittest 覆蓋上述行為
