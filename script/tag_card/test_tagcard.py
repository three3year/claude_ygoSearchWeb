"""效果標記表管線測試(拆句骨架)。

接縫:tagcard.build_tag_cards(卡片總表條目, 補足情報條目[, 既有標記表, 判定結果,
拆句表]) → (entries, report)。fixture 於測試內程式化建立,不碰網路與真實資料檔。
"""
import unittest

import rules
from tagcard import build_tag_cards, card_type_label, split_hash

TYPE_NORMAL_MONSTER = 0x11       # 怪獸 + 通常
TYPE_EFFECT_MONSTER = 0x21       # 怪獸 + 效果
TYPE_PENDULUM_EFFECT = 0x1000021  # 怪獸 + 效果 + 靈擺
TYPE_PENDULUM_NORMAL = 0x1000011  # 怪獸 + 通常 + 靈擺
TYPE_FUSION_MONSTER = 0x61       # 怪獸 + 效果 + 融合
TYPE_SPELL = 0x2                 # 魔法(沒有細分位元 = 通常魔法)
TYPE_QUICKPLAY_SPELL = 0x10002   # 魔法 + 速攻
TYPE_CONTINUOUS_SPELL = 0x20002  # 魔法 + 永續
TYPE_EQUIP_SPELL = 0x40002       # 魔法 + 裝備
TYPE_FIELD_SPELL = 0x80002       # 魔法 + 場地
TYPE_RITUAL_SPELL = 0x82         # 魔法 + 儀式
TYPE_TRAP = 0x4                  # 陷阱(沒有細分位元 = 通常陷阱)
TYPE_CONTINUOUS_TRAP = 0x20004   # 陷阱 + 永續
TYPE_COUNTER_TRAP = 0x100004     # 陷阱 + 反擊


def card(cid=1000, desc="", ctype=TYPE_EFFECT_MONSTER, name_zh="測試卡",
         name_ja="テストカード"):
    return {"id": cid, "name_zh": name_zh, "name_ja": name_ja,
            "desc": desc, "type": ctype}


def faq(password=1000, card_text="", supplement=None, pen_effect=None,
        pen_supplement=None, name_ja="テストカード"):
    entry = {"cid": password // 10, "password": password, "name_ja": name_ja,
             "card_text": card_text}
    if supplement is not None:
        entry["supplement"] = supplement
    if pen_effect is not None:
        entry["pen_effect"] = pen_effect
    if pen_supplement is not None:
        entry["pen_supplement"] = pen_supplement
    return entry


def clauses_of(entries, cid):
    for entry in entries:
        if entry["id"] == cid:
            return entry["clauses"]
    raise AssertionError(f"標記表沒有 {cid}")


def mark(entries, cid, index, **fields):
    """把既有標記表的某一行改成使用者手工修正(或前一票判定)後的樣子。

    既有標記表的 fixture 一律由「先建一次再改幾行」產生,text_hash 因此自然
    與重跑時算出來的一致——不必在測試裡複製雜湊邏輯。
    """
    for clause in clauses_of(entries, cid):
        if clause["index"] == index:
            clause.update(fields)
            return clause
    raise AssertionError(f"{cid} 沒有 index={index} 的效果句")


class TestNumberedSplitting(unittest.TestCase):
    """有編號卡文的拆句與繁中/日文對位。"""

    def test_two_numbered_effects_paired_with_japanese(self):
        entries, report = build_tag_cards(
            [card(desc="①：效果甲。\n②：效果乙。")],
            [faq(card_text="①：効果甲。②：効果乙。")])
        clauses = clauses_of(entries, 1000)
        self.assertEqual([c["index"] for c in clauses], ["①", "②"])
        self.assertEqual([c["section"] for c in clauses], ["main", "main"])
        self.assertEqual([c["text_zh"] for c in clauses],
                         ["①：效果甲。", "②：效果乙。"])
        self.assertEqual([c["text_ja"] for c in clauses],
                         ["①：効果甲。", "②：効果乙。"])
        self.assertEqual(report["clauses"], 2)

    def test_clause_has_all_fields_and_kind_is_null(self):
        entries, _ = build_tag_cards(
            [card(desc="①：效果甲。")], [faq(card_text="①：効果甲。")])
        clause = clauses_of(entries, 1000)[0]
        self.assertEqual(list(clause), [
            "index", "section", "text_zh", "text_ja", "text_hash", "kind",
            "optional", "role", "source", "needs_review", "rule_predicted",
            "confidence", "tags"])
        self.assertIsNone(clause["kind"])
        self.assertIsNone(clause["optional"])
        self.assertIsNone(clause["role"])
        self.assertIsNone(clause["source"])
        self.assertFalse(clause["needs_review"])
        self.assertIsNone(clause["rule_predicted"])
        self.assertEqual(clause["tags"], [])

    def test_japanese_without_newlines_still_splits(self):
        """官方日文卡文常整段不換行,切割不能只靠行首。"""
        entries, report = build_tag_cards(
            [card(desc="①：效果甲。\n②：效果乙。\n③：效果丙。")],
            [faq(card_text="①：効果甲。②：効果乙。③：効果丙。")])
        clauses = clauses_of(entries, 1000)
        self.assertEqual([c["text_ja"] for c in clauses],
                         ["①：効果甲。", "②：効果乙。", "③：効果丙。"])
        self.assertEqual(report["numeral_mismatch"], [])

    def test_bullet_sub_effects_stay_inside_their_clause(self):
        """● 子效果本票不拆(留給官方明示票),整段留在所屬效果句內。"""
        entries, _ = build_tag_cards(
            [card(desc="①：可以選1個發動。\n●選項甲。\n●選項乙。")],
            [faq(card_text="①：１つを選んで発動できる。\n●選択肢甲。\n●選択肢乙。")])
        clauses = clauses_of(entries, 1000)
        self.assertEqual(len(clauses), 1)
        self.assertIn("●選項乙。", clauses[0]["text_zh"])


class TestInlineNumeral(unittest.TestCase):
    """文中編號不得作為切割點(回歸測試)。"""

    def test_usage_limit_with_inline_numerals_is_not_split(self):
        entries, _ = build_tag_cards(
            [card(desc="這個卡名的①②效果1回合各能使用1次。\n①：效果甲。\n②：效果乙。")],
            [faq(card_text="このカード名の①②の効果はそれぞれ１ターンに１度しか"
                           "使用できない。①：効果甲。②：効果乙。")])
        clauses = clauses_of(entries, 1000)
        self.assertEqual([c["index"] for c in clauses], ["0", "①", "②"])
        self.assertEqual(clauses[0]["text_zh"],
                         "這個卡名的①②效果1回合各能使用1次。")
        self.assertEqual(clauses[0]["text_ja"],
                         "このカード名の①②の効果はそれぞれ１ターンに１度しか"
                         "使用できない。")

    def test_inline_numeral_inside_a_numbered_clause_is_not_split(self):
        entries, _ = build_tag_cards(
            [card(desc="①：適用②效果的場合可以發動。\n②：效果乙。")],
            [faq(card_text="①：②の効果を適用する場合に発動できる。②：効果乙。")])
        self.assertEqual([c["index"] for c in clauses_of(entries, 1000)],
                         ["①", "②"])


class TestPreamble(unittest.TestCase):
    """前言段抽取與 role 三種子分類。"""

    def test_preamble_is_non_effect_text_from_rule_layer(self):
        entries, report = build_tag_cards(
            [card(desc="這個卡名的①效果1回合只能使用1次。\n①：效果甲。")],
            [faq(card_text="このカード名の①の効果は１ターンに１度しか使用できない。"
                           "①：効果甲。")])
        preamble = clauses_of(entries, 1000)[0]
        self.assertEqual(preamble["index"], "0")
        self.assertEqual(preamble["kind"], "效果外文本")
        self.assertEqual(preamble["source"], "rule")
        self.assertEqual(preamble["role"], "使用次數限制")
        self.assertEqual(report["preambles"], 1)

    def test_role_material_from_extra_deck_material_line(self):
        entries, _ = build_tag_cards(
            [card(desc="「青眼白龍」+「青眼白龍」\n①：此卡不會被戰鬥破壞。",
                  ctype=TYPE_FUSION_MONSTER)],
            [faq(card_text="「青眼の白龍」＋「青眼の白龍」\n"
                           "①：このカードは戦闘では破壊されない。")])
        self.assertEqual(clauses_of(entries, 1000)[0]["role"], "素材指定")

    def test_role_summon_condition(self):
        entries, _ = build_tag_cards(
            [card(desc="此卡不能通常召喚。只能解放我方場上的怪獸來特殊召喚。\n"
                       "①：效果甲。")],
            [faq(card_text="このカードは通常召喚できない。自分フィールドの"
                           "モンスターをリリースした場合のみ特殊召喚できる。①：効果甲。")])
        self.assertEqual(clauses_of(entries, 1000)[0]["role"], "召喚條件")

    def test_role_material_for_ritual_advent_line(self):
        """儀式怪獸的「藉由「〜」降臨」是素材指定;有無句號都要認得。"""
        for desc_line in ("藉由「機械天使的儀式」降臨", "藉由「機械天使的儀式」降臨。"):
            with self.subTest(desc_line=desc_line):
                entries, _ = build_tag_cards(
                    [card(desc=f"{desc_line}\n①：效果甲。", ctype=0xa1)],
                    [faq(card_text="「機械天使の儀式」により降臨。①：効果甲。")])
                self.assertEqual(clauses_of(entries, 1000)[0]["role"], "素材指定")

    def test_role_summon_condition_for_tribute_summon(self):
        entries, _ = build_tag_cards(
            [card(desc="此卡可以解放1隻恐龍族怪獸以表側攻擊表示上級召喚。\n①：效果甲。")],
            [faq(card_text="このカードは恐竜族モンスター１体をリリースし、表側攻撃表示で"
                           "アドバンス召喚できる。①：効果甲。")])
        self.assertEqual(clauses_of(entries, 1000)[0]["role"], "召喚條件")

    def test_role_usage_limit_counted_per_duel(self):
        entries, _ = build_tag_cards(
            [card(desc="這個卡名的①效果在決鬥中只能使用1次。\n①：效果甲。")],
            [faq(card_text="このカード名の①の効果はデュエル中に１度しか使用できない。"
                           "①：効果甲。")])
        self.assertEqual(clauses_of(entries, 1000)[0]["role"], "使用次數限制")

    def test_role_none_when_no_pattern_matches(self):
        entries, _ = build_tag_cards(
            [card(desc="這個卡名在規則上也當作「偉魔」卡片。\n①：效果甲。")],
            [faq(card_text="このカード名はルール上「魔導」カードとしても扱う。"
                           "①：効果甲。")])
        preamble = clauses_of(entries, 1000)[0]
        self.assertEqual(preamble["kind"], "效果外文本")
        self.assertIsNone(preamble["role"])

    def test_material_role_wins_over_usage_limit(self):
        entries, _ = build_tag_cards(
            [card(desc="等級4怪獸×3\n這個卡名的①效果1回合只能使用1次。\n①：效果甲。",
                  ctype=0x800021)],
            [faq(card_text="レベル４モンスター×３\n"
                           "このカード名の①の効果は１ターンに１度しか使用できない。"
                           "①：効果甲。")])
        self.assertEqual(clauses_of(entries, 1000)[0]["role"], "素材指定")

    def test_preamble_only_on_one_side_is_reported(self):
        entries, report = build_tag_cards(
            [card(desc="爬蟲類族儀式怪獸的降臨所必需。\n①：效果甲。", ctype=TYPE_SPELL)],
            [faq(card_text="①：効果甲。")])
        preamble = clauses_of(entries, 1000)[0]
        self.assertEqual(preamble["text_zh"], "爬蟲類族儀式怪獸的降臨所必需。")
        self.assertEqual(preamble["text_ja"], "")
        self.assertEqual(report["preamble_one_sided"],
                         [{"id": 1000, "section": "main", "present": "zh"}])


class TestUnnumbered(unittest.TestCase):
    """無編號舊式卡文:先當單一效果句,列入待拆清單。"""

    def test_old_style_text_becomes_single_pending_clause(self):
        entries, report = build_tag_cards(
            [card(desc="1回合1次,可以將手牌1張卡捨棄。此時抽1張卡。")],
            [faq(card_text="１ターンに１度、手札を１枚捨てる事ができる。"
                           "その後カードを１枚ドローする。")])
        clauses = clauses_of(entries, 1000)
        self.assertEqual(len(clauses), 1)
        self.assertEqual(clauses[0]["index"], "1")
        self.assertIsNone(clauses[0]["kind"])
        self.assertIsNone(clauses[0]["source"])
        self.assertEqual([(row["id"], row["section"])
                          for row in report["pending_split"]], [(1000, "main")])


class TestPendulum(unittest.TestCase):
    """靈擺卡雙 section。"""

    def test_two_sections_numbered_independently(self):
        entries, _ = build_tag_cards(
            [card(desc="【靈擺效果】\n①：靈擺甲。\n【怪獸效果】\n①：怪獸甲。\n②：怪獸乙。",
                  ctype=TYPE_PENDULUM_EFFECT)],
            [faq(card_text="①：モンスター甲。②：モンスター乙。",
                 pen_effect="①：ペンデュラム甲。")])
        clauses = clauses_of(entries, 1000)
        self.assertEqual([(c["section"], c["index"]) for c in clauses],
                         [("pendulum", "①"), ("main", "①"), ("main", "②")])
        self.assertEqual(clauses[0]["text_zh"], "①：靈擺甲。")
        self.assertEqual(clauses[0]["text_ja"], "①：ペンデュラム甲。")
        self.assertEqual(clauses[1]["text_ja"], "①：モンスター甲。")

    def test_pendulum_normal_monster_drops_flavor_section(self):
        """靈擺通常怪獸同時帶 Normal 與 Pendulum 位元;敘述段整段丟棄。"""
        entries, report = build_tag_cards(
            [card(desc="【靈擺效果】\n①：靈擺甲。\n【怪獸敘述】\n操縱著銀鳥的美麗狙擊手。",
                  ctype=TYPE_PENDULUM_NORMAL)],
            [faq(card_text="白銀のジェットを操る美しき狙撃手。",
                 pen_effect="①：ペンデュラム甲。")])
        clauses = clauses_of(entries, 1000)
        self.assertEqual([(c["section"], c["index"]) for c in clauses],
                         [("pendulum", "①")])
        self.assertEqual(report["flavor_dropped"], 1)

    def test_flavor_header_spelling_variant_also_dropped(self):
        """來源資料有一張寫成【怪獸描述】。"""
        entries, report = build_tag_cards(
            [card(desc="【靈擺效果】\n①：靈擺甲。\n【怪獸描述】\n敘述文。",
                  ctype=TYPE_PENDULUM_NORMAL)],
            [faq(card_text="フレイバーテキスト。", pen_effect="①：ペンデュラム甲。")])
        self.assertEqual([c["section"] for c in clauses_of(entries, 1000)],
                         ["pendulum"])
        self.assertEqual(report["flavor_dropped"], 1)

    def test_sections_come_from_headers_not_type_bits(self):
        """有靈擺位元但卡文無標頭者不得憑位元硬拆。"""
        entries, report = build_tag_cards(
            [card(desc="①：效果甲。", ctype=TYPE_PENDULUM_EFFECT)],
            [faq(card_text="①：効果甲。")])
        self.assertEqual([c["section"] for c in clauses_of(entries, 1000)],
                         ["main"])
        self.assertEqual(report["pendulum_bit_without_header"], [1000])

    def test_empty_pendulum_section_yields_no_clause(self):
        entries, _ = build_tag_cards(
            [card(desc="【靈擺效果】\n【怪獸效果】\n①：怪獸甲。",
                  ctype=TYPE_PENDULUM_EFFECT)],
            [faq(card_text="①：モンスター甲。")])
        self.assertEqual([(c["section"], c["index"])
                          for c in clauses_of(entries, 1000)], [("main", "①")])


class TestNormalMonster(unittest.TestCase):

    def test_pure_normal_monster_has_empty_clause_list(self):
        entries, report = build_tag_cards(
            [card(desc="以高攻擊力著稱的傳說之龍。", ctype=TYPE_NORMAL_MONSTER)],
            [faq(card_text="高い攻撃力を誇る伝説のドラゴン。")])
        entry = entries[0]
        self.assertEqual(entry["clauses"], [])
        self.assertEqual(report["pure_normal"], 1)


class TestSubstringInvariant(unittest.TestCase):

    def test_every_clause_text_is_a_contiguous_substring(self):
        cards = [
            card(1000, desc="這個卡名的①②效果1回合各能使用1次。\n①：效果甲。\n②：效果乙。"),
            card(2000, desc="【靈擺效果】\n①：靈擺甲。\n【怪獸效果】\n①：怪獸甲。",
                 ctype=TYPE_PENDULUM_EFFECT),
        ]
        faqs = [
            faq(1000, card_text="このカード名の①②の効果はそれぞれ１ターンに１度しか"
                                "使用できない。①：効果甲。②：効果乙。"),
            faq(2000, card_text="①：モンスター甲。", pen_effect="①：ペンデュラム甲。"),
        ]
        entries, report = build_tag_cards(cards, faqs)
        by_id = {c["id"]: c for c in cards}
        ja_by_id = {f["password"]: f for f in faqs}
        for entry in entries:
            desc = by_id[entry["id"]]["desc"]
            ja = ja_by_id[entry["id"]]
            for clause in entry["clauses"]:
                self.assertIn(clause["text_zh"], desc)
                haystack = (ja.get("pen_effect", "")
                            if clause["section"] == "pendulum"
                            else ja.get("card_text", ""))
                self.assertIn(clause["text_ja"], haystack)
        self.assertEqual(report["substring_violations"], [])


class TestNumeralAlignment(unittest.TestCase):

    def test_count_mismatch_leaves_japanese_empty_and_reports(self):
        entries, report = build_tag_cards(
            [card(desc="①：裝備怪獸的攻擊力上升300。")],
            [faq(card_text="The equipped monster gains 300 ATK.")])
        clauses = clauses_of(entries, 1000)
        self.assertEqual(clauses[0]["text_zh"], "①：裝備怪獸的攻擊力上升300。")
        self.assertEqual(clauses[0]["text_ja"], "")
        self.assertEqual(report["numeral_mismatch"],
                         [{"id": 1000, "section": "main", "zh": "①", "ja": ""}])

    def test_duplicate_zh_numeral_uses_japanese_labels(self):
        """繁中誤植重複編號時取日文編號,確保 (密碼, section, index) 唯一。"""
        entries, report = build_tag_cards(
            [card(desc="①：效果甲。\n②：效果乙。\n②：效果丙。")],
            [faq(card_text="①：効果甲。②：効果乙。③：効果丙。")])
        clauses = clauses_of(entries, 1000)
        self.assertEqual([c["index"] for c in clauses], ["①", "②", "③"])
        self.assertEqual(report["numeral_relabelled"],
                         [{"id": 1000, "section": "main",
                           "zh": "①②②", "ja": "①②③"}])

    def test_missing_japanese_text_leaves_japanese_empty(self):
        entries, report = build_tag_cards(
            [card(desc="①：效果甲。")], [])
        clauses = clauses_of(entries, 1000)
        self.assertEqual(clauses[0]["text_ja"], "")
        self.assertIsNone(clauses[0]["text_hash"])
        self.assertEqual(clauses[0]["confidence"], "low")
        self.assertEqual(report["no_japanese_text"], [1000])


