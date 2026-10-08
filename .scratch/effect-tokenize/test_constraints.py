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


def timing(player, window, mode="限定", polarity="肯定"):
    return C("時機", player=player, window=window, mode=mode, polarity=polarity)


def event_turn(event, banned="発動"):
    return C("限制·事件回合禁用", event=event, banned=banned)


def pledge(trigger, action, form, scope, source=None, subject=None):
    return C("限制·誓約", trigger=trigger, subject=subject, action=action, form=form,
             scope=scope, source=source)


def summon(form, method=None, procedure=None, source=None):
    return C("限制·召喚條件", form=form, method=method, procedure=procedure or [],
             source=source)


def material(method, items):
    return C("素材", method=method,
             materials=[{"text": t, "count": c} for t, c in items])


def action_fields(text, **kw):
    """動作框架的 (動作, 次數, 期間, 窗口):票 06 的可選欄位。"""
    return [(f["action"], f.get("count"), f.get("period"), f.get("window"))
            for f in frames.extract(text, **kw) if f["kind"] == constraints.KIND_ACTION]


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


class TestCountNotes(unittest.TestCase):
    """票 02:使用次數註記、卡片發動次數註記、括弧註記、期間變體——都是限制·次數,
    註記句原本的 使用/発動/特殊召喚 否定動作框架不再出現。"""

    def test_each_effect_once_per_turn(self):
        self.assertEqual(
            rows("このカード名の①②の効果はそれぞれ１ターンに１度しか使用できない。"),
            [count("回合", 1, "このカード名の①②の効果", "それぞれ")])

    def test_either_one_shared_once_per_turn(self):
        self.assertEqual(
            rows("このカード名の①②の効果は１ターンに１度、いずれか１つしか使用できない。"),
            [count("回合", 1, "このカード名の①②の効果", "いずれか１つ")])

    def test_card_activation_once_per_turn(self):
        self.assertEqual(
            rows("このカード名のカードは１ターンに１枚しか発動できない。"),
            [count("回合", 1, "このカード名のカード")])

    def test_once_per_duel(self):
        self.assertEqual(
            rows("「セイクリッド・テンペスト」の①の効果はデュエル中に１度しか使用できない。"),
            [count("決鬥", 1, "「セイクリッド・テンペスト」の①の効果")])

    def test_once_per_chain_in_parenthesis(self):
        self.assertEqual(
            rows("①：相手が効果を発動した時に発動できる（同一チェーン上では１度まで）。"
                 "自分は１枚ドローする。"),
            [A("発動", "條件", "肯定"),
             count("同一連鎖", 1, "この効果"),
             A("ドロー", "效果", "肯定")])

    def test_once_per_turn_only_in_parenthesis(self):
        self.assertEqual(
            rows("②：このカードを裏側守備表示にする（１ターンに１度のみ）。"),
            [A("裏側守備表示にする", "效果", "肯定"),
             count("回合", 1, "この効果")])

    def test_this_effect_once_per_turn_note(self):
        self.assertEqual(
            rows("①：自分は１枚ドローする。この効果は１ターンに１度しか使用できない。"),
            [A("ドロー", "效果", "肯定"), count("回合", 1, "この効果")])
        self.assertEqual(
            rows("①：自分は１枚ドローする。この効果は１ターンに１度まで使用できる。"),
            [A("ドロー", "效果", "肯定"), count("回合", 1, "この効果")])

    def test_summon_method_count_takes_topic_as_target(self):
        self.assertEqual(
            rows("このカード名の①の方法による特殊召喚は１ターンに１度しかできない。"),
            [count("回合", 1, "このカード名の①の方法による特殊召喚")])

    def test_summoning_a_named_card_once_per_turn(self):
        self.assertEqual(
            rows("自分は「精霊獣 カンナホーク」を１ターンに１度しか特殊召喚できず、"
                 "その②の効果は１ターンに１度しか使用できない。"),
            [count("回合", 1, "「精霊獣 カンナホーク」の特殊召喚"),
             count("回合", 1, "その②の効果")])

    def test_two_notes_joined_by_dekizu(self):
        self.assertEqual(
            rows("このカード名の、①の方法による特殊召喚は１ターンに１度しかできず、"
                 "②の効果はデュエル中に１度しか使用できない。"),
            [count("回合", 1, "このカード名の、①の方法による特殊召喚"),
             count("決鬥", 1, "②の効果")])

    def test_not_in_same_chain_is_a_chain_count(self):
        self.assertEqual(
            rows("このカード名の①②の効果は、それぞれ１ターンに１度しか使用できず、"
                 "同一チェーン上では発動できない。"),
            [count("回合", 1, "このカード名の①②の効果", "それぞれ"),
             count("同一連鎖", 1, "このカード名の①②の効果", "それぞれ")])

    def test_selection_note_in_activation_parenthesis(self):
        self.assertEqual(
            rows("①：以下の効果から１つを選択して発動できる（このカード名の以下の効果は"
                 "それぞれ１ターンに１度しか選択できない）。\n●自分は１枚ドローする。"),
            [A("選択", "條件", "肯定"),
             count("回合", 1, "このカード名の以下の効果", "それぞれ"),
             A("ドロー", "效果", "肯定")])

    def test_pendulum_zone_prefix_without_activation(self):
        self.assertEqual(
            rows("①：１ターンに１度、自分フィールドの魔法使い族・闇属性モンスターを対象と"
                 "して発動した効果を無効にできる。その後、このカードを破壊する。"),
            [count("回合", 1, "この効果"),
             A("無効にする", "效果", "可能"),
             A("破壊", "效果", "肯定")])

    def test_replacement_destruction_prefix(self):
        self.assertEqual(
            rows("②：１ターンに１度、自分フィールドの闇属性モンスターが戦闘・効果で破壊"
                 "される場合、代わりに自分フィールドの黒羽カウンターを１つ取り除く事が"
                 "できる。"),
            [count("回合", 1, "この効果"),
             A("破壊", "條件", "肯定"),
             A("取り除く", "效果", "可能")])

    def test_field_only_count_is_not_a_usage_count(self):
        """「自分フィールドに１枚しか存在できない」:期間不是回合/決鬥/連鎖,照舊是動作。"""
        self.assertEqual(
            rows("①：「試作機」は自分フィールドに１枚しか表側表示で存在できない。"),
            [A("存在", "效果", "否定")])


