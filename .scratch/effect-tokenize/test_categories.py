# -*- coding: utf-8 -*-
"""動作類別歸組的行為測試(.scratch/action-categories 票 01〜)。

唯一接縫:一句效果句原文(帶同卡同段上文)→ 每個動作框架的類別紀錄
(categories.classify)。包住框架抽取接縫再接歸組,用真的分詞器、詞典、類別樹與
規則表;只斷言每個框架的(動作、狀態、葉清單、大類、來源玩家、目的玩家),不測規則
內部、不測樹怎麼存。每個句型一條回歸例子——修規則或改樹前先補一條會失敗的例子。

執行:PYTHONIOENCODING=utf-8 python -m unittest discover -s .scratch/effect-tokenize
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import categories  # noqa: E402


def classify(text, context=""):
    """類別紀錄 → 比對用的 tuple(動作, 狀態, 葉清單, 大類, 來源玩家, 目的玩家)。"""
    return [(r["action"], r["status"], r["leaves"], r["major"],
             r["source_player"], r["goal_player"])
            for r in categories.classify(text, context)]


class TestSkeleton(unittest.TestCase):
    """票 01:骨架——樹 → 規則匹配 → 類別紀錄。"""

    def test_revive_from_grave(self):
        self.assertEqual(
            classify("①：自分の墓地からモンスター１体を特殊召喚する。"),
            [("特殊召喚", "已歸", ["特殊召喚←墓地"], "區域移動", "自分", None)])

    def test_search_deck_to_hand_cost_and_effect(self):
        """代價位照貼;檢索歸 加える:デッキ→手札,捨てる 沒有詞元節點記未歸。"""
        self.assertEqual(
            classify("①：手札を１枚捨てて発動できる。デッキから「試作機」１体を"
                     "手札に加える。"),
            [("捨てる", "未歸", [], None, None, None),
             ("加える", "已歸", ["加える:デッキ→手札"], "區域移動", "無", "無")])

    def test_unmatched_conditions_without_default_leaf(self):
        """特殊召喚 沒有 ←EXデッキ 的葉、也沒有預設葉:EXデッキから 記未歸(玩家欄照記)。"""
        self.assertEqual(
            classify("①：このカードをEXデッキから特殊召喚する。"),
            [("特殊召喚", "未歸", [], None, "無", None)])

    def test_lemma_node_without_children_is_default_leaf(self):
        self.assertEqual(
            classify("①：自分は１０００LP回復する。"),
            [("回復", "已歸", ["回復"], "回復", None, None)])

    def test_condition_position_is_not_applicable(self):
        """條件位的框架不貼本樹(觸發事件軸另開線);沒有葉的詞元記未歸。"""
        self.assertEqual(
            classify("①：このカードが召喚に成功した時に発動できる。"
                     "自分は１枚ドローする。"),
            [("成功", "不適用", [], None, None, None),
             ("ドロー", "未歸", [], None, None, None)])

    def test_condition_position_wins_over_matching_leaf(self):
        """「…が破壊された場合」的 破壊 是條件位:即使 破壊 有葉也不適用。"""
        self.assertEqual(
            classify("①：このカードが戦闘で破壊された場合に発動できる。"
                     "自分の墓地からモンスター１体を特殊召喚する。"),
            [("破壊", "不適用", [], None, None, None),
             ("特殊召喚", "已歸", ["特殊召喚←墓地"], "區域移動", "自分", None)])

    def test_frames_inside_options(self):
        """出自選項(●)的框架照貼。"""
        self.assertEqual(
            classify("①：以下の効果から１つを選択して発動できる。"
                     "●自分の墓地からモンスター１体を特殊召喚する。"
                     "●相手フィールドのカード１枚を破壊する。"),
            [("選択", "不適用", [], None, None, None),
             ("特殊召喚", "已歸", ["特殊召喚←墓地"], "區域移動", "自分", None),
             ("破壊", "已歸", ["破壊"], "破壊", None, None)])


class TestZonesAndPlayers(unittest.TestCase):
    """票 02:來源/目的字面映成(玩家, 區域);玩家不進葉、複合字面一框架多葉。"""

    def test_compound_source_takes_one_leaf_per_zone(self):
        """手札・墓地から:依字面順序帶兩葉,大類仍一個。"""
        self.assertEqual(
            classify("①：手札・墓地から「試作機」１体を特殊召喚する。"),
            [("特殊召喚", "已歸", ["特殊召喚←手札", "特殊召喚←墓地"], "區域移動",
              "無", None)])

    def test_player_prefix_does_not_split_leaf(self):
        """相手の墓地から 與 自分の墓地から 同葉,玩家欄不同;目的 自分フィールド 照記。"""
        self.assertEqual(
            classify("①：相手の墓地からモンスター１体を選んで自分フィールドに"
                     "特殊召喚する。"),
            [("選ぶ", "未歸", [], None, "相手", None),
             ("特殊召喚", "已歸", ["特殊召喚←墓地"], "區域移動", "相手", "自分")])

    def test_either_player_is_both(self):
        """自分または相手の(與 自分か相手の、自分・相手の、お互いの)記雙方。"""
        self.assertEqual(
            classify("①：自分または相手の墓地からモンスター１体を選んで"
                     "自分フィールドに特殊召喚する。"),
            [("選ぶ", "未歸", [], None, "雙方", None),
             ("特殊召喚", "已歸", ["特殊召喚←墓地"], "區域移動", "雙方", "自分")])
        for prefix in ("自分か相手の", "自分・相手の"):
            self.assertEqual(
                classify("①：%s墓地からモンスター１体を特殊召喚する。" % prefix),
                [("特殊召喚", "已歸", ["特殊召喚←墓地"], "區域移動", "雙方", None)],
                prefix)

    def test_deck_top_is_deck(self):
        """デッキの上(牌組頂/底)歸牌組;お互いの 記雙方、無前綴的 墓地 記無。"""
        self.assertEqual(
            classify("①：お互いのデッキの上からカードを１枚墓地へ送る。"),
            [("送る", "已歸", ["送る:デッキ→墓地"], "區域移動", "雙方", "無")])

    def test_unmapped_zone_literal(self):
        """その中 對不上任何區域:需要區域的葉不匹配、不報錯;玩家欄留空。"""
        self.assertEqual(
            classify("①：デッキからカードを３枚めくり、その中からモンスター１体を"
                     "特殊召喚する。"),
            [("めくる", "未歸", [], None, "無", None),
             ("特殊召喚", "未歸", [], None, None, None)])


class TestNegationAndKeywords(unittest.TestCase):
    """票 03:否定極性分耐性/限制(述語形)、可能視同肯定、對象關鍵詞分葉。"""

    def test_not_destroyed_is_resistance(self):
        self.assertEqual(
            classify("①：このカードは効果では破壊されない。"),
            [("破壊", "已歸", ["破壊(耐性)"], "耐性", None, None)])

    def test_not_targeted_is_resistance(self):
        self.assertEqual(
            classify("①：このカードは相手の効果の対象にならない。"),
            [("対象になる", "已歸", ["対象になる(耐性)"], "耐性", None, None)])

    def test_unaffected_is_resistance(self):
        """受けない(述語形是一般否定,但 受ける 的否定就是不受影響)歸耐性。"""
        self.assertEqual(
            classify("①：このカードは相手の効果を受けない。"),
            [("受ける", "已歸", ["受ける(耐性)"], "耐性", None, None)])

    def test_cannot_is_restriction(self):
        self.assertEqual(
            classify("①：相手は自分の墓地のカードを除外できない。"),
            [("除外", "已歸", ["除外(限制)"], "限制", None, None)])

    def test_godan_potential_is_restriction(self):
        """行えない 是 行う 的可能否定。"""
        self.assertEqual(
            classify("①：相手はバトルフェイズを行えない。"),
            [("行う", "已歸", ["行う(限制)"], "限制", None, None)])

    def test_plain_negation_is_unplaced(self):
        """送らず 這類一般否定不是耐性也不是限制:沒有節點,記未歸。"""
        self.assertEqual(
            classify("①：発動後、このカードは墓地へ送らず、そのままセットする。"),
            [("送る", "未歸", [], None, None, "無"),
             ("セット", "未歸", [], None, None, None)])

    def test_possible_is_affirmative(self):
        """破壊できる 與 破壊する 同葉。"""
        self.assertEqual(
            classify("①：このカードが召喚に成功した場合に発動できる。"
                     "相手フィールドのカード１枚を選んで破壊できる。"),
            [("成功", "不適用", [], None, None, None),
             ("選ぶ", "未歸", [], None, None, None),
             ("破壊", "已歸", ["破壊"], "破壊", None, None)])

    def test_destroy_spell_trap_and_monster_split(self):
        self.assertEqual(
            classify("①：相手フィールドの魔法・罠カード１枚を破壊する。"),
            [("破壊", "已歸", ["破壊:魔法カード/罠カード"], "破壊", None, None)])
        self.assertEqual(
            classify("①：相手フィールドの罠カード１枚を破壊する。"),
            [("破壊", "已歸", ["破壊:魔法カード/罠カード"], "破壊", None, None)])
        self.assertEqual(
            classify("①：相手フィールドのモンスター１体を破壊する。"),
            [("破壊", "已歸", ["破壊:モンスター"], "破壊", None, None)])

    def test_negate_activation_and_effect_split(self):
        self.assertEqual(
            classify("①：相手が魔法・罠カードを発動した時に発動できる。"
                     "その発動を無効にする。"),
            [("発動", "不適用", [], None, None, None),
             ("無効にする", "已歸", ["無効にする:発動"], "無効にする", None, None)])
        self.assertEqual(
            classify("①：その効果を無効にする。"),
            [("無効にする", "已歸", ["無効にする:効果"], "無効にする", None, None)])

    def test_unmatched_object_falls_to_default_leaf(self):
        """對象對不上任何關鍵詞(相手フィールドのカード)落 破壊 的預設葉。"""
        self.assertEqual(
            classify("①：相手フィールドのカード１枚を破壊する。"),
            [("破壊", "已歸", ["破壊"], "破壊", None, None)])


class TestCardRollup(unittest.TestCase):
    """票 04:卡層彙總——一張卡的幾句原文 → 效果組與代價組的葉集合(各自去重、依樹序)。"""

    def test_cost_banish_stays_out_of_effect_group(self):
        """代價位的 除外 只進代價組;搜「除外」時不撈到自家代價除外的卡。"""
        self.assertEqual(
            categories.classify_card([
                "①：自分の墓地のモンスター１体を除外して発動できる。"
                "相手フィールドのモンスター１体を破壊する。"]),
            {"effect": ["破壊:モンスター"], "cost": ["除外"]})

    def test_groups_dedupe_and_follow_tree_order(self):
        """兩句各出的葉合併去重,依樹序排(特殊召喚 在 加える 前、←墓地 在 ←手札 前);
        未歸與條件位的框架不進任何組。"""
        self.assertEqual(
            categories.classify_card([
                "①：手札を１枚捨てて発動できる。デッキから「試作機」１体を手札に加える。",
                "②：このカードが墓地へ送られた場合に発動できる。"
                "手札・墓地から「試作機」１体を特殊召喚する。",
                "③：自分の墓地から「試作機」１体を特殊召喚する。"]),
            {"effect": ["特殊召喚←墓地", "特殊召喚←手札", "加える:デッキ→手札"],
             "cost": []})


class TestTreeIntegrity(unittest.TestCase):
    """建置期檢查:真的類別樹通過完整性檢查(葉名唯一、每葉有詞元條件、大類非空、
    同詞元的葉不被前面較寬的葉蓋掉)。"""

    def test_real_tree_loads(self):
        tree = categories.load_tree()
        self.assertTrue(tree.leaves)


if __name__ == "__main__":
    unittest.main()
