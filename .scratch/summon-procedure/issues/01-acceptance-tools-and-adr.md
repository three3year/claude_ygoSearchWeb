# 01: 驗收工具剝框重編,寫 ADR 0019

**What to build:** 召喚手續框出框之前,先讓守門分得出「新加的框」和「既有的框」。剝鍵比對、下游基準(動作對象、回指)、匯出檔比對在比之前都先剝掉位置是召喚手續的框,框序照剩下的重編;匯出檔另剝掉召喚手續框列與目錄列、統計裡新增的召喚手續那一格。現在全語料還沒有召喚手續框,所以三道守門照舊 0 差異,digest 不重凍。同時寫 ADR 0019「召喚手續另出動作框架」。見規格「既有欄位逐位元組不變怎麼驗?」與「要不要寫 ADR?」的決定。工作在新整合分支 `summon-procedure`(基於 `main`)上開始。

**Blocked by:** None (can start immediately)

**Status:** resolved

- [x] 剝框重編是一個共用的接縫(給一筆框架紀錄 → 剝掉召喚手續框、框序重編後的紀錄),剝鍵比對與下游基準都經它;單元測試:手寫一句含召喚手續框的紀錄,剝完的框與框序等於不含它的版本
- [x] 匯出檔比對:剝掉召喚手續框列、目錄列與統計的召喚手續格後,與現行 `data/action_frames.json` 逐句相同(不看版本號);有單元測試
- [x] 現行語料上:剝鍵 digest ok、差異 0;回指、動作對象逐框差異 0;匯出比對 0 差異;都沒有重凍
- [x] ADR 0019 寫明:為什麼不把約束框架直接進索引、為什麼要白名單、為什麼約束框架的手續欄保留不改、同一段卡文有兩種框架表示的取捨;docs/adr 的索引(若有)跟著加
- [x] effect-tokenize 全套通過;機械 lint 通過

## Comments

- 2026-11-03 實作(commit 7367fb0):
  - 接縫 `baseline_diff.strip_procedure(紀錄)`:剝掉 `position == 召喚手續` 的框、框序照剩下的重編,回副本。`baseline_diff.diff`/`stripped_md5` 與 `downstream_baseline` 的 snapshot(patient、anaphora)與 `frame_clauses` 都經它。動作對象是**整句判完才剝**(判定帶 `_verdict` 暫存再剝),召喚手續框若改到同句既有框的判定,patient 尺看得到。位置值 `constraints.POS_PROCEDURE = "召喚手續"` 定在 constraints;**還沒排進 POSITIONS**——排進去會讓匯出的目錄格、統計位置、值域現在就多一格,那是票 02 的事(票 02 加進 POSITIONS 末尾即可,三支工具已讀這個常數)。
  - 匯出檔比對 `export_diff.py`:剝掉召喚手續框列、目錄每列 cards/hash 的召喚手續格、統計.位置的召喚手續格、值域各表的 召喚手續,逐區(值域、目錄、統計位置、卡面、句)比。入版控 `export-digest.json`(tokens.json、cards.json、catalog.json 的 md5 與剝完的 md5;這是新檔,首次凍結,不是重凍);`--baseline P` 可給 `git show main:data/action_frames.json` 存下的檔逐列比。
  - 偏離/解讀:票寫「剝掉…統計裡新增的召喚手續那一格」;匯出統計除了「位置」,還有動作對象的框架、卡、理由等**全部框合計**,召喚手續框進來後必然變、剝不出那一份,所以 `export_diff` 只比 統計.位置,不比其餘統計(逐框的動作對象由 patient 尺在剝框重編後守)。另多剝了值域的 召喚手續(位置值域多一個值是預期的),說明文字也不比。
  - 測試 `test_procedure_strip.py` 14 例(剝框重編 2、剝鍵比對 2、下游基準 3、匯出 strip/diff 3、export_diff CLI 3、全語料 digest 1)。
  - 現行語料(worktree_bootstrap --build 重跑全鏈,入版控產物無變):剝鍵 digest ok(e43cc838…)、patient ok(225c4c7a…)、anaphora ok(dc03f6b9…),都沒重凍;匯出比對 0 差異(對自己凍結的基準與對 `main` 的 `data/action_frames.json` 都是 0)。主 repo 沒有 `baseline/frames.json`、`patient.json`、`anaphora.json`,逐框比對靠 digest 相等(值的 md5 相等即逐框 0 差異)。
  - 對原型驗證:`.scratch/summon-procedure/tools/proto_frames.py` 產出的框架檔(召喚手續框 283 框、271 張)丟進新工具——剝鍵比對 0 差異、剝鍵 md5 相等;patient、anaphora 逐框 0 差異;原型匯出(統計位置 召喚手續 283)與現行匯出比對 0 差異、剝完 md5 相等。沒剝框重編時原型與現行差 31 框框序(規格 Further Notes)。票 02 實作後跑這三道守門應直接 0 差異。
  - ADR `docs/adr/0019-summon-procedure-as-action-frames.md`(形狀照 0018);docs/adr 沒有索引檔。`docs/agents/build-products.md` 加 export-digest 一列、baseline 目錄多 `action_frames.json`、「剝框重編」一節。
  - effect-tokenize 909 OK(skipped 10;前 895)、test_lint OK。
