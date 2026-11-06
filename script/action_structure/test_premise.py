"""前提、遊戲狀態與位置繼承(票 05):只走接縫一(查詢判斷)與接縫二(反向檢查),
輸入官方卡文句型與卡片參數,看命中、不命中與整張是否通過反向檢查。

- 「Xが<區域>に存在する(場合|状態で)」把 X 在該區塊的目前位置設成該區域,後續段的
  「從」繼承它、不算推得;前提裡提到的物件就是後文「そのモンスター」指回的物件。
- 遊戲狀態(相手ターンに、自分・相手のメインフェイズに、ダメージステップに…)只記在前提;
  整句只有前提的發動句(「自分メインフェイズに発動できる」)仍整張通過反向檢查。
- 區域的方:明寫「自分の/相手の」記明寫、反向檢查寫出來;沒寫照慣例歸我方但記預設、不寫。
- 主語形子句「<到>に<物件>が特殊召喚された」:到是明寫、寫在物件前;「このカードが特殊召喚した」
  助詞「が」記在對象線,模板照它寫。
"""
import unittest

from action_query import run_query
from card_structure import build_structures
from reverse_check import check_card
from test_golden import ARCHETYPES, SPELL, card, faq

SELF = 10000101
DRAGON_RAVINE = 62265044    # 竜の渓谷(場地魔法)
PENGUIN_SOLDIER = 93920745  # ペンギン・ソルジャー setcode 0x5a
BLACK_MAGICIAN = 46986414


def library(text, **self_kw):
    cards = [
        card(SELF, name_ja="甲", **self_kw),
        card(DRAGON_RAVINE, name_ja="竜の渓谷", type=0x80002),
        card(PENGUIN_SOLDIER, name_ja="ペンギン・ソルジャー", level=2, race=0x40,
             attribute=0x2, setcode=0x5a),
        card(BLACK_MAGICIAN, name_ja="ブラック・マジシャン", level=7, race=0x2,
             attribute=0x20),
    ]
    structures, _ = build_structures(cards, [faq(SELF, "甲", text)],
                                     archetypes=ARCHETYPES)
    return cards, structures


def hits(cards, structures, **query):
    return [h["id"] for h in run_query(structures, cards, query)["hits"]]


def own(structures):
    return next(c for c in structures if c["id"] == SELF)


class PositionPremiseTest(unittest.TestCase):

    def test_premise_sets_current_position_and_later_from_inherits_it(self):
        """「このカードが墓地に存在する場合に発動できる。このカードを特殊召喚する。」:
        從墓地由前提繼承,推得關也命中;整張通過反向檢查。"""
        cards, structures = library(
            "①：このカードが墓地に存在する場合に発動できる。このカードを特殊召喚する。")
        self.assertIn(SELF, hits(cards, structures, actions=["特殊召喚"],
                                 from_zones=["墓地"], card=SELF))
        self.assertNotIn(SELF, hits(cards, structures, actions=["特殊召喚"],
                                    from_zones=["手牌"], card=SELF))
        self.assertEqual(check_card(own(structures)), [])

    def test_premise_before_trigger_and_cost_in_the_same_activation(self):
        """前提 + 條件子句 + 代價子句:前提掛在條件段;整張通過反向檢查。"""
        cards, structures = library(
            "①：このカードが手札に存在する場合、相手がモンスターを特殊召喚した時、"
            "手札からこのカードを捨てて発動できる。そのモンスターを破壊する。")
        self.assertEqual(check_card(own(structures)), [])
        self.assertIn(SELF, hits(cards, structures, actions=["捨棄"],
                                 from_zones=["手牌"], card=SELF))

    def test_existence_premise_object_is_the_one_sono_refers_back_to(self):
        """「自分フィールドに「ペンギン」モンスターが存在する場合に発動できる。
        そのモンスターを破壊する。」:前提裡的物件條件(字段)就是 そのモンスター 的條件,
        從場上(我方)由前提繼承;整張通過反向檢查。"""
        cards, structures = library(
            "①：自分フィールドに「ペンギン」モンスターが存在する場合に発動できる。"
            "そのモンスターを破壊する。")
        own_field = [{"zone": "場上", "side": "我方"}]
        self.assertIn(SELF, hits(cards, structures, actions=["破壞"],
                                 from_zones=own_field, card=PENGUIN_SOLDIER))
        self.assertNotIn(SELF, hits(cards, structures, actions=["破壞"],
                                    from_zones=own_field, card=BLACK_MAGICIAN))
        self.assertEqual(check_card(own(structures)), [])

    def test_negative_existence_premise_on_an_effect_sentence(self):
        """效果句開頭的前提「自分フィールドにモンスターが存在しない場合、」:整張通過。"""
        cards, structures = library(
            "①：自分フィールドにモンスターが存在しない場合、デッキから「竜の渓谷」"
            "１枚を手札に加える。")
        self.assertEqual(check_card(own(structures)), [])
        self.assertIn(SELF, hits(cards, structures, actions=["加入手牌"],
                                 from_zones=["牌組"], card=DRAGON_RAVINE))


