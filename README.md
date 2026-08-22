# ygoSearchWeb — 卡片總表、效果標記表與查卡網站

遊戲王 OCG 自建查卡網站。網站在 `web/`(零建置純靜態,雙擊 `index.html` 就會跑),
資料基礎是兩份自持的資料:

**卡片總表** `cards.json`:
繁中卡文(salix5/cdb)+ 日/英卡名(mycard/ygopro-database)+ MD 稀有度(masterduelmeta)
+ Genesys 點數(YGOPRODeck),
以卡片密碼對齊整合,只收錄有正式 8 位數密碼的已發售實卡(排除先行卡與衍生物),
同名異圖卡合併為主卡一筆。

**效果標記表** `tag_cards.json`:把每張卡的效果文拆成效果句,逐句標上效果類型
(十六種固定值)與必發/選發,是進階查詢(「找出所有有誘發即時效果的卡」)的核心依據。
判定分三層權威——官方補足情報的明示 > 規則層 > 逐條判定;規則只寫影子預測不決定值,
每一條都以官方明示獨立驗證(ADR-0002)。

領域詞彙見 [CONTEXT.md](CONTEXT.md);規格與票券見 `.scratch/card-list/` 與
`.scratch/search-web/`。

## 使用

```bash
# 一鍵更新:下載最新來源 → (差值)建置 → data/cards.json + 報告 + 官方 Q&A 對帳
python script/card_list/update_cards.py

# 離線重跑(用 data/sources/ 既有來源檔,不連網)
python script/card_list/update_cards.py --offline

# 手動指定來源建置
python script/card_list/build_cards.py --zh data/sources/cards.cdb --ja data/sources/ja-JP.cdb --en data/sources/en-US.cdb

# 測試(不連網)
python -m unittest discover -s script/card_list
python -m unittest discover -s script/faq_info
python -m unittest discover -s script/tag_card
python -m unittest discover -s script/text_format
python -m unittest discover -s script/web
node --test                       # 前端查詢引擎(node 內建,零 npm 依賴)
```

僅需 Python 3 標準庫,無安裝依賴;預設路徑以 repo 根為準,任意位置執行皆可。
前端測試同樣零安裝:`node:test` + `node:vm`,不進 `package.json`、不裝任何套件。

### 官方 Q&A 補足情報

```bash
# 由快取重建整合檔 → data/sources/faq_info.json + 報告
python script/faq_info/build_faq_info.py

# 盤點缺口(哪些卡沒有官方 Q&A 資料),只看不動
python script/faq_info/refill_faq.py --dry-run

# 補齊缺口:更新 dump 取 cid → 補爬 → 重建整合檔 → 驗收
python script/faq_info/refill_faq.py

# 抽樣重爬,確認「無補足情報」是否只是快取過舊
python script/faq_info/recrawl_faq.py --sample 20
```

快取預設在 `../data_ygoFaqCache/_cache`(repo 外,約 1.1GB),可用 `--cache` 指定他處。
`update_cards.py` 每次更新完會順帶對帳並回報缺口,但**不會自動補爬** —— 補爬要對官方站
發數十次請求,由人決定何時執行。

補爬靠 ygoprodeck 的 `konami_id` 把卡片密碼換成 cid。少數卡 ygoprodeck 查不到(未收錄、
或 `konami_id` 為 null),此時把人工查證的對應寫進 `data/cid_overrides.json`(入版控)即可,
不需改程式:開 `https://www.db.yugioh-card.com/yugiohdb/faq_search.action?ope=4&cid=<cid>`
確認卡名相符後加一筆,再跑 `refill_faq.py --offline`。

### 效果標記表

