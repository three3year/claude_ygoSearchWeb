"""物件修飾:閉集與卡片屬性。

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
    加入手牌那一段的物件是「その闇属性モンスター」(回指),這裡只驗取對象的那一段。"""
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


DRAGON_PALADIN = 6075801
DRAGON_PALADIN_TEXT = (
    "①：このカードが召喚・特殊召喚に成功した場合に発動できる。"
    "自分の手札・デッキからレベル７・８のドラゴン族モンスター１体を装備カード扱いとしてこのカードに装備する。"
    "②：装備カードを装備したこのカードは他のモンスターの効果を受けない。"
    "③：自分フィールドのモンスター１体とこのカードをリリースし、"
    "自分の墓地のレベル７・８のドラゴン族モンスター１体を対象として発動できる。そのモンスターを特殊召喚する。")
SPRIGHT_STARTER = 15443125
SPRIGHT_STARTER_TEXT = (
    "このカード名のカードは１ターンに１枚しか発動できない。\n"
    "①：デッキから「スプライト」モンスター１体を特殊召喚し、自分はそのモンスターの元々の攻撃力分のLPを失う。"
    "このカードの発動後、ターン終了時まで自分はレベル２・ランク２・リンク２のモンスターしか特殊召喚できない。")
REBEL_MONARCH = 9283801
REBEL_MONARCH_TEXT = (
    "このカード名の①②の効果はそれぞれ１ターンに１度しか使用できない。\n"
    "①：手札を１枚捨てて発動できる。攻撃力が２４００以上か８００で守備力が１０００のデッキのモンスター３体を"
    "相手に見せ、相手はその中から１体選ぶ。そのモンスター１体を自分の手札に加え、残りを墓地へ送る。"
    "このカードの発動後、ターン終了時まで自分はEXデッキからモンスターを特殊召喚できない。\n"
    "②：墓地のこのカードを除外して発動できる。手札から攻撃力８００／守備力１０００のモンスター１体を特殊召喚する。")
XYZ_MONSTER, LINK_MONSTER = 0x800021, 0x4000021
RED_EYES = 74677422        # 真紅眼の黒竜:龍族、等級 7
BLUE_EYES = 89631139       # 青眼の白龍:龍族、等級 8
RANK_2_XYZ = 90590303      # ギガンテック・スプライト:階級 2
RANK_4_XYZ = 84013237      # No.39 希望皇ホープ:階級 4
LINK_2 = 2857636           # スプライト・エルフ:連結 2
SQUIRE = 73125233          # 冥帝従騎エイドス:攻 800 守 1000
ALL_POLARITIES = ("做", "不能", "不會", "可以", "只能", "必須")


