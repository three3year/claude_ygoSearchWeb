"""前端索引管線的測試(接縫 1)。

接縫:`webindex.build_index(卡片總表條目, 效果標記表條目) → (index, report)`。
fixture 於測試內程式化建立,不碰網路也不碰真實資料檔(先例:
`script/card_list/test_cardlist.py`)。

四道一致性檢查的測試重點是**該擋的擋得住**,不是「現行資料跑得過」:每一道都餵
一份壞掉的輸入進去,斷言 report 的 problems 非空。
"""
import unittest

import vocab
from webindex import build_index, serialize_index

MONSTER = 0x21          # 怪獸 + 效果
SPELL_QUICK = 0x10002   # 速攻魔法
TRAP = 0x4              # 通常陷阱


def card(cid, **kw):
    """一筆卡片總表條目。預設是一張效果怪獸。

    非怪獸自動清空怪獸參數(比照 `cards.json` 的大類閘門,card-list 票07),
    測試明寫的值仍然優先——不變式那一條要故意違反閘門。
    """
    base = {"id": cid, "alt_ids": [], "name_zh": f"卡{cid}", "name_ja": "",
            "name_en": "", "desc": "", "type": MONSTER, "atk": 1000,
            "def": 1000, "level": 4, "race": 0x2000, "attribute": 0x20,
            "scale": 0, "link_marker": 0, "setcode": 0, "ot": 3,
            "md_rarity": "", "genesys_points": 0}
    base.update(kw)
    if not base["type"] & 0x1:
        base.update({"atk": None, "def": None, "level": 0, "race": 0,
                     "attribute": 0})
        base.update(kw)
    return base


def clause(text, kind="啟動效果", index="①", section="main",
           optional=None, role=None):
    return {"index": index, "section": section, "text_zh": text,
            "text_ja": "", "text_hash": "", "kind": kind,
            "optional": optional, "role": role, "source": "llm",
            "needs_review": False, "rule_predicted": None,
            "confidence": "high", "tags": []}


def tagged(cid, *clauses):
    return {"id": cid, "clauses": list(clauses)}


class EntryTest(unittest.TestCase):
    def test_card_fields_and_key_order(self):
        cards = [card(63028558, name_zh="青眼白龍", name_ja="青眼の白龍",
                      name_en="Blue-Eyes White Dragon",
                      desc="①：這樣。②：那樣。")]
        tags = [tagged(63028558,
                       clause("①：這樣。", kind="啟動效果"),
                       clause("②：那樣。", kind="誘發效果(1速)", index="②"))]
        index, report = build_index(cards, tags)
        entry = index["cards"][0]
        self.assertEqual(list(entry), ["id", "n", "nj", "ne", "c", "tx", "k"])
        self.assertEqual(entry["id"], 63028558)
        self.assertEqual(entry["n"], "青眼白龍")
        self.assertEqual(entry["nj"], "青眼の白龍")
        self.assertEqual(entry["ne"], "Blue-Eyes White Dragon")
        self.assertEqual(entry["tx"], ["①：這樣。", "②：那樣。"])
        self.assertEqual(report["problems"], [])

    def test_values_are_short_codes_not_chinese(self):
        """效果類型與大類存短碼,中文由 VOCAB 對照(ADR-0008)。"""
        cards = [card(1, desc="①：這樣。"), card(2, type=TRAP, desc="這樣。")]
        tags = [tagged(1, clause("①：這樣。", kind="誘發即時效果(2速)")),
                tagged(2, clause("這樣。", kind="通常陷阱卡效果", index="1"))]
        index, _ = build_index(cards, tags)
        self.assertEqual(index["cards"][0]["c"], "m")
        self.assertEqual(index["cards"][0]["k"], ["q"])
        self.assertEqual(index["cards"][1]["c"], "t")
        self.assertEqual(index["cards"][1]["k"], ["tn"])

    def test_empty_values_are_omitted_not_null(self):
        cards = [card(1, desc="①：這樣。")]
        tags = [tagged(1, clause("①：這樣。"))]
        index, _ = build_index(cards, tags)
        entry = index["cards"][0]
        for key in ("nj", "ne", "d"):
            self.assertNotIn(key, entry)

    def test_card_without_clauses_gets_flavor_text(self):
        """689 張純通常怪獸:沒有效果句,故事文進 `d` 而不是空的 `tx`。"""
        cards = [card(1, type=0x11, desc="從無人的13號墳墓突然出現的殭屍。")]
        index, report = build_index(cards, [tagged(1)])
        entry = index["cards"][0]
        self.assertEqual(entry["d"], "從無人的13號墳墓突然出現的殭屍。")
        self.assertNotIn("tx", entry)
        self.assertNotIn("k", entry)
        self.assertEqual(report["problems"], [])

    def test_pendulum_flavor_is_extracted(self):
        """靈擺通常怪獸的【怪獸敘述】段是故事文,不是效果句。"""
        desc = "【靈擺效果】\n①：這樣。\n【怪獸敘述】\n一條龍的故事。"
        cards = [card(1, type=0x1 | 0x10 | 0x1000000, desc=desc, scale=4)]
        tags = [tagged(1, clause("①：這樣。", kind="靈擺魔法卡效果",
                                 section="pendulum"))]
        index, report = build_index(cards, tags)
        entry = index["cards"][0]
        self.assertEqual(entry["tx"], ["①：這樣。"])
        self.assertEqual(entry["d"], "一條龍的故事。")
        self.assertEqual(report["problems"], [])

    def test_index_is_sorted_by_password(self):
        cards = [card(30), card(10), card(20)]
        tags = [tagged(30), tagged(10), tagged(20)]
        index, _ = build_index(cards, tags)
        self.assertEqual([c["id"] for c in index["cards"]], [10, 20, 30])


