# -*- coding: utf-8 -*-
"""類別匯出的行為測試(.scratch/category-search 票 01,ADR-0017)。

接縫:(動作框架、框架類別、標記句)→ 類別匯出紀錄(export_categories.export)。
fixture 是合成的幾張卡的標記句列,經真的組裝(tokenize.assemble)、框架抽取
(frames.extract)與類別樹(categories)跑出框架與框架類別,再進匯出;只斷言匯出
紀錄(每句的效果位葉、代價位葉、原文雜湊)與匯出的問題清單,不測對句規則的內部。

執行:PYTHONIOENCODING=utf-8 python -m unittest discover -s .scratch/effect-tokenize
"""
import hashlib
import importlib.util
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import categories  # noqa: E402
import export_categories  # noqa: E402
import frames  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "effect_tokenize", os.path.join(HERE, "tokenize.py"))
effect_tokenize = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(effect_tokenize)


def clause(index, text_ja, kind="啟動效果", section="main"):
    return {"index": index, "section": section, "kind": kind, "text_ja": text_ja}


def chain(cards):
    """{卡片密碼: 標記句列} → 分詞鏈的兩份中間產物(效果句與其框架、框架類別列),
    形狀同 frames.json(多帶 text_ja)與 frame_categories.json。"""
    tree = categories.default_tree()
    sentences, records = [], []
    for card, clauses in cards.items():
        sections = []
        for c in clauses:
            if c["section"] not in sections:
                sections.append(c["section"])
        for section in sections:
            context = ""
            for rec in effect_tokenize.assemble(
                    [c for c in clauses if c["section"] == section]):
                found = frames.extract(rec["text_ja"], context,
                                       extra=rec["kind"] == "效果外文本")
                for k, fr in enumerate(found):
                    fr["order"] = k
                sentences.append({"card": card, "section": section, "index": rec["index"],
                                  "parts": rec["parts"], "text_ja": rec["text_ja"],
                                  "frames": found})
                for fr, record in categories.classified(tree, found):
                    records.append({"card": card, "section": section,
                                    "index": rec["index"], "order": fr["order"],
                                    "status": record["status"], "leaves": record["leaves"]})
                context += rec["text_ja"]
    return sentences, records


def export(cards, faces=None):
    sentences, records = chain(cards)
    return export_categories.export(sentences, records, categories.default_tree(),
                                    faces=faces)


def rows(cards):
    """→ {(卡, 段落, index): (效果位葉, 代價位葉)};斷言匯出沒有問題。"""
    doc, problems = export(cards)
    assert not problems, problems
    return {(r["card"], r["section"], r["index"]): (r.get("effect", []), r.get("cost", []))
            for r in doc["句"]}


def sha(text):
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


REVIVE = "①：自分の墓地からモンスター１体を特殊召喚する。"


