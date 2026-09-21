"""效果 Tag 線的行為測試(票07/09/10/13)。

接縫與 test_tagcard 相同:tagcard.build_tag_cards 純函式,fixture 程式化建立。
只測外部行為:規則直貼、重跑保留、判空紀錄擋規則、時機承載、遮蔽計分、
收票關卡的少一筆多一筆指名道姓。
"""
import unittest

import masked_tags
import merge_tag_judgments as mtj
import tag_rules
from tagcard import build_tag_cards
from test_tagcard import card, clauses_of, faq, mark

SEARCH = "①：デッキから「試作機」１体を手札に加える。"
SEARCH_JA = "①：デッキから「試作機」１体を手札に加える。"
COST_SEARCH_ZH = "①：捨棄1張手牌可以發動。從牌組將1隻怪獸加入手牌。"
COST_SEARCH_JA = ("①：手札を１枚捨てて発動できる。"
                  "デッキからモンスター１体を手札に加える。")


def build(desc, card_text, **kwargs):
    return build_tag_cards([card(desc=desc)], [faq(card_text=card_text)],
                           **kwargs)


def tag_contents(clause):
    return {tuple(sorted((k, v) for k, v in tag.items()
                         if k not in ("src", "rule", "ticket")))
            for tag in clause["tags"]}


class TestRuleDirectWrite(unittest.TestCase):
    """規則層直接寫入 tags(ADR-0013),不是影子預測。"""

    def test_search_frame_writes_a_rule_tag(self):
        entries, report = build(SEARCH, SEARCH_JA)
        clause = clauses_of(entries, 1000)[0]
        tags = [t for t in clause["tags"] if t["src"] == "rule"]
        self.assertTrue(any(t.get("from") == "牌組" and t.get("to") == "手牌"
                            and t["pos"] == "效果" for t in tags))
        self.assertGreater(report["tag_rule_tags"], 0)

    def test_cost_in_activation_clause_is_tagged_as_cost(self):
        entries, _ = build(COST_SEARCH_ZH, COST_SEARCH_JA)
        clause = clauses_of(entries, 1000)[0]
        poses = {(t.get("from"), t.get("to"), t["pos"])
                 for t in clause["tags"]}
        self.assertIn(("手牌", "墓地", "成本"), poses)
        self.assertIn(("牌組", "手牌", "效果"), poses)

    def test_trigger_condition_is_not_tagged_as_movement(self):
        """觸發條件住在發動子句裡,處理段規則咬不到它。"""
        entries, _ = build(
            "①：怪獸被特殊召喚時可以發動。攻擊力上升500。",
            "①：モンスターが特殊召喚された場合に発動できる。"
            "攻撃力は５００アップする。")
        tags = clauses_of(entries, 1000)[0]["tags"]
        self.assertEqual([t for t in tags if t["cat"] == "區域移動"], [])
        # 處理段的「攻撃力は…アップ」自第3期起照貼攻守調整
        self.assertTrue(all(t["cat"] == "攻守調整" for t in tags))

    def test_old_style_clauses_are_out_of_scope(self):
        """第一期只貼新式卡文(index 帶①編號)。"""
        entries, report = build("從牌組將1隻怪獸加入手牌。",
                                "デッキからモンスター１体を手札に加える。")
        self.assertEqual(clauses_of(entries, 1000)[0]["tags"], [])
        self.assertEqual(report["tag_scope_clauses"], 0)


