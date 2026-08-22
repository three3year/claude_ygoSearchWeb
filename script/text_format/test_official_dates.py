"""官方後備日期純函式測試:合成 HTML 與合成記錄,不讀真實資料、不連網。"""
import unittest

from official_dates import (build_cid_to_password, build_password_to_cid,
                            conflict_report_lines, earliest_release_date,
                            extract_release_dates, find_gap_targets,
                            merge_aligned_dates)


def _page(dates, heading="収録シリーズ", tail=""):
    """合成官方卡片頁:収録シリーズ區塊 + 之後的其他區塊(tail)。"""
    rows = "".join(
        f'<div class="t_row"><div class="inside">'
        f'<div class="time">\n\t\t{d}\n\t</div>'
        f'<div class="card_number">XXXX-JP000</div>'
        f"</div></div>" for d in dates)
    return (f'<html><body><div id="CardSet">卡片本體</div>'
            f'<div id="update_list" class="list">'
            f'<div class="t_haed"><div>{heading}</div></div>'
            f'<div class="t_body">{rows}</div></div>'
            f"{tail}</body></html>")


class ExtractReleaseDatesTest(unittest.TestCase):
    def test_extracts_dates_from_update_list(self):
        """収録シリーズ區塊內的発売日全數取出。"""
        html = _page(["2026-06-27", "2026-06-27"])
        self.assertEqual(extract_release_dates(html),
                         ["2026-06-27", "2026-06-27"])

    def test_ignores_dates_outside_update_list(self):
        """區塊之後其他區塊的日期不取:掃描面只有収録シリーズ。"""
        tail = ('<div id="mode_set"><div class="time">1999-01-01</div></div>')
        html = _page(["2026-06-27"], tail=tail)
        self.assertEqual(extract_release_dates(html), ["2026-06-27"])

    def test_english_page_raises(self):
        """非日文 locale(標題不是収録シリーズ)→ 報錯:英文頁給的是 TCG
        日期,絕不能當 OCG 首發日入檔。"""
        html = _page(["2025-07-04"], heading="Yu-Gi-Oh! TCG")
        with self.assertRaises(ValueError):
            extract_release_dates(html)

    def test_page_without_update_list_raises(self):
        """整頁沒有収録シリーズ區塊(錯誤頁/非卡片頁)→ 報錯。"""
        with self.assertRaises(ValueError):
            extract_release_dates("<html><body>error</body></html>")


class EarliestReleaseDateTest(unittest.TestCase):
    def test_picks_earliest_even_unordered(self):
        """多筆収録取最早一筆発売日,不依頁面順序。"""
        html = _page(["2020-04-18", "2014-03-21", "2016-01-09"])
        self.assertEqual(earliest_release_date(html), "2014-03-21")

    def test_empty_block_yields_none(self):
        """區塊存在但沒有任何発売日 → None:查無日期,不硬猜。"""
        self.assertIsNone(earliest_release_date(_page([])))


class MergeAlignedDatesTest(unittest.TestCase):
    def test_fallback_fills_missing(self):
        """YGOPRODeck 缺的卡由官方後備補上。"""
        merged, conflicts = merge_aligned_dates(
            {111: None, 222: "2015-06-20"}, {111: "2026-06-27"})
        self.assertEqual(merged, {111: "2026-06-27", 222: "2015-06-20"})
        self.assertEqual(conflicts, [])

    def test_primary_wins_when_equal(self):
        """兩邊一致 → 用 YGOPRODeck 值,不算不一致。"""
        merged, conflicts = merge_aligned_dates(
            {111: "2014-03-21"}, {111: "2014-03-21"})
        self.assertEqual(merged, {111: "2014-03-21"})
        self.assertEqual(conflicts, [])

    def test_conflict_reported_not_overwritten(self):
        """兩邊都有日期且不同 → 列入回報;顯示值以 YGOPRODeck 為主,
        但不一致必須浮出,不默默以任一邊蓋掉。"""
        merged, conflicts = merge_aligned_dates(
            {111: "2014-03-21"}, {111: "2026-06-27"})
        self.assertEqual(merged, {111: "2014-03-21"})
        self.assertEqual(conflicts, [(111, "2014-03-21", "2026-06-27")])

    def test_both_missing_stays_none(self):
        """兩邊都查無 → 維持 None,報表端歸「日期不明」。"""
        merged, conflicts = merge_aligned_dates({111: None}, {})
        self.assertEqual(merged, {111: None})
        self.assertEqual(conflicts, [])

    def test_conflicts_sorted_by_password(self):
        """不一致清單依卡片密碼排序,回報輸出穩定。"""
        _, conflicts = merge_aligned_dates(
            {222: "2000-01-01", 111: "2000-01-01"},
            {222: "2001-01-01", 111: "2001-01-01"})
        self.assertEqual([c[0] for c in conflicts], [111, 222])