class NumberAttributeTest(_Golden):
    """數值屬性的列舉與並列:「レベル７・８の」「レベル２・ランク２・リンク２の」是或,「攻撃力８００／守備力１０００の」是且。"""
    cards = [
        card(DRAGON_PALADIN, name_ja="巨竜の聖騎士", level=4, race=0x1, attribute=0x10, atk=1700),
        card(SPRIGHT_STARTER, name_ja="スプライト・スターター", type=0x10002),
        card(REBEL_MONARCH, name_ja="叛逆の帝王", type=SPELL),
        card(RED_EYES, name_ja="真紅眼の黒竜", type=NORMAL_MONSTER, level=7, race=0x2000,
             attribute=0x20, atk=2400, **{"def": 2000}),
        card(BLUE_EYES, name_ja="青眼の白龍", type=NORMAL_MONSTER, level=8, race=0x2000,
             attribute=0x10, atk=3000, **{"def": 2500}),
        card(RANK_2_XYZ, name_ja="ギガンテック・スプライト", type=XYZ_MONSTER, level=2, race=0x1000,
             attribute=0x20, atk=1600, **{"def": 1600}),
        card(RANK_4_XYZ, name_ja="No.39 希望皇ホープ", type=XYZ_MONSTER, level=4, race=0x1,
             attribute=0x10, atk=2500, **{"def": 2000}),
        card(LINK_2, name_ja="スプライト・エルフ", type=LINK_MONSTER, level=2, race=0x1000,
             attribute=0x4, atk=1400, **{"def": None}),
        card(SQUIRE, name_ja="冥帝従騎エイドス", level=2, race=0x2, attribute=0x20, atk=800,
             **{"def": 1000}),
    ] + _STAT_CARDS
    faq = [faq(DRAGON_PALADIN, "巨竜の聖騎士", DRAGON_PALADIN_TEXT),
           faq(SPRIGHT_STARTER, "スプライト・スターター", SPRIGHT_STARTER_TEXT),
           faq(REBEL_MONARCH, "叛逆の帝王", REBEL_MONARCH_TEXT)]

    def test_level_list_accepts_either_level(self):
        """「自分の墓地のレベル７・８のドラゴン族モンスター１体を対象として〜特殊召喚する」:等級 7、8 的龍族命中,
        等級 4 的龍族不命中。"""
        for cid in (RED_EYES, BLUE_EYES):
            self.assertIn(DRAGON_PALADIN,
                          self.hits(actions=["特殊召喚"], targeting=True, card=cid))
        self.assertNotIn(DRAGON_PALADIN,
                         self.hits(actions=["特殊召喚"], targeting=True, card=LUSTER_DRAGON))
        self.assertWritesBack(DRAGON_PALADIN, "自分の墓地のレベル７・８のドラゴン族モンスター１体を対象として")

    def test_level_rank_link_list_accepts_any_of_the_three(self):
        """「レベル２・ランク２・リンク２のモンスターしか特殊召喚できない」:等級 2、階級 2、連結 2 各自命中,
        階級 4、等級 1 不命中。"""
        for cid in (SQUIRE, RANK_2_XYZ, LINK_2):
            self.assertTrue(self.hits_restriction(cid), cid)
        for cid in (RANK_4_XYZ, KURIBOH):
            self.assertFalse(self.hits_restriction(cid), cid)
        self.assertWritesBack(
            SPRIGHT_STARTER,
            "このカードの発動後、ターン終了時まで自分はレベル２・ランク２・リンク２のモンスターしか特殊召喚できない")

    def hit_texts(self, hit):
        structure = next(s for s in self.structures if s["id"] == hit["id"])
        return [seg["text"] for block in structure["blocks"] for seg in block["segments"]
                if seg["id"] in hit["segments"]]

    def hits_restriction(self, cid):
        """指定卡代入時,命中的段裡有沒有「レベル２・ランク２・リンク２の〜」那一段。"""
        result = self.run_(actions=["特殊召喚"], polarities=ALL_POLARITIES, card=cid)
        return any("リンク２" in text for hit in result["hits"] if hit["id"] == SPRIGHT_STARTER
                   for text in self.hit_texts(hit))

    def test_attack_slash_defense_requires_both(self):
        """「手札から攻撃力８００／守備力１０００のモンスター１体を特殊召喚する」:攻守都符合才命中。"""
        mine = {"zone": "手牌", "side": "我方"}
        self.assertIn(REBEL_MONARCH,
                      self.hits(actions=["特殊召喚"], from_zones=[mine], card=SQUIRE))
        self.assertNotIn(REBEL_MONARCH,
                         self.hits(actions=["特殊召喚"], from_zones=[mine], card=KURIBOH))
        self.assertWritesBack(REBEL_MONARCH, "手札から攻撃力８００／守備力１０００のモンスター１体を特殊召喚する")


DD_THOMAS = 41546
DD_THOMAS_TEXT = (
    "「DD魔導賢者トーマス」のモンスター効果は１ターンに１度しか使用できない。"
    "①：自分のPゾーンの「DD」カード１枚を対象として発動できる。そのカードを破壊し、"
    "デッキからレベル８の「DDD」モンスター１体を守備表示で特殊召喚する。"
    "このターン、この効果で特殊召喚したモンスターの効果は無効化され、相手が受ける戦闘ダメージは半分になる。")
DD_THOMAS_PEN = (
    "「DD魔導賢者トーマス」のP効果は１ターンに１度しか使用できない。"
    "①：自分メインフェイズに発動できる。"
    "自分のエクストラデッキから表側表示の「DD」Pモンスター１体を手札に加える。")
