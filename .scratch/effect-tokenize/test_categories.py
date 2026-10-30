# -*- coding: utf-8 -*-
"""動作類別歸組的行為測試(.scratch/action-categories 票 01〜)。

唯一接縫:一句效果句原文(帶同卡同段上文)→ 每個動作框架的類別紀錄
(categories.classify)。包住框架抽取接縫再接歸組,用真的分詞器、詞典、類別樹與
規則表;只斷言每個框架的(動作、狀態、葉清單、大類、來源玩家、目的玩家、路徑),不測
規則內部、不測樹怎麼存(預期路徑直接寫出,不依葉名查樹);空葉查詢另走自己的接縫(empty-leaf-removal)。每個句型一條回歸例子——
修規則或改樹前先補一條會失敗的例子。例外:匹配機制本身(所在、玩家、關鍵詞三欄、目的關鍵詞、
大類宣告、關鍵詞與所在兩軸並收、中類)另以測試小樹驗,免得真樹改葉表時把機制的例子一起
改掉;經同一接縫(classify 的 tree 參數),分詞器、詞典與規則表仍是真的
(category-tree-restart 票 01〜04、類別線票 06、category-middle-class 票 01、
category-lemma-followup 票 02)。

執行:PYTHONIOENCODING=utf-8 python -m unittest discover -s .scratch/effect-tokenize
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import categories  # noqa: E402
import frames  # noqa: E402


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
            [("選ぶ", "已歸", ["選ぶ@墓地"], "處理程序", "相手", None, ["處理程序 › 選ぶ › 選ぶ@墓地"]),
             ("特殊召喚", "已歸", ["特殊召喚←墓地"], "召喚", "相手", "自分",
              ["召喚 › 特殊召喚 › 特殊召喚←墓地"])])

    def test_either_player_is_both(self):
        """自分または相手の(與 自分か相手の、自分・相手の、お互いの)記雙方。"""
        self.assertEqual(
            classify("①：自分または相手の墓地からモンスター１体を選んで"
                     "自分フィールドに特殊召喚する。"),
            [("選ぶ", "已歸", ["選ぶ@墓地"], "處理程序", "雙方", None, ["處理程序 › 選ぶ › 選ぶ@墓地"]),
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
            [("対象にする", "已歸", ["対象にする(耐性)"], "耐性", None, None,
              ["耐性 › 対象にする(耐性)"])])

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
    所在條件只比所在,「來源空著時讀所在」的橋接拿掉。單向例外(類別線票 08,待裁定):
    非移動類動作所在空著時讀來源當所在——「〜から選ぶ」的 から 是受事者的所在。"""

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

    def test_non_move_action_reads_source_as_place(self):
        """票 08(category-round1):非移動類動作的「〜から」是受事者的所在(從手牌・墓地選
        = 選在手牌・墓地的卡),所在空著時讀來源欄比所在葉;來源玩家欄照記。真樹:
        自分の手札・墓地から…選び 帶 選ぶ@自分手札 與 選ぶ@自分墓地。"""
        self.assertEqual(
            classify("①：自分の手札・墓地から爬虫類族モンスターを２体まで選び、"
                     "対象のモンスターの下に重ねてX素材とする。")[0],
            ("選ぶ", "已歸", ["選ぶ@自分手札", "選ぶ@自分墓地"], "處理程序", "自分", None,
             ["處理程序 › 選ぶ › 選ぶ@自分手札", "處理程序 › 選ぶ › 選ぶ@自分墓地"]))

    def test_non_move_action_reads_deck_top_source_as_place(self):
        """めくる 的 自分のデッキの上から:牌組頂歸牌組,落 めくる@自分デッキ。"""
        self.assertEqual(
            classify("①：自分のデッキの上からカードを３枚めくる。"),
            [("めくる", "已歸", ["めくる@自分デッキ"], "處理程序", "自分", None,
              ["處理程序 › めくる › めくる@自分デッキ"])])


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

    def test_same_zone_with_two_players_takes_each_players_leaf(self):
        """自分フィールド・相手フィールド(自己一張加對手一張):同一區域兩個玩家各帶一葉
        (2026-10-28 站主裁定),不併成雙方;雙方只來自 自分・相手/お互いの 前綴(分詞器寫成
        自分(フィールド)・相手フィールド 的省略形也是)。"""
        self.assertEqual(
            classify("①：自分フィールドのモンスター１体と相手フィールドのカード１枚を破壊する。",
                     tree=PLAYER_TREE),
            [("破壊", "已歸", ["破壊@相手フィールド", "破壊@自分フィールド"], "破壊", None, None,
              ["破壊 › 破壊@相手フィールド", "破壊 › 破壊@自分フィールド"])])
        self.assertEqual(
            classify("①：自分・相手フィールドのカードを全て破壊する。", tree=PLAYER_TREE),
            [("破壊", "已歸", ["破壊@お互いのフィールド"], "破壊", None, None,
              ["破壊 › 破壊@お互いのフィールド"])])

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
    {"詞元": "にする", "子": [{"關鍵詞": ["攻撃力"]}, {"關鍵詞": ["守備力"]}, {"關鍵詞": ["レベル"]},
                           {}]},
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
            [("にする", "已歸", ["にする:守備力"], "にする", None, None,
              ["にする › にする:守備力"]),
             ("無効にする", "未歸", [], None, None, None, [])])

    def test_topic_hit(self):
        self.assertEqual(
            classify("①：このカードの攻撃力は１００００になる。", tree=KEYWORD_TREE),
            [("にする", "已歸", ["にする:攻撃力"], "にする", None, None,
              ["にする › にする:攻撃力"])])

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
            classify("①：相手のLPを１００にする。", tree=KEYWORD_TREE),
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

    def test_keyword_used_as_a_verb_is_not_a_hit(self):
        """真樹:關鍵詞緊接 した/する/され 是動詞用法、修飾後面的名詞,不算命中(2026-10-28
        站主裁定):その発動した効果 只帶 無効にする:効果(2026-10-19 曾是帶兩葉的多葉例子),
        この効果で特殊召喚したモンスターの効果 不帶 :召喚;召喚・特殊召喚を無効 的 召喚 照中。"""
        self.assertEqual(
            classify("①：その発動した効果を無効にする。"),
            [("無効にする", "已歸", ["無効にする:効果"], "無効", None, None,
              ["無効 › 無効にする › 無効にする:効果"])])
        self.assertEqual(
            classify("①：この効果で特殊召喚したモンスターの効果は無効化される。")[-1][2],
            ["無効にする:効果"])
        self.assertEqual(
            classify("①：相手がモンスターを召喚・特殊召喚する際に発動できる。"
                     "その召喚・特殊召喚を無効にし、そのモンスターを破壊する。")[2][2],
            ["無効にする:召喚"])


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


