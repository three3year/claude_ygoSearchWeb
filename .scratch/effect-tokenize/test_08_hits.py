# -*- coding: utf-8 -*-
"""具名查詢命中的行為測試(named-queries 票 08)。

接縫:一句效果句原文 → 每個動作框架命中的具名查詢名清單(catalog_hits.query_names;目錄序,不互斥)。
真目錄 catalog.json 一個句型一條(不互斥並收、所在取自來源、否定形 耐性/限制、詞元節點不含否定、尾綴);
機制(同欄多值、欄間 AND、尾綴、不看玩家)以測試小目錄驗,經同一接縫的目錄參數。另:匯出檔目錄欄的列(名、
路徑、述詞、三個位置的張數、卡集合雜湊;大類/中類是聯集)、「至少命中一張」的建置期檢查、重跑鏈的目錄一步。
只斷言命中的名字、目錄列與問題清單,不斷言怎麼比、樹怎麼存。

執行:PYTHONIOENCODING=utf-8 python -m unittest discover -s .scratch/effect-tokenize
"""
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import catalog  # noqa: E402
import catalog_hits  # noqa: E402
import export_frames  # noqa: E402
from constraints import POSITIONS  # noqa: E402
from test_05_export_frames import chain, clause, sha  # noqa: E402


def names(text, cat=None):
    return catalog_hits.query_names(text, cat=cat)



def query(lemma, children=None, **fields):
    """測試小目錄的具名查詢節點(寫法同 test_07_catalog)。"""
    node = {key: fields.pop(key) for key in ("大類", "中類") if key in fields}
    node["述詞"] = dict({"詞元": lemma}, **fields)
    if children is not None:
        node["子"] = children
    return node


# 機制用的小目錄:同欄多值(受事者中心詞 魔法カード/罠カード)、欄間 AND(來源 + 受事者中心詞)、尾綴、
# 不看玩家(所在 [null, 場上])、否定形;大類 小目錄 列中類 墓地系
SMALL = {"樹": [
    {"大類": "小目錄", "中類": ["墓地系"], "子": [
        query("特殊召喚", [
            query("特殊召喚", 來源=[[None, "墓地"]], 中類="墓地系"),
            query("特殊召喚", 來源=[[None, "墓地"]], 受事者中心詞=["モンスター"], 中類="墓地系"),
        ]),
        query("破壊", [
            query("破壊", 受事者中心詞=["魔法カード", "罠カード"]),
            query("破壊", 受事者中心詞=["モンスター"]),
            query("破壊", 所在=[[None, "場上"]]),
            query("破壊", 否定形=["受身", "不成不受"]),
        ]),
    ]},
]}


def small():
    return catalog.Catalog(SMALL)


class TestRealCatalog(unittest.TestCase):
    """真目錄:一個句型一條;具名查詢不互斥、沒有預設葉,命中清單是目錄序。"""

    def test_destroying_an_opponent_monster_hits_every_fitting_query(self):
        """不互斥並收:詞元節點、受事者中心詞、所在(含玩家與不看玩家)同時命中。"""
        self.assertEqual(names("①：相手フィールドのモンスター１体を破壊する。"),
                         [["破壊", "破壊:モンスター", "破壊@相手フィールド", "破壊@フィールド"]])

    def test_place_taken_from_the_source_of_a_non_moving_action(self):
        """所在取自來源:手札・墓地から選ぶ 的所在是取自來源寫進的,選ぶ@墓地 與 選ぶ@手札 都中;
        接著的 特殊召喚 讀來源。"""
        self.assertEqual(names("①：自分の手札・墓地からモンスター１体を選んで特殊召喚する。"),
                         [["選ぶ", "選ぶ@自分手札", "選ぶ@手札", "選ぶ@自分墓地", "選ぶ@墓地"],
                          ["特殊召喚", "特殊召喚←手札", "特殊召喚←墓地"]])

    def test_resistance_reads_the_negation_form_and_the_lemma_node_excludes_negation(self):
        """否定形:破壊されない 命中 破壊(耐性);詞元節點 破壊 是肯定與可能,不含否定框架。"""
        self.assertEqual(names("①：このカードは効果では破壊されない。"), [["破壊(耐性)"]])

    def test_restriction_reads_the_cannot_form(self):
        self.assertEqual(names("①：このカードは攻撃できない。"), [["攻撃(限制)"]])

    def test_patient_head_matches_by_suffix(self):
        """尾綴:効果モンスター 以 モンスター 結尾、中 破壊:モンスター;モンスターカード 不中。"""
        self.assertEqual(names("①：相手フィールドの効果モンスター１体を破壊する。"),
                         [["破壊", "破壊:モンスター", "破壊@相手フィールド", "破壊@フィールド"]])
        self.assertEqual(names("①：相手フィールドのモンスターカード１枚を破壊する。"),
                         [["破壊", "破壊@相手フィールド", "破壊@フィールド"]])

    def test_every_position_counts_and_a_frame_may_hit_nothing(self):
        """三個位置都算:代價位的 リリース 命中詞元節點;條件位的 対象とする 沒有具名查詢,清單空。"""
        self.assertEqual(names("①：自分フィールドのモンスター１体をリリースして発動できる。"
                               "自分の墓地のモンスター１体を対象として発動できる。そのモンスターを特殊召喚する。"),
                         [["リリース"], [], ["特殊召喚", "特殊召喚←墓地"]])


