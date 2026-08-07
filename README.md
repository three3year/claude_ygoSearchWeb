# ygoSearchWeb — 卡片總表

遊戲王 OCG 自建查卡網站的資料基礎。本階段產出**卡片總表** `cards.json`:
繁中卡文(salix5/cdb)+ 日/英卡名(mycard/ygopro-database)+ MD 稀有度(masterduelmeta)
+ Genesys 點數(YGOPRODeck),
以卡片密碼對齊整合,只收錄有正式 8 位數密碼的已發售實卡(排除先行卡與衍生物),
同名異圖卡合併為主卡一筆。

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
| `data/cards.json` | 卡片總表(一卡一行,git diff 可讀) |
| `data/sources/` | 來源檔暫存,含 `faq_info.json`(不入版控) |
| `../data_ygoFaqCache/_cache` | 官方 Q&A 快取(repo 外,約 1.1GB) |
| `web/` | 查卡網站(後續階段) |

## cards.json 欄位

`id`(主卡密碼)、`alt_ids`(異圖密碼)、`name_zh/ja/en`、`desc`(繁中卡文)、
`type/race/attribute/setcode`(cdb 原始位元值)、`atk`、`def`(Link 怪為 null)、
`level`、`scale`(靈擺刻度)、`link_marker`(Link 箭頭)、`ot`、
`md_rarity`(Master Duel 稀有度 N/R/SR/UR,未實裝為空字串)、
`genesys_points`(Genesys 點數,未列點為 0)。

## 後續階段(未實作)

效果 Tag 管線(拆效果句 → 分群 → LLM 貼標)、靜態查卡網站(進階查詢器)。
