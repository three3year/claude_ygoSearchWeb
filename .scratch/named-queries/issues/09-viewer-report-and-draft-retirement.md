# 09: 拆解頁、報告與草案退場

**What to build:** 拆解頁的類別總覽分頁改成具名查詢總覽:每個具名查詢三個位置的框數/卡數、大類/中類是聯集、展開看框架;已歸/未歸/不適用儀表板拿掉;卡片拆解分頁每框列命中的具名查詢名與動作對象。類別樹草案停止重生(草案模組與資料塊不再跑,鏡像網址留作歷史)。報告加「具名查詢目錄」小節(節點數、三個位置的命中框數分佈、不留清單)。規則補的值照舊淡色加 title。發布併到票 11。

**Blocked by:** 08

**Status:** resolved

- [x] 拆解頁總覽讀命中中間產物,決定性重生 md5 相同
- [x] 卡片拆解每框列命中名與動作對象
- [x] 草案停止重生、重跑鏈與建置產物文件移除它;鏡像記錄註明歷史
- [x] 報告小節;既有全部測試照過

## Comments

- 2026-11-01 實作(分支 wt/09-viewer,基於 4f715ad=票 01〜08 全部)。全部在 `.scratch/effect-tokenize/`。**拆解頁總覽**(`prepare_view.py`):`load_categories`/`category_overview`/`write_category_shards` 整段換成 `load_queries()`(真目錄 `catalog.load()` + 命中中間產物 `catalog_hits.OUT`=frame_queries.json)、接縫 **`query_overview(目錄, 命中) → (總覽表, 分片)`**、`write_query_shards` → **`view_queries_<k>.js`**(`window.VIEW_QUERIES[k]`,4 片;舊 `view_cats_*.js` 改名,`.gitignore` 跟著改)。總覽表進 view_data 的 `frames.queries`:`names`/`paths`(查詢號 = 目錄序)、`nodes` 樹 `[名, 查詢號或 -1, [代價, 效果, 條件, 合計 框數], [同 卡數], 子]`(合計是三個位置的聯集;大類/中類是底下具名查詢的聯集,一框多命中只算一次;樹由 `Node.path` 推得——宣告的大類取代本家、中類取代詞元層,中類列在詞元節點之前、借來的節點排在本家的之後;詞元節點自己就是一列具名查詢,沒有預設葉)、節點數(`majors` 頂層 13、`middles` 12、`queries` 236、`lemma_nodes` 100)、`hits` 三個位置的命中框數分佈(命中 0/1/2/3+)、`shard_of`;分片 `{"q<查詢號>": [[卡號, 段落, 句序, 框架序, 位置, 子句原文]…]}`。`prepare_view.py` 不再 import 舊歸葉程式 `categories`。**卡片拆解每框**:f[14] 改成命中的具名查詢號清單(目錄序,空清單 = 沒命中;約束框架 null)、新欄 **f[22] 動作對象 [此卡/非此卡/null, 理由]**;卡層彙總 c[7] 改成 [效果位命中的具名查詢號, 代價位命中的具名查詢號]。動作對象的來源:`catalog_hits.py` 的紀錄**多帶 `patient`/`why`**(`frame_rows` 本來就算了判定,一框一列寫出;與匯出框列 `patient_mode` 同一個判定、不在拆解頁重算),frame_queries.json md5 b8fa62e0c1b188a4ae511c1c9afcc5c2 → c05e335fb26d1763162e189ef6554307(只多兩鍵;票 10 讀它不受影響)。
- **viewer.html**:分頁 `cats`「類別總覽」→ `queries`「具名查詢總覽」(`querySection`):儀表板 tile 具名查詢 236(詞元節點 100・葉 136)、頂層 13(中類 12)、動作框架 46,732、三個位置「命中任一」(代價 3,728/3,734、效果 26,384/26,687、條件 6,446/16,311);「一框命中幾個具名查詢」表;目錄樹每列 代價/效果/條件/合計 各 框數+張數(大類/中類標「(聯集)」),點具名查詢載分片列框架、點卡號跳拆解並釘住;已歸/未歸/不適用儀表板與未歸類清單整段拿掉。卡片拆解表頭「動作類別」→「具名查詢」+ 新欄「動作對象」(皆非淡色、理由在 title),沒命中顯示淡色「—」加 title;規則補的值(回填/推得/轉欄/取自子句)照舊淡色加 title 不動;兩段說明改寫。`<script>` 抽出 `node --check` 通過;用 http.server + Playwright 實開:總覽分頁無 JS 錯誤(只 favicon 404)、展開 召喚 載入 683 框清單、點卡號跳到卡片拆解,表頭 17 欄,特殊召喚 效果 4,028 張與匯出檔目錄欄一致。
- **報告**(`report.py`):新小節 `## 具名查詢目錄(named-queries)`——接縫 `queries_section(目錄, 命中紀錄) → 行`,`hit_distribution(命中紀錄)` 與 `HIT_BUCKETS=("0","1","2","3+")` 和拆解頁同一把尺、`is_lemma_node(具名查詢)`(述詞只有詞元、極性、否定形);frame_queries.json 不在時略過。全語料數字:頂層 13(大類 12、自成大類 破壊 1)、中類 12、具名查詢 236(詞元節點 100、葉 136);動作框架 46,732、合計 66,491 框·查詢、每框平均 1.42;命中數分佈 0:代價 6/效果 303/條件 9,865(合計 10,174)、1:1,447/9,461/5,081(15,989)、2:1,894/10,435/957(13,286)、3+:387/6,488/408(7,283);**不留:無**。report.md 重生入版控,兩次 md5 相同 b7ff27be9cb9526b7731fb40ff2a3fd5。(票 08 Comments 寫「13 大類 + 11 中類」,實際目錄欄的 24 個無述詞列是 12 大類 + 12 中類,破壊 是自成大類的具名查詢列;總數 260 不變。)
- **草案退場**:`category_draft.py` 刪除(沒有人 import、`run_chain.STEPS` 與 `docs/agents/build-products.md` 本來就沒有它,無可移除;`.gitignore` 的鏈註解改成 catalog_hits.py 在內);`.scratch/action-categories/tree-draft.md` 開頭加「歷史(2026-11-01 退場)」一段(不再重生、鏡像 https://claude.ai/artifact/BgSzW7mb782GrbnGuetfHm 留作歷史、`mirrors.json` 網址照留不重發);`.scratch/effect-tokenize/mirrors.json` 沒有草案網址,不動。`draft-data/` 的 .gitignore 留著(目錄可能還在本機)。
- **決定性**:`prepare_view.py` 跑兩次 17 個檔 md5 全同——view_data.js 00f9c0ee948c265bbb92a966ddf65c06、view_queries_0〜3 30d5481ebba40db7baa44631c5fe8d6f/c2960b0e8f724b9c59c1e8c142fedd98/e8ac6d3faeb4a9f8a480d96db39cbf2d/eb1c3456ccf8604ee06003035ef5bd87(各約 3.1〜3.4 MB)、view_frames_0〜11 不列(本票只改 f[14]/f[22]/c[7],md5 在工作樹 /tmp 紀錄);`catalog_hits.py` 兩次 md5 相同。
- **測試 `test_09_viewer.py` 10 條**(先紅——沒有函式——再綠):總覽 6 條(名與路徑目錄序、具名查詢三個位置框數/卡數、詞元節點自己有命中且宣告中類的葉不掛它、大類/中類聯集與子節點序、分片列與沒框的查詢沒分片、節點數與命中分佈)、每框列 2 條(f[14]/f[22]、約束框架 15 欄)、報告 2 條(節點數/分佈/不留清單、全命中時「無」)。全套:effect-tokenize **1032 條**(1022 + 10)、node 172、script/* 66/43/469/55/136 全過;`downstream_baseline.py export` digest ok(6725c2536bb40c0865538cb4c37273b1);`data/` 無差異(本票不碰匯出);test_lint 的位置字面規則對 report/prepare_view 仍過(用 `constraints.POSITIONS`)。
- **假設 / 偏離**:(1)動作對象寫進命中中間產物而不是拆解頁重算——「一份判定」比省兩個鍵重要;(2)「詞元節點」的口徑依述詞(只有詞元/極性/否定形)而不是「帶子」(帶子的只有 35,真目錄述詞口徑 100 與票 07 的 100 對上;極性類節點 破壊(耐性) 也算詞元節點);(3)總覽的大類/中類列不給框架清單(聯集動輒數千框,展開看子節點);(4)規格「大類/中類是聯集」照做,「借來的節點排在本家之後」沿用舊總覽的慣例。
- **給票 11 的接點(重發拆解頁)**:發布 `viewer.html` 照原網址 https://claude.ai/artifact/SSvzzZPLJcZsVLewfm3Htx,`files` 要帶 `view_data.js`、`view_frames_0〜11.js`、**`view_queries_0〜3.js`(新名)**,並把舊的 `view_cats_0〜3.js` 以 null 移除;發布前在整合分支重跑 `catalog_hits.py → prepare_view.py`(票 10 若改目錄/評估器,命中會變)。檢驗摘要的「具名查詢目錄」一節可直接抄 report.md 同名小節的數字。
- 未決:無。
