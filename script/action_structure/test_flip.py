"""動作詞 反轉 的查詢層與反向檢查斷言:輸入真實卡的官方 DB 文本與卡片參數,看查詢結果。

只驗接縫一(查詢判斷)與接縫二(反向檢查),不驗結構內部的格。
"""
import unittest

from action_query import run_query
from card_structure import build_structures
from reverse_check import check_card
from test_golden import TRAP, card, faq

FLIP_MONSTER = 0x200021
CONTINUOUS_TRAP = 0x20004

HIITA = 759393
HIITA_TEXT = (
    "①：このカードがリバースした場合、相手フィールドの炎属性モンスター１体を対象として発動する。"
    "このモンスターが表側表示で存在する間、対象のモンスターのコントロールを得る。")
GEARGIARMOR = 923596
GEARGIARMOR_TEXT = (
    "このカードは１ターンに１度だけ裏側守備表示にする事ができる。このカードがリバースした時、"
    "デッキから「ギアギアーマー」以外の「ギアギア」と名のついたモンスター１体を手札に加える事ができる。")
DES_LACOODA = 2326738
DES_LACOODA_TEXT = (
    "①：自分メインフェイズに発動できる。このカードを裏側守備表示にする（１ターンに１度のみ）。"
    "②：このカードが反転召喚に成功した場合に発動する。自分はデッキから１枚ドローする。")
SUBTERROR_LEGACY = 73575650
SUBTERROR_LEGACY_TEXT = (
    "このカード名のカードは１ターンに１枚しか発動できない。①：以下の効果から１つを選択して発動できる。"
    "発動後このカードは墓地へ送らず、そのままセットする。●手札及び自分フィールドの表側表示モンスターの中から、"
    "モンスター１体を選んで墓地へ送り、同じ属性でカード名が異なるリバースモンスター１体をデッキから手札に"
    "加える。●手札及び自分フィールドの表側表示モンスターの中から、リバースモンスター１体を選んで墓地へ送り、"
    "同じ属性で元々のレベルが低いモンスター１体をデッキから手札に加える。")
ROYAL_DECREE = 33950246
ROYAL_DECREE_TEXT = "このカードがフィールド上に存在する限り、全てのリバース効果モンスターの発動及び効果は無効化される。"
BATTEL = 14824019
BATTEL_TEXT = ("①：このカードが召喚・リバースした場合に発動する。デッキから「魔導書」魔法カード１枚を"
               "手札に加える。")
WHITE_NINJA = 1571945
WHITE_NINJA_TEXT = "リバース：フィールド上の守備表示モンスター１体を破壊する。"
WORM_APOCALYPSE = 88650530
WORM_APOCALYPSE_TEXT = "リバース：フィールド上の魔法・罠カード１枚を選択して破壊する。"
ARCHETYPES = [
    {"setcode": 0x72, "hex": "0x72", "names_ja": ["ギアギア"], "name_zh": "齒輪齒輪",
     "source": "strings.conf"},
    {"setcode": 0x106e, "hex": "0x106e", "names_ja": ["魔導書"], "name_zh": "魔導書",
     "source": "strings.conf"},
]


