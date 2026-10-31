# 寫規格 2:下游改讀與匯出

Type: task
Mode: HITL
Status: resolved
Blocked by: —(04、02 已 resolved;2026-11-01 解鎖)
Map: ../map.md

## Question

跑 `/mattpocock-skills:to-spec` 再 `/mattpocock-skills:to-tickets`(spec.md 先過 `review-mirror`)。範圍:patient.py、anaphora.py、places.py 改讀論元片語與結構化區域欄、刪正則式,動作對象全語料結果不變或逐卡說明;export_categories.py 改匯出每句的框架與欄位(含此卡/非此卡為每框一欄、三個位置都匯)、沿用原文與卡面參數雜湊;categories.py 的歸葉退場,類別樹改為具名查詢目錄、建置期機械編譯成述詞、編不出來的列清單;「全語料沒有命中的具名查詢不留」的檢查;拆解頁與草案、檢驗摘要三個鏡像的去留。

to-spec 裡要順手定的細節:具名查詢來源檔形狀(沿用 category_tree.json 葉條件編譯,還是改寫成直接寫述詞欄位的目錄檔;以「具名查詢編譯試跑」的三張清單為依據)、極性類耐性/限制怎麼用欄位表達、玩家「相對」、開葉門檻要不要留、匯出檔格式與版本號。

答案記 spec.md 與 issues/ 的路徑。

## Comments

