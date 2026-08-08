"""缺口盤點與 cid 對應表管理的測試。

接縫:faqgap 的純函式(不碰網路與檔案系統)。
- find_missing_cards(cards, faq_entries) → 待補清單
- build_cid_to_password(dump 序列) / diff_cid_mapping(old, new)
- extract_konami_ids(dump) → {卡片密碼: konami_id}
"""
import unittest

from faqgap import (apply_cid_overrides, build_cid_to_password,
                    diff_cid_mapping, extract_konami_ids, find_missing_cards,
                    format_gap_report, parse_cid_overrides,
                    split_alt_artwork_changes)


def card(id_, ot=1, alt_ids=(), name_zh="卡", name_ja="カード"):
    return {"id": id_, "ot": ot, "alt_ids": list(alt_ids),
            "name_zh": name_zh, "name_ja": name_ja, "setcode": 0}


def dump(*cards):
    """仿 ygoprodeck dump 檔結構。cards 為 (密碼, konami_id) 序列。"""
    return {"data": [
        {"id": pw, "misc_info": ([{"konami_id": kid}] if kid is not None
                                 else [{}])}
        for pw, kid in cards]}


class TestFindMissingCards(unittest.TestCase):

    def test_card_without_faq_entry_is_missing(self):
        cards = [card(111), card(222)]
        faq = [{"cid": 1, "password": 111}]
        missing = find_missing_cards(cards, faq)
        self.assertEqual([c["id"] for c in missing], [222])

    def test_tcg_only_cards_excluded(self):
        cards = [card(111, ot=2), card(222, ot=1)]
        missing = find_missing_cards(cards, [])
        self.assertEqual([c["id"] for c in missing], [222])

    def test_both_ot_cards_included_when_missing(self):
        # ot=3(OCG+TCG)有官方日文頁,屬待補
        missing = find_missing_cards([card(111, ot=3)], [])
        self.assertEqual([c["id"] for c in missing], [111])

    def test_alt_artwork_password_counts_as_covered(self):
        cards = [card(111, alt_ids=[999])]
        faq = [{"cid": 1, "password": 999}]
        self.assertEqual(find_missing_cards(cards, faq), [])

    def test_faq_entry_with_null_password_does_not_cover(self):
        cards = [card(111)]
        faq = [{"cid": 1, "password": None}]
        self.assertEqual([c["id"] for c in find_missing_cards(cards, faq)],
                         [111])

    def test_result_sorted_by_password(self):
        cards = [card(333), card(111), card(222)]
        missing = find_missing_cards(cards, [])
        self.assertEqual([c["id"] for c in missing], [111, 222, 333])

    def test_excluded_cards_reported_separately(self):
        cards = [card(111, ot=2), card(222)]
        missing, excluded = find_missing_cards(cards, [], with_excluded=True)
        self.assertEqual([c["id"] for c in missing], [222])
        self.assertEqual([c["id"] for c in excluded], [111])


class TestExtractKonamiIds(unittest.TestCase):

    def test_konami_id_extracted_by_password(self):
        self.assertEqual(extract_konami_ids(dump((111, 23382), (222, 23333))),
                         {111: 23382, 222: 23333})

    def test_card_without_konami_id_omitted(self):
        self.assertEqual(extract_konami_ids(dump((111, None))), {})

    def test_first_non_null_misc_info_wins(self):
        data = {"data": [{"id": 111,
                          "misc_info": [{}, {"konami_id": 42}]}]}
        self.assertEqual(extract_konami_ids(data), {111: 42})

    def test_missing_misc_info_tolerated(self):
        self.assertEqual(extract_konami_ids({"data": [{"id": 111}]}), {})


class TestBuildCidToPassword(unittest.TestCase):

    def test_mapping_built_from_multiple_dumps(self):
        mapping = build_cid_to_password([dump((111, 1)), dump((222, 2))])
        self.assertEqual(mapping, {1: 111, 2: 222})

    def test_earlier_dump_wins_on_conflict(self):
        # 沿用既有行為:先掃到的檔優先,新增檔不覆寫既有對應
        mapping = build_cid_to_password([dump((111, 7)), dump((222, 7))])
        self.assertEqual(mapping, {7: 111})


