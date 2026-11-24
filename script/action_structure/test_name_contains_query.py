"""查詢側的卡名包含(action-search-coverage 票 05):只走接縫 `run_query`。

給條件的卡名包含先把打的字換成一組卡片編號:中文名、日文名、英文名、別名(中文卡文「※ 別名」)
任一個含這段字的卡;被動作的卡在這組裡就命中(滿足條件的卡與這條線的候選卡有交集)。
打的字先去頭尾空白,打的字與名字都做全形英數、全形空白當半形與小寫的折疊;以 `%` 切段、
去掉空段,各段依序出現在名字裡就算;沒有非空的段時等於沒給。

大皇帝ペンギン 的「デッキから「大皇帝ペンギン」以外の「ペンギン」モンスターを…特殊召喚する」:
候選卡是 ペンギン・ソルジャー,所以查得到它的名字就命中、查別張的名字不命中。
"""
import unittest

from action_query import run_query
from card_structure import build_structures
from test_golden import (ARCHETYPES, BLACK_MAGICIAN, EMPEROR_PENGUIN, EMPEROR_PENGUIN_TEXT,
                         PENGUIN_SOLDIER, card, faq)

BURNER = 20000051   # 測試用:傷害段沒有對象線,給了條件就不命中


def name_contains(text):
    return {"op": "卡名包含", "text": text}


class QueryNameContainsTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.cards = [
            card(EMPEROR_PENGUIN, name_zh="大皇帝企鵝", name_ja="大皇帝ペンギン",
                 name_en="Emperor Penguin", level=5, race=0x40, attribute=0x2, setcode=0x5a),
            card(PENGUIN_SOLDIER, name_zh="企鵝士兵", name_ja="ペンギン・ソルジャー",
                 name_en="Penguin Soldier", desc="①：這樣。\n\n※企鵝兵", level=2,
                 race=0x40, attribute=0x2, setcode=0x5a),
            card(BLACK_MAGICIAN, name_zh="黑魔導", name_ja="ブラック・マジシャン",
                 name_en="Dark Magician", level=7, race=0x2, attribute=0x20),
            card(BURNER, name_ja="焼く者"),
        ]
        cls.structures, _ = build_structures(
            cls.cards, [faq(EMPEROR_PENGUIN, "大皇帝ペンギン", EMPEROR_PENGUIN_TEXT),
                        faq(BURNER, "焼く者", "①：相手に１０００ダメージを与える。")],
            archetypes=ARCHETYPES)

    def hits(self, condition):
        result = run_query(self.structures, self.cards,
                           {"actions": ["特殊召喚"], "condition": condition})
        return EMPEROR_PENGUIN in result["groups"]["全部"]

    def query(self, condition, actions=("特殊召喚",)):
        return run_query(self.structures, self.cards,
                         {"actions": list(actions), "condition": condition})

    def test_chinese_name(self):
        self.assertTrue(self.hits(name_contains("企鵝士")))
        self.assertFalse(self.hits(name_contains("黑魔導")))

    def test_japanese_name(self):
        self.assertTrue(self.hits(name_contains("ソルジャー")))
        self.assertFalse(self.hits(name_contains("マジシャン")))

    def test_english_name_ignores_case(self):
        self.assertTrue(self.hits(name_contains("penguin sol")))
        self.assertTrue(self.hits(name_contains("PENGUIN SOLDIER")))
        self.assertFalse(self.hits(name_contains("Dark Magician")))

    def test_alias_from_the_chinese_text(self):
        self.assertTrue(self.hits(name_contains("企鵝兵")))

    def test_percent_parts_appear_in_order(self):
        self.assertTrue(self.hits(name_contains("企%兵")))
        self.assertTrue(self.hits(name_contains("%ペン%ソル%")))
        self.assertFalse(self.hits(name_contains("兵%企")))

    def test_full_width_letters_and_space_count_as_half_width(self):
        self.assertTrue(self.hits(name_contains("ＰＥＮＧＵＩＮ　ＳＯＬＤＩＥＲ")))
        self.assertTrue(self.hits(name_contains("企鵝％兵")))

    def test_surrounding_spaces_are_ignored(self):
        self.assertTrue(self.hits(name_contains("  企鵝士兵　")))

    def test_blank_or_only_percent_is_as_if_not_given(self):
        plain = run_query(self.structures, self.cards, {"actions": ["傷害"]})
        self.assertIn(BURNER, plain["groups"]["全部"])
        for text in ("", "   ", "　", "%", " %% ", "％"):
            with self.subTest(text=text):
                self.assertEqual(self.query(name_contains(text), ["傷害"]), plain)
                self.assertEqual(
                    self.query({"op": "且", "args": [name_contains(text)]}, ["傷害"]), plain)

    def test_blank_name_beside_other_atoms_is_dropped(self):
        spell = {"op": "大類", "value": "魔法"}
        self.assertFalse(self.hits({"op": "且", "args": [spell, name_contains("%")]}))
        monster = {"op": "大類", "value": "怪獸"}
        self.assertTrue(self.hits({"op": "且", "args": [monster, name_contains(" ")]}))