```bash
# 建置:卡片總表 + 補足情報 + 拆句表 + 既有標記表 → data/tag_cards.json
#       順帶回寫規則清單 docs/effect_kind_rules.md
python script/tag_card/build_tag_cards.py

# 定版驗收:全表完整性檢查 + 收斂條件 + 定版報告(不寫任何檔)
python script/tag_card/seal_report.py

# 差值更新:產生待判批次 → 判定票寫結果檔 → 合併回兩份來源檔
python script/tag_card/make_batches.py --dry-run
python script/tag_card/merge_judgments.py --result <結果檔> --batch <批次檔> --ticket <票號>

# 遮蔽測試:抽樣 → 判定者作答 → 對答案(量化判定準確率)
python script/tag_card/run_masked_test.py sample
python script/tag_card/run_masked_test.py score
```

`data/tag_cards.json` 與 `data/clause_splits.json` 是**來源檔而非建置產物**
(ADR-0001 / ADR-0003):人工修正直接改檔並標 `manual`,重跑永不覆蓋;
判定與拆句的成果同樣活過每一次重跑,只有 `rule` 那一種來源會重算。
判定規範見 `docs/effect_kind_guide.md`,規則清單 `docs/effect_kind_rules.md` 由建置流程產生。

### 查卡網站

```bash
# 建置前端索引:卡片總表 + 效果標記表 → web/data.js + 報告
python script/web/build_index.py

# 只跑檢查與報告,不動 data.js
python script/web/build_index.py --no-write
```

網站是**零建置的純靜態站**(ADR-0007):沒有 npm、沒有 bundler、沒有框架、沒有 ES modules。
雙擊 `web/index.html` 就會跑,不需要起本機 server——索引因此是 `window.CARD_DATA=…` 的
`.js` 而不是 `.json`(`file://` 下 `fetch` 會被 CORS 擋而 `<script src>` 不會)。

cdb 位元 → 值域的轉換只住在建置期的值域正典 `script/web/vocab.py`(ADR-0008),值域與
中文表隨索引輸出成 `window.VOCAB`,**HTML 不寫死任何選項**。索引裡出現正典沒有的值、正典
沒解釋的 `type` 位元、效果句缺效果類型、效果句串接後出現已知兩種以外的覆蓋缺口,
一律**建置失敗**——把「漏一個碼、某批卡無聲消失」換成吵鬧的失效。

`web/data.js` 是**入版控的建置產物**(GitHub Pages 直接吃 repo 內容,產物不進版控就沒有站),
一卡一行、git diff 可讀;同一份輸入兩次建置逐位元組相同。

## 目錄