class TestTimingAndEventTurn(unittest.TestCase):
    """票 03:發動句內的回合/階段窗口與「この効果は」註記句出時機框架;以事件界定的回合
    出限制·事件回合禁用;觸發事件照舊是條件動作框架;選項標籤不出時機。"""

    DRAW = A("ドロー", "效果", "肯定")

    def test_own_main_phase_window(self):
        self.assertEqual(
            rows("①：自分メインフェイズに発動できる。自分は１枚ドローする。"),
            [timing("自分", "メインフェイズ"), self.DRAW])

    def test_both_players_main_phase(self):
        self.assertEqual(
            rows("①：自分・相手のメインフェイズに発動できる。自分は１枚ドローする。"),
            [timing("雙方", "メインフェイズ"), self.DRAW])

    def test_opponent_turn_only(self):
        self.assertEqual(
            rows("③：相手ターンに発動できる。自分は１枚ドローする。"),
            [timing("相手", "ターン"), self.DRAW])

    def test_also_on_opponent_turn_is_additive(self):
        self.assertEqual(
            rows("①：自分は１枚ドローする。この効果は相手ターンでも発動できる。"),
            [self.DRAW, timing("相手", "ターン", "追加")])

    def test_phase_time_point(self):
        self.assertEqual(
            rows("①：自分・相手のバトルフェイズ開始時に発動できる。自分は１枚ドローする。"),
            [timing("雙方", "バトルフェイズ開始時"), self.DRAW])

    def test_mandatory_standby_phase_trigger(self):
        self.assertEqual(
            rows("②：自分スタンバイフェイズに発動する。自分は５００ダメージを受ける。"),
            [timing("自分", "スタンバイフェイズ"), A("受ける", "效果", "肯定")])

    def test_window_before_cost_clause(self):
        self.assertEqual(
            rows("①：自分メインフェイズに手札を１枚捨てて発動できる。自分は１枚ドローする。"),
            [timing("自分", "メインフェイズ"), A("捨てる", "代價", "肯定"), self.DRAW])

    def test_count_and_window_in_one_activation(self):
        self.assertEqual(
            rows("②：１ターンに１度、自分メインフェイズに発動できる。相手フィールドの魔法・"
                 "罠カードを全て持ち主の手札に戻す。"),
            [count("回合", 1, "この効果"), timing("自分", "メインフェイズ"),
             A("戻す", "效果", "肯定")])

    def test_event_turn_ban_note(self):
        self.assertEqual(
            rows("①：自分は１枚ドローする。この効果はこのカードが特殊召喚したターンには"
                 "発動できない。"),
            [self.DRAW, event_turn("このカードが特殊召喚したターン")])

    def test_event_turn_ban_on_use_replaces_action_frames(self):
        self.assertEqual(
            rows("①：自分は１枚ドローする。この効果はこのカードが墓地へ送られたターンには"
                 "使用できない。"),
            [self.DRAW, event_turn("このカードが墓地へ送られたターン", "使用")])

    def test_trigger_event_is_still_a_condition_action(self):
        self.assertEqual(
            rows("①：このカードが召喚に成功した時に発動できる。自分は１枚ドローする。"),
            [A("成功", "條件", "肯定"), self.DRAW])

    def test_event_defined_turn_is_not_a_timing(self):
        self.assertEqual(
            rows("②：モンスターが戦闘で破壊された自分・相手ターンに発動できる。"
                 "自分は１枚ドローする。"),
            [self.DRAW])

    def test_option_label_turn_is_not_a_timing(self):
        got = frames.extract("①：以下の効果を発動できる。\n●相手ターン：自分は１枚ドローする。")
        self.assertEqual([(f["kind"], f["option"], f["label"]) for f in got],
                         [("動作", 1, "相手ターン")])

    def test_denied_and_added_windows_in_one_note(self):
        self.assertEqual(
            rows("①：自分は１枚ドローする。この効果はダメージステップでは発動できず、"
                 "相手ターンでも発動できる。"),
            [self.DRAW, timing(None, "ダメージステップ", "限定", "否定"),
             timing("相手", "ターン", "追加")])

    def test_each_others_main_phase_only(self):
        self.assertEqual(
            rows("①：自分は１枚ドローする。この効果はお互いのメインフェイズにのみ発動できる。"),
            [self.DRAW, timing("雙方", "メインフェイズ")])

    def test_next_standby_phase_keeps_tsugi(self):
        self.assertEqual(
            rows("①：次の自分スタンバイフェイズに発動できる。自分は１枚ドローする。"),
            [timing("自分", "次のスタンバイフェイズ"), self.DRAW])

    def test_parenthetical_timing_note_in_activation(self):
        self.assertEqual(
            rows("①：手札を１枚捨て、相手フィールドのモンスター１体を対象として発動できる"
                 "（この効果は相手ターンでも発動できる）。そのモンスターを破壊する。"),
            [A("捨てる", "代價", "肯定"), A("対象とする", "條件", "肯定"),
             timing("相手", "ターン", "追加"), A("破壊", "效果", "肯定")])