class TestPhase2Rules(unittest.TestCase):
    """第2期(票16):破壞與無效的規則直貼邊界。"""

    def cat_tags(self, entries, cat):
        clause = clauses_of(entries, 1000)[0]
        return [t for t in clause["tags"] if t.get("cat") == cat]

    def test_targeted_single_monster_destroy(self):
        entries, _ = build(
            "①:以場上1隻怪獸為對象發動。破壞那隻怪獸。",
            "①：フィールドのモンスター１体を対象として発動できる。"
            "そのモンスターを破壊する。")
        tags = self.cat_tags(entries, "破壞")
        self.assertTrue(any(t.get("what") == "怪獸"
                            and t.get("scope") == "單體"
                            and t["pos"] == "效果" for t in tags))

    def test_destroy_all_opponent_cards(self):
        entries, _ = build(
            "①:此卡召喚成功時發動。破壞對手場上全部的卡。",
            "①：このカードが召喚に成功した時に発動できる。"
            "相手フィールドのカードを全て破壊する。")
        tags = self.cat_tags(entries, "破壞")
        self.assertTrue(any(t.get("what") == "卡" and t.get("scope") == "全體"
                            for t in tags))
        self.assertTrue(any(t.get("side") == "對手" for t in tags))

    def test_negate_and_destroy_tags_both_categories(self):
        """「無効にし破壊」:無效帶附帶槽位,破壞照貼(第一期 mv 對附帶除外
        的先例——附帶處置也是動作)。"""
        entries, _ = build(
            "①:魔法卡發動時可以發動。使那次發動無效並破壞。",
            "①：魔法カードが発動した時に発動できる。"
            "その発動を無効にし破壊する。")
        ng = self.cat_tags(entries, "無效")
        self.assertTrue(any(t.get("what") == "發動"
                            and t.get("extra") == "破壞" for t in ng))
        ds = self.cat_tags(entries, "破壞")
        self.assertTrue(any(t.get("scope") == "單體" for t in ds))
        self.assertTrue(tag_rules.screen_hit(
            "破壞", "その発動を無効にし破壊する。"))

    def test_replacement_destroy_is_not_tagged(self):
        """「代わりに破壊」歸耐性(代替破壞),破壞規則不開火。"""
        entries, _ = build(
            "①:場上怪獸被破壞的場合,可以改為破壞此卡。",
            "①：フィールドのモンスターが戦闘で破壊される場合、"
            "代わりにこのカードを破壊する事ができる。")
        self.assertEqual(self.cat_tags(entries, "破壞"), [])

    def test_destroy_cost_in_activation_clause(self):
        entries, _ = build(
            "①:破壞我方場上1張魔法卡發動。抽1張卡。",
            "①：自分フィールドの魔法・罠カード１枚を破壊して発動できる。"
            "自分はデッキから１枚ドローする。")
        tags = self.cat_tags(entries, "破壞")
        self.assertTrue(any(t["pos"] == "成本" for t in tags))

    def test_chained_effect_negate(self):
        entries, _ = build(
            "①:對手怪獸效果發動時發動。使那個效果無效。",
            "①：相手モンスターの効果が発動した時に発動できる。"
            "その効果を無効にする。")
        tags = self.cat_tags(entries, "無效")
        self.assertTrue(any(t.get("what") == "效果" for t in tags))

    def test_continuous_negation(self):
        entries, _ = build(
            "①:裝備怪獸的效果無效化。",
            "①：装備モンスターの効果は無効化される。")
        tags = self.cat_tags(entries, "無效")
        self.assertTrue(any(t.get("what") == "持續無效化" for t in tags))

    def test_negation_immunity_is_not_tagged(self):
        """「無効化されない」是耐性,無效規則不開火、粗篩不圈。"""
        entries, _ = build(
            "①:此卡的發動與效果不會被無效化。",
            "①：このカードの発動と効果は無効化されない。")
        self.assertEqual(self.cat_tags(entries, "無效"), [])
        self.assertFalse(tag_rules.screen_hit(
            "無效", "このカードの発動と効果は無効化されない。"))


