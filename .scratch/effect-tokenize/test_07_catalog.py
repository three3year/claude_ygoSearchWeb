# -*- coding: utf-8 -*-
"""具名查詢目錄的行為測試(named-queries 票 07)。

接縫:目錄檔的資料 → 載入後的目錄(catalog.Catalog;違反檢查即 CatalogError、訊息列全部違反處)。只斷言
節點名(由述詞機械組出)、載入後的述詞(極性補成明文清單)、路徑與大類/中類的聯集,以及檢查的錯誤訊息,
不斷言樹怎麼存。真目錄 catalog.json 一條:載入過檢查,每個具名查詢名與改寫對應表 catalog-mapping.json
(舊葉名/舊節點名 → 新節點名,233 葉 + 100 詞元節點;加 2026-11-01 裁定新增的 対象とする 一列)一致。

執行:PYTHONIOENCODING=utf-8 python -m unittest discover -s .scratch/effect-tokenize
"""
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import catalog  # noqa: E402
import predicate  # noqa: E402

MAPPING = os.path.join(HERE, "catalog-mapping.json")


def query(lemma, children=None, **fields):
    """測試用的具名查詢節點:述詞(詞元 + 欄)與可選的子;大類/中類 是節點的宣告、不進述詞。"""
    node = {key: fields.pop(key) for key in ("大類", "中類") if key in fields}
    node["述詞"] = dict({"詞元": lemma}, **fields)
    if children is not None:
        node["子"] = children
    return node


def major(name, children, middles=None):
    node = {"大類": name, "子": children}
    if middles:
        node["中類"] = middles
    return node


def load(*tree):
    return catalog.Catalog({"樹": list(tree)})


def names(*tree):
    return [q.name for q in load(*tree).queries]


def failure(*tree):
    """載入失敗的訊息(沒失敗就讓測試炸)。"""
    try:
        load(*tree)
    except catalog.CatalogError as e:
        return str(e)
    raise AssertionError("目錄應該載入失敗")


class TestNaming(unittest.TestCase):
    """節點名由述詞機械組出,寫法沿用第二版:詞元;←來源、→目的、:來源→目的、@所在;玩家前綴連寫;
    :受事者中心詞(多個以 / 並列);→目的中心詞;否定形 (耐性)/(限制);詞元節點就是詞元名。"""

    def test_lemma_node_is_named_by_its_lemma(self):
        self.assertEqual(names(query("特殊召喚")), ["特殊召喚"])

    def test_regions_use_the_second_edition_arrows(self):
        self.assertEqual(names(query("特殊召喚", 來源=[[None, "墓地"]]),
                               query("戻す", 目的=[[None, "牌組"]]),
                               query("加える", 來源=[[None, "牌組"]], 目的=[[None, "手牌"]]),
                               query("破壊", 所在=[[None, "場上"]]),
                               query("選ぶ", 所在=[[None, "額外牌組"]]),
                               query("置く", 目的=[[None, "靈擺區"]])),
                         ["特殊召喚←墓地", "戻す→デッキ", "加える:デッキ→手札", "破壊@フィールド", "選ぶ@EXデッキ",
                          "置く→Pゾーン"])

    def test_player_prefix_is_written_before_the_zone(self):
        self.assertEqual(names(query("破壊", 所在=[["相手", "場上"]]),
                               query("除外", 來源=[["自分", "墓地"]]),
                               query("取り除く", 所在=[["お互い", "場上"]])),
                         ["破壊@相手フィールド", "除外←自分墓地", "取り除く@お互いのフィールド"])

    def test_patient_heads_are_joined_with_a_slash(self):
        self.assertEqual(names(query("破壊", 受事者中心詞=["魔法カード", "罠カード"]),
                               query("アップ", 受事者中心詞=["攻撃力"])),
                         ["破壊:魔法カード/罠カード", "アップ:攻撃力"])

    def test_goal_heads_use_the_goal_arrow(self):
        self.assertEqual(names(query("にする", 目的中心詞=["裏側守備表示"]),
                               query("にする", 目的中心詞=["属性", "族"])),
                         ["にする→裏側守備表示", "にする→属性/族"])

    def test_resistance_and_restriction_come_from_the_negation_set(self):
        self.assertEqual(names(query("破壊", 否定形=["受身", "不成不受"]),
                               query("破壊", 否定形=["不成不受", "受身"], 所在=[["自分", "場上"]]),
                               query("発動", 否定形=["不可能"])),
                         ["破壊(耐性)", "破壊@自分フィールド(耐性)", "発動(限制)"])

    def test_a_single_lemma_string_is_the_only_lemma_shape(self):
        self.assertEqual(names(query("破壊", 極性=["肯定", "可能"])), ["破壊"])


