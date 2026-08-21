"""前端索引管線的測試(接縫 1)。

接縫:`webindex.build_index(卡片總表條目, 效果標記表條目) → (index, report)`。
fixture 於測試內程式化建立,不碰網路也不碰真實資料檔(先例:
`script/card_list/test_cardlist.py`)。

四道一致性檢查的測試重點是**該擋的擋得住**,不是「現行資料跑得過」:每一道都餵
一份壞掉的輸入進去,斷言 report 的 problems 非空。
"""
import unittest

import vocab
from webindex import build_index, serialize_index

MONSTER = 0x21          # 怪獸 + 效果
MONSTER_LINK = 0x4000021
MONSTER_PEND = 0x1000021
MONSTER_XYZ = 0x800021
MONSTER_FUSION = 0x40021
SPELL_QUICK = 0x10002   # 速攻魔法
SPELL_EQUIP = 0x40002   # 裝備魔法
SPELL_RITUAL = 0x82     # 儀式魔法
TRAP = 0x4              # 通常陷阱


def card(cid, **kw):
    """一筆卡片總表條目。預設是一張效果怪獸。

    非怪獸自動清空怪獸參數(比照 `cards.json` 的大類閘門,card-list 票07),
    測試明寫的值仍然優先——不變式那一條要故意違反閘門。

    守備寫成 `def_`:`def` 是保留字,當不了關鍵字參數。
    """
    if "def_" in kw:
        kw["def"] = kw.pop("def_")
    base = {"id": cid, "alt_ids": [], "name_zh": f"卡{cid}", "name_ja": "",
            "name_en": "", "desc": "", "type": MONSTER, "atk": 1000,
            "def": 1000, "level": 4, "race": 0x2000, "attribute": 0x20,
            "scale": 0, "link_marker": 0, "setcode": 0, "ot": 3,
            "md_rarity": "", "genesys_points": 0, "ban_ocg": "",
            "ban_tcg": "", "ban_md": ""}
    base.update(kw)
    if not base["type"] & 0x1:
        base.update({"atk": None, "def": None, "level": 0, "race": 0,
                     "attribute": 0})
        base.update(kw)
    return base


def clause(text, kind="啟動效果", index="①", section="main",
           optional=None, role=None):
    return {"index": index, "section": section, "text_zh": text,
            "text_ja": "", "text_hash": "", "kind": kind,
            "optional": optional, "role": role, "source": "llm",
            "needs_review": False, "rule_predicted": None,
            "confidence": "high", "tags": []}


def tagged(cid, *clauses):
    return {"id": cid, "clauses": list(clauses)}


class EntryTest(unittest.TestCase):
    def test_card_fields_and_key_order(self):
        cards = [card(63028558, name_zh="青眼白龍", name_ja="青眼の白龍",
                      name_en="Blue-Eyes White Dragon",
                      desc="①：這樣。②：那樣。")]
        tags = [tagged(63028558,
                       clause("①：這樣。", kind="啟動效果"),
                       clause("②：那樣。", kind="誘發效果(1速)", index="②"))]
        index, report = build_index(cards, tags)
        entry = index["cards"][0]
        self.assertEqual(list(entry), [
            "id", "n", "nj", "ne", "c", "s", "at", "r", "lv", "atk", "df",
            "ot", "tx", "k"])
        self.assertEqual(entry["id"], 63028558)
        self.assertEqual(entry["n"], "青眼白龍")
        self.assertEqual(entry["nj"], "青眼の白龍")
        self.assertEqual(entry["ne"], "Blue-Eyes White Dragon")
        self.assertEqual(entry["tx"], ["①：這樣。", "②：那樣。"])
        self.assertEqual(report["problems"], [])

    def test_values_are_short_codes_not_chinese(self):
        """效果類型與大類存短碼,中文由 VOCAB 對照(ADR-0008)。"""
        cards = [card(1, desc="①：這樣。"), card(2, type=TRAP, desc="這樣。")]
        tags = [tagged(1, clause("①：這樣。", kind="誘發即時效果(2速)")),
                tagged(2, clause("這樣。", kind="通常陷阱卡效果", index="1"))]
        index, _ = build_index(cards, tags)
        self.assertEqual(index["cards"][0]["c"], "m")
        self.assertEqual(index["cards"][0]["k"], ["q"])
        self.assertEqual(index["cards"][1]["c"], "t")
        self.assertEqual(index["cards"][1]["k"], ["tn"])

    def test_empty_values_are_omitted_not_null(self):
        cards = [card(1, desc="①：這樣。")]
        tags = [tagged(1, clause("①：這樣。"))]
        index, _ = build_index(cards, tags)
        entry = index["cards"][0]
        for key in ("nj", "ne", "d"):
            self.assertNotIn(key, entry)

    def test_card_without_clauses_gets_flavor_text(self):
        """689 張純通常怪獸:沒有效果句,故事文進 `d` 而不是空的 `tx`。"""
        cards = [card(1, type=0x11, desc="從無人的13號墳墓突然出現的殭屍。")]
        index, report = build_index(cards, [tagged(1)])
        entry = index["cards"][0]
        self.assertEqual(entry["d"], "從無人的13號墳墓突然出現的殭屍。")
        self.assertNotIn("tx", entry)
        self.assertNotIn("k", entry)
        self.assertEqual(report["problems"], [])

    def test_pendulum_flavor_is_extracted(self):
        """靈擺通常怪獸的【怪獸敘述】段是故事文,不是效果句。"""
        desc = "【靈擺效果】\n①：這樣。\n【怪獸敘述】\n一條龍的故事。"
        cards = [card(1, type=0x1 | 0x10 | 0x1000000, desc=desc, scale=4)]
        tags = [tagged(1, clause("①：這樣。", kind="靈擺魔法卡效果",
                                 section="pendulum"))]
        index, report = build_index(cards, tags)
        entry = index["cards"][0]
        self.assertEqual(entry["tx"], ["①：這樣。"])
        self.assertEqual(entry["d"], "一條龍的故事。")
        self.assertEqual(report["problems"], [])

    def test_index_is_sorted_by_password(self):
        cards = [card(30), card(10), card(20)]
        tags = [tagged(30), tagged(10), tagged(20)]
        index, _ = build_index(cards, tags)
        self.assertEqual([c["id"] for c in index["cards"]], [10, 20, 30])