class BuildPasswordToCidTest(unittest.TestCase):
    def test_maps_password_to_cid(self):
        """faq_info 條目的 password→cid;無密碼的條目略過。"""
        entries = [{"cid": 4007, "password": 89631139},
                   {"cid": 9999, "password": None}]
        self.assertEqual(build_password_to_cid(entries), {89631139: 4007})

    def test_overrides_take_priority(self):
        """人工查證的 cid 覆寫({cid: 密碼})優先於 faq_info 條目。"""
        entries = [{"cid": 4007, "password": 89631139}]
        mapping = build_password_to_cid(entries, overrides={5000: 89631139})
        self.assertEqual(mapping, {89631139: 5000})


class BuildCidToPasswordTest(unittest.TestCase):
    def test_reverse_of_password_mapping(self):
        """cid→密碼 的反向配對:同一個過濾(無密碼條目略過)。"""
        entries = [{"cid": 4007, "password": 89631139},
                   {"cid": 9999, "password": None}]
        self.assertEqual(build_cid_to_password(entries), {4007: 89631139})

    def test_overrides_take_priority(self):
        """人工查證的覆寫({cid: 密碼})蓋過 faq_info 條目。"""
        entries = [{"cid": 4007, "password": 89631139}]
        mapping = build_cid_to_password(entries, overrides={4007: 11111111})
        self.assertEqual(mapping, {4007: 11111111})


class ConflictReportLinesTest(unittest.TestCase):
    def test_no_conflicts_no_lines(self):
        """無不一致 → 空列表,呼叫端整段不印。"""
        self.assertEqual(conflict_report_lines([], [{"id": 1}]), [])

    def test_lists_each_conflict_with_both_values(self):
        """標題含張數,逐卡列出卡名與兩邊的值(不默默覆蓋)。"""
        lines = conflict_report_lines(
            [(111, "2014-03-21", "2026-06-27")],
            [{"id": 111, "name_zh": "左輪槍龍"}])
        self.assertIn("1 張", lines[0])
        self.assertIn("左輪槍龍", lines[1])
        self.assertIn("2014-03-21", lines[1])
        self.assertIn("2026-06-27", lines[1])

    def test_missing_name_defended(self):
        """卡片總表缺這張卡或缺卡名 → 顯示 ?,回報不炸。"""
        lines = conflict_report_lines([(111, "a", "b")], [])
        self.assertIn("?", lines[1])


class FindGapTargetsTest(unittest.TestCase):
    @staticmethod
    def _card(id_, alt_ids=()):
        return {"id": id_, "alt_ids": list(alt_ids)}

    def test_only_undated_cards_targeted(self):
        """有日期的卡不抓:只抓缺口,不做全庫抓取。"""
        targets, unresolved = find_gap_targets(
            [self._card(111), self._card(222)],
            {111: "2015-06-20", 222: None}, {111: 40, 222: 30})
        self.assertEqual([cid for cid, _ in targets], [30])
        self.assertEqual(unresolved, [])

    def test_resolves_cid_via_alt_password(self):
        """主卡密碼查不到 cid 時試異圖密碼(比照 refill 慣例)。"""
        card = self._card(111, alt_ids=[112])
        targets, unresolved = find_gap_targets([card], {111: None}, {112: 77})
        self.assertEqual(targets, [(77, card)])
        self.assertEqual(unresolved, [])

    def test_card_without_cid_unresolved(self):
        """無 cid 的缺口卡(TCG 限定)列入 unresolved,維持日期不明。"""
        card = self._card(111)
        targets, unresolved = find_gap_targets([card], {111: None}, {})
        self.assertEqual(targets, [])
        self.assertEqual(unresolved, [card])

    def test_targets_sorted_by_cid(self):
        """targets 依 cid 升冪,抓取順序穩定。"""
        targets, _ = find_gap_targets(
            [self._card(111), self._card(222)],
            {111: None, 222: None}, {111: 90, 222: 10})
        self.assertEqual([cid for cid, _ in targets], [10, 90])


if __name__ == "__main__":
    unittest.main()