class TestLoadedPredicate(unittest.TestCase):
    """載入後的述詞是明文的:極性省略時補成清單(沒寫否定形 → 肯定與可能;寫了否定形 → 否定),
    寫了的照寫;述詞用的是 predicate.FIELDS 的欄名。"""

    def test_omitted_polarity_becomes_affirmative_and_possible(self):
        cat = load(query("特殊召喚", 來源=[[None, "墓地"]]))
        self.assertEqual(cat.queries[0].predicate,
                         {"詞元": "特殊召喚", "極性": ["肯定", "可能"], "來源": [[None, "墓地"]]})

    def test_omitted_polarity_with_a_negation_form_becomes_negative(self):
        cat = load(query("破壊", 否定形=["受身", "不成不受"]))
        self.assertEqual(cat.queries[0].predicate, {"詞元": "破壊", "極性": ["否定"], "否定形": ["受身", "不成不受"]})

    def test_written_polarity_is_kept(self):
        cat = load(query("破壊", 極性=["可能", "肯定"]))
        self.assertEqual(cat.queries[0].predicate["極性"], ["可能", "肯定"])

    def test_loaded_predicates_pass_the_vocabulary_check(self):
        cat = load(query("破壊", children=[query("破壊", 所在=[["相手", "場上"]]), query("破壊", 否定形=["不可能"])]))
        for q in cat.queries:
            self.assertEqual(predicate.problems(q.predicate), [])


class TestNameScope(unittest.TestCase):
    """名字唯一的口徑(2026-11-01 code review 修正寫明):具名查詢之間唯一、頂層節點之間唯一;大類與它底下的同名
    具名查詢合法(召喚 › 召喚 收合成一段路徑)。"""

    def test_a_major_may_contain_a_named_query_of_the_same_name(self):
        cat = load(major("召喚", [query("召喚", children=[query("召喚", 來源=[[None, "手牌"]])])]))
        self.assertEqual([q.name for q in cat.queries], ["召喚", "召喚←手札"])
        self.assertEqual([list(q.path) for q in cat.queries], [["召喚"], ["召喚", "召喚←手札"]])
        self.assertEqual(cat.members("召喚"), ["召喚", "召喚←手札"])

    def test_a_top_level_named_query_may_not_share_a_name_with_a_major(self):
        self.assertIn("大類名重複:召喚", failure(major("召喚", [query("通常召喚")]), query("召喚")))

    def test_two_named_queries_may_not_share_a_name_even_under_different_majors(self):
        self.assertIn("名字重複:召喚", failure(major("召喚", [query("召喚")]), major("處理程序", [query("召喚")])))


class TestChecks(unittest.TestCase):
    """違反即載入失敗,訊息列全部違反處。"""

    def test_duplicate_names_are_listed(self):
        message = failure(query("破壊", children=[query("破壊", 受事者中心詞=["モンスター"]),
                                                 query("破壊", 受事者中心詞=["モンスター"])]))
        self.assertIn("名字重複:破壊:モンスター", message)

    def test_values_outside_the_domain_are_listed(self):
        message = failure(query("除外", 來源=[["雙方", "墓地"]]), query("破壊", 所在=[[None, "フィールド"]]))
        self.assertIn("來源 的玩家不在值域:雙方", message)
        self.assertIn("所在 的區域不在值域:フィールド", message)

    def test_a_non_canonical_lemma_is_listed(self):
        message = failure(query("戻る"))
        self.assertIn("戻る", message)
        self.assertIn("正規詞元是 戻す", message)

    def test_a_major_without_a_named_query_is_listed(self):
        self.assertIn("大類 空 底下沒有具名查詢", failure(major("空", [])))
        message = failure(major("甲", [query("破壊", 大類="乙")]), major("乙", [query("選ぶ")]))
        self.assertIn("大類 甲 底下的具名查詢都宣告到別的大類", message)

    def test_a_name_with_the_path_separator_is_listed(self):
        message = failure(major("甲›乙", [query("破壊")]), query("選ぶ", 受事者中心詞=["カード›1枚"]))
        self.assertIn("節點名含網址路徑分隔符 ›:甲›乙", message)
        self.assertIn("節點名含網址路徑分隔符 ›:選ぶ:カード›1枚", message)

    def test_a_field_without_a_naming_rule_is_listed(self):
        message = failure(query("破壊", 施事者=["自分"]), query("破壊", 態=["受身"]))
        self.assertIn("沒有命名規則的欄:施事者", message)
        self.assertIn("沒有命名規則的欄:態", message)

    def test_a_negation_set_or_polarity_without_a_naming_rule_is_listed(self):
        message = failure(query("破壊", 否定形=["一般"]), query("破壊", 極性=["否定"]),
                          query("選ぶ", 極性=["肯定"], 否定形=["不可能"]))
        self.assertIn("否定形集合沒有命名規則", message)
        self.assertIn("極性沒有命名規則", message)
        self.assertEqual(message.count("極性沒有命名規則"), 2)

    def test_multi_value_regions_and_relative_players_have_no_naming_rule(self):
        message = failure(query("除外", 來源=[[None, "墓地"], [None, "手牌"]]), query("破壊", 所在=[["相對", "墓地"]]))
        self.assertIn("來源 多值沒有命名規則", message)
        self.assertIn("所在 的玩家 相對 沒有命名規則", message)

    def test_declared_major_and_middle_must_exist(self):
        message = failure(major("甲", [query("破壊", 大類="丙"), query("選ぶ", 中類="無此中類")]))
        self.assertIn("宣告的大類 丙 不是頂層大類", message)
        self.assertIn("宣告的中類 無此中類 不在大類 甲 的中類清單", message)

    def test_middle_names_must_not_collide_or_go_unused(self):
        message = failure(major("甲", [query("破壊", 中類="破壊")], middles=["破壊", "沒人用"]))
        self.assertIn("大類 甲 的中類 破壊 與具名查詢同名", message)
        self.assertIn("大類 甲 的中類 沒人用 沒有具名查詢", message)

    def test_unknown_keys_and_a_missing_lemma_are_listed(self):
        message = failure({"述詞": {"來源": [[None, "墓地"]]}}, {"述詞": {"詞元": "破壊"}, "關鍵詞": ["x"]},
                          {"葉": "舊形狀"})
        self.assertIn("述詞要有單值的詞元", message)
        self.assertIn("不認得的鍵:關鍵詞", message)
        self.assertIn("不是大類也不是具名查詢", message)


