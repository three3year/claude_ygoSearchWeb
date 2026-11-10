"""物件修飾:閉集與卡片屬性(m3 票 04)。

卡片總表查得到的修飾語(子類型、攻守與階級的數值、區域字面、連體子句、「〜以外の」、「AまたはB」)
指定卡代入時判得了。接縫只有查詢判斷(`run_query`)與反向檢查(`check_card`);官方文本逐字寫在測試裡。
"""
import unittest

from action_query import run_query
from card_structure import build_structures
from reverse_check import check_card
from test_golden import SPELL, TRAP, card, faq

NORMAL_MONSTER = 0x11
SPIRIT_MONSTER = 0x221
CONTINUOUS_TRAP = 0x20004
BLACK_MAGICIAN = 46986414
POT_OF_GREED = 24094653

SPIRIT_RING = 276357
SPIRIT_RING_TEXT = (
    "「霊魂の円環」の①②の効果はそれぞれ１ターンに１度しか使用できない。"
    "①：このカードが魔法＆罠ゾーンに存在し、自分フィールドの表側表示のスピリットモンスターが"
    "自分の手札に戻った場合、相手フィールドのカード１枚を対象として発動できる。そのカードを破壊する。"
    "②：相手モンスターの攻撃宣言時に自分の墓地のスピリットモンスター１体を除外して発動できる。"
    "その攻撃を無効にし、その後バトルフェイズを終了する。")
YATA_GARASU = 3078576   # 八汰烏:靈魂怪獸


class _Golden(unittest.TestCase):
    cards = []
    faq = []
    archetypes = None

    @classmethod
    def setUpClass(cls):
        cls.structures, _ = build_structures(cls.cards, cls.faq, archetypes=cls.archetypes)

    def run_(self, **query):
        return run_query(self.structures, self.cards, query)

    def hits(self, **query):
        return [hit["id"] for hit in self.run_(**query)["hits"]]

    def unparsed(self, **query):
        return self.run_(**query)["groups"]["未解析"]

    def assertJudgedMiss(self, cid, **query):
        """判得了、不命中:不在命中組,也不落進未解析組。"""
        self.assertNotIn(cid, self.hits(**query))
        self.assertNotIn(cid, self.unparsed(**query))

    def assertWritesBack(self, cid, text):
        """那一段存在(原文正好是 `text`),而且通過反向檢查。"""
        structure = next(s for s in self.structures if s["id"] == cid)
        texts = [seg["text"] for block in structure["blocks"] for seg in block["segments"]]
        self.assertIn(text, texts)
        failed = {f["segment"] for f in check_card(structure) if f["segment"]}
        self.assertNotIn(text, [seg["text"] for block in structure["blocks"]
                                for seg in block["segments"] if seg["id"] in failed])

    def assertWholeCardPasses(self, cid):
        structure = next(s for s in self.structures if s["id"] == cid)
        self.assertEqual(check_card(structure), [])


class SpiritRingTest(_Golden):
    """霊魂の円環 276357:「スピリットモンスター」的子類型字面(使用者故事 25)。"""
    cards = [
        card(SPIRIT_RING, name_ja="霊魂の円環", type=CONTINUOUS_TRAP),
        card(YATA_GARASU, name_ja="八汰烏", type=SPIRIT_MONSTER, level=2, race=0x8,
             attribute=0x8, atk=200),
        card(BLACK_MAGICIAN, name_ja="ブラック・マジシャン", type=NORMAL_MONSTER, level=7,
             race=0x2, attribute=0x20, atk=2500),
    ]
    faq = [faq(SPIRIT_RING, "霊魂の円環", SPIRIT_RING_TEXT)]

    def test_banish_hits_for_a_spirit_monster(self):
        """查「除外」指定靈魂怪獸:命中「自分の墓地のスピリットモンスター１体を除外して」。"""
        self.assertIn(SPIRIT_RING, self.hits(actions=["除外"], card=YATA_GARASU))

    def test_banish_misses_for_a_non_spirit_monster(self):
        self.assertJudgedMiss(SPIRIT_RING, actions=["除外"], card=BLACK_MAGICIAN)

    def test_the_banish_cost_writes_back_to_its_text(self):
        self.assertWritesBack(SPIRIT_RING, "自分の墓地のスピリットモンスター１体を除外して")


DARK_BURST = 674561
DARK_BURST_TEXT = (
    "①：自分の墓地の攻撃力１５００以下の闇属性モンスター１体を対象として発動できる。"
    "その闇属性モンスターを手札に加える。")
