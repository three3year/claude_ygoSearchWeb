"""剝框重編(summon-procedure 票 01)的驗收測試:召喚手續框出框之前,先讓三道守門分得出新加的框和既有的框。

接縫:
- 單元:`baseline_diff.strip_procedure(紀錄)`(剝掉位置是召喚手續的框、框序照剩下的重編)——剝鍵比對
  (`baseline_diff`)與下游基準(`downstream_baseline`)都經它;`export_diff.strip(匯出文件)`(剝掉召喚手續框列、
  目錄列與統計的召喚手續格)與 `export_diff.diff(基準, 現在)`。手寫的小紀錄與小匯出文件,不讀全語料。
- 全語料:現行匯出檔剝完的 md5 與入版控的 export-digest.json 相同(輸入沒變時)。剝鍵比對與下游基準的全語料
  守門在 test_v4、test_downstream_baseline,它們現在都經剝框重編。

執行:PYTHONIOENCODING=utf-8 python -m unittest discover -s .scratch/effect-tokenize
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import baseline_diff  # noqa: E402
import downstream_baseline as db  # noqa: E402
import export_diff  # noqa: E402


def frame(order, action, position, **fields):
    return dict({"kind": "動作", "sentence": 0, "option": None, "label": None, "order": order,
                 "span": [order, order + 1], "clause": action, "action": action, "object": None,
                 "source": None, "goal": None, "position": position, "polarity": "肯定"}, **fields)


def record(*frames):
    return {"card": "59400890", "section": "main", "index": "0", "stratum": "extra", "parts": [],
            "frames": list(frames)}


class TestStripProcedure(unittest.TestCase):
    """票 01:一筆紀錄剝掉召喚手續框、框序重編後,等於不含召喚手續框的版本;原紀錄不動。"""

    def test_procedure_frames_are_dropped_and_the_rest_renumbered(self):
        constraint = {"kind": "約束", "sentence": 0, "option": None, "label": None, "order": 1,
                      "span": [0, 9], "clause": "", "category": "限制", "subtype": "召喚條件",
                      "procedure": ["除外"]}
        with_procedure = record(frame(0, "除外", "召喚手續", goal="除外"), constraint,
                                frame(2, "リリース", "召喚手續"), frame(3, "破壊", "效果"))
        without = record(dict(constraint, order=0), frame(1, "破壊", "效果", span=[3, 4]))
        self.assertEqual(baseline_diff.strip_procedure(with_procedure), without)
        self.assertEqual([f["order"] for f in with_procedure["frames"]], [0, 1, 2, 3])

    def test_a_record_without_procedure_frames_is_unchanged(self):
        plain = record(frame(0, "破壊", "效果"), frame(1, "除外", "代價"))
        self.assertEqual(baseline_diff.strip_procedure(plain), plain)


def write_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)


class TestBaselineDiffStripsProcedure(unittest.TestCase):
    """票 01:剝鍵比對先剝框重編——多出召喚手續框、後面框序往後推,不算差異;既有框的值變了仍算。"""

    BASE = record(frame(0, "除外", "效果"), frame(1, "破壊", "效果"))
    WITH_PROCEDURE = record(frame(0, "除外", "效果"), frame(1, "リリース", "召喚手續"),
                            dict(frame(2, "破壊", "效果"), span=[1, 2]))

    def setUp(self):
        self.root = tempfile.TemporaryDirectory()
        self.addCleanup(self.root.cleanup)
        self.base_path = os.path.join(self.root.name, "base.json")
        self.cur_path = os.path.join(self.root.name, "cur.json")
        write_json(self.base_path, [self.BASE])

    def test_an_added_procedure_frame_is_not_a_difference(self):
        write_json(self.cur_path, [self.WITH_PROCEDURE])
        self.assertEqual(baseline_diff.diff(self.base_path, self.cur_path), [])
        self.assertEqual(baseline_diff.stripped_md5([self.WITH_PROCEDURE]), baseline_diff.stripped_md5([self.BASE]))

    def test_a_changed_existing_frame_still_is(self):
        changed = record(frame(0, "除外", "效果"), frame(1, "リリース", "召喚手續"),
                         dict(frame(2, "破壊", "代價"), span=[1, 2]))
        write_json(self.cur_path, [changed])
        self.assertEqual(baseline_diff.diff(self.base_path, self.cur_path),
                         [("59400890", "main", "0", 1, "position", "效果", "代價")])


class TestDownstreamSnapshotStripsProcedure(unittest.TestCase):
    """票 01:下游基準的 snapshot 先剝框重編——召喚手續框不在基準裡,既有框依重編後的框序對到基準。
    動作對象在剝之前整句判(召喚手續框在句中時,既有框的判定若因它而變,要看得到差異)。"""

    ANAPHORA = {"text": "相手フィールドのモンスター１体", "place": "フィールド", "player": None,
                "via": "対象", "moving": False}

    def _pair(self):
        destroy_self = frame(0, "破壊", "效果", object="このカード", clause="このカード を 破壊 する")
        banish = frame(1, "除外", "效果", object="そのモンスター", anaphora=self.ANAPHORA, span=[1, 2])
        base = record(destroy_self, banish)
        current = record(destroy_self, frame(1, "リリース", "召喚手續", object="このカード"),
                         dict(banish, order=2))
        return base, current

    def test_patient_snapshot_ignores_procedure_frames_and_renumbers(self):
        base, current = self._pair()
        self.assertEqual(db.snapshot(db.PATIENT, [current]), db.snapshot(db.PATIENT, [base]))
        self.assertEqual(sorted(db.snapshot(db.PATIENT, [current])),
                         [("59400890", "main", "0", 0), ("59400890", "main", "0", 1)])

    def test_anaphora_snapshot_ignores_procedure_frames_and_renumbers(self):
        base, current = self._pair()
        self.assertEqual(db.snapshot(db.ANAPHORA, [current]), {
            ("59400890", "main", "0", 0): None,
            ("59400890", "main", "0", 1): self.ANAPHORA,
        })
        self.assertEqual(db.snapshot(db.ANAPHORA, [current]), db.snapshot(db.ANAPHORA, [base]))

    def test_clauses_follow_the_renumbered_order(self):
        _, current = self._pair()
        self.assertEqual(db.frame_clauses([current]), {
            ("59400890", "main", "0", 0): "このカード を 破壊 する",
            ("59400890", "main", "0", 1): "除外",
        })


def export_doc(version, positions, rows, catalog_cards, stats_positions):
    return {"說明": "v%d" % version, "版本": version,
            "值域": {"位置": list(positions), "極性": ["肯定", "否定", "可能"]},
            "目錄": [{"name": "除外", "path": ["區域移動", "除外"], "predicate": {"詞元": "除外"},
                      "cards": dict(catalog_cards), "hash": {p: "h" + str(n) for p, n in catalog_cards.items()}}],
            "統計": {"框架": {"此卡": 1, "非此卡": len(rows), "皆非": 0}, "位置": dict(stats_positions)},
            "卡面": [[59400890, "face"]],
            "句": [{"card": 59400890, "section": "main", "index": str(k), "hash": "t%d" % k, "frames": frames}
                   for k, frames in enumerate(rows)]}


THREE = ("代價", "效果", "條件")
BANISH_EFFECT = {"action": "除外", "position": "效果", "regions": {"source": [["相手", "場上"]]}}
BANISH_PROCEDURE = {"action": "除外", "position": "召喚手續", "regions": {"source": [["自分", "場上"]]},
                    "agent": "自分"}
CURRENT_DOC = export_doc(3, THREE + ("召喚手續",), [[BANISH_PROCEDURE], [BANISH_EFFECT, BANISH_PROCEDURE]],
                         {"代價": 0, "效果": 1, "條件": 0, "召喚手續": 1},
                         {"代價": 0, "效果": 1, "條件": 0, "召喚手續": 2})
BASE_DOC = export_doc(2, THREE, [[], [BANISH_EFFECT]], {"代價": 0, "效果": 1, "條件": 0},
                      {"代價": 0, "效果": 1, "條件": 0})


class TestExportStrip(unittest.TestCase):
    """票 01:匯出檔剝掉召喚手續框列、目錄列的召喚手續格、統計位置的召喚手續格、值域的召喚手續後,
    與沒有召喚手續的匯出檔逐句相同;版本號、說明、動作對象統計(全部框合計,剝不出來)不比。"""

    def test_procedure_rows_and_cells_are_not_differences(self):
        self.assertEqual(export_diff.diff(BASE_DOC, CURRENT_DOC), [])
        self.assertEqual(export_diff.stripped_md5(CURRENT_DOC), export_diff.stripped_md5(BASE_DOC))

    def test_changed_existing_rows_and_cells_are_listed_by_section(self):
        changed = json.loads(json.dumps(CURRENT_DOC))
        changed["句"][1]["frames"][0]["regions"] = {"source": [["相手", "墓地"]]}
        changed["目錄"][0]["cards"]["效果"] = 2
        changed["統計"]["位置"]["條件"] = 5
        changed["卡面"][0][1] = "face2"
        self.assertEqual(export_diff.diff(BASE_DOC, changed), [
            ("目錄", ("區域移動", "除外"), BASE_DOC["目錄"][0],
             dict(BASE_DOC["目錄"][0], cards={"代價": 0, "效果": 2, "條件": 0})),
            ("統計位置", "條件", 0, 5),
            ("卡面", 59400890, "face", "face2"),
            ("句", (59400890, "main", "1"), BASE_DOC["句"][1],
             dict(BASE_DOC["句"][1], frames=[dict(BANISH_EFFECT, regions={"source": [["相手", "墓地"]]})])),
        ])

    def test_missing_rows_and_domain_changes_are_listed(self):
        changed = json.loads(json.dumps(CURRENT_DOC))
        del changed["句"][0]
        changed["值域"]["極性"] = ["肯定", "否定"]
        self.assertEqual(export_diff.diff(BASE_DOC, changed), [
            ("值域", "極性", ["肯定", "否定", "可能"], ["肯定", "否定"]),
            ("句", (59400890, "main", "0"), BASE_DOC["句"][0], export_diff.MISSING),
        ])


class TestExportCli(unittest.TestCase):
    """票 01:export_diff.py 的入口——--freeze 記 digest 與基準檔;之後只多召喚手續的匯出檔 exit 0,
    既有框列變了 exit 1;輸入(語料、卡面、目錄)變了 digest 守門略過。"""

    def setUp(self):
        self.root = tempfile.TemporaryDirectory()
        self.addCleanup(self.root.cleanup)
        r = self.root.name
        self.loc = export_diff.Locations(
            export=os.path.join(r, "action_frames.json"), inputs=(os.path.join(r, "tokens.json"),),
            baseline_dir=os.path.join(r, "baseline"), digest_dir=r)
        write_json(self.loc.inputs[0], [])
        write_json(self.loc.export, BASE_DOC)
        self.assertEqual(export_diff.main(["--freeze"], self.loc), 0)

    def test_an_export_that_only_adds_procedure_passes(self):
        write_json(self.loc.export, CURRENT_DOC)
        self.assertEqual(export_diff.check_digest(self.loc)[0], "ok")
        self.assertEqual(export_diff.main([], self.loc), 0)

    def test_a_changed_existing_row_fails(self):
        changed = json.loads(json.dumps(CURRENT_DOC))
        changed["句"][1]["frames"][0]["action"] = "破壊"
        write_json(self.loc.export, changed)
        self.assertEqual(export_diff.check_digest(self.loc)[0], "mismatch")
        self.assertEqual(export_diff.main([], self.loc), 1)

    def test_changed_inputs_skip_the_digest_guard(self):
        write_json(self.loc.inputs[0], [{"card": 1}])
        status, message = export_diff.check_digest(self.loc)
        self.assertEqual(status, "skip")
        self.assertIn("tokens.json", message)


class TestExportCorpus(unittest.TestCase):
    """票 01 的全語料驗收:現行 data/action_frames.json 剝完的 md5 與入版控的 export-digest.json 相同
    (語料、卡面、目錄沒變時);輸入變了或檔不在時略過並印原因。"""

    def test_stripped_export_matches_the_frozen_digest(self):
        status, message = export_diff.check_digest()
        if status == "skip":
            print("匯出檔守門略過:" + message, file=sys.stderr)
            self.skipTest(message)
        self.assertEqual(status, "ok", message)


if __name__ == "__main__":
    unittest.main()
