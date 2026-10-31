# 01: 基準凍結與驗收工具

**What to build:** 站主在改讀之前就有三把尺:全語料每個動作框架的動作對象(判定值, 理由)凍結成基準檔,改讀後逐框比對、列出差異的卡與前後值;回指欄(既有鍵)逐框比對工具,沿用剝鍵基準的做法但比的是整個回指欄,差異逐卡列出、確認後可重新凍結;舊匯出檔 `data/action_categories.json` 逐位元組不變寫成測試(過渡期的守門)。三個檢查在現況全部通過;缺輸入(語料、基準檔)時 skipTest 並印原因。

**Blocked by:** None (can start immediately)

**Status:** resolved

- [x] 動作對象基準:凍結指令、比對測試、差異清單(卡片密碼、句、框、原文、前後值與理由)
- [x] 回指欄比對:逐框比對工具與測試、重新凍結指令;現況差異 0
- [x] 舊匯出檔逐位元組不變的測試;現況通過
- [x] 建置產物文件加基準檔與重生指令
- [x] 既有全部測試照過

## Comments

- 2026-11-01 實作(分支 wt/01-baseline,基於 966d798):全部在 `.scratch/effect-tokenize/`。**`downstream_baseline.py`**——三把尺一個模組,尺名就是 CLI 子命令與常數:`PATIENT`="patient"(每個動作框架的動作對象 `{"mode": 此卡|非此卡|None, "why": 理由}`,由 `patient.judge_sentence` 逐句判、帶 `data/cards.json` 的卡面;條件位的框架也判,約束框架不在基準裡)、`ANAPHORA`="anaphora"(每個動作框架的整個回指欄 dict,含新子鍵 moving,沒有就是 None)、`EXPORT_RULER`="export"(`data/action_categories.json` 整檔 md5)。函式:`snapshot(尺, records, faces=None)` → `{(卡號, 段落, 句序, 框序): 值}`;`current_snapshot(尺, loc, records=None)` 讀現在的 frames.json(與卡面);`diff(base, cur, clauses=None, why_aliases=WHY_ALIASES)` → `[(卡號, 段落, 句序, 框序, 子句字面, 基準值, 現值)]`(一邊沒有的框記 `MISSING`,回指欄的 None 是正常值要分得開);`frame_clauses(records)` 給差異清單的原文欄;`freeze(尺, loc)` 寫 `baseline/<尺>.json`(gitignore,一列一框)與入版控的 `<尺>-digest.json`(tokens.json 與 cards.json 的 md5、值的 md5;export 尺記檔的 md5);`check_digest(尺, loc, records=None)` → `(ok|mismatch|skip, 說明)`(語料或卡面變了 skip 並要求 `--freeze`,沒變時 md5 要同);`load_baseline(尺, loc)`;`Locations(frames, tokens, cards, export, baseline_dir, digest_dir)` 換路徑(測試用暫存目錄),預設 `DEFAULT`。**理由碼對照表 `WHY_ALIASES`**(模組頂,舊 → 新,現在空):票 02 改讀後理由名跟著變時填它,diff 把基準值換過再比,基準不必重凍。CLI:`PYTHONIOENCODING=utf-8 python .scratch/effect-tokenize/downstream_baseline.py <patient|anaphora|export> [--freeze] [--limit N]`——不帶 `--freeze` 先印 digest 守門、有基準檔再逐框列差異(卡 密碼 段落/句序 框 框序「子句」:基準 → 現在),差異非 0 或 mismatch 時 exit 1;`--freeze` 只在逐卡確認差異是要的之後。
- 「動作對象現在在哪算」:只有 `export_categories.export()` 呼叫 `patient.judge_sentence(s["frames"], faces.get(card), section)`,統計只記帶葉的效果位/代價位框架;本票的基準凍結**全部** 46,732 個動作框架(含條件位、未歸葉的),是匯出統計的超集——改讀後任何位置的判定變了都看得到。
- **舊匯出檔的守門怎麼比**(寫在測試 docstring):比入版控的 `export-digest.json` 記的 md5,不比 git HEAD 的 blob——HEAD 在工作樹是本票分支、合併後是合併點,誰不小心把改了的檔 commit 進去,HEAD 比對就跟著過;digest 要有人刻意 `--freeze` 才會動。語料或卡面變了(新卡)時略過並要求重新凍結。
- 測試 `test_downstream_baseline.py`(16 條,開新檔不碰 test_frames.py):單元 10 條(snapshot 兩把尺、diff 的相同/改值/缺框/理由別名、freeze → check ok / 改值 mismatch / 改語料 skip / 缺 digest skip、CLI exit code)用手寫小框架與暫存目錄;全語料 `TestCorpus` 5 條(patient 逐框差異 0、patient digest、anaphora 逐框差異 0、anaphora digest、舊匯出檔 md5),frames.json 不在整類略過、基準檔不在只略過逐框比對(digest 守門仍在)、語料變了 digest 略過並印原因。
- **全語料數字**(frames.json md5 3c4247ab5410fc85dd0a853322d59b43,與整合分支相同):動作框架 46,732——動作對象 此卡 8,806、非此卡 23,211、皆非 14,715,理由 51 種;回指欄有值 5,054 框(moving 真 343);三把尺現況:patient 差異 0、anaphora 差異 0、export md5 01b9d071f1ebaed795881e8f1aa994af 與 HEAD 相同。digest:patient values_md5 e27d4fa72db2c80c50b943d3f8d30f8f、anaphora values_md5 6536cac4ae4e7e5727227c2bdb1a82a2(tokens 0c24c7defae6087cc5059497f77c555e、cards 98d3c3f61f5e99ff54248af295a373ea)。`baseline_diff.py` 剝鍵差異 0、底線鍵 0、digest ok;categories.py → export_categories.py 重跑後 `git diff data/` 為空。
- 文件:`docs/agents/build-products.md` 表加三個 digest 與重生指令、建置輸入段加 `baseline/patient.json`/`anaphora.json`、新段「下游基準」(尺的表、比對與重新凍結的做法)。**順手修一處**:`script/dev/worktree_bootstrap.py` 在這台機器直接炸(路徑含中文,`text=True` 用 cp950 解 git 輸出 → UnicodeDecodeError),改 `encoding="utf-8"`;之前的票能跑大概是環境有 PYTHONUTF8。
- 測試:effect-tokenize 全套 886 條(870 + 16)、node 172、script/* 五套 66/43/469/55/136 全過(含 test_lint)。
- **給票 02/04 的接點**:改讀前先確認 `downstream_baseline.py patient`/`anaphora` 差異 0(基準檔由 `worktree_bootstrap.py` 從主 repo 的 `baseline/` 複製;主 repo 沒有時在改讀前的程式上 `--freeze` 一次,digest 會對);改讀後跑同一指令看差異清單、逐卡判「更對」才留、確認後 `--freeze` 重凍並把數字寫進 Comments;理由碼改名填 `WHY_ALIASES`;舊匯出檔過渡期不該動,`export` 尺 mismatch 就是動到了。基準檔 `baseline/patient.json`(3.2MB)、`baseline/anaphora.json`(2.1MB)已複製進主 repo 的 `.scratch/effect-tokenize/baseline/`(gitignore)供平行票 bootstrap。
- 未決:無。假設:基準凍結全部動作框架(含條件位)而不只匯出統計的那些——票面寫「每個動作框架」,照字面。