class FlipFixture(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.cards = [
            card(HIITA, name_ja="火霊使いヒータ", type=FLIP_MONSTER, level=3, race=0x2,
                 attribute=0x4, atk=500, setcode=0xbf),
            card(GEARGIARMOR, name_ja="ギアギアーマー", level=4, race=0x20, attribute=0x1,
                 atk=1100, setcode=0x72),
            card(DES_LACOODA, name_ja="デス・ラクーダ", level=3, race=0x10, attribute=0x1, atk=500),
            card(SUBTERROR_LEGACY, name_ja="サブテラーの継承", type=TRAP, setcode=0xed),
            card(ROYAL_DECREE, name_ja="王宮の号令", type=CONTINUOUS_TRAP),
            card(WHITE_NINJA, name_ja="白い忍者", type=FLIP_MONSTER, level=4, race=0x1,
                 attribute=0x10, atk=1500, setcode=0x2b),
            card(WORM_APOCALYPSE, name_ja="ワーム・アポカリプス", type=FLIP_MONSTER, level=1,
                 race=0x80000, attribute=0x10, atk=300, setcode=0x3e),
            card(BATTEL, name_ja="魔導書士 バテル", level=2, race=0x2, attribute=0x2, atk=500,
                 setcode=0x106e),
        ]
        cls.faq = [
            faq(HIITA, "火霊使いヒータ", HIITA_TEXT),
            faq(GEARGIARMOR, "ギアギアーマー", GEARGIARMOR_TEXT),
            faq(DES_LACOODA, "デス・ラクーダ", DES_LACOODA_TEXT),
            faq(SUBTERROR_LEGACY, "サブテラーの継承", SUBTERROR_LEGACY_TEXT),
            faq(ROYAL_DECREE, "王宮の号令", ROYAL_DECREE_TEXT),
            faq(WHITE_NINJA, "白い忍者", WHITE_NINJA_TEXT),
            faq(WORM_APOCALYPSE, "ワーム・アポカリプス", WORM_APOCALYPSE_TEXT),
            faq(BATTEL, "魔導書士 バテル", BATTEL_TEXT),
        ]
        cls.structures, cls.report = build_structures(cls.cards, cls.faq, archetypes=ARCHETYPES)

    def run_query(self, **query):
        return run_query(self.structures, self.cards, query)

    def hits(self, **query):
        return [hit["id"] for hit in self.run_query(**query)["hits"]]

    def hit_segments(self, cid, **query):
        return next((hit["segments"] for hit in self.run_query(**query)["hits"]
                     if hit["id"] == cid), None)

    def structure(self, cid):
        return next(c for c in self.structures if c["id"] == cid)


class NewStyleFlipTest(FlipFixture):
    """「Xがリバースした場合/時」:條件段,動作詞 反轉,X 是被反轉的卡。"""

    def test_flipped_this_card_hits_flip_with_condition_on(self):
        """火霊使いヒータ「このカードがリバースした場合」、ギアギアーマー「このカードがリバースした時」:
        開條件段查「反轉」命中,指定此卡也命中;條件段關時不命中。"""
        for cid in (HIITA, GEARGIARMOR):
            self.assertIn(cid, self.hits(actions=["反轉"], include_condition=True), cid)
            self.assertIn(cid, self.hits(actions=["反轉"], include_condition=True, card=cid), cid)
            self.assertNotIn(cid, self.hits(actions=["反轉"]), cid)

    def test_geargiarmor_passes_reverse_check(self):
        self.assertEqual(check_card(self.structure(GEARGIARMOR)), [])


class OldStyleFlipLabelTest(FlipFixture):
    """舊式標示「リバース：X」:條件段(反轉,此卡,觸發形 場合)加上 X 的段。"""

    def test_label_hits_flip_with_condition_on(self):
        """白い忍者:開條件段查「反轉」命中,指定此卡也命中;條件段關時不命中;
        和新式「このカードがリバースした場合」的 火霊使いヒータ 同一組查詢結果相同。"""
        self.assertIn(WHITE_NINJA, self.hits(actions=["反轉"], include_condition=True,
                                             card=WHITE_NINJA))
        self.assertNotIn(WHITE_NINJA, self.hits(actions=["反轉"]))
        for query in ({"actions": ["反轉"], "include_condition": True},
                      {"actions": ["反轉"], "include_condition": True, "kinds": ["條件"]},
                      {"actions": ["反轉"]}, {"actions": ["反轉召喚"], "include_condition": True}):
            hits = self.hits(**query)
            self.assertEqual(WHITE_NINJA in hits, HIITA in hits, query)

    def test_effect_after_label_hits_destroy_by_default(self):
        """白い忍者「フィールド上の守備表示モンスター１体を破壊する」:查「破壞」(預設開關)命中,
        命中的不是標示那一段;查「破壞,從 場上」也命中。"""
        segments = self.hit_segments(WHITE_NINJA, actions=["破壞"])
        self.assertIsNotNone(segments)
        flip = self.hit_segments(WHITE_NINJA, actions=["反轉"], include_condition=True)
        self.assertFalse(set(segments) & set(flip))
        self.assertIn(WHITE_NINJA, self.hits(actions=["破壞"], from_zones=["場上"]))

    def test_effect_after_label_is_not_delayed(self):
        """ワーム・アポカリプス「リバース：フィールド上の魔法・罠カード１枚を選択して破壊する」:標示後的效果段
        不因前面的條件段算延遲,查「破壞」並只看取對象時命中;白い忍者(沒有取對象)不命中;整張通過反向檢查。"""
        targeting = self.hits(actions=["破壞"], targeting=True)
        self.assertIn(WORM_APOCALYPSE, targeting)
        self.assertNotIn(WHITE_NINJA, targeting)
        self.assertEqual(check_card(self.structure(WORM_APOCALYPSE)), [])

    def test_white_ninja_writes_back_the_label(self):
        """白い忍者 整張通過反向檢查:標示那一段寫回「リバース：」,不是「このカードがリバースした場合」。"""
        self.assertEqual(check_card(self.structure(WHITE_NINJA)), [])


class EnumeratedFlipTest(FlipFixture):
    """「召喚・リバースした」:一段多個動作詞,同「召喚・特殊召喚に成功した」。"""

    def test_summon_and_flip_hit_the_same_segment(self):
        """魔導書士 バテル「このカードが召喚・リバースした場合」:開條件段查「召喚」與查「反轉」命中同一段,
        指定此卡也命中;查「反轉召喚」「特殊召喚」不命中。"""
        summon = self.hit_segments(BATTEL, actions=["召喚"], include_condition=True, card=BATTEL)
        flip = self.hit_segments(BATTEL, actions=["反轉"], include_condition=True, card=BATTEL)
        self.assertIsNotNone(summon)
        self.assertEqual(summon, flip)
        self.assertIn(BATTEL, self.hits(actions=["召喚", "反轉"], include_condition=True))
        for action in ("反轉召喚", "特殊召喚"):
            self.assertNotIn(BATTEL, self.hits(actions=[action], include_condition=True), action)

    def test_battel_passes_reverse_check(self):
        self.assertEqual(check_card(self.structure(BATTEL)), [])


class FlipIsNotFlipSummonOrFlipMonsterTest(FlipFixture):
    """反轉、反轉召喚、反轉怪獸是三個不一樣的東西(站主裁定)。"""

    ALL = {"polarities": ["做", "不能", "不會", "可以", "只能", "必須"]}

    def test_flip_does_not_hit_flip_summon_and_vice_versa(self):
        """開條件段查「反轉」不命中只寫「反転召喚に成功した」的 デス・ラクーダ,也不列進未解析組;
        開條件段查「反轉召喚」不命中只寫「リバースした」的 火霊使いヒータ、ギアギアーマー,也不列進未解析組。"""
        flip = self.run_query(actions=["反轉"], include_condition=True)
        self.assertNotIn(DES_LACOODA, [hit["id"] for hit in flip["hits"]])
        self.assertNotIn(DES_LACOODA, flip["groups"]["未解析"])
        self.assertIn(DES_LACOODA, self.hits(actions=["反轉召喚"], include_condition=True))
        flip_summon = self.run_query(actions=["反轉召喚"], include_condition=True)
        for cid in (HIITA, GEARGIARMOR):
            self.assertNotIn(cid, [hit["id"] for hit in flip_summon["hits"]], cid)
            self.assertNotIn(cid, flip_summon["groups"]["未解析"], cid)

    def test_flip_monster_literal_is_not_the_flip_action(self):
        """サブテラーの継承「リバースモンスター１体を選んで墓地へ送り」、王宮の号令「リバース効果モンスター」
        (段解析不出):查「反轉」不命中,也不因這兩個字面列進未解析組;查「送墓」列 サブテラーの継承。"""
        for query in ({}, {"include_condition": True}):
            result = self.run_query(actions=["反轉"], **self.ALL, **query)
            for cid in (SUBTERROR_LEGACY, ROYAL_DECREE):
                self.assertNotIn(cid, [hit["id"] for hit in result["hits"]], cid)
                self.assertNotIn(cid, result["groups"]["未解析"], cid)
        self.assertIn(SUBTERROR_LEGACY, self.run_query(actions=["送墓"])["groups"]["未解析"])


if __name__ == "__main__":
    unittest.main()
