"""效果 Tag 線的行為測試(票07/09/10/13)。

接縫與 test_tagcard 相同:tagcard.build_tag_cards 純函式,fixture 程式化建立。
只測外部行為:規則直貼、重跑保留、判空紀錄擋規則、時機承載、遮蔽計分、
收票關卡的少一筆多一筆指名道姓。
"""
import unittest

import masked_tags
import merge_tag_judgments as mtj
import tag_rules
from tagcard import build_tag_cards
from test_tagcard import card, clauses_of, faq, mark

SEARCH = "①：デッキから「試作機」１体を手札に加える。"
SEARCH_JA = "①：デッキから「試作機」１体を手札に加える。"
COST_SEARCH_ZH = "①：捨棄1張手牌可以發動。從牌組將1隻怪獸加入手牌。"
COST_SEARCH_JA = ("①：手札を１枚捨てて発動できる。"
                  "デッキからモンスター１体を手札に加える。")


def build(desc, card_text, **kwargs):
    return build_tag_cards([card(desc=desc)], [faq(card_text=card_text)],
                           **kwargs)


def tag_contents(clause):
    return {tuple(sorted((k, v) for k, v in tag.items()
                         if k not in ("src", "rule", "ticket")))
            for tag in clause["tags"]}


class TestRuleDirectWrite(unittest.TestCase):
    """規則層直接寫入 tags(ADR-0013),不是影子預測。"""

    def test_search_frame_writes_a_rule_tag(self):
        entries, report = build(SEARCH, SEARCH_JA)
        clause = clauses_of(entries, 1000)[0]
        tags = [t for t in clause["tags"] if t["src"] == "rule"]
        self.assertTrue(any(t.get("from") == "牌組" and t.get("to") == "手牌"
                            and t["pos"] == "效果" for t in tags))
        self.assertGreater(report["tag_rule_tags"], 0)

    def test_cost_in_activation_clause_is_tagged_as_cost(self):
        entries, _ = build(COST_SEARCH_ZH, COST_SEARCH_JA)
        clause = clauses_of(entries, 1000)[0]
        poses = {(t.get("from"), t.get("to"), t["pos"])
                 for t in clause["tags"]}
        self.assertIn(("手牌", "墓地", "成本"), poses)
        self.assertIn(("牌組", "手牌", "效果"), poses)

    def test_trigger_condition_is_not_tagged_as_movement(self):
        """觸發條件住在發動子句裡,處理段規則咬不到它。"""
        entries, _ = build(
            "①：怪獸被特殊召喚時可以發動。攻擊力上升500。",
            "①：モンスターが特殊召喚された場合に発動できる。"
            "攻撃力は５００アップする。")
        self.assertEqual(clauses_of(entries, 1000)[0]["tags"], [])

    def test_old_style_clauses_are_out_of_scope(self):
        """第一期只貼新式卡文(index 帶①編號)。"""
        entries, report = build("從牌組將1隻怪獸加入手牌。",
                                "デッキからモンスター１体を手札に加える。")
        self.assertEqual(clauses_of(entries, 1000)[0]["tags"], [])
        self.assertEqual(report["tag_scope_clauses"], 0)


