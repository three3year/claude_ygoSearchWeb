"""多子句先切再解析:只走接縫一(查詢判斷)與接縫二(反向檢查)。

連用形語尾加「、」就切,兩截各自解析;左半解不出時只有它標解析不出,右半照常命中;
右半沒主語時繼承左半的「は」主語。接續詞與不是連用形的讀點不切。
"""
import unittest

from action_query import run_query
from card_structure import build_structures
from reverse_check import check_card
from test_golden import ARCHETYPES, SPELL, card, faq

PARALLEL_PORT_ARMOR = 879958   # パラレルポート・アーマー(通常罠)
TRAP = 0x4
SELF = 10000108
BLACK_MAGICIAN = 46986414


def build(cid, name_ja, text, **kw):
    cards = [card(cid, name_ja=name_ja, **kw),
             card(BLACK_MAGICIAN, name_ja="ブラック・マジシャン", level=7, race=0x2,
                  attribute=0x20),
             card(24094653, name_ja="強欲な壺", type=SPELL)]
    structures, _ = build_structures(cards, [faq(cid, name_ja, text)],
                                     archetypes=ARCHETYPES)
    return cards, structures


def query(cards, structures, **q):
    result = run_query(structures, cards, q)
    return [h["id"] for h in result["hits"]], result["groups"]["未解析"]


def own(structures, cid):
    return next(c for c in structures if c["id"] == cid)


class ParallelPortArmorTest(unittest.TestCase):
    """パラレルポート・アーマー 879958:「〜の対象にならず、戦闘では破壊されない」切成兩段。"""

    TEXT = ("①：自分フィールドのリンクモンスター１体を対象としてこのカードを発動できる。"
            "このカードを装備カード扱いとしてそのモンスターに装備する。"
            "装備モンスターは相手の効果の対象にならず、戦闘では破壊されない。"
            "②：自分の墓地からこのカードとリンクモンスター２体を除外し、"
            "自分フィールドのリンクモンスター１体を対象として発動できる。"
            "このターン、そのモンスターは１度のバトルフェイズ中に２回攻撃できる。")

    @classmethod
    def setUpClass(cls):
        cls.cards, cls.structures = build(PARALLEL_PORT_ARMOR, "パラレルポート・アーマー",
                                          cls.TEXT, type=TRAP)

    def test_second_half_hits_cannot_be_destroyed(self):
        hits, _ = query(self.cards, self.structures, actions=["破壞"], polarities=["不會"])
        self.assertIn(PARALLEL_PORT_ARMOR, hits)

    def test_second_half_inherits_the_equipped_monster_as_subject(self):
        """右半的主語是左半的「装備モンスター」,不是此卡:代入此卡不命中。"""
        hits, _ = query(self.cards, self.structures, actions=["破壞"], polarities=["不會"],
                        card=PARALLEL_PORT_ARMOR)
        self.assertNotIn(PARALLEL_PORT_ARMOR, hits)

    def test_both_halves_pass_reverse_check(self):
        """前半「装備モンスターは相手の効果の対象にならず」自成一段;兩半都寫得回原文,整張通過。"""
        self.assertEqual(check_card(own(self.structures, PARALLEL_PORT_ARMOR)), [])


class ShapeSplitTest(unittest.TestCase):
    """左半解不出時右半照常命中。"""

    def test_right_half_hits_when_left_half_is_unparsed(self):
        cards, structures = build(
            SELF, "甲",
            "①：このカードの攻撃力は相手フィールドのモンスターの数×３００アップし、"
            "このカードを破壊する。")
        hits, _ = query(cards, structures, actions=["破壞"], card=SELF)
        self.assertIn(SELF, hits)

    def test_subjectless_right_half_after_unparsed_left_without_topic_is_unparsed(self):
        """左半解不出又沒有「Xは」時,右半省略的主語判不了:標解析不出、列未解析組,不退回此卡。"""
        cards, structures = build(
            SELF, "甲", "①：相手の墓地のモンスター１体を選択し、自分フィールドに特殊召喚する。")
        hits, unparsed = query(cards, structures, actions=["特殊召喚"])
        self.assertNotIn(SELF, hits)
        self.assertIn(SELF, unparsed)

    def test_conjunctions_and_non_continuative_endings_are_not_split_points(self):
        """「ただし、」「しかし、」「もし、」的「し」、「限り、」的「り」、「につき、」的「き」、
        「高い、」的「い」不是連用形語尾:不切。"""
        for text, head in (
                ("①：このカードを墓地へ送る。ただし、このカードを破壊する。", "ただし"),
                ("①：このカードを墓地へ送る。しかし、このカードを破壊する。", "しかし"),
                ("①：このカードを墓地へ送る。もし、このカードを破壊する。", "もし"),
                ("①：このカードがフィールドに存在する限り、このカードを破壊する。",
                 "このカードがフィールドに存在する限り"),
                ("①：モンスター１体につき、このカードを破壊する。", "モンスター１体につき"),
                ("①：このカードより攻撃力が高い、モンスター１体を破壊する。",
                 "このカードより攻撃力が高い")):
            with self.subTest(text=text):
                _, structures = build(SELF, "甲", text)
                texts = {seg["text"] for block in own(structures, SELF)["blocks"]
                         for seg in block["segments"]}
                self.assertNotIn(head, texts)


if __name__ == "__main__":
    unittest.main()
