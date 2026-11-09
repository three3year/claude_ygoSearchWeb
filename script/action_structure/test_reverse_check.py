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
from test_golden import (BRANCH_ARCHETYPES, DRAGON_RAVINE, KAMIKAZE_DRAGUNITY,
                         KAMIKAZE_DRAGUNITY_TEXT, SINGULARITY_FIEND,
                         SINGULARITY_FIEND_TEXT, SPELL, SPROUT, SPROUT_TEXT, card, faq)


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
        """NFKC 會把 ① 折成 1(docs/data_sources.md),這裡不能:編號字元與數字要分得開。"""
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
                         [("無模板", "段解析不出:述語解析不出")])

    def test_filled_slot_without_template_is_reported_by_slot_name(self):
        """段上多了一個還沒寫模板的格(票 09 前的數量格就是這樣):記「無模板」並指出是哪一格。"""
        structure = build_one(1, "甲", "①：このカードを破壊する。")
        segment(structure)["interval"] = {"text": "１ターンに１度"}
        self.assertEqual([(f["reason"], f["detail"]) for f in check_card(structure)],
                         [("無模板", "格 interval 無模板")])

    def test_targeting_line_has_no_template_yet(self):
        """沒有取對象字面、也沒指回先前被點名的物件,卻標了取對象:無模板(票 11 的規則)。"""
        structure = build_one(1, "甲", "①：このカードを破壊する。")
        segment(structure)["lines"][0]["targeting"] = True
        self.assertEqual([(f["reason"], f["detail"]) for f in check_card(structure)],
                         [("無模板", "取對象線無模板")])

    def test_targeting_declaration_renders_as_object_wo_taishou_toshite(self):
        """取對象宣告「Xを対象として発動できる」:沒有動作詞的代價段,述語就是取對象字面;
        後文指回 X 的效果段對象線帶取對象標記,標記本身沒有字面。"""
        structure = build_one(
            1, "甲", "①：相手フィールドのモンスター１体を対象として発動できる。"
                     "そのモンスターを破壊する。")
        self.assertEqual(check_card(structure), [])
        self.assertTrue(segment(structure, 0, 1)["lines"][0]["targeting"])

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


def lines_with_form(structure):
    return [line for block in structure["blocks"] for seg in block["segments"]
            for line in seg["lines"] if line["to"] and line["to"]["form"]]


class PlacementFormTest(unittest.TestCase):
    """到的放置形式三槽 `{treat, display, order}`(m2 票 01):各槽寫回固定位置。"""

    def test_order_slot_is_written_before_the_destination(self):
        structure = build_one(SPROUT, "森羅の神芽 スプラウト", SPROUT_TEXT)
        [line] = lines_with_form(structure)
        line["to"]["form"]["order"]["text"] = "好きな順に"
        self.assertEqual([(f["reason"], f["rendered"]) for f in check_card(structure)],
                         [("字面不符", "残りのカードは好きな順にデッキの一番下に戻す")])

    def kamikaze_dragunity(self):
        cards = [card(KAMIKAZE_DRAGUNITY, name_ja="神風のドラグニティ", type=0x80002,
                      setcode=0x29),
                 card(DRAGON_RAVINE, name_ja="竜の渓谷", type=0x80002, setcode=0x29)]
        structures, _ = build_structures(
            cards, [faq(KAMIKAZE_DRAGUNITY, "神風のドラグニティ", KAMIKAZE_DRAGUNITY_TEXT)],
            archetypes=BRANCH_ARCHETYPES)
        return structures[0]

    def test_treat_slot_is_written_before_the_inferred_destination(self):
        """「〜を装備魔法カード扱いで、〜に装備できる」:到是推得的,只寫 treat 的字面。"""
        structure = self.kamikaze_dragunity()
        self.assertEqual(check_card(structure), [])
        [line] = lines_with_form(structure)
        line["to"]["form"]["treat"]["text"] = "装備カード扱いで、"
        self.assertEqual(
            [(f["reason"], f["rendered"]) for f in check_card(structure)],
            [("字面不符", "デッキからドラゴン族の「ドラグニティ」モンスター１体を"
                          "装備カード扱いで、この効果で特殊召喚したモンスターに装備できる")])

    def test_treat_kind_must_agree_with_its_literal(self):
        structure = self.kamikaze_dragunity()
        [line] = lines_with_form(structure)
        line["to"]["form"]["treat"]["kind"] = "永續魔法"
        self.assertEqual([(f["reason"], f["detail"]) for f in check_card(structure)],
                         [("無模板", "放置形式無模板:永續魔法")])


