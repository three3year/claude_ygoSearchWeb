"""候選卡:卡片總表裡代得進一條對象線的物件的卡;加速前後每張都要相同。

接縫:`CandidateCards(cards, structures).of_line(owner, line)` → 卡片總表條目(照總表順序)。
輸入官方卡文、卡片參數(或直接給物件條件式),看回來的是哪幾張卡。
"""
import unittest

from candidate_cards import CandidateCards
from card_structure import build_structures
from structure_shape import iter_segments
from test_golden import card
from test_names_archetypes import (BLACK_MAGICIAN, DOOM_MAGICIAN, LISETTE_SAINT, Q_AZAMINA,
                                   Q_BM_FROM_DECK, Q_BM_FROM_GRAVE, fixtures)
from test_names_archetypes import ARCHETYPES as NAME_ARCHETYPES


def object_lines(owner):
    """這張卡每條帶物件、物件不是此卡的對象線。"""
    objects = {obj["id"]: obj for obj in owner["objects"]}
    for block in owner["blocks"]:
        for _, seg in iter_segments(block):
            for line in seg["lines"]:
                obj = objects.get(line["object"])
                if obj is not None and obj["source"]["kind"] != "自己":
                    yield line


class CardTextCandidatesTest(unittest.TestCase):
    """卡文抽出來的物件:字段、卡名、卡名的位置條件。"""

    @classmethod
    def setUpClass(cls):
        cls.cards, entries = fixtures()
        cls.structures, _ = build_structures(cls.cards, entries, archetypes=NAME_ARCHETYPES)
        cls.by_id = {s["id"]: s for s in cls.structures}
        cls.candidates = CandidateCards(cls.cards, cls.structures)

    def ids_on_first_line(self, owner_id):
        owner = self.by_id[owner_id]
        line = next(object_lines(owner))
        return [entry["id"] for entry in self.candidates.of_line(owner, line)]

    def test_archetype_monster_from_deck(self):
        """「アザミナ」モンスター:setcode 帶アザミナ的只有 白き森の聖徒リゼット。"""
        self.assertEqual(self.ids_on_first_line(Q_AZAMINA), [LISETTE_SAINT])

    def test_name_held_only_in_some_zones_follows_the_line_from(self):
        """滅びの黒魔術師 只在場上、墓地當「ブラック・マジシャン」:從牌組的線只有本尊,
        從墓地的線兩張都是(同一個物件,線不同候選卡就不同)。"""
        self.assertEqual(self.ids_on_first_line(Q_BM_FROM_DECK), [BLACK_MAGICIAN])
        self.assertEqual(self.ids_on_first_line(Q_BM_FROM_GRAVE), [BLACK_MAGICIAN, DOOM_MAGICIAN])

    def test_same_object_on_lines_from_different_zones(self):
        """同一張卡同一個物件,一條線從牌組、一條從墓地(條件式、名稱表完全相同)。"""
        obj = {"id": "o1", "source": {"kind": "新建"}, "kind": "卡", "count": None,
               "unparsed": None, "condition": {"op": "卡名", "name": "n1"}}
        owner = {"id": 1, "unparsed": None, "objects": [obj],
                 "names": [{"id": "n1", "text": "ブラック・マジシャン", "unparsed": None}]}

        def ids(zone):
            line = {"object": "o1", "from": {"zones": [{"zone": zone, "side": "我方"}]}}
            return [entry["id"] for entry in self.candidates.of_line(owner, line)]
        self.assertEqual(ids("牌組"), [BLACK_MAGICIAN])
        self.assertEqual(ids("墓地"), [BLACK_MAGICIAN, DOOM_MAGICIAN])
        self.assertEqual(ids("場上"), [BLACK_MAGICIAN, DOOM_MAGICIAN])
        self.assertEqual(ids("手牌"), [BLACK_MAGICIAN])


SPELL, QUICK_SPELL, TRAP = 0x2, 0x10002, 0x4
XYZ, LINK, FUSION = 0x800021, 0x4000021, 0x61
DRAGON, SPELLCASTER = 0x2000, 0x2
LIGHT, DARK = 0x10, 0x20

OWNER = 900          # 物件所屬的卡,本身也在總表裡
BLUE_EYES = 901      # 光 ドラゴン族 8 星 3000
DARK_MAGICIAN = 902  # 闇 魔法使い族 7 星 2500
MAGICIAN_GIRL = 903  # 闇 魔法使い族 6 星 2000,字段 0x10a2(帶子系列旗標)
APPRENTICE = 904     # 闇 魔法使い族 2 星 攻擊力「？」,字段 0xa2(沒有子系列旗標)
RANK4 = 905          # 超量 階級 4 光 ドラゴン族
LINK2 = 906          # 連結 2 闇 ドラゴン族
FUSION8 = 907        # 融合 8 星 光 ドラゴン族
QUICK = 908          # 速攻魔法
POT = 909            # 通常魔法
JAR = 910            # 通常陷阱