class TestMechanics(unittest.TestCase):
    """機制以小目錄驗,經同一接縫的目錄參數:同欄多值 OR、欄間 AND、尾綴、不看玩家。"""

    def test_values_in_one_field_are_alternatives(self):
        self.assertEqual(names("①：相手フィールドの罠カード１枚を破壊する。", small()),
                         [["破壊", "破壊:魔法カード/罠カード", "破壊@フィールド"]])
        self.assertEqual(names("①：相手フィールドの魔法カード１枚を破壊する。", small()),
                         [["破壊", "破壊:魔法カード/罠カード", "破壊@フィールド"]])

    def test_fields_are_conjoined(self):
        """來源 墓地 且 受事者中心詞 モンスター 才中第二片;卡名受事者只中來源那片。"""
        self.assertEqual(names("①：自分の墓地からモンスター１体を特殊召喚する。", small()),
                         [["特殊召喚", "特殊召喚←墓地", "特殊召喚←墓地:モンスター"]])
        self.assertEqual(names("①：自分の墓地から「青眼の白龍」１体を特殊召喚する。", small()),
                         [["特殊召喚", "特殊召喚←墓地"]])

    def test_head_suffix_not_prefix(self):
        self.assertEqual(names("①：自分フィールドの表側表示モンスター１体を破壊する。", small()),
                         [["破壊", "破壊:モンスター", "破壊@フィールド"]])
        self.assertEqual(names("①：フィールドのモンスターカード１枚を破壊する。", small()),
                         [["破壊", "破壊@フィールド"]])

    def test_region_without_player_ignores_the_player(self):
        for text in ("①：相手フィールドのカード１枚を破壊する。", "①：自分フィールドのカード１枚を破壊する。"):
            with self.subTest(text):
                self.assertEqual(names(text, small()), [["破壊", "破壊@フィールド"]])

    def test_negation_form_query_only_hits_negated_frames(self):
        self.assertEqual(names("①：このカードは戦闘では破壊されない。", small()), [["破壊(耐性)"]])


# 匯出目錄欄用的合成卡(小目錄):效果位 5 張、代價位 1 張(卡 6 的 破壊 在代價位)
EXPORT_CARDS = {
    1: [clause("①", "①：自分の墓地からモンスター１体を特殊召喚する。")],
    2: [clause("①", "①：手札を１枚捨てて発動できる。自分の墓地から「青眼の白龍」１体を特殊召喚する。")],
    3: [clause("①", "①：相手フィールドの罠カード１枚を破壊する。")],
    4: [clause("①", "①：自分フィールドの表側表示モンスター１体を破壊する。")],
    5: [clause("①", "①：このカードは効果では破壊されない。")],
    6: [clause("①", "①：自分フィールドのモンスター１体を破壊して発動できる。自分の墓地からモンスター１体を特殊召喚する。")],
}
NONE = {"代價": 0, "效果": 0, "條件": 0}


def counts(**positions):
    return dict(NONE, **positions)


def hashes(**positions):
    return {position: sha(positions.get(position, "")) for position in NONE}


