"""官方 Q&A 快取抽取管線測試。

接縫:faqinfo.extract_faq_info((cid, html) 序列[, cid→密碼對應]) → (entries, report)。
fixture HTML 於測試內合成(仿官方頁面結構),不碰網路與真實快取。
"""
import unittest

from faqinfo import extract_faq_info


def _section(section_id, title, text_id, text, supplement_id,
             supplement, supplement_date):
    parts = [f'<div id="{section_id}" class="qa_text_area">',
             f'<div id="{section_id}_title" class="title">{title}</div>',
             f'<div id="{text_id}" class="text">{text}</div>']
    if supplement is not None:
        parts.append('<div class="supplement">'
                     f'<div id="{section_id}_title" class="title">'
                     '<span>補足情報</span>'
                     f'<span class="update ">{supplement_date}</span></div>'
                     f'<div id="{supplement_id}" class="text">{supplement}</div>'
                     '</div>')
    parts.append('</div>')
    return "".join(parts)


def make_page(name_ja="テストカード", card_info=True, card_text="効果テキスト。",
              supplement=None, supplement_date="2024-01-01",
              pen_effect=None, pen_supplement=None,
              pen_supplement_date="2024-02-02"):
    """合成官方 Q&A 頁。supplement/pen_supplement=None 表示無該補足情報區塊,
    pen_effect=None 表示非靈擺卡(無 pen_info 區塊)。"""
    if name_ja:
        title = f"{name_ja} | カードに関連するＱ＆Ａ | 遊戯王ニューロン"
    else:
        title = "カードに関連するＱ＆Ａ | 遊戯王ニューロン"
    parts = [f"<!DOCTYPE html><html><head><title>{title}</title></head>",
             "<body><header><h1>site</h1></header>",
             '<div id="article_body">']
    if pen_effect is not None:
        parts.append(_section("pen_info", "ペンデュラム効果", "pen_effect",
                              pen_effect, "pen_supplement", pen_supplement,
                              pen_supplement_date))
    if card_info:
        parts.append(_section("card_info", "カードテキスト", "card_text",
                              card_text, "supplement", supplement,
                              supplement_date))
        parts[-1] += "<!--#card_info-->"
    parts.append('</div></body></html>')
    return "".join(parts)


class TestExtractGeneralCard(unittest.TestCase):

    def test_general_card_with_supplement(self):
        html = make_page(name_ja="ジェムナイト・セラフィ",
                         card_text="効果A。<br>効果B。",
                         supplement="■裁定1。<br>■裁定2。",
                         supplement_date="2024-11-23")
        entries, report = extract_faq_info([(10000, html)])
        self.assertEqual(len(entries), 1)
        e = entries[0]
        self.assertEqual(e["cid"], 10000)
        self.assertEqual(e["name_ja"], "ジェムナイト・セラフィ")
        self.assertEqual(e["card_text"], "効果A。\n効果B。")
        self.assertEqual(e["supplement"], "■裁定1。\n■裁定2。")
        self.assertEqual(e["supplement_date"], "2024-11-23")
        self.assertEqual(report["included"], 1)

    def test_card_without_supplement_included_without_field(self):
        html = make_page(supplement=None)
        entries, report = extract_faq_info([(123, html)])
        self.assertEqual(len(entries), 1)
        e = entries[0]
        self.assertNotIn("supplement", e)
        self.assertNotIn("supplement_date", e)
        self.assertEqual(e["card_text"], "効果テキスト。")
        self.assertEqual(report["no_supplement"], [123])

    def test_text_cleanup_strips_tags_and_decodes_entities(self):
        html = make_page(card_text="  A&amp;B<br><b>強調</b>C&#9312;  ",
                         supplement=None)
        entries, _ = extract_faq_info([(1, html)])
        self.assertEqual(entries[0]["card_text"], "A&B\n強調C①")

    def test_entries_sorted_by_cid(self):
        pages = [(20, make_page()), (10, make_page()), (15, make_page())]
        entries, _ = extract_faq_info(pages)
        self.assertEqual([e["cid"] for e in entries], [10, 15, 20])