DD, DDD = 0xaf, 0x10af
DD_ARCHETYPES = [
    {"setcode": DD, "hex": "0xaf", "names_ja": ["DD"], "name_zh": "DD", "source": "strings.conf"},
    {"setcode": DDD, "hex": "0x10af", "names_ja": ["DDD"], "name_zh": "DDD",
     "source": "strings.conf"},
]
PENDULUM_MONSTER = 0x1000021
DD_SAVANT_KEPLER = 11609969    # DD魔導賢者ケプラー:DD、靈擺、等級 1
DDD_CAESAR = 44186624          # DDD制覇王カイゼル:DDD、靈擺、等級 7
DDD_HELL_ARMAGEDDON = 47198668  # DDD死偉王ヘル・アーマゲドン:DDD、靈擺、等級 8


class DDThomasTest(_Golden):
    """DD魔導賢者トーマス 41546:區域字面「Pゾーン」「エクストラデッキ」(使用者故事 30)。"""
    archetypes = DD_ARCHETYPES
    cards = [
        card(DD_THOMAS, name_ja="DD魔導賢者トーマス", type=PENDULUM_MONSTER, level=8, race=0x8,
             attribute=0x20, atk=1800, setcode=DD),
        card(DD_SAVANT_KEPLER, name_ja="DD魔導賢者ケプラー", type=PENDULUM_MONSTER, level=1,
             race=0x8, attribute=0x20, atk=0, setcode=DD),
        card(DDD_CAESAR, name_ja="DDD制覇王カイゼル", type=PENDULUM_MONSTER, level=7,
             race=0x8, attribute=0x20, atk=2800, setcode=DDD),
        card(DDD_HELL_ARMAGEDDON, name_ja="DDD死偉王ヘル・アーマゲドン", type=PENDULUM_MONSTER,
             level=8, race=0x8, attribute=0x20, atk=3000, setcode=DDD),
        card(BLACK_MAGICIAN, name_ja="ブラック・マジシャン", type=NORMAL_MONSTER, level=7,
             race=0x2, attribute=0x20, atk=2500),
    ]
    faq = [faq(DD_THOMAS, "DD魔導賢者トーマス", DD_THOMAS_TEXT, pen_effect=DD_THOMAS_PEN)]

    def test_destroy_hits_for_a_dd_card(self):
        """查「破壞」指定一張「DD」卡:「自分のPゾーンの「DD」カード１枚」判得了、命中。"""
        self.assertIn(DD_THOMAS, self.hits(actions=["破壞"], card=DD_SAVANT_KEPLER))

    def test_destroy_misses_for_a_non_dd_card(self):
        self.assertJudgedMiss(DD_THOMAS, actions=["破壞"], card=BLACK_MAGICIAN)

    def test_the_target_comes_from_my_pendulum_zone(self):
        """「自分のPゾーンの」是從:查「破壞,從我方的 P區」命中;P區算在場上裡。"""
        mine = {"zone": "P區", "side": "我方"}
        self.assertIn(DD_THOMAS, self.hits(actions=["破壞"], from_zones=[mine]))
        self.assertIn(DD_THOMAS, self.hits(actions=["破壞"], from_zones=["場上"]))
        self.assertNotIn(DD_THOMAS, self.hits(actions=["破壞"], from_zones=["墓地"]))

    def test_special_summon_hits_only_for_a_level_8_ddd_monster(self):
        """「レベル８の「DDD」モンスター１体」:等級後面的「の」不擋住後面的字段。"""
        self.assertIn(DD_THOMAS, self.hits(actions=["特殊召喚"], card=DDD_HELL_ARMAGEDDON))
        self.assertNotIn(DD_THOMAS, self.hits(actions=["特殊召喚"], card=DDD_CAESAR))

    def test_add_to_hand_comes_from_the_extra_deck(self):
        """靈擺效果「自分のエクストラデッキから〜」:查「加入手牌,從額外牌組」指定 DD 靈擺怪獸命中。"""
        self.assertIn(DD_THOMAS, self.hits(actions=["加入手牌"], from_zones=["額外牌組"],
                                           card=DD_SAVANT_KEPLER))
        self.assertJudgedMiss(DD_THOMAS, actions=["加入手牌"], from_zones=["額外牌組"],
                              card=BLACK_MAGICIAN)

    def test_segments_write_back_to_their_text(self):
        for text in ("自分のPゾーンの「DD」カード１枚を対象として",
                     "デッキからレベル８の「DDD」モンスター１体を守備表示で特殊召喚する",
                     "自分のエクストラデッキから表側表示の「DD」Pモンスター１体を手札に加える"):
            self.assertWritesBack(DD_THOMAS, text)