class TestExport(unittest.TestCase):

    def test_single_sentence_effect_leaf_and_hash(self):
        doc, problems = export({1: [clause("①", REVIVE)]})
        self.assertEqual(problems, [])
        self.assertEqual(doc["句"], [{"card": 1, "section": "main", "index": "①",
                                      "hash": sha(REVIVE), "effect": ["特殊召喚←墓地"],
                                      "effect_nonself": ["特殊召喚←墓地"]}])

    def test_cost_leaves_are_grouped_apart_from_effect_leaves(self):
        self.assertEqual(rows({1: [clause("①", "①：手札を１枚捨てて発動できる。デッキから"
                                              "「試作機」１体を手札に加える。")]}),
                         {(1, "main", "①"): (["加える:デッキ→手札"], ["捨てる"])})

    def test_split_options_go_to_their_own_sub_sentences(self):
        """拆開的效果句:選項 n 的框架屬 index-●n,沒有選項的屬領起句;雜湊各是自己那一句。"""
        sub1 = "●自分の墓地からモンスター１体を特殊召喚する。"
        doc, problems = export({1: [
            clause("①", "①：以下の効果から１つを選択して発動できる。", kind="效果外文本"),
            clause("①-●1", sub1),
            clause("①-●2", "●フィールドのカード１枚を破壊する。")]})
        self.assertEqual(problems, [])
        by_index = {r["index"]: r for r in doc["句"]}
        self.assertEqual(list(by_index), ["①", "①-●1", "①-●2"])
        self.assertNotIn("effect", by_index["①"])
        self.assertEqual(by_index["①-●1"]["effect"], ["特殊召喚←墓地"])
        self.assertEqual(by_index["①-●2"]["effect"], ["破壊@フィールド"])
        self.assertEqual(by_index["①-●1"]["hash"], sha(sub1))

    def test_unsplit_options_stay_in_their_one_sentence(self):
        """官方沒拆的 ●:框架帶選項,效果句只有一段,整個屬那一句。"""
        self.assertEqual(
            rows({1: [clause("①", "①：以下の効果から１つを選択して発動できる。\n"
                                  "●自分の墓地からモンスター１体を特殊召喚する。\n"
                                  "●フィールドのカード１枚を破壊する。")]}),
            {(1, "main", "①"): (["特殊召喚←墓地", "破壊@フィールド"], [])})

    def test_extra_text_and_condition_frames_carry_no_leaves(self):
        """效果外文本照樣有紀錄(只是沒有葉);條件位(墓地へ送られた場合)不帶葉;
        複合區域的框架帶多個葉。"""
        self.assertEqual(
            rows({1: [clause("0", "このカード名の①の効果は１ターンに１度しか使用できない。",
                             kind="效果外文本"),
                      clause("①", "①：このカードが墓地へ送られた場合に発動できる。"
                                  "手札・墓地からモンスター１体を特殊召喚する。",
                             kind="誘發效果(1速)")]}),
            {(1, "main", "0"): ([], []),
             (1, "main", "①"): (["特殊召喚←手札", "特殊召喚←墓地"], [])})

    def test_pendulum_section_unplaced_frames_and_tree_order(self):
        """靈擺段落是自己的鍵;未歸的框架(振り直す)不帶葉;同句重複的葉只記一次、依樹序。"""
        self.assertEqual(
            rows({1: [clause("①", "①：自分フィールドのカード１枚を破壊する。",
                             section="pendulum"),
                      clause("①", "①：サイコロを振り直す。デッキからモンスター１体を墓地へ"
                                  "送り、自分の墓地からモンスター１体を特殊召喚する。その後、"
                                  "墓地からモンスター１体を特殊召喚する。")]}),
            {(1, "pendulum", "①"): (["破壊@自分フィールド"], []),
             (1, "main", "①"): (["特殊召喚←墓地", "送る:デッキ→墓地"], [])})

    def test_frame_without_a_sentence_fails_the_export(self):
        """不變式:每個動作框架剛好對到一句——選項對不到子效果句就失敗。"""
        sentences, records = chain({1: [
            clause("①", "①：以下の効果から１つを選択して発動できる。", kind="效果外文本"),
            clause("①-●1", "●自分の墓地からモンスター１体を特殊召喚する。"),
            clause("①-●2", "●フィールドのカード１枚を破壊する。")]})
        frame = next(f for f in sentences[0]["frames"] if f.get("option") == 2)
        frame["option"] = 3
        _, problems = export_categories.export(sentences, records, categories.default_tree())
        self.assertEqual(len(problems), 1)
        self.assertIn("對不到標記句", problems[0])

    def test_stale_frame_categories_fail_the_export(self):
        """框架類別與框架對不上(中間產物過時)就失敗,兩個方向都擋。"""
        sentences, records = chain({1: [clause("①", REVIVE)]})
        extra = dict(records[0], order=9)
        _, problems = export_categories.export(sentences, records + [extra],
                                               categories.default_tree())
        self.assertEqual(len(problems), 1)
        _, problems = export_categories.export(sentences, [], categories.default_tree())
        self.assertEqual(len(problems), 1)

    def test_tree_rides_along_with_leaf_names_in_tree_order(self):
        """匯出帶類別樹:葉名依樹序,巢狀節點的葉號指回葉名;詞元節點帶預設葉時同一節點
        既有葉號又有子節點(破壊 底下的 {})。"""
        doc, _ = export({1: [clause("①", REVIVE)]})
        leaves = doc["葉"]
        self.assertEqual(len(leaves), len(categories.default_tree().leaves))

        def find(nodes, path):
            node = next(n for n in nodes if n[0] == path[0])
            return node if len(path) == 1 else find(node[2], path[1:])
        revive = find(doc["樹"], ["召喚", "特殊召喚", "特殊召喚←墓地"])
        self.assertEqual(leaves[revive[1]], "特殊召喚←墓地")
        self.assertEqual(revive[2], [])
        destroy = find(doc["樹"], ["破壊"])
        self.assertEqual(leaves[destroy[1]], "破壊")
        self.assertTrue(destroy[2])

    def test_serialization_is_one_sentence_per_line_and_roundtrips(self):
        import json
        doc, _ = export({1: [clause("①", REVIVE)], 2: [clause("①", REVIVE)]})
        text = export_categories.serialize(doc)
        self.assertEqual(json.loads(text), doc)
        self.assertEqual(sum(line.startswith('{"card"') for line in text.splitlines()), 2)

    def test_same_input_exports_byte_identical(self):
        cards = {1: [clause("①", REVIVE)],
                 2: [clause("①", "①：手札を１枚捨てて発動できる。デッキから「試作機」１体を"
                                 "手札に加える。")]}
        first = export_categories.serialize(export(cards)[0])
        self.assertEqual(first, export_categories.serialize(export(cards)[0]))


