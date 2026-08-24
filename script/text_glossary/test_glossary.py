"""卡文詞彙表驗證接縫的純函式測試:餵詞彙表 md 全文+合成卡句記錄,不做 IO
(先例:text_format/test_classify.py、tag_card/test_sync_errata.py)。

必蓋案例照 spec Testing Decisions(票 text-glossary#01):譯詞命中且照規範
不報、未照規範報、用禁譯報、例外卡跳過、`〈n〉` 佔位、`〜` 佔位、句式日文
命中中文照模板不報、未照模板報、解析失敗吵出來、多條目命中分組。只斷言
外部行為(餵什麼進、報什麼出),不斷言中間 entries 結構。檔尾另有對真實
docs/text_glossary.md 的輕量迴歸。
"""
import os
import unittest

from glossary import GlossaryError, check_texts

_REAL_GLOSSARY = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "..", "..", "docs", "text_glossary.md")

_HEADER = "| 日文 | 規範譯法 | 禁譯 | 庫內計數 | PSCT | 例外 | 備註 |"
_SEP = "|---|---|---|---|---|---|---|"


def _glossary(term_rows=(), pattern_rows=()):
    """合成一份格式合規的詞彙表 md(兩節標題+七欄表格,體例同正式檔)。"""
    lines = ["# 卡文詞彙表", "", "## 體例", "", "略。", "",
             "## 1. 譯詞對照", "", _HEADER, _SEP, *term_rows, "",
             "## 2. 句式模板", "",
             "| 日文樣式 | 中文樣式 | 禁譯 | 庫內計數 | PSCT | 例外 | 備註 |",
             _SEP, *pattern_rows]
    return "\n".join(lines) + "\n"


def _rec(rid=1, name="測試卡", ja="", zh=""):
    return {"id": rid, "name": name, "text_ja": ja, "text_zh": zh}


TERM_RELEASE = "| リリース | 解放 | 祭品;犧牲 | 100 | — | — | — |"
TERM_DRAW = "| ドローする | 抽〈n〉張卡 | — | 434 | draw | — | — |"
TERM_UNAFFECTED = "| 〜の効果を受けない | 不受〜效果影響 | — | 214 | — | — | — |"
PATTERN_TWICE = ("| この効果は１ターンに〈n〉度まで使用できる "
                 "| 這個效果1回合可以使用最多〈n〉次 | — | 10 | — | — | — |")


class TermCheckTest(unittest.TestCase):
    """譯詞級:日文側含原詞 → 中文側須用規範譯法、不得用禁譯。"""

    def test_conforming_translation_not_reported(self):
        """命中且照規範:不報。"""
        findings = check_texts(
            _glossary([TERM_RELEASE]),
            [_rec(ja="このカードをリリースして発動できる。",
                  zh="將此卡解放可以發動。")])
        self.assertEqual(findings, [])

    def test_missing_norm_translation_reported(self):
        """命中而未用規範譯法:報,問題註明「未用規範譯法」。"""
        findings = check_texts(
            _glossary([TERM_RELEASE]),
            [_rec(ja="このカードをリリースして発動できる。",
                  zh="將此卡送去墓地可以發動。")])
        self.assertEqual([(f["entry"], f["problem"]) for f in findings],
                         [("リリース", "未用規範譯法")])

    def test_banned_translation_reported_with_which(self):
        """用禁譯:報,並指出命中哪個禁譯樣式。"""
        findings = check_texts(
            _glossary([TERM_RELEASE]),
            [_rec(ja="このカードをリリースして発動できる。",
                  zh="將此卡作為祭品可以發動。")])
        self.assertEqual([(f["problem"], f["banned"]) for f in findings],
                         [("用禁譯", ["祭品"])])

    def test_banned_wins_even_with_norm_present(self):
        """規範譯法與禁譯同句並存:仍以「用禁譯」上報(句中混用)。"""
        findings = check_texts(
            _glossary([TERM_RELEASE]),
            [_rec(ja="リリースして発動できる。",
                  zh="解放或作為犧牲。")])
        self.assertEqual([(f["problem"], f["banned"]) for f in findings],
                         [("用禁譯", ["犧牲"])])

    def test_ja_side_not_hit_never_reported(self):
        """日文側不含原詞:中文側就算用了禁譯也不報(檢查以日文側為門)。"""
        findings = check_texts(
            _glossary([TERM_RELEASE]),
            [_rec(ja="このカードを墓地へ送って発動できる。",
                  zh="將此卡作為祭品。")])
        self.assertEqual(findings, [])

    def test_record_without_ja_text_skipped(self):
        """無日文卡文的記錄(ot=2 繁中單側)整筆跳過。"""
        findings = check_texts(_glossary([TERM_RELEASE]),
                               [_rec(ja="", zh="將此卡作為祭品。")])
        self.assertEqual(findings, [])


