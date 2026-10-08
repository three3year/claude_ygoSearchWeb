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


if __name__ == "__main__":
    unittest.main()
