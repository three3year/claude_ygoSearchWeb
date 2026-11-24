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
        self.assertEqual(summon_from_grave("對手"), [EITHER_GRAVE])
        self.assertEqual(sorted(summon_from_grave("我方")), [EITHER_GRAVE, OWN_GRAVE])

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
                         [EITHER_GRAVE, OWN_GRAVE])

    def test_inferred_zone_still_needs_the_switch(self):
        opponent_field = [{"zone": "場上", "side": "對手"}]
        self.assertEqual(self.hits(actions=["特殊召喚"], to_zones=opponent_field), [])
        self.assertEqual(self.hits(actions=["特殊召喚"], to_zones=opponent_field,
                                   include_inferred=True), [BOTH_SUMMON])


if __name__ == "__main__":
    unittest.main()
