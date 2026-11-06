"""標準卡的查詢層斷言:輸入官方 DB 文本與卡片參數,看查詢結果。

依 spec「測試決策」:只驗接縫一(查詢判斷),不驗結構內部的格與形狀,
所以結構重構不會讓這裡失效。官方文本逐字寫在測試裡(`data/sources/` 不入版控)。
"""
import unittest

from card_structure import build_structures
from action_query import run_query
from reverse_check import check_card

MONSTER = 0x21  # 效果怪獸
SPELL = 0x2
TRAP = 0x4


def card(cid, **kw):
    """一筆卡片總表條目;預設是一張效果怪獸。"""
    base = {"id": cid, "alt_ids": [], "name_zh": f"卡{cid}", "name_ja": "",
            "name_en": "", "desc": "", "type": MONSTER, "atk": 1000,
            "def": 1000, "level": 4, "race": 0x2000, "attribute": 0x20,
            "scale": 0, "link_marker": 0, "setcode": 0, "ot": 3,
            "md_rarity": "", "genesys_points": 0, "ban_ocg": "",
            "ban_tcg": "", "ban_md": ""}
    base.update(kw)
    if not base["type"] & 0x1:
        base.update({"atk": None, "def": None, "level": 0, "race": 0,
                     "attribute": 0})
    return base


def faq(password, name_ja, card_text, pen_effect=None):
    entry = {"cid": 0, "password": password, "name_ja": name_ja,
             "card_text": card_text}
    if pen_effect is not None:
        entry["pen_effect"] = pen_effect
    return entry


ARCHETYPES = [
    {"setcode": 0x5a, "hex": "0x5a", "names_ja": ["ペンギン"], "name_zh": "企鵝",
     "source": "strings.conf"},
    {"setcode": 0x1b1, "hex": "0x1b1", "names_ja": ["白き森"], "name_zh": "白森林",
     "source": "strings.conf"},
    {"setcode": 0x1bc, "hex": "0x1bc", "names_ja": ["アザミナ"], "name_zh": "聖徒",
     "source": "strings.conf"},
]

SINGULARITY_FIEND = 32484853  # 特異点の悪魔
SINGULARITY_FIEND_TEXT = (
    "このカード名の効果は１ターンに１度しか使用できない。\n"
    "①：相手がモンスターを特殊召喚した時、手札からこのカードと魔法カード１枚を"
    "捨てて発動できる。そのモンスターを破壊する。")


