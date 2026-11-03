# -*- coding: utf-8 -*-
"""召喚手續抽驗線(summon-procedure 票 05)的行為測試。

接縫:llm_check.sample_procedure() → 母體全取的樣本(句裡有手續非空的召喚條件約束框架);write_procedure_batches(目錄, 樣本,
設定) → 批次檔(每張卡一節,召喚條件原文、約束框架、召喚手續框帶動作對象格、被白名單擋掉的步驟一行);
report_procedure(目錄) → report.md(各錯誤類型的筆數、框數、卡數、成因分項;複檢輪多一張前後對照表)。
全語料的例子缺 frames.json 時 skipTest 並印原因;報告的例子用假樣本與假回報,只寫 tempdir。

執行:PYTHONIOENCODING=utf-8 python -m unittest discover -s .scratch/effect-tokenize -p test_procedure_llm_check.py
"""
import json
import os
import re
import sys
import tempfile
import unittest
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import llm_check  # noqa: E402


def read(root, name):
    with open(os.path.join(root, name), encoding="utf-8") as f:
        return f.read()


class TestCorpusProcedure(unittest.TestCase):
    """票 05:母體是手續非空的召喚條件所在的句,全取不抽樣;批次檔每張卡一節、召喚手續框帶動作對象格、被擋步驟另列一行。"""

    @classmethod
    def setUpClass(cls):
        cls.reason = "" if os.path.exists(llm_check.FRAMES) else "沒有 frames.json(先跑 frames.py)"
        if cls.reason:
            print(cls.reason, file=sys.stderr)

    def setUp(self):
        if self.reason:
            self.skipTest(self.reason)

    def test_population_is_every_sentence_with_a_procedure(self):
        picked = llm_check.sample_procedure()
        self.assertEqual(picked, llm_check.sample_procedure())
        self.assertEqual(len(picked), 304)
        self.assertEqual(len({p["card"] for p in picked}), 304)
        # 效果文被認成召喚條件的那句(Ｄ・テレホン,stratum 是 effect)也在母體
        self.assertIn(38082437, {p["card"] for p in picked})
        self.assertEqual(Counter(p["stratum"] for p in picked),
                         {llm_check.STRATUM_HAS_PROCEDURE: 271, llm_check.STRATUM_ALL_BLOCKED: 33})

    def card_sections(self, picked, write=None):
        """寫進 tempdir 的批次檔 → {卡號: 那張卡的一節}。"""
        with tempfile.TemporaryDirectory() as root:
            (write or llm_check.write_procedure_batches)(root, picked, {"batches": 8})
            text = "".join(read(root, "batch-%d.md" % k) for k in range(8))
        return {int(m.group(1)): m.group(0) for m in re.finditer(r"## 卡 (\d+)[^\n]*\n(?:(?!## 卡 ).*\n?)*", text)}

    def test_batches_list_every_card_with_the_procedure_frames_and_patient(self):
        picked = llm_check.sample_procedure()
        sections = self.card_sections(picked)
        self.assertEqual(set(sections), {p["card"] for p in picked})
        black = sections[59400890]
        self.assertIn("原文:", black)
        self.assertIn("手續 除外", black)
        self.assertRegex(black, r"\[召喚手續\] 除外.*動作對象=非此卡.*發動位置=額外牌組\(寫明的召喚來源\)")
        # 同一張卡的效果句、和召喚條件無關的框架不列
        self.assertNotIn("加える", black)
        self.assertNotIn("[條件] 発動", black)

    def test_batches_list_the_steps_blocked_by_the_whitelist(self):
        sections = self.card_sections(llm_check.sample_procedure())
        self.assertIn("被白名單擋掉的步驟:第 1 步 存在", sections[263926])
        self.assertNotIn("[召喚手續]", sections[263926])
        self.assertIn("被白名單擋掉的步驟:第 1 步 選ぶ", sections[38082437])
        self.assertNotIn("被白名單擋掉的步驟", sections[59400890])

    def test_recheck_rewrites_the_same_sample_with_the_same_cells(self):
        with tempfile.TemporaryDirectory() as root:
            saved = llm_check.CHECK_DIR
            llm_check.CHECK_DIR = root
            try:
                for argv in (["procedure", "--round", "1"], ["recheck", "--round", "2", "--from", "1", "--line", "procedure"]):
                    sys.argv = ["llm_check.py"] + argv
                    llm_check.main()
            finally:
                llm_check.CHECK_DIR = saved
            second = os.path.join(root, "procedure-round2")
            meta = json.loads(read(second, "meta.json"))
            self.assertEqual(meta["recheck_of"], 1)
            self.assertEqual(meta["batches"], llm_check.BATCHES_PROCEDURE)
            self.assertEqual(read(second, "sample.json"), read(os.path.join(root, "procedure-round1"), "sample.json"))
            text = "".join(read(second, "batch-%d.md" % k) for k in range(meta["batches"]))
            self.assertIn("動作對象=", text)
            self.assertIn("被白名單擋掉的步驟:", text)


