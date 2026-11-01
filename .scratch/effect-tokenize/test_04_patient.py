# -*- coding: utf-8 -*-
"""[[動作對象]]的回歸例子(action-patient 票 01〜05、anaphora 票 05/06、named-queries 票 04 改讀[[論元片語]])。

接縫:合成卡的標記句經組裝、框架抽取進框列匯出(export_frames),斷言框列的 patient_mode 與匯出的「統計」。modes 把一句
收成 {位置_值: [動作詞元…]}(效果位、代價位的此卡/非此卡,空的省略),patient_modes 帶條件位。判定規則的例子原掛在舊匯出的
句列上(test_export.py,規格 4 票 08 與舊匯出一起刪,例子搬來這裡、斷言從葉名換成動作詞元)。機械規則(patient.py 沒有
正則式、不呼叫區域辨識去解字面)在 test_lint.py。

執行:PYTHONIOENCODING=utf-8 python -m unittest discover -s .scratch/effect-tokenize -p "test_*.py"
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import export_common  # noqa: E402
import export_frames  # noqa: E402
import patient  # noqa: E402
from constraints import POS_COST, POS_EFFECT  # noqa: E402
from test_05_export_frames import DRAGON, REVIVE, clause, export  # noqa: E402
from test_05_export_frames import rows as frame_rows  # noqa: E402

SPELL = {"id": 1, "type": 0x2, "race": 0, "attribute": 0, "level": 0,
         "atk": None, "def": None, "name_ja": "テスト・魔法"}
XYZ = {"id": 1, "type": 0x800021, "race": 0x1, "attribute": 0x10, "level": 4,
       "atk": 2000, "def": 1000, "name_ja": "テスト・エクシーズ"}
UNKNOWN_ATK = dict(DRAGON, atk=-2, **{"def": -2})
TRAP = {"id": 1, "type": 0x4, "race": 0, "attribute": 0, "level": 0,
        "atk": None, "def": None, "name_ja": "テスト・罠"}


GROUP_OF = {POS_EFFECT: "effect", POS_COST: "cost"}
MODE_OF = {patient.SELF: "self", patient.NONSELF: "nonself"}


def modes(text, card=1, kind="啟動效果", face=DRAGON, section="main"):
    """一句效果句 → {效果位此卡、效果位非此卡、代價位此卡、代價位非此卡: [動作詞元…]}(依原文順序、同一詞元只記一次;
    空的省略;條件位的判定看 patient_modes);斷言匯出沒有問題。"""
    faces = {card: export_common.card_face(dict(face, id=card))}
    found = {}
    for row in frame_rows({card: [clause("①", text, kind=kind, section=section)]}, faces)[(card, section, "①")]:
        if row["position"] in GROUP_OF and row.get("patient_mode") in MODE_OF:
            actions = found.setdefault(GROUP_OF[row["position"]] + "_" + MODE_OF[row["patient_mode"]], [])
            if row["action"] not in actions:
                actions.append(row["action"])
    return found


def wipe(group, face=DRAGON):
    """「自分フィールドの〈群體〉を全て破壊する」:會不會判成非此卡。"""
    return "effect_nonself" in modes("①：自分フィールドの%sを全て破壊する。" % group, face=face)


def patient_modes(text, face=DRAGON):
    """一句效果句 → 每個動作框架的 (動作, 位置, 動作對象);接縫是框列匯出(export_frames)的 patient_mode,
    三個位置都帶,皆非是 None(鍵不帶)。條件位的判定只有這個接縫看得到。"""
    faces = {1: export_common.card_face(dict(face, id=1))}
    found = frame_rows({1: [clause("①", text)]}, faces)[(1, "main", "①")]
    return [(r["action"], r["position"], r.get("patient_mode")) for r in found]


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
                        {1: export_common.card_face(DRAGON)})
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


class TestDecisions20261101(unittest.TestCase):
    """2026-11-01 站主裁定(summary.md「需要你決定的」具名查詢目錄三題,全採 (a)):態空且對象空時看主語再主題、
    判法同自動態;全部類任一個比得了的條件(玩家、卡種…)對不上就 非此卡,區域不明只在其餘都對得上時才停在 皆非;
    以下の効果 是此卡自己接著列的子效果,算此卡。"""

    def test_empty_voice_without_object_reads_the_subject(self):
        """このカードが特殊召喚した場合:述語沒判態、對象空,主語是此卡 → 此卡(原本 皆非:沒有受事者)。"""
        self.assertIn(("特殊召喚", "條件", "此卡"),
                      patient_modes("①：このカードが特殊召喚した場合に発動できる。自分はデッキから１枚ドローする。"))

    def test_empty_voice_subject_of_another_card_is_judged_by_its_segments(self):
        """主語是別張卡時依主語的片語判:帶數量是選擇類 → 非此卡。"""
        self.assertIn(("存在", "條件", "非此卡"),
                      patient_modes("①：自分の墓地にモンスターが３体以上存在する場合に発動できる。"
                                    "自分はデッキから１枚ドローする。"))

    def test_empty_voice_without_subject_falls_back_to_the_topic(self):
        self.assertIn(("直接攻撃", "效果", "此卡"), patient_modes("①：このカードは直接攻撃できる。"))

    def test_all_class_player_is_compared_even_without_a_zone(self):
        """相手モンスターを破壊した:群體沒有區域,但玩家是相手、此卡在我方 → 非此卡(原本 皆非:全部類區域不明)。"""
        self.assertIn(("破壊", "條件", "非此卡"),
                      patient_modes("①：このカードの攻撃で相手モンスターを破壊した時に発動できる。"
                                    "自分はデッキから１枚ドローする。"))

    def test_all_class_player_from_the_goal_of_a_summon(self):
        """相手フィールドにモンスターが特殊召喚された:被召喚到相手場上的怪獸是相手的 → 非此卡。"""
        self.assertIn(("特殊召喚", "條件", "非此卡"),
                      patient_modes("①：相手フィールドにモンスターが特殊召喚された場合に発動できる。"
                                    "自分はデッキから１枚ドローする。"))

    def test_all_class_card_kind_blocks_before_the_zone_is_asked(self):
        """此卡是陷阱卡,群體是 モンスター:卡種對不上 → 非此卡,不停在區域不明。"""
        self.assertIn(("除外", "效果", "非此卡"),
                      patient_modes("①：この効果で特殊召喚したモンスターはエンドフェイズに除外される。", face=TRAP))

    def test_following_effects_belong_to_this_card(self):
        """このカードは以下の効果を得る/以下の効果を適用する:以下の効果 是此卡自己的 ● 子效果 → 此卡
        (原本 非此卡:主人不是此卡的效果)。"""
        self.assertIn(("得る", "效果", "此卡"), patient_modes("①：このカードは以下の効果を得る。"))
        self.assertIn(("適用", "效果", "此卡"), patient_modes("①：その後、以下の効果を適用できる。"))


class TestPatientSelf(unittest.TestCase):
    """[[動作對象]]「此卡」(action-patient 票 01):受事者以 このカード 收尾,與主題規則。"""

    def test_this_card_special_summoned_from_hand_is_self(self):
        self.assertEqual(modes("①：自分メインフェイズに発動できる。このカードを手札から"
                               "特殊召喚する。"),
                         {"effect_self": ["特殊召喚"]})

    def test_this_card_written_as_topic_is_self(self):
        """「このカードは手札から特殊召喚できる」:對象空著、主題是此卡。"""
        self.assertEqual(modes("①：このカードは手札から特殊召喚できる。"),
                         {"effect_self": ["特殊召喚"]})

    def test_topic_carried_over_within_the_sentence_is_self(self):
        """主題延續給後面沒有自己主題的子句。"""
        self.assertEqual(
            modes("①：このカードは相手フィールドにモンスターが存在する場合、"
                  "手札から特殊召喚できる。"),
            {"effect_self": ["特殊召喚"]})

    def test_this_card_with_a_modifier_is_self(self):
        """帶定語、切掉區域的此卡(墓地のこのカード)。"""
        self.assertEqual(modes("①：墓地のこのカードを除外して発動できる。自分フィールドの"
                               "カード１枚を破壊する。"),
                         {"cost_self": ["除外"], "effect_nonself": ["破壊"]})

    def test_releasing_this_card_then_summoning_another_is_not_self_summon(self):
        """代價解放此卡、處理從手牌特召另一隻:特召不是此卡,代價的解放才是。"""
        found = modes("①：このカードをリリースして発動できる。手札からモンスター１体を"
                      "特殊召喚する。")
        self.assertEqual(found.get("cost_self"), ["リリース"])
        self.assertNotIn("effect_self", found)

    # ── 票 02:此卡字面規則 ──

    def test_attribute_of_this_card_is_self(self):
        self.assertEqual(modes("①：このカードの攻撃力は５００アップする。"),
                         {"effect_self": ["アップ"]})
        self.assertEqual(modes("①：このカードのレベルを１つ上げる。"),
                         {"effect_self": ["アップ"]})

    def test_attribute_of_this_card_with_a_modifier_is_self(self):
        self.assertEqual(modes("①：この効果で特殊召喚したこのカードの攻撃力は倍になる。"),
                         {"effect_self": ["倍にする"]})

    def test_effect_owned_by_this_card_is_self(self):
        self.assertEqual(modes("①：このカードの効果を無効にする。"),
                         {"effect_self": ["無効にする"]})

    def test_this_card_listed_with_another_card_is_self(self):
        self.assertEqual(modes("①：このカードと植物族モンスター１体を手札から特殊召喚する。"),
                         {"effect_self": ["特殊召喚"]})

    def test_group_including_this_card_is_self(self):
        self.assertEqual(modes("①：このカードを含む自分フィールドのモンスター２体をリリースして"
                               "発動できる。自分はデッキから１枚ドローする。"),
                         {"cost_self": ["リリース"]})

    def test_this_card_treated_as_something_is_self(self):
        self.assertEqual(modes("①：このカードはフィールド上に存在する限り、闇属性として扱う。")
                         .get("effect_self"), ["扱う"])

    def test_equipped_monster_and_xyz_material_of_this_card_are_not_self(self):
        self.assertNotIn("effect_self",
                         modes("①：このカードの装備モンスターの攻撃力は５００アップする。"))
        self.assertNotIn("cost_self", modes("①：このカードのX素材を１つ取り除いて発動できる。"
                                            "自分はデッキから１枚ドローする。"))

    def test_this_card_name_and_other_than_this_card_are_not_self(self):
        self.assertNotIn("effect_self", modes("①：このカード以外の自分フィールドのモンスターを"
                                              "全て破壊する。"))
        self.assertNotIn("effect_self", modes("①：このカードと同じ縦列の他のモンスターを全て"
                                              "破壊する。"))
        self.assertNotIn("effect_self", modes("①：このカードと戦闘を行うモンスターを破壊する。"))
        self.assertNotIn("effect_self", modes("①：このカードと(共同)戦闘を行うモンスターの"
                                              "攻撃力は０になる。"))

    def test_stats_count_each_self_rule(self):
        doc, _ = export({1: [clause("①", "①：このカードの攻撃力は５００アップする。")],
                         2: [clause("①", "①：このカードと植物族モンスター１体を手札から"
                                          "特殊召喚する。")]})
        reasons = doc["統計"]["理由"]
        self.assertEqual(reasons.get("此卡:此卡的屬性"), 1)
        self.assertEqual(reasons.get("此卡:並列含此卡"), 1)

    def test_frames_on_this_card_are_counted_in_the_stats(self):
        doc, _ = export({1: [clause("①", "①：このカードは手札から特殊召喚できる。")],
                         2: [clause("①", REVIVE)]})
        self.assertEqual(doc["統計"]["框架"]["此卡"], 1)
        self.assertEqual(doc["統計"]["卡"]["此卡"], 1)


class TestPatientNonSelf(unittest.TestCase):
    """[[動作對象]]「非此卡」(action-patient 票 03):確定不動到此卡;全部類暫當皆非。"""

    def test_selection_with_a_count_is_nonself(self):
        self.assertEqual(modes("①：フィールドのカード１枚を対象として発動できる。そのカードを"
                               "破壊する。").get("effect_nonself"), ["破壊"])
        self.assertEqual(modes("①：自分の墓地からモンスター１体を特殊召喚する。"),
                         {"effect_nonself": ["特殊召喚"]})

    def test_summoning_another_monster_from_hand_is_nonself(self):
        self.assertEqual(modes("①：このカードをリリースして発動できる。手札からモンスター１体を"
                               "特殊召喚する。"),
                         {"cost_self": ["リリース"], "effect_nonself": ["特殊召喚"]})

    def test_other_than_this_card_is_nonself(self):
        self.assertEqual(modes("①：このカード以外の自分フィールドのモンスターを全て破壊する。"),
                         {"effect_nonself": ["破壊"]})

    def test_other_cards_written_as_hoka_is_nonself(self):
        """群體前的「他の」:フィールドの他のカードを全て破壊 不會破壞此卡。"""
        self.assertEqual(modes("①：フィールドの他のカードを全て破壊する。"),
                         {"effect_nonself": ["破壊"]})

    def test_zone_patient_with_a_count_is_nonself(self):
        """受事者寫成區域:手札を１枚捨てる(數量在子句裡)。"""
        self.assertEqual(modes("①：手札を１枚捨てて発動できる。自分はデッキから１枚ドローする。"),
                         {"cost_nonself": ["捨てる"]})

    def test_effect_or_activation_owned_by_another_is_nonself(self):
        self.assertEqual(modes("①：相手が魔法カードを発動した時に発動できる。その発動を無効にする。",
                               kind="誘發即時效果").get("effect_nonself"),
                         ["無効にする"])
        self.assertEqual(modes("①：相手の効果を無効にする。").get("effect_nonself"),
                         ["無効にする"])

    def test_attribute_of_a_selected_card_is_nonself(self):
        self.assertEqual(modes("①：相手フィールドのモンスター１体を対象として発動できる。"
                               "そのモンスターの攻撃力は０になる。").get("effect_nonself"),
                         ["にする"])

    def test_cards_attached_to_this_card_are_nonself(self):
        self.assertEqual(modes("①：このカードのX素材を１つ取り除いて発動できる。自分はデッキから"
                               "１枚ドローする。"),
                         {"cost_nonself": ["取り除く"]})

    def test_bare_card_count_is_a_selection(self):
        """受事者只剩量詞(その内の１体)也是選擇類。"""
        self.assertEqual(modes("①：相手フィールドのモンスター２体を対象として発動できる。"
                               "その内の１体を破壊する。").get("effect_nonself"), ["破壊"])

    def test_draw_and_damage_have_no_card_patient(self):
        self.assertEqual(modes("①：自分はデッキから２枚ドローする。"), {})
        self.assertEqual(modes("①：相手に１０００ダメージを与える。"), {})

    def test_this_card_listed_with_another_is_only_self(self):
        self.assertEqual(modes("①：このカードと植物族モンスター１体を手札から特殊召喚する。"),
                         {"effect_self": ["特殊召喚"]})

    def test_same_sentence_can_carry_a_leaf_in_both_modes(self):
        self.assertEqual(modes("①：このカードを手札から特殊召喚する。その後、手札からモンスター"
                               "１体を特殊召喚する。"),
                         {"effect_self": ["特殊召喚"], "effect_nonself": ["特殊召喚"]})

    def test_stats_count_nonself_and_unknown_patients(self):
        doc, _ = export({1: [clause("①", "①：自分の墓地からモンスター１体を特殊召喚する。")],
                         2: [clause("①", "①：相手に１０００ダメージを与える。")]})
        stats = doc["統計"]
        self.assertEqual(stats["框架"]["非此卡"], 1)
        self.assertEqual(stats["卡"]["非此卡"], 1)
        self.assertEqual(stats["理由"].get("皆非:不是卡"), 1)
        self.assertIn("表外受事者", stats)


class TestPatientAllClass(unittest.TestCase):
    """[[動作對象]]全部類(action-patient 票 04):依發動位置與區域、玩家、卡種判斷會不會
    包含此卡;會包含是皆非,不會是非此卡。"""

    def test_field_wipe_launched_on_the_field_is_neither(self):
        """都沒寫就是場上:場上的卡全部破壞會連此卡一起破壞。"""
        self.assertEqual(modes("①：フィールドのカードを全て破壊する。"), {})

    def test_launch_written_in_the_cost_moves_it_off_the_field(self):
        self.assertEqual(modes("①：墓地のこのカードを除外して発動できる。フィールドのカードを"
                               "全て破壊する。"),
                         {"cost_self": ["除外"], "effect_nonself": ["破壊"]})

    def test_launch_written_as_existing_in_the_graveyard(self):
        self.assertEqual(modes("①：このカードが墓地に存在する場合に発動できる。フィールドの"
                               "モンスターを全て破壊する。"),
                         {"effect_nonself": ["破壊"]})

    def test_launch_from_where_the_trigger_sent_this_card(self):
        self.assertEqual(modes("①：このカードが墓地へ送られた場合に発動できる。フィールドの"
                               "モンスターを全て破壊する。", kind="誘發效果(1速)"),
                         {"effect_nonself": ["破壊"]})

    def test_leaving_the_field_with_unknown_destination_is_off_the_field(self):
        self.assertEqual(modes("①：このカードがフィールドから離れた場合に発動できる。"
                               "フィールドのモンスターを全て破壊する。", kind="誘發效果(1速)"),
                         {"effect_nonself": ["破壊"]})

    def test_launch_from_where_this_card_moves_from_while_resolving(self):
        """移動之前的框架:處理中此卡自己移動的起點(手札)當發動位置。"""
        self.assertEqual(modes("①：手札を全て捨てる。その後、このカードを手札から特殊召喚する。"),
                         {"effect_self": ["特殊召喚"]})
        # 對照:沒有自己移動時預設場上,手札全部丟棄 不會包含此卡
        self.assertEqual(modes("①：手札を全て捨てる。"), {"effect_nonself": ["捨てる"]})

    def test_opponents_side_does_not_include_this_card(self):
        self.assertEqual(modes("①：相手フィールドのカードを全て破壊する。"),
                         {"effect_nonself": ["破壊"]})

    def test_card_kind_that_does_not_match_this_card(self):
        self.assertEqual(modes("①：フィールドの魔法・罠カードを全て破壊する。"),
                         {"effect_nonself": ["破壊"]})
        self.assertEqual(modes("①：フィールドの魔法・罠カードを全て破壊する。", face=SPELL), {})

    def test_zone_written_at_the_head_of_the_patient(self):
        """所在沒被切出、寫在受事者開頭(自分フィールドの…):同樣當群體區域。"""
        self.assertEqual(modes("①：自分フィールドの「天気」魔法・罠カードは相手の効果の対象に"
                               "ならない。").get("effect_nonself"), ["対象にする"])

    def test_zone_patient_without_a_count_follows_the_same_rule(self):
        self.assertEqual(modes("①：このカードが墓地に存在する場合に発動できる。手札を全て捨てる。"),
                         {"effect_nonself": ["捨てる"]})

    def test_stats_count_launch_sources(self):
        doc, _ = export({1: [clause("①", "①：フィールドのカードを全て破壊する。")],
                         2: [clause("①", "①：このカードが墓地に存在する場合に発動できる。"
                                          "フィールドのモンスターを全て破壊する。")]})
        launch = doc["統計"]["發動位置"]
        self.assertEqual(launch.get("預設場上"), 1)
        self.assertEqual(launch.get("寫明"), 1)

    def test_card_face_digest_rides_along_and_changes_with_the_face(self):
        faces = {1: export_common.card_face(DRAGON)}
        doc, _ = export({1: [clause("①", REVIVE)]}, faces)
        before = dict(doc["卡面"])
        faces = {1: export_common.card_face(dict(DRAGON, level=8))}
        doc, _ = export({1: [clause("①", REVIVE)]}, faces)
        self.assertEqual(set(before), {1})
        self.assertNotEqual(dict(doc["卡面"])[1], before[1])
        self.assertEqual(dict(doc["卡面"])[1],
                         export_common.face_hash(dict(DRAGON, level=8)))


class TestPatientCountIsNotDuration(unittest.TestCase):
    """數量要是受事者的數量:子句裡的期間、升降值不是選擇類(回歸:真資料抽樣發現)。"""

    def test_until_end_of_turn_is_not_a_count(self):
        self.assertEqual(modes("①：自分フィールドの全てのモンスターの攻撃力はターン終了時まで"
                               "倍になる。"), {})

    def test_level_change_amount_is_not_a_count(self):
        self.assertEqual(modes("①：自分フィールドの全てのモンスターのレベルは５つ上がる。"), {})

    def test_all_of_them_wins_over_a_duration(self):
        self.assertEqual(modes("①：発動後２回目の相手エンドフェイズまで、フィールドのモンスターを"
                               "全て除外する。"), {})

    def test_count_right_after_the_patient_still_counts(self):
        self.assertEqual(modes("①：手札を２枚まで捨てて発動できる。自分はデッキから１枚"
                               "ドローする。").get("cost_nonself"), ["捨てる"])

    def test_up_to_a_number_written_before_the_patient(self):
        self.assertTrue(modes("①：自分の墓地の魔法カードの数まで、デッキからモンスターを"
                              "手札に加える。").get("effect_nonself"))


class TestPatientLaunchEdgeCases(unittest.TestCase):
    """發動位置:此卡是施事者時沒有移動;靈擺區在場上。"""

    def test_this_card_destroying_another_does_not_leave_the_field(self):
        self.assertEqual(modes("①：このカードが相手モンスターを戦闘で破壊した場合に発動できる。"
                               "フィールドのモンスターを全て破壊する。",
                               kind="誘發效果(1速)"), {})

    def test_this_card_sending_another_does_not_move_it(self):
        self.assertEqual(modes("①：このカードがモンスターを墓地へ送った場合に発動できる。"
                               "フィールドのモンスターを全て破壊する。",
                               kind="誘發效果(1速)"), {})

    def test_this_card_destroyed_leaves_the_field(self):
        self.assertTrue(modes("①：このカードが破壊された場合に発動できる。フィールドのモンスターを"
                              "全て破壊する。", kind="誘發效果(1速)").get("effect_nonself"))

    def test_pendulum_zone_is_on_the_field(self):
        self.assertEqual(modes("①：このカードがPゾーンに存在する場合に発動できる。フィールドの"
                               "カードを全て破壊する。"), {})

    def test_pendulum_section_launches_from_the_pendulum_zone(self):
        text = "①：自分のPゾーンのカードを全て破壊する。"
        self.assertEqual(modes(text, section="pendulum"), {})
        self.assertTrue(modes(text).get("effect_nonself"))


class TestPatientThisEffect(unittest.TestCase):
    """受事者是效果、發動:主人是此卡就是此卡;「この効果で…したモンスターの効果」主人是別張。"""

    def test_this_effect_is_owned_by_this_card(self):
        self.assertTrue(modes("①：この効果の発動は無効化されない。").get("effect_self"))

    def test_effect_of_a_monster_summoned_by_this_effect_is_nonself(self):
        found = modes("①：手札からモンスター１体を特殊召喚する。この効果で特殊召喚した"
                      "モンスターの効果は無効化される。")
        self.assertIn("無効にする", found.get("effect_nonself", []))
        self.assertNotIn("effect_self", found)

    def test_sorezore_is_not_a_demonstrative(self):
        """それぞれ・それ以外 不是指示詞:沒有數量仍是全部類。"""
        self.assertEqual(modes("①：それ以外の自分フィールドのモンスターを全て破壊する。"), {})


class TestPatientAfterSelfMove(unittest.TestCase):
    """此卡自己移動之後的框架看移動的目的(2026-10-30 站主裁定,取代 story 16 例句判皆非)。"""

    def test_discarding_the_hand_after_leaving_it(self):
        self.assertEqual(modes("①：このカードを手札から特殊召喚する。その後、手札を全て捨てる。"),
                         {"effect_self": ["特殊召喚"], "effect_nonself": ["捨てる"]})

    def test_field_wipe_after_summoning_itself_includes_it(self):
        self.assertEqual(modes("①：このカードを手札から特殊召喚する。その後、フィールドのカードを"
                               "全て破壊する。"),
                         {"effect_self": ["特殊召喚"]})

    def test_field_wipe_after_returning_to_hand_does_not_include_it(self):
        found = modes("①：このカードを手札に戻す。その後、フィールドのモンスターを全て破壊する。")
        self.assertIn("破壊", found.get("effect_nonself", []))

    def test_destroying_itself_leaves_the_field(self):
        found = modes("①：このカードを破壊し、フィールドのモンスターを全て破壊する。")
        self.assertIn("破壊", found.get("effect_nonself", []))

    def test_moving_itself_as_a_cost_counts(self):
        self.assertEqual(modes("①：このカードをリリースして発動できる。フィールドのカードを"
                               "全て破壊する。"),
                         {"cost_self": ["リリース"], "effect_nonself": ["破壊"]})

    def test_negated_move_is_not_a_move(self):
        self.assertNotIn("effect_nonself", modes("①：このカードは戦闘では破壊されない。"
                                                 "フィールドのカードを全て破壊する。"))

    def test_move_in_one_option_does_not_affect_another(self):
        self.assertNotIn("effect_nonself", modes(
            "①：以下の効果から１つを選択して発動できる。\n●このカードを手札に戻す。\n"
            "●フィールドのカードを全て破壊する。"))

    def test_stats_report_frames_judged_after_a_self_move(self):
        doc, _ = export({1: [clause("①", "①：このカードを手札から特殊召喚する。その後、手札を全て"
                                         "捨てる。")]})
        self.assertEqual(doc["統計"]["發動位置"].get("移動後"), 1)


class TestPatientReviewFindings(unittest.TestCase):
    """code review 用例句實跑抓到的錯。"""

    def test_count_on_the_choosing_clause_carries_to_the_backfilled_frame(self):
        """１枚選んで破壊する:破壊 的對象是回填的,數量在 選ぶ 的子句裡。"""
        found = modes("①：フィールドのカードを１枚選んで破壊する。")
        self.assertIn("破壊", found.get("effect_nonself", []))

    def test_draw_never_has_a_card_patient(self):
        """「N枚」是抽卡張數,不是卡的選擇。"""
        self.assertEqual(modes("①：自分はデッキに戻した数＋１枚をドローする。"), {})

    def test_listed_with_this_card_counts_for_the_launch_position(self):
        self.assertEqual(modes("①：手札を全て捨てる。その後、このカードと植物族モンスター１体を"
                               "手札から特殊召喚する。"),
                         {"effect_self": ["特殊召喚"]})

    def test_listed_with_this_card_in_the_cost_counts_for_the_launch_position(self):
        found = modes("①：墓地のこのカードとモンスター１体を除外して発動できる。フィールドの"
                      "カードを全て破壊する。")
        self.assertEqual(found.get("effect_nonself"), ["破壊"])

    def test_listed_with_this_card_may_carry_a_modifier(self):
        self.assertTrue(modes("①：リンク状態のこのカード及びこのカードのリンク先のモンスターを"
                              "破壊する。").get("effect_self"))

    def test_comparing_with_this_card_is_not_listing_it(self):
        self.assertNotIn("effect_self", modes("①：このカードとカード名が異なるモンスターを全て"
                                              "破壊する。"))

    def test_stats_split_launch_sources_of_the_neither_frames(self):
        doc, _ = export({1: [clause("①", "①：フィールドのカードを全て破壊する。")],
                         2: [clause("①", "①：相手フィールドのカードを全て破壊する。")]})
        self.assertEqual(doc["統計"]["發動位置"].get("預設場上"), 2)
        self.assertEqual(doc["統計"]["皆非發動位置"].get("預設場上"), 1)


class TestPatientReadsAnaphora(unittest.TestCase):
    """[[動作對象]]讀[[回指]](action-patient-anaphora 票 05、06):斷言此卡葉、非此卡葉。"""

    def assert_nonself(self, found, group="effect"):
        self.assertTrue(found.get(group + "_nonself"), found)
        self.assertNotIn(group + "_self", found)

    def assert_self(self, found, group="effect"):
        self.assertTrue(found.get(group + "_self"), found)
        self.assertNotIn(group + "_nonself", found)

    def assert_neither(self, found, group="effect"):
        self.assertNotIn(group + "_self", found)
        self.assertNotIn(group + "_nonself", found)

    # ── 票 05:選擇類、含此卡、留空 ──

    def test_selected_target_stays_nonself(self):
        self.assert_nonself(modes("①：フィールドのモンスター１体を対象として発動できる。そのモンスターを破壊する。"))

    def test_other_than_this_card_target_is_nonself(self):
        self.assert_nonself(modes("①：このカード以外のモンスター１体を対象として発動できる。そのモンスターを破壊する。"))

    def test_listed_target_is_only_self(self):
        self.assert_self(modes("①：手札のこのカードと手札のモンスター１体を相手に見せて発動できる。その２体を特殊召喚する。"))

    def test_one_of_listed_target_is_self(self):
        self.assert_self(modes("①：手札のこのカードと手札のモンスター１体を相手に見せて発動できる。"
                               "その２体の内の１体を特殊召喚する。"))

    def test_this_card_or_alternative_is_self(self):
        self.assert_self(modes("①：このカードまたは自分フィールドのモンスター１体を対象として発動できる。"
                               "そのモンスターを破壊する。"))

    def test_attribute_follows_target(self):
        self.assert_nonself(modes("①：フィールドのモンスター１体を対象として発動できる。そのモンスターの攻撃力は０になる。"))
        self.assert_self(modes("①：このカードまたは自分のモンスター１体を選び、その攻撃力を１０００アップする。"))

    def test_blank_stays_nonself(self):
        self.assert_nonself(modes("①：そのモンスターを破壊する。"))
        self.assert_nonself(modes("①：その効果を無効にする。"))

    def test_this_card_alone_is_skipped_so_blank(self):
        self.assert_nonself(modes("①：このカードを手札から捨てて発動できる。そのモンスターを破壊する。"))

    def test_literal_this_card_rule_goes_first(self):
        self.assert_self(modes("①：相手のモンスター１体を対象として発動できる。そのカードとこのカードを破壊する。"))

    def test_modifier_with_count_is_selected(self):
        self.assert_nonself(modes("①：自分フィールドのXモンスター１体を対象として発動できる。"
                                  "そのモンスターよりランクが２つ高いXモンスター１体を特殊召喚する。"))

    def test_modifier_without_count_is_all_class(self):
        found = modes("①：フィールドのモンスター１体を対象として発動できる。"
                      "そのモンスターより低い攻撃力を持つフィールドのモンスターを破壊する。")
        self.assert_neither(found)

    # ── 票 06:全部類與效果類 ──

    def test_event_subject_opponent_is_nonself(self):
        self.assert_nonself(modes("①：相手がモンスターを特殊召喚した時に発動できる。そのモンスターを破壊する。"))

    def test_group_target_that_may_include_self_is_neither(self):
        self.assert_neither(modes("①：自分のモンスターが戦闘を行うダメージ計算時に発動できる。"
                                  "そのモンスターの攻撃力はターン終了時まで１０００アップする。"))

    def test_race_mismatch_is_nonself(self):
        self.assert_nonself(modes("①：自分の戦士族モンスターが戦闘を行うダメージ計算時に発動できる。"
                                  "そのモンスターの攻撃力はターン終了時まで１０００アップする。"))

    def test_race_match_is_neither(self):
        self.assert_neither(modes("①：自分のドラゴン族モンスターが戦闘を行うダメージ計算時に発動できる。"
                                  "そのモンスターの攻撃力はターン終了時まで１０００アップする。"))

    def test_target_group_uses_position_after_self_move(self):
        """此卡移動之後:目標的區域看移動的目的。"""
        self.assert_nonself(
            {k: v for k, v in modes("①：このカードを手札から特殊召喚する。その後、手札のモンスターが"
                                    "存在する場合、そのモンスターを破壊する。").items()
             if "破壊" in str(v)})

    def test_owner_this_card_is_self(self):
        self.assert_self(modes("①：このカードの攻撃宣言時に発動できる。その攻撃を無効にする。"))

    def test_owner_other_is_nonself(self):
        self.assert_nonself(modes("①：相手が効果を発動した時に発動できる。その発動を無効にする。"))
        self.assert_nonself(modes("①：相手モンスターの攻撃宣言時に発動できる。その攻撃を無効にする。"))

    def test_targeted_this_card_is_not_owner(self):
        self.assert_nonself(modes("①：このカードが攻撃対象に選択された時に発動できる。その攻撃を無効にする。"))
        self.assert_nonself(modes("①：このカードを対象とする効果が発動した時に発動できる。その効果を無効にする。"))

    def test_owner_mentioning_this_card_is_not_self(self):
        """47946130:主人字面只是提到此卡(このカードまたは…を対象とする相手)不算此卡。"""
        self.assert_nonself(modes("①：このカードまたはこのカードのリンク先のモンスターを対象とする相手の効果が"
                                  "発動した時に発動できる。その発動を無効にする。"))

    def test_target_attached_to_this_card_is_nonself(self):
        """12067160:このカードのリンク先のモンスター 是另一張卡。"""
        self.assert_nonself(modes("①：このカードのリンク先のモンスターは攻撃できず、そのモンスターの攻撃力は０になる。"))

    def test_this_card_as_event_subject_means_another_card(self):
        """10602628:このカードが戦闘でモンスターを破壊し…その破壊されたモンスター。"""
        self.assert_nonself(
            {k: v for k, v in modes("①：このカードが戦闘でモンスターを破壊した時に発動できる。"
                                    "その破壊されたモンスターを除外する。").items()})

    def test_attack_target_is_not_owner(self):
        """3507053(code review):攻撃対象になった。"""
        self.assert_nonself(modes("①：このカードが攻撃対象になった時に発動できる。その攻撃を無効にする。"))

    def test_target_own_player_beats_event_subject(self):
        """code review:相手が自分のモンスターを破壊した時…そのモンスター 可能就是此卡。"""
        self.assert_neither(modes("①：相手が自分のモンスターを破壊した時に発動できる。そのモンスターの攻撃力を０にする。"))

    def test_reason_card_counts_and_uncomparable_are_reported(self):
        doc, _ = export({1: [clause("①", "①：自分のモンスターが戦闘を行うダメージ計算時に発動できる。"
                                        "そのモンスターの攻撃力はターン終了時まで１０００アップする。")],
                         2: [clause("①", "①：フィールドのモンスター１体を対象として発動できる。そのモンスターを破壊する。"),
                             clause("②", "②：墓地のモンスター１体を対象として発動できる。そのモンスターを除外する。")]},
                        faces={1: DRAGON, 2: DRAGON})
        stats = doc["統計"]
        self.assertEqual(stats["理由"]["非此卡:回指選擇類"], 2)
        self.assertEqual(stats["理由卡"]["非此卡:回指選擇類"], 1)
        self.assertEqual(stats["比不了"], 1)

    def test_reasons_are_reported(self):
        doc, _ = export({1: [clause("①", "①：フィールドのモンスター１体を対象として発動できる。そのモンスターを破壊する。"),
                             clause("②", "②：このカードの攻撃宣言時に発動できる。その攻撃を無効にする。")]},
                        faces={1: DRAGON})
        reasons = doc["統計"]["理由"]
        self.assertEqual(reasons["非此卡:回指選擇類"], 1)
        self.assertEqual(reasons["此卡:回指事件主人是此卡"], 1)

    def test_rerun_is_byte_identical(self):
        cards = {1: [clause("①", "①：相手がモンスターを特殊召喚した時に発動できる。そのモンスターを破壊する。")]}
        once = export_frames.serialize(export(cards, faces={1: DRAGON})[0])
        self.assertEqual(once, export_frames.serialize(export(cards, faces={1: DRAGON})[0]))


class TestPatientAllClassConditions(unittest.TestCase):
    """[[動作對象]]全部類(action-patient 票 05):種族、屬性、字段、子類型、數值。合成的此卡是
    等級 7、攻 2500 守 2000 的暗屬性龍族效果怪獸「テスト・ドラゴン」。"""

    def test_race(self):
        self.assertTrue(wipe("戦士族モンスター"))
        self.assertFalse(wipe("ドラゴン族モンスター"))
        self.assertFalse(wipe("戦士族・ドラゴン族モンスター"))

    def test_attribute(self):
        self.assertTrue(wipe("光属性モンスター"))
        self.assertFalse(wipe("闇属性モンスター"))
        self.assertFalse(wipe("光・闇属性モンスター"))

    def test_archetype_is_contained_in_the_japanese_card_name(self):
        self.assertTrue(wipe("「サイバー」モンスター"))
        self.assertFalse(wipe("「テスト」モンスター"))

    def test_card_subtype(self):
        self.assertTrue(wipe("融合モンスター"))
        self.assertFalse(wipe("効果モンスター"))
        self.assertTrue(wipe("通常モンスター"))
        self.assertTrue(wipe("融合・S・Xモンスター"))
        self.assertFalse(wipe("融合・S・Xモンスター", face=XYZ))

    def test_spell_subtype(self):
        self.assertTrue(wipe("永続魔法カード", face=SPELL))
        self.assertFalse(wipe("通常魔法カード", face=SPELL))

    def test_numeric_conditions(self):
        self.assertTrue(wipe("レベル４以下のモンスター"))
        self.assertFalse(wipe("レベル７以上のモンスター"))
        self.assertTrue(wipe("攻撃力１０００以下のモンスター"))
        self.assertFalse(wipe("攻撃力２５００以上のモンスター"))
        self.assertTrue(wipe("守備力１０００以下のモンスター"))
        self.assertFalse(wipe("守備力２０００のモンスター"))

    def test_rank_and_level_do_not_mix(self):
        """超量怪獸沒有等級、只有階級(總表的 level 欄存階級)。"""
        self.assertTrue(wipe("レベル４以下のモンスター", face=XYZ))
        self.assertFalse(wipe("ランク４以下のモンスター", face=XYZ))
        self.assertTrue(wipe("ランク４のモンスター"))

    def test_unknown_atk_cannot_be_compared(self):
        self.assertFalse(wipe("攻撃力１０００以下のモンスター", face=UNKNOWN_ATK))

    def test_uncomparable_modifiers_may_include_this_card(self):
        self.assertFalse(wipe("表側表示モンスター"))
        self.assertFalse(wipe("このカードと同じ種族のモンスター"))

    def test_condition_inside_a_modifier_does_not_count(self):
        """修飾語裡的種族說的是素材,不是群體本身。"""
        self.assertFalse(wipe("戦士族モンスターを素材としたモンスター"))
        self.assertFalse(wipe("戦士族以外のモンスター"))

    def test_alternatives_match_when_any_of_them_matches(self):
        self.assertFalse(wipe("「サイバー」モンスターかドラゴン族モンスター"))
        self.assertTrue(wipe("「サイバー」モンスターか戦士族モンスター"))

    def test_conditions_of_one_alternative_are_all_required(self):
        self.assertTrue(wipe("闇属性の戦士族モンスター"))
        self.assertFalse(wipe("闇属性のドラゴン族モンスター"))

    def test_archetype_compares_across_full_and_half_width(self):
        self.assertFalse(wipe("「DD」モンスター", face=dict(DRAGON, name_ja="ＤＤ魔導賢者")))

    def test_stats_count_each_blocker_and_uncomparable_literals(self):
        doc, _ = export({1: [clause("①", "①：自分フィールドの戦士族モンスターを全て破壊する。")],
                         2: [clause("①", "①：自分フィールドの表側表示モンスターを全て破壊する。")]},
                        {1: export_common.card_face(DRAGON),
                         2: export_common.card_face(DRAGON)})
        stats = doc["統計"]
        self.assertEqual(stats["理由"].get("非此卡:全部類種族對不上"), 1)
        self.assertEqual(stats["理由"].get("皆非:全部類比不了"), 1)
        self.assertEqual(stats["比不了字面"], {"表側表示モンスター": 1})


if __name__ == "__main__":
    unittest.main()
