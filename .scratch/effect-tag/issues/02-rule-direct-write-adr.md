# 02 — 規則直貼 ADR

**What to build:** 一份 ADR 記錄「tag 規則層可直接寫入(source=rule)」偏離 ADR-0002(規則僅影子預測)的決策:背景(tag 無官方明示、19,342 條×多標籤全量逐票成本)、取捨(遮蔽測試門檻+首批抽驗+rejudge 對沖錯貼風險)、適用邊界(僅 tag 線;kind 線維持 ADR-0002)。決策內容已於 2026-09-20 訪談定案,本票為落檔。

**Blocked by:** None — can start immediately.

**Status:** resolved(2026-09-20)

- [x] docs/adr/ 新增一篇,格式循既有 ADR
- [x] 明確寫出與 ADR-0002 的關係(補充而非取代)
- [x] 規則敘用門檻(遮蔽 recall+抽驗)寫入決策段

完成紀錄:`docs/adr/0013-tag-rules-write-directly.md`——明確定位為 ADR-0002 的補充(僅 tag 線),敘用門檻(遮蔽錯標 0/recall ≥ 90%/分母 ≥ 8+首批抽驗 50)寫入決策段;門檻數字由裁定批4 定案(rulings.md)。
