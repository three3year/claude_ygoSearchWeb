"""代替、延遲、極性與性質變更(票 08)的句型層級測試:只走接縫一(查詢判斷)與接縫二(反向檢查)。

- 取對象:「〜を対象として発動できる」之後對著它做的效果段標取對象;延遲段(次のスタンバイフェイズに、
  序列中段的條件段之後)不標。
- 代替:「〜場合、代わりに〜」的被代替段與做代替的段都只在查詢含代替時看。
- 極性:「〜できない」是不能、「Xは〜できる」是永續的許可(可以),「Xを〜できる」仍是可選的做。
- 原因含誰的、戦闘・効果;「A」または「B」;曾被特殊召喚;レベルN以上/以下;性質變更句的數值形。
"""
import unittest

from action_query import run_query
from card_structure import build_structures
from reverse_check import check_card
from test_golden import ARCHETYPES, SPELL, card, faq

SELF = 10000108
PENGUIN_SOLDIER = 93920745   # ペンギン・ソルジャー setcode 0x5a、等級 2
BLACK_MAGICIAN = 46986414    # 等級 7
BLUE_EYES_ULTIMATE = 23995346  # 青眼の究極竜(融合、等級 12)
GREEDY_POT = 24094653


def library(text, **self_kw):
    cards = [
        card(SELF, name_ja="甲", **self_kw),
        card(PENGUIN_SOLDIER, name_ja="ペンギン・ソルジャー", level=2, race=0x40,
             attribute=0x2, setcode=0x5a),
        card(BLACK_MAGICIAN, name_ja="ブラック・マジシャン", level=7, race=0x2,
             attribute=0x20),
        card(BLUE_EYES_ULTIMATE, name_ja="青眼の究極竜", type=0x41, level=12,
             race=0x2000, attribute=0x10),
        card(GREEDY_POT, name_ja="強欲な壺", type=SPELL),
    ]
    structures, _ = build_structures(cards, [faq(SELF, "甲", text)],
                                     archetypes=ARCHETYPES)
    return cards, structures


def hits(cards, structures, **query):
    return [h["id"] for h in run_query(structures, cards, query)["hits"]]


def own(structures):
    return next(c for c in structures if c["id"] == SELF)


class TargetingTest(unittest.TestCase):

    def test_effect_on_the_declared_target_is_marked_targeting(self):
        """取對象宣言之後「そのモンスターを破壊する」標取對象;整張通過反向檢查。"""
        cards, structures = library(
            "①：相手フィールドのモンスター１体を対象として発動できる。そのモンスターを破壊する。")
        self.assertEqual(check_card(own(structures)), [])
        self.assertIn(SELF, hits(cards, structures, actions=["破壞"], targeting=True,
                                 from_zones=[{"zone": "場上", "side": "對手"}],
                                 card=BLACK_MAGICIAN))

    def test_segments_after_a_mid_sequence_condition_are_delayed(self):
        """序列中段出現條件段:之後的段算延遲、不標取對象(リビングデッドの呼び声的句型)。"""
        cards, structures = library(
            "①：自分の墓地のモンスター１体を対象として発動できる。そのモンスターを特殊召喚する。"
            "このカードが破壊された場合、そのモンスターを破壊する。")
        self.assertEqual(check_card(own(structures)), [])
        self.assertIn(SELF, hits(cards, structures, actions=["特殊召喚"], targeting=True))
        self.assertIn(SELF, hits(cards, structures, actions=["破壞"],
                                 card=BLACK_MAGICIAN))
        self.assertNotIn(SELF, hits(cards, structures, actions=["破壞"], targeting=True))


class ReplacementTest(unittest.TestCase):

    def test_both_sides_of_a_replacement_are_hidden_without_the_switch(self):
        cards, structures = library(
            "①：自分フィールドの「ペンギン」モンスターが戦闘で破壊される場合、"
            "代わりに手札のこのカードを墓地へ送る事ができる。")
        self.assertEqual(check_card(own(structures)), [])
        self.assertNotIn(SELF, hits(cards, structures, actions=["送墓"]))
        self.assertNotIn(SELF, hits(cards, structures, actions=["破壞"]))
        self.assertIn(SELF, hits(cards, structures, actions=["送墓"], from_zones=["手牌"],
                                 card=SELF, replacement=True))
        self.assertIn(SELF, hits(cards, structures, actions=["破壞"], card=PENGUIN_SOLDIER,
                                 replacement=True))
        self.assertNotIn(SELF, hits(cards, structures, actions=["破壞"],
                                    card=BLACK_MAGICIAN, replacement=True))

    def test_replaced_segment_does_not_move_the_object(self):
        """被代替段不更新位置:被破壞的怪獸仍在場上,後面「そのモンスターを除外する」的從是場上。"""
        cards, structures = library(
            "①：自分フィールドの「ペンギン」モンスターが効果で破壊される場合、"
            "代わりにそのモンスターを除外する。")
        self.assertEqual(check_card(own(structures)), [])
        self.assertIn(SELF, hits(cards, structures, actions=["除外"],
                                 from_zones=[{"zone": "場上", "side": "我方"}],
                                 card=PENGUIN_SOLDIER, replacement=True))
        self.assertNotIn(SELF, hits(cards, structures, actions=["除外"],
                                    from_zones=["墓地"], card=PENGUIN_SOLDIER,
                                    replacement=True, include_inferred=True))