class SingularityFiendTest(unittest.TestCase):
    """特異点の悪魔 32484853(票 01)。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = [
            card(SINGULARITY_FIEND, name_ja="特異点の悪魔", level=1,
                 race=0x40, attribute=0x20, atk=0),
            card(46986414, name_ja="ブラック・マジシャン", level=7,
                 race=0x2, attribute=0x20, atk=2500),
            card(24094653, name_ja="強欲な壺", type=SPELL),
            card(44095762, name_ja="ミラーフォース", type=TRAP),
        ]
        cls.faq = [faq(SINGULARITY_FIEND, "特異点の悪魔",
                       SINGULARITY_FIEND_TEXT)]
        cls.structures, cls.report = build_structures(cls.cards, cls.faq)

    def hits(self, **query):
        result = run_query(self.structures, self.cards, query)
        return [hit["id"] for hit in result["hits"]]

    def test_discard_from_hand_hits_with_this_card_as_object(self):
        """「捨棄 手牌」且對象是此卡:代價段「手札からこのカードと…捨てて」。"""
        self.assertIn(SINGULARITY_FIEND,
                      self.hits(actions=["捨棄"], from_zones=["手牌"],
                                card=SINGULARITY_FIEND))

    def test_discard_to_graveyard_needs_inferred_switch(self):
        """「捨棄 手牌 → 墓地」:終點墓地是推得的,開關開才命中、關不命中。"""
        self.assertIn(SINGULARITY_FIEND,
                      self.hits(actions=["捨棄"], from_zones=["手牌"],
                                to_zones=["墓地"], card=SINGULARITY_FIEND,
                                include_inferred=True))
        self.assertNotIn(SINGULARITY_FIEND,
                         self.hits(actions=["捨棄"], from_zones=["手牌"],
                                   to_zones=["墓地"], card=SINGULARITY_FIEND))

    def test_discard_object_substitution_by_category(self):
        """代價的另一個物件是「魔法カード１枚」:魔法卡代入符合,怪獸與陷阱不符。"""
        self.assertIn(SINGULARITY_FIEND,
                      self.hits(actions=["捨棄"], card=24094653))
        self.assertNotIn(SINGULARITY_FIEND,
                         self.hits(actions=["捨棄"], card=46986414))
        self.assertNotIn(SINGULARITY_FIEND,
                         self.hits(actions=["捨棄"], card=44095762))

    def test_destroy_monster_on_field_needs_inferred_switch(self):
        """「破壞 怪獸 場上」:そのモンスター 的場上是從條件段的特殊召喚推得再繼承的,
        推得開才命中。"""
        monster = {"op": "大類", "value": "怪獸"}
        self.assertIn(SINGULARITY_FIEND,
                      self.hits(actions=["破壞"], condition=monster,
                                from_zones=["場上"], include_inferred=True))
        self.assertNotIn(SINGULARITY_FIEND,
                         self.hits(actions=["破壞"], condition=monster,
                                   from_zones=["場上"]))

    def test_destroy_with_card_substituted(self):
        """破壞的對象是怪獸:黑魔導代入符合,魔法卡不符。"""
        self.assertIn(SINGULARITY_FIEND,
                      self.hits(actions=["破壞"], card=46986414))
        self.assertNotIn(SINGULARITY_FIEND,
                         self.hits(actions=["破壞"], card=24094653))

    def test_targeting_destroy_does_not_hit(self):
        """そのモンスター 是從條件段指回來的,不標取對象:查「取對象 破壞」不命中。"""
        self.assertNotIn(SINGULARITY_FIEND,
                         self.hits(actions=["破壞"], targeting=True))

    def test_special_summon_only_with_condition_switch(self):
        """「相手がモンスターを特殊召喚した時」是條件段:開關關不命中、開命中。"""
        self.assertNotIn(SINGULARITY_FIEND, self.hits(actions=["特殊召喚"]))
        self.assertIn(SINGULARITY_FIEND,
                      self.hits(actions=["特殊召喚"], include_condition=True))

    def test_unrelated_action_does_not_hit(self):
        """這張卡沒有除外:不命中。"""
        self.assertNotIn(SINGULARITY_FIEND, self.hits(actions=["除外"]))

    def test_whole_card_passes_reverse_check(self):
        """整張卡通過反向檢查(票 02):每段由結構套句型模板產生的日文與原文全等。"""
        structure = next(c for c in self.structures
                         if c["id"] == SINGULARITY_FIEND)
        self.assertEqual(check_card(structure), [])


EMPEROR_PENGUIN = 6836211  # 大皇帝ペンギン
EMPEROR_PENGUIN_TEXT = (
    "①：このカードをリリースして発動できる。デッキから「大皇帝ペンギン」以外の"
    "「ペンギン」モンスターを２体まで特殊召喚する。")
PENGUIN_SOLDIER = 93920745   # ペンギン・ソルジャー(setcode 0x5a)
PENGUIN_SPELL = 55555555     # 測試用:帶 ペンギン setcode 的魔法卡
BLACK_MAGICIAN = 46986414


class EmperorPenguinTest(unittest.TestCase):
    """大皇帝ペンギン 6836211(票 04):卡名「以外」、字段依 setcode、物件後置數量。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = [
            card(EMPEROR_PENGUIN, name_ja="大皇帝ペンギン", level=5, race=0x40,
                 attribute=0x2, atk=1800, setcode=0x5a),
            card(PENGUIN_SOLDIER, name_ja="ペンギン・ソルジャー", level=2,
                 race=0x40, attribute=0x2, atk=750, setcode=0x5a),
            card(PENGUIN_SPELL, name_ja="ペンギンの魔法", type=SPELL, setcode=0x5a),
            card(BLACK_MAGICIAN, name_ja="ブラック・マジシャン", level=7,
                 race=0x2, attribute=0x20, atk=2500),
        ]
        cls.faq = [faq(EMPEROR_PENGUIN, "大皇帝ペンギン", EMPEROR_PENGUIN_TEXT)]
        cls.structures, cls.report = build_structures(cls.cards, cls.faq,
                                                      archetypes=ARCHETYPES)

    def hits(self, **query):
        result = run_query(self.structures, self.cards, query)
        return [hit["id"] for hit in result["hits"]]

    def test_penguin_monster_from_deck_special_summon_hits(self):
        """「ペンギン 怪獸 牌組 → 特殊召喚」:ペンギン・ソルジャー(setcode 0x5a)代入命中;
        只給條件(怪獸 且 字段 ペンギン)也命中。"""
        self.assertIn(EMPEROR_PENGUIN,
                      self.hits(actions=["特殊召喚"], from_zones=["牌組"],
                                card=PENGUIN_SOLDIER))
        penguin_monster = {"op": "且", "args": [
            {"op": "大類", "value": "怪獸"},
            {"op": "字段", "setcodes": [0x5a]}]}
        self.assertIn(EMPEROR_PENGUIN,
                      self.hits(actions=["特殊召喚"], from_zones=["牌組"],
                                condition=penguin_monster))

    def test_itself_is_excluded_by_igai(self):
        """「大皇帝ペンギン」以外:指定大皇帝ペンギン本身查「牌組 → 特殊召喚」不命中。"""
        self.assertNotIn(EMPEROR_PENGUIN,
                         self.hits(actions=["特殊召喚"], from_zones=["牌組"],
                                   card=EMPEROR_PENGUIN))

    def test_non_penguin_and_penguin_spell_do_not_fit(self):
        """字段依 setcode:黑魔導(無 setcode)不符;帶 ペンギン setcode 的魔法卡因大類不符。"""
        self.assertNotIn(EMPEROR_PENGUIN,
                         self.hits(actions=["特殊召喚"], card=BLACK_MAGICIAN))
        self.assertNotIn(EMPEROR_PENGUIN,
                         self.hits(actions=["特殊召喚"], card=PENGUIN_SPELL))

    def test_release_this_card_hits(self):
        """「此卡 解放」:代價段「このカードをリリースして」;從場上、到墓地是推得的,
        開關開才算。"""
        self.assertIn(EMPEROR_PENGUIN,
                      self.hits(actions=["解放"], card=EMPEROR_PENGUIN))
        self.assertIn(EMPEROR_PENGUIN,
                      self.hits(actions=["解放"], card=EMPEROR_PENGUIN,
                                from_zones=["場上"], to_zones=["墓地"],
                                include_inferred=True))
        self.assertNotIn(EMPEROR_PENGUIN,
                         self.hits(actions=["解放"], card=EMPEROR_PENGUIN,
                                   from_zones=["場上"]))

    def test_special_summon_destination_is_inferred(self):
        """特殊召喚的終點「場上」是推得的:推得開才以「→ 場上」命中。"""
        self.assertIn(EMPEROR_PENGUIN,
                      self.hits(actions=["特殊召喚"], to_zones=["場上"],
                                include_inferred=True))
        self.assertNotIn(EMPEROR_PENGUIN,
                         self.hits(actions=["特殊召喚"], to_zones=["場上"]))

    def test_unrelated_actions_do_not_hit(self):
        self.assertNotIn(EMPEROR_PENGUIN, self.hits(actions=["破壞"]))
        self.assertNotIn(EMPEROR_PENGUIN, self.hits(actions=["捨棄"]))

    def test_whole_card_passes_reverse_check(self):
        structure = next(c for c in self.structures
                         if c["id"] == EMPEROR_PENGUIN)
        self.assertEqual(check_card(structure), [])


