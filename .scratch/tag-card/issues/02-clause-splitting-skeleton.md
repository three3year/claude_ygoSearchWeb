# 02 — 拆句骨架:卡片總表 → 效果標記表

**What to build:** [[效果標記表]]首次存在。跑一次建置就能得到 `data/tag_cards.json`:14,207 張卡全部被拆成[[效果句]],每句帶編號、段落歸屬、繁中與日文原文、文本雜湊與[[效果外文本]]的子分類,`kind` 全部為 `null`。使用者打開檔案就能逐卡檢查拆句是否正確,而類型判定留給後續票。

同時建立本功能唯一的接縫:`build_tag_cards(卡片總表條目, 補足情報條目, 既有標記表=None, 判定結果=None) -> (entries, report)`,純函式、不碰網路與檔案系統。CLI 薄殼負責讀檔、寫 JSON、印報告,不納入自動測試。

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [ ] `data/tag_cards.json` 產出,涵蓋全部 14,207 張卡,一卡一物件,依卡片密碼升冪,`indent=2`,保留結尾換行
- [ ] 每個效果句具備 `index` / `section` / `text_zh` / `text_ja` / `text_hash` / `kind` / `optional` / `role` / `source` / `rule_predicted` / `confidence` / `tags` 欄位,本票 `kind` 一律 `null`
- [ ] 切割點只取行首或緊接換行的編號字元;含文中編號的 2,509 張卡(如「這個卡名的①②效果1回合各能使用1次」)不得被切開,需有回歸測試
- [ ] 第一個切割點之前的非空文字(排除段落標頭)抽成 `index: "0"`、`kind: "效果外文本"`、`source: "rule"` 的效果句
- [ ] 前言段的 `role` 判為 `素材指定` / `召喚條件` / `使用次數限制` 之一或 `null`
- [ ] 靈擺卡拆成 `section: "main"` 與 `section: "pendulum"` 兩組,兩組各自從①編號互不衝突
- [ ] 靈擺卡以卡文標頭字串判別段落,不得只依賴資料庫 type 位元
- [ ] 純通常怪獸的 `clauses` 為空陣列(不是缺欄位)
- [ ] 靈擺通常怪獸只抽靈擺段,`【怪獸敘述】`以下整段丟棄,需有回歸測試(該類卡同時帶 Normal 與 Pendulum 位元)
- [ ] 無編號舊式卡文先當單一效果句並在報告中標記待拆,實際語意拆分留給判定票
- [ ] 每個效果句的 `text_zh` / `text_ja` 都是對應卡文的連續子字串,有測試驗證
- [ ] 報告列出繁中與日文編號數量不一致的卡(預期 2 張)
- [ ] 測試只透過 `build_tag_cards` 這一個接縫驗證外部行為,fixture 於測試內程式化建立,不碰網路與真實資料檔