class CardFaceTest(unittest.TestCase):
    """卡面欄位:呈現層要畫出一張卡需要的東西(票02)。"""

    def test_monster_params_are_short_codes(self):
        cards = [card(1, type=MONSTER_XYZ, race=0x2000, attribute=0x20,
                      level=8, atk=3000, def_=2500)]
        entry = build_index(cards, [tagged(1)])[0]["cards"][0]
        self.assertEqual(entry["s"], ["effect", "xyz"])
        self.assertEqual(entry["at"], "dark")
        self.assertEqual(entry["r"], "dragon")
        self.assertEqual(entry["lv"], 8)
        self.assertEqual(entry["atk"], 3000)
        self.assertEqual(entry["df"], 2500)

    def test_link_monster_has_lk_and_markers_but_no_level_or_def(self):
        """cdb 把連結值存在 `level`,而連結怪獸沒有守備欄——不是 `?`,是沒有。"""
        cards = [card(1, type=MONSTER_LINK, level=3, def_=None,
                      link_marker=0x8 | 0x20 | 0x2)]
        entry = build_index(cards, [tagged(1)])[0]["cards"][0]
        self.assertEqual(entry["lk"], 3)
        # 宣告序 = 九宮格讀法(左上到右下),呈現層直接照序擺格子
        self.assertEqual(entry["lm"], ["L", "R", "B"])
        self.assertNotIn("lv", entry)
        self.assertNotIn("df", entry)

    def test_pendulum_scale_zero_is_kept(self):
        """刻度 0 是真的刻度(28 張),省略它等於把它畫成沒有靈擺欄。"""
        cards = [card(1, type=MONSTER_PEND, scale=0),
                 card(2, type=MONSTER_PEND, scale=13),
                 card(3, type=MONSTER)]
        index, _ = build_index(cards, [tagged(1), tagged(2), tagged(3)])
        first, second, third = index["cards"]
        self.assertEqual(first["sc"], 0)
        self.assertEqual(second["sc"], 13)
        self.assertNotIn("sc", third)

    def test_unknown_atk_is_distinguishable_from_zero(self):
        """攻守 `?` 與 0 是不同的東西,範圍條件不得把 `?` 當 0(票05)。"""
        cards = [card(1, atk=-2, def_=-2), card(2, atk=0, def_=0)]
        index, _ = build_index(cards, [tagged(1), tagged(2)])
        unknown, zero = index["cards"]
        self.assertEqual((unknown["atk"], unknown["df"]), (-2, -2))
        self.assertEqual((zero["atk"], zero["df"]), (0, 0))

    def test_non_monster_has_no_monster_params(self):
        """罠モンスター那 79 張的清理在來源層;索引這一側連欄位都不該有。"""
        cards = [card(1, type=SPELL_QUICK), card(2, type=TRAP)]
        index, _ = build_index(cards, [tagged(1), tagged(2)])
        for entry in index["cards"]:
            for key in ("at", "r", "lv", "lk", "sc", "lm", "atk", "df"):
                self.assertNotIn(key, entry)
        self.assertEqual(index["cards"][0]["s"], ["quick"])
        self.assertEqual(index["cards"][1]["s"], ["normal"])

    def test_printing_fields(self):
        cards = [card(1, ot=1, md_rarity="UR", genesys_points=40),
                 card(2, ot=3, md_rarity="", genesys_points=0)]
        index, _ = build_index(cards, [tagged(1), tagged(2)])
        first, second = index["cards"]
        self.assertEqual((first["ot"], first["ra"], first["gy"]),
                         ("o", "UR", 40))
        self.assertEqual(second["ot"], "b")
        # MD 未實裝的 416 張與 0 點不是值域成員,是「沒有這個參數」
        self.assertNotIn("ra", second)
        self.assertNotIn("gy", second)

    def test_ban_field_only_on_listed_cards(self):
        """[[禁限狀態]]:上榜卡帶短碼,未上榜是「沒有這個欄位」而不是空值。"""
        cards = [card(1, ban_ocg="禁止", ban_tcg="限制", ban_md="準限制",
                      md_rarity="UR"),
                 card(2, ban_ocg="限制"),
                 card(3, ban_ocg="準限制"), card(4)]
        index, report = build_index(cards, [tagged(i) for i in (1, 2, 3, 4)])
        by_id = {c["id"]: c for c in index["cards"]}
        self.assertEqual(by_id[1]["bo"], "f")
        self.assertEqual(by_id[1]["bt"], "l")
        self.assertEqual(by_id[1]["bm"], "s")
        self.assertEqual(by_id[2]["bo"], "l")
        self.assertEqual(by_id[3]["bo"], "s")
        self.assertNotIn("bt", by_id[2])  # 賽制各自獨立:TCG 未上榜就沒有 bt
        self.assertNotIn("bm", by_id[2])
        for key in ("bo", "bt", "bm"):
            self.assertNotIn(key, by_id[4])
        self.assertEqual(report["problems"], [])

    def test_unknown_ban_value_fails_the_build(self):
        """索引出現禁限值域沒有的值即建置失敗(吵鬧失效)。"""
        cards = [card(1, ban_ocg="解禁")]
        _, report = build_index(cards, [tagged(1)])
        self.assertTrue(report["problems"])
        self.assertTrue(report["checks"]["unknown_values"])

    def test_alt_ids_become_al(self):
        cards = [card(46986414, alt_ids=[46986415, 46986430]), card(2)]
        index, _ = build_index(cards, [tagged(46986414), tagged(2)])
        with_alt = next(c for c in index["cards"] if c["id"] == 46986414)
        without = next(c for c in index["cards"] if c["id"] == 2)
        self.assertEqual(with_alt["al"], [46986415, 46986430])
        self.assertNotIn("al", without)

    def test_token_subtype_has_no_button_so_the_build_fails(self):
        """[[衍生物]]登記在正典裡但不做成按鈕:短碼進了索引就該倒。

        這是 ADR-0008 說的「換個地方發生的同一個失效模式」——值域登記了碼卻沒做
        成按鈕,那批卡在畫面上點不出來,與漏一個碼一樣是無聲消失。
        """
        cards = [card(1, type=MONSTER | 0x4000)]
        _, report = build_index(cards, [tagged(1)])
        self.assertEqual(report["checks"]["unknown_values"],
                         [{"id": 1, "field": "s", "code": "token",
                           "reason": "短碼不在按鈕清單"}])
        self.assertTrue(report["problems"])