SPROUT = 10753491  # 森羅の神芽 スプラウト
SPROUT_TEXT = (
    "このカードが特殊召喚に成功した時、自分のデッキの上からカードを２枚までめくる事ができる。"
    "めくったカードの中に植物族モンスターがあった場合、それらのモンスターを全て墓地へ送る。"
    "残りのカードは好きな順番でデッキの一番下に戻す。"
    "また、デッキのこのカードがカードの効果によってめくられて墓地へ送られた場合、"
    "デッキから植物族・レベル１モンスター１体を特殊召喚できる。"
    "「森羅の神芽 スプラウト」のこの効果は１ターンに１度しか使用できない。")
SPROUT_SUPPLEMENT = (
    "■『このカードが特殊召喚に成功した時、自分のデッキの上からカードを２枚までめくる事ができる。"
    "めくったカードの中に植物族モンスターがあった場合、それらのモンスターを全て墓地へ送る。"
    "残りのカードは好きな順番でデッキの一番下に戻す』モンスター効果は誘発効果です。")
PLANT = 0x400
LONEFIRE = 56638913  # ローンファイア・ブロッサム:植物族、等級 3
SPROUT_FIXTURE = {
    "cards": [
        card(SPROUT, name_ja="森羅の神芽 スプラウト", level=1, race=PLANT,
             attribute=0x10, atk=100, setcode=0xa60090),
        card(LONEFIRE, name_ja="ローンファイア・ブロッサム", level=3, race=PLANT,
             attribute=0x4, atk=500),
        card(46986414, name_ja="ブラック・マジシャン", level=7, race=0x2,
             attribute=0x20, atk=2500),
        card(24094653, name_ja="強欲な壺", type=SPELL),
    ],
}


