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


MAGISTUS_FLAME = 327051  # 絶火の祆現
MAGISTUS_FLAME_TEXT = (
    "このカード名の①②の効果はそれぞれ１ターンに１度しか使用できない。"
    "①：自分の墓地のレベル４以下の「マギストス」モンスター１体を対象として発動できる。"
    "そのモンスターを特殊召喚する。"
    "②：自分の魔法＆罠ゾーンの「マギストス」カードが相手の効果で破壊される場合、"
    "代わりに墓地のこのカードを除外できる。")
MAGISTUS = 0x150
ZOROA_SAGE = 36099130      # 絶火の大賢者ゾロア:マギストス、等級 4
ZOROA_FIEND = 95911373     # 絶火の魔神ゾロア:マギストス、等級 8(同步)
MAGISTUS_ARCHETYPES = ARCHETYPES + [
    {"setcode": MAGISTUS, "hex": "0x150", "names_ja": ["マギストス"],
     "name_zh": "偉魔", "source": "strings.conf"},
]


class MagistusFlameTest(unittest.TestCase):
    """絶火の祆現 327051(票 08):取對象、代替。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = [
            card(MAGISTUS_FLAME, name_ja="絶火の祆現", type=SPELL, setcode=MAGISTUS),
            card(ZOROA_SAGE, name_ja="絶火の大賢者ゾロア", type=0x1021, level=4,
                 race=0x2, attribute=0x4, atk=1500, setcode=MAGISTUS),
            card(ZOROA_FIEND, name_ja="絶火の魔神ゾロア", type=0x2021, level=8,
                 race=0x2, attribute=0x4, atk=2900, setcode=MAGISTUS),
            card(BLACK_MAGICIAN, name_ja="ブラック・マジシャン", level=7,
                 race=0x2, attribute=0x20, atk=2500),
        ]
        cls.faq = [faq(MAGISTUS_FLAME, "絶火の祆現", MAGISTUS_FLAME_TEXT)]
        cls.structures, cls.report = build_structures(
            cls.cards, cls.faq, archetypes=MAGISTUS_ARCHETYPES)

    def hits(self, **query):
        result = run_query(self.structures, self.cards, query)
        return [hit["id"] for hit in result["hits"]]

    def test_targeted_magistus_from_graveyard_special_summon(self):
        """①「取對象 墓地 → 特殊召喚 マギストス」:等級 4 的マギストス怪獸代入命中;
        等級 8 的不符(レベル４以下)、黑魔導不符(字段);從墓地由取對象的物件繼承,推得關也命中。"""
        self.assertIn(MAGISTUS_FLAME,
                      self.hits(actions=["特殊召喚"], targeting=True,
                                from_zones=["墓地"], card=ZOROA_SAGE))
        self.assertNotIn(MAGISTUS_FLAME,
                         self.hits(actions=["特殊召喚"], card=ZOROA_FIEND))
        self.assertNotIn(MAGISTUS_FLAME,
                         self.hits(actions=["特殊召喚"], card=BLACK_MAGICIAN))

    def test_replacement_banish_only_with_replacement_switch(self):
        """②「代わりに墓地のこのカードを除外できる」是做代替的段:查「除外」預設不命中,
        查詢含代替才命中(從墓地明寫)。"""
        self.assertNotIn(MAGISTUS_FLAME, self.hits(actions=["除外"]))
        self.assertNotIn(MAGISTUS_FLAME,
                         self.hits(actions=["除外"], card=MAGISTUS_FLAME))
        self.assertIn(MAGISTUS_FLAME,
                      self.hits(actions=["除外"], from_zones=["墓地"],
                                card=MAGISTUS_FLAME, replacement=True))

    def test_replaced_destruction_is_reachable_from_the_replacing_segment(self):
        """②被代替段「「マギストス」カードが相手の効果で破壊される」:查「破壞」預設不命中,
        查詢含代替時命中,且結果指出做代替的段(= 查「除外」含代替時命中的那段)。"""
        self.assertNotIn(MAGISTUS_FLAME, self.hits(actions=["破壞"], card=ZOROA_SAGE))
        destroyed = run_query(self.structures, self.cards,
                              {"actions": ["破壞"], "card": ZOROA_SAGE,
                               "replacement": True})
        banished = run_query(self.structures, self.cards,
                             {"actions": ["除外"], "card": MAGISTUS_FLAME,
                              "replacement": True})
        hit = next(h for h in destroyed["hits"] if h["id"] == MAGISTUS_FLAME)
        self.assertEqual(sorted(hit["replaced_by"].values()),
                         next(h for h in banished["hits"]
                              if h["id"] == MAGISTUS_FLAME)["segments"])

    def test_unrelated_actions_do_not_hit(self):
        for action in ("捨棄", "送墓", "加入手牌"):
            self.assertNotIn(MAGISTUS_FLAME, self.hits(actions=[action]))

    def test_whole_card_passes_reverse_check(self):
        structure = next(c for c in self.structures if c["id"] == MAGISTUS_FLAME)
        self.assertEqual(check_card(structure), [])


CROSS_DIMENSION = 56889  # 競闘－クロス・ディメンション
CROSS_DIMENSION_TEXT = (
    "①：自分フィールドの「アンティーク・ギア」モンスター１体を対象として発動できる。"
    "そのモンスターを除外する。この効果で除外したモンスターは次のスタンバイフェイズに"
    "フィールドに戻り、その攻撃力はそのターンの終了時まで元々の攻撃力の倍になる。"
    "②：自分フィールドの、「古代の機械巨人」または「古代の機械巨人－アルティメット・パウンド」"
    "が戦闘・効果で破壊される場合、代わりに墓地のこのカードを除外できる。")
ANCIENT_GEAR = 0x7
ANCIENT_GEAR_GOLEM = 83104731          # 古代の機械巨人
ANCIENT_GEAR_GOLEM_ULTIMATE = 95735217  # 古代の機械巨人－アルティメット・パウンド
ANCIENT_GEAR_ARCHETYPES = ARCHETYPES + [
    {"setcode": ANCIENT_GEAR, "hex": "0x7", "names_ja": ["古代の機械", "アンティーク・ギア"],
     "name_zh": "古代機械齒輪", "source": "strings.conf"},
]


class CrossDimensionTest(unittest.TestCase):
    """競闘－クロス・ディメンション 56889(票 08):取對象、延遲回場、被改的屬性、代替。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = [
            card(CROSS_DIMENSION, name_ja="競闘－クロス・ディメンション", type=TRAP),
            card(ANCIENT_GEAR_GOLEM, name_ja="古代の機械巨人", level=8, race=0x20,
                 attribute=0x1, atk=3000, setcode=ANCIENT_GEAR),
            card(ANCIENT_GEAR_GOLEM_ULTIMATE,
                 name_ja="古代の機械巨人－アルティメット・パウンド", level=8, race=0x20,
                 attribute=0x1, atk=3000, setcode=ANCIENT_GEAR),
            card(BLACK_MAGICIAN, name_ja="ブラック・マジシャン", level=7,
                 race=0x2, attribute=0x20, atk=2500),
        ]
        cls.faq = [faq(CROSS_DIMENSION, "競闘－クロス・ディメンション",
                       CROSS_DIMENSION_TEXT)]
        cls.structures, cls.report = build_structures(
            cls.cards, cls.faq, archetypes=ANCIENT_GEAR_ARCHETYPES)

    def hits(self, **query):
        result = run_query(self.structures, self.cards, query)
        return [hit["id"] for hit in result["hits"]]

    def test_targeted_ancient_gear_on_field_is_banished(self):
        """①「取對象 場上 → 除外」:アンティーク・ギア 怪獸(setcode)代入命中,從場上(我方)由
        取對象的物件繼承、到除外明寫;黑魔導不符(字段)。"""
        own_field = [{"zone": "場上", "side": "我方"}]
        self.assertIn(CROSS_DIMENSION,
                      self.hits(actions=["除外"], targeting=True, from_zones=own_field,
                                to_zones=["除外"], card=ANCIENT_GEAR_GOLEM))
        self.assertNotIn(CROSS_DIMENSION,
                         self.hits(actions=["除外"], card=BLACK_MAGICIAN))

    def test_return_at_next_standby_phase_is_delayed_and_not_targeting(self):
        """回場段「次のスタンバイフェイズにフィールドに戻り」是延遲段:仍算卡片做的動作
        (「除外 → 場上 返回」命中,從除外由前一段繼承),但不標取對象。"""
        self.assertIn(CROSS_DIMENSION,
                      self.hits(actions=["返回"], from_zones=["除外"], to_zones=["場上"],
                                card=ANCIENT_GEAR_GOLEM))
        self.assertNotIn(CROSS_DIMENSION, self.hits(actions=["返回"], targeting=True))

    def test_attack_change_is_a_modification_segment(self):
        """「その攻撃力は…元々の攻撃力の倍になる」:性質變更段,對象是回場的怪獸、不標取對象。"""
        self.assertIn(CROSS_DIMENSION,
                      self.hits(actions=["性質變更"], card=ANCIENT_GEAR_GOLEM))
        self.assertNotIn(CROSS_DIMENSION,
                         self.hits(actions=["性質變更"], targeting=True))
        self.assertNotIn(CROSS_DIMENSION,
                         self.hits(actions=["性質變更"], card=BLACK_MAGICIAN))

    def test_replacement_banish_needs_the_replacement_switch(self):
        """②「代わりに墓地のこのカードを除外できる」:查「除外 此卡」預設不命中(①的除外對象
        不是此卡),查詢含代替才命中;被代替的「「古代の機械巨人」または「…パウンド」が破壊される」
        兩個卡名都代得進去、黑魔導不行。"""
        self.assertNotIn(CROSS_DIMENSION,
                         self.hits(actions=["除外"], card=CROSS_DIMENSION))
        self.assertIn(CROSS_DIMENSION,
                      self.hits(actions=["除外"], from_zones=["墓地"],
                                card=CROSS_DIMENSION, replacement=True))
        for golem in (ANCIENT_GEAR_GOLEM, ANCIENT_GEAR_GOLEM_ULTIMATE):
            with self.subTest(card=golem):
                self.assertNotIn(CROSS_DIMENSION,
                                 self.hits(actions=["破壞"], card=golem))
                self.assertIn(CROSS_DIMENSION,
                              self.hits(actions=["破壞"], card=golem, replacement=True))
        self.assertNotIn(CROSS_DIMENSION,
                         self.hits(actions=["破壞"], card=BLACK_MAGICIAN,
                                   replacement=True))

    def test_whole_card_passes_reverse_check(self):
        structure = next(c for c in self.structures if c["id"] == CROSS_DIMENSION)
        self.assertEqual(check_card(structure), [])


