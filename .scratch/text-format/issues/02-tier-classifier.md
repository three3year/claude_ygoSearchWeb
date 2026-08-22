# 02 — 三級分類器與測試

**What to build:** 一個純函式分類器:給一張卡的效果文段落與 OCG 首發日,回答它屬於哪一級——舊文本(無①段)、官方已改寫(有①且 9 期界日 2014-03-21 前首發)、新格式新卡(有①且界日含以後首發)、日期不明(有①但查無日期)。分段沿用 tagcard 管線既有的分段邏輯(同一把尺,不重造),段為單位:排除純通常怪獸與風味文段,靈擺卡各段獨立判級。

**Blocked by:** 01 — ocg_date 發售日來源引入。

**Status:** resolved

- [x] 分類器是純函式,不做 IO;餵合成卡片記錄即可測
- [x] 邊界測試齊全:界日前一日/當日/後一日、無日期、有①但帶無編號段的靈擺卡(段分級不同)、純通常怪獸排除、只剩風味文的靈擺通常怪獸
- [x] 對真實資料的迴歸檢查:判為舊文本的段數 == tagcard 報告的 pending_split(3,805,同一把尺)
- [x] 測試比照既有合成記錄測試的慣例(prior art:tag_card 的勘誤同步測試)

## Comments

2026-08-22 實作完成:

- 分類器:`script/text_format/classify.py` 純函式 `classify_card(card,
  ocg_date)` → 各段 `{"section", "tier"}`。分段整套復用 tagcard 同一把尺
  (`FOOTNOTE_RE` 剝別名註記 → `_zh_sections` 分段丟風味文 → `_segments`
  認①),純通常怪獸以 type 位元整張排除;有①段依 ISO 日期字串與界日
  `ERA9_START = "2014-03-21"` 比大小分級,無①段一律舊文本(日期不參與)。
- 測試:`test_classify.py` 合成記錄測邊界五族;同一把尺迴歸對真實
  `data/cards.json` 跑 `build_tag_cards(cards, [], splits=None)`(不套拆句
  表,pending_split 才是「無編號整團」的全集)比對相等,並釘住基準 3,805。
- 全套測試綠(card_list/faq_info/tag_card/text_format/web + node)。
- README 目錄表補列 classify.py。