# 測試小樹:目的關鍵詞只比目的欄,與關鍵詞葉、所在葉並收
GOAL_TREE = [
    {"詞元": "にする", "子": [
        {"關鍵詞": ["レベル"]},
        {"目的關鍵詞": ["裏側守備表示"]},
        {"目的關鍵詞": ["守備表示"]},
        {"目的關鍵詞": ["属性", "族"]},
        {"目的關鍵詞": ["レベル"]},
        {"關鍵詞": ["攻撃力"], "目的關鍵詞": ["攻撃力"]},
        {"所在": "場上"},
        {}]},
]


class TestGoalKeywords(unittest.TestCase):
    """category-lemma-followup 票 02:葉的「目的關鍵詞」條件只比框架的目的欄(子字串命中任一),
    與關鍵詞(對象→主語→主題)各自獨立;命中的關鍵詞葉與目的關鍵詞葉全收、任一命中就不取預設葉,
    帶所在條件的葉照樣並收;葉名以「→」接字面,多個以 / 連寫。"""

    def test_goal_keyword_reads_goal_column_only(self):
        """對象寫了 裏側守備表示、目的是 攻撃表示:目的關鍵詞葉不中,落預設葉。"""
        self.assertEqual(
            classify("①：裏側守備表示のモンスターを攻撃表示にする。", tree=GOAL_TREE),
            [("にする", "已歸", ["にする"], "にする", None, None, ["にする"])])

    def test_goal_hits_several_leaves(self):
        """裏側守備表示 同時中 →裏側守備表示 與 →守備表示;預設葉不收。"""
        self.assertEqual(
            classify("①：このカードを裏側守備表示にする。", tree=GOAL_TREE),
            [("にする", "已歸", ["にする→裏側守備表示", "にする→守備表示"], "にする", None, None,
              ["にする › にする→裏側守備表示", "にする › にする→守備表示"])])

    def test_keyword_and_goal_keyword_leaves_both_taken(self):
        """對象與目的都有 レベル:にする:レベル 與 にする→レベル 都帶。"""
        self.assertEqual(
            classify("①：そのモンスターのレベルを宣言したレベルにする。", tree=GOAL_TREE),
            [("にする", "已歸", ["にする:レベル", "にする→レベル"], "にする", None, None,
              ["にする › にする:レベル", "にする › にする→レベル"])])

    def test_goal_keyword_leaf_paired_with_place_leaf(self):
        """相手フィールドのモンスター を蓋伏:目的關鍵詞葉與所在葉兩軸並收。"""
        self.assertEqual(
            classify("①：相手フィールドのモンスター１体を裏側守備表示にする。", tree=GOAL_TREE),
            [("にする", "已歸", ["にする→裏側守備表示", "にする→守備表示", "にする@フィールド"],
              "にする", None, None,
              ["にする › にする→裏側守備表示", "にする › にする→守備表示",
               "にする › にする@フィールド"])])

    def test_several_goal_keywords_join_with_slash(self):
        self.assertEqual(
            classify("①：このカードは機械族になる。", tree=GOAL_TREE),
            [("にする", "已歸", ["にする→属性/族"], "にする", None, None,
              ["にする › にする→属性/族"])])

    def test_keyword_and_goal_keyword_on_one_leaf_both_required(self):
        """一葉同時宣告關鍵詞與目的關鍵詞:葉名 にする:攻撃力→攻撃力,兩者都中才收(目的關鍵詞
        原為 元々,keyword-head-noun 起它在「元々の攻撃力」裡是修飾語,改比中心詞)。"""
        self.assertEqual(
            classify("①：そのモンスターの攻撃力を元々の攻撃力にする。", tree=GOAL_TREE),
            [("にする", "已歸", ["にする:攻撃力→攻撃力"], "にする", None, None,
              ["にする › にする:攻撃力→攻撃力"])])
        self.assertEqual(
            classify("①：そのモンスターは元々の攻撃力になる。", tree=GOAL_TREE),
            [("にする", "已歸", ["にする"], "にする", None, None, ["にする"])])