CRIMSON_BLADER_BUSTER = 50604072  # クリムゾン・ブレーダー／バスター
CRIMSON_BLADER_BUSTER_TEXT = (
    "このカードは通常召喚できず、「バスター・モード」の効果でのみ特殊召喚できる。\n"
    "このカード名の①の効果は１ターンに１度しか使用できない。\n"
    "①：手札のこのカードを相手に見せて発動できる。「バスター・モード」またはそのカード名が"
    "記されたカード１枚をデッキから手札に加え、このカードをデッキに戻す。\n"
    "②：相手はEXデッキから特殊召喚されたレベル５以上のモンスターの効果を発動できない。\n"
    "③：このカードが破壊された場合に発動できる。自分の墓地から「クリムゾン・ブレーダー」"
    "１体を特殊召喚する。")
CRIMSON_BLADER = 80321197      # クリムゾン・ブレーダー(同步、等級 8)
BUSTER_MODE = 80280737         # バスター・モード(陷阱)
BLUE_EYES_ULTIMATE = 23995346  # 青眼の究極竜(融合、等級 12)
SUMMON_CONDITION_SENTENCE = "このカードは通常召喚できず"


class CrimsonBladerBusterTest(unittest.TestCase):
    """クリムゾン・ブレーダー／バスター 50604072(票 08):極性「不能」、連用形串接、記載。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = [
            card(CRIMSON_BLADER_BUSTER, name_ja="クリムゾン・ブレーダー／バスター",
                 type=0x2000021, level=10, race=0x1, attribute=0x4, atk=3300,
                 setcode=0x104f),
            card(CRIMSON_BLADER, name_ja="クリムゾン・ブレーダー", type=0x2021, level=8,
                 race=0x1, attribute=0x4, atk=2800),
            card(BUSTER_MODE, name_ja="バスター・モード", type=TRAP),
            card(BLUE_EYES_ULTIMATE, name_ja="青眼の究極竜", type=0x41, level=12,
                 race=0x2000, attribute=0x10, atk=4500),
            card(BLACK_MAGICIAN, name_ja="ブラック・マジシャン", level=7,
                 race=0x2, attribute=0x20, atk=2500),
        ]
        cls.faq = [faq(CRIMSON_BLADER_BUSTER, "クリムゾン・ブレーダー／バスター",
                       CRIMSON_BLADER_BUSTER_TEXT)]
        cls.structures, cls.report = build_structures(cls.cards, cls.faq,
                                                      archetypes=ARCHETYPES)

    def hits(self, **query):
        result = run_query(self.structures, self.cards, query)
        return [hit["id"] for hit in result["hits"]]

    def test_search_buster_mode_or_card_that_mentions_it(self):
        """①「デッキ → 手牌」:バスター・モード 代入命中(卡名);記載「バスター・モード」的卡
        (此卡自己)也命中;黑魔導不符。"""
        self.assertIn(CRIMSON_BLADER_BUSTER,
                      self.hits(actions=["加入手牌"], from_zones=["牌組"],
                                to_zones=["手牌"], card=BUSTER_MODE))
        self.assertIn(CRIMSON_BLADER_BUSTER,
                      self.hits(actions=["加入手牌"], from_zones=["牌組"],
                                card=CRIMSON_BLADER_BUSTER))
        self.assertNotIn(CRIMSON_BLADER_BUSTER,
                         self.hits(actions=["加入手牌"], card=BLACK_MAGICIAN))

    def test_this_card_returns_to_deck_in_the_same_sentence(self):
        """①「〜手札に加え、このカードをデッキに戻す」:連用形串接的第二段,此卡「→ 牌組 返回」命中。"""
        self.assertIn(CRIMSON_BLADER_BUSTER,
                      self.hits(actions=["返回"], to_zones=["牌組"],
                                card=CRIMSON_BLADER_BUSTER))

    def test_cannot_activate_is_not_an_activation_hit(self):
        """②「〜効果を発動できない」極性「不能」:查「發動」預設不命中、也不列進未解析組;
        極性範圍含「不能」才命中,且只有額外牌組的等級 5 以上怪獸代得進去。"""
        result = run_query(self.structures, self.cards, {"actions": ["發動"]})
        self.assertNotIn(CRIMSON_BLADER_BUSTER, result["groups"]["全部"])
        self.assertNotIn(CRIMSON_BLADER_BUSTER, result["groups"]["未解析"])
        self.assertIn(CRIMSON_BLADER_BUSTER,
                      self.hits(actions=["發動"], polarities=["不能"],
                                card=BLUE_EYES_ULTIMATE))
        self.assertNotIn(CRIMSON_BLADER_BUSTER,
                         self.hits(actions=["發動"], polarities=["不能"],
                                   card=BLACK_MAGICIAN))

    def test_destroyed_condition_then_special_summon_from_graveyard(self):
        """③「このカードが破壊された場合」是條件段(開關開才算);「墓地 → 特殊召喚
        クリムゾン・ブレーダー」命中、此卡自己不符。"""
        self.assertNotIn(CRIMSON_BLADER_BUSTER,
                         self.hits(actions=["破壞"], card=CRIMSON_BLADER_BUSTER))
        self.assertIn(CRIMSON_BLADER_BUSTER,
                      self.hits(actions=["破壞"], card=CRIMSON_BLADER_BUSTER,
                                include_condition=True))
        self.assertIn(CRIMSON_BLADER_BUSTER,
                      self.hits(actions=["特殊召喚"], from_zones=["墓地"],
                                card=CRIMSON_BLADER))
        self.assertNotIn(CRIMSON_BLADER_BUSTER,
                         self.hits(actions=["特殊召喚"], card=CRIMSON_BLADER_BUSTER))

    def test_whole_card_passes_reverse_check_except_summon_condition(self):
        """整張通過反向檢查;召喚條件句「このカードは通常召喚できず、…」留給票 09 的區塊種類,
        它所在的區塊除外。"""
        structure = next(c for c in self.structures
                         if c["id"] == CRIMSON_BLADER_BUSTER)
        summon_blocks = {b["id"] for b in structure["blocks"]
                         if SUMMON_CONDITION_SENTENCE in b["text"]}
        self.assertEqual(len(summon_blocks), 1)
        self.assertEqual([f for f in check_card(structure)
                          if f["block"] not in summon_blocks], [])

    def test_summon_condition_block_is_a_restriction(self):
        """召喚條件句(票 09):「通常召喚できず」極性不能、「〜の効果でのみ特殊召喚できる」極性只能,
        都是限制段,預設不命中;極性範圍含只能時命中,且只在召喚條件區塊。"""
        self.assertNotIn(CRIMSON_BLADER_BUSTER,
                         self.hits(actions=["特殊召喚"], card=CRIMSON_BLADER_BUSTER))
        self.assertIn(CRIMSON_BLADER_BUSTER,
                      self.hits(actions=["特殊召喚"], card=CRIMSON_BLADER_BUSTER,
                                polarities=["只能"], kinds=["限制"],
                                block_kinds=["召喚條件"]))
        self.assertNotIn(CRIMSON_BLADER_BUSTER,
                         self.hits(actions=["特殊召喚"], card=CRIMSON_BLADER_BUSTER,
                                   polarities=["只能"], kinds=["限制"],
                                   block_kinds=["編號效果"]))
        self.assertIn(CRIMSON_BLADER_BUSTER,
                      self.hits(actions=["通常召喚"], card=CRIMSON_BLADER_BUSTER,
                                polarities=["不能"], kinds=["限制"]))

    def test_whole_card_passes_reverse_check(self):
        """票 09:召喚條件區塊也過,整張通過。"""
        structure = next(c for c in self.structures
                         if c["id"] == CRIMSON_BLADER_BUSTER)
        self.assertEqual(check_card(structure), [])


DARK_MAGICIAN_OF_DESTRUCTION = 59400890  # 滅びの黒魔術師
DARK_MAGICIAN_OF_DESTRUCTION_TEXT = (
    "「ブラック・マジシャン」＋光・闇属性モンスター\n"
    "「滅びの黒魔術師」は１ターンに１度、融合召喚及び以下の方法でのみ特殊召喚できる。\n"
    "●魔法カードの効果が発動したターン、自分フィールドのレベル６以上の魔法使い族・闇属性"
    "モンスター１体を除外した場合にEXデッキから特殊召喚できる。\n"
    "①：このカードのカード名は、フィールド・墓地に存在する限り「ブラック・マジシャン」として扱う。\n"
    "②：このカードが特殊召喚した場合に発動できる。「ブラック・マジシャン」１体またはそのカード名が"
    "記されたカード１枚をデッキから手札に加える。")
# 測試虛構的三張卡:黑魔導的送墓與除外手段,看滅び在哪個位置被當成黑魔導。
FIELD_SENDER = 70000091      # 場上的「ブラック・マジシャン」送墓
DECK_SENDER = 70000092       # 牌組的「ブラック・マジシャン」送墓
GRAVE_BANISHER = 70000093    # 墓地的「ブラック・マジシャン」除外


class DarkMagicianOfDestructionTest(unittest.TestCase):
    """滅びの黒魔術師 59400890(票 09):素材、召喚條件(● 召喚手續)、修飾(視為黑魔導)。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = [
            card(DARK_MAGICIAN_OF_DESTRUCTION, name_ja="滅びの黒魔術師", type=0x61,
                 level=8, race=0x2, attribute=0x20, atk=2800),
            card(BLACK_MAGICIAN, name_ja="ブラック・マジシャン", level=7,
                 race=0x2, attribute=0x20, atk=2500),
            card(SINGULARITY_FIEND, name_ja="特異点の悪魔", level=1,
                 race=0x40, attribute=0x20, atk=0),
            card(GREEDY_POT, name_ja="強欲な壺", type=SPELL),
            card(FIELD_SENDER, name_ja="場の送り手", type=SPELL),
            card(DECK_SENDER, name_ja="デッキの送り手", type=SPELL),
            card(GRAVE_BANISHER, name_ja="墓地の除外手", type=SPELL),
        ]
        cls.faq = [
            faq(DARK_MAGICIAN_OF_DESTRUCTION, "滅びの黒魔術師",
                DARK_MAGICIAN_OF_DESTRUCTION_TEXT),
            faq(FIELD_SENDER, "場の送り手",
                "①：自分フィールドの「ブラック・マジシャン」１体を墓地へ送る。"),
            faq(DECK_SENDER, "デッキの送り手",
                "①：デッキから「ブラック・マジシャン」１体を墓地へ送る。"),
            faq(GRAVE_BANISHER, "墓地の除外手",
                "①：自分の墓地の「ブラック・マジシャン」１体を除外する。"),
        ]
        cls.structures, cls.report = build_structures(cls.cards, cls.faq,
                                                      archetypes=ARCHETYPES)

    def hits(self, **query):
        result = run_query(self.structures, self.cards, query)
        return [hit["id"] for hit in result["hits"]]

    def test_summoning_procedure_banishes_a_monster_from_the_field(self):
        """● 召喚手續「自分フィールドのレベル６以上の魔法使い族・闇属性モンスター１体を除外した場合」:
        「場上 → 除外」限定召喚條件區塊命中;黑魔導(等級 7 魔法使い族 闇)代入符合、特異点の悪魔
        (等級 1)不符;限定編號效果區塊不命中。"""
        self.assertIn(DARK_MAGICIAN_OF_DESTRUCTION,
                      self.hits(actions=["除外"], from_zones=["場上"],
                                to_zones=["除外"], block_kinds=["召喚條件"]))
        self.assertIn(DARK_MAGICIAN_OF_DESTRUCTION,
                      self.hits(actions=["除外"], from_zones=["場上"],
                                card=BLACK_MAGICIAN, block_kinds=["召喚條件"]))
        self.assertNotIn(DARK_MAGICIAN_OF_DESTRUCTION,
                         self.hits(actions=["除外"], card=SINGULARITY_FIEND))
        self.assertNotIn(DARK_MAGICIAN_OF_DESTRUCTION,
                         self.hits(actions=["除外"], block_kinds=["編號效果"]))

    def test_summoning_procedure_special_summons_itself_from_the_extra_deck(self):
        """● 的「EXデッキから特殊召喚できる」主語省略 = 此卡:「額外牌組 → 特殊召喚」此卡命中,
        是召喚手續(預設段類別範圍內);限定召喚條件區塊也命中。"""
        self.assertIn(DARK_MAGICIAN_OF_DESTRUCTION,
                      self.hits(actions=["特殊召喚"], from_zones=["額外牌組"],
                                card=DARK_MAGICIAN_OF_DESTRUCTION))
        self.assertIn(DARK_MAGICIAN_OF_DESTRUCTION,
                      self.hits(actions=["特殊召喚"], card=DARK_MAGICIAN_OF_DESTRUCTION,
                                block_kinds=["召喚條件"], kinds=["召喚手續"]))

    def test_only_by_fusion_or_the_listed_method_is_a_restriction(self):
        """「融合召喚及び以下の方法でのみ特殊召喚できる」是限制段(極性只能):極性範圍含只能才命中;
        查「融合召喚」不命中(它是召喚方式,不是這張卡做的動作)。"""
        self.assertIn(DARK_MAGICIAN_OF_DESTRUCTION,
                      self.hits(actions=["特殊召喚"], card=DARK_MAGICIAN_OF_DESTRUCTION,
                                polarities=["只能"], kinds=["限制"]))
        self.assertNotIn(DARK_MAGICIAN_OF_DESTRUCTION,
                         self.hits(actions=["融合召喚"], include_condition=True))

    def test_spell_activation_in_this_turn_is_a_condition_segment(self):
        """「魔法カードの効果が発動したターン、」是條件段(本回合發生過):條件段關不命中、開命中。"""
        self.assertNotIn(DARK_MAGICIAN_OF_DESTRUCTION,
                         self.hits(actions=["發動"], card=GREEDY_POT))
        self.assertIn(DARK_MAGICIAN_OF_DESTRUCTION,
                      self.hits(actions=["發動"], card=GREEDY_POT,
                                include_condition=True))

    def test_second_effect_adds_dark_magician_or_a_card_naming_it_to_hand(self):
        """②「黑魔導 牌組 → 手牌」命中;記載「ブラック・マジシャン」的卡(此卡自己)也命中;強欲な壺不符。"""
        self.assertIn(DARK_MAGICIAN_OF_DESTRUCTION,
                      self.hits(actions=["加入手牌"], from_zones=["牌組"],
                                to_zones=["手牌"], card=BLACK_MAGICIAN))
        self.assertIn(DARK_MAGICIAN_OF_DESTRUCTION,
                      self.hits(actions=["加入手牌"], from_zones=["牌組"],
                                card=DARK_MAGICIAN_OF_DESTRUCTION))
        self.assertNotIn(DARK_MAGICIAN_OF_DESTRUCTION,
                         self.hits(actions=["加入手牌"], card=GREEDY_POT))

    def test_treated_as_dark_magician_only_on_the_field_and_in_the_graveyard(self):
        """①「フィールド・墓地に存在する限り「ブラック・マジシャン」として扱う」:查「送墓」「除外」
        時,此卡只在場上與墓地被當成黑魔導——場上的送墓手段、墓地的除外手段命中,牌組的送墓手段不命中。"""
        self.assertIn(FIELD_SENDER,
                      self.hits(actions=["送墓"], card=DARK_MAGICIAN_OF_DESTRUCTION))
        self.assertIn(GRAVE_BANISHER,
                      self.hits(actions=["除外"], card=DARK_MAGICIAN_OF_DESTRUCTION))
        self.assertNotIn(DECK_SENDER,
                         self.hits(actions=["送墓"], card=DARK_MAGICIAN_OF_DESTRUCTION))
        self.assertIn(DECK_SENDER, self.hits(actions=["送墓"], card=BLACK_MAGICIAN))

    def test_material_line_is_its_own_block_kind(self):
        """素材行「「ブラック・マジシャン」＋光・闇属性モンスター」自成素材區塊:限定素材區塊時沒有動作可命中,
        也不列進未解析組(素材行不含動作詞)。"""
        result = run_query(self.structures, self.cards,
                           {"actions": ["特殊召喚"], "block_kinds": ["素材"]})
        self.assertEqual(result["groups"]["全部"], [])
        self.assertNotIn(DARK_MAGICIAN_OF_DESTRUCTION, result["groups"]["未解析"])

    def test_whole_card_passes_reverse_check(self):
        for cid in (DARK_MAGICIAN_OF_DESTRUCTION, FIELD_SENDER, DECK_SENDER,
                    GRAVE_BANISHER):
            with self.subTest(card=cid):
                structure = next(c for c in self.structures if c["id"] == cid)
                self.assertEqual(check_card(structure), [])