class TestExportCatalog(unittest.TestCase):
    """匯出檔的目錄欄:每個節點一列(名、路徑、述詞或空、三個位置的張數、卡集合雜湊),目錄序;大類/中類的
    張數是底下具名查詢的聯集;「至少命中一張」違反時匯出失敗、問題清單列名字。"""

    def test_catalog_rows_in_catalog_order_with_counts_per_position(self):
        doc, problems = export_frames.export(chain(EXPORT_CARDS), cat=small())
        self.assertEqual(problems, [])
        rows = doc["目錄"]
        self.assertEqual([(r["name"], r["path"], r["cards"]) for r in rows], [
            ("小目錄", ["小目錄"], counts(代價=1, 效果=6)),
            ("墓地系", ["小目錄", "墓地系"], counts(效果=3)),
            ("特殊召喚", ["小目錄", "特殊召喚"], counts(效果=3)),
            ("特殊召喚←墓地", ["小目錄", "墓地系", "特殊召喚←墓地"], counts(效果=3)),
            ("特殊召喚←墓地:モンスター", ["小目錄", "墓地系", "特殊召喚←墓地:モンスター"], counts(效果=2)),
            ("破壊", ["小目錄", "破壊"], counts(代價=1, 效果=2)),
            ("破壊:魔法カード/罠カード", ["小目錄", "破壊", "破壊:魔法カード/罠カード"], counts(效果=1)),
            ("破壊:モンスター", ["小目錄", "破壊", "破壊:モンスター"], counts(代價=1, 效果=1)),
            ("破壊@フィールド", ["小目錄", "破壊", "破壊@フィールド"], counts(代價=1, 效果=2)),
            ("破壊(耐性)", ["小目錄", "破壊", "破壊(耐性)"], counts(效果=1)),
        ])
        self.assertEqual([list(r) for r in rows], [list(export_frames.CATALOG_KEYS)] * len(rows))

    def test_predicates_and_hashes_of_the_card_sets(self):
        doc, _ = export_frames.export(chain(EXPORT_CARDS), cat=small())
        rows = {r["name"]: r for r in doc["目錄"]}
        self.assertIsNone(rows["小目錄"]["predicate"])
        self.assertIsNone(rows["墓地系"]["predicate"])
        self.assertEqual(rows["特殊召喚"]["predicate"], {"詞元": "特殊召喚", "極性": ["肯定", "可能"]})
        self.assertEqual(rows["破壊(耐性)"]["predicate"],
                         {"詞元": "破壊", "否定形": ["受身", "不成不受"], "極性": ["否定"]})
        self.assertEqual(rows["小目錄"]["hash"], hashes(代價="6", 效果="1,2,3,4,5,6"))
        self.assertEqual(rows["墓地系"]["hash"], hashes(效果="1,2,6"))
        self.assertEqual(rows["破壊:モンスター"]["hash"], hashes(代價="6", 效果="4"))

    def test_a_query_with_no_card_in_any_position_fails_the_export(self):
        doc, problems = export_frames.export(chain({1: EXPORT_CARDS[1]}), cat=small())
        self.assertEqual(problems, [
            "具名查詢在全語料三個位置都沒有命中(不留):破壊",
            "具名查詢在全語料三個位置都沒有命中(不留):破壊:魔法カード/罠カード",
            "具名查詢在全語料三個位置都沒有命中(不留):破壊:モンスター",
            "具名查詢在全語料三個位置都沒有命中(不留):破壊@フィールド",
            "具名查詢在全語料三個位置都沒有命中(不留):破壊(耐性)",
        ])

    def test_without_a_catalog_the_column_stays_empty(self):
        doc, problems = export_frames.export(chain({1: EXPORT_CARDS[1]}))
        self.assertEqual((doc["目錄"], problems), ([], []))


class TestCorpus(unittest.TestCase):
    """全語料:真目錄每個具名查詢三個位置合計至少命中一張(匯出檔目錄欄),命中中間產物與目錄欄的張數一致;
    缺輸入時略過並印原因。"""

    @classmethod
    def setUpClass(cls):
        cls.reason = None
        missing = [path for path in (export_frames.OUT, catalog_hits.OUT) if not os.path.exists(path)]
        if missing:
            cls.reason = "略過:沒有 %s(先跑 run_chain.py)" % "、".join(missing)
            print(cls.reason, file=sys.stderr)
            return
        with open(export_frames.OUT, encoding="utf-8") as f:
            cls.doc = json.load(f)
        with open(catalog_hits.OUT, encoding="utf-8") as f:
            cls.records = json.load(f)

    def setUp(self):
        if self.reason:
            self.skipTest(self.reason)

    def test_every_named_query_hits_at_least_one_card_in_some_position(self):
        cat = catalog_hits.default_catalog()
        rows = {r["name"]: r for r in self.doc["目錄"]}
        self.assertEqual([q.name for q in cat.queries if q.name not in rows], [])
        self.assertEqual([q.name for q in cat.queries if not any(rows[q.name]["cards"].values())], [])

    def test_hit_records_agree_with_the_catalog_column(self):
        """中間產物逐框的命中 → 每個具名查詢三個位置的卡集合,張數與匯出檔目錄欄相同;框數等於匯出的框數。"""
        sets = {}
        for r in self.records:
            for name in r["queries"]:
                sets.setdefault(name, {position: set() for position in POSITIONS})[r["position"]].add(r["card"])
        for row in self.doc["目錄"]:
            if row["predicate"] is None:
                continue
            with self.subTest(row["name"]):
                self.assertEqual(row["cards"], {position: len(sets.get(row["name"], {}).get(position, ()))
                                                for position in POSITIONS})
        self.assertEqual(len(self.records), sum(self.doc["統計"]["位置"].values()))


if __name__ == "__main__":
    unittest.main()
