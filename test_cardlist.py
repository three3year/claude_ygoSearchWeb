"""卡片總表管線測試。

接縫:cardlist.build_card_list(來源 cdb 路徑們[, 既有總表]) → (cards, report)。
fixture cdb 於測試內程式化建立,不碰網路。
"""
import os
import sqlite3
import tempfile
import unittest

from cardlist import build_card_list, serialize_card_list

DATAS_COLS = "(id,ot,alias,setcode,type,atk,def,level,race,attribute,category)"
TEXTS_COLS = "(id,name,desc,str1,str2,str3,str4,str5,str6,str7,str8,"
TEXTS_COLS += "str9,str10,str11,str12,str13,str14,str15,str16)"


def make_cdb(path, rows):
    """建立迷你 cdb。rows: list of dict,鍵為 datas/texts 欄位,未給者取預設。"""
    con = sqlite3.connect(path)
    con.execute(
        "CREATE TABLE datas(id INTEGER PRIMARY KEY, ot, alias, setcode, type,"
        " atk, def, level, race, attribute, category)")
    con.execute(
        "CREATE TABLE texts(id INTEGER PRIMARY KEY, name, desc,"
        " str1, str2, str3, str4, str5, str6, str7, str8,"
        " str9, str10, str11, str12, str13, str14, str15, str16)")
    for row in rows:
        d = {"ot": 1, "alias": 0, "setcode": 0, "type": 0x11, "atk": 0,
             "def": 0, "level": 0, "race": 0, "attribute": 0, "category": 0,
             "name": "", "desc": ""}
        d.update(row)
        con.execute(
            "INSERT INTO datas VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (d["id"], d["ot"], d["alias"], d["setcode"], d["type"], d["atk"],
             d["def"], d["level"], d["race"], d["attribute"], d["category"]))
        con.execute(
            "INSERT INTO texts VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (d["id"], d["name"], d["desc"]) + ("",) * 16)
    con.commit()
    con.close()
    return path


class CardListTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def cdb(self, name, rows):
        return make_cdb(os.path.join(self.tmp.name, name), rows)

    def test_monster_card_fields(self):
        """一張怪獸卡進總表,欄位齊全且順序固定。"""
        zh = self.cdb("zh.cdb", [{
            "id": 63028558, "name": "青眼白龍",
            "desc": "以高攻擊力著稱的傳說之龍。",
            "type": 0x11, "atk": 3000, "def": 2500, "level": 8,
            "race": 0x2000, "attribute": 0x20, "setcode": 0xdd,
        }])
        cards, report = build_card_list(zh)
        self.assertEqual(len(cards), 1)
        card = cards[0]
        self.assertEqual(list(card.keys()), [
            "id", "alt_ids", "name_zh", "name_ja", "name_en", "desc",
            "type", "atk", "def", "level", "race", "attribute",
            "scale", "link_marker", "setcode", "ot"])
        self.assertEqual(card["id"], 63028558)
        self.assertEqual(card["alt_ids"], [])
        self.assertEqual(card["name_zh"], "青眼白龍")
        self.assertEqual(card["name_ja"], "")
        self.assertEqual(card["name_en"], "")
        self.assertEqual(card["desc"], "以高攻擊力著稱的傳說之龍。")
        self.assertEqual(card["type"], 0x11)
        self.assertEqual(card["atk"], 3000)
        self.assertEqual(card["def"], 2500)
        self.assertEqual(card["level"], 8)
        self.assertEqual(card["race"], 0x2000)
        self.assertEqual(card["attribute"], 0x20)
        self.assertEqual(card["scale"], 0)
        self.assertEqual(card["link_marker"], 0)
        self.assertEqual(card["setcode"], 0xdd)
        self.assertEqual(card["ot"], 1)
        self.assertEqual(report["included"], 1)

    def test_exclusion_rules(self):
        """9 位數暫時編號與衍生物被排除,報告含排除統計。"""
        zh = self.cdb("zh.cdb", [
            {"id": 12345678, "name": "正常卡"},
            {"id": 100267001, "name": "先行卡"},          # 9 位數暫時編號
            {"id": 73915052, "name": "羊衍生物", "type": 0x11 | 0x4000},
            {"id": 5043010, "name": "防火牆龍",
             "type": 0x11 | 0x4000000},                   # Link 怪,不得誤殺
        ])
        cards, report = build_card_list(zh)
        self.assertEqual([c["id"] for c in cards], [5043010, 12345678])
        self.assertEqual(report["included"], 2)
        self.assertEqual(report["excluded"], {"no_password": 1, "token": 1})

    def test_alias_merge(self):
        """同名 alias 條目合併進主卡;卡名不同或主卡不存在者不合併並列入報告。"""
        zh = self.cdb("zh.cdb", [
            {"id": 1861628, "name": "解碼語者", "atk": 2300},
            {"id": 1861631, "name": "解碼語者", "alias": 1861628},
            {"id": 1861629, "name": "解碼語者", "alias": 1861628},
            {"id": 20409757, "name": "改名卡", "alias": 1861628},   # 名字不同
            {"id": 30000000, "name": "孤兒異圖", "alias": 99999999},  # 主卡不存在
        ])
        cards, report = build_card_list(zh)
        ids = [c["id"] for c in cards]
        self.assertEqual(ids, [1861628, 20409757, 30000000])
        main = cards[0]
        self.assertEqual(main["alt_ids"], [1861629, 1861631])
        self.assertEqual(main["atk"], 2300)
        self.assertEqual(report["included"], 3)
        self.assertEqual(report["merged_alt"], 2)
        self.assertEqual(
            report["alias_exceptions"],
            [{"id": 20409757, "alias": 1861628, "reason": "name_mismatch"},
             {"id": 30000000, "alias": 99999999, "reason": "target_missing"}])

    def test_level_decomposition(self):
        """靈擺卡的複合 level 欄位拆出等級與刻度;Link 怪的 def 欄位是連結標記。"""
        zh = self.cdb("zh.cdb", [
            # 靈擺怪:cdb level = 刻度8<<24 | 刻度8<<16 | 等級4
            {"id": 16178681, "name": "靈擺魔術師",
             "type": 0x11 | 0x1000000, "level": (8 << 24) | (8 << 16) | 4},
            # Link 怪:def 欄位存連結標記,無守備力
            {"id": 1861628, "name": "解碼語者",
             "type": 0x11 | 0x4000000, "level": 3, "def": 0b100101010},
        ])
        cards, _ = build_card_list(zh)
        pend, link = cards[1], cards[0]
        self.assertEqual(pend["level"], 4)
        self.assertEqual(pend["scale"], 8)
        self.assertEqual(link["level"], 3)
        self.assertEqual(link["scale"], 0)
        self.assertEqual(link["link_marker"], 0b100101010)
        self.assertIsNone(link["def"])

    def test_serialization_stable(self):
        """一卡一行的 JSON;同輸入兩次執行輸出逐位元組相同,且可 round-trip。"""
        import json
        rows = [{"id": 12345678, "name": "卡A", "desc": "效果甲"},
                {"id": 23456789, "name": "卡B", "desc": "效果乙"}]
        zh = self.cdb("zh.cdb", rows)
        cards1, _ = build_card_list(zh)
        zh2 = self.cdb("zh2.cdb", list(reversed(rows)))
        cards2, _ = build_card_list(zh2)
        text1 = serialize_card_list(cards1)
        text2 = serialize_card_list(cards2)
        self.assertEqual(text1.encode("utf-8"), text2.encode("utf-8"))
        # 一卡一行:總行數 = 卡數 + 首尾括號兩行
        self.assertEqual(len(text1.strip().splitlines()), len(cards1) + 2)
        self.assertNotIn("\\u", text1)  # 中文不被 escape,git diff 可讀
        self.assertEqual(json.loads(text1), cards1)

    def test_ja_en_name_merge(self):
        """日英卡名以密碼對齊填入;來源缺卡時留空;異圖主卡取主卡密碼的名稱;報告含覆蓋率。"""
        zh = self.cdb("zh.cdb", [
            {"id": 89631139, "name": "青眼白龍"},
            {"id": 89631140, "name": "青眼白龍", "alias": 89631139},  # 異圖
            {"id": 46986414, "name": "黑魔導"},
        ])
        ja = self.cdb("ja.cdb", [
            {"id": 89631139, "name": "青眼の白龍"},
            {"id": 89631140, "name": "（異圖名,不應被採用）"},
        ])
        en = self.cdb("en.cdb", [
            {"id": 46986414, "name": "Dark Magician"},
        ])
        cards, report = build_card_list(zh, ja_path=ja, en_path=en)
        by_id = {c["id"]: c for c in cards}
        self.assertEqual(by_id[89631139]["name_ja"], "青眼の白龍")
        self.assertEqual(by_id[89631139]["name_en"], "")
        self.assertEqual(by_id[46986414]["name_ja"], "")
        self.assertEqual(by_id[46986414]["name_en"], "Dark Magician")
        cov = report["name_coverage"]
        self.assertEqual(cov["ja"], {"named": 1, "missing": 1})
        self.assertEqual(cov["en"], {"named": 1, "missing": 1})

    def test_ja_en_optional(self):
        """不給日英來源時行為與純繁中建置相同,報告無覆蓋率段。"""
        zh = self.cdb("zh.cdb", [{"id": 89631139, "name": "青眼白龍"}])
        cards, report = build_card_list(zh)
        self.assertEqual(cards[0]["name_ja"], "")
        self.assertNotIn("name_coverage", report)


if __name__ == "__main__":
    unittest.main()