# 合成的卡面參數(卡片總表的欄位):等級 7 的暗屬性龍族效果怪獸、通常魔法
DRAGON = {"id": 1, "type": 0x21, "race": 0x2000, "attribute": 0x20, "level": 7,
          "atk": 2500, "def": 2000, "name_ja": "テスト・ドラゴン"}
SPELL = {"id": 1, "type": 0x2, "race": 0, "attribute": 0, "level": 0,
         "atk": None, "def": None, "name_ja": "テスト・魔法"}


def modes(text, card=1, kind="啟動效果", face=DRAGON, section="main"):
    """一句效果句 → {效果位此卡葉、效果位非此卡葉、代價位此卡葉、代價位非此卡葉}
    (空的省略);斷言匯出沒有問題。"""
    faces = {card: export_categories.card_face(dict(face, id=card))} if face else None
    doc, problems = export({card: [clause("①", text, kind=kind, section=section)]}, faces)
    assert not problems, problems
    row = doc["句"][0]
    return {k: row[k] for k in ("effect_self", "effect_nonself", "cost_self", "cost_nonself")
            if k in row}


class TestPatientSelf(unittest.TestCase):
    """[[動作對象]]「此卡」(action-patient 票 01):受事者以 このカード 收尾,與主題規則。"""

    def test_this_card_special_summoned_from_hand_is_self(self):
        self.assertEqual(modes("①：自分メインフェイズに発動できる。このカードを手札から"
                               "特殊召喚する。"),
                         {"effect_self": ["特殊召喚←手札"]})

    def test_this_card_written_as_topic_is_self(self):
        """「このカードは手札から特殊召喚できる」:對象空著、主題是此卡。"""
        self.assertEqual(modes("①：このカードは手札から特殊召喚できる。"),
                         {"effect_self": ["特殊召喚←手札"]})

    def test_topic_carried_over_within_the_sentence_is_self(self):
        """主題延續給後面沒有自己主題的子句。"""
        self.assertEqual(
            modes("①：このカードは相手フィールドにモンスターが存在する場合、"
                  "手札から特殊召喚できる。"),
            {"effect_self": ["特殊召喚←手札"]})

    def test_this_card_with_a_modifier_is_self(self):
        """帶定語、切掉區域的此卡(墓地のこのカード)。"""
        self.assertEqual(modes("①：墓地のこのカードを除外して発動できる。自分フィールドの"
                               "カード１枚を破壊する。"),
                         {"cost_self": ["除外←墓地"], "effect_nonself": ["破壊@自分フィールド"]})

    def test_releasing_this_card_then_summoning_another_is_not_self_summon(self):
        """代價解放此卡、處理從手牌特召另一隻:特召不是此卡,代價的解放才是。"""
        found = modes("①：このカードをリリースして発動できる。手札からモンスター１体を"
                      "特殊召喚する。")
        self.assertEqual(found.get("cost_self"), ["リリース"])
        self.assertNotIn("effect_self", found)

    # ── 票 02:此卡字面規則 ──

    def test_attribute_of_this_card_is_self(self):
        self.assertEqual(modes("①：このカードの攻撃力は５００アップする。"),
                         {"effect_self": ["アップ:攻撃力"]})
        self.assertEqual(modes("①：このカードのレベルを１つ上げる。"),
                         {"effect_self": ["アップ:レベル"]})

    def test_attribute_of_this_card_with_a_modifier_is_self(self):
        self.assertEqual(modes("①：この効果で特殊召喚したこのカードの攻撃力は倍になる。"),
                         {"effect_self": ["倍にする:攻撃力"]})

    def test_effect_owned_by_this_card_is_self(self):
        self.assertEqual(modes("①：このカードの効果を無効にする。"),
                         {"effect_self": ["無効にする:効果"]})

    def test_this_card_listed_with_another_card_is_self(self):
        self.assertEqual(modes("①：このカードと植物族モンスター１体を手札から特殊召喚する。"),
                         {"effect_self": ["特殊召喚←手札"]})

    def test_group_including_this_card_is_self(self):
        self.assertEqual(modes("①：このカードを含む自分フィールドのモンスター２体をリリースして"
                               "発動できる。自分はデッキから１枚ドローする。"),
                         {"cost_self": ["リリース"]})

    def test_this_card_treated_as_something_is_self(self):
        self.assertEqual(modes("①：このカードはフィールド上に存在する限り、闇属性として扱う。")
                         .get("effect_self"), ["扱う"])

    def test_equipped_monster_and_xyz_material_of_this_card_are_not_self(self):
        self.assertNotIn("effect_self",
                         modes("①：このカードの装備モンスターの攻撃力は５００アップする。"))
        self.assertNotIn("cost_self", modes("①：このカードのX素材を１つ取り除いて発動できる。"
                                            "自分はデッキから１枚ドローする。"))

    def test_this_card_name_and_other_than_this_card_are_not_self(self):
        self.assertNotIn("effect_self", modes("①：このカード以外の自分フィールドのモンスターを"
                                              "全て破壊する。"))
        self.assertNotIn("effect_self", modes("①：このカードと同じ縦列の他のモンスターを全て"
                                              "破壊する。"))
        self.assertNotIn("effect_self", modes("①：このカードと戦闘を行うモンスターを破壊する。"))
        self.assertNotIn("effect_self", modes("①：このカードと(共同)戦闘を行うモンスターの"
                                              "攻撃力は０になる。"))

    def test_stats_count_each_self_rule(self):
        doc, _ = export({1: [clause("①", "①：このカードの攻撃力は５００アップする。")],
                         2: [clause("①", "①：このカードと植物族モンスター１体を手札から"
                                          "特殊召喚する。")]})
        reasons = doc["統計"]["理由"]
        self.assertEqual(reasons.get("此卡:此卡的屬性"), 1)
        self.assertEqual(reasons.get("此卡:並列含此卡"), 1)

    def test_frames_on_this_card_are_counted_in_the_stats(self):
        doc, _ = export({1: [clause("①", "①：このカードは手札から特殊召喚できる。")],
                         2: [clause("①", REVIVE)]})
        self.assertEqual(doc["統計"]["框架"]["此卡"], 1)
        self.assertEqual(doc["統計"]["卡"]["此卡"], 1)