class GameStatePremiseTest(unittest.TestCase):

    def test_premise_only_activation_passes_and_following_effect_hits(self):
        """「自分メインフェイズに発動できる。」整句只有前提:整張通過反向檢查,
        後面的效果段照常命中。"""
        cards, structures = library(
            "①：自分メインフェイズに発動できる。デッキから「竜の渓谷」１枚を手札に加える。")
        self.assertEqual(check_card(own(structures)), [])
        self.assertIn(SELF, hits(cards, structures, actions=["加入手牌"],
                                 from_zones=["牌組"], to_zones=["手牌"],
                                 card=DRAGON_RAVINE))

    def test_each_game_state_form_renders_its_own_text(self):
        texts = (
            "①：相手ターンに発動できる。このカードを破壊する。",
            "①：自分・相手のバトルフェイズに発動できる。このカードを破壊する。",
            "①：ダメージステップに発動できる。このカードを破壊する。",
            "①：相手メインフェイズ１に、このカードが墓地に存在する状態で発動できる。"
            "このカードを特殊召喚する。",
            "①：自分エンドフェイズに、手札からこのカードを捨てて発動できる。"
            "デッキから「竜の渓谷」１枚を手札に加える。",
        )
        for text in texts:
            with self.subTest(text=text):
                _, structures = library(text)
                self.assertEqual(check_card(own(structures)), [])


class SideSourceTest(unittest.TestCase):
    """區域的方:明寫才寫「自分の」;沒寫歸我方(預設),查「我方」也命中。"""

    def test_written_and_default_side_both_pass_reverse_check(self):
        for text in ("①：自分の墓地からモンスター１体を手札に加える。",
                     "①：墓地からモンスター１体を手札に加える。",
                     "①：相手の墓地からモンスター１体を手札に加える。",
                     "①：自分の手札・フィールドから魔法カード１枚を墓地へ送る。"):
            with self.subTest(text=text):
                _, structures = library(text)
                self.assertEqual(check_card(own(structures)), [])

    def test_default_side_counts_as_own_side_in_queries(self):
        cards, structures = library("①：墓地からモンスター１体を手札に加える。")
        own_grave = [{"zone": "墓地", "side": "我方"}]
        self.assertIn(SELF, hits(cards, structures, actions=["加入手牌"],
                                 from_zones=own_grave, card=BLACK_MAGICIAN))
        self.assertNotIn(SELF, hits(cards, structures, actions=["加入手牌"],
                                    from_zones=[{"zone": "墓地", "side": "對手"}],
                                    card=BLACK_MAGICIAN))

    def test_field_without_written_side_has_no_side(self):
        """「手札・フィールドから」沒寫方:手牌照慣例是我方,場上不預設(任一方的場上),
        查「場上(我方)」不命中、查「場上」命中;整張仍通過反向檢查。"""
        cards, structures = library(
            "①：手札・フィールドから魔法カード１枚を墓地へ送って発動できる。"
            "このカードを破壊する。")
        self.assertEqual(check_card(own(structures)), [])
        self.assertIn(SELF, hits(cards, structures, actions=["送墓"],
                                 from_zones=["場上"]))
        self.assertIn(SELF, hits(cards, structures, actions=["送墓"],
                                 from_zones=[{"zone": "手牌", "side": "我方"}]))
        self.assertNotIn(SELF, hits(cards, structures, actions=["送墓"],
                                    from_zones=[{"zone": "場上", "side": "我方"}]))