class TestDiffCidMapping(unittest.TestCase):

    def test_added_cids_listed(self):
        d = diff_cid_mapping({1: 111}, {1: 111, 2: 222})
        self.assertEqual(d["added"], [2])
        self.assertEqual(d["removed"], [])
        self.assertEqual(d["changed"], [])

    def test_removed_cids_listed(self):
        d = diff_cid_mapping({1: 111, 2: 222}, {1: 111})
        self.assertEqual(d["removed"], [2])

    def test_changed_password_listed_with_both_values(self):
        d = diff_cid_mapping({1: 111}, {1: 999})
        self.assertEqual(d["changed"], [(1, 111, 999)])

    def test_is_safe_only_when_nothing_lost_or_changed(self):
        self.assertTrue(diff_cid_mapping({1: 111}, {1: 111, 2: 2})["is_safe"])
        self.assertFalse(diff_cid_mapping({1: 111, 2: 2}, {1: 111})["is_safe"])
        self.assertFalse(diff_cid_mapping({1: 111}, {1: 999})["is_safe"])

    def test_lists_sorted(self):
        d = diff_cid_mapping({}, {3: 3, 1: 1, 2: 2})
        self.assertEqual(d["added"], [1, 2, 3])


class TestCidOverrides(unittest.TestCase):
    """ygoprodeck 查不到 konami_id 的卡,靠人工查證的 cid 對應補上。"""

    def test_parses_string_keys_to_ints(self):
        data = {"note": "說明", "cid_to_password": {"23363": 89813287}}
        self.assertEqual(parse_cid_overrides(data), {23363: 89813287})

    def test_missing_section_yields_empty(self):
        self.assertEqual(parse_cid_overrides({}), {})
        self.assertEqual(parse_cid_overrides(None), {})

    def test_override_adds_cid_absent_from_dumps(self):
        self.assertEqual(apply_cid_overrides({1: 111}, {2: 222}),
                         {1: 111, 2: 222})

    def test_override_wins_over_dump(self):
        # 人工查證優先於 dump——會用到覆寫,就表示 dump 的資料有問題
        self.assertEqual(apply_cid_overrides({1: 111}, {1: 999}), {1: 999})

    def test_original_mapping_not_mutated(self):
        mapping = {1: 111}
        apply_cid_overrides(mapping, {2: 222})
        self.assertEqual(mapping, {1: 111})


class TestSplitAltArtworkChanges(unittest.TestCase):
    """dump 排序不同會讓同一張卡的 cid 在主卡密碼與異圖密碼之間擺盪,
    那不是真的改指別張卡,不該擋下流程。"""

    CARDS = [card(111, alt_ids=[112, 113]), card(222)]

    def test_main_to_alt_password_is_benign(self):
        benign, real = split_alt_artwork_changes([(7, 111, 112)], self.CARDS)
        self.assertEqual(benign, [(7, 111, 112)])
        self.assertEqual(real, [])

    def test_alt_to_alt_password_is_benign(self):
        benign, real = split_alt_artwork_changes([(7, 112, 113)], self.CARDS)
        self.assertEqual(benign, [(7, 112, 113)])
        self.assertEqual(real, [])

    def test_different_card_is_real(self):
        benign, real = split_alt_artwork_changes([(7, 111, 222)], self.CARDS)
        self.assertEqual(benign, [])
        self.assertEqual(real, [(7, 111, 222)])

    def test_password_outside_card_list_is_real(self):
        # 保守:認不出來的一律當成真的改指,由人判讀
        benign, real = split_alt_artwork_changes([(7, 111, 999)], self.CARDS)
        self.assertEqual(real, [(7, 111, 999)])


class TestFormatGapReport(unittest.TestCase):

    def test_reports_counts_and_sample(self):
        missing = [card(111, name_ja="カードA"), card(222, name_ja="カードB")]
        lines = format_gap_report(missing, [card(333, ot=2)], sample=1)
        text = "\n".join(lines)
        self.assertIn("2", text)          # 待補張數
        self.assertIn("111", text)        # 抽樣列出的密碼
        self.assertIn("カードA", text)
        self.assertNotIn("222", text)     # sample=1 只列一筆
        self.assertIn("1", text)          # 排除張數

    def test_no_gap_reports_clean(self):
        lines = format_gap_report([], [], sample=5)
        self.assertTrue(any("無缺口" in ln for ln in lines))


if __name__ == "__main__":
    unittest.main()
