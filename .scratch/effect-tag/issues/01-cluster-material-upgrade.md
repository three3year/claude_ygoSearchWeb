# 01 — 分群素材優化:模型升級重跑+兩層分群

**What to build:** 裁定用的分群素材升級到前導研究 §6.3 的建議配置:以 BGE-M3(或 multilingual-e5-large,視 CPU 時間取捨)重算新式子集 19,342 條的日文向量;粗分群後對大群做群內二次分群(兩層),提高長尾用途的解析度;用新結果更新 `taxonomy-draft.md` 各類別的分群證據,並重發佈檢視 artifact 供裁定時翻閱。全程在 session 暫存區,repo 零新增依賴。

**Blocked by:** None — can start immediately.

**Status:** resolved(2026-09-20)

- [x] 新模型向量與兩層分群完成,與 e5-small 舊結果做一次一致性對照(NMI)記錄於研究報告追記
- [x] taxonomy-draft.md 的 A 群證據編號更新為新分群
- [x] 檢視 artifact 更新(同連結),含兩層分群的子群瀏覽
- [x] 長尾類別(除外/表示形式/傷害等)在二層分群下是否成群,結論寫入草案對應【裁定點】

完成紀錄:multilingual-e5-large 重算新式子集 19,342 條日文向量(CPU,session 暫存區),粗分群 k=48 + 17 個大群二層分群(55 子群);與 e5-small 舊分群 NMI 0.548 記於研究報告追記。長尾結論:除外/表示形式/效果傷害在二層下成群,生命回復/計數器/控制權不成群(維持獨立類別的依據是人工裁定)。快照 `../../effect-tag-research/c-arm-e5large-two-layer.json`;檢視 artifact 同連結更新(含子群瀏覽)。註:實際時序上裁定(票03–06)以既有素材先行、本票素材後到——升級結果與既定裁定無矛盾,供站主覆核與後續期次使用。