class TestLemmaFollowupRealTree(unittest.TestCase):
    """category-lemma-followup 票 01〜04 的真樹:直接攻撃 在 戰鬥/限制 各一節點;にする 依目的
    分出表示形式五葉、→属性/→族(規則改寫)、→レベル(數值 › レベル);ダメージ 與 LP 各一葉。
    →レベル 的兩個句型見 TestMiddleClassRealTree.test_level_complements_land_on_nisuru,
    半分になる/０になる 的 ダメージ 葉見 TestDraftTree、TestMajorByLeaf。"""

    def test_direct_attack_possible_is_battle(self):
        self.assertEqual(
            classify("①：このカードは直接攻撃できる。"),
            [("直接攻撃", "已歸", ["直接攻撃"], "戰鬥", None, None, ["戰鬥 › 直接攻撃"])])

    def test_direct_attack_cannot_is_restriction(self):
        self.assertEqual(
            classify("①：このカードは直接攻撃できない。"),
            [("直接攻撃", "已歸", ["直接攻撃(限制)"], "限制", None, None,
              ["限制 › 直接攻撃(限制)"])])

    def test_attack_becomes_direct_attack_keeps_its_node(self):
        self.assertEqual(
            classify("①：相手の攻撃は自分への直接攻撃になる。"),
            [("直接攻撃にする", "已歸", ["直接攻撃にする"], "戰鬥", None, None,
              ["戰鬥 › 直接攻撃にする"])])

    def test_face_down_defense_takes_two_battle_position_leaves(self):
        self.assertEqual(
            classify("①：このカードを裏側守備表示にする。"),
            [("にする", "已歸", ["にする→裏側守備表示", "にする→守備表示"], "表示形式", None, None,
              ["表示形式 › にする › にする→裏側守備表示", "表示形式 › にする › にする→守備表示"])])

    def test_attack_position(self):
        self.assertEqual(
            classify("①：そのモンスターを攻撃表示にする。"),
            [("にする", "已歸", ["にする→攻撃表示"], "表示形式", None, None,
              ["表示形式 › にする › にする→攻撃表示"])])

    def test_either_position_takes_both_sides(self):
        self.assertEqual(
            classify("①：そのモンスターを表側攻撃表示または表側守備表示にする。"),
            [("にする", "已歸", ["にする→表側守備表示", "にする→表側攻撃表示", "にする→守備表示",
                                  "にする→攻撃表示"], "表示形式", None, None,
              ["表示形式 › にする › にする→表側守備表示", "表示形式 › にする › にする→表側攻撃表示",
               "表示形式 › にする › にする→守備表示", "表示形式 › にする › にする→攻撃表示"])])

    def test_attribute_goal(self):
        for text in ("①：このカードは闇属性になる。", "①：そのモンスターは宣言した属性になる。"):
            self.assertEqual(
                classify(text),
                [("にする", "已歸", ["にする→属性"], "規則改寫", None, None,
                  ["規則改寫 › にする › にする→属性"])])

    def test_race_goal(self):
        self.assertEqual(
            classify("①：このカードは機械族になる。"),
            [("にする", "已歸", ["にする→族"], "規則改寫", None, None,
              ["規則改寫 › にする › にする→族"])])

    def test_race_and_attribute_goal_takes_both(self):
        self.assertEqual(
            classify("①：そのモンスターは宣言した種族・属性になる。"),
            [("にする", "已歸", ["にする→属性", "にする→族"], "規則改寫", None, None,
              ["規則改寫 › にする › にする→属性", "規則改寫 › にする › にする→族"])])

    def test_other_goal_values_stay_on_default_leaf(self):
        """エンドフェイズ 這類其餘目的值不開葉,仍落 にする 預設葉;攻撃力を０ 照舊。"""
        self.assertEqual(
            classify("①：このターンのエンドフェイズになる。"),
            [("にする", "已歸", ["にする"], "數值", None, None, ["數值 › にする"])])
        self.assertEqual(
            classify("①：そのモンスターの攻撃力を０にする。"),
            [("にする", "已歸", ["にする:攻撃力"], "數值", None, None,
              ["數值 › 攻撃力 › にする:攻撃力"])])

    def test_halve_lp_takes_lp_leaf_only(self):
        self.assertEqual(
            classify("①：相手のLPを半分にする。"),
            [("半分にする", "已歸", ["半分にする:LP"], "LP・ダメージ", None, None,
              ["LP・ダメージ › LP › 半分にする:LP"])])

    def test_lp_becomes_value_is_lp_middle_class(self):
        self.assertEqual(
            classify("①：相手のLPは４０００になる。"),
            [("にする", "已歸", ["にする:LP"], "LP・ダメージ", None, None,
              ["LP・ダメージ › LP › にする:LP"])])