class TestPatientNonSelf(unittest.TestCase):
    """[[動作對象]]「非此卡」(action-patient 票 03):確定不動到此卡;全部類暫當皆非。"""

    def test_selection_with_a_count_is_nonself(self):
        self.assertEqual(modes("①：フィールドのカード１枚を対象として発動できる。そのカードを"
                               "破壊する。").get("effect_nonself"), ["破壊"])
        self.assertEqual(modes("①：自分の墓地からモンスター１体を特殊召喚する。"),
                         {"effect_nonself": ["特殊召喚←墓地"]})

    def test_summoning_another_monster_from_hand_is_nonself(self):
        self.assertEqual(modes("①：このカードをリリースして発動できる。手札からモンスター１体を"
                               "特殊召喚する。"),
                         {"cost_self": ["リリース"], "effect_nonself": ["特殊召喚←手札"]})

    def test_other_than_this_card_is_nonself(self):
        self.assertEqual(modes("①：このカード以外の自分フィールドのモンスターを全て破壊する。"),
                         {"effect_nonself": ["破壊:モンスター", "破壊@自分フィールド"]})

    def test_other_cards_written_as_hoka_is_nonself(self):
        """群體前的「他の」:フィールドの他のカードを全て破壊 不會破壞此卡。"""
        self.assertEqual(modes("①：フィールドの他のカードを全て破壊する。"),
                         {"effect_nonself": ["破壊@フィールド"]})

    def test_zone_patient_with_a_count_is_nonself(self):
        """受事者寫成區域:手札を１枚捨てる(數量在子句裡)。"""
        self.assertEqual(modes("①：手札を１枚捨てて発動できる。自分はデッキから１枚ドローする。"),
                         {"cost_nonself": ["捨てる"]})

    def test_effect_or_activation_owned_by_another_is_nonself(self):
        self.assertEqual(modes("①：相手が魔法カードを発動した時に発動できる。その発動を無効にする。",
                               kind="誘發即時效果").get("effect_nonself"),
                         ["無効にする:発動"])
        self.assertEqual(modes("①：相手の効果を無効にする。").get("effect_nonself"),
                         ["無効にする:効果"])

    def test_attribute_of_a_selected_card_is_nonself(self):
        self.assertEqual(modes("①：相手フィールドのモンスター１体を対象として発動できる。"
                               "そのモンスターの攻撃力は０になる。").get("effect_nonself"),
                         ["にする:攻撃力"])

    def test_cards_attached_to_this_card_are_nonself(self):
        self.assertEqual(modes("①：このカードのX素材を１つ取り除いて発動できる。自分はデッキから"
                               "１枚ドローする。"),
                         {"cost_nonself": ["取り除く:X素材"]})

    def test_bare_card_count_is_a_selection(self):
        """受事者只剩量詞(その内の１体)也是選擇類。"""
        self.assertEqual(modes("①：相手フィールドのモンスター２体を対象として発動できる。"
                               "その内の１体を破壊する。").get("effect_nonself"), ["破壊"])

    def test_draw_and_damage_have_no_card_patient(self):
        self.assertEqual(modes("①：自分はデッキから２枚ドローする。"), {})
        self.assertEqual(modes("①：相手に１０００ダメージを与える。"), {})

    def test_this_card_listed_with_another_is_only_self(self):
        self.assertEqual(modes("①：このカードと植物族モンスター１体を手札から特殊召喚する。"),
                         {"effect_self": ["特殊召喚←手札"]})

    def test_same_sentence_can_carry_a_leaf_in_both_modes(self):
        self.assertEqual(modes("①：このカードを手札から特殊召喚する。その後、手札からモンスター"
                               "１体を特殊召喚する。"),
                         {"effect_self": ["特殊召喚←手札"], "effect_nonself": ["特殊召喚←手札"]})

    def test_stats_count_nonself_and_unknown_patients(self):
        doc, _ = export({1: [clause("①", "①：自分の墓地からモンスター１体を特殊召喚する。")],
                         2: [clause("①", "①：相手に１０００ダメージを与える。")]})
        stats = doc["統計"]
        self.assertEqual(stats["框架"]["非此卡"], 1)
        self.assertEqual(stats["卡"]["非此卡"], 1)
        self.assertEqual(stats["理由"].get("皆非:不是卡"), 1)
        self.assertIn("表外受事者", stats)