class TestPledges(unittest.TestCase):
    """票 04:誓約「〜するターン、自分は…しか/を…できない」(含括弧內、このターン、発動後〜
    ターン終了時まで)出限制·誓約,句內的 特殊召喚 否定動作框架不再出現。"""

    DRAW = A("ドロー", "效果", "肯定")

    def test_pledge_only_scope(self):
        self.assertEqual(
            rows("この効果を発動するターン、自分は機械族・闇属性モンスターしか特殊召喚できない。"),
            [pledge("この効果を発動するターン", "特殊召喚", "只能", "機械族・闇属性モンスター")])

    def test_pledge_after_effect_with_source(self):
        self.assertEqual(
            rows("①：このカードをリリースして発動できる。手札から「試作機」１体を特殊召喚する。"
                 "この効果を発動したターン、自分はSモンスターしかEXデッキから特殊召喚できない。"),
            [A("リリース", "代價", "肯定"), A("特殊召喚", "效果", "肯定"),
             pledge("この効果を発動したターン", "特殊召喚", "只能", "Sモンスター", "EXデッキ")])

    def test_pledge_cannot_form_with_coordinated_summons(self):
        self.assertEqual(
            rows("このカードの効果を発動するターン、自分は効果モンスターを召喚・特殊召喚できない。"),
            [pledge("このカードの効果を発動するターン", "召喚・特殊召喚", "不能", "効果モンスター")])

    def test_pledge_in_activation_parenthesis(self):
        self.assertEqual(
            rows("②：墓地のこのカードを除外して発動できる（この効果を発動するターン、自分は"
                 "機械族・闇属性モンスターしか特殊召喚できない）。自分のデッキの機械族モンスター"
                 "１体を手札に加える。"),
            [A("除外", "代價", "肯定"),
             pledge("この効果を発動するターン", "特殊召喚", "只能", "機械族・闇属性モンスター"),
             A("加える", "效果", "肯定")])

    def test_count_note_then_pledge(self):
        self.assertEqual(
            rows("このカード名のカードは１ターンに１枚しか発動できず、このカードを発動するターン、"
                 "自分はサイキック族モンスターしか特殊召喚できない。"),
            [count("回合", 1, "このカード名のカード"),
             pledge("このカードを発動するターン", "特殊召喚", "只能", "サイキック族モンスター")])

    def test_pledge_until_end_of_turn_after_activation(self):
        self.assertEqual(
            rows("①：自分は１枚ドローする。この効果の発動後、ターン終了時まで自分は闇属性"
                 "モンスターしか特殊召喚できない。"),
            [self.DRAW,
             pledge("この効果の発動後、ターン終了時まで", "特殊召喚", "只能", "闇属性モンスター")])

    def test_pledge_this_turn(self):
        self.assertEqual(
            rows("①：自分は１枚ドローする。このターン、自分は「試作機」モンスターしか特殊召喚"
                 "できない。"),
            [self.DRAW, pledge("このターン", "特殊召喚", "只能", "「試作機」モンスター")])

    def test_pledge_scope_keeps_relative_clause(self):
        self.assertEqual(
            rows("①：自分は１枚ドローする。このターン、自分はレベルまたはランクが３以上の"
                 "モンスターしか特殊召喚できない。"),
            [self.DRAW,
             pledge("このターン", "特殊召喚", "只能", "レベルまたはランクが３以上のモンスター")])

    def test_pledge_manner_before_shika(self):
        self.assertEqual(
            rows("この効果を発動するターン、自分は裏側守備表示でしかモンスターを特殊召喚できない。"),
            [pledge("この効果を発動するターン", "特殊召喚", "只能", "モンスター(裏側守備表示で)")])

    def test_this_turn_without_ban_is_not_a_pledge(self):
        self.assertEqual(rows("①：このターン、自分は１枚ドローする。"), [self.DRAW])

    def test_two_pledge_predicates(self):
        self.assertEqual(
            rows("①：自分は１枚ドローする。このターン、自分はエクストラデッキからモンスターを"
                 "特殊召喚できず、地属性以外のモンスターの効果を発動できない。"),
            [self.DRAW,
             pledge("このターン", "特殊召喚", "不能", "モンスター", "エクストラデッキ"),
             pledge("このターン", "発動", "不能", "地属性以外のモンスターの効果")])