DARK_DIMENSION_WARRIOR = 109401
DARK_DIMENSION_WARRIOR_TEXT = (
    "チューナー＋チューナー以外のモンスター１体以上\n"
    "このカード名の①②の効果はそれぞれ１ターンに１度しか使用できない。"
    "①：手札を１枚除外し、除外されている自分の闇属性モンスター１体を対象として発動できる。"
    "そのモンスターを表側守備表示または裏側守備表示で特殊召喚する。"
    "②：自分・相手のエンドフェイズに発動する。"
    "フィールドにセットされたカードの数×１００ダメージを相手に与える。")
SYNCHRO_MONSTER = 0x2021


class DarkDimensionWarriorTest(_Golden):
    """闇次元の戦士 109401:連體子句「除外されている自分の」(使用者故事 24)。"""
    cards = [card(DARK_DIMENSION_WARRIOR, name_ja="闇次元の戦士", type=SYNCHRO_MONSTER, level=5,
                  race=0x1, attribute=0x20, atk=1200)] + _STAT_CARDS
    faq = [faq(DARK_DIMENSION_WARRIOR, "闇次元の戦士", DARK_DIMENSION_WARRIOR_TEXT)]

    def test_targets_a_dark_monster(self):
        """只看取對象、指定闇屬性怪獸:「除外されている自分の闇属性モンスター１体」判得了、命中。"""
        self.assertIn(DARK_DIMENSION_WARRIOR, self.hits(targeting=True, card=KURIBOH))

    def test_does_not_target_a_non_dark_monster(self):
        self.assertNotIn(DARK_DIMENSION_WARRIOR, self.hits(targeting=True, card=LUSTER_DRAGON))

    def test_the_target_is_in_my_banished_zone(self):
        mine = {"zone": "除外", "side": "我方"}
        theirs = {"zone": "除外", "side": "對手"}
        self.assertIn(DARK_DIMENSION_WARRIOR, self.hits(targeting=True, from_zones=[mine]))
        self.assertNotIn(DARK_DIMENSION_WARRIOR, self.hits(targeting=True, from_zones=[theirs]))

    def test_special_summon_from_banished_judges_the_target(self):
        """「そのモンスターを表側守備表示または裏側守備表示で特殊召喚する」:查「特殊召喚,從除外」只看取對象,
        闇屬性怪獸命中;非闇屬性怪獸判得了、不命中,不落進未解析組。"""
        query = dict(actions=["特殊召喚"], targeting=True, from_zones=["除外"])
        self.assertIn(DARK_DIMENSION_WARRIOR, self.hits(card=KURIBOH, **query))
        self.assertJudgedMiss(DARK_DIMENSION_WARRIOR, card=LUSTER_DRAGON, **query)

    def test_segments_write_back_to_their_text(self):
        for text in ("除外されている自分の闇属性モンスター１体を対象として",
                     "そのモンスターを表側守備表示または裏側守備表示で特殊召喚する"):
            self.assertWritesBack(DARK_DIMENSION_WARRIOR, text)


LURKING_G = 25137581
LURKING_G_TEXT = (
    "このカード名の①の効果は１ターンに１度しか使用できない。"
    "①：相手がモンスターの特殊召喚に成功した時に発動できる。このカードを手札から裏側守備表示で特殊召喚する。"
    "この効果で特殊召喚したこのカードは、このターンのエンドフェイズに表側守備表示になる。"
    "②：このカードがエンドフェイズにリバースした場合に発動する。"
    "フィールドの特殊召喚されたモンスターを全て破壊する。")
GRANMARG = 60229110
GRANMARG_TEXT = (
    "①：このカードがアドバンス召喚に成功した場合、フィールドにセットされたカード１枚を対象として発動する。"
    "セットされたそのカードを破壊する。")
KASHTIRA_SOLITARY = 92998610
KASHTIRA_SOLITARY_TEXT = (
    "このカード名の①②の効果はそれぞれ１ターンに１度しか使用できない。\n"
    "①：このカードが召喚した時、手札からモンスター１体を除外して発動できる。"
    "種族が除外したモンスターと同じモンスター１体をデッキから除外する。\n"
    "②：このカードが戦闘または相手の効果で破壊された場合、"
    "自分の除外状態のモンスター１体を対象として発動できる。そのモンスターを手札に加える。")