class ExceptionColumnTest(unittest.TestCase):
    def test_excepted_card_skipped_others_still_reported(self):
        """例外欄所列卡片密碼自動跳過;不在清單上的照報。"""
        row = "| リリース | 解放 | — | 100 | — | 100,200 | 裁示不用修 |"
        records = [_rec(rid=100, ja="リリースする。", zh="送去墓地。"),
                   _rec(rid=300, ja="リリースする。", zh="送去墓地。")]
        findings = check_texts(_glossary([row]), records)
        self.assertEqual([f["id"] for f in findings], [300])


class PlaceholderTest(unittest.TestCase):
    def test_number_placeholder_matches_digits(self):
        """`〈n〉`=連續數字:「抽2張卡」照規範,不報。"""
        findings = check_texts(
            _glossary([TERM_DRAW]),
            [_rec(ja="自分はデッキから２枚ドローする。", zh="我方抽2張卡。")])
        self.assertEqual(findings, [])

    def test_number_placeholder_mismatch_reported(self):
        """中文側沒有「抽〈n〉張卡」形:報。"""
        findings = check_texts(
            _glossary([TERM_DRAW]),
            [_rec(ja="１枚ドローする。", zh="我方從牌組拿1張卡。")])
        self.assertEqual([f["entry"] for f in findings], ["ドローする"])

    def test_tilde_placeholder_spans_within_sentence(self):
        """`〜`=同句內任意內文:「不受此卡以外的卡的效果影響」照規範。"""
        findings = check_texts(
            _glossary([TERM_UNAFFECTED]),
            [_rec(ja="このカードは罠カードの効果を受けない。",
                  zh="此卡不受陷阱卡的效果影響。")])
        self.assertEqual(findings, [])

    def test_tilde_placeholder_does_not_cross_sentence(self):
        """`〜` 不跨句號:「不受」與「效果影響」分居兩句時不算照規範。"""
        findings = check_texts(
            _glossary([TERM_UNAFFECTED]),
            [_rec(ja="このカードは罠カードの効果を受けない。",
                  zh="此卡不受戰鬥破壞。陷阱卡的效果影響不到。")])
        self.assertEqual([f["problem"] for f in findings], ["未用規範譯法"])


class PatternCheckTest(unittest.TestCase):
    """句式級:日文側命中樣式 → 中文側須照模板(佔位符含全形數字)。"""

    def test_conforming_pattern_not_reported(self):
        """日文命中(全形數字)且中文照模板:不報。"""
        findings = check_texts(
            _glossary(pattern_rows=[PATTERN_TWICE]),
            [_rec(ja="この効果は１ターンに２度まで使用できる。",
                  zh="這個效果1回合可以使用最多2次。")])
        self.assertEqual(findings, [])

    def test_nonconforming_pattern_reported(self):
        """日文命中而中文未照模板:報,問題註明「未照模板」。"""
        findings = check_texts(
            _glossary(pattern_rows=[PATTERN_TWICE]),
            [_rec(ja="この効果は１ターンに２度まで使用できる。",
                  zh="此效果1回合可以使用最多2次。")])
        self.assertEqual([(f["level"], f["problem"]) for f in findings],
                         [("句式", "未照模板")])


