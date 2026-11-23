"""被動作的卡:這張卡自己(action-search-web 票 12;接縫一 `run_query`,物件的種類另走接縫二)。

查詢鍵 `this_card`(True):只命中物件是此卡的對象線(物件0,或帶狀態的此卡)。物件是條件式、
這張卡剛好滿足的不算;做動作的線不算。和指定卡(`card`)、給條件(`condition`)三者擇一。
官方文本逐字寫在測試裡。標準卡待站主核可(票 12 的 Comments)。
"""
import unittest

from action_index import build_action_index, decode_action_index
from action_query import run_query
from action_rows import (OBJECT_CANDIDATES, OBJECT_THIS, OBJECT_UNDECIDABLE,
                         OBJECT_UNSUBSTITUTABLE, flatten)
from card_structure import build_structures
from test_golden import ARCHETYPES, card, faq

DRAGONMAID_LUFT = 15848542      # ドラゴンメイド・ルフト:自己不會被效果破壞
STARDUST_SIFR = 26268488        # 聖珖神竜 スターダスト・シフル:自分フィールドのカード(含自己)不會被破壞
CHOBHAM = 27352108              # チョバムアーマー・ドラゴン:帶狀態的此卡不會被戰鬥破壞
ISHZARK = 57902462              # 聖導騎士イシュザーク:此卡是破壞的一方(做動作的線)

LUFT_TEXT = (
    "このカード名の①③の効果はそれぞれ１ターンに１度しか使用できない。\n"
    "①：このカードを手札から捨て、フィールドの表側表示モンスター１体を対象として発動できる。"
    "このターン、お互いにその表側表示モンスターのフィールドで発動する効果を発動できない。\n"
    "②：自分フィールドに融合モンスターが存在する限り、このカードは効果では破壊されない。\n"
    "③：自分・相手のバトルフェイズ終了時に発動できる。このカードを手札に戻し、"
    "手札からレベル３の「ドラゴンメイド」モンスター１体を特殊召喚する。")
SIFR_TEXT = (
    "Sモンスターのチューナー＋チューナー以外のSモンスター２体以上\n"
    "このカードはS召喚でしか特殊召喚できない。\n"
    "①：自分フィールドのカードはそれぞれ１ターンに１度だけ戦闘・効果では破壊されない。\n"
    "②：１ターンに１度、相手がモンスターの効果を発動した時に発動できる。"
    "その効果を無効にし、フィールドのカード１枚を破壊する。\n"
    "③：墓地のこのカードを除外し、自分の墓地のレベル８以下の「スターダスト」モンスター１体を"
    "対象として発動できる。そのモンスターを特殊召喚する。")
CHOBHAM_TEXT = (
    "このカード名の②の効果は１ターンに１度しか使用できない。①：相手モンスターの直接攻撃宣言時に"
    "発動できる。このカードを手札から攻撃表示で特殊召喚する。このターン、この効果で特殊召喚した"
    "このカードは戦闘では破壊されず、このカードの戦闘で発生する自分への戦闘ダメージは半分になる。"
    "②：このカードがリンク素材として墓地へ送られた場合、このカード以外の自分の墓地の闇属性"
    "モンスター１体を対象として発動できる。そのモンスターを手札に加える。相手は自身の墓地の"
    "モンスター１体を選んで手札に加える事ができる。")
ISHZARK_TEXT = "このカードが戦闘によってモンスターを破壊した時、そのモンスターをゲームから除外する。"

SELF_ARCHETYPES = ARCHETYPES + [
    {"setcode": 0xa3, "hex": "0xa3", "names_ja": ["スターダスト"], "name_zh": "星塵",
     "source": "strings.conf"},
    {"setcode": 0x133, "hex": "0x133", "names_ja": ["ドラゴンメイド"], "name_zh": "龍女僕",
     "source": "strings.conf"},
]

RESIST_DESTROY = {"actions": ["破壞"], "polarities": ["不會"]}


def self_fixture():
    cards = [
        card(DRAGONMAID_LUFT, name_ja="ドラゴンメイド・ルフト", level=8, race=0x2000,
             attribute=0x8, atk=2700,
             setcode=0x133),
        card(STARDUST_SIFR, name_ja="聖珖神竜 スターダスト・シフル", type=0x2021, level=12,
             race=0x2000, attribute=0x10, atk=4000, setcode=0xa3),
        card(CHOBHAM, name_ja="チョバムアーマー・ドラゴン", level=1, race=0x2000, atk=0),
        card(ISHZARK, name_ja="聖導騎士イシュザーク", level=6, race=0x1, attribute=0x10,
             atk=2300),
    ]
    entries = [
        faq(DRAGONMAID_LUFT, "ドラゴンメイド・ルフト", LUFT_TEXT),
        faq(STARDUST_SIFR, "聖珖神竜 スターダスト・シフル", SIFR_TEXT),
        faq(CHOBHAM, "チョバムアーマー・ドラゴン", CHOBHAM_TEXT),
        faq(ISHZARK, "聖導騎士イシュザーク", ISHZARK_TEXT),
    ]
    structures, _ = build_structures(cards, entries, archetypes=SELF_ARCHETYPES)
    return structures, cards, SELF_ARCHETYPES


class ThisCardTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.structures, cls.cards, _ = self_fixture()

    def hits(self, **query):
        return run_query(self.structures, self.cards, query)["groups"]["全部"]

    def test_self_resistance_hits_and_granted_resistance_does_not(self):
        """「這張卡自己、破壞、極性 不會」:ドラゴンメイド・ルフト「このカードは効果では破壊されない」
        命中;聖珖神竜 スターダスト・シフル 給的是「自分フィールドのカード」,不命中。"""
        self.assertIn(STARDUST_SIFR, self.hits(**RESIST_DESTROY))   # 不限定被動作的卡時兩張都有
        self.assertIn(DRAGONMAID_LUFT, self.hits(**RESIST_DESTROY))
        found = self.hits(**RESIST_DESTROY, this_card=True)
        self.assertIn(DRAGONMAID_LUFT, found)
        self.assertNotIn(STARDUST_SIFR, found)

    def test_condition_the_card_happens_to_satisfy_is_not_this_card(self):
        """スターダスト・シフル 自己也是「自分フィールドのカード」:指定它這張卡時命中,「這張卡自己」不命中。"""
        self.assertIn(STARDUST_SIFR, self.hits(**RESIST_DESTROY, card=STARDUST_SIFR))
        self.assertNotIn(STARDUST_SIFR, self.hits(**RESIST_DESTROY, this_card=True))

    def test_this_card_with_a_state_counts(self):
        """チョバムアーマー・ドラゴン「この効果で特殊召喚したこのカードは戦闘では破壊されず」:
        帶狀態的此卡也是此卡。"""
        self.assertIn(CHOBHAM, self.hits(**RESIST_DESTROY, this_card=True))

    def test_doer_line_does_not_count(self):
        """聖導騎士イシュザーク「このカードが戦闘によってモンスターを破壊した時」:此卡是破壞的一方,
        被破壞的是別的怪獸,「這張卡自己」不命中。"""
        destroyed = {"actions": ["破壞"], "include_condition": True}
        self.assertIn(ISHZARK, self.hits(**destroyed))
        self.assertNotIn(ISHZARK, self.hits(**destroyed, this_card=True))

    def test_this_card_card_and_condition_are_exclusive(self):
        """這張卡自己、指定卡、給條件三者擇一:同時給兩個以上是錯的查詢。"""
        condition = {"op": "屬性比較", "attr": "種族", "cmp": "=", "value": "ドラゴン族"}
        for extra in ({"this_card": True, "card": DRAGONMAID_LUFT},
                      {"this_card": True, "condition": condition},
                      {"card": DRAGONMAID_LUFT, "condition": condition},
                      {"this_card": True, "card": DRAGONMAID_LUFT, "condition": condition}):
            with self.subTest(extra=sorted(extra)):
                with self.assertRaises(ValueError):
                    run_query(self.structures, self.cards, {**RESIST_DESTROY, **extra})

    def test_this_card_false_is_the_same_as_not_given(self):
        for query in (RESIST_DESTROY, {"actions": ["特殊召喚"]}):
            with self.subTest(query=query):
                self.assertEqual(run_query(self.structures, self.cards, query),
                                 run_query(self.structures, self.cards,
                                           {**query, "this_card": False}))


class ObjectKindIndexTest(unittest.TestCase):
    """接縫二:被動作的卡的五種(沒有物件、此卡、候選卡集合、判不了、代不進去)從動作索引讀得回來。"""

    def test_object_kinds_round_trip(self):
        from test_web_parity import parity_fixture
        structures, cards, archetypes = parity_fixture()
        text, report = build_action_index(structures, cards,
                                          [{"id": entry["id"]} for entry in cards], archetypes)
        self.assertEqual(report["problems"], [])
        expected = {}
        for row in flatten(structures, cards).rows:
            lines = expected.setdefault(row.card, {}).setdefault(row.segment, [])
            if row.line is not None:
                lines.append(None if row.line.object is None else row.line.object.kind)
        decoded = {cid: {seg["id"]: [None if line["object"] is None else line["object"]["kind"]
                                     for line in seg["lines"]]
                         for seg in entry["segments"]}
                   for cid, entry in decode_action_index(text)["cards"].items()
                   if entry["segments"]}
        self.assertEqual(decoded, expected)
        kinds = {kind for segs in decoded.values() for lines in segs.values() for kind in lines}
        self.assertLessEqual({OBJECT_THIS, OBJECT_CANDIDATES, OBJECT_UNDECIDABLE,
                              OBJECT_UNSUBSTITUTABLE}, kinds)


if __name__ == "__main__":
    unittest.main()
