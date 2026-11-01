# 框架述詞搜尋(frame-predicate-search)地圖

Label: wayfinder:map
Charted: 2026-10-31(/mattpocock-skills:wayfinder)

## Destination

四份規格都寫完並切好票,可以開始 implement:框架線片語與新欄 / 下游改讀與匯出 / 索引與述詞評估器 / 介面與網址,各自是 `.scratch/<子線 slug>/spec.md` 加 `issues/`,到時沒有待決定的事。implement 不在此圖上,照票逐張做。

## Notes

- 形狀已定,不重問:GLOSSARY.md 2026-10-31 定案段(動作類別第三版、框架述詞、具名查詢、論元片語、動作框架第四版論元、論元的方式與數量、動作對象為述詞欄位、軸例外)與 docs/adr/0018-search-reads-frame-predicates.md。各規格的裁定直接從那裡抄。
- 形狀底下的規則細節(施事者推導順序、片語切分與各封閉類完整值表、具名查詢來源檔形狀、條件位框架的述詞語意、句尾標籤在不互斥下顯示什麼、hash 轉義)**不開細節票**,寫規格時在 to-spec 裡順手問(2026-10-31 站主裁定)。
- 順序照資料流:規格 1 → 2 → 3 → 4,不先動搜尋端;介面原型等規格 3 寫完再做。
- 約束:純 Python 零依賴、同輸入逐位元組決定性、字面欄逐位元組不變是框架線驗收條件、每個新封閉類進值域正典、新欄各做一輪 LLM 抽驗(慣例:100 卡 4 批加複檢,存 `llm-check/`)、舊 act 網址不保證。
- 寫規格票的做法:`/mattpocock-skills:to-spec` 再 `/mattpocock-skills:to-tickets`;spec.md 是審核關卡 md,寫或改之前先用 `review-mirror` skill。
- 相關程式:`.scratch/effect-tokenize/`(frames.py、anaphora.py、patient.py、places.py、categories.py、export_categories.py、category_tree.json;是網站資料上游,不可隨手改)、`script/web/build_index.py`、`web/js/{engine,hash,query,acat,render}.js`。重跑:`python .scratch/effect-tokenize/run_chain.py` 再 `python script/web/build_index.py`;測試:`node --test script/web/`、effect-tokenize 的 unittest。
- 上午六項定案的 GLOSSARY diff 留在 session scratchpad `glossary-2026-10-31-six-directions.diff`,其中回指回填的規則併進規格 1。
- 只 commit 本地,永遠不要 git push;站主說 commit 才 commit。

## Decisions so far

<!-- 每張 resolved 票一行:名稱連到票,加一句答案的要旨 -->

- [索引體積與評估器速度實測](issues/01-index-size-and-evaluator-timing.md):編碼 C(定序元組+列舉小整數+中心詞對照表)對現在 data.js +946 KB raw / +184 KB gz(再加 5 個封閉類欄約 +337 KB gz,+17%);Node 逐卡逐框掃 1〜5 述詞 3〜4 ms、最差 10 ms;建議不拆檔、字面欄一律對照表、不需倒排索引。
- [具名查詢編譯試跑](issues/02-named-query-compile-dry-run.md):233 葉全部編得出來;效果位張數相同 105 葉、不同 31 葉(不再互斥 2,710 卡·葉、並收取消 13、非移動類 から 不當所在 1,187)、預設葉取消 97 葉改詞元節點;欄位不夠兩處給規格 1——極性類(耐性/限制)要一個否定形封閉類欄(只用極性+態會讓 受ける(耐性) 197 → 0、対象にする(限制) 144 → 267),非移動類的 から 要定進所在欄或編成「所在或來源」。
- [寫規格 1:框架線的論元片語與新欄](issues/04-spec-frame-line-phrases-and-fields.md):規格 `.scratch/frame-args-v4/spec.md`(ready-for-agent)與 11 張票;九項細節全裁(否定形封閉類欄、非移動類 から 與 で 接區域進結構化所在標轉欄、預設施事者只補代價/效果位他動帶對象框架、によって、此卡帶對象才是施事者、中心詞是最後一個名詞格、數量類加下限、LLM 一輪分七層);字面欄不動、下游不改,規格 2 在乾淨基準上改讀。 **2026-11-01 交件**:整合分支 `frame-args-v4`(票 01〜11 全部 resolved);動作框架 46,732 全部是新鍵、剝鍵後與修前凍結檔差異 0、匯出不變;填充率 片語 45,316/結構化區域 32,195/施事者 25,145(預設 21,100)/方式 3,807/否定形 3,088/取自來源 1,410/取自で 36/回指回填 3,475;LLM 抽驗 v4-round1 42 筆 → round2 8 筆;編譯試跑 49 片關鍵詞類葉 44 葉相同、5 葉少 10 張(全是舊式子字串命中);GLOSSARY 五處與 `.scratch/effect-tokenize/closed_values.py` 一致;鍵名與下游對照在 [frame-args-v4 票 11 Comments](../frame-args-v4/issues/11-handoff.md);六條未決在 `.scratch/effect-tokenize/llm-check/summary.md`「需要你決定的」(引用量、戦闘・効果で、全ての/任意の、施事者規則 (3)、段首 その、其他類中心詞加值)。