OMOI = 20000061      # 想い集いし竜:場上、墓地當作「救世竜 セイヴァー・ドラゴン」
SAVIOR = 20000062    # 救世竜 セイヴァー・ドラゴン:沒有卡文,只當被指到的卡
CITY = 20000063      # 伝説の都 アトランティス:ルール上當作「海」;卡片總表沒有「海」
TWINKLE = 20000064   # N・ティンクル・モス:場上當作「N・グロー・モス」(卡名是全形 Ｎ)
GLOW = 20000065      # Ｎ・グロー・モス
UMI = 20000066       # 海:只在 FAQ 有,卡片總表沒有
WARRIOR = 0x1


def treated_fixture():
    """當作的卡名(票 06):各卡都有「このカードを手札から特殊召喚する」,給條件時看這張卡自己。
    種族都是戰士族,不擾動兩邊答案一致測試裡「龍族」的斷言。→ (卡片總表, FAQ 條目)。"""
    summon = "①：このカードを手札から特殊召喚する。"
    cards = [
        card(OMOI, name_zh="思念聚集之龍", name_ja="想い集いし竜", level=1, race=WARRIOR),
        card(SAVIOR, name_zh="救世龍 救世龍", name_ja="救世竜 セイヴァー・ドラゴン",
             name_en="Majestic Dragon", level=1, race=WARRIOR),
        card(CITY, name_zh="傳說之都 亞特蘭提斯", name_ja="伝説の都 アトランティス", race=WARRIOR),
        card(TWINKLE, name_zh="新宇宙俠 閃爍苔", name_ja="N・ティンクル・モス", level=1,
             race=WARRIOR),
        card(GLOW, name_zh="新宇宙俠 光輝苔", name_ja="Ｎ・グロー・モス", level=1, race=WARRIOR),
    ]
    entries = [
        faq(OMOI, "想い集いし竜",
            "①：このカードのカード名は、フィールド・墓地に存在する限り"
            "「救世竜 セイヴァー・ドラゴン」として扱う。\n" + summon),
        faq(CITY, "伝説の都 アトランティス",
            "このカード名はルール上「海」として扱う。\n" + summon),
        faq(TWINKLE, "N・ティンクル・モス",
            "このカードのカード名は、フィールドに存在する限り「N・グロー・モス」として扱う。\n"
            + summon),
        faq(UMI, "海", ""),
    ]
    return cards, entries


class QueryTreatedNameTest(unittest.TestCase):
    """卡名包含也比「〜として扱う」當作的卡名:先換成它指的那張卡、用那張卡的四種名字比;
    對不到卡的比日文字面;不看位置條件(想い集いし竜 只在場上、墓地當作救世竜,從手牌特殊召喚也命中)。"""

    @classmethod
    def setUpClass(cls):
        cls.cards, entries = treated_fixture()
        cls.structures, _ = build_structures(cls.cards, entries, archetypes=[])

    def hits(self, text):
        result = run_query(self.structures, self.cards,
                           {"actions": ["特殊召喚"], "condition": name_contains(text)})
        return set(result["groups"]["全部"])

    def test_treated_name_in_japanese(self):
        self.assertEqual(self.hits("セイヴァー"), {OMOI})

    def test_treated_card_matches_by_its_chinese_and_english_names(self):
        self.assertEqual(self.hits("救世龍"), {OMOI})
        self.assertEqual(self.hits("majestic"), {OMOI})

    def test_treated_name_counts_outside_its_zones(self):
        """當作的卡名只在場上、墓地,特殊召喚的是手牌的這張卡:照樣命中。"""
        self.assertIn(OMOI, self.hits("救世%セイヴァー"))

    def test_treated_name_matches_a_card_after_folding_width(self):
        self.assertEqual(self.hits("光輝苔"), {TWINKLE})

    def test_treated_name_without_a_card_matches_its_japanese_text(self):
        self.assertEqual(self.hits("海"), {CITY})

    def test_own_names_still_match(self):
        self.assertEqual(self.hits("思念聚集"), {OMOI})
        self.assertEqual(self.hits("アトランティス"), {CITY})


if __name__ == "__main__":
    unittest.main()
