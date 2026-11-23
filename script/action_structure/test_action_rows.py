import unittest

from action_query import run_query
from card_structure import build_structures
from test_golden import (ARCHETYPES, BLACK_MAGICIAN, EMPEROR_PENGUIN, EMPEROR_PENGUIN_TEXT,
                         PENGUIN_SOLDIER, SINGULARITY_FIEND, SINGULARITY_FIEND_TEXT, card, faq)


BATTLE_DESTROYER = 30000001


class RowsPathTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.cards = [
            card(SINGULARITY_FIEND, name_ja="特異点の悪魔", level=1, race=0x40),
            card(EMPEROR_PENGUIN, name_ja="大皇帝ペンギン", level=5, race=0x40,
                 attribute=0x2, setcode=0x5a),
            card(PENGUIN_SOLDIER, name_ja="ペンギン・ソルジャー", level=2,
                 race=0x40, attribute=0x2, setcode=0x5a),
            card(BLACK_MAGICIAN, name_ja="ブラック・マジシャン", level=7,
                 race=0x2, attribute=0x20),
        ]
        entries = [
            faq(SINGULARITY_FIEND, "特異点の悪魔", SINGULARITY_FIEND_TEXT),
            faq(EMPEROR_PENGUIN, "大皇帝ペンギン", EMPEROR_PENGUIN_TEXT),
        ]
        cls.structures, _ = build_structures(cls.cards, entries, archetypes=ARCHETYPES)

    def query(self, **query):
        return run_query(self.structures, self.cards, query)

    def test_generic_destroy_is_in_the_generic_group(self):
        groups = self.query(actions=["破壞"])["groups"]
        self.assertEqual(groups["泛用"], [SINGULARITY_FIEND])
        self.assertEqual(groups["特定"], [])
        self.assertEqual(groups["全部"], [SINGULARITY_FIEND])

    def test_generic_only_keeps_the_generic_group(self):
        self.assertEqual(self.query(actions=["捨棄"])["groups"]["特定"], [SINGULARITY_FIEND])
        self.assertEqual(self.query(actions=["捨棄"], generic_only=True)["groups"]["全部"], [])

    def test_hit_segments_are_returned(self):
        hit = next(h for h in self.query(actions=["特殊召喚"])["hits"]
                   if h["id"] == EMPEROR_PENGUIN)
        self.assertEqual(len(hit["segments"]), 1)
        self.assertEqual(hit["group"], "特定")

    def test_condition_segment_needs_the_switch(self):
        self.assertNotIn(SINGULARITY_FIEND, self.query(actions=["特殊召喚"])["groups"]["全部"])
        self.assertIn(SINGULARITY_FIEND, self.query(
            actions=["特殊召喚"], include_condition=True)["groups"]["全部"])
        self.assertNotIn(SINGULARITY_FIEND, self.query(
            actions=["特殊召喚"], include_condition=True, kinds=["效果"])["groups"]["全部"])

    def test_from_zone_counts_sub_zones_and_side(self):
        self.assertEqual(self.query(actions=["特殊召喚"], from_zones=["牌組"])["groups"]["全部"],
                         [EMPEROR_PENGUIN])
        self.assertEqual(self.query(actions=["特殊召喚"], from_zones=["手牌"])["groups"]["全部"], [])
        self.assertEqual(self.query(actions=["特殊召喚"], from_zones=[
            {"zone": "牌組", "side": "對手"}])["groups"]["全部"], [])

    def test_inferred_destination_needs_the_switch(self):
        self.assertEqual(self.query(actions=["解放"], to_zones=["墓地"])["groups"]["全部"], [])
        self.assertEqual(self.query(actions=["解放"], to_zones=["墓地"],
                                    include_inferred=True)["groups"]["全部"], [EMPEROR_PENGUIN])

    def test_card_is_judged_against_the_line_candidates(self):
        def hits(cid):
            return self.query(actions=["特殊召喚"], card=cid)["groups"]["全部"]
        self.assertEqual(hits(PENGUIN_SOLDIER), [EMPEROR_PENGUIN])
        self.assertEqual(hits(EMPEROR_PENGUIN), [])
        self.assertEqual(hits(BLACK_MAGICIAN), [])

    def test_condition_needs_a_real_card_on_the_line(self):
        def hits(condition):
            return self.query(actions=["特殊召喚"], condition=condition)["groups"]["全部"]
        self.assertEqual(hits({"op": "屬性比較", "attr": "等級", "cmp": "≤", "value": 2}),
                         [EMPEROR_PENGUIN])
        self.assertEqual(hits({"op": "屬性比較", "attr": "等級", "cmp": "≥", "value": 5}), [])

    def test_the_doer_line_is_not_the_card_acted_on(self):
        cards = self.cards + [card(BATTLE_DESTROYER, name_ja="戦闘破壊者", race=0x1)]
        structures, _ = build_structures(cards, [faq(BATTLE_DESTROYER, "戦闘破壊者", (
            "①：このカードが戦闘で相手の魔法使い族モンスターを破壊した時に発動できる。"
            "自分はデッキから１枚ドローする。"))])

        def hits(cid):
            return run_query(structures, cards, dict(actions=["破壞"], include_condition=True,
                                                     card=cid))["groups"]["全部"]
        self.assertEqual(hits(BLACK_MAGICIAN), [BATTLE_DESTROYER])
        self.assertEqual(hits(BATTLE_DESTROYER), [])


PREAMBLE_CARD = 30000002


class UnknownBlockKindTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.cards = [card(PREAMBLE_CARD, name_ja="前言カード", level=4, race=0x1)]
        cls.structures, _ = build_structures(cls.cards, [faq(PREAMBLE_CARD, "前言カード", (
            "このカードの効果を発動するターン、自分はモンスターを特殊召喚できない。\n"
            "①：相手フィールドのカード１枚を対象として発動できる。そのカードを破壊する。"))])

    def query(self, **query):
        return run_query(self.structures, self.cards, query)

    def test_filtered_out_unknown_block_is_listed_with_the_block_reason(self):
        result = self.query(actions=["特殊召喚"], block_kinds=["召喚條件"])
        self.assertEqual(result["groups"]["未解析"], [PREAMBLE_CARD])
        self.assertEqual(result["unparsed"], [{"id": PREAMBLE_CARD, "reason": None, "segments": [{
            "segment": "b0.s0", "reason": "區塊種類判不出",
            "text": "このカードの効果を発動するターン、自分はモンスターを特殊召喚できない"}]}])

    def test_kept_unknown_block_is_listed_with_the_segment_reason(self):
        result = self.query(actions=["特殊召喚"])
        self.assertEqual([s["reason"] for s in result["unparsed"][0]["segments"]], ["子句解析不出"])

    def test_filtered_out_known_block_is_not_listed(self):
        result = self.query(actions=["破壞"], block_kinds=["召喚條件"])
        self.assertEqual(result["groups"]["全部"], [])
        self.assertEqual(result["groups"]["未解析"], [])


if __name__ == "__main__":
    unittest.main()