class TestSummonConditions(unittest.TestCase):
    """票 04:效果外文本的召喚條件句出限制·召喚條件(形式/方式/手續/來源),召喚手續與
    特殊召喚 本身不再出動作框架;編號效果裡的同形句照舊是動作框架。"""

    def test_cannot_normal_summon_then_only_by_procedure(self):
        self.assertEqual(
            rows("このカードは通常召喚できない。自分の墓地の「SPYRAL」カード３枚を除外した"
                 "場合のみ特殊召喚できる。"),
            [summon("不能通常召喚"),
             summon("只能以某方式特殊召喚",
                    procedure=[{"action": "除外",
                                "object": "自分の墓地の「SPYRAL」カード3枚"}])])

    def test_only_by_card_effect(self):
        self.assertEqual(
            rows("このカードは通常召喚できず、カードの効果でのみ特殊召喚できる。"),
            [summon("不能通常召喚"), summon("只能以某方式特殊召喚", method="カードの効果")])

    def test_only_by_fusion_summon_from_extra_deck(self):
        self.assertEqual(
            rows("このカードは融合召喚でのみＥＸデッキから特殊召喚できる。"),
            [summon("只能以某方式特殊召喚", method="融合召喚", source="ＥＸデッキ")])

    def test_deshika_dekinai_is_only_form(self):
        self.assertEqual(
            rows("このカードは融合召喚でしか特殊召喚できない。"),
            [summon("只能以某方式特殊召喚", method="融合召喚")])

    def test_cannot_special_summon_only_in_extra_text(self):
        self.assertEqual(rows("このカードは特殊召喚できない。"), [summon("不能特殊召喚")])
        self.assertEqual(rows("①：このカードは特殊召喚できない。"),
                         [A("特殊召喚", "效果", "否定")])

    def test_summon_condition_with_count_gives_two_frames(self):
        self.assertEqual(
            rows("「終焉龍 カオス・エンペラー」は１ターンに１度、自分の墓地の光属性と闇属性の"
                 "モンスターを１体ずつ除外した場合のみ、EXデッキから特殊召喚できる。"),
            [count("回合", 1, "「終焉龍 カオス・エンペラー」の特殊召喚"),
             summon("只能以某方式特殊召喚",
                    procedure=[{"action": "除外",
                                "object": "自分の墓地の光属性と闇属性のモンスター"}],
                    source="EXデッキ")])

    def test_xyz_summon_procedure_with_count(self):
        self.assertEqual(
            rows("「FA－ホープ・レイ・ランサー」は１ターンに１度、自分フィールドの「希望皇ホープ」"
                 "モンスターの上に重ねてX召喚する事もできる。"),
            [count("回合", 1, "「FA－ホープ・レイ・ランサー」のX召喚"),
             summon("可以某方式X召喚",
                    procedure=[{"action": "重ねる",
                                "goal": "自分フィールドの「希望皇ホープ」モンスターの上"}])])

    def test_method_list_with_option_procedure(self):
        text = ("このカードは融合召喚及び以下の方法でのみ特殊召喚できる。\n●自分のモンスター"
                "ゾーンの上記のカードを墓地へ送った場合にEXデッキから特殊召喚できる。")
        self.assertEqual(
            rows(text),
            [summon("只能以某方式特殊召喚", method="融合召喚及び以下の方法"),
             summon("可以某方式特殊召喚",
                    procedure=[{"action": "送る", "object": "自分のモンスターゾーンの上記のカード",
                                "goal": "墓地"}],
                    source="EXデッキ")])
        self.assertEqual([f["option"] for f in frames.extract(text)], [None, 1])

    def test_tribute_then_advance_summon(self):
        self.assertEqual(
            rows("このカードはアドバンス召喚したモンスター１体をリリースしてアドバンス召喚できる。"),
            [summon("可以某方式アドバンス召喚",
                    procedure=[{"action": "リリース",
                                "object": "アドバンス召喚したモンスター1体"}])])

    def test_cannot_synchro_then_only_by_procedure(self):
        self.assertEqual(
            rows("このカードはS召喚できず、自分フィールドからチューナー１体とチューナー以外の"
                 "モンスター１体を墓地へ送った場合のみ特殊召喚できる。"),
            [summon("不能S召喚"),
             summon("只能以某方式特殊召喚",
                    procedure=[{"action": "送る",
                                "object": "チューナー1体とチューナー以外のモンスター1体",
                                "source": "自分フィールド", "goal": "墓地"}])])