class AliasTest(unittest.TestCase):
    """`※` 別名(117 張)是另一種中文譯名,不是卡文的一部分。

    抽出來進 `ax`,顯示在副標而不是卡文裡。容易寫成「顯示時再剝掉」——那樣
    卡名搜尋(票03 要比對別名)就得自己再剝一次,兩處剝法遲早不一致。
    """

    def test_alias_is_extracted_into_ax_and_not_left_in_the_text(self):
        cards = [card(1, desc="①：這樣。\n\n※另一個譯名")]
        tags = [tagged(1, clause("①：這樣。"))]
        index, report = build_index(cards, tags)
        entry = index["cards"][0]
        self.assertEqual(entry["ax"], "另一個譯名")
        self.assertEqual(entry["tx"], ["①：這樣。"])
        for text in entry["tx"]:
            self.assertNotIn("※", text)
        self.assertEqual(report["problems"], [])

    def test_alias_does_not_leak_into_the_flavor_text(self):
        """沒有效果句的卡:故事文進 `d`,別名仍然走 `ax`。"""
        cards = [card(1, type=0x11, desc="一隻傳說中的龍。\n\n※另一個譯名")]
        entry = build_index([cards[0]], [tagged(1)])[0]["cards"][0]
        self.assertEqual(entry["d"], "一隻傳說中的龍。")
        self.assertEqual(entry["ax"], "另一個譯名")

    def test_card_without_alias_has_no_ax(self):
        cards = [card(1, desc="①：這樣。")]
        entry = build_index(cards, [tagged(1, clause("①：這樣。"))])[0]["cards"][0]
        self.assertNotIn("ax", entry)

    def test_alias_mark_inside_a_clause_is_not_an_alias(self):
        """行內的 `※` 不是別名——別名是卡文末尾自成一行的那一段。"""
        cards = [card(1, desc="①：這樣※那樣。")]
        entry = build_index(cards, [tagged(1, clause("①：這樣※那樣。"))])[0]["cards"][0]
        self.assertNotIn("ax", entry)

    def test_alias_shaped_gap_that_is_not_extracted_fails_the_build(self):
        """缺口分類器認得、抽取器抽不到 → 那段文字三處都沒有,建置要倒。

        兩邊對「別名長什麼樣」的定義漂開時的形狀:覆蓋檢查看到 `※` 開頭就放行,
        而 `ax` 是空的,那一段就從畫面上無聲消失了。
        """
        cards = [card(1, desc="①：這樣。※沒有換行的一段")]
        _, report = build_index(cards, [tagged(1, clause("①：這樣。"))])
        self.assertEqual(report["checks"]["alias_gap_not_extracted"], [1])
        self.assertTrue(report["problems"])