class TestPhase3Rules(unittest.TestCase):
    """第3期(票17):數值向五類的規則直貼邊界。"""

    def cat_tags(self, entries, cat):
        clause = clauses_of(entries, 1000)[0]
        return [t for t in clause["tags"] if t.get("cat") == cat]

    def test_atk_up_fixed(self):
        entries, _ = build(
            "①:場上龍族怪獸的攻擊力上升300。",
            "①：フィールドのドラゴン族モンスターの攻撃力は３００アップする。")
        tags = self.cat_tags(entries, "攻守調整")
        self.assertTrue(any(t.get("item") == "攻擊" and t.get("dir") == "上升"
                            and t["pos"] == "效果" for t in tags))

    def test_atk_def_down_combined(self):
        entries, _ = build(
            "①:對手場上怪獸的攻擊力、守備力下降500。",
            "①：相手フィールドのモンスターの攻撃力・守備力は"
            "５００ダウンする。")
        tags = self.cat_tags(entries, "攻守調整")
        self.assertTrue(any(t.get("item") == "攻守" and t.get("dir") == "下降"
                            for t in tags))
        self.assertFalse(any(t.get("item") in ("攻擊", "守備") for t in tags))

    def test_atk_becomes_doubled(self):
        entries, _ = build(
            "①:此卡的攻擊力直到回合結束時變成倍。",
            "①：このカードの攻撃力はターン終了時まで倍になる。")
        tags = self.cat_tags(entries, "攻守調整")
        self.assertTrue(any(t.get("item") == "攻擊" and t.get("dir") == "變成"
                            for t in tags))

    def test_mixed_directions_do_not_cross(self):
        """「攻撃力は…アップし、守備力は…ダウン」不得配成 攻擊×下降。"""
        entries, _ = build(
            "①:攻擊力上升500、守備力下降500。",
            "①：このカードの攻撃力は５００アップし、守備力は５００ダウン"
            "する。")
        tags = self.cat_tags(entries, "攻守調整")
        pairs = {(t.get("item"), t.get("dir")) for t in tags}
        self.assertIn(("攻擊", "上升"), pairs)
        self.assertIn(("守備", "下降"), pairs)
        self.assertNotIn(("攻擊", "下降"), pairs)
        self.assertNotIn(("守備", "上升"), pairs)

    def test_equip_modifier_form_is_not_tagged(self):
        """「攻撃力６００アップの装備魔法カード扱い」是賦予效果的修飾,
        不是攻守調整動作(動作歸放置轉換)。"""
        text_ja = ("①：自分の墓地からこのカードを攻撃力６００アップの"
                   "装備魔法カード扱いで自分のモンスターに装備する。")
        entries, _ = build("①:把此卡當作攻擊力上升600的裝備卡裝備。", text_ja)
        self.assertEqual(self.cat_tags(entries, "攻守調整"), [])
        self.assertFalse(tag_rules.screen_hit("攻守調整", text_ja))

    def test_damage_to_opponent_fixed(self):
        entries, _ = build(
            "①:給對手500傷害。",
            "①：相手に５００ダメージを与える。")
        tags = self.cat_tags(entries, "效果傷害")
        self.assertTrue(any(t.get("side") == "對手" for t in tags))
        self.assertTrue(any(t.get("form") == "固定值" for t in tags))

    def test_reference_damage_inverted_order(self):
        entries, _ = build(
            "①:給對手場上怪獸數量×100傷害。",
            "①：フィールドのモンスターの数×１００ダメージを相手に与える。")
        tags = self.cat_tags(entries, "效果傷害")
        self.assertTrue(any(t.get("side") == "對手" for t in tags))
        self.assertTrue(any(t.get("form") == "參照值" for t in tags))
        self.assertFalse(any(t.get("form") == "固定值" for t in tags))

    def test_self_damage_action(self):
        entries, _ = build(
            "①:我方準備階段發動。自己受到1000傷害。",
            "①：自分スタンバイフェイズに発動する。"
            "自分は１０００ダメージを受ける。")
        tags = self.cat_tags(entries, "效果傷害")
        self.assertTrue(any(t.get("side") == "我方" for t in tags))

    def test_battle_damage_modifier_is_not_tagged(self):
        """「戦闘ダメージは倍になる」是戰鬥傷害修飾,歸「其他」(批3)。"""
        text_ja = ("①：このカードの戦闘で発生する相手への戦闘ダメージは"
                   "倍になる。")
        entries, _ = build("①:此卡戰鬥發生的對對手戰鬥傷害變成倍。", text_ja)
        self.assertEqual(self.cat_tags(entries, "效果傷害"), [])
        self.assertFalse(tag_rules.screen_hit("效果傷害", text_ja))

    def test_heal_self_fixed(self):
        entries, _ = build(
            "①:自己回復1000基本分。",
            "①：自分は１０００LP回復する。")
        tags = self.cat_tags(entries, "生命回復")
        self.assertTrue(any(t.get("side") == "我方" for t in tags))
        self.assertTrue(any(t.get("form") == "固定值" for t in tags))

    def test_lp_pay_cost_has_no_pos(self):
        entries, _ = build(
            "①:支付800基本分才能發動。抽1張卡。",
            "①：８００LPを払って発動できる。自分はデッキから１枚ドロー"
            "する。")
        tags = self.cat_tags(entries, "LP支付")
        self.assertTrue(any(t.get("side") == "我方"
                            and t.get("form") == "固定值" for t in tags))
        self.assertTrue(all("pos" not in t for t in tags))

    def test_lp_pay_half_is_ratio(self):
        entries, _ = build(
            "①:支付一半基本分才能發動。",
            "①：LPを半分払って発動できる。フィールドのカードを全て破壊"
            "する。")
        tags = self.cat_tags(entries, "LP支付")
        self.assertTrue(any(t.get("form") == "比例" for t in tags))

    def test_lp_toll_on_opponent(self):
        """通行費形「相手は…払わなければ〜できない」貼 LP支付(對手)。"""
        entries, _ = build(
            "①:對手不支付600基本分就不能發動卡片效果。",
            "①：このカードがモンスターゾーンに存在する限り、相手は"
            "６００LPを払わなければ、カードの効果を発動できない。")
        tags = self.cat_tags(entries, "LP支付")
        self.assertTrue(any(t.get("side") == "對手" for t in tags))

    def test_lp_lose_self_reference(self):
        entries, _ = build(
            "①:自己失去回去的怪獸數量×1000基本分。",
            "①：その後、自分は戻したモンスターの数×１０００LPを失う。")
        tags = self.cat_tags(entries, "LP失去")
        self.assertTrue(any(t.get("side") == "我方" for t in tags))
        self.assertTrue(any(t.get("form") == "參照值" for t in tags))

    def test_opponent_pay_trigger_is_not_lpp(self):
        """「相手がLPを払って…発動する度に」是觸發敘述非支付動作;
        後段「相手は５００LPを失う」照貼 LP失去。"""
        entries, _ = build(
            "①:每次對手支付基本分發動效果,對手失去500基本分。",
            "①：自分フィールドに他の「氷結界」モンスターが存在する限り、"
            "相手がLPを払ってカードの効果を発動する度に相手は５００LPを"
            "失う。")
        self.assertEqual(self.cat_tags(entries, "LP支付"), [])
        tags = self.cat_tags(entries, "LP失去")
        self.assertTrue(any(t.get("side") == "對手" for t in tags))