class TestDraftTree(unittest.TestCase):
    """票 06 重起草案的真樹(待站主裁定):にする/アップ 系(2026-10-27 起 になる 併入 にする)的
    關鍵詞葉與大類、非移動類的所在/玩家葉、否定葉帶所在。"""

    def test_up_family_keyword_leaves(self):
        self.assertEqual(
            classify("①：自分フィールドのモンスターの攻撃力・守備力は５００アップする。"),
            [("アップ", "已歸", ["アップ:攻撃力", "アップ:守備力"], "數值", None, None,
              ["數值 › 攻撃力 › アップ:攻撃力", "數值 › 守備力 › アップ:守備力"])])
        self.assertEqual(
            classify("①：このカードのレベルを１つ上げる。"),
            [("アップ", "已歸", ["アップ:レベル"], "數值", None, None,
              ["數值 › レベル › アップ:レベル"])])

    def test_naru_family_keywords_pick_major(self):
        """半分にする:ダメージ 歸 LP・ダメージ、にする:レベル 歸 數值。"""
        self.assertEqual(
            classify("①：その戦闘で発生する相手への戦闘ダメージは半分になる。"),
            [("半分にする", "已歸", ["半分にする:ダメージ"], "LP・ダメージ", None, None,
              ["LP・ダメージ › ダメージ › 半分にする:ダメージ"])])
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
        """真樹的 にする:攻撃力/:守備力 沒宣告、取本家 數值;:ダメージ 宣告 LP・ダメージ、
        :ドロー/数 宣告 規則改寫(2026-10-28 第四批裁定前是 :ドロー/枚数/回数)。"""
        self.assertEqual(
            classify("①：このカードの攻撃力は１００００になる。"),
            [("にする", "已歸", ["にする:攻撃力"], "數值", None, None,
              ["數值 › 攻撃力 › にする:攻撃力"])])
        self.assertEqual(
            classify("①：そのモンスターの守備力が０になり、効果は無効化される。"),
            [("にする", "已歸", ["にする:守備力"], "數值", None, None,
              ["數值 › 守備力 › にする:守備力"]),
             ("無効にする", "已歸", ["無効にする:効果"], "無効", None, None,
              ["無効 › 無効にする › 無効にする:効果"])])
        self.assertEqual(
            classify("①：その戦闘で発生する自分への戦闘ダメージは０になる。"),
            [("にする", "已歸", ["にする:ダメージ"], "LP・ダメージ", None, None,
              ["LP・ダメージ › ダメージ › にする:ダメージ"])])
        self.assertEqual(
            classify("①：自分の通常のドローは２枚になる。"),
            [("にする", "已歸", ["にする:ドロー/数"], "規則改寫", None, None,
              ["規則改寫 › にする › にする:ドロー/数"])])

    def test_multi_leaf_across_majors_takes_first_leafs_major(self):
        tree = [
            {"大類": "甲", "子": [{"詞元": "にする", "子": [
                {"關鍵詞": ["攻撃力"], "大類": "乙"}, {"關鍵詞": ["守備力"]}, {}]}]},
            {"大類": "乙", "子": [{"詞元": "アップ"}]},
        ]
        self.assertEqual(
            classify("①：そのモンスターの攻撃力・守備力が０になる。", tree=tree),
            [("にする", "已歸", ["にする:攻撃力", "にする:守備力"], "乙", None, None,
              ["乙 › にする › にする:攻撃力", "甲 › にする › にする:守備力"])])
        self.assertEqual(
            classify("①：そのモンスターの守備力が０になる。", tree=tree),
            [("にする", "已歸", ["にする:守備力"], "甲", None, None,
              ["甲 › にする › にする:守備力"])])


class TestLeafProposalsRealTree(unittest.TestCase):
    """類別線票 06 第四批裁定(2026-10-28,LLM 檢驗 round1 挑出的葉表提議):アップ 開 :Pスケール
    (中類 Pスケール);無効にする(耐性) 比照肯定節點依 効果/発動/召喚 分葉;にする 的 ドロー/枚数/回数
    葉改宣告 ドロー/数(枚数/回数 是 数 的子字串,「手札に加える数を２枚に」也收);使用(限制) 開
    使用:ゾーン(限制)(9 框,站主點名開、不照門檻);異なる(對象限定語)、見る(視點語)不是卡在做的
    動作,節點刪除、框架回未歸。"""

    def test_pendulum_scale_up(self):
        self.assertEqual(
            classify("①：１ターンに１度、自分メインフェイズに発動できる。"
                     "このカードのPスケールを１つ上げる（最大１２まで）。"),
            [("アップ", "已歸", ["アップ:Pスケール"], "數值", None, None,
              ["數值 › Pスケール › アップ:Pスケール"])])

    def test_negate_resistance_splits_by_keyword(self):
        self.assertEqual(
            classify("①：このカードの発動と効果は無効化されない。"),
            [("無効にする", "已歸", ["無効にする:効果(耐性)", "無効にする:発動(耐性)"], "耐性",
              None, None,
              ["耐性 › 無効にする(耐性) › 無効にする:効果(耐性)",
               "耐性 › 無効にする(耐性) › 無効にする:発動(耐性)"])])
        # 発動する効果 的 発動 是動詞用法、不算命中
        self.assertEqual(
            classify("①：このターン、「サブテラー」カードの発動する効果は無効化されない。")[0][2],
            ["無効にする:効果(耐性)"])
        self.assertEqual(
            classify("①：このカードの特殊召喚は無効化されず、"
                     "特殊召喚成功時に相手は効果を発動できない。")[0][2],
            ["無効にする:召喚(耐性)"])

    def test_count_rewrite_takes_kazu(self):
        for text in ("①：この効果で手札に加える数を２枚にできる。",
                     "①：このカードのX素材を取り除く数を１つにできる。"):
            self.assertEqual(
                classify(text),
                [("にする", "已歸", ["にする:ドロー/数"], "規則改寫", None, None,
                  ["規則改寫 › にする › にする:ドロー/数"])])

    def test_zone_use_restriction(self):
        self.assertEqual(
            classify("①：このターン、指定したゾーンは使用できない。"),
            [("使用", "已歸", ["使用:ゾーン(限制)"], "限制", None, None,
              ["限制 › 使用(限制) › 使用:ゾーン(限制)"])])
        # 召喚素材用途的 使用 字面在子句,仍落預設葉
        self.assertEqual(
            classify("①：このカードをS素材とする場合、"
                     "「セイヴァー」モンスターのS召喚にしか使用できない。")[-1][2],
            ["使用(限制)"])

    def test_differ_and_seen_from_are_unplaced(self):
        self.assertEqual(
            classify("①：フィールドの表側表示モンスター１体を対象として発動できる。"
                     "そのモンスターとはカード名が異なり、同じ属性を持つフィールドの"
                     "モンスター１体を選んで破壊する。")[1],
            ("異なる", "未歸", [], None, None, None, []))
        self.assertIn(
            ("見る", "未歸", [], None, None, None, []),
            classify("①：１ターンに１度、自分メインフェイズに発動できる。装備モンスターの位置を、"
                     "そのモンスターのリンク先のメインモンスターゾーンに移動する"
                     "（そのモンスターから見て相手のフィールドには移動できない）。"))


