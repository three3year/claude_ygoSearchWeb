"""召喚手續框的分詞鏈例子(summon-procedure 票 02;ADR-0019)。

接縫:一句效果外文本原文 → 框架清單(frames.extract)。召喚條件的手續步驟,動作在白名單
(constraints.PROCEDURE_ACTIONS)內的,各出一個動作框架、位置 召喚手續,走完整條結構化;約束框架
(含手續欄)照舊;白名單外的步驟(存在、になる…前提)與召喚條件本身的召喚不出框。只斷言輸出欄位。

執行:PYTHONIOENCODING=utf-8 python -m unittest discover -s .scratch/effect-tokenize -p test_procedure_frames.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import constraints  # noqa: E402
import frames  # noqa: E402

DARK_MAGICIAN = ("「滅びの黒魔術師」は１ターンに１度、融合召喚及び以下の方法でのみ特殊召喚できる。\n"
                 "●魔法カードの効果が発動したターン、自分フィールドのレベル６以上の魔法使い族・闇属性"
                 "モンスター１体を除外した場合にEXデッキから特殊召喚できる。")


def actions(text, **kw):
    return [f for f in frames.extract(text, **kw) if f["kind"] == constraints.KIND_ACTION]


def procedure_frames(text, **kw):
    return [f for f in actions(text, **kw) if f["position"] == constraints.POS_PROCEDURE]


def summons(text, **kw):
    return [f for f in frames.extract(text, **kw)
            if f["kind"] == constraints.KIND_CONSTRAINT and f.get("subtype") == constraints.SUB_SUMMON]


class TestProcedureFrame(unittest.TestCase):
    """票 02:白名單內的手續步驟出一個動作框架、位置 召喚手續,區域與受事者片語同效果位那一套。"""

    def test_dark_magician_banish_is_a_procedure_frame(self):
        [frame] = procedure_frames(DARK_MAGICIAN)
        self.assertEqual((frame["action"], frame["polarity"]), ("除外", "肯定"))
        self.assertEqual(frame["regions"]["source"], [["自分", "場上"]])
        self.assertEqual(frame["regions"]["goal"], [["無", "除外"]])
        self.assertEqual(frame["phrases"]["object"]["text"], "レベル6以上の魔法使い族・闇属性モンスター1体")
        self.assertEqual(frame["option"], 1)

    def test_summon_condition_constraint_frames_unchanged(self):
        self.assertEqual(
            [(f["form"], f["method"], f["procedure"], f["source"]) for f in summons(DARK_MAGICIAN)],
            [("只能以某方式特殊召喚", "融合召喚及び以下の方法", [], None),
             ("可以某方式特殊召喚", None,
              [{"action": "除外", "object": "自分フィールドのレベル6以上の魔法使い族・闇属性モンスター1体"}],
              "EXデッキ")])

    def test_summon_itself_is_not_a_frame(self):
        self.assertNotIn("特殊召喚", [f["action"] for f in actions(DARK_MAGICIAN)])


class TestWhitelist(unittest.TestCase):
    """票 02:只出白名單內的手續步驟;前提(存在する場合、合計が…以上になる)不出框,但照舊留在約束框架
    的手續欄。"""

    def test_premise_exists_is_not_a_frame(self):
        text = ("自分の墓地に「王家の神殿」か罠カードが合計３種類以上存在する状態で、その内の２種類を１枚ずつ"
                "好きな順番でデッキの下に戻した場合のみ、手札・墓地から特殊召喚できる。")
        self.assertEqual([f["action"] for f in procedure_frames(text)], ["戻す"])
        self.assertEqual([step["action"] for step in summons(text)[0]["procedure"]], ["存在", "戻す"])

    def test_premise_total_becomes_is_not_a_frame(self):
        text = ("このカードは通常召喚できない。攻撃力の合計と守備力の合計が、合わせて１００００以上になるように"
                "自分フィールドのモンスターをリリースした場合のみ特殊召喚できる。")
        self.assertEqual([f["action"] for f in procedure_frames(text)], ["リリース"])
        self.assertEqual([f["action"] for f in actions(text)], ["リリース"])

    def test_xyz_overlay_is_a_procedure_frame(self):
        text = ("「FA－ホープ・レイ・ランサー」は１ターンに１度、自分フィールドの「希望皇ホープ」"
                "モンスターの上に重ねてX召喚する事もできる。")
        [frame] = procedure_frames(text)
        self.assertEqual(frame["action"], "重ねる")
        self.assertEqual(frame["goal"], "自分フィールドの「希望皇ホープ」モンスターの上")

    def test_numbered_effect_sentence_has_no_procedure_frame(self):
        text = "①：自分の墓地のモンスター１体を除外した場合のみ特殊召喚できる。"
        self.assertEqual(procedure_frames(text), [])


if __name__ == "__main__":
    unittest.main()
