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


if __name__ == "__main__":
    unittest.main()
