# -*- coding: utf-8 -*-
"""回指改讀論元片語(named-queries 票 03)的回歸例子。

唯一接縫:一句效果文原文 → 動作框架清單(frames.extract);只斷言輸出框架的 anaphora 欄,不斷言段、候選、
封閉表。每個句型一條例子、配一條反例:限定語相符/不符(修飾語依類與字面比、中心詞自帶的卡種)、單複數、
數量在子句(片語段的 取自子句 數量)、玩家與區域、指示詞是修飾語不回指(綁屬性詞/區域/同名/以外 的指示詞)、
並列含此卡。既有的回指例子仍在 test_frames.py(TestAnaphora*)。機械規則(anaphora.py 沒有正則式、不解區域字面)在
test_lint.py。

執行:PYTHONIOENCODING=utf-8 python -m unittest discover -s .scratch/effect-tokenize
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import frames  # noqa: E402


def anaphora_of(text, action, context=""):
    """效果句 → 第一個動作是 action 的框架的回指欄;沒有回指時 None。"""
    found = [f for f in frames.extract(text, context) if f["kind"] == "動作" and f["action"] == action]
    return found[0].get("anaphora") if found else None


class TestQualifiers(unittest.TestCase):
    """票 03:限定語讀段的修飾語(種族、卡片子類型、表示形式)與中心詞自帶的卡種;相符的候選勝過較近的,
    都不符時退回最近的。"""

    def test_race_modifier_picks_the_matching_candidate(self):
        found = anaphora_of("①：自分の墓地のドラゴン族モンスター１体を除外し、手札の戦士族モンスター１体を墓地へ送る。"
                            "そのドラゴン族モンスターを特殊召喚する。", "特殊召喚")
        self.assertEqual((found["text"], found["place"]), ("ドラゴン族モンスター1体", "自分の墓地"))

    def test_unmatched_race_modifier_falls_back_to_nearest(self):
        found = anaphora_of("①：自分の墓地のドラゴン族モンスター１体を除外し、手札の戦士族モンスター１体を墓地へ送る。"
                            "その悪魔族モンスターを特殊召喚する。", "特殊召喚")
        self.assertEqual(found["text"], "戦士族モンスター1体")

    def test_position_modifier_picks_the_matching_candidate(self):
        found = anaphora_of("①：相手フィールドの表側表示モンスター１体を対象として発動できる。"
                            "自分フィールドのモンスター１体をリリースし、その表側表示モンスターを破壊する。", "破壊")
        self.assertEqual(found["text"], "表側表示モンスター1体")

    def test_head_card_kind_picks_the_matching_candidate(self):
        found = anaphora_of("①：デッキから効果モンスター１体を墓地へ送り、手札からモンスター１体を特殊召喚する。"
                            "その効果モンスターを手札に加える。", "加える")
        self.assertEqual(found["text"], "効果モンスター1体")


class TestPlural(unittest.TestCase):
    """票 03:それら/その２体 要複數的候選(段的數量 ≥ 2 或多段);單數照最近。"""

    def test_plural_skips_singular_candidate(self):
        found = anaphora_of("①：自分の墓地のモンスター２体を除外し、相手フィールドのモンスター１体を破壊する。"
                            "それらを手札に戻す。", "戻す")
        self.assertEqual(found["text"], "モンスター2体")

    def test_singular_takes_the_nearest(self):
        found = anaphora_of("①：自分の墓地のモンスター２体を除外し、相手フィールドのモンスター１体を破壊する。"
                            "そのモンスターを手札に戻す。", "戻す")
        self.assertEqual(found["text"], "モンスター1体")


class TestClauseCount(unittest.TestCase):
    """票 03:目標的數量只寫在子句裡時讀段的 取自子句 數量;全て 不是數量。"""

    def test_count_after_object_particle(self):
        found = anaphora_of("①：デッキからモンスターを１体選び、そのモンスターを特殊召喚する。", "特殊召喚")
        self.assertEqual((found["text"], found["count"]), ("モンスター", "1体"))

    def test_all_is_not_a_count(self):
        found = anaphora_of("①：自分の墓地のモンスターを全て除外し、そのモンスターの攻撃力分のLPを回復する。", "回復")
        self.assertIsNone(found)
        found = anaphora_of("①：自分の墓地のモンスターを全て除外する。そのモンスターを特殊召喚する。", "特殊召喚")
        self.assertEqual((found["text"], found.get("count")), ("モンスター", None))


class TestPlayerAndZone(unittest.TestCase):
    """票 03:指示詞的玩家限定語比候選段的玩家(含區域字面的玩家);その内の 指前面確認的區域。"""

    def test_player_qualifier_picks_the_candidate_with_that_player(self):
        found = anaphora_of("①：自分のモンスター１体を墓地へ送り、相手モンスター１体を破壊する。"
                            "その自分のモンスターを特殊召喚する。", "特殊召喚")
        self.assertEqual((found["text"], found["player"]), ("自分のモンスター1体", "自分"))

    def test_without_player_qualifier_the_nearest_wins(self):
        found = anaphora_of("①：自分のモンスター１体を墓地へ送り、相手モンスター１体を破壊する。"
                            "そのモンスターを特殊召喚する。", "特殊召喚")
        self.assertEqual((found["text"], found["player"]), ("相手モンスター1体", "相手"))

    def test_within_points_to_the_zone_literal(self):
        found = anaphora_of("①：相手の手札を確認し、その内の１枚を墓地へ送る。", "送る")
        self.assertEqual((found["text"], found["player"]), ("相手の手札", "相手"))

    def test_zone_is_not_a_card_target(self):
        self.assertIsNone(anaphora_of("①：相手の手札を確認し、そのカードを墓地へ送る。", "送る"))


class TestDemonstrativeAsModifier(unittest.TestCase):
    """票 03:指示詞綁的詞是屬性詞、區域、同名、以外 或在定語子句裡時,指示詞只修飾另一張卡,不回指;
    綁定語述語(その破壊された)的仍是回指。"""

    def test_bound_attribute_word_is_a_modifier(self):
        self.assertIsNone(anaphora_of("①：モンスター１体を対象として発動できる。"
                                      "その属性のモンスター１体をデッキから手札に加える。", "加える"))

    def test_bound_zone_is_a_modifier(self):
        self.assertIsNone(anaphora_of("①：相手の手札を確認する。その手札のカード１枚を墓地へ送る。", "送る"))

    def test_same_name_is_a_modifier(self):
        self.assertIsNone(anaphora_of("①：モンスター１体を対象として発動できる。"
                                      "そのカードの同名カード１枚をデッキから手札に加える。", "加える"))

    def test_other_than_is_a_modifier(self):
        self.assertIsNone(anaphora_of("①：モンスター１体を対象として発動できる。"
                                      "そのモンスター以外のモンスター１体を破壊する。", "破壊"))

    def test_relative_clause_is_a_modifier(self):
        self.assertIsNone(anaphora_of("①：モンスター１体を対象として発動できる。"
                                      "そのモンスターより攻撃力が高いモンスター１体を破壊する。", "破壊"))

    def test_predicate_modifier_is_still_a_reference(self):
        found = anaphora_of("①：相手モンスター１体を破壊する。その破壊されたモンスターを除外する。", "除外")
        self.assertEqual(found["text"], "相手モンスター1体")


class TestListedWithThisCard(unittest.TestCase):
    """票 03:並列含此卡的候選算(段數 > 1);字面只是此卡的不算;指示詞與此卡並列時回指只關於指示詞那段。"""

    def test_listed_candidate_counts(self):
        found = anaphora_of("①：このカードとモンスター１体を墓地へ送る。そのモンスターを特殊召喚する。", "特殊召喚")
        self.assertEqual(found["text"], "このカードとモンスター1体")

    def test_only_this_card_is_not_a_candidate(self):
        self.assertIsNone(anaphora_of("①：S召喚したこのカードを墓地へ送る。そのモンスターを特殊召喚する。", "特殊召喚"))

    def test_reference_listed_with_this_card_resolves_its_own_segment(self):
        found = anaphora_of("①：相手モンスター１体を対象として発動できる。そのモンスターとこのカードを破壊する。", "破壊")
        self.assertEqual((found["text"], found["via"]), ("相手モンスター1体", "欄位"))


if __name__ == "__main__":
    unittest.main()