class TestTagPreservation(unittest.TestCase):
    """llm/manual 的 tag 走「判定一次就算數」,rule 的 tag 每次重算。"""

    def rebuilt_with_llm_tag(self, tag):
        existing, _ = build(SEARCH, SEARCH_JA)
        clause = clauses_of(existing, 1000)[0]
        mark(existing, 1000, "①", tags=clause["tags"] + [tag])
        return build(SEARCH, SEARCH_JA, existing=existing)

    def test_llm_tag_survives_rebuild_even_on_rule_sourced_kind(self):
        """kind 是 rule 來源的行也可能帶著 llm tag,不得隨重跑洗掉。"""
        llm_tag = {"cat": "區域移動", "to": "場上", "pos": "效果",
                   "src": "llm", "ticket": "票T"}
        entries, _ = self.rebuilt_with_llm_tag(llm_tag)
        clause = clauses_of(entries, 1000)[0]
        self.assertIn(("cat", "區域移動"),
                      [item for tags in tag_contents(clause)
                       for item in tags])
        self.assertTrue(any(t.get("src") == "llm" and t.get("to") == "場上"
                            for t in clause["tags"]))

    def test_identical_content_upgrades_to_llm_then_rule(self):
        llm_tag = {"cat": "區域移動", "from": "牌組", "to": "手牌",
                   "pos": "效果", "src": "llm", "ticket": "票T"}
        existing, _ = build(SEARCH, SEARCH_JA)
        mark(existing, 1000, "①", tags=[llm_tag])
        entries, _ = build(SEARCH, SEARCH_JA, existing=existing)
        clause = clauses_of(entries, 1000)[0]
        srcs = [t["src"] for t in clause["tags"]
                if t.get("from") == "牌組" and t.get("to") == "手牌"]
        self.assertEqual(srcs, ["llm_then_rule"])

    def test_checked_category_blocks_rule_write_and_reports(self):
        """LLM 判空的類別,規則不再寫入,不一致進報告。"""
        existing, _ = build(SEARCH, SEARCH_JA)
        mark(existing, 1000, "①", tags=[], tags_checked=["區域移動"])
        entries, report = build(SEARCH, SEARCH_JA, existing=existing)
        clause = clauses_of(entries, 1000)[0]
        self.assertEqual(clause["tags"], [])
        self.assertEqual(clause["tags_checked"], ["區域移動"])
        # 檢索句同時命中特定與泛用兩條規則,兩個被擋的 tag 都要看得見
        self.assertGreaterEqual(len(report["tag_rule_vs_llm"]), 1)
        self.assertTrue(all(row["id"] == 1000
                            for row in report["tag_rule_vs_llm"]))


class TestTiming(unittest.TestCase):
    """觸發時機:只長在誘發系承載類型、規則值重算、llm 值保留。"""

    TRIGGER_ZH = "①:此卡召喚成功時發動。抽1張卡。"
    TRIGGER_JA = ("①：このカードが召喚に成功した場合に発動する。"
                  "自分はデッキから１枚ドローする。")

    def judged(self, kind):
        judgments = [{"id": 1000, "section": "main",
                      "clauses": [{"index": "①", "kind": kind,
                                   "optional": "必發"}]}]
        return build(self.TRIGGER_ZH, self.TRIGGER_JA, judgments=judgments)

    def test_trigger_kind_gets_rule_timing(self):
        entries, _ = self.judged("誘發效果(1速)")
        clause = clauses_of(entries, 1000)[0]
        self.assertEqual((clause["timing"], clause["timing_src"]),
                         ("召喚成功時", "rule"))

    def test_non_carrier_kind_gets_no_timing(self):
        entries, report = self.judged("永續效果")
        clause = clauses_of(entries, 1000)[0]
        self.assertIsNone(clause["timing"])
        self.assertEqual(report["timing_on_wrong_kind"], [])

    def test_llm_timing_survives_and_conflicts_are_reported(self):
        entries, _ = self.judged("誘發效果(1速)")
        mark(entries, 1000, "①", timing="其他", timing_src="llm")
        rebuilt, report = build(self.TRIGGER_ZH, self.TRIGGER_JA,
                                existing=entries)
        clause = clauses_of(rebuilt, 1000)[0]
        # kind 隨 existing 保留,規則時機與 llm 值不同 → 保留 llm、列衝突
        self.assertEqual((clause["timing"], clause["timing_src"]),
                         ("其他", "llm"))
        self.assertEqual(len(report["timing_rule_vs_llm"]), 1)

    def test_matching_llm_timing_upgrades(self):
        entries, _ = self.judged("誘發效果(1速)")
        mark(entries, 1000, "①", timing="召喚成功時", timing_src="llm")
        rebuilt, _ = build(self.TRIGGER_ZH, self.TRIGGER_JA,
                           existing=entries)
        clause = clauses_of(rebuilt, 1000)[0]
        self.assertEqual(clause["timing_src"], "llm_then_rule")


class TestMaskedTags(unittest.TestCase):
    """遮蔽測試計分:錯標與框架 recall 都對著標準答案現場重算。"""

    def setUp(self):
        self.entries, _ = build(SEARCH, SEARCH_JA)
        self.sample = [{"id": 1000, "section": "main", "index": "①",
                        "name_zh": "測試卡", "text_zh": SEARCH,
                        "text_ja": SEARCH_JA}]

    def score(self, tags):
        answers = [{"id": 1000, "section": "main", "index": "①",
                    "tags": tags}]
        return masked_tags.score_tag_masked(self.entries, self.sample,
                                            answers)

    def test_agreeing_truth_passes(self):
        res = self.score([{"cat": "區域移動", "from": "牌組", "to": "手牌",
                           "side": "我方", "pos": "效果"}])
        self.assertEqual(sum(r["wrong"] for r in res["rules"]), 0)
        self.assertEqual(res["category_recall"], 1.0)

    def test_disagreeing_truth_counts_a_wrong(self):
        res = self.score([{"cat": "區域移動", "from": "墓地", "to": "手牌",
                           "pos": "效果"}])
        self.assertGreater(sum(r["wrong"] for r in res["rules"]), 0)
        self.assertFalse(res["passed"])

    def test_missing_answer_is_named(self):
        res = masked_tags.score_tag_masked(self.entries, self.sample, [])
        self.assertEqual(res["missing"], [(1000, "main", "①")])
        self.assertFalse(res["passed"])