class TestPhase4Rules(unittest.TestCase):
    """第4期(票18):行動限制與耐性/保護的規則直貼邊界。"""

    def cat_tags(self, entries, cat):
        clause = clauses_of(entries, 1000)[0]
        return [t for t in clause["tags"] if t.get("cat") == cat]

    def test_opponent_special_summon_lock(self):
        entries, _ = build(
            "①:此卡在怪獸區存在期間,對手不能特殊召喚怪獸。",
            "①：このカードがモンスターゾーンに存在する限り、"
            "相手はモンスターを特殊召喚できない。")
        tags = self.cat_tags(entries, "行動限制")
        self.assertTrue(any(t.get("what") == "特殊召喚"
                            and t.get("side") == "對手"
                            and t["pos"] == "效果" for t in tags))
        self.assertTrue(any(t.get("term") == "持續" for t in tags))

    def test_oath_self_restriction_is_tagged(self):
        """誓約尾句是行動限制動作(側=我方,批2 裁定)。"""
        entries, _ = build(
            "①:從牌組將1隻怪獸加入手牌。此效果發動後直到回合結束,"
            "自己不能特殊召喚怪獸。",
            "①：デッキからモンスター１体を手札に加える。"
            "この効果の発動後、ターン終了時まで自分はモンスターを"
            "特殊召喚できない。")
        tags = self.cat_tags(entries, "行動限制")
        self.assertTrue(any(t.get("what") == "特殊召喚"
                            and t.get("side") == "我方" for t in tags))
        self.assertTrue(any(t.get("term") == "單回合" for t in tags))

    def test_summon_modifier_form_is_not_tagged(self):
        """「通常召喚できないモンスター」是對象修飾非限制動作。"""
        text_ja = ("①：自分の墓地の通常召喚できないモンスター１体を"
                   "対象として発動できる。そのモンスターを特殊召喚する。")
        entries, _ = build("①:以墓地1隻不能通常召喚的怪獸為對象發動。"
                           "特殊召喚那隻怪獸。", text_ja)
        self.assertEqual(self.cat_tags(entries, "行動限制"), [])
        self.assertFalse(tag_rules.screen_hit("行動限制", text_ja))

    def test_self_restriction_with_negation_immunity(self):
        """「自分は〜しか特殊召喚できない。この効果は無効化されない」:
        前半行動限制(我方)、後半無效化保護(what 缺值只貼類別)。"""
        entries, _ = build(
            "①:自己只能特殊召喚「機關」怪獸。此效果不會被無效化。",
            "①：自分は「クリフォート」モンスターしか特殊召喚できない。"
            "この効果は無効化されない。")
        rs = self.cat_tags(entries, "行動限制")
        self.assertTrue(any(t.get("what") == "特殊召喚"
                            and t.get("side") == "我方" for t in rs))
        pt = self.cat_tags(entries, "耐性/保護")
        self.assertTrue(any("what" not in t for t in pt))

    def test_direct_attack_is_not_restriction(self):
        """「直接攻撃できない」歸戰鬥規則(批2),行動限制不開火不圈。"""
        text_ja = "①：このカードは直接攻撃できない。"
        entries, _ = build("①:此卡不能直接攻擊。", text_ja)
        self.assertEqual(self.cat_tags(entries, "行動限制"), [])
        self.assertFalse(tag_rules.screen_hit("行動限制", text_ja))

    def test_attack_lock_on_self(self):
        entries, _ = build(
            "①:此卡不能攻擊。",
            "①：このカードは攻撃できない。")
        tags = self.cat_tags(entries, "行動限制")
        self.assertTrue(any(t.get("what") == "攻擊"
                            and t.get("side") == "自身" for t in tags))

    def test_battle_and_effect_destruction_protection(self):
        """合記「戦闘・効果では破壊されない」戰鬥/效果兩面各貼。"""
        entries, _ = build(
            "①:此卡不會被戰鬥、效果破壞。",
            "①：このカードは戦闘・効果では破壊されない。")
        tags = self.cat_tags(entries, "耐性/保護")
        whats = {t.get("what") for t in tags}
        self.assertIn("戰鬥破壞", whats)
        self.assertIn("效果破壞", whats)
        self.assertTrue(any(t.get("side") == "自身" for t in tags))

    def test_active_target_protection(self):
        """「効果の対象にできない」是「にならない」的能動寫法,歸耐性。"""
        entries, _ = build(
            "①:對手不能以自己場上的魔法師族怪獸為效果對象。",
            "①：このカードがモンスターゾーンに存在する限り、自分フィールド"
            "の魔法使い族モンスターを相手は効果の対象にできない。")
        tags = self.cat_tags(entries, "耐性/保護")
        self.assertTrue(any(t.get("what") == "效果對象" for t in tags))
        self.assertTrue(any(t.get("side") == "我方" for t in tags))

    def test_replacement_destroy_protection(self):
        entries, _ = build(
            "①:場上怪獸被破壞的場合,可以改為破壞此卡。",
            "①：フィールドのモンスターが戦闘で破壊される場合、"
            "代わりにこのカードを破壊する事ができる。")
        tags = self.cat_tags(entries, "耐性/保護")
        self.assertTrue(any(t.get("what") == "代替破壞" for t in tags))

    def test_toll_restriction_both_faces(self):
        """通行費「払わなければ〜できない」:支付面 LP支付、限制面行動限制,
        兩面各自成立。"""
        entries, _ = build(
            "①:對手不支付600基本分就不能發動卡片效果。",
            "①：このカードがモンスターゾーンに存在する限り、相手は"
            "６００LPを払わなければ、カードの効果を発動できない。")
        self.assertTrue(any(t.get("side") == "對手" for t in
                            self.cat_tags(entries, "LP支付")))
        rs = self.cat_tags(entries, "行動限制")
        self.assertTrue(any(t.get("what") == "發動效果"
                            and t.get("side") == "對手" for t in rs))

    def test_self_effect_usage_condition_is_not_tagged(self):
        """「この効果は…にしか発動できない」是自我使用條件非限制動作。"""
        text_ja = ("①：フィールドの表側表示モンスター１体を対象として"
                   "発動できる。そのモンスターの表示形式を変更する。"
                   "この効果は自分ターンにしか発動できない。")
        entries, _ = build("①:變更場上1隻怪獸的表示形式。此效果只能在"
                           "自己回合發動。", text_ja)
        self.assertEqual(self.cat_tags(entries, "行動限制"), [])
        self.assertFalse(tag_rules.screen_hit("行動限制", text_ja))