class ClauseArrayTest(unittest.TestCase):
    """`tx` / `k` / `o` / `ro` / `pz` 的同索引對齊——呈現層照索引取值。"""

    def test_optional_codes_align_with_tx(self):
        """[[必發/選發]]逐句進 `o`,不承載的句子留空字串佔位。

        佔位而不是壓縮成「只記承載的那幾句」:`tx` / `k` / `o` / `ro` 是同索引
        的四個陣列,壓縮之後第 2 個 `o` 對到的是第幾句就得再記一份對照。
        """
        desc = "①：這樣。②：那樣。③：又一樣。"
        cards = [card(1, desc=desc)]
        tags = [tagged(1,
                       clause("①：這樣。", kind="誘發即時效果(2速)",
                              optional="必發"),
                       clause("②：那樣。", kind="誘發效果(1速)", index="②",
                              optional="選發"),
                       clause("③：又一樣。", kind="啟動效果", index="③"))]
        index, report = build_index(cards, tags)
        entry = index["cards"][0]
        self.assertEqual(entry["o"], ["m", "o", ""])
        self.assertEqual(len(entry["o"]), len(entry["tx"]))
        self.assertEqual(report["problems"], [])

    def test_o_is_omitted_when_no_clause_carries_it(self):
        """22,942 個效果句不承載這個屬性,空陣列一律省略(gzip 便宜得多)。"""
        cards = [card(1, desc="①：這樣。")]
        entry = build_index(cards, [tagged(1, clause("①：這樣。"))])[0]["cards"][0]
        self.assertNotIn("o", entry)

    def test_optional_outside_the_canon_fails_the_build(self):
        cards = [card(1, desc="①：這樣。")]
        tags = [tagged(1, clause("①：這樣。", kind="誘發效果(1速)",
                                 optional="看心情"))]
        _, report = build_index(cards, tags)
        self.assertEqual(report["checks"]["unknown_values"],
                         [{"id": 1, "field": "o", "value": "看心情",
                           "reason": "來源值對不到短碼"}])
        self.assertTrue(report["problems"])

    def test_optional_on_a_non_carrier_kind_fails_the_build(self):
        """永續效果帶著「必發」= 一個永遠零結果的條件在等著使用者設出來。

        搜尋介面照正典的承載關係決定「必發/選發」出不出得來(Story 25),而這道
        檢查守的是反方向:標記表哪天把值貼到不承載的類型上,要在建置期吵。
        """
        cards = [card(1, desc="①：這樣。")]
        tags = [tagged(1, clause("①：這樣。", kind="永續效果",
                                 optional="必發"))]
        _, report = build_index(cards, tags)
        self.assertEqual(report["checks"]["optional_on_non_carrier"],
                         [{"id": 1, "index": "①", "kind": "c", "o": "m"}])
        self.assertTrue(report["problems"])

    def test_optional_on_a_carrier_kind_passes(self):
        cards = [card(1, type=TRAP, desc="①：這樣。")]
        tags = [tagged(1, clause("①：這樣。", kind="通常陷阱卡效果",
                                 optional="必發"))]
        _, report = build_index(cards, tags)
        self.assertEqual(report["checks"]["optional_on_non_carrier"], [])
        self.assertEqual(report["problems"], [])

    def test_role_codes_align_with_tx(self):
        desc = "「素材A」＋「素材B」\n這個卡名的①效果1回合只能使用1次。\n①：這樣。"
        cards = [card(1, type=MONSTER_FUSION, desc=desc)]
        tags = [tagged(1,
                       clause("「素材A」＋「素材B」", kind="效果外文本",
                              index="0", role="素材指定"),
                       clause("這個卡名的①效果1回合只能使用1次。",
                              kind="效果外文本", index="0",
                              role="使用次數限制"),
                       clause("①：這樣。"))]
        index, report = build_index(cards, tags)
        entry = index["cards"][0]
        self.assertEqual(entry["ro"], ["mat", "limit", ""])
        self.assertEqual(len(entry["ro"]), len(entry["tx"]))
        self.assertEqual(report["problems"], [])

    def test_ro_is_omitted_when_no_clause_carries_a_role(self):
        cards = [card(1, desc="①：這樣。")]
        entry = build_index(cards, [tagged(1, clause("①：這樣。"))])[0]["cards"][0]
        self.assertNotIn("ro", entry)

    def test_pz_marks_the_pendulum_clauses(self):
        desc = "【靈擺效果】\n①：這樣。\n【怪獸效果】\n②：那樣。"
        cards = [card(1, type=MONSTER_PEND, desc=desc, scale=4)]
        tags = [tagged(1, clause("①：這樣。", kind="靈擺魔法卡效果",
                                 section="pendulum"),
                       clause("②：那樣。", index="②"))]
        entry = build_index(cards, tags)[0]["cards"][0]
        self.assertEqual(entry["pz"], [0])

    def test_pz_is_omitted_on_non_pendulum_cards(self):
        cards = [card(1, desc="①：這樣。")]
        entry = build_index(cards, [tagged(1, clause("①：這樣。"))])[0]["cards"][0]
        self.assertNotIn("pz", entry)