- [寫規格 2:下游改讀與匯出](issues/05-spec-downstream-and-export.md):規格 `.scratch/named-queries/spec.md`(ready-for-agent)與 11 張票;十二項細節全裁(目錄檔一次改寫成述詞字彙、不留算三位置、中心詞尾綴、片語結構化搬到回指之前並改讀、新匯出檔 `data/action_frames.json` 與舊檔並存到規格 3、格式版本號、開葉門檻退場、拆解頁總覽改具名查詢總覽/草案退場/檢驗摘要留、具名查詢命中一輪 LLM、相對/無留值域、詞元節點只含肯定與可能、接縫四個);純 Python 參考評估器算目錄張數與卡集合雜湊,規格 3 的 JS 評估器要對得上它。 **2026-11-01 交件**:整合分支 `named-queries`(票 01〜11 全部 resolved);目錄 `catalog.json` 236 個具名查詢(詞元節點 100、葉 136;改寫不改名)全部編得出、不留清單空(三個位置合計口徑);匯出檔 `data/action_frames.json`(版本 1;句 24,599 列、框列 46,732、目錄欄 260 列帶三個位置張數與卡集合雜湊);與試跑逐葉比對 +回指回填 3,076 卡·葉、+取自來源收回 1,769、−尾綴 6、其他 0(`.scratch/named-queries/tools/results/compare-v4.md`);動作對象改讀後判定值變 132 框(票 04,含 14 框變差)+27 框(票 03 回指連帶)、回指欄變 246 框,逐卡說明後重凍;LLM 抽驗 queries-round1 89 筆(全歸上游框架/動作對象規則/目錄內容)→ round2 0;剝鍵差異 0、舊匯出檔過渡期照產。給規格 3 的對照(匯出欄與值域、目錄張數與雜湊、夾具、要刪的舊東西)在 [named-queries 票 11 Comments](../named-queries/issues/11-handoff.md);三條未決在 `.scratch/effect-tokenize/llm-check/summary.md`「需要你決定的」(対象とする 進目錄、態空看主語、全部類比對順序與 以下の効果)。

## Not yet specified

- 索引編碼:數字已在「索引體積與評估器速度實測」的答案(建議 C 元組+對照表、不拆檔),規格 3 時定案。
- 拆解頁與檢驗摘要在新模型下的去留規格 2 已定(留;草案退場);網站端怎麼呈現具名查詢、相對/無、只在代價位或條件位命中的具名查詢顯示 0 張,待規格 4。
- 條件位框架進搜尋後,「觸發事件」這類高頻需求要不要預先放幾個具名查詢進目錄,待規格 4 或目錄上線後(規格 2 把目錄改成述詞字彙,加一列就是了)。

## Out of scope

- 上午定案的六項(任一組、目的玩家葉、置く・装備來源葉、回指回填、數量欄、條件類別):重做完成後重新檢視;其中回指回填的規則併進規格 1,其餘不在此圖。
- 約束框架線:不動。
- 換剖析器(Sudachi/GiNZA)或 LLM 逐卡抽框架凍結成來源檔:另一個量級,不綁在此線(ADR-0018 考慮過的選項)。
- 把分詞鏈搬出試點目錄 `.scratch/effect-tokenize/`:ADR-0017 的「類別定版後另開線」,仍另開線。