class TestLemmaVariantsRealTree(unittest.TestCase):
    """動作詞元變體(frame-lemma-variants,2026-10-29):統一後的框架落到既有節點,沒有葉的記未歸;
    變空的節點與葉刪除。"""

    def test_performed_summon_lands_on_the_summon_node(self):
        self.assertEqual(
            classify("①：S召喚を行う。"),
            [("S召喚", "已歸", ["S召喚"], "召喚", None, None, ["召喚 › S召喚"])])

    def test_summon_material_restriction_per_method(self):
        """X素材にする(限制) 2026-10-29 站主裁定開節點,與 融合/S/L素材にする(限制) 並列。"""
        self.assertEqual(
            classify("①：このカードは融合・S・X召喚の素材にできない。"),
            [("融合素材にする", "已歸", ["融合素材にする(限制)"], "限制", None, None,
              ["限制 › 融合素材にする(限制)"]),
             ("S素材にする", "已歸", ["S素材にする(限制)"], "限制", None, None,
              ["限制 › S素材にする(限制)"]),
             ("X素材にする", "已歸", ["X素材にする(限制)"], "限制", None, None,
              ["限制 › X素材にする(限制)"])])

    def test_cannot_select_as_attack_target_is_a_restriction(self):
        self.assertEqual(
            classify("①：相手は「ジェネレイド」効果モンスターを攻撃対象に選択できない。"),
            [("攻撃対象にする", "已歸", ["攻撃対象にする(限制)"], "限制", None, None,
              ["限制 › 攻撃対象にする(限制)"])])

    def test_not_targeted_even_with_mo_is_resistance(self):
        self.assertEqual(
            classify("①：このカードは相手の効果の対象にもならない。"),
            [("対象にする", "已歸", ["対象にする(耐性)"], "耐性", None, None,
              ["耐性 › 対象にする(耐性)"])])

    def test_effect_becomes_another_effect_is_rule_rewrite(self):
        self.assertEqual(
            classify("①：その裏表によってその効果は以下の効果となる。"),
            [("とする", "已歸", ["とする"], "規則改寫", None, None, ["規則改寫 › とする"])])


class TestHeadNounRealTree(unittest.TestCase):
    """keyword-head-noun 票 01(2026-10-30 /grill-with-docs 定案):關鍵詞類條件只比欄位的中心詞——
    依並列詞切段、每段取最後一個修飾標記之後、去數量尾;只出現在修飾語裡的字面不算命中。"""

    def test_lp_in_modifier_is_not_lp_leaf(self):
        self.assertEqual(
            classify("①：このカードがフィールドゾーンに存在する限り、相手よりLPが少ないプレイヤーが"
                     "受ける全てのダメージは０になる。")[-1],
            ("にする", "已歸", ["にする:ダメージ"], "LP・ダメージ", None, None,
             ["LP・ダメージ › ダメージ › にする:ダメージ"]))

    def test_quantity_tail_with_uchi_keeps_head(self):
        """「その内の1体」這種數量尾連同 の内の 一起去掉,中心詞仍是 モンスター。"""
        self.assertEqual(
            classify("●EXデッキ：EXデッキから特殊召喚されたそのモンスターの内の１体を破壊する。")[-1][2],
            ["破壊:モンスター"])

    def test_level_in_modifier_is_not_level_up(self):
        self.assertEqual(
            classify("③：墓地のこのカードを除外して発動できる。自分フィールドの全てのレベル８以上の"
                     "ドラゴン族モンスターの攻撃力は１０００アップする。")[-1][2],
            ["アップ:攻撃力"])

    def test_attack_position_in_modifier_is_not_negate_attack(self):
        self.assertEqual(
            classify("②：自分・相手のバトルフェイズ開始時に発動できる。"
                     "相手フィールドの全ての攻撃表示モンスターの効果は無効化される。")[-1][2],
            ["無効にする:効果", "無効にする@相手フィールド"])

    def test_attack_in_modifier_is_not_set_attack(self):
        self.assertEqual(
            classify("●相手フィールドの攻撃力２０００以下のモンスター１体を裏側守備表示にする。")[-1][2],
            ["にする→裏側守備表示", "にする→守備表示"])

    def test_goal_keyword_in_modifier_is_not_a_hit(self):
        self.assertEqual(
            classify("①：１ターンに１度、自分フィールドの表側守備表示モンスター１体を対象として発動できる。"
                     "そのモンスターの守備力は、自分フィールドの全ての表側守備表示モンスターの"
                     "元々の守備力を合計した数値になる。")[-1][2],
            ["にする:守備力"])

    def test_damage_to_recovery_is_effect_rewrite(self):
        """傷害效果變回復效果:不帶 にする:LP/にする:ダメージ,歸 にする→効果(票 02)。"""
        self.assertEqual(
            classify("①：自分が効果ダメージを受けた時にこの効果を発動できる。このカードを破壊し、"
                     "さらにこのターン、LPにダメージを与える効果は、LPを回復する効果になる。")[-1],
            ("にする", "已歸", ["にする→効果"], "規則改寫", None, None,
             ["規則改寫 › にする › にする→効果"]))
        self.assertEqual(
            classify("①：このカードがモンスターゾーンに存在する限り、自分にダメージを与える効果は、"
                     "自分のLPを回復する効果になる。")[-1][2],
            ["にする→効果"])

    def test_effect_becomes_activatable_effect_is_rule_rewrite(self):
        self.assertEqual(
            classify("①：自分フィールドに「獄神」Lモンスターが存在する限り、元々のカード名に"
                     "「アルス＝マグナ」を含む、自分フィールドのモンスターが発動する効果は、"
                     "相手ターンでも発動できる効果になる。")[-1],
            ("にする", "已歸", ["にする→効果"], "規則改寫", None, None,
             ["規則改寫 › にする › にする→効果"]))

    def test_head_hits_are_kept(self):
        """不誤傷:中心詞本身就是關鍵詞(或含它)的照中。"""
        self.assertEqual(classify("●相手のLPを１００にする。")[-1][2], ["にする:LP"])
        self.assertEqual(
            classify("①：このカードがモンスターゾーンに存在する限り、"
                     "自分が受ける効果ダメージは０になる。")[-1][2],
            ["にする:ダメージ"])
        self.assertEqual(
            classify("①：このカードのX素材を２つまで取り除いて発動できる。")[0][2],
            ["取り除く:X素材"])