class TestHashAndConfidence(unittest.TestCase):

    def test_hash_follows_japanese_text(self):
        """同一句日文原文的雜湊相同,不同原文則不同——身分變動偵測的基礎。"""
        entries, _ = build_tag_cards(
            [card(1000, desc="①：效果甲。"),
             card(2000, desc="①：翻譯不同但日文相同。"),
             card(3000, desc="①：別的效果。")],
            [faq(1000, card_text="①：同じ本文。"),
             faq(2000, card_text="①：同じ本文。"),
             faq(3000, card_text="①：違う本文。")])
        first = clauses_of(entries, 1000)[0]
        self.assertEqual(first["text_hash"],
                         clauses_of(entries, 2000)[0]["text_hash"])
        self.assertNotEqual(first["text_hash"],
                            clauses_of(entries, 3000)[0]["text_hash"])

    def test_confidence_high_only_with_supplement_for_that_section(self):
        entries, report = build_tag_cards(
            [card(desc="【靈擺效果】\n①：靈擺甲。\n【怪獸效果】\n①：怪獸甲。",
                  ctype=TYPE_PENDULUM_EFFECT)],
            [faq(card_text="①：モンスター甲。", supplement="■裁定。",
                 pen_effect="①：ペンデュラム甲。")])
        clauses = clauses_of(entries, 1000)
        self.assertEqual([c["confidence"] for c in clauses], ["low", "high"])
        self.assertEqual(report["low_confidence"], [1000])


class TestAggregation(unittest.TestCase):

    def test_entries_sorted_by_password_and_cover_every_card(self):
        cards = [card(3000, desc="①：效果丙。"),
                 card(1000, desc="①：效果甲。"),
                 card(2000, desc="以高攻擊力著稱的龍。", ctype=TYPE_NORMAL_MONSTER)]
        entries, report = build_tag_cards(cards, [faq(1000, "①：効果甲。")])
        self.assertEqual([e["id"] for e in entries], [1000, 2000, 3000])
        self.assertEqual(report["cards"], 3)

    def test_every_optional_input_is_accepted(self):
        """既有標記表、判定結果、拆句表三個參數都已實作(票05 / 票08)。"""
        _, report = build_tag_cards([card(desc="①：效果甲。")], [],
                                    existing=[], judgments=[], splits=[])
        self.assertEqual(report["cards"], 1)


class TestOfficialHeaderAttestation(unittest.TestCase):
    """階梯一:【①の効果について】系列標頭直接對位編號。"""

    def test_header_maps_each_kind_to_its_numbered_clause(self):
        entries, report = build_tag_cards(
            [card(desc="①：效果甲。\n②：效果乙。")],
            [faq(card_text="①：効果甲。②：効果乙。",
                 supplement="【①の効果について】\n"
                            "■モンスターゾーンで発動できる起動効果です。\n\n"
                            "【②の効果について】\n"
                            "■モンスターゾーンで適用する永続効果です。")])
        clauses = clauses_of(entries, 1000)
        self.assertEqual([c["kind"] for c in clauses], ["啟動效果", "永續效果"])
        self.assertEqual([c["source"] for c in clauses],
                         ["official", "official"])
        self.assertEqual(report["official_coverage"]["header"], 2)

    def test_monster_effect_header_variant_is_recognised(self):
        entries, _ = build_tag_cards(
            [card(desc="①：效果甲。\n②：效果乙。")],
            [faq(card_text="①：効果甲。②：効果乙。",
                 supplement="【②のモンスター効果について】\n"
                            "■墓地で発動する誘発効果です。")])
        clauses = clauses_of(entries, 1000)
        self.assertEqual([c["kind"] for c in clauses], [None, "誘發效果(1速)"])

    def test_pendulum_header_targets_the_pendulum_section_only(self):
        entries, _ = build_tag_cards(
            [card(desc="【靈擺效果】\n①：靈擺甲。\n【怪獸效果】\n①：怪獸甲。",
                  ctype=TYPE_PENDULUM_EFFECT)],
            [faq(card_text="①：モンスター甲。", supplement="■永続効果です。",
                 pen_effect="①：ペンデュラム甲。",
                 pen_supplement="【①のペンデュラム効果について】\n"
                                "■ペンデュラムゾーンで発動できる起動効果です。")])
        clauses = clauses_of(entries, 1000)
        self.assertEqual([(c["section"], c["kind"]) for c in clauses],
                         [("pendulum", "啟動效果"), ("main", "永續效果")])

    def test_header_naming_an_absent_index_assigns_nothing(self):
        entries, report = build_tag_cards(
            [card(desc="①：效果甲。\n②：效果乙。")],
            [faq(card_text="①：効果甲。②：効果乙。",
                 supplement="【③の効果について】\n■永続効果です。")])
        self.assertEqual([c["kind"] for c in clauses_of(entries, 1000)],
                         [None, None])
        self.assertEqual(report["header_index_missing"],
                         [{"id": 1000, "section": "main", "index": "③"}])


class TestSequenceReference(unittest.TestCase):
    """階梯二:『①』純序號引用。短引號不得被字元長度過濾掉。"""

    def test_short_numeral_quote_is_not_filtered_out(self):
        entries, report = build_tag_cards(
            [card(desc="①：效果甲。\n②：效果乙。")],
            [faq(card_text="①：効果甲。②：効果乙。",
                 supplement="■『①』のモンスター効果は、"
                            "フィールドで発動する誘発効果です。")])
        clauses = clauses_of(entries, 1000)
        self.assertEqual([c["kind"] for c in clauses], ["誘發效果(1速)", None])
        self.assertEqual(clauses[0]["source"], "official")
        self.assertEqual(report["official_coverage"]["seq"], 1)

    def test_sequence_reference_to_a_missing_index_is_reported(self):
        entries, report = build_tag_cards(
            [card(desc="①：效果甲。\n②：效果乙。")],
            [faq(card_text="①：効果甲。②：効果乙。",
                 supplement="■『③』の効果は永続効果です。")])
        self.assertEqual([c["kind"] for c in clauses_of(entries, 1000)],
                         [None, None])
        self.assertEqual(report["seq_missing"],
                         [{"id": 1000, "section": "main", "index": "③"}])

    def test_sequence_reference_on_old_style_text_hits_the_sole_effect(self):
        """舊式無編號卡文沒有①,但官方仍以『①』稱呼那唯一的效果。"""
        entries, report = build_tag_cards(
            [card(desc="反轉:從牌組選1張場地魔法卡放到牌組最上方。")],
            [faq(card_text="リバース：デッキからフィールド魔法カードを"
                           "１枚選択し、デッキの一番上に置く。",
                 supplement="■『①』のモンスター効果は、"
                            "フィールドで発動する誘発効果です。")])
        self.assertEqual(clauses_of(entries, 1000)[0]["kind"], "誘發效果(1速)")
        self.assertEqual(report["seq_missing"], [])

    def test_only_the_first_reference_in_a_line_decides_attribution(self):
        """後面的『①』是解說時提到的另一個效果,不得被複製上主語的判定。"""
        entries, _ = build_tag_cards(
            [card(desc="①：效果甲。\n②：效果乙。")],
            [faq(card_text="①：効果甲。②：効果乙。",
                 supplement="■『②』はフィールドで発動する誘発効果です。"
                            "（自身の『①』の効果を発動した場合に、"
                            "必ず発動する効果です。）")])
        clauses = clauses_of(entries, 1000)
        self.assertEqual([c["kind"] for c in clauses], [None, "誘發效果(1速)"])
        self.assertEqual([c["optional"] for c in clauses], [None, "必發"])


class TestQuoteReference(unittest.TestCase):
    """階梯三:『效果原文』引用比對回日文卡文的編號區段。"""

    def test_quote_locates_the_matching_numbered_clause(self):
        entries, report = build_tag_cards(
            [card(desc="①：效果甲。\n②：效果乙。")],
            [faq(card_text="①：効果甲。②：効果乙。",
                 supplement="■『②：効果乙。』のモンスター効果は永続効果です。")])
        clauses = clauses_of(entries, 1000)
        self.assertEqual([c["kind"] for c in clauses], [None, "永續效果"])
        self.assertEqual(report["official_coverage"]["quote"], 1)

    def test_fullwidth_and_halfwidth_digits_are_normalised(self):
        entries, _ = build_tag_cards(
            [card(desc="①：效果甲。\n②：支付1000基本分發動。")],
            [faq(card_text="①：効果甲。②：１０００ライフを払って発動する。",
                 supplement="■『②：1000ライフを払って発動する。』は"
                            "起動効果です。")])
        self.assertEqual([c["kind"] for c in clauses_of(entries, 1000)],
                         [None, "啟動效果"])

    def test_truncated_quote_matches_by_prefix(self):
        entries, _ = build_tag_cards(
            [card(desc="①：效果甲。\n②：效果乙,然後抽1張卡。")],
            [faq(card_text="①：効果甲。②：効果乙、その後カードを１枚ドローする。",
                 supplement="■『②：効果乙』の効果は誘発即時効果です。")])
        self.assertEqual([c["kind"] for c in clauses_of(entries, 1000)],
                         [None, "誘發即時效果(2速)"])

    def test_quote_matching_no_clause_makes_no_guess(self):
        entries, report = build_tag_cards(
            [card(desc="①：效果甲。\n②：效果乙。")],
            [faq(card_text="①：効果甲。②：効果乙。",
                 supplement="■『このカードは魔法の効果を受けない』効果は"
                            "永続効果です。")])
        self.assertEqual([c["kind"] for c in clauses_of(entries, 1000)],
                         [None, None])
        self.assertEqual([row["id"] for row in report["quote_unmatched"]],
                         [1000])

    def test_quote_matching_several_clauses_is_treated_as_ambiguous(self):
        entries, report = build_tag_cards(
            [card(desc="①：效果甲。\n②：效果甲。")],
            [faq(card_text="①：効果甲。②：効果甲。",
                 supplement="■『効果甲。』の効果は永続効果です。")])
        self.assertEqual([c["kind"] for c in clauses_of(entries, 1000)],
                         [None, None])
        self.assertEqual([row["id"] for row in report["quote_ambiguous"]],
                         [1000])

    def test_only_the_first_quote_in_a_line_decides_attribution(self):
        entries, _ = build_tag_cards(
            [card(desc="①：效果甲。\n②：效果乙。")],
            [faq(card_text="①：効果甲。②：効果乙。",
                 supplement="■『②：効果乙。』のモンスター効果は誘発効果です。"
                            "『①：効果甲。』の効果を発動した場合に"
                            "必ず発動する効果です。")])
        clauses = clauses_of(entries, 1000)
        self.assertEqual([c["kind"] for c in clauses], [None, "誘發效果(1速)"])
        self.assertEqual([c["optional"] for c in clauses], [None, "必發"])


class TestCardNameLimited(unittest.TestCase):
    """階梯四與「只提別卡名」的排除。"""

    def test_own_name_with_a_single_clause_applies(self):
        entries, report = build_tag_cards(
            [card(desc="①：只要「海」在場上存在,此卡不受魔法效果影響。",
                  name_ja="深海の戦士")],
            [faq(card_text="①：「海」がフィールド上に存在する限り、"
                           "このカードは魔法の効果を受けない。",
                 name_ja="深海の戦士",
                 supplement="■「深海の戦士」の効果は永続効果です。")])
        clause = clauses_of(entries, 1000)[0]
        self.assertEqual(clause["kind"], "永續效果")
        self.assertEqual(clause["source"], "official")
        self.assertEqual(report["official_coverage"]["name_single"], 1)

    def test_own_name_with_several_clauses_defers_attribution(self):
        entries, report = build_tag_cards(
            [card(desc="①：效果甲。\n②：效果乙。", name_ja="深海の戦士")],
            [faq(card_text="①：効果甲。②：効果乙。", name_ja="深海の戦士",
                 supplement="■「深海の戦士」の効果は永続効果です。")])
        self.assertEqual([c["kind"] for c in clauses_of(entries, 1000)],
                         [None, None])
        self.assertEqual([(r["id"], r["kind"])
                          for r in report["attribution_deferred"]],
                         [(1000, "永續效果")])

    def test_line_naming_only_another_card_makes_no_judgment(self):
        """深海の戦士型陷阱:補足為了解說而提到別張卡,不得產生任何判定。"""
        entries, report = build_tag_cards(
            [card(desc="只要「海」在場上存在,此卡不受魔法效果影響。",
                  name_ja="深海の戦士")],
            [faq(card_text="「海」がフィールド上に存在する限り、"
                           "このカードは魔法の効果を受けない。",
                 name_ja="深海の戦士",
                 supplement="■「海神の巫女」の効果は永続効果です。")])
        self.assertIsNone(clauses_of(entries, 1000)[0]["kind"])
        self.assertEqual([r["id"] for r in report["other_card_only"]], [1000])
        self.assertEqual(report["official_coverage"]["name_single"], 0)

    def test_own_name_line_still_applies_when_another_line_names_others(self):
        entries, report = build_tag_cards(
            [card(desc="①：只要「海」在場上存在,此卡不受魔法效果影響。",
                  name_ja="深海の戦士")],
            [faq(card_text="①：「海」がフィールド上に存在する限り、"
                           "このカードは魔法の効果を受けない。",
                 name_ja="深海の戦士",
                 supplement="■「深海の戦士」の効果は永続効果です。\n"
                            "■「海神の巫女」の効果は永続効果です。")])
        self.assertEqual(clauses_of(entries, 1000)[0]["kind"], "永續效果")
        self.assertEqual([r["id"] for r in report["other_card_only"]], [1000])


class TestGenericSingleClause(unittest.TestCase):
    """階梯五:無任何歸屬標記且該卡只有一個效果句。"""

    def test_unmarked_attestation_applies_to_the_only_clause(self):
        entries, report = build_tag_cards(
            [card(desc="①：效果甲。")],
            [faq(card_text="①：効果甲。",
                 supplement="■モンスターゾーンで発動できる起動効果です。")])
        clause = clauses_of(entries, 1000)[0]
        self.assertEqual(clause["kind"], "啟動效果")
        self.assertEqual(report["official_coverage"]["single"], 1)

    def test_preamble_does_not_count_as_a_second_clause(self):
        entries, _ = build_tag_cards(
            [card(desc="這個卡名的①效果1回合只能使用1次。\n①：效果甲。")],
            [faq(card_text="このカード名の①の効果は１ターンに１度しか使用できない。"
                           "①：効果甲。",
                 supplement="■モンスターゾーンで発動できる起動効果です。")])
        clauses = clauses_of(entries, 1000)
        self.assertEqual([c["kind"] for c in clauses],
                         ["效果外文本", "啟動效果"])

    def test_unmarked_attestation_on_a_multi_clause_card_defers(self):
        entries, report = build_tag_cards(
            [card(desc="①：效果甲。\n②：效果乙。")],
            [faq(card_text="①：効果甲。②：効果乙。",
                 supplement="■モンスターゾーンで適用する永続効果です。")])
        self.assertEqual([c["kind"] for c in clauses_of(entries, 1000)],
                         [None, None])
        self.assertEqual([(r["id"], r["kind"])
                          for r in report["attribution_deferred"]],
                         [(1000, "永續效果")])


class TestUnsplitOldStyleAttribution(unittest.TestCase):
    """階梯四、五問的是「這張卡只有一個效果句嗎」,未拆的舊式整團答不出來。

    舊式無編號卡文在依語意拆開之前整團只算一個效果句,兩道階梯會在一個假的前提
    上開火——整團拿到一個官方類型,而那個類型其實只描述整團裡的其中一段。
    """

    # 機海竜プレシオン(40160226)的實例:第一段是無種類效果、第二段是啟動效果,
    # 官方明示講的是第一段
    DESC = ("我方場上有海龍族怪獸存在的場合,此卡可以不用解放來召喚。"
            "1回合1次,藉由解放我方場上的1隻水屬性怪獸,"
            "選擇對手場上表側表示存在的1張卡破壞。")
    CARD_TEXT = ("自分フィールド上に海竜族モンスターが存在する場合、"
                 "このカードはリリースなしで召喚できる。"
                 "１ターンに１度、自分フィールド上の水属性モンスター１体を"
                 "リリースする事で、相手フィールド上に表側表示で存在する"
                 "カード１枚を選択して破壊する。")

    def _build(self, supplement, name_ja="機海竜プレシオン"):
        return build_tag_cards(
            [card(desc=self.DESC, name_ja=name_ja)],
            [faq(card_text=self.CARD_TEXT, name_ja=name_ja,
                 supplement=supplement)])

    def test_unmarked_line_on_an_unsplit_blob_defers(self):
        entries, report = self._build(
            "■手札から自身を召喚する効果の種別は、永続効果、起動効果、誘発効果、"
            "誘発即時効果のどれにも分類されない効果となります。")
        clause = clauses_of(entries, 1000)[0]
        self.assertEqual(clause["index"], "1")
        self.assertIsNone(clause["kind"])
        self.assertIsNone(clause["source"])
        self.assertEqual(report["official_coverage"]["single"], 0)
        self.assertEqual([(r["id"], r["kind"], r["reason"])
                          for r in report["attribution_deferred"]],
                         [(1000, "無種類效果", "無編號卡文待拆")])

    def test_name_limited_line_on_an_unsplit_blob_defers(self):
        entries, report = self._build(
            "■「機海竜プレシオン」の効果は起動効果です。")
        self.assertIsNone(clauses_of(entries, 1000)[0]["kind"])
        self.assertEqual(report["official_coverage"]["name_single"], 0)
        self.assertEqual([(r["id"], r["kind"], r["reason"])
                          for r in report["attribution_deferred"]],
                         [(1000, "啟動效果", "無編號卡文待拆")])

    def test_mandatory_line_on_an_unsplit_blob_defers_too(self):
        """必發明示與類型明示共用同一套歸屬對位,排除條件也必須一起生效。"""
        entries, report = self._build(
            "■フィールドで発動する誘発効果です。必ず発動します。")
        clause = clauses_of(entries, 1000)[0]
        self.assertIsNone(clause["kind"])
        self.assertIsNone(clause["optional"])
        self.assertEqual([r["id"] for r in report["attribution_deferred"]],
                         [1000])

    def test_a_numbered_single_clause_card_still_applies(self):
        """排除的是「未拆的整團」而不是「單效果卡」,階梯五本身照常運作。"""
        entries, report = build_tag_cards(
            [card(desc="①：效果甲。")],
            [faq(card_text="①：効果甲。",
                 supplement="■モンスターゾーンで適用する永続効果です。")])
        self.assertEqual(clauses_of(entries, 1000)[0]["kind"], "永續效果")
        self.assertEqual(report["official_coverage"]["single"], 1)
        self.assertEqual(report["attribution_deferred"], [])

    def test_sequence_reference_still_reaches_the_unsplit_blob(self):
        """官方以『①』稱呼整團時,歸屬證據是官方自己給的,階梯二不受影響。"""
        entries, report = self._build(
            "■『①』の効果はフィールドで発動する誘発効果です。")
        self.assertEqual(clauses_of(entries, 1000)[0]["kind"], "誘發效果(1速)")
        self.assertEqual(report["official_coverage"]["seq"], 1)

    def test_a_quote_pointing_at_the_unsplit_blob_defers_not_unmatched(self):
        """引用指的是整團裡的一段:那是「待拆」而不是「引號對不回本卡卡文」。

        `●` 拆出去之後整團的頭仍然是未拆的,對得出歸屬的效果句於是不再是空的
        ——但引用照樣落在那個頭上,它只是還沒被切開,不是官方引用了別張卡。
        """
        entries, report = build_tag_cards(
            [card(desc=self.DESC + "\n●選項甲。")],
            [faq(card_text=self.CARD_TEXT + "●選択肢甲。",
                 supplement="■『１ターンに１度、自分フィールド上の水属性"
                            "モンスター１体をリリースする事で』"
                            "は起動効果です。\n"
                            "【●の効果について】\n■永続効果です。")])
        self.assertEqual(report["quote_unmatched"], [])
        self.assertEqual([(r["kind"], r["reason"])
                          for r in report["attribution_deferred"]],
                         [("啟動效果", "無編號卡文待拆")])


