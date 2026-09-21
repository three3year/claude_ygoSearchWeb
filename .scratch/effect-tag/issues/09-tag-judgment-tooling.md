# 09 — tag 判定票工具+首批長尾判定

**What to build:** 判定票三支的 tag 系列:出票(入選=kind 已定、tags 未貼、屬當期類別;批次檔攜帶體系定稿、kind、RESULT_FORMAT 新版)、收票(三道關卡語意沿用:集合一致性、對得回效果句、改判旗標對帳)、tag 判定規範首版(仿效果類型判別規範形狀)。用規則未命中的區域移動句跑首小批 LLM 判定並收票進資料。

**Blocked by:** 07 — schema 與管線就緒。

**Status:** resolved(2026-09-20)

- [x] 出票/收票行為測試(少一筆多一筆指名道姓;tags 不隨 kind 改判消失)
- [x] rejudge 流程對 tag 可用
- [x] 首小批(約 200 句)判定收票進版
- [x] 判定規範首版供批次檔引用

完成紀錄:`make_tag_batches.py`(tag-<類別>/timing 兩系列,批次自帶體系與規則指紋+RESULT_FORMAT)、`merge_tag_judgments.py`(三道關卡:集合一致指名道姓、值全在正典、對得回效果句;rejudge 旗標雙向對帳)、判定規範 `docs/effect_tag_guide.md` 首版。首批 tag-mv-01(144 條,寫入 93 tag、判空 83)與 timing-01(4 條)已收票進版,關卡 0 問題。