class TestEmptyLeafRemovalRealTree(unittest.TestCase):
    """empty-leaf-removal 票 01 的真樹:刪掉 にする→裏側表示 與 指定、無効にする(耐性) 的預設葉。"""

    def actions(self, text):
        return [(action, status, leaves) for action, status, leaves, *_ in classify(text)]

    def test_face_down_goal_falls_to_nisuru_default_leaf(self):
        """語料沒有效果位的「裏側表示にする」,用造句:將來出現時落預設葉、不遺失。"""
        self.assertEqual(self.actions("①：このカードを裏側表示にする。"),
                         [("にする", "已歸", ["にする"])])

    def test_face_down_defense_keeps_its_two_leaves(self):
        """真卡 28273805 的句子。"""
        self.assertEqual(
            self.actions("●相手フィールドの攻撃力２０００以下のモンスター１体を裏側守備表示にする。"),
            [("にする", "已歸", ["にする→裏側守備表示", "にする→守備表示"])])

    def test_turned_face_down_condition_has_no_category_leaf(self):
        """條件位不進動作類別(語料 8 框的前段都是這個句型,留給觸發事件軸;後段是造句)。"""
        self.assertEqual(
            self.actions("①：自分フィールドの表側表示モンスターが裏側表示になった時に発動できる。"
                         "このカードを手札から特殊召喚する。"),
            [("にする", "不適用", []), ("特殊召喚", "已歸", ["特殊召喚←手札"])])

    def test_designate_off_field_is_unplaced(self):
        """語料的 指定 全在場上,用造句:所在不是場上的框進未歸、不落預設葉。"""
        self.assertEqual(self.actions("①：相手の墓地のカード１枚を指定する。"),
                         [("指定", "未歸", [])])

    def test_designate_on_field_keeps_its_leaf(self):
        self.assertEqual(self.actions("①：使用していない相手のモンスターゾーンを１ヵ所指定する。"),
                         [("指定", "已歸", ["指定@フィールド"])])

    def test_negate_resistance_without_keyword_is_unplaced(self):
        """語料的耐性 無効にする 都含 効果/発動/召喚,用造句:都不含的框進未歸。"""
        self.assertEqual(self.actions("①：このカードの攻撃は無効にされない。"),
                         [("無効にする", "未歸", [])])


# 測試小樹:空葉查詢(預設葉與目的關鍵詞葉各可空)
EMPTY_LEAF_TREE = [
    {"詞元": "破壊", "子": [{"所在": "墓地"}, {}]},
    {"詞元": "にする", "子": [{"目的關鍵詞": ["裏側表示"]}, {}]},
]
# 補滿 破壊 兩葉的句子,讓各測試只看 にする 那一側
DESTROY_LEAVES_FILLED = ("①：相手の墓地のカードを破壊する。", "①：このカードを破壊する。")


