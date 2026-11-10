"""前提的數量與列舉(m3 票 12):只走接縫一(查詢判斷)與接縫二(反向檢查)。

- 數量「２体以上/３枚以上/２種類以上」寫在「存在する」前:記在 存在 原子所指物件的數量格。
- 連用形串接「Aが存在し、/存在せず、Bが存在しない場合」:兩個前提的且。
- 「〜存在しない場合に〜される」(「場合に」後面沒有讀點)。
- 列舉:「A及びB」「AとB」= 且;「〜のいずれか」「AまたはB」= 或;「それぞれ存在」= 每種各一;
  「〜場合、または〜場合」= 兩個前提的或。區域的或(「墓地またはフィールド上に」)是區域集合。
- LP 比較(「自分のLPが相手より少なく、」)是遊戲狀態原子;沒寫區域的「Xが表側表示で存在する場合」預設場上。
前提不參與查詢:且/或、數量從這兩個接縫分不出來,這裡只驗前提剝得出(後面的段照常命中、
前提設的位置由後面的段繼承)與寫回原文相符。
標準卡的官方文本逐字寫在測試裡(`data/sources/` 不入版控)。
"""
import unittest

from action_query import run_query
from card_structure import build_structures
from reverse_check import check_card
from test_end_phase_timing_ritual import HYMN, RITUAL_SPELL, SAFFIRA, SAFFIRA_TEXT
from test_golden import ARCHETYPES, SPELL, TRAP, card, faq

SELF = 10000121
FIELD_SPELL = 0x80002
FUSION_MONSTER = 0x41
DRAGON_RAVINE = 62265044    # 竜の渓谷(場地魔法)
PENGUIN_SOLDIER = 93920745  # ペンギン・ソルジャー setcode 0x5a
BLACK_MAGICIAN = 46986414
BLUE_EYES = 89631139        # 青眼の白龍
FUSION_DRAGON = 70000121    # 測試用:融合怪獸


def build(cards, faqs, archetypes=ARCHETYPES):
    structures, _ = build_structures(cards, faqs, archetypes=archetypes)
    return structures


def library(text, **self_kw):
    cards = [
        card(SELF, name_ja="甲", **self_kw),
        card(DRAGON_RAVINE, name_ja="竜の渓谷", type=FIELD_SPELL),
        card(PENGUIN_SOLDIER, name_ja="ペンギン・ソルジャー", level=2, race=0x40,
             attribute=0x2, setcode=0x5a),
        card(BLACK_MAGICIAN, name_ja="ブラック・マジシャン", level=7, race=0x2,
             attribute=0x20),
        card(BLUE_EYES, name_ja="青眼の白龍", level=8, race=0x2000, attribute=0x10),
        card(FUSION_DRAGON, name_ja="乙", type=FUSION_MONSTER, level=8),
    ]
    return cards, build(cards, [faq(SELF, "甲", text)])


def hits(cards, structures, **query):
    return [h["id"] for h in run_query(structures, cards, query)["hits"]]


def own(structures, cid=SELF):
    return next(c for c in structures if c["id"] == cid)


def failures_on(structure, fragment):
    """反向檢查的不通過清單裡與這段字面有關的:沒過的段原文含它,或是段外殘留、段樹的無模板
    (前提沒剝成、整截漏在段外時會落在這裡)。"""
    texts = {s["id"]: s["text"] for b in structure["blocks"] for s in b["segments"]}
    return [f for f in check_card(structure)
            if fragment in (texts.get(f["segment"]) or "") or f["segment"] is None]


MOON_GARDNA = 336601        # ムーン・ガードナー
MOON_GARDNA_TEXT = (
    "このカード名の、①の方法による特殊召喚は１ターンに１度しかできず、②の効果は１ターンに１度しか使用できない。\n"
    "①：相手フィールドにモンスターが２体以上存在する場合、このカードは手札から特殊召喚できる。\n"
    "②：このカードが召喚・特殊召喚した場合、相手フィールドにモンスターが存在していれば、"
    "「ムーン・ガードナー」以外の自分の墓地の光属性・レベル４モンスター１体を対象として発動できる。"
    "そのモンスターを手札に加える。")


