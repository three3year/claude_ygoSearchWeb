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
            [card(desc="只要「海」在場上存在,此卡不受魔法效果影響。",
                  name_ja="深海の戦士")],
            [faq(card_text="「海」がフィールド上に存在する限り、"
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
            [card(desc="只要「海」在場上存在,此卡不受魔法效果影響。",
                  name_ja="深海の戦士")],
            [faq(card_text="「海」がフィールド上に存在する限り、"
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


class TestNegationAndForbiddenPhrases(unittest.TestCase):

    def test_izure_ni_mo_bunrui_sarenai_is_a_single_unclassified_kind(self):
        """否定句優先:列舉了四個類型詞也只判無種類效果。"""
        entries, _ = build_tag_cards(
            [card(desc="可以代替1隻融合素材怪獸。")],
            [faq(card_text="このカードを融合素材モンスター１体の代わりにする"
                           "事ができる。",
                 supplement="■起動効果・誘発効果・誘発即時効果・永続効果の"
                            "いずれにも分類されない効果です。")])
        clause = clauses_of(entries, 1000)[0]
        self.assertEqual(clause["kind"], "無種類效果")
        self.assertEqual(clause["source"], "official")

    def test_dore_ni_mo_variant_is_also_unclassified(self):
        """官方寫過「いずれにも」與「どれにも」兩種,都是無種類效果。"""
        entries, _ = build_tag_cards(
            [card(desc="可以代替1隻融合素材怪獸。")],
            [faq(card_text="このカードを融合素材モンスター１体の代わりにする"
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

    def test_attestation_pointing_outside_the_preamble_is_reported_only(self):
        entries, report = build_tag_cards(
            [card(desc="此卡不能通常召喚。\n①：效果甲。")],
            [faq(card_text="このカードは通常召喚できない。①：効果甲。",
                 supplement="■『①：効果甲。』は効果として扱いません。")])
        clauses = clauses_of(entries, 1000)
        self.assertEqual(clauses[0]["source"], "rule")
        self.assertIsNone(clauses[1]["kind"])
        self.assertEqual(
            [r["id"] for r in report["non_effect_outside_preamble"]], [1000])


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
        """「②：…は以下の効果を得る。●…」的領起句不是發動子句。"""
        clauses, report = self.optional_of(
            "①：このカードと相互リンクしているモンスターの数によって"
            "以下の効果を得る。\n●１体以上：攻撃宣言時に発動する。")
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
        """舊式無編號卡文還沒依語意拆開,第一句不保證是發動子句。"""
        entries, report = build_tag_cards(
            [card(desc="這張卡被送去墓地時可以發動。從卡組抽1張卡。")],
            [faq(card_text="このカードが墓地へ送られた場合に発動できる。"
                           "デッキから１枚ドローする。",
                 supplement="■モンスターゾーンで発動する誘発効果です。")])
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
                 supplement="■モンスターゾーンで発動する誘発効果です。"
                            "（必ず発動する効果です。）")])
        validation = report["optional_validation"]
        self.assertEqual(validation["attested"], 1)
        self.assertEqual(validation["predicted"], 0)
        self.assertEqual(validation["unsplit"], 1)


if __name__ == "__main__":
    unittest.main()
