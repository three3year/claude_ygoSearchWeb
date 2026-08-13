"""值域正典自檢的測試(接縫 2)。

測的是**正典這份資料本身合不合法**,而不是管線的中間產物:重複短碼、缺中文、
分組有空洞、cdb 位元對應重疊。接縫 1 測不到這件事——`build_index` 吃的永遠是
repo 裡那一份,所以每一項都要拿一份**刻意寫壞的正典**驗,而不是只驗現行那一份
跑得過。
"""
import unittest

import vocab


def broken(name, **changes):
    """複製一份正典,把其中一個值域換成寫壞的版本。"""
    domains = dict(vocab.DOMAINS)
    domains[name] = dict(domains[name], **changes)
    return domains


class CanonTest(unittest.TestCase):
    def test_repo_canon_is_clean(self):
        """現行正典沒有問題(其餘測試才有意義)。"""
        self.assertEqual(vocab.problems(), [])

    def test_sizes_match_documented_domains(self):
        """成員數與 CONTEXT.md / spec 記的值域規模逐項對得上。"""
        for name, expected in vocab.EXPECTED_SIZES.items():
            self.assertEqual(len(vocab.codes(name)), expected, name)

    def test_duplicate_code_is_caught(self):
        dom = broken(vocab.RACE, entries=vocab.entries(vocab.RACE) + (
            vocab.entry("dragon", "亞龍族", 0x8000000),))
        self.assertIn("race: 短碼重複 'dragon'", vocab.problems(dom))

    def test_missing_chinese_is_caught(self):
        dom = broken(vocab.ATTR, entries=(
            vocab.entry("earth", "", 0x1),) + vocab.entries(vocab.ATTR)[1:])
        self.assertIn("attr: 成員 'earth' 缺中文", vocab.problems(dom))

    def test_duplicate_chinese_is_caught(self):
        """兩顆長一樣的按鈕:使用者分不出來,點哪一顆都不對。"""
        dom = broken(vocab.ATTR, entries=vocab.entries(vocab.ATTR) + (
            vocab.entry("earth2", "地", 0x80),))
        self.assertIn("attr: 中文重複 '地'", vocab.problems(dom))

    def test_bit_overlap_is_caught(self):
        """位元對應重疊:同一個位元對到兩個成員,解碼時兩個都中。"""
        dom = broken("sub_m", entries=vocab.entries("sub_m") + (
            vocab.entry("effect2", "效果二", 0x20),))
        problems = vocab.problems(dom)
        self.assertTrue(any("位元重疊" in p for p in problems), problems)

    def test_group_hole_is_caught(self):
        """成員沒排進任何分組 = 漏一顆按鈕,失效模式與漏一個碼一模一樣。"""
        groups = vocab.DOMAINS[vocab.KIND]["groups"]
        holed = ((groups[0][0], groups[0][1][:-1]), groups[1])
        problems = vocab.problems(broken(vocab.KIND, groups=holed))
        self.assertIn("kind: 成員 'i' 不在任何分組(宣告序有空洞)", problems)

    def test_group_listing_unknown_member_is_caught(self):
        groups = vocab.DOMAINS[vocab.KIND]["groups"]
        extra = ((groups[0][0], groups[0][1] + ("zz",)), groups[1])
        problems = vocab.problems(broken(vocab.KIND, groups=extra))
        self.assertIn("kind: 分組列了非可篩選成員 'zz'", problems)

    def test_size_change_is_caught(self):
        """值域少一個成員:那批卡從搜尋結果消失,而 EXPECTED_SIZES 會先叫。"""
        dom = broken(vocab.RACE, entries=vocab.entries(vocab.RACE)[:-1])
        self.assertIn("race: 成員數 25 與預期 26 不符", vocab.problems(dom))

    def test_missing_domain_is_caught(self):
        domains = {k: v for k, v in vocab.DOMAINS.items() if k != vocab.ROLE}
        self.assertIn("role: 值域不存在", vocab.problems(domains))

    def test_fallback_must_be_a_member(self):
        dom = broken("sub_s", fallback="nope")
        self.assertIn("sub_s: fallback 'nope' 不是成員", vocab.problems(dom))