class TestNegationAndForbiddenPhrases(unittest.TestCase):

    def test_izure_ni_mo_bunrui_sarenai_is_a_single_unclassified_kind(self):
        """否定句優先:列舉了四個類型詞也只判無種類效果。"""
        entries, _ = build_tag_cards(
            [card(desc="①：可以代替1隻融合素材怪獸。")],
            [faq(card_text="①：このカードを融合素材モンスター１体の代わりにする"
                           "事ができる。",
                 supplement="■起動効果・誘発効果・誘発即時効果・永続効果の"
                            "いずれにも分類されない効果です。")])
        clause = clauses_of(entries, 1000)[0]
        self.assertEqual(clause["kind"], "無種類效果")
        self.assertEqual(clause["source"], "official")

    def test_dore_ni_mo_variant_is_also_unclassified(self):
        """官方寫過「いずれにも」與「どれにも」兩種,都是無種類效果。"""
        entries, _ = build_tag_cards(
            [card(desc="①：可以代替1隻融合素材怪獸。")],
            [faq(card_text="①：このカードを融合素材モンスター１体の代わりにする"
                           "事ができる。",
                 supplement="■効果の種別は、永続効果、起動効果、誘発効果、"
                            "誘発即時効果のどれにも分類されない効果となります。")])
        self.assertEqual(clauses_of(entries, 1000)[0]["kind"], "無種類效果")

    def test_one_sentence_naming_two_kinds_produces_no_judgment(self):
        """官方在一句裡分別交代兩個子效果時,無從得知「です」收尾的是哪一個。"""
        entries, _ = build_tag_cards(
            [card(desc="①：效果甲。")],
            [faq(card_text="①：効果甲。",
                 supplement="■『甲』の効果が永続効果、『乙』の効果が誘発効果です。")])
        self.assertIsNone(clauses_of(entries, 1000)[0]["kind"])

    def test_a_later_sentence_mentioning_another_kind_is_harmless(self):
        entries, _ = build_tag_cards(
            [card(desc="①：效果甲。")],
            [faq(card_text="①：効果甲。",
                 supplement="■フィールドで発動する誘発効果です。"
                            "（自身の起動効果を発動した場合に発動します。）")])
        self.assertEqual(clauses_of(entries, 1000)[0]["kind"], "誘發效果(1速)")

    def test_kouka_dewa_arimasen_never_produces_a_judgment(self):
        """禁令回歸測試:「効果ではありません」不得產生任何判定。"""
        for line in ("■対象を取る効果ではありません。",
                     "■チェーンブロックの作られる効果ではありません。",
                     "■起動効果ではありません。"):
            with self.subTest(line=line):
                entries, _ = build_tag_cards(
                    [card(desc="①：效果甲。")],
                    [faq(card_text="①：効果甲。", supplement=line)])
                self.assertIsNone(clauses_of(entries, 1000)[0]["kind"])

    def test_conflicting_kinds_for_one_clause_are_not_applied(self):
        entries, report = build_tag_cards(
            [card(desc="①：效果甲。")],
            [faq(card_text="①：効果甲。",
                 supplement="【①の効果について】\n"
                            "■モンスターゾーンで発動できる起動効果です。\n"
                            "■モンスターゾーンで適用する永続効果です。")])
        self.assertIsNone(clauses_of(entries, 1000)[0]["kind"])
        self.assertEqual([r["id"] for r in report["kind_conflicts"]], [1000])


class TestNonEffectAttestation(unittest.TestCase):
    """「〜は効果として扱いません」是效果外文本的官方明示。"""

    def test_quote_header_on_the_preamble_upgrades_it_to_official(self):
        entries, report = build_tag_cards(
            [card(desc="此卡不能通常召喚。\n①：效果甲。")],
            [faq(card_text="このカードは通常召喚できない。①：効果甲。",
                 supplement="【『このカードは通常召喚できない』について】\n"
                            "■効果として扱いません。")])
        preamble = clauses_of(entries, 1000)[0]
        self.assertEqual(preamble["kind"], "效果外文本")
        self.assertEqual(preamble["source"], "official")
        self.assertEqual(report["official_coverage"]["non_effect"], 1)

    def test_attestation_covering_only_part_of_a_clause_is_reported_only(self):
        entries, report = build_tag_cards(
            [card(desc="此卡不能通常召喚。\n①：效果甲。效果乙。")],
            [faq(card_text="このカードは通常召喚できない。①：効果甲。効果乙。",
                 supplement="■『①：効果甲。』は効果として扱いません。")])
        clauses = clauses_of(entries, 1000)
        self.assertEqual(clauses[0]["source"], "rule")
        self.assertIsNone(clauses[1]["kind"])
        self.assertEqual(
            [r["id"] for r in report["non_effect_outside_preamble"]], [1000])

    # 官方寫過的八種變體(2026-08-09 實測:「効果として扱いません」1,214 行、
    # 「効果の扱いではありません」476 行、其餘六種各 0~9 行)
    VARIANTS = ("効果として扱いません", "効果の扱いではありません",
                "効果として扱われません", "効果としては扱いません",
                "効果としては扱われません", "効果としての扱いではありません",
                "効果としての扱いません", "効果の扱いにはなりません")

    def test_every_official_variant_is_the_same_attestation(self):
        for mark_text in self.VARIANTS:
            with self.subTest(mark=mark_text):
                entries, report = build_tag_cards(
                    [card(desc="此卡不能通常召喚。\n①：效果甲。")],
                    [faq(card_text="このカードは通常召喚できない。①：効果甲。",
                         supplement="【『このカードは通常召喚できない』について】"
                                    f"\n■{mark_text}。")])
                preamble = clauses_of(entries, 1000)[0]
                self.assertEqual(preamble["kind"], "效果外文本")
                self.assertEqual(preamble["source"], "official")
                self.assertEqual(report["official_coverage"]["non_effect"], 1)

    def test_variant_covering_only_part_of_a_clause_is_reported_only(self):
        """變體與既有寫法走完全相同的歸屬路徑,不因為是新寫法就放寬。"""
        entries, report = build_tag_cards(
            [card(desc="此卡不能通常召喚。\n①：效果甲。效果乙。")],
            [faq(card_text="このカードは通常召喚できない。①：効果甲。効果乙。",
                 supplement="■『①：効果甲。』そのものは効果の扱いでは"
                            "ありません。")])
        clauses = clauses_of(entries, 1000)
        self.assertEqual(clauses[0]["source"], "rule")
        self.assertIsNone(clauses[1]["kind"])
        self.assertEqual(
            [r["id"] for r in report["non_effect_outside_preamble"]], [1000])

    def test_the_variant_does_not_punch_through_the_forbidden_phrase(self):
        """「効果の扱いではありません」與「効果ではありません」只差三個字。"""
        entries, report = build_tag_cards(
            [card(desc="此卡不能通常召喚。\n①：效果甲。")],
            [faq(card_text="このカードは通常召喚できない。①：効果甲。",
                 supplement="【『このカードは通常召喚できない』について】\n"
                            "■対象を取る効果ではありません。")])
        preamble = clauses_of(entries, 1000)[0]
        self.assertEqual(preamble["source"], "rule")
        self.assertEqual(report["official_coverage"]["non_effect"], 0)
        self.assertEqual(report["non_effect_outside_preamble"], [])

    def test_negation_inside_a_parenthetical_is_only_a_scoping_aside(self):
        """括弧裡的否定是「不算哪一種效果」的補述,不是「這一段不是效果」。

        實測 7 行的明示句只在括弧內出現,無一例外都是限定否定
        (「ダメージを与える効果としては扱われません」「罠カードの効果としては
        扱われません」),而其中兩行的括弧外正是一句貨真價實的類型明示——
        整行改判會把那個類型吃掉。
        """
        entries, report = build_tag_cards(
            [card(desc="①：效果甲。")],
            [faq(card_text="①：効果甲。",
                 supplement="■モンスターゾーンで適用する永続効果です。"
                            "（モンスター効果として扱われます。"
                            "罠カードの効果としては扱われません。）")])
        self.assertEqual(clauses_of(entries, 1000)[0]["kind"], "永續效果")
        self.assertEqual(report["non_effect_outside_preamble"], [])

    # 「効果」與「扱い」之間夾了別的詞:講的是別件事(被效果破壞、效果傷害),
    # 不是「這一段不是效果」
    LOOKALIKES = ("このカードが効果で破壊された扱いにはなりません",
                  "この効果で墓地へ送られた扱いにはなりません",
                  "効果ダメージの扱いではありません",
                  "効果による破壊として扱いません",
                  "この効果でリリースされた扱いではありません")

    def test_lookalike_atsukai_phrases_are_not_attestations(self):
        for line in self.LOOKALIKES:
            with self.subTest(line=line):
                entries, report = build_tag_cards(
                    [card(desc="此卡不能通常召喚。\n①：效果甲。")],
                    [faq(card_text="このカードは通常召喚できない。①：効果甲。",
                         supplement="【『このカードは通常召喚できない』について】"
                                    f"\n■{line}。")])
                preamble = clauses_of(entries, 1000)[0]
                self.assertEqual(preamble["source"], "rule")
                self.assertEqual(report["official_coverage"]["non_effect"], 0)
                self.assertEqual(report["non_effect_outside_preamble"], [])


class TestBulletSubEffects(unittest.TestCase):
    """官方以【●の効果について】系列標頭描述的子效果拆成獨立效果句。"""

    SUPPLEMENT = ("【①の効果について】\n"
                  "■１ターンに１度、２つの●のうちいずれかを発動できます。\n\n"
                  "【１つ目の●について】\n"
                  "■モンスターゾーンで発動できる起動効果です。\n\n"
                  "【２つ目の●について】\n"
                  "■モンスターゾーンで適用する永続効果です。")
    DESC = "①：可以發動1個以下效果。\n●選項甲。\n●選項乙。"
    CARD_TEXT = "①：以下の効果を１つ発動できる。●選択肢甲。●選択肢乙。"

    def test_bullets_become_their_own_clauses_with_their_own_kinds(self):
        entries, report = build_tag_cards(
            [card(desc=self.DESC)],
            [faq(card_text=self.CARD_TEXT, supplement=self.SUPPLEMENT)])
        clauses = clauses_of(entries, 1000)
        self.assertEqual([c["index"] for c in clauses], ["①", "①-●1", "①-●2"])
        self.assertEqual([c["kind"] for c in clauses],
                         [None, "啟動效果", "永續效果"])
        self.assertEqual([c["text_zh"] for c in clauses],
                         ["①：可以發動1個以下效果。", "●選項甲。", "●選項乙。"])
        self.assertEqual([c["text_ja"] for c in clauses],
                         ["①：以下の効果を１つ発動できる。", "●選択肢甲。",
                          "●選択肢乙。"])
        self.assertEqual(report["bullet_clauses"], 2)

    def test_labelled_bullet_header_targets_the_matching_bullet(self):
        entries, _ = build_tag_cards(
            [card(desc="①：擲1次硬幣。\n●正面:效果甲。\n●反面:效果乙。")],
            [faq(card_text="①：コイントスを１回行う。●表：効果甲。●裏：効果乙。",
                 supplement="【『●裏』の効果について】\n"
                            "■モンスターゾーンで適用する永続効果です。")])
        clauses = clauses_of(entries, 1000)
        self.assertEqual([c["index"] for c in clauses],
                         ["①", "①-●1", "①-●2"])
        self.assertEqual([c["kind"] for c in clauses], [None, None, "永續效果"])

    def test_sole_bullet_header_targets_the_only_bullet(self):
        entries, _ = build_tag_cards(
            [card(desc="①：以對手怪獸為對象發動。此卡得到以下效果。\n"
                       "●只要此卡在怪獸區域存在,對象怪獸不能攻擊。")],
            [faq(card_text="①：相手モンスター１体を対象として発動する。"
                           "このカードは以下の効果を得る。"
                           "●このカードがモンスターゾーンに存在する限り、"
                           "対象のモンスターは攻撃できない。",
                 supplement="【●の効果について】\n"
                            "■モンスターゾーンで適用する永続効果です。")])
        clauses = clauses_of(entries, 1000)
        self.assertEqual([c["index"] for c in clauses], ["①", "①-●1"])
        self.assertEqual(clauses[1]["kind"], "永續效果")

    def test_bullets_are_not_split_without_official_bullet_headers(self):
        entries, report = build_tag_cards(
            [card(desc=self.DESC)],
            [faq(card_text=self.CARD_TEXT,
                 supplement="【①の効果について】\n■１ターンに１度発動できます。")])
        clauses = clauses_of(entries, 1000)
        self.assertEqual([c["index"] for c in clauses], ["①"])
        self.assertEqual(report["bullet_clauses"], 0)

    def test_bullet_counts_that_disagree_across_languages_are_not_split(self):
        entries, report = build_tag_cards(
            [card(desc="①：可以發動1個以下效果。\n●選項甲。")],
            [faq(card_text=self.CARD_TEXT, supplement=self.SUPPLEMENT)],)
        self.assertEqual([c["index"] for c in clauses_of(entries, 1000)],
                         ["①"])
        self.assertEqual([r["id"] for r in report["bullet_split_mismatch"]],
                         [1000])

    def test_split_bullets_remain_contiguous_substrings(self):
        cards = [card(desc=self.DESC)]
        faqs = [faq(card_text=self.CARD_TEXT, supplement=self.SUPPLEMENT)]
        entries, report = build_tag_cards(cards, faqs)
        for clause in clauses_of(entries, 1000):
            self.assertIn(clause["text_zh"], cards[0]["desc"])
            self.assertIn(clause["text_ja"], faqs[0]["card_text"])
        self.assertEqual(report["substring_violations"], [])


class TestTrailingHeader(unittest.TestCase):
    """票15:黏在行尾的【…】標頭一樣是新段的開始。

    官方偶爾把下一段的標頭接在前一行的尾巴。抽取器只認行首標頭時,那一行之後的
    明示會繼續算在**上一個**編號底下,類型因此掛錯效果句。
    """

    DESC = "①：效果甲。\n②：效果乙。\n③：效果丙。"
    CARD_TEXT = "①：効果甲。②：効果乙。③：効果丙。"

    def _build(self, supplement):
        return build_tag_cards(
            [card(desc=self.DESC)],
            [faq(card_text=self.CARD_TEXT, supplement=supplement)])

    def test_a_kind_after_a_trailing_header_belongs_to_the_new_index(self):
        """黎明の堕天使ルシフェル(4167084):③的標頭黏在②那一行的尾巴。

        前半句自己就是一句類型明示,它講的仍是②;行尾標頭只切開它自己。
        """
        entries, report = self._build(
            "【②の効果について】\n"
            "■モンスターゾーンで適用される永続効果です。【③の効果について】\n"
            "■モンスターゾーンで発動できる誘発即時効果です。")
        self.assertEqual([c["kind"] for c in clauses_of(entries, 1000)],
                         [None, "永續效果", "誘發即時效果(2速)"])
        self.assertEqual(report["official_coverage"]["header"], 2)

    def test_a_mandatory_after_a_trailing_header_belongs_to_the_new_index(self):
        """始祖の守護者ティラス(31386180):必發明示走同一套歸屬對位。"""
        entries, _ = self._build(
            "【②の効果について】\n"
            "■モンスターゾーンで発動する誘発効果です。\n"
            "■このカードが戦闘を行ったバトルフェイズ終了時に1度、"
            "必ず発動する効果です。【③の効果について】\n"
            "■モンスターゾーンで発動する誘発効果です。\n"
            "■自分のエンドフェイズ毎に1度、必ず発動する効果です。")
        clauses = clauses_of(entries, 1000)
        self.assertEqual([c["kind"] for c in clauses],
                         [None, "誘發效果(1速)", "誘發效果(1速)"])
        self.assertEqual([c["optional"] for c in clauses],
                         [None, "必發", "必發"])

    def test_a_header_in_the_middle_of_a_line_is_not_a_header(self):
        """オーディンの眼(88069166):【カードの発動】是強調而不是標頭。"""
        entries, report = self._build(
            "【②の効果について】\n"
            "■効果の発動を伴わない【カードの発動】だけであれば、"
            "モンスターゾーンで適用する永続効果です。")
        self.assertEqual([c["kind"] for c in clauses_of(entries, 1000)],
                         [None, "永續效果", None])
        self.assertEqual(report["official_coverage"]["header"], 1)

    def test_a_trailing_header_after_a_bullet_marker_is_still_a_header(self):
        """希望皇オノマトピア(8512558):行尾標頭前面只剩一個「■」也照切。"""
        entries, _ = self._build(
            "■効果として扱いません。【①の効果について】\n"
            "■モンスターゾーンで発動できる起動効果です。")
        self.assertEqual([c["kind"] for c in clauses_of(entries, 1000)],
                         ["啟動效果", None, None])

    def test_a_trailing_bullet_header_reaches_the_bullet_splitter(self):
        """CNo.104 仮面魔踏士アンブラル(49456901)②:2 速是 `●` 的,不是②的。

        行尾的【『●』の効果について】既是拆句依據也是歸屬標記,兩邊一起恢復。
        `●` 拆走之後領起句剩自己一段,官方那句「そのものは効果として扱いません」
        涵蓋的正是這一段,於是它也拿到了類型(票16)。
        """
        entries, report = build_tag_cards(
            [card(desc="①：效果甲。\n"
                       "②：此卡以「甲」為X素材時,得到以下效果。\n"
                       "●1回合1次,可以發動。")],
            [faq(card_text="①：効果甲。"
                           "②：このカードが「甲」をX素材としている場合、"
                           "以下の効果を得る。"
                           "●１ターンに１度、発動できる。",
                 supplement="【②の効果について】\n"
                            "■『このカードが「甲」をX素材としている場合、"
                            "以下の効果を得る』そのものは効果として扱いません。"
                            "【『●』の効果について】\n"
                            "■モンスターゾーンで発動できる誘発即時効果です。")])
        clauses = clauses_of(entries, 1000)
        self.assertEqual([c["index"] for c in clauses], ["①", "②", "②-●1"])
        self.assertEqual([c["kind"] for c in clauses],
                         [None, "效果外文本", "誘發即時效果(2速)"])
        self.assertEqual(report["attribution_deferred"], [])


