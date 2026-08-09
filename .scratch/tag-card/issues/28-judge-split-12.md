# 28 — 判定票 11/33 — 要拆+判 split-12

**What to build:** 要拆+判系列第 12 批(200 張卡)的[[效果句]]拆分與[[效果類型]]判定。本票完全自足:只讀 `docs/effect_kind_guide.md` 與自己的批次檔,不回頭查其他來源,也不需要前一票的記憶。

**Blocked by:** 06 — 影子預測與規則登記、07 — 遮蔽準確率測試、08 — 拆句表、判定結果合併與批次檔、13 — 拆句試點票、27 — 前一張判定票

**Status:** ready-for-agent

## 工作契約

- [ ] **產生批次檔**:`python script/tag_card/make_batches.py --series split --limit 1 --start 12` → `.scratch/tag-card/batches/split-12.json`。批次即時產生,吃得到最新的規則層與最新的效果句集合
- [ ] **讀規範**:`docs/effect_kind_guide.md` 從頭讀完。§8 是拆句判準所在,§5.5 / §5.6 / §5.8 是判類型最容易錯的地方。
- [ ] **逐卡判定**:每一團拆成幾段、每段的繁中與日文原文**連續子字串**、每段的[[效果類型]]與[[必發/選發]]。判不出來的**留空並在 `note` 記理由**,不猜
- [ ] **寫一個結果檔** `.scratch/tag-card/judgments/split-12.json`(入版控,它是這一票的稽核軌跡)。判定者不維護拆句表與效果標記表的一致性,那由合併程序保證
- [ ] **合併**:`python script/tag_card/merge_judgments.py --result .scratch/tag-card/judgments/split-12.json --batch .scratch/tag-card/batches/split-12.json --ticket 票28`。先 `--dry-run` 跑一次三道關卡(集合一致性自檢、拆句表三道驗證、判定對得回效果句),問題修到 0 再正式寫入。**不要用 `--force`**
- [ ] **歸納規則**:被打臉的地方寫進 `docs/effect_kind_guide.md`;可規則化的判定寫進 `script/tag_card/rules.py` 的影子預測層(覆蓋 ≥ 8 條才進)。**新增或修改 §8 的拆句判準前**,先用 `python script/tag_card/check_split_rule.py '<判準正則>'` 掃過全部未拆整團,確認它不會把官方 `『原文』` 引用切開,再寫進文件
- [ ] **回報**:本票拆了幾段、幾團拆不出來(附理由)、判了幾條、因拆句新取得[[官方明示]]幾條、其中與判定不一致幾條(這是準確率的免費量測),以及 `rule_llm_conflict` 幾筆
- [ ] 只 commit 到本地分支,不 push

## Comments

流程由票13(要拆+判的第一批 200 張)實測定案:三道關卡一次過、判定與回頭撿到的[[官方明示]]不一致 0 條。本系列每票 200 張。