class TestPatientAllClass(unittest.TestCase):
    """[[動作對象]]全部類(action-patient 票 04):依發動位置與區域、玩家、卡種判斷會不會
    包含此卡;會包含是皆非,不會是非此卡。"""

    def test_field_wipe_launched_on_the_field_is_neither(self):
        """都沒寫就是場上:場上的卡全部破壞會連此卡一起破壞。"""
        self.assertEqual(modes("①：フィールドのカードを全て破壊する。"), {})

    def test_launch_written_in_the_cost_moves_it_off_the_field(self):
        self.assertEqual(modes("①：墓地のこのカードを除外して発動できる。フィールドのカードを"
                               "全て破壊する。"),
                         {"cost_self": ["除外←墓地"], "effect_nonself": ["破壊@フィールド"]})

    def test_launch_written_as_existing_in_the_graveyard(self):
        self.assertEqual(modes("①：このカードが墓地に存在する場合に発動できる。フィールドの"
                               "モンスターを全て破壊する。"),
                         {"effect_nonself": ["破壊:モンスター", "破壊@フィールド"]})

    def test_launch_from_where_the_trigger_sent_this_card(self):
        self.assertEqual(modes("①：このカードが墓地へ送られた場合に発動できる。フィールドの"
                               "モンスターを全て破壊する。", kind="誘發效果(1速)"),
                         {"effect_nonself": ["破壊:モンスター", "破壊@フィールド"]})

    def test_leaving_the_field_with_unknown_destination_is_off_the_field(self):
        self.assertEqual(modes("①：このカードがフィールドから離れた場合に発動できる。"
                               "フィールドのモンスターを全て破壊する。", kind="誘發效果(1速)"),
                         {"effect_nonself": ["破壊:モンスター", "破壊@フィールド"]})

    def test_launch_from_where_this_card_moves_from_while_resolving(self):
        """移動之前的框架:處理中此卡自己移動的起點(手札)當發動位置。"""
        self.assertEqual(modes("①：手札を全て捨てる。その後、このカードを手札から特殊召喚する。"),
                         {"effect_self": ["特殊召喚←手札"]})
        # 對照:沒有自己移動時預設場上,手札全部丟棄 不會包含此卡
        self.assertEqual(modes("①：手札を全て捨てる。"), {"effect_nonself": ["捨てる"]})

    def test_opponents_side_does_not_include_this_card(self):
        self.assertEqual(modes("①：相手フィールドのカードを全て破壊する。"),
                         {"effect_nonself": ["破壊@相手フィールド"]})

    def test_card_kind_that_does_not_match_this_card(self):
        self.assertEqual(modes("①：フィールドの魔法・罠カードを全て破壊する。"),
                         {"effect_nonself": ["破壊:魔法カード/罠カード", "破壊@フィールド"]})
        self.assertEqual(modes("①：フィールドの魔法・罠カードを全て破壊する。", face=SPELL), {})

    def test_zone_written_at_the_head_of_the_patient(self):
        """所在沒被切出、寫在受事者開頭(自分フィールドの…):同樣當群體區域。"""
        self.assertEqual(modes("①：自分フィールドの「天気」魔法・罠カードは相手の効果の対象に"
                               "ならない。").get("effect_nonself"), ["対象にする(耐性)"])

    def test_zone_patient_without_a_count_follows_the_same_rule(self):
        self.assertEqual(modes("①：このカードが墓地に存在する場合に発動できる。手札を全て捨てる。"),
                         {"effect_nonself": ["捨てる"]})

    def test_stats_count_launch_sources(self):
        doc, _ = export({1: [clause("①", "①：フィールドのカードを全て破壊する。")],
                         2: [clause("①", "①：このカードが墓地に存在する場合に発動できる。"
                                          "フィールドのモンスターを全て破壊する。")]})
        launch = doc["統計"]["發動位置"]
        self.assertEqual(launch.get("預設場上"), 1)
        self.assertEqual(launch.get("寫明"), 1)

    def test_card_face_digest_rides_along_and_changes_with_the_face(self):
        faces = {1: export_categories.card_face(DRAGON)}
        doc, _ = export({1: [clause("①", REVIVE)]}, faces)
        before = dict(doc["卡面"])
        faces = {1: export_categories.card_face(dict(DRAGON, level=8))}
        doc, _ = export({1: [clause("①", REVIVE)]}, faces)
        self.assertEqual(set(before), {1})
        self.assertNotEqual(dict(doc["卡面"])[1], before[1])
        self.assertEqual(dict(doc["卡面"])[1],
                         export_categories.face_hash(dict(DRAGON, level=8)))


