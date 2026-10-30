# 03 — 交件

**What to build:** 站主回到搜尋頁、拆解頁、草案與檢驗摘要時,本線都已上線且一致:搜尋頁的動作類別軸吃到新的類別資料(搜 にする:LP 不再出現 92536468),三個鏡像照原網址顯示新葉與新計數,檢驗摘要每型差異附實例供站主抽樣。來源:spec 實作決策「產物與檢視」「文件」、Testing Decisions「全語料」。

**Blocked by:** 01、02

**Status:** ready-for-human

- [x] 跑分詞鏈(分詞 → 框架 → 類別 → 匯出):分詞與框架產物逐位元組不變,匯出的類別檔更新;再重建網站資料,建置通過。
- [x] 類別、草案、拆解頁資料決定性重跑兩次逐位元組相同;與修前框架類別檔逐框比對,差異只落在 01、02 的幾型,框數與檢驗摘要對得上。
- [x] 檢驗摘要加「關鍵詞只比中心詞」一節:每型差異(改前葉 → 改後葉)的框數與一兩個實例(卡號、欄位字面),已歸/未歸/不適用前後(修前 30,112/309/16,311);鏡像照原網址重新發布。
- [x] 草案(類別樹票 06 的 tree-draft):新增一個已決事項記本規格決定,受影響的節隨資料重跑;鏡像照原網址重新發布。
- [x] 拆解頁(類別總覽)照原網址重新發布。
- [x] GLOSSARY.md「動作類別」詞條的中心詞規則與程式核對一致。
- [x] script/ 與 .scratch 全套測試通過;真瀏覽器在搜尋頁選 にする:LP 確認 92536468 不在結果、選 にする→効果 確認它在。
- [x] 交件後本票標 ready-for-human,等站主依檢驗摘要抽樣。

交件(2026-10-30),等站主依檢驗摘要抽樣:

- 分詞鏈 run_chain.py 重跑:tokens.json、frames.json 逐位元組不變;data/action_categories.json 更新(類別樹葉 236);build_index.py 全部檢查通過,web/data.js 大小不變(8.00 MB、gzip 1.93 MB)。
- 決定性:categories → category_draft → prepare_view → export_categories → build_index 連跑兩次,除 web/data.js 的 META.built_at 建置時間戳外逐位元組相同(built_at 是設計上每次建置都變的欄位)。
- 與修前框架類別檔逐框比對 39 框,分型與實例見檢驗摘要「關鍵詞只比中心詞」一節;已歸 30,112/未歸 309/不適用 16,311 不變。
- 檢驗摘要:新增「關鍵詞只比中心詞」一節(分型表附實例、偏離、仍在的誤收);「動作類別已知未修」第 6 項標已修;「類別線跟進」一節的誤收例外逐框標已修/仍在;儀表板葉數 235 → 236。
- 草案:開頭說明補本線,新增已決事項「關鍵詞只比中心詞,照規格可以嗎?」。
- GLOSSARY「動作類別」中心詞一句與程式核對一致(實作偏離「以上/以下/より/除く」已在票 01 同步拿掉)。
- 真瀏覽器(node 經 CDP 驅動 headless Chrome,開本機 web/index.html;頁面例外 0):`code=92536468` + にする:LP → 沒有符合條件的卡片;+ にする→効果 → 1 張;+ にする:ダメージ → 1 張(是主卡②「自分が受ける効果ダメージは０になる」,本來就該中)。にする:LP 全部 6 張(65314286、45836982、6387204、58720904、72453068、74202664,都是把 LP 改成某值);にする→効果 全部 6 張,正是規格列的 6 張。
- 測試:script/ Python 762(card_list 66、faq_info 43、tag_card 469、text_format 55、web 129)、JS 154、.scratch/effect-tokenize 506 條全部通過。
- 發布(照原網址):拆解頁 Version 63 https://claude.ai/artifact/SSvzzZPLJcZsVLewfm3Htx (view_data 與全部分片都換);草案鏡像 Version 16 https://claude.ai/artifact/BgSzW7mb782GrbnGuetfHm ;檢驗摘要鏡像 Version 23 https://claude.ai/artifact/K9v5rfWiXgSdTgPgs83PpK ;規格鏡像 Version 2 https://claude.ai/artifact/3KCowumWqUyWU569moaGek 。
