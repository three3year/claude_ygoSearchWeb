"""召喚手續抽驗 procedure-round1 的抽取修正(summon-procedure 票 05)。

接縫:一句效果外文本原文 → 框架清單(frames.extract),只斷言召喚手續框的論元欄。

執行:PYTHONIOENCODING=utf-8 python -m unittest discover -s .scratch/effect-tokenize -p test_procedure_round1.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import constraints  # noqa: E402
import frames  # noqa: E402


def procedure_args(text):
    return [(f["action"], f.get("object"), f.get("source"), f.get("goal"))
            for f in frames.extract(text, extra=True)
            if f["kind"] == constraints.KIND_ACTION and f["position"] == constraints.POS_PROCEDURE]


class TestSummonThenAlternative(unittest.TestCase):
    """procedure-round1:「…に召喚、または…をリリース」「手札からのP召喚、または…をリリース」的「召喚、」是連用中止的述語
    (召喚する 省略 する),不是 または 並列的名詞——後面那步的論元從讀點之後起算,召喚去處不當它的目的、召喚不併進它的對象。"""

    def test_summon_destination_is_not_the_next_release_goal(self):
        self.assertEqual(procedure_args(
            "このカードを通常召喚する場合、自分フィールドのモンスター３体をリリースして自分フィールドに召喚、"
            "または相手フィールドのモンスター３体をリリースして相手フィールドに召喚しなければならず、"
            "召喚したこのカードのコントロールは次のターンのエンドフェイズに元々の持ち主に戻る。"),
            [("リリース", "モンスター3体", "自分フィールド", None), ("リリース", "モンスター3体", "相手フィールド", None)])

    def test_pendulum_summon_alternative_is_not_the_release_object(self):
        self.assertEqual(procedure_args(
            "このカードは通常召喚できない。手札からのP召喚、または自分フィールドのドラゴン族の融合・S・Xモンスターを"
            "１体ずつリリースした場合のみ特殊召喚できる。"),
            [("リリース", "ドラゴン族の融合・S・Xモンスター", "自分フィールド", None)])

    def test_nouns_joined_by_comma_mata_stay_one_object(self):
        """反例:名詞之間的「、または」照舊是並列,整段是一個對象。"""
        self.assertEqual(procedure_args(
            "このカードは通常召喚できない。自分の墓地の魔法カード、または罠カード１枚を除外した場合のみ特殊召喚できる。"),
            [("除外", "魔法カードまたは罠カード1枚", "自分の墓地", "除外")])


class TestCopulaRelativeClause(unittest.TestCase):
    """procedure-round1:「X が Y である Z」的 である 是繫詞定語——で 不是格助詞,X が 是定語的主語,整段是 Z 的受事者片語
    (元々の持ち主が相手であるモンスター、元々のカード名が「A」であるモンスター)。"""

    def test_owner_is_opponent_stays_in_the_release_object(self):
        self.assertEqual(procedure_args(
            "このカードは融合召喚及び以下の方法でのみEXデッキから特殊召喚できる。"
            "●自分フィールドの、幻想魔族モンスター１体と元々の持ち主が相手である表側表示モンスター１体を"
            "リリースした場合に特殊召喚できる。"),
            [("リリース", "幻想魔族モンスター1体と元々の持ち主が相手である表側表示モンスター1体", "自分フィールド", None)])

    def test_original_name_clause_stays_in_the_overlay_goal(self):
        self.assertEqual(procedure_args(
            "このカードは元々のカード名が「No.69 紋章神コート・オブ・アームズ」である自分フィールドのモンスターの上に"
            "重ねてX召喚する事もできる。"),
            [("重ねる", None, None, "元々のカード名が「No.69 紋章神コート・オブ・アームズ」である自分フィールドのモンスターの上")])

    def test_de_aru_before_a_conjunctive_noun_is_not_a_relative_clause(self):
        """反例:「〜である限り」的 である 接的是條件名詞,不是定語;「手札が０枚である」不併進後面的論元。"""
        found = [(f["action"], f.get("topic"), f.get("object")) for f in frames.extract(
            "自分の手札が０枚である限り、自分フィールドのモンスターは戦闘では破壊されない。")
            if f["kind"] == constraints.KIND_ACTION]
        self.assertEqual(found, [("破壊", "モンスター", None)])


if __name__ == "__main__":
    unittest.main()