class PolarityTest(unittest.TestCase):

    def test_cannot_is_excluded_by_default_and_included_on_request(self):
        cards, structures = library("①：このカードは特殊召喚できない。")
        self.assertEqual(check_card(own(structures)), [])
        self.assertNotIn(SELF, hits(cards, structures, actions=["特殊召喚"]))
        self.assertIn(SELF, hits(cards, structures, actions=["特殊召喚"],
                                 polarities=["不能"], card=SELF))

    def test_permission_with_wa_is_may_not_an_optional_action(self):
        """「このカードは直接攻撃できる」是永續的許可(可以),預設不算命中;
        「〜を特殊召喚できる」仍是可選的做,預設命中。"""
        cards, structures = library("①：このカードは直接攻撃できる。")
        self.assertEqual(check_card(own(structures)), [])
        self.assertNotIn(SELF, hits(cards, structures, actions=["直接攻擊"]))
        self.assertIn(SELF, hits(cards, structures, actions=["直接攻擊"],
                                 polarities=["可以"]))
        cards, structures = library("①：手札からこのカードを特殊召喚できる。")
        self.assertEqual(check_card(own(structures)), [])
        self.assertIn(SELF, hits(cards, structures, actions=["特殊召喚"], card=SELF))

    def test_non_doing_polarity_does_not_update_position(self):
        """極性非「做」的段不更新位置:「除外できない」之後「このカードを破壊する」的從不是除外。"""
        cards, structures = library(
            "①：このカードが墓地に存在する場合に発動できる。このカードは除外できない。"
            "このカードを破壊する。")
        self.assertNotIn(SELF, hits(cards, structures, actions=["破壞"],
                                    from_zones=["除外"], card=SELF))
        self.assertIn(SELF, hits(cards, structures, actions=["破壞"],
                                 from_zones=["墓地"], card=SELF))


class CauseAndNamesTest(unittest.TestCase):

    def test_cause_forms_round_trip(self):
        for text in ("①：このカードが相手の効果で破壊された場合に発動できる。このカードを除外する。",
                     "①：このカードが戦闘・効果で破壊された場合に発動できる。このカードを除外する。",
                     "①：このカードが戦闘によって破壊された場合に発動できる。このカードを除外する。"):
            with self.subTest(text=text):
                _, structures = library(text)
                self.assertEqual(check_card(own(structures)), [])

    def test_either_of_two_names_with_a_pause_after_the_zone(self):
        cards, structures = library(
            "①：自分フィールドの、「ペンギン・ソルジャー」または「ブラック・マジシャン」を"
            "墓地へ送る。")
        self.assertEqual(check_card(own(structures)), [])
        for cid in (PENGUIN_SOLDIER, BLACK_MAGICIAN):
            self.assertIn(SELF, hits(cards, structures, actions=["送墓"], card=cid))
        self.assertNotIn(SELF, hits(cards, structures, actions=["送墓"], card=GREEDY_POT))


class ConditionAtomsTest(unittest.TestCase):

    def test_level_bounds_and_summoned_from_extra_deck(self):
        cards, structures = library(
            "①：EXデッキから特殊召喚されたレベル５以上のモンスター１体を破壊する。")
        self.assertEqual(check_card(own(structures)), [])
        self.assertIn(SELF, hits(cards, structures, actions=["破壞"],
                                 card=BLUE_EYES_ULTIMATE))
        self.assertNotIn(SELF, hits(cards, structures, actions=["破壞"],
                                    card=BLACK_MAGICIAN))
        cards, structures = library("①：手札からレベル４以下のモンスター１体を特殊召喚する。")
        self.assertEqual(check_card(own(structures)), [])
        self.assertIn(SELF, hits(cards, structures, actions=["特殊召喚"],
                                 card=PENGUIN_SOLDIER))
        self.assertNotIn(SELF, hits(cards, structures, actions=["特殊召喚"],
                                    card=BLACK_MAGICIAN))


class ModificationTest(unittest.TestCase):

    def test_numeric_form_on_this_card(self):
        cards, structures = library("①：このカードの攻撃力はターン終了時まで０になる。")
        self.assertEqual(check_card(own(structures)), [])
        self.assertIn(SELF, hits(cards, structures, actions=["性質變更"], card=SELF))
        self.assertNotIn(SELF, hits(cards, structures, actions=["性質變更"],
                                    card=BLACK_MAGICIAN))

    def test_joined_clauses_share_the_delay(self):
        """「次のエンドフェイズに墓地へ送り、その攻撃力は〜になる」:第二段與第一段同時、同樣延遲。"""
        cards, structures = library(
            "①：相手フィールドのモンスター１体を対象として発動できる。"
            "そのモンスターは次のエンドフェイズに墓地へ送り、その守備力は０になる。")
        self.assertEqual(check_card(own(structures)), [])
        self.assertIn(SELF, hits(cards, structures, actions=["送墓"], card=BLACK_MAGICIAN))
        self.assertNotIn(SELF, hits(cards, structures, actions=["送墓"], targeting=True))
        self.assertNotIn(SELF, hits(cards, structures, actions=["性質變更"],
                                    targeting=True))


if __name__ == "__main__":
    unittest.main()