class TestPatientCountIsNotDuration(unittest.TestCase):
    """數量要是受事者的數量:子句裡的期間、升降值不是選擇類(回歸:真資料抽樣發現)。"""

    def test_until_end_of_turn_is_not_a_count(self):
        self.assertEqual(modes("①：自分フィールドの全てのモンスターの攻撃力はターン終了時まで"
                               "倍になる。"), {})

    def test_level_change_amount_is_not_a_count(self):
        self.assertEqual(modes("①：自分フィールドの全てのモンスターのレベルは５つ上がる。"), {})

    def test_all_of_them_wins_over_a_duration(self):
        self.assertEqual(modes("①：発動後２回目の相手エンドフェイズまで、フィールドのモンスターを"
                               "全て除外する。"), {})

    def test_count_right_after_the_patient_still_counts(self):
        self.assertEqual(modes("①：手札を２枚まで捨てて発動できる。自分はデッキから１枚"
                               "ドローする。").get("cost_nonself"), ["捨てる"])

    def test_up_to_a_number_written_before_the_patient(self):
        self.assertTrue(modes("①：自分の墓地の魔法カードの数まで、デッキからモンスターを"
                              "手札に加える。").get("effect_nonself"))


class TestPatientLaunchEdgeCases(unittest.TestCase):
    """發動位置:此卡是施事者時沒有移動;靈擺區在場上。"""

    def test_this_card_destroying_another_does_not_leave_the_field(self):
        self.assertEqual(modes("①：このカードが相手モンスターを戦闘で破壊した場合に発動できる。"
                               "フィールドのモンスターを全て破壊する。",
                               kind="誘發效果(1速)"), {})

    def test_this_card_sending_another_does_not_move_it(self):
        self.assertEqual(modes("①：このカードがモンスターを墓地へ送った場合に発動できる。"
                               "フィールドのモンスターを全て破壊する。",
                               kind="誘發效果(1速)"), {})

    def test_this_card_destroyed_leaves_the_field(self):
        self.assertTrue(modes("①：このカードが破壊された場合に発動できる。フィールドのモンスターを"
                              "全て破壊する。", kind="誘發效果(1速)").get("effect_nonself"))

    def test_pendulum_zone_is_on_the_field(self):
        self.assertEqual(modes("①：このカードがPゾーンに存在する場合に発動できる。フィールドの"
                               "カードを全て破壊する。"), {})

    def test_pendulum_section_launches_from_the_pendulum_zone(self):
        text = "①：自分のPゾーンのカードを全て破壊する。"
        self.assertEqual(modes(text, section="pendulum"), {})
        self.assertTrue(modes(text).get("effect_nonself"))


class TestPatientThisEffect(unittest.TestCase):
    """受事者是效果、發動:主人是此卡就是此卡;「この効果で…したモンスターの効果」主人是別張。"""

    def test_this_effect_is_owned_by_this_card(self):
        self.assertTrue(modes("①：この効果の発動は無効化されない。").get("effect_self"))

    def test_effect_of_a_monster_summoned_by_this_effect_is_nonself(self):
        found = modes("①：手札からモンスター１体を特殊召喚する。この効果で特殊召喚した"
                      "モンスターの効果は無効化される。")
        self.assertIn("無効にする:効果", found.get("effect_nonself", []))
        self.assertNotIn("effect_self", found)

    def test_sorezore_is_not_a_demonstrative(self):
        """それぞれ・それ以外 不是指示詞:沒有數量仍是全部類。"""
        self.assertEqual(modes("①：それ以外の自分フィールドのモンスターを全て破壊する。"), {})