class SubjectClauseTest(unittest.TestCase):

    def test_passive_subject_with_written_destination(self):
        """「このカードが墓地へ送られた場合」:條件段,到是述語寫的墓地;開關開才命中。"""
        cards, structures = library(
            "①：このカードが墓地へ送られた場合に発動できる。デッキから「竜の渓谷」"
            "１枚を手札に加える。")
        self.assertEqual(check_card(own(structures)), [])
        self.assertIn(SELF, hits(cards, structures, actions=["送墓"],
                                 to_zones=["墓地"], card=SELF,
                                 include_condition=True))
        self.assertNotIn(SELF, hits(cards, structures, actions=["送墓"],
                                    to_zones=["墓地"], card=SELF))

    def test_intransitive_subject_form_is_rendered_with_ga(self):
        """「このカードが特殊召喚した場合」:語尾不是被動,助詞「が」照對象線寫回。"""
        cards, structures = library(
            "①：このカードが特殊召喚した場合に発動できる。デッキから「竜の渓谷」"
            "１枚を手札に加える。")
        self.assertEqual(check_card(own(structures)), [])
        self.assertIn(SELF, hits(cards, structures, actions=["特殊召喚"],
                                 card=SELF, include_condition=True))


class OldStylePremiseTest(unittest.TestCase):
    """前提(票 05)與舊式用語(票 11)同時出現的句型。"""

    def test_old_style_field_ue_in_premise_is_written_back_literally(self):
        """「自分フィールド上にモンスターが存在しない場合、このカードは手札から特殊召喚できる」:
        フィールド上 是前提的區域(場上、我方),反向檢查照原文字面寫回「フィールド上」;
        從手牌特殊召喚此卡命中。"""
        cards, structures = library(
            "自分フィールド上にモンスターが存在しない場合、このカードは手札から特殊召喚できる。")
        self.assertEqual(check_card(own(structures)), [])
        self.assertIn(SELF, hits(cards, structures, actions=["特殊召喚"],
                                 from_zones=["手牌"], card=SELF))

    def test_field_ue_before_object_with_wo_is_a_modifier_not_a_front_destination(self):
        """「相手フィールド上にセットされたカード１枚を選択して破壊する」:物件前的「到に」只在
        助詞が時成立,這裡的「相手フィールド上に」是物件修飾,段照樣解析出、查破壞 + 取對象命中。"""
        cards, structures = library(
            "相手フィールド上にセットされたカード１枚を選択して破壊する。")
        self.assertIn(SELF, hits(cards, structures, actions=["破壞"], targeting=True))

    def test_old_style_ni_sonzai_suru_from_is_not_a_front_destination(self):
        """「自分フィールド上に存在するモンスターが破壊された時、〜」:助詞是が,但「に存在する」
        是舊式從的助詞,不是物件前的到;條件段的從 = 場上(我方),整張通過反向檢查。"""
        cards, structures = library(
            "自分フィールド上に存在するモンスターが破壊された時、"
            "デッキから「竜の渓谷」１枚を手札に加える。")
        self.assertEqual(check_card(own(structures)), [])
        self.assertIn(SELF, hits(cards, structures, actions=["破壞"],
                                 from_zones=[{"zone": "場上", "side": "我方"}],
                                 include_condition=True))


if __name__ == "__main__":
    unittest.main()
