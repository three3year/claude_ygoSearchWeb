# 寫規格 1:框架線的論元片語與新欄

Type: task
Mode: HITL
Status: resolved
Blocked by: —
Map: ../map.md

## Question

跑 `/mattpocock-skills:to-spec` 再 `/mattpocock-skills:to-tickets`,產出 `.scratch/<子線 slug>/spec.md` 與 `issues/`(spec.md 先過 `review-mirror`)。範圍:frames.py 產出論元片語(中心詞字面與中心詞類、分型修飾語、數量字面與數量類、玩家、區域、指示詞、字面)取代受事者位與目的補語的純字串;來源/目的/所在結構化成區域加玩家加字面;新欄施事者(玩家或卡片片語,推得標記)與方式(字面加方式類);回指回填(上午方向 6 的規則:對象是指示詞、回指目標有區域、框架缺字面來源/所在時填來源(移動類)或所在(非移動類),只接非移動類目標,跨句,在回指之後跑)。驗收:字面欄逐位元組不變、新欄填充率報告、每個新封閉類進值域正典、各做一輪 LLM 抽驗。

to-spec 裡要順手定的細節:施事者推導順序(主題、事件主語、預設發動者)、被動句 によって 記誰、此卡當施事者的條件;中心詞邊界(沿用關鍵詞只比中心詞的規則?)、修飾語切段與各類的辨識規則、數量類與方式類的完整值表與邊界例(定語裡的 で、それぞれ、数の分だけ);LLM 抽驗的分層。

答案記 spec.md 與 issues/ 的路徑。

## Comments

- 2026-10-31(wayfinder,票 02 交件):「具名查詢編譯試跑」查出兩處欄位不夠,寫規格 1 時要裁——(1) 耐性/限制 的述詞沒有欄可讀:框架線要把否定述語形記成封閉類(被動否定 / 不成・不受 / 不可能 / 一般)或直接匯出極性類;(2) 非移動類動作的 から 字面(手札・墓地から選ぶ,1,187 卡·葉)要不要記進所在欄。數字與例子見 [02 的 Answer](02-named-query-compile-dry-run.md#answer)。
- 2026-10-31(wayfinder,走圖 session):05〜07 與 03 全被擋,本票是唯一可動的票,維持 claimed。還沒有子線目錄;to-spec / to-tickets 由站主執行,本 session 只整理輸入——規格 1 的裁定來源是 GLOSSARY「論元片語」「框架述詞」「具名查詢」「動作對象」段與 ADR-0018,加票 02 Answer 的兩處欄位不夠(否定形封閉類、非移動類 から)。子線 slug 建議 `frame-args-v4`(對齊 GLOSSARY 的動作框架第四版論元,延續 frame-args-v2/v3)。
- 2026-10-31(to-spec):規格初稿寫在 `.scratch/frame-args-v4/spec.md`,鏡像 https://claude.ai/artifact/P5Uedpfhejqz5Lxi6K3ZNt;九個待決事項在頁首(否定形、非移動類 から、預設施事者範圍、によって、此卡當施事者、中心詞邊界、數量類下限、で 接區域、LLM 分層),裁定後補 `決定` 行、再 to-tickets。
- 2026-10-31(to-spec 收尾):九項全部裁定(全採建議選項;數量類加下限),spec.md 標 ready-for-agent、鏡像第 3 版;等 to-tickets 產出 issues/ 後本票 resolve。

## Answer

2026-10-31 resolved(to-spec 與 to-tickets 由站主執行,wayfinder session 記錄)。

- 規格:[.scratch/frame-args-v4/spec.md](../../frame-args-v4/spec.md),Status ready-for-agent;鏡像 https://claude.ai/artifact/P5Uedpfhejqz5Lxi6K3ZNt(第 3 版)。
- 票:[.scratch/frame-args-v4/issues/](../../frame-args-v4/issues/) 11 張——01 基準凍結與驗收工具;02 片語切段/中心詞/中心詞類;03 修飾語;04 數量;05 來源/目的/所在結構化與取自來源;06 方式;07 施事者;08 否定形;09 回指回填;10 LLM 抽驗一輪加複檢;11 交件。02 含編譯試跑改讀新中心詞重跑。
- 九項細節全部裁定(全採建議):否定形封閉類欄(受身/不成不受/不可能/一般);非移動類 から 與 で 接區域都進結構化所在、標轉欄、字面不動;預設施事者只補代價/效果位他動帶對象框架、值 自分 標推得;によって 玩家/其他卡/此卡;此卡帶對象才是施事者;中心詞是最後一個名詞格、封閉值域複合詞一格一詞;數量類加下限;LLM 一輪合併分七層。
- 票 02 的兩處欄位不夠已裁:否定形欄;所在取自來源。接縫仍是框架抽取一個;下游四支程式本規格不改。