class ModifiedAttrTest(unittest.TestCase):
    """性質變更段的 `modified.attr` 是清單(m2 票 01);多項以「・」寫回(m2 票 08)。"""

    TEXT = "①：このカードの攻撃力はターン終了時まで０になる。"

    def test_single_attr_is_written_back(self):
        structure = build_one(1, "甲", self.TEXT)
        self.assertEqual(check_card(structure), [])
        segment(structure)["modified"]["attr"] = ["守備力"]
        self.assertEqual([(f["reason"], f["rendered"]) for f in check_card(structure)],
                         [("字面不符", "このカードの守備力はターン終了時まで０になる")])

    def test_two_attrs_are_joined_with_a_middle_dot(self):
        structure = build_one(1, "甲", self.TEXT)
        segment(structure)["modified"]["attr"] = ["攻擊力", "守備力"]
        self.assertEqual([(f["reason"], f["rendered"]) for f in check_card(structure)],
                         [("字面不符", "このカードの攻撃力・守備力はターン終了時まで０になる")])

    def test_attr_outside_the_closed_set_has_no_template(self):
        structure = build_one(1, "甲", self.TEXT)
        segment(structure)["modified"]["attr"] = ["攻擊力", "階級"]
        self.assertEqual([(f["reason"], f["detail"]) for f in check_card(structure)],
                         [("無模板", "被改的屬性無模板")])


