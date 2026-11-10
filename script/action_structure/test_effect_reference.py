"""引用他卡效果:「この効果は、その罠カード発動時の効果と同じになる」這類複製他卡效果的句子。

走接縫一(查詢判斷:經引用組、`via`、泛用引用開關)與接縫二(反向檢查);覆蓋報告的兩節
(引用其他效果、引用循環)從 `build_coverage` / `render_coverage` 驗。官方文本逐字寫在測試裡
(`data/sources/` 不入版控)。
"""
import unittest

from action_query import run_query
from card_structure import build_structures, load_structures, serialize_structures
from coverage_report import build_coverage, render_coverage
from reverse_check import check_card
from test_golden import ARCHETYPES, card, faq

ARCHETYPES_13 = ARCHETYPES + [
    {"setcode": 0x4c, "hex": "0x4c", "names_ja": ["落とし穴"], "name_zh": "落穴",
     "source": "strings.conf"},
    {"setcode": 0x89, "hex": "0x89", "names_ja": ["ホール"], "name_zh": "空洞",
     "source": "strings.conf"},
    {"setcode": 0x108a, "hex": "0x108a", "names_ja": ["蟲惑魔"], "name_zh": "蟲惑魔",
     "source": "strings.conf"},
    {"setcode": 0x3a, "hex": "0x3a", "names_ja": ["リチュア"], "name_zh": "遺式",
     "source": "strings.conf"},
    {"setcode": 0x1c4, "hex": "0x1c4", "names_ja": ["征竜"], "name_zh": "征龍",
     "source": "strings.conf"},
    {"setcode": 0x1f, "hex": "0x1f", "names_ja": ["Ｎ", "ネオスペーシアン"],
     "name_zh": "新空間俠", "source": "strings.conf"},
]
NORMAL_TRAP = 0x4
NORMAL_SPELL = 0x2
RITUAL_SPELL = 0x82
XYZ_MONSTER = 0x800021


def build(cards, faqs):
    structures, _ = build_structures(cards, faqs, archetypes=ARCHETYPES_13)
    return structures


def own(structures, cid):
    return next(s for s in structures if s["id"] == cid)


def hit_of(result, cid):
    return next((h for h in result["hits"] if h["id"] == cid), None)


def reference_nodes(structure):
    return [node for block in structure["blocks"] for node in block["tree"]["items"]
            if node["node"] == "內嵌效果" and node["block"] is None]


FRESHIA = 6511113   # フレシアの蟲惑魔
FRESHIA_TEXT = (
    "レベル４モンスター×２\n"
    "①：X素材を持っているこのカードは罠カードの効果を受けない。\n"
    "②：このカードがモンスターゾーンに存在する限り、「フレシアの蟲惑魔」以外の自分フィールドの"
    "「蟲惑魔」モンスターは戦闘・効果では破壊されず、相手はそれらを効果の対象にできない。\n"
    "③：自分・相手ターンに１度、このカードのX素材を１つ取り除き、デッキから「ホール」通常罠カードか"
    "「落とし穴」通常罠カード１枚を墓地へ送って発動できる。この効果は、その罠カード発動時の効果と"
    "同じになる。")
OTOSHIANA = 4206964   # 落とし穴
OTOSHIANA_TEXT = (
    "①：相手が攻撃力１０００以上のモンスターを召喚・反転召喚した時、そのモンスター１体を対象として"
    "発動できる。その攻撃力１０００以上のモンスターを破壊する。")
NARAKU = 29401950   # 奈落の落とし穴
NARAKU_TEXT = (
    "①：相手が攻撃力１５００以上のモンスターを召喚・反転召喚・特殊召喚した時に発動できる。"
    "その攻撃力１５００以上のモンスターを破壊し除外する。")
BLACK_HOLE = 53129443   # ブラック・ホール(通常魔法:「ホール」通常罠カードではない)
BLACK_HOLE_TEXT = "①：フィールドのモンスターを全て破壊する。"