class TestPatientAfterSelfMove(unittest.TestCase):
    """此卡自己移動之後的框架看移動的目的(2026-10-30 站主裁定,取代 story 16 例句判皆非)。"""

    def test_discarding_the_hand_after_leaving_it(self):
        self.assertEqual(modes("①：このカードを手札から特殊召喚する。その後、手札を全て捨てる。"),
                         {"effect_self": ["特殊召喚←手札"], "effect_nonself": ["捨てる"]})

    def test_field_wipe_after_summoning_itself_includes_it(self):
        self.assertEqual(modes("①：このカードを手札から特殊召喚する。その後、フィールドのカードを"
                               "全て破壊する。"),
                         {"effect_self": ["特殊召喚←手札"]})

    def test_field_wipe_after_returning_to_hand_does_not_include_it(self):
        found = modes("①：このカードを手札に戻す。その後、フィールドのモンスターを全て破壊する。")
        self.assertIn("破壊@フィールド", found.get("effect_nonself", []))

    def test_destroying_itself_leaves_the_field(self):
        found = modes("①：このカードを破壊し、フィールドのモンスターを全て破壊する。")
        self.assertIn("破壊@フィールド", found.get("effect_nonself", []))

    def test_moving_itself_as_a_cost_counts(self):
        self.assertEqual(modes("①：このカードをリリースして発動できる。フィールドのカードを"
                               "全て破壊する。"),
                         {"cost_self": ["リリース"], "effect_nonself": ["破壊@フィールド"]})

    def test_negated_move_is_not_a_move(self):
        self.assertNotIn("effect_nonself", modes("①：このカードは戦闘では破壊されない。"
                                                 "フィールドのカードを全て破壊する。"))

    def test_move_in_one_option_does_not_affect_another(self):
        self.assertNotIn("effect_nonself", modes(
            "①：以下の効果から１つを選択して発動できる。\n●このカードを手札に戻す。\n"
            "●フィールドのカードを全て破壊する。"))

    def test_stats_report_frames_judged_after_a_self_move(self):
        doc, _ = export({1: [clause("①", "①：このカードを手札から特殊召喚する。その後、手札を全て"
                                         "捨てる。")]})
        self.assertEqual(doc["統計"]["發動位置"].get("移動後"), 1)


class TestPatientReviewFindings(unittest.TestCase):
    """code review 用例句實跑抓到的錯。"""

    def test_count_on_the_choosing_clause_carries_to_the_backfilled_frame(self):
        """１枚選んで破壊する:破壊 的對象是回填的,數量在 選ぶ 的子句裡。"""
        found = modes("①：フィールドのカードを１枚選んで破壊する。")
        self.assertIn("破壊@フィールド", found.get("effect_nonself", []))

    def test_draw_never_has_a_card_patient(self):
        """「N枚」是抽卡張數,不是卡的選擇。"""
        self.assertEqual(modes("①：自分はデッキに戻した数＋１枚をドローする。"), {})

    def test_listed_with_this_card_counts_for_the_launch_position(self):
        self.assertEqual(modes("①：手札を全て捨てる。その後、このカードと植物族モンスター１体を"
                               "手札から特殊召喚する。"),
                         {"effect_self": ["特殊召喚←手札"]})

    def test_listed_with_this_card_in_the_cost_counts_for_the_launch_position(self):
        found = modes("①：墓地のこのカードとモンスター１体を除外して発動できる。フィールドの"
                      "カードを全て破壊する。")
        self.assertEqual(found.get("effect_nonself"), ["破壊@フィールド"])

    def test_listed_with_this_card_may_carry_a_modifier(self):
        self.assertTrue(modes("①：リンク状態のこのカード及びこのカードのリンク先のモンスターを"
                              "破壊する。").get("effect_self"))

    def test_comparing_with_this_card_is_not_listing_it(self):
        self.assertNotIn("effect_self", modes("①：このカードとカード名が異なるモンスターを全て"
                                              "破壊する。"))

    def test_stats_split_launch_sources_of_the_neither_frames(self):
        doc, _ = export({1: [clause("①", "①：フィールドのカードを全て破壊する。")],
                         2: [clause("①", "①：相手フィールドのカードを全て破壊する。")]})
        self.assertEqual(doc["統計"]["發動位置"].get("預設場上"), 2)
        self.assertEqual(doc["統計"]["皆非發動位置"].get("預設場上"), 1)


XYZ = {"id": 1, "type": 0x800021, "race": 0x1, "attribute": 0x10, "level": 4,
       "atk": 2000, "def": 1000, "name_ja": "テスト・エクシーズ"}