class TestMaterials(unittest.TestCase):
    """票 05:效果外文本的素材行與降臨句出素材框架(召喚法由卡片子類型帶入、有序清單帶數量)。"""

    def test_fusion_material_line(self):
        self.assertEqual(
            rows("「アマゾネス女王」＋「アマゾネス」モンスター", card_type="融合"),
            [material("融合", [("「アマゾネス女王」", 1), ("「アマゾネス」モンスター", 1)])])

    def test_times_count(self):
        self.assertEqual(
            rows("「双天脚の鴻鵠」＋「双天」モンスター×２", card_type="融合"),
            [material("融合", [("「双天脚の鴻鵠」", 1), ("「双天」モンスター", 2)])])

    def test_synchro_lower_bound(self):
        self.assertEqual(
            rows("チューナー＋チューナー以外のモンスター１体以上", card_type="同調"),
            [material("同調", [("チューナー", 1), ("チューナー以外のモンスター", "1以上")])])

    def test_xyz_times(self):
        self.assertEqual(rows("レベル４モンスター×３", card_type="超量"),
                         [material("超量", [("レベル４モンスター", 3)])])
        self.assertEqual(rows("レベル１モンスター×２体以上", card_type="超量"),
                         [material("超量", [("レベル１モンスター", "2以上")])])

    def test_link_quantity(self):
        self.assertEqual(rows("効果モンスター２体以上", card_type="連結"),
                         [material("連結", [("効果モンスター", "2以上")])])
        self.assertEqual(rows("「キスキル」モンスターを含むモンスター２体", card_type="連結"),
                         [material("連結", [("「キスキル」モンスターを含むモンスター", 2)])])

    def test_ritual_descent_line(self):
        self.assertEqual(rows("「光の黄金櫃」により降臨。", card_type="儀式"),
                         [material("儀式", [("「光の黄金櫃」", 1)])])
        self.assertEqual(rows("「ヴェンデット」儀式魔法カードにより降臨"),
                         [material("儀式", [("「ヴェンデット」儀式魔法カード", 1)])])

    def test_without_card_type_method_is_empty(self):
        self.assertEqual(rows("レベル４モンスター×３"),
                         [material(None, [("レベル４モンスター", 3)])])

    def test_non_material_extra_lines_stay_unframed(self):
        self.assertEqual(rows("「御巫」モンスターにのみ装備可能。", card_type="融合"), [])
        self.assertEqual(rows("「ヴェンデット」儀式モンスターの降臨に必要。"), [])

    def test_effect_sentence_is_not_a_material_line(self):
        self.assertEqual(rows("①：レベル４モンスター×３", card_type="超量"), [])