SEVEN_TOOLS = 3819470  # 盗賊の七つ道具
SEVEN_TOOLS_TEXT = "①：罠カードが発動した時、１０００LPを払って発動できる。その発動を無効にし破壊する。"
MIRROR_FORCE = 44095762  # 聖なるバリア－ミラーフォース－(陷阱)


class SevenToolsTest(unittest.TestCase):
    """盗賊の七つ道具 3819470(票 09):卡片發動、數量格(1000LP、段無物件)、無效且破壞。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = [
            card(SEVEN_TOOLS, name_ja="盗賊の七つ道具", type=0x100004),
            card(MIRROR_FORCE, name_ja="聖なるバリア－ミラーフォース－", type=TRAP),
            card(GREEDY_POT, name_ja="強欲な壺", type=SPELL),
            card(BLACK_MAGICIAN, name_ja="ブラック・マジシャン", level=7,
                 race=0x2, attribute=0x20, atk=2500),
        ]
        cls.faq = [faq(SEVEN_TOOLS, "盗賊の七つ道具", SEVEN_TOOLS_TEXT)]
        cls.structures, cls.report = build_structures(cls.cards, cls.faq)

    def hits(self, **query):
        result = run_query(self.structures, self.cards, query)
        return [hit["id"] for hit in result["hits"]]

    def test_negates_and_destroys_the_activated_trap(self):
        """「その発動を無効にし破壊する」:「無效 且 破壞」命中;對象是發動的那張陷阱卡,
        陷阱代入符合、魔法與怪獸不符。"""
        self.assertIn(SEVEN_TOOLS, self.hits(actions=["無效", "破壞"]))
        self.assertIn(SEVEN_TOOLS,
                      self.hits(actions=["無效", "破壞"], card=MIRROR_FORCE))
        self.assertNotIn(SEVEN_TOOLS, self.hits(actions=["無效"], card=GREEDY_POT))
        self.assertNotIn(SEVEN_TOOLS, self.hits(actions=["破壞"], card=BLACK_MAGICIAN))

    def test_paying_lp_is_a_cost_without_an_object(self):
        """「１０００LPを払って」:支付 LP 是代價段、段無物件;只看效果段不命中。"""
        self.assertIn(SEVEN_TOOLS, self.hits(actions=["支付"], kinds=["代價"]))
        self.assertNotIn(SEVEN_TOOLS, self.hits(actions=["支付"], kinds=["效果"]))

    def test_trap_activation_is_a_condition_segment(self):
        """「罠カードが発動した時」:條件段,開關關不命中、開命中。"""
        self.assertNotIn(SEVEN_TOOLS, self.hits(actions=["發動"]))
        self.assertIn(SEVEN_TOOLS, self.hits(actions=["發動"], include_condition=True,
                                             card=MIRROR_FORCE))

    def test_numbered_effect_of_a_trap_is_a_numbered_block(self):
        """魔陷的①是編號效果(spec 決定):限定編號效果區塊命中、限定卡片發動區塊不命中。"""
        self.assertIn(SEVEN_TOOLS, self.hits(actions=["無效"], block_kinds=["編號效果"]))
        self.assertNotIn(SEVEN_TOOLS, self.hits(actions=["無效"], block_kinds=["卡片發動"]))

    def test_whole_card_passes_reverse_check(self):
        structure = next(c for c in self.structures if c["id"] == SEVEN_TOOLS)
        self.assertEqual(check_card(structure), [])


if __name__ == "__main__":
    unittest.main()
