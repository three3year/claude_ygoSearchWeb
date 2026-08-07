# 04 — 場外補足情報掃描 + 異常檔報告

**What to build:** 抽取執行時同步完成使用者要的「檢查」:凡「補足情報」字樣出現在 card_info/pen_info 兩區塊之外的檔案,report 記錄檔名、位置與前後文,只報告不抽取;整頁無 card_info 的檔不進 JSON、列入異常清單。

**Blocked by:** 01 — 一般卡抽取管線 + 建置薄殼。

**Status:** done

- [x] 場外「補足情報」被偵測並記錄(cid、位置、前後文),兩區塊內的不誤報
- [x] 無 card_info 的頁面不進 entries,cid 列入異常清單
- [x] CLI 報告輸出以上兩份清單
- [x] unittest 覆蓋:場外有補足、場內正常、無 card_info 三種頁面