class TestPhase5Rules(unittest.TestCase):
    """第5期(票19):狀態向四類的規則直貼邊界。"""

    def cat_tags(self, entries, cat):
        clause = clauses_of(entries, 1000)[0]
        return [t for t in clause["tags"] if t.get("cat") == cat]

    def test_free_position_change_has_no_to(self):
        """「表示形式を変更する」自由選,to 缺值只貼類別(裁定批3)。"""
        entries, _ = build(
            "①:以場上1隻怪獸為對象發動。變更那隻怪獸的表示形式。",
            "①：フィールドのモンスター１体を対象として発動できる。"
            "そのモンスターの表示形式を変更する。")
        tags = self.cat_tags(entries, "表示形式變更")
        self.assertTrue(any("to" not in t and t["pos"] == "效果"
                            for t in tags))

    def test_face_down_defense_maps_to_face_down(self):
        """裏側守備表示=裡側表示,不是守備表示(to 映射照字面)。"""
        entries, _ = build(
            "①:對手特殊召喚怪獸時可以發動。那隻怪獸變成裡側守備表示。",
            "①：相手がモンスターを特殊召喚した時に発動できる。"
            "そのモンスターを裏側守備表示にする。")
        tags = self.cat_tags(entries, "表示形式變更")
        self.assertTrue(any(t.get("to") == "裡側表示" for t in tags))
        self.assertFalse(any(t.get("to") == "守備表示" for t in tags))

    def test_self_defense_position_change(self):
        entries, _ = build(
            "①:此卡召喚的場合發動。此卡變成守備表示。",
            "①：このカードが召喚した場合に発動する。"
            "このカードを守備表示にする。")
        tags = self.cat_tags(entries, "表示形式變更")
        self.assertTrue(any(t.get("to") == "守備表示"
                            and t.get("side") == "自身" for t in tags))

    def test_position_at_summon_is_not_a_change(self):
        """「守備表示で特殊召喚」是召喚時表示指定(に/で 粒子切分),不貼不圈。"""
        text_ja = ("①：自分の墓地のモンスター１体を対象として発動できる。"
                   "そのモンスターを守備表示で特殊召喚する。")
        entries, _ = build("①:以墓地1隻怪獸為對象發動。將那隻怪獸守備表示"
                           "特殊召喚。", text_ja)
        self.assertEqual(self.cat_tags(entries, "表示形式變更"), [])
        self.assertFalse(tag_rules.screen_hit("表示形式變更", text_ja))

    def test_position_or_choice_tags_both(self):
        """或格「表側攻撃表示か裏側守備表示にする」兩面各貼(第3期先例)。"""
        entries, _ = build(
            "①:此卡反轉的場合以場上1隻怪獸為對象發動。那隻怪獸變成表側"
            "攻擊表示或裡側守備表示。",
            "①：このカードがリバースした場合、フィールドの他のモンスター"
            "１体を対象として発動できる。そのモンスターを表側攻撃表示か"
            "裏側守備表示にする。")
        tos = {t.get("to") for t in self.cat_tags(entries, "表示形式變更")}
        self.assertIn("攻擊表示", tos)
        self.assertIn("裡側表示", tos)

    def test_control_gain(self):
        entries, _ = build(
            "①:以對手場上1隻怪獸為對象發動。直到結束階段得到那隻怪獸的"
            "控制權。",
            "①：相手フィールドのモンスター１体を対象として発動できる。"
            "そのモンスターのコントロールをエンドフェイズまで得る。")
        tags = self.cat_tags(entries, "控制權轉移")
        self.assertTrue(any(t.get("dir") == "取得" and t["pos"] == "效果"
                            for t in tags))

    def test_control_give_and_swap(self):
        """「相手に移す」=移交;「入れ替える」互換兩向各貼(代行裁定)。"""
        entries, _ = build(
            "①:此卡的控制權轉移給對手。",
            "①：自分スタンバイフェイズに発動する。"
            "このカードのコントロールを相手に移す。")
        self.assertTrue(any(t.get("dir") == "移交" for t in
                            self.cat_tags(entries, "控制權轉移")))
        entries, _ = build(
            "①:交換那2隻怪獸的控制權。",
            "①：自分及び相手フィールドの表側表示モンスターを１体ずつ対象"
            "として発動できる。そのモンスター２体のコントロールを"
            "入れ替える。")
        dirs = {t.get("dir") for t in self.cat_tags(entries, "控制權轉移")}
        self.assertEqual(dirs, {"取得", "移交"})

    def test_control_gained_modifier_is_not_tagged(self):
        """「この効果でコントロールを得たモンスター」完成/修飾形非動作。"""
        text_ja = ("①：この効果でコントロールを得たモンスターは"
                   "攻撃できない。")
        entries, _ = build("①:以此效果得到控制權的怪獸不能攻擊。", text_ja)
        self.assertEqual(self.cat_tags(entries, "控制權轉移"), [])
        self.assertFalse(tag_rules.screen_hit("控制權轉移", text_ja))

    def test_card_name_treatment_with_continuous_term(self):
        entries, _ = build(
            "①:此卡在怪獸區存在期間,卡名當作「死亡青蛙」使用。",
            "①：このカードはモンスターゾーンに存在する限り、"
            "カード名を「デスガエル」として扱う。")
        tags = self.cat_tags(entries, "性質變更")
        self.assertTrue(any(t.get("item") == "卡名"
                            and t.get("term") == "持續" for t in tags))

    def test_declared_race_and_attribute_tags_both(self):
        """「宣言した種族・属性になる」合記兩面各貼。"""
        entries, _ = build(
            "①:那隻怪獸直到回合結束變成宣言的種族、屬性。",
            "①：種族と属性を１つずつ宣言し、フィールドの表側表示モンスター"
            "１体を対象として発動できる。そのモンスターはターン終了時まで"
            "宣言した種族・属性になる。")
        items = {t.get("item") for t in self.cat_tags(entries, "性質變更")}
        self.assertIn("種族", items)
        self.assertIn("屬性", items)

    def test_level_becomes_and_raises(self):
        entries, _ = build(
            "①:這個效果特殊召喚的怪獸等級變成1。",
            "①：この効果で特殊召喚したモンスターのレベルは１になり、"
            "効果は無効化される。")
        self.assertTrue(any(t.get("item") == "等級" for t in
                            self.cat_tags(entries, "性質變更")))
        entries, _ = build(
            "①:以場上1隻怪獸為對象發動。那隻怪獸的等級上升1個。",
            "①：フィールドの表側表示モンスター１体を対象として発動できる。"
            "そのモンスターのレベルを１つ上げる。")
        self.assertTrue(any(t.get("item") == "等級" for t in
                            self.cat_tags(entries, "性質變更")))

    def test_tuner_treatment_has_no_item_value(self):
        """值域無對應 item 值的扱う形(チューナー等)缺值只貼類別+term。"""
        entries, _ = build(
            "①:以我方場上1隻怪獸為對象發動。這個回合,那隻怪獸當作調整"
            "怪獸使用。",
            "①：自分フィールドのモンスター１体を対象として発動できる。"
            "このターン、そのモンスターをチューナーとして扱う。")
        tags = self.cat_tags(entries, "性質變更")
        self.assertTrue(any("item" not in t and t.get("term") == "單回合"
                            for t in tags))

    def test_treat_annotation_is_not_tagged(self):
        """「(罠カードとしては扱わない)」括弧註記非動作,不圈。"""
        text_ja = ("①：このカードは発動後、効果モンスター（機械族・地・"
                   "星４・攻１８００／守１０００）となり、モンスターゾーンに"
                   "特殊召喚する（罠カードとしては扱わない）。")
        entries, _ = build("①:此卡發動後,變成效果怪獸特殊召喚(不當作"
                           "陷阱卡使用)。", text_ja)
        self.assertEqual(self.cat_tags(entries, "性質變更"), [])
        self.assertFalse(tag_rules.screen_hit("性質變更", text_ja))

    def test_counter_place_and_cost_removal(self):
        entries, _ = build(
            "①:在此卡放置1個魔力指示物。",
            "①：装備モンスターが戦闘を行う攻撃宣言時に発動する。"
            "このカードに魔力カウンターを１つ置く。")
        self.assertTrue(any(t.get("act") == "放置" and t["pos"] == "效果"
                            for t in self.cat_tags(entries, "計數器操作")))
        entries, _ = build(
            "①:取除此卡2個魔力指示物,以場上1張蓋卡為對象發動。破壞那"
            "張卡。",
            "①：このカードの魔力カウンターを２つ取り除き、フィールドの"
            "カード１枚を対象として発動できる。そのカードを破壊する。")
        self.assertTrue(any(t.get("act") == "去除" and t["pos"] == "成本"
                            for t in self.cat_tags(entries, "計數器操作")))

    def test_xyz_material_detach_is_not_counter(self):
        """「X素材を取り除く」不是計數器操作(カウンター 錨天然不配)。"""
        text_ja = ("①：このカードのX素材を１つ取り除いて発動できる。"
                   "フィールドのカード１枚を対象として破壊する。")
        entries, _ = build("①:取除此卡1個X素材可以發動。破壞場上1張卡。",
                           text_ja)
        self.assertEqual(self.cat_tags(entries, "計數器操作"), [])
        self.assertFalse(tag_rules.screen_hit("計數器操作", text_ja))

    def test_counter_placed_trigger_is_not_tagged(self):
        """「カウンターが置かれた場合」是觸發事件非動作。"""
        text_ja = ("①：このカードに魔力カウンターが置かれた場合に発動"
                   "できる。自分はデッキから１枚ドローする。")
        entries, _ = build("①:此卡被放置魔力指示物的場合可以發動。自己從"
                           "牌組抽1張卡。", text_ja)
        self.assertEqual(self.cat_tags(entries, "計數器操作"), [])
        self.assertFalse(tag_rules.screen_hit("計數器操作", text_ja))