class TestActionCountAndWindow(unittest.TestCase):
    """票 06:句中「１度だけ」「もう１度だけ」與非發動句的階段窗口記在動作框架自己身上,
    不是約束框架;句首「…度、」仍是限制·次數。"""

    def test_once_per_turn_in_effect_content(self):
        text = "①：装備モンスターは１ターンに１度だけ戦闘では破壊されない。"
        self.assertEqual(rows(text), [A("破壊", "效果", "否定")])
        self.assertEqual(action_fields(text), [("破壊", 1, "回合", None)])

    def test_extra_normal_summon_count_and_window(self):
        text = "①：自分は通常召喚に加えて１度だけ、自分メインフェイズにモンスター１体を召喚できる。"
        self.assertEqual(rows(text), [A("召喚", "效果", "可能")])
        self.assertEqual(action_fields(text), [("召喚", 1, None, "自分メインフェイズ")])

    def test_one_more_attack(self):
        text = "②：このカードはもう１度だけ続けて攻撃できる。"
        self.assertEqual(rows(text), [A("攻撃", "效果", "可能")])
        self.assertEqual(action_fields(text), [("攻撃", 1, None, None)])

    def test_sentence_initial_count_stays_a_constraint(self):
        text = "①：１ターンに１度、自分は１枚ドローする。"
        self.assertEqual(rows(text), [count("回合", 1, "この効果"), A("ドロー", "效果", "肯定")])
        self.assertEqual(action_fields(text), [("ドロー", None, None, None)])

    def test_while_in_pendulum_zone_once(self):
        text = ("①：このカードがPゾーンに存在する限り１度だけ、このカード以外の自分フィールドの"
                "「ダイナミスト」カードを対象として発動した効果を無効にできる。")
        self.assertEqual(action_fields(text),
                         [("存在", None, None, None), ("無効にする", 1, None, None)])


