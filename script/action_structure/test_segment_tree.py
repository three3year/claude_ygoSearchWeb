"""段樹(票 06)的句型層級測試:同時/先後連接、● 分歧的方式、依前提與省略的「存在しない場合」、
內嵌效果的綁定。都走查詢判斷與反向檢查兩個接縫(spec「測試決策」),不驗段樹內部的形狀;
產物 round-trip 走序列化接縫。
"""
import unittest

from action_query import run_query
from card_structure import build_structures, load_structures, serialize_structures
from reverse_check import check_card
from test_golden import (BLACK_MAGICIAN, BRANCH_ARCHETYPES, FALLEN_VIRTUOUS,
                         FALLEN_VIRTUOUS_TEXT, GREEDY_POT, KAMIKAZE_DRAGUNITY,
                         KAMIKAZE_DRAGUNITY_TEXT, SPELL, card, faq)

TEST_CARD = 1


def build(text, cards=None, name_ja="甲"):
    cards = cards or [card(TEST_CARD, name_ja=name_ja),
                      card(BLACK_MAGICIAN, name_ja="ブラック・マジシャン", level=7,
                           race=0x2, attribute=0x20),
                      card(GREEDY_POT, name_ja="強欲な壺", type=SPELL)]
    structures, _ = build_structures(cards, [faq(TEST_CARD, name_ja, text)],
                                     archetypes=BRANCH_ARCHETYPES)
    return structures, cards


def hits(structures, cards, **query):
    return [hit["id"] for hit in run_query(structures, cards, query)["hits"]]


class SimultaneousJoinTest(unittest.TestCase):
    """「〜し、〜」「〜え、〜」串接的子句各自成段(同時連接),兩個動作都查得到。"""

    def test_two_clauses_joined_by_renyoukei_both_hit(self):
        """クリムゾン・ブレーダー／バスター ① 的句型:「〜手札に加え、このカードをデッキに戻す」。"""
        structures, cards = build(
            "①：デッキから「バスター・モード」１枚を手札に加え、このカードをデッキに戻す。",
            cards=[card(TEST_CARD, name_ja="甲"),
                   card(80280737, name_ja="バスター・モード", type=0x4)])
        self.assertIn(TEST_CARD, hits(structures, cards, actions=["加入手牌"],
                                      from_zones=["牌組"], to_zones=["手牌"],
                                      card=80280737))
        self.assertIn(TEST_CARD, hits(structures, cards, actions=["返回"],
                                      to_zones=["牌組"], card=TEST_CARD))
        self.assertEqual(check_card(structures[0]), [])

    def test_cost_clauses_joined_by_renyoukei(self):
        """發動句的代價也可串接:「〜を墓地へ送り、〜を捨てて発動できる」。"""
        structures, cards = build(
            "①：手札からモンスター１体を墓地へ送り、手札からカード１枚を捨てて発動できる。"
            "このカードを特殊召喚する。")
        self.assertIn(TEST_CARD, hits(structures, cards, actions=["送墓"],
                                      from_zones=["手牌"], to_zones=["墓地"],
                                      card=BLACK_MAGICIAN))
        self.assertIn(TEST_CARD, hits(structures, cards, actions=["特殊召喚"],
                                      card=TEST_CARD))
        self.assertEqual(check_card(structures[0]), [])

    def test_comma_without_connective_predicate_is_not_a_split(self):
        """「装備魔法カード扱いで、」不是述語的連用形:不切,整句一段。"""
        structures, cards = build(
            "①：このカードを特殊召喚する。その後、デッキからモンスター１体を装備魔法カード扱いで、"
            "この効果で特殊召喚したモンスターに装備できる。")
        self.assertIn(TEST_CARD, hits(structures, cards, actions=["裝備"],
                                      from_zones=["牌組"], card=BLACK_MAGICIAN))
        self.assertIn(TEST_CARD, hits(structures, cards, actions=["裝備"],
                                      to_zones=["魔陷區"], include_inferred=True))
        self.assertEqual(check_card(structures[0]), [])