class TestTree(unittest.TestCase):
    """路徑、大類與中類的聯集由樹推得。"""

    def tree(self):
        return load(major("區域移動", [
            query("加える", children=[query("加える", 來源=[[None, "牌組"]], 目的=[[None, "手牌"]], 中類="←デッキ"),
                                      query("加える", 目的=[[None, "手牌"]])]),
            query("ドロー")], middles=["←デッキ"]),
            major("數值", [query("にする", children=[query("にする", 受事者中心詞=["攻撃力"]),
                                                     query("にする", 目的中心詞=["属性"], 大類="規則改寫")])]),
            major("規則改寫", [query("扱う")]),
            query("破壊", children=[query("破壊", 所在=[[None, "場上"]])]))

    def test_paths_follow_declared_major_and_middle(self):
        paths = {q.name: list(q.path) for q in self.tree().queries}
        self.assertEqual(paths["加える:デッキ→手札"], ["區域移動", "←デッキ", "加える:デッキ→手札"])
        self.assertEqual(paths["加える→手札"], ["區域移動", "加える", "加える→手札"])
        self.assertEqual(paths["にする→属性"], ["規則改寫", "にする", "にする→属性"])
        self.assertEqual(paths["破壊"], ["破壊"])
        self.assertEqual(paths["破壊@フィールド"], ["破壊", "破壊@フィールド"])

    def test_major_and_middle_members_are_unions_of_named_queries(self):
        cat = self.tree()
        self.assertEqual(cat.members("區域移動"), ["加える", "加える:デッキ→手札", "加える→手札", "ドロー"])
        self.assertEqual(cat.members("區域移動", "←デッキ"), ["加える:デッキ→手札"])
        self.assertEqual(cat.members("規則改寫"), ["にする→属性", "扱う"])
        self.assertEqual(cat.members("破壊"), ["破壊", "破壊@フィールド"])
        self.assertEqual(cat.majors, ["區域移動", "數值", "規則改寫", "破壊"])
        self.assertEqual(cat.middles, {"區域移動": ["←デッキ"]})

    def test_queries_are_in_catalog_order_and_children_hang_on_their_parent(self):
        cat = self.tree()
        self.assertEqual([q.name for q in cat.queries][:3], ["加える", "加える:デッキ→手札", "加える→手札"])
        self.assertEqual([c.name for c in cat.by_name["加える"].children], ["加える:デッキ→手札", "加える→手札"])


class TestRealCatalog(unittest.TestCase):
    """真目錄載入過檢查;每個具名查詢名與改寫對應表一致(舊 233 葉 + 100 詞元節點 → 新節點名,236 個具名查詢;
    2026-11-01 站主裁定加 対象とする 詞元節點 → 237,對應表的種類 裁定新增、舊名 null)。"""

    @classmethod
    def setUpClass(cls):
        cls.catalog = catalog.load()
        with open(MAPPING, encoding="utf-8") as f:
            cls.mapping = json.load(f)["對應"]

    def test_mapping_covers_the_old_tree(self):
        kinds = {}
        for _, kind, _ in self.mapping:
            kinds[kind] = kinds.get(kind, 0) + 1
        self.assertEqual(kinds, {"葉": 136, "預設葉": 97, "詞元節點": 100, "裁定新增": 1})
        self.assertEqual(len(self.catalog.queries), 237)

    def test_every_node_name_matches_the_mapping(self):
        self.assertEqual(sorted(q.name for q in self.catalog.queries), sorted({new for _, _, new in self.mapping}))
        for old, kind, new in self.mapping:
            with self.subTest(new):
                self.assertIn(new, self.catalog.by_name)
                if kind == "裁定新增":
                    self.assertIsNone(old)     # 改寫之後加的節點沒有舊名
                else:
                    self.assertEqual(new, old)     # 改寫不改名

    def test_every_predicate_is_explicit_and_in_the_vocabulary(self):
        for q in self.catalog.queries:
            with self.subTest(q.name):
                self.assertIn("極性", q.predicate)
                self.assertEqual(predicate.problems(q.predicate), [])
                self.assertIsInstance(q.predicate["詞元"], str)


if __name__ == "__main__":
    unittest.main()