class TestGrantLeadWithUnsplitBullets(unittest.TestCase):
    """領起句「〜は以下の効果を得る。●…」不發動,官方給的類型多半是 ● 的。

    領起句只是把一組效果賦予別的東西,自己不形成連鎖;`●` 才是被賦予的效果。
    `●` 還沒拆開之前兩者併在同一個效果句裡,官方明示講的是哪一邊要看證據——
    引用從領起句開始才算講的是這一段,其餘一律留待判定。
    """

    # 晴れの天気模様(89355716)②的實例:官方給的 2 速是 `●` 的,領起句自己
    # 在同一份補足裡被寫成「チェーンブロックの作られない効果」
    DESC = ("②：與此卡同縱列的我方主要怪獸區域的「天氣」效果怪獸得到以下效果。\n"
            "●將此卡除外,以我方場上1隻怪獸為對象發動。")
    CARD_TEXT = ("②：このカードと同じ縦列の自分のメインモンスターゾーンに存在する"
                 "「天気」効果モンスターは以下の効果を得る。"
                 "●このカードを除外し、自分フィールドのモンスター１体を対象として"
                 "発動できる。")

    def _build(self, supplement, desc=None, card_text=None):
        return build_tag_cards(
            [card(desc=desc or self.DESC)],
            [faq(card_text=card_text or self.CARD_TEXT, supplement=supplement)])

    def test_a_header_without_a_quote_defers(self):
        """【②の効果について】指的是整個編號效果,分不出領起句與 ●。"""
        entries, report = self._build(
            "【②の効果について】\n■モンスターゾーンで発動できる誘発即時効果です。")
        self.assertIsNone(clauses_of(entries, 1000)[0]["kind"])
        self.assertEqual(report["official_coverage"]["header"], 0)
        self.assertEqual([r["reason"] for r in report["attribution_deferred"]],
                         ["● 子效果待拆"])

    def test_a_quote_starting_in_the_lead_still_applies(self):
        """官方連領起句一起引用(RR－スカル・イーグル 45184165)時證據是明確的。"""
        entries, report = self._build(
            "■『②：このカードと同じ縦列の自分のメインモンスターゾーンに存在する"
            "「天気」効果モンスターは以下の効果を得る。●このカードを除外し』"
            "モンスター効果は、起動効果・誘発効果・誘発即時効果・永続効果の"
            "いずれにも分類されない効果です。")
        clause = clauses_of(entries, 1000)[0]
        self.assertEqual(clause["kind"], "無種類效果")
        self.assertEqual(report["official_coverage"]["quote"], 1)
        self.assertEqual(report["attribution_deferred"], [])

    def test_bullets_that_are_options_of_one_activation_are_untouched(self):
        """領起句自己就寫了發動時,`●` 只是選項列舉,官方的類型是整段的。"""
        entries, report = build_tag_cards(
            [card(desc="①：以下效果從1個選擇發動。\n●效果甲。\n●效果乙。")],
            [faq(card_text="①：以下の効果から１つを選択して発動できる。"
                           "●効果甲。●効果乙。",
                 supplement="■『●効果甲』はフィールドで発動できる起動効果です。")])
        self.assertEqual(clauses_of(entries, 1000)[0]["kind"], "啟動效果")
        self.assertEqual(report["attribution_deferred"], [])

    def test_a_mandatory_header_line_defers_too(self):
        """必發明示與類型明示共用同一套歸屬對位,排除條件也必須一起生效。"""
        entries, report = self._build(
            "【②の効果について】\n"
            "■モンスターゾーンで発動できる誘発効果です。必ず発動します。")
        clause = clauses_of(entries, 1000)[0]
        self.assertIsNone(clause["kind"])
        self.assertIsNone(clause["optional"])
        self.assertEqual([r["reason"] for r in report["attribution_deferred"]],
                         ["● 子效果待拆"])

    def test_splitting_the_bullets_out_restores_the_attestation(self):
        """官方以【●…について】解說時 ● 已拆成獨立效果句,領起句不再含 ●。"""
        entries, report = self._build(
            "【●の効果について】\n■モンスターゾーンで発動できる誘発即時効果です。")
        clauses = clauses_of(entries, 1000)
        self.assertEqual([c["index"] for c in clauses], ["②", "②-●1"])
        self.assertEqual([c["kind"] for c in clauses],
                         [None, "誘發即時效果(2速)"])
        self.assertEqual(report["attribution_deferred"], [])

    def test_a_lead_without_bullets_is_not_affected(self):
        """條件是「● 還沒拆開」,沒有 ● 的賦予句照常走五階梯。"""
        entries, report = build_tag_cards(
            [card(desc="②：我方場上的怪獸得到以下效果:攻擊力上升500。")],
            [faq(card_text="②：自分フィールドのモンスターは以下の効果を得る。"
                           "攻撃力は５００アップする。",
                 supplement="■モンスターゾーンで適用する永続効果です。")])
        self.assertEqual(clauses_of(entries, 1000)[0]["kind"], "永續效果")
        self.assertEqual(report["attribution_deferred"], [])


class TestInlineBulletQuoteSplitting(unittest.TestCase):
    """票16:官方以行內 `『●…』` 引用逐項給裁定,就是認可 ● 是獨立子效果。

    官方常常不開 `【●…について】` 標頭,改成在行內引用 `『●…』` 再說它的類型
    ——兩者是同一件事(官方拿整個 ● 當一個東西在講),拆句因此認第二種依據。
    只在**賦予型領起句**這一族開火:領起句自己就寫了發動時 `●` 只是同一個發動
    的選項列舉,票14 實測那一族的官方類型是對的。
    """

    # 晴れの天気模様(89355716)②:領起句不形成連鎖,2 速是 `●` 的
    DESC = ("②：與此卡同縱列的「天氣」效果怪獸得到以下效果。\n"
            "●將此卡除外發動。\n"
            "●只要此卡在場上存在,對方不能發動效果。")
    CARD_TEXT = ("②：このカードと同じ縦列の「天気」効果モンスターは"
                 "以下の効果を得る。"
                 "●このカードを除外して発動できる。"
                 "●このカードがフィールドに存在する限り、"
                 "相手は効果を発動できない。")

    def _build(self, supplement, desc=None, card_text=None):
        return build_tag_cards(
            [card(desc=desc or self.DESC)],
            [faq(card_text=card_text or self.CARD_TEXT, supplement=supplement)])

    def test_inline_bullet_quotes_split_the_bullets_out(self):
        entries, report = self._build(
            "■『●このカードを除外して発動できる』効果は誘発即時効果です。\n"
            "■『●このカードがフィールドに存在する限り、相手は効果を発動できない』"
            "効果は永続効果です。")
        clauses = clauses_of(entries, 1000)
        self.assertEqual([c["index"] for c in clauses],
                         ["②", "②-●1", "②-●2"])
        self.assertEqual([c["kind"] for c in clauses],
                         [None, "誘發即時效果(2速)", "永續效果"])
        self.assertEqual(report["bullet_clauses"], 2)
        self.assertEqual(report["bullet_quote_splits"], 1)
        self.assertEqual(report["attribution_deferred"], [])

    def test_a_bare_bullet_quote_is_evidence_too(self):
        """官方以『●』代稱子效果(大融合 7614732)也是拿它當一個東西在講。"""
        entries, report = self._build(
            "■同一チェーン上で２つ以上の『●』の効果の発動条件を満たした場合、"
            "そのそれぞれの『●』を同一チェーン上で発動できます。")
        self.assertEqual([c["index"] for c in clauses_of(entries, 1000)],
                         ["②", "②-●1", "②-●2"])
        self.assertEqual(report["bullet_quote_splits"], 1)

    def test_a_quote_that_does_not_start_at_a_bullet_is_no_evidence(self):
        """從句中截斷的引用只是一句話的片段,不是子效果的邊界(ADR-0003)。"""
        entries, report = self._build(
            "■『相手は効果を発動できない』というのは、"
            "効果の発動そのものができないという意味です。")
        self.assertEqual([c["index"] for c in clauses_of(entries, 1000)],
                         ["②"])
        self.assertEqual(report["bullet_quote_splits"], 0)

    def test_an_activating_lead_is_not_split_by_a_bullet_quote(self):
        """票14 回歸:領起句自己就寫了發動時,官方的類型是整段的。"""
        entries, report = build_tag_cards(
            [card(desc="①：以下效果從1個選擇發動。\n●效果甲。\n●效果乙。")],
            [faq(card_text="①：以下の効果から１つを選択して発動できる。"
                           "●効果甲。●効果乙。",
                 supplement="■『●効果甲』はフィールドで発動できる起動効果です。")])
        clauses = clauses_of(entries, 1000)
        self.assertEqual([c["index"] for c in clauses], ["①"])
        self.assertEqual(clauses[0]["kind"], "啟動效果")
        self.assertEqual(report["bullet_quote_splits"], 0)

    def test_a_quote_spanning_the_cut_blocks_the_split(self):
        """驗證二:官方自己的引用橫跨 ● 拆點,就證明那兩段是同一個效果句。

        RR－スカル・イーグル(45184165)②:官方的引用從領起句一路引到 `●`,
        講的是整段——這種卡不拆,類型照樣落在整段上。
        """
        entries, report = self._build(
            "■『②：このカードと同じ縦列の「天気」効果モンスターは"
            "以下の効果を得る。●このカードを除外して発動できる』モンスター効果は、"
            "起動効果・誘発効果・誘発即時効果・永続効果のいずれにも"
            "分類されない効果です。\n"
            "■『●このカードを除外して発動できる』効果は誘発即時効果です。")
        clauses = clauses_of(entries, 1000)
        self.assertEqual([c["index"] for c in clauses], ["②"])
        self.assertEqual(clauses[0]["kind"], "無種類效果")
        self.assertEqual([(r["id"], r["quotes"])
                          for r in report["bullet_quote_violations"]],
                         [(1000, ["②：このカードと同じ縦列の「天気」効果モンスター"
                                  "は以下の効果を得る。●このカードを除外して"
                                  "発動できる"])])

    def test_split_bullets_remain_contiguous_substrings(self):
        """驗證一:分項串接後等於原文,每一段都是原文的連續子字串。"""
        cards = [card(desc=self.DESC)]
        faqs = [faq(card_text=self.CARD_TEXT,
                    supplement="■『●このカードを除外して発動できる』効果は"
                               "誘発即時効果です。")]
        entries, report = build_tag_cards(cards, faqs)
        for clause in clauses_of(entries, 1000):
            self.assertIn(clause["text_zh"], cards[0]["desc"])
            self.assertIn(clause["text_ja"], faqs[0]["card_text"])
        self.assertEqual(report["substring_violations"], [])
        self.assertEqual(report["bullet_coverage_failed"], [])

    def test_bullet_counts_that_disagree_across_languages_are_not_split(self):
        entries, report = self._build(
            "■『●このカードを除外して発動できる』効果は誘発即時効果です。",
            desc="②：與此卡同縱列的「天氣」效果怪獸得到以下效果。\n●將此卡除外發動。")
        self.assertEqual([c["index"] for c in clauses_of(entries, 1000)],
                         ["②"])
        self.assertEqual([r["id"] for r in report["bullet_split_mismatch"]],
                         [1000])

    def test_the_mandatory_attestation_lands_on_the_bullet(self):
        """必發明示與類型明示共用同一套歸屬對位,拆完之後一起落到 ● 上。"""
        entries, _ = self._build(
            "■『●このカードを除外して発動できる』効果は誘発効果です。"
            "必ず発動します。")
        clauses = clauses_of(entries, 1000)
        self.assertEqual([c["kind"] for c in clauses],
                         [None, "誘發效果(1速)", None])
        self.assertEqual([c["optional"] for c in clauses],
                         [None, "必發", None])


class TestSequenceReferenceToABullet(unittest.TestCase):
    """票16:`『②』の『●…』` 指的是子效果,不是編號效果本身。

    序號引用只說了哪一個編號,`●` 拆開之後光靠它就不夠了——把 `●` 的類型套回
    編號效果的領起句正是票14 治的那個病,只是這一次是序號階梯犯的。
    """

    DESC = ("②：以此卡為素材X召喚的怪獸得到以下效果。\n"
            "●甲:攻擊力上升500。\n●乙:守備力上升500。")
    CARD_TEXT = ("②：このカードを素材としてX召喚したモンスターは"
                 "以下の効果を得る。"
                 "●甲：攻撃力は５００アップする。"
                 "●乙：守備力は５００アップする。")
    EVIDENCE = "■『●甲：攻撃力は５００アップする』効果は永続効果です。\n"

    def _build(self, supplement):
        return build_tag_cards(
            [card(desc=self.DESC)],
            [faq(card_text=self.CARD_TEXT,
                 supplement=self.EVIDENCE + supplement)])

    def test_a_sequence_ref_qualified_by_a_bullet_targets_the_bullet(self):
        entries, report = self._build(
            "■『②』の『●乙：守備力は５００アップする』は永続効果です。")
        clauses = clauses_of(entries, 1000)
        self.assertEqual([c["index"] for c in clauses],
                         ["②", "②-●1", "②-●2"])
        self.assertEqual([c["kind"] for c in clauses],
                         [None, "永續效果", "永續效果"])
        self.assertEqual(report["kind_conflicts"], [])

    def test_a_bullet_only_named_inside_a_parenthetical_is_not_the_subject(self):
        """『②』は…です。(…『●』…) 的主語是②,括弧裡的 `●` 只是解說時的指代。"""
        entries, _ = self._build(
            "■『②』は起動効果・誘発効果・誘発即時効果・永続効果の"
            "いずれにも分類されない効果です。"
            "（このカードを素材としてX召喚したモンスターが『●』の効果を得ます。）")
        clauses = clauses_of(entries, 1000)
        self.assertEqual([c["kind"] for c in clauses],
                         ["無種類效果", "永續效果", None])

    def test_an_unresolvable_bullet_reference_defers(self):
        """官方以『●』代稱但這個編號效果有兩個 `●`:指的是哪一個沒有證據。"""
        entries, report = self._build("■『②』の『●』は永続効果です。")
        clauses = clauses_of(entries, 1000)
        self.assertEqual([c["kind"] for c in clauses],
                         [None, "永續效果", None])
        self.assertEqual([(r["quote"], r["hits"])
                          for r in report["quote_ambiguous"]],
                         [("●", ["②-●1", "②-●2"])])

    def test_a_bullet_reference_with_the_bullets_unsplit_stays_on_the_clause(
            self):
        """`●` 還沒拆開時標的仍是整個編號效果,交給票14 那道閘門處理。

        領起句自己就寫了發動,`●` 因此不拆(票14);那一族的 `●` 只是同一個發動
        的選項列舉,官方的類型本來就是整段的。
        """
        entries, report = build_tag_cards(
            [card(desc="①：以下效果從1個選擇發動。\n●甲:抽1張卡。\n●乙:回復500。")],
            [faq(card_text="①：以下の効果から１つを選択して発動できる。"
                           "●甲：１枚ドローする。●乙：５００回復する。",
                 supplement="■『①』の『●乙：５００回復する』は起動効果です。")])
        clauses = clauses_of(entries, 1000)
        self.assertEqual([c["index"] for c in clauses], ["①"])
        self.assertEqual(clauses[0]["kind"], "啟動效果")
        self.assertEqual(report["attribution_deferred"], [])

    def test_a_bullet_reference_under_a_grant_lead_still_defers(self):
        """賦予型領起句不發動,`●` 又還沒拆開:官方講的是哪一邊沒有證據可分。

        引用不是卡文的子字串(官方改寫過)因此不構成拆句依據,`●` 留在原地。
        """
        entries, report = build_tag_cards(
            [card(desc="①：我方怪獸得到以下效果。\n●甲:攻擊力上升。\n●乙:守備力上升。")],
            [faq(card_text="①：自分のモンスターは以下の効果を得る。"
                           "●甲：攻撃力アップ。●乙：守備力アップ。",
                 supplement="【①の効果について】\n"
                            "■『●乙の効果』は永続効果です。")])
        clauses = clauses_of(entries, 1000)
        self.assertEqual([c["index"] for c in clauses], ["①"])
        self.assertIsNone(clauses[0]["kind"])
        self.assertEqual([r["reason"] for r in report["attribution_deferred"]],
                         ["● 子效果待拆"])

    def test_a_header_qualified_by_a_bullet_targets_the_bullet(self):
        """標頭同樣只說得出哪一個編號效果(降雷皇ハモン 73104892 ①)。"""
        entries, report = self._build(
            "【②の効果について】\n"
            "■この効果で得た『●乙：守備力は５００アップする』の効果は"
            "永続効果です。")
        clauses = clauses_of(entries, 1000)
        self.assertEqual([c["kind"] for c in clauses],
                         [None, "永續效果", "永續效果"])
        self.assertEqual(report["kind_conflicts"], [])


class TestNonEffectOnAWholeClause(unittest.TestCase):
    """票16:效果外明示的引用涵蓋整個效果句時就自動套用,涵蓋一部分只報告。

    領起句拆出 ● 之後自己還是沒有類型,而官方對這一族常寫
    `『②：…以下の効果を得る』は効果の扱いではありません`——引用涵蓋的正是拆完
    的那一段,對位沒有任何歧義可言,再交給判定只是浪費額度。
    """

    DESC = "①：此卡依表示形式得到以下效果。\n●攻擊表示:效果甲。\n●守備表示:效果乙。"
    CARD_TEXT = ("①：このカードは表示形式によって以下の効果を得る。"
                 "●攻撃表示：効果甲。●守備表示：効果乙。")
    NON_EFFECT = ("■『①：このカードは表示形式によって以下の効果を得る』"
                  "は効果の扱いではありません。")

    def _build(self, supplement):
        return build_tag_cards(
            [card(desc=self.DESC)],
            [faq(card_text=self.CARD_TEXT, supplement=supplement)])

    def test_a_split_lead_takes_the_non_effect_attestation(self):
        entries, report = self._build(
            self.NON_EFFECT
            + "\n■『●攻撃表示：効果甲』効果は永続効果です。")
        clauses = clauses_of(entries, 1000)
        self.assertEqual([c["index"] for c in clauses],
                         ["①", "①-●1", "①-●2"])
        self.assertEqual([c["kind"] for c in clauses],
                         ["效果外文本", "永續效果", None])
        self.assertEqual(clauses[0]["source"], "official")
        self.assertEqual(report["official_coverage"]["non_effect"], 1)
        self.assertEqual(report["non_effect_outside_preamble"], [])

    def test_an_unsplit_clause_only_gets_the_report(self):
        """符文眼靈擺龍(1516510):官方說領起句不是效果,但 `●` 還沒拆開。

        整段套上效果外文本會把 `●` 的效果一起吃掉,所以引用涵蓋不到整段時
        照舊只進報告。
        """
        entries, report = self._build(self.NON_EFFECT)
        clauses = clauses_of(entries, 1000)
        self.assertEqual([c["index"] for c in clauses], ["①"])
        self.assertIsNone(clauses[0]["kind"])
        self.assertEqual(
            [r["id"] for r in report["non_effect_outside_preamble"]], [1000])

    def test_the_preamble_still_matches_on_any_substring(self):
        """前言段整段都是效果外文本,引用命中其中一句就指得回同一段(票10)。"""
        entries, report = build_tag_cards(
            [card(desc="此卡不能通常召喚。此卡不能特殊召喚。\n①：效果甲。")],
            [faq(card_text="このカードは通常召喚できない。"
                           "このカードは特殊召喚できない。①：効果甲。",
                 supplement="■『このカードは通常召喚できない』"
                            "は効果として扱いません。")])
        preamble = clauses_of(entries, 1000)[0]
        self.assertEqual(preamble["kind"], "效果外文本")
        self.assertEqual(preamble["source"], "official")
        self.assertEqual(report["non_effect_outside_preamble"], [])


class TestMandatoryAttestation(unittest.TestCase):
    """官方明示「必ず発動する効果です」→ 必發,優先於任何規則。"""

    TRIGGER_HEADER = ("【①の効果について】\n"
                      "■モンスターゾーンで発動する誘発効果です。")

    def test_official_mandatory_beats_the_dekiru_rule(self):
        entries, report = build_tag_cards(
            [card(desc="①：可以發動。從卡組抽1張卡。")],
            [faq(card_text="①：このカードが墓地へ送られた場合に発動できる。"
                           "デッキから１枚ドローする。",
                 supplement=self.TRIGGER_HEADER + "（必ず発動する効果です。）")])
        clause = clauses_of(entries, 1000)[0]
        self.assertEqual(clause["kind"], "誘發效果(1速)")
        self.assertEqual(clause["optional"], "必發")
        self.assertEqual(report["optional_official"], 1)

    def test_masu_form_is_also_a_mandatory_attestation(self):
        """官方寫過「必ず発動する効果です」與「必ず発動します」兩種。"""
        entries, _ = build_tag_cards(
            [card(desc="①：可以發動。從卡組抽1張卡。")],
            [faq(card_text="①：このカードが墓地へ送られた場合に発動できる。"
                           "デッキから１枚ドローする。",
                 supplement=self.TRIGGER_HEADER
                            + "\n■条件を満たした場合に必ず発動します。")])
        self.assertEqual(clauses_of(entries, 1000)[0]["optional"], "必發")

    def test_mandatory_without_a_kind_leaves_optional_for_judgment(self):
        """官方只寫必發、沒寫類型時不寫值——必發/選發只在兩種類型上有值。"""
        entries, report = build_tag_cards(
            [card(desc="①：效果甲。")],
            [faq(card_text="①：効果甲。",
                 supplement="■このカードがリバースした場合に"
                            "必ず発動する効果です。")])
        clause = clauses_of(entries, 1000)[0]
        self.assertIsNone(clause["kind"])
        self.assertIsNone(clause["optional"])
        self.assertEqual(report["mandatory_kind_unknown"], 1)

    def test_mandatory_line_on_a_multi_clause_card_defers_attribution(self):
        """歸屬不確定的必發明示自成一份清單,不混進票03 的類型清單。"""
        entries, report = build_tag_cards(
            [card(desc="①：效果甲。\n②：效果乙。")],
            [faq(card_text="①：効果甲。②：効果乙。",
                 supplement="■このカードがリバースした場合に"
                            "必ず発動する効果です。")])
        self.assertEqual([c["optional"] for c in clauses_of(entries, 1000)],
                         [None, None])
        self.assertEqual([(r["id"], r["note"], r["reason"])
                          for r in report["mandatory_deferred"]],
                         [(1000, "attribution_deferred", "無歸屬標記")])
        self.assertEqual(report["attribution_deferred"], [])

    def test_forbidden_phrase_still_blocks_a_mandatory_judgment(self):
        """「効果ではありません」的禁令對必發明示同樣有效,規則層照常接手。"""
        entries, _ = build_tag_cards(
            [card(desc="①：可以發動。")],
            [faq(card_text="①：１ターンに１度、発動できる。",
                 supplement=self.TRIGGER_HEADER
                            + "\n■必ず発動する効果ではありません。")])
        self.assertEqual(clauses_of(entries, 1000)[0]["optional"], "選發")