- 2026-10-31(wayfinder,票 02 交件):編譯規則與三張清單在 [02 的 Answer](02-named-query-compile-dry-run.md#answer);寫規格 2 時要定——「全語料沒有命中的具名查詢不留」算哪些位置(只算效果位時 取り除く@お互いのフィールド 是空的,算三位置就不空);若規格 1 不把 から 搬進所在,非移動類詞元的所在葉要編成「所在=X 或 來源=X」;規格 1 換成片語中心詞後重跑 tools/compile_dry_run.py 確認關鍵詞葉張數。
- 2026-11-01(frame-args-v4 票 11 交件):規格 1 已交件,本票解鎖。寫規格 2 時讀——鍵名與下游對照(動作對象/回指/類別線/匯出 → phrases/regions/transfer/agent/manner/negation/region_backfill/anaphora.moving)在 [frame-args-v4 票 11 Comments](../../frame-args-v4/issues/11-handoff.md);值域表 `.scratch/effect-tokenize/closed_values.py`;編譯試跑以新中心詞重跑的結果 [tools/results/compile-v4.md](../tools/results/compile-v4.md)(非移動類 から 已在 `regions.place` 以 `transfer`=取自來源 轉進所在,否定形欄已有);六條未決(引用量、戦闘・効果で 加值、全ての/任意の、施事者規則 (3)、段首 その 旗標、其他類中心詞加值)在 `.scratch/effect-tokenize/llm-check/summary.md`「需要你決定的」,規格 2 的 to-spec 要先裁或帶進去。
- 2026-11-01(wayfinder,走圖 session):本票是唯一在前沿的票(06 擋在 05/01、03 擋在 06、07 擋在 06/03),claimed。to-spec / to-tickets 由站主執行,本 session 只整理輸入;還沒有子線目錄,slug 建議 `category-queries-v3`(動作類別第三版=具名查詢目錄;或 `downstream-export-v2`,站主定)。規格 2 在整合分支 `frame-args-v4`(92b2731,未併 main)上寫、在它的鍵上改讀。
  - **裁定來源(抄,不重問)**:GLOSSARY「動作類別」第三版段(目錄、不互斥、詞元節點=詞元全部、「全語料沒有命中的具名查詢不留」)、「動作對象」(述詞欄位、三選一、此卡/非此卡/選擇類/全部類/發動位置的判法)、「框架述詞」、「具名查詢」、「論元片語」(L388〜)、「值域正典」(L451〜);ADR-0018 Consequences 第 1〜2 條(匯出改「每句的框架與欄位」、ADR-0017 的入版控/原文雜湊/卡面雜湊/試點目錄是上游不變;歸葉程式退場、樹檔改為具名查詢來源、編不出來的列清單)。
  - **事實來源**:票 02 Answer 與 [tools/results/compile-v4.md](../tools/results/compile-v4.md)(233 葉全編得出;101 葉張數相同、31 葉不同:不再互斥 2,710 卡·葉、並收取消 13、非移動類 から 1,187 已由 `regions.place` 取自來源 收回;預設葉取消 97 葉);鍵名對照全文在 [frame-args-v4 票 11 Comments「給規格 2 的對照」](../../frame-args-v4/issues/11-handoff.md)(動作對象 → `phrases.object.segments[].quantity/head/head_kind/modifiers/player/zones/demonstrative`、`regions.source|place`;回指 → `phrases[欄].segments[].modifiers/head/quantity`、`anaphora.moving`、`region_backfill`;類別線 → `phrases[對象→主語→主題].segments[].head`、`phrases.goal.segments[].head`、`negation`(受身/不成不受 → 耐性、不可能 → 限制、一般 → 無)、`regions.*` 玩家(推得欄 無、雙方 お互い)、`agent`/`agent_source`/`agent_inferred`、`manner`/`manner_kind`/`manner_value`;匯出 → 上面全部,可選鍵、`closed_values.py` 值域、`baseline_diff.NEW_KEYS`);現行下游尺寸:patient.py 660 行(25 處正則)、anaphora.py 472(32)、places.py 167(9)、categories.py 684(`LEAF_KEYS`/`polarity_class`/`classify_frame`/`place_literal`)、export_categories.py 273(docstring 是現行格式:每句效果位/代價位葉 × 此卡/非此卡六組、原文 sha1 前 16 碼、卡面雜湊、統計、樹;`DOC` 字串是檔內說明)、category_tree.json 340 行(鍵 說明/樹;節點三種:大類/詞元節點(極性類)/葉,葉條件欄 來源/目的/所在/×玩家/關鍵詞/目的關鍵詞/大類/中類);category_draft.py(類別樹草案資料塊,開葉門檻 ≥10 框在它第 52 行)、prepare_view.py(拆解頁);`script/web/build_index.py` 讀 data/action_categories.json(3.99 MB),建置失敗碼 category_stale / category_unknown_leaves / category_face_stale。
  - **三個鏡像**(去留本票裁):拆解頁 https://claude.ai/artifact/SSvzzZPLJcZsVLewfm3Htx(Version 67)、檢驗摘要 https://claude.ai/artifact/K9v5rfWiXgSdTgPgs83PpK(Version 27)、類別樹草案 `.scratch/action-categories/tree-draft.md`(category_draft.py 產資料塊)。
  - **to-spec 要先裁或帶進去的未決**(`llm-check/summary.md`「需要你決定的」第四版論元九條,各附選項與建議;其中 (1)(2)(3)(5)(6) 直接影響規格 2 的述詞讀法):(1) 受事者之前的引用量 280 框+が+數量 4 框;(2) 戦闘・効果で 一族約 655 框要不要加「手段:戰鬥或效果」(規格 3 的方式述詞讀得到);(3) 全ての/任意の 276 段收進數量;(4) 施事者規則 (3) 0 框 vs 513 框;(5) 段首 その 在定語子句裡的指示詞旗標約 520 段(規格 2 改讀旗標判此卡時會把「同族怪獸」當指示詞);(6) 其他類中心詞加 玩家/牌組位置/表示形式值 三值約 3,700 段(目的欄 裏側守備表示 這型葉 にする→裏側守備表示 的編法靠它);(7) 方式類保留 其他(補 ADR-0018 一句);(8) 効果モンスター 整格是中心詞(葉 破壊:魔法カード/罠カード 的比法跟著定);(9) 表側/裏側 不進分詞封閉值域。採 (a) 的要改的是框架線模組(phrases/manner/closed_values),可以當規格 2 的前置票或另開小票。
  - **票面要順手定的細節,補到的依據**:具名查詢來源檔形狀——沿用 category_tree.json 葉條件編譯(`compile_dry_run.py` 已示範全部規則:區域條件 → `regions` 任一 (玩家, 區域) 段相等、沒宣告玩家不看;關鍵詞 → 中心詞子字串;極性類 → `negation` 同欄多值)vs 改寫成直接寫述詞欄位的目錄檔;「不留」算哪些位置(只算效果位時 取り除く@お互いのフィールド 空,算三位置不空);玩家「相對」是玩家值域一值、不中宣告玩家的葉;開葉門檻 ≥10 框隨歸葉退場還留不留;匯出檔格式與版本號(現行無版本號,靠 DOC 字串與雜湊擋建置);關鍵詞比對 相等/子字串 地圖寫規格 3 定,但編譯具名查詢時就要用,建議在本票定。
  - **驗收口徑可沿用票 11**:動作對象全語料結果不變或逐卡說明(現行 patient 判定的 WHY_* 理由碼 40 種可當逐卡說明的鍵)、三步鏈後 `git diff --ignore-all-space data/`、effect-tokenize 全套 857 條、node 172、script/* 五套;匯出改格式後 `build_index.py` 的三個 category_* 失敗碼要對應改。
- 2026-11-01(to-spec):規格初稿寫在 `.scratch/named-queries/spec.md`(Status ready-for-human),鏡像 https://claude.ai/artifact/D5A6HYgwaf35Tr8tNQXRPr。上一條提到的九條未決在 1981da1 已全部落地(站主全採建議),規格 2 不用再裁;本規格頁首另有十二個待決事項(目錄檔形狀、不留的位置口徑、中心詞比法(試算:尾綴與子字串只差 6 張)、回指改讀要不要搬片語結構化、舊匯出檔過渡、格式版本號、開葉門檻、三個鏡像、LLM 一輪、相對/無、詞元節點極性、測試接縫),裁定後補 `決定` 行、改 ready-for-agent、再 to-tickets。
- 2026-11-01(to-spec 收尾):十二項全部裁定(全採建議),spec.md 標 ready-for-agent、鏡像第 2 版;等 to-tickets 產出 issues/ 後本票 resolve。

## Answer

2026-11-01 resolved(to-spec 與 to-tickets 由站主執行,wayfinder session 記錄)。

- 規格:[.scratch/named-queries/spec.md](../../named-queries/spec.md),Status ready-for-agent;鏡像 https://claude.ai/artifact/D5A6HYgwaf35Tr8tNQXRPr(第 3 版)。
- 票:[.scratch/named-queries/issues/](../../named-queries/issues/) 11 張——01 基準凍結與驗收工具;02 片語結構化搬到回指之前;03 回指改讀片語;04 動作對象改讀片語;05 匯出新檔的框列;06 參考評估器與夾具;07 目錄檔改寫與檢查;08 命中、張數與「不留」;09 拆解頁、報告與草案退場;10 LLM 抽驗一輪加複檢;11 交件。04 與 02→03 平行;05〜08 一條鏈;11 擋在 03/09/10。
- 十二項細節全部裁定(全採建議):目錄檔一次改寫成述詞字彙(過渡期寫新目錄檔、舊樹檔凍結給舊歸葉);「不留」算三個位置合計;中心詞尾綴比對(與子字串只差 6 張);片語結構化搬到回指之前、回指改讀;新匯出檔 `data/action_frames.json` 與舊檔並存、歸葉程式留到規格 3 刪;匯出加整數格式版本;開葉門檻退場;拆解頁總覽改具名查詢總覽、草案退場、檢驗摘要留;具名查詢命中一輪 LLM 抽驗;相對/無留在值域;詞元節點只含肯定與可能;接縫四個(框架抽取、目錄、匯出、參考評估器)。
- 票面的「極性類怎麼用欄位表達」已由規格 1 的否定形欄解掉(耐性 = 否定形 ∈ {受身, 不成不受}、限制 = 否定形 = 不可能);票 02 的「非移動類 から」由 regions.place 取自來源收回。
