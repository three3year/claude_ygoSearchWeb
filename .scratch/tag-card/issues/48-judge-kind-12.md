# 48 — 判定票 31/33 — 只判類型 kind-12

**What to build:** 只判類型系列第 12 批(300 張卡)的[[效果類型]]與[[必發/選發]]判定。本票完全自足:只讀 `docs/effect_kind_guide.md` 與自己的批次檔,不回頭查其他來源,也不需要前一票的記憶。

**Blocked by:** 06 — 影子預測與規則登記、07 — 遮蔽準確率測試、08 — 拆句表、判定結果合併與批次檔、13 — 拆句試點票、47 — 前一張判定票

**Status:** ready-for-agent

## 工作契約

- [ ] **產生批次檔**:`python script/tag_card/make_batches.py --series kind --limit 1 --start 12` → `.scratch/tag-card/batches/kind-12.json`。批次即時產生,吃得到最新的規則層與最新的效果句集合
- [ ] **讀規範**:`docs/effect_kind_guide.md` 從頭讀完。§5.5 / §5.6 / §5.8 是判類型最容易錯的地方。本系列的卡文已經有①②③編號,效果句集合已定,不需要拆句,§8 用不上。
- [ ] **逐卡判定**:每個待判效果句的[[效果類型]]與[[必發/選發]]。判不出來的**留空並在 `note` 記理由**,不猜
- [ ] **寫一個結果檔** `.scratch/tag-card/judgments/kind-12.json`(入版控,它是這一票的稽核軌跡)。判不出來的留空並寫 `note`,合併程序會把它們列進待審
- [ ] **合併**:`python script/tag_card/merge_judgments.py --result .scratch/tag-card/judgments/kind-12.json --batch .scratch/tag-card/batches/kind-12.json --ticket 票48`。先 `--dry-run` 跑一次三道關卡(集合一致性自檢、拆句表三道驗證、判定對得回效果句),問題修到 0 再正式寫入。**不要用 `--force`**
- [ ] **歸納規則**:被打臉的地方寫進 `docs/effect_kind_guide.md`;可規則化的判定寫進 `script/tag_card/rules.py` 的影子預測層(覆蓋 ≥ 8 條才進)。本系列不動 §8
- [ ] **回報**:本票判了幾條、與[[官方明示]]一致而留 `official` 幾條(這是準確率的免費量測)、留空待審幾條,以及 `rule_llm_conflict` 幾筆
- [ ] 只 commit 到本地分支,不 push

## Comments

流程由票13(要拆+判的第一批 200 張)實測定案:三道關卡一次過、判定與回頭撿到的[[官方明示]]不一致 0 條。本系列每票 300 張。
