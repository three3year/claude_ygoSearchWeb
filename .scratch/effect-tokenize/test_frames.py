# -*- coding: utf-8 -*-
"""動作框架抽取的行為測試(票 effect-tokenize#05〜#10)。

唯一接縫:一句效果文原文(帶同卡同段上文)→ 動作框架清單(frames.extract)。
用真的分詞器與詞典;只斷言輸出框架的動作、論元、位置、極性,不測規則內部。
每個句型一條回歸例子——修規則前先補一條會失敗的例子。

執行:PYTHONIOENCODING=utf-8 python -m unittest discover -s .scratch/effect-tokenize
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import frames  # noqa: E402


def literal(frame, key):
    """論元欄的原文值:推得的格(frame-args-v3 票 05,規則補的)當作沒寫——推得值另由
    TestInferredValues 斷言。"""
    return None if key in (frame.get("inferred") or ()) else frame.get(key)


def brief(frame):
    """框架 → 比對用的精簡 tuple(動作, 對象, 來源, 目的, 位置, 極性);來源/目的只看原文
    (推得的格當作沒寫)。"""
    return (frame["action"], frame.get("object"), literal(frame, "source"),
            literal(frame, "goal"), frame["position"], frame["polarity"])


def actions(text, context=""):
    """只看動作框架(約束框架的回歸例子在 test_constraints.py)。"""
    return [f for f in frames.extract(text, context) if f["kind"] == "動作"]


def extract(text, context=""):
    return [brief(f) for f in actions(text, context)]


def options(text, context=""):
    """框架 → (動作, 位置, 選項, 標籤):票 14 的選項欄。"""
    return [(f["action"], f["position"], f["option"], f["label"])
            for f in actions(text, context)]


class TestSingleAction(unittest.TestCase):
    """票 05:單動作句——一個動詞、論元是 を/から/に、位置是效果。"""

    def test_search_from_deck_to_hand(self):
        self.assertEqual(
            extract("①：デッキから「試作機」１体を手札に加える。"),
            [("加える", "「試作機」1体", "デッキ", "手札", "效果", "肯定")])

    def test_send_to_grave_is_verb_plus_goal(self):
        """ADR-0014:墓地|へ|送る 三格,框架組回 動作=送る、目的=墓地。"""
        self.assertEqual(
            extract("①：デッキからサイバース族モンスター１体を墓地へ送る。"),
            [("送る", "サイバース族モンスター1体", "デッキ", "墓地",
              "效果", "肯定")])

    def test_object_only_verb(self):
        self.assertEqual(
            extract("①：相手フィールドの表側表示モンスター１体のコントロールを"
                    "得る。"),
            [("得る", "表側表示モンスター1体のコントロール",
              None, None, "效果", "肯定")])

    def test_frame_fields(self):
        """框架欄位第一版:動作、論元、位置、極性、句序、對應詞序列範圍。"""
        frame = frames.extract("①：デッキから「試作機」１体を手札に加える。")[0]
        for key in ("action", "object", "source", "goal", "position",
                    "polarity", "sentence", "span"):
            self.assertIn(key, frame)
        self.assertEqual(frame["sentence"], 0)
        start, end = frame["span"]
        self.assertLess(start, end)


class TestClausesAndPosition(unittest.TestCase):
    """票 06:子句切分與位置——代價/效果/條件,依原文順序。"""

    def test_cost_then_effect(self):
        self.assertEqual(
            extract("①：手札を１枚捨てて発動できる。デッキからモンスター１体を"
                    "手札に加える。"),
            [("捨てる", "手札", "手札", None, "代價", "肯定"),
             ("加える", "モンスター1体", "デッキ", "手札", "效果", "肯定")])

    def test_condition_clause(self):
        self.assertEqual(
            extract("①：自分フィールドに「試作機」が存在する場合に発動できる。"
                    "相手フィールドのカード１枚を破壊する。"),
            [("存在", None, None, "自分フィールド", "條件", "肯定"),
             ("破壊", "カード1枚", None, None, "效果", "肯定")])

    def test_trigger_toki(self):
        self.assertEqual(
            extract("①：このカードが召喚に成功した時に発動できる。"
                    "自分は１枚ドローする。"),
            [("成功", None, None, "召喚", "條件", "肯定"),
             ("ドロー", None, None, None, "效果", "肯定")])

    def test_sonogo_sequence(self):
        self.assertEqual(
            extract("①：手札からモンスター１体を墓地へ送る。その後、自分は"
                    "１枚ドローする。"),
            [("送る", "モンスター1体", "手札", "墓地", "效果", "肯定"),
             ("ドロー", None, None, None, "效果", "肯定")])

    def test_te_form_parallel_actions(self):
        self.assertEqual(
            extract("①：このカードを破壊し、デッキからカード１枚を手札に加える。"),
            [("破壊", "このカード", None, None, "效果", "肯定"),
             ("加える", "カード1枚", "デッキ", "手札", "效果", "肯定")])

    def test_passive_in_activation_is_condition(self):
        self.assertEqual(
            extract("①：このカードが戦闘で破壊され墓地へ送られた場合に発動できる。"
                    "デッキからカード１枚を手札に加える。"),
            [("破壊", None, None, None, "條件", "肯定"),
             ("送る", None, None, "墓地", "條件", "肯定"),
             ("加える", "カード1枚", "デッキ", "手札", "效果", "肯定")])


class TestPredicatesAndPolarity(unittest.TestCase):
    """票 07:述語家族、極性、論元特殊值。"""

    def test_negative_passive(self):
        self.assertEqual(
            extract("①：このカードは戦闘では破壊されない。"),
            [("破壊", None, None, None, "效果", "否定")])

    def test_cannot(self):
        self.assertEqual(
            extract("①：このカードは特殊召喚できない。"),
            [("特殊召喚", None, None, None, "效果", "否定")])

    def test_can_from_hand(self):
        self.assertEqual(
            extract("①：このカードは手札から特殊召喚できる。"),
            [("特殊召喚", None, "手札", None, "效果", "可能")])

    def test_summon_method_from_grave(self):
        self.assertEqual(
            extract("①：自分の墓地からモンスター１体を特殊召喚する。"),
            [("特殊召喚", "モンスター1体", "自分の墓地", None, "效果", "肯定")])

    def test_sahen_banish(self):
        self.assertEqual(
            extract("①：相手の墓地のカード１枚を除外する。"),
            [("除外", "カード1枚", "相手の墓地", None, "效果", "肯定")])

    def test_elided_head_in_object(self):
        self.assertEqual(
            extract("①：フィールドの魔法・罠カード１枚を破壊する。"),
            [("破壊", "魔法(カード)・罠カード1枚", None, None,
              "效果", "肯定")])

    def test_demonstrative_binding_and_target(self):
        self.assertEqual(
            extract("①：相手フィールドのモンスター１体を対象として発動できる。"
                    "そのモンスターを破壊する。"),
            [("対象とする", "モンスター1体", None, None,
              "條件", "肯定"),
             ("破壊", "そのモンスター", None, None, "效果", "肯定")])

    def test_quantity_constraint_in_object(self):
        self.assertEqual(
            extract("①：デッキからレベル４以下のモンスター１体を特殊召喚する。"),
            [("特殊召喚", "レベル4以下のモンスター1体", "デッキ", None,
              "效果", "肯定")])

    def test_lemma_from_conjugated_verb(self):
        self.assertEqual(
            extract("①：このカードを墓地へ送って発動できる。デッキから"
                    "カード１枚を手札に加える。"),
            [("送る", "このカード", None, "墓地", "代價", "肯定"),
             ("加える", "カード1枚", "デッキ", "手札", "效果", "肯定")])

    def test_mukou_ni_suru_is_one_action(self):
        self.assertEqual(
            extract("①：その発動を無効にし破壊する。"),
            [("無効にする", "その発動", None, None, "效果", "肯定"),
             ("破壊", None, None, None, "效果", "肯定")])

    def test_bare_dekinai_takes_topic_as_action(self):
        """約束框架票 02 起:使用次數註記整句是限制·次數框架(test_constraints.py),
        不再出 特殊召喚 動作框架。"""
        self.assertEqual(
            extract("このカード名の①の方法による特殊召喚は１ターンに１度しか"
                    "できない。"),
            [])

    def test_koto_ga_dekiru_is_potential(self):
        self.assertEqual(
            extract("①：このカードを手札に加える事ができる。"),
            [("加える", "このカード", None, "手札", "效果", "可能")])


class TestRound1Fixes(unittest.TestCase):
    """票 10:第一輪 LLM 檢驗(round1)各類高頻錯誤的回歸例子。"""

    def test_nozoku_before_comma_is_attributive(self):
        self.assertEqual(
            extract("①：「アンカーボルト・ヘッジホッグ」を除く、「ジャンク・ウォリアー」"
                    "モンスター１体を墓地へ送る。"),
            [("送る", "「アンカーボルト・ヘッジホッグ」を除く「ジャンク・ウォリアー」"
              "モンスター1体", None, "墓地", "效果", "肯定")])

    def test_ta_tail_relative_clause(self):
        self.assertEqual(
            extract("①：手札に加えたそのモンスターを特殊召喚できる。"),
            [("特殊召喚", "手札に加えたそのモンスター", None, None, "效果", "可能")])

    def test_double_wo_carries_object_to_next_action(self):
        self.assertEqual(
            extract("①：そのモンスター２体を効果を無効にして特殊召喚する。"),
            [("無効にする", "効果", None, None, "效果", "肯定"),
             ("特殊召喚", "そのモンスター2体", None, None, "效果", "肯定")])

    def test_double_wo_carries_source_too(self):
        self.assertEqual(
            extract("①：手札・デッキからレベル７以上の恐竜族モンスター１体を"
                    "召喚条件を無視して特殊召喚する。"),
            [("無視", "召喚条件", None, None, "效果", "肯定"),
             ("特殊召喚", "レベル7以上の恐竜族モンスター1体", "手札・デッキ", None,
              "效果", "肯定")])

    def test_option_label_is_not_an_argument(self):
        self.assertEqual(
            extract("●魔法：自分の墓地から魔法カード１枚を手札に加える。"),
            [("加える", "魔法カード1枚", "自分の墓地", "手札", "效果", "肯定")])

    def test_adverb_sarani_not_in_argument(self):
        self.assertEqual(
            extract("①：さらに相手フィールドのモンスター１体を選んで破壊する。"),
            [("選ぶ", "モンスター1体", None, None, "效果", "肯定"),
             ("破壊", "モンスター1体", None, None, "效果", "肯定")])

    def test_coordinated_summon_predicates_both_framed(self):
        self.assertEqual(
            extract("①：このカードが召喚・特殊召喚した場合に発動できる。"
                    "自分は１枚ドローする。"),
            [("召喚", None, None, None, "條件", "肯定"),
             ("特殊召喚", None, None, None, "條件", "肯定"),
             ("ドロー", None, None, None, "效果", "肯定")])

    def test_sozai_toshite_is_an_action(self):
        self.assertEqual(
            extract("①：Pモンスターを素材として融合召喚していた場合、"
                    "自分は１枚ドローする。"),
            [("素材とする", "Pモンスター", None, None, "條件", "肯定"),
             ("融合召喚", None, None, None, "條件", "肯定"),
             ("ドロー", None, None, None, "效果", "肯定")])

    def test_ni_kuwaete_idiom_is_not_an_action(self):
        self.assertEqual(
            extract("①：自分は通常召喚に加えて１度だけ、自分メインフェイズに"
                    "モンスター１体を召喚できる。"),
            [("召喚", "モンスター1体", None, None, "效果", "可能")])

    def test_tsuzukete_is_an_adverb(self):
        self.assertEqual(
            extract("①：このカードは続けて攻撃できる。"),
            [("攻撃", None, None, None, "效果", "可能")])

    def test_activating_this_card_is_not_an_action(self):
        self.assertEqual(
            extract("自分フィールドに「試作機」が存在する場合、このカードを"
                    "発動できる。"),
            [("存在", None, None, "自分フィールド", "條件", "肯定")])

    def test_choosing_an_option_is_a_condition(self):
        self.assertEqual(
            extract("①：以下の効果から１つを選択して発動できる。"
                    "●自分は１枚ドローする。"),
            [("選択", "1つ", "以下の効果", None, "條件", "肯定"),
             ("ドロー", None, None, None, "效果", "肯定")])

    def test_conditional_form_is_a_condition(self):
        self.assertEqual(
            extract("①：５００LPを払わなければ、カードの効果を発動できない。"),
            [("払う", "500LP", None, None, "條件", "肯定"),
             ("発動", "カードの効果", None, None, "效果", "否定")])

    def test_state_chain_before_baai_is_condition(self):
        self.assertEqual(
            extract("①：相手フィールドにモンスターが２体以上存在し、自分フィールド"
                    "にモンスターが存在しない場合、このカードは手札から"
                    "特殊召喚できる。"),
            [("存在", None, None, "相手フィールド", "條件", "肯定"),
             ("存在", None, None, "自分フィールド", "條件", "否定"),
             ("特殊召喚", None, "手札", None, "效果", "可能")])

    def test_relative_clause_before_attack_declaration(self):
        self.assertEqual(
            extract("①：このカードが相手モンスターと戦闘を行う攻撃宣言時に"
                    "発動できる。そのモンスターを破壊する。"),
            [("攻撃宣言", None, None, None, "條件", "肯定"),
             ("破壊", "そのモンスター", None, None, "效果", "肯定")])

    def test_release_and_advance_summon_are_two_actions(self):
        """約束框架票 04 起:效果外文本的召喚條件句整句是限制·召喚條件框架
        (test_constraints.py),アドバンス召喚 不出動作框架;summon-procedure 票 02 起手續的 リリース
        另出召喚手續框。同形句在編號效果裡照舊是兩個效果位的動作。"""
        self.assertEqual(
            extract("このカードはアドバンス召喚したモンスター１体をリリースして"
                    "アドバンス召喚できる。"),
            [("リリース", "アドバンス召喚したモンスター1体", None, None, "召喚手續", "肯定")])
        self.assertEqual(
            extract("①：このカードはアドバンス召喚したモンスター１体をリリースして"
                    "アドバンス召喚できる。"),
            [("リリース", "アドバンス召喚したモンスター1体", None, None,
              "效果", "肯定"),
             ("A召喚", None, None, None, "效果", "可能")])

    def test_bare_number_of_time_phrase_stays_out_of_object(self):
        """約束框架票 02 起:「〜を１ターンに１度しか特殊召喚できない」是限制·次數框架
        (對象 〜の特殊召喚),不再出動作框架;裸數字不進對象的規則改由本例驗:"""
        self.assertEqual(
            extract("「精霊獣 カンナホーク」を１ターンに１度しか特殊召喚できない。"),
            [])
        self.assertEqual(
            extract("①：「精霊獣 カンナホーク」を１ターンに１体まで特殊召喚できる。"),
            [("特殊召喚", "「精霊獣 カンナホーク」", None, None, "效果", "可能")])

    def test_otagai_ni_is_not_a_goal(self):
        self.assertEqual(
            extract("①：お互いに墓地のモンスターを特殊召喚できない。"),
            [("特殊召喚", "モンスター", "墓地", None, "效果", "否定")])

    def test_relative_naru_does_not_absorb_object(self):
        self.assertEqual(
            extract("①：このカードを対象のモンスターのリンク先となる自分フィールド"
                    "に特殊召喚する。"),
            [("特殊召喚", "このカード", None,
              "対象のモンスターのリンク先となる自分フィールド", "效果", "肯定")])

    def test_taisho_ni_mo_dekinai(self):
        self.assertEqual(
            extract("①：このカードは効果の対象にもできない。"),
            [("対象にする", None, None, None, "效果", "否定")])

    def test_kisareta_absorbs_ni(self):
        self.assertEqual(
            extract("①：融合モンスターカードに記された罠カード１枚を墓地へ送る。"),
            [("送る", "融合モンスターカードに記された罠カード1枚", None, "墓地",
              "效果", "肯定")])

    def test_attribute_ga_phrase_stays_in_object(self):
        self.assertEqual(
            extract("①：デッキから攻撃力と守備力が０の悪魔族モンスター１体を"
                    "特殊召喚する。"),
            [("特殊召喚", "攻撃力と守備力が0の悪魔族モンスター1体", "デッキ", None,
              "效果", "肯定")])

    def test_target_in_parenthesis_is_condition(self):
        self.assertEqual(
            extract("①：自分の墓地のモンスター１体を対象として発動できる"
                    "（代わりに自分の墓地の罠カード１枚を対象とする事もできる）。"
                    "そのカードを手札に加える。"),
            [("対象とする", "モンスター1体", None, None, "條件", "肯定"),
             ("対象とする", "罠カード1枚", None, None, "條件", "可能"),
             ("加える", "そのカード", None, "手札", "效果", "肯定")])

    def test_onaji_and_adjective_relative_clauses(self):
        self.assertEqual(
            extract("①：そのモンスターと元々のレベルが同じモンスター１体をデッキ"
                    "から手札に加える。除外したモンスターよりレベルが高い天使族"
                    "モンスター１体を手札から特殊召喚する。"),
            [("加える", "そのモンスターと元々のレベルが同じモンスター1体", "デッキ",
              "手札", "效果", "肯定"),
             ("特殊召喚", "除外したモンスターよりレベルが高い天使族モンスター1体",
              "手札", None, "效果", "肯定")])

    def test_comma_separated_name_list_stays_one_phrase(self):
        self.assertEqual(
            extract("①：手札から「ガガガ」、「ドドド」、「ゴゴゴ」モンスターを"
                    "合計２体まで守備表示で特殊召喚できる。"),
            [("特殊召喚", "「ガガガ」「ドドド」「ゴゴゴ」モンスター", "手札", None,
              "效果", "可能")])


class TestRound2Fixes(unittest.TestCase):
    """票 10:同批複檢(round2)剩餘高頻錯誤的回歸例子。"""

    def test_scoped_relative_absorbs_only_nearest_wo(self):
        self.assertEqual(
            extract("①：そのモンスター以外の、自分の墓地のXモンスター１体を以下の"
                    "効果を持つ装備魔法カード扱いで対象のモンスターに装備する。"),
            [("装備", "そのモンスター以外のXモンスター1体", "自分の墓地",
              "対象のモンスター", "效果", "肯定")])

    def test_method_chain_summons_each_framed(self):
        self.assertEqual(
            extract("①：モンスターが儀式・融合・S・X召喚された場合に発動できる。"
                    "自分は１枚ドローする。"),
            [("儀式召喚", None, None, None, "條件", "肯定"),
             ("融合召喚", None, None, None, "條件", "肯定"),
             ("S召喚", None, None, None, "條件", "肯定"),
             ("X召喚", None, None, None, "條件", "肯定"),
             ("ドロー", None, None, None, "效果", "肯定")])

    def test_leading_time_phrase_dropped_with_its_particle(self):
        self.assertEqual(
            extract("●このターンに戦闘を行った相手フィールドのモンスター１体を"
                    "破壊する。"),
            [("破壊", "戦闘を行ったモンスター1体", None, None,
              "效果", "肯定")])

    def test_renyo_potential_before_comma_is_an_action(self):
        self.assertEqual(
            extract("●このカードは相手モンスターに続けて攻撃でき、守備表示モンスター"
                    "を攻撃した場合、戦闘ダメージを与える。"),
            [("攻撃", None, None, "相手モンスター", "效果", "可能"),
             ("攻撃", "守備表示モンスター", None, None, "條件", "肯定"),
             ("与える", "戦闘ダメージ", None, None, "效果", "肯定")])

    def test_result_clause_before_comma_is_not_a_condition(self):
        self.assertEqual(
            extract("①：このカードの攻撃力は１０００アップし、相手フィールドに"
                    "モンスターが存在する場合、その攻撃力はダウンする。"),
            [("アップ", None, None, None, "效果", "肯定"),
             ("存在", None, None, "相手フィールド", "條件", "肯定"),
             ("ダウン", None, None, None, "效果", "肯定")])


class TestRound3Fixes(unittest.TestCase):
    """票 10:新種子樣本(round3)抽驗的回歸例子。"""

    def test_passive_result_before_condition_stays_effect(self):
        self.assertEqual(
            extract("①：この効果で特殊召喚したモンスターの効果は無効化され、"
                    "フィールドから離れた場合に除外される。"),
            [("無効にする", None, None, None, "效果", "肯定"),
             ("離れる", None, "フィールド", None, "條件", "肯定"),
             ("除外", None, None, None, "效果", "肯定")])

    def test_this_effect_cannot_be_activated_is_a_note(self):
        self.assertEqual(
            extract("①：自分は１枚ドローする。この効果はこのカードが特殊召喚した"
                    "ターンには発動できない。"),
            [("ドロー", None, None, None, "效果", "肯定")])

    def test_coordinated_materials_each_framed(self):
        self.assertEqual(
            extract("①：このカードを融合素材またはリンク素材として墓地へ送った"
                    "場合、自分は１枚ドローする。"),
            [("融合素材とする", "このカード", None, None, "條件", "肯定"),
             ("L素材とする", "このカード", None, None, "條件", "肯定"),
             ("送る", "このカード", None, "墓地", "條件", "肯定"),
             ("ドロー", None, None, None, "效果", "肯定")])

    def test_te_ireba_is_a_condition(self):
        self.assertEqual(
            extract("①：自分のPスケールの合計がP召喚したモンスターのレベルの合計を"
                    "超えていれば発動できる。自分は１枚ドローする。"),
            [("超える", "P召喚したモンスターのレベルの合計", None, None, "條件",
              "肯定"),
             ("ドロー", None, None, None, "效果", "肯定")])

    def test_activation_with_goal_is_an_action(self):
        self.assertEqual(
            extract("①：デッキからフィールド魔法カード１枚を選び、手札に加えるか"
                    "自分フィールドに発動する。"),
            [("選ぶ", "フィールド魔法カード1枚", "デッキ", None, "效果", "肯定"),
             ("加える", "フィールド魔法カード1枚", "デッキ", "手札", "效果", "肯定"),
             ("発動", "フィールド魔法カード1枚", None, "自分フィールド", "效果",
              "肯定")])

    def test_noun_ga_dekinai_and_motanai_relative(self):
        self.assertEqual(
            extract("①：レベルを持たないモンスターの効果は発動できない。"
                    "このターン自分は特殊召喚ができない。"),
            [("発動", None, None, None, "效果", "否定"),
             ("特殊召喚", None, None, None, "效果", "否定")])

    def test_state_clause_before_no_baai_is_condition(self):
        self.assertEqual(
            extract("①：特殊召喚されたモンスターが相手フィールドに存在し、"
                    "自分フィールドのモンスターが１体のみの場合、このカードは"
                    "手札から特殊召喚できる。"),
            [("存在", None, None, "相手フィールド", "條件", "肯定"),
             ("特殊召喚", None, "手札", None, "效果", "可能")])

    def test_zu_negative_renyo_is_an_action(self):
        self.assertEqual(
            extract("①：そのカードをデッキに戻さず手札に加える事もできる。"),
            [("戻す", "そのカード", None, "デッキ", "效果", "否定"),
             ("加える", None, None, "手札", "效果", "可能")])

    def test_to_partner_and_de_modifier(self):
        self.assertEqual(
            extract("①：このカードがモンスターと戦闘を行う場合、デッキから攻撃力"
                    "２４００以上で守備力１０００のモンスター１体を特殊召喚する。"),
            [("行う", "戦闘", None, None, "條件", "肯定"),
             ("特殊召喚", "攻撃力2400以上で守備力1000のモンスター1体", "デッキ",
              None, "效果", "肯定")])

    def test_parenthetical_note_does_not_drop_activation_frames(self):
        self.assertEqual(
            extract("①：手札を１枚捨て、相手フィールドのモンスター１体を対象として"
                    "発動できる（この効果は相手ターンでも発動できる）。"
                    "そのモンスターを破壊する。"),
            [("捨てる", "手札", "手札", None, "代價", "肯定"),
             ("対象とする", "モンスター1体", None, None, "條件",
              "肯定"),
             ("破壊", "そのモンスター", None, None, "效果", "肯定")])

    def test_this_effect_note_without_activation_anchor(self):
        self.assertEqual(
            extract("①：自分は１枚ドローする。この効果は自分フィールドに「試作機」"
                    "が存在する場合に発動と処理ができる。"),
            [("ドロー", None, None, None, "效果", "肯定")])


class TestOptions(unittest.TestCase):
    """票 13/14(ADR-0015):效果句含 ● 選項時,● 是句界,框架記選項與標籤。"""

    def test_single_sentence_frames_have_no_option(self):
        frame = frames.extract("①：デッキから「試作機」１体を手札に加える。")[0]
        self.assertIsNone(frame["option"])
        self.assertIsNone(frame["label"])

    def test_labelled_options_each_with_own_activation(self):
        """43476205 ①:兩個選項各帶選項 1/2 與標籤,対象として 照判條件。"""
        self.assertEqual(
            options("①：発動ターンによって以下の効果を発動できる。\n"
                    "●自分ターン：自分フィールドの「RR」Xモンスター１体を対象として"
                    "発動できる。ランクが１つ高い「RR」モンスター１体を、対象の自分の"
                    "モンスターの上に重ねてX召喚扱いとしてエクストラデッキから特殊召喚"
                    "する。\n"
                    "●相手ターン：相手フィールドのX素材の無いXモンスター１体を対象と"
                    "して発動できる。そのXモンスターのコントロールを得る。"),
            [("対象とする", "條件", 1, "自分ターン"),
             ("重ねる", "效果", 1, "自分ターン"),
             ("特殊召喚", "效果", 1, "自分ターン"),
             ("対象とする", "條件", 2, "相手ターン"),
             ("得る", "效果", 2, "相手ターン")])

    def test_granted_effect_option_keeps_its_activation_sentence(self):
        """220414 ②:●１つ 的 無効にする 在選項 1、標籤 1つ、位置效果。"""
        self.assertEqual(
            options("②：このカードは、このカードのカウンターの数によって以下の効果を"
                    "得る。\n"
                    "●１つ：１ターンに１度、相手モンスターの攻撃宣言時に発動できる。"
                    "その攻撃を無効にする。\n"
                    "●２つ：このカードをリリースして発動できる。フィールドのモンスター"
                    "を全て除外する。"),
            [("得る", "效果", None, None),
             ("攻撃宣言", "條件", 1, "1つ"),
             ("無効にする", "效果", 1, "1つ"),
             ("リリース", "代價", 2, "2つ"),
             ("除外", "效果", 2, "2つ")])

    def test_choose_on_activation_options_are_effects(self):
        """59080 ①:選項裡的 特殊召喚/除外 位置是效果。"""
        self.assertEqual(
            options("①：魔力カウンターを２つ取り除き、以下の効果から１つを選択して"
                    "発動できる。\n"
                    "●自分の手札・EXデッキ（表側）・墓地から魔法使い族モンスター１体を"
                    "特殊召喚する。\n"
                    "●フィールドの他のカード１枚を除外する。"),
            [("取り除く", "代價", None, None),
             ("選択", "條件", None, None),
             ("特殊召喚", "效果", 1, None),
             ("除外", "效果", 2, None)])

    def test_enumerated_items_do_not_frame(self):
        """4079728 ②:選ぶ 的對象仍是「以下のモンスターの内１体」,列舉項不出框架
        (frame-args-v2 後列舉項掛在列舉欄、か 兩邊回填對象與來源,見 TestEnumeration/
        TestBackfill)。"""
        self.assertEqual(
            extract("②：このカードのX素材を２つ取り除いて発動できる。デッキから以下の"
                    "モンスターの内１体を選び、手札に加えるか特殊召喚する。\n"
                    "●「スプリガンズ」モンスター\n"
                    "●「セリオンズ」モンスター\n"
                    "●「アルバスの落胤」またはそのカード名が記されたモンスター"),
            [("取り除く", "このカードのX素材", None, None, "代價", "肯定"),
             ("選ぶ", "以下のモンスターの内1体", "デッキ", None, "效果", "肯定"),
             ("加える", "以下のモンスターの内1体", "デッキ", "手札", "效果", "肯定"),
             ("特殊召喚", "以下のモンスターの内1体", "デッキ", None, "效果", "肯定")])

    def test_unsplit_options_same_frames_plus_option_column(self):
        """269510 ③(未拆 ●):框架與合併前相同,只多選項欄。"""
        text = ("③：フィールドにサイバース族リンクモンスターが２体以上存在する場合、"
                "以下の効果を適用する。\n"
                "●サイバース族モンスターが発動した効果は無効化される。\n"
                "●フィールドのサイバース族モンスターは攻撃できず、攻撃対象にならず、"
                "効果の対象にもならない。")
        self.assertEqual(
            extract(text),
            [("存在", None, None, "フィールド", "條件", "肯定"),
             ("適用", "以下の効果", None, None, "效果", "肯定"),
             ("無効にする", None, None, None, "效果", "肯定"),
             ("攻撃", None, None, None, "效果", "否定"),
             ("攻撃対象にする", None, None, None, "效果", "否定"),
             ("対象にする", None, None, None, "效果", "否定")])
        self.assertEqual([(f["option"], f["label"]) for f in frames.extract(text)],
                         [(None, None), (None, None), (1, None), (2, None),
                          (2, None), (2, None)])

    def test_option_label_values_are_not_arguments(self):
        self.assertEqual(
            options("①：種族を１つ宣言して発動できる。\n"
                    "●魔法：自分の墓地から魔法カード１枚を手札に加える。\n"
                    "●罠：自分の墓地から罠カード１枚を手札に加える。"),
            [("宣言", "代價", None, None),
             ("加える", "效果", 1, "魔法"),
             ("加える", "效果", 2, "罠")])


class TestRound5Fixes(unittest.TestCase):
    """票 16:受影響卡檢驗(round5)高頻錯誤的回歸例子。"""

    def test_motte_iru_relative_clause_is_not_an_action(self):
        """〜を素材として持っているXモンスター:いる 收尾的定語子句,不出 素材とする。"""
        self.assertEqual(
            extract("②：このカードを素材として持っているXモンスターは以下の効果を"
                    "得る。\n●１つ：自分は１枚ドローする。"),
            [("得る", "以下の効果", None, None, "效果", "肯定"),
             ("ドロー", None, None, None, "效果", "肯定")])

    def test_motte_iru_before_comma_is_still_attributive(self):
        """持っている、元々の種族が…のXモンスター:隔讀點的 いる 定語(round6)。"""
        self.assertEqual(
            extract("②：このカードを素材として持っている、元々の種族が獣戦士族のXモンスター"
                    "は以下の効果を得る。\n●このカードのX素材を１つ取り除いて発動できる。"
                    "その発動を無効にする。"),
            [("得る", "以下の効果", None, None, "效果", "肯定"),
             ("取り除く", "このカードのX素材", None, None, "代價", "肯定"),
             ("無効にする", "その発動", None, None, "效果", "肯定")])

    def test_toshite_iru_relative_clause_is_not_an_action(self):
        self.assertEqual(
            extract("①：このカードがX素材としているモンスターの数×１００アップする。"),
            [("アップ", None, None, None, "效果", "肯定")])

    def test_relative_motte_iru_absorbs_its_arguments(self):
        self.assertEqual(
            extract("①：このカードをX素材として持っているXモンスター１体を対象として"
                    "発動できる。そのモンスターを破壊する。"),
            [("対象とする", "このカードをX素材として持っているXモンスター1体", None,
              None, "條件", "肯定"),
             ("破壊", "そのモンスター", None, None, "效果", "肯定")])

    def test_relative_toshite_iru_absorbs_its_arguments(self):
        self.assertEqual(
            extract("①：このカードがX素材としているモンスターを対象として発動できる。"
                    "そのモンスターを破壊する。"),
            [("対象とする", "このカードがX素材としているモンスター", None, None,
              "條件", "肯定"),
             ("破壊", "そのモンスター", None, None, "效果", "肯定")])


def enumerations(text, context=""):
    """框架 → (動作或類別, 對象, 列舉):frame-args-v2 票 01 的列舉欄(兩種框架都看)。"""
    return [(f.get("action") or f["category"], f.get("object"), f.get("enumeration"))
            for f in frames.extract(text, context)]


def groups(text, context=""):
    """動作框架 → (動作, 連接, 群組):票 02。"""
    return [(f["action"], f.get("link"), f.get("group")) for f in actions(text, context)]


def filled(text, context=""):
    """動作框架 → (動作, 對象, 來源, 目的, 回填):票 03;推得的格當作沒寫。"""
    return [(f["action"], f.get("object"), literal(f, "source"), literal(f, "goal"),
             f.get("backfill")) for f in actions(text, context)]


SPRIGGANS = ("②：このカードのX素材を２つ取り除いて発動できる。デッキから以下のモンスターの内"
             "１体を選び、手札に加えるか特殊召喚する。\n●「スプリガンズ」モンスター\n"
             "●「セリオンズ」モンスター\n●「アルバスの落胤」またはそのカード名が記された"
             "モンスター")
SPRIGGANS_ITEMS = ["「スプリガンズ」モンスター", "「セリオンズ」モンスター",
                   "「アルバスの落胤」またはそのカード名が記されたモンスター"]


class TestEnumeration(unittest.TestCase):
    """frame-args-v2 票 01:純列舉項(● 項全部沒有框架)掛進母句「以下の」所指框架的列舉欄,
    對象欄維持原文字面;部分 ● 項有框架的不掛。"""

    def test_items_attach_to_the_ika_no_object_frame(self):
        self.assertEqual(
            enumerations(SPRIGGANS),
            [("取り除く", "このカードのX素材", None),
             ("選ぶ", "以下のモンスターの内1体", SPRIGGANS_ITEMS),
             ("加える", "以下のモンスターの内1体", None),
             ("特殊召喚", "以下のモンスターの内1体", None)])

    def test_items_fall_back_to_the_frame_whose_clause_has_ika(self):
        self.assertEqual(
            enumerations("②：自分フィールドの以下のモンスターが戦闘・効果で破壊される場合、"
                         "代わりにフィールド・墓地のこのカードを除外できる。\n"
                         "●「ジャンク・ウォリアー」のカード名が記されたモンスター\n"
                         "●元々のカード名に「ウォリアー」を含むSモンスター"),
            [("破壊", None, ["「ジャンク・ウォリアー」のカード名が記されたモンスター",
                           "元々のカード名に「ウォリアー」を含むSモンスター"]),
             ("除外", "このカード", None)])

    def test_item_text_drops_the_bullet_and_trailing_period(self):
        self.assertEqual(
            enumerations("②：自分メインフェイズに発動できる。デッキから以下のカードの内いずれか"
                         "１枚を手札に加える。\n●「海」。\n●「リバイアサン」魔法・罠カード"),
            [("時機", None, None),
             ("加える", "以下のカードの内いずれか1枚", ["「海」", "「リバイアサン」魔法・罠カード"])])

    def test_partial_enumeration_is_not_attached(self):
        self.assertEqual(
            enumerations("②：デッキから以下のカードの内１枚を手札に加える。\n●「海」\n"
                         "●自分フィールドのカード１枚を破壊する。"),
            [("加える", "以下のカードの内1枚", None), ("破壊", "カード1枚", None)])


class TestLinkAndGroup(unittest.TestCase):
    """frame-args-v2 票 02:か 並列的述語各自一個框架,都記 連接=或、群組=n(一句效果句內
    從 1 起編);名詞間的 か 與 その後 不記。"""

    def test_ka_coordinated_predicates_share_a_group(self):
        self.assertEqual(
            groups("①：デッキからモンスター１体を手札に加えるか特殊召喚する。"),
            [("加える", "或", 1), ("特殊召喚", "或", 1)])

    def test_three_way_ka(self):
        self.assertEqual(
            groups("①：デッキからカード１枚を手札に加えるか特殊召喚するか墓地へ送る。"),
            [("加える", "或", 1), ("特殊召喚", "或", 1), ("送る", "或", 1)])

    def test_groups_are_numbered_in_order_within_the_effect_clause(self):
        self.assertEqual(
            groups("①：手札を１枚捨てるかこのカードをリリースして発動できる。デッキから"
                   "カード１枚を手札に加えるか特殊召喚する。"),
            [("捨てる", "或", 1), ("リリース", "或", 1),
             ("加える", "或", 2), ("特殊召喚", "或", 2)])

    def test_ka_between_nouns_is_not_a_group(self):
        self.assertEqual(
            groups("①：デッキからモンスターか魔法カード１枚を手札に加える。"),
            [("加える", None, None)])
        self.assertEqual(
            extract("①：デッキからモンスターか魔法カード１枚を手札に加える。"),
            [("加える", "モンスターか魔法カード1枚", "デッキ", "手札", "效果", "肯定")])

    def test_sonogo_is_not_a_link(self):
        self.assertEqual(
            groups("①：デッキからカード１枚を手札に加える。その後、自分は１枚ドローする。"),
            [("加える", None, None), ("ドロー", None, None)])

    def test_ka_member_is_the_head_of_a_te_form_chain(self):
        """v2-round1:「戻すか召喚条件を無視して特殊召喚する」的右成員是鏈的收尾 特殊召喚,
        不是緊接 か 的 無視して;回填也落在 特殊召喚。"""
        text = ("①：自分の墓地のモンスター１体を対象として発動できる。そのモンスターを"
                "EXデッキに戻すか召喚条件を無視して特殊召喚する。")
        self.assertEqual(
            groups(text),
            [("対象とする", None, None), ("戻す", "或", 1), ("無視", None, None),
             ("特殊召喚", "或", 1)])
        self.assertEqual(
            filled(text)[1:],
            [("戻す", "そのモンスター", None, "EXデッキ", None),
             ("無視", "召喚条件", None, None, None),
             ("特殊召喚", "そのモンスター", None, None, ["object"])])

    def test_ka_chain_does_not_cross_a_comma(self):
        """code review:「戻すか墓地へ送り、相手に…与える」的第二成員是讀點前的 送る,
        不跨過讀點跳到 与える。"""
        self.assertEqual(
            groups("①：そのカードをデッキに戻すか墓地へ送り、相手に５００ダメージを与える。"),
            [("戻す", "或", 1), ("送る", "或", 1), ("与える", None, None)])

    def test_nakaguro_coordinated_predicates_are_not_a_ka_group(self):
        """召喚・リバースした 是一個錨點出兩個框架,不是 か 並列。"""
        self.assertEqual(
            groups("③：このカードが召喚・リバースしたターンのエンドフェイズに発動する。"
                   "このカードを手札に戻す。"),
            [("召喚", None, None), ("リバース", None, None), ("戻す", None, None)])


class TestBackfill(unittest.TestCase):
    """frame-args-v2 票 03:か 群組與選ぶ鏈之後缺對象的述語從前面接過對象與來源,框架記
    回填欄;到句號、有對象的述語、新主題 は 為止;從不帶對象的動作不填;不填目的。"""

    def test_select_chain_fills_object_and_source(self):
        self.assertEqual(
            filled("①：墓地から「SPYRAL－ダンディ」１体を選んで特殊召喚する。"),
            [("選ぶ", "「SPYRAL－ダンディ」1体", "墓地", None, None),
             ("特殊召喚", "「SPYRAL－ダンディ」1体", "墓地", None, ["object", "source"])])

    def test_ka_group_members_are_all_filled(self):
        self.assertEqual(
            filled(SPRIGGANS)[1:],
            [("選ぶ", "以下のモンスターの内1体", "デッキ", None, None),
             ("加える", "以下のモンスターの内1体", "デッキ", "手札", ["object", "source"]),
             ("特殊召喚", "以下のモンスターの内1体", "デッキ", None, ["object", "source"])])

    def test_ka_group_without_select_fills_from_the_first_member(self):
        self.assertEqual(
            filled("①：デッキからモンスター１体を手札に加えるか特殊召喚する。"),
            [("加える", "モンスター1体", "デッキ", "手札", None),
             ("特殊召喚", "モンスター1体", "デッキ", None, ["object", "source"])])

    def test_chain_fills_every_lacking_predicate_until_the_period(self):
        self.assertEqual(
            filled("①：手札からカード１枚を選んで墓地へ送り、除外する。自分は１枚ドローする。"),
            [("選ぶ", "カード1枚", "手札", None, None),
             ("送る", "カード1枚", "手札", "墓地", ["object", "source"]),
             ("除外", "カード1枚", "手札", None, ["object", "source"]),
             ("ドロー", None, None, None, None)])

    def test_predicate_with_its_own_object_stops_the_chain(self):
        self.assertEqual(
            filled("①：デッキからモンスター１体を選んで特殊召喚し、相手フィールドのカード"
                   "１枚を破壊し、墓地へ送る。"),
            [("選ぶ", "モンスター1体", "デッキ", None, None),
             ("特殊召喚", "モンスター1体", "デッキ", None, ["object", "source"]),
             ("破壊", "カード1枚", None, None, None),
             ("送る", None, None, "墓地", None)])

    def test_predicate_with_a_topic_stops_the_chain(self):
        self.assertEqual(
            filled("①：デッキからモンスター１体を選んで特殊召喚し、そのモンスターの攻撃力は"
                   "５００アップする。"),
            [("選ぶ", "モンスター1体", "デッキ", None, None),
             ("特殊召喚", "モンスター1体", "デッキ", None, ["object", "source"]),
             ("アップ", None, None, None, None)])
        self.assertEqual(
            filled("①：デッキからカード１枚を選んで相手に見せ、相手はその中から１枚選ぶ。"),
            [("選ぶ", "カード1枚", "デッキ", None, None),
             ("見せる", "カード1枚", None, "相手", ["object", "place"]),
             ("選ぶ", None, "その中", None, None)])

    def test_intransitive_action_is_not_filled(self):
        self.assertEqual(
            filled("①：デッキからカード１枚を選んで墓地へ送り、１枚ドローする。"),
            [("選ぶ", "カード1枚", "デッキ", None, None),
             ("送る", "カード1枚", "デッキ", "墓地", ["object", "source"]),
             ("ドロー", None, None, None, None)])

    def test_backfill_lists_only_the_filled_fields(self):
        self.assertEqual(
            filled("①：自分の墓地のモンスター１体を選んで特殊召喚する。"),
            [("選ぶ", "モンスター1体", None, None, None),
             ("特殊召喚", "モンスター1体", "自分の墓地", None, ["object", "source"])])
        self.assertEqual(
            filled("①：デッキからモンスター１体を選び、墓地から特殊召喚する。"),
            [("選ぶ", "モンスター1体", "デッキ", None, None),
             ("特殊召喚", "モンスター1体", "墓地", None, ["object"])])


def topics(text, context=""):
    """動作框架 → (動作, 主題, 主語, 對象, 態):frame-args-v3 票 02;被動旗標 2026-10-27 起是
    態=受身(frame-lemma-unify 票 01),態空是 None。"""
    return [(f["action"], f.get("topic"), f.get("subject"), f.get("object"),
             f.get("voice")) for f in actions(text, context)]


class TestTopicAndSubject(unittest.TestCase):
    """frame-args-v3 票 02:子句內「は」前的片語記主題、「が」前的片語記主語,同一子句有多個時
    取離述語最近的;被動句的受事者留在主題/主語、不搬進對象,框架的態是 受身。"""

    def test_topic_and_subject_of_naru(self):
        self.assertEqual(
            topics("①：相手フィールドの全ての表側表示モンスターは、守備力が０になる。"),
            [("にする", "相手フィールドの全ての表側表示モンスター", "守備力", None, "自動")])

    def test_topic_with_relative_ga_has_no_subject(self):
        """自分が受ける 是定語,屬名詞片語;整段是主題、沒有主語。"""
        self.assertEqual(
            topics("①：自分が受ける効果ダメージは０になる。"),
            [("にする", "自分が受ける効果ダメージ", None, None, "自動")])

    def test_actor_topic(self):
        self.assertEqual(
            topics("①：自分は手札を１枚捨てる。"),
            [("捨てる", "自分", None, "手札", None)])

    def test_passive_patient_stays_in_topic(self):
        """このカードは…破壊されない:受事者留在主題、對象空著;では 併入前一格,不算主題。"""
        self.assertEqual(
            topics("①：このカードは戦闘では破壊されない。"),
            [("破壊", "このカード", None, None, "受身")])

    def test_passive_patient_stays_in_subject(self):
        self.assertEqual(
            topics("①：このカードが墓地へ送られた場合に発動できる。デッキからカード１枚を"
                   "手札に加える。"),
            [("送る", None, "このカード", None, "受身"),
             ("加える", None, None, "カード1枚", None)])

    def test_relative_ga_is_not_a_subject(self):
        self.assertEqual(
            topics("①：「X」のカード名が記されたモンスター１体を特殊召喚する。"),
            [("特殊召喚", None, None, "「X」のカード名が記されたモンスター1体", None)])

    def test_ni_wa_is_not_a_topic(self):
        """には 的 は 是後綴,併入 に 格(目的),不出主題。"""
        self.assertEqual(
            topics("①：相手フィールドにはモンスターを特殊召喚できない。"),
            [("特殊召喚", None, None, "モンスター", None)])

    def test_nearest_subject_wins(self):
        """同一子句有多個 が:取離述語最近的。"""
        self.assertEqual(
            topics("①：自分フィールドに「X」が存在し、このカードが戦闘で破壊された場合に"
                   "発動できる。このカードを特殊召喚する。")[:2],
            [("存在", None, "「X」", None, None), ("破壊", None, "このカード", None, "受身")])


def carried(text, context=""):
    """動作框架 → (動作, 主題, 主語, 回填):frame-args-v3 票 03。"""
    return [(f["action"], f.get("topic"), f.get("subject"), f.get("backfill"))
            for f in actions(text, context)]


class TestTopicCarryOver(unittest.TestCase):
    """frame-args-v3 票 03:子句沒有自己的主題時沿用同一句內前一個主題(回填欄記 topic),
    到句號、新的主題、或自己帶 が/は 的條件子句為止;主語不延續。"""

    def test_topic_carries_to_the_next_clause(self):
        self.assertEqual(
            carried("①：自分は手札を１枚捨て、デッキから１枚ドローする。"),
            [("捨てる", "自分", None, None), ("ドロー", "自分", None, ["topic"])])

    def test_period_stops_the_carry(self):
        self.assertEqual(
            carried("①：自分は手札を１枚捨てる。その後、デッキから１枚ドローする。"),
            [("捨てる", "自分", None, None), ("ドロー", None, None, None)])

    def test_new_topic_stops_the_carry(self):
        self.assertEqual(
            carried("①：自分は手札を１枚捨て、相手はデッキから１枚ドローし、"
                    "手札を１枚選んで墓地へ送る。"),
            [("捨てる", "自分", None, None), ("ドロー", "相手", None, None),
             ("選ぶ", "相手", None, ["topic"]), ("送る", "相手", None, ["topic", "object", "source"])])

    def test_conditional_clause_with_its_own_subject_blocks_the_carry(self):
        """このカードは、相手モンスターが攻撃した場合、…:句首主題屬主句,不給有自己主語的
        條件子句;主句接過主題(回填)。"""
        self.assertEqual(
            carried("①：このカードは、相手モンスターが攻撃した場合、攻撃できない。"),
            [("攻撃", None, "相手モンスター", None),
             ("攻撃", "このカード", None, ["topic"])])
        self.assertEqual(
            carried("①：自分は手札を１枚捨て、相手フィールドにモンスターが存在する場合、"
                    "デッキから１枚ドローする。"),
            [("捨てる", "自分", None, None), ("存在", None, "モンスター", None),
             ("ドロー", None, None, None)])

    def test_attribute_topic_carries_its_owner(self):
        """「Xの攻撃力は…アップし、…破壊されない」:延續給下一子句的是 X,不是 X の攻撃力。"""
        self.assertEqual(
            carried("①：装備モンスターの攻撃力は３００アップし、効果では破壊されない。"),
            [("アップ", "装備モンスターの攻撃力", None, None),
             ("破壊", "装備モンスター", None, ["topic"])])
        self.assertEqual(
            carried("②：この効果で特殊召喚したモンスターの効果は無効化され、エンドフェイズに"
                    "破壊される。"),
            [("無効にする", "この効果で特殊召喚したモンスターの効果", None, None),
             ("破壊", "この効果で特殊召喚したモンスター", None, ["topic"])])

    def test_bare_attribute_topic_keeps_the_carried_owner(self):
        """「Xの攻撃力・守備力は０になり、効果は無効化され、…素材にできない」:光禿禿的屬性主題
        (効果は)是 X 的屬性,不換掉延續中的 X;它自己的主題補成「Xの効果」(標回填)。"""
        self.assertEqual(
            carried("①：この効果で特殊召喚したモンスターの攻撃力・守備力は０になり、"
                    "効果は無効化され、S・X召喚の素材にできない。"),
            [("にする", "この効果で特殊召喚したモンスターの攻撃力・守備力", None, None),
             ("無効にする", "この効果で特殊召喚したモンスターの効果", None, ["topic"]),
             ("S素材にする", "この効果で特殊召喚したモンスター", None, ["topic"]),
             ("X素材にする", "この効果で特殊召喚したモンスター", None, ["topic"])])

    def test_completed_attribute_topic_keeps_its_own_voice(self):
        """「装備モンスターは…、攻撃力は１０００ダウンする」:補了主人的屬性主題原文有主題,
        ダウン 照舊記 自動(延續來的主題才不算)。"""
        frame = actions("①：装備モンスターは戦闘では破壊されず、攻撃力は１０００ダウンする。")[-1]
        self.assertEqual((frame["action"], frame["topic"], frame["backfill"], frame.get("voice")),
                         ("ダウン", "装備モンスターの攻撃力", ["topic"], "自動"))
        self.assertNotIn("topic_literal", frame)

    def test_subject_does_not_carry(self):
        self.assertEqual(
            carried("①：相手フィールドの全ての表側表示モンスターは、守備力が０になり、"
                    "その効果は無効化される。"),
            [("にする", "相手フィールドの全ての表側表示モンスター", "守備力", None),
             ("無効にする", "その効果", None, None)])
        self.assertEqual(
            carried("①：このカードが戦闘で破壊され、墓地へ送られた時に発動できる。"
                    "相手に５００ダメージを与える。")[:2],
            [("破壊", None, "このカード", None), ("送る", None, None, None)])


def placed(text, context=""):
    """動作框架 → (動作, 主題, 主語, 對象, 來源, 所在):frame-args-v3 票 04。"""
    return [(f["action"], f.get("topic"), f.get("subject"), f.get("object"),
             f.get("source"), f.get("place")) for f in actions(text, context)]


class TestPatientPlaceSplit(unittest.TestCase):
    """frame-args-v3 票 04:受事者(主動句是對象;被動句是主語,沒有時是主題)片語裡的第一段
    「(玩家の)區域の」切出——移動類動作記來源、其餘記所在;開頭或中間都切,並列的受事者
    各帶區域時取聯集;原文有 から 來源時不切;主動句執行者的主題不切。"""

    def test_zone_of_a_moved_card_is_the_source(self):
        self.assertEqual(
            placed("①：墓地のこのカードを除外する。"),
            [("除外", None, None, "このカード", "墓地", None)])

    def test_zone_of_a_destroyed_card_is_the_place(self):
        self.assertEqual(
            placed("①：相手フィールドのカード１枚を破壊する。"),
            [("破壊", None, None, "カード1枚", None, "相手フィールド")])

    def test_target_zone_is_the_place(self):
        self.assertEqual(
            placed("①：自分フィールドの表側表示モンスター１体を対象として発動できる。"
                   "そのモンスターの攻撃力は５００アップする。")[0],
            ("対象とする", None, None, "表側表示モンスター1体", None, "自分フィールド"))

    def test_player_prefix_goes_with_the_zone(self):
        self.assertEqual(
            placed("①：自分の墓地の機械族モンスター１体を特殊召喚する。"),
            [("特殊召喚", None, None, "機械族モンスター1体", "自分の墓地", None)])
        self.assertEqual(
            placed("①：自分か相手の墓地のカード１枚を除外する。"),
            [("除外", None, None, "カード1枚", "自分か相手の墓地", None)])

    def test_zone_in_the_middle_is_cut(self):
        self.assertEqual(
            placed("①：対象のモンスター以外の自分フィールドの表側表示モンスター１体を除外する。"),
            [("除外", None, None, "対象のモンスター以外の表側表示モンスター1体",
              "自分フィールド", None)])

    def test_coordinated_patients_union_their_zones(self):
        self.assertEqual(
            placed("①：自分の墓地のモンスター１体と相手フィールドの表側表示モンスター１体を"
                   "除外する。"),
            [("除外", None, None, "モンスター1体と表側表示モンスター1体",
              "自分の墓地・相手フィールド", None)])

    def test_compound_zone_and_deck_position(self):
        self.assertEqual(
            placed("①：お互いのフィールド・墓地のカードを全て除外する。"),
            [("除外", None, None, "カード", "お互いのフィールド・墓地", None)])
        self.assertEqual(
            placed("①：デッキの一番上のカードを墓地へ送る。"),
            [("送る", None, None, "カード", "デッキの一番上", None)])

    def test_banished_state_zone(self):
        self.assertEqual(
            placed("①：除外されている自分のモンスター１体を対象として発動できる。"
                   "そのモンスターを特殊召喚する。")[0],
            ("対象とする", None, None, "モンスター1体", None, "除外されている自分"))
        self.assertEqual(
            placed("①：除外されているこのカードを特殊召喚する。"),
            [("特殊召喚", None, None, "このカード", "除外されている", None)])

    def test_zone_verb_inside_a_relative_clause_is_not_cut(self):
        """「この効果で除外されているカード」「この効果で除外したモンスター」:區域詞是定語子句的
        述語(前面接助詞),切了會留下殘缺的對象,不切。"""
        self.assertEqual(
            placed("①：この効果で除外されているカードを手札に加える。"),
            [("加える", None, None, "この効果で除外されているカード", None, None)])
        self.assertEqual(
            placed("①：この効果で除外したモンスターを特殊召喚する。"),
            [("特殊召喚", None, None, "この効果で除外したモンスター", None, None)])

    def test_player_coordinated_with_a_player_zone(self):
        """自分または相手フィールド、自分・相手フィールド(自分(フィールド) 是省略寫法)是一段區域。"""
        self.assertEqual(
            placed("①：自分または相手フィールドのモンスター１体をリリースする。"),
            [("リリース", None, None, "モンスター1体", "自分または相手フィールド", None)])
        self.assertEqual(
            placed("①：自分・相手フィールドの攻撃表示モンスター１体をリリースする。"),
            [("リリース", None, None, "攻撃表示モンスター1体", "自分(フィールド)・相手フィールド",
              None)])

    def test_positional_qualifier_stays_with_the_zone(self):
        """自分の中央のメインモンスターゾーン:玩家與位置限定語跟著區域切。"""
        self.assertEqual(
            placed("①：自分の中央のメインモンスターゾーンのモンスター１体を破壊する。"),
            [("破壊", None, None, "モンスター1体", None, "自分の中央のメインモンスターゾーン")])

    def test_zone_inside_a_relative_clause_is_not_the_patients(self):
        """「自分の墓地の…と同じとなる相手フィールドのモンスター」:と 是比較(と同じ)不是並列,
        定語子句裡的區域不是受事者的;受事者的區域是定語之後那一段。"""
        frame = actions("●種族か属性が、自分の墓地の通常モンスターのいずれかと同じとなる"
                        "相手フィールドのモンスター１体を除外する。")[-1]
        self.assertEqual((frame["action"], frame["source"]), ("除外", "相手フィールド"))
        self.assertIn("自分の墓地の通常モンスター", frame["object"])

    def test_zone_after_a_relative_clause_keeps_its_player(self):
        """定語動詞後的「自分の墓地の」:玩家跟著區域一起切。"""
        self.assertEqual(
            placed("①：「X」モンスターを含む自分の墓地のモンスターを除外する。"),
            [("除外", None, None, "「X」モンスターを含むモンスター", "自分の墓地", None)])

    def test_two_token_and_parenthesised_zones(self):
        """除外状態(兩個詞)、フィールド（表側表示）、その墓地 也是區域。"""
        self.assertEqual(
            placed("①：自分の手札・除外状態の「御巫」モンスター１体を特殊召喚する。"),
            [("特殊召喚", None, None, "「御巫」モンスター1体", "自分の手札・除外状態", None)])
        self.assertEqual(
            placed("①：このカード以外の自分の手札・フィールド（表側表示）の「真竜」カード１枚を"
                   "破壊する。"),
            [("破壊", None, None, "このカード以外の「真竜」カード1枚", None,
              "自分の手札・フィールド（表側表示）")])
        self.assertEqual(
            placed("①：その墓地のモンスター１体を特殊召喚する。"),
            [("特殊召喚", None, None, "モンスター1体", "その墓地", None)])

    def test_object_carried_past_another_wo_is_cut(self):
        """「Xを効果を無効にして特殊召喚」:X 留給 特殊召喚,它的區域照切。"""
        self.assertEqual(
            placed("①：自分の墓地のモンスター１体を効果を無効にして特殊召喚する。"),
            [("無効にする", None, None, "効果", None, None),
             ("特殊召喚", None, None, "モンスター1体", "自分の墓地", None)])

    def test_zone_in_a_count_is_not_cut(self):
        """區域修飾的是數量(墓地のモンスターの数×100ダメージ):受事者不在那裡,不切。"""
        self.assertEqual(
            placed("①：自分の墓地のモンスターの数×１００ダメージを相手に与える。"),
            [("与える", None, None, "自分の墓地のモンスターの数×100ダメージ", None, None)])

    def test_explicit_source_is_not_overwritten(self):
        """原文用 から 寫了來源:對象欄不切。"""
        self.assertEqual(
            placed("①：デッキから自分フィールドのモンスターと同じ種族のモンスター１体を"
                   "手札に加える。"),
            [("加える", None, None, "自分フィールドのモンスターと同じ種族のモンスター1体",
              "デッキ", None)])

    def test_actor_topic_is_not_cut(self):
        """主動句的主題是執行者,不切;受事者(對象)照切。"""
        self.assertEqual(
            placed("①：自分フィールドの「X」モンスターは、相手フィールドの守備表示モンスターを"
                   "攻撃できる。"),
            [("攻撃", "自分フィールドの「X」モンスター", None, "守備表示モンスター", None,
              "相手フィールド")])

    def test_passive_patient_is_cut_from_subject_or_topic(self):
        self.assertEqual(
            placed("①：墓地のこのカードが除外された場合に発動できる。デッキからカード１枚を"
                   "手札に加える。")[0],
            ("除外", None, "このカード", None, "墓地", None))
        self.assertEqual(
            placed("①：自分フィールドのモンスターは効果では破壊されない。"),
            [("破壊", "モンスター", None, None, None, "自分フィールド")])

    def test_whole_phrase_is_a_zone(self):
        """整個受事者就是區域:區域記進來源/所在,受事者欄維持原文。"""
        self.assertEqual(
            placed("①：手札を１枚捨てる。")[0][3:5],
            ("手札", "手札"))
        self.assertEqual(
            placed("①：相手のEXデッキを確認する。"),
            [("確認", None, None, "相手のEXデッキ", None, "相手のEXデッキ")])
        self.assertEqual(
            placed("①：このカード以外の手札を１枚捨てる。")[0][3:5],
            ("このカード以外の手札", "手札"))
        self.assertEqual(
            placed("●お互いは自身の手札を全てデッキに戻す。")[0][3:5],
            ("自身の手札", "自身の手札"))

    def test_material_zone_is_the_place(self):
        """素材類不算移動類(規格決定 2026-10-17):區域記所在。"""
        self.assertEqual(
            placed("①：自分の手札・フィールドのモンスターを融合素材とする。"),
            [("融合素材とする", None, None, "モンスター", None, "自分の手札・フィールド")])


def inferred(text, context=""):
    """動作框架 → (動作, 來源, 目的, 推得):frame-args-v3 票 05。"""
    return [(f["action"], f.get("source"), f.get("goal"), f.get("inferred"))
            for f in actions(text, context)]


class TestInferredValues(unittest.TestCase):
    """frame-args-v3 票 05:目的(與 捨てる、ドロー 的來源)由動作唯一決定、原文沒寫時補上並標
    推得——除外→除外;捨てる→墓地(來源 手札);ドロー→手札(來源 デッキ);特殊召喚與各召喚法、
    セット→フィールド;加える→手札。装備、リリース、破壊 不補;原文有字面時用原文。"""

    def test_banish_goal(self):
        self.assertEqual(
            inferred("①：墓地のこのカードを除外する。"),
            [("除外", "墓地", "除外", ["goal"])])

    def test_discard_goal_and_source(self):
        self.assertEqual(
            inferred("①：「X」１枚を捨てる。"),
            [("捨てる", "手札", "墓地", ["source", "goal"])])
        # 受事者整段就是區域(手札を):來源是原文切出的,不標推得
        self.assertEqual(
            inferred("①：手札を１枚捨てる。"),
            [("捨てる", "手札", "墓地", ["goal"])])

    def test_draw_keeps_a_written_source(self):
        self.assertEqual(
            inferred("①：デッキから１枚ドローする。"),
            [("ドロー", "デッキ", "手札", ["goal"])])
        self.assertEqual(
            inferred("①：自分は１枚ドローする。"),
            [("ドロー", "デッキ", "手札", ["source", "goal"])])

    def test_summon_goal_unless_written(self):
        self.assertEqual(
            inferred("①：自分の墓地のモンスター１体を特殊召喚する。"),
            [("特殊召喚", "自分の墓地", "フィールド", ["goal"])])
        self.assertEqual(
            inferred("①：自分の墓地のモンスター１体を相手フィールドに特殊召喚する。"),
            [("特殊召喚", "自分の墓地", "相手フィールド", None)])
        self.assertEqual(
            inferred("①：このカードをアドバンス召喚する。"),
            [("A召喚", None, "フィールド", ["goal"])])

    def test_set_and_add_goal(self):
        self.assertEqual(
            inferred("①：デッキから「X」１枚をセットする。"),
            [("セット", "デッキ", "フィールド", ["goal"])])

    def test_equip_release_destroy_are_not_inferred(self):
        self.assertEqual(
            inferred("①：このカードを装備カード扱いとして装備する。")[-1],
            ("装備", None, None, None))
        self.assertEqual(
            inferred("①：自分フィールドのモンスター１体をリリースし、"
                     "相手フィールドのカード１枚を破壊する。"),
            [("リリース", "自分フィールド", None, None), ("破壊", None, None, None)])

    def test_negated_frames_are_inferred_too(self):
        self.assertEqual(
            inferred("①：相手は墓地のカードを除外できない。"),
            [("除外", "墓地", "除外", ["goal"])])

    def test_condition_frame_is_inferred(self):
        self.assertEqual(
            inferred("①：墓地のこのカードが除外された場合に発動できる。デッキからカード１枚を"
                     "手札に加える。"),
            [("除外", "墓地", "除外", ["goal"]), ("加える", "デッキ", "手札", None)])


def converted(text, context=""):
    """動作框架 → (動作, 對象, 來源, 所在, 回填, 推得):frame-args-v3 票 06。"""
    return [(f["action"], f.get("object"), f.get("source"), f.get("place"), f.get("backfill"),
             f.get("inferred")) for f in actions(text, context)]


class TestBackfillPlaceConversion(unittest.TestCase):
    """frame-args-v3 票 06:回填(か 群組、選ぶ鏈)把上游的區域交給下游時,依下游動作是不是移動類
    放進來源或所在;下游原文自己有來源或所在時不填;回填接到的區域蓋過推得的同欄;對象照舊
    原字面接過。"""

    def test_place_of_select_becomes_source_of_summon(self):
        self.assertEqual(
            converted("①：墓地のモンスター１体を選んで特殊召喚する。"),
            [("選ぶ", "モンスター1体", None, "墓地", None, None),
             ("特殊召喚", "モンスター1体", "墓地", None, ["object", "source"], ["goal"])])

    def test_region_handed_to_a_non_moving_action_is_a_place(self):
        self.assertEqual(
            converted("①：相手フィールドのカード１枚を選んで破壊する。"),
            [("選ぶ", "カード1枚", None, "相手フィールド", None, None),
             ("破壊", "カード1枚", None, "相手フィールド", ["object", "place"], None)])
        self.assertEqual(
            converted("①：手札からカード１枚を選んで破壊する。"),
            [("選ぶ", "カード1枚", "手札", None, None, None),
             ("破壊", "カード1枚", None, "手札", ["object", "place"], None)])

    def test_ka_group_converts_the_region(self):
        self.assertEqual(
            converted("①：自分の墓地のモンスター１体を手札に加えるか特殊召喚する。"),
            [("加える", "モンスター1体", "自分の墓地", None, None, None),
             ("特殊召喚", "モンスター1体", "自分の墓地", None, ["object", "source"], ["goal"])])
        self.assertEqual(
            converted("①：フィールドのカード１枚を破壊するか除外する。"),
            [("破壊", "カード1枚", None, "フィールド", None, None),
             ("除外", "カード1枚", "フィールド", None, ["object", "source"], ["goal"])])

    def test_own_place_is_not_overwritten(self):
        self.assertEqual(
            converted("①：デッキからモンスター１体を選び、墓地から特殊召喚する。")[1],
            ("特殊召喚", "モンスター1体", "墓地", None, ["object"], ["goal"]))

    def test_carried_topic_of_a_passive_frame_is_cut(self):
        """延續來的主題落在被動框架(受事者就是主題):區域照切,主題與所在都標回填。"""
        self.assertEqual(
            [(f["action"], f.get("topic"), f.get("place"), f.get("backfill"))
             for f in actions("①：自分フィールドの「X」モンスターの攻撃力は５００アップし、"
                              "相手の効果では破壊されない。")],
            [("アップ", "自分フィールドの「X」モンスターの攻撃力", None, None),
             ("破壊", "「X」モンスター", "自分フィールド", ["topic", "place"])])

    def test_backfilled_region_wins_over_inferred(self):
        """選んで捨てる:上游的區域(その中)蓋過 捨てる 推得的來源 手札。"""
        self.assertEqual(
            converted("①：デッキからカードを３枚めくり、その中からカード１枚を選んで捨てる。")[1:],
            [("選ぶ", "カード1枚", "その中", None, None, None),
             ("捨てる", "カード1枚", "その中", None, ["object", "source"], ["goal"])])


class TestV3Round1Fixes(unittest.TestCase):
    """frame-args-v3 票 07:v3-round1 回報的同型錯誤,先補例子再修。"""

    def test_attribute_ga_in_a_noun_phrase_is_not_a_subject(self):
        """「攻撃力か守備力が２０００の…モンスター」「属性が…と同じ…モンスター」的 が 屬名詞片語,
        併回對象、不出主語;「攻撃力が超えた分」的 が 是定語子句的,不出主語。"""
        self.assertEqual(
            topics("①：攻撃力か守備力が２０００の通常召喚できないモンスター１体を特殊召喚する。"),
            [("特殊召喚", None, None, "攻撃力か守備力が2000の通常召喚できないモンスター1体",
              None)])
        frame = actions("①：属性がこの効果で特殊召喚したモンスターと同じ相手フィールドのモンスター"
                        "１体を墓地へ送る。")[0]
        self.assertEqual((frame.get("subject"), frame["object"], frame["source"]),
                         (None, "属性がこの効果で特殊召喚したモンスターと同じモンスター1体",
                          "相手フィールド"))
        self.assertEqual(
            topics("①：その守備力を攻撃力が超えた分だけ戦闘ダメージを与える。"),
            [("与える", None, None, "戦闘ダメージ", None)])

    def test_attribute_ga_inside_a_subject(self):
        """v3-round2:「攻撃力か守備力が２０００のモンスターが存在する場合」:屬性 が 併進主語片語。"""
        self.assertEqual(
            topics("①：自分フィールドに攻撃力か守備力が２０００のモンスターが存在する場合に"
                   "発動できる。このカードを特殊召喚する。")[0][:3],
            ("存在", None, "攻撃力か守備力が2000のモンスター"))

    def test_subject_of_an_unanchored_clause_is_not_taken(self):
        """「自分のLPが相手より３０００以上少なく、このカードが…」:主語只取最後一個讀點之後;
        「自分のLPが相手より少ない場合、…を対象として」的 自分のLP 屬條件子句,不給 対象とする。"""
        self.assertEqual(
            topics("①：自分のLPが相手より３０００以上少なく、このカードがX召喚に成功した場合に"
                   "発動できる。このカードを破壊する。")[0][:3],
            ("成功", None, "このカード"))
        self.assertEqual(
            topics("①：自分のLPが相手より少ない場合、自分フィールドのモンスター１体を対象として"
                   "発動できる。そのモンスターを破壊する。")[0][:3],
            ("対象とする", None, None))

    def test_subject_of_an_adjunct_clause_moves_to_its_predicate(self):
        """「このカードが「X」を素材としてL召喚された場合」「…Sモンスターが自身の効果を発動する
        ためにリリースされた場合」:主語屬後面的述語,前面的附加子句(として/ために)不帶。"""
        self.assertEqual(
            [(f["action"], f.get("subject"), f.get("backfill"))
             for f in actions("①：このカードが「X」を素材としてL召喚された場合に発動できる。"
                              "デッキからカード１枚を手札に加える。")][:2],
            [("素材とする", None, None), ("L召喚", "このカード", ["subject"])])
        frame = actions("①：自分フィールドの「スターダスト」Sモンスターが自身の効果を発動するために"
                        "リリースされた場合に発動できる。このカードを特殊召喚する。")[0]
        self.assertEqual((frame["action"], frame.get("subject"), frame.get("source")),
                         ("リリース", "「スターダスト」Sモンスター", "自分フィールド"))

    def test_material_object_goes_to_the_banish(self):
        """「自分の墓地のモンスターを融合素材として除外し」:被除外的就是素材。"""
        self.assertEqual(
            converted("①：自分の墓地のモンスターを融合素材として除外し、融合モンスター１体を"
                      "EXデッキから融合召喚する。")[:2],
            [("融合素材とする", "モンスター", None, "自分の墓地", None, None),
             ("除外", "モンスター", "自分の墓地", None, ["object", "source"], ["goal"])])

    def test_link_summon_short_name_is_inferred(self):
        self.assertEqual(
            inferred("①：このカードがL召喚した場合に発動できる。デッキからカード１枚を手札に"
                     "加える。")[0],
            ("L召喚", None, "フィールド", ["goal"]))

    def test_zone_with_a_quantity_is_the_whole_patient(self):
        self.assertEqual(
            placed("①：手札を１枚相手に見せる。"),
            [("見せる", None, None, "手札1枚", None, "手札")])

    def test_intransitive_move_cuts_its_subject(self):
        """戻る 是移動類的自動詞:移動的卡是主語,區域照切成來源。"""
        self.assertEqual(
            placed("①：自分フィールドのモンスターがデッキに戻った場合に発動できる。"
                   "デッキからカード１枚を手札に加える。")[0],
            ("戻す", None, "モンスター", None, "自分フィールド", None))

    def test_card_name_topic_carries_as_is(self):
        """「このカードのカード名は…」延續下去的仍是 このカードのカード名(カード名 不算屬性)。"""
        self.assertEqual(
            carried("①：このカードのカード名は「X」として扱い、「Y」としても扱う。")[1],
            ("扱う", "このカードのカード名", None, ["topic"]))


def merged_clauses(text, context=""):
    """動作框架 → (動作, 主題, 主語, 對象, 來源, 回填, 子句字面去空白):frame-args-v3 票 09。
    子句字面一般不斷言,這裡是票 09 的驗收條件(後面述語的子句含 〜よう 的字面)。"""
    return [(f["action"], f.get("topic"), f.get("subject"), f.get("object"),
             literal(f, "source"), f.get("backfill"), f["clause"].replace(" ", ""))
            for f in actions(text, context)]


class TestYouNiClauseMerged(unittest.TestCase):
    """frame-args-v3 票 09:以 よう/ように 收尾的子句是後面述語的連用修飾——不出動作框架,字面
    併入後面述語的子句;量條件(よう 子句的主語、目的)不結構化,其餘論元(對象、來源、主題)
    屬後面的述語。"""

    def test_ritual_release_takes_the_you_clause(self):
        self.assertEqual(
            merged_clauses("②：このカードのX素材を１つ取り除いて発動できる。レベルの合計が"
                           "儀式召喚するモンスターのレベル以上になるように、自分の手札・"
                           "フィールドのモンスターをリリースし、手札から儀式モンスター１体を"
                           "儀式召喚する。")[1:3],
            [("リリース", None, None, "モンスター", "自分の手札・フィールド", None,
              "レベルの合計が儀式召喚するモンスターのレベル以上になるように、"
              "自分の手札・フィールドのモンスターをリリースし"),
             ("儀式召喚", None, None, "儀式モンスター1体", "手札", None,
              "手札から儀式モンスター1体を儀式召喚する")])

    def test_conditional_you_clause_has_no_frame_either(self):
        """條件位(發動句的代價前)的「〜になるよう」同樣不出。"""
        self.assertEqual(
            [f[0] for f in merged_clauses("①：このカードが手札に存在する場合、リンクマーカーの合計が"
                                          "５になるようにEXデッキから機械族Lモンスターを除外して"
                                          "発動できる。このカードを特殊召喚する。")],
            ["存在", "除外", "特殊召喚"])

    def test_topic_and_object_of_the_you_clause_belong_to_the_predicate(self):
        """「自分は手札が５枚になるようにドローする」:主題 自分 是 ドロー 自己子句的字(不標回填);
        「そのモンスターを…となるように特殊召喚する」:對象屬 特殊召喚。"""
        self.assertEqual(
            merged_clauses("②：自分は手札が５枚になるようにデッキからドローする。"),
            [("ドロー", "自分", None, None, "デッキ", None,
              "自分は手札が5枚になるようにデッキからドローする")])
        self.assertEqual(
            merged_clauses("②：そのモンスターをこのカードとリンク状態となるように"
                           "自分フィールドに特殊召喚する。")[0][:5],
            ("特殊召喚", None, None, "そのモンスター", None))

    def test_subject_moved_into_the_you_clause_stays_there(self):
        """「攻撃力の合計が、…発動するために払ったLPの数値以下になるように…選んで」:ために 移過來的
        主語是 よう 子句的量條件,不往後給 選ぶ。"""
        self.assertEqual(
            merged_clauses("②：その差分のLPを払ってこの効果を発動できる。攻撃力の合計が、"
                           "この効果を発動するために払ったLPの数値以下になるように、"
                           "相手フィールドの表側表示モンスターを選んで破壊する。")[1][:4],
            ("選ぶ", None, None, "表側表示モンスター"))

    def test_you_without_a_following_predicate_is_kept(self):
        """反例:よう 之後同一句沒有述語時不受影響;名詞後的「同じように」本來就不是錨點。"""
        self.assertEqual(
            [f[:3] for f in merged_clauses("①：レベルの合計が８になるように。")],
            [("にする", None, "レベルの合計")])
        self.assertEqual(
            [f[0] for f in merged_clauses("①：このカードは通常召喚と同じように扱う。")],
            ["扱う"])


def voiced(text, context=""):
    """動作框架 → (動作, 態, 極性):frame-lemma-unify 的詞元與態;態空是 None。"""
    return [(f["action"], f.get("voice"), f["polarity"]) for f in actions(text, context)]


def complements(text, context=""):
    """動作框架 → (動作, 態, 目的, 對象, 主題):補語不併(frame-lemma-unify 票 05)。"""
    return [(f["action"], f.get("voice"), literal(f, "goal"), f.get("object"), f.get("topic"))
            for f in actions(text, context)]


class TestVoiceColumn(unittest.TestCase):
    """frame-lemma-unify 票 01:態欄取代被動旗標——述語錨點判出被動的框架態是 受身,沒判的是空。"""

    def test_passive_negation_is_passive_voice(self):
        self.assertEqual(voiced("①：このカードはリリースされない。"),
                         [("リリース", "受身", "否定")])

    def test_active_verb_outside_unified_groups_has_no_voice(self):
        """態空是「沒判」,不是他動:破壊 不在統一組。"""
        self.assertEqual(voiced("①：フィールドのカード１枚を破壊する。"),
                         [("破壊", None, "肯定")])

    def test_passive_flag_is_gone(self):
        frame = actions("①：ダメージステップ終了時までそのモンスターの効果は無効化される。")[0]
        self.assertEqual((frame["action"], frame.get("voice")), ("無効にする", "受身"))
        self.assertNotIn("passive", frame)


class TestSpellingUnified(unittest.TestCase):
    """frame-lemma-unify 票 02:縮寫與全名、分詞殘片是同一個詞元,以現行官方縮寫為名。"""

    def test_advance_summon_is_a_summon(self):
        self.assertEqual(
            extract("①：自分は通常召喚に加えて１度だけ、自分メインフェイズにレベル７以上の"
                    "モンスター１体を表側攻撃表示でアドバンス召喚できる。"),
            [("A召喚", "レベル7以上のモンスター1体", None, None, "效果", "可能")])

    def test_link_summon_in_condition(self):
        self.assertEqual(
            voiced("①：このカードがリンク召喚した場合に発動できる。デッキからカード１枚を"
                   "手札に加える。")[0], ("L召喚", None, "肯定"))
        self.assertEqual(
            actions("①：このカードがリンク召喚した場合に発動できる。デッキからカード１枚を"
                    "手札に加える。")[0]["position"], "條件")

    def test_link_material_as(self):
        """として 系:リンク素材として → L素材とする。"""
        self.assertEqual(
            [f[0] for f in voiced("③：このカードが「ティンダングル」リンクモンスターのリンク素材として"
                                  "墓地へ送られた場合に発動できる。")][:1],
            ["L素材とする"])

    def test_demonstrative_is_not_folded_into_material(self):
        """そのX素材とする:指示詞 その/この 不併入補語,詞元 X素材とする、對象不變。"""
        self.assertEqual(
            complements("①：このカードをそのX素材とする。"),
            [("X素材とする", "他動", None, "このカード", None)])
        self.assertEqual(
            complements("②：このカード及びこのカードの装備カードを全てそのX素材にする。"),
            [("X素材にする", "他動", None, "このカード及びこのカードの装備カード", None)])

    def test_coordinated_summons_each_normalized(self):
        """召喚法鏈的「・」並列各框架照樣對照。"""
        self.assertEqual(
            [f[0] for f in voiced("①：このカードがアドバンス召喚・リンク召喚した場合に発動できる。")],
            ["A召喚", "L召喚"])


class TestVoiceUnified(unittest.TestCase):
    """frame-lemma-unify 票 03:同一動作的他動/自動/受身是一個詞元、以他動形為名,差別記在態;
    受事者落在哪一欄不變(自動與受身在主語/主題、他動在對象)。"""

    def test_return_two_voices(self):
        self.assertEqual(topics("①：このカードは手札に戻る。"),
                         [("戻す", "このカード", None, None, "自動")])
        self.assertEqual(topics("①：このカードを手札に戻す。"),
                         [("戻す", None, None, "このカード", "他動")])

    def test_returned_subject_keeps_its_place_cut(self):
        """戻った 的受事者在主語,區域照舊從主語切出(移動類記來源)。"""
        frame = actions("②：自分フィールドの表側表示のスピリットモンスターが自分の手札に戻った場合"
                        "に発動できる。")[0]
        self.assertEqual((frame["action"], frame.get("voice"), frame.get("subject"),
                          literal(frame, "source")),
                         ("戻す", "自動", "表側表示のスピリットモンスター", "自分フィールド"))

    def test_up_voice_by_particle(self):
        self.assertEqual(voiced("①：このカードの攻撃力は３００アップする。"),
                         [("アップ", "自動", "肯定")])
        self.assertEqual(voiced("①：このカードの攻撃力を３００アップする。"),
                         [("アップ", "他動", "肯定")])

    def test_up_voice_unknown_stays_empty(self):
        """受事者既不是 を 也不是 は/が:態留空;延續來的主題(執行者 自分)不算受事者。"""
        self.assertEqual(voiced("①：３００アップする。"), [("アップ", None, "肯定")])
        self.assertEqual(
            voiced("①：自分は手札を１枚捨て、さらに３００アップする。")[1], ("アップ", None, "肯定"))

    def test_passive_of_a_unified_verb(self):
        """被統一組的受身形也是 受身(無効にされない),受事者留在主題。"""
        self.assertEqual(topics("①：このカードの効果は無効にされない。"),
                         [("無効にする", "このカードの効果", None, None, "受身")])

    def test_raise_and_rise_are_up(self):
        self.assertEqual(voiced("①：対象のモンスターのレベルを１つ上げる。"),
                         [("アップ", "他動", "肯定")])
        self.assertEqual(
            voiced("①：フィールドの「F.A.」モンスターのレベルはメインフェイズの間だけ２つ上がる。"),
            [("アップ", "自動", "肯定")])

    def test_lower_and_fall_are_down(self):
        self.assertEqual(voiced("①：このターン、お互いの手札のモンスターのレベルを１つ下げる。"),
                         [("ダウン", "他動", "肯定")])
        self.assertEqual(voiced("①：対象のモンスターのレベルは１つ下がる。"),
                         [("ダウン", "自動", "肯定")])

    def test_double_half_same(self):
        self.assertEqual(voiced("②：このカードの攻撃力はターン終了時まで倍になる。"),
                         [("倍にする", "自動", "肯定")])
        self.assertEqual(voiced("①：このカードの攻撃力を倍にする。"),
                         [("倍にする", "他動", "肯定")])
        self.assertEqual(voiced("①：相手が受ける戦闘ダメージは半分になる。"),
                         [("半分にする", "自動", "肯定")])
        self.assertEqual(
            complements("②：対象のモンスターの種族・属性はターン終了時まで、見せたモンスターと"
                        "同じになる。"),
            [("同じにする", "自動", "見せたモンスター", None, "対象のモンスターの種族・属性")])

    def test_bare_naru_is_nisuru(self):
        self.assertEqual(complements("①：自分が受ける効果ダメージは０になる。"),
                         [("にする", "自動", "0", None, "自分が受ける効果ダメージ")])
        self.assertEqual(complements("③：相手のLPを１００にする。"),
                         [("にする", "他動", "100", "相手のLP", None)])

    def test_negated_is_negate_passive(self):
        self.assertEqual(
            voiced("①：ダメージステップ終了時までそのモンスターの効果は無効化される。"),
            [("無効にする", "受身", "肯定")])
        self.assertEqual(voiced("①：このカードの発動と効果は無効化されない。"),
                         [("無効にする", "受身", "否定")])

    def test_other_folded_naru(self):
        self.assertEqual(
            voiced("①：フィールドのレベル１０以上のモンスターは効果の対象にならず、"
                   "効果では破壊されない。"),
            [("対象にする", "自動", "否定"), ("破壊", "受身", "否定")])
        self.assertEqual(
            voiced("②：このカードが融合召喚の素材となって墓地へ送られた場合に発動できる。"
                   "このカードを特殊召喚する。")[0],
            ("融合素材とする", "自動", "肯定"))


class TestFullActionNames(unittest.TestCase):
    """frame-lemma-unify 票 04:攻撃+宣言 一律 攻撃宣言、直接+攻撃 一律 直接攻撃。"""

    def test_attack_declaration_all_forms(self):
        self.assertEqual(voiced("①：このカードは攻撃宣言できない。"),
                         [("攻撃宣言", None, "否定")])
        self.assertEqual(
            voiced("②：この効果でコントロールを得たモンスターは、攻撃宣言できず、"
                   "リリースできない。")[0],
            ("攻撃宣言", None, "否定"))
        self.assertEqual(
            extract("③：このカードが相手モンスターに攻撃宣言した時に発動できる。"
                    "そのモンスターを破壊する。")[0],
            ("攻撃宣言", None, None, "相手モンスター", "條件", "肯定"))
        self.assertEqual(
            [f[:2] for f in voiced("①：相手モンスターの攻撃宣言時に発動できる。"
                                   "その攻撃を無効にする。")],
            [("攻撃宣言", None), ("無効にする", "他動")])

    def test_negative_conditional_before_attack_declaration(self):
        """「送らなければ攻撃宣言できない」:〜なければ 是條件形、自成框架,不是定語;
        攻撃宣言 不拿它的論元。"""
        self.assertEqual(
            extract("①：お互いのプレイヤーは手札を１枚墓地へ送らなければ攻撃宣言できない。"),
            [("送る", "手札1枚", "手札", "墓地", "條件", "否定"),
             ("攻撃宣言", None, None, None, "效果", "否定")])

    def test_card_name_declaration_stays(self):
        self.assertEqual(voiced("①：カード名を１つ宣言して発動できる。")[0][0], "宣言")

    def test_direct_attack(self):
        self.assertEqual(
            extract("①：このカードは相手プレイヤーに直接攻撃できる。"),
            [("直接攻撃", None, None, "相手プレイヤー", "效果", "可能")])
        self.assertEqual(voiced("①：このカードは直接攻撃できない。"),
                         [("直接攻撃", None, "否定")])

    def test_plain_attack_stays(self):
        self.assertEqual(voiced("①：このカードは相手モンスター全てに１回ずつ攻撃できる。"),
                         [("攻撃", None, "可能")])


class TestComplementNotFolded(unittest.TestCase):
    """frame-lemma-unify 票 05:補語收在封閉值域字面或屬性名詞時不併入詞元,整段留目的欄、詞元是
    にする/とする 形;狀態/角色詞照舊併。"""

    def test_attribute_values(self):
        self.assertEqual(complements("①：このカードは闇属性になる。"),
                         [("にする", "自動", "闇属性", None, "このカード")])
        self.assertEqual(
            complements("②：フィールドの全ての表側表示モンスターは、ターン終了時まで宣言した"
                        "属性になる。"),
            [("にする", "自動", "宣言した属性", None, "フィールドの全ての表側表示モンスター")])
        self.assertEqual(
            complements("②：墓地のこのカードはターン終了時までドラゴン族になる。"),
            [("にする", "自動", "ドラゴン族", None, "墓地のこのカード")])

    def test_battle_positions(self):
        self.assertEqual(complements("②：このカードを裏側守備表示にする。"),
                         [("にする", "他動", "裏側守備表示", "このカード", None)])
        self.assertEqual(
            complements("③：Ａカウンターが置かれている相手モンスターは、守備表示になる。"),
            [("にする", "自動", "守備表示", None, "〈Ａ〉カウンターが置かれている相手モンスター")])

    def test_quantifier_is_not_part_of_the_complement(self):
        """「…は全て守備表示になり」:全て 是主題的量化詞,不屬補語(lemma-round1)。"""
        self.assertEqual(
            complements("①：相手フィールドの表側攻撃表示モンスターは全て守備表示になる。")[0][:3],
            ("にする", "自動", "守備表示"))

    def test_attribute_nouns(self):
        self.assertTrue(
            complements("②：このカードの攻撃力は、リリースしたモンスターの元々の攻撃力・守備力を"
                        "それぞれ合計した数値になる。")[0][2].endswith("合計した数値"))
        self.assertEqual(
            complements("①：自分フィールドの全てのモンスターのレベルはターン終了時まで、"
                        "除外したモンスターと同じレベルになる。")[0][:3],
            ("にする", "自動", "除外したモンスターと同じレベル"))
        self.assertEqual(complements("①：このカードの守備力は元々の守備力になる。")[0][:3],
                         ("にする", "自動", "元々の守備力"))
        self.assertEqual(
            complements("①：相手が宣言したカード名はこの効果で宣言したカード名になる。")[0][:3],
            ("にする", "自動", "この効果で宣言したカード名"))

    def test_relative_complement_keeps_the_only_object(self):
        """「Xを宣言したレベルにする」:する 的補語裡的定語不吸收句裡唯一的 を——X 是對象。"""
        self.assertEqual(
            complements("②：そのモンスターのレベルを宣言したレベルにする。"),
            [("にする", "他動", "宣言したレベル", "そのモンスターのレベル", None)])
        self.assertEqual(
            complements("①：そのモンスターとこのカードのレベルを、ターン終了時までその２体のレベルを"
                        "合計したレベルにする。")[0][:4],
            ("にする", "他動", "その2体のレベルを合計したレベル", "そのモンスターとこのカードのレベル"))

    def test_sum_value_is_an_attribute(self):
        """合計|値、合計|分 兩詞連起來是屬性名詞。"""
        self.assertEqual(
            complements("②：このカードの攻撃力は、他の「D-HERO」モンスターの元々の攻撃力の"
                        "合計値になる。")[0][:3],
            ("にする", "自動", "他の「D-HERO」モンスターの元々の攻撃力の合計値"))
        self.assertEqual(
            complements("①：その攻撃力はリリースしたモンスターの攻撃力の合計分となる。")[0][:3],
            ("とする", "自動", "リリースしたモンスターの攻撃力の合計分"))

    def test_phase_name(self):
        """已知偏離:エンドフェイズになる 依規則記 にする+目的(時間語的 に 也收)。"""
        self.assertEqual(complements("②：このターンのエンドフェイズになる。")[0][:3],
                         ("にする", "自動", "エンドフェイズ"))

    def test_state_words_still_fold(self):
        """照舊併入;対象とする 沒有 なる 形被併進來,態空。"""
        self.assertEqual(voiced("①：フィールドのモンスター１体を対象として発動できる。")[0][:2],
                         ("対象とする", None))
        self.assertEqual(complements("①：そのモンスターの効果を無効にする。"),
                         [("無効にする", "他動", None, "そのモンスターの効果", None)])
        self.assertEqual(
            voiced("②：自分の手札・フィールドのモンスターを融合素材とし、融合モンスター１体を"
                   "EXデッキから融合召喚する。")[0][:2],
            ("融合素材とする", "他動"))
        self.assertEqual(voiced("①：このカードは攻撃対象にされない。"),
                         [("攻撃対象にする", "受身", "否定")])
        self.assertEqual(voiced("①：相手が受ける戦闘ダメージを半分にする。"),
                         [("半分にする", "他動", "肯定")])

    def test_number_stays_in_goal(self):
        self.assertEqual(complements("②：そのモンスターの攻撃力を０にする。"),
                         [("にする", "他動", "0", "そのモンスターの攻撃力", None)])

    def test_comparison_stays_in_goal(self):
        """以上 照舊不吸收:補語整段留目的。"""
        self.assertEqual(
            complements("①：レベルの合計がそのモンスターのレベル以上になる。")[0][:3],
            ("にする", "自動", "そのモンスターのレベル以上"))


class TestPerformSummon(unittest.TestCase):
    """frame-lemma-variants 票 01:「〜召喚を行う」的詞元是那個召喚,「の」前的名詞片語是對象;
    對象不是召喚的 行う 不動。"""

    def test_bare_summon_performed(self):
        self.assertEqual(extract("①：S召喚を行う。"),
                         [("S召喚", None, None, None, "效果", "肯定")])

    def test_noun_before_no_is_the_object(self):
        self.assertEqual(extract("③：魚族Sモンスター１体のS召喚を行う。"),
                         [("S召喚", "魚族Sモンスター1体", None, None, "效果", "肯定")])
        self.assertEqual(extract("①：このカードの召喚を行う。"),
                         [("召喚", "このカード", None, None, "效果", "肯定")])
        self.assertEqual(extract("②：Sモンスターのチューナー１体のS召喚を行う事ができる。"),
                         [("S召喚", "Sモンスターのチューナー1体", None, None, "效果", "可能")])

    def test_spelling_and_inferred_values_as_a_direct_summon(self):
        """寫法歸一照舊(A召喚、L召喚),推得的目的 フィールド 與直接寫「〜をS召喚する」一樣補。"""
        frame = actions("②：「真竜」モンスター１体のA召喚を表側表示で行う。")[0]
        self.assertEqual((frame["action"], frame["object"], frame["goal"], frame.get("inferred")),
                         ("A召喚", "「真竜」モンスター1体", "フィールド", ["goal"]))
        self.assertEqual(extract("②：「ヴァルモニカ」Lモンスター１体のL召喚を行う。")[0][:2],
                         ("L召喚", "「ヴァルモニカ」Lモンスター1体"))

    def test_zone_of_the_summoned_monster_is_its_source(self):
        """召喚是移動類:對象片語裡的區域切成來源。"""
        self.assertEqual(extract("①：手札の「霊獣」モンスター１体の召喚を行う。"),
                         [("召喚", "「霊獣」モンスター1体", "手札", None, "效果", "肯定")])

    def test_count_and_condition_follow_the_rule(self):
        self.assertEqual(extract("①：このターン自分は通常召喚を３回まで行う事ができる。"),
                         [("通常召喚", None, None, None, "效果", "可能")])
        self.assertEqual(
            extract("②：自分が儀式召喚を行う場合、その儀式召喚に必要なレベル分のリリースの代わりに"
                    "このカードを除外できる。")[0],
            ("儀式召喚", None, None, None, "條件", "肯定"))

    def test_topic_form_keeps_no_owner(self):
        """主題形:所有格 このカードの 只留子句字面。"""
        self.assertEqual(topics("②：このカードの融合召喚は上記のカードでしか行えない。"),
                         [("融合召喚", None, None, None, None)])
        self.assertEqual(voiced("②：このカードの融合召喚は上記のカードでしか行えない。"),
                         [("融合召喚", None, "否定")])

    def test_method_chain_one_frame_each(self):
        self.assertEqual(
            voiced("②：このカードを素材とした融合・S・X・リンク召喚しか行えない。"),
            [("融合召喚", None, "否定"), ("S召喚", None, "否定"), ("X召喚", None, "否定"),
             ("L召喚", None, "否定")])

    def test_summons_coordinated_by_nakaguro(self):
        """「召喚・特殊召喚を行えない」:・ 並列的兩個召喚各出一框。"""
        self.assertEqual(voiced("①：このターン、自分は召喚・特殊召喚を行えない。"),
                         [("召喚", None, "否定"), ("特殊召喚", None, "否定")])

    def test_summons_coordinated_by_matawa(self):
        self.assertEqual(
            [f[:2] for f in extract(
                "①：その後、「覇王眷竜」Sモンスター１体のS召喚または「覇王眷竜」Xモンスター１体の"
                "X召喚を行う事ができる。")],
            [("S召喚", "「覇王眷竜」Sモンスター1体"), ("X召喚", "「覇王眷竜」Xモンスター1体")])

    def test_topic_before_the_condition_belongs_to_the_main_clause(self):
        """條件子句裡主題寫在自己主語之前:和「S召喚する場合」一樣,主題不給條件框架。"""
        self.assertEqual(topics("①：このカードは、自分がS召喚を行う場合、除外できる。")[0],
                         ("S召喚", None, "自分", None, None))

    def test_other_objects_stay_perform(self):
        self.assertEqual(
            [f[0] for f in voiced("①：このカードが相手モンスターと戦闘を行う場合、"
                                  "ダメージ計算前に発動できる。")][:1],
            ["行う"])
        self.assertEqual(voiced("①：コイントスを１回行い、表が出た場合、このカードを破壊する。")[0],
                         ("行う", None, "肯定"))
        self.assertEqual(voiced("①：このターン、相手はバトルフェイズを行えない。"),
                         [("行う", None, "否定")])


class TestSummonMaterialExpanded(unittest.TestCase):
    """frame-lemma-variants 票 02:「法(・法)*召喚の素材に/と + する/なる」展開成各法的素材詞元,一法一框,
    不論極性與位置;原文助詞 に/と 照留;法前的所有格不進任何欄。"""

    def test_cannot_be_material_for_each_method(self):
        self.assertEqual(
            topics("①：このカードは融合・S・X召喚の素材にできない。"),
            [("融合素材にする", "このカード", None, None, "他動"),
             ("S素材にする", "このカード", None, None, "他動"),
             ("X素材にする", "このカード", None, None, "他動")])
        self.assertEqual([f[2] for f in voiced("①：このカードは融合・S・X召喚の素材にできない。")],
                         ["否定"] * 3)

    def test_single_method(self):
        self.assertEqual([f[:1] + f[2:] for f in voiced("①：このカードはX召喚の素材にできない。")],
                         [("X素材にする", "否定")])

    def test_mo_between_material_and_cannot(self):
        self.assertEqual(
            [f[0] for f in voiced("①：このカードは融合・S・X・L召喚の素材にもできない。")],
            ["融合素材にする", "S素材にする", "X素材にする", "L素材にする"])

    def test_naru_form_in_a_condition(self):
        frame = actions("②：このカードが融合召喚の素材となって墓地へ送られた場合に発動できる。"
                        "このカードを特殊召喚する。")[0]
        self.assertEqual((frame["action"], frame.get("voice"), frame["position"],
                          frame.get("subject")),
                         ("融合素材とする", "自動", "條件", "このカード"))
        self.assertEqual(
            [f[:2] for f in voiced("③：装備モンスターが融合・S・X・リンク召喚の素材になった事で"
                                   "墓地へ送られた場合に発動できる。")][:4],
            [("融合素材にする", "自動"), ("S素材にする", "自動"), ("X素材にする", "自動"),
             ("L素材にする", "自動")])

    def test_suru_form_in_a_condition(self):
        self.assertEqual(
            [(f[0], f[1], f[4]) for f in extract(
                "①：このカードをS・X召喚の素材とする場合、このカードはチューナー以外の"
                "モンスターとして扱う事ができる。")][:2],
            [("S素材とする", "このカード", "條件"), ("X素材とする", "このカード", "條件")])

    def test_potential(self):
        self.assertEqual(
            [f[:1] + f[2:] for f in voiced(
                "③：そのXモンスターはこのターン、自身のランクと同じ数値のレベルのモンスターとして"
                "X召喚の素材にできる。")],
            [("X素材にする", "可能")])

    def test_owner_before_the_method_stays_in_the_clause(self):
        self.assertEqual(
            topics("①：元々の持ち主が相手となるモンスターをこのカードのX召喚の素材とする場合、"
                   "１体で２体分の素材にできる。")[0][0:4:3],
            ("X素材とする", "元々の持ち主が相手となるモンスター"))
        self.assertEqual(
            [(f[0], f[1], f[2]) for f in topics(
                "②：このカードが墓地へ送られたターン、自分フィールドのモンスター及び、相手の"
                "融合・S・L召喚の素材となり墓地へ送られたモンスターは効果を発動できない。")
             if "素材" in f[0]],
            [("融合素材とする", None, None), ("S素材とする", None, None),
             ("L素材とする", None, None)])

    def test_material_without_summon_stays(self):
        self.assertEqual(
            voiced("①：自分フィールドのランク４モンスターをレベル４モンスターとして素材にできる。"),
            [("素材にする", "他動", "可能")])


class TestMaterialVoice(unittest.TestCase):
    """frame-lemma-variants 票 03:融合/S/X/L素材にする/とする 有 なる 形併進來,加進態的統一組——
    原文 する 記他動、なる 記自動,受身照舊。"""

    def test_suru_forms_are_active(self):
        """融合素材とし、そのX素材とする 的 他動 在 TestComplementNotFolded、TestSpellingUnified。"""
        self.assertEqual(voiced("①：このカードはリンク素材にできない。"),
                         [("L素材にする", "他動", "否定")])

    def test_naru_form_is_intransitive(self):
        self.assertEqual(
            voiced("①：このカードが融合召喚の素材となって墓地へ送られた場合に発動できる。")[0][:2],
            ("融合素材とする", "自動"))

    def test_passive_stays_passive(self):
        self.assertEqual(voiced("①：このカードは融合素材にされない。"),
                         [("融合素材にする", "受身", "否定")])
        self.assertEqual(
            voiced("③：このカードがS素材として墓地へ送られた場合に発動できる。"),
            [("S素材とする", "他動", "肯定"), ("送る", "受身", "肯定")])


class TestAttackTargetSelect(unittest.TestCase):
    """frame-lemma-variants 票 04:「攻撃対象に選択」是 攻撃対象にする——目的清空、所有格只留子句字面;
    主題句「攻撃対象は…が選択する」與選效果的 選択 不動。"""

    def test_cannot_select_as_attack_target(self):
        self.assertEqual(
            complements("①：相手は「ジェネレイド」効果モンスターを攻撃対象に選択できない。"),
            [("攻撃対象にする", "他動", None, "「ジェネレイド」効果モンスター", "相手")])
        self.assertEqual(
            voiced("①：相手は「竜騎士ガイア」しか攻撃対象に選択できない。"),
            [("攻撃対象にする", "他動", "否定")])
        self.assertEqual(
            voiced("①：相手はこのカードを攻撃対象に選択できず、効果の対象にもできない。")[0],
            ("攻撃対象にする", "他動", "否定"))

    def test_selected_as_attack_target(self):
        frame = actions("①：このカードが攻撃対象に選択された場合に発動できる。"
                        "その攻撃を無効にする。")[0]
        self.assertEqual((frame["action"], frame.get("voice"), frame["position"], frame["goal"]),
                         ("攻撃対象にする", "受身", "條件", None))
        frame = actions("②：このカードが相手モンスターの攻撃対象に選択された時に発動できる。"
                        "その攻撃を無効にする。")[0]
        self.assertEqual((frame["action"], frame.get("voice"), frame["goal"]),
                         ("攻撃対象にする", "受身", None))

    def test_who_selects_stays_select(self):
        self.assertEqual(
            [f[0] for f in voiced("①：相手モンスターの攻撃対象は自分が選択する。")], ["選択"])
        self.assertEqual(
            voiced("①：以下の効果から１つを選択して発動できる。")[0][0], "選択")


class TestComplementMoEffectAndTreat(unittest.TestCase):
    """frame-lemma-variants 票 05:補語與 なる/する 之間夾 も 不擋併入;補語以 効果 收尾時不併(效果
    變成什麼,補語是值);「〜の素材として扱う」的述語是 扱う。"""

    def test_mo_between_complement_and_naru(self):
        self.assertEqual(
            complements("①：このカードは相手の効果の対象にもならない。"),
            [("対象にする", "自動", None, None, "このカード")])
        self.assertEqual(voiced("①：このカードは相手の効果の対象にもならない。")[0][2], "否定")

    def test_mo_after_a_verb_or_noun_is_unchanged(self):
        self.assertEqual(voiced("①：このカードを特殊召喚する事もできる。"),
                         [("特殊召喚", None, "可能")])
        self.assertEqual(voiced("①：このカードは攻撃宣言もできない。"),
                         [("攻撃宣言", None, "否定")])

    def test_effect_complement_is_a_value(self):
        self.assertEqual(
            complements("①：その裏表によってその効果は以下の効果となる。"),
            [("とする", "自動", "以下の効果", None, "その効果")])
        self.assertEqual(
            complements("①：自分にダメージを与える効果は、自分のLPを回復する効果になる。")[0][:3],
            ("にする", "自動", "自分のLPを回復する効果"))
        self.assertEqual(complements("①：同じ効果になる。")[0][:3], ("にする", "自動", "同じ効果"))

    def test_negating_an_effect_still_folds(self):
        self.assertEqual(complements("①：そのモンスターの効果を無効にする。")[0][:4],
                         ("無効にする", "他動", None, "そのモンスターの効果"))
        self.assertEqual(voiced("①：その効果を無効化する。")[0][:2], ("無効にする", "他動"))

    def test_treated_as_material_is_treat(self):
        self.assertEqual(
            topics("①：このターンにL召喚する場合、このカードは見せたモンスターと同じ"
                   "カード名・種族・属性の素材として扱う事ができる。")[1:],
            [("扱う", "このカード", None, None, None)])
        self.assertEqual(
            voiced("②：自分の手札・フィールドのモンスターを融合素材として墓地へ送り、"
                   "融合モンスター１体を特殊召喚する。")[0][:2],
            ("融合素材とする", "他動"))
        # 「〜を S素材として扱う」沒有「の」:素材として 照舊成框架
        self.assertEqual([f[0] for f in voiced("①：このカードをS素材として扱う事ができる。")],
                         ["S素材とする", "扱う"])


def anaphora_of(text, action=None, context=""):
    """效果句 → 第一個(或第一個動作是 action 的)帶指示詞受事者框架的回指欄;沒有回指時 None。"""
    found = [f for f in actions(text, context)
             if (action is None and f.get("anaphora")) or f["action"] == action]
    return found[0].get("anaphora") if found else None


class TestAnaphoraTargeted(unittest.TestCase):
    """回指(action-patient-anaphora 票 01):対象の 與 対象とする 的目標。"""

    def test_across_full_stop_keeps_text_and_place(self):
        found = anaphora_of("①：フィールドのモンスター１体を対象として発動できる。"
                            "そのモンスターを破壊する。")
        self.assertEqual((found["text"], found["place"]), ("モンスター1体", "フィールド"))

    def test_player_comes_from_place(self):
        found = anaphora_of("①：相手フィールドのモンスター１体を対象として発動できる。"
                            "そのモンスターを破壊する。")
        self.assertEqual((found["place"], found["player"]), ("相手フィールド", "相手"))

    def test_taishou_no_skips_this_card_and_points_to_target_frame(self):
        found = anaphora_of("①：自分フィールドの魔法・罠カード１枚を対象として発動できる。"
                            "このカードを特殊召喚し、対象のカードをデッキに戻す。", "戻す")
        self.assertEqual((found["text"], found["via"]), ("魔法(カード)・罠カード1枚", "対象"))

    def test_taishou_no_without_target_frame_is_blank(self):
        self.assertIsNone(anaphora_of("①：このカードを特殊召喚し、対象のカードをデッキに戻す。", "戻す"))

    def test_this_effects_target(self):
        found = anaphora_of("①：相手フィールドのカード１枚を対象として発動できる。"
                            "この効果の対象を破壊する。", "破壊")
        self.assertEqual(found["text"], "カード1枚")

    def test_backfilled_demonstrative_object(self):
        # 破壊 的對象由か群組從 そのカード 回填
        found = anaphora_of("①：フィールドのカード１枚を対象として発動できる。"
                            "そのカードを除外するか破壊する。", "破壊")
        self.assertEqual(found["text"], "カード1枚")

    def test_no_demonstrative_no_field(self):
        self.assertNotIn("anaphora", actions("①：フィールドのカード１枚を破壊する。")[0])


class TestAnaphoraGeneral(unittest.TestCase):
    """回指(票 02):欄位候選、此卡、範圍、解到底、修飾語、不是卡。"""

    def test_singular_skips_this_card(self):
        self.assertIsNone(anaphora_of("①：このカードを手札から捨てて発動できる。"
                                      "その破壊されたモンスターを除外する。", "除外"))
        found = anaphora_of("①：相手モンスター１体を破壊し、このカードを手札に戻す。"
                            "その破壊されたモンスターを除外する。", "除外")
        self.assertEqual(found["text"], "相手モンスター1体")

    def test_listed_with_this_card_is_not_skipped(self):
        found = anaphora_of("①：手札のこのカードと手札のモンスター１体を相手に見せて発動できる。"
                            "その２体を特殊召喚する。", "特殊召喚")
        self.assertEqual((found["text"], found["place"]), ("このカードとモンスター1体", "手札"))

    def test_this_card_or_alternative_is_not_skipped(self):
        found = anaphora_of("①：このカードまたは自分フィールドのモンスター１体を対象として発動できる。"
                            "そのモンスターの攻撃力は１０００アップする。", "アップ")
        self.assertIn("このカード", found["text"])

    def test_this_card_other_than_is_a_candidate(self):
        found = anaphora_of("①：このカード以外のモンスター１体を対象として発動できる。"
                            "そのモンスターを破壊する。", "破壊")
        self.assertEqual(found["text"], "このカード以外のモンスター1体")

    def test_qualifier_beats_nearest(self):
        found = anaphora_of("①：相手の墓地のモンスター１体を除外し、自分の墓地のモンスター１体を手札に加える。"
                            "その相手モンスターを戻す。", "戻す")
        self.assertEqual(found["player"], "相手")
        found = anaphora_of("①：デッキから融合モンスター１体を墓地へ送り、手札からモンスター１体を特殊召喚する。"
                            "その融合モンスターを除外する。", "除外")
        self.assertEqual(found["text"], "融合モンスター1体")

    def test_nearest_when_qualifiers_tie(self):
        found = anaphora_of("①：墓地のモンスター１体を除外し、手札のモンスター１体を墓地へ送る。"
                            "そのモンスターを破壊する。", "破壊")
        self.assertEqual(found["place"], "手札")

    def test_options_are_isolated(self):
        text = ("①：以下の効果から１つを選択して発動できる。\n"
                "●自分フィールドのカード１枚を対象として発動できる。そのカードを破壊する。\n"
                "●そのカードを除外する。")
        self.assertEqual(anaphora_of(text, "破壊")["text"], "カード1枚")
        self.assertIsNone(anaphora_of(text, "除外"))

    def test_common_part_reaches_both_options(self):
        text = ("①：フィールドのカード１枚を対象として発動できる。\n"
                "●そのカードを破壊する。\n●そのカードを除外する。")
        self.assertEqual(anaphora_of(text, "破壊")["text"], "カード1枚")
        self.assertEqual(anaphora_of(text, "除外")["text"], "カード1枚")

    def test_no_reach_into_context(self):
        self.assertIsNone(anaphora_of("②：そのモンスターを破壊する。", "破壊",
                                      context="①：モンスター１体を対象として発動できる。"))

    def test_chain_resolves_to_the_end(self):
        found = anaphora_of("①：相手フィールドのモンスター１体を対象として発動できる。"
                            "そのモンスターを破壊し、それを除外する。", "除外")
        self.assertEqual((found["text"], found["player"]), ("モンスター1体", "相手"))

    def test_modifier_is_not_anaphora(self):
        for text, action in (
                ("①：自分フィールドのXモンスター１体を対象として発動できる。"
                 "そのモンスターよりランクが２つ高いXモンスター１体を特殊召喚する。", "特殊召喚"),
                ("①：墓地のモンスター１体を対象として発動できる。"
                 "そのモンスターと同じ種族のモンスター１体を破壊する。", "破壊"),
                ("①：墓地のモンスター１体を対象として発動できる。"
                 "そのモンスターとはカード名が異なるモンスター１体を破壊する。", "破壊"),
                ("①：墓地のモンスター１体を対象として発動できる。"
                 "そのモンスターのレベル以下のレベルを持つモンスターを破壊する。", "破壊"),
                ("①：墓地のモンスター１体を対象として発動できる。"
                 "そのモンスターにカード名が記されたモンスター１体を破壊する。", "破壊")):
            self.assertIsNone(anaphora_of(text, action), text)

    def test_not_a_card_has_no_anaphora(self):
        self.assertIsNone(anaphora_of("①：モンスター１体を対象として発動できる。"
                                      "その戦闘で発生する戦闘ダメージを０にする。", "にする"))
        self.assertIsNone(anaphora_of("①：モンスター１体を対象として発動できる。"
                                      "その数を０にする。", "にする"))

    def test_attribute_follows_owner(self):
        found = anaphora_of("①：フィールドのモンスター１体を対象として発動できる。"
                            "そのモンスターの攻撃力は０になる。", "にする")
        self.assertEqual(found["text"], "モンスター1体")

    def test_card_effect_follows_owner(self):
        found = anaphora_of("①：相手フィールドのモンスター１体を対象として発動できる。"
                            "そのモンスターの効果を無効にする。", "無効にする")
        self.assertEqual((found["text"], found["via"]), ("モンスター1体", "欄位"))

    def test_condition_position_too(self):
        found = [f for f in actions("①：モンスター１体を対象として発動できる。"
                                    "そのモンスターが破壊された場合、このカードを破壊する。")
                 if f.get("anaphora")]
        self.assertEqual([f["position"] for f in found], ["條件"])

    def test_count_only_in_clause_is_kept(self):
        found = anaphora_of("①：自分の墓地からモンスターを１体選んで特殊召喚する。"
                            "そのモンスターの攻撃力は０になる。", "にする")
        self.assertEqual((found["text"], found["count"]), ("モンスター", "1体"))


class TestAnaphoraEvent(unittest.TestCase):
    """回指(票 03):事件主語、效果類的主人、字面備援、留空。"""

    def test_event_object_records_subject(self):
        found = anaphora_of("①：相手がモンスターを特殊召喚した時に発動できる。"
                            "そのモンスターを破壊する。", "破壊")
        self.assertEqual((found["text"], found["subject"]), ("モンスター", "相手"))

    def test_effect_owner_from_subject(self):
        found = anaphora_of("①：相手が効果を発動した時に発動できる。その発動を無効にする。", "無効にする")
        self.assertEqual((found["subject"], found["via"]), ("相手", "事件"))

    def test_effect_owner_from_clause_literal(self):
        found = anaphora_of("①：相手モンスターの攻撃宣言時に発動できる。その攻撃を無効にする。",
                            "無効にする")
        self.assertEqual(found["subject"], "相手モンスター")
        found = anaphora_of("①：このカードの攻撃宣言時に発動できる。その攻撃を無効にする。", "無効にする")
        self.assertEqual(found["subject"], "このカード")

    def test_targeted_card_is_not_the_owner(self):
        found = anaphora_of("①：このカードが攻撃対象に選択された時に発動できる。その攻撃を無効にする。",
                            "無効にする")
        self.assertNotIn("subject", found)
        found = anaphora_of("①：このカードを対象とする効果が発動した時に発動できる。その効果を無効にする。",
                            "無効にする")
        self.assertEqual(found["subject"], "このカードを対象とする効果")

    def test_effect_with_no_event_is_blank(self):
        self.assertIsNone(anaphora_of("①：その効果を無効にする。", "無効にする"))

    def test_literal_fallback(self):
        found = anaphora_of("①：このカードが相手モンスターと戦闘を行う時に発動できる。"
                            "その相手モンスターの攻撃力は０になる。", "にする")
        self.assertEqual((found["text"], found["via"], found["player"]),
                         ("相手モンスター", "字面", "相手"))

    def test_literal_fallback_from_unframed_clause(self):
        # 「戦闘を行う|ダメージ計算時」定語不出框架,仍從字面找到
        found = anaphora_of("①：自分のモンスターが戦闘を行うダメージ計算時に発動できる。"
                            "そのモンスターの攻撃力はターン終了時まで１０００アップする。", "アップ")
        self.assertEqual((found["text"], found["player"]), ("自分のモンスター", "自分"))

    def test_blank_when_nothing_matches(self):
        self.assertIsNone(anaphora_of("①：このカードを破壊する。そのモンスターを除外する。", "除外"))


class TestAnaphoraRound1(unittest.TestCase):
    """回指 LLM 檢驗第一輪(anaphora-round1)抓到的錯,每類一條。"""

    def test_bare_attribute(self):
        """6622715:光禿禿的 その攻撃力 指前一個選的卡。"""
        found = anaphora_of("①：このカードまたは自分のモンスター１体を選び、その攻撃力を１０００アップする。",
                            "アップ")
        self.assertEqual(found["text"], "このカードまたは自分のモンスター1体")

    def test_target_of_listed_with_its_material(self):
        """10424147:対象のモンスターとそのX素材 的 そのX素材 不是「另一張實體卡」的寫法。"""
        found = anaphora_of("①：自分のXモンスター１体を対象として発動できる。"
                            "対象のモンスターとそのX素材を除外する。", "除外")
        self.assertEqual(found["text"], "自分のXモンスター1体")

    def test_within_points_to_zone(self):
        """39576656、91501248:その内の１枚 指前面確認的區域。"""
        found = anaphora_of("①：相手の手札を確認し、その内の１枚を墓地へ送る。", "送る")
        self.assertEqual(found["text"], "相手の手札")

    def test_modified_this_card_is_still_this_card(self):
        """39576656:S召喚したこのカード 字面只是此卡,不是候選。"""
        self.assertIsNone(anaphora_of("①：S召喚したこのカードを破壊する。そのモンスターを除外する。", "除外"))

    def test_fusion_monster_is_not_fusion_material(self):
        """46136942:その融合モンスター 不指融合素材モンスター。"""
        found = anaphora_of("①：EXデッキの融合モンスターカードに決められた融合素材モンスターを墓地へ送り、"
                            "その融合モンスター１体を特殊召喚する。", "特殊召喚")
        self.assertEqual(found["text"], "融合モンスターカード")

    def test_used_material_is_a_modifier(self):
        """76647978:その融合召喚に使用した融合素材 是另一組實體卡。"""
        self.assertIsNone(anaphora_of("①：融合モンスター１体を対象として発動できる。そのモンスターの"
                                      "融合召喚に使用した融合素材モンスター１組を特殊召喚する。", "特殊召喚"))

    def test_literal_keeps_listed_names_and_ranges(self):
        """64283880、29085954:字面片語不切開並列與範圍。"""
        found = anaphora_of("①：「ガガガ」か「ドドド」モンスターが存在する場合に発動できる。"
                            "そのモンスターを破壊する。", "破壊")
        self.assertEqual(found["text"], "「ガガガ」か「ドドド」モンスター")

    def test_literal_card_drops_event_tail(self):
        """99157310、71442223:その攻撃モンスター 的目標是相手モンスター,不是攻撃宣言。"""
        found = anaphora_of("①：相手モンスターの直接攻撃宣言時に発動できる。"
                            "その攻撃モンスターを破壊する。", "破壊")
        self.assertEqual((found["text"], found["via"]), ("相手モンスター", "字面"))

    def test_field_target_drops_attribute(self):
        """46947713:目標是卡本身,不帶屬性尾巴。"""
        found = anaphora_of("①：自分のモンスターの攻撃力は５００アップする。それらを破壊する。", "破壊")
        self.assertEqual(found["text"], "自分のモンスター")

    def test_each_other_literal_and_own_qualifier_sets_player(self):
        """86449372:モンスター同士 也是字面候選;その相手モンスター 的玩家看自己的限定語。"""
        found = anaphora_of("①：自分と相手のモンスター同士が戦闘を行うダメージ計算時に発動できる。"
                            "その相手モンスターの攻撃力を０にする。", "にする")
        self.assertEqual((found["text"], found["player"]), ("自分と相手のモンスター", "相手"))

    def test_bare_activation_word_is_not_an_event(self):
        """8690387:「発動できる」的 発動 不是事件,沒有主人的片語不當目標。"""
        self.assertIsNone(anaphora_of("①：モンスター１体を対象として発動できる。自分はその効果を適用する。",
                                      "適用"))

    def test_owner_from_relative_clause(self):
        """34536828、6798031:相手が発動したモンスターの効果 的主人是相手。"""
        found = anaphora_of("①：相手が発動したモンスターの効果の処理時に、その効果を無効にできる。",
                            "無効にする")
        self.assertEqual((found["subject"], found["via"]), ("相手", "事件"))

    def test_owner_from_literal_with_processing_tail(self):
        """46796664:魔法カードの効果の処理時に、その効果。"""
        found = anaphora_of("①：魔法カードの効果の処理時に、その効果を無効にできる。", "無効にする")
        self.assertEqual(found["subject"], "魔法カード")

    def test_targeted_players_are_not_the_owners(self):
        """19502505:自分フィールドの…を対象とする魔法カード 的玩家不是自分。"""
        found = anaphora_of("①：自分フィールドのモンスター１体を対象とする魔法カードが発動した時に発動できる。"
                            "その発動を無効にする。", "無効にする")
        self.assertNotIn("player", found)

    def test_activation_time_effect_follows_card(self):
        """2815176 等(anaphora-round2):その魔法カード発動時の効果 跟著那張魔法卡。"""
        found = anaphora_of("①：自分の墓地の魔法カード１枚を対象として発動できる。"
                            "その魔法カード発動時の効果を適用する。", "適用")
        self.assertEqual((found["text"], found["via"]), ("魔法カード1枚", "欄位"))

    def test_bare_count_phrase_is_not_a_target(self):
        """88494120(round2):モンスターが１体のみの場合 的「1体」不是目標。"""
        found = anaphora_of("①：自分フィールドの表側表示モンスターが１体のみの場合、"
                            "そのモンスター１体を対象として発動できる。", "対象とする")
        self.assertEqual(found["text"], "表側表示モンスター")

    def test_earlier_demonstrative_in_clause_does_not_cut_literal(self):
        """46613515(round2):そのドローしたカードがモンスターだった場合、そのモンスター。"""
        found = anaphora_of("①：相手モンスターの攻撃宣言時に発動できる。自分はデッキから１枚ドローする。"
                            "そのドローしたカードがモンスターだった場合、そのモンスターを特殊召喚する。",
                            "特殊召喚")
        self.assertEqual(found["text"], "モンスター")

    def test_literal_summon_success_keeps_event_subject(self):
        """72971064(round2):相手がモンスターの特殊召喚に成功した時…そのモンスター。"""
        found = anaphora_of("①：相手がモンスターの特殊召喚に成功した時に発動できる。"
                            "そのモンスターを破壊する。", "破壊")
        self.assertEqual((found["text"], found["subject"]), ("モンスター", "相手"))

    def test_bare_sore_with_negation_is_the_event(self):
        """10300821(round2):それを無効にし 無效的是事件,不是剛取除的素材。"""
        found = anaphora_of("①：相手がモンスターを特殊召喚する際に、このカードのX素材を１つ取り除いて発動できる。"
                            "それを無効にする。", "無効にする")
        self.assertEqual((found["via"], found["subject"]), ("事件", "相手"))

    def test_count_after_attribute(self):
        """29251488(round2):そのモンスターのレベル３つまで。"""
        found = anaphora_of("①：自分・相手ターンに１度、フィールドの効果モンスター１体を対象として発動できる。"
                            "そのモンスターのレベルを３つまで上げる。", "アップ")
        self.assertEqual(found["text"], "効果モンスター1体")

    def test_processing_tail_not_in_text(self):
        """17473466(round2):字面去掉「の処理」。"""
        found = anaphora_of("①：魔法カードの効果の処理時に、その効果を無効にできる。", "無効にする")
        self.assertEqual(found["text"], "魔法カードの効果")

    def test_attack_target_is_never_the_owner(self):
        """3507053(code review):攻撃対象になった 是自動,主語仍是被攻擊的那張。"""
        found = anaphora_of("①：このカードが攻撃対象になった時に発動できる。その攻撃を無効にする。",
                            "無効にする")
        self.assertNotIn("subject", found)

    def test_agent_before_phrase_does_not_own_the_effect(self):
        """code review:このカードが相手の効果を受ける場合…その効果 的主人是相手。"""
        found = anaphora_of("①：このカードが相手の効果を受ける場合に発動できる。その効果を無効にする。",
                            "無効にする")
        self.assertEqual(found["subject"], "相手")

    def test_owner_in_clause_does_not_cross_case_particles(self):
        """code review:相手がこのカードの効果を無効にする効果を発動した時 的主人不是「相手がこのカード」。"""
        found = anaphora_of("①：相手がこのカードの効果を無効にする効果を発動した時に発動できる。"
                            "その発動を無効にする。", "無効にする")
        self.assertNotIn("このカード", found.get("subject", ""))

    def test_player_qualifier_reads_the_candidate_not_its_clause(self):
        """code review:子句裡有 相手モンスター 不算主語 自分のモンスター 帶限定語 相手。"""
        found = anaphora_of("①：自分のモンスターが相手モンスターと戦闘を行う時に発動できる。"
                            "その相手モンスターの攻撃力を０にする。", "にする")
        self.assertEqual((found["text"], found["player"]), ("相手モンスター", "相手"))

    def test_type_qualifier_reads_the_candidate_not_its_clause(self):
        found = anaphora_of("①：自分のモンスターが融合モンスターと戦闘を行う時に発動できる。"
                            "その融合モンスターの攻撃力を０にする。", "にする")
        self.assertEqual(found["text"], "融合モンスター")

    def test_modifier_with_effect_tail(self):
        """19271881(code review):そのモンスター以外の…カードの効果 受事者是別的卡。"""
        self.assertIsNone(anaphora_of("①：モンスター１体を対象として発動できる。"
                                      "そのモンスター以外の全ての表側表示カードの効果を無効にする。", "無効にする"))

    def test_own_frame_subject_owns_the_effect(self):
        """48497555:魔法カードがその効果を発動した時。"""
        found = anaphora_of("①：相手の魔法カードがその効果を発動した時に発動できる。そのカードを破壊する。",
                            "発動")
        self.assertEqual((found["subject"], found["via"]), ("相手の魔法カード", "事件"))



def segments(text, key="object", action=None, context=""):
    """票 02 的接縫輔助:第一個(指定動作的)動作框架該欄的論元片語 → 各段
    (字面, 中心詞, 中心詞類, 指示詞, 玩家, 區域);該欄沒有片語時 None。"""
    frame = next(f for f in actions(text, context) if action is None or f["action"] == action)
    phrase = (frame.get("phrases") or {}).get(key)
    if phrase is None:
        return None
    return [(s["text"], s["head"], s["head_kind"], s["demonstrative"], s["player"], s["zones"])
            for s in phrase["segments"]]


class TestArgumentPhrases(unittest.TestCase):
    """frame-args-v4 票 02:受事者位三欄與目的欄各帶論元片語——依並列詞切段,每段的中心詞是去掉數量尾
    後的最後一個名詞格、中心詞類走封閉表、指示詞旗標看段首、玩家與區域沿用區域辨識(切走的仍留一份);
    推得的目的沒有片語。只斷言輸出框架的 phrases 欄。指示詞旗標依 2026-11-01 站主裁定改成語意判定(段首指示詞
    之後先有格助詞再有定語述語或比較詞時旗標假),test_to_onaji_is_comparison_not_a_segment_boundary 的預期
    跟著從真改假;規則例子在 TestV4Decisions。"""

    def test_single_segment_keeps_the_region_cut_into_place(self):
        """相手フィールドの表側表示モンスター１体:一段,中心詞 モンスター(卡),玩家 相手、區域 場上;
        整段字面是對象欄現在的值(區域已切走)。"""
        frame = actions("①：相手フィールドの表側表示モンスター１体を破壊する。")[0]
        self.assertEqual(frame["phrases"]["object"]["text"], "表側表示モンスター1体")
        self.assertEqual(segments("①：相手フィールドの表側表示モンスター１体を破壊する。"),
                         [("相手フィールドの表側表示モンスター1体", "モンスター", "卡", False, "相手", ["場上"])])

    def test_coordinated_patients_are_separate_segments_with_their_own_regions(self):
        """區域寫了、玩家沒寫:玩家照區域辨識記 無(和結構化區域同一套)。"""
        self.assertEqual(
            segments("①：墓地のモンスター１体と手札のカード１枚を除外する。"),
            [("墓地のモンスター1体", "モンスター", "卡", False, "無", ["墓地"]),
             ("手札のカード1枚", "カード", "卡", False, "無", ["手牌"])])

    def test_dot_coordinated_card_kinds_are_two_segments(self):
        """魔法・罠カード 是兩段;省略寫法 魔法(カード) 的中心詞是補全的 魔法カード。"""
        self.assertEqual(
            segments("①：相手フィールドの魔法・罠カードを全て破壊する。"),
            [("相手フィールドの魔法(カード)", "魔法カード", "卡", False, "相手", ["場上"]),
             ("罠カード", "罠カード", "卡", False, None, [])])

    def test_to_onaji_is_comparison_not_a_segment_boundary(self):
        """と同じ 的 と 不切段;指示詞旗標 票 02 時為真(段首字面),2026-11-01 裁定改語意判定後為假
        (その 綁在比較子句裡的另一張卡)。"""
        self.assertEqual(
            segments("①：デッキからそのモンスターと同じ種族のモンスター１体を手札に加える。"),
            [("そのモンスターと同じ種族のモンスター1体", "モンスター", "卡", False, None, [])])

    def test_closed_value_compound_is_the_head_itself(self):
        """分詞一格的封閉值域複合詞(戦闘ダメージ、自分フィールド)本身就是中心詞。"""
        self.assertEqual(
            segments("①：このカードが相手に与える戦闘ダメージは倍になる。", key="topic"),
            [("このカードが相手に与える戦闘ダメージ", "戦闘ダメージ", "非卡", False, None, [])])
        self.assertEqual(
            segments("①：自分フィールドにモンスターが存在しない場合、このカードは手札から特殊召喚できる。",
                     key="goal", action="存在"),
            [("自分フィールド", "自分フィールド", "卡", False, "自分", ["場上"])])

    def test_attribute_prefix_is_not_part_of_the_head(self):
        """闇属性モンスター 的中心詞是 モンスター(屬性字是前面的格)。"""
        self.assertEqual(
            segments("①：手札から闇属性モンスター１体を特殊召喚する。"),
            [("闇属性モンスター1体", "モンスター", "卡", False, None, [])])

    def test_card_name_is_the_whole_head(self):
        self.assertEqual(
            segments("①：デッキから「青眼の白龍」１体を手札に加える。"),
            [("「青眼の白龍」1体", "「青眼の白龍」", "卡", False, None, [])])

    def test_attribute_head_with_demonstrative_and_numeric_goal(self):
        text = "①：そのモンスターの攻撃力を０にする。"
        self.assertEqual(segments(text), [("そのモンスターの攻撃力", "攻撃力", "屬性", True, None, [])])
        self.assertEqual(segments(text, key="goal"), [("0", "0", "非卡", False, None, [])])

    def test_kono_is_not_a_demonstrative_flag_but_taishou_no_is(self):
        self.assertEqual(segments("①：このカードは戦闘では破壊されない。", key="topic"),
                         [("このカード", "カード", "卡", False, None, [])])
        self.assertEqual(segments("①：対象のモンスターを破壊する。"),
                         [("対象のモンスター", "モンスター", "卡", True, None, [])])

    def test_segment_without_a_noun_head_is_a_demonstrative_kind(self):
        self.assertEqual(segments("①：その内の１体を手札に加える。"),
                         [("その内の1体", "内", "指示詞", True, None, [])])

    def test_method_prefix_joins_the_event_head(self):
        """特殊召喚 的分詞是 特殊|召喚 兩格,中心詞合記 特殊召喚(屬性);カード|名 合記 カード名。"""
        self.assertEqual(
            segments("①：このカードが特殊召喚に成功した場合に発動できる。デッキから１枚ドローする。",
                     key="goal", action="成功"),
            [("特殊召喚", "特殊召喚", "屬性", False, None, [])])
        self.assertEqual(
            segments("①：このカードのカード名は「青眼の白龍」として扱う。", key="topic"),
            [("このカードのカード名", "カード名", "屬性", False, None, [])])

    def test_counter_head_is_non_card(self):
        found = segments("①：このカードに〈魔力〉カウンターを１つ置く。")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0][2], "非卡")

    def test_leading_player_word_is_the_segments_player(self):
        self.assertEqual(segments("①：相手モンスター１体を破壊する。"),
                         [("相手モンスター1体", "モンスター", "卡", False, "相手", [])])

    def test_inferred_goal_has_no_phrase(self):
        frame = actions("①：手札から闇属性モンスター１体を特殊召喚する。")[0]
        self.assertEqual(frame["goal"], "フィールド")
        self.assertNotIn("goal", frame["phrases"])
        self.assertEqual(sorted(frame["phrases"]), ["object"])

    def test_coordinated_modifiers_do_not_split_the_segment(self):
        """攻撃力か守備力が2100の…、ドラゴン族か植物族の…:並列的是修飾語(後面還有 が/の),不是兩個受事者。"""
        self.assertEqual(
            segments("①：攻撃力か守備力が２１００の自分の墓地の機械族モンスター１体を対象として発動できる。"),
            [("攻撃力か守備力が2100の自分の墓地の機械族モンスター1体", "モンスター", "卡", False, "自分", ["墓地"])])
        self.assertEqual(
            segments("①：自分フィールドにドラゴン族か植物族のチューナーが存在する場合に発動できる。",
                     key="subject"),
            [("ドラゴン族か植物族のチューナー", "チューナー", "卡", False, None, [])])

    def test_dot_before_a_no_chain_is_a_modifier_list(self):
        """魔法・罠カードの効果:「・」並列的是修飾語(後面還有 の),一段、中心詞 効果。"""
        self.assertEqual(
            segments("①：相手フィールドの魔法・罠カードの効果を無効にする。"),
            [("相手フィールドの魔法(カード)・罠カードの効果", "効果", "屬性", False, "相手", ["場上"])])

    def test_bare_coordinated_heads_still_split(self):
        self.assertEqual(
            segments("①：そのモンスターの攻撃力と守備力を入れ替える。"),
            [("そのモンスターの攻撃力", "攻撃力", "屬性", True, None, []), ("守備力", "守備力", "屬性", False, None, [])])

    def test_token_stat_block_is_not_the_head(self):
        self.assertEqual(
            segments("①：自分フィールドに「ガジェット・トークン」（サイバース族・光・星２・攻／守０）１体を特殊召喚する。"),
            [("「ガジェット・トークン」（サイバース族・光・星2・攻／守0）1体", "「ガジェット・トークン」", "卡",
              False, None, [])])

    def test_standalone_sono_with_a_count_is_a_demonstrative_quantity_segment(self):
        self.assertEqual(segments("①：その３枚をシャッフルしてデッキに戻す。"),
                         [("その3枚", "3枚", "指示詞", True, None, [])])

    def test_zone_is_found_when_the_description_after_no_has_a_dot(self):
        self.assertEqual(
            segments("①：自分の墓地の攻撃力２５００の悪魔族・レベル６モンスター１体を対象として発動できる。"),
            [("自分の墓地の攻撃力2500の悪魔族・レベル6モンスター1体", "モンスター", "卡", False, "自分", ["墓地"])])

    def test_no_underscore_key_leaks_into_the_frame(self):
        for frame in actions("①：相手フィールドの表側表示モンスター１体を破壊する。"):
            self.assertEqual([k for k in frame if k.startswith("_")], [])

def modifiers(text, key="object", action=None, context=""):
    """frame-args-v4 票 03:各段的修飾語清單 [(字面, 類)…];數值類的多帶 (欄位, 比較, 數字)。
    回每段一個清單;沒有該欄片語時 None。"""
    frame = next((f for f in actions(text, context) if action is None or f["action"] == action), None)
    phrase = (frame.get("phrases") or {}).get(key) if frame else None
    if phrase is None:
        return None
    return [[(m["text"], m["kind"], m["field"], m["compare"], m["number"]) if m["kind"] == "數值"
             else (m["text"], m["kind"]) for m in seg["modifiers"]]
            for seg in phrase["segments"]]


class TestArgumentPhraseModifiers(unittest.TestCase):
    """frame-args-v4 票 03:中心詞之前的各格依 の 與讀點切成修飾語段,每段記字面與修飾語類
    (種族/屬性/字段/卡片子類型/數值/區域/玩家/表示形式/其他);數值段另帶欄位、比較、數字。
    只斷言輸出框架 phrases 欄裡各段的 modifiers。"""

    def test_attribute_race_and_subtype_compound_head(self):
        """闇属性・ドラゴン族の効果モンスター:修飾語 闇属性(屬性)、ドラゴン族(種族);効果モンスター 是分詞一格的
        封閉值域複合詞、整個是中心詞(票 02 的決定),効果 不另記修飾語。"""
        self.assertEqual(modifiers("①：闇属性・ドラゴン族の効果モンスター１体を破壊する。"),
                         [[("闇属性", "屬性"), ("ドラゴン族", "種族")]])

    def test_position_modifier(self):
        self.assertEqual(modifiers("①：相手フィールドの表側表示モンスター１体を破壊する。"),
                         [[("相手フィールド", "區域"), ("表側表示", "表示形式")]])

    def test_summon_methods_are_subtypes_each(self):
        self.assertEqual(modifiers("①：融合・S・Xモンスター１体を破壊する。"),
                         [[("融合", "卡片子類型"), ("S", "卡片子類型"), ("X", "卡片子類型")]])
        self.assertEqual(modifiers("①：チューナーモンスター１体を破壊する。"), [[("チューナー", "卡片子類型")]])

    def test_coordinated_attributes_are_separate_modifiers(self):
        self.assertEqual(modifiers("①：光・闇属性モンスターを破壊する。"), [[("光", "屬性"), ("闇属性", "屬性")]])
        self.assertEqual(modifiers("①：ドラゴン族か植物族のモンスターを破壊する。"),
                         [[("ドラゴン族", "種族"), ("植物族", "種族")]])

    def test_player_and_zone_modifiers(self):
        self.assertEqual(modifiers("①：相手の手札のカードを捨てる。"), [[("相手", "玩家"), ("手札", "區域")]])
        self.assertEqual(modifiers("①：相手モンスター１体を破壊する。"), [[("相手", "玩家")]])
        self.assertEqual(modifiers("①：自分か相手の墓地のモンスターを除外する。"),
                         [[("自分", "玩家"), ("相手", "玩家"), ("墓地", "區域")]])

    def test_head_without_modifiers_has_an_empty_list(self):
        self.assertEqual(modifiers("①：デッキから「青眼の白龍」１体を手札に加える。"), [[]])
        self.assertEqual(modifiers("①：このカードは戦闘では破壊されない。", key="topic"), [[]])

    def test_numeric_with_comparator(self):
        """レベル４以下のモンスター:數值,欄位 レベル、比較 以下、數字 4;攻撃力2400以上 同形;欄位寫在 が 前也一樣。"""
        self.assertEqual(modifiers("①：レベル４以下のモンスター１体を破壊する。"),
                         [[("レベル4以下", "數值", "レベル", "以下", 4)]])
        self.assertEqual(modifiers("①：攻撃力２４００以上のモンスターを破壊する。"),
                         [[("攻撃力2400以上", "數值", "攻撃力", "以上", 2400)]])
        self.assertEqual(modifiers("①：攻撃力が０のモンスターを破壊する。"),
                         [[("攻撃力が0", "數值", "攻撃力", None, 0)]])

    def test_numeric_slash_form_is_one_modifier_per_field(self):
        """攻撃力N／守備力N:兩個數值修飾語,各帶自己的欄位與數字。"""
        self.assertEqual(modifiers("①：攻撃力１０００／守備力１０００のモンスター１体を特殊召喚する。"),
                         [[("攻撃力1000", "數值", "攻撃力", None, 1000), ("守備力1000", "數值", "守備力", None, 1000)]])
        self.assertEqual(modifiers("①：攻撃力２４００以上で守備力１０００のモンスターを破壊する。"),
                         [[("攻撃力2400以上", "數值", "攻撃力", "以上", 2400), ("守備力1000", "數值", "守備力", None, 1000)]])

    def test_numeric_level_list_is_one_modifier_with_the_numbers(self):
        """レベルN・N:一個數值修飾語,number 空、numbers 列兩個數。"""
        frame = actions("①：レベル４・５のモンスターを破壊する。")[0]
        mods = frame["phrases"]["object"]["segments"][0]["modifiers"]
        self.assertEqual(mods, [{"text": "レベル4・5", "kind": "數值", "field": "レベル", "compare": None,
                                 "number": None, "numbers": [4, 5]}])

    def test_coordinated_fields_share_one_number(self):
        self.assertEqual(
            modifiers("①：攻撃力か守備力が２１００の自分の墓地の機械族モンスター１体を対象として発動できる。"),
            [[("攻撃力か守備力が2100", "數值", "攻撃力か守備力", None, 2100), ("自分", "玩家"), ("墓地", "區域"),
              ("機械族", "種族")]])

    def test_counter_count_is_not_a_numeric_modifier(self):
        """３つ以上の:量詞的數是數量不是數值欄位,落 其他(對象字面本身已被既有規則切成 3つ以上のモンスター)。"""
        self.assertEqual(modifiers("①：〈魔力〉カウンターが３つ以上のモンスターを破壊する。"),
                         [[("3つ以上", "其他")]])

    def test_archetype_versus_card_name(self):
        """「DD」モンスター 的 「DD」 是字段(引號段後面還有中心詞);「青眼の白龍」の攻撃力 的引號段接 の,是卡名、落 其他。"""
        self.assertEqual(modifiers("①：デッキから「DD」モンスター１体を手札に加える。"), [[("「DD」", "字段")]])
        self.assertEqual(modifiers("①：「HERO」融合モンスター１体を破壊する。"),
                         [[("「HERO」", "字段"), ("融合", "卡片子類型")]])
        self.assertEqual(modifiers("①：「青眼の白龍」の攻撃力を０にする。"), [[("「青眼の白龍」", "其他")]])

    def test_relative_clause_is_other_with_its_literal(self):
        self.assertEqual(modifiers("①：この効果で特殊召喚したモンスターを破壊する。"),
                         [[("この効果で特殊召喚したモンスター"[:-5], "其他")]])
        self.assertEqual(modifiers("①：相手が特殊召喚したレベル４以下のモンスターを破壊する。"),
                         [[("相手が特殊召喚した", "其他"), ("レベル4以下", "數值", "レベル", "以下", 4)]])

    def test_relative_clause_with_an_argument_absorbs_its_own_modifiers(self):
        """墓地のモンスターを対象とする効果:墓地 修飾的是子句裡的 モンスター,不是 効果——整個子句一段 其他。"""
        self.assertEqual(modifiers("①：墓地のモンスターを対象とする効果を無効にする。"),
                         [[("墓地のモンスターを対象とする", "其他")]])

    def test_igai_hoka_motomoto_nokori_are_other(self):
        self.assertEqual(modifiers("①：チューナー以外のモンスター１体を破壊する。"), [[("チューナー以外", "其他")]])
        self.assertEqual(modifiers("①：自分の墓地の表側表示モンスター以外の他のモンスターを破壊する。"),
                         [[("自分", "玩家"), ("墓地", "區域"), ("表側表示モンスター以外", "其他"), ("他", "其他")]])
        self.assertEqual(modifiers("①：元々の攻撃力を０にする。"), [[("元々", "其他")]])
        self.assertEqual(modifiers("①：残りのカードを墓地へ送る。"), [[("残り", "其他")]])
        self.assertEqual(modifiers("①：そのモンスターと同じ種族のモンスター１体を破壊する。"),
                         [[("そのモンスターと同じ種族", "其他")]])

    def test_zone_spelled_over_two_tokens_and_elided_zone_pairs(self):
        """墓地・除外状態 是兩個區域(除外|状態 兩格合起來才是區域辨識認得的字面);自分(フィールド)・相手フィールド
        的省略寫法補全後交給區域辨識。"""
        self.assertEqual(modifiers("①：自分の墓地・除外状態のモンスター１体を手札に加える。"),
                         [[("自分", "玩家"), ("墓地", "區域"), ("除外状態", "區域")]])
        self.assertEqual(modifiers("①：自分・相手フィールドのモンスター１体を破壊する。"),
                         [[("自分(フィールド)", "區域"), ("相手フィールド", "區域")]])

    def test_owner_is_a_player_and_leading_sono_is_transparent(self):
        """持ち主の手札:持ち主 沿用區域辨識的玩家前綴(相對玩家)記 玩家;その自分のモンスター 的 その自分 是指示詞
        綁在玩家詞上的一格,類照玩家詞記 玩家、字面含 その;自身の攻撃力 的 自身 指卡片自己,落 其他。"""
        self.assertEqual(modifiers("①：そのモンスターを持ち主の手札に戻す。", key="goal", action="戻す"),
                         [[("持ち主", "玩家"), ]])
        self.assertEqual(modifiers("①：その自分のモンスター１体を破壊する。"), [[("その自分", "玩家")]])
        self.assertEqual(modifiers("①：自身の攻撃力を１０００アップする。", action="アップ"), [[("自身", "其他")]])

    def test_bare_number_before_a_non_card_head_is_numeric_without_a_field(self):
        """500ダメージ、1000LP:中心詞前只有一個數,記 數值、欄位空、數字照記。"""
        self.assertEqual(modifiers("①：相手に５００ダメージを与える。"), [[("500", "數值", None, None, 500)]])

    def test_demonstrative_bound_closed_values_keep_their_kind(self):
        """その表側表示のモンスター、その融合モンスター:指示詞綁在封閉值/召喚法上的一格,類照詞記、字面含 その;
        その特殊召喚 的單獨一格 その 不是修飾語。"""
        self.assertEqual(modifiers("①：その表側表示のモンスターを破壊する。"), [[("その表側表示", "表示形式")]])
        self.assertEqual(modifiers("①：その融合モンスター１体を破壊する。"), [[("その融合", "卡片子類型")]])
        self.assertEqual(modifiers("①：その特殊召喚を無効にする。"), [[]])

    def test_joined_head_keeps_its_prefix_out_of_the_modifiers(self):
        """カード|名 合記 カード名:修飾語到 このカード 為止。"""
        self.assertEqual(modifiers("①：このカードのカード名は「青眼の白龍」として扱う。", key="topic"),
                         [[("このカード", "其他")]])


def regioned(text, context=""):
    """frame-args-v4 票 05:(動作, 來源/目的/所在的結構化值, 轉欄記號)。結構化值是
    {"source"|"goal"|"place": [[玩家, 區域七值], …]},只放算得出區域的欄;沒有時 None。"""
    return [(f["action"], f.get("regions"), f.get("transfer")) for f in actions(text, context)]


class TestV4StructuredRegions(unittest.TestCase):
    """frame-args-v4 票 05:來源/目的/所在三欄各多一個結構化值 [(玩家, 區域七值)…](依字面順序去重,
    沿用區域辨識;玩家 自分/相手/お互い/相對/無),字面欄不動;推得的欄照字面算、玩家 無;認不出區域
    的字面結構化值空。非移動類動作所在空、來源有字面時所在的結構化值取來源的、標 取自來源
    (2026-10-31 定案);移動類不轉、所在已有字面不轉。"""

    def test_source_goal_and_place_each_get_a_structured_value(self):
        self.assertEqual(
            regioned("①：自分の墓地からモンスター１体を手札に加える。"),
            [("加える", {"source": [["自分", "墓地"]], "goal": [["無", "手牌"]]}, None)])
        self.assertEqual(
            regioned("①：相手フィールドのモンスター１体を破壊する。"),
            [("破壊", {"place": [["相手", "場上"]]}, None)])

    def test_literal_columns_are_untouched(self):
        fr = actions("①：自分の手札・墓地からモンスター１体を選ぶ。")[0]
        self.assertEqual((fr["source"], fr.get("place"), fr.get("goal")), ("自分の手札・墓地", None, None))

    def test_multiple_zones_keep_literal_order(self):
        self.assertEqual(
            regioned("①：自分の手札・墓地からモンスター１体を特殊召喚する。"),
            [("特殊召喚", {"source": [["自分", "手牌"], ["自分", "墓地"]], "goal": [["無", "場上"]]}, None)])

    def test_player_prefix_is_per_zone_and_pairs_are_deduplicated(self):
        """自分フィールド・相手フィールド 是兩段(玩家不同);並列受事者各帶區域時聯集照字面順序。"""
        self.assertEqual(
            regioned("①：自分フィールド・相手フィールドのモンスターを全て破壊する。"),
            [("破壊", {"place": [["自分", "場上"], ["相手", "場上"]]}, None)])
        self.assertEqual(
            regioned("①：自分フィールドのモンスター１体と自分の墓地のモンスター１体を破壊する。"),
            [("破壊", {"place": [["自分", "場上"], ["自分", "墓地"]]}, None)])
        self.assertEqual(
            regioned("①：相手のフィールドゾーンのカードを破壊する。"),
            [("破壊", {"place": [["相手", "場上"]]}, None)])

    def test_both_players_prefix_is_spelled_otagai(self):
        self.assertEqual(
            regioned("①：お互いのフィールドのモンスターを全て破壊する。"),
            [("破壊", {"place": [["お互い", "場上"]]}, None)])

    def test_inferred_columns_are_structured_with_player_none(self):
        self.assertEqual(
            regioned("①：墓地のこのカードを除外する。"),
            [("除外", {"source": [["無", "墓地"]], "goal": [["無", "除外"]]}, None)])
        self.assertEqual(
            regioned("①：「X」１枚を捨てる。"),
            [("捨てる", {"source": [["無", "手牌"]], "goal": [["無", "墓地"]]}, None)])

    def test_unrecognized_literals_have_no_structured_value(self):
        """目的 相手、來源 その中 認不出區域:regions 整個不帶,也不轉欄。"""
        self.assertEqual(regioned("①：相手に５００ダメージを与える。"), [("与える", None, None)])
        self.assertEqual(regioned("①：その中から１枚を選ぶ。"), [("選ぶ", None, None)])

    def test_non_move_source_becomes_structured_place(self):
        """手札・墓地から選ぶ:所在字面空、結構化所在取來源的、標取自來源;來源的結構化值也在。"""
        self.assertEqual(
            regioned("①：自分の手札・墓地からモンスター１体を選ぶ。"),
            [("選ぶ", {"source": [["自分", "手牌"], ["自分", "墓地"]],
                      "place": [["自分", "手牌"], ["自分", "墓地"]]}, "取自來源")])
        self.assertEqual(
            regioned("①：デッキの上からカードを３枚めくる。"),
            [("めくる", {"source": [["無", "牌組"]], "place": [["無", "牌組"]]}, "取自來源")])

    def test_move_action_source_is_not_transferred(self):
        self.assertEqual(
            regioned("①：自分の墓地からモンスター１体を特殊召喚する。"),
            [("特殊召喚", {"source": [["自分", "墓地"]], "goal": [["無", "場上"]]}, None)])

    def test_written_place_is_not_overridden(self):
        """所在已有字面時不轉。框架抽取從不讓非移動類同時帶 から 來源與切出的所在(原文已有 から 時不切),
        全語料也沒有這種框,所以這條反例直接餵 regions.mark 一個手寫框架。"""
        import regions
        fr = {"kind": "動作", "action": "選ぶ", "object": "モンスター1体", "source": "自分の墓地",
              "place": "相手フィールド", "goal": None, "position": "效果", "polarity": "肯定"}
        regions.mark(frames.context(), [], fr)
        self.assertEqual((fr["regions"], fr.get("transfer")),
                         ({"source": [["自分", "墓地"]], "place": [["相手", "場上"]]}, None))

    def test_backfilled_place_counts_as_written(self):
        """選んで破壊する:破壊 的所在是回填來的字面,照字面算、不是轉欄。"""
        self.assertEqual(
            regioned("①：フィールドのモンスター１体を対象として発動できる。"
                     "そのモンスターを自分の墓地から選んで破壊する。")[1:],
            [("選ぶ", {"source": [["自分", "墓地"]], "place": [["自分", "墓地"]]}, "取自來源"),
             ("破壊", {"place": [["自分", "墓地"]]}, None)])


def region_backfilled(text, context=""):
    """frame-args-v4 票 09:(動作, 結構化值 regions, 回指回填記號 region_backfill, 回指欄的目標移動類旗標
    anaphora.moving);沒有的欄 None。"""
    return [(f["action"], f.get("regions"), f.get("region_backfill"), (f.get("anaphora") or {}).get("moving"))
            for f in actions(text, context)]


class TestV4AnaphoraBackfill(unittest.TestCase):
    """frame-args-v4 票 09:回指回填——受事者是指示詞、回指欄有目標且目標帶區域、回指不是事件類、
    本框缺該欄字面(移動類看來源、非移動類看所在;推得的不算有)、目標非移動類時,把目標的區域字面
    的結構化值寫進本框的 regions[來源|所在],region_backfill 記欄名,蓋過推得的同欄結構化值;字面欄
    不動;跨句號。回指欄多記 moving:目標框架(回指鏈上經過的框架任一)是不是移動類;目標不是框架
    (字面備援)時 false。"""

    def test_non_move_target_fills_source_of_move_frame(self):
        """對象として…。そのモンスターを特殊召喚する:特殊召喚 的來源結構化值是目標的 (自分, 墓地)。"""
        self.assertEqual(
            region_backfilled("①：自分の墓地のモンスター１体を対象として発動できる。そのモンスターを特殊召喚する。")[1],
            ("特殊召喚", {"source": [["自分", "墓地"]], "goal": [["無", "場上"]]}, "source", False))

    def test_non_move_target_fills_place_of_non_move_frame(self):
        self.assertEqual(
            region_backfilled("①：相手フィールドのモンスター１体を対象として発動できる。そのモンスターを破壊する。")[1],
            ("破壊", {"place": [["相手", "場上"]]}, "place", False))

    def test_literal_columns_are_untouched(self):
        fr = actions("①：相手フィールドのモンスター１体を対象として発動できる。そのモンスターを破壊する。")[1]
        self.assertEqual((fr.get("place"), fr.get("source"), fr.get("backfill")), (None, None, None))

    def test_move_target_is_rejected(self):
        """手札に加える…そのモンスターを破壊する:目標是移動類(卡已經不在墓地),不填、旗標 true。"""
        self.assertEqual(
            region_backfilled("①：自分の墓地のモンスター１体を手札に加える。その後、そのモンスターを破壊する。")[1],
            ("破壊", None, None, True))

    def test_own_literal_is_not_overridden(self):
        """本框自己寫了 墓地から:來源照自己的字面(玩家 無),不回填。"""
        self.assertEqual(
            region_backfilled("①：自分の墓地のモンスター１体を対象として発動できる。"
                              "そのモンスターを墓地から特殊召喚する。")[1],
            ("特殊召喚", {"source": [["無", "墓地"]], "goal": [["無", "場上"]]}, None, False))

    def test_backfilled_literal_counts_as_written(self):
        """選んで破壊する:破壊 的所在是回填來的字面,算有字面,不回填。"""
        self.assertEqual(
            region_backfilled("①：フィールドのモンスター１体を対象として発動できる。"
                              "そのモンスターを自分の墓地から選んで破壊する。")[2],
            ("破壊", {"place": [["自分", "墓地"]]}, None, False))

    def test_transferred_place_counts_as_written(self):
        """そのモンスターを自分のデッキから選ぶ:非移動類本框的所在是取自來源轉欄來的(自己的字面),不回填。"""
        self.assertEqual(
            region_backfilled("①：自分の墓地のモンスター１体を対象として発動できる。"
                              "そのモンスターを自分のデッキから選ぶ。")[1],
            ("選ぶ", {"source": [["自分", "牌組"]], "place": [["自分", "牌組"]]}, None, False))

    def test_backfill_overrides_inferred_source(self):
        """手札のモンスターを見せ、そのカードを捨てる:捨てる 推得的來源 (無, 手牌) 被目標的 (自分, 手牌) 蓋過;
        字面欄仍是推得的 手札。"""
        frs = actions("①：自分の手札のモンスター１体を相手に見せ、そのカードを捨てる。")
        self.assertEqual(
            (frs[1]["action"], frs[1]["regions"], frs[1]["region_backfill"]),
            ("捨てる", {"source": [["自分", "手牌"]], "goal": [["無", "墓地"]]}, "source"))
        self.assertEqual((frs[1]["source"], frs[1]["inferred"]), ("手札", ["source", "goal"]))

    def test_across_full_stops(self):
        self.assertEqual(
            region_backfilled("①：自分の墓地のモンスター１体を対象として発動できる。このカードを特殊召喚する。"
                              "その後、そのモンスターを破壊する。")[2],
            ("破壊", {"place": [["自分", "墓地"]]}, "place", False))

    def test_event_target_is_not_backfilled(self):
        """その発動を無効にし:回指是事件類,沒有區域可填;目標 発動 不是移動類。"""
        self.assertEqual(
            region_backfilled("①：相手フィールドの魔法カードが発動した時に発動できる。その発動を無効にし破壊する。")[1],
            ("無効にする", None, None, False))

    def test_chain_through_a_move_frame_is_rejected(self):
        """対象として…。そのモンスターを特殊召喚する。その後、そのモンスターを破壊する:破壊 的回指是經
        特殊召喚 解到底的,鏈上有移動類 → 旗標 true、不填;特殊召喚 自己照填來源。"""
        frs = region_backfilled("①：自分の墓地のモンスター１体を対象として発動できる。そのモンスターを特殊召喚する。"
                                "その後、そのモンスターを破壊する。")
        self.assertEqual(frs[1], ("特殊召喚", {"source": [["自分", "墓地"]], "goal": [["無", "場上"]]}, "source", False))
        self.assertEqual(frs[2], ("破壊", None, None, True))

    def test_literal_target_is_not_a_frame(self):
        """墓地のモンスターが３体以上の場合…そのモンスター１体を特殊召喚する:目標從字面備援找到,沒有框架
        → 旗標 false,照填來源。"""
        self.assertEqual(
            region_backfilled("①：自分の墓地のモンスターが３体以上の場合に発動できる。そのモンスター１体を特殊召喚する。")[0],
            ("特殊召喚", {"source": [["自分", "墓地"]], "goal": [["無", "場上"]]}, "source", False))

    def test_target_without_region_is_not_backfilled(self):
        """相手の墓地にモンスターが存在する…そのモンスター１体を特殊召喚:目標沒有區域,不填、旗標 false。"""
        self.assertEqual(
            region_backfilled("①：相手の墓地にモンスターが存在する場合に発動できる。"
                              "そのモンスター１体を自分フィールドに特殊召喚する。")[1],
            ("特殊召喚", {"goal": [["自分", "場上"]]}, None, False))


def negations(text, context=""):
    """框架 → (動作, 極性, 否定形):frame-args-v4 票 08 的否定形欄;沒有值時 None。"""
    return [(f["action"], f["polarity"], f.get("negation")) for f in actions(text, context)]


class TestNegationForm(unittest.TestCase):
    """frame-args-v4 票 08:否定框架加封閉類欄 否定形(受身/不成不受/不可能/一般)。態 受身 → 受身;
    否則看述語自己的否定形;肯定與可能框架沒有這一格。"""

    def test_passive_negation_is_passive(self):
        self.assertEqual(negations("①：このカードは戦闘では破壊されない。"),
                         [("破壊", "否定", "受身")])

    def test_ni_naranai_is_not_become(self):
        self.assertEqual(negations("①：このカードは相手の効果の対象にならない。"),
                         [("対象にする", "否定", "不成不受")])

    def test_ukenai_is_not_receive(self):
        self.assertEqual(negations("①：このカードは相手の効果を受けない。"),
                         [("受ける", "否定", "不成不受")])

    def test_dekinai_is_cannot(self):
        self.assertEqual(negations("①：このカードは攻撃できない。"), [("攻撃", "否定", "不可能")])

    def test_okonaenai_is_cannot(self):
        self.assertEqual(negations("①：このターン、自分は通常召喚を行えない。"),
                         [("通常召喚", "否定", "不可能")])

    def test_plain_zu_is_general(self):
        """送らず 是一般否定;後面的肯定框架沒有這一格。"""
        self.assertEqual(negations("①：発動後、このカードは墓地へ送らず、そのままセットする。"),
                         [("送る", "否定", "一般"), ("セット", "肯定", None)])

    def test_potential_has_no_negation_form(self):
        self.assertEqual(negations("①：相手フィールドのカード１枚を選んで破壊できる。"),
                         [("選ぶ", "肯定", None), ("破壊", "可能", None)])

    def test_nakereba_naranai_is_obligation_not_negation(self):
        """〜しなければならない 是義務:極性不是否定,沒有否定形。"""
        self.assertEqual(negations("①：このカードは攻撃可能な場合、攻撃しなければならない。"),
                         [("攻撃", "肯定", None)])

    def test_de_nakereba_naranai_is_not_naranai(self):
        """Xでなければならない 的 ならない 不是 にならない:不記 不成不受(極性 否定 是上游既有判法,
        這裡只管否定形)。"""
        self.assertEqual(negations("①：融合素材モンスターは全てアンデット族モンスターでなければならない。"),
                         [("なる", "否定", "一般")])

    def test_passive_wins_over_literal_in_clause(self):
        """受身優先於字面:定語裡的 受けない/できない 不改被動否定的否定形。"""
        self.assertEqual(negations("①：このカードは効果を受けないモンスターには攻撃されない。"),
                         [("攻撃", "否定", "受身")])
        self.assertEqual(negations("①：このカードは攻撃できないモンスターとの戦闘では破壊されない。"),
                         [("破壊", "否定", "受身")])

    def test_negation_form_in_condition_position(self):
        self.assertEqual(negations("①：このカードが相手の効果の対象にならない場合に発動できる。")[0],
                         ("対象にする", "否定", "不成不受"))


def agents(text, context=""):
    """框架 → (動作, 施事者, 來源, 推得旗標):frame-args-v4 票 07 的施事者欄;沒有值時 None/None/False。"""
    return [(f["action"], f.get("agent"), f.get("agent_source"), bool(f.get("agent_inferred")))
            for f in actions(text, context)]


class TestV4Agent(unittest.TestCase):
    """frame-args-v4 票 07:施事者(自分/相手/お互い/此卡/其他卡)與來源(主題/主語/事件主語/によって/預設)。
    (1)主題或主語是玩家 → 該玩家(受身除外);是 このカード(含帶定語)或卡片片語 → 此卡/其他卡,只在框架
    自己帶對象時(受身、自動、沒對象的 このカード 是受事者)。"""

    def test_topic_player_is_agent(self):
        """自分はデッキから１枚ドローする:沒對象也記——ドロー 的執行者由主題給。"""
        self.assertEqual(agents("①：自分はデッキから１枚ドローする。"), [("ドロー", "自分", "主題", False)])

    def test_topic_opponent_and_both(self):
        self.assertEqual(agents("①：相手は手札を１枚捨てる。"), [("捨てる", "相手", "主題", False)])
        self.assertEqual(agents("①：お互いはデッキから１枚ドローする。"), [("ドロー", "お互い", "主題", False)])

    def test_subject_player_in_condition(self):
        """相手がモンスターを特殊召喚した時:條件框架的主語是玩家 → 相手(主語)。"""
        self.assertEqual(agents("①：相手がモンスターを特殊召喚した時に発動できる。")[0],
                         ("特殊召喚", "相手", "主語", False))

    def test_this_card_with_object_is_agent(self):
        self.assertEqual(agents("①：このカードが相手モンスターを攻撃した場合に発動できる。")[0],
                         ("攻撃", "此卡", "主語", False))
        self.assertEqual(agents("①：このカードは相手フィールドのモンスター１体を破壊する。"),
                         [("破壊", "此卡", "主題", False)])

    def test_this_card_with_modifier_is_agent(self):
        """墓地のこのカード、S召喚したこのカード:帶定語的此卡仍是此卡。"""
        self.assertEqual(agents("①：S召喚したこのカードが相手モンスターを攻撃した場合に発動できる。")[0],
                         ("攻撃", "此卡", "主語", False))

    def test_passive_this_card_is_not_agent(self):
        """このカードは破壊されない:受身的主題是承受方,沒有施事者。"""
        self.assertEqual(agents("①：このカードは戦闘では破壊されない。"), [("破壊", None, None, False)])

    def test_this_card_without_object_is_patient(self):
        """墓地のこのカードは手札に戻す事ができる:他動但沒對象,主題是受事者。"""
        self.assertEqual(agents("①：墓地のこのカードは手札に戻す事ができる。"), [("戻す", None, None, False)])

    def test_card_phrase_is_other_card(self):
        """主語是卡片片語(中心詞類 卡)且帶對象 → 其他卡。"""
        self.assertEqual(agents("①：相手モンスターがこのカードを攻撃した場合に発動できる。")[0],
                         ("攻撃", "其他卡", "主語", False))
        self.assertEqual(agents("①：装備モンスターは相手モンスター１体を破壊する。"),
                         [("破壊", "其他卡", "主題", False)])

    def test_player_noun_topic(self):
        """お互いのプレイヤーは…:玩家名詞帶玩家 → 該玩家;分不出哪個玩家的(ターンプレイヤー)留空、不補預設。"""
        self.assertEqual(agents("①：お互いのプレイヤーはデッキから１枚ドローする。"),
                         [("ドロー", "お互い", "主題", False)])
        self.assertEqual(agents("①：ターンプレイヤーは手札を１枚捨てる。"), [("捨てる", None, None, False)])

    def test_continued_topic_is_used(self):
        """延續來的主題(回填 topic)照用:自分は…ドローし、その後手札を１枚捨てる。"""
        self.assertEqual(agents("①：自分はデッキから２枚ドローし、その後手札を１枚捨てる。"),
                         [("ドロー", "自分", "主題", False), ("捨てる", "自分", "主題", False)])


class TestV4AgentNiyotte(unittest.TestCase):
    """frame-args-v4 票 07 (2):受身框架(與態空/自動且沒對象的框架)讀子句裡的 によって 片語——玩家或玩家起頭
    → 該玩家、卡片片語 → 其他卡、指名此卡 → 此卡,其他不記;定語裡的 によって 不讀。"""

    def test_player_effect_niyotte(self):
        self.assertEqual(agents("①：このカードが相手の効果によって破壊された場合に発動できる。")[0],
                         ("破壊", "相手", "によって", False))

    def test_bare_player_niyotte_on_intransitive(self):
        """相手によってフィールドから離れた:態空、沒對象的自動詞框架也讀 によって。"""
        self.assertEqual(agents("①：このカードが相手によってフィールドから離れた場合に発動できる。")[0],
                         ("離れる", "相手", "によって", False))

    def test_card_effect_niyotte_is_other_card(self):
        self.assertEqual(agents("①：このカードがカードの効果によって破壊された場合に発動できる。")[0],
                         ("破壊", "其他卡", "によって", False))

    def test_this_card_effect_niyotte(self):
        self.assertEqual(agents("①：相手フィールドのモンスターがこのカードの効果によって破壊された場合に発動できる。")[0],
                         ("破壊", "此卡", "によって", False))

    def test_non_agent_niyotte_is_not_recorded(self):
        """出た目によって/数によって:不是施事者,不記。"""
        self.assertEqual(agents("①：このカードがコイントスの結果によって破壊された場合に発動できる。")[0],
                         ("破壊", None, None, False))
        self.assertEqual(agents("①：自分の墓地のモンスターの数によって以下の効果を適用する。"),
                         [("適用", "自分", "預設", True)])

    def test_attributive_niyotte_is_not_read(self):
        """融合モンスターカードによって決められた融合素材モンスターを墓地へ送り:によって 在定語裡,框架自己帶對象
        → 預設 自分。"""
        found = agents("①：自分の手札・フィールドから、融合モンスターカードによって決められた融合素材モンスターを墓地へ送り、"
                       "その融合モンスター１体をEXデッキから融合召喚する。")
        self.assertEqual(found[0], ("送る", "自分", "預設", True))


class TestV4AgentEventAndDefault(unittest.TestCase):
    """frame-args-v4 票 07 (3)(4):效果類事件框架讀回指欄的事件主語;一般受事者的回指事件主語不用。預設只補
    代價/效果位、態不是受身/自動、帶對象的框架(自分、推得);條件位、受身、自動、沒對象留空;「この効果は」註記
    不是施事者。"""

    def test_event_owner_is_not_agent_of_negation(self):
        """相手がモンスターの効果を発動した時…その発動を無効にし破壊する:発動 的主語是 相手;無効にする 與 破壊
        的回指事件主語(相手)是目標的來歷,不是施事者 → 無効にする 預設 自分;破壊 沒有自己的對象,留空。"""
        self.assertEqual(agents("①：相手がモンスターの効果を発動した時に発動できる。その発動を無効にし破壊する。"),
                         [("発動", "相手", "主語", False), ("無効にする", "自分", "預設", True),
                          ("破壊", None, None, False)])

    def test_anaphora_event_subject_not_used_for_patient(self):
        """相手がモンスターを特殊召喚した時…そのモンスターを破壊する:破壊 不是 相手 做的 → 預設 自分。"""
        self.assertEqual(agents("①：相手がモンスターを特殊召喚した時に発動できる。そのモンスターを破壊する。"),
                         [("特殊召喚", "相手", "主語", False), ("破壊", "自分", "預設", True)])

    def test_default_self_in_effect(self):
        self.assertEqual(agents("①：デッキからモンスター１体を手札に加える。"), [("加える", "自分", "預設", True)])

    def test_default_self_in_cost(self):
        self.assertEqual(agents("①：手札を１枚捨てて発動できる。")[0], ("捨てる", "自分", "預設", True))

    def test_no_default_in_condition(self):
        self.assertEqual(agents("①：モンスターを特殊召喚した場合に発動できる。")[0], ("特殊召喚", None, None, False))

    def test_no_default_for_intransitive_or_passive_or_objectless(self):
        self.assertEqual(agents("①：このカードの攻撃力は５００アップする。"), [("アップ", None, None, False)])
        self.assertEqual(agents("①：このカードは戦闘では破壊されない。"), [("破壊", None, None, False)])
        self.assertEqual(agents("①：デッキから１枚ドローする。"), [("ドロー", None, None, False)])

    def test_this_effect_note_topic_is_not_agent(self):
        """この効果は相手ターンでも発動できる:註記主題,上游已排除、沒有帶施事者的框架。"""
        found = agents("①：自分フィールドのモンスター１体を選んで破壊する。この効果は相手ターンでも発動できる。")
        self.assertEqual([a for a in found if a[0] == "発動"], [])
        self.assertEqual(found[:2], [("選ぶ", "自分", "預設", True), ("破壊", "自分", "預設", True)])


def quantities(text, key="object", action=None, context=""):
    """票 04 的接縫輔助:第一個(指定動作的)動作框架該欄的論元片語 → 各段的數量
    (字面, 數量類, 數字, 取自子句),沒有數量的段是 None;該欄沒有片語時 None。"""
    frame = next(f for f in actions(text, context) if action is None or f["action"] == action)
    phrase = (frame.get("phrases") or {}).get(key)
    if phrase is None:
        return None
    return [None if s.get("quantity") is None else
            (s["quantity"]["text"], s["quantity"]["kind"], s["quantity"]["number"], s["quantity"]["from_clause"])
            for s in phrase["segments"]]


class TestArgumentPhraseQuantity(unittest.TestCase):
    """frame-args-v4 票 04:每段的數量——段尾的 數字+量詞(+まで/以上)→ 定數/上限/下限 帶數字、全て → 全部、
    任意の数/好きな数 → 任意;引用量(数まで/同じ数/数の分だけ)只記字面、類空;受事者字面沒有數量而子句裡
    緊接受事者的 を+數量 取進那段、標取自子句;それぞれ、ターン終了時まで、５つ上がる、修飾語裡的數值不算。
    只斷言輸出框架 phrases 各段的 quantity。"""

    def test_fixed_count_at_segment_tail(self):
        self.assertEqual(quantities("①：相手フィールドのモンスター１体を破壊する。"), [("1体", "定數", 1, False)])

    def test_upper_bound_made_is_in_the_literal_already(self):
        """手札を２枚まで捨てる:框架抽取已把 ２枚まで 併回對象字面,段尾就是上限。"""
        self.assertEqual(quantities("①：手札を２枚まで捨てる。"), [("2枚まで", "上限", 2, False)])

    def test_lower_bound_ijou(self):
        self.assertEqual(quantities("①：自分フィールドのモンスター１体以上を除外して発動できる。"),
                         [("1体以上", "下限", 1, False)])

    def test_subete_at_goal_tail_is_all(self):
        self.assertEqual(quantities("②：このカードは相手モンスター全てに１回ずつ攻撃できる。", key="goal"),
                         [("全て", "全部", None, False)])

    def test_each_coordinated_segment_has_its_own_count(self):
        self.assertEqual(quantities("①：墓地のモンスター１体と手札のカード２枚を除外する。"),
                         [("1体", "定數", 1, False), ("2枚", "定數", 2, False)])

    def test_numeric_modifier_before_the_head_is_not_a_quantity(self):
        """カウンターが３つ以上のこのカード:３つ以上 是修飾語裡的數值,不是這段的數量。"""
        self.assertEqual(quantities("①：カウンターが３つ以上のこのカードを墓地へ送る。"), [None])

    def test_sorezore_is_not_a_quantity(self):
        self.assertEqual(quantities("①：自分フィールドのモンスターの攻撃力はそれぞれ３００アップする。", key="topic"),
                         [None])

    def test_other_numbers_in_the_clause_are_not_quantities(self):
        """ターン終了時まで、５つ上がる:不是 を 後緊接受事者的數量。"""
        self.assertEqual(quantities("①：このカードの攻撃力はターン終了時まで５００アップする。", key="topic"), [None])
        self.assertEqual(quantities("①：このカードのレベルは５つ上がる。", key="topic"), [None])
        self.assertEqual(quantities("①：このカードの攻撃力を５００アップする。"), [None])

    def test_count_right_after_wo_is_taken_from_the_clause(self):
        """手札を１枚捨てる:受事者字面沒有數量,子句裡緊接 を 的 １枚 取進這段、標取自子句。"""
        self.assertEqual(quantities("①：手札を１枚捨てる。"), [("1枚", "定數", 1, True)])

    def test_subete_after_wo_is_all_from_the_clause(self):
        self.assertEqual(quantities("①：相手フィールドのカードを全て破壊する。"), [("全て", "全部", None, True)])

    def test_nin_i_no_kazu_after_wo_is_any(self):
        self.assertEqual(quantities("①：手札のカードを任意の数選んで捨てる。", action="選ぶ"),
                         [("任意の数", "任意", None, True)])
        self.assertEqual(quantities("①：手札を任意の枚数捨てる。"), [("任意の枚数", "任意", None, True)])

    def test_nin_i_no_kazu_after_a_source_phrase_is_still_any(self):
        """をデッキから任意の数だけ:來源片語夾在中間,數量仍是 任意(字面只記 任意の数)。"""
        self.assertEqual(quantities("①：「X」モンスターをデッキから任意の数だけ選んで手札に加える。", action="選ぶ"),
                         [("任意の数", "任意", None, True)])

    def test_reference_quantities_keep_the_literal_with_no_kind(self):
        """その数まで、同じ数だけ、数の分だけ:引用量只記字面、類空(それぞれ 不進字面)。"""
        self.assertEqual(quantities("①：墓地のモンスターをその数まで特殊召喚する。"), [("その数まで", None, None, True)])
        self.assertEqual(quantities("①：相手フィールドのカードをその数の分だけ破壊する。"),
                         [("その数の分だけ", None, None, True)])
        self.assertEqual(
            quantities("①：自分の墓地の「閃刀姫」モンスターと「閃刀」魔法カードをそれぞれ同じ数だけ対象として発動できる。"),
            [None, ("同じ数だけ", None, None, True)])

    def test_backfilled_object_takes_the_count_from_the_providing_clause(self):
        """手札を１枚選んで捨てる:捨てる 的對象是回填來的,數量寫在 選ぶ 的子句裡,兩框都帶。"""
        text = "①：手札を１枚選んで捨てる。"
        self.assertEqual(quantities(text, action="選ぶ"), [("1枚", "定數", 1, True)])
        self.assertEqual(quantities(text, action="捨てる"), [("1枚", "定數", 1, True)])

    def test_random_ni_and_sorezore_may_stand_between_wo_and_the_count(self):
        self.assertEqual(quantities("①：相手の手札をランダムに１枚選んで捨てる。", action="選ぶ"),
                         [("1枚", "定數", 1, True)])
        self.assertEqual(
            quantities("①：自分及び相手の墓地の同じランクのXモンスターをそれぞれ１体以上対象として発動できる。"),
            [("1体以上", "下限", 1, True)])

    def test_zutsu_is_part_of_the_count_literal(self):
        self.assertEqual(
            quantities("②：このカード以外の光・闇属性モンスターを１体ずつ、自分の手札・墓地から除外して発動できる。"),
            [("1体ずつ", "定數", 1, True)])

    def test_count_in_another_clause_is_not_taken(self):
        """手札を１枚捨てる。その後、…カードを１枚墓地へ送る:各框只看自己(或提供對象)的子句。"""
        text = "①：手札を１枚捨てる。その後、デッキからカードを１枚墓地へ送る。"
        self.assertEqual(quantities(text, action="捨てる"), [("1枚", "定數", 1, True)])
        self.assertEqual(quantities(text, action="送る"), [("1枚", "定數", 1, False)])

    def test_counter_outside_the_closed_list_is_not_a_quantity(self):
        self.assertEqual(quantities("①：相手の魔法＆罠ゾーンを１ヵ所指定して発動できる。"), [None])


def mannered(text, context=""):
    """框架 → (動作, 方式字面, 方式類, 表示形式值):frame-args-v4 票 06 的方式欄;沒有值時 None。"""
    return [(f["action"], f.get("manner"), f.get("manner_kind"), f.get("manner_value"))
            for f in actions(text, context)]


class TestManner(unittest.TestCase):
    """frame-args-v4 票 06:述語前同一子句內的 で 片語是方式(字面含 で、不含 は/も 後綴),配封閉類
    方式類(手段:效果/手段:戰鬥/手段:方法/表示形式(另帶值)/視同/順序/其他);一框至多一個、取離述語
    最近的。定語裡的 で(並列修飾、定語子句裡的 で)與繫詞 で 不是方式;で 接區域不是方式,進結構化
    所在、標 取自で(2026-10-31 定案)。戦闘・効果で 一族原本落 其他,依 2026-11-01 站主裁定改記
    手段:戰鬥或效果(兩條例子的預期跟著改,規則例子在 TestV4Decisions)。"""

    def test_battle_is_means_battle(self):
        self.assertEqual(mannered("①：このカードが戦闘で破壊された場合に発動できる。")[0],
                         ("破壊", "戦闘で", "手段:戰鬥", None))

    def test_de_wa_suffix_is_not_part_of_the_literal(self):
        self.assertEqual(mannered("①：このカードは戦闘では破壊されない。"),
                         [("破壊", "戦闘で", "手段:戰鬥", None)])

    def test_this_effect_is_means_effect(self):
        self.assertEqual(mannered("①：この効果でカードを２枚破壊できなかった場合、自分は１０００ダメージを受ける。")[0],
                         ("破壊", "この効果で", "手段:效果", None))

    def test_this_method_is_means_method(self):
        self.assertEqual(mannered("①：このカードはこの方法でのみ特殊召喚できる。"),
                         [("特殊召喚", "この方法で", "手段:方法", None)])

    def test_display_form_carries_its_value(self):
        self.assertEqual(mannered("①：デッキからレベル４以下のモンスター１体を守備表示で特殊召喚する。"),
                         [("特殊召喚", "守備表示で", "表示形式", "守備表示")])

    def test_leading_quantity_adverb_belongs_to_the_object(self):
        """全て 是對象的數量,不進方式字面。"""
        self.assertEqual(mannered("①：相手の手札を全て裏側表示で除外する。"),
                         [("除外", "裏側表示で", "表示形式", "裏側表示")])

    def test_shorthand_display_form_is_a_display_form(self):
        """表側/裏側 是規格方式段列的縮略寫法,分詞封閉值域 表示形式 沒有它們(code review 第 5 條:值域改從
        extract_seed.CLOSED_VALUES 取,兩個縮略寫法另列),仍是 表示形式、值是字面。"""
        self.assertEqual(mannered("①：デッキからモンスター１体を表側で特殊召喚する。"),
                         [("特殊召喚", "表側で", "表示形式", "表側")])
        self.assertEqual(mannered("①：相手の手札を裏側で除外する。"),
                         [("除外", "裏側で", "表示形式", "裏側")])

    def test_coordinated_display_forms_keep_the_whole_phrase(self):
        self.assertEqual(mannered("①：そのモンスターを表側守備表示または裏側守備表示で特殊召喚する。"),
                         [("特殊召喚", "表側守備表示または裏側守備表示で", "表示形式",
                           "表側守備表示または裏側守備表示")])

    def test_treated_as_is_regarded(self):
        found = mannered("①：自分の墓地のモンスター１体を対象として発動できる。"
                         "そのモンスターを装備カード扱いでこのカードに装備する。")
        self.assertEqual(found[-1], ("装備", "装備カード扱いで", "視同", None))

    def test_order_phrase_is_order(self):
        found = mannered("①：自分の墓地のカード３枚を対象として発動できる。そのカードを好きな順番でデッキの上に戻す。")
        self.assertEqual(found[-1], ("戻す", "好きな順番で", "順序", None))

    def test_nashi_de_is_other_with_literal(self):
        self.assertEqual(mannered("①：このカードはリリースなしで召喚できる。"),
                         [("召喚", "リリースなしで", "其他", None)])

    def test_battle_or_effect_coordination_is_battle_or_effect(self):
        """戦闘・効果で:兩類並列,記 手段:戰鬥或效果、字面保留(票 06 時落 其他;2026-11-01 裁定改)。"""
        self.assertEqual(mannered("①：フィールドのこのカードが戦闘・効果で破壊された場合に発動できる。")[0],
                         ("破壊", "戦闘・効果で", "手段:戰鬥或效果", None))

    def test_attributive_coordination_de_is_not_manner(self):
        """攻撃力2400以上で守備力1000の:定語裡的並列修飾。"""
        self.assertEqual(mannered("①：自分の墓地の攻撃力２４００以上で守備力１０００のモンスター１体を対象として発動できる。")[0],
                         ("対象とする", None, None, None))
        self.assertEqual(mannered("①：デッキから戦士族・ドラゴン族で光属性のモンスター１体を手札に加える。"),
                         [("加える", None, None, None)])

    def test_de_inside_relative_clause_is_not_manner(self):
        """この効果で特殊召喚したモンスター 的 で 屬定語子句,不是主述語的方式。"""
        self.assertEqual(mannered("①：この効果で特殊召喚したモンスターの効果は無効化される。"),
                         [("無効にする", None, None, None)])

    def test_copula_de_is_not_manner(self):
        self.assertEqual(mannered("①：融合素材モンスターは全てアンデット族モンスターでなければならない。"),
                         [("なる", None, None, None)])
        self.assertEqual(mannered("①：自分の手札が０枚ではない場合、このカードは墓地へ送られる。")[-1],
                         ("送る", None, None, None))

    def test_nearest_de_phrase_wins(self):
        self.assertEqual(mannered("①：デッキからレベル４以下のモンスター１体をこの効果で守備表示で特殊召喚する。"),
                         [("特殊召喚", "守備表示で", "表示形式", "守備表示")])

    def test_zone_de_goes_to_structured_place_as_transfer(self):
        text = "①：このカードがPゾーンで破壊された場合に発動できる。"
        self.assertEqual(mannered(text)[0], ("破壊", None, None, None))
        self.assertEqual(regioned(text)[0], ("破壊", {"place": [["無", "靈擺區"]]}, "取自で"))
        self.assertIsNone(actions(text)[0].get("place"))
        found = regioned("①：自分の永続罠カードが相手フィールドで効果を発動した場合に発動できる。")[0]
        self.assertEqual(found, ("発動", {"place": [["相手", "場上"]]}, "取自で"))

    def test_zone_de_does_not_override_a_literal_place(self):
        """字面所在已有值:で 接的區域不轉、不標。"""
        self.assertEqual(regioned("①：自分フィールドのモンスターがモンスターゾーンで破壊された場合に発動できる。")[0],
                         ("破壊", {"place": [["自分", "場上"]]}, None))

    def test_zone_de_does_not_override_source_transfer(self):
        """已 取自來源 的結構化所在不被 取自で 蓋掉(全語料沒有兩者同框的句子,直接餵手寫框架)。"""
        import regions
        fr = {"action": "選ぶ", "object": "カード１枚", "source": "自分の墓地", "goal": None,
              "position": "效果", "polarity": "肯定", "regions": {"source": [["自分", "墓地"]],
                                                                 "place": [["自分", "墓地"]]},
              "transfer": "取自來源"}
        regions.place_from_de(fr, "フィールド")
        self.assertEqual((fr["regions"]["place"], fr["transfer"]), ([["自分", "墓地"]], "取自來源"))

    def test_non_zone_de_is_still_manner(self):
        """同じ縦列 不是區域七值:仍是方式、落 其他。"""
        self.assertEqual(mannered("①：このカードと同じ縦列で魔法・罠カードが発動した場合に発動できる。")[0],
                         ("発動", "同じ縦列で", "其他", None))

    def test_mama_de_is_other_with_literal(self):
        self.assertEqual(mannered("①：このカードは表側守備表示のままで攻撃できる。"),
                         [("攻撃", "表側守備表示のままで", "其他", None)])

    def test_igai_de_is_other_not_attributive(self):
        self.assertEqual(mannered("①：自分のモンスターが戦闘以外で墓地へ送られた場合に発動できる。")[0],
                         ("送る", "戦闘以外で", "其他", None))

    def test_coordinated_modifier_takes_the_head_kind(self):
        """魔法・罠カードの効果で:・ 並列的是修飾語,類看中心的 効果(省略格的字面照分詞器寫法 魔法(カード))。"""
        self.assertEqual(mannered("①：魔法・罠カードの効果で、EXデッキからモンスターが特殊召喚された場合に発動できる。")[0],
                         ("特殊召喚", "魔法(カード)・罠カードの効果で", "手段:效果", None))

    def test_ka_coordinated_display_forms(self):
        self.assertEqual(mannered("①：そのモンスターを表側攻撃表示か裏側守備表示で特殊召喚する。"),
                         [("特殊召喚", "表側攻撃表示か裏側守備表示で", "表示形式", "表側攻撃表示か裏側守備表示")])

    def test_battle_or_effect_alternatives_are_battle_or_effect(self):
        """票 06 時落 其他;2026-11-01 裁定改記 手段:戰鬥或效果。"""
        self.assertEqual(mannered("①：このカードが戦闘または相手の効果で破壊された場合に発動できる。")[0],
                         ("破壊", "戦闘または相手の効果で", "手段:戰鬥或效果", None))

    def test_relative_clause_after_a_comma_does_not_swallow_the_de_phrase(self):
        """扱いで、 後面另一個論元裡的定語子句(この効果で特殊召喚したモンスターに)不影響前面的 扱いで。"""
        found = mannered("①：デッキからモンスター１体を装備魔法カード扱いで、この効果で特殊召喚したモンスターに装備する。")
        self.assertEqual(found[-1], ("装備", "装備魔法カード扱いで", "視同", None))


class TestV4Round1Fixes(unittest.TestCase):
    """frame-args-v4 票 10:v4-round1 LLM 抽驗抓到的同型錯,各一條回歸例子(先失敗再修)。只斷言輸出框架的
    phrases 欄(段、中心詞、玩家、區域、修飾語、數量)。"""

    def test_adnominal_compare_after_a_case_particle_closes_the_clause(self):
        """数値が同じ機械族モンスター:同じ 前有格助詞(が),是定語子句的述語,之後是新的修飾語段;
        同じ種族 這種連體用法(前面沒有格助詞)仍是同一個修飾語。"""
        self.assertEqual(modifiers("①：攻撃力と守備力の数値が同じ機械族モンスター１体を特殊召喚する。"),
                         [[("攻撃力と守備力の数値が同じ", "其他"), ("機械族", "種族")]])
        self.assertEqual(modifiers("①：見せたモンスターとは種族と属性が異なる儀式モンスター１体を手札に加える。"),
                         [[("見せた", "其他"), ("モンスターとは種族と属性が異なる", "其他"), ("儀式", "卡片子類型")]])
        self.assertEqual(modifiers("①：そのモンスターと同じ種族のモンスター１体を破壊する。"),
                         [[("そのモンスターと同じ種族", "其他")]])

    def test_dot_run_followed_by_no_is_one_segment(self):
        """魔法・罠・モンスターの効果:整串 ・ 並列修飾 効果,看的是整串之後有沒有 の,不是下一個 ・ 之前;
        自分の手札・デッキ・墓地・除外状態の「ユベル」 同理一段、四個區域。魔法・罠カード１枚 後面沒有 の,照切兩段。"""
        self.assertEqual([s[1] for s in segments("①：魔法・罠・モンスターの効果を発動できない。")], ["効果"])
        self.assertEqual(segments("①：自分の手札・デッキ・墓地・除外状態の「ユベル」１体を選んで特殊召喚する。"),
                         [("自分の手札・デッキ・墓地・除外状態の「ユベル」1体", "「ユベル」", "卡", False, "自分",
                           ["手牌", "牌組", "墓地", "除外"])])
        self.assertEqual([s[1] for s in segments("①：魔法・罠カード１枚を破壊する。")], ["魔法カード", "罠カード"])

    def test_coordinator_inside_an_attributive_clause_does_not_split(self):
        """「A」と「B」となるモンスター:と 夾在定語子句(カード名が…となる)裡面,不是受事者的並列;
        及び墓地へ送ったカードとは種類が異なる…カード 同理。このカードと相手フィールドのモンスター１体 照切兩段。"""
        self.assertEqual([s[1] for s in segments(
            "①：元々のカード名が「ブラック・マジシャン」と「ブラック・マジシャン・ガール」となるモンスター１体を特殊召喚する。")],
            ["モンスター"])
        self.assertEqual([s[1] for s in segments(
            "①：対象のカード及び墓地へ送ったカードとは種類が異なる「電脳堺媛－瑞々」以外の「電脳堺」カード１枚を手札に加える。")],
            ["カード"])
        self.assertEqual([s[1] for s in segments("①：このカードと相手フィールドのモンスター１体を破壊する。")],
                         ["カード", "モンスター"])

    def test_dot_inside_a_parenthesis_does_not_split(self):
        """種類（モンスター・魔法・罠）が異なる「電脳堺」カード:括號註記裡的 ・ 不是受事者的並列;一段,「電脳堺」是字段。"""
        text = "①：そのカードとは種類（モンスター・魔法・罠）が異なる「電脳堺」カード１枚を手札に加える。"
        self.assertEqual([s[1] for s in segments(text)], ["カード"])
        self.assertEqual(modifiers(text), [[("そのカードとは種類（モンスター・魔法・罠）が異なる", "其他"), ("「電脳堺」", "字段")]])

    def test_numeric_item_inside_a_mixed_dot_list(self):
        """ドラゴン族・レベル８モンスター:・ 並列的項各自定類——ドラゴン族 種族、レベル8 數值(欄位 レベル、數字 8)。"""
        self.assertEqual(modifiers("①：ドラゴン族・レベル８モンスター１体を特殊召喚する。"),
                         [[("ドラゴン族", "種族"), ("レベル8", "數值", "レベル", None, 8)]])

    def test_archetype_before_an_owner_noun(self):
        """「X－セイバー」モンスターの攻撃力:の 前的段裡引號段直接接名詞,引號段是字段、後面的所有者名詞落 其他;
        「青眼の白龍」の攻撃力 的引號段接 の,仍是卡名、落 其他。"""
        self.assertEqual(modifiers("①：自分フィールドの「X－セイバー」モンスターの攻撃力は５００アップする。", key="topic"),
                         [[("自分フィールド", "區域"), ("「X－セイバー」", "字段"), ("モンスター", "其他")]])
        self.assertEqual(modifiers("①：「青眼の白龍」の攻撃力を０にする。"), [[("「青眼の白龍」", "其他")]])

    def test_segment_region_falls_back_to_its_region_modifiers(self):
        """相手フィールドの特殊召喚されたモンスター:區域在定語述語之前、但定語子句沒有自己的格,區域修飾的是中心詞
        ——段的玩家/區域從區域/玩家類的修飾語補;このカード以外の自分の獣戦士族モンスター 的玩家 自分 同理。
        墓地のモンスターを対象とする効果 的 墓地 屬子句裡的 モンスター,段沒有區域。"""
        self.assertEqual(segments("①：相手フィールドの特殊召喚されたモンスター１体を破壊する。")[0][4:],
                         ("相手", ["場上"]))
        self.assertEqual(segments("①：このカード以外の自分の獣戦士族モンスターを特殊召喚する。")[0][4:], ("自分", []))
        self.assertEqual(segments("①：墓地のモンスターを対象とする効果を無効にする。")[0][4:], (None, []))

    def test_zone_head_with_a_count_keeps_its_zone(self):
        """手札を１枚相手に見せる:對象 手札1枚 的中心詞就是區域詞,數量尾不擋區域辨識——玩家 無、區域 手牌
        (和 目的=手札 的段一樣)。"""
        self.assertEqual(segments("①：手札を１枚相手に見せる。")[0], ("手札1枚", "手札", "卡", False, "無", ["手牌"]))

    def test_literal_with_a_comma_still_takes_the_clause_quantity(self):
        """…縦列に存在する、このカード以外のカードを全て破壊する:對象字面裡的讀點被上游去掉,片語仍要對回句子的
        詞序列(不然子句裡的 を全て 取不到)——一段、數量 全て(全部、取自子句)。"""
        frame = actions("①：移動する前と移動した後のモンスターゾーン及びその間のモンスターゾーンと同じ縦列に存在する、"
                        "このカード以外のカードを全て破壊する。", )
        frame = next(f for f in frame if f["action"] == "破壊")
        segs = frame["phrases"]["object"]["segments"]
        self.assertEqual([s["head"] for s in segs], ["カード"])
        self.assertEqual(segs[-1]["quantity"], {"text": "全て", "kind": "全部", "number": None, "from_clause": True})

    def test_closed_value_before_an_owner_noun(self):
        """攻撃表示モンスターの攻撃力、「No.」Xモンスターの攻撃力:の 前的段裡封閉值/字段/召喚法直接接所有者名詞——
        各項照類記、所有者名詞落 其他(v4-round2,和 「X」モンスターの攻撃力 同一條)。"""
        self.assertEqual(modifiers("①：相手フィールドの全ての攻撃表示モンスターの攻撃力は０になる。", key="topic"),
                         [[("相手フィールド", "區域"), ("攻撃表示", "表示形式"), ("モンスター", "其他")]])   # 全ての 是數量(2026-11-01 裁定)
        self.assertEqual(modifiers("①：自分フィールドの全ての「No.」Xモンスターの攻撃力は５００アップする。", key="topic"),
                         [[("自分フィールド", "區域"), ("「No.」", "字段"), ("X", "卡片子類型"), ("モンスター", "其他")]])


class TestV4Decisions(unittest.TestCase):
    """frame-args-v4 待裁定九項的落地(2026-11-01 站主裁定:檢驗摘要「需要你決定的」第四版論元九項全採建議 (a)):
    (1)受事者之前的引用量與主語位 が+數量 取進片語;(2)方式 戦闘・効果で 一族記 手段:戰鬥或效果;(3)全ての/任意の
    連體寫法記該段的數量、修飾語不留;(5)段首指示詞之後先有格助詞再有定語述語或比較詞時旗標假;(6)中心詞類加
    玩家/位置/表示形式。(4)(7)(8)(9)維持現狀、不改程式。只斷言輸出框架的 phrases/manner 欄。"""

    def test_reference_quantity_before_the_object_is_taken_from_the_clause(self):
        """…の数まで/数だけ/数の分だけ/枚数まで 寫在受事者之前(同一子句):記進受事者最後一段,只記字面、類空、
        標取自子句,與 を 後的引用量同形;字面從 数 往前收到讀點或 の 以外的助詞為止。"""
        self.assertEqual(quantities("①：相手フィールドのモンスターの数まで、手札からレベル４以下のモンスターを特殊召喚する。"),
                         [("相手フィールドのモンスターの数まで", None, None, True)])
        self.assertEqual(quantities("①：除外した数だけ相手フィールドのカードを除外する。"),
                         [("除外した数だけ", None, None, True)])
        self.assertEqual(quantities("①：その数の分だけ相手フィールドのカードを破壊する。"),
                         [("その数の分だけ", None, None, True)])
        self.assertEqual(quantities("①：手札の枚数まで相手フィールドのカードを破壊する。"),
                         [("手札の枚数まで", None, None, True)])

    def test_reference_quantity_in_another_clause_is_not_taken(self):
        """数が５体以上の場合、 是條件子句;主句的受事者沒有數量。"""
        self.assertEqual(quantities("①：墓地のモンスターの数が５体以上の場合、手札から「X」モンスターを特殊召喚する。",
                                    action="特殊召喚"), [None])

    def test_subject_count_after_ga_is_taken_from_the_clause(self):
        """「DD」カードが２枚存在する:主語位緊接 が 的數量取進主語段、標取自子句;數量後接 に(３つになった)是值,不收。"""
        self.assertEqual(
            quantities("①：自分フィールドに「DD」カードが２枚存在する場合、手札から「DD」モンスター１体を特殊召喚する。",
                       key="subject", action="存在"), [("2枚", "定數", 2, True)])
        self.assertEqual(quantities("①：自分フィールドにモンスターが２体以上存在する場合に発動できる。", key="subject",
                                    action="存在"), [("2体以上", "下限", 2, True)])
        self.assertEqual(quantities("①：このカードのX素材が３つになった場合に発動できる。", key="subject"), [None])

    def test_battle_or_effect_manner_is_its_own_kind(self):
        """戦闘・効果で、戦闘または相手の効果で、相手モンスターの攻撃または相手の効果で:手段:戰鬥 與 手段:效果
        的並列記 手段:戰鬥或效果;其他組合(戦闘以外で)仍落 其他。"""
        self.assertEqual(mannered("①：このカードが戦闘・効果で破壊された場合に発動できる。")[0],
                         ("破壊", "戦闘・効果で", "手段:戰鬥或效果", None))
        self.assertEqual(mannered("①：このカードが戦闘または相手の効果で破壊された場合に発動できる。")[0],
                         ("破壊", "戦闘または相手の効果で", "手段:戰鬥或效果", None))
        self.assertEqual(mannered("①：このカードが相手モンスターの攻撃または相手の効果で破壊された場合に発動できる。")[0],
                         ("破壊", "相手モンスターの攻撃または相手の効果で", "手段:戰鬥或效果", None))
        self.assertEqual(mannered("①：自分のモンスターが戦闘以外で墓地へ送られた場合に発動できる。")[0],
                         ("送る", "戦闘以外で", "其他", None))

    def test_adnominal_subete_and_nin_i_are_the_segment_quantity(self):
        """全てのモンスター、任意のレベル:記成該段的數量(全部/任意、字面 全ての/任意の、不是取自子句),修飾語不留。"""
        text = "①：相手フィールドの全てのモンスターを破壊する。"
        self.assertEqual(quantities(text), [("全ての", "全部", None, False)])
        self.assertEqual(modifiers(text), [[("相手フィールド", "區域")]])
        text = "①：このカードのレベルを１～８までの任意のレベルにする。"
        self.assertEqual(quantities(text, key="goal"), [("任意の", "任意", None, False)])
        self.assertNotIn(("任意", "其他"), modifiers(text, key="goal")[0])

    def test_demonstrative_bound_inside_a_relative_clause_is_not_a_demonstrative_segment(self):
        """段首指示詞之後先有格助詞(と/が/は/より/を/で…)再有定語述語或比較詞:指示詞綁在定語子句裡的另一張卡,
        旗標假;その破壊された(沒有格助詞)、その無効にした(する名詞的 に)、その手札に加えた(區域的 に)仍為真。"""
        self.assertFalse(segments("①：そのカードとはカード名が異なる「戦華」魔法・罠カード１枚を手札に加える。")[0][3])
        self.assertFalse(segments("①：そのモンスターよりランクが２つ高いXモンスター１体を特殊召喚する。")[0][3])
        self.assertFalse(segments("①：デッキからそのモンスターと同じ種族のモンスター１体を手札に加える。")[0][3])
        self.assertFalse(segments("①：そのカード名が記されたモンスター１体を手札に加える。")[0][3])
        self.assertTrue(segments("①：その破壊されたモンスターを特殊召喚する。")[0][3])
        self.assertTrue(segments("①：その無効にしたカードを破壊する。")[0][3])
        self.assertTrue(segments("①：その手札に加えたカードを相手に見せる。")[0][3])
        self.assertTrue(segments("①：そのモンスターの攻撃力は５００アップする。", key="topic")[0][3])

    def test_player_position_and_display_form_heads(self):
        """玩家詞(相手/自分/プレイヤー/コントローラー/持ち主)→ 玩家;牌組位置(一番上/一番下/上/下)→ 位置;
        表示形式的值(裏側守備表示…)→ 表示形式;表示形式 這個詞本身仍是 屬性。"""
        self.assertEqual(segments("①：相手に５００ダメージを与える。", key="goal"),
                         [("相手", "相手", "玩家", False, "相手", [])])
        self.assertEqual(segments("①：相手プレイヤーに１０００ダメージを与える。", key="goal"),
                         [("相手プレイヤー", "プレイヤー", "玩家", False, "相手", [])])
        self.assertEqual(segments("①：そのモンスターのコントローラーは手札を１枚捨てる。", key="topic")[0][1:3],
                         ("コントローラー", "玩家"))
        self.assertEqual(segments("①：自分はデッキから１枚ドローする。", key="topic"),
                         [("自分", "自分", "玩家", False, "自分", [])])
        self.assertEqual(segments("①：このカードをデッキの一番下に戻す。", key="goal"),
                         [("デッキの一番下", "一番下", "位置", False, "無", ["牌組"])])
        self.assertEqual(segments("①：そのモンスターを裏側守備表示にする。", key="goal"),
                         [("裏側守備表示", "裏側守備表示", "表示形式", False, None, [])])
        self.assertEqual(segments("①：そのモンスターの表示形式を変更する。")[0][1:3], ("表示形式", "屬性"))

    def test_player_heads_keep_the_old_segmentation_and_region_rules(self):
        """自分・相手 仍是一段(玩家的並列不切);自分または相手 不從前面的玩家修飾語補玩家(玩家仍空);
        対象の自分のモンスターの上 的 自分 修飾的是怪獸,位置段不補玩家。"""
        self.assertEqual(segments("①：自分・相手がコイントスを行う度に発動する。", key="subject")[0][:3],
                         ("自分・相手", "相手", "玩家"))
        self.assertEqual(segments("①：自分または相手が戦闘ダメージを受けた時に発動できる。", key="subject"),
                         [("自分または相手", "相手", "玩家", False, None, [])])
        self.assertEqual(segments("①：Xモンスター１体を、対象の自分のモンスターの上に重ねてX召喚扱いでEXデッキから特殊召喚する。",
                                  key="goal", action="重ねる")[0][1:6], ("上", "位置", True, None, []))


if __name__ == "__main__":
    unittest.main()