def table():
    return [
        card(OWNER, name_ja="持ち主", level=4, race=SPELLCASTER, attribute=LIGHT),
        card(BLUE_EYES, name_ja="青眼の白龍", level=8, race=DRAGON, attribute=LIGHT, atk=3000),
        card(DARK_MAGICIAN, name_ja="ブラック・マジシャン", level=7, race=SPELLCASTER,
             attribute=DARK, atk=2500),
        card(MAGICIAN_GIRL, name_ja="ブラック・マジシャン・ガール", level=6,
             race=SPELLCASTER, attribute=DARK, atk=2000, setcode=0x10a2),
        card(APPRENTICE, name_ja="見習い魔術師", level=2, race=SPELLCASTER, attribute=DARK,
             atk=-2, setcode=0xa2),
        card(RANK4, name_ja="ランク４", type=XYZ, level=4, race=DRAGON, attribute=LIGHT),
        card(LINK2, name_ja="リンク２", type=LINK, level=2, race=DRAGON, attribute=DARK,
             **{"def": None}),
        card(FUSION8, name_ja="融合８", type=FUSION, level=8, race=DRAGON, attribute=LIGHT),
        card(QUICK, name_ja="速攻の魔法", type=QUICK_SPELL),
        card(POT, name_ja="強欲な壺", type=SPELL),
        card(JAR, name_ja="落とし穴", type=TRAP),
    ]


def attr(name, cmp, value):
    return {"op": "屬性比較", "attr": name, "cmp": cmp, "value": value}


def name(text, op="卡名"):
    return {"op": op, "text": text}


def both(*args):
    return {"op": "且", "args": list(args)}


def either(*args):
    return {"op": "或", "args": list(args)}


MONSTER = {"op": "大類", "value": "怪獸"}