class SproutTest(unittest.TestCase):
    """森羅の神芽 スプラウト 10753491(票 10):舊式無編號卡,兩個效果區塊。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = SPROUT_FIXTURE["cards"]
        entry = faq(SPROUT, "森羅の神芽 スプラウト", SPROUT_TEXT)
        entry["supplement"] = SPROUT_SUPPLEMENT
        cls.structures, cls.report = build_structures(cls.cards, [entry])

    def hits(self, **query):
        result = run_query(self.structures, self.cards, query)
        return [hit["id"] for hit in result["hits"]]

    def test_plant_monsters_from_deck_to_graveyard(self):
        """命中「植物族 怪獸 牌組 → 墓地 送墓」:めくったカードの中の植物族モンスター 是翻開的卡
        (牌組頂)的子集,全部送墓;植物族怪獸代入符合、黑魔導與魔法卡不符。"""
        self.assertIn(SPROUT, self.hits(actions=["送墓"], from_zones=["牌組"],
                                        to_zones=["墓地"], card=LONEFIRE))
        self.assertIn(SPROUT, self.hits(actions=["送墓"], from_zones=["牌組頂"],
                                        to_zones=["墓地"], card=SPROUT))
        self.assertNotIn(SPROUT, self.hits(actions=["送墓"], card=46986414))
        self.assertNotIn(SPROUT, self.hits(actions=["送墓"], card=24094653))

    def test_plant_level_1_from_deck_special_summon(self):
        """命中「牌組 → 特殊召喚 植物族 等級1」:等級 3 的植物族不符、黑魔導不符;
        終點場上是推得的,推得開才算。"""
        self.assertIn(SPROUT, self.hits(actions=["特殊召喚"], from_zones=["牌組"],
                                        card=SPROUT))
        self.assertIn(SPROUT, self.hits(actions=["特殊召喚"], from_zones=["牌組"],
                                        to_zones=["場上"], card=SPROUT,
                                        include_inferred=True))
        self.assertNotIn(SPROUT, self.hits(actions=["特殊召喚"], from_zones=["牌組"],
                                           to_zones=["場上"], card=SPROUT))
        self.assertNotIn(SPROUT, self.hits(actions=["特殊召喚"], card=LONEFIRE))
        self.assertNotIn(SPROUT, self.hits(actions=["特殊召喚"], card=46986414))

    def test_remaining_cards_from_deck_top_to_deck_bottom(self):
        """剩餘的卡「牌組頂 → 牌組底」:残りのカード = 翻開的卡 − 植物族怪獸,
        所以黑魔導代入符合、植物族怪獸不符;查「牌組 → 牌組」也對得上。"""
        self.assertIn(SPROUT, self.hits(actions=["返回"], from_zones=["牌組頂"],
                                        to_zones=["牌組底"]))
        self.assertIn(SPROUT, self.hits(actions=["返回"], from_zones=["牌組頂"],
                                        to_zones=["牌組底"], card=46986414))
        self.assertIn(SPROUT, self.hits(actions=["返回"], from_zones=["牌組"],
                                        to_zones=["牌組"], card=24094653))
        self.assertNotIn(SPROUT, self.hits(actions=["返回"], card=LONEFIRE))

    def test_reveal_does_not_move_cards(self):
        """「めくる」不移動:從牌組頂翻開命中,但任何「到」都不命中。"""
        self.assertIn(SPROUT, self.hits(actions=["翻開"], from_zones=["牌組頂"]))
        for zone in ("墓地", "手牌", "場上", "牌組"):
            self.assertNotIn(SPROUT, self.hits(actions=["翻開"], to_zones=[zone],
                                               include_inferred=True))

    def test_being_revealed_and_sent_is_a_condition_segment(self):
        """「めくられて墓地へ送られた場合」是條件段,同時含翻開與送墓:開關關不命中、開命中,
        且從牌組(デッキのこのカード)到墓地。"""
        self.assertNotIn(SPROUT, self.hits(actions=["翻開", "送墓"], card=SPROUT))
        self.assertIn(SPROUT, self.hits(actions=["翻開", "送墓"], card=SPROUT,
                                        from_zones=["牌組"], to_zones=["墓地"],
                                        include_condition=True))

    def test_unrelated_actions_do_not_hit(self):
        for action in ("破壞", "捨棄", "除外", "加入手牌"):
            self.assertNotIn(SPROUT, self.hits(actions=[action]))

    def test_whole_card_passes_reverse_check(self):
        structure = next(c for c in self.structures if c["id"] == SPROUT)
        self.assertEqual(check_card(structure), [])


WHITE_FOREST_LISETTE = 61980241  # 白き森のリゼット
WHITE_FOREST_LISETTE_TEXT = (
    "このカード名の①②の効果はそれぞれ１ターンに１度しか使用できない。\n"
    "①：このカードが手札に存在する場合、自分の手札・フィールドから魔法・罠カード１枚を"
    "墓地へ送って発動できる。このカードを特殊召喚する。その後、デッキから"
    "「白き森のリゼット」以外の「白き森」モンスター１体を手札に加える。\n"
    "②：このカードが墓地に存在する状態で、相手ターンに自分フィールドに魔法使い族・"
    "光属性チューナーが特殊召喚された場合に発動できる。このカードを手札に加える。")
LISETTE_SAINT = 38648860     # 白き森の聖徒リゼット setcode 0x1bc01b1(白き森 + アザミナ)
LIGHT_SPELLCASTER_TUNER = 77777777  # 測試用:光屬性・魔法使族的協調怪獸,無字段
GREEDY_POT = 24094653        # 強欲な壺(魔法)


class WhiteForestLisetteTest(unittest.TestCase):
    """白き森のリゼット 61980241(票 05):前提把此卡的目前位置設成手牌/墓地,
    後續段的「從」繼承;遊戲狀態(相手ターンに)記進前提;代價段兩個出發地。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = [
            card(WHITE_FOREST_LISETTE, name_ja="白き森のリゼット", level=2,
                 race=0x2, attribute=0x10, atk=0, setcode=0x1b1),
            card(LISETTE_SAINT, name_ja="白き森の聖徒リゼット", level=2,
                 race=0x2, attribute=0x10, setcode=0x1bc01b1),
            card(LIGHT_SPELLCASTER_TUNER, name_ja="光の魔法使いチューナー",
                 type=0x1021, level=3, race=0x2, attribute=0x10),
            card(BLACK_MAGICIAN, name_ja="ブラック・マジシャン", level=7,
                 race=0x2, attribute=0x20, atk=2500),
            card(GREEDY_POT, name_ja="強欲な壺", type=SPELL),
        ]
        cls.faq = [faq(WHITE_FOREST_LISETTE, "白き森のリゼット",
                       WHITE_FOREST_LISETTE_TEXT)]
        cls.structures, cls.report = build_structures(cls.cards, cls.faq,
                                                      archetypes=ARCHETYPES)

    def hits(self, **query):
        result = run_query(self.structures, self.cards, query)
        return [hit["id"] for hit in result["hits"]]

    def test_white_forest_monster_from_deck_to_hand_hits(self):
        """「白き森 怪獸 牌組 → 手牌」:只給條件命中;白き森の聖徒リゼット 代入命中;
        リゼット 本身不命中(「白き森のリゼット」以外)。"""
        white_forest_monster = {"op": "且", "args": [
            {"op": "大類", "value": "怪獸"},
            {"op": "字段", "setcodes": [0x1b1]}]}
        self.assertIn(WHITE_FOREST_LISETTE,
                      self.hits(actions=["加入手牌"], from_zones=["牌組"],
                                to_zones=["手牌"], condition=white_forest_monster))
        self.assertIn(WHITE_FOREST_LISETTE,
                      self.hits(actions=["加入手牌"], from_zones=["牌組"],
                                to_zones=["手牌"], card=LISETTE_SAINT))
        self.assertNotIn(WHITE_FOREST_LISETTE,
                         self.hits(actions=["加入手牌"], from_zones=["牌組"],
                                   card=WHITE_FOREST_LISETTE))

    def test_this_card_from_graveyard_to_hand_hits_via_premise(self):
        """「此卡 墓地 → 手牌」:②的「このカードが墓地に存在する状態で」把此卡的位置
        設成墓地,「このカードを手札に加える」的從繼承它;不是推得,推得關也命中。"""
        self.assertIn(WHITE_FOREST_LISETTE,
                      self.hits(actions=["加入手牌"], from_zones=["墓地"],
                                to_zones=["手牌"], card=WHITE_FOREST_LISETTE))

    def test_this_card_from_hand_special_summon_hits_via_premise(self):
        """「此卡 手牌 → 特殊召喚」:①的「このカードが手札に存在する場合」把位置設成手牌;
        終點場上仍是推得的,推得開才以「→ 場上」命中。"""
        self.assertIn(WHITE_FOREST_LISETTE,
                      self.hits(actions=["特殊召喚"], from_zones=["手牌"],
                                card=WHITE_FOREST_LISETTE))
        self.assertIn(WHITE_FOREST_LISETTE,
                      self.hits(actions=["特殊召喚"], from_zones=["手牌"],
                                to_zones=["場上"], card=WHITE_FOREST_LISETTE,
                                include_inferred=True))
        self.assertNotIn(WHITE_FOREST_LISETTE,
                         self.hits(actions=["特殊召喚"], from_zones=["手牌"],
                                   to_zones=["場上"], card=WHITE_FOREST_LISETTE))

    def test_lisette_to_banish_does_not_hit(self):
        """「莉賽特 → 除外」:這張卡沒有除外。"""
        self.assertNotIn(WHITE_FOREST_LISETTE,
                         self.hits(actions=["除外"], card=WHITE_FOREST_LISETTE))
        self.assertNotIn(WHITE_FOREST_LISETTE, self.hits(actions=["除外"]))

    def test_cost_has_two_departure_zones(self):
        """代價段「自分の手札・フィールドから魔法・罠カード１枚を墓地へ送って」:
        從手牌或從場上都命中、到墓地是明寫;魔法卡代入命中,怪獸不符。"""
        for zone_name in ("手牌", "場上"):
            with self.subTest(from_zone=zone_name):
                self.assertIn(WHITE_FOREST_LISETTE,
                              self.hits(actions=["送墓"], from_zones=[zone_name],
                                        to_zones=["墓地"], card=GREEDY_POT))
        self.assertNotIn(WHITE_FOREST_LISETTE,
                         self.hits(actions=["送墓"], card=BLACK_MAGICIAN))
        self.assertNotIn(WHITE_FOREST_LISETTE,
                         self.hits(actions=["送墓"], from_zones=["牌組"],
                                   card=GREEDY_POT))

    def test_condition_segment_with_race_attribute_tuner(self):
        """條件段「自分フィールドに魔法使い族・光属性チューナーが特殊召喚された」:
        條件段開時,光屬性魔法使族協調怪獸代入命中「特殊召喚 → 場上(我方)」,
        黑魔導(非協調)不符;條件段關不命中。"""
        own_field = [{"zone": "場上", "side": "我方"}]
        self.assertIn(WHITE_FOREST_LISETTE,
                      self.hits(actions=["特殊召喚"], to_zones=own_field,
                                card=LIGHT_SPELLCASTER_TUNER,
                                include_condition=True))
        self.assertNotIn(WHITE_FOREST_LISETTE,
                         self.hits(actions=["特殊召喚"], to_zones=own_field,
                                   card=BLACK_MAGICIAN, include_condition=True))
        self.assertNotIn(WHITE_FOREST_LISETTE,
                         self.hits(actions=["特殊召喚"], to_zones=own_field,
                                   card=LIGHT_SPELLCASTER_TUNER))

    def test_whole_card_passes_reverse_check(self):
        structure = next(c for c in self.structures
                         if c["id"] == WHITE_FOREST_LISETTE)
        self.assertEqual(check_card(structure), [])


