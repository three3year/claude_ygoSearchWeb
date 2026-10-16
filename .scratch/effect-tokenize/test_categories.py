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
            [("特殊召喚", "已歸", ["特殊召喚←墓地"], "區域移動", None, None)])

    def test_search_deck_to_hand_cost_and_effect(self):
        """代價位照貼;檢索歸 加える:デッキ→手札,捨てる 沒有詞元節點記未歸。"""
        self.assertEqual(
            classify("①：手札を１枚捨てて発動できる。デッキから「試作機」１体を"
                     "手札に加える。"),
            [("捨てる", "未歸", [], None, None, None),
             ("加える", "已歸", ["加える:デッキ→手札"], "區域移動", None, None)])

    def test_unmatched_conditions_without_default_leaf(self):
        """特殊召喚 只有 ←墓地 一葉、沒有預設葉:手札から 記未歸。"""
        self.assertEqual(
            classify("①：このカードを手札から特殊召喚する。"),
            [("特殊召喚", "未歸", [], None, None, None)])

    def test_lemma_node_without_children_is_default_leaf(self):
        self.assertEqual(
            classify("①：相手フィールドのカード１枚を破壊する。"),
            [("破壊", "已歸", ["破壊"], "破壊", None, None)])

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
             ("特殊召喚", "已歸", ["特殊召喚←墓地"], "區域移動", None, None)])

    def test_frames_inside_options(self):
        """出自選項(●)的框架照貼。"""
        self.assertEqual(
            classify("①：以下の効果から１つを選択して発動できる。"
                     "●自分の墓地からモンスター１体を特殊召喚する。"
                     "●相手フィールドのカード１枚を破壊する。"),
            [("選択", "不適用", [], None, None, None),
             ("特殊召喚", "已歸", ["特殊召喚←墓地"], "區域移動", None, None),
             ("破壊", "已歸", ["破壊"], "破壊", None, None)])


class TestTreeIntegrity(unittest.TestCase):
    """建置期檢查:真的類別樹通過完整性檢查(葉名唯一、每葉有詞元條件、大類非空、
    同詞元的葉不被前面較寬的葉蓋掉)。"""

    def test_real_tree_loads(self):
        tree = categories.load_tree()
        self.assertTrue(tree.leaves)


if __name__ == "__main__":
    unittest.main()
