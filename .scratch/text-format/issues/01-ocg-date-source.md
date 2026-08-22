# 01 — ocg_date 發售日來源引入

**What to build:** 站主更新資料時,能一併取得全庫每張卡的 OCG 首發日:從既有來源 YGOPRODeck(`misc_info` 的 `ocg_date`)一次抓齊,存成新的來源檔,並納入既有[[資料更新時間]]機制。跑完能回報覆蓋率——幾張卡查無日期(它們之後在報表歸「日期不明」)。發售日只服務報表與稽核排序,不進[[前端索引]]、不做搜尋軸。

**Blocked by:** None — can start immediately.

**Status:** resolved

- [x] 更新腳本可重跑、冪等,產出的來源檔與其他來源檔並列,記入資料更新時間
- [x] 以[[卡片密碼]]對齊[[卡片總表]],異圖(alt_ids)歸主卡
- [x] 回報覆蓋率統計:有日期/查無日期張數
- [x] 查無日期的卡保留在資料中並可辨識,不硬猜日期

## Comments

2026-08-22 實作完成:

- 下載端:`update_cards.py` 新增 `download_ocg_dates`(YGOPRODeck 全量 dump
  `?misc=yes`,不帶 `format=` 卡池篩選),萃取 `{密碼: ocg_date}` 存
  `data/sources/ocg-dates.json`,納入 `download_all`——任一來源失敗即不記
  [[資料更新時間]],offline 沿用快取,原子替換寫檔(與其他來源同慣例)。
- 消費端:新模組 `script/text_format/ocg_dates.py` 純函式
  `load_ocg_dates` / `align_ocg_dates`——每張主卡一筆,主卡沒對到試異圖密碼,
  查無日期記 `None`(可辨識、不猜);來源檔存原始樣貌,對齊在消費端做,
  比照 genesys/禁限慣例。
- 覆蓋回報:`update_cards.py` 的 `check_ocg_date_coverage` 於一鍵更新後印出
  「有日期/查無日期張數」。實跑結果:14,207 張中 **13,868 張有日期、339 張
  查無**(含 20 張 `ot=2` TCG 限定;其餘多為 YGOPRODeck 尚未給日期的新卡)。
- 測試:`test_update.py` 增下載/覆蓋回報測試,`test_ocg_dates.py` 合成記錄測
  對齊;全套(card_list/faq_info/tag_card/text_format/web + node)全綠。
- 文件:CONTEXT.md [[資料更新時間]]改八個來源檔;README 測試指令與目錄表補列。
