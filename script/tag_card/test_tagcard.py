"""效果標記表管線測試(拆句骨架)。

接縫:tagcard.build_tag_cards(卡片總表條目, 補足情報條目) → (entries, report)。
fixture 於測試內程式化建立,不碰網路與真實資料檔。
"""
import unittest

from tagcard import build_tag_cards

TYPE_NORMAL_MONSTER = 0x11       # 怪獸 + 通常
TYPE_EFFECT_MONSTER = 0x21       # 怪獸 + 效果
TYPE_PENDULUM_EFFECT = 0x1000021  # 怪獸 + 效果 + 靈擺
TYPE_PENDULUM_NORMAL = 0x1000011  # 怪獸 + 通常 + 靈擺
TYPE_FUSION_MONSTER = 0x61       # 怪獸 + 效果 + 融合
TYPE_SPELL = 0x2


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
            "optional", "role", "source", "rule_predicted", "confidence",
            "tags"])
        self.assertIsNone(clause["kind"])
        self.assertIsNone(clause["optional"])
        self.assertIsNone(clause["role"])
        self.assertIsNone(clause["source"])
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
        self.assertEqual(report["pending_split"],
                         [{"id": 1000, "section": "main"}])


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

    def test_unsupported_inputs_are_reported_not_silently_ignored(self):
        _, report = build_tag_cards([card(desc="①：效果甲。")], [],
                                    existing=[], judgments=[])
        self.assertEqual(report["unsupported_inputs"],
                         ["existing", "judgments"])


if __name__ == "__main__":
    unittest.main()
