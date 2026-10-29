# -*- coding: utf-8 -*-
"""重跑分詞鏈的行為測試(.scratch/category-search 票 05,ADR-0017)。

接縫:run_chain.run(runner) → (成功與否, 失敗的步驟名)。runner 是「跑一支腳本、回
exit code」;測試給記錄用的假 runner,只斷言步驟順序與失敗即停,不真的跑分詞鏈。

執行:PYTHONIOENCODING=utf-8 python -m unittest discover -s .scratch/effect-tokenize
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_chain  # noqa: E402


class TestRunChain(unittest.TestCase):

    def test_steps_run_in_chain_order_ending_with_the_export(self):
        ran = []
        ok, failed = run_chain.run(lambda script: ran.append(script) or 0)
        self.assertTrue(ok)
        self.assertIsNone(failed)
        self.assertEqual(ran, ["tokenize.py", "frames.py", "categories.py",
                               "export_categories.py"])

    def test_a_failing_step_stops_the_chain_and_is_named(self):
        ran = []

        def runner(script):
            ran.append(script)
            return 1 if script == "categories.py" else 0
        ok, failed = run_chain.run(runner)
        self.assertFalse(ok)
        self.assertEqual(failed, "類別")
        self.assertEqual(ran, ["tokenize.py", "frames.py", "categories.py"])


if __name__ == "__main__":
    unittest.main()
