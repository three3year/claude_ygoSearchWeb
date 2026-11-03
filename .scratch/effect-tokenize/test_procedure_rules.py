"""召喚手續框的兩條專門規則(summon-procedure 票 03;ADR-0019)。

施事者:位置 召喚手續 的框架一律 自分,來源 預設、標推得,不看主題與主語。接縫:一句效果外文本原文 → 框架清單
(frames.extract),斷言 agent / agent_source / agent_inferred。

動作對象:召喚手續框把此卡當成在所屬召喚條件的召喚來源——寫了照寫,沒寫時主牌組怪獸 手牌、額外牌組怪獸 額外牌組;
召喚手續的 重ねる 一律 此卡。接縫:合成卡的效果外文本經組裝、框架抽取進框列匯出(export_frames),斷言框列的
patient_mode 與匯出「統計」的發動位置來源。

執行:PYTHONIOENCODING=utf-8 python -m unittest discover -s .scratch/effect-tokenize -p test_procedure_rules.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import constraints  # noqa: E402
import export_common  # noqa: E402
import frames  # noqa: E402
from test_04_patient import XYZ  # noqa: E402
from test_05_export_frames import DRAGON, clause, export  # noqa: E402
from test_05_export_frames import rows as frame_rows  # noqa: E402


def procedure_frames(text):
    return [f for f in frames.extract(text, extra=True)
            if f["kind"] == constraints.KIND_ACTION and f["position"] == constraints.POS_PROCEDURE]


def agents(text):
    return [(f["action"], f.get("agent"), f.get("agent_source"), bool(f.get("agent_inferred")))
            for f in procedure_frames(text)]


class TestProcedureAgent(unittest.TestCase):
    """票 03:召喚手續框的施事者一律 自分(來源 預設、推得),主題 このカード 不是施事者。"""

    def test_topic_this_card_is_not_the_agent(self):
        self.assertEqual(agents("このカードはモンスター１体をリリースしてアドバンス召喚できる。"),
                         [("リリース", "自分", "預設", True)])

    def test_overlay_without_an_object_is_still_done_by_self(self):
        self.assertEqual(agents("このカードは自分フィールドのランク８の「ギャラクシーアイズ」Xモンスターの上に"
                                "重ねてX召喚する事もできる。"),
                         [("重ねる", "自分", "預設", True)])


def procedure_modes(text, face=DRAGON):
    faces = {1: export_common.card_face(dict(face, id=1))} if face else {}
    found = frame_rows({1: [clause("0", text, kind="效果外文本")]}, faces)[(1, "main", "0")]
    return [(r["action"], r.get("patient_mode")) for r in found if r["position"] == constraints.POS_PROCEDURE]


WIPE_FIELD = "このカードは通常召喚できない。自分フィールドのモンスターを全てリリースした場合のみ特殊召喚できる。"


class TestProcedureLaunch(unittest.TestCase):
    """票 03:召喚手續框的發動位置是所屬召喚條件的召喚來源;沒寫時主牌組怪獸在手牌、額外牌組怪獸在額外牌組。"""

    def test_main_deck_monster_without_a_source_is_in_the_hand(self):
        self.assertEqual(procedure_modes(WIPE_FIELD), [("リリース", "非此卡")])

    def test_extra_deck_monster_without_a_source_is_in_the_extra_deck(self):
        self.assertEqual(procedure_modes(WIPE_FIELD, face=XYZ), [("リリース", "非此卡")])

    def test_written_source_is_used_as_written(self):
        text = "このカードは通常召喚できない。自分の墓地のモンスターを全て除外した場合のみ、墓地から特殊召喚できる。"
        self.assertEqual(procedure_modes(text, face=XYZ), [("除外", None)])

    def test_unwritten_source_reads_the_card_kind(self):
        text = "このカードは通常召喚できない。自分の墓地のモンスターを全て除外した場合のみ特殊召喚できる。"
        self.assertEqual(procedure_modes(text, face=XYZ), [("除外", "非此卡")])

    def test_unwritten_source_without_a_card_face_is_unknown(self):
        self.assertEqual(procedure_modes(WIPE_FIELD, face=None), [("リリース", None)])

    def test_stats_split_written_and_inferred_summon_sources(self):
        doc, _ = export({1: [clause("0", WIPE_FIELD, kind="效果外文本")],
                         2: [clause("0", "このカードは通常召喚できない。自分の墓地のモンスターを全て除外した場合のみ、"
                                         "墓地から特殊召喚できる。", kind="效果外文本")]},
                        {card: export_common.card_face(dict(DRAGON, id=card)) for card in (1, 2)})
        launch = doc["統計"]["發動位置"]
        self.assertEqual((launch.get("推得的召喚來源"), launch.get("寫明的召喚來源")), (1, 1))


class TestProcedureOverlay(unittest.TestCase):
    """票 03:召喚手續的 重ねる 一律此卡,不論有沒有寫主題 このカード。"""

    def test_overlay_without_a_topic_is_this_card(self):
        text = "「テスト・エクシーズ」は１ターンに１度、自分フィールドの「メルフィー・マミィ」の上に重ねてX召喚する事もできる。"
        self.assertEqual(procedure_modes(text, face=XYZ), [("重ねる", "此卡")])

    def test_overlay_in_an_effect_keeps_the_patient_rule(self):
        found = frame_rows({1: [clause("①", "①：自分の墓地のモンスター１体を選び、このカードの下に重ねてX素材とする。")]},
                           {1: export_common.card_face(dict(XYZ, id=1))})[(1, "main", "①")]
        self.assertIn(("重ねる", constraints.POS_EFFECT, "非此卡"),
                      [(r["action"], r["position"], r.get("patient_mode")) for r in found])


if __name__ == "__main__":
    unittest.main()