class MoonGardnaTest(unittest.TestCase):
    """ムーン・ガードナー 336601:「相手フィールドにモンスターが２体以上存在する場合」(故事 33)。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = [card(MOON_GARDNA, name_ja="ムーン・ガードナー", level=4, race=0x2,
                          attribute=0x10, atk=100, **{"def": 2000})]
        cls.structures = build(cls.cards, [faq(MOON_GARDNA, "ムーン・ガードナー",
                                               MOON_GARDNA_TEXT)])
        cls.own = own(cls.structures, MOON_GARDNA)

    def test_counted_premise_segment_writes_back(self):
        """「〜モンスターが２体以上存在する場合、このカードは手札から特殊召喚できる」寫回原文相符。"""
        self.assertEqual(failures_on(self.own, "２体以上存在する場合"), [])

    def test_special_summon_from_hand_hits(self):
        """查「特殊召喚,從手牌」、此卡代入命中;從墓地不命中。"""
        self.assertIn(MOON_GARDNA, hits(self.cards, self.structures, actions=["特殊召喚"],
                                        from_zones=["手牌"], card=MOON_GARDNA))
        self.assertNotIn(MOON_GARDNA, hits(self.cards, self.structures, actions=["特殊召喚"],
                                           from_zones=["墓地"], card=MOON_GARDNA))


BURNING_DRAGON = 8085950    # バーニング・ドラゴン
BURNING_DRAGON_TEXT = (
    "このカード名の①②の効果はそれぞれ１ターンに１度しか使用できない。"
    "①：このカードが手札に存在し、相手フィールドにモンスターが２体以上存在する場合に発動できる。"
    "このカードを特殊召喚する。"
    "②：このカードが召喚・特殊召喚に成功した場合、手札から魔法カード１枚を捨てて発動できる。"
    "フィールドの魔法・罠カードを全て破壊する。")


class BurningDragonTest(unittest.TestCase):
    """バーニング・ドラゴン 8085950:連用形串接「このカードが手札に存在し、相手フィールドにモンスターが
    ２体以上存在する場合に発動できる」(故事 34)。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = [card(BURNING_DRAGON, name_ja="バーニング・ドラゴン", level=8,
                          race=0x2000, attribute=0x4, atk=2500, **{"def": 2100})]
        cls.structures = build(cls.cards, [faq(BURNING_DRAGON, "バーニング・ドラゴン",
                                               BURNING_DRAGON_TEXT)])

    def test_whole_card_writes_back(self):
        self.assertEqual(check_card(own(self.structures, BURNING_DRAGON)), [])

    def test_first_premise_sets_the_position_the_summon_inherits(self):
        """兩個前提都剝得出:第一個(此卡在手牌)設的位置由「このカードを特殊召喚する」繼承——
        查「特殊召喚,從手牌」、此卡代入命中(推得關);從墓地不命中。"""
        self.assertIn(BURNING_DRAGON, hits(self.cards, self.structures, actions=["特殊召喚"],
                                           from_zones=["手牌"], card=BURNING_DRAGON))
        self.assertNotIn(BURNING_DRAGON, hits(self.cards, self.structures, actions=["特殊召喚"],
                                              from_zones=["墓地"], card=BURNING_DRAGON))

    def test_other_actions_do_not_hit_the_premise(self):
        """前提不是動作:查「送墓」不命中、也不列未解析組。"""
        result = run_query(self.structures, self.cards, {"actions": ["送墓"]})
        self.assertNotIn(BURNING_DRAGON,
                         [h["id"] for h in result["hits"]] + result["groups"]["未解析"])


TRICKSTAR_FOODIE = 1410324  # トリックスター・フーディ
TRICKSTAR_FOODIE_TEXT = (
    "このカード名の①②の効果はそれぞれ１ターンに１度しか使用できない。\n"
    "①：自分フィールドに「トリックスター」融合・Lモンスターのいずれかが存在する場合に発動できる。"
    "このカードを手札から特殊召喚する。\n"
    "②：このカードが「トリックスター」LモンスターのL素材として墓地へ送られた場合に発動できる。"
    "デッキから「トリックスター・フュージョン」か「トリックスター・ディフュージョン」１枚を手札に加える。")
