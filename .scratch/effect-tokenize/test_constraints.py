# -*- coding: utf-8 -*-
"""約束框架的行為測試(.scratch/constraint-frames 票 01〜06)。

同一接縫:一句效果句原文(帶同卡同段上文,可選效果外/卡片子類型)→ 框架清單
(frames.extract),動作框架與約束框架混排、依原文位置排序。只斷言輸出框架:
動作框架看(動作, 位置, 極性),約束框架看(類別·子類, 專屬欄位);取代規則在
同一個斷言裡驗(誓約句只剩誓約框架、沒有 特殊召喚 動作框架)。用真的分詞器與詞典。
每個句型一條回歸例子——修規則前先補一條會失敗的例子。

執行:PYTHONIOENCODING=utf-8 python -m unittest discover -s .scratch/effect-tokenize
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import constraints  # noqa: E402
import frames  # noqa: E402


def rows(text, context="", **kw):
    """框架 → 比對用的 tuple:動作框架 (動作, 動作, 位置, 極性);約束框架
    (約束, 類別·子類, {專屬欄位})。"""
    out = []
    for f in frames.extract(text, context, **kw):
        if f["kind"] == constraints.KIND_ACTION:
            out.append((constraints.KIND_ACTION, f["action"], f["position"],
                        f["polarity"]))
        else:
            label = f["category"] + ("·" + f["subtype"] if f["subtype"] else "")
            fields = {k: f.get(k) for k in constraints.FIELDS[label]}
            out.append((constraints.KIND_CONSTRAINT, label, fields))
    return out


def A(action, position, polarity):
    return (constraints.KIND_ACTION, action, position, polarity)


def C(label, **fields):
    return (constraints.KIND_CONSTRAINT, label, fields)


def count(period, count, target, sharing=None):
    return C("限制·次數", period=period, count=count, target=target,
             sharing=sharing)


class TestActivationCount(unittest.TestCase):
    """票 01:發動句內的「１ターンに１度、」出限制·次數,同句其餘動作框架不變。"""

    def test_activation_count_prefix(self):
        self.assertEqual(
            rows("①：１ターンに１度、自分フィールドの「SPYRAL」カード１枚を対象として"
                 "発動できる。そのカードを破壊する。"),
            [count("回合", 1, "この効果"),
             A("対象とする", "條件", "肯定"),
             A("破壊", "效果", "肯定")])

    def test_count_prefix_after_condition_clause(self):
        self.assertEqual(
            rows("④：このカードが装備されている場合、１ターンに１度、相手がフィールドで"
                 "発動したモンスターの効果の処理時に、その効果を無効にできる。"),
            [A("装備", "條件", "肯定"),
             count("回合", 1, "この効果"),
             A("無効にする", "效果", "可能")])

    def test_count_prefix_in_option_keeps_option_column(self):
        got = frames.extract("②：このカードは以下の効果を得る。\n●１つ：１ターンに１度、"
                             "相手モンスターの攻撃宣言時に発動できる。その攻撃を無効にする。")
        self.assertEqual([(f["kind"], f.get("option"), f.get("label")) for f in got],
                         [("動作", None, None), ("約束", 1, "1つ"),
                          ("動作", 1, "1つ"), ("動作", 1, "1つ")])

    def test_constraint_frame_common_fields(self):
        frame = frames.extract("①：１ターンに１度、自分は１枚ドローする。")[0]
        for key in ("kind", "category", "subtype", "sentence", "span", "clause",
                    "option", "label"):
            self.assertIn(key, frame)
        self.assertEqual(frame["kind"], "約束")
        self.assertEqual((frame["category"], frame["subtype"]), ("限制", "次數"))
        self.assertEqual(frame["clause"], "1 ターン に 1 度 、")
        self.assertEqual(frame["span"], [0, 6])
        # 動作框架也帶種類欄,子句不含被約束框架吃掉的字首
        action = frames.extract("①：１ターンに１度、自分は１枚ドローする。")[1]
        self.assertEqual(action["kind"], "動作")
        self.assertEqual(action["span"][0], 6)

    def test_sentence_without_constraint_has_only_action_frames(self):
        self.assertEqual(
            rows("①：デッキから「試作機」１体を手札に加える。"),
            [A("加える", "效果", "肯定")])


if __name__ == "__main__":
    unittest.main()
