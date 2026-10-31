# -*- coding: utf-8 -*-
"""片語結構化搬到回指之前(named-queries 票 02)。

接縫是 enrich 的兩段入口(frames.py 唯一的呼叫端):
- before_anaphora(ctx, tokens, frames):回指之前跑的步驟——只有片語結構化;切區域前的字面 _raw 這類
  內部鍵要留到回指之後(回指與後段步驟還要讀底線鍵)。
- after_anaphora(ctx, tokens, frames):回指之後的步驟(結構化區域、施事者、方式、否定形、回指回填),
  最後 pop 底線鍵。
用手寫的小框架,不讀全語料;片語欄與既有鍵逐位元組不變由 test_v4.TestCorpus(剝鍵基準)與
test_downstream_baseline.TestCorpus(回指欄)守。句型例子仍走 frames.extract(test_frames.py)。

執行:PYTHONIOENCODING=utf-8 python -m unittest discover -s .scratch/effect-tokenize
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import enrich  # noqa: E402
import frames  # noqa: E402

AFTER_KEYS = ("regions", "transfer", "agent", "agent_source", "manner", "manner_kind", "negation", "region_backfill")


def action_frame():
    """手寫的動作框架:對象切走所在後的字面與切前字面 _raw(frames.py 切區域時暫存)。"""
    return {"kind": "動作", "sentence": 0, "action": "破壊", "object": "モンスター1体", "place": "相手フィールド",
            "source": None, "goal": None, "position": "效果", "polarity": "肯定", "option": None, "label": None,
            "span": [0, 0], "clause": "", "voice": "他動", "_raw": {"object": "相手フィールドのモンスター1体"}}


class TestTwoPhases(unittest.TestCase):
    """票 02:片語在回指之前、其餘新欄在回指之後;底線鍵只在後段結尾 pop。"""

    def setUp(self):
        self.ctx = frames.default_extractor()._context()

    def test_before_anaphora_only_structures_phrases_and_keeps_internal_keys(self):
        fr = action_frame()
        enrich.before_anaphora(self.ctx, [], [fr])
        self.assertEqual([seg["head"] for seg in fr["phrases"]["object"]["segments"]], ["モンスター"])
        self.assertEqual([k for k in AFTER_KEYS if k in fr], [])
        self.assertEqual(fr["_raw"], {"object": "相手フィールドのモンスター1体"})

    def test_after_anaphora_adds_the_rest_and_drops_internal_keys(self):
        fr = action_frame()
        enrich.before_anaphora(self.ctx, [], [fr])
        enrich.after_anaphora(self.ctx, [], [fr])
        self.assertEqual(fr["regions"], {"place": [["相手", "場上"]]})
        self.assertEqual(fr["agent"], "自分")
        self.assertEqual([k for k in fr if k.startswith("_")], [])
        self.assertEqual([seg["head"] for seg in fr["phrases"]["object"]["segments"]], ["モンスター"])


if __name__ == "__main__":
    unittest.main()