class TestTagPreservation(unittest.TestCase):
    """llm/manual 的 tag 走「判定一次就算數」,rule 的 tag 每次重算。"""

    def rebuilt_with_llm_tag(self, tag):
        existing, _ = build(SEARCH, SEARCH_JA)
        clause = clauses_of(existing, 1000)[0]
        mark(existing, 1000, "①", tags=clause["tags"] + [tag])
        return build(SEARCH, SEARCH_JA, existing=existing)

    def test_llm_tag_survives_rebuild_even_on_rule_sourced_kind(self):
        """kind 是 rule 來源的行也可能帶著 llm tag,不得隨重跑洗掉。"""
        llm_tag = {"cat": "區域移動", "to": "場上", "pos": "效果",
                   "src": "llm", "ticket": "票T"}
        entries, _ = self.rebuilt_with_llm_tag(llm_tag)
        clause = clauses_of(entries, 1000)[0]
        self.assertIn(("cat", "區域移動"),
                      [item for tags in tag_contents(clause)
                       for item in tags])
        self.assertTrue(any(t.get("src") == "llm" and t.get("to") == "場上"
                            for t in clause["tags"]))

    def test_identical_content_upgrades_to_llm_then_rule(self):
        llm_tag = {"cat": "區域移動", "from": "牌組", "to": "手牌",
                   "pos": "效果", "src": "llm", "ticket": "票T"}
        existing, _ = build(SEARCH, SEARCH_JA)
        mark(existing, 1000, "①", tags=[llm_tag])
        entries, _ = build(SEARCH, SEARCH_JA, existing=existing)
        clause = clauses_of(entries, 1000)[0]
        srcs = [t["src"] for t in clause["tags"]
                if t.get("from") == "牌組" and t.get("to") == "手牌"]
        self.assertEqual(srcs, ["llm_then_rule"])

    def test_checked_category_blocks_rule_write_and_reports(self):
        """LLM 判空的類別,規則不再寫入,不一致進報告。"""
        existing, _ = build(SEARCH, SEARCH_JA)
        mark(existing, 1000, "①", tags=[], tags_checked=["區域移動"])
        entries, report = build(SEARCH, SEARCH_JA, existing=existing)
        clause = clauses_of(entries, 1000)[0]
        self.assertEqual(clause["tags"], [])
        self.assertEqual(clause["tags_checked"], ["區域移動"])
        # 檢索句同時命中特定與泛用兩條規則,兩個被擋的 tag 都要看得見
        self.assertGreaterEqual(len(report["tag_rule_vs_llm"]), 1)
        self.assertTrue(all(row["id"] == 1000
                            for row in report["tag_rule_vs_llm"]))