class CoverageCheckTest(unittest.TestCase):
    """效果句串接後必須覆蓋卡文,容許靈擺標頭與 `※` 別名兩種已知缺口。"""

    def test_section_headers_are_a_known_gap(self):
        desc = "【靈擺效果】\n①：這樣。\n【怪獸效果】\n②：那樣。"
        cards = [card(1, type=0x1 | 0x20 | 0x1000000, desc=desc)]
        tags = [tagged(1, clause("①：這樣。", section="pendulum"),
                       clause("②：那樣。", index="②"))]
        _, report = build_index(cards, tags)
        self.assertEqual(report["problems"], [])
        self.assertEqual(report["known_gaps"]["header"], 2)

    def test_alias_is_a_known_gap(self):
        cards = [card(1, desc="①：這樣。\n\n※另一個譯名")]
        tags = [tagged(1, clause("①：這樣。"))]
        _, report = build_index(cards, tags)
        self.assertEqual(report["problems"], [])
        self.assertEqual(report["known_gaps"]["alias"], 1)

    def test_third_kind_of_gap_fails_the_build(self):
        """第三種缺口 = 拆句或卡文出了預期外的變化,建置要倒。"""
        cards = [card(1, desc="①：這樣。②：漏掉的一句。")]
        tags = [tagged(1, clause("①：這樣。"))]
        _, report = build_index(cards, tags)
        self.assertEqual([g["gap"] for g in report["checks"]["coverage_gaps"]],
                         ["②：漏掉的一句。"])
        self.assertTrue(report["problems"])

    def test_clause_not_in_card_text_fails_the_build(self):
        cards = [card(1, desc="①：這樣。")]
        tags = [tagged(1, clause("①：完全不同的一句。"))]
        _, report = build_index(cards, tags)
        self.assertTrue(report["checks"]["clauses_not_in_desc"])
        self.assertTrue(report["problems"])


