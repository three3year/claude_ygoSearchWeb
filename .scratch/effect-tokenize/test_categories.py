# -*- coding: utf-8 -*-
"""動作類別歸組的行為測試(.scratch/action-categories 票 01〜)。

唯一接縫:一句效果句原文(帶同卡同段上文)→ 每個動作框架的類別紀錄
(categories.classify)。包住框架抽取接縫再接歸組,用真的分詞器、詞典、類別樹與
規則表;只斷言每個框架的(動作、狀態、葉清單、大類、來源玩家、目的玩家),不測規則
內部、不測樹怎麼存。每個句型一條回歸例子——修規則或改樹前先補一條會失敗的例子。
例外:真樹還沒開的葉條件(所在、玩家;葉表在類別線票 06 草案才提議)用測試小樹驗,
經同一接縫(classify 的 tree 參數),分詞器、詞典與規則表仍是真的
(category-tree-restart 票 01、02)。

執行:PYTHONIOENCODING=utf-8 python -m unittest discover -s .scratch/effect-tokenize
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import categories  # noqa: E402


def classify(text, context="", tree=None):
    """類別紀錄 → 比對用的 tuple(動作, 狀態, 葉清單, 大類, 來源玩家, 目的玩家)。
    tree 給樹來源檔的「樹」清單時改用該測試小樹(驗真樹還沒開的葉條件)。"""
    if tree is not None:
        tree = categories.CategoryTree({"樹": tree})
    return [(r["action"], r["status"], r["leaves"], r["major"],
             r["source_player"], r["goal_player"])
            for r in categories.classify(text, context, tree)]


class TestSkeleton(unittest.TestCase):
    """票 01:骨架——樹 → 規則匹配 → 類別紀錄。"""

    def test_revive_from_grave(self):
        self.assertEqual(
            classify("①：自分の墓地からモンスター１体を特殊召喚する。"),
            [("特殊召喚", "已歸", ["特殊召喚←墓地"], "召喚", "自分", None)])

    def test_search_deck_to_hand_cost_and_effect(self):
        """代價位照貼(捨てる);檢索歸 加える:デッキ→手札。"""
        self.assertEqual(
            classify("①：手札を１枚捨てて発動できる。デッキから「試作機」１体を"
                     "手札に加える。"),
            [("捨てる", "已歸", ["捨てる"], "區域移動", "無", None),
             ("加える", "已歸", ["加える:デッキ→手札"], "區域移動", "無", "無")])

    def test_lemma_without_node_is_unplaced(self):
        """樹裡沒有這個詞元(長尾 振り直す):記未歸,沒有「其他」類。"""
        self.assertEqual(
            classify("①：サイコロを振り直す。"),
            [("振り直す", "未歸", [], None, None, None)])

    def test_unmatched_conditions_without_default_leaf(self):
        """得る 只有 コントロール/効果 兩個關鍵詞葉、沒有預設葉:對象對不上時記未歸。"""
        self.assertEqual(
            classify("①：相手は１０００LPを得る。"),
            [("得る", "未歸", [], None, None, None)])

    def test_lemma_node_without_children_is_default_leaf(self):
        self.assertEqual(
            classify("①：自分は１０００LP回復する。"),
            [("回復", "已歸", ["回復"], "LP・ダメージ", None, None)])

    def test_condition_position_is_not_applicable(self):
        """條件位的框架不貼本樹(觸發事件軸另開線)。"""
        self.assertEqual(
            classify("①：このカードが召喚に成功した時に発動できる。"
                     "自分は１枚ドローする。"),
            [("成功", "不適用", [], None, None, None),
             ("ドロー", "已歸", ["ドロー"], "區域移動", None, None)])

    def test_condition_position_wins_over_matching_leaf(self):
        """「…が破壊された場合」的 破壊 是條件位:即使 破壊 有葉也不適用。"""
        self.assertEqual(
            classify("①：このカードが戦闘で破壊された場合に発動できる。"
                     "自分の墓地からモンスター１体を特殊召喚する。"),
            [("破壊", "不適用", [], None, None, None),
             ("特殊召喚", "已歸", ["特殊召喚←墓地"], "召喚", "自分", None)])

    def test_frames_inside_options(self):
        """出自選項(●)的框架照貼。"""
        self.assertEqual(
            classify("①：以下の効果から１つを選択して発動できる。"
                     "●自分の墓地からモンスター１体を特殊召喚する。"
                     "●相手フィールドのカード１枚を破壊する。"),
            [("選択", "不適用", [], None, None, None),
             ("特殊召喚", "已歸", ["特殊召喚←墓地"], "召喚", "自分", None),
             ("破壊", "已歸", ["破壊@フィールド"], "破壊", None, None)])


class TestZonesAndPlayers(unittest.TestCase):
    """票 02:來源/目的字面映成(玩家, 區域);玩家不進葉、複合字面一框架多葉。"""

    def test_compound_source_takes_one_leaf_per_zone(self):
        """手札・墓地から:依字面順序帶兩葉,大類仍一個。"""
        self.assertEqual(
            classify("①：手札・墓地から「試作機」１体を特殊召喚する。"),
            [("特殊召喚", "已歸", ["特殊召喚←手札", "特殊召喚←墓地"], "召喚",
              "無", None)])

    def test_player_prefix_does_not_split_leaf(self):
        """相手の墓地から 與 自分の墓地から 同葉,玩家欄不同;目的 自分フィールド 照記。"""
        self.assertEqual(
            classify("①：相手の墓地からモンスター１体を選んで自分フィールドに"
                     "特殊召喚する。"),
            [("選ぶ", "已歸", ["選ぶ"], "處理程序", "相手", None),
             ("特殊召喚", "已歸", ["特殊召喚←墓地"], "召喚", "相手", "自分")])

    def test_either_player_is_both(self):
        """自分または相手の(與 自分か相手の、自分・相手の、お互いの)記雙方。"""
        self.assertEqual(
            classify("①：自分または相手の墓地からモンスター１体を選んで"
                     "自分フィールドに特殊召喚する。"),
            [("選ぶ", "已歸", ["選ぶ"], "處理程序", "雙方", None),
             ("特殊召喚", "已歸", ["特殊召喚←墓地"], "召喚", "雙方", "自分")])
        for prefix in ("自分か相手の", "自分・相手の"):
            self.assertEqual(
                classify("①：%s墓地からモンスター１体を特殊召喚する。" % prefix),
                [("特殊召喚", "已歸", ["特殊召喚←墓地"], "召喚", "雙方", None)],
                prefix)

    def test_deck_top_is_deck(self):
        """デッキの上(牌組頂/底)歸牌組;お互いの 記雙方、無前綴的 墓地 記無。"""
        self.assertEqual(
            classify("①：お互いのデッキの上からカードを１枚墓地へ送る。"),
            [("送る", "已歸", ["送る:デッキ→墓地"], "區域移動", "雙方", "無")])

    def test_patient_zone_from_frame_source_or_place(self):
        """frame-args-v3 票 04:受事者片語裡的區域由框架抽取切出——移動類(除外)記來源,
        其餘(破壊)記所在;所在不當來源讀(category-tree-restart 票 01),來源玩家欄只記來源
        字面的玩家;原文有來源字面時對象欄不切。"""
        self.assertEqual(
            classify("①：墓地のこのカードを除外して発動できる。"
                     "相手フィールドのカード１枚を破壊する。"),
            [("除外", "已歸", ["除外←墓地"], "區域移動", "無", None),
             ("破壊", "已歸", ["破壊@フィールド"], "破壊", None, None)])
        self.assertEqual(
            classify("①：自分の手札から「墓地のモンスター」１体を特殊召喚する。"),
            [("特殊召喚", "已歸", ["特殊召喚←手札"], "召喚", "自分", None)])

    def test_patient_zone_compound_and_described(self):
        """受事者的複合區域(手札・フィールドのこのカード)帶多葉;描述裡有「・」
        (魔法・罠カード)也切得出區域。"""
        self.assertEqual(
            classify("①：手札・フィールドのこのカードを墓地へ送って発動できる。"
                     "相手フィールドの魔法・罠カード１枚を破壊する。"),
            [("送る", "已歸", ["送る:手札→墓地", "送る:フィールド→墓地"], "區域移動",
              "無", "無"),
             ("破壊", "已歸", ["破壊:魔法カード/罠カード"], "破壊", None, None)])

    def test_moved_patient_zone_still_reaches_source_leaves(self):
        """frame-args-v3 票 04:拿掉「對象欄當來源」的補丁後,除外←墓地、戻す:フィールド→手札
        仍歸得到(區域改由框架的來源給)。"""
        self.assertEqual(
            classify("①：自分の墓地のモンスター１体を除外する。"),
            [("除外", "已歸", ["除外←墓地"], "區域移動", "自分", None)])
        self.assertEqual(
            classify("①：相手フィールドのモンスター１体を持ち主の手札に戻す。"),
            [("戻す", "已歸", ["戻す:フィールド→手札"], "區域移動", "相手", "無")])

    def test_banished_state_zone_keeps_its_player(self):
        """code review:切出的「除外されている自分」仍讀得出玩家 自分。"""
        self.assertEqual(
            classify("①：除外されている自分のモンスター１体を手札に加える。"),
            [("加える", "已歸", ["加える:除外→手札"], "區域移動", "自分", "無")])

    def test_unmapped_zone_literal(self):
        """その中 對不上任何區域:需要區域的葉不匹配、不報錯,落預設葉;玩家欄留空。"""
        self.assertEqual(
            classify("①：デッキからカードを３枚めくり、その中からモンスター１体を"
                     "特殊召喚する。"),
            [("めくる", "已歸", ["めくる"], "處理程序", "無", None),
             ("特殊召喚", "已歸", ["特殊召喚"], "召喚", None, None)])


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
            [("除外", "已歸", ["除外(限制)"], "限制", "自分", None)])

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
             ("セット", "已歸", ["セット"], "區域移動", None, None)])

    def test_possible_is_affirmative(self):
        """破壊できる 與 破壊する 同葉。"""
        self.assertEqual(
            classify("①：このカードが召喚に成功した場合に発動できる。"
                     "相手フィールドのカード１枚を選んで破壊できる。"),
            [("成功", "不適用", [], None, None, None),
             ("選ぶ", "已歸", ["選ぶ"], "處理程序", None, None),
             ("破壊", "已歸", ["破壊@フィールド"], "破壊", None, None)])

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
             ("無効にする", "已歸", ["無効にする:発動"], "無効", None, None)])
        self.assertEqual(
            classify("①：その効果を無効にする。"),
            [("無効にする", "已歸", ["無効にする:効果"], "無効", None, None)])

    def test_unmatched_object_falls_to_default_leaf(self):
        """對象對不上任何關鍵詞(相手フィールドのカード)依所在落 破壊@フィールド;
        所在也沒有時落 破壊 的預設葉。"""
        self.assertEqual(
            classify("①：相手フィールドのカード１枚を破壊する。"),
            [("破壊", "已歸", ["破壊@フィールド"], "破壊", None, None)])
        self.assertEqual(
            classify("①：このカードを破壊する。"),
            [("破壊", "已歸", ["破壊"], "破壊", None, None)])


# 測試小樹:所在條件與來源條件各自只比自己那一欄
PLACE_TREE = [
    {"詞元": "破壊", "子": [{"來源": "場上"}, {"所在": "手牌"}, {"所在": "場上"}, {}]},
    {"詞元": "除外", "子": [{"所在": "墓地"}, {}]},
]


class TestPlaceCondition(unittest.TestCase):
    """category-tree-restart 票 01:所在成為葉條件(葉名 詞元@區域);來源條件只比來源、
    所在條件只比所在,「來源空著時讀所在」的橋接拿掉。"""

    def test_place_leaf(self):
        """真樹的 破壊@フィールド:無前綴與帶玩家前綴的場上都歸得到(本票先不分玩家)。"""
        for place in ("相手フィールド", "フィールド", "自分フィールド"):
            self.assertEqual(
                classify("①：%sのカード１枚を破壊する。" % place),
                [("破壊", "已歸", ["破壊@フィールド"], "破壊", None, None)], place)

    def test_place_does_not_match_source_leaf(self):
        """破壊 的所在 フィールド 不中 破壊←フィールド(來源葉),落 破壊@フィールド。"""
        self.assertEqual(
            classify("①：相手フィールドのカード１枚を破壊する。", tree=PLACE_TREE),
            [("破壊", "已歸", ["破壊@フィールド"], "破壊", None, None)])

    def test_source_does_not_match_place_leaf(self):
        """除外 的來源 墓地(受事者切分)不中 除外@墓地(所在葉),落預設葉。"""
        self.assertEqual(
            classify("①：自分の墓地のモンスター１体を除外する。", tree=PLACE_TREE),
            [("除外", "已歸", ["除外"], "除外", "自分", None)])

    def test_compound_place_takes_one_leaf_per_zone(self):
        """自分の手札・フィールド:依字面順序帶 @手札 與 @フィールド 兩葉;來源玩家欄空著。"""
        self.assertEqual(
            classify("①：自分の手札・フィールドのカード１枚を破壊する。", tree=PLACE_TREE),
            [("破壊", "已歸", ["破壊@手札", "破壊@フィールド"], "破壊", None, None)])

    def test_no_source_nor_place_takes_default_leaf(self):
        self.assertEqual(
            classify("①：このカードを破壊する。", tree=PLACE_TREE),
            [("破壊", "已歸", ["破壊"], "破壊", None, None)])


# 測試小樹:玩家條件綁在區域條件上(來源玩家/目的玩家/所在玩家)
PLAYER_TREE = [
    {"詞元": "破壊", "子": [
        {"所在": "手牌", "所在玩家": "自分"},
        {"所在": "場上", "所在玩家": "相手"},
        {"所在": "場上", "所在玩家": "自分"},
        {"所在": "場上", "所在玩家": "雙方"},
        {"所在": "場上", "所在玩家": "無"},
        {}]},
    {"詞元": "除外", "子": [{"來源": "墓地", "來源玩家": "相手"}, {"目的": "除外", "目的玩家": "無"},
                          {}]},
    {"詞元": "送る", "子": [{"目的": "墓地", "目的玩家": "無"}, {}]},
    {"詞元": "特殊召喚", "子": [{"來源": "墓地"}, {}]},
]


class TestPlayerCondition(unittest.TestCase):
    """category-tree-restart 票 02:玩家是可選葉條件,綁在它修飾的區域條件上;葉名以日文
    前綴連寫(自分、相手、お互いの,無不寫);沒宣告的葉不看玩家,來源玩家/目的玩家欄不變。"""

    def test_place_player_splits_leaves(self):
        for place, leaf in (("相手フィールド", "破壊@相手フィールド"),
                            ("自分フィールド", "破壊@自分フィールド"),
                            ("フィールド", "破壊@フィールド"),
                            ("お互いの魔法＆罠ゾーン", "破壊@お互いのフィールド")):
            self.assertEqual(
                classify("①：%sのカードを全て破壊する。" % place, tree=PLAYER_TREE),
                [("破壊", "已歸", [leaf], "破壊", None, None)], place)

    def test_compound_place_carries_player_to_each_leaf(self):
        self.assertEqual(
            classify("①：自分の手札・フィールドのカード１枚を破壊する。", tree=PLAYER_TREE),
            [("破壊", "已歸", ["破壊@自分手札", "破壊@自分フィールド"], "破壊", None, None)])

    def test_compound_place_with_mixed_players_takes_each_zones_player(self):
        """自分の墓地・相手フィールド:玩家逐區域取(墓地 自分、フィールド 相手),不因
        字面合起來是雙方就貼 お互いの;玩家合起來的雙方只留在玩家欄的語意裡。"""
        tree = [{"詞元": "破壊", "子": [
            {"所在": "墓地", "所在玩家": "自分"}, {"所在": "場上", "所在玩家": "相手"},
            {"所在": "場上", "所在玩家": "雙方"}, {}]}]
        self.assertEqual(
            classify("①：自分の墓地・相手フィールドのカードを全て破壊する。", tree=tree),
            [("破壊", "已歸", ["破壊@自分墓地", "破壊@相手フィールド"], "破壊", None, None)])
        self.assertEqual(
            classify("①：お互いのフィールド・墓地のカードを全て破壊する。", tree=tree),
            [("破壊", "已歸", ["破壊@お互いのフィールド", "破壊"], "破壊", None, None)])

    def test_no_place_literal_matches_no_player_leaf(self):
        """沒有所在字面(玩家 null)不中「無」:落預設葉。"""
        self.assertEqual(
            classify("①：このカードを破壊する。", tree=PLAYER_TREE),
            [("破壊", "已歸", ["破壊"], "破壊", None, None)])

    def test_source_player_leaf(self):
        """除外←相手墓地 只收 相手の墓地;自分の墓地 落預設葉;玩家欄照記。"""
        self.assertEqual(
            classify("①：相手の墓地のモンスター１体を除外する。", tree=PLAYER_TREE),
            [("除外", "已歸", ["除外←相手墓地"], "除外", "相手", None)])
        self.assertEqual(
            classify("①：自分の墓地のモンスター１体を除外する。", tree=PLAYER_TREE),
            [("除外", "已歸", ["除外"], "除外", "自分", None)])

    def test_undeclared_player_does_not_split(self):
        """特殊召喚←墓地 沒宣告玩家:相手の墓地 與 自分の墓地 同葉,來源玩家欄各記各的。"""
        for prefix, player in (("相手の", "相手"), ("自分の", "自分"), ("", "無")):
            self.assertEqual(
                classify("①：%s墓地からモンスター１体を特殊召喚する。" % prefix,
                         tree=PLAYER_TREE),
                [("特殊召喚", "已歸", ["特殊召喚←墓地"], "特殊召喚", player, None)], prefix)

    def test_inferred_goal_matches_no_player_leaf(self):
        """推得的目的(除外→除外)沒有字面、玩家 null:不中 除外→除外 的「無」葉;
        原文寫出的目的(墓地へ)才中 送る→墓地。"""
        self.assertEqual(
            classify("①：このカードを除外する。", tree=PLAYER_TREE),
            [("除外", "已歸", ["除外"], "除外", None, None)])
        self.assertEqual(
            classify("①：このカードを墓地へ送る。", tree=PLAYER_TREE),
            [("送る", "已歸", ["送る→墓地"], "送る", None, "無")])


class TestCardRollup(unittest.TestCase):
    """票 04:卡層彙總——一張卡的幾句原文 → 效果組與代價組的葉集合(各自去重、依樹序)。"""

    def test_cost_banish_stays_out_of_effect_group(self):
        """代價位的 除外 只進代價組;搜「除外」時不撈到自家代價除外的卡。"""
        self.assertEqual(
            categories.classify_card([
                "①：自分の墓地のモンスター１体を除外して発動できる。"
                "相手フィールドのモンスター１体を破壊する。"]),
            {"effect": ["破壊:モンスター"], "cost": ["除外←墓地"]})

    def test_groups_dedupe_and_follow_tree_order(self):
        """兩句各出的葉合併去重,依樹序排(特殊召喚 在 加える 前、←手札 在 ←墓地 前);
        條件位的框架不進任何組;代價位的 捨てる 只進代價組。"""
        self.assertEqual(
            categories.classify_card([
                "①：手札を１枚捨てて発動できる。デッキから「試作機」１体を手札に加える。",
                "②：このカードが墓地へ送られた場合に発動できる。"
                "手札・墓地から「試作機」１体を特殊召喚する。",
                "③：自分の墓地から「試作機」１体を特殊召喚する。"]),
            {"effect": ["特殊召喚←手札", "特殊召喚←墓地", "加える:デッキ→手札"],
             "cost": ["捨てる"]})


class TestTreeIntegrity(unittest.TestCase):
    """建置期檢查:真的類別樹通過完整性檢查(葉名唯一、每葉有詞元條件、大類非空、
    同詞元的葉不被前面較寬的葉蓋掉)。"""

    def test_real_tree_loads(self):
        tree = categories.load_tree()
        self.assertTrue(tree.leaves)

    def assertTreeError(self, tree, message):
        with self.assertRaises(categories.TreeError) as caught:
            categories.CategoryTree({"樹": tree})
        self.assertIn(message, str(caught.exception))

    def test_place_value_must_be_zone(self):
        self.assertTreeError([{"詞元": "破壊", "子": [{"所在": "フィールド"}, {}]}],
                             "不在區域七值")

    def test_player_value_must_be_one_of_four(self):
        self.assertTreeError([{"詞元": "破壊", "子": [{"所在": "場上", "所在玩家": "持ち主"}, {}]}],
                             "不在 自分/相手/雙方/無")

    def test_player_must_bind_to_existing_zone_condition(self):
        self.assertTreeError([{"詞元": "破壊", "子": [{"所在": "場上", "來源玩家": "相手"}, {}]}],
                             "來源玩家 綁在葉沒有的區域條件")

    def test_undeclared_player_leaf_covering_player_leaf(self):
        """沒宣告玩家的 破壊@フィールド 寫在前,蓋掉後面同區域的 破壊@相手フィールド。"""
        self.assertTreeError([{"詞元": "破壊", "子": [
            {"所在": "場上"}, {"所在": "場上", "所在玩家": "相手"}]}],
            "葉 破壊@相手フィールド 被前面的 破壊@フィールド 蓋掉")

    def test_wider_leaf_covering_place_leaf(self):
        """沒有所在條件的 破壊:モンスター 寫在前,蓋掉後面的 破壊@フィールド:モンスター。"""
        self.assertTreeError([{"詞元": "破壊", "子": [
            {"對象": ["モンスター"]}, {"所在": "場上", "對象": ["モンスター"]}]}],
            "葉 破壊@フィールド:モンスター 被前面的 破壊:モンスター 蓋掉")


if __name__ == "__main__":
    unittest.main()