class TestEmptyLeaves(unittest.TestCase):
    """empty-leaf-removal 票 02:每片葉在全語料的效果位或代價位至少要有一框,預設葉也一樣。
    接縫是空葉查詢,不是 classify:一棵樹對一批框架報哪些空葉(規格裁定的第二個接縫)。"""

    def empty_leaves(self, *texts):
        tree = categories.CategoryTree({"樹": EMPTY_LEAF_TREE})
        return categories.empty_leaves(tree, [{"frames": frames.extract(t)} for t in texts])

    def test_reports_empty_leaves_in_tree_order(self):
        self.assertEqual(self.empty_leaves(DESTROY_LEAVES_FILLED[0]),
                         ["破壊", "にする→裏側表示", "にする"])

    def test_default_leaf_without_frames_is_empty(self):
        self.assertEqual(
            self.empty_leaves(*DESTROY_LEAVES_FILLED, "①：このカードを裏側表示にする。"),
            ["にする"])

    def test_leaf_hit_only_in_condition_position_is_empty(self):
        self.assertEqual(
            self.empty_leaves(*DESTROY_LEAVES_FILLED, "①：このカードを攻撃表示にする。",
                              "①：自分のモンスターが裏側表示になった時に発動できる。"),
            ["にする→裏側表示"])

    def test_cost_position_counts(self):
        self.assertEqual(
            self.empty_leaves(*DESTROY_LEAVES_FILLED, "①：このカードを攻撃表示にする。",
                              "①：このカードを裏側表示にして発動できる。"),
            [])

    def test_all_leaves_have_frames(self):
        self.assertEqual(
            self.empty_leaves(*DESTROY_LEAVES_FILLED, "①：このカードを裏側表示にする。",
                              "①：このカードを攻撃表示にする。"),
            [])

    def test_real_tree_has_no_empty_leaf_in_corpus(self):
        """真樹對框架檔重新歸類(不讀舊的類別產物):改樹後不必重跑分詞鏈就驗得到。卡文更新或
        改規則讓這條變紅時,由站主決定刪葉或改規則。"""
        if not os.path.exists(categories.FRAMES):
            reason = "空葉防線沒有生效:沒有 frames.json,先跑分詞鏈(run_chain.py)"
            print(reason, file=sys.stderr)
            self.skipTest(reason)
        with open(categories.FRAMES, encoding="utf-8") as f:
            sentences = json.load(f)
        self.assertEqual(categories.empty_leaves(categories.default_tree(), sentences), [],
                         "這些葉在全語料的效果位與代價位都沒有框,請站主決定刪葉或改規則")