UNKNOWN_ATK = dict(DRAGON, atk=-2, **{"def": -2})


def wipe(group, face=DRAGON):
    """「自分フィールドの〈群體〉を全て破壊する」:會不會判成非此卡。"""
    return "effect_nonself" in modes("①：自分フィールドの%sを全て破壊する。" % group, face=face)


class TestPatientAllClassConditions(unittest.TestCase):
    """[[動作對象]]全部類(action-patient 票 05):種族、屬性、字段、子類型、數值。合成的此卡是
    等級 7、攻 2500 守 2000 的暗屬性龍族效果怪獸「テスト・ドラゴン」。"""

    def test_race(self):
        self.assertTrue(wipe("戦士族モンスター"))
        self.assertFalse(wipe("ドラゴン族モンスター"))
        self.assertFalse(wipe("戦士族・ドラゴン族モンスター"))

    def test_attribute(self):
        self.assertTrue(wipe("光属性モンスター"))
        self.assertFalse(wipe("闇属性モンスター"))
        self.assertFalse(wipe("光・闇属性モンスター"))

    def test_archetype_is_contained_in_the_japanese_card_name(self):
        self.assertTrue(wipe("「サイバー」モンスター"))
        self.assertFalse(wipe("「テスト」モンスター"))

    def test_card_subtype(self):
        self.assertTrue(wipe("融合モンスター"))
        self.assertFalse(wipe("効果モンスター"))
        self.assertTrue(wipe("通常モンスター"))
        self.assertTrue(wipe("融合・S・Xモンスター"))
        self.assertFalse(wipe("融合・S・Xモンスター", face=XYZ))

    def test_spell_subtype(self):
        self.assertTrue(wipe("永続魔法カード", face=SPELL))
        self.assertFalse(wipe("通常魔法カード", face=SPELL))

    def test_numeric_conditions(self):
        self.assertTrue(wipe("レベル４以下のモンスター"))
        self.assertFalse(wipe("レベル７以上のモンスター"))
        self.assertTrue(wipe("攻撃力１０００以下のモンスター"))
        self.assertFalse(wipe("攻撃力２５００以上のモンスター"))
        self.assertTrue(wipe("守備力１０００以下のモンスター"))
        self.assertFalse(wipe("守備力２０００のモンスター"))

    def test_rank_and_level_do_not_mix(self):
        """超量怪獸沒有等級、只有階級(總表的 level 欄存階級)。"""
        self.assertTrue(wipe("レベル４以下のモンスター", face=XYZ))
        self.assertFalse(wipe("ランク４以下のモンスター", face=XYZ))
        self.assertTrue(wipe("ランク４のモンスター"))

    def test_unknown_atk_cannot_be_compared(self):
        self.assertFalse(wipe("攻撃力１０００以下のモンスター", face=UNKNOWN_ATK))

    def test_uncomparable_modifiers_may_include_this_card(self):
        self.assertFalse(wipe("表側表示モンスター"))
        self.assertFalse(wipe("このカードと同じ種族のモンスター"))

    def test_condition_inside_a_modifier_does_not_count(self):
        """修飾語裡的種族說的是素材,不是群體本身。"""
        self.assertFalse(wipe("戦士族モンスターを素材としたモンスター"))
        self.assertFalse(wipe("戦士族以外のモンスター"))

    def test_alternatives_match_when_any_of_them_matches(self):
        self.assertFalse(wipe("「サイバー」モンスターかドラゴン族モンスター"))
        self.assertTrue(wipe("「サイバー」モンスターか戦士族モンスター"))

    def test_conditions_of_one_alternative_are_all_required(self):
        self.assertTrue(wipe("闇属性の戦士族モンスター"))
        self.assertFalse(wipe("闇属性のドラゴン族モンスター"))

    def test_archetype_compares_across_full_and_half_width(self):
        self.assertFalse(wipe("「DD」モンスター", face=dict(DRAGON, name_ja="ＤＤ魔導賢者")))

    def test_stats_count_each_blocker_and_uncomparable_literals(self):
        doc, _ = export({1: [clause("①", "①：自分フィールドの戦士族モンスターを全て破壊する。")],
                         2: [clause("①", "①：自分フィールドの表側表示モンスターを全て破壊する。")]},
                        {1: export_categories.card_face(DRAGON),
                         2: export_categories.card_face(DRAGON)})
        stats = doc["統計"]
        self.assertEqual(stats["理由"].get("非此卡:全部類種族對不上"), 1)
        self.assertEqual(stats["理由"].get("皆非:全部類比不了"), 1)
        self.assertEqual(stats["比不了字面"], {"表側表示モンスター": 1})


if __name__ == "__main__":
    unittest.main()