class TestOptionalRule(unittest.TestCase):
    """日文發動子句的「できる」規則(官方沒明示時的第二層)。"""

    TRIGGER_HEADER = ("【①の効果について】\n"
                      "■モンスターゾーンで発動する誘発効果です。")

    def optional_of(self, card_text, desc="①：效果甲。", supplement=None):
        entries, report = build_tag_cards(
            [card(desc=desc)],
            [faq(card_text=card_text,
                 supplement=supplement or self.TRIGGER_HEADER)])
        return clauses_of(entries, 1000), report

    def test_activation_clause_ending_in_dekiru_is_optional(self):
        clauses, report = self.optional_of(
            "①：このカードが墓地へ送られた場合に発動できる。"
            "デッキから１枚ドローする。")
        self.assertEqual(clauses[0]["optional"], "選發")
        self.assertEqual(report["optional_rule"], 1)

    def test_activation_clause_not_ending_in_dekiru_is_mandatory(self):
        clauses, _ = self.optional_of(
            "①：自分エンドフェイズに発動する。フィールドのカード１枚を"
            "持ち主の手札に戻す。")
        self.assertEqual(clauses[0]["optional"], "必發")

    def test_dekimasu_ending_is_also_optional(self):
        clauses, _ = self.optional_of("①：１ターンに１度、発動できます。")
        self.assertEqual(clauses[0]["optional"], "選發")

    def test_completed_event_keeps_dekiru_inside_its_only_sentence(self):
        """「…時,可以」型:できる 在唯一那句上,屬於發動子句。"""
        clauses, _ = self.optional_of(
            "①：このカードが召喚に成功した時、相手に"
            "１０００ダメージを与える事ができる。")
        self.assertEqual(clauses[0]["optional"], "選發")

    def test_dekinai_in_the_resolution_is_not_an_activation_ending(self):
        clauses, _ = self.optional_of(
            "①：相手が魔法カードを発動した時に発動する。その発動を無効にする。"
            "このターン、このカードは攻撃できない。")
        self.assertEqual(clauses[0]["optional"], "必發")

    def test_trailing_parenthetical_does_not_hide_the_ending(self):
        """官方把補述寫在發動子句句尾的括號裡,可否仍在括號之前。"""
        clauses, _ = self.optional_of(
            "①：通常魔法カードが発動した時に発動できる（同一チェーン上では"
            "１度まで）。そのカードを除外する。")
        self.assertEqual(clauses[0]["optional"], "選發")

    def test_period_inside_a_parenthetical_is_not_the_sentence_end(self):
        clauses, _ = self.optional_of(
            "①：自分フィールドのモンスター１体を対象として発動できる"
            "（この効果は１ターンに１度しか使えない。）。"
            "そのモンスターを破壊する。")
        self.assertEqual(clauses[0]["optional"], "選發")

    def test_lead_in_sentence_without_an_activation_is_left_for_judgment(self):
        """「②：…は以下の効果を得る。●…」的領起句不是發動子句。

        明示句得**引用領起句**才進得了必發/選發那一層:`●` 未拆時,不指名領起句
        的官方類型會先被歸屬那一關擋掉(見 TestGrantLeadWithUnsplitBullets)。
        """
        clauses, report = self.optional_of(
            "①：このカードと相互リンクしているモンスターの数によって"
            "以下の効果を得る。\n●１体以上：攻撃宣言時に発動する。",
            supplement="■『①：このカードと相互リンクしているモンスターの数に"
                       "よって以下の効果を得る』モンスター効果は、"
                       "モンスターゾーンで発動する誘発効果です。")
        self.assertIsNone(clauses[0]["optional"])
        self.assertEqual([(r["id"], r["reason"])
                          for r in report["optional_pending"]],
                         [(1000, "找不到發動子句")])

    def test_scan_stops_at_the_clause_boundary(self):
        """日文卡文整段不換行時,①的掃描不得咬到②的「発動できる」。"""
        entries, _ = build_tag_cards(
            [card(desc="①：發動。\n②：可以發動。")],
            [faq(card_text="①：自分エンドフェイズに発動する。"
                           "フィールドのカード１枚を持ち主の手札に戻す。"
                           "②：１ターンに１度、手札を１枚捨てて発動できる。"
                           "デッキから１枚ドローする。",
                 supplement="【①の効果について】\n"
                            "■モンスターゾーンで発動する誘発効果です。\n"
                            "【②の効果について】\n"
                            "■モンスターゾーンで発動する誘発効果です。")])
        self.assertEqual([c["optional"] for c in clauses_of(entries, 1000)],
                         ["必發", "選發"])

    def test_only_the_two_activated_kinds_get_a_value(self):
        supplements = {
            "永續效果": "■モンスターゾーンで適用する永続効果です。",
            "啟動效果": "■モンスターゾーンで発動できる起動効果です。",
            "誘發即時效果(2速)": "■手札で発動できる誘発即時効果です。",
            "無種類效果": "■起動効果・誘発効果・誘発即時効果・永続効果の"
                          "いずれにも分類されない効果です。",
        }
        for kind, line in supplements.items():
            with self.subTest(kind=kind):
                clauses, report = self.optional_of(
                    "①：１ターンに１度、発動できる。デッキから１枚ドローする。",
                    supplement="【①の効果について】\n" + line)
                self.assertEqual(clauses[0]["kind"], kind)
                if kind == "誘發即時效果(2速)":
                    self.assertEqual(clauses[0]["optional"], "選發")
                else:
                    self.assertIsNone(clauses[0]["optional"])
                self.assertEqual(report["optional_on_wrong_kind"], [])

    def test_non_effect_preamble_never_gets_a_value(self):
        clauses, _ = self.optional_of(
            "このカード名の①の効果は１ターンに１度しか使用できない。"
            "①：１ターンに１度、発動できる。デッキから１枚ドローする。",
            desc="這個卡名的①效果1回合只能使用1次。\n①：效果甲。")
        self.assertEqual(clauses[0]["kind"], "效果外文本")
        self.assertIsNone(clauses[0]["optional"])

    def test_missing_japanese_text_leaves_optional_for_judgment(self):
        entries, report = build_tag_cards(
            [card(desc="①：效果甲。")],
            [faq(card_text="",
                 supplement="■モンスターゾーンで発動する誘発効果です。")])
        self.assertIsNone(clauses_of(entries, 1000)[0]["optional"])
        self.assertEqual([(r["id"], r["index"])
                          for r in report["optional_pending"]], [(1000, "①")])

    def test_unsplit_old_style_text_is_left_for_judgment(self):
        """舊式無編號卡文還沒依語意拆開,第一句不保證是發動子句。

        整團的類型只能由官方自己給的『①』歸屬證據決定(階梯二)——階梯四、五
        對未拆的整團不開火。
        """
        entries, report = build_tag_cards(
            [card(desc="這張卡被送去墓地時可以發動。從卡組抽1張卡。")],
            [faq(card_text="このカードが墓地へ送られた場合に発動できる。"
                           "デッキから１枚ドローする。",
                 supplement="■『①』はモンスターゾーンで発動する誘発効果です。")])
        clause = clauses_of(entries, 1000)[0]
        self.assertEqual(clause["kind"], "誘發效果(1速)")
        self.assertIsNone(clause["optional"])
        self.assertEqual([(r["id"], r["reason"])
                          for r in report["optional_pending"]],
                         [(1000, "未拆句")])


class TestOptionalValidation(unittest.TestCase):
    """用官方明示的必發當獨立驗證集,遮住答案跑規則再對答案。"""

    MANDATORY = ("【①の効果について】\n"
                 "■モンスターゾーンで発動する誘発効果です。"
                 "（必ず発動する効果です。）")

    def build_two(self):
        return build_tag_cards(
            [card(cid=1000, desc="①：效果甲。"),
             card(cid=2000, desc="①：效果乙。")],
            [faq(password=1000,
                 card_text="①：自分エンドフェイズに発動する。"
                           "フィールドのカード１枚を持ち主の手札に戻す。",
                 supplement=self.MANDATORY),
             faq(password=2000,
                 card_text="①：１ターンに１度、発動できる。"
                           "デッキから１枚ドローする。",
                 supplement=self.MANDATORY)])

    def test_rate_counts_only_clauses_the_rule_could_predict(self):
        _, report = self.build_two()
        validation = report["optional_validation"]
        self.assertEqual(validation["attested"], 2)
        self.assertEqual(validation["predicted"], 2)
        self.assertEqual(validation["agree"], 1)

    def test_every_disagreement_is_listed_with_its_activation_clause(self):
        _, report = self.build_two()
        disagree = report["optional_validation"]["disagree"]
        self.assertEqual([(r["id"], r["predicted"]) for r in disagree],
                         [(2000, "選發")])
        self.assertEqual(disagree[0]["activation"], "１ターンに１度、発動できる")

    def test_official_answer_wins_even_where_the_rule_disagrees(self):
        entries, _ = self.build_two()
        self.assertEqual(clauses_of(entries, 2000)[0]["optional"], "必發")

    def test_unsplit_clauses_are_excluded_from_the_denominator(self):
        _, report = build_tag_cards(
            [card(desc="這張卡被送去墓地時發動。從卡組抽1張卡。")],
            [faq(card_text="このカードが墓地へ送られた場合に発動できる。"
                           "デッキから１枚ドローする。",
                 supplement="■『①』はモンスターゾーンで発動する誘発効果です。"
                            "（必ず発動する効果です。）")])
        validation = report["optional_validation"]
        self.assertEqual(validation["attested"], 1)
        self.assertEqual(validation["predicted"], 0)
        self.assertEqual(validation["unsplit"], 1)


class TestExistingSheetMerge(unittest.TestCase):
    """重跑保留語意:既有標記表以 (卡片密碼, section, index) 對應回來。"""

    CARD = card(desc="①：效果甲。\n②：效果乙。")
    PLAIN = faq(card_text="①：効果甲。②：効果乙。")
    ATTESTED = faq(card_text="①：効果甲。②：効果乙。",
                   supplement="【①の効果について】\n"
                              "■モンスターゾーンで発動できる起動効果です。")
    # ①的日文卡文被勘誤:身分改變,雜湊隨之改變
    ERRATA = faq(card_text="①：効果甲、その後１枚ドローする。②：効果乙。")

    def first_build(self, faqs=None):
        entries, _ = build_tag_cards([self.CARD], faqs or [self.PLAIN])
        return entries

    def rerun(self, existing, faqs=None):
        return build_tag_cards([self.CARD], faqs or [self.PLAIN],
                               existing=existing)

    def test_existing_judgment_is_reused_when_the_hash_matches(self):
        existing = self.first_build()
        mark(existing, 1000, "①", kind="永續效果", source="llm")
        entries, report = self.rerun(existing)
        clause = clauses_of(entries, 1000)[0]
        self.assertEqual((clause["kind"], clause["source"]),
                         ("永續效果", "llm"))
        self.assertFalse(clause["needs_review"])
        self.assertEqual(report["preserved_judgments"], 1)

    def test_judgment_is_matched_by_password_section_index(self):
        """同一個 index 在別張卡、別個 section 上不得互相污染。"""
        cards = [card(1000, desc="①：效果甲。"),
                 card(2000, desc="【靈擺效果】\n①：靈擺甲。\n【怪獸效果】\n①：怪獸甲。",
                      ctype=TYPE_PENDULUM_EFFECT)]
        faqs = [faq(1000, card_text="①：効果甲。"),
                faq(2000, card_text="①：モンスター甲。",
                    pen_effect="①：ペンデュラム甲。")]
        existing, _ = build_tag_cards(cards, faqs)
        mark(existing, 2000, "①", kind="永續效果", source="manual")  # pendulum 在前
        entries, _ = build_tag_cards(cards, faqs, existing=existing)
        self.assertIsNone(clauses_of(entries, 1000)[0]["kind"])
        self.assertEqual([(c["section"], c["kind"])
                          for c in clauses_of(entries, 2000)],
                         [("pendulum", "永續效果"), ("main", None)])

    def test_manual_row_survives_a_conflicting_official_attestation(self):
        existing = self.first_build()
        mark(existing, 1000, "①", kind="永續效果", source="manual")
        entries, report = self.rerun(existing, [self.ATTESTED])
        clause = clauses_of(entries, 1000)[0]
        self.assertEqual((clause["kind"], clause["source"]),
                         ("永續效果", "manual"))
        self.assertEqual([(r["id"], r["existing"], r["official"])
                          for r in report["late_official_conflicts"]],
                         [(1000, "永續效果", "啟動效果")])

    def test_manual_row_agreeing_with_official_keeps_its_provenance(self):
        existing = self.first_build()
        mark(existing, 1000, "①", kind="啟動效果", source="manual")
        entries, report = self.rerun(existing, [self.ATTESTED])
        self.assertEqual(clauses_of(entries, 1000)[0]["source"], "manual")
        self.assertEqual(report["late_official_conflicts"], [])

    def test_official_row_survives_when_the_attestation_disappears(self):
        existing = self.first_build([self.ATTESTED])
        entries, _ = self.rerun(existing)
        clause = clauses_of(entries, 1000)[0]
        self.assertEqual((clause["kind"], clause["source"]),
                         ("啟動效果", "official"))

    def test_row_never_judged_is_processed_normally(self):
        """source 為 null 的行沒有什麼要保留的,照常吃本次的判定。"""
        existing = self.first_build()
        entries, report = self.rerun(existing, [self.ATTESTED])
        self.assertEqual(clauses_of(entries, 1000)[0]["kind"], "啟動效果")
        self.assertEqual(report["preserved_judgments"], 0)

    def test_first_build_and_rerun_take_the_same_path(self):
        existing = self.first_build([self.ATTESTED])
        entries, report = self.rerun(existing, [self.ATTESTED])
        self.assertEqual(entries, existing)
        self.assertEqual(report["needs_review"], [])
        self.assertEqual(report["late_official_conflicts"], [])

    # 卡文的發動子句不以「できる」結尾 → [[規則層]]會預測必發;而補足情報只寫了
    # [[效果類型]],沒寫「必ず発動」——[[必發/選發]]那一格因此是判定票填的
    MANDATORY_LOOKING = card(desc="①：此卡送去墓地的場合發動。抽1張卡。")
    TRIGGER_ATTESTED = faq(
        card_text="①：このカードが墓地へ送られた場合に発動する。"
                  "デッキから１枚ドローする。",
        supplement="■墓地で発動する誘発効果です。")

    def judged_optional_sheet(self, optional="選發"):
        """官方給類型、判定票給必發/選發的一行(舊式卡文的常態)。"""
        entries, _ = build_tag_cards(
            [self.MANDATORY_LOOKING], [self.TRIGGER_ATTESTED],
            judgments=[{"id": 1000, "section": "main",
                        "clauses": [{"index": "①", "kind": "誘發效果(1速)",
                                     "optional": optional}]}])
        clause = clauses_of(entries, 1000)[0]
        self.assertEqual((clause["source"], clause["optional"]),
                         ("official", optional))
        return entries

    def test_the_rule_layer_does_not_overwrite_a_judged_optional_on_rerun(self):
        """[[規則層]]的必發/選發是對當前文本的猜測,不得洗掉判定票的決定。

        規則層看發動子句的句尾:不以「できる」結尾就推定必發。魔法・陷阱卡「這張卡
        本身的發動」與 `〜する事で` 代價句型正是它會猜錯的兩族(§4、§5.8),判定票
        覆寫成選發之後,重跑不能又把它翻回去(票18 實測 2 條)。
        """
        entries, report = build_tag_cards(
            [self.MANDATORY_LOOKING], [self.TRIGGER_ATTESTED],
            existing=self.judged_optional_sheet())
        self.assertEqual(clauses_of(entries, 1000)[0]["optional"], "選發")
        self.assertEqual(report["official_changed"], [])

    def test_an_official_mandatory_attestation_still_wins_on_rerun(self):
        """官方後來寫了「必ず発動」時照樣以官方為準,而且要看得見。"""
        attested = faq(card_text=self.TRIGGER_ATTESTED["card_text"],
                       supplement="■墓地で発動する誘発効果です。"
                                  "(必ず発動する効果です。)")
        entries, report = build_tag_cards(
            [self.MANDATORY_LOOKING], [attested],
            existing=self.judged_optional_sheet())
        self.assertEqual(clauses_of(entries, 1000)[0]["optional"], "必發")
        self.assertEqual([(r["id"], r["existing"], r["official"])
                          for r in report["official_changed"]],
                         [(1000, "誘發效果(1速)/選發", "誘發效果(1速)/必發")])

    def test_rerunning_an_official_row_keeps_a_value_official_never_wrote(self):
        """官方明示只管它自己寫得出來的欄位。

        官方寫了[[效果類型]]、沒寫[[必發/選發]]時,那一格是判定票填的(§4 階梯二)。
        重跑時把整行換成本次算出來的官方結果會把它洗成 null,而且會冒充成
        「官方改了自己的裁定」——票18 實測一次重跑掉 22 條。
        """
        existing = self.first_build([self.ATTESTED])
        mark(existing, 1000, "①", optional="選發")
        entries, report = self.rerun(existing, [self.ATTESTED])
        clause = clauses_of(entries, 1000)[0]
        self.assertEqual((clause["kind"], clause["source"], clause["optional"]),
                         ("啟動效果", "official", "選發"))
        self.assertEqual(report["official_changed"], [])