class RelativeClauseTest(_Golden):
    """連體子句:「特殊召喚された」「セットされた」「除外状態の」。"""
    cards = [card(LURKING_G, name_ja="潜伏するG", level=7, race=0x800, attribute=0x1, atk=1300),
             card(GRANMARG, name_ja="地帝グランマーグ", level=6, race=0x100, attribute=0x1,
                  atk=2400),
             card(KASHTIRA_SOLITARY, name_ja="孤高除獣", level=4, race=0x4000, attribute=0x20,
                  atk=1700)] + _STAT_CARDS
    faq = [faq(LURKING_G, "潜伏するG", LURKING_G_TEXT),
           faq(GRANMARG, "地帝グランマーグ", GRANMARG_TEXT),
           faq(KASHTIRA_SOLITARY, "孤高除獣", KASHTIRA_SOLITARY_TEXT)]

    def test_special_summoned_is_a_state_any_monster_can_have(self):
        """「フィールドの特殊召喚されたモンスターを全て破壊する」:曾被特殊召喚是狀態,任何怪獸都代得進去;
        魔法卡不是怪獸,不命中。"""
        self.assertIn(LURKING_G, self.hits(actions=["破壞"], card=KURIBOH))
        self.assertJudgedMiss(LURKING_G, actions=["破壞"], card=POT_OF_GREED)
        self.assertWritesBack(LURKING_G, "フィールドの特殊召喚されたモンスターを全て破壊する")

    def test_set_card_on_the_field_is_targeted(self):
        """「フィールドにセットされたカード１枚を対象として」:位置 場上 加 表示形式 裏側,任何卡都代得進去。"""
        self.assertIn(GRANMARG, self.hits(targeting=True, card=POT_OF_GREED))
        self.assertIn(GRANMARG, self.hits(targeting=True, from_zones=["場上"]))
        self.assertNotIn(GRANMARG, self.hits(targeting=True, from_zones=["墓地"]))
        self.assertWritesBack(GRANMARG, "フィールドにセットされたカード１枚を対象として")

    def test_banished_state_is_the_banished_zone(self):
        """「自分の除外状態のモンスター１体を対象として〜そのモンスターを手札に加える」:
        查「加入手牌,從我方的除外」指定怪獸命中,指定魔法卡不命中。"""
        mine = {"zone": "除外", "side": "我方"}
        self.assertIn(KASHTIRA_SOLITARY,
                      self.hits(actions=["加入手牌"], from_zones=[mine], card=KURIBOH))
        self.assertJudgedMiss(KASHTIRA_SOLITARY, actions=["加入手牌"], from_zones=[mine],
                              card=POT_OF_GREED)
        self.assertNotIn(KASHTIRA_SOLITARY, self.hits(actions=["加入手牌"], from_zones=["墓地"]))
        self.assertWritesBack(KASHTIRA_SOLITARY, "自分の除外状態のモンスター１体を対象として")


PEERLESS_FIST = 21834870
PEERLESS_FIST_TEXT = (
    "①：自分フィールドに効果モンスター以外の表側表示モンスターが存在し、"
    "モンスターの効果・魔法・罠カードが発動した時に発動できる。その発動を無効にする。"
    "②：セットされたこのカードが相手の効果で破壊された場合に発動できる。"
    "EXデッキから効果モンスター以外のモンスター１体を特殊召喚する。")
SHINE_SPIRITS = 12624008
SHINE_SPIRITS_TEXT = (
    "このカードが戦闘によって破壊され墓地へ送られた時、"
    "フィールド上に表側表示で存在する光属性モンスター以外のモンスターを全て破壊する。")
COUNTER_TRAP = 0x100004
LIGHT_MONSTER = 89631139   # 青眼の白龍:光屬性


