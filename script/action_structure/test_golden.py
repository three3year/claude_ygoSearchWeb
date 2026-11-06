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


if __name__ == "__main__":
    unittest.main()