class MultiEntryTest(unittest.TestCase):
    def test_one_record_hits_multiple_entries(self):
        """多條目命中:同一句記錄對每個命中條目各報一筆,供依條目分組。"""
        findings = check_texts(
            _glossary([TERM_RELEASE, TERM_DRAW]),
            [_rec(ja="リリースして１枚ドローする。", zh="送去墓地拿1張卡。")])
        self.assertEqual([f["entry"] for f in findings],
                         ["リリース", "ドローする"])


class ParseFailureTest(unittest.TestCase):
    """詞彙表解析失敗必須吵出來,不靜默漏檢。"""

    def test_wrong_column_count_raises(self):
        """資料列欄數不是 7:大聲失敗。"""
        bad = "| リリース | 解放 | — | 100 | — | — |"
        with self.assertRaises(GlossaryError):
            check_texts(_glossary([bad]), [])

    def test_unknown_placeholder_raises(self):
        """`〈n〉` 以外的 `〈…〉` 佔位符:大聲失敗。"""
        bad = "| ドローする | 抽〈m〉張卡 | — | 1 | — | — | — |"
        with self.assertRaises(GlossaryError):
            check_texts(_glossary([bad]), [])

    def test_stray_bracket_raises(self):
        """落單的 `〈`:大聲失敗。"""
        bad = "| ドローする | 抽〈n張卡 | — | 1 | — | — | — |"
        with self.assertRaises(GlossaryError):
            check_texts(_glossary([bad]), [])

    def test_missing_section_heading_raises(self):
        """找不到「句式模板」節標題:大聲失敗(表格挪動或改名立即發現)。"""
        md = "\n".join(["# 卡文詞彙表", "", "## 1. 譯詞對照", "",
                        _HEADER, _SEP, TERM_RELEASE]) + "\n"
        with self.assertRaises(GlossaryError):
            check_texts(md, [])

    def test_bad_exception_cell_raises(self):
        """例外欄不是「—」或卡片密碼逗號清單:大聲失敗。"""
        bad = "| リリース | 解放 | — | 100 | — | 見備註 | — |"
        with self.assertRaises(GlossaryError):
            check_texts(_glossary([bad]), [])


@unittest.skipUnless(os.path.exists(_REAL_GLOSSARY),
                     "需要 docs/text_glossary.md")
class RealGlossaryRegressionTest(unittest.TestCase):
    """對真實詞彙表的輕量迴歸(先例:test_classify.py 檔尾):正式檔可解析、
    種子條目端對端有效。條目增修若打壞格式,這裡先於全掃吵出來。"""

    def setUp(self):
        with open(_REAL_GLOSSARY, encoding="utf-8") as f:
            self.md = f.read()

    def test_real_glossary_parses_and_seed_entry_fires(self):
        conforming = _rec(ja="カードを１枚ドローする。", zh="抽1張卡。")
        violating = _rec(rid=2, ja="カードを１枚ドローする。",
                         zh="從牌組拿1張卡。")
        self.assertEqual(check_texts(self.md, [conforming]), [])
        self.assertEqual([f["entry"] for f in check_texts(self.md,
                                                          [violating])],
                         ["ドローする"])

    def test_real_pattern_entry_fires_end_to_end(self):
        """句式試金石條目(票01)在正式檔上端對端有效。"""
        rec = _rec(ja="この効果は１ターンに３度まで使用できる。",
                   zh="這個效果1回合最多用3次。")
        self.assertEqual([(f["level"], f["problem"])
                          for f in check_texts(self.md, [rec])],
                         [("句式", "未照模板")])


if __name__ == "__main__":
    unittest.main()
