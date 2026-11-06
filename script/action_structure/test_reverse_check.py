"""反向檢查(接縫二):正規化、句型模板的固定測試、全庫報告與 CLI。

輸入是卡片結構(由官方 DB 文本建出,或在測試裡改過的結構),看不通過清單與報告;
期望值是手寫的字面,不照程式重算。
"""
import contextlib
import io
import os
import tempfile
import unittest

import build_reverse_check
from card_structure import build_structures, serialize_structures
from reverse_check import (check_card, check_structures, normalise,
                           render_report)
from test_golden import (SINGULARITY_FIEND, SINGULARITY_FIEND_TEXT, SPELL,
                         card, faq)


def build_one(cid, name_ja, text):
    cards = [card(cid, name_ja=name_ja)]
    structures, _ = build_structures(cards, [faq(cid, name_ja, text)])
    return structures[0]


def segment(structure, block_index=0, segment_index=0):
    return structure["blocks"][block_index]["segments"][segment_index]


class NormaliseTest(unittest.TestCase):

    def test_whitespace_removed_and_fullwidth_ascii_folded(self):
        self.assertEqual(normalise("魔法カード １枚\nを　捨てて（Ａ）"),
                         "魔法カード1枚を捨てて(A)")

    def test_circled_numbers_are_not_folded_to_digits(self):
        """NFKC 會把 ① 折成 1(筆記 00 第 4 點),這裡不能:編號字元與數字要分得開。"""
        self.assertEqual(normalise("①：１枚"), "①:1枚")
        self.assertNotEqual(normalise("①"), normalise("1"))


class TemplateTest(unittest.TestCase):
    """句型模板的固定測試:簡單子句 [誰が][從から][物件を]述語[觸發形]。"""

    def test_each_segment_of_the_golden_card_renders_its_own_text(self):
        structure = build_one(SINGULARITY_FIEND, "特異点の悪魔",
                              SINGULARITY_FIEND_TEXT)
        self.assertEqual(check_card(structure), [])

    def test_literal_mismatch_reports_rendered_and_original(self):
        """結構說是陷阱卡、原文寫魔法卡:字面不符,附產生的日文與原文。"""
        structure = build_one(SINGULARITY_FIEND, "特異点の悪魔",
                              SINGULARITY_FIEND_TEXT)
        spell = next(o for o in structure["objects"] if o["text"] == "魔法カード１枚")
        spell["condition"] = {"op": "大類", "value": "陷阱"}
        failures = check_card(structure)
        self.assertEqual([(f["reason"], f["rendered"], f["original"])
                          for f in failures],
                         [("字面不符", "手札からこのカードと罠カード１枚を捨てて",
                           "手札からこのカードと魔法カード１枚を捨てて")])
        self.assertEqual(failures[0]["card"], SINGULARITY_FIEND)
        self.assertEqual(failures[0]["segment"], "b27.s19")

    def test_unparsed_segment_has_no_template(self):
        structure = build_one(1, "甲", "①：このカードをバウンスする。")
        failures = check_card(structure)
        self.assertEqual([(f["reason"], f["detail"]) for f in failures],
                         [("無模板", "段未解析:述語解析不出")])

    def test_filled_slot_without_template_is_reported_by_slot_name(self):
        """後面的票填了新格(例:期間)但還沒寫模板:記「無模板」並指出是哪一格。"""
        structure = build_one(1, "甲", "①：このカードを破壊する。")
        segment(structure)["duration"] = "本回合"
        self.assertEqual([(f["reason"], f["detail"]) for f in check_card(structure)],
                         [("無模板", "格 duration 無模板")])

    def test_targeting_line_has_no_template_yet(self):
        structure = build_one(1, "甲", "①：このカードを破壊する。")
        segment(structure)["lines"][0]["targeting"] = True
        self.assertEqual([(f["reason"], f["detail"]) for f in check_card(structure)],
                         [("無模板", "取對象線無模板")])

    def test_predicate_literal_must_agree_with_action_and_polarity(self):
        """述語字面與動作詞/態/極性對不上(結構內部矛盾):不通過,不照字面放行。"""
        structure = build_one(1, "甲", "①：このカードを破壊する。")
        segment(structure)["polarity"] = "不能"
        self.assertEqual([(f["reason"], f["detail"]) for f in check_card(structure)],
                         [("無模板", "述語字面與動作詞、態、極性不一致")])

    def test_text_outside_any_segment_is_residue(self):
        """區塊裡有段沒涵蓋、又不是固定接著詞的文字:段外殘留。"""
        structure = build_one(1, "甲", "①：このカードを破壊する。相手に５００ダメージを与える。")
        block = structure["blocks"][0]
        block["segments"] = block["segments"][:1]
        block["tree"]["items"] = block["tree"]["items"][:1]
        self.assertEqual([(f["reason"], f["detail"]) for f in check_card(structure)],
                         [("段外殘留", "相手に５００ダメージを与える")])

    def test_glue_between_segments_is_not_residue(self):
        """「①：」「、」「発動できる。」「その後、」與觸發形後的「に」是句型的固定接著詞,
        不算殘留;連著出現(「発動する。その後、」)也是。"""
        texts = (
            "①：このカードを破壊する。その後、相手がモンスターを特殊召喚した時、"
            "手札からこのカードを捨てて発動できる。",
            "①：相手がモンスターを特殊召喚した場合に発動できる。そのモンスターを破壊する。",
            "①：相手がモンスターを特殊召喚した時に発動する。その後、このカードを破壊する。",
        )
        for text in texts:
            with self.subTest(text=text):
                structure = build_one(1, "甲", text)
                self.assertEqual([f for f in check_card(structure)
                                  if f["reason"] == "段外殘留"], [])

    def test_particle_ni_counts_as_glue_only_after_a_condition_segment(self):
        structure = build_one(1, "甲", "①：このカードを破壊する。に発動できる。")
        block = structure["blocks"][0]
        block["segments"] = block["segments"][:1]  # 留下效果段,「に発動できる」沒人認
        block["tree"]["items"] = block["tree"]["items"][:1]
        self.assertEqual([(f["reason"], f["detail"]) for f in check_card(structure)],
                         [("段外殘留", "に発動できる")])

    def test_card_without_official_text_has_nothing_to_check(self):
        cards = [card(20240828, name_ja="デコピン", type=SPELL)]
        structures, _ = build_structures(cards, [])
        self.assertEqual(check_card(structures[0]), [])


