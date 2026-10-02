# 03 — 分詞+報表票:新格式新卡全量分詞、三件套報表+檢視頁

**What to build:** 用 02 的種子詞典對新格式新卡層(`script/text_format/classify.py` 的 TIER_NEW,7,818 張)的效果句日文文本(`data/tag_cards.json` 逐句 `text_ja`)做最長匹配分詞,產出:(1) 詞頻表;(2) OOV 率與高頻 OOV 段(補詞迭代輸入);(3) NAME/NUM/助詞正規化後的句型模板分佈(top-N+長尾形狀)。markdown 報表入 `.scratch/effect-tokenize/report.md`,另發互動檢視 artifact(逐模板翻例句,比照先前分群檢視頁)。分詞器純 Python 零依賴、結果決定性。驗收:量化(OOV 率/模板覆蓋)當參考,站主翻檢視頁質性裁定——之後才定推導方法(票 04)。

**Blocked by:** 02

**Status:** resolved

**進度(2026-10-01):** 分詞+報表完成;互動檢視頁已發佈
(`viewer.html`+`view_data.js`,prepare_view.py 產資料,artifact:
https://claude.ai/code/artifact/ce1356df-b8f0-4de6-a74e-a71d4c441fd5 ——
模板 top 300/150 逐列展開例句、OOV top 100、詞頻 top 100、長尾直方;
view_data.js 以純 ASCII 輸出避開伺服器 charset 問題)。
`tokenize.py` 對 TIER_NEW **8,156 段/7,818 張**的 24,599 句 text_ja 分詞
(效果句 16,474/效果外 8,125;無 text_ja 略過 2 句)→ `tokens.json`;
`report.py` → `report.md` + `wordfreq.json`。關鍵數字:OOV token 佔比
效果句 **7.42%**(字數 5.75%)/效果外 7.30%;零 OOV 句 23.12%/34.89%;
模板 14,419 種/1,264 種;top-100 模板覆蓋率效果句 **6.57%**、效果外
**80.39%**(效果句長尾極長:13,706 個單句模板——OOV 段保留字面+活用尾
未收斂是主因,對應 conventions.md 裁定點 R2/R4/R5/R6/R12)。高頻 OOV
top 100 已列報表,補詞迭代輸入就緒。