class ConditionCandidatesTest(unittest.TestCase):
    """直接給物件條件式:每種原子、且或非、引用、此卡,回來的卡照總表順序。"""

    def candidates_of(self, condition, source=None, unparsed=None, extra=(), zones=None):
        obj = {"id": "o1", "source": source or {"kind": "新建"}, "kind": "卡",
               "condition": condition, "count": None, "unparsed": unparsed}
        this = {"id": "o0", "source": {"kind": "自己"}, "kind": "卡", "condition": None,
                "count": None, "unparsed": None}
        owner = {"id": OWNER, "unparsed": None, "names": [],
                 "objects": [this, obj, *extra]}
        line = {"object": "o1", "from": {"zones": zones} if zones else None}
        found = CandidateCards(table(), []).of_line(owner, line)
        return [entry["id"] for entry in found]

    def test_level_counts_only_monsters_that_have_levels(self):
        """等級 ≥ 7:超量、連結沒有等級;魔陷沒有。"""
        self.assertEqual(self.candidates_of(attr("等級", "≥", 7)),
                         [BLUE_EYES, DARK_MAGICIAN, FUSION8])

    def test_rank_and_link_rating(self):
        self.assertEqual(self.candidates_of(attr("階級", "=", 4)), [RANK4])
        self.assertEqual(self.candidates_of(attr("連結值", "≤", 2)), [LINK2])

    def test_race_and_attribute_words(self):
        self.assertEqual(self.candidates_of(both(attr("種族", "=", "ドラゴン族"),
                                                 attr("屬性", "=", "光"))),
                         [BLUE_EYES, RANK4, FUSION8])
        self.assertEqual(self.candidates_of(attr("種族", "=", "未知族")), [])

    def test_unknown_attack_never_compares(self):
        """攻擊力「？」(負數)比不了:≤ 2000 不收 見習い魔術師。"""
        self.assertEqual(self.candidates_of(attr("攻擊力", "≤", 2000)),
                         [OWNER, MAGICIAN_GIRL, RANK4, LINK2, FUSION8])

    def test_subtypes_of_monsters_and_spells(self):
        self.assertEqual(self.candidates_of(attr("卡片子類型", "=", "融合")), [FUSION8])
        self.assertEqual(self.candidates_of(attr("卡片子類型", "=", "速攻")), [QUICK])
        self.assertEqual(self.candidates_of(both({"op": "大類", "value": "魔法"},
                                                 attr("卡片子類型", "≠", "速攻"))), [POT])

    def test_archetype_respects_sub_archetype_flag(self):
        """要 0x10a2:只有帶旗標的;要 0xa2:兩張都算。"""
        self.assertEqual(self.candidates_of({"op": "字段", "setcodes": [0x10a2]}),
                         [MAGICIAN_GIRL])
        self.assertEqual(self.candidates_of({"op": "字段", "setcodes": [0xa2]}),
                         [MAGICIAN_GIRL, APPRENTICE])

    def test_names(self):
        self.assertEqual(self.candidates_of(name("ブラック・マジシャン")), [DARK_MAGICIAN])
        self.assertEqual(self.candidates_of(name("ブラック・マジシャン", "卡名包含")),
                         [DARK_MAGICIAN, MAGICIAN_GIRL])
        self.assertEqual(self.candidates_of(name("ＢＬＵＥ")), [])

    def test_or_and_not(self):
        self.assertEqual(self.candidates_of(either(name("強欲な壺"), name("落とし穴"))),
                         [POT, JAR])
        self.assertEqual(
            self.candidates_of(both(MONSTER, attr("種族", "=", "魔法使い族"),
                                    {"op": "非", "arg": name("ブラック・マジシャン")})),
            [OWNER, MAGICIAN_GIRL, APPRENTICE])

    def test_category_and_any_card(self):
        self.assertEqual(self.candidates_of({"op": "大類", "value": "陷阱"}), [JAR])
        self.assertEqual(len(self.candidates_of({"op": "大類", "value": "卡"})), len(table()))
        self.assertEqual(len(self.candidates_of(None)), len(table()))

    def test_not_this_card_and_state_atoms(self):
        """「同一張」永遠不符,「此卡以外」永遠符合;位置是狀態,任何卡都代得進去。"""
        self.assertEqual(self.candidates_of({"op": "同一張"}), [])
        self.assertEqual(
            self.candidates_of(both({"op": "非", "arg": {"op": "同一張"}},
                                    {"op": "大類", "value": "陷阱"})), [JAR])
        self.assertEqual(self.candidates_of(both({"op": "位置", "zones": []},
                                                 {"op": "大類", "value": "魔法"})),
                         [QUICK, POT])

    def test_reference_to_another_object(self):
        """等級 = 物件2.階級,物件2 是超量怪獸:只有 4 星的卡。"""
        xyz = {"id": "o2", "source": {"kind": "新建"}, "kind": "卡",
               "condition": attr("卡片子類型", "=", "超量"), "count": None, "unparsed": None}
        level_is_rank = {"op": "屬性比較", "attr": "等級", "cmp": "=",
                         "ref": {"object": "o2", "attr": "階級"}}
        self.assertEqual(self.candidates_of(level_is_rank, extra=[xyz]), [OWNER])

    def test_reference_alongside_plain_conditions(self):
        """魔法使い族 且 等級 ≥ 物件2.階級(物件2 是超量怪獸,階級 4):4 星以上的魔法使い族。"""
        xyz = {"id": "o2", "source": {"kind": "新建"}, "kind": "卡",
               "condition": attr("卡片子類型", "=", "超量"), "count": None, "unparsed": None}
        level_at_least_rank = {"op": "屬性比較", "attr": "等級", "cmp": "≥",
                               "ref": {"object": "o2", "attr": "階級"}}
        self.assertEqual(
            self.candidates_of(both(MONSTER, attr("種族", "=", "魔法使い族"), level_at_least_rank),
                               extra=[xyz]),
            [OWNER, DARK_MAGICIAN, MAGICIAN_GIRL])

    def test_same_and_different_from_another_object(self):
        """與物件2 同種族、不同名:物件2 是魔法使い族時四張魔法使い族都找得到同族異名的;
        物件2 只有 ブラック・マジシャン 時,它自己就不算了。"""
        def other(condition):
            return {"id": "o2", "source": {"kind": "新建"}, "kind": "卡",
                    "condition": condition, "count": None, "unparsed": None}
        same_race_other_name = both(
            MONSTER,
            {"op": "異同", "cmp": "=", "attrs": ["種族"], "ref": {"object": "o2"}},
            {"op": "異同", "cmp": "≠", "attrs": ["卡名"], "ref": {"object": "o2"}})
        self.assertEqual(
            self.candidates_of(same_race_other_name,
                               extra=[other(attr("種族", "=", "魔法使い族"))]),
            [OWNER, DARK_MAGICIAN, MAGICIAN_GIRL, APPRENTICE])
        self.assertEqual(
            self.candidates_of(same_race_other_name, extra=[other(name("ブラック・マジシャン"))]),
            [OWNER, MAGICIAN_GIRL, APPRENTICE])

    def test_same_in_every_listed_attribute(self):
        """與物件2(光 ドラゴン族 的 青眼 或 闇 ドラゴン族 的 リンク２)種族、屬性都相同的怪獸。"""
        either_dragon = {"id": "o2", "source": {"kind": "新建"}, "kind": "卡",
                         "condition": either(name("青眼の白龍"), name("リンク２")),
                         "count": None, "unparsed": None}
        same_race_and_attribute = both(
            MONSTER, {"op": "異同", "cmp": "=", "attrs": ["種族", "屬性"], "ref": {"object": "o2"}})
        self.assertEqual(self.candidates_of(same_race_and_attribute, extra=[either_dragon]),
                         [BLUE_EYES, RANK4, LINK2, FUSION8])

    def test_this_card_with_state(self):
        """帶狀態的此卡(母體是物件0 的子集):只有這張卡自己。"""
        self.assertEqual(self.candidates_of({"op": "位置", "zones": []},
                                            source={"kind": "子集", "of": "o0"}), [OWNER])

    def test_unparsed_object_has_no_candidates(self):
        self.assertEqual(self.candidates_of(MONSTER, unparsed={"reason": "x"}), [])

    def test_unknown_atom_never_fits(self):
        self.assertEqual(self.candidates_of(either({"op": "沒見過"}, name("落とし穴"))), [JAR])
        self.assertEqual(self.candidates_of(both({"op": "沒見過"}, MONSTER)), [])

    def test_not_an_unresolved_name_never_fits(self):
        """名稱解析不出判不了,包了「非」還是判不了;「非 字段(沒列 setcode)」也一樣。"""
        self.assertEqual(self.candidates_of({"op": "非", "arg": {"op": "卡名", "name": "n9"}}), [])
        self.assertEqual(self.candidates_of({"op": "非", "arg": {"op": "字段", "setcodes": []}}), [])
        self.assertEqual(self.candidates_of({"op": "非", "arg": {"op": "字段", "setcodes": [0xa2]}}),
                         [OWNER, BLUE_EYES, DARK_MAGICIAN, RANK4, LINK2, FUSION8, QUICK, POT, JAR])


