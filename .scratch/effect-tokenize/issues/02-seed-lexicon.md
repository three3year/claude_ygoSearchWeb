# 02 — 詞典種子票:從既有資產萃取種子詞典+切分慣例裁定點

**What to build:** 日文側分詞詞典的第一版種子:從 `script/tag_card/tag_rules.py` 的 regex 字彙(alternation 裡的字面詞)與 `docs/text_glossary.md` 的日文詞條萃取,人工整理成 `.scratch/effect-tokenize/lexicon.json`(詞條+詞 ID+來源出處)。同時定第一版切分慣例:「卡名」→NAME token、數字(漢數字/阿拉伯數字)→NUM token(帶原值)、助詞(に/で/を/は/が/と/の/へ/も/から/まで/より)獨立成 token;慣例寫成 `.scratch/effect-tokenize/conventions.md`,拿不準的切法列成裁定點清單供站主裁定。

**Blocked by:** None — can start immediately.

**Status:** resolved

**成果(2026-10-01):** 種子詞典 `lexicon.json` **384 詞條**(tag_rules regex
萃出 329、glossary 153、兩源皆有 96;ID 依 surface 碼位排序後編,決定性)。
萃取腳本 `extract_seed.py`:regex 元字符當邊界+群組交替/字元類前綴接合還原
活用形(送(る|り|って)→送る/送り/送って)、負向環視不接合;兩源統一過
助詞切分(票面 14 個+として/または/及び/しか)、純平假名白名單、黑名單擋
斷頭殘渣、「〜できる」複合形終篩剝除(可能形獨立 token 暫行慣例)。切分
慣例與 **12 條裁定點**(複合動詞/サ変+する/可能形/〜場合/指示詞/種族屬性
封閉類/副助詞/では/縮寫並列/漢數字量詞/『』/活用尾)各附語料實例,見
`conventions.md`,待站主裁定。
