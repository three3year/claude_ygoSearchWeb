import unittest

from action_query import run_query
from card_structure import build_structures
from test_golden import card, faq


EITHER_GRAVE = 30100001
BOTH_DRAW = 30100002
OWNER_HAND = 30100003
OWN_GRAVE = 30100004
BOTH_SUMMON = 30100005
EITHER_BANISHED = 30100006
EITHER_FIELD = 30100007
SIDELESS_FIELD = 30100008
OWN_GRAVE_OBJECT = 30100009
SEND_OPPONENTS = 30100010
THIS_CARD_REVIVES = 30100011
OTHER_REVIVES = 30100012
OPPONENT_SELF_HAND = 30100013

TEXTS = {
    EITHER_GRAVE: ("①：自分か相手の墓地のモンスター１体を対象として発動できる。"
                   "そのモンスターを自分フィールドに特殊召喚する。"),
    BOTH_DRAW: "①：お互いのプレイヤーはデッキから１枚ドローする。",
    OWNER_HAND: ("①：相手フィールドのモンスター１体を対象として発動できる。"
                 "そのモンスターを持ち主の手札に戻す。"),
    OWN_GRAVE: ("①：自分の墓地のモンスター１体を対象として発動できる。"
                "そのモンスターを特殊召喚する。"),
    BOTH_SUMMON: "①：お互いのプレイヤーはデッキからモンスター１体を特殊召喚する。",
    EITHER_BANISHED: ("①：自分か相手の除外状態のモンスター１体を対象として発動できる。"
                      "そのモンスターを墓地に戻す。"),
    EITHER_FIELD: ("①：自分か相手のフィールドのカード１枚を対象として発動できる。"
                   "そのカードを破壊する。"),
    SIDELESS_FIELD: "①：フィールドのカードを全て破壊する。",
    OWN_GRAVE_OBJECT: ("①：このカード以外の自分の墓地のモンスター１体を対象として発動できる。"
                       "そのモンスターを特殊召喚する。"),
    SEND_OPPONENTS: ("①：相手フィールドのモンスター１体を対象として発動できる。"
                     "そのモンスターを墓地へ送る。"),
    THIS_CARD_REVIVES: ("①：このカードが戦闘で破壊され墓地へ送られた場合に発動できる。"
                        "このカードを特殊召喚する。"),
    OTHER_REVIVES: ("①：モンスターが戦闘で破壊され墓地へ送られた時に発動できる。"
                    "そのモンスターを特殊召喚する。"),
    OPPONENT_SELF_HAND: "①：相手は自身の手札を１枚選んで捨てる。",
}


def side_library():
    cards = [card(cid, name_ja=f"方テスト{cid}", level=4, race=0x1) for cid in TEXTS]
    structures, _ = build_structures(
        cards, [faq(cid, f"方テスト{cid}", text) for cid, text in TEXTS.items()])
    return cards, structures


class SideCoverageTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.cards, cls.structures = side_library()

    def hits(self, **query):
        return run_query(self.structures, self.cards, query)["groups"]["全部"]

    def test_either_side_zone_hits_both_sides(self):
        def summon_from_grave(side):
            return self.hits(actions=["特殊召喚"], from_zones=[{"zone": "墓地", "side": side}])
        self.assertEqual(sorted(summon_from_grave("對手")), [EITHER_GRAVE, OTHER_REVIVES])
        self.assertEqual(sorted(summon_from_grave("我方")),
                         [EITHER_GRAVE, OWN_GRAVE, OWN_GRAVE_OBJECT, THIS_CARD_REVIVES,
                          OTHER_REVIVES])

    def test_each_side_zone_hits_both_sides(self):
        for side in ("我方", "對手"):
            self.assertEqual(self.hits(actions=["抽牌"], from_zones=[
                {"zone": "牌組", "side": side}]), [BOTH_DRAW], side)

    def test_owner_zone_hits_both_sides(self):
        for side in ("我方", "對手"):
            self.assertEqual(self.hits(actions=["返回"], to_zones=[
                {"zone": "手牌", "side": side}]), [OWNER_HAND], side)

    def test_written_side_still_only_hits_that_side(self):
        self.assertEqual(self.hits(actions=["返回"], from_zones=[
            {"zone": "場上", "side": "我方"}]), [])
        self.assertEqual(self.hits(actions=["返回"], from_zones=[
            {"zone": "場上", "side": "對手"}]), [OWNER_HAND])

    def test_query_without_side_is_unchanged(self):
        self.assertEqual(sorted(self.hits(actions=["特殊召喚"], from_zones=["墓地"])),
                         [EITHER_GRAVE, OWN_GRAVE, OWN_GRAVE_OBJECT, THIS_CARD_REVIVES,
                          OTHER_REVIVES])

    def test_sideless_field_hits_both_sides(self):
        for side in ("我方", "對手"):
            self.assertIn(SIDELESS_FIELD, self.hits(actions=["破壞"], from_zones=[
                {"zone": "場上", "side": side}]), side)

    def test_controller_written_on_the_object_only_hits_that_side(self):
        def summon_from_grave(side):
            return self.hits(actions=["特殊召喚"], from_zones=[{"zone": "墓地", "side": side}])
        self.assertIn(OWN_GRAVE_OBJECT, summon_from_grave("我方"))
        self.assertNotIn(OWN_GRAVE_OBJECT, summon_from_grave("對手"))

    def test_sending_opponents_card_hits_the_opponents_graveyard(self):
        self.assertIn(SEND_OPPONENTS, self.hits(actions=["送墓"], to_zones=[
            {"zone": "墓地", "side": "對手"}]))

    def test_this_cards_graveyard_is_only_own(self):
        def summon_from_grave(side):
            return self.hits(actions=["特殊召喚"], from_zones=[{"zone": "墓地", "side": side}])
        self.assertIn(THIS_CARD_REVIVES, summon_from_grave("我方"))
        self.assertNotIn(THIS_CARD_REVIVES, summon_from_grave("對手"))

    def test_other_objects_graveyard_hits_both_sides(self):
        for side in ("我方", "對手"):
            self.assertIn(OTHER_REVIVES, self.hits(actions=["特殊召喚"], from_zones=[
                {"zone": "墓地", "side": side}]), side)

    def test_self_zone_hits_the_side_of_the_segment_agent(self):
        def discard_from_hand(side):
            return self.hits(actions=["捨棄"], from_zones=[{"zone": "手牌", "side": side}])
        self.assertEqual(discard_from_hand("對手"), [OPPONENT_SELF_HAND])
        self.assertEqual(discard_from_hand("我方"), [])

    def test_inferred_zone_still_needs_the_switch(self):
        opponent_field = [{"zone": "場上", "side": "對手"}]
        self.assertEqual(self.hits(actions=["特殊召喚"], to_zones=opponent_field), [])
        self.assertEqual(self.hits(actions=["特殊召喚"], to_zones=opponent_field,
                                   include_inferred=True), [BOTH_SUMMON])


if __name__ == "__main__":
    unittest.main()