class TestHashChangeReview(unittest.TestCase):
    """雜湊變動:不覆蓋,標記待複查並列進報告。"""

    CARD = TestExistingSheetMerge.CARD
    PLAIN = TestExistingSheetMerge.PLAIN
    ERRATA = TestExistingSheetMerge.ERRATA

    def judged_sheet(self, source="manual"):
        entries, _ = build_tag_cards([self.CARD], [self.PLAIN])
        mark(entries, 1000, "①", kind="永續效果", source=source)
        return entries

    def test_changed_hash_keeps_the_judgment_and_flags_review(self):
        entries, report = build_tag_cards([self.CARD], [self.ERRATA],
                                          existing=self.judged_sheet())
        clause = clauses_of(entries, 1000)[0]
        self.assertEqual(clause["text_ja"], "①：効果甲、その後１枚ドローする。")
        self.assertEqual((clause["kind"], clause["source"]),
                         ("永續效果", "manual"))
        self.assertTrue(clause["needs_review"])
        self.assertEqual([(r["id"], r["index"], r["hash_changed"])
                          for r in report["needs_review"]],
                         [(1000, "①", True)])

    def test_unchanged_rows_are_not_flagged(self):
        _, report = build_tag_cards([self.CARD], [self.ERRATA],
                                    existing=self.judged_sheet())
        self.assertEqual([r["index"] for r in report["needs_review"]], ["①"])

    def test_review_flag_persists_until_the_user_clears_it(self):
        flagged, _ = build_tag_cards([self.CARD], [self.ERRATA],
                                     existing=self.judged_sheet())
        entries, report = build_tag_cards([self.CARD], [self.ERRATA],
                                          existing=flagged)
        self.assertTrue(clauses_of(entries, 1000)[0]["needs_review"])
        self.assertEqual([(r["index"], r["hash_changed"])
                          for r in report["needs_review"]], [("①", False)])

    def test_clearing_the_flag_sticks(self):
        flagged, _ = build_tag_cards([self.CARD], [self.ERRATA],
                                     existing=self.judged_sheet())
        mark(flagged, 1000, "①", needs_review=False)
        entries, report = build_tag_cards([self.CARD], [self.ERRATA],
                                          existing=flagged)
        self.assertFalse(clauses_of(entries, 1000)[0]["needs_review"])
        self.assertEqual(report["needs_review"], [])

    def test_unjudged_row_whose_text_changed_is_simply_rebuilt(self):
        """沒有判定可保留的行不必待複查——重跑本來就會給它新的文本。"""
        existing, _ = build_tag_cards([self.CARD], [self.PLAIN])
        entries, report = build_tag_cards([self.CARD], [self.ERRATA],
                                          existing=existing)
        self.assertFalse(clauses_of(entries, 1000)[0]["needs_review"])
        self.assertEqual(report["needs_review"], [])


class TestLateOfficialAttestation(unittest.TestCase):
    """遲到的官方明示:不沿用而是比對(補足情報是會成長的來源)。"""

    CARD = TestExistingSheetMerge.CARD
    PLAIN = TestExistingSheetMerge.PLAIN
    ATTESTED = TestExistingSheetMerge.ATTESTED
    TRIGGER = faq(card_text="①：効果甲。②：効果乙。",
                  supplement="【①の効果について】\n"
                             "■モンスターゾーンで発動する誘発効果です。")

    def rerun_with(self, kind, source, **fields):
        existing, _ = build_tag_cards([self.CARD], [self.PLAIN])
        mark(existing, 1000, "①", kind=kind, source=source, **fields)
        return build_tag_cards([self.CARD], [self.ATTESTED], existing=existing)

    def test_agreement_upgrades_the_source_to_official(self):
        entries, report = self.rerun_with("啟動效果", "llm")
        clause = clauses_of(entries, 1000)[0]
        self.assertEqual((clause["kind"], clause["source"]),
                         ("啟動效果", "official"))
        self.assertEqual(report["late_official_upgrades"], 1)
        self.assertEqual(report["late_official_conflicts"], [])

    def test_llm_then_rule_is_upgraded_the_same_way(self):
        entries, _ = self.rerun_with("啟動效果", "llm_then_rule")
        self.assertEqual(clauses_of(entries, 1000)[0]["source"], "official")

    def test_disagreement_keeps_the_existing_judgment(self):
        entries, report = self.rerun_with("永續效果", "llm")
        clause = clauses_of(entries, 1000)[0]
        self.assertEqual((clause["kind"], clause["source"]),
                         ("永續效果", "llm"))
        self.assertEqual([(r["id"], r["index"], r["existing"], r["official"],
                           r["source"])
                          for r in report["late_official_conflicts"]],
                         [(1000, "①", "永續效果", "啟動效果", "llm")])
        self.assertEqual(report["late_official_upgrades"], 0)

    def test_upgrading_keeps_the_existing_tags(self):
        """tags 不是官方明示決定的欄位,升級不得把它洗掉。"""
        entries, _ = self.rerun_with("啟動效果", "llm", tags=["從牌組特招"])
        self.assertEqual(clauses_of(entries, 1000)[0]["tags"], ["從牌組特招"])

    def test_upgrading_keeps_an_optional_this_run_cannot_produce(self):
        """規則層算不出來的欄位不得在升級時被洗成 null。"""
        rebuilt, _ = build_tag_cards([self.CARD], [self.TRIGGER])
        self.assertIsNone(clauses_of(rebuilt, 1000)[0]["optional"])

        existing, _ = build_tag_cards([self.CARD], [self.PLAIN])
        mark(existing, 1000, "①", kind="誘發效果(1速)", optional="必發",
             source="llm")
        entries, _ = build_tag_cards([self.CARD], [self.TRIGGER],
                                     existing=existing)
        clause = clauses_of(entries, 1000)[0]
        self.assertEqual((clause["source"], clause["optional"]),
                         ("official", "必發"))

    def test_upgraded_row_does_not_count_as_a_preserved_judgment(self):
        """升為 official 的行吃的是本次的判定,不算「沿用既有判定」。"""
        _, report = self.rerun_with("啟動效果", "llm")
        self.assertEqual(report["preserved_judgments"], 0)
        _, report = self.rerun_with("永續效果", "llm")
        self.assertEqual(report["preserved_judgments"], 1)

    def test_late_mandatory_attestation_reaches_the_upgraded_row(self):
        existing, _ = build_tag_cards([self.CARD], [self.PLAIN])
        mark(existing, 1000, "①", kind="誘發效果(1速)", source="llm")
        entries, _ = build_tag_cards(
            [self.CARD],
            [faq(card_text="①：効果甲。②：効果乙。",
                 supplement="【①の効果について】\n"
                            "■モンスターゾーンで発動する誘発効果です。"
                            "（必ず発動する効果です。）")],
            existing=existing)
        clause = clauses_of(entries, 1000)[0]
        self.assertEqual((clause["source"], clause["optional"]),
                         ("official", "必發"))


class TestRuleLayerRecompute(unittest.TestCase):
    """source=rule 是當前規則層的純函式輸出,規則改了就該重算並列出差異。"""

    CARD = card(desc="這個卡名的①效果1回合只能使用1次。\n①：效果甲。")
    FAQ = faq(card_text="このカード名の①の効果は１ターンに１度しか使用できない。"
                        "①：効果甲。")

    def test_rule_row_is_recomputed_and_its_change_reported(self):
        existing, _ = build_tag_cards([self.CARD], [self.FAQ])
        mark(existing, 1000, "0", role="召喚條件")  # 假裝上一版規則層判成這樣
        entries, report = build_tag_cards([self.CARD], [self.FAQ],
                                          existing=existing)
        preamble = clauses_of(entries, 1000)[0]
        self.assertEqual(preamble["role"], "使用次數限制")
        self.assertEqual([(r["id"], r["index"], r["existing"], r["rebuilt"])
                          for r in report["rule_changed"]],
                         [(1000, "0", "效果外文本/召喚條件",
                           "效果外文本/使用次數限制")])

    def test_unchanged_rule_row_is_not_listed(self):
        existing, _ = build_tag_cards([self.CARD], [self.FAQ])
        _, report = build_tag_cards([self.CARD], [self.FAQ], existing=existing)
        self.assertEqual(report["rule_changed"], [])


class TestOrphanedJudgments(unittest.TestCase):
    """拆句法變動讓某一行消失時,那行的判定不得靜靜蒸發。"""

    THREE = card(desc="①：效果甲。\n②：效果乙。\n③：效果丙。")
    THREE_FAQ = faq(card_text="①：効果甲。②：効果乙。③：効果丙。")

    def test_judgment_with_no_matching_row_is_reported(self):
        existing, _ = build_tag_cards([self.THREE], [self.THREE_FAQ])
        mark(existing, 1000, "③", kind="永續效果", source="manual")
        _, report = build_tag_cards([TestExistingSheetMerge.CARD],
                                    [TestExistingSheetMerge.PLAIN],
                                    existing=existing)
        self.assertEqual([(r["id"], r["index"], r["source"], r["kind"])
                          for r in report["orphaned_judgments"]],
                         [(1000, "③", "manual", "永續效果")])

    def test_unjudged_disappearing_row_is_not_reported(self):
        existing, _ = build_tag_cards([self.THREE], [self.THREE_FAQ])
        _, report = build_tag_cards([TestExistingSheetMerge.CARD],
                                    [TestExistingSheetMerge.PLAIN],
                                    existing=existing)
        self.assertEqual(report["orphaned_judgments"], [])


class TestMergeReport(unittest.TestCase):

    CARD = card(desc="這個卡名的①效果1回合只能使用1次。\n①：效果甲。\n②：效果乙。")
    FAQ = faq(card_text="このカード名の①の効果は１ターンに１度しか使用できない。"
                        "①：効果甲。②：効果乙。",
              supplement="【①の効果について】\n"
                         "■モンスターゾーンで発動できる起動効果です。")

    def test_report_counts_every_source_value(self):
        existing, _ = build_tag_cards([self.CARD], [self.FAQ])
        mark(existing, 1000, "②", kind="永續效果", source="manual")
        _, report = build_tag_cards([self.CARD], [self.FAQ], existing=existing)
        self.assertEqual(report["source_counts"],
                         {"official": 1, "rule": 1, "llm": 0,
                          "llm_then_rule": 0, "manual": 1, "null": 0})

    def test_first_build_counts_sources_too(self):
        _, report = build_tag_cards([self.CARD], [self.FAQ])
        self.assertEqual(report["source_counts"]["null"], 1)
        self.assertEqual(report["preserved_judgments"], 0)


class TestRerunEndToEnd(unittest.TestCase):
    """票面的端到端場景。"""

    CARD = card(desc="①：效果甲。\n②：效果乙。")
    FAQ = faq(card_text="①：効果甲。②：効果乙。",
              supplement="【①の効果について】\n"
                         "■モンスターゾーンで発動できる起動効果です。")
    ERRATA = faq(card_text="①：効果甲、その後１枚ドローする。②：効果乙。",
                 supplement="【①の効果について】\n"
                            "■モンスターゾーンで発動できる起動効果です。")

    def test_manual_fix_survives_a_rerun_then_errata_flags_review(self):
        first, _ = build_tag_cards([self.CARD], [self.FAQ])
        self.assertEqual(clauses_of(first, 1000)[0]["kind"], "啟動效果")

        # 使用者把①改成別的類型並標 manual
        mark(first, 1000, "①", kind="誘發即時效果(2速)", source="manual")
        second, report = build_tag_cards([self.CARD], [self.FAQ],
                                         existing=first)
        clause = clauses_of(second, 1000)[0]
        self.assertEqual((clause["kind"], clause["source"]),
                         ("誘發即時效果(2速)", "manual"))
        self.assertFalse(clause["needs_review"])

        # 來源卡文改了 → 雜湊變動 → 待複查,原判定保留
        third, report = build_tag_cards([self.CARD], [self.ERRATA],
                                        existing=second)
        clause = clauses_of(third, 1000)[0]
        self.assertEqual((clause["kind"], clause["source"]),
                         ("誘發即時效果(2速)", "manual"))
        self.assertTrue(clause["needs_review"])
        self.assertEqual([(r["id"], r["index"])
                          for r in report["needs_review"]], [(1000, "①")])


class TestShadowPrediction(unittest.TestCase):
    """效果類型規則層:規則只寫影子預測,不決定 kind(ADR-0002)。

    fixture 用的是真的規則清單(`rules.RULES`),不是為測試捏造的假規則——規則層
    要覆蓋 ≥8 條才上工,所以每個場景都得成批餵卡,這也順便把「覆蓋條數由本次
    全表算出來」測進去了。
    """

    # 只命中 R1(發動子句含「〜た場合に発動」)→ 誘發效果(1速)
    ZH = "①：此卡被送去墓地的場合發動。從牌組抽1張卡。"
    JA = "①：このカードが墓地へ送られた場合に発動する。デッキから１枚ドローする。"
    PREDICTED = "誘發效果(1速)"

    def build(self, count, existing=None, supplement=None):
        cards = [card(1000 + i, desc=self.ZH) for i in range(count)]
        faqs = [faq(1000 + i, card_text=self.JA, supplement=supplement)
                for i in range(count)]
        return build_tag_cards(cards, faqs, existing=existing)

    def judged(self, count, kind, source):
        """既有標記表:每一張的①都已判定成 kind,來源為 source。"""
        entries, _ = self.build(count)
        for cid in range(1000, 1000 + count):
            mark(entries, cid, "①", kind=kind, source=source)
        return entries

    def rule_row(self, report, rule_id):
        for row in report["rules"]:
            if row["id"] == rule_id:
                return row
        raise AssertionError(f"報告沒有 {rule_id}")

    def test_prediction_is_written_without_deciding_the_kind(self):
        entries, report = self.build(8)
        clause = clauses_of(entries, 1000)[0]
        self.assertEqual(clause["rule_predicted"], self.PREDICTED)
        self.assertIsNone(clause["kind"])
        self.assertIsNone(clause["source"])
        self.assertEqual(report["rule_predictions"], 8)

    def test_coverage_is_counted_from_this_run_not_from_the_registry(self):
        _, report = self.build(11)
        self.assertEqual(self.rule_row(report, "R1")["coverage"], 11)
        self.assertEqual(self.rule_row(report, "R2")["coverage"], 0)

    def test_a_rule_below_the_coverage_threshold_does_not_run(self):
        entries, report = self.build(7)
        self.assertIsNone(clauses_of(entries, 1000)[0]["rule_predicted"])
        self.assertEqual(report["rule_predictions"], 0)
        self.assertIn("R1", report["rule_below_threshold"])
        self.assertFalse(self.rule_row(report, "R1")["applied"])

    def test_agreeing_llm_row_becomes_a_double_confirmation(self):
        entries, report = self.build(8, self.judged(8, self.PREDICTED, "llm"))
        clause = clauses_of(entries, 1000)[0]
        self.assertEqual((clause["kind"], clause["source"]),
                         (self.PREDICTED, "llm_then_rule"))
        self.assertEqual(report["rule_upgrades"], 8)
        self.assertEqual(report["rule_conflicts"], [])
        self.assertEqual(report["source_counts"]["llm_then_rule"], 8)

    def test_disagreeing_llm_row_is_left_alone_and_listed(self):
        entries, report = self.build(8, self.judged(8, "永續效果", "llm"))
        clause = clauses_of(entries, 1000)[0]
        self.assertEqual((clause["kind"], clause["source"]),
                         ("永續效果", "llm"))
        self.assertEqual(clause["rule_predicted"], self.PREDICTED)
        self.assertEqual(report["rule_upgrades"], 0)
        self.assertEqual(
            [(r["id"], r["rules"], r["existing"], r["predicted"])
             for r in report["rule_conflicts"][:1]],
            [(1000, ["R1"], "永續效果", self.PREDICTED)])
        self.assertEqual(len(report["rule_conflicts"]), 8)

    def test_below_threshold_rule_leaves_the_llm_row_untouched(self):
        entries, report = self.build(7, self.judged(7, self.PREDICTED, "llm"))
        clause = clauses_of(entries, 1000)[0]
        self.assertEqual(clause["source"], "llm")
        self.assertIsNone(clause["rule_predicted"])
        self.assertEqual(report["rule_upgrades"], 0)

    def test_manual_row_agreeing_with_the_shadow_keeps_its_provenance(self):
        """`manual` 是使用者看過這一行的證據,不因規則附和而洗掉。"""
        entries, report = self.build(8,
                                     self.judged(8, self.PREDICTED, "manual"))
        self.assertEqual(clauses_of(entries, 1000)[0]["source"], "manual")
        self.assertEqual(report["rule_upgrades"], 0)
        self.assertEqual(report["rule_conflicts"], [])

    def test_disagreeing_manual_row_is_listed_without_being_touched(self):
        entries, report = self.build(8, self.judged(8, "永續效果", "manual"))
        clause = clauses_of(entries, 1000)[0]
        self.assertEqual((clause["kind"], clause["source"]),
                         ("永續效果", "manual"))
        self.assertEqual([r["source"] for r in report["rule_conflicts"][:1]],
                         ["manual"])

    def test_double_confirmation_survives_the_next_rerun(self):
        upgraded, _ = self.build(8, self.judged(8, self.PREDICTED, "llm"))
        entries, report = self.build(8, upgraded)
        self.assertEqual(clauses_of(entries, 1000)[0]["source"],
                         "llm_then_rule")
        self.assertEqual(report["rule_upgrades"], 0)
        self.assertEqual(report["preserved_judgments"], 8)

    def test_official_agreement_counts_as_validation_not_an_upgrade(self):
        entries, report = self.build(
            8, supplement="■モンスターゾーンで発動する誘発効果です。")
        clause = clauses_of(entries, 1000)[0]
        self.assertEqual((clause["kind"], clause["source"]),
                         (self.PREDICTED, "official"))
        row = self.rule_row(report, "R1")
        self.assertEqual((row["attested"], row["agree"], row["disagree"]),
                         (8, 8, 0))
        self.assertEqual(report["rule_upgrades"], 0)

    def test_official_disagreement_is_validation_not_a_conflict(self):
        """官方明示是規則層的驗證集,不是被規則檢查的對象——另立一份清單。"""
        _, report = self.build(8, supplement="■永続効果です。")
        row = self.rule_row(report, "R1")
        self.assertEqual((row["attested"], row["agree"], row["disagree"]),
                         (8, 0, 8))
        self.assertEqual(report["rule_conflicts"], [])
        self.assertEqual(
            [(r["id"], r["official"], r["predicted"])
             for r in report["rule_official_disagree"][:1]],
            [(1000, "永續效果", self.PREDICTED)])

    def test_first_build_lists_every_prediction_as_a_change(self):
        _, report = self.build(8)
        self.assertEqual(
            [(r["id"], r["before"], r["after"])
             for r in report["rule_prediction_changed"][:1]],
            [(1000, None, self.PREDICTED)])
        self.assertEqual(len(report["rule_prediction_changed"]), 8)

    def test_rerun_without_a_rule_change_lists_no_difference(self):
        first, _ = self.build(8)
        _, report = self.build(8, first)
        self.assertEqual(report["rule_prediction_changed"], [])

    def test_a_rule_change_shows_up_line_by_line(self):
        """既有標記表記的是上一版規則的預測,逐行差異就是這次改動的影響範圍。"""
        stale, _ = self.build(8)
        for cid in range(1000, 1008):
            mark(stale, cid, "①", rule_predicted="啟動效果")
        _, report = self.build(8, stale)
        self.assertEqual(
            [(r["before"], r["after"])
             for r in report["rule_prediction_changed"]],
            [("啟動效果", self.PREDICTED)] * 8)

    def test_overlapping_rules_with_different_kinds_predict_nothing(self):
        """判別條件重疊且結論不同時規則層自相矛盾,不猜哪一條對。"""
        zh = "①：此卡被送去墓地的場合,可以在自己主要階段發動。"
        ja = "①：このカードが墓地へ送られた場合に、自分メインフェイズに発動できる。"
        cards = [card(1000 + i, desc=zh) for i in range(8)]
        faqs = [faq(1000 + i, card_text=ja) for i in range(8)]
        entries, report = build_tag_cards(cards, faqs)
        self.assertIsNone(clauses_of(entries, 1000)[0]["rule_predicted"])
        self.assertEqual(report["rule_predictions"], 0)
        self.assertEqual(
            [(r["id"], r["rules"], r["kinds"])
             for r in report["rule_overlaps"][:1]],
            [(1000, ["R1", "R4"], ["啟動效果", self.PREDICTED])])


