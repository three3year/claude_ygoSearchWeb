# Spec: 官方 Q&A 快取抽取為補足情報 JSON

Status: done

## Problem Statement

使用者手上有 14,095 個從 KONAMI 官方卡片資料庫擷取的官方 Q&A 快取頁(以 cid 命名的 HTML,每檔約 85KB、總計約 1.2GB)。其中真正有價值的只有 `id="card_info"` 與 `id="pen_info"` 兩個區塊——特別是各效果的官方裁定說明「補足情報」。其餘 95% 的頁面內容(導覽、SNS、腳本、關聯 Q&A 列表)都是雜訊,導致資料難以取用且佔用大量空間。

此外,使用者需要確認抽取範圍的完整性:「補足情報」是否只出現在這兩個 id 區塊內,有沒有漏網之魚。

## Solution

提供一個抽取管線,把官方 Q&A 快取解析成單一整合的結構化 JSON(每張卡一筆,含 cid、卡片密碼、卡名、卡片文字、補足情報及其更新日期,靈擺卡另含靈擺效果與其補足情報),存入專案的來源資料目錄,供後續建置流程與網站直接取用。原始 HTML 快取保留不動。

同時對全量快取執行「場外補足情報」掃描:凡「補足情報」字樣出現在 card_info/pen_info 之外者,產出報告(檔案、位置、前後文)供人工判讀,不自動抽取。

對「無補足情報」與「無 card_info」的異常檔,先抽樣重爬官方頁面確認快取是否過舊,再決定是否擴大重爬。

## User Stories

1. As a 網站建置流程, I want 一份整合所有卡片補足情報的結構化 JSON, so that 建置時不需解析 1.2GB 的 HTML 快取。
2. As a 使用者, I want 每筆資料同時含 cid 與卡片密碼, so that 可以直接用卡片密碼與卡片總表 join。
3. As a 使用者, I want 每筆資料含日文卡名, so that 人工核對與除錯時不必回頭開原始 HTML。
4. As a 使用者, I want 卡片文字(カードテキスト)與補足情報一併抽出, so that 每條補足能對照其效果原文。
5. As a 使用者, I want 靈擺卡的靈擺效果與其專屬補足情報獨立成欄, so that 靈擺效果與怪獸效果的裁定不會混在一起。
6. As a 使用者, I want 補足情報的更新日期被保留, so that 之後能判斷裁定的新舊與做差值更新。
7. As a 使用者, I want 內文的 `<br>` 轉為換行、其餘標記去除, so that 下游(效果句拆解、網站顯示)拿到乾淨純文字,補足情報可直接以換行切回「■」條目。
8. As a 使用者, I want 沒有補足情報的卡照樣收進 JSON(僅缺該欄位), so that JSON 完整覆蓋所有有快取的卡。
9. As a 使用者, I want 一份「場外補足情報」掃描報告, so that 我能確認兩個 id 區塊之外沒有漏抽的補足情報;若有,由我人工判讀後再決定處理方式。
10. As a 使用者, I want 對「無補足情報」的快取先抽樣重爬 20 檔確認, so that 能排除快取過舊(官方後來才補上補足情報)的可能,而不必立刻全量重爬 698 檔。
11. As a 使用者, I want 2 個無 card_info 的疑似無效 cid 也一併重爬確認, so that 能判定它們是爬取失敗還是官方本就無此卡頁。
12. As a 使用者, I want 重爬取得的新頁面覆蓋快取中的舊檔並重新抽取, so that 快取與 JSON 保持一致。
13. As a 使用者, I want 重爬有禮貌的間隔(約 1.5 秒/請求), so that 不對官方伺服器造成負擔。
14. As a 使用者, I want 若抽樣重爬發現線上頁面確實新增了補足情報,流程停下來回報, so that 由我決定是否全量重爬其餘無補足檔。
15. As a 使用者, I want 抽取執行後的統計報告(收錄數、無補足數、靈擺卡數、對不到密碼的 cid 清單、異常檔清單), so that 我能快速確認抽取結果的健康度。
16. As a 使用者, I want 原始 HTML 快取全部保留不動, so that 未抽取的內容(關聯 Q&A 列表等)日後仍可取用,不需重爬。
17. As a 開發者, I want 解析邏輯集中在單一純函式管線且不碰網路與檔案系統, so that 測試可以餵合成 HTML 片段快速驗證。
18. As a 開發者, I want 對不到卡片密碼的 cid 保留 null 而非丟棄, so that 資料不遺失且缺漏可見於報告。
19. As a 使用者, I want JSON 依 cid 排序且格式穩定, so that 重跑時 diff 乾淨,利於版本控管與差值更新。

