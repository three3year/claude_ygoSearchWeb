# 07 — §4.1×怪獸 子批 1:密碼升冪前 50 筆改寫進站

**Type:** task(HITL,站主逐行審查)

**Blocked by:** 06

**Status:** open

## Question

首群「僅基礎條目(缺圈號分層 §4.1)× 怪獸」(964 段)的第 1 子批:自重跑後的
三級分類報表取該群卡片,依卡片密碼升冪取前 50 筆,走子批全流程:

1. 依 `docs/text_format_guide.md` §4.1 → §3.x 改寫(日文基底 `faq_info`,
   對照查牌網舊譯互查語意缺漏)。
2. 產完整三欄審查檔(日文原文/查牌網舊譯/新文本+依據條目+判斷點),
   範本 `review-flip-monsters.md`;站主逐行審查、退回的迭代到放行。
3. 放行後寫入 `data/text_rewrites.json`(ticket: text-rewrite#07),重建全站
   全線驗證(照 issue 05 checklist:desc 替換、報表縮減、pending_split 等式、
   前端 ow/tx、tagcard 切句、五套測試全綠)。
4. kind 補判收尾:新句待判佇列清零後,站主明說 commit 才提交。

**首子批額外責任**:確立 §4.1×怪獸群的規範細節——審查中長出的規範追記
`docs/text_format_guide.md`(「審查批改」commit),供同群後續約 19 個子批沿用。

Resolved 後:開子批 2 的票(密碼升冪第 51–100 筆),並把本票答案的規範增補
要點記回 map 的 Decisions so far。