class SharedAcrossCardsTest(unittest.TestCase):
    """同一份 CandidateCards 依序算很多張卡:條件式長得一樣、意思不同的物件,答案各自正確。
    (卡號在全庫裡唯一,每個測試用不同卡號。)"""

    @classmethod
    def setUpClass(cls):
        cls.candidates = CandidateCards(table(), [])

    def ids(self, owner_id, condition, names=(), extra=()):
        obj = {"id": "o1", "source": {"kind": "新建"}, "kind": "卡", "condition": condition,
               "count": None, "unparsed": None}
        owner = {"id": owner_id, "unparsed": None, "names": list(names),
                 "objects": [obj, *extra]}
        found = self.candidates.of_line(owner, {"object": "o1", "from": None})
        return [entry["id"] for entry in found]

    def test_same_name_id_in_two_cards_reads_each_cards_name_table(self):
        """兩張卡都寫 {"op": "卡名", "name": "n1"},n1 在各自的名稱表是不同的卡名。"""
        by_name = {"op": "卡名", "name": "n1"}
        self.assertEqual(self.ids(1, by_name, [{"id": "n1", "text": "強欲な壺",
                                                 "unparsed": None}]), [POT])
        self.assertEqual(self.ids(2, by_name, [{"id": "n1", "text": "落とし穴",
                                                 "unparsed": None}]), [JAR])

    def test_same_reference_in_two_cards_reads_each_cards_object(self):
        """兩張卡都寫 等級 = o2.階級,o2 在一張是超量怪獸、另一張是連結怪獸(沒有階級)。"""
        level_is_rank = {"op": "屬性比較", "attr": "等級", "cmp": "=",
                         "ref": {"object": "o2", "attr": "階級"}}

        def other(kind):
            return {"id": "o2", "source": {"kind": "新建"}, "kind": "卡",
                    "condition": attr("卡片子類型", "=", kind), "count": None, "unparsed": None}
        self.assertEqual(self.ids(3, level_is_rank, extra=[other("超量")]), [OWNER])
        self.assertEqual(self.ids(4, level_is_rank, extra=[other("連結")]), [])


if __name__ == "__main__":
    unittest.main()