class TestExtractPendulumCard(unittest.TestCase):

    def test_pendulum_card_both_sections_with_dates(self):
        html = make_page(pen_effect="P効果。", pen_supplement="■P裁定。",
                         pen_supplement_date="2016-12-23",
                         card_text="M効果。", supplement="■M裁定。",
                         supplement_date="2016-11-11")
        entries, report = extract_faq_info([(11134, html)])
        e = entries[0]
        self.assertEqual(e["pen_effect"], "P効果。")
        self.assertEqual(e["pen_supplement"], "■P裁定。")
        self.assertEqual(e["pen_supplement_date"], "2016-12-23")
        self.assertEqual(e["card_text"], "M効果。")
        self.assertEqual(e["supplement"], "■M裁定。")
        self.assertEqual(e["supplement_date"], "2016-11-11")
        self.assertEqual(report["pendulum"], 1)

    def test_pen_effect_without_pen_supplement(self):
        html = make_page(pen_effect="P効果。", pen_supplement=None,
                         supplement="■M裁定。")
        entries, _ = extract_faq_info([(2, html)])
        e = entries[0]
        self.assertEqual(e["pen_effect"], "P効果。")
        self.assertNotIn("pen_supplement", e)
        self.assertNotIn("pen_supplement_date", e)
        self.assertEqual(e["supplement"], "■M裁定。")

    def test_non_pendulum_card_has_no_pen_fields(self):
        html = make_page(supplement="■裁定。")
        entries, report = extract_faq_info([(3, html)])
        self.assertNotIn("pen_effect", entries[0])
        self.assertEqual(report["pendulum"], 0)


class TestPasswordJoin(unittest.TestCase):

    def test_password_joined_from_mapping(self):
        entries, report = extract_faq_info(
            [(10000, make_page())], cid_to_password={10000: 4064256})
        self.assertEqual(entries[0]["password"], 4064256)
        self.assertEqual(report["password_missing"], [])

    def test_unmapped_cid_gets_null_and_reported(self):
        entries, report = extract_faq_info(
            [(10000, make_page())], cid_to_password={99999: 1})
        self.assertIsNone(entries[0]["password"])
        self.assertEqual(report["password_missing"], [10000])

    def test_no_mapping_given_omits_password(self):
        entries, report = extract_faq_info([(10000, make_page())])
        self.assertNotIn("password", entries[0])
        self.assertNotIn("password_missing", report)


class TestOutsideSupplementAndAnomalies(unittest.TestCase):

    def test_supplement_word_outside_sections_reported(self):
        html = make_page(supplement="■裁定。").replace(
            "</body>", "<p>ここにも補足情報があります</p></body>")
        entries, report = extract_faq_info([(7, html)])
        self.assertEqual(len(entries), 1)  # 卡片本身照常收錄
        self.assertEqual(len(report["outside_supplement"]), 1)
        hit = report["outside_supplement"][0]
        self.assertEqual(hit["cid"], 7)
        self.assertIn("補足情報", hit["context"])

    def test_supplement_word_inside_sections_not_reported(self):
        html = make_page(supplement="■裁定。",
                         pen_effect="P効果。", pen_supplement="■P裁定。")
        _, report = extract_faq_info([(8, html)])
        self.assertEqual(report["outside_supplement"], [])

    def test_supplement_word_in_html_comment_outside_reported(self):
        html = make_page(supplement="■裁定。").replace(
            "</body>", "<!-- 補足情報はこちら --></body>")
        _, report = extract_faq_info([(9, html)])
        self.assertEqual(len(report["outside_supplement"]), 1)
        self.assertEqual(report["outside_supplement"][0]["cid"], 9)

    def test_page_without_card_info_excluded_and_reported(self):
        html = make_page(name_ja=None, card_info=False)
        entries, report = extract_faq_info([(19359, html)])
        self.assertEqual(entries, [])
        self.assertEqual(report["no_card_info"], [19359])
        self.assertEqual(report["included"], 0)
        self.assertEqual(report["no_supplement"], [])


if __name__ == "__main__":
    unittest.main()