class TestTiming(unittest.TestCase):
    """觸發時機:只長在誘發系承載類型、規則值重算、llm 值保留。"""

    TRIGGER_ZH = "①:此卡召喚成功時發動。抽1張卡。"
    TRIGGER_JA = ("①：このカードが召喚に成功した場合に発動する。"
                  "自分はデッキから１枚ドローする。")

    def judged(self, kind):
        judgments = [{"id": 1000, "section": "main",
                      "clauses": [{"index": "①", "kind": kind,
                                   "optional": "必發"}]}]
        return build(self.TRIGGER_ZH, self.TRIGGER_JA, judgments=judgments)

    def test_trigger_kind_gets_rule_timing(self):
        entries, _ = self.judged("誘發效果(1速)")
        clause = clauses_of(entries, 1000)[0]
        self.assertEqual((clause["timing"], clause["timing_src"]),
                         ("召喚成功時", "rule"))

    def test_non_carrier_kind_gets_no_timing(self):
        entries, report = self.judged("永續效果")
        clause = clauses_of(entries, 1000)[0]
        self.assertIsNone(clause["timing"])
        self.assertEqual(report["timing_on_wrong_kind"], [])

    def test_llm_timing_survives_and_conflicts_are_reported(self):
        entries, _ = self.judged("誘發效果(1速)")
        mark(entries, 1000, "①", timing="其他", timing_src="llm")
        rebuilt, report = build(self.TRIGGER_ZH, self.TRIGGER_JA,
                                existing=entries)
        clause = clauses_of(rebuilt, 1000)[0]
        # kind 隨 existing 保留,規則時機與 llm 值不同 → 保留 llm、列衝突
        self.assertEqual((clause["timing"], clause["timing_src"]),
                         ("其他", "llm"))
        self.assertEqual(len(report["timing_rule_vs_llm"]), 1)

    def test_matching_llm_timing_upgrades(self):
        entries, _ = self.judged("誘發效果(1速)")
        mark(entries, 1000, "①", timing="召喚成功時", timing_src="llm")
        rebuilt, _ = build(self.TRIGGER_ZH, self.TRIGGER_JA,
                           existing=entries)
        clause = clauses_of(rebuilt, 1000)[0]
        self.assertEqual(clause["timing_src"], "llm_then_rule")


