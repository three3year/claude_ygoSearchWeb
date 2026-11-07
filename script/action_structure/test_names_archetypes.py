"""名稱表、卡片屬性表與字段條件(票 04):只走接縫一(查詢判斷)與接縫二(反向檢查),
輸入官方卡文、卡片參數與字段表,看命中與不命中。

- 字段依 setcode 判:讀音型字段(白き森の聖徒リゼット 屬 アザミナ)卡名裡沒有字段名也命中;
  「古代の機械（アンティーク・ギア）」兩種寫法都對得到同一個 setcode。
- 「「X」と名のついた」= 字段;「カード名に「X」を含む」= 卡名子字串、不看 setcode。
- 卡名帶位置條件(「フィールド・墓地に存在する限り「X」として扱う」)只在該位置算;
  「ルール上「X」カードとしても扱う」任何位置都算字段。
- 不認得的「」名稱:該物件標解析不出、進未解析組與覆蓋報告,建置照常。
"""
import unittest

from action_query import run_query
from card_structure import build_structures
from coverage_report import build_coverage
from reverse_check import check_card
from test_golden import ARCHETYPES, SPELL, card, faq

ARCHETYPES = ARCHETYPES + [
    {"setcode": 0x7, "hex": "0x7", "names_ja": ["古代の機械", "アンティーク・ギア"],
     "name_zh": "古代的機械", "source": "strings.conf"},
    {"setcode": 0x10a2, "hex": "0x10a2", "names_ja": ["ブラック・マジシャン"],
     "name_zh": "黑魔導", "source": "strings.conf"},
    {"setcode": 0x1a8, "hex": "0x1a8", "names_ja": ["トイ"], "name_zh": "玩具",
     "source": "strings.conf"},
]

LISETTE_SAINT = 38648860   # 白き森の聖徒リゼット setcode 0x1bc01b1(白き森 + アザミナ)
LISETTE = 61980241         # 白き森のリゼット setcode 0x1b1
GEAR_GOLEM = 83104731      # 古代の機械巨人 setcode 0x7
AZAMINA_NAMED = 70000001   # 測試用:卡名含「アザミナ」但沒有 setcode
BLACK_MAGICIAN = 46986414
DOOM_MAGICIAN = 59400890   # 滅びの黒魔術師:場上、墓地視為ブラック・マジシャン
SKY_STRIKER_LIKE = 70000002  # 測試用:ルール上「ペンギン」カードとしても扱う

Q_AZAMINA = 10000001
Q_WHITE_FOREST = 10000002
Q_GEAR_READING = 10000003
Q_GEAR_KANJI = 10000004
Q_OLD_STYLE = 10000005
Q_NAME_CONTAINS = 10000006
Q_BM_FROM_DECK = 10000007
Q_BM_FROM_GRAVE = 10000008
Q_PENGUIN_CARD = 10000009
Q_UNKNOWN = 10000010