class ReportTest(unittest.TestCase):
    """全庫報告:通過段數、不通過依原因分類、附全部卡號;同一輸入兩次產出相同。"""

    @staticmethod
    def library():
        cards = [
            card(SINGULARITY_FIEND, name_ja="特異点の悪魔"),
            card(2, name_ja="乙"), card(3, name_ja="丙"), card(4, name_ja="丁"),
            card(5, name_ja="戊", type=SPELL),
            card(20240828, name_ja="デコピン", type=SPELL),
        ]
        entries = [
            faq(SINGULARITY_FIEND, "特異点の悪魔", SINGULARITY_FIEND_TEXT),
            faq(2, "乙", "①：このカードをバウンスする。"),
            faq(3, "丙", "①：このカードをバウンスする。②：このカードを破壊する。"),
            faq(4, "丁", "①：このカードをバウンスする。"),
            faq(5, "戊", "①：自分の手札からこのカードを捨てて発動できる。"),
        ]
        return cards, entries

    def test_report_counts_and_lists_every_card_per_reason(self):
        cards, entries = self.library()
        structures, _ = build_structures(cards, entries)
        # 戊 的「自分の手札から」照字面還原會通過;拿掉字面,模板只能由區域拼回,製造字面不符。
        wu = next(c for c in structures if c["id"] == 5)
        wu["blocks"][0]["segments"][0]["lines"][0]["from"]["text"] = None
        md = render_report(check_structures(structures))
        self.assertIn("| 段 | 8 |", md)
        self.assertIn("| 通過 | 4 |", md)
        self.assertIn("| 不通過 | 4 |", md)
        self.assertIn("| 有段外殘留的區塊 | 0 |", md)
        self.assertIn("| 無官方日文(不計) | 1 |", md)
        self.assertIn("### 無模板(3 段 / 3 張)", md)
        self.assertIn("段未解析:述語解析不出(3 段 / 3 張):2, 3, 4", md)
        self.assertIn("### 字面不符(1 段 / 1 張)", md)
        self.assertIn("`5` 戊 `b0.s2` 產生「手札からこのカードを捨てて」"
                      "原文「自分の手札からこのカードを捨てて」", md)
        self.assertIn("<!-- 由 script/action_structure/build_reverse_check.py 產生", md)

    def test_same_input_renders_identical_report(self):
        cards, entries = self.library()
        first, _ = build_structures(cards, entries)
        second, _ = build_structures(list(reversed(cards)), list(reversed(entries)))
        self.assertEqual(render_report(check_structures(first)).encode("utf-8"),
                         render_report(check_structures(second)).encode("utf-8"))


class CliTest(unittest.TestCase):
    """走 CLI 入口:讀產物、寫報告;兩次寫出的檔逐位元組相同。"""

    def setUp(self):
        self._quiet = contextlib.redirect_stdout(io.StringIO())
        self._quiet.__enter__()
        self.addCleanup(self._quiet.__exit__, None, None, None)

    def test_cli_writes_identical_report_twice(self):
        cards, entries = ReportTest.library()
        structures, _ = build_structures(cards, entries)
        with tempfile.TemporaryDirectory() as tmp:
            product = os.path.join(tmp, "action_structure.json")
            out = os.path.join(tmp, "report", "reverse_check.md")
            with open(product, "w", encoding="utf-8", newline="\n") as f:
                f.write(serialize_structures(structures))
            argv = ["--structures", product, "--out", out]
            self.assertEqual(build_reverse_check.main(argv), 0)
            with open(out, "rb") as f:
                first = f.read()
            self.assertEqual(build_reverse_check.main(argv), 0)
            with open(out, "rb") as f:
                second = f.read()
            self.assertEqual(first, second)
            self.assertNotIn(b"\r\n", first)
            self.assertIn("| 不通過 | 3 |".encode("utf-8"), first)


if __name__ == "__main__":
    unittest.main()
