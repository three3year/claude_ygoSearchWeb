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


def brief(frame):
    """框架 → 比對用的精簡 tuple(動作, 對象, 來源, 目的, 位置, 極性)。"""
    return (frame["action"], frame.get("object"), frame.get("source"),
            frame.get("goal"), frame["position"], frame["polarity"])


def extract(text, context=""):
    return [brief(f) for f in frames.extract(text, context)]


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
            [("得る", "相手フィールドの表側表示モンスター1体のコントロール",
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
            [("捨てる", "手札", None, None, "代價", "肯定"),
             ("加える", "モンスター1体", "デッキ", "手札", "效果", "肯定")])

    def test_condition_clause(self):
        self.assertEqual(
            extract("①：自分フィールドに「試作機」が存在する場合に発動できる。"
                    "相手フィールドのカード１枚を破壊する。"),
            [("存在", None, None, "自分フィールド", "條件", "肯定"),
             ("破壊", "相手フィールドのカード1枚", None, None, "效果", "肯定")])

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
            [("除外", "相手の墓地のカード1枚", None, None, "效果", "肯定")])

    def test_elided_head_in_object(self):
        self.assertEqual(
            extract("①：フィールドの魔法・罠カード１枚を破壊する。"),
            [("破壊", "フィールドの魔法(カード)・罠カード1枚", None, None,
              "效果", "肯定")])

    def test_demonstrative_binding_and_target(self):
        self.assertEqual(
            extract("①：相手フィールドのモンスター１体を対象として発動できる。"
                    "そのモンスターを破壊する。"),
            [("対象とする", "相手フィールドのモンスター1体", None, None,
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
        self.assertEqual(
            extract("このカード名の①の方法による特殊召喚は１ターンに１度しか"
                    "できない。"),
            [("特殊召喚", None, None, None, "效果", "否定")])

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
            [("選ぶ", "相手フィールドのモンスター1体", None, None, "效果", "肯定"),
             ("破壊", None, None, None, "效果", "肯定")])

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
        self.assertEqual(
            extract("このカードはアドバンス召喚したモンスター１体をリリースして"
                    "アドバンス召喚できる。"),
            [("リリース", "アドバンス召喚したモンスター1体", None, None,
              "效果", "肯定"),
             ("アドバンス召喚", None, None, None, "效果", "可能")])

    def test_bare_number_of_time_phrase_stays_out_of_object(self):
        self.assertEqual(
            extract("「精霊獣 カンナホーク」を１ターンに１度しか特殊召喚できない。"),
            [("特殊召喚", "「精霊獣 カンナホーク」", None, None, "效果", "否定")])

    def test_otagai_ni_is_not_a_goal(self):
        self.assertEqual(
            extract("①：お互いに墓地のモンスターを特殊召喚できない。"),
            [("特殊召喚", "墓地のモンスター", None, None, "效果", "否定")])

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
            [("対象とする", "自分の墓地のモンスター1体", None, None, "條件", "肯定"),
             ("対象とする", "自分の墓地の罠カード1枚", None, None, "條件", "可能"),
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
            [("装備", "そのモンスター以外の自分の墓地のXモンスター1体", None,
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
            [("破壊", "戦闘を行った相手フィールドのモンスター1体", None, None,
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
            [("無効化", None, None, None, "效果", "肯定"),
             ("離れる", None, "フィールド", None, "條件", "肯定"),
             ("除外", None, None, None, "效果", "肯定")])

    def test_this_effect_cannot_be_activated_is_a_note(self):
        self.assertEqual(
            extract("①：自分は１枚ドローする。この効果はこのカードが特殊召喚した"
                    "ターンには発動できない。"),
            [("ドロー", None, None, None, "效果", "肯定"),
             ("特殊召喚", None, None, None, "條件", "肯定")])

    def test_coordinated_materials_each_framed(self):
        self.assertEqual(
            extract("①：このカードを融合素材またはリンク素材として墓地へ送った"
                    "場合、自分は１枚ドローする。"),
            [("融合素材とする", "このカード", None, None, "條件", "肯定"),
             ("リンク素材とする", "このカード", None, None, "條件", "肯定"),
             ("送る", None, None, "墓地", "條件", "肯定"),
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
             ("加える", None, None, "手札", "效果", "肯定"),
             ("発動", None, None, "自分フィールド", "效果", "肯定")])

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


if __name__ == "__main__":
    unittest.main()