# 測試小樹:中類(大類底下列中類清單,葉以名字宣告)
MIDDLE_TREE = [
    {"大類": "甲", "中類": ["攻撃力", "守備力"], "子": [
        {"詞元": "アップ", "子": [
            {"關鍵詞": ["攻撃力"], "中類": "攻撃力"}, {"關鍵詞": ["守備力"], "中類": "守備力"}, {}]},
        {"詞元": "にする", "子": [
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
        """同一詞元的葉一半在中類、一半在詞元節點:にする:守備力 與預設葉照舊掛詞元節點
        (預設葉與詞元節點同名、相鄰收合,路徑是 甲 › アップ)。"""
        self.assertEqual(
            classify("①：そのモンスターの攻撃力・守備力は０になる。", tree=MIDDLE_TREE),
            [("にする", "已歸", ["にする:攻撃力", "にする:守備力"], "甲", None, None,
              ["甲 › 攻撃力 › にする:攻撃力", "甲 › にする › にする:守備力"])])
        self.assertEqual(
            classify("①：ターン終了時まで１０００アップする。", tree=MIDDLE_TREE),
            [("アップ", "已歸", ["アップ"], "甲", None, None, ["甲 › アップ"])])

    def test_borrowed_leaf_takes_middle_class_of_declared_major(self):
        """宣告了別的大類的葉,中類寫在宣告的大類的清單裡。"""
        self.assertEqual(
            classify("①：その戦闘で発生する自分への戦闘ダメージは０になる。", tree=MIDDLE_TREE),
            [("にする", "已歸", ["にする:ダメージ"], "乙", None, None,
              ["乙 › ダメージ › にする:ダメージ"])])


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

    def test_level_complements_land_on_nisuru(self):
        """「宣言したレベルになる」「同じレベルになる」:補語不併(frame-lemma-unify 票 05)後詞元是
        にする、レベル 在目的欄,由目的關鍵詞葉 にする→レベル 收進 數值 › レベル;主題也寫了 レベル
        時另帶 にする:レベル(命中全收;category-lemma-followup 票 03)。"""
        self.assertEqual(
            classify("①：このカードのレベルはターン終了時まで宣言したレベルになる。"),
            [("にする", "已歸", ["にする:レベル", "にする→レベル"], "數值", None, None,
              ["數值 › レベル › にする:レベル", "數值 › レベル › にする→レベル"])])
        self.assertEqual(
            classify("①：そのモンスターはターン終了時まで、除外したモンスターと同じレベルになる。"),
            [("にする", "已歸", ["にする→レベル"], "數值", None, None,
              ["數值 › レベル › にする→レベル"])])

    def test_borrowed_damage_leaf_in_damage_middle_class(self):
        """借到 LP・ダメージ 的 にする:ダメージ 歸 ダメージ 中類;与える 也在同一處。"""
        self.assertEqual(
            classify("①：その戦闘で発生する自分への戦闘ダメージは０になる。"),
            [("にする", "已歸", ["にする:ダメージ"], "LP・ダメージ", None, None,
              ["LP・ダメージ › ダメージ › にする:ダメージ"])])
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
        self.assertTreeError([{"大類": "數值", "子": [{"詞元": "にする", "子": [
            {"關鍵詞": ["ダメージ"], "大類": "LP"}, {}]}]}],
            "葉 にする:ダメージ 宣告的大類 LP 不是頂層大類")

    def test_declared_major_must_be_a_major_node(self):
        """自成大類的頂層詞元節點(破壊)不是可宣告的大類;空字串與非字串也不行。"""
        for declared, message in (("破壊", "葉 にする:ダメージ 宣告的大類 破壊 不是頂層大類"),
                                  ("", "宣告的大類 '' 不是頂層大類"),
                                  (["數值"], "宣告的大類 ['數值'] 不是頂層大類")):
            self.assertTreeError([
                {"大類": "數值", "子": [{"詞元": "にする", "子": [
                    {"關鍵詞": ["ダメージ"], "大類": declared}, {}]}]},
                {"詞元": "破壊"}], message)

    def test_major_left_without_leaves_by_declarations(self):
        """本家大類的葉全宣告到別的大類時,本家大類沒有葉。"""
        self.assertTreeError([
            {"大類": "數值", "子": [{"詞元": "にする", "子": [{"大類": "規則改寫"}]}]},
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
            {"大類": "數值", "子": [{"詞元": "にする", "子": [
                {"關鍵詞": ["ダメージ"], "中類": "ダメージ"}, {}]}]},
            {"大類": "LP・ダメージ", "中類": ["ダメージ"], "子": [{"詞元": "与える", "子": [
                {"中類": "ダメージ"}]}]}],
            "葉 にする:ダメージ 宣告的中類 ダメージ 屬於大類 LP・ダメージ,不在它所掛的大類 數值")

    def test_middle_class_without_leaves(self):
        self.assertTreeError([{"大類": "數值", "中類": ["攻撃力", "守備力"], "子": [
            {"詞元": "アップ", "子": [{"關鍵詞": ["攻撃力"], "中類": "攻撃力"}, {}]}]}],
            "大類 數值 的中類 守備力 沒有葉")

    def test_middle_class_named_like_lemma_node(self):
        """中類與同大類底下的詞元節點同名(總覽頁會出現兩個同名節點)。"""
        self.assertTreeError([{"大類": "數值", "中類": ["アップ"], "子": [
            {"詞元": "ダウン", "子": [{"中類": "アップ"}]},
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
        self.assertTreeError([{"大類": "數值", "子": [{"詞元": "にする", "子": [
            {"大類": "數值", "子": [{"詞元": "アップ"}]}, {}]}]}],
            "詞元節點 にする 底下只能掛葉")

    def test_goal_keywords_format(self):
        """目的關鍵詞要是非空字串清單(category-lemma-followup 票 02)。"""
        for value in ([], "守備表示", [""], [1]):
            self.assertTreeError([{"詞元": "にする", "子": [{"目的關鍵詞": value}, {}]}],
                                 "詞元 にする 的葉目的關鍵詞要是非空字串清單")

    def test_goal_and_goal_keywords_on_one_leaf(self):
        self.assertTreeError([{"詞元": "戻す", "子": [{"目的": "手牌", "目的關鍵詞": ["手札"]}, {}]}],
                             "詞元 戻す 的葉不能同時宣告 目的 與 目的關鍵詞")

    def test_goal_leaf_and_goal_keyword_leaf_name_clash(self):
        """目的區域葉 戻す→手札 與目的關鍵詞葉 戻す→手札 撞名,由葉名唯一檢查擋下。"""
        self.assertTreeError([{"詞元": "戻す", "子": [{"目的": "手牌"}, {"目的關鍵詞": ["手札"]}, {}]}],
                             "葉名重複:戻す→手札")

    def test_plain_leaf_covering_goal_keyword_leaf(self):
        """不帶關鍵詞類條件的預設葉寫在目的關鍵詞葉之前會蓋掉它;目的關鍵詞葉之間、與關鍵詞葉
        之間不互蓋。"""
        self.assertTreeError([{"詞元": "にする", "子": [{}, {"目的關鍵詞": ["守備表示"]}]}],
                             "葉 にする→守備表示 被前面的 にする 蓋掉")
        tree = categories.CategoryTree({"樹": [{"詞元": "にする", "子": [
            {"目的關鍵詞": ["守備表示"]}, {"目的關鍵詞": ["裏側守備表示"]},
            {"關鍵詞": ["レベル"]}, {"目的關鍵詞": ["レベル"]}, {}]}]})
        self.assertEqual(len(tree.leaves), 5)

    def test_lemma_must_be_canonical(self):
        """詞元節點寫了對照表的輸入端(態歸一前的原詞元、全名):建置失敗並指出正規詞元
        (category-lemma-followup 票 05)。"""
        for lemma, canonical in (("戻る", "戻す"), ("無効化", "無効にする"), ("上げる", "アップ"),
                                 ("アドバンス召喚", "A召喚")):
            self.assertTreeError([{"詞元": lemma}],
                                 "詞元節點 %s 不是框架抽取產得出的詞元(正規詞元是 %s)"
                                 % (lemma, canonical))

    def test_lemma_split_by_complement_rule(self):
        """「值或屬性 + にする」:補語不併判準會拆成 にする 與目的,樹上不能寫。"""
        for lemma in ("裏側守備表示にする", "属性にする", "レベルにする", "同じレベルにする",
                      "数値にする"):
            self.assertTreeError([{"詞元": lemma}],
                                 "詞元節點 %s 的補語是值或屬性,框架抽取不併入詞元" % lemma)

    def test_old_object_key_is_rejected(self):
        """葉條件鍵「對象」已改名「關鍵詞」。"""
        self.assertTreeError([{"詞元": "破壊", "子": [{"對象": ["モンスター"]}, {}]}],
                             "不認得的條件欄:對象")


if __name__ == "__main__":
    unittest.main()