class ConsistencyCheckTest(unittest.TestCase):
    """四道檢查各自能失敗——重點是該擋的擋得住。"""

    def test_missing_card_fails_the_build(self):
        """大類解不出來的卡進不了索引,總表有卡而索引沒有 → 失敗。"""
        cards = [card(1, type=0x40)]  # 只有融合位元,沒有大類
        _, report = build_index(cards, [tagged(1)])
        self.assertEqual(report["checks"]["missing_cards"], [1])
        self.assertEqual(report["cards"], 0)
        self.assertTrue(report["problems"])

    def test_duplicate_password_fails_the_build(self):
        cards = [card(1), card(1)]
        _, report = build_index(cards, [tagged(1)])
        self.assertEqual(report["checks"]["duplicate_ids"], [1])
        self.assertTrue(report["problems"])

    def test_card_without_tag_entry_fails_the_build(self):
        _, report = build_index([card(1, desc="①：這樣。")], [])
        self.assertEqual(report["checks"]["cards_without_clause_entry"], [1])
        self.assertTrue(report["problems"])

    def test_clause_without_kind_fails_the_build(self):
        cards = [card(1, desc="①：這樣。")]
        tags = [tagged(1, clause("①：這樣。", kind=None))]
        index, report = build_index(cards, tags)
        self.assertEqual(report["checks"]["clauses_without_kind"],
                         [{"id": 1, "index": "①"}])
        self.assertEqual(index["cards"][0]["k"], [""])
        self.assertTrue(report["problems"])

    def test_kind_outside_the_canon_fails_the_build(self):
        """索引出現值域正典沒有的值 → 失敗(漏一個碼就是這個形狀)。"""
        cards = [card(1, desc="①：這樣。")]
        tags = [tagged(1, clause("①：這樣。", kind="鬼扯效果"))]
        _, report = build_index(cards, tags)
        self.assertEqual(report["checks"]["unknown_values"],
                         [{"id": 1, "field": "k", "value": "鬼扯效果",
                           "reason": "來源值對不到短碼"}])
        self.assertTrue(report["problems"])

    def test_unexplained_type_bit_fails_the_build(self):
        """`type` 冒出正典沒登記的位元:要吵,不要靜靜忽略。"""
        cards = [card(1, type=MONSTER | 0x100)]
        _, report = build_index(cards, [tagged(1)])
        self.assertEqual(report["checks"]["unexplained_type_bits"],
                         [{"id": 1, "bits": "0x100"}])
        self.assertTrue(report["problems"])


class MonsterInvariantTest(unittest.TestCase):
    """「大類是怪獸 ⟺ 有種族與屬性」雙向成立,否則建置失敗。"""

    def test_holds_on_clean_input(self):
        cards = [card(1), card(2, type=SPELL_QUICK), card(3, type=TRAP)]
        tags = [tagged(1), tagged(2), tagged(3)]
        _, report = build_index(cards, tags)
        inv = report["monster_invariant"]
        self.assertEqual(inv["monsters"], 1)
        self.assertEqual(inv["monster_missing_race_or_attribute"], [])
        self.assertEqual(inv["non_monster_with_monster_params"], [])
        self.assertEqual(report["problems"], [])

    def test_trap_with_monster_params_fails_the_build(self):
        """罠モンスター的種族是它變成怪獸之後的形態,不是卡片的參數。"""
        cards = [card(1, type=TRAP, race=0x100, attribute=0x2, level=2,
                      atk=1200)]
        _, report = build_index(cards, [tagged(1)])
        inv = report["monster_invariant"]
        self.assertEqual(inv["non_monster_with_monster_params"], [1])
        self.assertTrue(report["problems"])

    def test_monster_without_race_fails_the_build(self):
        cards = [card(1, race=0)]
        _, report = build_index(cards, [tagged(1)])
        inv = report["monster_invariant"]
        self.assertEqual(inv["monster_missing_race_or_attribute"], [1])
        self.assertTrue(report["problems"])