class ExceptNounTest(_Golden):
    """「<名詞短語>以外の」→ 非(那個名詞短語的條件)。"""
    cards = [card(PEERLESS_FIST, name_ja="天威無双の拳", type=COUNTER_TRAP),
             card(SHINE_SPIRITS, name_ja="シャインスピリッツ", level=7, race=0x80000,
                  attribute=0x10, atk=2000),
             card(LIGHT_MONSTER, name_ja="青眼の白龍", type=NORMAL_MONSTER, level=8, race=0x2000,
                  attribute=0x10, atk=3000)] + _STAT_CARDS
    faq = [faq(PEERLESS_FIST, "天威無双の拳", PEERLESS_FIST_TEXT),
           faq(SHINE_SPIRITS, "シャインスピリッツ", SHINE_SPIRITS_TEXT)]

    def test_other_than_effect_monsters_accepts_a_non_effect_monster(self):
        """「EXデッキから効果モンスター以外のモンスター１体を特殊召喚する」:通常怪獸命中,效果怪獸不命中。"""
        self.assertIn(PEERLESS_FIST, self.hits(actions=["特殊召喚"], card=BLACK_MAGICIAN))
        self.assertJudgedMiss(PEERLESS_FIST, actions=["特殊召喚"], card=KURIBOH)
        self.assertJudgedMiss(PEERLESS_FIST, actions=["特殊召喚"], card=POT_OF_GREED)
        self.assertWritesBack(PEERLESS_FIST, "EXデッキから効果モンスター以外のモンスター１体を特殊召喚する")

    def test_other_than_light_monsters_rejects_a_light_monster(self):
        """「光属性モンスター以外のモンスターを全て破壊する」:闇屬性怪獸命中,光屬性怪獸不命中。"""
        self.assertIn(SHINE_SPIRITS, self.hits(actions=["破壞"], card=KURIBOH))
        self.assertJudgedMiss(SHINE_SPIRITS, actions=["破壞"], card=LIGHT_MONSTER)


WATTGIRAFFE = 402568
WATTGIRAFFE_TEXT = (
    "①：このカードは直接攻撃できる。\n"
    "②：このカードが直接攻撃で相手に戦闘ダメージを与えた場合に発動する。"
    "このターン、相手は魔法・罠・モンスターの効果を発動できない。")


SERIOUS_DUEL = 39276790
SERIOUS_DUEL_TEXT = (
    "①：ダメージステップにモンスターの効果・魔法・罠カードが発動した時に発動できる。"
    "その発動を無効にし破壊する。")


class EffectHeadNounTest(_Golden):
    """「魔法・罠・モンスターの効果」「モンスターの効果・魔法・罠カード」:被發動的是效果(物件種類 效果),
    條件式是「誰的效果」;指定卡代入時比那張卡。"""
    cards = [card(WATTGIRAFFE, name_ja="エレキリン", level=4, race=0x1000, attribute=0x10,
                  atk=1200),
             card(SERIOUS_DUEL, name_ja="真剣勝負", type=COUNTER_TRAP)] + _STAT_CARDS
    faq = [faq(WATTGIRAFFE, "エレキリン", WATTGIRAFFE_TEXT),
           faq(SERIOUS_DUEL, "真剣勝負", SERIOUS_DUEL_TEXT)]

    def test_cannot_activate_covers_spell_trap_and_monster_effects(self):
        """「相手は魔法・罠・モンスターの効果を発動できない」:查「發動」(不能)指定魔法卡或怪獸都命中。"""
        for cid in (POT_OF_GREED, KURIBOH):
            self.assertIn(WATTGIRAFFE,
                          self.hits(actions=["發動"], polarities=["不能"], card=cid))
        self.assertWritesBack(WATTGIRAFFE, "このターン、相手は魔法・罠・モンスターの効果を発動できない")

    def test_activation_trigger_covers_monster_effects_and_spell_trap_cards(self):
        """「モンスターの効果・魔法・罠カードが発動した時」:查「發動」開條件段,指定魔法卡或怪獸都命中;
        後面「その発動を無効にし破壊する」指回的就是它。"""
        for cid in (POT_OF_GREED, KURIBOH):
            self.assertIn(SERIOUS_DUEL,
                          self.hits(actions=["發動"], include_condition=True, card=cid))
            self.assertIn(SERIOUS_DUEL, self.hits(actions=["無效", "破壞"], card=cid))
        self.assertWholeCardPasses(SERIOUS_DUEL)


BLIZZARD = 473469
BLIZZARD_TEXT = (
    "相手のコントロールするカードの効果によって自分の罠カードが破壊され、"
    "フィールドから墓地に送られた時に発動する事ができる。フィールド上の魔法または罠カード１枚を破壊する。")