## Implementation Decisions

- 沿用 card_list 的架構模式:一個純函式管線模組(吃「(cid, HTML 字串) 序列」與「cid→卡片密碼對應表」,回傳 entries 與 report)加 CLI 薄殼(負責掃描快取目錄、讀檔、寫出 JSON、列印報告)。
- 新增獨立的重爬 CLI 薄殼:對指定 cid 清單抓取官方 Q&A 頁(`faq_search.action?ope=4&cid=…&request_locale=ja`),間隔約 1.5 秒,覆蓋快取舊檔。解析復用同一管線。重爬薄殼不納入自動測試。
- cid→卡片密碼對應:讀取快取目錄中的 ygoprodeck 資料檔(`misc_info` 內的 `konami_id`)建表。對不到者 `password: null` 並列入報告。
- 輸出為單一 JSON 整合檔,置於專案來源資料目錄(與 cards.cdb 等原始來源同層),屬「建置時讀取的原始來源」;每筆欄位:`cid`、`password`、`name_ja`、`card_text`、`supplement`、`supplement_date`、(靈擺卡)`pen_effect`、`pen_supplement`、`pen_supplement_date`。無該資料的欄位省略。依 cid 升冪排序。
- 卡名取自頁面 meta/title(日文)。
- 內文清洗:`<br>` → `\n`,其餘標記剝除,HTML entity 解碼,前後空白修剪;不做其他正規化(全形字元等保持原樣)。
- 「場外補足情報」檢查是管線 report 的一部分:對每檔計算「補足情報」出現位置,凡不在 card_info/pen_info 區塊內者記錄檔名、位置與前後文;只報告,不抽取。
- 異常處理:無 card_info 的檔不進 JSON、列入報告;無補足情報的卡正常進 JSON(缺 supplement 欄)。重爬確認流程為獨立步驟:抽樣 20 檔(無補足)+ 2 檔(無 card_info),重爬後重新抽取比對;若有新增補足情報則停下回報,由使用者決定是否全量重爬。
- 原始 HTML 快取(1.2GB)保留不動,不刪除、不壓縮覆蓋。
- Git:只 commit 本地,不 push(專案既有規則)。

## Testing Decisions

- 測試只驗證管線的外部行為:給定合成 HTML 片段(仿官方頁結構:card_info/pen_info/supplement 區塊)與對應表,斷言回傳的 entries 欄位值與 report 內容;不測內部實作細節。
- 受測模組:僅純函式管線模組。CLI 薄殼與重爬薄殼不納入自動測試(與 card_list 的 build/update 薄殼同等待遇)。
- 先例:card_list 的測試(unittest、fixture 於測試內程式化建立、不碰網路不碰真實資料檔)。
- 應覆蓋的情境:一般卡(有補足/無補足)、靈擺卡(雙區塊、各自補足與日期)、無 card_info 的錯誤頁、場外「補足情報」偵測、`<br>` 轉換與標記剝除、entity 解碼、cid 對不到密碼、多筆整合排序。

## Out of Scope

- 關聯 Q&A 列表(標題與連結)的抽取——本次不抽,原始 HTML 保留故日後可補。
- 個別 Q&A 問答內文的爬取與整合。
- 補足情報的效果句對位、拆解與 tag 分配(屬既有效果句/分類表流程的後續工作)。
- 刪除或壓縮原始 HTML 快取。
- 全量 14,095 檔的重爬或快取更新機制(僅異常檔抽樣重爬;全量重爬另案)。
- 網站前端如何呈現補足情報。
- 卡片總表(cards.json)的 schema 變更——本 JSON 為獨立來源檔,整合與否另議。

## Further Notes

- 事實基線(2026-08-07 快取現況):14,095 個 Q&A 快取頁、495 個 ygoprodeck 資料檔;698 檔無補足情報區塊;2 檔(cid 19359、20691)為空結果頁(77,185 bytes、無卡名);抽樣中「補足情報」皆在兩個 id 區塊內,全量掃描於執行時完成。
- 預估輸出 JSON 體積 20-40MB。
- cid 與卡片密碼是不同編號體系(詳見 CONTEXT.md 詞彙表),join 一律以卡片密碼為準。
- 官方頁面語系固定 `request_locale=ja`;補足情報為日文原文,不翻譯。