class FreshiaTest(unittest.TestCase):
    """フレシアの蟲惑魔 6511113 ③:經引用「ホール」「落とし穴」通常罠的卡片發動。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = [
            card(FRESHIA, name_ja="フレシアの蟲惑魔", type=XYZ_MONSTER, level=4, race=0x400,
                 attribute=0x1, atk=300, **{"def": 2500}, setcode=0x108a),
            card(OTOSHIANA, name_ja="落とし穴", type=NORMAL_TRAP, setcode=0x4c),
            card(NARAKU, name_ja="奈落の落とし穴", type=NORMAL_TRAP, setcode=0x4c),
            card(BLACK_HOLE, name_ja="ブラック・ホール", type=NORMAL_SPELL),
        ]
        cls.structures = build(cls.cards, [
            faq(FRESHIA, "フレシアの蟲惑魔", FRESHIA_TEXT),
            faq(OTOSHIANA, "落とし穴", OTOSHIANA_TEXT),
            faq(NARAKU, "奈落の落とし穴", NARAKU_TEXT),
            faq(BLACK_HOLE, "ブラック・ホール", BLACK_HOLE_TEXT)])
        cls.structure = own(cls.structures, FRESHIA)
        cls.destroy = run_query(cls.structures, cls.cards, {"actions": ["破壞"]})

    def test_destroy_puts_freshia_in_via_group_not_hit_groups(self):
        self.assertIn(FRESHIA, self.destroy["groups"]["經引用"])
        self.assertNotIn(FRESHIA, self.destroy["groups"]["全部"])
        self.assertNotIn(FRESHIA, self.destroy["groups"]["未解析"])

    def test_via_lists_trap_cards_with_their_hit_segments(self):
        hit = hit_of(self.destroy, FRESHIA)
        via = {entry["id"]: entry["segments"] for entry in hit["via"]}
        self.assertEqual(sorted(via), [OTOSHIANA, NARAKU])
        direct = {h["id"]: h["segments"] for h in self.destroy["hits"]
                  if h["group"] != "經引用"}
        self.assertEqual(via[OTOSHIANA], direct[OTOSHIANA])
        self.assertEqual(via[NARAKU], direct[NARAKU])

    def test_spell_named_hole_is_not_a_candidate(self):
        node, = reference_nodes(self.structure)
        self.assertNotIn(BLACK_HOLE, node["reference"]["candidates"])

    def test_referenced_part_is_card_activation(self):
        node, = reference_nodes(self.structure)
        self.assertEqual(node["reference"]["effect"], {"part": "卡片發動"})
        self.assertNotIn("any", node)

    def test_reference_sentence_and_cost_pass_reverse_check(self):
        """③ 的引用句(節點只寫引導句模板)沒有殘留、送墓代價(「か」列舉的物件)通過。"""
        failures = [f for f in check_card(self.structure) if f["block"] == "b131"]
        self.assertEqual([f for f in failures if f["segment"] in (None, "b131.s31")], [])

    def test_round_trip(self):
        text = serialize_structures(self.structures)
        self.assertEqual(load_structures(text), self.structures)
        self.assertEqual(serialize_structures(load_structures(text)), text)


HOSHIAI = 20417688   # 星逢の天河
HOSHIAI_TEXT = (
    "このカード名の①②の効果はそれぞれ１ターンに１度しか使用できない。①：手札の儀式モンスター１体を"
    "相手に見せて発動できる。そのモンスターとはカード名が異なり、レベルが同じ儀式モンスター１体を"
    "デッキから手札に加える。②：墓地のこのカードを除外し、手札から儀式魔法カード１枚を墓地へ送って"
    "発動できる。この効果は、その儀式魔法カード発動時の儀式召喚する効果と同じになる。")
GISHIKI_MIRROR = 36982581   # リチュアの氷魔鏡(儀式魔法)
GISHIKI_MIRROR_TEXT = (
    "「リチュア」儀式モンスターの降臨に必要。①：相手フィールドの表側表示モンスター１体をリリース、"
    "またはレベルの合計が儀式召喚するモンスターと同じになるように自分の手札・フィールドのモンスターを"
    "リリースし、手札から「リチュア」儀式モンスター１体を儀式召喚し、自分はその元々の攻撃力分のLPを"
    "失う。②：このカードが墓地に存在する場合、自分の墓地の「リチュア」モンスター１体を対象として"
    "発動できる。そのモンスターをデッキの一番上に戻し、このカードをデッキの一番下に戻す。")


class HoshiaiTest(unittest.TestCase):
    """星逢の天河 20417688 ②:經引用儀式魔法裡含儀式召喚的區塊。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = [
            card(HOSHIAI, name_ja="星逢の天河", type=NORMAL_TRAP),
            card(GISHIKI_MIRROR, name_ja="リチュアの氷魔鏡", type=RITUAL_SPELL, setcode=0x3a),
            card(OTOSHIANA, name_ja="落とし穴", type=NORMAL_TRAP, setcode=0x4c),
        ]
        cls.structures = build(cls.cards, [
            faq(HOSHIAI, "星逢の天河", HOSHIAI_TEXT),
            faq(GISHIKI_MIRROR, "リチュアの氷魔鏡", GISHIKI_MIRROR_TEXT),
            faq(OTOSHIANA, "落とし穴", OTOSHIANA_TEXT)])
        cls.structure = own(cls.structures, HOSHIAI)

    def query(self, action):
        return run_query(self.structures, self.cards, {"actions": [action]})

    def test_referenced_part_is_block_with_ritual_summon(self):
        node, = reference_nodes(self.structure)
        self.assertEqual(node["reference"]["effect"], {"part": "含動作", "action": "儀式召喚"})
        self.assertEqual(node["reference"]["candidates"], [GISHIKI_MIRROR])

    def test_ritual_summon_hits_via_ritual_spell(self):
        result = self.query("儀式召喚")
        self.assertIn(HOSHIAI, result["groups"]["經引用"])
        hit = hit_of(result, HOSHIAI)
        self.assertEqual([entry["id"] for entry in hit["via"]], [GISHIKI_MIRROR])
        self.assertTrue(hit["via"][0]["segments"])

    def test_other_effect_of_ritual_spell_does_not_hit_via(self):
        """氷魔鏡 ② 的「デッキに戻す」不在含儀式召喚的區塊裡:查返回,星逢不經引用命中。"""
        result = self.query("返回")
        self.assertIn(GISHIKI_MIRROR, result["groups"]["全部"])
        self.assertNotIn(HOSHIAI, result["groups"]["經引用"])

    def test_reference_sentence_passes_reverse_check(self):
        failures = [f for f in check_card(self.structure) if f["block"] == "b106"]
        self.assertEqual(failures, [])