class TestConstraintRound1Fixes(unittest.TestCase):
    """票 08:第一輪 LLM 檢驗(constraint-round1)各同型錯誤的回歸例子。"""

    DRAW = A("ドロー", "效果", "肯定")

    def test_player_turn_count_prefix_gives_count_and_timing(self):
        self.assertEqual(
            rows("①：相手ターンに１度、自分は１枚ドローする。"),
            [count("回合", 1, "この効果"), timing("相手", "ターン"), self.DRAW])
        self.assertEqual(
            rows("③：自分・相手ターンに１度、フィールドの魔法・罠カード１枚を対象として"
                 "発動できる。そのカードを破壊する。"),
            [count("回合", 1, "この効果"), timing("雙方", "ターン"),
             A("対象とする", "條件", "肯定"), A("破壊", "效果", "肯定")])

    def test_pledge_subject_this_card(self):
        self.assertEqual(
            rows("①：自分は１枚ドローする。この効果を発動するターン、このカードは攻撃できない。"),
            [self.DRAW, pledge("この効果を発動するターン", "攻撃", "不能", None,
                               subject="このカード")])
        self.assertEqual(
            rows("①：自分は１枚ドローする。この効果を発動するターン、このカードしか攻撃できない。"),
            [self.DRAW, pledge("この効果を発動するターン", "攻撃", "只能", "このカード")])

    def test_pledge_subject_own_monsters(self):
        self.assertEqual(
            rows("①：自分は１枚ドローする。この効果で守備表示にしたターン、自分のモンスターは"
                 "対象のモンスターしか攻撃できず、戦闘ダメージは０になる。"),
            [self.DRAW,
             pledge("この効果で守備表示にしたターン", "攻撃", "只能", "対象のモンスター",
                    subject="自分のモンスター"),
             A("になる", "效果", "肯定")])

    def test_protection_this_turn_is_not_a_pledge(self):
        """被動否定(破壊されない)是保護效果,不是誓約;可能形否定(攻撃できない)才是。"""
        self.assertEqual(
            rows("①：自分は１枚ドローする。このターン、このカードは戦闘・効果では破壊されない。"),
            [self.DRAW, A("破壊", "效果", "否定")])

    def test_opponent_restriction_this_turn_is_not_a_pledge(self):
        self.assertEqual(
            rows("①：自分は１枚ドローする。このターン、相手はモンスターの効果を発動できない。"),
            [self.DRAW, A("発動", "效果", "否定")])

    def test_window_ending_with_comma(self):
        self.assertEqual(
            rows("②：自分・相手のバトルフェイズ終了時、自分フィールドに「試作機」が存在する"
                 "場合に発動できる。自分は１枚ドローする。"),
            [timing("雙方", "バトルフェイズ終了時"), A("存在", "條件", "肯定"), self.DRAW])

    def test_window_inside_trigger_clause_is_not_a_timing(self):
        self.assertEqual(
            rows("①：相手がバトルフェイズにモンスターの効果を発動した時に発動できる。"
                 "自分は１枚ドローする。"),
            [A("発動", "條件", "肯定"), self.DRAW])
        self.assertEqual(
            rows("①：このカードがメインフェイズにリバースした場合に発動する。自分は１枚ドローする。"),
            [A("リバース", "條件", "肯定"), self.DRAW])

    def test_gemini_resummon_is_an_action_with_count(self):
        text = "②：フィールドの通常モンスター扱いのこのカードを通常召喚としてもう１度召喚できる。"
        self.assertEqual(rows(text, extra=True), [A("召喚", "效果", "可能")])
        self.assertEqual(action_fields(text, extra=True), [("召喚", 1, None, None)])

    def test_pledge_attack_declaration_action_name(self):
        self.assertEqual(
            rows("このターン、自分は「空牙団」モンスターでしか攻撃宣言できない。"),
            [pledge("このターン", "攻撃宣言", "只能", "「空牙団」モンスターで")])

    def test_pledge_scope_manner_before_shika_keeps_relative_clause(self):
        self.assertEqual(
            rows("①：自分は１枚ドローする。このターン、自分は「紋章獣」モンスターのみを素材と"
                 "したX召喚でしかEXデッキからモンスターを特殊召喚できない。"),
            [self.DRAW,
             pledge("このターン", "特殊召喚", "只能",
                    "モンスター(「紋章獣」モンスターのみを素材としたX召喚で)", "EXデッキ")])

    def test_pledge_scope_from_ga_subject(self):
        self.assertEqual(
            rows("①：自分は１枚ドローする。このターン、自分はこの効果で手札に加えたカードの"
                 "効果の発動ができない。"),
            [self.DRAW,
             pledge("このターン", "発動", "不能", "この効果で手札に加えたカードの効果")])

    def test_two_ritual_spells_in_descent_line(self):
        self.assertEqual(
            rows("「カオス・フォーム」「超戦士の儀式」により降臨"),
            [material("儀式", [("「カオス・フォーム」", 1), ("「超戦士の儀式」", 1)])])

    def test_material_line_each_one_total(self):
        self.assertEqual(
            rows("ドラゴン族の融合・S・X・Pモンスター１体ずつ合計４体", card_type="融合"),
            [material("融合", [("ドラゴン族の融合・S・X・Pモンスター", "4(1体ずつ)")])])

    def test_event_turn_before_summon_procedure_stays_a_condition(self):
        self.assertEqual(
            rows("雷族モンスターの効果が手札で発動したターン、融合モンスター以外の自分フィールド"
                 "の雷族の効果モンスター１体をリリースした場合にEXデッキから特殊召喚できる。"),
            [A("発動", "條件", "肯定"),
             summon("可以某方式特殊召喚",
                    procedure=[{"action": "リリース",
                                "object": "融合モンスター以外の自分フィールドの雷族の効果モンスター1体"}],
                    source="EXデッキ")])

    def test_window_with_comma_before_condition_clause(self):
        """round2:「自分・相手ターンに、…場合、…発動できる」的窗口自成一段,是時機。"""
        self.assertEqual(
            rows("①：自分・相手ターンに、自分フィールドにカードが存在しない場合、このカードを"
                 "手札から捨てて発動できる。自分は１枚ドローする。"),
            [timing("雙方", "ターン"), A("存在", "條件", "否定"), A("捨てる", "代價", "肯定"),
             self.DRAW])

    def test_pledge_direct_attack_action_name(self):
        self.assertEqual(
            rows("①：自分は１枚ドローする。このターン、このカードは直接攻撃できない。"),
            [self.DRAW, pledge("このターン", "直接攻撃", "不能", None, subject="このカード")])

    def test_must_tribute_to_normal_summon(self):
        self.assertEqual(
            rows("このカードを通常召喚する場合、自分フィールドのモンスター３体をリリースして"
                 "召喚しなければならず、このカードは特殊召喚できない。"),
            [summon("必須以某方式召喚",
                    procedure=[{"action": "リリース", "object": "自分フィールドのモンスター3体"}]),
             summon("不能特殊召喚")])