SANGAN = 26202165
SANGAN_TEXT = (
    "このカード名の効果は１ターンに１度しか使用できない。\n"
    "①：このカードがフィールドから墓地へ送られた場合に発動する。"
    "デッキから攻撃力１５００以下のモンスター１体を手札に加える。"
    "このターン、自分はこの効果で手札に加えたカード及びその同名カードの効果を発動できない。")
KURIBOH = 40640057            # クリボー:闇、攻 300
LUSTER_DRAGON = 11091375      # サファイアドラゴン:風、攻 1900
ATK_UNKNOWN = 10000           # 万物創世龍:攻擊力「？」(卡片總表記 -2)

_STAT_CARDS = [
    card(KURIBOH, name_ja="クリボー", level=1, race=0x8, attribute=0x20, atk=300, **{"def": 200}),
    card(BLACK_MAGICIAN, name_ja="ブラック・マジシャン", type=NORMAL_MONSTER, level=7,
         race=0x2, attribute=0x20, atk=2500, **{"def": 2100}),
    card(LUSTER_DRAGON, name_ja="サファイアドラゴン", type=NORMAL_MONSTER, level=4,
         race=0x2000, attribute=0x8, atk=1900, **{"def": 1600}),
    card(ATK_UNKNOWN, name_ja="万物創世龍", level=10, race=0x2000, attribute=0x20, atk=-2,
         **{"def": -2}),
    card(POT_OF_GREED, name_ja="強欲な壺", type=SPELL),
]


class DarkBurstTest(_Golden):
    """ダーク・バースト 674561:「攻撃力１５００以下の闇属性モンスター１体」(使用者故事 23)。
    加入手牌那一段的物件是「その闇属性モンスター」(票 05 的回指),這裡只驗取對象的那一段。"""
    cards = [card(DARK_BURST, name_ja="ダーク・バースト", type=SPELL)] + _STAT_CARDS
    faq = [faq(DARK_BURST, "ダーク・バースト", DARK_BURST_TEXT)]

    def test_targets_a_dark_monster_with_1500_or_less_attack(self):
        self.assertIn(DARK_BURST, self.hits(targeting=True, card=KURIBOH))

    def test_does_not_target_a_dark_monster_with_more_attack(self):
        self.assertNotIn(DARK_BURST, self.hits(targeting=True, card=BLACK_MAGICIAN))

    def test_does_not_target_a_non_dark_monster(self):
        self.assertNotIn(DARK_BURST, self.hits(targeting=True, card=LUSTER_DRAGON))

    def test_the_targeting_declaration_writes_back_to_its_text(self):
        self.assertWritesBack(DARK_BURST, "自分の墓地の攻撃力１５００以下の闇属性モンスター１体を対象として")


class SanganTest(_Golden):
    """クリッター 26202165:「デッキから攻撃力１５００以下のモンスター１体を手札に加える」。"""
    cards = [card(SANGAN, name_ja="クリッター", level=3, race=0x8, attribute=0x20, atk=1000,
                  **{"def": 600})] + _STAT_CARDS
    faq = [faq(SANGAN, "クリッター", SANGAN_TEXT)]

    def test_add_to_hand_hits_for_a_monster_with_1500_or_less_attack(self):
        self.assertIn(SANGAN, self.hits(actions=["加入手牌"], card=KURIBOH))

    def test_add_to_hand_misses_for_a_monster_with_more_attack(self):
        self.assertJudgedMiss(SANGAN, actions=["加入手牌"], card=LUSTER_DRAGON)

    def test_add_to_hand_misses_for_a_monster_whose_attack_is_unknown(self):
        """攻擊力「？」的怪獸沒有數值可比,不符。"""
        self.assertJudgedMiss(SANGAN, actions=["加入手牌"], card=ATK_UNKNOWN)

    def test_add_to_hand_misses_for_a_spell(self):
        self.assertJudgedMiss(SANGAN, actions=["加入手牌"], card=POT_OF_GREED)

    def test_condition_only_query_compares_attack(self):
        """只給條件:攻擊力 2000 以上的怪獸代不進去,攻擊力 1000 以下的代得進去。"""
        strong = {"op": "屬性比較", "attr": "攻擊力", "cmp": "≥", "value": 2000}
        weak = {"op": "屬性比較", "attr": "攻擊力", "cmp": "≤", "value": 1000}
        self.assertNotIn(SANGAN, self.hits(actions=["加入手牌"], condition=strong))
        self.assertIn(SANGAN, self.hits(actions=["加入手牌"], condition=weak))

    def test_the_search_writes_back_to_its_text(self):
        self.assertWritesBack(SANGAN, "デッキから攻撃力１５００以下のモンスター１体を手札に加える")


if __name__ == "__main__":
    unittest.main()