def fixtures():
    cards = [
        card(LISETTE_SAINT, name_ja="白き森の聖徒リゼット", level=2, race=0x2,
             attribute=0x10, setcode=0x1bc01b1),
        card(LISETTE, name_ja="白き森のリゼット", level=2, race=0x2,
             attribute=0x10, setcode=0x1b1),
        card(GEAR_GOLEM, name_ja="古代の機械巨人", level=8, race=0x8,
             attribute=0x40, setcode=0x7),
        card(AZAMINA_NAMED, name_ja="アザミナの偽者", level=4),
        card(BLACK_MAGICIAN, name_ja="ブラック・マジシャン", level=7, race=0x2),
        card(DOOM_MAGICIAN, name_ja="滅びの黒魔術師", level=8, race=0x2,
             type=0x61),
        card(SKY_STRIKER_LIKE, name_ja="南極の魔法陣", type=SPELL),
    ] + [card(cid, name_ja=f"查詢卡{cid}") for cid in (
        Q_AZAMINA, Q_WHITE_FOREST, Q_GEAR_READING, Q_GEAR_KANJI, Q_OLD_STYLE,
        Q_NAME_CONTAINS, Q_BM_FROM_DECK, Q_BM_FROM_GRAVE, Q_PENGUIN_CARD,
        Q_UNKNOWN)]
    entries = [
        faq(DOOM_MAGICIAN, "滅びの黒魔術師",
            "①：このカードはフィールド・墓地に存在する限り、カード名を"
            "「ブラック・マジシャン」として扱う。"),
        faq(SKY_STRIKER_LIKE, "南極の魔法陣",
            "このカード名はルール上「ペンギン」カードとしても扱う。\n"
            "①：このカードを破壊する。"),
        faq(Q_AZAMINA, "查詢卡",
            "①：デッキから「アザミナ」モンスター１体を特殊召喚する。"),
        faq(Q_WHITE_FOREST, "查詢卡",
            "①：デッキから「白き森」モンスター１体を特殊召喚する。"),
        faq(Q_GEAR_READING, "查詢卡",
            "①：デッキから「アンティーク・ギア」モンスター１体を特殊召喚する。"),
        faq(Q_GEAR_KANJI, "查詢卡",
            "①：デッキから「古代の機械」モンスター１体を特殊召喚する。"),
        faq(Q_OLD_STYLE, "查詢卡",
            "①：デッキから「アザミナ」と名のついたモンスター１体を特殊召喚する。"),
        faq(Q_NAME_CONTAINS, "查詢卡",
            "①：デッキからカード名に「アザミナ」を含むモンスター１体を特殊召喚する。"),
        faq(Q_BM_FROM_DECK, "查詢卡",
            "①：デッキから「ブラック・マジシャン」１体を特殊召喚する。"),
        faq(Q_BM_FROM_GRAVE, "查詢卡",
            "①：墓地から「ブラック・マジシャン」１体を特殊召喚する。"),
        faq(Q_PENGUIN_CARD, "查詢卡",
            "①：デッキから「ペンギン」カード１枚を手札に加える。"),
        faq(Q_UNKNOWN, "查詢卡",
            "①：デッキから「ペンギントークン」モンスター１体を特殊召喚する。"),
    ]
    return cards, entries


class ArchetypeConditionTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.cards, entries = fixtures()
        cls.structures, _ = build_structures(cls.cards, entries,
                                             archetypes=ARCHETYPES)

    def hits(self, **query):
        return [h["id"] for h in run_query(self.structures, self.cards, query)["hits"]]

    def test_reading_type_archetype_is_judged_by_setcode(self):
        """白き森の聖徒リゼット 的卡名沒有「アザミナ」,setcode 有:
        「アザミナ」モンスター 命中;白き森のリゼット(只有 白き森)不命中。"""
        self.assertIn(Q_AZAMINA, self.hits(actions=["特殊召喚"], card=LISETTE_SAINT))
        self.assertNotIn(Q_AZAMINA, self.hits(actions=["特殊召喚"], card=LISETTE))
        self.assertIn(Q_WHITE_FOREST, self.hits(actions=["特殊召喚"], card=LISETTE_SAINT))
        self.assertIn(Q_WHITE_FOREST, self.hits(actions=["特殊召喚"], card=LISETTE))

    def test_kanji_and_reading_spellings_map_to_the_same_setcode(self):
        """卡文寫「アンティーク・ギア」或「古代の機械」都是 0x7。"""
        for q in (Q_GEAR_READING, Q_GEAR_KANJI):
            self.assertIn(q, self.hits(actions=["特殊召喚"], card=GEAR_GOLEM))
            self.assertNotIn(q, self.hits(actions=["特殊召喚"], card=BLACK_MAGICIAN))

    def test_old_style_to_na_no_tsuita_is_archetype(self):
        self.assertIn(Q_OLD_STYLE, self.hits(actions=["特殊召喚"], card=LISETTE_SAINT))
        self.assertNotIn(Q_OLD_STYLE, self.hits(actions=["特殊召喚"], card=AZAMINA_NAMED))

    def test_name_contains_compares_card_name_not_setcode(self):
        """「カード名に「アザミナ」を含む」:卡名含字串的命中,只有 setcode 的不命中。"""
        self.assertIn(Q_NAME_CONTAINS,
                      self.hits(actions=["特殊召喚"], card=AZAMINA_NAMED))
        self.assertNotIn(Q_NAME_CONTAINS,
                         self.hits(actions=["特殊召喚"], card=LISETTE_SAINT))

    def test_condition_only_query_with_archetype(self):
        """只給條件「字段 アザミナ 的怪獸」:總表裡有 白き森の聖徒リゼット 符合。"""
        azamina = {"op": "且", "args": [{"op": "大類", "value": "怪獸"},
                                        {"op": "字段", "setcodes": [0x1bc]}]}
        self.assertIn(Q_AZAMINA, self.hits(actions=["特殊召喚"], condition=azamina))
        self.assertNotIn(Q_WHITE_FOREST,
                         self.hits(actions=["特殊召喚"], condition={
                             "op": "字段", "setcodes": [0x7]}))

    def test_name_with_position_condition_uses_the_line_from(self):
        """滅びの黒魔術師 只在場上、墓地視為ブラック・マジシャン:
        「デッキから「ブラック・マジシャン」１体を特殊召喚」不命中、「墓地から」命中;
        ブラック・マジシャン 本身兩者都命中。"""
        self.assertNotIn(Q_BM_FROM_DECK,
                         self.hits(actions=["特殊召喚"], card=DOOM_MAGICIAN))
        self.assertIn(Q_BM_FROM_GRAVE,
                      self.hits(actions=["特殊召喚"], card=DOOM_MAGICIAN))
        self.assertIn(Q_BM_FROM_DECK,
                      self.hits(actions=["特殊召喚"], card=BLACK_MAGICIAN))
        self.assertIn(Q_BM_FROM_GRAVE,
                      self.hits(actions=["特殊召喚"], card=BLACK_MAGICIAN))

    def test_treat_as_line_after_a_material_line_is_still_recognised(self):
        """素材行沒有句號,「〜として扱う」句要靠換行與它分開(票 09 修的票 04 漏洞):
        那一句進略過文本、字段列照記。"""
        cards = [card(SKY_STRIKER_LIKE, name_ja="甲", type=0x2000021),
                 card(93920745, name_ja="ペンギン・ソルジャー", setcode=0x5a)]
        structures, _ = build_structures(cards, [faq(
            SKY_STRIKER_LIKE, "甲",
            "闇属性モンスターを含むモンスター２体\nこのカード名はルール上「ペンギン」カードとしても扱う。\n"
            "①：このカードを破壊する。")], archetypes=ARCHETYPES)
        own = structures[0]
        self.assertEqual([o["reason"] for o in own["omitted"]], ["視為(卡片屬性表)"])
        self.assertIn(0x5a, [row["value"] for row in own["attributes"]["archetype"]])

    def test_rule_archetype_applies_anywhere(self):
        """「ルール上「ペンギン」カードとしても扱う」:沒有 setcode 的魔法卡從牌組也算ペンギン卡。"""
        self.assertIn(Q_PENGUIN_CARD,
                      self.hits(actions=["加入手牌"], card=SKY_STRIKER_LIKE))
        self.assertNotIn(Q_PENGUIN_CARD,
                         self.hits(actions=["加入手牌"], card=BLACK_MAGICIAN))

    def test_unknown_quoted_name_goes_to_unparsed_group_and_coverage(self):
        """「ペンギントークン」不是卡名也不是字段:指定卡代入判不了 → 未解析組附原因;
        覆蓋報告「不認得的「」名稱」列出它與卡號;建置照常通過。"""
        result = run_query(self.structures, self.cards,
                           {"actions": ["特殊召喚"], "card": LISETTE_SAINT})
        self.assertNotIn(Q_UNKNOWN, result["groups"]["全部"])
        self.assertIn(Q_UNKNOWN, result["groups"]["未解析"])
        entry = next(u for u in result["unparsed"] if u["id"] == Q_UNKNOWN)
        self.assertEqual([s["reason"] for s in entry["segments"]],
                         ["不認得的「」名稱"])
        unknown = build_coverage(self.structures)["unknown_names"]
        self.assertEqual(unknown, {"ペンギントークン": [Q_UNKNOWN]})

    def test_query_cards_pass_reverse_check(self):
        """各條件式都有句型模板:字段、「X」以外、と名のついた、カード名に「X」を含む、「X」１体。"""
        for cid in (Q_AZAMINA, Q_GEAR_READING, Q_OLD_STYLE, Q_NAME_CONTAINS,
                    Q_BM_FROM_DECK, Q_PENGUIN_CARD):
            structure = next(c for c in self.structures if c["id"] == cid)
            self.assertEqual(check_card(structure), [], cid)


if __name__ == "__main__":
    unittest.main()