class TestRuleLayerScope(unittest.TestCase):
    """規則層只管效果句;前言段的類型由位置規則決定,不歸規則層。"""

    ZH = "此卡不能通常召喚。\n①：此卡不受魔法效果影響。"
    JA = ("このカードはモンスターゾーンに存在する限り通常召喚できない。"
          "①：このカードがモンスターゾーンに存在する限り、魔法の効果を受けない。")

    def build(self):
        cards = [card(1000 + i, desc=self.ZH) for i in range(8)]
        faqs = [faq(1000 + i, card_text=self.JA) for i in range(8)]
        return build_tag_cards(cards, faqs)

    def test_preamble_gets_no_shadow_prediction(self):
        entries, _ = self.build()
        preamble, effect = clauses_of(entries, 1000)
        self.assertEqual((preamble["index"], preamble["kind"]),
                         ("0", "效果外文本"))
        self.assertIsNone(preamble["rule_predicted"])
        self.assertEqual(effect["rule_predicted"], "永續效果")

    def test_preamble_does_not_count_toward_coverage(self):
        """前言段的日文也命中 R7,若算進覆蓋條數就會是 16。"""
        _, report = self.build()
        coverage = {row["id"]: row["coverage"] for row in report["rules"]}
        self.assertEqual((coverage["R7"], coverage["R8"]), (8, 8))
        self.assertEqual(report["rule_predictions"], 8)


class TestRuleRegistry(unittest.TestCase):
    """規則清單本身:登記的欄位、合併語意、變更紀律。"""

    def test_shipped_registry_is_well_formed(self):
        self.assertEqual(rules.problems(), [])
        _, report = build_tag_cards([card(desc="①：效果甲。")],
                                    [faq(card_text="①：効果甲。")])
        self.assertEqual(report["rules_problems"], [])

    def test_every_registered_rule_reaches_the_report_with_its_metadata(self):
        _, report = build_tag_cards([card(desc="①：效果甲。")],
                                    [faq(card_text="①：効果甲。")])
        rows = {row["id"]: row for row in report["rules"]}
        self.assertEqual(sorted(rows), sorted(r["id"] for r in rules.RULES))
        for rule in rules.RULES:
            row = rows[rule["id"]]
            self.assertEqual(row["kind"], rule["kind"])
            self.assertEqual(row["condition"], rule["condition"])
            self.assertEqual(row["ticket"], rule["ticket"])

    def test_a_broken_registry_shuts_the_whole_layer_down(self):
        """規則清單自己都對不起來時不上工——寧可沒有影子預測。"""
        broken = (rules.define("R1", "不存在的類型", rules.SCOPE_CLAUSE,
                               "條件", r"効果甲", "票06"),)
        self.assertEqual(len(rules.problems(broken)), 1)

    def test_change_without_a_ticket_or_a_listed_reason_is_a_problem(self):
        no_ticket = rules.define(
            "R1", "永續效果", rules.SCOPE_CLAUSE, "條件", r"甲", "票06",
            changes=({"reason": rules.CHANGE_TOO_BROAD, "ticket": "",
                      "note": "說明"},))
        bad_reason = rules.define(
            "R1", "永續效果", rules.SCOPE_CLAUSE, "條件", r"甲", "票06",
            changes=({"reason": "手滑", "ticket": "票09", "note": "說明"},))
        self.assertEqual(len(rules.problems((no_ticket,))), 1)
        self.assertEqual(len(rules.problems((bad_reason,))), 1)

    def test_merged_rule_keeps_its_row_and_leaves_the_layer(self):
        """R12 + R15 → R31:舊條標記合併去向而不刪行。"""
        merge = {"reason": rules.CHANGE_MERGE, "ticket": "票09",
                 "note": "與 R15 判別條件幾乎相同"}
        registry = (
            rules.define("R12", "永續效果", rules.SCOPE_CLAUSE, "甲", r"甲",
                         "票06", changes=(merge,), merged_into="R31"),
            rules.define("R15", "永續效果", rules.SCOPE_CLAUSE, "乙", r"乙",
                         "票06", changes=(merge,), merged_into="R31"),
            rules.define("R31", "永續效果", rules.SCOPE_CLAUSE, "甲或乙",
                         r"甲|乙", "票09"),
        )
        self.assertEqual(rules.problems(registry), [])
        self.assertEqual([r["id"] for r in rules.active(registry)], ["R31"])
        self.assertEqual(rules.merged_groups(registry), {"R31": ["R12", "R15"]})

    def test_merge_without_a_merge_change_or_a_target_is_a_problem(self):
        undocumented = rules.define("R12", "永續效果", rules.SCOPE_CLAUSE, "甲",
                                    r"甲", "票06", merged_into="R31")
        self.assertEqual(len(rules.problems((undocumented,))), 2)

    def test_digest_tracks_definitions_only(self):
        """收斂條件的第一問靠指紋回答:規則清單本輪是否有異動。"""
        base = (rules.define("R1", "永續效果", rules.SCOPE_CLAUSE, "甲", r"甲",
                             "票06"),)
        same = (rules.define("R1", "永續效果", rules.SCOPE_CLAUSE, "甲", r"甲",
                             "票06"),)
        widened = (rules.define("R1", "永續效果", rules.SCOPE_CLAUSE, "甲",
                                r"甲|乙", "票06"),)
        self.assertEqual(rules.digest(base), rules.digest(same))
        self.assertNotEqual(rules.digest(base), rules.digest(widened))


# ---------------------------------------------------------------- 拆句表

# 舊式無編號卡文:前半是召喚條件(效果外文本),後半才是效果句
OLD_ZH_HEAD = "此卡不能通常召喚。將我方場上1隻怪獸解放才能特殊召喚。"
OLD_ZH_TAIL = "1回合1次，可以破壞對手場上1張卡。"
OLD_JA_HEAD = ("このカードは通常召喚できない。"
               "自分フィールドのモンスター１体をリリースした場合に特殊召喚できる。")
OLD_JA_TAIL = "１ターンに１度、相手フィールドのカード１枚を破壊できる。"
OLD_ZH = OLD_ZH_HEAD + OLD_ZH_TAIL
OLD_JA = OLD_JA_HEAD + OLD_JA_TAIL


def segment(index, text_zh, text_ja):
    return {"index": index, "text_zh": text_zh, "text_ja": text_ja}


def split(segments, cid=1000, section="main", text_zh=OLD_ZH, text_ja=OLD_JA,
          ticket="票13", text_hash=None, ja_order=None):
    """拆句表的一筆。雜湊由拆句當時的卡文算出來,與骨架用的是同一支函式。"""
    record = {"id": cid, "section": section, "ticket": ticket,
              "text_hash": text_hash or split_hash(text_zh, text_ja),
              "segments": segments}
    if ja_order is not None:
        record["ja_order"] = ja_order
    return record


def two_segments():
    return [segment("0", OLD_ZH_HEAD, OLD_JA_HEAD),
            segment("1", OLD_ZH_TAIL, OLD_JA_TAIL)]


def old_card(desc=OLD_ZH, card_text=OLD_JA, supplement=None):
    return [card(desc=desc)], [faq(card_text=card_text, supplement=supplement)]


class TestClauseSplits(unittest.TestCase):
    """拆句表把舊式無編號的整團切開;拆點是來源檔,不由規則產生(ADR-0003)。"""

    def build(self, splits, supplement=None, desc=OLD_ZH, card_text=OLD_JA):
        cards, faqs = old_card(desc, card_text, supplement)
        return build_tag_cards(cards, faqs, splits=splits)

    def test_blob_is_cut_into_the_recorded_segments(self):
        entries, report = self.build([split(two_segments())])
        self.assertEqual(
            [(c["index"], c["text_zh"], c["text_ja"])
             for c in clauses_of(entries, 1000)],
            [("0", OLD_ZH_HEAD, OLD_JA_HEAD), ("1", OLD_ZH_TAIL, OLD_JA_TAIL)])
        self.assertEqual(report["split_records"], 1)
        self.assertEqual(report["split_clauses"], 1)
        self.assertEqual(report["pending_split"], [])

    def test_non_effect_segment_is_typed_by_the_position_rule(self):
        """拆出來的效果外文本段走的是前言段那條位置規則,不是判定。"""
        entries, report = self.build([split(two_segments())])
        preamble = clauses_of(entries, 1000)[0]
        self.assertEqual((preamble["kind"], preamble["role"],
                          preamble["source"]), ("效果外文本", "召喚條件", "rule"))
        self.assertEqual(report["preambles"], 1)
        self.assertEqual(report["role_counts"]["召喚條件"], 1)

    def test_effect_segment_is_still_left_for_judgment(self):
        entries, _ = self.build([split(two_segments())])
        clause = clauses_of(entries, 1000)[1]
        self.assertIsNone(clause["kind"])
        self.assertIsNone(clause["source"])

    def test_a_second_non_effect_segment_uses_a_suffixed_index(self):
        """59 張同時含召喚條件與使用次數限制,一個 "0" 不夠。"""
        zh = ("此卡不能通常召喚。", "這個卡名的效果1回合只能使用1次。",
              "1回合1次，可以破壞對手場上1張卡。")
        ja = ("このカードは通常召喚できない。",
              "このカード名の効果は１ターンに１度しか使用できない。",
              "１ターンに１度、相手フィールドのカード１枚を破壊できる。")
        record = split([segment("0", zh[0], ja[0]),
                        segment("0-2", zh[1], ja[1]),
                        segment("1", zh[2], ja[2])],
                       text_zh="".join(zh), text_ja="".join(ja))
        entries, report = self.build([record], desc="".join(zh),
                                     card_text="".join(ja))
        self.assertEqual([(c["index"], c["kind"], c["role"])
                          for c in clauses_of(entries, 1000)],
                         [("0", "效果外文本", "召喚條件"),
                          ("0-2", "效果外文本", "使用次數限制"),
                          ("1", None, None)])
        self.assertEqual(report["split_clauses"], 1)

    def test_segments_are_contiguous_substrings_of_the_card_text(self):
        """比對忽略空白,但切出來的一律是原文的連續子字串。"""
        entries, report = self.build(
            [split(two_segments(), text_zh=f"{OLD_ZH_HEAD}\n{OLD_ZH_TAIL}",
                   text_ja=f"{OLD_JA_HEAD}\n{OLD_JA_TAIL}")],
            desc=f"{OLD_ZH_HEAD}\n{OLD_ZH_TAIL}",
            card_text=f"{OLD_JA_HEAD}\n{OLD_JA_TAIL}")
        self.assertEqual([c["text_zh"] for c in clauses_of(entries, 1000)],
                         [OLD_ZH_HEAD, OLD_ZH_TAIL])
        self.assertEqual(report["substring_violations"], [])

    def test_a_record_for_a_numbered_card_is_reported_as_unused(self):
        entries, report = self.build([split(two_segments())],
                                     desc="①：效果甲。", card_text="①：効果甲。")
        self.assertEqual([c["index"] for c in clauses_of(entries, 1000)], ["①"])
        self.assertEqual(report["split_unused"],
                         [{"id": 1000, "section": "main"}])


class TestCrossOrderedSplits(unittest.TestCase):
    """繁中與日文把同一批句子排成不同順序的卡(票51)。

    `segments` 照**繁中**順序列(網站給人看的是繁中),`ja_order` 給出**日文**的
    閱讀順序,`index` 照**日文**的序號給(官方用①②③稱呼舊式卡文,`_seq_target`
    是拿 index 字串對位)。實例:一族の掟 296499 把日文的維持代價句搬到繁中最前面。
    """

    # 日文 ①宣言 → ②不能攻擊宣言 → ③維持代價;繁中把 ③ 搬到最前面
    JA = ("発動時に１種類の種族を宣言する。",
          "その種族のモンスターは攻撃宣言ができない。",
          "自分のスタンバイフェイズ毎にモンスター１体を生け贄に捧げなければ"
          "このカードを破壊する。")
    ZH = ("此卡的控制者在每次我方準備階段解放1隻怪獸，或不解放讓此卡破壞。",
          "宣言1個種族可以發動此卡。",
          "那個種族的怪獸不能攻擊宣言。")
    ZH_TEXT = "\n".join(ZH)
    JA_TEXT = "".join(JA)
    # 繁中順序:維持代價(日文第 3 句) → 宣言(第 1) → 攻擊宣言(第 2)
    SEGMENTS = [segment("0", ZH[0], JA[2]),
                segment("1", ZH[1], JA[0]),
                segment("2", ZH[2], JA[1])]
    JA_ORDER = [1, 2, 0]

    def build(self, record, supplement=None):
        cards, faqs = old_card(self.ZH_TEXT, self.JA_TEXT, supplement)
        return build_tag_cards(cards, faqs, splits=[record])

    def record(self, **kwargs):
        kwargs.setdefault("segments", self.SEGMENTS)
        kwargs.setdefault("ja_order", self.JA_ORDER)
        return split(text_zh=self.ZH_TEXT, text_ja=self.JA_TEXT,
                     ticket="票51", **kwargs)

    def test_each_side_is_covered_in_its_own_reading_order(self):
        entries, report = self.build(self.record())
        self.assertEqual(
            [(c["index"], c["text_zh"], c["text_ja"])
             for c in clauses_of(entries, 1000)],
            [("0", self.ZH[0], self.JA[2]),
             ("1", self.ZH[1], self.JA[0]),
             ("2", self.ZH[2], self.JA[1])])
        self.assertEqual(report["split_coverage_failed"], [])
        self.assertEqual(report["pending_split"], [])

    def test_the_official_sequence_reference_follows_the_japanese_index(self):
        """官方說『①』指的是日文的第一句,不是繁中列在最前面的那一段。"""
        entries, _ = self.build(
            self.record(),
            supplement="■『①』はフィールドで発動する誘発効果です。")
        by_index = {c["index"]: c for c in clauses_of(entries, 1000)}
        self.assertEqual(by_index["1"]["text_ja"], self.JA[0])
        self.assertEqual((by_index["1"]["kind"], by_index["1"]["source"]),
                         ("誘發效果(1速)", "official"))
        self.assertIsNone(by_index["2"]["kind"])

    def test_a_quote_cut_apart_by_the_reordered_split_is_still_caught(self):
        """驗證二只問「引用有沒有完整落在某一段裡」,與段落順序無關。"""
        quote = self.JA[0] + self.JA[1]
        _, report = self.build(self.record(), supplement=f"■『{quote}』効果です。")
        self.assertEqual([r["id"] for r in report["split_quote_violations"]],
                         [1000])
        self.assertEqual(len(report["pending_split"]), 1)

    def test_a_japanese_order_that_leaves_a_gap_fails_coverage(self):
        """日文那一側照樣要無遺漏覆蓋,排列對了不代表段落切對了。"""
        broken = [segment("0", self.ZH[0], self.JA[2]),
                  segment("1", self.ZH[1], self.JA[0]),
                  segment("2", self.ZH[2], "")]
        _, report = self.build(self.record(segments=broken))
        self.assertEqual([(r["id"], r["side"])
                          for r in report["split_coverage_failed"]],
                         [(1000, "ja")])

    def test_a_ja_order_that_is_not_a_permutation_is_malformed(self):
        # 結果檔是人寫的 JSON,型別也可能是壞的("1" 而不是 1);拒收不是拋例外
        for bad in ([0, 1], [0, 1, 1], [0, 1, 3], "abc", [0, "1", 2],
                    [0, 1, None], [0, 1, True]):
            with self.subTest(ja_order=bad):
                _, report = self.build(self.record(ja_order=bad))
                self.assertEqual([r["id"] for r in report["split_malformed"]],
                                 [1000])

    def test_without_ja_order_the_two_sides_stay_positionally_paired(self):
        """既有 395 筆都沒有這個欄位,行為必須一個字都不變。"""
        cards, faqs = old_card()
        entries, report = build_tag_cards(cards, faqs,
                                          splits=[split(two_segments())])
        self.assertEqual(
            [(c["text_zh"], c["text_ja"]) for c in clauses_of(entries, 1000)],
            [(OLD_ZH_HEAD, OLD_JA_HEAD), (OLD_ZH_TAIL, OLD_JA_TAIL)])
        self.assertEqual(report["split_coverage_failed"], [])

    def test_an_identity_ja_order_is_the_same_as_omitting_it(self):
        cards, faqs = old_card()
        entries, _ = build_tag_cards(
            cards, faqs, splits=[split(two_segments(), ja_order=[0, 1])])
        self.assertEqual(
            [(c["text_zh"], c["text_ja"]) for c in clauses_of(entries, 1000)],
            [(OLD_ZH_HEAD, OLD_JA_HEAD), (OLD_ZH_TAIL, OLD_JA_TAIL)])


class TestSplitPreservesTheFirstIndex(unittest.TestCase):
    """`"1"` 沿用整團現在的 index,重跑合併因此對得回去、不製造孤兒。"""

    def blob_judged_as(self, kind):
        entries, _ = build_tag_cards(*old_card())
        mark(entries, 1000, "1", kind=kind, source="llm")
        return entries

    def rerun(self, existing, segments):
        cards, faqs = old_card()
        return build_tag_cards(cards, faqs, existing=existing,
                               splits=[split(segments)])

    def test_a_one_segment_split_changes_nothing_about_the_row(self):
        existing = self.blob_judged_as("啟動效果")
        entries, report = self.rerun(existing, [segment("1", OLD_ZH, OLD_JA)])
        clause = clauses_of(entries, 1000)[0]
        self.assertEqual((clause["index"], clause["kind"], clause["source"]),
                         ("1", "啟動效果", "llm"))
        self.assertFalse(clause["needs_review"])
        self.assertEqual(report["orphaned_judgments"], [])

    def test_the_first_effect_segment_inherits_the_blob_judgment(self):
        existing = self.blob_judged_as("啟動效果")
        entries, report = self.rerun(existing, two_segments())
        clause = clauses_of(entries, 1000)[1]
        self.assertEqual((clause["index"], clause["kind"], clause["source"]),
                         ("1", "啟動效果", "llm"))
        # 這一行的身分變了(整團 → 只剩後半),判定保留但要人回頭看
        self.assertTrue(clause["needs_review"])
        self.assertEqual(report["orphaned_judgments"], [])


class TestPendingSplitCarriesTheBlob(unittest.TestCase):
    """待拆清單帶著整團的兩側原文與雜湊——判定票看到的必須就是驗證會對的那一份。

    否則批次檔只能拿標記表上那一行的文字當拆句標的,而 ● 已經把它切掉一塊了
    (票13 實測 5 張):判定者照那一份拆,雜湊與覆蓋兩道驗證必然雙雙失敗。
    """

    def test_row_carries_both_sides_and_the_hash(self):
        _entries, report = build_tag_cards(*old_card())
        self.assertEqual(report["pending_split"], [{
            "id": 1000, "section": "main", "text_zh": OLD_ZH,
            "text_ja": OLD_JA, "text_hash": split_hash(OLD_ZH, OLD_JA)}])

    def test_a_blob_whose_bullets_were_carved_off_still_reports_the_whole_blob(
            self):
        desc = OLD_ZH + "可以發動1個以下效果。\n●選項甲。\n●選項乙。"
        card_text = OLD_JA + "以下の効果を１つ発動できる。●選択肢甲。●選択肢乙。"
        supplement = ("【１つ目の●について】\n"
                      "■モンスターゾーンで発動できる起動効果です。\n\n"
                      "【２つ目の●について】\n"
                      "■モンスターゾーンで適用する永続効果です。")
        _entries, report = build_tag_cards(
            [card(desc=desc)],
            [faq(card_text=card_text, supplement=supplement)])
        self.assertEqual(report["pending_split"], [{
            "id": 1000, "section": "main", "text_zh": desc,
            "text_ja": card_text, "text_hash": split_hash(desc, card_text)}])


