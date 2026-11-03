# 06: 交件

**What to build:** 站主在真瀏覽器裡查得到寫在召喚條件裡的動作。真 Chrome 桌面與手機寬(390 px)各走一輪:從目錄加「除外」標籤、打開抽屜按亮位置的召喚手續,毀滅的黑魔術師在結果裡,命中句是召喚條件那句、標「召喚手續:」;只按亮召喚手續、關掉效果的查詢貼網址重開不變;新加的標籤預設只看效果;console 錯誤 0、版面違規 0。全套測試重跑,寫交件註記。見規格「Testing Decisions」的真瀏覽器一條。

**Blocked by:** 04, 05

**Status:** resolved

- [x] 真 Chrome 桌面與手機寬各走一輪,上述每一步通過;截圖或腳本輸出附進 Comments(先例:drawer-lock 票 04 的瀏覽器走查工具)
- [x] 舊網址(交件前 main 上任取幾個,含 位置 參數的)查到的卡與 main 相同——955 條中 953 條相同;2 條不同是票 05 的抽取修正(儀式召喚 條件位多 32354768),不是網址讀法變,見 Comments
- [x] 分詞鏈全鏈、網站建置 exit 0;effect-tokenize、script、node 全套通過;剝框重編後各守門 0 差異
- [x] 交件註記:召喚手續框數、張數、動作對象分佈、抽驗結果、目錄有召喚手續張數的列,各附出處;規格 Further Notes 數字若有變動,在規格補一行更正(註日期與出處)

## Comments

2026-11-04 交件(基準 summon-procedure 07f6e95;工作樹 `worktree_bootstrap.py --build` 複製建置輸入,另跑 `run_chain.py`(含 `catalog_hits.py`)與 `build_index.py`)。

### 摘要

- 真 Chrome 桌面 1400×1000 與手機 390×844 各一輪,每一步都過:**版面違規 0、console 錯誤 0、違規 0**。前端程式沒改,沒走出 bug。
- 舊網址:main(4627bd2)產生的 955 條網址在本分支讀進來,953 條卡片、命中句、正規網址、讀進來的位置都相同;2 條不同,成因是票 05 的抽取修正(見下),不是網址讀法變。
- 入版控的建置產物重跑全部不變(`data/action_frames.json`、`web/data.js`「內容沒變,不動」、`report.md`)。
- 新工具三支(本功能 `tools/`):`procedure_browser.js`(真 Chrome 走查,版面自己量)、`old_urls.js`(舊網址比對)、`handoff_stats.py`(交件數字)。
- 規格 Further Notes 補兩條:數字更正(票 05 之後)與交件註記;規格鏡像、拆解頁、檢驗摘要鏡像都照原網址重發(見「鏡像」)。

### 全套測試

| 項目 | 結果 |
|---|---|
| node `script/web/*.test.js` | **411 pass / 0 fail / 0 skip**,約 41 秒 |
| effect-tokenize 全套(含 test_lint) | **948 OK、skip 3**:同票 02〜04,本工作樹沒有 `baseline/frames.json`、`patient.json`、`anaphora.json`(主 repo 也沒有),逐框比對略過,digest 守門照跑(票 05 的 skip 1 是因為重凍時在它的工作樹寫出了 patient/anaphora 基準檔) |
| `script/*` 五套 | card_list 66、faq_info 43、tag_card 469、text_format 55、web 169,全 OK |
| 全鏈 `run_chain.py` / 網站建置 `build_index.py` | exit 0 / exit 0(全部檢查通過、內容沒變不動) |

### 守門(剝框重編後)

| 守門 | 結果 |
|---|---|
| 剝鍵 `baseline_diff.py` | digest ok(79a014c97f153350c145e8d21410ef2f,票 05 重凍值) |
| 下游基準 patient / anaphora | digest ok(4e6d5485cdad2152de3bfd811b6f207d / e069229e10ea0cc8f0bcef641ec0c23a) |
| 匯出 `export_diff.py` | digest ok(d05a4dbe6452679d1e7f94f4bcaf64c6) |
| 匯出對 main(`git show 4627bd2:data/action_frames.json`,剝召喚手續後) | 8 處,全是票 05 Comments 逐框列過的變動:目錄 儀式召喚 條件 34 → 35、統計.位置 條件 16,311 → 16,312、句 22916418 ③、31411835 ②、32354768 ②、43932352 ①、45951104 ①、49604192 ① |

### 交件數字(各附出處)