class TestConstraintRound3Fixes(unittest.TestCase):
    """票 09:新種子抽驗(constraint-round3)小型同型的回歸例子。"""

    DRAW = A("ドロー", "效果", "肯定")

    def test_parenthetical_damage_step_note(self):
        self.assertEqual(
            rows("②：モンスターが手札から捨てられた場合に発動できる（ダメージステップでも"
                 "発動可能）。自分は１枚ドローする。"),
            [A("捨てる", "條件", "肯定"), timing(None, "ダメージステップ", "追加"), self.DRAW])

    def test_count_prefix_with_made(self):
        self.assertEqual(
            rows("①：１ターンに３度まで、相手がモンスターを召喚した場合に発動できる。"
                 "自分は１枚ドローする。"),
            [count("回合", 3, "この効果"), A("召喚", "條件", "肯定"), self.DRAW])

    def test_phase_count_prefix_gives_count_and_timing(self):
        self.assertEqual(
            rows("②：自分・相手のメインフェイズ１に１度、このカードのX素材を１つ取り除いて"
                 "発動できる。自分は１枚ドローする。"),
            [count("回合", 1, "この効果"), timing("雙方", "メインフェイズ１"),
             A("取り除く", "代價", "肯定"), self.DRAW])

    def test_effect_on_summoned_monster_is_not_a_pledge(self):
        self.assertEqual(
            rows("②：自分は１枚ドローする。この効果で特殊召喚したモンスターはこのターン、"
                 "効果が無効化され、L素材にできない。"),
            [self.DRAW, A("無効化", "效果", "肯定"), A("L素材にする", "效果", "否定")])

    def test_condition_clause_is_not_a_pledge_subject(self):
        self.assertEqual(
            rows("①：自分は１枚ドローする。このターン、自分の墓地に「試作機」が存在しない"
                 "場合には、そのカードは発動できない。"),
            [self.DRAW, A("存在", "條件", "否定"), A("発動", "效果", "否定")])

    def test_pledge_with_count_stays_a_pledge(self):
        self.assertEqual(
            rows("①：自分は１枚ドローする。このカードの発動後、次のターンの終了時まで自分は"
                 "魔法カードの効果を１ターンに１度しか発動できない。"),
            [self.DRAW,
             pledge("このカードの発動後、次のターンの終了時まで", "発動", "只能",
                    "魔法カードの効果(１ターンに１度)")])

    def test_each_pledge_predicate_has_its_own_subject(self):
        self.assertEqual(
            rows("このカードを発動するターン、自分はこのカードの効果以外ではモンスターを"
                 "召喚・特殊召喚できず、自分のモンスターは攻撃できない。"),
            [pledge("このカードを発動するターン", "召喚・特殊召喚", "不能", "モンスター"),
             pledge("このカードを発動するターン", "攻撃", "不能", None,
                    subject="自分のモンスター")])


class TestCodeReviewFixes(unittest.TestCase):
    """code review(Spec 軸)指出的正確性問題。"""

    DRAW = A("ドロー", "效果", "肯定")

    def test_card_name_containing_wa_does_not_block_pledge(self):
        self.assertEqual(
            rows("①：自分は１枚ドローする。「はぐれ者」を特殊召喚したターン、自分は"
                 "「はぐれ者」モンスターしか特殊召喚できない。"),
            [self.DRAW, pledge("「はぐれ者」を特殊召喚したターン", "特殊召喚", "只能",
                               "「はぐれ者」モンスター")])

    def test_nomi_inside_procedure_is_not_the_only_form(self):
        self.assertEqual(
            rows("自分フィールドの「試作機」のみをリリースした場合に特殊召喚できる。"),
            [summon("可以某方式特殊召喚",
                    procedure=[{"action": "リリース", "object": "自分フィールドの「試作機」"}])])

    def test_topic_count_prefix_in_effect_is_action_content(self):
        text = "①：このカードは１ターンに１度、戦闘では破壊されない。"
        self.assertEqual(rows(text), [A("破壊", "效果", "否定")])
        self.assertEqual(action_fields(text), [("破壊", 1, "回合", None)])

    def test_internal_topic_field_is_not_exported(self):
        for f in frames.extract("「終焉龍 カオス・エンペラー」は１ターンに１度、自分の墓地の"
                                "モンスター１体を除外した場合のみ特殊召喚できる。"):
            self.assertNotIn("topic", f)


if __name__ == "__main__":
    unittest.main()
