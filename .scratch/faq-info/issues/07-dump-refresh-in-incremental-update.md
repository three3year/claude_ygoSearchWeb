# 07 — 官方 Q&A 缺口對帳納入差值更新流程

**What to build:** 讓「卡片總表有、官方 Q&A 沒有」的缺口在每次[[差值更新]]後自動浮現,使新卡不再因為 ygoprodeck dump 過舊而默默缺席。只回報,不自動補爬。

**Blocked by:** 06 — 先驗證補爬這條路走得通,再談常設化。

**Status:** done

- [x] `update_cards.py` 建置完成後執行對帳,列印缺口張數、抽樣卡名與補齊指令
- [x] 對帳為純本地比對(cards.json 對 faq_info.json),不連網、不下載 dump
- [x] TCG 限定卡(`ot=2`)不列入缺口
- [x] 尚未建過 `faq_info.json` 時略過對帳而非報錯
- [x] 無缺口時不提補齊指令(避免每次更新都像有事待辦)
- [x] `--faq-json` 可指定對帳對象路徑
- [x] unittest 覆蓋:有缺口、無缺口、TCG 限定卡、缺 faq_info.json 四種情境

## 為什麼要做

06 揭露的根因:官方 Q&A 的爬取清單由 ygoprodeck dump 產生,dump 一舊,之後官方登錄的新卡就永遠不會被爬,而且破洞是稀疏的、不會在任何既有報告裡顯現。95 張的缺口是這樣累積出來的。

## 實作前的四個問題與定案

| 問題 | 定案 | 理由 |
| --- | --- | --- |
| dump 怎麼取 | **差值更新時完全不碰 dump**。對帳是純本地比對(總表對 `faq_info.json`),零網路成本 | 缺口偵測不需要 dump——沒有官方 Q&A 資料這件事,本機兩份檔案一比就知道。只有真的要補爬時才需要 dump,那是 06 的 `refill_faq.py` 的工作 |
| 舊 dump 保留策略 | 新 dump 存成 `ygopro_full_<日期>.json`,檔名排序在既有 `ygopro_<密碼>_<密碼>.json` 之後 | `build_cid_to_password` 是「先出現者優先」,排序在後代表既有對應永遠不被新檔覆寫,天然滿足只增不減。收斂成單一份留待日後 |
| 缺口偵測放哪 | 純函式 `faqgap.find_missing_cards` / `format_gap_report`,薄殼 `update_cards.check_faq_gap` | 同一組純函式同時給 `update_cards.py`(對帳)和 `refill_faq.py`(補爬)用,判定邏輯只有一份 |
| 偵測到之後 | **只回報,不自動補爬** | 沿用 05 建立的慣例(發現異常就停下回報,不自動全量動作)。補爬要對官方站發數十次請求,該由人決定何時執行 |

## Comments

### 跨資料夾 import

`update_cards.py` 在 `script/card_list/`,`faqgap.py` 在 `script/faq_info/`,兩者不是套件。對帳採在 `update_cards.py` 頂端把 `script/faq_info` 插入 `sys.path` 後直接 import,不用 subprocess——對帳是純函式運算,起一個子行程只為了跨資料夾取用不划算。

### 開票背景(2026-08-08,grilling 產出)

grilling 過程中把「補齊這 95 張」與「以後不再破洞」拆成兩件事。理由:前者範圍清楚、驗收明確,後者要先決定 dump 的取得與比對方式;混在一起會讓 06 遲遲收不了尾。
