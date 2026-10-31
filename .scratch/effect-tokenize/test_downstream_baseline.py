# -*- coding: utf-8 -*-
"""下游基準(named-queries 票 01)的驗收測試:動作對象判定、回指欄、舊匯出檔三把尺。

接縫:
- 單元:`downstream_baseline.snapshot(尺, 紀錄, 卡面)`(每個動作框架一個值)、`diff(基準, 現在)`(差異清單)、
  `freeze/check_digest`(入版控的 digest 守門)——手寫的小框架清單與暫存目錄,不讀全語料。
- 全語料:動作對象 (判定值, 理由) 逐框與 `baseline/patient.json` 差異 0、回指欄逐框與 `baseline/anaphora.json`
  差異 0、`data/action_categories.json` 的 md5 與 digest 相同;輸入不在時 skipTest 並印原因。

執行:PYTHONIOENCODING=utf-8 python -m unittest discover -s .scratch/effect-tokenize
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import downstream_baseline as db  # noqa: E402


def record(card, *frame_list, index="0"):
    """手寫的 frames.json 紀錄:一張卡的一句、帶幾個框架(預設動作框架)。"""
    return {"card": card, "section": "main", "index": index, "stratum": "effect", "parts": [],
            "frames": [dict({"kind": "動作", "sentence": 0, "option": None, "label": None, "order": k,
                             "span": [0, 1], "clause": "", "source": None, "goal": None,
                             "position": "效果", "polarity": "肯定"}, **f)
                       for k, f in enumerate(frame_list)]}


class TestPatientSnapshot(unittest.TestCase):
    """票 01:動作對象尺的值是每個動作框架的 (判定值, 理由);約束框架不在基準裡。"""

    def test_each_action_frame_gets_its_mode_and_why(self):
        records = [record("10000000",
                          {"action": "破壊", "object": "このカード", "clause": "このカード を 破壊 する"},
                          {"action": "破壊", "object": "相手フィールドのモンスター１体"},
                          {"kind": "約束", "action": "回数", "object": None})]
        snap = db.snapshot(db.PATIENT, records)
        self.assertEqual(snap, {
            ("10000000", "main", "0", 0): {"mode": "此卡", "why": "受事者是此卡"},
            ("10000000", "main", "0", 1): {"mode": "非此卡", "why": "選擇類"},
        })


class TestAnaphoraSnapshot(unittest.TestCase):
    """票 01:回指尺的值是整個回指欄(含新子鍵 moving);沒有回指的動作框架記 None。"""

    def test_the_whole_anaphora_dict_is_the_value(self):
        anaphora = {"text": "フィールドのモンスター１体", "place": "フィールド", "player": None,
                    "via": "対象", "moving": False}
        records = [record("10000000",
                          {"action": "破壊", "object": "そのモンスター", "anaphora": anaphora},
                          {"action": "ドロー", "object": "カード"})]
        self.assertEqual(db.snapshot(db.ANAPHORA, records), {
            ("10000000", "main", "0", 0): anaphora,
            ("10000000", "main", "0", 1): None,
        })


class TestDiff(unittest.TestCase):
    """票 01:差異清單每列是 (卡號, 段落, 句序, 框序, 子句字面, 基準值, 現值);相同的框不列。"""

    KEY = ("10000000", "main", "0", 0)

    def test_equal_snapshots_have_no_difference(self):
        snap = {self.KEY: {"mode": "此卡", "why": "受事者是此卡"}}
        self.assertEqual(db.diff(snap, dict(snap)), [])

    def test_a_changed_value_lists_the_frame_with_its_clause_and_both_values(self):
        base = {self.KEY: {"mode": "此卡", "why": "受事者是此卡"}}
        cur = {self.KEY: {"mode": "非此卡", "why": "選擇類"}}
        self.assertEqual(db.diff(base, cur, clauses={self.KEY: "そのカード を 破壊 する"}), [
            ("10000000", "main", "0", 0, "そのカード を 破壊 する",
             {"mode": "此卡", "why": "受事者是此卡"}, {"mode": "非此卡", "why": "選擇類"})])

    def test_frames_missing_on_either_side_are_listed_with_the_missing_marker(self):
        other = ("10000000", "main", "0", 1)
        base = {self.KEY: {"mode": "此卡", "why": "受事者是此卡"}}
        cur = {other: None}   # 回指欄的 None 是正常值,和「沒有這個框」要分得開
        self.assertEqual(db.diff(base, cur), [
            ("10000000", "main", "0", 0, "", {"mode": "此卡", "why": "受事者是此卡"}, db.MISSING),
            ("10000000", "main", "0", 1, "", db.MISSING, None)])

    def test_a_renamed_why_is_not_a_difference_when_the_alias_table_maps_it(self):
        base = {self.KEY: {"mode": "此卡", "why": "舊理由"}}
        cur = {self.KEY: {"mode": "此卡", "why": "新理由"}}
        self.assertEqual(len(db.diff(base, cur)), 1)
        self.assertEqual(db.diff(base, cur, why_aliases={"舊理由": "新理由"}), [])


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False)


class TestFreezeAndDigest(unittest.TestCase):
    """票 01:凍結寫 baseline/<尺>.json 與入版控的 <尺>-digest.json;digest 守門在語料沒變時比值的 md5,
    語料(tokens.json、cards.json)變了就 skip 並要求重新凍結;基準檔讀回來就是凍結時的 snapshot。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = self.tmp.name
        self.loc = db.Locations(frames=os.path.join(root, "frames.json"), tokens=os.path.join(root, "tokens.json"),
                                cards=os.path.join(root, "cards.json"), export=os.path.join(root, "export.json"),
                                baseline_dir=os.path.join(root, "baseline"), digest_dir=root)
        self.records = [record("10000000", {"action": "破壊", "object": "このカード"},
                               {"action": "破壊", "object": "相手フィールドのモンスター１体"})]
        write_json(self.loc.frames, self.records)
        write_json(self.loc.tokens, [{"card": "10000000", "text_ja": "x"}])
        write_json(self.loc.cards, [])
        with open(self.loc.export, "w", encoding="utf-8", newline="\n") as f:
            f.write('{"句":[]}\n')

    def tearDown(self):
        self.tmp.cleanup()

    def test_freeze_then_check_is_ok_and_the_baseline_reads_back_as_the_snapshot(self):
        for ruler in (db.PATIENT, db.ANAPHORA, db.EXPORT_RULER):
            db.freeze(ruler, self.loc)
            self.assertEqual(db.check_digest(ruler, self.loc)[0], "ok", ruler)
            self.assertTrue(os.path.exists(os.path.join(self.loc.digest_dir, ruler + "-digest.json")))
        self.assertEqual(db.load_baseline(db.PATIENT, self.loc), db.snapshot(db.PATIENT, self.records))
        self.assertEqual(db.load_baseline(db.ANAPHORA, self.loc), db.snapshot(db.ANAPHORA, self.records))

    def test_a_changed_value_is_a_mismatch(self):
        db.freeze(db.PATIENT, self.loc)
        db.freeze(db.EXPORT_RULER, self.loc)
        self.records[0]["frames"][0]["object"] = "相手フィールドのモンスター１体"
        write_json(self.loc.frames, self.records)
        with open(self.loc.export, "a", encoding="utf-8") as f:
            f.write("\n")
        self.assertEqual(db.check_digest(db.PATIENT, self.loc)[0], "mismatch")
        self.assertEqual(db.check_digest(db.EXPORT_RULER, self.loc)[0], "mismatch")

    def test_a_changed_corpus_skips_and_asks_for_a_refreeze(self):
        db.freeze(db.ANAPHORA, self.loc)
        write_json(self.loc.tokens, [{"card": "10000001", "text_ja": "y"}])
        status, message = db.check_digest(db.ANAPHORA, self.loc)
        self.assertEqual(status, "skip")
        self.assertIn("--freeze", message)

    def test_missing_digest_or_input_skips_with_the_path_in_the_reason(self):
        status, message = db.check_digest(db.PATIENT, self.loc)
        self.assertEqual(status, "skip")
        self.assertIn("patient-digest.json", message)