- **召喚手續框 283 框、271 張**;詞元 リリース 78、除外 68、重ねる 68、送る 37、戻す 19、捨てる 7、取り除く 3、見せる 2、払う 1;**施事者 自分 283**;**動作對象 非此卡 208、此卡 68、皆非 7**;結構化區域有值 187、空 96;統計.位置 代價 3,734、效果 26,687、條件 16,312、召喚手續 283(`python -X utf8 .scratch/summon-procedure/tools/handoff_stats.py` 讀 `data/action_frames.json`,`tools/results/handoff_stats.txt`)。
- **目錄**:237 個具名查詢中 **26 列**在召喚手續有張數,效果位 0 張的 0 列;リリース 77(效果 170)、除外 68(982)、重ねる 68(137)、除外←墓地 49、送る 37、送る:フィールド→墓地 36、除外←フィールド 33、除外←手札 23、戻す 19、戻す→デッキ 18、送る:手札→墓地 14、戻す:フィールド→デッキ 10、戻す:墓地→デッキ 8、戻す→EXデッキ 8、捨てる 7、戻す:除外→デッキ 3、取り除く 3、取り除く:X素材 3、除外←EXデッキ 2、見せる 2、見せる@手札 2、払う 1、送る:デッキ→墓地 1、除外←デッキ 1、取り除く@フィールド 1、取り除く@自分フィールド 1;大類 區域移動 207、素材 68(同上檔)。
- **手續步驟**:召喚條件框 737、519 張;手續非空 304 框、304 張、**339 步**、**19 種動作**(`proc_stats.py` 重跑,`tools/results/proc_stats_handoff.txt`;規格原數字的 `proc_stats.txt` 保留,差在 10000080 多 召喚、16306932 多 P召喚 兩步)。
- **LLM 抽驗**(票 05):304 句/304 張全數;round1 47 筆(33 框、33 張;規則 32、抽取 15)→ 修兩型抽取後同批 round2 **42 筆(32 框、32 張、10.5%;規則 34、抽取 8)**,新冒出 0;多出、詞元錯 0(`.scratch/effect-tokenize/llm-check/procedure-round2/report.md`)。沒修的兩題在 summary.md「需要你決定的」。

### 真 Chrome(`node .scratch/summon-procedure/tools/procedure_browser.js both <main 的匯出目錄>`;headless 真 Chrome,CDP 真輸入)

做法:骨架照 drawer-lock 票 04 的 `drawer_browser.js`(純 CDP、零依賴;桌面真滑鼠、手機觸控 tap,點前捲到中央、`elementFromPoint` 確認點得到)。手機先按「篩選條件」打開側欄再用目錄過濾框。結果 `tools/results/procedure_browser.txt`;截圖用 `Page.captureScreenshot`:`procedure_desktop_drawer.png`、`procedure_desktop_card.png`、`procedure_phone_drawer.png`、`procedure_phone_card.png`(只留召喚手續時的抽屜,與 59400890 的召喚條件句)。

| 步驟 | 桌面 | 手機 |
|---|---|---|
| 目錄過濾框打 除外、點 區域移動›除外 | 網址只寫葉路徑 `#act=區域移動›除外`、982 張 | 同 |
| 新標籤的抽屜位置欄 | 代價 [效果·最後一個] 條件 召喚手續(四顆、只亮效果) | 同 |
| 按亮 召喚手續 | 1,029 張、條件列「效果或召喚手續位 除外」、網址 `詞元:除外;位置:效果~召喚手續;極性:肯定~可能`;翻到第 5 頁找到 59400890,命中句 #1(召喚條件)句尾「召喚手續:除外」 | 同 |
| 關掉 效果 | 68 張、[召喚手續·最後一個]、條件列「召喚手續位 除外」、網址 `#act=詞元:除外;位置:召喚手續;極性:肯定~可能`;59400890 在第 1 頁,命中句只有召喚條件那句、句尾「召喚手續:除外」 | 同 |
| 貼網址重開 | 網址、條件列、68 張、命中句與句尾、位置欄都不變 | 同 |
| 再從目錄加 リリース | 原標籤仍「召喚手續位 除外」;リリース 新標籤位置欄只亮效果 | 同 |
| 版面違規 / console 錯誤 | 0 / 0 | 0 / 0 |