FALLEN_VIRTUOUS = 30271097  # The Fallen ＆ The Virtuous
FALLEN_VIRTUOUS_TEXT = (
    "このカード名はルール上「烙印」カード、「ドラグマ」カードとしても扱う。\n"
    "このカード名のカードは１ターンに１枚しか発動できない。\n"
    "①：以下の効果から１つを選択して発動できる。\n"
    "●EXデッキから「アルバスの落胤」のカード名が記されたモンスター１体を墓地へ送り、"
    "フィールドの表側表示カード１枚を対象として発動できる。そのカードを破壊する。\n"
    "●自分のフィールドか墓地に「エクレシア」モンスターが存在する場合、"
    "自分か相手の墓地のモンスター１体を対象として発動できる。"
    "そのモンスターを自分フィールドに特殊召喚する。")
ALBAZ = 68468459            # アルバスの落胤(setcode 0x15d 烙印)
MIRRORJADE = 44146295       # 氷剣竜ミラージェイド:卡文記載「アルバスの落胤」的融合怪獸(測試文本)
MIRRORJADE_TEXT = (
    "「アルバスの落胤」＋モンスター１体\n"
    "①：相手フィールドのモンスター１体を対象として発動できる。そのモンスターを除外する。")
BRANCH_ARCHETYPES = ARCHETYPES + [
    {"setcode": 0x15d, "hex": "0x15d", "names_ja": ["烙印"], "name_zh": "烙印",
     "source": "strings.conf"},
    {"setcode": 0x145, "hex": "0x145", "names_ja": ["ドラグマ"], "name_zh": "教導",
     "source": "strings.conf"},
    {"setcode": 0x157, "hex": "0x157", "names_ja": ["エクレシア"], "name_zh": "教會",
     "source": "strings.conf"},
    {"setcode": 0x29, "hex": "0x29", "names_ja": ["ドラグニティ"], "name_zh": "龍盟",
     "source": "strings.conf"},
]