SHASMATIS = 4965193   # 極征竜－シャスマティス
SHASMATIS_TEXT = (
    "ドラゴン族レベル７モンスター×２\n"
    "このカード名の①②の効果はそれぞれ１ターンに１度しか使用できない。\n"
    "①：自分・相手ターンに、デッキからレベル７の「征竜」モンスター１体を墓地へ送り、このカードのX素材を"
    "１つ取り除いて発動できる。この効果は、デッキから墓地へ送ったそのモンスターの、自身を手札から"
    "捨てて発動する効果と同じになる。\n"
    "②：このカードが戦闘または相手の効果で破壊された場合に発動できる。自分の墓地・除外状態のレベル７の"
    "「征竜」モンスター１体を特殊召喚する。")
BLACK_PANTHER = 43237273   # Ｎ・ブラック・パンサー
BLACK_PANTHER_TEXT = (
    "①：１ターンに１度、相手フィールドの表側表示モンスター１体を対象として発動できる。"
    "このカードはエンドフェイズまで、そのモンスターの元々のカード名・効果と同じカード名・効果を得る。")
PANTHER_TARGET = 46986414   # ブラック・マジシャン(通常怪獸,任何查詢都不命中)
DESTROYER = 71413901   # 破壞效果的怪獸(合成卡)
DESTROYER_TEXT = "①：このカードが召喚に成功した時に発動できる。相手フィールドのカード１枚を破壊する。"


