# 04: 拆解頁與報表分得出召喚手續

**What to build:** 看卡片拆解時,召喚手續框不再被畫成效果:拆解頁的框架列給召喚手續自己的樣式與圖例。分詞報表、建置報告、目錄命中報表凡是逐位置列的都多一欄召喚手續,寫死 代價/效果/條件 三欄的那幾行改成照位置清單。見規格「拆解頁與報表」。

**Blocked by:** 02

**Status:** resolved

- [x] 拆解頁接縫(拆解頁資料與既有的 viewer 測試):召喚手續框的位置值帶到頁面,樣式與圖例和三個既有位置分得開;既有三個位置的樣式不變
- [x] 拆解頁重發後,毀滅的黑魔術師那張的召喚條件句顯示 除外 召喚手續框(真 Chrome 截一張圖附進 Comments)——本機重產頁面截圖;artifact 照原網址重發留到票 03 合入後,見 Comments
- [x] 分詞報表的位置那一行、建置報告、目錄命中報表的位置分項都有召喚手續一欄,數字與匯出統計相同(召喚手續 283)
- [x] 報表不再有寫死三個位置的字串(全文搜「三個位置」「代價/效果/條件」,剩下的逐一說明為何保留)
- [x] effect-tokenize、script 全套通過

## Comments