TRICKSTAR_FUSION = 88693151      # トリックスター・フュージョン(魔法)
TRICKSTAR_DIFFUSION = 63181559   # トリックスター・ディフュージョン(陷阱)
TRICKSTAR_ARCHETYPES = ARCHETYPES + [
    {"setcode": 0xfb, "hex": "0xfb", "names_ja": ["トリックスター"], "name_zh": "淘氣仙星",
     "source": "strings.conf"}]


class TrickstarFoodieTest(unittest.TestCase):
    """トリックスター・フーディ 1410324:「「トリックスター」融合・Lモンスターのいずれかが存在する場合」
    (故事 35);②的「「A」か「B」１枚」是兩個卡名的或。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = [card(TRICKSTAR_FOODIE, name_ja="トリックスター・フーディ", level=2,
                          race=0x4, attribute=0x10, atk=600, setcode=0xfb, **{"def": 1800}),
                     card(TRICKSTAR_FUSION, name_ja="トリックスター・フュージョン", type=SPELL,
                          setcode=0xfb),
                     card(TRICKSTAR_DIFFUSION, name_ja="トリックスター・ディフュージョン",
                          type=TRAP, setcode=0xfb),
                     card(BLACK_MAGICIAN, name_ja="ブラック・マジシャン", type=SPELL)]
        cls.structures = build(cls.cards, [faq(TRICKSTAR_FOODIE, "トリックスター・フーディ",
                                               TRICKSTAR_FOODIE_TEXT)], TRICKSTAR_ARCHETYPES)
        cls.own = own(cls.structures, TRICKSTAR_FOODIE)

    def test_any_of_premise_writes_back(self):
        self.assertEqual(failures_on(self.own, "のいずれかが存在する場合"), [])

    def test_whole_card_writes_back(self):
        self.assertEqual(check_card(self.own), [])

    def test_either_named_card_is_added_to_hand(self):
        """②「「A」か「B」１枚を手札に加える」:兩張卡代入都命中,別的卡不命中。"""
        query = dict(actions=["加入手牌"], from_zones=["牌組"])
        for named in (TRICKSTAR_FUSION, TRICKSTAR_DIFFUSION):
            with self.subTest(card=named):
                self.assertIn(TRICKSTAR_FOODIE,
                              hits(self.cards, self.structures, card=named, **query))
        self.assertNotIn(TRICKSTAR_FOODIE,
                         hits(self.cards, self.structures, card=BLACK_MAGICIAN, **query))

    def test_special_summon_from_hand_hits(self):
        self.assertIn(TRICKSTAR_FOODIE, hits(self.cards, self.structures, actions=["特殊召喚"],
                                             from_zones=["手牌"], card=TRICKSTAR_FOODIE))
        self.assertNotIn(TRICKSTAR_FOODIE, hits(self.cards, self.structures, actions=["特殊召喚"],
                                                from_zones=["墓地"], card=TRICKSTAR_FOODIE))


class SaffiraSecondTimepointTest(unittest.TestCase):
    """竜姫神サフィラ 56350972 ① 第二個時點的條件段「このカードがモンスターゾーンに存在し、手札・デッキから
    光属性モンスターが墓地へ送られたターン」:句首的連用形前提剝得出(票 11 留給本票驗的那一段)。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = [
            card(SAFFIRA, name_ja="竜姫神サフィラ", type=0xa1, level=6, race=0x2000,
                 attribute=0x10, atk=2500, **{"def": 2400}),
            card(HYMN, name_ja="祝祷の聖歌", type=RITUAL_SPELL),
        ]
        cls.structures = build(cls.cards, [faq(SAFFIRA, "竜姫神サフィラ", SAFFIRA_TEXT)])

    def test_whole_card_writes_back(self):
        self.assertEqual(check_card(own(self.structures, SAFFIRA)), [])

    def test_sent_to_graveyard_from_hand_hits_the_condition_segment(self):
        """開條件段查「送墓,從手牌」命中(不再只是列在未解析組);關掉條件段不命中。"""
        query = dict(actions=["送墓"], from_zones=["手牌"])
        self.assertIn(SAFFIRA, hits(self.cards, self.structures, include_condition=True, **query))
        self.assertNotIn(SAFFIRA, hits(self.cards, self.structures, **query))


