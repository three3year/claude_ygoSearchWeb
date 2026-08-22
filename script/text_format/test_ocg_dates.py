"""OCG 首發日對齊的純函式測試:餵合成卡片記錄,不讀真實資料。"""
import json
import os
import tempfile
import unittest

from ocg_dates import align_ocg_dates, load_ocg_dates


def _card(id_, alt_ids=()):
    return {"id": id_, "alt_ids": list(alt_ids)}


class AlignOcgDatesTest(unittest.TestCase):
    def test_main_password_match(self):
        """主卡密碼直接對到來源 → 取該日期。"""
        aligned = align_ocg_dates([_card(89631139)],
                                  {89631139: "1999-02-04"})
        self.assertEqual(aligned, {89631139: "1999-02-04"})

    def test_alt_password_fallback(self):
        """主卡沒對到時試異圖密碼:異圖歸主卡,日期記在主卡密碼下。"""
        aligned = align_ocg_dates([_card(89631139, alt_ids=[36996508])],
                                  {36996508: "1999-02-04"})
        self.assertEqual(aligned, {89631139: "1999-02-04"})

    def test_main_password_wins_over_alt(self):
        """主卡與異圖都有日期時以主卡為準(比照 genesys 的消費慣例)。"""
        aligned = align_ocg_dates(
            [_card(89631139, alt_ids=[36996508])],
            {89631139: "1999-02-04", 36996508: "2004-12-09"})
        self.assertEqual(aligned, {89631139: "1999-02-04"})

    def test_missing_date_kept_as_none(self):
        """查無日期的卡保留在結果中、值為 None:可辨識,不硬猜日期。"""
        aligned = align_ocg_dates([_card(111), _card(222)],
                                  {111: "2015-06-20"})
        self.assertEqual(aligned, {111: "2015-06-20", 222: None})

    def test_every_card_present(self):
        """輸出鍵集合 = 卡片總表全部主卡密碼,與來源多出的卡無關。"""
        aligned = align_ocg_dates([_card(111)],
                                  {111: "2015-06-20", 999: "2000-01-01"})
        self.assertEqual(set(aligned), {111})


class LoadOcgDatesTest(unittest.TestCase):
    def test_loads_string_keys_as_int(self):
        """來源檔鍵是密碼字串(JSON 限制),載入後轉 int 與卡片總表對齊。"""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = os.path.join(tmp.name, "ocg-dates.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"89631139": "1999-02-04"}, f)
        self.assertEqual(load_ocg_dates(path), {89631139: "1999-02-04"})


if __name__ == "__main__":
    unittest.main()
