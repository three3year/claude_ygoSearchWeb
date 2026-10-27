# -*- coding: utf-8 -*-
"""動作類別歸組的行為測試(.scratch/action-categories 票 01〜)。

唯一接縫:一句效果句原文(帶同卡同段上文)→ 每個動作框架的類別紀錄
(categories.classify)。包住框架抽取接縫再接歸組,用真的分詞器、詞典、類別樹與
規則表;只斷言每個框架的(動作、狀態、葉清單、大類、來源玩家、目的玩家、路徑),不測
規則內部、不測樹怎麼存(預期路徑直接寫出,不依葉名查樹)。每個句型一條回歸例子——
修規則或改樹前先補一條會失敗的例子。例外:匹配機制本身(所在、玩家、關鍵詞三欄、大類
宣告、關鍵詞與所在兩軸並收、中類)另以測試小樹驗,免得真樹改葉表時把機制的例子一起
改掉;經同一接縫(classify 的 tree 參數),分詞器、詞典與規則表仍是真的
(category-tree-restart 票 01〜04、類別線票 06、category-middle-class 票 01)。

執行:PYTHONIOENCODING=utf-8 python -m unittest discover -s .scratch/effect-tokenize
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import categories  # noqa: E402


def classify(text, context="", tree=None):
    """類別紀錄 → 比對用的 tuple(動作, 狀態, 葉清單, 大類, 來源玩家, 目的玩家, 路徑);
    路徑每葉一條、與葉清單同序,節點名以 › 連寫(大類 › 中類或詞元 › 葉)。
    tree 給樹來源檔的「樹」清單時改用該測試小樹(驗真樹還沒開的葉條件)。"""
    if tree is not None:
        tree = categories.CategoryTree({"樹": tree})
    return [(r["action"], r["status"], r["leaves"], r["major"],
             r["source_player"], r["goal_player"], [" › ".join(p) for p in r["paths"]])
            for r in categories.classify(text, context, tree)]


class TestSkeleton(unittest.TestCase):
    """票 01:骨架——樹 → 規則匹配 → 類別紀錄。"""

    def test_revive_from_grave(self):
        self.assertEqual(
            classify("①：自分の墓地からモンスター１体を特殊召喚する。"),
            [("特殊召喚", "已歸", ["特殊召喚←墓地"], "召喚", "自分", None,
              ["召喚 › 特殊召喚 › 特殊召喚←墓地"])])

    def test_search_deck_to_hand_cost_and_effect(self):
        """代價位照貼(捨てる);檢索歸 加える:デッキ→手札。"""
        self.assertEqual(
            classify("①：手札を１枚捨てて発動できる。デッキから「試作機」１体を"
                     "手札に加える。"),
            [("捨てる", "已歸", ["捨てる"], "區域移動", "無", None, ["區域移動 › 捨てる"]),
             ("加える", "已歸", ["加える:デッキ→手札"], "區域移動", "無", "無",
              ["區域移動 › ←デッキ › 加える:デッキ→手札"])])

    def test_lemma_without_node_is_unplaced(self):
        """樹裡沒有這個詞元(長尾 振り直す):記未歸,沒有「其他」類。"""
        self.assertEqual(
            classify("①：サイコロを振り直す。"),
            [("振り直す", "未歸", [], None, None, None, [])])

    def test_unmatched_conditions_without_default_leaf(self):
        """得る 只有 コントロール/効果 兩個關鍵詞葉、沒有預設葉:對象對不上時記未歸。"""
        self.assertEqual(
            classify("①：相手は１０００LPを得る。"),
            [("得る", "未歸", [], None, None, None, [])])

    def test_lemma_node_without_children_is_default_leaf(self):
        self.assertEqual(
            classify("①：自分は１０００LP回復する。"),
            [("回復", "已歸", ["回復"], "LP・ダメージ", None, None, ["LP・ダメージ › LP › 回復"])])

    def test_condition_position_is_not_applicable(self):
        """條件位的框架不貼本樹(觸發事件軸另開線)。"""
        self.assertEqual(
            classify("①：このカードが召喚に成功した時に発動できる。"
                     "自分は１枚ドローする。"),
            [("成功", "不適用", [], None, None, None, []),
             ("ドロー", "已歸", ["ドロー"], "區域移動", None, None, ["區域移動 › ドロー"])])

    def test_condition_position_wins_over_matching_leaf(self):
        """「…が破壊された場合」的 破壊 是條件位:即使 破壊 有葉也不適用。"""
        self.assertEqual(
            classify("①：このカードが戦闘で破壊された場合に発動できる。"
                     "自分の墓地からモンスター１体を特殊召喚する。"),
            [("破壊", "不適用", [], None, None, None, []),
             ("特殊召喚", "已歸", ["特殊召喚←墓地"], "召喚", "自分", None,
              ["召喚 › 特殊召喚 › 特殊召喚←墓地"])])

    def test_frames_inside_options(self):
        """出自選項(●)的框架照貼。"""
        self.assertEqual(
            classify("①：以下の効果から１つを選択して発動できる。"
                     "●自分の墓地からモンスター１体を特殊召喚する。"
                     "●相手フィールドのカード１枚を破壊する。"),
            [("選択", "不適用", [], None, None, None, []),
             ("特殊召喚", "已歸", ["特殊召喚←墓地"], "召喚", "自分", None,
              ["召喚 › 特殊召喚 › 特殊召喚←墓地"]),
             ("破壊", "已歸", ["破壊@相手フィールド"], "破壊", None, None,
              ["破壊 › 破壊@相手フィールド"])])


class TestZonesAndPlayers(unittest.TestCase):
    """票 02:來源/目的字面映成(玩家, 區域);玩家不進葉、複合字面一框架多葉。"""

    def test_compound_source_takes_one_leaf_per_zone(self):
        """手札・墓地から:依字面順序帶兩葉,大類仍一個。"""
        self.assertEqual(
            classify("①：手札・墓地から「試作機」１体を特殊召喚する。"),
            [("特殊召喚", "已歸", ["特殊召喚←手札", "特殊召喚←墓地"], "召喚",
              "無", None, ["召喚 › 特殊召喚 › 特殊召喚←手札", "召喚 › 特殊召喚 › 特殊召喚←墓地"])])

    def test_player_prefix_does_not_split_leaf(self):
        """相手の墓地から 與 自分の墓地から 同葉,玩家欄不同;目的 自分フィールド 照記。"""
        self.assertEqual(
            classify("①：相手の墓地からモンスター１体を選んで自分フィールドに"
                     "特殊召喚する。"),
            [("選ぶ", "已歸", ["選ぶ"], "處理程序", "相手", None, ["處理程序 › 選ぶ"]),
             ("特殊召喚", "已歸", ["特殊召喚←墓地"], "召喚", "相手", "自分",
              ["召喚 › 特殊召喚 › 特殊召喚←墓地"])])

    def test_either_player_is_both(self):
        """自分または相手の(與 自分か相手の、自分・相手の、お互いの)記雙方。"""
        self.assertEqual(
            classify("①：自分または相手の墓地からモンスター１体を選んで"
                     "自分フィールドに特殊召喚する。"),
            [("選ぶ", "已歸", ["選ぶ"], "處理程序", "雙方", None, ["處理程序 › 選ぶ"]),
             ("特殊召喚", "已歸", ["特殊召喚←墓地"], "召喚", "雙方", "自分",
              ["召喚 › 特殊召喚 › 特殊召喚←墓地"])])
        for prefix in ("自分か相手の", "自分・相手の"):
            self.assertEqual(
                classify("①：%s墓地からモンスター１体を特殊召喚する。" % prefix),
                [("特殊召喚", "已歸", ["特殊召喚←墓地"], "召喚", "雙方", None,
                  ["召喚 › 特殊召喚 › 特殊召喚←墓地"])],
                prefix)

    def test_deck_top_is_deck(self):
        """デッキの上(牌組頂/底)歸牌組;お互いの 記雙方、無前綴的 墓地 記無。"""
        self.assertEqual(
            classify("①：お互いのデッキの上からカードを１枚墓地へ送る。"),
            [("送る", "已歸", ["送る:デッキ→墓地"], "區域移動", "雙方", "無",
              ["區域移動 › ←デッキ › 送る:デッキ→墓地"])])

    def test_patient_zone_from_frame_source_or_place(self):
        """frame-args-v3 票 04:受事者片語裡的區域由框架抽取切出——移動類(除外)記來源,
        其餘(破壊)記所在;所在不當來源讀(category-tree-restart 票 01),來源玩家欄只記來源
        字面的玩家;原文有來源字面時對象欄不切。"""
        self.assertEqual(
            classify("①：墓地のこのカードを除外して発動できる。"
                     "相手フィールドのカード１枚を破壊する。"),
            [("除外", "已歸", ["除外←墓地"], "區域移動", "無", None,
              ["區域移動 › ←墓地 › 除外←墓地"]),
             ("破壊", "已歸", ["破壊@相手フィールド"], "破壊", None, None,
              ["破壊 › 破壊@相手フィールド"])])
        self.assertEqual(
            classify("①：自分の手札から「墓地のモンスター」１体を特殊召喚する。"),
            [("特殊召喚", "已歸", ["特殊召喚←手札"], "召喚", "自分", None,
              ["召喚 › 特殊召喚 › 特殊召喚←手札"])])

    def test_patient_zone_compound_and_described(self):
        """受事者的複合區域(手札・フィールドのこのカード)帶多葉;描述裡有「・」
        (魔法・罠カード)也切得出區域。"""
        self.assertEqual(
            classify("①：手札・フィールドのこのカードを墓地へ送って発動できる。"
                     "相手フィールドの魔法・罠カード１枚を破壊する。"),
            [("送る", "已歸", ["送る:手札→墓地", "送る:フィールド→墓地"], "區域移動",
              "無", "無",
              ["區域移動 › ←手札 › 送る:手札→墓地", "區域移動 › ←フィールド › 送る:フィールド→墓地"]),
             ("破壊", "已歸", ["破壊:魔法カード/罠カード", "破壊@相手フィールド"], "破壊",
              None, None, ["破壊 › 破壊:魔法カード/罠カード", "破壊 › 破壊@相手フィールド"])])

    def test_moved_patient_zone_still_reaches_source_leaves(self):
        """frame-args-v3 票 04:拿掉「對象欄當來源」的補丁後,除外←墓地、戻す:フィールド→手札
        仍歸得到(區域改由框架的來源給)。"""
        self.assertEqual(
            classify("①：自分の墓地のモンスター１体を除外する。"),
            [("除外", "已歸", ["除外←墓地"], "區域移動", "自分", None,
              ["區域移動 › ←墓地 › 除外←墓地"])])
        self.assertEqual(
            classify("①：相手フィールドのモンスター１体を持ち主の手札に戻す。"),
            [("戻す", "已歸", ["戻す:フィールド→手札"], "區域移動", "相手", "相對",
              ["區域移動 › ←フィールド › 戻す:フィールド→手札"])])

    def test_banished_state_zone_keeps_its_player(self):
        """code review:切出的「除外されている自分」仍讀得出玩家 自分。"""
        self.assertEqual(
            classify("①：除外されている自分のモンスター１体を手札に加える。"),
            [("加える", "已歸", ["加える:除外→手札"], "區域移動", "自分", "無",
              ["區域移動 › ←除外 › 加える:除外→手札"])])

    def test_unmapped_zone_literal(self):
        """その中 對不上任何區域:需要區域的葉不匹配、不報錯,落預設葉;玩家欄留空。"""
        self.assertEqual(
            classify("①：デッキからカードを３枚めくり、その中からモンスター１体を"
                     "特殊召喚する。"),
            [("めくる", "已歸", ["めくる"], "處理程序", "無", None, ["處理程序 › めくる"]),
             ("特殊召喚", "已歸", ["特殊召喚"], "召喚", None, None, ["召喚 › 特殊召喚"])])


class TestNegationAndKeywords(unittest.TestCase):
    """票 03:否定極性分耐性/限制(述語形)、可能視同肯定、對象關鍵詞分葉。"""

    def test_not_destroyed_is_resistance(self):
        self.assertEqual(
            classify("①：このカードは効果では破壊されない。"),
            [("破壊", "已歸", ["破壊(耐性)"], "耐性", None, None, ["耐性 › 破壊(耐性)"])])

    def test_not_targeted_is_resistance(self):
        self.assertEqual(
            classify("①：このカードは相手の効果の対象にならない。"),
            [("対象になる", "已歸", ["対象になる(耐性)"], "耐性", None, None,
              ["耐性 › 対象になる(耐性)"])])

    def test_unaffected_is_resistance(self):
        """受けない(述語形是一般否定,但 受ける 的否定就是不受影響)歸耐性。"""
        self.assertEqual(
            classify("①：このカードは相手の効果を受けない。"),
            [("受ける", "已歸", ["受ける(耐性)"], "耐性", None, None, ["耐性 › 受ける(耐性)"])])

    def test_cannot_is_restriction(self):
        self.assertEqual(
            classify("①：相手は自分の墓地のカードを除外できない。"),
            [("除外", "已歸", ["除外(限制)"], "限制", "自分", None, ["限制 › 除外(限制)"])])

    def test_godan_potential_is_restriction(self):
        """行えない 是 行う 的可能否定。"""
        self.assertEqual(
            classify("①：相手はバトルフェイズを行えない。"),
            [("行う", "已歸", ["行う(限制)"], "限制", None, None, ["限制 › 行う(限制)"])])

    def test_plain_negation_is_unplaced(self):
        """送らず 這類一般否定不是耐性也不是限制:沒有節點,記未歸。"""
        self.assertEqual(
            classify("①：発動後、このカードは墓地へ送らず、そのままセットする。"),
            [("送る", "未歸", [], None, None, "無", []),
             ("セット", "已歸", ["セット"], "區域移動", None, None, ["區域移動 › セット"])])

    def test_possible_is_affirmative(self):
        """破壊できる 與 破壊する 同葉。"""
        self.assertEqual(
            classify("①：このカードが召喚に成功した場合に発動できる。"
                     "相手フィールドのカード１枚を選んで破壊できる。"),
            [("成功", "不適用", [], None, None, None, []),
             ("選ぶ", "已歸", ["選ぶ@相手フィールド"], "處理程序", None, None,
              ["處理程序 › 選ぶ › 選ぶ@相手フィールド"]),
             ("破壊", "已歸", ["破壊@相手フィールド"], "破壊", None, None,
              ["破壊 › 破壊@相手フィールド"])])

    def test_destroy_spell_trap_and_monster_split(self):
        """關鍵詞葉之外,所在葉 破壊@相手フィールド 並收(票 06 草案的兩軸並收)。"""
        self.assertEqual(
            classify("①：相手フィールドの魔法・罠カード１枚を破壊する。"),
            [("破壊", "已歸", ["破壊:魔法カード/罠カード", "破壊@相手フィールド"], "破壊",
              None, None, ["破壊 › 破壊:魔法カード/罠カード", "破壊 › 破壊@相手フィールド"])])
        self.assertEqual(
            classify("①：相手フィールドの罠カード１枚を破壊する。"),
            [("破壊", "已歸", ["破壊:魔法カード/罠カード", "破壊@相手フィールド"], "破壊",
              None, None, ["破壊 › 破壊:魔法カード/罠カード", "破壊 › 破壊@相手フィールド"])])
        self.assertEqual(
            classify("①：相手フィールドのモンスター１体を破壊する。"),
            [("破壊", "已歸", ["破壊:モンスター", "破壊@相手フィールド"], "破壊", None, None,
              ["破壊 › 破壊:モンスター", "破壊 › 破壊@相手フィールド"])])

    def test_negate_activation_and_effect_split(self):
        self.assertEqual(
            classify("①：相手が魔法・罠カードを発動した時に発動できる。"
                     "その発動を無効にする。"),
            [("発動", "不適用", [], None, None, None, []),
             ("無効にする", "已歸", ["無効にする:発動"], "無効", None, None,
              ["無効 › 無効にする › 無効にする:発動"])])
        self.assertEqual(
            classify("①：その効果を無効にする。"),
            [("無効にする", "已歸", ["無効にする:効果"], "無効", None, None,
              ["無効 › 無効にする › 無効にする:効果"])])

    def test_unmatched_object_falls_to_default_leaf(self):
        """對象對不上任何關鍵詞(相手フィールドのカード)依所在落 破壊@相手フィールド;
        所在也沒有時落 破壊 的預設葉。"""
        self.assertEqual(
            classify("①：相手フィールドのカード１枚を破壊する。"),
            [("破壊", "已歸", ["破壊@相手フィールド"], "破壊", None, None,
              ["破壊 › 破壊@相手フィールド"])])
        self.assertEqual(
            classify("①：このカードを破壊する。"),
            [("破壊", "已歸", ["破壊"], "破壊", None, None, ["破壊"])])


# 測試小樹:所在條件與來源條件各自只比自己那一欄
PLACE_TREE = [
    {"詞元": "破壊", "子": [{"來源": "場上"}, {"所在": "手牌"}, {"所在": "場上"}, {}]},
    {"詞元": "除外", "子": [{"所在": "墓地"}, {}]},
]


class TestPlaceCondition(unittest.TestCase):
    """category-tree-restart 票 01:所在成為葉條件(葉名 詞元@區域);來源條件只比來源、
    所在條件只比所在,「來源空著時讀所在」的橋接拿掉。"""

    def test_place_leaf(self):
        """真樹(票 06 草案)的 破壊 依所在玩家分葉:相手/自分/お互いの 各一葉,無前綴落
        破壊@フィールド。"""
        for place, leaf in (("相手フィールド", "破壊@相手フィールド"),
                            ("自分フィールド", "破壊@自分フィールド"),
                            ("お互いのフィールド", "破壊@お互いのフィールド"),
                            ("フィールド", "破壊@フィールド")):
            self.assertEqual(
                classify("①：%sのカード１枚を破壊する。" % place),
                [("破壊", "已歸", [leaf], "破壊", None, None, ["破壊 › " + leaf])], place)

    def test_place_does_not_match_source_leaf(self):
        """破壊 的所在 フィールド 不中 破壊←フィールド(來源葉),落 破壊@フィールド。"""
        self.assertEqual(
            classify("①：相手フィールドのカード１枚を破壊する。", tree=PLACE_TREE),
            [("破壊", "已歸", ["破壊@フィールド"], "破壊", None, None, ["破壊 › 破壊@フィールド"])])

    def test_source_does_not_match_place_leaf(self):
        """除外 的來源 墓地(受事者切分)不中 除外@墓地(所在葉),落預設葉。"""
        self.assertEqual(
            classify("①：自分の墓地のモンスター１体を除外する。", tree=PLACE_TREE),
            [("除外", "已歸", ["除外"], "除外", "自分", None, ["除外"])])

    def test_compound_place_takes_one_leaf_per_zone(self):
        """自分の手札・フィールド:依字面順序帶 @手札 與 @フィールド 兩葉;來源玩家欄空著。"""
        self.assertEqual(
            classify("①：自分の手札・フィールドのカード１枚を破壊する。", tree=PLACE_TREE),
            [("破壊", "已歸", ["破壊@手札", "破壊@フィールド"], "破壊", None, None,
              ["破壊 › 破壊@手札", "破壊 › 破壊@フィールド"])])

    def test_no_source_nor_place_takes_default_leaf(self):
        self.assertEqual(
            classify("①：このカードを破壊する。", tree=PLACE_TREE),
            [("破壊", "已歸", ["破壊"], "破壊", None, None, ["破壊"])])


# 測試小樹:玩家條件綁在區域條件上(來源玩家/目的玩家/所在玩家)
PLAYER_TREE = [
    {"詞元": "破壊", "子": [
        {"所在": "手牌", "所在玩家": "自分"},
        {"所在": "場上", "所在玩家": "相手"},
        {"所在": "場上", "所在玩家": "自分"},
        {"所在": "場上", "所在玩家": "雙方"},
        {"所在": "場上"},
        {}]},
    {"詞元": "除外", "子": [{"來源": "墓地", "來源玩家": "相手"}, {}]},
    {"詞元": "特殊召喚", "子": [{"來源": "墓地"}, {"目的": "場上", "目的玩家": "自分"}, {}]},
]


class TestPlayerCondition(unittest.TestCase):
    """category-tree-restart 票 02:玩家是可選葉條件,綁在它修飾的區域條件上;葉名以日文
    前綴連寫(自分、相手、お互いの);可宣告的值只有 自分/相手/雙方(2026-10-19 站主裁定
    不切「無」),沒寫玩家的落沒宣告玩家的葉;沒宣告的葉不看玩家,來源玩家/目的玩家欄不變。"""

    def test_place_player_splits_leaves(self):
        """相手/自分/お互いの 各一葉;沒寫玩家的 フィールド 落後面沒宣告玩家的 破壊@フィールド。"""
        for place, leaf in (("相手フィールド", "破壊@相手フィールド"),
                            ("自分フィールド", "破壊@自分フィールド"),
                            ("フィールド", "破壊@フィールド"),
                            ("お互いの魔法＆罠ゾーン", "破壊@お互いのフィールド")):
            self.assertEqual(
                classify("①：%sのカードを全て破壊する。" % place, tree=PLAYER_TREE),
                [("破壊", "已歸", [leaf], "破壊", None, None, ["破壊 › " + leaf])], place)

    def test_compound_place_carries_player_to_each_leaf(self):
        self.assertEqual(
            classify("①：自分の手札・フィールドのカード１枚を破壊する。", tree=PLAYER_TREE),
            [("破壊", "已歸", ["破壊@自分手札", "破壊@自分フィールド"], "破壊", None, None,
              ["破壊 › 破壊@自分手札", "破壊 › 破壊@自分フィールド"])])

    def test_compound_place_with_mixed_players_takes_each_zones_player(self):
        """自分の墓地・相手フィールド:玩家逐區域取(墓地 自分、フィールド 相手),不因
        字面合起來是雙方就貼 お互いの;玩家合起來的雙方只留在玩家欄的語意裡。"""
        tree = [{"詞元": "破壊", "子": [
            {"所在": "墓地", "所在玩家": "自分"}, {"所在": "場上", "所在玩家": "相手"},
            {"所在": "場上", "所在玩家": "雙方"}, {}]}]
        self.assertEqual(
            classify("①：自分の墓地・相手フィールドのカードを全て破壊する。", tree=tree),
            [("破壊", "已歸", ["破壊@自分墓地", "破壊@相手フィールド"], "破壊", None, None,
              ["破壊 › 破壊@自分墓地", "破壊 › 破壊@相手フィールド"])])
        self.assertEqual(
            classify("①：お互いのフィールド・墓地のカードを全て破壊する。", tree=tree),
            [("破壊", "已歸", ["破壊@お互いのフィールド", "破壊"], "破壊", None, None,
              ["破壊 › 破壊@お互いのフィールド", "破壊"])])

    def test_relative_prefix_takes_undeclared_leaf(self):
        """相手は自身のフィールド:自身の 記 相對、不算明示玩家,不中 破壊@相手フィールド,
        落沒宣告玩家的 破壊@フィールド;來源字面是 自身の墓地 時不中 除外←相手墓地、落預設葉,
        來源玩家欄記 相對(2026-10-27 站主裁定另記一值)。"""
        self.assertEqual(
            classify("①：相手は自身のフィールドのカード１枚を破壊する。", tree=PLAYER_TREE),
            [("破壊", "已歸", ["破壊@フィールド"], "破壊", None, None, ["破壊 › 破壊@フィールド"])])
        self.assertEqual(
            classify("①：相手は自身の墓地のモンスター１体を除外する。", tree=PLAYER_TREE),
            [("除外", "已歸", ["除外"], "除外", "相對", None, ["除外"])])

    def test_no_place_literal_takes_default_leaf(self):
        """沒有所在字面:區域條件都不中,落預設葉。"""
        self.assertEqual(
            classify("①：このカードを破壊する。", tree=PLAYER_TREE),
            [("破壊", "已歸", ["破壊"], "破壊", None, None, ["破壊"])])

    def test_source_player_leaf(self):
        """除外←相手墓地 只收 相手の墓地;自分の墓地 落預設葉;玩家欄照記。"""
        self.assertEqual(
            classify("①：相手の墓地のモンスター１体を除外する。", tree=PLAYER_TREE),
            [("除外", "已歸", ["除外←相手墓地"], "除外", "相手", None, ["除外 › 除外←相手墓地"])])
        self.assertEqual(
            classify("①：自分の墓地のモンスター１体を除外する。", tree=PLAYER_TREE),
            [("除外", "已歸", ["除外"], "除外", "自分", None, ["除外"])])

    def test_undeclared_player_does_not_split(self):
        """特殊召喚←墓地 沒宣告玩家:相手の墓地 與 自分の墓地 同葉,來源玩家欄各記各的。"""
        for prefix, player in (("相手の", "相手"), ("自分の", "自分"), ("", "無")):
            self.assertEqual(
                classify("①：%s墓地からモンスター１体を特殊召喚する。" % prefix,
                         tree=PLAYER_TREE),
                [("特殊召喚", "已歸", ["特殊召喚←墓地"], "特殊召喚", player, None,
                  ["特殊召喚 › 特殊召喚←墓地"])], prefix)

    def test_inferred_goal_matches_no_player_leaf(self):
        """推得的目的(特殊召喚→フィールド)沒有字面、玩家 null:不中 特殊召喚→自分フィールド,
        落預設葉;原文寫出 自分フィールドに 才中。"""
        self.assertEqual(
            classify("①：手札からモンスター１体を特殊召喚する。", tree=PLAYER_TREE),
            [("特殊召喚", "已歸", ["特殊召喚"], "特殊召喚", "無", None, ["特殊召喚"])])
        self.assertEqual(
            classify("①：手札からモンスター１体を自分フィールドに特殊召喚する。",
                     tree=PLAYER_TREE),
            [("特殊召喚", "已歸", ["特殊召喚→自分フィールド"], "特殊召喚", "無", "自分",
              ["特殊召喚 › 特殊召喚→自分フィールド"])])


# 測試小樹:關鍵詞讀 對象→主語→主題 的第一個有值的欄,多關鍵詞多葉
KEYWORD_TREE = [
    {"詞元": "アップ", "子": [{"關鍵詞": ["攻撃力"]}, {"關鍵詞": ["守備力"]}, {}]},
    {"詞元": "になる", "子": [{"關鍵詞": ["攻撃力"]}, {"關鍵詞": ["守備力"]}, {}]},
    {"詞元": "にする", "子": [{"關鍵詞": ["レベル"]}, {}]},
    {"詞元": "破壊", "子": [{"關鍵詞": ["このカード"]}, {}]},
    {"詞元": "破壊", "極性類": "耐性", "子": [{"關鍵詞": ["モンスター"]}, {}]},
]


class TestKeywordFields(unittest.TestCase):
    """category-tree-restart 票 03:葉的「關鍵詞」條件依 對象→主語→主題 找第一個有值的欄、
    只比那一欄(主題含回填延續的值);同時命中幾個關鍵詞葉就帶幾個葉(依樹序)。"""

    def test_object_hit(self):
        self.assertEqual(
            classify("①：そのモンスターのレベルを４にする。", tree=KEYWORD_TREE),
            [("にする", "已歸", ["にする:レベル"], "にする", None, None,
              ["にする › にする:レベル"])])

    def test_subject_hit(self):
        self.assertEqual(
            classify("①：そのモンスターの守備力が０になり、効果は無効化される。",
                     tree=KEYWORD_TREE),
            [("になる", "已歸", ["になる:守備力"], "になる", None, None,
              ["になる › になる:守備力"]),
             ("無効化", "未歸", [], None, None, None, [])])

    def test_topic_hit(self):
        self.assertEqual(
            classify("①：このカードの攻撃力は１００００になる。", tree=KEYWORD_TREE),
            [("になる", "已歸", ["になる:攻撃力"], "になる", None, None,
              ["になる › になる:攻撃力"])])

    def test_backfilled_topic_hit(self):
        """「マリンセス」モンスター…破壊されない 的主題由回填延續而來,照樣比對。"""
        self.assertEqual(
            classify("①：自分フィールドの「マリンセス」モンスターの攻撃力は５００アップし、"
                     "効果では破壊されない。", tree=KEYWORD_TREE),
            [("アップ", "已歸", ["アップ:攻撃力"], "アップ", None, None,
              ["アップ › アップ:攻撃力"]),
             ("破壊", "已歸", ["破壊:モンスター(耐性)"], "破壊(耐性)", None, None,
              ["破壊(耐性) › 破壊:モンスター(耐性)"])])

    def test_object_present_ignores_topic(self):
        """有對象(モンスター)就只比對象:主題 このカード 不看,落預設葉。"""
        self.assertEqual(
            classify("①：このカードは相手フィールドのモンスターを全て破壊する。",
                     tree=KEYWORD_TREE),
            [("破壊", "已歸", ["破壊"], "破壊", None, None, ["破壊"])])

    def test_no_keyword_hit_takes_default_leaf(self):
        self.assertEqual(
            classify("①：そのモンスターの攻撃力を０にする。", tree=KEYWORD_TREE),
            [("にする", "已歸", ["にする"], "にする", None, None, ["にする"])])

    def test_all_three_fields_empty_takes_default_leaf(self):
        """對象、主語、主題都空著:關鍵詞葉不中,落預設葉。"""
        self.assertEqual(
            classify("①：ターン終了時まで１０００アップする。", tree=KEYWORD_TREE),
            [("アップ", "已歸", ["アップ"], "アップ", None, None, ["アップ"])])

    def test_two_keywords_take_two_leaves(self):
        """攻撃力・守備力 同時命中兩個關鍵詞葉:搜守備力上升也撈得到攻守同升的卡。"""
        self.assertEqual(
            classify("①：自分フィールドのモンスターの攻撃力・守備力が１０００アップする。",
                     tree=KEYWORD_TREE),
            [("アップ", "已歸", ["アップ:攻撃力", "アップ:守備力"], "アップ", None, None,
              ["アップ › アップ:攻撃力", "アップ › アップ:守備力"])])

    def test_activated_effect_takes_both_negate_leaves(self):
        """真樹:その発動した効果 同時帶 無効にする:効果 與 :発動,不再依樹裡順序先到先得。"""
        self.assertEqual(
            classify("①：その発動した効果を無効にする。"),
            [("無効にする", "已歸", ["無効にする:効果", "無効にする:発動"], "無効", None, None,
              ["無効 › 無効にする › 無効にする:効果", "無効 › 無効にする › 無効にする:発動"])])


# 測試小樹:關鍵詞葉與區域葉兩軸並收
TWO_AXES_TREE = [
    {"詞元": "破壊", "子": [
        {"關鍵詞": ["モンスター"]},
        {"所在": "場上", "所在玩家": "相手"},
        {"所在": "場上"},
        {}]},
]


class TestKeywordAndZoneAxes(unittest.TestCase):
    """票 06(2026-10-19 站主裁定):關鍵詞葉命中時,樹序第一個條件相符、不帶關鍵詞的葉若帶所在
    條件也收——「做什麼」與「在哪裡」兩軸並收;來源/目的葉不並收,預設葉只在都沒中時才收。"""

    def test_keyword_hit_also_takes_place_leaf(self):
        """相手フィールドのモンスター:破壊:モンスター 與 破壊@相手フィールド 都帶,
        搜「破壞對手場上」撈得到破壞對手怪獸的卡。"""
        self.assertEqual(
            classify("①：相手フィールドのモンスター１体を破壊する。", tree=TWO_AXES_TREE),
            [("破壊", "已歸", ["破壊:モンスター", "破壊@相手フィールド"], "破壊", None, None,
              ["破壊 › 破壊:モンスター", "破壊 › 破壊@相手フィールド"])])

    def test_keyword_hit_without_zone_skips_default_leaf(self):
        """沒有所在:只帶關鍵詞葉,預設葉不收。"""
        self.assertEqual(
            classify("①：そのモンスターを破壊する。", tree=TWO_AXES_TREE),
            [("破壊", "已歸", ["破壊:モンスター"], "破壊", None, None, ["破壊 › 破壊:モンスター"])])

    def test_no_keyword_hit_takes_zone_leaf_only(self):
        self.assertEqual(
            classify("①：フィールドのカード１枚を破壊する。", tree=TWO_AXES_TREE),
            [("破壊", "已歸", ["破壊@フィールド"], "破壊", None, None, ["破壊 › 破壊@フィールド"])])

    def test_goal_leaf_is_not_paired_with_keyword_leaf(self):
        """真樹:目的葉是移動的訖點、不並收——カウンター 放在場上怪獸身上,不帶 置く→フィールド。"""
        self.assertEqual(
            classify("①：相手フィールドの表側表示モンスター１体に"
                     "〈乙女〉カウンターを１つ置く。"),
            [("置く", "已歸", ["置く:カウンター"], "區域移動", None, "相手",
              ["區域移動 › 置く › 置く:カウンター"])])


class TestDraftTree(unittest.TestCase):
    """票 06 重起草案的真樹(待站主裁定):になる/アップ 系的關鍵詞葉與大類、非移動類的
    所在/玩家葉、否定葉帶所在。"""

    def test_up_family_keyword_leaves(self):
        self.assertEqual(
            classify("①：自分フィールドのモンスターの攻撃力・守備力は５００アップする。"),
            [("アップ", "已歸", ["アップ:攻撃力", "アップ:守備力"], "數值", None, None,
              ["數值 › 攻撃力 › アップ:攻撃力", "數值 › 守備力 › アップ:守備力"])])
        self.assertEqual(
            classify("①：このカードのレベルを１つ上げる。"),
            [("上げる", "已歸", ["上げる:レベル"], "數值", None, None,
              ["數值 › レベル › 上げる:レベル"])])

    def test_naru_family_keywords_pick_major(self):
        """半分になる:ダメージ/LP 歸 LP・ダメージ、にする:レベル 歸 數值。"""
        self.assertEqual(
            classify("①：その戦闘で発生する相手への戦闘ダメージは半分になる。"),
            [("半分になる", "已歸", ["半分になる:ダメージ/LP"], "LP・ダメージ", None, None,
              ["LP・ダメージ › ダメージ › 半分になる:ダメージ/LP"])])
        self.assertEqual(
            classify("①：そのモンスターのレベルを４にする。"),
            [("にする", "已歸", ["にする:レベル"], "數值", None, None,
              ["數值 › レベル › にする:レベル"])])

    def test_place_player_leaves_on_non_move_lemmas(self):
        self.assertEqual(
            classify("①：相手の手札をランダムに１枚選んで墓地へ捨てる。"),
            [("選ぶ", "已歸", ["選ぶ@相手手札"], "處理程序", None, None,
              ["處理程序 › 選ぶ › 選ぶ@相手手札"]),
             ("捨てる", "已歸", ["捨てる"], "區域移動", "相手", "無", ["區域移動 › 捨てる"])])
        self.assertEqual(
            classify("①：自分の手札・フィールドのモンスターを融合素材とし、"
                     "融合モンスター１体を融合召喚する。"),
            [("融合素材とする", "已歸", ["融合素材とする@自分フィールド", "融合素材とする@自分手札"],
              "素材", None, None,
              ["素材 › 融合素材とする › 融合素材とする@自分フィールド",
               "素材 › 融合素材とする › 融合素材とする@自分手札"]),
             ("融合召喚", "已歸", ["融合召喚"], "召喚", None, None, ["召喚 › 融合召喚"])])

    def test_negation_leaf_with_place_player(self):
        self.assertEqual(
            classify("①：自分フィールドのモンスターは効果では破壊されない。"),
            [("破壊", "已歸", ["破壊@自分フィールド(耐性)"], "耐性", None, None,
              ["耐性 › 破壊(耐性) › 破壊@自分フィールド(耐性)"])])

    def test_threshold_leaves_that_duplicate_lemma_or_keyword(self):
        """2026-10-27 站主裁定照門檻開的三葉:指定@フィールド、S素材とする@自分フィールド
        (葉幾乎等於詞元)、得る@相手フィールド(與 得る:コントロール 兩軸並收)。"""
        self.assertEqual(
            classify("①：使用していない相手のモンスターゾーンを１ヵ所指定する。"),
            [("指定", "已歸", ["指定@フィールド"], "處理程序", None, None,
              ["處理程序 › 指定 › 指定@フィールド"])])
        self.assertEqual(
            classify("①：自分フィールドの「竜星」モンスターのみをS素材としてS召喚する。"),
            [("S素材とする", "已歸", ["S素材とする@自分フィールド"], "素材", None, None,
              ["素材 › S素材とする › S素材とする@自分フィールド"]),
             ("S召喚", "已歸", ["S召喚"], "召喚", None, None, ["召喚 › S召喚"])])
        self.assertEqual(
            classify("①：相手フィールドのモンスター１体のコントロールをエンドフェイズまで得る。"),
            [("得る", "已歸", ["得る:コントロール", "得る@相手フィールド"], "規則改寫", None, None,
              ["規則改寫 › 得る › 得る:コントロール", "規則改寫 › 得る › 得る@相手フィールド"])])

    def test_relative_prefix_player_column(self):
        """持ち主の手札 的目的玩家記 相對(2026-10-27 站主裁定另記一值),葉照舊不分。"""
        self.assertEqual(
            classify("①：相手フィールドの魔法・罠カードを全て持ち主の手札に戻す。"),
            [("戻す", "已歸", ["戻す:フィールド→手札"], "區域移動", "相手", "相對",
              ["區域移動 › ←フィールド › 戻す:フィールド→手札"])])


class TestMajorByLeaf(unittest.TestCase):
    """category-tree-restart 票 04:葉可宣告自己掛的大類(沒宣告取詞元節點的本家大類),
    同一詞元的葉可以在不同大類;多葉跨大類時框架的大類取第一葉(樹序)的。"""

    def test_same_lemma_leaves_in_three_majors(self):
        """真樹的 になる:攻撃力/:守備力 沒宣告、取本家 數值;:ダメージ/LP 宣告 LP・ダメージ、
        :ドロー/枚数/回数 宣告 規則改寫。"""
        self.assertEqual(
            classify("①：このカードの攻撃力は１００００になる。"),
            [("になる", "已歸", ["になる:攻撃力"], "數值", None, None,
              ["數值 › 攻撃力 › になる:攻撃力"])])
        self.assertEqual(
            classify("①：そのモンスターの守備力が０になり、効果は無効化される。"),
            [("になる", "已歸", ["になる:守備力"], "數值", None, None,
              ["數值 › 守備力 › になる:守備力"]),
             ("無効化", "已歸", ["無効化"], "無効", None, None, ["無効 › 無効化"])])
        self.assertEqual(
            classify("①：その戦闘で発生する自分への戦闘ダメージは０になる。"),
            [("になる", "已歸", ["になる:ダメージ/LP"], "LP・ダメージ", None, None,
              ["LP・ダメージ › ダメージ › になる:ダメージ/LP"])])
        self.assertEqual(
            classify("①：自分の通常のドローは２枚になる。"),
            [("になる", "已歸", ["になる:ドロー/枚数/回数"], "規則改寫", None, None,
              ["規則改寫 › になる › になる:ドロー/枚数/回数"])])

    def test_multi_leaf_across_majors_takes_first_leafs_major(self):
        tree = [
            {"大類": "甲", "子": [{"詞元": "になる", "子": [
                {"關鍵詞": ["攻撃力"], "大類": "乙"}, {"關鍵詞": ["守備力"]}, {}]}]},
            {"大類": "乙", "子": [{"詞元": "アップ"}]},
        ]
        self.assertEqual(
            classify("①：そのモンスターの攻撃力・守備力が０になる。", tree=tree),
            [("になる", "已歸", ["になる:攻撃力", "になる:守備力"], "乙", None, None,
              ["乙 › になる › になる:攻撃力", "甲 › になる › になる:守備力"])])
        self.assertEqual(
            classify("①：そのモンスターの守備力が０になる。", tree=tree),
            [("になる", "已歸", ["になる:守備力"], "甲", None, None,
              ["甲 › になる › になる:守備力"])])


# 測試小樹:中類(大類底下列中類清單,葉以名字宣告)
MIDDLE_TREE = [
    {"大類": "甲", "中類": ["攻撃力", "守備力"], "子": [
        {"詞元": "アップ", "子": [
            {"關鍵詞": ["攻撃力"], "中類": "攻撃力"}, {"關鍵詞": ["守備力"], "中類": "守備力"}, {}]},
        {"詞元": "になる", "子": [
            {"關鍵詞": ["攻撃力"], "中類": "攻撃力"}, {"關鍵詞": ["守備力"]},
            {"關鍵詞": ["ダメージ"], "大類": "乙", "中類": "ダメージ"}, {}]}]},
    {"大類": "乙", "中類": ["ダメージ"], "子": [{"詞元": "回復"}]},
]


class TestMiddleClass(unittest.TestCase):
    """類別樹中類(category-middle-class 票 01):葉宣告了中類時路徑是 大類 › 中類 › 葉
    (詞元層省掉),沒宣告的照舊 大類 › 詞元 › 葉;中類只改路徑,葉名、葉清單、大類不變。"""

    def test_middle_class_replaces_lemma_level(self):
        """攻撃力・守備力 兩葉各在自己的中類下。"""
        self.assertEqual(
            classify("①：そのモンスターの攻撃力・守備力は５００アップする。", tree=MIDDLE_TREE),
            [("アップ", "已歸", ["アップ:攻撃力", "アップ:守備力"], "甲", None, None,
              ["甲 › 攻撃力 › アップ:攻撃力", "甲 › 守備力 › アップ:守備力"])])

    def test_undeclared_leaf_keeps_lemma_level(self):
        """同一詞元的葉一半在中類、一半在詞元節點:になる:守備力 與預設葉照舊掛詞元節點
        (預設葉與詞元節點同名、相鄰收合,路徑是 甲 › アップ)。"""
        self.assertEqual(
            classify("①：そのモンスターの攻撃力・守備力は０になる。", tree=MIDDLE_TREE),
            [("になる", "已歸", ["になる:攻撃力", "になる:守備力"], "甲", None, None,
              ["甲 › 攻撃力 › になる:攻撃力", "甲 › になる › になる:守備力"])])
        self.assertEqual(
            classify("①：ターン終了時まで１０００アップする。", tree=MIDDLE_TREE),
            [("アップ", "已歸", ["アップ"], "甲", None, None, ["甲 › アップ"])])

    def test_borrowed_leaf_takes_middle_class_of_declared_major(self):
        """宣告了別的大類的葉,中類寫在宣告的大類的清單裡。"""
        self.assertEqual(
            classify("①：その戦闘で発生する自分への戦闘ダメージは０になる。", tree=MIDDLE_TREE),
            [("になる", "已歸", ["になる:ダメージ"], "乙", None, None,
              ["乙 › ダメージ › になる:ダメージ"])])


class TestMiddleClassRealTree(unittest.TestCase):
    """真樹的中類(category-middle-class 票 01〜02):數值 依屬性(攻撃力/守備力/レベル/
    Pスケール)開中類,沒寫屬性的葉照舊掛詞元節點;沒開中類的大類路徑不變。"""

    def test_attack_and_defense_up_in_two_middle_classes(self):
        """攻守同升同時出現在 攻撃力 與 守備力 兩個中類下。"""
        self.assertEqual(
            classify("①：自分フィールドのモンスターの攻撃力・守備力が１０００アップする。"),
            [("アップ", "已歸", ["アップ:攻撃力", "アップ:守備力"], "數值", None, None,
              ["數值 › 攻撃力 › アップ:攻撃力", "數值 › 守備力 › アップ:守備力"])])

    def test_up_without_attribute_stays_under_lemma(self):
        """沒寫屬性的 アップ 落預設葉,照舊掛詞元節點(預設葉與詞元節點同名收合)。"""
        self.assertEqual(
            classify("①：ターン終了時まで１０００アップする。"),
            [("アップ", "已歸", ["アップ"], "數值", None, None, ["數值 › アップ"])])

    def test_level_lemmas_join_level_middle_class(self):
        """詞元名本身含屬性的 レベルになる、同じレベルになる 也歸 數值 › レベル。"""
        self.assertEqual(
            classify("①：このカードのレベルはターン終了時まで宣言したレベルになる。"),
            [("レベルになる", "已歸", ["レベルになる"], "數值", None, None,
              ["數值 › レベル › レベルになる"])])
        self.assertEqual(
            classify("①：そのモンスターはターン終了時まで、除外したモンスターと同じレベルになる。"),
            [("同じレベルになる", "已歸", ["同じレベルになる"], "數值", None, None,
              ["數值 › レベル › 同じレベルになる"])])

    def test_borrowed_damage_leaf_in_damage_middle_class(self):
        """借到 LP・ダメージ 的 になる:ダメージ/LP 歸 ダメージ 中類;与える 也在同一處。"""
        self.assertEqual(
            classify("①：その戦闘で発生する自分への戦闘ダメージは０になる。"),
            [("になる", "已歸", ["になる:ダメージ/LP"], "LP・ダメージ", None, None,
              ["LP・ダメージ › ダメージ › になる:ダメージ/LP"])])
        self.assertEqual(
            classify("①：相手に１０００ダメージを与える。"),
            [("与える", "已歸", ["与える"], "LP・ダメージ", None, "相手",
              ["LP・ダメージ › ダメージ › 与える"])])

    def test_recover_in_lp_middle_class(self):
        self.assertEqual(
            classify("①：自分は１０００LP回復する。"),
            [("回復", "已歸", ["回復"], "LP・ダメージ", None, None, ["LP・ダメージ › LP › 回復"])])

    def test_zone_move_by_source(self):
        """區域移動 依來源開中類:回收(加える:墓地→手札)在 ←墓地、檢索在 ←デッキ。"""
        self.assertEqual(
            classify("①：自分の墓地のモンスター１体を手札に加える。"),
            [("加える", "已歸", ["加える:墓地→手札"], "區域移動", "自分", "無",
              ["區域移動 › ←墓地 › 加える:墓地→手札"])])
        self.assertEqual(
            classify("①：デッキから「試作機」１体を手札に加える。"),
            [("加える", "已歸", ["加える:デッキ→手札"], "區域移動", "無", "無",
              ["區域移動 › ←デッキ › 加える:デッキ→手札"])])

    def test_compound_source_in_two_middle_classes(self):
        """手札・墓地 複合來源:兩葉各在自己來源的中類下。"""
        self.assertEqual(
            classify("①：自分の手札・墓地からモンスター１体を除外する。"),
            [("除外", "已歸", ["除外←墓地", "除外←手札"], "區域移動", "自分", None,
              ["區域移動 › ←墓地 › 除外←墓地", "區域移動 › ←手札 › 除外←手札"])])

    def test_goal_only_leaf_stays_under_lemma(self):
        """只有目的的 加える→手札 不歸任何來源中類,照舊掛詞元節點。"""
        self.assertEqual(
            classify("①：このカードを手札に加える。"),
            [("加える", "已歸", ["加える→手札"], "區域移動", None, "無",
              ["區域移動 › 加える › 加える→手札"])])

    def test_major_without_middle_classes_keeps_lemma_path(self):
        self.assertEqual(
            classify("①：自分の墓地からモンスター１体を特殊召喚する。"),
            [("特殊召喚", "已歸", ["特殊召喚←墓地"], "召喚", "自分", None,
              ["召喚 › 特殊召喚 › 特殊召喚←墓地"])])


class TestCardRollup(unittest.TestCase):
    """票 04:卡層彙總——一張卡的幾句原文 → 效果組與代價組的葉集合(各自去重、依樹序)。"""

    def test_cost_banish_stays_out_of_effect_group(self):
        """代價位的 除外 只進代價組;搜「除外」時不撈到自家代價除外的卡。"""
        self.assertEqual(
            categories.classify_card([
                "①：自分の墓地のモンスター１体を除外して発動できる。"
                "相手フィールドのモンスター１体を破壊する。"]),
            {"effect": ["破壊:モンスター", "破壊@相手フィールド"], "cost": ["除外←墓地"]})

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
    同詞元的葉不被前面較寬的葉蓋掉、中類的引用與清單一致)。"""

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

    def test_player_value_must_be_one_of_three(self):
        """「無」「相對」不能宣告(2026-10-19 站主裁定不切「無」;2026-10-27 自身の/持ち主の
        另記 相對、也不切):由沒宣告玩家的葉收。"""
        for player in ("無", "相對", "持ち主"):
            self.assertTreeError(
                [{"詞元": "破壊", "子": [{"所在": "場上", "所在玩家": player}, {}]}],
                "不在 自分/相手/雙方")

    def test_player_must_bind_to_existing_zone_condition(self):
        self.assertTreeError([{"詞元": "破壊", "子": [{"所在": "場上", "來源玩家": "相手"}, {}]}],
                             "來源玩家 綁在葉沒有的區域條件")

    def test_undeclared_player_leaf_covering_player_leaf(self):
        """沒宣告玩家的 破壊@フィールド 寫在前,蓋掉後面同區域的 破壊@相手フィールド。"""
        self.assertTreeError([{"詞元": "破壊", "子": [
            {"所在": "場上"}, {"所在": "場上", "所在玩家": "相手"}]}],
            "葉 破壊@相手フィールド 被前面的 破壊@フィールド 蓋掉")

    def test_wider_leaf_covering_place_leaf(self):
        """沒有所在條件的 破壊 預設葉寫在前,蓋掉後面的 破壊@フィールド。"""
        self.assertTreeError([{"詞元": "破壊", "子": [{}, {"所在": "場上"}]}],
                             "葉 破壊@フィールド 被前面的 破壊 蓋掉")

    def test_leaf_without_keyword_covering_keyword_leaf(self):
        """沒有關鍵詞條件的 破壊@フィールド 寫在前、涵蓋後面 破壊@フィールド:モンスター 的
        區域條件:較具體者要寫在前(票 03)。"""
        self.assertTreeError([{"詞元": "破壊", "子": [
            {"所在": "場上"}, {"所在": "場上", "關鍵詞": ["モンスター"]}]}],
            "葉 破壊@フィールド:モンスター 被前面的 破壊@フィールド 蓋掉")

    def test_keyword_leaves_do_not_cover_each_other(self):
        """關鍵詞葉之間不互蓋(多葉):破壊:モンスター 在 破壊@フィールド:モンスター 之前、
        魔法 在 魔法・罠 之前都合法。"""
        tree = categories.CategoryTree({"樹": [{"詞元": "破壊", "子": [
            {"關鍵詞": ["モンスター"]}, {"所在": "場上", "關鍵詞": ["モンスター"]},
            {"關鍵詞": ["魔法"]}, {"關鍵詞": ["魔法・罠"]}, {}]}]})
        self.assertEqual(len(tree.leaves), 5)

    def test_declared_major_must_exist(self):
        """葉宣告的大類要是樹裡某個頂層大類的名字(票 04)。"""
        self.assertTreeError([{"大類": "數值", "子": [{"詞元": "になる", "子": [
            {"關鍵詞": ["ダメージ"], "大類": "LP"}, {}]}]}],
            "葉 になる:ダメージ 宣告的大類 LP 不是頂層大類")

    def test_declared_major_must_be_a_major_node(self):
        """自成大類的頂層詞元節點(破壊)不是可宣告的大類;空字串與非字串也不行。"""
        for declared, message in (("破壊", "葉 になる:ダメージ 宣告的大類 破壊 不是頂層大類"),
                                  ("", "宣告的大類 '' 不是頂層大類"),
                                  (["數值"], "宣告的大類 ['數值'] 不是頂層大類")):
            self.assertTreeError([
                {"大類": "數值", "子": [{"詞元": "になる", "子": [
                    {"關鍵詞": ["ダメージ"], "大類": declared}, {}]}]},
                {"詞元": "破壊"}], message)

    def test_major_left_without_leaves_by_declarations(self):
        """本家大類的葉全宣告到別的大類時,本家大類沒有葉。"""
        self.assertTreeError([
            {"大類": "數值", "子": [{"詞元": "になる", "子": [{"大類": "規則改寫"}]}]},
            {"大類": "規則改寫", "子": [{"詞元": "得る"}]}],
            "大類 數值 底下的葉都宣告到別的大類")

    def test_middle_class_not_in_list(self):
        """葉宣告的中類不在所掛大類的清單裡(打錯字;自成大類的頂層詞元節點沒有清單)。"""
        self.assertTreeError([{"大類": "數值", "中類": ["攻撃力"], "子": [{"詞元": "アップ", "子": [
            {"關鍵詞": ["攻撃力"], "中類": "攻撃"}, {}]}]}],
            "葉 アップ:攻撃力 宣告的中類 攻撃 不在大類 數值 的中類清單")
        self.assertTreeError([{"詞元": "破壊", "子": [{"關鍵詞": ["モンスター"], "中類": "怪獸"},
                                                      {}]}],
                             "葉 破壊:モンスター 宣告的中類 怪獸 不在大類 破壊 的中類清單")

    def test_middle_class_of_another_major(self):
        """葉引用的中類屬於別的大類(葉沒宣告該大類):中類只看葉所掛的大類。"""
        self.assertTreeError([
            {"大類": "數值", "子": [{"詞元": "になる", "子": [
                {"關鍵詞": ["ダメージ"], "中類": "ダメージ"}, {}]}]},
            {"大類": "LP・ダメージ", "中類": ["ダメージ"], "子": [{"詞元": "与える", "子": [
                {"中類": "ダメージ"}]}]}],
            "葉 になる:ダメージ 宣告的中類 ダメージ 屬於大類 LP・ダメージ,不在它所掛的大類 數值")

    def test_middle_class_without_leaves(self):
        self.assertTreeError([{"大類": "數值", "中類": ["攻撃力", "守備力"], "子": [
            {"詞元": "アップ", "子": [{"關鍵詞": ["攻撃力"], "中類": "攻撃力"}, {}]}]}],
            "大類 數值 的中類 守備力 沒有葉")

    def test_middle_class_named_like_lemma_node(self):
        """中類與同大類底下的詞元節點同名(總覽頁會出現兩個同名節點)。"""
        self.assertTreeError([{"大類": "數值", "中類": ["アップ"], "子": [
            {"詞元": "上げる", "子": [{"中類": "アップ"}]},
            {"詞元": "アップ"}]}],
            "大類 數值 的中類 アップ 與詞元節點同名")

    def test_middle_class_named_like_major(self):
        """中類與所屬大類同名時,相鄰同名收合會把中類那一層吃掉。"""
        self.assertTreeError([{"大類": "數值", "中類": ["數值"], "子": [
            {"詞元": "アップ", "子": [{"關鍵詞": ["攻撃力"], "中類": "數值"}, {}]}]}],
            "大類 數值 的中類 數值 與大類同名")

    def test_middle_class_list_only_on_top_level_major(self):
        self.assertTreeError([{"大類": "數值", "子": [
            {"大類": "攻守", "中類": ["攻撃力"], "子": [{"詞元": "アップ", "子": [
                {"關鍵詞": ["攻撃力"], "中類": "攻撃力"}, {}]}]}]}],
            "大類 攻守 不是頂層大類,不能列中類")

    def test_middle_class_list_format(self):
        for middles, message in ((["攻撃力", "攻撃力"], "中類清單重複:攻撃力"),
                                 ("攻撃力", "中類清單要是非空字串清單"),
                                 ([""], "中類清單要是非空字串清單")):
            self.assertTreeError([{"大類": "數值", "中類": middles, "子": [
                {"詞元": "アップ", "子": [{"關鍵詞": ["攻撃力"], "中類": "攻撃力"}, {}]}]}],
                message)

    def test_middle_class_declaration_must_be_string(self):
        self.assertTreeError([{"大類": "數值", "中類": ["攻撃力"], "子": [
            {"詞元": "アップ", "子": [{"關鍵詞": ["攻撃力"], "中類": ["攻撃力"]}, {}]}]}],
            "詞元 アップ 的葉宣告的中類 ['攻撃力'] 不是字串")

    def test_nested_node_under_lemma_is_rejected(self):
        """詞元節點底下只能掛葉:帶 子 的物件(大類節點)不能掛。"""
        self.assertTreeError([{"大類": "數值", "子": [{"詞元": "になる", "子": [
            {"大類": "數值", "子": [{"詞元": "アップ"}]}, {}]}]}],
            "詞元節點 になる 底下只能掛葉")

    def test_old_object_key_is_rejected(self):
        """葉條件鍵「對象」已改名「關鍵詞」。"""
        self.assertTreeError([{"詞元": "破壊", "子": [{"對象": ["モンスター"]}, {}]}],
                             "不認得的條件欄:對象")


if __name__ == "__main__":
    unittest.main()
