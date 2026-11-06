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


BUSTER_MODE = 80280737          # バスター・モード(陷阱)
CRIMSON_BLADER_BUSTER = 50604072  # クリムゾン・ブレーダー／バスター(票 08 的標準卡,這裡只借①做記載夾具)
CRIMSON_BLADER_BUSTER_TEXT = (
    "このカードは通常召喚できず、「バスター・モード」の効果でのみ特殊召喚できる。\n"
    "このカード名の①の効果は１ターンに１度しか使用できない。\n"
    "①：手札のこのカードを相手に見せて発動できる。「バスター・モード」またはそのカード名が"
    "記されたカード１枚をデッキから手札に加え、このカードをデッキに戻す。\n"
    "②：相手はEXデッキから特殊召喚されたレベル５以上のモンスターの効果を発動できない。\n"
    "③：このカードが破壊された場合に発動できる。自分の墓地から「クリムゾン・ブレーダー」"
    "１体を特殊召喚する。")
BUSTER_SNIPER = 39015           # バスター・スナイパー(真實卡:「X」以外の「Y」のカード名が記されたモンスター)
BUSTER_SNIPER_TEXT = (
    "このカード名の①②の効果はそれぞれ１ターンに１度しか使用できない。①：このカードを"
    "リリースして発動できる。手札・デッキから「バスター・スナイパー」以外の「バスター・モード」"
    "のカード名が記されたモンスター１体を特殊召喚する。この効果を発動したターン、自分は"
    "SモンスターしかEXデッキから特殊召喚できない。②：自分フィールドの表側表示モンスター"
    "１体を対象として発動できる。EXデッキのSモンスター１体を相手に見せ、対象のモンスターの"
    "種族・属性はターン終了時まで、見せたモンスターと同じになる。")
BUSTER_SEARCHER = 20000002      # 測試用:「X」またはそのカード名が記されたカード
BUSTER_MODE_ZERO = 20000003     # 測試用:卡名含「バスター・モード」但不等、卡文沒引用它
MENTIONS_ZERO = 20000004        # 測試用:卡文引用「バスター・モード・ゼロ」,不算記載「バスター・モード」
MENTION_MONSTER = 20000005      # 測試用:「X」のカード名が記されたモンスター


class MentionTest(unittest.TestCase):
    """記載(名稱):卡文含「X」(含括號精確比對),查詢時直接掃卡文、不建表。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = [
            card(BLACK_MAGICIAN, name_ja="ブラック・マジシャン", level=7,
                 race=0x2, attribute=0x20),
            card(BUSTER_MODE, name_ja="バスター・モード", type=TRAP),
            card(CRIMSON_BLADER_BUSTER, name_ja="クリムゾン・ブレーダー／バスター",
                 type=0x2000021, level=10, race=0x1, attribute=0x4,
                 setcode=0x104f),
            card(BUSTER_SNIPER, name_ja="バスター・スナイパー", level=4,
                 race=0x8000, attribute=0x1),
            card(BUSTER_SEARCHER, name_ja="バスター探し"),
            card(BUSTER_MODE_ZERO, name_ja="バスター・モード・ゼロ"),
            card(MENTIONS_ZERO, name_ja="ゼロ探し"),
            card(MENTION_MONSTER, name_ja="記載探し"),
        ]
        entries = [
            faq(CRIMSON_BLADER_BUSTER, "クリムゾン・ブレーダー／バスター",
                CRIMSON_BLADER_BUSTER_TEXT),
            faq(BUSTER_SNIPER, "バスター・スナイパー", BUSTER_SNIPER_TEXT),
            faq(BUSTER_SEARCHER, "バスター探し",
                "①：デッキから「バスター・モード」またはそのカード名が記されたカード１枚を"
                "手札に加える。"),
            faq(BUSTER_MODE_ZERO, "バスター・モード・ゼロ", "①：このカードを破壊する。"),
            faq(MENTIONS_ZERO, "ゼロ探し",
                "①：デッキから「バスター・モード・ゼロ」１枚を手札に加える。"),
            faq(MENTION_MONSTER, "記載探し",
                "①：デッキから「バスター・モード」のカード名が記されたモンスター１体を"
                "特殊召喚する。"),
        ]
        cls.structures, _ = build_structures(cls.cards, entries,
                                             archetypes=ARCHETYPES)

    def hits(self, **query):
        return [h["id"] for h in run_query(self.structures, self.cards, query)["hits"]]

    def test_black_magician_is_not_buster_mode_nor_mentions_it(self):
        """「「バスター・モード」またはそのカード名が記されたカード」:黑魔導不符。"""
        self.assertNotIn(BUSTER_SEARCHER,
                         self.hits(actions=["加入手牌"], card=BLACK_MAGICIAN))

    def test_the_named_card_itself_fits(self):
        self.assertIn(BUSTER_SEARCHER,
                      self.hits(actions=["加入手牌"], card=BUSTER_MODE))

    def test_card_whose_text_quotes_the_name_fits(self):
        """クリムゾン・ブレーダー／バスター 的卡文含「バスター・モード」→ 符合記載。"""
        self.assertIn(BUSTER_SEARCHER,
                      self.hits(actions=["加入手牌"], card=CRIMSON_BLADER_BUSTER))
        self.assertIn(BUSTER_SEARCHER,
                      self.hits(actions=["加入手牌"], card=BUSTER_SNIPER))

    def test_mention_is_exact_with_brackets(self):
        """卡名只是含「バスター・モード」子字串、卡文沒引用它 → 不符;
        卡文引用的是「バスター・モード・ゼロ」→ 不算記載「バスター・モード」。"""
        self.assertNotIn(BUSTER_SEARCHER,
                         self.hits(actions=["加入手牌"], card=BUSTER_MODE_ZERO))
        self.assertNotIn(BUSTER_SEARCHER,
                         self.hits(actions=["加入手牌"], card=MENTIONS_ZERO))

    def test_condition_only_query_finds_a_mentioning_card(self):
        """只給條件「記載 バスター・モード」:總表裡有實卡(クリムゾン・ブレーダー／バスター)符合。"""
        mention = {"op": "記載", "text": "バスター・モード"}
        self.assertIn(BUSTER_SEARCHER,
                      self.hits(actions=["加入手牌"], condition=mention))
        self.assertNotIn(BUSTER_SEARCHER,
                         self.hits(actions=["加入手牌"],
                                   condition={"op": "記載", "text": "ペンギン"}))

    def test_real_card_buster_sniper_mention_monster(self):
        """バスター・スナイパー ①:「バスター・スナイパー」以外の「バスター・モード」のカード名が
        記されたモンスター:クリムゾン・ブレーダー／バスター 符合;自己(以外)、黑魔導、
        バスター・モード(陷阱)不符。"""
        self.assertIn(BUSTER_SNIPER,
                      self.hits(actions=["特殊召喚"], from_zones=["牌組"],
                                card=CRIMSON_BLADER_BUSTER))
        for cid in (BUSTER_SNIPER, BLACK_MAGICIAN, BUSTER_MODE):
            self.assertNotIn(BUSTER_SNIPER,
                             self.hits(actions=["特殊召喚"], card=cid), cid)

    def test_mention_cards_pass_reverse_check(self):
        for cid in (BUSTER_SEARCHER, MENTION_MONSTER):
            structure = next(c for c in self.structures if c["id"] == cid)
            self.assertEqual(check_card(structure), [], cid)


if __name__ == "__main__":
    unittest.main()
