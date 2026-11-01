# -*- coding: utf-8 -*-
"""第四版論元(frame-args-v4)的驗收測試(票 01)。

兩個接縫:
- 單元:`closed_values.violations(records)`(封閉表外的值)、`baseline_diff.strip/diff/underscore_keys`
  (剝掉新鍵後與基準逐框比對;底線開頭的內部鍵不得出現在輸出)——用手寫的小框架清單,不讀全語料。
- 全語料:frames.json 剝掉新鍵後與基準檔(修前的全語料框架檔,`baseline/frames.json`,不入版控)
  差異 0,且剝鍵後的 md5 與入版控的 baseline-digest.json 相同(語料沒變時);封閉類沒有表外值;
  沒有底線鍵。輸入不在時 skipTest 並印原因。

各票的句型回歸例子仍放 test_frames.py(接縫 frames.extract)。

執行:PYTHONIOENCODING=utf-8 python -m unittest discover -s .scratch/effect-tokenize
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import baseline_diff  # noqa: E402
import closed_values  # noqa: E402
import frames  # noqa: E402


def record(card, *frame_list):
    """手寫的 frames.json 紀錄:一張卡的一句、帶幾個動作框架。"""
    return {"card": card, "section": "main", "index": "0", "stratum": "effect", "parts": [],
            "frames": [dict(f, kind="動作", sentence=0, option=None, label=None, order=k,
                            span=[0, 1], clause="")
                       for k, f in enumerate(frame_list)]}


def action(**fields):
    base = {"action": "破壊", "object": "モンスター", "source": None, "goal": None,
            "position": "效果", "polarity": "肯定"}
    base.update(fields)
    return base


class TestClosedValues(unittest.TestCase):
    """票 01:封閉表就是值域;表外值回 (欄位路徑, 值, 框數),沒有就是空清單。"""

    def test_frames_without_new_keys_have_no_violations(self):
        self.assertEqual(closed_values.violations([record(1, action(), action(action="除外"))]), [])

    def test_values_inside_the_tables_are_fine(self):
        fr = action(
            phrases={"object": {"text": "相手フィールドのモンスター１体", "segments": [
                {"text": "相手フィールドのモンスター１体", "head": "モンスター", "head_kind": "卡",
                 "demonstrative": False, "player": "相手", "zones": ["場上"],
                 "modifiers": [{"text": "相手フィールドの", "kind": "區域"}],
                 "quantity": {"text": "１体", "kind": "定數", "number": 1, "from_clause": False}}]}},
            regions={"place": [["相手", "場上"]]}, transfer="取自來源",
            agent="自分", agent_source="預設", agent_inferred=True,
            manner="戦闘で", manner_kind="手段:戰鬥", negation="一般", region_backfill="place")
        self.assertEqual(closed_values.violations([record(1, fr)]), [])

    def test_other_is_fine_for_head_and_modifier_kinds(self):
        fr = action(phrases={"object": {"text": "x", "segments": [
            {"text": "x", "head": "x", "head_kind": "其他", "demonstrative": False, "player": None,
             "zones": [], "modifiers": [{"text": "y", "kind": "其他"}], "quantity": None}]}})
        self.assertEqual(closed_values.violations([record(1, fr)]), [])

    def test_other_is_a_violation_for_agent_and_quantity_kind(self):
        fr = action(agent="其他", agent_source="主題",
                    phrases={"object": {"text": "x", "segments": [
                        {"text": "x", "head": "x", "head_kind": "卡", "demonstrative": False,
                         "player": None, "zones": [],
                         "quantity": {"text": "x", "kind": "其他", "number": None,
                                      "from_clause": False}}]}})
        self.assertEqual(
            closed_values.violations([record(1, fr)]),
            [("agent", "其他", 1), ("phrases.segments.quantity.kind", "其他", 1)])

    def test_violations_are_counted_per_frame_and_sorted_by_path(self):
        bad = action(negation="受け身", regions={"source": [["雙方", "手牌"], ["自分", "山札"]]})
        self.assertEqual(
            closed_values.violations([record(1, bad, bad), record(2, action(manner_kind="手段"))]),
            [("manner_kind", "手段", 1), ("negation", "受け身", 2),
             ("regions.player", "雙方", 2), ("regions.zone", "山札", 2)])

    def test_unknown_phrase_and_region_keys_are_violations(self):
        fr = action(phrases={"source": {"text": "x", "segments": []}}, regions={"topic": []})
        self.assertEqual(closed_values.violations([record(1, fr)]),
                         [("phrases", "source", 1), ("regions", "topic", 1)])

    def test_constraint_frames_are_not_scanned(self):
        rec = record(1)
        rec["frames"].append({"kind": "約束", "category": "限制", "agent": "其他"})
        self.assertEqual(closed_values.violations([rec]), [])

    def test_zones_are_the_seven_values_of_places(self):
        self.assertEqual(closed_values.ZONES,
                         ("場上", "墓地", "手牌", "牌組", "除外", "靈擺區", "額外牌組"))


class TestBaselineStrip(unittest.TestCase):
    """票 01:strip 只剝新鍵(含回指欄的 moving),既有鍵與值原樣;不改原框架。"""

    def test_strip_removes_every_new_key_and_keeps_the_rest(self):
        fr = action(phrases={"object": {"text": "x", "segments": []}}, regions={}, transfer="取自來源",
                    agent="自分", agent_source="預設", agent_inferred=True, manner="戦闘で",
                    manner_kind="手段:戰鬥", manner_value=None, negation="一般",
                    region_backfill="place", anaphora={"text": "そのカード", "via": "対象", "moving": False})
        stripped = baseline_diff.strip(fr)
        self.assertEqual(stripped, action(anaphora={"text": "そのカード", "via": "対象"}))
        self.assertIn("phrases", fr, "strip 不改原框架")

    def test_strip_leaves_a_frame_without_new_keys_alone(self):
        fr = action(anaphora={"text": "それ", "via": "欄位"}, inferred=["goal"])
        self.assertEqual(baseline_diff.strip(fr), fr)

    def test_underscore_keys_are_reported_with_their_position(self):
        rec = record(7, action(), action(_raw={"object": "x"}))
        self.assertEqual(baseline_diff.underscore_keys([rec]), [(7, "main", "0", 1, "_raw")])
        self.assertEqual(baseline_diff.underscore_keys([record(7, action())]), [])


class TestBaselineDiff(unittest.TestCase):
    """票 01:diff 讀兩個框架檔,剝掉新鍵後逐紀錄、逐框、逐鍵比;回差異清單
    (卡號, 段落, 句序, 框序, 鍵, 基準值, 現值)。"""

    def _write(self, name, records):
        path = os.path.join(self.tmp, name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False)
        return path

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def test_new_keys_do_not_count_as_differences(self):
        base = self._write("base.json", [record(1, action(), action(action="除外"))])
        cur = self._write("cur.json", [record(1, action(agent="自分", agent_source="預設"),
                                              action(action="除外", regions={"goal": [["無", "除外"]]}))])
        self.assertEqual(baseline_diff.diff(base, cur), [])

    def test_a_changed_existing_value_is_a_difference(self):
        base = self._write("base.json", [record(1, action(), action(object="カード"))])
        cur = self._write("cur.json", [record(1, action(), action(object="カード２枚"))])
        self.assertEqual(baseline_diff.diff(base, cur),
                         [(1, "main", "0", 1, "object", "カード", "カード２枚")])

    def test_a_dropped_or_added_existing_key_is_a_difference(self):
        base = self._write("base.json", [record(1, action(voice="他動"))])
        cur = self._write("cur.json", [record(1, action(inferred=["goal"]))])
        self.assertEqual(baseline_diff.diff(base, cur),
                         [(1, "main", "0", 0, "inferred", None, ["goal"]),
                          (1, "main", "0", 0, "voice", "他動", None)])

    def test_frame_count_and_record_count_mismatches_are_differences(self):
        base = self._write("base.json", [record(1, action(), action()), record(2, action())])
        cur = self._write("cur.json", [record(1, action())])
        self.assertEqual(baseline_diff.diff(base, cur),
                         [(1, "main", "0", None, "frames", 2, 1),
                          (2, "main", "0", None, "record", "基準有", "現在沒有")])


class TestCorpus(unittest.TestCase):
    """票 01 的全語料驗收:剝鍵差異 0、沒有表外值、沒有底線鍵。frames.json 不在時整類略過;基準檔
    (不入版控)不在時只略過逐框比對,改由入版控的 baseline-digest.json 守門(retro 2026-11-01):語料
    沒變時剝鍵後的 md5 要和 digest 相同,語料變了略過並印原因。"""

    @classmethod
    def setUpClass(cls):
        cls.reason = None
        if not os.path.exists(frames.OUT):
            cls.reason = "第四版論元的全語料驗收沒有生效:沒有 frames.json(%s)——先跑 frames.py" % frames.OUT
            print(cls.reason, file=sys.stderr)
            return
        with open(frames.OUT, encoding="utf-8") as f:
            cls.records = json.load(f)

    def setUp(self):
        if self.reason:
            self.skipTest(self.reason)

    def test_stripping_the_new_keys_gives_back_the_baseline(self):
        if not os.path.exists(baseline_diff.BASELINE):
            reason = ("沒有基準檔 %s,逐框比對略過(digest 守門仍在);要逐框看差異時用 "
                      "script/dev/worktree_bootstrap.py 複製基準檔" % baseline_diff.BASELINE)
            print(reason, file=sys.stderr)
            self.skipTest(reason)
        differences = baseline_diff.diff(baseline_diff.BASELINE, frames.OUT)
        self.assertEqual(differences[:20], [], "剝掉新鍵後與基準有 %d 處差異(只列前 20)" % len(differences))

    def test_stripped_digest_matches_the_frozen_one(self):
        status, message = baseline_diff.check_digest()
        if status == "skip":
            print("字面欄守門略過:" + message, file=sys.stderr)
            self.skipTest(message)
        self.assertEqual(status, "ok", message)

    def test_no_value_outside_the_closed_tables(self):
        self.assertEqual(closed_values.violations(self.records), [])

    def test_no_underscore_key_in_the_output(self):
        self.assertEqual(baseline_diff.underscore_keys(self.records)[:20], [])


if __name__ == "__main__":
    unittest.main()