class CrossTypeTest(unittest.TestCase):
    """跨類型魔陷效果(ADR-0010):魔陷十值的按鈕只收本類以外的卡。

    建置期做兩件事:全庫算每值的**跨類型卡數**(自身卡片種類與值不一致),
    跨類型 0 張的值從輸出的按鈕分組移除。`items` 是顯示詞彙表(呈現層的逐行
    類型標籤照它查中文),**不**跟著減。
    """

    def build(self):
        cards = [
            # 怪獸「當作裝備魔法卡」:跨類型,se 因它保住按鈕
            card(1, desc="①：把這張卡當作裝備卡裝備。"),
            # 裝備魔法卡自己的裝備魔法卡效果:本類,不算跨類型
            card(2, type=SPELL_EQUIP, desc="①：裝備怪獸攻擊力上升。"),
            # 儀式魔法卡:本類,sr 全庫無跨類型 → 按鈕拿掉
            card(3, type=SPELL_RITUAL, desc="①：儀式召喚。"),
            # 靈擺怪獸的靈擺效果句:靈擺怪獸算本類(ADR-0010),sp 按鈕拿掉
            card(4, type=MONSTER_PEND, scale=1,
                 desc="【靈擺效果】\n①：這樣。\n【怪獸效果】\n②：那樣。"),
        ]
        tags = [
            tagged(1, clause("①：把這張卡當作裝備卡裝備。",
                             kind="裝備魔法卡效果")),
            tagged(2, clause("①：裝備怪獸攻擊力上升。", kind="裝備魔法卡效果")),
            tagged(3, clause("①：儀式召喚。", kind="儀式魔法卡效果")),
            tagged(4, clause("①：這樣。", kind="靈擺魔法卡效果",
                             section="pendulum"),
                   clause("②：那樣。", kind="啟動效果", index="②")),
        ]
        return build_index(cards, tags)

    def test_cross_type_card_counts_per_value(self):
        _, report = self.build()
        cross = report["kind_cross"]["cards"]
        # 十值都有數字(某值突然掉到 0 要看得見),本類卡不計入
        self.assertEqual(sorted(cross), sorted(
            ["sn", "sq", "sr", "sc", "se", "sf", "sp", "tn", "tc", "tk"]))
        self.assertEqual(cross["se"], 1)   # 只有怪獸那張,裝備魔法卡不算
        self.assertEqual(cross["sr"], 0)
        self.assertEqual(cross["sp"], 0)

    def test_values_without_cross_type_cards_lose_their_buttons(self):
        """排除本類後全庫無卡的值,建置期就不生成按鈕(前端零推導)。"""
        index, report = self.build()
        kind = index["vocab"]["kind"]
        cross_group = next(g for g in kind["groups"]
                           if g["zh"] == "跨類型魔陷效果")
        self.assertEqual(cross_group["codes"], ["se"])
        # 怪獸側六類不受影響
        monster_group = next(g for g in kind["groups"] if g["zh"] == "怪獸側")
        self.assertEqual(monster_group["codes"], ["x", "u", "c", "q", "t", "i"])
        self.assertEqual(report["kind_cross"]["dropped"],
                         ["sc", "sf", "sn", "sp", "sq", "sr", "tc", "tk", "tn"])

    def test_items_stay_complete_for_display(self):
        """items 是顯示詞彙表:本類卡的效果句照樣掛著「儀式魔法卡效果」標籤,
        中文查表不能因為按鈕被拿掉而查不到。"""
        index, _ = self.build()
        codes = [i["code"] for i in index["vocab"]["kind"]["items"]]
        self.assertEqual(len(codes), 16)
        for code in ("sr", "sp", "se"):
            self.assertIn(code, codes)

    def test_own_type_cards_do_not_fail_the_build(self):
        """本類卡帶著被拿掉按鈕的值是 ADR-0010 的既定語意,不是碼沒登記。"""
        _, report = self.build()
        self.assertEqual(report["problems"], [])

    def test_group_disappears_when_all_ten_are_dropped(self):
        """整組都沒有跨類型卡時,連「跨類型魔陷效果」這個組標題都不生成。"""
        cards = [card(1, type=SPELL_RITUAL, desc="①：儀式召喚。")]
        tags = [tagged(1, clause("①：儀式召喚。", kind="儀式魔法卡效果"))]
        index, report = build_index(cards, tags)
        self.assertEqual([g["zh"] for g in index["vocab"]["kind"]["groups"]],
                         ["怪獸側"])
        self.assertEqual(report["problems"], [])


class ErrataTest(unittest.TestCase):
    """[[卡文勘誤表]]的原文欄位:被勘誤的卡帶 `og`(勘誤前原樣),其餘卡不帶。"""

    def build(self, desc, errata):
        cards = [card(84488827, desc=desc)]
        tags = [tagged(84488827, clause(desc, kind="誘發效果(1速)",
                                        optional="必發"))]
        return build_index(cards, tags, errata=errata)

    def test_errata_card_carries_original_text(self):
        index, report = self.build(
            "召喚成功時，從以下效果選擇1個效果發動。",
            [{"id": 84488827, "from": "可以從以下效果", "to": "從以下效果"}])
        self.assertEqual(report["problems"], [])
        self.assertEqual(index["cards"][0]["og"],
                         "召喚成功時，可以從以下效果選擇1個效果發動。")

    def test_untouched_card_has_no_og(self):
        cards = [card(1000, desc="①：這樣。")]
        tags = [tagged(1000, clause("①：這樣。"))]
        index, report = build_index(cards, tags, errata=[])
        self.assertNotIn("og", index["cards"][0])

    def test_irreversible_errata_fails_the_build(self):
        """修正後子字串在卡文出現兩次 → 逆推不唯一,建置失敗。"""
        index, report = self.build(
            "從以下效果選擇。從以下效果選擇。",
            [{"id": 84488827, "from": "可以從以下效果", "to": "從以下效果"}])
        self.assertTrue(report["checks"]["errata_not_reversible"])
        self.assertTrue(any("逆推" in p for p in report["problems"]))


