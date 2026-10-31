# 01: 基準凍結與驗收工具

**What to build:** 站主在後面每張票交件時都能一眼確認「結構化是加欄不是換值」:凍結修前的全語料框架檔當基準;一支比對工具把新鍵剝掉後逐框、逐鍵與基準比,差異要 0,寫成全語料測試(沒有基準檔時略過並印原因,沿用空葉移除票 02 的做法);新封閉類的值表模組骨架(中心詞類、修飾語類、數量類、方式類、施事者、否定形、轉欄記號、回填記號的新值)與「全語料出現表外值即建置失敗」的檢查(「其他」只允許在中心詞類與修飾語類);報告加「新欄填充率」一節的骨架,後面每張票各補自己那幾列。分詞鏈決定性重跑相同。

**Blocked by:** None (can start immediately)

**Status:** resolved

- [x] 修前全語料框架檔凍結成基準(不入版控),比對工具剝掉新鍵後逐框比對、差異 0;工具的新鍵清單是唯一要維護的東西
- [x] 全語料測試:剝鍵比對差異 0、封閉類沒有表外值;基準檔缺時略過並印原因
- [x] 封閉類值表模組:每個新封閉類一張表,值表就是值域;表外值的欄名與值列清單、建置失敗
- [x] 報告多「新欄填充率」一節(分位置:有值/推得/轉欄/取自子句/其他/空),此票只有骨架與空列
- [x] 既有全部測試照過;決定性重跑相同

## Comments

- 2026-11-01 實作(分支 wt/01-baseline):全部在 `.scratch/effect-tokenize/`。`closed_values.py`——十一張封閉表(HEAD_KINDS/MODIFIER_KINDS/QUANTITY_KINDS/MANNER_KINDS/AGENTS/AGENT_SOURCES/NEGATION_FORMS/TRANSFERS/REGION_BACKFILLS/PLAYERS/ZONES,ZONES 由 places.ZONE_TERMS 算出七值、PLACE_PLAYER 把 places 的 雙方 對到 お互い)、`violations(records)` 回 [(欄位路徑, 值, 框數)](路徑如 `agent`、`phrases.segments.head_kind`、`regions.player`;也檢查 phrases/regions 的欄名只在 object/topic/subject/goal 與 source/goal/place);`frames.py main()` 寫檔前呼叫,有表外值就逐筆印到 stderr、不寫 frames.json、exit 1。`baseline_diff.py`——NEW_KEYS 列齊筆記的十一個頂層新鍵、NEW_ANAPHORA_KEYS=(moving,);`strip`/`diff`/`underscore_keys` 與 CLI(`--baseline/--current/--limit`、環境變數 FRAMES_BASELINE;差異或底線鍵非 0 時 exit 1);紀錄依 (卡號, 段落, 句序) 對齊,框數不同記鍵 `frames`、紀錄缺少記鍵 `record`。`enrich.py`——`Context(surface, word, is_noun_like, move_actions, intransitive_moves, patient_coordinators, pol_neg)` namedtuple 由 `FrameExtractor._context()` 裝;`enrich(ctx, tokens, frames)` 對每個動作框架依序呼叫 `phrases.structure`/`regions.structure`/`agent.mark`/`manner.mark`/`negation.mark`(簽名都是 `(ctx, tokens, frame)`),再 `regions.backfill_from_anaphora(ctx, tokens, actions)` 一次拿整句的動作框架清單(票 09 要找回指目標),最後 pop 底線鍵;五個步驟模組只有 docstring 與空函式。registry:`enrich.FILL_RATE_ROWS`(名稱, frame → FILL_STATES 之一|None)與 `enrich.REPORT_SECTIONS`(標題, records → markdown 行)。
- 掛勾位置偏離規格字面(照共用筆記):enrich 在 `anaphora.resolve` 之後、是框架抽取的最後一步,不是插在主題延續/回填/推得之前——新欄讀的是既有欄的最終值,放最後一樣符合每條使用者故事。交件時併進檢驗摘要的偏離清單。另一個小偏離:MANNER_KINDS 保留「其他」(規格方式段自己列了 なしで/ままで 記 其他),所以「其他」在中心詞類、修飾語類、方式類三張表裡合法,施事者/否定形/數量類等表沒有它、出現即表外。
- 報告:`report.py` 加 `fill_rate_section`——「## 新欄填充率(frame-args-v4)」一張表,列是 新欄×位置(代價/效果/條件),欄是 有值/推得/轉欄/取自子句/其他/空,各票只往 `enrich.FILL_RATE_ROWS` 加列;此票空列(表裡一行佔位)。REPORT_SECTIONS 留給 其他類中心詞 top 100(票 02)/其他類修飾語 top 100(票 03)/回指回填 填/拒(票 09)。report.py 裡 enrich 在函式內才 import:constraints 載入時 import report,enrich 又 import constraints,模組層級會循環(第一次就踩到)。report.md 已重生並一起 commit。
- 顯示:`prepare_view.py` 的 `frame_row` 加 f[21] = `{k: fr[k] for k in NEW_KEYS if k in fr}`(空時 null);`viewer.html` 框架表加「第四版論元」欄、`v4Text(f[21])` 組合函式(此票回空)、`td.v4` 內的 `.inf`/`.bf` span 與 details 樣式;`llm_check.py` 加 `v4_cells(f)`(回空清單)接在 `argument_cells` 尾。`.scratch/effect-tokenize/.gitignore` 加 `baseline/`。
- 測試(`test_v4.py`,18 條):單元接縫 `closed_values.violations`、`baseline_diff.strip/diff/underscore_keys`(手寫小框架清單,含表外值計數與排序、約束框架不掃、ZONES 七值、新鍵不算差異、改值/增減鍵/框數/紀錄數都算差異);全語料 `TestCorpus`(剝鍵差異 0、沒有表外值、沒有底線鍵),基準檔或 frames.json 不在時 skipTest 並印原因。基準檔預設路徑 `.scratch/effect-tokenize/baseline/frames.json`(md5 2bcfb772edbdfa53f31885a3c103ce18)。
- 數字:全語料框架 59,314(動作 46,732、約束 12,582)不變;掛勾後 frames.json 與基準逐位元組相同(md5 相同),`baseline_diff.py` 差異 0、底線鍵 0;`frames.py` 單跑與 `run_chain.py` 全鏈兩次產出的 frames.json、frame_categories.json、card_categories.json md5 都與修前版一致(決定性)。`run_chain.py` 後 `data/action_categories.json` 的 blob hash 與 HEAD 相同(`git diff` 空、JSON 相等);`git status` 一度顯示 M 是 autocrlf 的換行符 stat 假象(匯出寫 LF、工作樹預期 CRLF),`git add` 同一 blob 後乾淨,沒有內容變動。測試:effect-tokenize 704 條(686+18)、node 172、script/ 五套 769 條全過。
- 未決:無。整合分支 frame-args-v4 在本票交件時沒有新 commit,不需 merge。