class TestCli(unittest.TestCase):
    """票 01:CLI 差異非 0 時 exit 1、差異 0 時 exit 0——票 02/04 改讀後就用這個指令看清單。"""

    def test_exit_code_follows_the_frame_diff(self):
        with tempfile.TemporaryDirectory() as root:
            loc = db.Locations(frames=os.path.join(root, "frames.json"), tokens=os.path.join(root, "tokens.json"),
                               cards=os.path.join(root, "cards.json"), export=os.path.join(root, "export.json"),
                               baseline_dir=os.path.join(root, "baseline"), digest_dir=root)
            records = [record("10000000", {"action": "破壊", "object": "このカード"})]
            write_json(loc.frames, records)
            write_json(loc.tokens, [])
            write_json(loc.cards, [])
            self.assertEqual(db.main(["patient", "--freeze"], loc), 0)
            self.assertEqual(db.main(["patient"], loc), 0)
            records[0]["frames"][0]["object"] = "相手フィールドのモンスター１体"
            write_json(loc.frames, records)
            self.assertEqual(db.main(["patient"], loc), 1)


class TestCorpus(unittest.TestCase):
    """票 01 的全語料驗收:動作對象 (判定值, 理由) 與回指欄逐框與基準差異 0、舊匯出檔 md5 與 digest 相同。
    frames.json 不在時整類略過;基準檔(不入版控)不在時只略過逐框比對、改由入版控的 <尺>-digest.json
    守門;語料或卡面變了時 digest 守門略過並印原因(要重新凍結)。"""

    @classmethod
    def setUpClass(cls):
        cls.reason = None
        if not os.path.exists(db.FRAMES):
            cls.reason = "下游基準的全語料驗收沒有生效:沒有 frames.json(%s)——先跑 frames.py" % db.FRAMES
            print(cls.reason, file=sys.stderr)
            return
        cls.records = db.load_records()
        cls.clauses = db.frame_clauses(cls.records)

    def setUp(self):
        if self.reason:
            self.skipTest(self.reason)

    def _frame_diff(self, ruler):
        path = db.baseline_path(ruler)
        if not os.path.exists(path):
            reason = ("沒有基準檔 %s,逐框比對略過(digest 守門仍在);要逐框看差異時 downstream_baseline.py %s "
                      "--freeze 在改讀前的程式上凍結,或 script/dev/worktree_bootstrap.py 從主 repo 複製" % (path, ruler))
            print(reason, file=sys.stderr)
            self.skipTest(reason)
        differences = db.diff(db.load_baseline(ruler), db.current_snapshot(ruler, records=self.records), self.clauses)
        self.assertEqual(differences[:20], [], "%s 尺與基準有 %d 處差異(只列前 20)" % (ruler, len(differences)))

    def _digest(self, ruler):
        status, message = db.check_digest(ruler, records=self.records)
        if status == "skip":
            print("%s 尺的 digest 守門略過:%s" % (ruler, message), file=sys.stderr)
            self.skipTest(message)
        self.assertEqual(status, "ok", message)

    def test_patient_verdicts_match_the_frozen_baseline(self):
        self._frame_diff(db.PATIENT)

    def test_patient_digest_matches_the_frozen_one(self):
        self._digest(db.PATIENT)

    def test_anaphora_column_matches_the_frozen_baseline(self):
        self._frame_diff(db.ANAPHORA)

    def test_anaphora_digest_matches_the_frozen_one(self):
        self._digest(db.ANAPHORA)

    def test_old_export_file_is_byte_for_byte_unchanged(self):
        """過渡期(規格 3 切換索引前)data/action_categories.json 不變:比入版控的 export-digest.json 記的 md5,
        不比 git HEAD 的 blob——HEAD 在工作樹是本票分支、合併後是合併點,誰不小心把改了的檔 commit 進去,
        HEAD 比對就跟著過;digest 要有人刻意 --freeze 才會動,語料或卡面變了(新卡)時略過並要求重新凍結。"""
        self._digest(db.EXPORT_RULER)


if __name__ == "__main__":
    unittest.main()
