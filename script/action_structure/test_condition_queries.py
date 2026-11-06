"""條件查詢、引用與泛用分組(票 07):只走接縫一(查詢判斷)與接縫二(反向檢查),
輸入官方卡文與卡片參數,看命中、分組與反向檢查。

- 只給條件的查詢:卡片總表裡存在一張實卡同時滿足查詢條件與物件條件就命中。
- 泛用組:只靠泛用物件(條件式除大類、位置、控制方外沒有條件)命中的卡;`generic_only` 只查這組。
- S/X/L/融合召喚是特殊召喚的下位:查「特殊召喚」含它們,查「融合召喚」不含其他。
- 記載:「「X」またはそのカード名が記されたカード」= 卡名∋X 或 卡文含「X」(含括號精確比對)。
- 卡名範圍與引用:「No.101」～「No.107」、「そのモンスターのランクと同じ数値のレベル」;
  引用時在被引用物件的候選卡裡找得到一組讓全部條件成立即可。
"""
import unittest

from action_query import run_query
from card_structure import build_structures
from reverse_check import check_card
from test_golden import (ARCHETYPES, BLACK_MAGICIAN, EMPEROR_PENGUIN,
                         EMPEROR_PENGUIN_TEXT, PENGUIN_SOLDIER,
                         SINGULARITY_FIEND, SINGULARITY_FIEND_TEXT, SPELL,
                         TRAP, card, faq)

MONSTER = {"op": "大類", "value": "怪獸"}
FUSION_SUMMONER = 20000001   # 測試用:「ペンギン」モンスターを融合召喚する


class GenericGroupTest(unittest.TestCase):
    """三組結果:特定、泛用、全部;只給條件的查詢化成指定卡的判法。"""

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
            card(24094653, name_ja="強欲な壺", type=SPELL),
            card(FUSION_SUMMONER, name_ja="融合する者"),
        ]
        entries = [
            faq(SINGULARITY_FIEND, "特異点の悪魔", SINGULARITY_FIEND_TEXT),
            faq(EMPEROR_PENGUIN, "大皇帝ペンギン", EMPEROR_PENGUIN_TEXT),
            faq(FUSION_SUMMONER, "融合する者",
                "①：EXデッキから「ペンギン」モンスター１体を融合召喚する。"),
        ]
        cls.structures, _ = build_structures(cls.cards, entries,
                                             archetypes=ARCHETYPES)

    def query(self, **query):
        return run_query(self.structures, self.cards, query)

    def test_destroy_that_monster_is_in_the_generic_group(self):
        """特異点の悪魔 的「そのモンスターを破壊する」:物件只有大類 → 泛用組;
        只查泛用組也找得到。"""
        result = self.query(actions=["破壞"])
        self.assertIn(SINGULARITY_FIEND, result["groups"]["泛用"])
        self.assertNotIn(SINGULARITY_FIEND, result["groups"]["特定"])
        self.assertIn(SINGULARITY_FIEND, result["groups"]["全部"])
        self.assertIn(SINGULARITY_FIEND,
                      self.query(actions=["破壞"], generic_only=True)["groups"]["全部"])

    def test_discard_with_this_card_is_specific(self):
        """「手札からこのカードと魔法カード１枚を捨てて」:物件0 是特定的卡,
        同一段的「魔法カード１枚」雖泛用,段不算只靠泛用物件命中 → 特定組。"""
        result = self.query(actions=["捨棄"])
        self.assertIn(SINGULARITY_FIEND, result["groups"]["特定"])
        self.assertNotIn(SINGULARITY_FIEND, result["groups"]["泛用"])
        self.assertNotIn(SINGULARITY_FIEND,
                         self.query(actions=["捨棄"], generic_only=True)["groups"]["全部"])

    def test_archetype_object_is_specific(self):
        """大皇帝ペンギン 的「「ペンギン」モンスター」有字段條件 → 特定組。"""
        result = self.query(actions=["特殊召喚"], from_zones=["牌組"])
        self.assertIn(EMPEROR_PENGUIN, result["groups"]["特定"])
        self.assertNotIn(EMPEROR_PENGUIN, result["groups"]["泛用"])

    def test_condition_only_monster_from_deck_special_summon(self):
        """只給條件「怪獸 牌組 → 特殊召喚」:總表裡有 ペンギン・ソルジャー 滿足
        「「大皇帝ペンギン」以外の「ペンギン」モンスター」→ 大皇帝ペンギン 命中;
        條件改成魔法卡就沒有實卡同時滿足 → 不命中。"""
        self.assertIn(EMPEROR_PENGUIN,
                      self.query(actions=["特殊召喚"], from_zones=["牌組"],
                                 condition=MONSTER)["groups"]["全部"])
        spell = {"op": "大類", "value": "魔法"}
        self.assertNotIn(EMPEROR_PENGUIN,
                         self.query(actions=["特殊召喚"], from_zones=["牌組"],
                                    condition=spell)["groups"]["全部"])

    def test_condition_only_destroy_monster_hits_generic_card(self):
        """只給條件「破壞 怪獸」:特異点の悪魔 的 そのモンスター 代得進去,仍在泛用組。"""
        result = self.query(actions=["破壞"], condition=MONSTER)
        self.assertIn(SINGULARITY_FIEND, result["groups"]["泛用"])

    def test_fusion_summon_is_a_kind_of_special_summon(self):
        """「融合召喚する」:查「特殊召喚」命中(下位詞),查「融合召喚」也命中;
        大皇帝ペンギン 的「特殊召喚する」查「融合召喚」不命中。"""
        self.assertIn(FUSION_SUMMONER,
                      self.query(actions=["特殊召喚"], card=PENGUIN_SOLDIER)["groups"]["全部"])
        self.assertIn(FUSION_SUMMONER,
                      self.query(actions=["融合召喚"])["groups"]["全部"])
        self.assertNotIn(EMPEROR_PENGUIN,
                         self.query(actions=["融合召喚"])["groups"]["全部"])

    def test_fusion_summon_card_passes_reverse_check(self):
        structure = next(c for c in self.structures if c["id"] == FUSION_SUMMONER)
        self.assertEqual(check_card(structure), [])


if __name__ == "__main__":
    unittest.main()
