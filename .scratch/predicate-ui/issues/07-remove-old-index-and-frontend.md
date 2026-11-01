# 07: 刪舊欄與前端舊路徑

**What to build:** 網站只剩述詞一套搜尋:引擎、前端、索引建置都不再碰舊動作類別,data.js 變小。清單以 predicate-index 票 05 Comments「要刪的舊東西」的網站建置、前端、測試與 harness 三段為準,並先看它列的七條出入。分詞鏈與舊工具在票 08,舊匯出檔這張還在、只是建置不再讀。

**Blocked by:** 03, 04, 05

**Status:** resolved

- [x] 引擎的舊軸函式、`q.act` 分支、`act` mark 與相關匯出都刪掉;`Acat` 只留目錄導覽
- [x] 建置不再讀舊匯出檔:舊六欄 `ae/ac/aes/aen/acs/acn`、`VOCAB.acat`、`META.acat_digest`、參數與檢查、報告列都刪掉;`_content_digest`、`_export_stale` 留給框架部分
- [x] `vocab.py` 的同名舊 tag 值域不刪;`part["table"]` 順手改名
- [x] 舊樣式、harness 的舊驅動函式、`engine.test.js` 與 `render.test.js` 的舊段逐條看過:動作類別線的刪,述詞線以外的合成資料保留
- [x] data.js 重建:舊欄、`VOCAB.acat` 不在檔內;其餘欄與 `fr`、`fl`、框表除了 digest 外相同(比對方法與結果記進 Comments);同輸入建置兩次逐位元組相同
- [x] 全語料 783 格與 237 個具名查詢照過;體積實測記進 Comments,對照規格 Further Notes 的估計
- [x] node 測試與 script/web 全過;真瀏覽器桌面開一次,console 無錯

## Comments

2026-11-02 交件(基準 predicate-ui d848ade;`worktree_bootstrap.py --build` 複製建置輸入,工作樹的 `data/cards.json`、`data/tag_cards.json` 已是 LF,md5 與 digest 相同,不必蓋)。

### 體積(LF 版,舊檔同樣先轉 LF 再量)

| | 改前 | 改後 | 差 | 規格 Further Notes 估計 |
|---|---|---|---|---|
| 整檔 | 9,326,221 / gzip 2,258,289 | **8,730,524 / gzip 2,092,991** | −595,697 / −165,298 | 基準相同,切換後值由本票量 |
| 卡片段 | 8,627,124 / 2,153,781 | 8,044,385 / 1,990,867 | −582,739 / −162,914 | −582,739 / −162,805 |
| VOCAB 段 | 107,363 / 20,954 | 94,483 / 18,379 | −12,880 / −2,575 | `acat` −12,871 / −2,836 |

raw 卡片段與估計完全相同;gzip 差在分段壓縮與舊估計的量法。整檔 raw 另外 −78 是 META 少 `acat_digest` 與舊匯出檔來源。新檔 md5(LF)8921648e4ab4553f52b3ab8be22e5b59。

### 比對(改前 data.js 與新檔各解析四段,一次性腳本,沒入版控)

- 卡 14,207 張;去掉舊六欄後逐卡 JSON 字串相同(含鍵序),0 張不同;有舊欄的卡 7,817 → 0;`fr` 7,817 張、`fl` 445 張隨之相同。
- 框表 12,048 列,整段文字相同。VOCAB 只少 `acat`,其餘鍵值相同。
- META 不同的鍵:`acat_digest` 拿掉;`sources` 少 `action_categories.json`,其餘三個雜湊不變;`frame_digest` 9373596d… → 54da5eb4…(`part["table"]` 改名 `part["frames"]`,鍵算進雜湊);`built_at` 取新時間。
- 同輸入建置兩次:md5 相同,第二次印「內容沒變」。

### 數字

- node `script/web/` 七個檔 **334 pass / 0 fail / 0 skip**(動工前 371:`engine.test.js` 舊段 35 條、`predicate.test.js` 舊 `q.act` 4 條刪掉,新增 2 條),含全語料 783 格與 237 個具名查詢。
- `script/web` unittest **166 OK**(動工前 186:`CategoryTest` 21 條刪掉,新增 1 條);`test_lint` 8 OK。
- 紅燈:新增的 3 條先看到失敗才改程式(CLI 不讀舊匯出檔、`q.act` 不是條件、真 data.js 沒有舊欄)。

### 逐條看過的舊段

- `engine.test.js`:檔尾「動作類別」「動作對象」兩段全是舊軸,整段刪;檔內其他段沒用舊欄。目錄過濾由 `conditions.test.js` 守,一般軸往返由原有網址段守。
- `render.test.js`:舊段票 03 已拿掉,本票沒東西可刪。`clause_tail.test.js` 那條改成不帶舊欄。
- `CategoryTest` 的過時、卡面、段落多一句檢查:`FramesInIndexTest` 已有同型例子(`frame_stale`、`frame_face_stale`),不搬。
- `style.css`:`.act*` 票 03 已刪;掃過全部類名,JS 與 HTML 沒出現的只剩程式組字面的(`ban-*`、`mat-*`、`ot-*`、`ra-*`、`role-*`),沒有舊軸的。`query.js` 舊軸 UI 票 02 已拿掉。

### 真瀏覽器(桌面 1400×900,`python -m http.server` 起 `web/`,Playwright isolated context)

console 只有 `favicon.ico` 404 一筆,pageerror 0。

| 操作 | 看到什麼 |
|---|---|
| 開頁 | `VOCAB.acat`、`META.acat_digest` 不存在,`CARD_DATA` 帶 `ae` 的 0 張,`Object.keys(Acat)` 只有 `catalog`,`Engine` 沒有 `modeLeaves`、`patMode`;目錄 13 個大類,條件列空 |
| 過濾後點 特殊召喚←墓地 | 標籤「特殊召喚 從 墓地」,共 1,228 張(目錄同),句尾標籤 106 個 |
| 點標籤的字 | 抽屜開,1,228 張,欄位照列 |
| 上一頁 | 回到空條件 |
| 舊網址 `破壊,-召喚›特殊召喚&actCost=1&actPat=self` | 兩張標籤,共 900 張,舊參數忽略 |
| 欄位對 + OR 區 | `破壊 動到 非此卡` 與 `條件位 対象とする` 兩張,共 825 張 |

### 規格沒定、這張自己決定的

- `part["table"]` 改名 `part["frames"]`,與 `index["frames"]`、`window.FRAMES` 同字。
- `--categories` 直接拿掉,傳了是 argparse 錯誤,不留無作用的參數。
- `_BuildState` 留著:只剩 `_attach_frames` 一個讀者,但收 4 個參數,攤平不會比較好讀。

### 偏離與留給票 08

- 無偏離。清單的 `hash.js` `ACT` 沒刪:`act` 是規格 4 的新參數,同名不同物;`ACT_COST`、`ACT_PAT` 票 02 已刪。
- 留給票 08:`webindex.py` 的 `SUB_INDEX` 註解與 `test_copies_of_chain_tables_stay_equal` 還指 `export_categories`(舊匯出程式還在);`.scratch/predicate-index/tools/measure_index.py` 還列舊欄名,是量測當時的歷史工具,沒動。
- 文件(GLOSSARY、README、`build-products.md` 的 data.js 列)在票 09。
