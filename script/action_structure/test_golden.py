"""標準卡的查詢層斷言:輸入官方 DB 文本與卡片參數,看查詢結果。

依 spec「測試決策」:只驗接縫一(查詢判斷),不驗結構內部的格與形狀,
所以結構重構不會讓這裡失效。官方文本逐字寫在測試裡(`data/sources/` 不入版控)。
"""
import unittest

from card_structure import build_structures
from action_query import run_query

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


if __name__ == "__main__":
    unittest.main()