class FallenVirtuousTest(unittest.TestCase):
    """The Fallen ＆ The Virtuous 30271097(票 06):● 列舉是「選1」分歧,兩支各自查得到;
    「〜墓地へ送り、〜を対象として発動できる」是同時連接的兩個子句。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = [
            card(FALLEN_VIRTUOUS, name_ja="The Fallen ＆ The Virtuous",
                 type=0x10002, setcode=0x145015d),
            card(ALBAZ, name_ja="アルバスの落胤", level=4, race=0x2000,
                 attribute=0x20, atk=1800, setcode=0x15d),
            card(MIRRORJADE, name_ja="氷剣竜ミラージェイド", type=0x61, level=8,
                 race=0x2000, attribute=0x20, atk=3000, setcode=0x15d),
            card(BLACK_MAGICIAN, name_ja="ブラック・マジシャン", level=7,
                 race=0x2, attribute=0x20, atk=2500),
            card(GREEDY_POT, name_ja="強欲な壺", type=SPELL),
        ]
        cls.faq = [faq(FALLEN_VIRTUOUS, "The Fallen ＆ The Virtuous",
                       FALLEN_VIRTUOUS_TEXT),
                   faq(MIRRORJADE, "氷剣竜ミラージェイド", MIRRORJADE_TEXT)]
        cls.structures, cls.report = build_structures(
            cls.cards, cls.faq, archetypes=BRANCH_ARCHETYPES)

    def hits(self, **query):
        result = run_query(self.structures, self.cards, query)
        return [hit["id"] for hit in result["hits"]]

    def test_first_option_sends_albaz_mentioning_monster_from_extra_to_graveyard(self):
        """第一支「EXデッキから「アルバスの落胤」のカード名が記されたモンスター１体を墓地へ送り」:
        卡文記載「アルバスの落胤」的 ミラージェイド 代入命中「額外牌組 → 墓地 送墓」;
        黑魔導(卡文不記載)不命中;強欲な壺(魔法)不命中。"""
        self.assertIn(FALLEN_VIRTUOUS,
                      self.hits(actions=["送墓"], from_zones=["額外牌組"],
                                to_zones=["墓地"], card=MIRRORJADE))
        self.assertNotIn(FALLEN_VIRTUOUS,
                         self.hits(actions=["送墓"], from_zones=["額外牌組"],
                                   card=BLACK_MAGICIAN))
        self.assertNotIn(FALLEN_VIRTUOUS,
                         self.hits(actions=["送墓"], card=GREEDY_POT))

    def test_first_option_destroys_targeted_face_up_card_on_field(self):
        """「そのカードを破壊する」指回取對象的「フィールドの表側表示カード１枚」:
        查「取對象 場上 → 破壞」命中(從場上是明寫的,推得關也命中),任何卡都代得進去。"""
        self.assertIn(FALLEN_VIRTUOUS,
                      self.hits(actions=["破壞"], targeting=True,
                                from_zones=["場上"]))
        self.assertIn(FALLEN_VIRTUOUS,
                      self.hits(actions=["破壞"], targeting=True,
                                from_zones=["場上"], card=GREEDY_POT))

    def test_second_option_special_summons_targeted_monster_from_graveyard(self):
        """第二支「自分か相手の墓地のモンスター１体を対象として…そのモンスターを自分フィールドに
        特殊召喚する」:查「取對象 墓地 → 特殊召喚」命中、到=自分フィールド 是明寫的;
        黑魔導代入命中,魔法卡不符。"""
        self.assertIn(FALLEN_VIRTUOUS,
                      self.hits(actions=["特殊召喚"], targeting=True,
                                from_zones=["墓地"], card=BLACK_MAGICIAN))
        self.assertIn(FALLEN_VIRTUOUS,
                      self.hits(actions=["特殊召喚"], targeting=True,
                                from_zones=["墓地"],
                                to_zones=[{"zone": "場上", "side": "我方"}],
                                card=BLACK_MAGICIAN))
        self.assertNotIn(FALLEN_VIRTUOUS,
                         self.hits(actions=["特殊召喚"], card=GREEDY_POT))

    def test_branches_do_not_leak_positions_into_each_other(self):
        """分歧每支各一份位置:第一支送墓的怪獸不會讓第二支的特殊召喚從額外牌組出發,
        第二支的墓地也不會讓第一支的破壞從墓地出發。"""
        self.assertNotIn(FALLEN_VIRTUOUS,
                         self.hits(actions=["特殊召喚"], from_zones=["額外牌組"],
                                   card=BLACK_MAGICIAN))
        self.assertNotIn(FALLEN_VIRTUOUS,
                         self.hits(actions=["破壞"], from_zones=["墓地"]))

    def test_unrelated_actions_do_not_hit(self):
        self.assertNotIn(FALLEN_VIRTUOUS, self.hits(actions=["捨棄"]))
        self.assertNotIn(FALLEN_VIRTUOUS, self.hits(actions=["除外"]))
        self.assertNotIn(FALLEN_VIRTUOUS, self.hits(actions=["加入手牌"]))

    def test_whole_card_passes_reverse_check(self):
        structure = next(c for c in self.structures
                         if c["id"] == FALLEN_VIRTUOUS)
        self.assertEqual(check_card(structure), [])


KAMIKAZE_DRAGUNITY = 7917970  # 神風のドラグニティ
KAMIKAZE_DRAGUNITY_TEXT = (
    "このカード名の①の効果は１ターンに１度しか使用できない。\n"
    "①：自分メインフェイズに発動できる。自分の墓地に「竜の渓谷」が存在する場合、"
    "以下の効果をそれぞれ適用できる。存在しない場合、以下の効果から１つを選んで適用する。\n"
    "●自分の墓地からドラゴン族・鳥獣族モンスター１体を手札に加える。\n"
    "●手札から「ドラグニティ」モンスター１体を特殊召喚する。その後、デッキから"
    "ドラゴン族の「ドラグニティ」モンスター１体を装備魔法カード扱いで、"
    "この効果で特殊召喚したモンスターに装備できる。")
DRAGON_RAVINE = 74822425     # 竜の渓谷(場地魔法,setcode 0x29)
DRAGUNITY_DUX = 76445440     # ドラグニティ－ドゥクス:鳥獣族・風屬性的「ドラグニティ」
DRAGUNITY_PHALANX = 60645181  # ドラグニティ－ファランクス:ドラゴン族的「ドラグニティ」


class KamikazeDragunityTest(unittest.TestCase):
    """神風のドラグニティ 7917970(票 06):「依前提」分歧——墓地有「竜の渓谷」時各自可以、
    沒有時選 1;兩支的段各自查得到;「その後」是先後連接。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = [
            card(KAMIKAZE_DRAGUNITY, name_ja="神風のドラグニティ", type=0x80002,
                 setcode=0x29),
            card(DRAGON_RAVINE, name_ja="竜の渓谷", type=0x80002, setcode=0x29),
            card(DRAGUNITY_DUX, name_ja="ドラグニティ－ドゥクス", level=4,
                 race=0x200, attribute=0x4, atk=1500, setcode=0x29),
            card(DRAGUNITY_PHALANX, name_ja="ドラグニティ－ファランクス", level=2,
                 race=0x2000, attribute=0x4, atk=500, setcode=0x29),
            card(BLACK_MAGICIAN, name_ja="ブラック・マジシャン", level=7,
                 race=0x2, attribute=0x20, atk=2500),
            card(GREEDY_POT, name_ja="強欲な壺", type=SPELL),
        ]
        cls.faq = [faq(KAMIKAZE_DRAGUNITY, "神風のドラグニティ",
                       KAMIKAZE_DRAGUNITY_TEXT)]
        cls.structures, cls.report = build_structures(
            cls.cards, cls.faq, archetypes=BRANCH_ARCHETYPES)

    def hits(self, **query):
        result = run_query(self.structures, self.cards, query)
        return [hit["id"] for hit in result["hits"]]

    def test_first_option_adds_dragon_or_winged_beast_from_graveyard_to_hand(self):
        """第一支「自分の墓地からドラゴン族・鳥獣族モンスター１体を手札に加える」:
        鳥獣族的 ドゥクス、ドラゴン族的 ファランクス 代入都命中「墓地 → 手牌」;
        黑魔導(魔法使い族)不命中。"""
        for cid in (DRAGUNITY_DUX, DRAGUNITY_PHALANX):
            with self.subTest(card=cid):
                self.assertIn(KAMIKAZE_DRAGUNITY,
                              self.hits(actions=["加入手牌"], from_zones=["墓地"],
                                        to_zones=["手牌"], card=cid))
        self.assertNotIn(KAMIKAZE_DRAGUNITY,
                         self.hits(actions=["加入手牌"], from_zones=["墓地"],
                                   card=BLACK_MAGICIAN))

    def test_second_option_special_summons_dragunity_from_hand(self):
        """第二支「手札から「ドラグニティ」モンスター１体を特殊召喚する」:
        ドゥクス(字段 ドラグニティ)代入命中「手牌 → 特殊召喚」;黑魔導不命中;
        竜の渓谷(ドラグニティ 魔法卡)因大類不符。"""
        self.assertIn(KAMIKAZE_DRAGUNITY,
                      self.hits(actions=["特殊召喚"], from_zones=["手牌"],
                                card=DRAGUNITY_DUX))
        self.assertNotIn(KAMIKAZE_DRAGUNITY,
                         self.hits(actions=["特殊召喚"], card=BLACK_MAGICIAN))
        self.assertNotIn(KAMIKAZE_DRAGUNITY,
                         self.hits(actions=["特殊召喚"], card=DRAGON_RAVINE))

    def test_second_option_then_equips_dragon_dragunity_from_deck(self):
        """「その後、デッキからドラゴン族の「ドラグニティ」モンスター１体を装備魔法カード扱いで、
        この効果で特殊召喚したモンスターに装備できる」:ドラゴン族的 ファランクス 代入命中
        「牌組 → 裝備」;鳥獣族的 ドゥクス 不命中。"""
        self.assertIn(KAMIKAZE_DRAGUNITY,
                      self.hits(actions=["裝備"], from_zones=["牌組"],
                                card=DRAGUNITY_PHALANX))
        self.assertNotIn(KAMIKAZE_DRAGUNITY,
                         self.hits(actions=["裝備"], from_zones=["牌組"],
                                   card=DRAGUNITY_DUX))

    def test_branches_do_not_leak_positions_into_each_other(self):
        """第一支把怪獸加入手牌後,第二支的特殊召喚不會因此從墓地出發。"""
        self.assertNotIn(KAMIKAZE_DRAGUNITY,
                         self.hits(actions=["特殊召喚"], from_zones=["墓地"],
                                   card=DRAGUNITY_DUX))

    def test_unrelated_actions_do_not_hit(self):
        self.assertNotIn(KAMIKAZE_DRAGUNITY, self.hits(actions=["破壞"]))
        self.assertNotIn(KAMIKAZE_DRAGUNITY, self.hits(actions=["除外"]))
        self.assertNotIn(KAMIKAZE_DRAGUNITY, self.hits(actions=["送墓"]))

    def test_whole_card_passes_reverse_check(self):
        structure = next(c for c in self.structures
                         if c["id"] == KAMIKAZE_DRAGUNITY)
        self.assertEqual(check_card(structure), [])


if __name__ == "__main__":
    unittest.main()
