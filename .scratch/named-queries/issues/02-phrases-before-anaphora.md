# 02: 片語結構化搬到回指之前

**What to build:** 框架抽取拆成兩段:既有步驟(主題延續、回填、列舉、推得、正規化)→ 片語結構化(段/中心詞/中心詞類/修飾語/數量/玩家/區域/指示詞)→ 回指解析 → 結構化區域、施事者、方式、否定形、回指回填。片語只讀既有欄與切區域前的字面,不讀回指,所以搬了之後片語欄與所有既有鍵逐位元組不變;回指還沒改讀(票 03),本票只重排。拆解頁、批次檔、報告的讀法不變。

**Blocked by:** 01

**Status:** resolved

- [x] 片語結構化在回指之前執行,其餘新欄仍在回指之後
- [x] 剝鍵基準差異 0、回指欄比對差異 0、底線鍵 0、決定性重跑 md5 相同
- [x] 舊匯出檔不變;既有全部測試照過
- [x] 處理順序寫進框架抽取與後處理模組的檔頭 docstring

## Comments

- 2026-11-01 實作(分支 wt/02-phrases-order,基於 8eb863d):只重排,判定邏輯一行沒動(patient.py/anaphora.py 未碰)。`frames.frames_of_tokens` 的尾段改成三步:`enrich.before_anaphora(ctx, tokens, frames)`(片語結構化)→ `anaphora.resolve(...)` → `enrich.after_anaphora(ctx, tokens, frames)`(regions → agent → manner → negation → 回指回填,結尾 pop 底線鍵);ctx 只建一次。**自宣告怎麼維持**:`enrich.STEPS` 仍是一張表(順序未變),哪些步驟在回指前由模組自己宣告——`phrases.py` 頂層 `BEFORE_ANAPHORA = True`,沒宣告的在回指後;enrich 用 `_runs_before_anaphora(module)` 把 STEPS 篩成兩段,沒有手寫插入。`declared()`/`FILL_RATE_ROWS`/`REPORT_SECTIONS`/`batch_cells` 照舊依 STEPS 收,report/llm_check/viewer 不動。新 lint `test_lint.test_before_anaphora_steps_lead_the_list`:宣告 BEFORE_ANAPHORA 的模組要排在 STEPS 前段(STEPS 的順序才仍是執行順序;把 phrases 移到 regions 後面試過會失敗)。底線鍵:`_raw`(frames.py 寫、phrases 讀)與 `_anaphora_targets`(anaphora 寫、regions 讀)都留到 after_anaphora 結尾才 pop——確認過 phrases.py 不讀 anaphora/regions/agent/manner/negation 任何鍵,anaphora.py 不讀 `_raw` 也不讀 `phrases`。處理順序寫進 frames.py 檔頭(新段「處理順序」)與 enrich.py 檔頭;phrases.py 檔頭加「執行位置」段。
- 測試:新檔 `test_02_phrases_order.py` 2 條(接縫是 enrich 的兩段入口、手寫框架:前段只加 phrases 且 `_raw` 留著;後段補 regions/agent 並清光底線鍵)——先紅(`enrich` 沒有 `before_anaphora`)再綠;句型例子不開(行為零改變,片語與既有鍵由全語料守)。effect-tokenize 全套 889 條(886 + 2 + lint 1)、node 172、script/* 五套 66/43/469/55/136 全過。
- **全語料數字**(frames.py 重跑兩次,決定性):動作 46,112 + 620、約束 4,383 + 8,199、框架總數 59,314(同修前)。`baseline_diff.py`:剝鍵差異 0、底線鍵 0、digest ok(67be8548dddc95dd432ff59064fc27e8);`downstream_baseline.py anaphora`:差異 0、digest ok(6536cac4ae4e7e5727227c2bdb1a82a2);`patient`:差異 0、digest ok(e27d4fa72db2c80c50b943d3f8d30f8f);`export`:ok(01b9d071f1ebaed795881e8f1aa994af);categories.py → export_categories.py 重跑後 `git diff data/` 空;report.py 重生 report.md 無 diff;prepare_view 對修前/修後 frames.json 各跑一次,17 個 view_*.js 逐檔 md5 相同。
- **偏離(要站主知道)**:frames.json 的原始 md5 從 3c4247ab5410fc85dd0a853322d59b43 變成 aca2f99db313617924c83d1e7eccce9b。逐框比對:值差異 0;差的只有 5,054 框(恰是同時帶 anaphora 與 phrases 的那些)的**鍵序**——片語現在在回指前寫進框架,json.dump 照插入序輸出,所以 `phrases` 排到 `anaphora` 前面。sort_keys 正規化後整檔 md5 修前修後相同(e8e8be9c1cade30f6c7e4fea740d87a9)。沒有為了保住舊 md5 去動鍵序(那是為雜湊寫程式);所有入版控的 digest 都是值的 md5(剝鍵 sort_keys、逐框值),全部 ok,下游讀法(拆解頁、批次檔、報告、匯出)逐鍵取值、產物逐位元組相同。票 03 改回指欄後反正要重凍,屆時 md5 又會變。
- 給票 03 的接點:片語段在 `anaphora.resolve` 執行時已在候選框架的 `frame["phrases"][key]["segments"]`;字面備援片語(`frames._phrases`)仍沒有片語結構,要自己過 `phrases.segment`;`_raw` 在回指時仍在框架上(不建議讀,它是切前字面)。給票 04:patient 未動,`WHY_ALIASES` 仍空。
- 未決:無。假設:「決定性重跑 md5 相同」解讀為兩次重跑同一個 md5(成立),不是與修前相同(見偏離)。
