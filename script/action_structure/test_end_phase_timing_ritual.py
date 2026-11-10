"""標準卡剩下的時點與降臨(m3 票 11):只走接縫一(查詢判斷)與接縫二(反向檢查)。

- 「「X」により降臨」:召喚手續段,動作詞 儀式召喚,原因 效果帶物件 X,極性 做。
- 「Xした/されたターンのエンドフェイズに」:前提 本回合發生過(指向那個動作的條件段)且
  遊戲狀態 結束階段;舊式「〜ターンのエンドフェイズ時」同一個讀法。
- 時點列舉「〜ターンのエンドフェイズ及び、〜ターンのエンドフェイズに」:兩個時點的或。
官方文本逐字寫在測試裡(`data/sources/` 不入版控)。
"""
import unittest

from action_query import run_query
from card_structure import build_structures
from reverse_check import check_card
from test_golden import card, faq

RITUAL_MONSTER = 0x81
RITUAL_SPELL = 0x82

LAW_GUARDIAN = 3627449      # ローガーディアン
LAW_GUARDIAN_TEXT = (
    "「ローの祈り」により降臨。場か手札から、星の数が合計７個以上になるようカードを"
    "生け贄に捧げなければならない。")
LAW_PRAYER = 43694075       # ローの祈り


def build(cards, faqs):
    structures, _ = build_structures(cards, faqs)
    return structures


def hits(cards, structures, **query):
    return [h["id"] for h in run_query(structures, cards, query)["hits"]]


def own(structures, cid):
    return next(c for c in structures if c["id"] == cid)


def failed_texts(structure):
    """反向檢查沒過的段的原文(段外殘留與段樹的列 None)。"""
    texts = {s["id"]: s["text"] for b in structure["blocks"] for s in b["segments"]}
    return [texts.get(f["segment"]) for f in check_card(structure)]


class LawGuardianTest(unittest.TestCase):
    """ローガーディアン 3627449:「「ローの祈り」により降臨」。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = [
            card(LAW_GUARDIAN, name_ja="ローガーディアン", type=RITUAL_MONSTER, level=7,
                 race=0x1, attribute=0x10, atk=2050, **{"def": 2500}),
            card(LAW_PRAYER, name_ja="ローの祈り", type=RITUAL_SPELL),
        ]
        cls.structures = build(cls.cards, [faq(LAW_GUARDIAN, "ローガーディアン",
                                               LAW_GUARDIAN_TEXT)])

    def test_ritual_summon_hits_the_descent_line(self):
        """查「儀式召喚」命中「「ローの祈り」により降臨」(召喚手續段,預設就看)。"""
        self.assertIn(LAW_GUARDIAN, hits(self.cards, self.structures, actions=["儀式召喚"]))

    def test_special_summon_hits_through_the_hypernym(self):
        """儀式召喚是特殊召喚的下位詞:查「特殊召喚」也命中。"""
        self.assertIn(LAW_GUARDIAN, hits(self.cards, self.structures, actions=["特殊召喚"]))

    def test_other_actions_do_not_hit_the_descent_line(self):
        """查「融合召喚」不命中;查「儀式召喚」只算不能/只能的極性時也不命中(極性是做)。"""
        self.assertNotIn(LAW_GUARDIAN, hits(self.cards, self.structures, actions=["融合召喚"]))
        self.assertNotIn(LAW_GUARDIAN, hits(self.cards, self.structures, actions=["儀式召喚"],
                                            polarities=["不能", "只能"]))

    def test_descent_line_writes_back(self):
        """降臨句寫回原文相符(第二句的「〜になるよう」物件修飾不在本票)。"""
        self.assertNotIn("「ローの祈り」により降臨",
                         failed_texts(own(self.structures, LAW_GUARDIAN)))


SAURAVIS = 4810828          # 古聖戴サウラヴィス
SAURAVIS_TEXT = (
    "「精霊の祝福」により降臨\n"
    "①：自分フィールドのモンスターを対象とする魔法・罠・モンスターの効果を相手が発動した時、"
    "このカードを手札から捨てて発動できる。その発動を無効にする。")
SPIRIT_BLESSING = 37626500  # 精霊の祝福


class DescentWithoutPeriodTest(unittest.TestCase):
    """古聖戴サウラヴィス 4810828:降臨句不以句號結尾,被區塊切分歸成素材行。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = [
            card(SAURAVIS, name_ja="古聖戴サウラヴィス", type=0xa1, level=7, race=0x2000,
                 attribute=0x10, atk=2600, **{"def": 2800}),
            card(SPIRIT_BLESSING, name_ja="精霊の祝福", type=RITUAL_SPELL),
        ]
        cls.structures = build(cls.cards, [faq(SAURAVIS, "古聖戴サウラヴィス", SAURAVIS_TEXT)])

    def test_ritual_summon_hits(self):
        self.assertIn(SAURAVIS, hits(self.cards, self.structures, actions=["儀式召喚"]))

    def test_descent_line_writes_back(self):
        self.assertNotIn("「精霊の祝福」により降臨",
                         failed_texts(own(self.structures, SAURAVIS)))


LEARNER_DEVICE = 42149850   # 使い捨て学習装置
LEARNER_DEVICE_TEXT = (
    "このカード名の②の効果は１ターンに１度しか使用できない。①：装備モンスターの攻撃力は、"
    "自分の墓地のモンスターの数×２００アップする。②：このカードがフィールドから墓地へ送られた"
    "ターンのエンドフェイズに発動できる。このカードを自分フィールドにセットする。"
    "この効果でセットしたこのカードはフィールドから離れた場合に除外される。")
LEAVE_SENTENCE = "この効果でセットしたこのカードはフィールドから離れた場合に除外される"


class LearnerDeviceTest(unittest.TestCase):
    """使い捨て学習装置 42149850 ②:「このカードがフィールドから墓地へ送られたターンのエンドフェイズに
    発動できる」。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = [card(LEARNER_DEVICE, name_ja="使い捨て学習装置", type=0x40002)]
        cls.structures = build(cls.cards, [faq(LEARNER_DEVICE, "使い捨て学習装置",
                                               LEARNER_DEVICE_TEXT)])

    def test_sent_to_graveyard_is_a_condition_segment(self):
        """「フィールドから墓地へ送られたターン」是條件段:查「送墓,從場上」開條件段命中,
        關掉不命中。"""
        query = dict(actions=["送墓"], from_zones=["場上"], card=LEARNER_DEVICE)
        self.assertIn(LEARNER_DEVICE, hits(self.cards, self.structures,
                                           include_condition=True, **query))
        self.assertNotIn(LEARNER_DEVICE, hits(self.cards, self.structures, **query))

    def test_set_inherits_the_graveyard_from_the_condition(self):
        """後面的「このカードを自分フィールドにセットする」從墓地出發(繼承條件段的到)。"""
        self.assertIn(LEARNER_DEVICE, hits(self.cards, self.structures, actions=["覆蓋"],
                                           from_zones=["墓地"], card=LEARNER_DEVICE))

    def test_activation_sentence_writes_back(self):
        """發動句的兩段(條件段、只有前提的段)寫回原文相符;剩下沒過的只有離場那一句(票 10)。"""
        self.assertLessEqual(set(failed_texts(own(self.structures, LEARNER_DEVICE))),
                             {LEAVE_SENTENCE})


if __name__ == "__main__":
    unittest.main()