**版面怎麼量**(先例工具沒量,本票自己加):每個狀態(首頁、抽屜打開、按亮召喚手續、結果頁、只留召喚手續、重開後、加 リリース)量——頁面 `scrollWidth − clientWidth`;`#condStrip`、`#condDrawer`、`#results` 的橫向溢出;body 底下每個看得見的元素左右緣超出視埠(被某個 overflow 不是 visible、且自己在視埠內的祖先裁住的不算);命中句的句尾標籤超出所在卡片。每種寬度開頭先塞一個兩倍視埠寬的塊做**量法自檢**:兩種寬度都量到 3 處(頁面溢出、#results 溢出、該塊超出視埠),量完拿掉,證明這把尺量得到。

**舊網址在瀏覽器**:同一支 Chrome 開 main 匯出的 `web/index.html` 與本分支的,四條舊網址(`詞元:破壊;位置:代價~效果;極性:肯定~可能;動作對象:非此卡`、`詞元:除外;位置:效果~條件`、`詞元:リリース;位置:代價~效果~條件`、葉路徑 `區域移動›除外`)張數、條件列、第一頁卡片都相同(1,182/1,106/762/982 張),console 0。

每種寬度約 5 秒。

### 舊網址比對(`node .scratch/summon-procedure/tools/old_urls.js <main 的匯出目錄>`,`tools/results/old_urls.txt`)

main 的匯出目錄:`git archive 4627bd2 web script/web/frontend_harness.js` 解到 session scratchpad。兩邊各載自己的 `frontend_harness.js`(依 index.html 順序載真前端碼與各自的真 data.js),對同一批網址跑 `Hash.parse → Cond.toQuery → Engine.runQuery`,逐網址比卡片密碼、每張卡的命中句索引、`Hash.canon` 與讀進來的位置。網址用 main 的 `Hash.stringify` 產生:目錄 237 個具名查詢 × {只寫路徑、位置:代價~效果~條件、位置:條件、排除},另手寫 7 條(欄位對含 動作對象、OR 區、排除、沒寫位置)——共 955 條,含位置參數(欄位對寫法)479 條,main 查到 0 張的 119 條照樣比。

結果:953 條相同;不同 2 條,都是 儀式召喚:

| 網址 | main | 分支 | 成因 |
|---|---|---|---|
| `act=詞元:儀式召喚;位置:代價~效果~條件;極性:肯定~可能` | 109 張 | 110 張(多 32354768) | 票 05 修「…に召喚、または…」的召喚連用中止後,32354768 ②「以下のモンスターを、「セフィラ」モンスターを使用して儀式召喚、または…特殊召喚した時」多一個條件位 儀式召喚 框(票 05 Comments「新增 1 框」;目錄 儀式召喚 條件位 34 → 35) |
| `act=詞元:儀式召喚;位置:條件;極性:肯定~可能` | 34 張 | 35 張(多 32354768) | 同上 |

兩條的讀進來的位置與正規網址兩邊相同,其餘卡的命中句也相同,所以不同的只是資料多一框,不是網址讀法。工具把這一筆列成已說明的差異(`KNOWN`),沒有說明的不同 0 條、exit 0。

### 鏡像

- **拆解頁**照原網址重發 https://claude.ai/artifact/SSvzzZPLJcZsVLewfm3Htx (`.scratch/effect-tokenize/mirrors.json`):本工作樹 `report.py`、`prepare_view.py` 重產後,先例(named-queries 票 11)分兩次——Version 74 `viewer.html`+`view_data.js`+`view_frames_0〜9.js`、Version 75 `view_frames_10〜11.js`+`view_queries_0〜3.js`;發布後 files 清單 18 檔齊、大小與本機逐檔相同。這一版帶票 03(施事者、動作對象、發動位置)、票 04(召喚手續樣式與圖例、總覽四位置)、票 05(抽取修正、檢驗摘要分頁讀新的 summary.md)。發布前 `viewer_shot.js` 對現行資料重跑:59400890 召喚手續 除外 chip f-proc、總覽 召喚 條件 1,931(票 04 時 1,930,差的是票 05 新增的 32354768 儀式召喚 框)、console 0、違規 0,結果檔與兩張截圖跟著更新。
- **檢驗摘要**(`llm-check/summary.md`,票 05 留給本票)照原網址重發 https://claude.ai/artifact/K9v5rfWiXgSdTgPgs83PpK Version 32(`review-mirror` 的 `cli.mjs` 從正本產生)。
- **規格**補兩條後照原網址重發 https://claude.ai/artifact/QNxdyribKJh8MF4PNxwYLP Version 3(同上做法;`.scratch/summon-procedure/mirrors.json` 網址不變)。

### 沒驗到的

只有 Chrome headless,沒開 Firefox、Safari;手機是模擬(觸控與裝置尺寸),不是真手機。舊網址只比了 main 能產生的網址形狀(目錄列 × 三種位置寫法、排除、7 條手寫),不是真的被分享出去的網址;瀏覽器裡只並排看了四條的第一頁。拆解頁重發後沒在 claude.ai 上開來看,只核對 files 清單與大小。
