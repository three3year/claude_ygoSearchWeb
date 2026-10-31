# Coding standards(給審查者)

審查時逐條對 diff;每條附範本檔,「像範本一樣」就是通過。機械性的規則不在這裡,在
`.scratch/effect-tokenize/test_lint.py`(審查前先跑 `python -m unittest discover -s .scratch/effect-tokenize`)。

## 模組形狀

- 檔頭 docstring 說三件事:哪張票、接縫(輸入 → 輸出)、產出的欄位各是什麼意思。範本:`.scratch/effect-tokenize/frames.py` 檔頭。
- 封閉表是模組頂的常數(tuple/frozenset/dict),表上方一行註解寫來源與裁定日期;判定邏輯讀表,表就是值域。範本:`places.py` 的 `ZONE_TERMS`。
- 一個意思一個地方:玩家詞、區域詞、量詞、態、位置、封閉值域這些表只有一份,其他模組 import。第二份抄本(哪怕值一樣)就是違規。
- 新鍵只加不換:既有欄位的鍵名與值逐位元組不變,新資訊是新的可選鍵、只在有值時帶;推得、轉欄、回填寫進記號欄,字面欄不動。
- 掛勾點讓新模組「宣告」而不是「插入」:報告列、顯示格、批次檔格各由模組自己提供,收集端只有一張模組清單。多張票平行時合併只碰那一行。

## 用詞

- 鍵名、常數、報告列名用 `GLOSSARY.md` 的詞;同一個概念在程式、報告、拆解頁、批次檔四處同一個字。
- 註解與 docstring 用中文、全形標點,寫「為什麼這樣判」。

## 測試

- 接縫只有一個:`frames.extract(原文) → 框架清單`。只斷言輸出框架的欄位,不斷言切段、候選、中間狀態,不斷言封閉表內容。範本:`test_frames.py` 檔頭與 `TestInferredValues`。
- 一個句型一條例子,class docstring 寫票號與規則;每條規則配反例。修規則的 commit 先有一條會失敗的例子。
- 全語料檢查寫成測試、缺輸入時 `skipTest` 並印原因。範本:`test_categories.TestEmptyLeaves.test_real_tree_has_no_empty_leaf_in_corpus`。

## 報告與顯示

- 新欄同時出現在三處:報告(填充率一列)、拆解頁(`viewer.html`)、批次檔(`llm_check.py`)。少一處就是沒做完。
- 規則補的值在顯示層看得出是規則補的(淡色加 title),和原文字面分得開。

## 交件文件

- 票檔 Comments 寫數字(全語料前後框數)、偏離規格之處與理由、留給下一票的接點。範本:`.scratch/frame-args-v3/issues/07-llm-check.md`。
- 偏離規格要指到 `llm-check/summary.md` 的偏離清單或「需要你決定的」。