class ContinuativePremiseTest(unittest.TestCase):
    """連用形串接:「存在し、」「存在せず、」後面接下一個前提或子句。"""

    def test_negative_continuative_then_existence(self):
        cards, structures = library(
            "①：自分フィールドにモンスターが存在せず、相手フィールドにモンスターが存在する場合に発動できる。"
            "このカードを手札から特殊召喚する。")
        self.assertEqual(check_card(own(structures)), [])
        self.assertIn(SELF, hits(cards, structures, actions=["特殊召喚"], from_zones=["手牌"],
                                 card=SELF))

    def test_continuative_premise_before_a_trigger_clause(self):
        """「このカードがモンスターゾーンに存在し、相手がモンスターを特殊召喚した場合に発動できる」:
        前提掛在條件段,後面的「そのモンスター」照常指回被特殊召喚的怪獸。"""
        cards, structures = library(
            "①：このカードがモンスターゾーンに存在し、相手がモンスターを特殊召喚した場合に発動できる。"
            "そのモンスターを破壊する。")
        self.assertEqual(check_card(own(structures)), [])
        self.assertIn(SELF, hits(cards, structures, actions=["破壞"], card=BLACK_MAGICIAN))
        self.assertIn(SELF, hits(cards, structures, actions=["特殊召喚"], include_condition=True))

    def test_old_style_effect_sentence_with_two_premises(self):
        """「相手フィールド上にモンスターが存在し、自分フィールド上にモンスターが存在しない場合、
        このカードは手札から特殊召喚できる」:兩個前提掛在效果段。"""
        cards, structures = library(
            "相手フィールド上にモンスターが存在し、自分フィールド上にモンスターが存在しない場合、"
            "このカードは手札から特殊召喚できる。")
        self.assertEqual(check_card(own(structures)), [])
        self.assertIn(SELF, hits(cards, structures, actions=["特殊召喚"], from_zones=["手牌"],
                                 card=SELF))


class PremiseThenClauseWithoutPauseTest(unittest.TestCase):
    """「〜場合に〜される」:前提後面沒有讀點直接接子句。"""

    def test_baai_ni_before_an_effect_clause(self):
        cards, structures = library(
            "自分フィールドにモンスターが存在しない場合にこのカードは破壊される。")
        self.assertEqual(check_card(own(structures)), [])
        self.assertIn(SELF, hits(cards, structures, actions=["破壞"], card=SELF))

    def test_baai_ni_before_activation_is_unchanged(self):
        """「〜場合に発動できる」的「に」照舊不算前提的字面:整張通過。"""
        _, structures = library(
            "①：自分フィールドにモンスターが存在しない場合に発動できる。このカードを破壊する。")
        self.assertEqual(check_card(own(structures)), [])


class DefaultFieldPremiseTest(unittest.TestCase):
    """沒寫區域的「Xが表側表示で存在する場合」預設場上。"""

    TEXT = "①：フィールド魔法カードが表側表示で存在する場合に発動できる。そのカードを破壊する。"

    def test_writes_back_without_a_zone(self):
        _, structures = library(self.TEXT)
        self.assertEqual(check_card(own(structures)), [])

    def test_default_field_counts_only_with_inferred_switch(self):
        """預設的場上是推得的:查「破壞,從場上」推得開才命中。"""
        cards, structures = library(self.TEXT)
        query = dict(actions=["破壞"], from_zones=["場上"], card=DRAGON_RAVINE)
        self.assertIn(SELF, hits(cards, structures, include_inferred=True, **query))
        self.assertNotIn(SELF, hits(cards, structures, **query))

    def test_negative_default_field_before_a_clause(self):
        """「フィールド魔法カードが表側表示で存在しない場合にこのカードは破壊される」(Sin 怪獸的句型)。"""
        cards, structures = library(
            "フィールド魔法カードが表側表示で存在しない場合にこのカードは破壊される。")
        self.assertEqual(check_card(own(structures)), [])
        self.assertIn(SELF, hits(cards, structures, actions=["破壞"], card=SELF))