- 2026-11-03 實作(分支 wt/04-viewer-reports):
  - **位置順序**:新接縫 `report.position_items(位置 Counter) → [(位置, 框數)]`,照 `constraints.POSITIONS` 排、沒有框的位置記 0。分詞報表「位置分佈」(`report.frames_section`)與拆解頁覆蓋分頁(`prepare_view` 的 `position`)原本用字串排序(召喚手續會排第二),兩處都改讀它。report.md 該行現在是「代價 3,734、效果 26,687、條件 16,311、召喚手續 283」(原本是「代價 3,734、召喚手續 283、效果 26,687、條件 16,311」)。
  - **片語報表那一行**(`phrases.quantity_section`):寫死的三格改成照 `position_items` 迭代;report.md「數量各類框數」現在是「帶數量的動作框架 16,107(代價 2,061、效果 9,570、條件 4,322、召喚手續 154)」——合計 16,107 原本就含這 154 框,只是那一行沒列出來。`phrases.py` 不再 import 三個位置常數。
  - **具名查詢小節**(`report.queries_section`):說明的「三個位置都算」改成「每個位置(代價、效果、條件、召喚手續)都算」(由 POSITIONS 組字);「不留(三個位置都沒命中)」改「不留(每個位置都沒命中)」,`test_09_viewer` 兩條斷言跟著改。分佈表與動作對象表本來就照 POSITIONS,已有召喚手續一欄。
  - **拆解頁**(`viewer.html`):新色票 `--chip-proc-bg/ink`(淺 #F4E6F0/#93406F、深 #3A2433/#E2A0C8,四組主題都定義)、`.f-proc`、圖例在「條件」之後多一顆「召喚手續」;`posChip` 改讀 `POS_CHIP` 表(代價 f-cost、效果 f-eff、條件 f-cond、召喚手續 f-proc),既有三個位置的樣式不變。另修兩處**功能性**寫死(探索筆記指出、規格沒點名):具名查詢總覽的合計原本寫死索引 3(位置變四個後會拿到召喚手續的數),改成 `POS.length`;總覽樹 grid 寫死 6 欄,改成 `repeat(var(--npos),92px)`,`.ctree` 帶 `--npos`。說明文字的位置清單改成四個(見下)。
  - **建置報告**(`export_frames.py` 的 stdout)與**目錄命中報表**(`catalog_hits.py` 的 stdout)票 02 已改成照 POSITIONS,本票沒動程式,只實跑核對:建置報告「框列 47015(代價 3734、效果 26687、條件 16311、召喚手續 283)」「具名查詢各位置的張數合計:代價 6324、效果 48352、條件 11532、召喚手續 495」;目錄命中報表「命中任一具名查詢的 40737(代價 3728、效果 26384、條件 10342、召喚手續 283)」。召喚手續 283 與匯出統計相同。票 03 會在建置報告加發動位置來源分項,本票沒碰 export_frames.py。
  - **docstring**:`prepare_view.py`(總覽註解、`query_overview`)、`report.py`(檔頭、`position_table`、`queries_section`)、`manner.py`、`negation.py` 的「三個位置」「(代價/效果/條件)」改成「各位置」「照位置清單」。
  - **全文搜「三個位置」「代價/效果/條件」剩下的**(排除 issues、規格、地圖、工具結果、產物):
    - `viewer.html` 兩處說明(頁頭 `<p>` 與卡片拆解說明)列的是「代價/效果/條件/召喚手續」四個值的完整清單,不是寫死三個;頁頭是靜態 HTML,沒有資料可迭代,保留。
    - `catalog_hits.py:18`、`export_frames.py:24`、`frames.py:27` 同上,是四值清單(票 02 已改)。
    - `frames.py:1506` 註解「不經代價/效果/條件的判定」——說的就是那三個值的判定規則,召喚手續不走它,保留。
    - `test_frames.py:80`(票 06 的位置判定例子,只涉三個值)、`test_04_patient.py:57`(動作對象現行規則只看三個位置,票 03 範圍)保留。
    - `script/web/field-pairs.test.js:127,330`(測試名,按亮三顆的情境)、`.scratch/drawer-lock/tools/lock_stats.js:6`(舊工具註解)、`summon-procedure/tools/proto_export.py:45`(原型工具,比的就是三個舊位置)保留。
    - `viewer.html` 施事者 title「代價/效果位的他動框架預設發動者 自分」與 `agent.py:19,206` 的同義說明:用驗收字串搜不到,屬施事者規則,票 03 改規則時一起改,本票沒動。
  - **測試**:新檔 `test_procedure_reports.py` 8 例——`position_items` 召喚手續最後、無框記 0;`quantity_section` 那一行四格;`queries_section` 分佈表/動作對象表的召喚手續欄、說明不含「三個位置」;`frame_row` 帶位置 召喚手續;`query_overview` 的 positions 末位是召喚手續、節點列 [代價, 效果, 條件, 召喚手續, 合計]、hits 有召喚手續、分片列照帶;`viewer.html` 圖例每個位置一顆 chip、樣式各不相同且 CSS 有定義。`test_09_viewer` 只改「不留」字串與 docstring。
  - **真 Chrome**(`node .scratch/summon-procedure/tools/viewer_shot.js`,headless,CDP,零依賴;結果 `.scratch/summon-procedure/tools/results/viewer_shot.txt`):卡片拆解打 59400890,效果外文本 0-2 的框架表第 5 列「召喚手續 · 除外 · 區域移動 › 除外 …· 非此卡 · レベル6以上の魔法使い族・闇属性モンスター1体 · 自分フィールド」,chip 是 f-proc、沒有落到 f-eff 的召喚手續 chip;四個位置 chip 底色各不相同;圖例有召喚手續;具名查詢總覽表頭 節點|代價|效果|條件|召喚手續|合計、目錄列 7 格同一行、合計格是聯集(召喚 7,297);console 錯誤 0、違規 0。截圖:`.scratch/summon-procedure/tools/results/viewer_59400890_procedure.png`(召喚條件句那一塊;截圖時工具裡放開 `.wrap` 的 1060px 限寬,不然 17 欄的框架表擠成直排——頁面本身沒改)、`viewer_overview_tree.png`(總覽樹)。
  - **沒重發 artifact**:拆解頁的發布先例是照原網址(`.scratch/effect-tokenize/mirrors.json` 的 viewer.html)publish `viewer.html` 帶 `view_data.js`、`view_frames_0〜11.js`、`view_queries_0〜3.js`(現在 86MB,要分兩次)。票 03 同時在改施事者/動作對象(拆解頁會顯示的值),還沒合進 summon-procedure;現在發會發出票 03 之前的值,所以本票只在本機重產頁面截圖,重發留到票 03 合入後一次做。
  - **數字**:effect-tokenize 926 OK(skipped 3;前 918 + 本票 8);script card_list、faq_info、tag_card、text_format、web 169 全 OK;node `script/web/*.test.js` 411 pass / 0 fail。重生 report.md(只有上述 4 行變);匯出檔重跑內容不變。