class CoverageCheckTest(unittest.TestCase):
    """效果句串接後必須覆蓋卡文,容許靈擺標頭與 `※` 別名兩種已知缺口。"""

    def test_section_headers_are_a_known_gap(self):
        desc = "【靈擺效果】\n①：這樣。\n【怪獸效果】\n②：那樣。"
        cards = [card(1, type=0x1 | 0x20 | 0x1000000, desc=desc)]
        tags = [tagged(1, clause("①：這樣。", section="pendulum"),
                       clause("②：那樣。", index="②"))]
        _, report = build_index(cards, tags)
        self.assertEqual(report["problems"], [])
        self.assertEqual(report["known_gaps"]["header"], 2)

    def test_alias_is_a_known_gap(self):
        cards = [card(1, desc="①：這樣。\n\n※另一個譯名")]
        tags = [tagged(1, clause("①：這樣。"))]
        _, report = build_index(cards, tags)
        self.assertEqual(report["problems"], [])
        self.assertEqual(report["known_gaps"]["alias"], 1)

    def test_third_kind_of_gap_fails_the_build(self):
        """第三種缺口 = 拆句或卡文出了預期外的變化,建置要倒。"""
        cards = [card(1, desc="①：這樣。②：漏掉的一句。")]
        tags = [tagged(1, clause("①：這樣。"))]
        _, report = build_index(cards, tags)
        self.assertEqual([g["gap"] for g in report["checks"]["coverage_gaps"]],
                         ["②：漏掉的一句。"])
        self.assertTrue(report["problems"])

    def test_clause_not_in_card_text_fails_the_build(self):
        cards = [card(1, desc="①：這樣。")]
        tags = [tagged(1, clause("①：完全不同的一句。"))]
        _, report = build_index(cards, tags)
        self.assertTrue(report["checks"]["clauses_not_in_desc"])
        self.assertTrue(report["problems"])


class ConsistencyCheckTest(unittest.TestCase):
    """四道檢查各自能失敗——重點是該擋的擋得住。"""

    def test_missing_card_fails_the_build(self):
        """大類解不出來的卡進不了索引,總表有卡而索引沒有 → 失敗。"""
        cards = [card(1, type=0x40)]  # 只有融合位元,沒有大類
        _, report = build_index(cards, [tagged(1)])
        self.assertEqual(report["checks"]["missing_cards"], [1])
        self.assertEqual(report["cards"], 0)
        self.assertTrue(report["problems"])

    def test_duplicate_password_fails_the_build(self):
        cards = [card(1), card(1)]
        _, report = build_index(cards, [tagged(1)])
        self.assertEqual(report["checks"]["duplicate_ids"], [1])
        self.assertTrue(report["problems"])

    def test_card_without_tag_entry_fails_the_build(self):
        _, report = build_index([card(1, desc="①：這樣。")], [])
        self.assertEqual(report["checks"]["cards_without_clause_entry"], [1])
        self.assertTrue(report["problems"])

    def test_clause_without_kind_fails_the_build(self):
        cards = [card(1, desc="①：這樣。")]
        tags = [tagged(1, clause("①：這樣。", kind=None))]
        index, report = build_index(cards, tags)
        self.assertEqual(report["checks"]["clauses_without_kind"],
                         [{"id": 1, "index": "①"}])
        self.assertEqual(index["cards"][0]["k"], [""])
        self.assertTrue(report["problems"])

    def test_kind_outside_the_canon_fails_the_build(self):
        """索引出現值域正典沒有的值 → 失敗(漏一個碼就是這個形狀)。"""
        cards = [card(1, desc="①：這樣。")]
        tags = [tagged(1, clause("①：這樣。", kind="鬼扯效果"))]
        _, report = build_index(cards, tags)
        self.assertEqual(report["checks"]["unknown_values"],
                         [{"id": 1, "field": "k", "value": "鬼扯效果",
                           "reason": "來源值對不到短碼"}])
        self.assertTrue(report["problems"])

    def test_unexplained_type_bit_fails_the_build(self):
        """`type` 冒出正典沒登記的位元:要吵,不要靜靜忽略。"""
        cards = [card(1, type=MONSTER | 0x100)]
        _, report = build_index(cards, [tagged(1)])
        self.assertEqual(report["checks"]["unexplained_type_bits"],
                         [{"id": 1, "bits": "0x100"}])
        self.assertTrue(report["problems"])


