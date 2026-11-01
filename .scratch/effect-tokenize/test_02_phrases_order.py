# -*- coding: utf-8 -*-
"""片語結構化搬到回指之前(named-queries 票 02)。

接縫是 enrich 的兩段入口(frames.py 唯一的呼叫端;ctx 從公開的 frames.context() 拿):
- before_anaphora(ctx, tokens, frames):回指之前跑的步驟——只有片語結構化,其餘新欄還沒有。
- after_anaphora(ctx, tokens, frames):回指之後的步驟(結構化區域、施事者、方式、否定形、回指回填),
  輸出的框架沒有底線開頭的內部鍵。
用手寫的小框架,不讀全語料;只斷言輸出框架的欄位,不斷言內部鍵的值。片語欄與既有鍵逐位元組不變由
test_v4.TestCorpus(剝鍵基準)與 test_downstream_baseline.TestCorpus(回指欄)守。句型例子仍走 frames.extract
(test_frames.py)。

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
        self.ctx = frames.context()

    def test_before_anaphora_only_structures_phrases(self):
        fr = action_frame()
        enrich.before_anaphora(self.ctx, [], [fr])
        self.assertEqual([seg["head"] for seg in fr["phrases"]["object"]["segments"]], ["モンスター"])
        self.assertEqual([k for k in AFTER_KEYS if k in fr], [])

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
