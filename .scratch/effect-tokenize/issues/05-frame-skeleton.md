# 05 — 框架抽取骨架:單動作句從原文到拆解頁

**What to build:** 站主打開檢視頁的「卡片拆解」分頁,找到一張只有簡單效果句的卡(一個動詞、論元是 を/から/に、位置是效果,例:デッキから「X」１体を手札に加える。),就看到原文旁邊列出這句的[[動作框架]]——動作(詞元)、對象、來源、目的、位置。框架抽取接在分詞鏈之後,決定性重跑,同時顯示框架覆蓋率(有抽到動作的句子比例)當參考數字。這是規格 04 的 tracer bullet:抽取、資料、檢視頁、測試一條路走通,後續票都在這條路上擴。

**Blocked by:** None — can start immediately(規格見 04)

**Status:** resolved

- [x] 唯一測試接縫「一句效果文原文(帶同卡同段上文)→ 動作框架清單」建立,用真的分詞器與詞典,只斷言框架輸出;沿用專案 unittest 寫法
- [x] 第一批回歸例子通過:單動作檢索(デッキから…手札に加える)、墓地へ送る(動作=送る、目的=墓地)、を+動詞 的單動作句
- [x] 框架欄位第一版:卡號、效果段落位置、句序、框架序、動作(詞元)、對象、來源、目的、位置、極性、對應詞序列範圍
- [x] 框架抽取併入分詞鏈重跑,輸出建置產物(決定性、不入版控)
- [x] 檢視頁新增最小版「卡片拆解」分頁:輸入卡號看原文與框架
- [x] 報表/檢視頁顯示框架覆蓋率

## 追記(2026-10-09 實作完成)

- `frames.py`:接縫 `extract(text, context)`(內部呼叫真的分詞器與 lexicon.json),
  批次 `main()` 讀 tokens.json → `frames.json`(建置產物,.gitignore);
  `test_frames.py` 沿用 unittest,`python -m unittest discover -s .scratch/effect-tokenize`。
- 框架欄位:action(詞元)、object/source/goal、position(代價/效果/條件)、
  polarity(肯定/否定/可能)、sentence(。句序)、span(詞序列範圍)、clause(子句字面);
  批次輸出另帶 card/section/index/stratum/order。
- 詞典:既有無 lemma 的動詞/補助動詞詞形補 lemma(extract_seed.py 的
  FRAME_LEMMA_SUPPLEMENT,49 條;只補欄位、ID 不動)。分詞器修一處:數量約束的前詞
  不綁純平假名功能詞(合わせ|て|１００００以上 原把 て 綁進 q:)。
- 分詞鏈順序:extract_seed → tokenize → frames → report → prepare_view;
  report.md 新增「動作框架覆蓋率」節;檢視頁新增「卡片拆解」「框架覆蓋與盲區」
  兩分頁(逐卡資料分 12 片 view_frames_<k>.js 按需載入,純 ASCII)。
- 覆蓋率(第一版規則):效果句 99.97%、效果外 78.34%(素材行沒有述語);框架 54,747。