class ReportTest(unittest.TestCase):
    def test_census_counts_members_and_cards(self):
        """每一個值域的成員數與對應卡數:某個值掉到 0 要看得見。"""
        cards = [card(1, type=0x1 | 0x10 | 0x1000000),  # 靈擺通常怪獸
                 card(2, type=SPELL_QUICK), card(3, type=TRAP)]
        tags = [tagged(1), tagged(2), tagged(3)]
        _, report = build_index(cards, tags)
        counts = report["census"]["counts"]
        self.assertEqual(counts["cat"], {"m": 1, "s": 1, "t": 1})
        # 多位元並存:同一張卡同時算進通常與靈擺
        self.assertEqual(counts["sub_m"]["normal"], 1)
        self.assertEqual(counts["sub_m"]["pendulum"], 1)
        self.assertEqual(counts["sub_s"]["quick"], 1)
        self.assertEqual(counts["sub_t"]["normal"], 1)
        self.assertEqual(counts["race"]["dragon"], 1)
        # 非怪獸沒有屬性,那不是值域成員而是「沒有這個參數」
        self.assertEqual(report["census"]["no_value"]["attr"], 2)

    def test_report_counts_and_vocab_digest(self):
        cards = [card(1, desc="①：這樣。"), card(2, desc="①：那樣。")]
        tags = [tagged(1, clause("①：這樣。")), tagged(2, clause("①：那樣。"))]
        _, report = build_index(cards, tags)
        self.assertEqual(report["cards"], 2)
        self.assertEqual(report["clauses"], 2)
        self.assertEqual(report["vocab"]["digest"], vocab.digest())
        self.assertEqual(report["vocab"]["problems"], [])


class SerializeTest(unittest.TestCase):
    def build(self, built_at="2026-08-13T00:00:00+0800", **kwargs):
        cards = [card(1, desc="①：這樣。", name_ja="日", name_en="En"),
                 card(2, type=TRAP, desc="這樣。")]
        tags = [tagged(1, clause("①：這樣。")),
                tagged(2, clause("這樣。", kind="通常陷阱卡效果", index="1"))]
        return build_index(cards, tags, built_at=built_at,
                           sources={"cards.json": "abc"}, **kwargs)

    def test_three_globals(self):
        index, _ = self.build()
        text = serialize_index(index)
        self.assertTrue(text.startswith("window.CARD_DATA=[\n"))
        self.assertIn("\nwindow.VOCAB={\n", text)
        self.assertIn("\nwindow.META={\n", text)
        self.assertTrue(text.endswith("};\n"))
        # 一卡一行:data.js 入版控,git diff 要讀得出來
        cards_block = text.split("window.VOCAB")[0]
        self.assertEqual(cards_block.count("\n{"), 2)

    def test_meta_carries_build_context(self):
        index, _ = self.build()
        meta = index["meta"]
        self.assertEqual(meta["built_at"], "2026-08-13T00:00:00+0800")
        self.assertEqual(meta["cards"], 2)
        self.assertEqual(meta["clauses"], 2)
        self.assertEqual(meta["vocab_digest"], vocab.digest())
        self.assertEqual(meta["sources"], {"cards.json": "abc"})

    def test_meta_carries_data_updated_at_when_given(self):
        """資料更新時間(來源檔下載時間)由薄殼傳入 → META 帶欄位、序列化看得到。"""
        index, _ = self.build(data_updated_at="2026-08-08T17:57:00+0800")
        self.assertEqual(index["meta"]["data_updated_at"],
                         "2026-08-08T17:57:00+0800")
        self.assertIn('"data_updated_at":"2026-08-08T17:57:00+0800"',
                      serialize_index(index))

    def test_meta_omits_data_updated_at_when_absent(self):
        """從未跑過更新流程 → 欄位缺席(不是空字串),不是建置失敗。"""
        index, report = self.build()
        self.assertNotIn("data_updated_at", index["meta"])
        self.assertEqual(report["problems"], [])

    def test_same_input_builds_byte_identical_output(self):
        """時鐘與來源雜湊由呼叫端給,純函式不碰,所以重跑逐位元組相同。"""
        first, _ = self.build()
        second, _ = self.build()
        self.assertEqual(serialize_index(first), serialize_index(second))


if __name__ == "__main__":
    unittest.main()