# 假樣本:三句,一句全被擋
SAMPLE = [{"card": 1, "section": "main", "index": "0", "stratum": llm_check.STRATUM_HAS_PROCEDURE},
          {"card": 2, "section": "main", "index": "0-2", "stratum": llm_check.STRATUM_HAS_PROCEDURE},
          {"card": 3, "section": "main", "index": "0", "stratum": llm_check.STRATUM_ALL_BLOCKED}]


def finding(card, frame, kind, cause="抽取", step=None, index="0"):
    return {"card": card, "index": index, "frame": frame, "step": step, "type": kind, "cause": cause,
            "got": "現值", "expected": "該值", "reason": "測試 %d" % card}


def write_round(root, name, findings, **meta):
    round_dir = os.path.join(root, name)
    llm_check.write_sample_meta(round_dir, SAMPLE, dict({"mode": "procedure", "batches": 2,
                                                         "strata": list(llm_check.STRATA_PROCEDURE),
                                                         "error_types": list(llm_check.ERROR_TYPES_PROCEDURE)}, **meta))
    for k in range(2):
        with open(os.path.join(round_dir, "findings-%d.json" % k), "w", encoding="utf-8") as f:
            json.dump(findings[k::2], f, ensure_ascii=False)
    return round_dir


def table_row(report, name):
    """報告表裡某一列 → 各格(去掉首尾的 |)。"""
    line = next(line for line in report.splitlines() if line.startswith("| %s |" % name))
    return [cell.strip() for cell in line.strip("|").split("|")][1:]


class TestProcedureReport(unittest.TestCase):
    """票 05:報告列各錯誤類型的筆數、框數(同一框多筆算一框;漏出沒有框,以該出的步算)、卡數與成因(規則/抽取)。"""

    FINDINGS = [finding(1, 2, "中心詞錯"), finding(1, 2, "中心詞錯", cause="規則"), finding(1, 3, "中心詞錯"),
                finding(2, 4, "數量錯", index="0-2"), finding(3, None, "漏出", step=1), finding(3, None, "漏出", step=2),
                finding(1, 2, "修飾語類錯"), finding(2, 5, "說不出來的錯", cause="不知道", index="0-2")]

    def test_counts_frames_cards_and_causes_per_type(self):
        with tempfile.TemporaryDirectory() as root:
            round_dir = write_round(root, "procedure-round1", self.FINDINGS)
            llm_check.report_procedure(round_dir)
            report = read(round_dir, "report.md")
        # 筆數、框數、卡數、規則、抽取
        self.assertEqual(table_row(report, "中心詞錯"), ["3", "2", "1", "1", "2"])
        self.assertEqual(table_row(report, "漏出"), ["2", "2", "1", "0", "2"])
        self.assertEqual(table_row(report, "數量錯"), ["1", "1", "1", "0", "1"])
        self.assertEqual(table_row(report, "多出"), ["0", "0", "0", "0", "0"])
        # 型外的類型與成因不吞掉
        self.assertEqual(table_row(report, "(其他)")[:3], ["1", "1", "1"])
        self.assertIn("不知道", report)
        # 合計的框數跨類型去重:(1,2) (1,3) (2,4) (2,5) 與兩個漏的步
        self.assertEqual(table_row(report, "合計")[:3], ["8", "6", "3"])
        self.assertIn("測試 3", report)
        self.assertNotIn("對照", report)

    def test_recheck_report_compares_with_the_round_it_rechecks(self):
        with tempfile.TemporaryDirectory() as root:
            write_round(root, "procedure-round1", self.FINDINGS)
            round_dir = write_round(root, "procedure-round2", [finding(1, 3, "中心詞錯"), finding(2, 4, "多出", index="0-2")],
                                    recheck_of=1)
            llm_check.report_procedure(round_dir)
            report = read(round_dir, "report.md")
        self.assertIn("與 procedure-round1 對照", report)
        # 筆數 前 → 後、框數 前 → 後、卡數 前 → 後
        self.assertEqual(table_row(report, "中心詞錯 前 → 後"), ["3 → 1", "2 → 1", "1 → 1"])
        self.assertEqual(table_row(report, "漏出 前 → 後"), ["2 → 0", "2 → 0", "1 → 0"])
        self.assertEqual(table_row(report, "多出 前 → 後"), ["0 → 1", "0 → 1", "0 → 1"])


if __name__ == "__main__":
    unittest.main()