| 位置 | 內容 |
|---|---|
| `script/card_list/` | 卡片總表建置/更新腳本(下方三支+測試);之後其他用途的腳本各自開資料夾 |
| `script/card_list/cardlist.py` | 核心管線(純函式):來源 → 總表結構 + 建置/變動報告 |
| `script/card_list/build_cards.py` | 建置 CLI 薄殼(讀檔、寫 JSON、印報告) |
| `script/card_list/update_cards.py` | 一鍵更新殼(下載來源 → 建置 → 官方 Q&A 對帳 + 首發日覆蓋回報;`--offline` 離線重跑) |
| `script/faq_info/faqinfo.py` | 官方 Q&A 抽取管線(純函式):HTML → 補足情報結構 + 報告 |
| `script/faq_info/faqgap.py` | 缺口盤點與 cid 對應表管理(純函式) |
| `script/faq_info/faqfetch.py` | 官方 Q&A 頁與 ygoprodeck 的網路存取 |
| `script/faq_info/build_faq_info.py` | 抽取 CLI 薄殼(掃快取 → 寫 faq_info.json) |
| `script/faq_info/refill_faq.py` | 補齊缺漏卡的快取(更新 dump → 補爬 → 重建 → 驗收) |
| `script/faq_info/recrawl_faq.py` | 抽樣重爬殼(確認快取是否過舊) |
| `script/tag_card/tagcard.py` | 效果標記表管線(純函式):卡片總表 + 補足情報 + 拆句表 + 判定結果 → 標記表 + 報告 |
| `script/tag_card/official.py` | 官方明示的抽取與歸屬對位(五道階梯) |
| `script/tag_card/rules.py` | 效果類型規則層的規則登記處(只寫影子預測) |
| `script/tag_card/masked.py` | 遮蔽測試的兩個接縫(抽樣 / 對答案) |
| `script/tag_card/build_tag_cards.py` | 建置 CLI 薄殼(寫 tag_cards.json + 回寫規則清單) |
| `script/tag_card/seal_report.py` | 定版驗收殼(完整性檢查 + 收斂條件 + 定版報告) |
| `script/tag_card/make_batches.py` | 待判批次殼(排票 / 補判 / 改判三種批次) |
| `script/tag_card/merge_judgments.py` | 判定結果合併殼(結果檔 → 拆句表 + 標記表) |
| `script/tag_card/run_masked_test.py` | 遮蔽測試殼(抽樣 / 對答案) |
| `script/tag_card/check_split_rule.py` | 拆句判準的交叉驗證器(新判準會不會切開官方引用) |
| `script/text_format/ocg_dates.py` | OCG 首發日來源的消費端(純函式):以卡片密碼對齊總表、異圖歸主卡 |
| `script/text_format/classify.py` | 三級分類器(純函式):卡文段落 + OCG 首發日 → 舊文本/官方已改寫/新格式新卡/日期不明 |
| `script/text_format/build_report.py` | 三級分類報表殼(全庫盤點 → .scratch/text-format/report.md,可重跑冪等) |
| `script/web/vocab.py` | 值域正典(cdb 位元/整數/中文 → 短碼 → 中文 + 宣告序)+ 自檢接縫 |
| `script/web/webindex.py` | 前端索引管線(純函式):總表 + 標記表 → 索引 + 一致性檢查報告 |
| `script/web/build_index.py` | 建置 CLI 薄殼(讀檔 → 寫 web/data.js → 印報告 → 依 problems 定 exit code) |
| `script/web/frontend_harness.js` | 接縫 3 的沙箱載入器(`node:vm` 依 index.html 的順序載入真實前端程式碼) |
| `script/web/engine.test.js` | 前端查詢引擎的接縫測試(`node:test`,合成資料集) |
| `data/cards.json` | 卡片總表(一卡一行,git diff 可讀) |
| `data/tag_cards.json` | 效果標記表(一卡一物件,入版控的來源檔) |
| `data/clause_splits.json` | 拆句表:舊式無編號卡文的效果句邊界(入版控的來源檔) |
| `data/cid_overrides.json` | 人工查證的 cid→卡片密碼 對應(ygoprodeck 查不到的卡) |
| `data/sources/` | 來源檔暫存,含 `faq_info.json`(不入版控) |
| `docs/effect_kind_guide.md` | 效果類型的判定規範(所有判定票的共同 prompt) |
| `docs/effect_kind_rules.md` | 規則清單(建置流程產生,不要手改) |
| `docs/text_format_guide.md` | 文本格式規範(新式卡文句型的三欄對照與本站規範句) |
| `docs/adr/` | 最難反轉的決定 |
| `../data_ygoFaqCache/_cache` | 官方 Q&A 快取(repo 外,約 1.1GB) |
| `web/index.html` | 查卡網站的頁面(雙擊即可跑;`<script>` 依序載入,無建置步驟) |
| `web/data.js` | 前端索引(建置產物,**入版控**):`window.CARD_DATA` / `VOCAB` / `META` |
| `web/js/` | 前端模組(IIFE 閉包):`util`(工具與值域中文表)、`sort`(領域序與排序鍵,純函式)、`engine`(搜尋判定核心,純函式)、`query`(側欄條件 ⇄ 條件物件)、`hash`(條件與排序 ⇄ 網址 `#hash`,純函式)、`render`(卡片呈現、異圖切換、排序與分頁)、`main`(主流程與網址寫入時機) |
| `index.html` / `.nojekyll` | GitHub Pages 部署形態(根目錄為來源):轉址到 `web/index.html`、擋掉 Jekyll |

## cards.json 欄位