ORCUST_ATTACK = 29666221
ORCUST_ATTACK_TEXT = (
    "①：自分または相手のモンスターの攻撃宣言時に、自分フィールドの、「オルフェゴール」モンスター"
    "または「星遺物」モンスター１体をリリースし、相手フィールドのモンスター１体を対象として発動できる。"
    "そのモンスターを除外する。")
TOO_DEEP_GRAVE = 17688543
TOO_DEEP_GRAVE_TEXT = (
    "①：自分または相手の墓地のモンスター１体を対象として発動できる。"
    "次の自分スタンバイフェイズにそのモンスターを墓地から自分フィールドに特殊召喚する。")
ORCUST, WORLD_LEGACY = 0x11b, 0xfe
ORCUST_ARCHETYPES = [
    {"setcode": ORCUST, "hex": "0x11b", "names_ja": ["オルフェゴール"], "name_zh": "自奏聖樂",
     "source": "strings.conf"},
    {"setcode": WORLD_LEGACY, "hex": "0xfe", "names_ja": ["星遺物"], "name_zh": "星遺物",
     "source": "strings.conf"},
]
ORCUST_CYMBAL = 21441617          # オルフェゴール・ディヴェル
WORLD_LEGACY_MONSTER = 55787576   # 星遺物－『星杯』


class EnumerationTest(_Golden):
    """「AまたはB」:用既有的 或。"""
    archetypes = ORCUST_ARCHETYPES
    cards = [card(BLIZZARD, name_ja="猛吹雪", type=TRAP),
             card(ORCUST_ATTACK, name_ja="オルフェゴール・アタック", type=TRAP, setcode=ORCUST),
             card(TOO_DEEP_GRAVE, name_ja="深すぎた墓穴", type=TRAP),
             card(ORCUST_CYMBAL, name_ja="オルフェゴール・ディヴェル", level=4, race=0x20,
                  attribute=0x20, atk=1700, setcode=ORCUST),
             card(WORLD_LEGACY_MONSTER, name_ja="星遺物－『星杯』", level=5, race=0x20,
                  attribute=0x10, atk=0, setcode=WORLD_LEGACY)] + _STAT_CARDS
    faq = [faq(BLIZZARD, "猛吹雪", BLIZZARD_TEXT),
           faq(ORCUST_ATTACK, "オルフェゴール・アタック", ORCUST_ATTACK_TEXT),
           faq(TOO_DEEP_GRAVE, "深すぎた墓穴", TOO_DEEP_GRAVE_TEXT)]

    def test_spell_or_trap_card_is_either_category(self):
        """「フィールド上の魔法または罠カード１枚を破壊する」:魔法卡、陷阱卡命中,怪獸不命中。"""
        self.assertIn(BLIZZARD, self.hits(actions=["破壞"], card=POT_OF_GREED))
        self.assertIn(BLIZZARD, self.hits(actions=["破壞"], card=TOO_DEEP_GRAVE))
        self.assertJudgedMiss(BLIZZARD, actions=["破壞"], card=KURIBOH)
        self.assertWritesBack(BLIZZARD, "フィールド上の魔法または罠カード１枚を破壊する")

    def test_either_of_two_noun_phrases(self):
        """「「オルフェゴール」モンスターまたは「星遺物」モンスター１体をリリースし」:兩個字段的怪獸都命中,
        別的怪獸不命中。"""
        self.assertIn(ORCUST_ATTACK, self.hits(actions=["解放"], card=ORCUST_CYMBAL))
        self.assertIn(ORCUST_ATTACK, self.hits(actions=["解放"], card=WORLD_LEGACY_MONSTER))
        self.assertJudgedMiss(ORCUST_ATTACK, actions=["解放"], card=KURIBOH)

    def test_either_players_graveyard(self):
        """「自分または相手の墓地のモンスター１体を対象として」:方是任一方,怪獸代得進去、魔法卡代不進去。"""
        self.assertIn(TOO_DEEP_GRAVE, self.hits(targeting=True, card=KURIBOH))
        self.assertNotIn(TOO_DEEP_GRAVE, self.hits(targeting=True, card=POT_OF_GREED))
        self.assertWritesBack(TOO_DEEP_GRAVE, "自分または相手の墓地のモンスター１体を対象として")
        self.assertWholeCardPasses(TOO_DEEP_GRAVE)


if __name__ == "__main__":
    unittest.main()