class DecodeTest(unittest.TestCase):
    def test_category_and_subtypes(self):
        self.assertEqual(vocab.subtypes(0x21), ("m", ("effect",)))
        self.assertEqual(vocab.subtypes(0x2)[0], "s")
        self.assertEqual(vocab.subtypes(0x4)[0], "t")

    def test_multiple_bits_coexist(self):
        """靈擺通常怪獸同時帶 Normal 與 Pendulum,兩個碼都要出來。"""
        cat, subs = vocab.subtypes(0x1 | 0x10 | 0x1000000)
        self.assertEqual(cat, "m")
        self.assertEqual(subs, ("normal", "pendulum"))

    def test_spell_trap_normal_has_no_bit(self):
        """通常魔法/通常陷阱在 cdb 裡沒有位元,由 fallback 補。"""
        self.assertEqual(vocab.subtypes(0x2), ("s", ("normal",)))
        self.assertEqual(vocab.subtypes(0x4), ("t", ("normal",)))
        self.assertEqual(vocab.subtypes(0x4 | 0x100000), ("t", ("counter",)))

    def test_shared_bit_reads_from_the_right_side(self):
        """0x80 在怪獸側是儀式怪獸、在魔法側是儀式魔法:同位元不同值域。"""
        self.assertEqual(vocab.subtypes(0x1 | 0x80)[1], ("ritual",))
        self.assertEqual(vocab.subtypes(0x2 | 0x80)[1], ("ritual",))
        self.assertEqual(vocab.zh("sub_m", "ritual"), "儀式")
        self.assertEqual(vocab.zh("sub_s", "ritual"), "儀式")

    def test_undecodable_category(self):
        self.assertEqual(vocab.subtypes(0x40), (None, ()))

    def test_single_bit_domains(self):
        self.assertEqual(vocab.code_of(vocab.ATTR, 0x20), "dark")
        self.assertEqual(vocab.code_of(vocab.RACE, 0x2000), "dragon")
        # 0 是「沒有這個參數」(非怪獸),不是值域成員
        self.assertIsNone(vocab.code_of(vocab.ATTR, 0))
        # 對不到任何成員的值(屬性寫成 3)不猜,交給呼叫端當未知值報上去
        self.assertIsNone(vocab.code_of(vocab.ATTR, 3))

    def test_text_and_int_domains(self):
        self.assertEqual(vocab.code_of(vocab.KIND, "誘發即時效果(2速)"), "q")
        self.assertEqual(vocab.code_of(vocab.ROLE, "素材指定"), "mat")
        self.assertEqual(vocab.code_of(vocab.OT, 2), "t")
        self.assertIsNone(vocab.code_of(vocab.KIND, None))

    def test_link_markers(self):
        codes = vocab.bitmask_codes(vocab.LINK_MARKER, 0x1 | 0x40)
        self.assertEqual(codes, ("TL", "BL"))

    def test_unexplained_type_bits(self):
        """沒登記的位元要被指出來,不能靜靜被忽略。"""
        self.assertEqual(vocab.unexplained_type_bits(0x21), 0)
        self.assertEqual(vocab.unexplained_type_bits(0x21 | 0x100), 0x100)


class ExportTest(unittest.TestCase):
    def test_export_shape(self):
        exported = vocab.export()
        self.assertEqual([i["code"] for i in exported["cat"]["items"]],
                         ["m", "s", "t"])
        self.assertEqual(exported["cat"]["zh"], "大類")
        kinds = exported["kind"]
        self.assertEqual(len(kinds["items"]), 16)
        self.assertEqual([g["zh"] for g in kinds["groups"]],
                         ["怪獸側", "魔陷卡效果"])
        self.assertEqual(len(kinds["groups"][0]["codes"]), 6)
        self.assertEqual(len(kinds["groups"][1]["codes"]), 10)

    def test_export_order_is_declaration_order(self):
        """宣告序就是按鈕順序,也是領域序排序的比較序,兩者共用同一份。"""
        exported = vocab.export()
        for name, dom in exported.items():
            declared = [e["code"] for e in vocab.entries(name) if e["filter"]]
            self.assertEqual([i["code"] for i in dom["items"]], declared, name)

    def test_unfilterable_member_stays_out_of_buttons(self):
        """[[衍生物]]登記在正典裡(位元要解得動),但不做成永遠 0 筆的按鈕。"""
        self.assertIn("token", vocab.codes("sub_m"))
        codes = [i["code"] for i in vocab.export()["sub_m"]["items"]]
        self.assertNotIn("token", codes)

    def test_digest_changes_with_the_canon(self):
        before = vocab.digest()
        after = vocab.digest(broken(vocab.ATTR, entries=(
            vocab.entry("earth", "大地", 0x1),) + vocab.entries(vocab.ATTR)[1:]))
        self.assertNotEqual(before, after)
        self.assertEqual(before, vocab.digest())


if __name__ == "__main__":
    unittest.main()
