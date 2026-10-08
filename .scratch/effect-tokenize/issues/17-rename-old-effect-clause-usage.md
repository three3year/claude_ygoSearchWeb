# 17 — 舊義「效果句」改稱標記句

**What to build:** ADR-0015 把效果句改指整段編號效果(含 ● 選項),帶效果類型的那一列改稱標記句。把現行規範文件與程式註解裡指「效果標記表那一列」的「效果句」改成標記句,讓讀者不會把搜尋與效果類型的單位誤解成整段。只改用詞,不改任何行為與資料。

**Blocked by:** None — can start immediately

**Status:** resolved

- [x] 效果類型判定指南與判別規則兩份規範文件:指標記單位的「效果句」改為標記句;真的指整段效果的地方照新義保留。
- [x] 搜尋判定核心、前端索引建置、效果標記表建置與官方明示等腳本的註解、說明字串與測試名稱同樣處理。
- [x] `.scratch` 底下的舊票、舊規格是歷史紀錄,不改。
- [x] 逐處判斷新舊義,不做機械全替換;改完全 repo 測試照舊通過(指令見 README 的測試段)。
- [x] `data/tag_cards.json` 等資料檔與其欄位名不動。

## Comments

- 2026-10-09 完成:docs/effect_kind_guide.md 53 行、web/js/engine.js 13 處、script/tag_card 15 個檔約 180 處改為標記句;docs/effect_kind_rules.md 是建置產生檔,改產生端(build_tag_cards.py 的前言/驗證標題、rules.py 的 SCOPE_CLAUSE 與 R5〜R17 判別條件字串)後以 scratch 複本重出 md(data/ 逐位元組未變);因判別條件字串進規則定義指紋,指紋由 2f4e19456407ed71 變 6c021728a05a7a15(seal_report 比對 md 上那一行與現算值,已一致)。保留原字的地方(兩義都成立或指編號效果邊界):不得跨越效果句邊界、咬進下一個效果句、舊式卡文依語意拆成多個效果句、index 序數「第幾個效果句」、與效果外文本段對比的「效果句 1、2、3」、領起句是效果句的一部分。README.md、CONTEXT.md、ADR、data/text_errata.json(資料檔 3 處)未動。全 repo 測試照舊通過。