class TestMergeGates(unittest.TestCase):
    """收票關卡:少一筆多一筆指名道姓、值不在正典、改判旗標對帳。"""

    BATCH = {"series": "tag-mv", "category": "區域移動", "entries": [
        {"id": 1000, "section": "main", "index": "①",
         "text_ja": SEARCH_JA, "kind": "啟動效果"},
        {"id": 1000, "section": "main", "index": "②",
         "text_ja": "②：効果乙。", "kind": "啟動效果", "rejudge": True},
    ]}

    def test_missing_and_extra_rows_are_named(self):
        result = [{"id": 1000, "section": "main", "index": "①", "tags": []},
                  {"id": 9999, "section": "main", "index": "①", "tags": []}]
        problems = mtj.set_problems(self.BATCH, result)
        self.assertTrue(any("少了 (1000, 'main', '②')" in p
                            for p in problems))
        self.assertTrue(any("多了 (9999, 'main', '①')" in p
                            for p in problems))

    def test_rejudge_flags_must_match_both_ways(self):
        result = [{"id": 1000, "section": "main", "index": "①", "tags": [],
                   "rejudge": True},
                  {"id": 1000, "section": "main", "index": "②", "tags": []}]
        problems = mtj.rejudge_problems(self.BATCH, result)
        self.assertEqual(len(problems), 2)

    def test_out_of_canon_value_is_named(self):
        result = [{"id": 1000, "section": "main", "index": "①",
                   "tags": [{"cat": "區域移動", "from": "牌組頂",
                             "to": "手牌", "pos": "效果"}]},
                  {"id": 1000, "section": "main", "index": "②", "tags": [],
                   "rejudge": True}]
        problems = mtj.value_problems(self.BATCH, result)
        self.assertEqual(len(problems), 1)
        self.assertIn("解不進正典", problems[0])

    def test_apply_marks_checked_and_stamps_ticket(self):
        entries, _ = build(SEARCH, SEARCH_JA)
        batch = {"series": "tag-mv", "category": "區域移動", "entries": [
            {"id": 1000, "section": "main", "index": "①",
             "text_ja": SEARCH_JA, "kind": None}]}
        result = [{"id": 1000, "section": "main", "index": "①",
                   "tags": [{"cat": "區域移動", "to": "手牌",
                             "pos": "效果"}]}]
        problems = mtj.apply_rows(entries, batch, result, "票測")
        self.assertEqual(problems, [])
        clause = clauses_of(entries, 1000)[0]
        self.assertIn("區域移動", clause["tags_checked"])
        self.assertTrue(any(t.get("ticket") == "票測" and t["src"] == "llm"
                            for t in clause["tags"]))

    def test_stale_text_is_rejected(self):
        entries, _ = build(SEARCH, SEARCH_JA)
        batch = {"series": "tag-mv", "category": "區域移動", "entries": [
            {"id": 1000, "section": "main", "index": "①",
             "text_ja": "①：昔の文。", "kind": None}]}
        result = [{"id": 1000, "section": "main", "index": "①", "tags": []}]
        problems = mtj.apply_rows(entries, batch, result, "票測")
        self.assertEqual(len(problems), 1)
        self.assertIn("卡文已變動", problems[0])


class TestScreenAndRegistry(unittest.TestCase):
    def test_screen_hits_action_not_pure_negation(self):
        self.assertTrue(tag_rules.screen_hit(
            "區域移動", "デッキからモンスター１体を特殊召喚する。"))
        self.assertFalse(tag_rules.screen_hit(
            "區域移動", "お互いにモンスターを特殊召喚できない。"))

    def test_registry_is_clean(self):
        self.assertEqual(tag_rules.problems(), [])


if __name__ == "__main__":
    unittest.main()
