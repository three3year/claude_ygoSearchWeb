# -*- coding: utf-8 -*-
"""[[動作對象]]改讀[[論元片語]](named-queries 票 04)的回歸例子。

接縫同既有的動作對象測試(test_export.py):合成卡的標記句經組裝、框架抽取、類別樹,斷言匯出句列的
此卡/非此卡葉(effect_self/effect_nonself/cost_self/cost_nonself)。判定規則不變、只換讀取來源,
所以這些例子改讀前後都要過;每條例子挑的是改讀後從片語結構拿值的句型(段數量、取自子句的數量、
回指目標的數量、結構化區域、段的玩家/區域、中心詞字面尾的卡種、修飾語類、替代項段、指示詞旗標、
此卡四條字面規則改成比段)。機械規則(patient.py 沒有正則式、不呼叫區域辨識去解字面)在 test_lint.py。

執行:PYTHONIOENCODING=utf-8 python -m unittest discover -s .scratch/effect-tokenize -p "test_*.py"
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from test_export import DRAGON, SPELL, XYZ, clause, export, modes, wipe  # noqa: E402


def assert_mode(case, found, mode, group="effect"):
    """found 是 modes() 的結果;mode 是 self/nonself/neither。"""
    other = {"self": "nonself", "nonself": "self"}.get(mode)
    if mode == "neither":
        case.assertNotIn(group + "_self", found)
        case.assertNotIn(group + "_nonself", found)
        return
    case.assertTrue(found.get(group + "_" + mode), found)
    case.assertNotIn(group + "_" + other, found)


class TestSelectionReadsQuantity(unittest.TestCase):
    """選擇類 ← 受事者片語任一段的數量(段尾、取自子句、受事者之前的引用量)或回指目標的數量。"""

    def test_quantity_on_the_segment(self):
        assert_mode(self, modes("①：自分の墓地からモンスター１体を特殊召喚する。"), "nonself")

    def test_quantity_taken_from_the_clause(self):
        assert_mode(self, modes("①：手札を１枚捨てて発動できる。自分はデッキから１枚ドローする。"),
                    "nonself", group="cost")

    def test_quantity_on_the_backfilled_object(self):
        """１枚選んで破壊する:破壊 的對象是回填來的,數量在 選ぶ 的子句裡。"""
        assert_mode(self, modes("①：自分フィールドのモンスターを１体選んで破壊する。"), "nonself")

    def test_quantity_on_the_second_listed_segment(self):
        """このカードと…１体:並列含此卡優先;カードとモンスター１体:第二段帶數量也是選擇類。"""
        assert_mode(self, modes("①：自分の墓地からカードとモンスター１体を手札に加える。"), "nonself")

    def test_quantity_inside_the_attribute_owner(self):
        """モンスター１体の攻撃力:屬性跟主人走,主人帶數量。"""
        assert_mode(self, modes("①：フィールドのモンスター１体の攻撃力は０になる。"), "nonself")

    def test_reference_quantity_on_the_target(self):
        assert_mode(self, modes("①：フィールドのカード２枚を対象として発動できる。そのカードを破壊する。"),
                    "nonself")

    def test_one_of_them_is_a_selection(self):
        """その内の１枚:目標沒有數量,指示詞自己挑一張。"""
        assert_mode(self, modes("①：相手の手札を確認し、その内の１枚を選んで墓地へ送る。"), "nonself")

    def test_all_of_them_is_not_a_selection(self):
        assert_mode(self, modes("①：自分の墓地のカードを全て除外する。"), "nonself")


class TestAllClassReadsStructure(unittest.TestCase):
    """全部類:區域 ← 結構化所在/來源與段的玩家/區域;卡種 ← 中心詞字面尾;種族/屬性/字段/子類型/數值 ←
    修飾語類;其他類修飾語比不了;替代項逐段比。合成的此卡是等級 7 暗屬性龍族效果怪獸。"""

    def test_zone_from_the_structured_place(self):
        """發動位置是場上:自分フィールド 的群體含此卡(皆非);墓地 的群體不含。"""
        assert_mode(self, modes("①：自分フィールドのモンスターを全て破壊する。"), "neither")
        assert_mode(self, modes("①：自分の墓地のモンスターを全て除外する。"), "nonself")

    def test_zone_from_the_segment_when_the_frame_has_none(self):
        """手札を全て捨てる:受事者本身是區域;此卡在場上,不含。"""
        assert_mode(self, modes("①：手札を全て捨てる。"), "nonself")

    def test_player_from_the_segment(self):
        assert_mode(self, modes("①：相手フィールドのモンスターを全て破壊する。"), "nonself")

    def test_launch_position_from_the_structured_cost_source(self):
        assert_mode(self, modes("①：墓地のこのカードを除外して発動できる。自分の墓地のモンスターを全て"
                                "手札に戻す。"), "nonself")

    def test_card_kind_from_the_head_tail(self):
        self.assertTrue(wipe("魔法・罠カード"))
        self.assertFalse(wipe("モンスター・魔法・罠カード"))
        self.assertTrue(wipe("モンスター", face=SPELL))

    def test_subtype_inside_the_head_word(self):
        """効果モンスター、速攻魔法カード 是詞典一格:子類型在中心詞字面裡。"""
        self.assertFalse(wipe("効果モンスター"))
        self.assertTrue(wipe("通常モンスター"))
        self.assertTrue(wipe("速攻魔法カード", face=SPELL))
        self.assertFalse(wipe("通常魔法カード", face=SPELL))

    def test_subtype_from_the_modifiers(self):
        self.assertTrue(wipe("融合・S・Xモンスター"))
        self.assertFalse(wipe("融合・S・Xモンスター", face=XYZ))

    def test_race_attribute_archetype_from_the_modifiers(self):
        self.assertTrue(wipe("闇属性の戦士族モンスター"))
        self.assertFalse(wipe("光・闇属性のドラゴン族モンスター"))
        self.assertTrue(wipe("「サイバー」ドラゴン族モンスター"))

    def test_numeric_from_the_modifier(self):
        self.assertTrue(wipe("レベル４以下のモンスター"))
        self.assertFalse(wipe("レベル７以上のモンスター"))
        self.assertTrue(wipe("攻撃力１０００以下のモンスター"))

    def test_other_modifiers_cannot_be_compared(self):
        self.assertFalse(wipe("表側表示モンスター"))
        self.assertFalse(wipe("特殊召喚されたモンスター"))
        self.assertFalse(wipe("このカードと同じ種族のモンスター"))

    def test_alternatives_are_segments(self):
        self.assertFalse(wipe("「サイバー」モンスターかドラゴン族モンスター"))
        self.assertTrue(wipe("戦士族モンスターまたは光属性モンスター"))

    def test_uncomparable_literal_is_reported(self):
        doc, _ = export({1: [clause("①", "①：自分フィールドの表側表示モンスターを全て破壊する。")]},
                        {1: __import__("export_common").card_face(DRAGON)})
        self.assertEqual(doc["統計"]["比不了字面"], {"表側表示モンスター": 1})


class TestDemonstrativeReadsTheFlag(unittest.TestCase):
    """指示詞 ← 段的指示詞旗標;旗標假而段首是指示詞的,指示詞只修飾另一張卡。"""

    def test_demonstrative_follows_the_target(self):
        assert_mode(self, modes("①：相手がモンスターを特殊召喚した時に発動できる。そのモンスターを破壊する。"),
                    "nonself")

    def test_demonstrative_bound_in_a_relative_clause_is_a_modifier(self):
        assert_mode(self, modes("①：フィールドのモンスター１体を対象として発動できる。"
                                "そのモンスターと同じ種族のモンスターを全て破壊する。"), "neither")
        assert_mode(self, modes("①：自分フィールドのXモンスター１体を対象として発動できる。そのモンスターより"
                                "ランクが２つ高いXモンスター１体を特殊召喚する。"), "nonself")

    def test_sono_hoka_is_other_than_this_card(self):
        """その他の:修飾語 その他 就是群體前的「他の」,不是回指。"""
        assert_mode(self, modes("①：フィールドのモンスター１体を対象として発動できる。"
                                "その他のモンスターを全て破壊する。"), "nonself")

    def test_demonstrative_on_an_attribute_follows_the_owner(self):
        assert_mode(self, modes("①：フィールドのモンスター１体を対象として発動できる。"
                                "そのモンスターの攻撃力は０になる。"), "nonself")

    def test_blank_reference_is_nonself(self):
        assert_mode(self, modes("①：そのモンスターを破壊する。"), "nonself")


class TestThisCardRulesCompareSegments(unittest.TestCase):
    """此卡/此卡以外/此卡的附屬卡/この効果:字面規則改成比段。"""

    def test_last_segment_is_this_card(self):
        assert_mode(self, modes("①：墓地のこのカードを特殊召喚する。"), "self")
        assert_mode(self, modes("①：相手のモンスター１体を対象として発動できる。そのカードとこのカードを"
                                "破壊する。"), "self")

    def test_attribute_of_this_card_with_original_and_a_list(self):
        assert_mode(self, modes("①：このカードの元々の攻撃力は５００アップする。"), "self")
        assert_mode(self, modes("①：このカードの攻撃力・守備力は５００アップする。"), "self")

    def test_attribute_of_another_card_of_this_card_is_not_self(self):
        assert_mode(self, modes("①：このカードの装備モンスターの攻撃力は５００アップする。"), "nonself")

    def test_listed_with_this_card_is_a_segment_ending_in_this_card(self):
        assert_mode(self, modes("①：このカードと植物族モンスター１体を手札から特殊召喚する。"), "self")
        assert_mode(self, modes("①：このカードと戦闘を行うモンスターを破壊する。"), "neither")

    def test_including_this_card_is_a_modifier(self):
        assert_mode(self, modes("①：このカードを含む自分フィールドのモンスター２体をリリースして発動できる。"
                                "自分はデッキから１枚ドローする。"), "self", group="cost")

    def test_this_effect_and_its_activation(self):
        assert_mode(self, modes("①：この効果の発動は無効化されない。"), "self")
        assert_mode(self, modes("①：この発動とこの効果は無効化されない。"), "self")

    def test_other_than_this_card_is_a_modifier(self):
        assert_mode(self, modes("①：このカード以外の自分フィールドのモンスターを全て破壊する。"), "nonself")
        assert_mode(self, modes("①：フィールドの他のカードを全て破壊する。"), "nonself")

    def test_attached_to_this_card(self):
        assert_mode(self, modes("①：このカードのリンク先のモンスターを破壊する。"), "nonself")
        assert_mode(self, modes("①：このカードのX素材を１つ取り除いて発動できる。自分はデッキから１枚"
                                "ドローする。"), "nonself", group="cost")


if __name__ == "__main__":
    unittest.main()