class TestSplitValidation(unittest.TestCase):
    """三道驗證,任何一道失敗即整筆不寫入、退回整團(ADR-0003)。"""

    def build(self, record, supplement=None, desc=OLD_ZH, card_text=OLD_JA):
        cards, faqs = old_card(desc, card_text, supplement)
        return build_tag_cards(cards, faqs, splits=[record])

    def assert_fell_back_to_the_blob(self, entries, report):
        clauses = clauses_of(entries, 1000)
        self.assertEqual([c["index"] for c in clauses], ["1"])
        self.assertEqual(clauses[0]["text_zh"], OLD_ZH)
        self.assertEqual(report["split_records"], 0)
        self.assertEqual([(row["id"], row["section"])
                          for row in report["pending_split"]], [(1000, "main")])

    def test_a_dropped_sentence_fails_the_coverage_check(self):
        """「連續子字串」擋得住竄改但擋不住漏掉,漏掉是判定者的沉默失效模式。"""
        entries, report = self.build(
            split([segment("1", OLD_ZH_TAIL, OLD_JA_TAIL)]))
        self.assert_fell_back_to_the_blob(entries, report)
        self.assertEqual([(r["id"], r["side"])
                          for r in report["split_coverage_failed"]],
                         [(1000, "zh")])

    def test_a_japanese_side_that_does_not_cover_also_fails(self):
        """兩側各驗一次——489 張兩側句數不一致,只驗一側等於沒驗。"""
        entries, report = self.build(
            split([segment("0", OLD_ZH_HEAD, OLD_JA_HEAD),
                   segment("1", OLD_ZH_TAIL, "")]))
        self.assert_fell_back_to_the_blob(entries, report)
        self.assertEqual([(r["id"], r["side"])
                          for r in report["split_coverage_failed"]],
                         [(1000, "ja")])

    def test_an_official_quote_cut_in_half_fails(self):
        """官方 『原文』 引用橫跨拆點就是拆錯,不需要標準答案就查得出來。"""
        entries, report = self.build(
            split(two_segments()),
            supplement="■『特殊召喚できる。１ターンに１度』について。")
        self.assert_fell_back_to_the_blob(entries, report)
        self.assertEqual([(r["id"], r["quotes"])
                          for r in report["split_quote_violations"]],
                         [(1000, ["特殊召喚できる。１ターンに１度"])])

    def test_a_quote_inside_one_segment_is_not_a_violation(self):
        entries, report = self.build(
            split(two_segments()),
            supplement="■『相手フィールドのカード１枚を破壊できる』について。")
        self.assertEqual([c["index"] for c in clauses_of(entries, 1000)],
                         ["0", "1"])
        self.assertEqual(report["split_quote_violations"], [])

    def test_a_quote_belonging_to_another_card_is_not_a_violation(self):
        entries, report = self.build(
            split(two_segments()),
            supplement="■『別のカードの効果テキスト』について。")
        self.assertEqual(report["split_quote_violations"], [])

    def test_errata_invalidates_the_whole_record(self):
        """卡文變動即失效:退回整團,不保留舊拆點(票11 的錯誤不再犯)。"""
        errata_zh = OLD_ZH.replace("1張卡", "2張卡")
        errata_ja = OLD_JA.replace("１枚を破壊", "２枚を破壊")
        entries, report = self.build(split(two_segments()), desc=errata_zh,
                                     card_text=errata_ja)
        clauses = clauses_of(entries, 1000)
        self.assertEqual([c["index"] for c in clauses], ["1"])
        self.assertEqual(clauses[0]["text_zh"], errata_zh)
        self.assertEqual(report["split_stale"],
                         [{"id": 1000, "section": "main"}])
        self.assertEqual(report["split_coverage_failed"], [])

    def test_a_hash_that_does_not_match_is_stale_even_if_the_text_covers(self):
        entries, report = self.build(
            split(two_segments(), text_hash="0000000000000000"))
        self.assert_fell_back_to_the_blob(entries, report)
        self.assertEqual(report["split_stale"],
                         [{"id": 1000, "section": "main"}])

    def test_a_duplicate_or_unknown_index_is_malformed(self):
        for segments in ([segment("1", OLD_ZH_HEAD, OLD_JA_HEAD),
                          segment("1", OLD_ZH_TAIL, OLD_JA_TAIL)],
                         [segment("①", OLD_ZH_HEAD, OLD_JA_HEAD),
                          segment("2", OLD_ZH_TAIL, OLD_JA_TAIL)],
                         []):
            with self.subTest(segments=segments):
                entries, report = self.build(split(segments))
                self.assert_fell_back_to_the_blob(entries, report)
                self.assertEqual(report["split_malformed"],
                                 [{"id": 1000, "section": "main"}])

    def test_a_record_without_a_hash_is_malformed(self):
        record = split(two_segments())
        del record["text_hash"]
        entries, report = self.build(record)
        self.assert_fell_back_to_the_blob(entries, report)
        self.assertEqual(report["split_malformed"],
                         [{"id": 1000, "section": "main"}])


class TestSplitEnablesAttestation(unittest.TestCase):
    """有拆句表紀錄本身就是「這張卡有幾個效果句」的斷言,歸屬階梯據此開火。"""

    def build(self, supplement, segments=None):
        cards, faqs = old_card(supplement=supplement)
        return build_tag_cards(cards, faqs,
                               splits=[split(segments or two_segments())])

    def test_the_sole_effect_segment_lets_the_single_clause_ladder_fire(self):
        entries, report = self.build("■モンスターゾーンで適用する永続効果です。")
        clause = clauses_of(entries, 1000)[1]
        self.assertEqual((clause["kind"], clause["source"]),
                         ("永續效果", "official"))
        self.assertEqual(report["official_coverage"]["single"], 1)
        self.assertEqual(report["attribution_deferred"], [])
        self.assertEqual(report["split_new_official"], 1)

    def test_a_non_effect_segment_does_not_count_as_a_second_effect(self):
        _, report = self.build("■「テストカード」の効果は起動効果です。")
        self.assertEqual(report["official_coverage"]["name_single"], 1)

    def test_a_quote_reaches_the_segment_it_names(self):
        entries, report = self.build(
            f"■『{OLD_JA_TAIL}』の効果は起動効果です。")
        self.assertEqual(clauses_of(entries, 1000)[1]["kind"], "啟動效果")
        self.assertEqual(report["official_coverage"]["quote"], 1)

    def test_a_sequence_reference_maps_onto_the_split_segments(self):
        """官方對舊式卡仍以①②稱呼,拆出來的 "1" / "2" 就是它指的那幾段。"""
        entries, report = self.build(
            "■『②』の効果は起動効果です。",
            segments=[segment("1", OLD_ZH_HEAD, OLD_JA_HEAD),
                      segment("2", OLD_ZH_TAIL, OLD_JA_TAIL)])
        clauses = clauses_of(entries, 1000)
        self.assertIsNone(clauses[0]["kind"])
        self.assertEqual(clauses[1]["kind"], "啟動效果")
        self.assertEqual(report["official_coverage"]["seq"], 1)
        self.assertEqual(report["seq_missing"], [])

    def test_the_optional_rule_runs_on_the_segments_too(self):
        """未拆整團的第一句常是召喚條件而不是發動子句,拆完才輪得到規則。"""
        entries, _ = self.build("■『②』の効果は誘発即時効果です。",
                                segments=[segment("1", OLD_ZH_HEAD, OLD_JA_HEAD),
                                          segment("2", OLD_ZH_TAIL, OLD_JA_TAIL)])
        self.assertEqual(clauses_of(entries, 1000)[1]["optional"], "選發")

    def test_an_unsplit_blob_is_still_excluded(self):
        cards, faqs = old_card(supplement="■モンスターゾーンで適用する永続効果です。")
        entries, report = build_tag_cards(cards, faqs)
        self.assertIsNone(clauses_of(entries, 1000)[0]["kind"])
        self.assertEqual(report["official_coverage"]["single"], 0)
        self.assertEqual(report["split_new_official"], 0)


# ---------------------------------------------------------------- 判定結果

class TestJudgmentMerge(unittest.TestCase):
    """判定結果決定效果句上的**值**(拆句表決定集合,ADR-0003)。"""

    def judge(self, clauses, cid=1000, section="main"):
        return [{"id": cid, "section": section, "clauses": clauses}]

    def build(self, rows, desc="①：效果甲。", card_text="①：効果甲。",
              supplement="■なにかの説明。", existing=None):
        return build_tag_cards(
            [card(desc=desc)],
            [faq(card_text=card_text, supplement=supplement)],
            existing=existing, judgments=self.judge(rows))

    def test_judgment_fills_kind_optional_and_role(self):
        entries, report = self.build(
            [{"index": "①", "kind": "誘發效果(1速)", "optional": "必發"}])
        clause = clauses_of(entries, 1000)[0]
        self.assertEqual((clause["kind"], clause["optional"], clause["source"]),
                         ("誘發效果(1速)", "必發", "llm"))
        self.assertEqual(report["judgment_clauses"], 1)
        self.assertEqual(report["source_counts"]["llm"], 1)

    def test_confidence_follows_the_supplement_not_the_judgment(self):
        for supplement, expected in (("■なにかの説明。", "high"), (None, "low")):
            with self.subTest(expected=expected):
                entries, _ = self.build([{"index": "①", "kind": "啟動效果"}],
                                        supplement=supplement)
                self.assertEqual(clauses_of(entries, 1000)[0]["confidence"],
                                 expected)

    def test_official_agreement_keeps_the_official_provenance(self):
        """官方權威高於判定,一致時不降級——這一行也不占 ADR-0002 的判定額度。"""
        entries, report = self.build(
            [{"index": "①", "kind": "永續效果"}],
            supplement="■モンスターゾーンで適用する永続効果です。")
        clause = clauses_of(entries, 1000)[0]
        self.assertEqual((clause["kind"], clause["source"]),
                         ("永續效果", "official"))
        self.assertEqual(report["judgment_confirmed_by_official"], 1)
        self.assertEqual(report["late_official_conflicts"], [])

    def test_official_disagreement_keeps_the_judgment_and_flags_the_card(self):
        """不一致的最可能成因是拆錯而不是判錯,只標一行會讓人去看錯的東西。"""
        entries, report = build_tag_cards(
            [card(desc="①：效果甲。\n②：效果乙。")],
            [faq(card_text="①：効果甲。\n②：効果乙。",
                 supplement="【①の効果について】\n■永続効果です。")],
            judgments=self.judge([{"index": "①", "kind": "啟動效果"}]))
        clauses = clauses_of(entries, 1000)
        self.assertEqual((clauses[0]["kind"], clauses[0]["source"]),
                         ("啟動效果", "llm"))
        self.assertTrue(all(c["needs_review"] for c in clauses))
        self.assertEqual([(r["id"], r["index"], r["existing"], r["official"])
                          for r in report["late_official_conflicts"]],
                         [(1000, "①", "啟動效果", "永續效果")])

    def test_judgment_optional_beats_the_rule(self):
        """必發/選發四層:官方明示 → 判定 → 日文發動子句規則 → 留 null。"""
        entries, report = self.build(
            [{"index": "①", "kind": "誘發效果(1速)", "optional": "必發"}],
            card_text="①：このカードが墓地へ送られた場合に発動できる。"
                      "デッキから１枚ドローする。")
        self.assertEqual(clauses_of(entries, 1000)[0]["optional"], "必發")
        self.assertEqual(report["optional_llm"], 1)
        self.assertEqual(report["optional_rule"], 0)

    def test_official_taking_the_kind_still_leaves_the_judged_optional(self):
        """兩道階梯各走各的:官方接手[[效果類型]]不代表它也給了[[必發/選發]]。

        官方明示只寫類型、卡文又沒有發動子句時(舊式卡文的常態),兩道階梯綁在一起
        會把判定者填的必發/選發連帶丟掉——票18 實測 200 張裡 20 條。
        """
        entries, report = self.build(
            [{"index": "①", "kind": "誘發效果(1速)", "optional": "必發"}],
            card_text="①：このカードが墓地へ送られた時、デッキから１枚ドローする。",
            supplement="■墓地で発動する誘発効果です。")
        clause = clauses_of(entries, 1000)[0]
        self.assertEqual((clause["kind"], clause["source"]),
                         ("誘發效果(1速)", "official"))
        self.assertEqual(clause["optional"], "必發")
        self.assertEqual(report["judgment_confirmed_by_official"], 1)
        self.assertEqual(report["optional_llm"], 1)

    def test_optional_is_dropped_when_the_kind_cannot_carry_it(self):
        """值域規則優先:只有誘發即時與誘發兩類寫必發/選發。"""
        entries, report = self.build(
            [{"index": "①", "kind": "永續效果", "optional": "選發"}])
        self.assertIsNone(clauses_of(entries, 1000)[0]["optional"])
        self.assertEqual([(r["id"], r["index"], r["optional"])
                          for r in report["judgment_optional_dropped"]],
                         [(1000, "①", "選發")])
        self.assertEqual(report["optional_on_wrong_kind"], [])

    def test_a_row_matching_no_clause_is_reported(self):
        """集合一致性:結果檔多出一筆就是判定者跑錯批次,不能靜靜吞掉。"""
        _, report = self.build([{"index": "②", "kind": "啟動效果"}])
        self.assertEqual(report["judgment_orphans"],
                         [{"id": 1000, "section": "main", "index": "②"}])

    def test_a_row_left_blank_by_the_judge_is_reported_not_written(self):
        entries, report = self.build(
            [{"index": "①", "kind": None, "note": "判不出來"}])
        self.assertIsNone(clauses_of(entries, 1000)[0]["kind"])
        self.assertEqual([(r["id"], r["index"], r["note"])
                          for r in report["judgment_blank"]],
                         [(1000, "①", "判不出來")])

    def test_the_position_rule_is_not_overwritten_by_a_judgment(self):
        """前言段的效果外文本由位置規則決定,判定只在結論不同時進報告。"""
        entries, report = build_tag_cards(
            [card(desc="此卡不能通常召喚。\n①：效果甲。")],
            [faq(card_text="このカードは通常召喚できない。\n①：効果甲。")],
            judgments=self.judge([{"index": "0", "kind": "永續效果"}]))
        preamble = clauses_of(entries, 1000)[0]
        self.assertEqual((preamble["kind"], preamble["source"]),
                         ("效果外文本", "rule"))
        self.assertEqual([(r["id"], r["index"], r["judged"])
                          for r in report["judgment_vs_rule"]],
                         [(1000, "0", "永續效果")])

    def test_a_judged_row_survives_the_next_rerun(self):
        entries, _ = self.build([{"index": "①", "kind": "啟動效果"}])
        rebuilt, report = build_tag_cards(
            [card(desc="①：效果甲。")],
            [faq(card_text="①：効果甲。", supplement="■なにかの説明。")],
            existing=entries)
        clause = clauses_of(rebuilt, 1000)[0]
        self.assertEqual((clause["kind"], clause["source"]),
                         ("啟動效果", "llm"))
        self.assertEqual(report["preserved_judgments"], 1)

    def test_a_rejudgement_blocked_by_the_existing_row_is_reported(self):
        """判定一次就算數(ADR-0002),但擋掉這件事不能靜靜發生。"""
        entries, _ = self.build([{"index": "①", "kind": "啟動效果"}])
        _, report = self.build([{"index": "①", "kind": "永續效果"}],
                               existing=entries)
        self.assertEqual([(r["id"], r["index"], r["existing"], r["judged"])
                          for r in report["judgment_overridden"]],
                         [(1000, "①", "啟動效果", "永續效果")])

    def test_repeating_the_same_judgment_is_not_reported(self):
        entries, _ = self.build([{"index": "①", "kind": "啟動效果"}])
        _, report = self.build([{"index": "①", "kind": "啟動效果"}],
                               existing=entries)
        self.assertEqual(report["judgment_overridden"], [])

    def test_a_judgment_agreeing_with_the_shadow_becomes_a_double_check(self):
        """判定票的產出才是 ADR-0002 說的獨立對照,升級在同一次呼叫裡就成立。"""
        zh, ja = TestShadowPrediction.ZH, TestShadowPrediction.JA
        judgments = [{"id": 1000 + i, "section": "main",
                      "clauses": [{"index": "①",
                                   "kind": TestShadowPrediction.PREDICTED}]}
                     for i in range(8)]
        entries, report = build_tag_cards(
            [card(1000 + i, desc=zh) for i in range(8)],
            [faq(1000 + i, card_text=ja) for i in range(8)],
            judgments=judgments)
        self.assertEqual(clauses_of(entries, 1000)[0]["source"],
                         "llm_then_rule")
        self.assertEqual(report["rule_upgrades"], 8)


class TestJudgmentAfterSplit(unittest.TestCase):
    """拆句表與判定結果在同一次呼叫裡:先拆句,再抽官方明示,最後合併判定。"""

    def build(self, supplement=None, rows=(), segments=None):
        cards, faqs = old_card(supplement=supplement)
        return build_tag_cards(
            cards, faqs, splits=[split(segments or two_segments())],
            judgments=[{"id": 1000, "section": "main", "clauses": list(rows)}])

    def test_the_judgment_lands_on_the_segment_the_split_created(self):
        entries, report = self.build(rows=[{"index": "1", "kind": "啟動效果"}])
        clause = clauses_of(entries, 1000)[1]
        self.assertEqual((clause["index"], clause["kind"], clause["source"]),
                         ("1", "啟動效果", "llm"))
        self.assertEqual(report["judgment_orphans"], [])

    def test_a_split_that_failed_leaves_the_judgment_without_a_home(self):
        """拆句沒生效時判定的 index 對不到任何一行,必須是報告裡看得見的失敗。"""
        cards, faqs = old_card()
        _, report = build_tag_cards(
            cards, faqs,
            splits=[split([segment("1", OLD_ZH_TAIL, OLD_JA_TAIL)])],
            judgments=[{"id": 1000, "section": "main",
                        "clauses": [{"index": "2", "kind": "啟動效果"}]}])
        self.assertEqual(len(report["split_coverage_failed"]), 1)
        self.assertEqual(report["judgment_orphans"],
                         [{"id": 1000, "section": "main", "index": "2"}])

    def test_official_regained_by_the_split_outranks_the_judgment(self):
        entries, report = self.build(
            supplement="■モンスターゾーンで適用する永続効果です。",
            rows=[{"index": "1", "kind": "永續效果"}])
        self.assertEqual(clauses_of(entries, 1000)[1]["source"], "official")
        self.assertEqual(report["split_new_official"], 1)
        self.assertEqual(report["judgment_confirmed_by_official"], 1)


class TestCardTypeLabel(unittest.TestCase):
    """[[卡片種類]]的名稱。判定者要靠它走 §5.8——魔法・陷阱卡「這張卡本身的發動」
    的[[效果類型]]由卡片種類決定,而通常魔法與速攻魔法的卡文分不出來。"""

    def test_spell_subtypes_each_have_their_own_name(self):
        for ctype, expected in ((TYPE_SPELL, "通常魔法"),
                                (TYPE_QUICKPLAY_SPELL, "速攻魔法"),
                                (TYPE_CONTINUOUS_SPELL, "永續魔法"),
                                (TYPE_EQUIP_SPELL, "裝備魔法"),
                                (TYPE_FIELD_SPELL, "場地魔法"),
                                (TYPE_RITUAL_SPELL, "儀式魔法")):
            with self.subTest(expected=expected):
                self.assertEqual(card_type_label(ctype), expected)

    def test_trap_subtypes_each_have_their_own_name(self):
        for ctype, expected in ((TYPE_TRAP, "通常陷阱"),
                                (TYPE_CONTINUOUS_TRAP, "永續陷阱"),
                                (TYPE_COUNTER_TRAP, "反擊陷阱")):
            with self.subTest(expected=expected):
                self.assertEqual(card_type_label(ctype), expected)

    def test_monsters_are_just_monsters(self):
        """§5.8 只問「是不是魔法・陷阱卡」,怪獸的細分對判定沒有作用。"""
        self.assertEqual(card_type_label(TYPE_EFFECT_MONSTER), "怪獸")
        self.assertEqual(card_type_label(TYPE_PENDULUM_EFFECT), "怪獸")

    def test_unknown_bits_yield_no_label_rather_than_a_wrong_one(self):
        self.assertIsNone(card_type_label(0))


if __name__ == "__main__":
    unittest.main()