class ResistanceSlotTest(unittest.TestCase):
    """m2 票 04 的新格:`times` 由原述語字面驗、`per_turn` 照字面寫回、原因的物件寫回。"""

    def test_times_must_agree_with_the_predicate_literal(self):
        structure = build_one(10000401, "甲", "このカードは１度のバトルフェイズ中に２回攻撃できる。")
        self.assertEqual(check_card(structure), [])
        segment(structure)["times"]["value"] = 3
        self.assertEqual([f["detail"] for f in check_card(structure)],
                         ["攻擊次數與述語字面不一致"])

    def test_per_turn_is_written_after_the_particle(self):
        structure = build_one(10000402, "甲",
                              "このカードはそれぞれ１ターンに１度だけ戦闘では破壊されない。")
        self.assertEqual(check_card(structure), [])
        segment(structure)["per_turn"]["value"] = 2
        self.assertEqual([f["detail"] for f in check_card(structure)], ["每回合次數無模板"])

    def test_battle_opponent_in_cause_is_written_back(self):
        structure = build_one(10000403, "甲",
                              "このカードは闇属性モンスターとの戦闘では破壊されない。")
        self.assertEqual(check_card(structure), [])
        cause = segment(structure)["cause"]
        opponent = next(o for o in structure["objects"] if o["id"] == cause["objects"][0])
        opponent["condition"]["args"][0]["value"] = "光"
        self.assertEqual([(f["reason"], f["rendered"]) for f in check_card(structure)],
                         [("字面不符", "このカードは光属性モンスターとの戦闘では破壊されない")])


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
            # 「闇属性のモンスター」的「の」模板不寫(attribute_atoms):字面不符的固定例。
            faq(5, "戊", "①：デッキから闇属性のモンスター１体を特殊召喚する。"),
        ]
        return cards, entries

    def test_report_counts_per_reason(self):
        cards, entries = self.library()
        structures, _ = build_structures(cards, entries)
        md = render_report(check_structures(structures))
        self.assertIn("| 段 | 8 |", md)
        self.assertIn("| 通過 | 4 |", md)
        self.assertIn("| 不通過 | 4 |", md)
        self.assertIn("| 有段外殘留的區塊 | 0 |", md)
        self.assertIn("| 無官方日文(不計) | 1 |", md)
        self.assertIn("### 無模板(3 段 / 3 張)", md)
        self.assertIn("### 字面不符(1 段 / 1 張)", md)
        self.assertIn("`5` 戊 `b0.s2` 產生「デッキから闇属性モンスター１体を特殊召喚する」"
                      "原文「デッキから闇属性のモンスター１体を特殊召喚する」", md)
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
            self.assertIn("| 不通過 | 4 |".encode("utf-8"), first)

    def test_cli_lists_every_card_per_reason_without_truncation_including_broken_values(self):
        """「每類附全部卡號」列全部(CODING_STANDARDS):無模板 120 段、字面不符 4 段、段外殘留 3 筆
        同時出現;產物裡有格式壞掉的值——卡號是字串、解析不出的原因是空字串/含換行/不是字串——
        走 CLI 寫出的 md 仍把每張卡列出來、不截斷、不崩。"""
        bounce = [card(80000000 + i, name_ja=f"彈{i}") for i in range(120)]
        mismatch = [card(81000000 + i, name_ja=f"闇{i}", type=SPELL) for i in range(4)]
        residue = [card(82000000 + i, name_ja=f"殘{i}") for i in range(3)]
        cards = bounce + mismatch + residue
        entries = ([faq(c["id"], c["name_ja"], "①：このカードをバウンスする。") for c in bounce]
                   + [faq(c["id"], c["name_ja"], "①：デッキから闇属性のモンスター１体を特殊召喚する。")
                      for c in mismatch]
                   + [faq(c["id"], c["name_ja"], "①：このカードを破壊する。相手に５００ダメージを与える。")
                      for c in residue])
        structures, _ = build_structures(cards, entries)
        by_id = {s["id"]: s for s in structures}
        for cid in (82000000, 82000001, 82000002):
            block = by_id[cid]["blocks"][0]
            block["segments"] = block["segments"][:1]
            block["tree"]["items"] = block["tree"]["items"][:1]
        by_id[80000000]["blocks"][0]["segments"][0]["unparsed"] = {"reason": ""}
        by_id[80000001]["blocks"][0]["segments"][0]["unparsed"] = {"reason": "原因\n換行"}
        by_id[80000002]["blocks"][0]["segments"][0]["unparsed"] = {"reason": 123}
        by_id[80000119]["id"] = "壞卡號"
        with tempfile.TemporaryDirectory() as tmp:
            product = os.path.join(tmp, "action_structure.json")
            out = os.path.join(tmp, "reverse_check.md")
            with open(product, "w", encoding="utf-8", newline="\n") as f:
                f.write(serialize_structures(structures))
            self.assertEqual(build_reverse_check.main(["--structures", product, "--out", out]), 0)
            with open(out, encoding="utf-8") as f:
                md = f.read()
        self.assertIn("| 不通過 | 124 |", md)
        self.assertIn("### 無模板(120 段 / 120 張)", md)
        self.assertIn("### 字面不符(4 段 / 4 張)", md)
        self.assertIn("### 段外殘留(3 筆 / 3 張)", md)
        line = next(l for l in md.splitlines() if l.startswith("- 段解析不出:述語解析不出(117 段 / 117 張):"))
        listed = line.split(":", 2)[2].split(", ")
        self.assertEqual(listed, [str(c["id"]) for c in bounce[3:119]] + ["壞卡號"])
        self.assertIn("- 段解析不出:(1 段 / 1 張):80000000", md)
        self.assertIn("- (格式壞掉:'段解析不出:原因\\n換行')(1 段 / 1 張):80000001", md)
        self.assertIn("- 段解析不出:123(1 段 / 1 張):80000002", md)
        for entry in mismatch:
            self.assertIn(f"- `{entry['id']}` {entry['name_ja']} `b0.s2` 產生「", md)
        self.assertIn("- 相手に５００ダメージを与える(3 筆 / 3 張):82000000, 82000001, 82000002", md)


if __name__ == "__main__":
    unittest.main()
