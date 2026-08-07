# ygoSearchWeb — 卡片總表

遊戲王 OCG 自建查卡網站的資料基礎。本階段產出**卡片總表** `cards.json`:
繁中卡文(salix5/cdb)+ 日/英卡名(mycard/ygopro-database)+ MD 稀有度(masterduelmeta),
以卡片密碼對齊整合,只收錄有正式 8 位數密碼的已發售實卡(排除先行卡與衍生物),
同名異圖卡合併為主卡一筆。

領域詞彙見 [CONTEXT.md](CONTEXT.md);規格與票券見 `.scratch/card-list/`。

## 使用

```bash
# 一鍵更新:下載最新來源 → (差值)建置 → data/cards.json + 報告
python script/update_cards.py

# 離線重跑(用 data/sources/ 既有來源檔,不連網)
python script/update_cards.py --offline

# 手動指定來源建置
python script/build_cards.py --zh data/sources/cards.cdb --ja data/sources/ja-JP.cdb --en data/sources/en-US.cdb

# 測試(不連網)
python -m unittest discover -s script
```

僅需 Python 3 標準庫,無安裝依賴;預設路徑以 repo 根為準,任意位置執行皆可。

## 目錄

| 位置 | 內容 |
|---|---|
| `script/cardlist.py` | 核心管線(純函式):來源 cdb → 總表結構 + 建置/變動報告 |
| `script/build_cards.py` | 建置 CLI 薄殼(讀檔、寫 JSON、印報告) |
| `script/update_cards.py` | 一鍵更新殼(下載三來源 → 建置;`--offline` 離線重跑) |
| `data/cards.json` | 卡片總表(一卡一行,git diff 可讀) |
| `data/sources/` | 來源 cdb 暫存(不入版控) |
| `web/` | 查卡網站(後續階段) |

## cards.json 欄位

`id`(主卡密碼)、`alt_ids`(異圖密碼)、`name_zh/ja/en`、`desc`(繁中卡文)、
`type/race/attribute/setcode`(cdb 原始位元值)、`atk`、`def`(Link 怪為 null)、
`level`、`scale`(靈擺刻度)、`link_marker`(Link 箭頭)、`ot`、
`md_rarity`(Master Duel 稀有度 N/R/SR/UR,未實裝為空字串)。

## 後續階段(未實作)

效果 Tag 管線(拆效果句 → 分群 → LLM 貼標)、靜態查卡網站(進階查詢器)。