class ShasmatisTest(unittest.TestCase):
    """極征竜－シャスマティス 4965193 ①:被引用物件解析不出 → 節點標解析不出(引用其他效果)。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = [card(SHASMATIS, name_ja="極征竜－シャスマティス", type=XYZ_MONSTER, level=7,
                          race=0x2000, attribute=0x10, atk=3000, **{"def": 1600},
                          setcode=0x1c4),
                     card(BLACK_HOLE, name_ja="ブラック・ホール", type=NORMAL_SPELL)]
        cls.structures = build(cls.cards, [
            faq(SHASMATIS, "極征竜－シャスマティス", SHASMATIS_TEXT),
            faq(BLACK_HOLE, "ブラック・ホール", BLACK_HOLE_TEXT)])
        cls.structure = own(cls.structures, SHASMATIS)

    def test_node_is_unparsed_with_reference_reason(self):
        node, = reference_nodes(self.structure)
        self.assertEqual(node["unparsed"], {"reason": "引用其他效果"})
        self.assertEqual(node["reference"]["effect"], {"part": "代價", "action": "捨棄"})
        self.assertEqual(node["reference"]["candidates"], [])

    def test_never_in_via_group(self):
        for actions in (["破壞"], ["捨棄"], ["特殊召喚"], []):
            result = run_query(self.structures, self.cards,
                               {"actions": actions, "generic_reference": True})
            self.assertNotIn(SHASMATIS, result["groups"]["經引用"], actions)

    def test_coverage_report_lists_card(self):
        coverage = build_coverage(self.structures)
        self.assertEqual(coverage["references"]["unparsed"], [SHASMATIS])
        self.assertIn("## 引用其他效果", render_coverage(coverage))


class BlackPantherTest(unittest.TestCase):
    """Ｎ・ブラック・パンサー 43237273:被引用物件是泛用物件 → `any`,只在泛用引用開關開時展開。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = [
            card(BLACK_PANTHER, name_ja="Ｎ・ブラック・パンサー", level=3, race=0x4000,
                 attribute=0x20, atk=1000, **{"def": 500}, setcode=0x1f),
            card(PANTHER_TARGET, name_ja="ブラック・マジシャン", type=0x11, level=7,
                 race=0x2, attribute=0x20, atk=2500),
            card(DESTROYER, name_ja="破壊者"),
            card(BLACK_HOLE, name_ja="ブラック・ホール", type=NORMAL_SPELL),
        ]
        cls.structures = build(cls.cards, [
            faq(BLACK_PANTHER, "Ｎ・ブラック・パンサー", BLACK_PANTHER_TEXT),
            faq(PANTHER_TARGET, "ブラック・マジシャン", "魔法使いとしては、攻撃力・守備力ともに最高クラス。"),
            faq(DESTROYER, "破壊者", DESTROYER_TEXT),
            faq(BLACK_HOLE, "ブラック・ホール", BLACK_HOLE_TEXT)])
        cls.structure = own(cls.structures, BLACK_PANTHER)

    def query(self, actions, generic_reference):
        return run_query(self.structures, self.cards,
                         {"actions": actions, "generic_reference": generic_reference})

    def test_node_is_any_with_monster_candidates(self):
        node, = reference_nodes(self.structure)
        self.assertTrue(node["any"])
        self.assertEqual(node["reference"]["effect"], {"part": "整張"})
        self.assertNotIn(BLACK_HOLE, node["reference"]["candidates"])
        self.assertIn(DESTROYER, node["reference"]["candidates"])

    def test_switch_off_never_hits_via(self):
        for actions in (["破壞"], ["特殊召喚"], []):
            self.assertEqual(self.query(actions, False)["groups"]["經引用"], [], actions)

    def test_switch_on_destroy_hits_via_generic_reference(self):
        result = self.query(["破壞"], True)
        self.assertIn(BLACK_PANTHER, result["groups"]["經引用"])
        hit = hit_of(result, BLACK_PANTHER)
        self.assertEqual(hit["mark"], "經泛用引用")
        self.assertEqual([entry["id"] for entry in hit["via"]], [DESTROYER])

    def test_whole_card_passes_reverse_check(self):
        self.assertEqual(check_card(self.structure), [])


class CycleReportTest(unittest.TestCase):
    """覆蓋報告「引用循環」節:兩張互相引用的合成卡成環;同一輸入兩次產出相同。"""

    @classmethod
    def setUpClass(cls):
        loop_text = ("①：手札から通常罠カード１枚を墓地へ送って発動できる。"
                     "この効果は、その罠カード発動時の効果と同じになる。")
        cls.cards = [card(11, name_ja="甲", type=NORMAL_TRAP), card(12, name_ja="乙", type=NORMAL_TRAP),
                     card(FRESHIA, name_ja="フレシアの蟲惑魔", type=XYZ_MONSTER, level=4,
                          setcode=0x108a)]
        cls.faqs = [faq(11, "甲", loop_text), faq(12, "乙", loop_text),
                    faq(FRESHIA, "フレシアの蟲惑魔", FRESHIA_TEXT)]
        cls.structures = build(cls.cards, cls.faqs)

    def test_cycle_listed_with_card_ids(self):
        coverage = build_coverage(self.structures)
        self.assertEqual(coverage["references"]["cycles"], [[11, 12]])
        self.assertIn("## 引用循環", render_coverage(coverage))

    def test_query_stops_at_cycle(self):
        result = run_query(self.structures, self.cards, {"actions": ["破壞"]})
        self.assertEqual(result["groups"]["經引用"], [])

    def test_same_input_same_report(self):
        again = build(self.cards, self.faqs)
        self.assertEqual(render_coverage(build_coverage(self.structures)),
                         render_coverage(build_coverage(again)))


if __name__ == "__main__":
    unittest.main()