class BranchTest(unittest.TestCase):
    """● 列舉是分歧:每支各自查得到、位置不互相污染、引導句進反向檢查。"""

    def test_choose_one_branch_both_options_hit(self):
        structures, cards = build(
            "①：以下の効果から１つを選択して発動できる。\n"
            "●手札からモンスター１体を特殊召喚する。\n"
            "●自分の墓地からモンスター１体を除外する。")
        self.assertIn(TEST_CARD, hits(structures, cards, actions=["特殊召喚"],
                                      from_zones=["手牌"], card=BLACK_MAGICIAN))
        self.assertIn(TEST_CARD, hits(structures, cards, actions=["除外"],
                                      from_zones=["墓地"], card=BLACK_MAGICIAN))
        self.assertNotIn(TEST_CARD, hits(structures, cards, actions=["除外"],
                                         from_zones=["手牌"]))
        self.assertEqual(check_card(structures[0]), [])

    def test_header_with_premise_is_a_premise_branch(self):
        """帶前提的引導句:「〜場合、以下の効果から１つを選んで適用する」是一支依前提的分歧。"""
        structures, cards = build(
            "①：自分フィールドに「ブラック・マジシャン」が存在する場合、"
            "以下の効果から１つを選んで適用する。\n"
            "●デッキからカード１枚を手札に加える。\n"
            "●自分はデッキから１枚ドローする。")
        self.assertIn(TEST_CARD, hits(structures, cards, actions=["加入手牌"],
                                      from_zones=["牌組"], card=GREEDY_POT))
        failures = check_card(structures[0])
        # 第二支的「ドローする」還沒有動作詞,只有它不過;引導句與第一支都過。
        self.assertEqual([(f["segment"], f["reason"]) for f in failures],
                         [("b0.s70", "無模板")])

    def test_unknown_header_leaves_branch_mode_unparsed_but_nothing_silent(self):
        """引導句認不得(「以下の効果を適用する」):分歧方式標解析不出、引導句仍解析成段,
        反向檢查列「段樹無模板」而不是靜默放過;支內的段照常查得到。"""
        structures, cards = build(
            "①：以下の効果を適用する。\n●手札からモンスター１体を特殊召喚する。")
        self.assertIn(TEST_CARD, hits(structures, cards, actions=["特殊召喚"],
                                      from_zones=["手牌"], card=BLACK_MAGICIAN))
        details = {f["detail"] for f in check_card(structures[0])}
        self.assertIn("段樹無模板:分歧方式判不出", details)
        self.assertIn("段解析不出:述語解析不出", details)

    def test_after_join_on_header_and_elided_premise(self):
        """神風:「その後、以下の効果から１つを選んで適用できる」的引導句帶先後連接;
        「存在しない場合、」對回前一個前提,整張過反向檢查(golden 已驗),這裡驗兩支都查得到。"""
        structures, cards = build(
            KAMIKAZE_DRAGUNITY_TEXT,
            cards=[card(TEST_CARD, name_ja="神風のドラグニティ", type=0x80002),
                   card(74822425, name_ja="竜の渓谷", type=0x80002, setcode=0x29),
                   card(60645181, name_ja="ドラグニティ－ファランクス", level=2,
                        race=0x2000, attribute=0x4, setcode=0x29)],
            name_ja="神風のドラグニティ")
        self.assertIn(TEST_CARD, hits(structures, cards, actions=["加入手牌"],
                                      from_zones=["墓地"], card=60645181))
        self.assertIn(TEST_CARD, hits(structures, cards, actions=["特殊召喚"],
                                      from_zones=["手牌"], card=60645181))
        self.assertEqual(check_card(structures[0]), [])


class EmbeddedEffectTest(unittest.TestCase):
    """「Xは以下の効果を得る」是內嵌效果:內容區塊裡的「このカード」綁定成 X。"""

    def test_gained_effect_binds_this_card_to_the_subject(self):
        structures, cards = build(
            "①：手札からモンスター１体を特殊召喚する。"
            "この効果で特殊召喚したモンスターは以下の効果を得る。\n"
            "●このカードを墓地へ送る。")
        # 內嵌段的「このカード」是被特殊召喚的怪獸:黑魔導代入命中「送墓」,魔法卡不命中。
        self.assertIn(TEST_CARD, hits(structures, cards, actions=["送墓"],
                                      card=BLACK_MAGICIAN))
        self.assertNotIn(TEST_CARD, hits(structures, cards, actions=["送墓"],
                                         card=GREEDY_POT))
        self.assertEqual(check_card(structures[0]), [])

    def test_unresolvable_subject_falls_back_to_an_unparsed_branch(self):
        """主語解析不出:引導句照一般句子解析(段標原因)、● 列舉是方式判不出的分歧,
        支內的段仍查得到,沒有字被靜默略過(不是段外殘留)。"""
        structures, cards = build(
            "①：そのモンスターは以下の効果を得る。\n●このカードを墓地へ送る。")
        self.assertIn(TEST_CARD, hits(structures, cards, actions=["送墓"], card=TEST_CARD))
        failures = check_card(structures[0])
        self.assertEqual({f["reason"] for f in failures}, {"無模板"})
        self.assertIn("段樹無模板:分歧方式判不出", {f["detail"] for f in failures})


class RoundTripTest(unittest.TestCase):

    def test_tree_nodes_survive_serialize_and_load(self):
        cards = [card(FALLEN_VIRTUOUS, name_ja="The Fallen ＆ The Virtuous",
                      type=0x10002, setcode=0x145015d),
                 card(KAMIKAZE_DRAGUNITY, name_ja="神風のドラグニティ", type=0x80002,
                      setcode=0x29),
                 card(TEST_CARD, name_ja="甲")]
        entries = [faq(FALLEN_VIRTUOUS, "The Fallen ＆ The Virtuous", FALLEN_VIRTUOUS_TEXT),
                   faq(KAMIKAZE_DRAGUNITY, "神風のドラグニティ", KAMIKAZE_DRAGUNITY_TEXT),
                   faq(TEST_CARD, "甲", "①：手札からモンスター１体を特殊召喚する。"
                       "この効果で特殊召喚したモンスターは以下の効果を得る。\n"
                       "●このカードを墓地へ送る。")]
        structures, _ = build_structures(cards, entries, archetypes=BRANCH_ARCHETYPES)
        text = serialize_structures(structures)
        loaded = load_structures(text)
        self.assertEqual(loaded, structures)
        self.assertEqual(serialize_structures(loaded), text)


if __name__ == "__main__":
    unittest.main()