class CountedPremiseTest(unittest.TestCase):
    """數量寫在「存在する」前:以上/以下/剛好,單位 体/枚/種類;可接在表示形式後。"""

    def test_each_count_form_writes_back(self):
        texts = (
            "①：自分の墓地に魔法カードが３枚以上存在する場合に発動できる。このカードを破壊する。",
            "①：自分の墓地に魔法カードが３種類以上存在する場合に発動できる。このカードを破壊する。",
            "①：自分フィールドにモンスターが２体存在する場合に発動できる。このカードを破壊する。",
            "①：相手フィールドにモンスターが１体以下存在する場合に発動できる。このカードを破壊する。",
            "①：自分フィールド上にモンスターが表側表示で２体以上存在する場合に発動できる。"
            "このカードを破壊する。",
            "①：「ブラック・マジシャン」が自分フィールド上に表側表示で３体存在する場合に発動できる。"
            "このカードを破壊する。",
        )
        for text in texts:
            with self.subTest(text=text):
                _, structures = library(text)
                self.assertEqual(check_card(own(structures)), [])

    def test_counter_count_writes_back(self):
        """計數器的數量(單位 つ):「魔力カウンターが４つ以上存在する場合」。"""
        _, structures = library(
            "自分フィールドに魔力カウンターが４つ以上存在する場合、このカードは手札から特殊召喚できる。")
        self.assertEqual(check_card(own(structures)), [])

    def test_counted_object_is_still_what_sono_refers_back_to(self):
        """「相手フィールドに「ペンギン」モンスターが２体以上存在する場合に発動できる。そのモンスターを
        破壊する。」:前提的物件帶數量,後文照常指回它(條件是字段)。"""
        cards, structures = library(
            "①：相手フィールドに「ペンギン」モンスターが２体以上存在する場合に発動できる。"
            "そのモンスターを破壊する。")
        self.assertEqual(check_card(own(structures)), [])
        opponent_field = [{"zone": "場上", "side": "對手"}]
        self.assertIn(SELF, hits(cards, structures, actions=["破壞"],
                                 from_zones=opponent_field, card=PENGUIN_SOLDIER))
        self.assertNotIn(SELF, hits(cards, structures, actions=["破壞"],
                                    from_zones=opponent_field, card=BLACK_MAGICIAN))