`id`(主卡密碼)、`alt_ids`(異圖密碼)、`name_zh/ja/en`、`desc`(繁中卡文)、
`type/race/attribute/setcode`(cdb 原始位元值)、`atk`、`def`(Link 怪為 null)、
`level`、`scale`(靈擺刻度)、`link_marker`(Link 箭頭)、`ot`、
`md_rarity`(Master Duel 稀有度 N/R/SR/UR,未實裝為空字串)、
`genesys_points`(Genesys 點數,未列點為 0)。

**欄位只在卡片真的有那個參數時才填**:大類非怪獸的卡 `race`/`attribute`/`level` 為 0、
`atk`/`def` 為 null(cdb 為 79 張陷阱怪獸存著完整的怪獸參數,但那是它變成怪獸之後
的形態、寫在效果文的括號裡,不是卡片的參數),Link 怪的 `def` 為 null,`scale` 只在
靈擺卡填、`link_marker` 只在 Link 怪填。`setcode` 不在此列——系列碼是卡面上真的有的
東西。建置報告會驗「大類是怪獸 ⟺ 有種族與屬性」這道不變式。

## tag_cards.json 欄位

一卡一物件,`id` + `clauses`(純通常怪獸為空陣列);穩定鍵為
`(卡片密碼, section, index)`。每個效果句:

`index`(`"0"`=效果外文本段、`"①"`~=原文編號、`"①-●1"`=● 子效果、`"1"`~=舊式卡文的序位)、
`section`(`main` / `pendulum`)、`text_zh` / `text_ja`(卡文的連續子字串,不改寫)、
`text_hash`(身分變動偵測)、`kind`(十六種效果類型)、`optional`(`必發` / `選發` / `null`)、
`role`(效果外文本的子分類:素材指定 / 召喚條件 / 使用次數限制)、
`source`(`official` / `rule` / `llm` / `llm_then_rule` / `manual`)、
`needs_review`、`rule_predicted`(影子預測,不參與 `kind`)、`confidence`、
`tags`(預留給分類表,目前一律為空)。

## 部署

GitHub Pages 以**本 repo 根目錄**為來源:根目錄的 `.nojekyll` 擋掉 Jekyll(否則底線開頭
的檔案會被吃掉),根目錄的 `index.html` 以 meta refresh 轉址到 `web/index.html`。
`web/data.js` 是入版控的建置產物,Pages 直接吃 repo 內容,不需要任何建置步驟。

**推上 GitHub 由使用者手動執行**(專案規則:只 commit 本地、永不 push)。按下按鈕前的
已知代價:repo 必須公開(`data/` 33 MB 與 `.scratch/` 的判定票、遮蔽測試樣本與標準答案
都會公開可下載);`.git` 已約 200 MB,效果標記表每次判定票整檔改寫加上 `web/data.js`
(7.6 MB)每次重生,只會更快逼近 GitHub 單 repo 軟性上限 1 GB(750 MB 開始警告)。

## 後續階段(未實作)

效果 Tag 管線的後半(效果句分群 → 分類表定稿 → 逐句填 `tags`),票券見 `.scratch/tag-card/`。
查卡網站十張票全數完成(規格與票券見 `.scratch/search-web/`):票 01(值域正典與最小索引)、票 02(完整卡片呈現:卡圖、
異圖切換、怪獸參數、靈擺分區、效果外文本樣式)、票 03(搜尋骨架與卡名軸)、
票 04/05(效果文軸與句層標亮、卡片參數軸)、票 06(效果類型與必發/選發軸,句層耦合)、
票 07(領域序與排序選單)、票 08(網址狀態:條件與排序進 `#hash`,帶條件的網址一開就
自動搜尋)、票 09(手機版面:側欄收成頂部可摺疊區、卡片單欄)
與票 10(部署形態:根目錄 `.nojekyll` 與轉址 `index.html`,人工驗收以真實瀏覽器逐項走過;
僅「分享網址在另一台裝置開啟」留待 push 後驗)。
