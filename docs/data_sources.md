# 資料來源索引

要查資料的形狀或格式坑時,照這張表找到 source of truth;這裡只記沒有任何檔案寫的事。

| 要查的事 | 看哪裡 |
|---|---|
| `cards.json` 每卡的鍵、哪些欄位只在怪獸填 | README「cards.json 欄位」;`script/card_list/cardlist.py` 的 `_make_card`(cdb 一列 → 一卡;`level` 低 8 位是等級/階級/連結數,高位是靈擺刻度) |
| `setcode` 64 位怎麼拆、怎麼比對 | `script/action_structure/archetype_table.py` 的 `split_setcode`、`setcode_matches`(照 ygopro-core `check_setcode`) |
| `faq_info.json` 的鍵(`card_text`、`pen_effect`、`supplement`…)怎麼抽 | `script/faq_info/faqinfo.py` 的 `TEXT_FIELDS`、`DATE_FIELD` |
| 卡片總表與官方 DB 文本怎麼對齊、沒有官方日文的卡怎麼處理 | `script/action_structure/card_structure.py` 的 `build_structures`(`faq.password == cards.id`);張數見 `.scratch/action-structure/spec.md`「數據出處」 |
| 官方文本的 ①②③ 不靠換行切、素材行與召喚條件句長相 | `script/action_structure/block_split.py` 模組 docstring |
| 全半形折疊、NFKC 不能用(會把 ① 折成 1) | `archetype_table.fold_width`;`reverse_check.normalise` |
| 上游 `strings.conf` 的 URL、`!setname` 格式、「漢字(読み)」兩種寫法 | README「動作搜尋的卡片結構」的 `build_archetypes.py --fetch`;`archetype_table.parse_setnames`、`name_variants` |
| 共識集(拆句表、cdb ①、英文三方一致)的邊界從哪取 | `script/action_structure/block_boundary_report.py` 模組 docstring;`.scratch/action-structure/stats/boundary.py` |
| 拆句表與邊界補丁的雜湊、失效規則 | `script/tag_card/tagcard.py` 的 `split_hash`;`block_split.boundary_patch_hash`(ADR-0003) |

沒有檔案寫的事:

- `name_ja` 兩份不同:`cards.json` 來自 ja-JP.cdb,英數全形;`faq_info.json` 來自官方 DB,英數半形。2026-11-07 逐字不同 1,729 張,比對前兩邊都走 `fold_width`。
- `core.autocrlf=true` 而 `.gitattributes` 只管 `*.json` 與 vendored:非 `.json` 的產物 checkout 後是 CRLF,建置寫 LF。拿工作樹檔與建置輸出逐位元組比之前先重跑一次;`git diff` 正規化後不受影響。
