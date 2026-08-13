# ygoSearchWeb — 卡片總表與效果標記表

遊戲王 OCG 自建查卡網站的資料基礎,目前有兩份資料:

**卡片總表** `cards.json`:
繁中卡文(salix5/cdb)+ 日/英卡名(mycard/ygopro-database)+ MD 稀有度(masterduelmeta)
+ Genesys 點數(YGOPRODeck),
以卡片密碼對齊整合,只收錄有正式 8 位數密碼的已發售實卡(排除先行卡與衍生物),
同名異圖卡合併為主卡一筆。

**效果標記表** `tag_cards.json`:把每張卡的效果文拆成效果句,逐句標上效果類型
(十六種固定值)與必發/選發,是進階查詢(「找出所有有誘發即時效果的卡」)的核心依據。
判定分三層權威——官方補足情報的明示 > 規則層 > 逐條判定;規則只寫影子預測不決定值,
每一條都以官方明示獨立驗證(ADR-0002)。

領域詞彙見 [CONTEXT.md](CONTEXT.md);規格與票券見 `.scratch/card-list/`。

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
```

僅需 Python 3 標準庫,無安裝依賴;預設路徑以 repo 根為準,任意位置執行皆可。

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

## 目錄

| 位置 | 內容 |
|---|---|
| `script/card_list/` | 卡片總表建置/更新腳本(下方三支+測試);之後其他用途的腳本各自開資料夾 |
| `script/card_list/cardlist.py` | 核心管線(純函式):來源 → 總表結構 + 建置/變動報告 |
| `script/card_list/build_cards.py` | 建置 CLI 薄殼(讀檔、寫 JSON、印報告) |
| `script/card_list/update_cards.py` | 一鍵更新殼(下載來源 → 建置 → 官方 Q&A 對帳;`--offline` 離線重跑) |
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
| `data/cards.json` | 卡片總表(一卡一行,git diff 可讀) |
| `data/tag_cards.json` | 效果標記表(一卡一物件,入版控的來源檔) |
| `data/clause_splits.json` | 拆句表:舊式無編號卡文的效果句邊界(入版控的來源檔) |
| `data/cid_overrides.json` | 人工查證的 cid→卡片密碼 對應(ygoprodeck 查不到的卡) |
| `data/sources/` | 來源檔暫存,含 `faq_info.json`(不入版控) |
| `docs/effect_kind_guide.md` | 效果類型的判定規範(所有判定票的共同 prompt) |
| `docs/effect_kind_rules.md` | 規則清單(建置流程產生,不要手改) |
| `docs/adr/` | 最難反轉的決定 |
| `../data_ygoFaqCache/_cache` | 官方 Q&A 快取(repo 外,約 1.1GB) |
| `web/` | 查卡網站(後續階段) |

## cards.json 欄位

`id`(主卡密碼)、`alt_ids`(異圖密碼)、`name_zh/ja/en`、`desc`(繁中卡文)、
`type/race/attribute/setcode`(cdb 原始位元值)、`atk`、`def`(Link 怪為 null)、
`level`、`scale`(靈擺刻度)、`link_marker`(Link 箭頭)、`ot`、
`md_rarity`(Master Duel 稀有度 N/R/SR/UR,未實裝為空字串)、
`genesys_points`(Genesys 點數,未列點為 0)。

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

## 後續階段(未實作)

效果 Tag 管線的後半(效果句分群 → 分類表定稿 → 逐句填 `tags`)、
靜態查卡網站(進階查詢器)。
