"""查詢的從、到指定方時,區域寫任一方、雙方各自、持有者的也命中(spec「比對規則」,照 Q17
「寫得比查詢寬也算」)。"""
import unittest

from action_query import run_query
from card_structure import build_structures
from test_golden import card, faq


EITHER_GRAVE = 30100001   # 自分か相手の墓地の:從的墓地是任一方
BOTH_DRAW = 30100002      # お互いのプレイヤーはデッキから:從的牌組是雙方各自
OWNER_HAND = 30100003     # 持ち主の手札に:到的手牌是持有者
OWN_GRAVE = 30100004      # 自分の墓地の:從的墓地只寫我方
BOTH_SUMMON = 30100005    # お互いのプレイヤーは〜特殊召喚する:到的場上是推得的雙方各自
EITHER_BANISHED = 30100006   # 自分か相手の除外状態の:從的除外是任一方
EITHER_FIELD = 30100007      # 自分か相手のフィールドの:從的場上是任一方
SIDELESS_FIELD = 30100008    # フィールドの:場上沒寫方,建置時照規則記任一方(票 02)
OWN_GRAVE_OBJECT = 30100009  # このカード以外の自分の墓地の:「自分の」是物件的控制方,從的墓地照它記我方
SEND_OPPONENTS = 30100010    # 相手のモンスターを墓地へ送る:到的墓地沒寫方,其他物件記持有者(票 03)
THIS_CARD_REVIVES = 30100011  # このカードが墓地へ送られた場合、このカードを特殊召喚:此卡的墓地記我方
OTHER_REVIVES = 30100012     # モンスターが墓地へ送られた時、そのモンスターを特殊召喚:其他物件的墓地記持有者

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
}


def side_library():
    """這組卡的卡片總表與結構;「兩邊答案一致」的測試也拿它驗網站。"""
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
        """「フィールドのカードを全て破壊する」:場上沒寫方是任一方,破壞 從對手、從我方的場上都命中。"""
        for side in ("我方", "對手"):
            self.assertIn(SIDELESS_FIELD, self.hits(actions=["破壞"], from_zones=[
                {"zone": "場上", "side": side}]), side)

    def test_controller_written_on_the_object_only_hits_that_side(self):
        """「自分の墓地の」寫在物件上:從的墓地是我方,查對手的墓地不命中。"""
        def summon_from_grave(side):
            return self.hits(actions=["特殊召喚"], from_zones=[{"zone": "墓地", "side": side}])
        self.assertIn(OWN_GRAVE_OBJECT, summon_from_grave("我方"))
        self.assertNotIn(OWN_GRAVE_OBJECT, summon_from_grave("對手"))

    def test_sending_opponents_card_hits_the_opponents_graveyard(self):
        """「そのモンスターを墓地へ送る」:到的墓地是持有者,送墓 到對手的墓地命中。"""
        self.assertIn(SEND_OPPONENTS, self.hits(actions=["送墓"], to_zones=[
            {"zone": "墓地", "side": "對手"}]))

    def test_this_cards_graveyard_is_only_own(self):
        """此卡戰鬥破壞送墓後特殊召喚自己:從的墓地是我方,查對手的墓地不命中。"""
        def summon_from_grave(side):
            return self.hits(actions=["特殊召喚"], from_zones=[{"zone": "墓地", "side": side}])
        self.assertIn(THIS_CARD_REVIVES, summon_from_grave("我方"))
        self.assertNotIn(THIS_CARD_REVIVES, summon_from_grave("對手"))

    def test_other_objects_graveyard_hits_both_sides(self):
        for side in ("我方", "對手"):
            self.assertIn(OTHER_REVIVES, self.hits(actions=["特殊召喚"], from_zones=[
                {"zone": "墓地", "side": side}]), side)

    def test_inferred_zone_still_needs_the_switch(self):
        opponent_field = [{"zone": "場上", "side": "對手"}]
        self.assertEqual(self.hits(actions=["特殊召喚"], to_zones=opponent_field), [])
        self.assertEqual(self.hits(actions=["特殊召喚"], to_zones=opponent_field,
                                   include_inferred=True), [BOTH_SUMMON])


if __name__ == "__main__":
    unittest.main()
