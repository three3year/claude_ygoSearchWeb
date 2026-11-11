# 08: 收尾

**What to build:** 補票的收尾:前後對比與給站主的短摘要,讓站主接著排查詢篩選欄與前端。

- 前後對比:「前」是里程碑三收尾的產物(9ebd797,與 `action-structure-m3b` 開工時相同),「後」是整合分支的產物;用統計腳本對兩份產物跑(段解析出比例、整張通過張數、只差一種原因的張數、常用動作詞與「反轉」「裝備」的命中與未解析組張數、`m3b_scope.py` 各項)。
- 收尾摘要(審核關卡 md,寫或改之前先用 `review-mirror` skill;放在本資料夾的 report 目錄):
  - 需要站主決定的:各票留下的待裁定事項(沒有就省略這一節)。
  - 待核可的查詢斷言清單(各票 Comments「待站主核可」彙整,一條一行),含因裁定而改的舊斷言。
  - 標「讀法」的實作決定清單(回合方 任一方、「１度、」記在略過文本等查詢與反向檢查驗不到的)。
  - 這輪沒收的寫法與段數(規格「不做的事」加各票回報的)。
  - 重跑方法。
- GLOSSARY:各條目剩下的「m3b(2026-11-11 站主裁定,尚未實作)」標記全部拿掉或改成已實作的描述;規格與 GLOSSARY 的用詞一致。
- 整合分支重建產物與報告,兩次建置逐位元組相同。

- 規格:需要你決定的「怎麼驗收?」;實作決策「反向檢查與報告」「詞彙與文件」;測試決策;使用者故事 41–43、45。
- 前例:里程碑三的票 13 與 `.scratch/action-structure-m3/report/milestone-3-summary.md`(這次的摘要短得多,只報這張補票的範圍)。

**Blocked by:** 01, 02, 03, 04, 05, 06, 07

**Status:** resolved

- [x] 里程碑一到三的標準卡測試與已核可的斷言:因這份規格的裁定而改的逐條列進摘要,其餘全部照舊通過
- [x] 各規則票「改前通過反向檢查、改後不通過」的張數彙整在摘要(應為 0;有例外的逐張列出)
- [x] 前後對比的數字都來自實跑,每項附出處指令
- [x] 整合分支重建產物與報告,兩次建置逐位元組相同
- [x] 收尾摘要寫成、鏡像發布,網址記在 report 目錄的 mirrors.json
- [ ] (站主)核可待核可的查詢斷言清單與標「讀法」的實作決定
- [x] GLOSSARY 沒有剩下的「尚未實作」標記

## Comments

### 實作紀錄(2026-11-11,分支 as/08)

- 摘要正本:`.scratch/action-structure-m3b/report/m3b-summary.md`(審核關卡;照 `review-mirror` 寫,`cli.mjs` 無錯)。鏡像 https://claude.ai/artifact/As1feTkr1ENH9cw1Y8qMMf ,記在同目錄 `mirrors.json`。
- 摘要「需要你決定的」8 題:アドバンス・ディボーター 右半記成此卡(票 04)、墓守の大神官 兩框沒過(票 04)、不帶讀點的「自分・相手ターンに」用合成卡驗(票 01)、「表側表示で召喚できる」框改用 享楽の堕天使(票 07)、票 01 原因槽多收的寫法、封神鏡 推得的手牌照舊標取對象(票 07)、替代標準卡、斷言與讀法怎麼核。
- 產物:整合分支 cb6f45c 的程式重建兩次(`build_structure.py`、`build_report.py`、`build_reverse_check.py`),`data/action_structure.json`、`coverage.md`、`reverse_check.md` 兩次逐位元組相同,也與 cb6f45c 已 commit 的產物相同(報告在工作樹只有換行字元的差,內容相同)。本票不改程式,產物與報告不 commit。
- 回歸(前 = 9ebd797 解出的根,後 = cb6f45c;`passdump.py` + `regress.py`,輸出 `stats/m3b_regress.txt`):改前通過、改後不通過 **0 張**;改前不通過、改後通過 350 張,等於票 01–07 Comments 各自回報之和(43 + 116 + 177 + 1 + 3 + 9 + 1)。
- 測試(cb6f45c 實跑):action_structure 921、card_list 66、faq_info 43、tag_card 379、text_format 55、text_glossary 37、web 104,`node --test` 121,全綠。
- 里程碑一、二:`.scratch/action-structure-m2/stats/golden_check.py` 171 個測試失敗 0,18 張全庫產物上全部通過(`stats/m2_golden_check_after.txt`);里程碑二 74 條斷言所在的九個測試檔從 834f518 起沒有改動。里程碑三:`m3_golden_check.py` 收尾 2 / 2、替代 29 / 29 照舊,候選 6 → 7 / 35(TG ワーウルフ 新通過;`stats/m3_golden_check_after.txt`)。
- 因裁定而改的舊斷言 2 條(票 01 `WakeCupKuroTest`、票 07 `test_crystal_core_cannot_remove_condition`),摘要逐條列出;既有測試檔另外只有票 03 改了 `TgWerewolfTest` 兩個 docstring(`git diff 62a3bb0 HEAD` 對既有測試檔只有這三處)。
- GLOSSARY:「尚未實作」0 處;規格〔詞彙〕點名的 13 段都已是已實作的描述。本票沒改 GLOSSARY。

新增的統計(都在 `stats/`,輸出決定性):

- `m3b_compare.py <根>`:跑里程碑三的 `m3_compare.py` 再加補票牽動的查詢(反轉、裝備各種、選択して、推得、取り除けない)。輸出 `m3b_compare_before.txt`(前 109 行與 `m3_compare_after.txt` 逐行相同)、`m3b_compare_after.txt`。
- `m3b_scope_after.txt`:`m3b_scope.py` 在 cb6f45c 的輸出;在 9ebd797 的根重跑與 `m3b_scope.txt` 逐行相同。
- `c7_clause_fronts_before.txt`、`_after.txt`:認不得的前文 2,149 → 1,837 處。
- `m3b_golden_check.py`:各票候選、替代、另寫斷言的卡整張通不通過(`m3b_golden_check.txt`;候選 3 / 32、替代 14 / 14、其他 4 / 11)。

前後(前 = 9ebd797,後 = cb6f45c):段 65,282 → 65,401;段解析出 42,066(64.4%)→ 43,316(66.2%);反向檢查通過段 38,948 → 40,170;字面不符 1 → 0;整張通過 2,432 → 2,782;只差一種原因 5,360 → 5,324;查「反轉」開條件段 不認得 → 294 張;查「裝備」149 → 223 張、未解析組 596 → 520 張。全表在摘要「主要數字」。

沒勾的框:只有(站主)那一格。