class EnumeratedPremiseTest(unittest.TestCase):
    """列舉:及び/と(且)、のいずれか(或)、それぞれ(每種各一)、「〜場合、または〜場合」(前提的或)。"""

    def test_each_enumeration_form_writes_back(self):
        texts = (
            "①：自分フィールドに「ペンギン」モンスター及び「竜の渓谷」が存在する場合に発動できる。"
            "このカードを破壊する。",
            "①：自分フィールドに「ブラック・マジシャン」と「青眼の白龍」が存在する場合に発動できる。"
            "このカードを破壊する。",
            "①：自分フィールドに融合・Sモンスターのいずれかが存在する場合に発動できる。"
            "このカードを破壊する。",
            "①：自分フィールドに「青眼の白龍」か「ブラック・マジシャン」が存在する場合に発動できる。"
            "このカードを破壊する。",
            "①：自分フィールドに融合・Sモンスターがそれぞれ存在する場合に発動できる。"
            "このカードを破壊する。",
            "①：自分の墓地に融合・Sモンスターがそれぞれ１体以上存在する場合に発動できる。"
            "このカードを破壊する。",
            "①：自分フィールドにモンスターが存在しない場合、または相手フィールドに「ペンギン」モンスターが"
            "存在する場合に発動できる。このカードを破壊する。",
            "①：自分メインフェイズに、自分フィールドにモンスターが存在しない場合または"
            "相手フィールドにモンスターが存在する場合に発動できる。このカードを破壊する。",
        )
        for text in texts:
            with self.subTest(text=text):
                _, structures = library(text)
                self.assertEqual(check_card(own(structures)), [])

    def test_to_inside_a_name_modifier_is_not_an_enumeration(self):
        """「「ペンギン」と名のついたモンスター」的「と」不是列舉:照舊是一個物件,後文指回它。"""
        cards, structures = library(
            "①：自分フィールド上に「ペンギン」と名のついたモンスターが存在する場合に発動できる。"
            "そのモンスターを破壊する。")
        self.assertEqual(check_card(own(structures)), [])
        self.assertIn(SELF, hits(cards, structures, actions=["破壞"], card=PENGUIN_SOLDIER))
        self.assertNotIn(SELF, hits(cards, structures, actions=["破壞"], card=BLACK_MAGICIAN))

    def test_this_card_in_an_enumeration_sets_its_position(self):
        """「自分の墓地にこのカードと「ブラック・マジシャン」が存在する場合」:列舉裡的此卡照舊把目前位置
        設成墓地,後面的「このカードを特殊召喚する」從墓地(推得關也命中)。"""
        cards, structures = library(
            "①：自分の墓地にこのカードと「ブラック・マジシャン」が存在する場合に発動できる。"
            "このカードを特殊召喚する。")
        self.assertEqual(check_card(own(structures)), [])
        self.assertIn(SELF, hits(cards, structures, actions=["特殊召喚"], from_zones=["墓地"],
                                 card=SELF))
        self.assertNotIn(SELF, hits(cards, structures, actions=["特殊召喚"], from_zones=["手牌"],
                                    card=SELF))

    def test_effect_after_alternative_premises_hits(self):
        """前提的或後面的段照常命中。"""
        cards, structures = library(
            "①：自分フィールドにモンスターが存在しない場合、または相手フィールドに「ペンギン」モンスターが"
            "存在する場合に発動できる。このカードを手札から特殊召喚する。")
        self.assertIn(SELF, hits(cards, structures, actions=["特殊召喚"], from_zones=["手牌"],
                                 card=SELF))


class ZoneAlternativePremiseTest(unittest.TestCase):
    """區域的或「自分のフィールドまたは墓地に」:區域集合。"""

    TEXT = ("①：自分のフィールドまたは墓地に「竜の渓谷」が存在する場合に発動できる。"
            "そのカードを手札に加える。")

    def test_writes_back(self):
        _, structures = library(self.TEXT)
        self.assertEqual(check_card(own(structures)), [])

    def test_either_zone_is_where_the_later_segment_moves_it_from(self):
        cards, structures = library(self.TEXT)
        for zone in ("場上", "墓地"):
            with self.subTest(zone=zone):
                self.assertIn(SELF, hits(cards, structures, actions=["加入手牌"],
                                         from_zones=[{"zone": zone, "side": "我方"}],
                                         card=DRAGON_RAVINE))
        self.assertNotIn(SELF, hits(cards, structures, actions=["加入手牌"],
                                    from_zones=["牌組"], card=DRAGON_RAVINE))


class LpComparePremiseTest(unittest.TestCase):
    """LP 比較:遊戲狀態前提。"""

    def test_each_form_writes_back(self):
        texts = (
            "①：自分のLPが相手より少ない場合に発動できる。このカードを破壊する。",
            "自分のLPが相手より多い場合、このカードは手札から特殊召喚できる。",
            "自分のLPが相手より２０００以上少ない場合、このカードは手札から特殊召喚できる。",
            "①：自分のライフポイントが相手より少ない場合、手札を１枚捨てて発動できる。"
            "このカードを破壊する。",
            "①：自分のLPが相手より多く、自分フィールドにモンスターが存在しない場合に発動できる。"
            "このカードを破壊する。",
        )
        for text in texts:
            with self.subTest(text=text):
                _, structures = library(text)
                self.assertEqual(check_card(own(structures)), [])

    def test_effect_after_lp_premise_hits(self):
        cards, structures = library(
            "自分のLPが相手より少ない場合、このカードは手札から特殊召喚できる。")
        self.assertIn(SELF, hits(cards, structures, actions=["特殊召喚"], from_zones=["手牌"],
                                 card=SELF))


if __name__ == "__main__":
    unittest.main()