class MonsterInvariantTest(unittest.TestCase):
    """「大類是怪獸 ⟺ 有種族與屬性」雙向成立,否則建置失敗。"""

    def test_holds_on_clean_input(self):
        cards = [card(1), card(2, type=SPELL_QUICK), card(3, type=TRAP)]
        tags = [tagged(1), tagged(2), tagged(3)]
        _, report = build_index(cards, tags)
        inv = report["monster_invariant"]
        self.assertEqual(inv["monsters"], 1)
        self.assertEqual(inv["monster_missing_race_or_attribute"], [])
        self.assertEqual(inv["non_monster_with_monster_params"], [])
        self.assertEqual(report["problems"], [])

    def test_trap_with_monster_params_fails_the_build(self):
        """罠モンスター的種族是它變成怪獸之後的形態,不是卡片的參數。"""
        cards = [card(1, type=TRAP, race=0x100, attribute=0x2, level=2,
                      atk=1200)]
        _, report = build_index(cards, [tagged(1)])
        inv = report["monster_invariant"]
        self.assertEqual(inv["non_monster_with_monster_params"], [1])
        self.assertTrue(report["problems"])

    def test_monster_without_race_fails_the_build(self):
        cards = [card(1, race=0)]
        _, report = build_index(cards, [tagged(1)])
        inv = report["monster_invariant"]
        self.assertEqual(inv["monster_missing_race_or_attribute"], [1])
        self.assertTrue(report["problems"])


class ReportTest(unittest.TestCase):
    def test_census_counts_members_and_cards(self):
        """每一個值域的成員數與對應卡數:某個值掉到 0 要看得見。"""
        cards = [card(1, type=0x1 | 0x10 | 0x1000000),  # 靈擺通常怪獸
                 card(2, type=SPELL_QUICK), card(3, type=TRAP)]
        tags = [tagged(1), tagged(2), tagged(3)]
        _, report = build_index(cards, tags)
        counts = report["census"]["counts"]
        self.assertEqual(counts["cat"], {"m": 1, "s": 1, "t": 1})
        # 多位元並存:同一張卡同時算進通常與靈擺
        self.assertEqual(counts["sub_m"]["normal"], 1)
        self.assertEqual(counts["sub_m"]["pendulum"], 1)
        self.assertEqual(counts["sub_s"]["quick"], 1)
        self.assertEqual(counts["sub_t"]["normal"], 1)
        self.assertEqual(counts["race"]["dragon"], 1)
        # 非怪獸沒有屬性,那不是值域成員而是「沒有這個參數」
        self.assertEqual(report["census"]["no_value"]["attr"], 2)

    def test_report_counts_and_vocab_digest(self):
        cards = [card(1, desc="①：這樣。"), card(2, desc="①：那樣。")]
        tags = [tagged(1, clause("①：這樣。")), tagged(2, clause("①：那樣。"))]
        _, report = build_index(cards, tags)
        self.assertEqual(report["cards"], 2)
        self.assertEqual(report["clauses"], 2)
        self.assertEqual(report["vocab"]["digest"], vocab.digest())
        self.assertEqual(report["vocab"]["problems"], [])


class SerializeTest(unittest.TestCase):
    def build(self, built_at="2026-08-13T00:00:00+0800"):
        cards = [card(1, desc="①：這樣。", name_ja="日", name_en="En"),
                 card(2, type=TRAP, desc="這樣。")]
        tags = [tagged(1, clause("①：這樣。")),
                tagged(2, clause("這樣。", kind="通常陷阱卡效果", index="1"))]
        return build_index(cards, tags, built_at=built_at,
                           sources={"cards.json": "abc"})

    def test_three_globals(self):
        index, _ = self.build()
        text = serialize_index(index)
        self.assertTrue(text.startswith("window.CARD_DATA=[\n"))
        self.assertIn("\nwindow.VOCAB={\n", text)
        self.assertIn("\nwindow.META={\n", text)
        self.assertTrue(text.endswith("};\n"))
        # 一卡一行:data.js 入版控,git diff 要讀得出來
        cards_block = text.split("window.VOCAB")[0]
        self.assertEqual(cards_block.count("\n{"), 2)

    def test_meta_carries_build_context(self):
        index, _ = self.build()
        meta = index["meta"]
        self.assertEqual(meta["built_at"], "2026-08-13T00:00:00+0800")
        self.assertEqual(meta["cards"], 2)
        self.assertEqual(meta["clauses"], 2)
        self.assertEqual(meta["vocab_digest"], vocab.digest())
        self.assertEqual(meta["sources"], {"cards.json": "abc"})

    def test_same_input_builds_byte_identical_output(self):
        """時鐘與來源雜湊由呼叫端給,純函式不碰,所以重跑逐位元組相同。"""
        first, _ = self.build()
        second, _ = self.build()
        self.assertEqual(serialize_index(first), serialize_index(second))


if __name__ == "__main__":
    unittest.main()