class TestMaskedTags(unittest.TestCase):
    """遮蔽測試計分:錯標與框架 recall 都對著標準答案現場重算。"""

    def setUp(self):
        self.entries, _ = build(SEARCH, SEARCH_JA)
        self.sample = [{"id": 1000, "section": "main", "index": "①",
                        "name_zh": "測試卡", "text_zh": SEARCH,
                        "text_ja": SEARCH_JA}]

    def score(self, tags):
        answers = [{"id": 1000, "section": "main", "index": "①",
                    "tags": tags}]
        return masked_tags.score_tag_masked(self.entries, self.sample,
                                            answers)

    def test_agreeing_truth_passes(self):
        res = self.score([{"cat": "區域移動", "from": "牌組", "to": "手牌",
                           "side": "我方", "pos": "效果"}])
        self.assertEqual(sum(r["wrong"] for r in res["rules"]), 0)
        self.assertEqual(res["category_recall"], 1.0)

    def test_disagreeing_truth_counts_a_wrong(self):
        res = self.score([{"cat": "區域移動", "from": "墓地", "to": "手牌",
                           "pos": "效果"}])
        self.assertGreater(sum(r["wrong"] for r in res["rules"]), 0)
        self.assertFalse(res["passed"])

    def test_missing_answer_is_named(self):
        res = masked_tags.score_tag_masked(self.entries, self.sample, [])
        self.assertEqual(res["missing"], [(1000, "main", "①")])
        self.assertFalse(res["passed"])


class TestMergeGates(unittest.TestCase):
    """收票關卡:少一筆多一筆指名道姓、值不在正典、改判旗標對帳。"""

    BATCH = {"series": "tag-mv", "category": "區域移動", "entries": [
        {"id": 1000, "section": "main", "index": "①",
         "text_ja": SEARCH_JA, "kind": "啟動效果"},
        {"id": 1000, "section": "main", "index": "②",
         "text_ja": "②：効果乙。", "kind": "啟動效果", "rejudge": True},
    ]}

    def test_missing_and_extra_rows_are_named(self):
        result = [{"id": 1000, "section": "main", "index": "①", "tags": []},
                  {"id": 9999, "section": "main", "index": "①", "tags": []}]
        problems = mtj.set_problems(self.BATCH, result)
        self.assertTrue(any("少了 (1000, 'main', '②')" in p
                            for p in problems))
        self.assertTrue(any("多了 (9999, 'main', '①')" in p
                            for p in problems))

    def test_rejudge_flags_must_match_both_ways(self):
        result = [{"id": 1000, "section": "main", "index": "①", "tags": [],
                   "rejudge": True},
                  {"id": 1000, "section": "main", "index": "②", "tags": []}]
        problems = mtj.rejudge_problems(self.BATCH, result)
        self.assertEqual(len(problems), 2)

    def test_out_of_canon_value_is_named(self):
        result = [{"id": 1000, "section": "main", "index": "①",
                   "tags": [{"cat": "區域移動", "from": "牌組頂",
                             "to": "手牌", "pos": "效果"}]},
                  {"id": 1000, "section": "main", "index": "②", "tags": [],
                   "rejudge": True}]
        problems = mtj.value_problems(self.BATCH, result)
        self.assertEqual(len(problems), 1)
        self.assertIn("解不進正典", problems[0])

    def test_apply_marks_checked_and_stamps_ticket(self):
        entries, _ = build(SEARCH, SEARCH_JA)
        batch = {"series": "tag-mv", "category": "區域移動", "entries": [
            {"id": 1000, "section": "main", "index": "①",
             "text_ja": SEARCH_JA, "kind": None}]}
        result = [{"id": 1000, "section": "main", "index": "①",
                   "tags": [{"cat": "區域移動", "to": "手牌",
                             "pos": "效果"}]}]
        problems = mtj.apply_rows(entries, batch, result, "票測")
        self.assertEqual(problems, [])
        clause = clauses_of(entries, 1000)[0]
        self.assertIn("區域移動", clause["tags_checked"])
        self.assertTrue(any(t.get("ticket") == "票測" and t["src"] == "llm"
                            for t in clause["tags"]))

    def test_stale_text_is_rejected(self):
        entries, _ = build(SEARCH, SEARCH_JA)
        batch = {"series": "tag-mv", "category": "區域移動", "entries": [
            {"id": 1000, "section": "main", "index": "①",
             "text_ja": "①：昔の文。", "kind": None}]}
        result = [{"id": 1000, "section": "main", "index": "①", "tags": []}]
        problems = mtj.apply_rows(entries, batch, result, "票測")
        self.assertEqual(len(problems), 1)
        self.assertIn("卡文已變動", problems[0])


class TestScreenAndRegistry(unittest.TestCase):
    def test_screen_hits_action_not_pure_negation(self):
        self.assertTrue(tag_rules.screen_hit(
            "區域移動", "デッキからモンスター１体を特殊召喚する。"))
        self.assertFalse(tag_rules.screen_hit(
            "區域移動", "お互いにモンスターを特殊召喚できない。"))

    def test_registry_is_clean(self):
        self.assertEqual(tag_rules.problems(), [])


if __name__ == "__main__":
    unittest.main()
