# 召喚手續、針對卡片與中文化(procedure-target-zh)地圖

Label: wayfinder:map
Charted: 2026-11-03(/mattpocock-skills:wayfinder)

## Destination

三份規格都寫完並切好票,可以開始 implement:召喚手續進索引 / 針對卡片 / 搜尋介面中文化,各自是 `.scratch/<子線 slug>/spec.md` 加 `issues/`,到時沒有待決定的事;丙的譯名表已經站主核可。implement 不在此圖上,照票逐張做。

## Notes

- 形狀已定,不重問:[三項需求的設計決定](issues/01-grill-three-requirements.md)(Q1〜Q35)與 GLOSSARY.md 2026-11-03 改的五條(約束框架、動作框架、框架述詞、回指、針對卡片)。各規格的裁定直接從那裡抄。
- 規則細節不開細節票,寫規格時在 to-spec 裡順手問(每張規格票列了要順手定的項目)。
- 順序:甲 → 乙 → 丙;丙的譯名表草稿(票 04)可以和甲並行。
- 約束(沿用框架述詞線):純 Python 零依賴、同輸入逐位元組決定性、既有欄位逐位元組不變是驗收條件、新規則各做一輪 LLM 抽驗(存 `llm-check/`)、網址不變。
- 例子與驗收用已在框架涵蓋範圍內的卡(黑魔導等),不用骷髏火焰這類官方已改寫級的卡。
- 寫規格票的做法:`/mattpocock-skills:to-spec` 再 `/mattpocock-skills:to-tickets`;spec.md 與譯名表草稿是審核關卡 md,寫或改之前先用 `review-mirror` skill。
- 相關程式:`.scratch/effect-tokenize/`(constraints.py `summon_conditions`、frames.py、enrich.py、phrases.py、regions.py、patient.py `_segment_blocker`、anaphora.py、export_frames.py、predicate.py)、`script/web/`(build_index.py、frameindex.py、vocab.py)、`web/js/`(engine.js、cond.js、strip.js、render.js、query.js、acat.js、hash.js)。本機 `.scratch/effect-tokenize/frames.json` 是 10-30 舊檔,動工前先重跑分詞鏈。
- 只 commit 本地,永遠不要 git push;站主說 commit 才 commit。
- ADR:甲定案寫 ADR 0019「召喚手續另出動作框架」(由 summon-procedure 票 01 寫);乙的「匯出條件值與回指目標」要不要寫,寫規格乙時再問。
- 甲的實作在 `.scratch/summon-procedure/`;乙的匯出改動建在甲的格式版本 3(第四個位置)之上。

## Decisions so far

<!-- 每張 resolved 票一行:名稱連到票,加一句答案的要旨 -->

- [三項需求的設計決定](issues/01-grill-three-requirements.md):召喚手續出位置「召喚手續」的動作框架(白名單、重ねる 算、預設不查、沒寫位置=四個位置);針對卡片看受事者或目的片語、跟回指、兩種模式、從抽屜或結果卡片的鈕帶入;中文化只換顯示、譯名由 agent 起草站主核可、玩家 我方/對手/雙方;順序 甲 → 乙 → 丙。

- [寫規格甲:召喚手續進索引](issues/02-spec-summon-procedure.md):規格與 6 張票在 `.scratch/summon-procedure/`;白名單 9 種、283 框;召喚來源沒寫依卡種、重ねる 一律此卡;剝框重編後比既有欄;寫 ADR 0019。

- [寫規格乙:針對卡片](issues/03-spec-target-card.md):規格與 8 張票在 `.scratch/target-card/`;段的條件建置期解析、前端比對,與動作對象共用一份判法(順手修區間與屬性段);回指目標存段、目的片語也解;字段用卡名包含加核可的對照表;寫 ADR 0020。

## Not yet specified

- 拆解頁(`.scratch/effect-tokenize` 的 viewer)與其他工具頁的日文要不要一起中文化:這次只說「搜尋介面」,寫規格丙時再看。

## Out of scope

- 擴大框架涵蓋範圍到官方已改寫、日期不明兩級(骷髏火焰的 case):要重跑整條分詞鏈與 LLM 抽驗,另一個量級,另開(01 的 Q8)。
- 「〜として扱う」的別名進針對卡片的卡名比對(01 的 Q30)。
- 目的片語回指回填區域欄(01 的 Q33)。
- 召喚條件本身的形式(不能通常召喚、只能以某方式特殊召喚)作為搜尋條件:這次的需求只有召喚手續的動作;站主要再另開。
