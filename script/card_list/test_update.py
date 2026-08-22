"""來源下載殼測試:注入假 fetch,不實際連網。"""
import json
import os
import tempfile
import unittest

from update_cards import (BANLIST_FORMATS, SOURCES, check_faq_gap,
                          check_ocg_date_coverage, download_all,
                          download_banlists, download_genesys,
                          download_md_rarity, download_ocg_dates,
                          download_sources, record_downloaded_at)


class DownloadSourcesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = self.tmp.name

    def test_downloads_all_sources(self):
        """三個來源各自下載寫入暫存目錄,回傳名稱→路徑。"""
        fetched = []
        paths = download_sources(
            self.dir, fetch=lambda url: fetched.append(url) or b"data:" + url.encode())
        self.assertEqual(set(paths), {"zh", "ja", "en"})
        self.assertEqual(fetched, [SOURCES["zh"], SOURCES["ja"], SOURCES["en"]])
        for key, path in paths.items():
            with open(path, "rb") as f:
                self.assertEqual(f.read(), b"data:" + SOURCES[key].encode())

    def test_failed_download_keeps_existing_and_names_source(self):
        """單一來源失敗:錯誤指明來源,既有暫存檔不被覆蓋毀損。"""
        paths = download_sources(self.dir, fetch=lambda url: b"old")
        def flaky(url):
            if url == SOURCES["ja"]:
                raise OSError("boom")
            return b"new"
        with self.assertRaises(RuntimeError) as ctx:
            download_sources(self.dir, fetch=flaky)
        self.assertIn("ja", str(ctx.exception))
        with open(paths["ja"], "rb") as f:
            self.assertEqual(f.read(), b"old")  # 舊檔完好

    def test_offline_uses_cached_files(self):
        """offline 模式:不呼叫 fetch,直接用既有暫存檔。"""
        download_sources(self.dir, fetch=lambda url: b"cached")
        def no_net(url):
            raise AssertionError("offline 不應連網")
        paths = download_sources(self.dir, fetch=no_net, offline=True)
        self.assertEqual(set(paths), {"zh", "ja", "en"})

    def test_offline_missing_file_errors(self):
        """offline 但暫存檔不存在 → 指明缺哪個來源。"""
        with self.assertRaises(RuntimeError) as ctx:
            download_sources(self.dir, fetch=None, offline=True)
        self.assertIn("zh", str(ctx.exception))


class DownloadMdRarityTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = self.tmp.name

    def test_paged_fetch_builds_password_entry_map(self):
        """分頁抓到空頁為止,彙整成 {密碼: {稀有度, 禁限}};略過無效條目。

        稀有度與 banStatus 各自可缺:只有 banStatus 的筆(未收錄卡的預掛)
        也入檔——採不採計是建置端的決定,下載端保留原貌讓報告數得到。
        """
        pages = {
            1: [{"konamiID": "89631139", "rarity": "UR"},
                {"konamiID": "23434538", "rarity": "SR",
                 "banStatus": "Limited 1"}],
            2: [{"konamiID": None, "rarity": "R"},          # 無密碼 → 略過
                {"konamiID": "91869203", "banStatus": "Forbidden"},
                {"konamiID": "23456789", "rarity": ""}],    # 兩者皆無 → 略過
            3: [],
        }
        def fetch_json(url):
            self.assertIn("banStatus", url)  # 端點要多要 banStatus 欄位
            page = int(url.split("page=")[1].split("&")[0])
            return pages[page]
        path = download_md_rarity(self.dir, fetch_json=fetch_json)
        with open(path, encoding="utf-8") as f:
            self.assertEqual(json.load(f), {
                "23434538": {"rarity": "SR", "banStatus": "Limited 1"},
                "89631139": {"rarity": "UR"},
                "91869203": {"banStatus": "Forbidden"},
            })

    def test_duplicate_konami_id_rows_merge_per_field(self):
        """同一密碼多列(異圖/預掛):逐欄位合併,後列缺的欄位不蓋掉先列的值。

        整筆覆蓋的病灶:只有 banStatus 的後列會把先列的稀有度吃掉,
        MD 稀有度覆蓋率無聲下降(實測掉了 9 張)。
        """
        pages = {
            1: [{"konamiID": "89631139", "rarity": "UR"}],
            2: [{"konamiID": "89631139", "banStatus": "Forbidden"}],
            3: [],
        }
        def fetch_json(url):
            page = int(url.split("page=")[1].split("&")[0])
            return pages[page]
        path = download_md_rarity(self.dir, fetch_json=fetch_json)
        with open(path, encoding="utf-8") as f:
            self.assertEqual(json.load(f), {
                "89631139": {"rarity": "UR", "banStatus": "Forbidden"}})

    def test_failure_keeps_existing_file(self):
        """抓取失敗:錯誤指明 md 來源,既有檔不毀損。"""
        path = download_md_rarity(
            self.dir, fetch_json=lambda url: [] if "page=2" in url
            else [{"konamiID": "1", "rarity": "N"}])
        def boom(url):
            raise OSError("boom")
        with self.assertRaises(RuntimeError) as ctx:
            download_md_rarity(self.dir, fetch_json=boom)
        self.assertIn("md", str(ctx.exception))
        with open(path, encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"1": {"rarity": "N"}})

    def test_offline_uses_cache_and_errors_when_missing(self):
        """offline:有既有檔直接沿用;沒有則指明缺 md 來源。"""
        with self.assertRaises(RuntimeError) as ctx:
            download_md_rarity(self.dir, fetch_json=None, offline=True)
        self.assertIn("md", str(ctx.exception))
        download_md_rarity(
            self.dir, fetch_json=lambda url: [] if "page=2" in url
            else [{"konamiID": "1", "rarity": "N"}])
        path = download_md_rarity(self.dir, fetch_json=None, offline=True)
        self.assertTrue(os.path.exists(path))


class RecordDownloadedAtTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = self.tmp.name

    def test_writes_single_timestamp(self):
        """一次執行記一個時間;時刻由呼叫端注入,不讀時鐘。"""
        path = record_downloaded_at(self.dir, "2026-08-08T17:57:00+0800")
        with open(path, encoding="utf-8") as f:
            self.assertEqual(json.load(f),
                             {"downloaded_at": "2026-08-08T17:57:00+0800"})

    def test_new_run_overwrites_previous(self):
        """再跑一次更新 → 記錄換成新時間。"""
        record_downloaded_at(self.dir, "2026-08-01T00:00:00+0800")
        path = record_downloaded_at(self.dir, "2026-08-08T17:57:00+0800")
        with open(path, encoding="utf-8") as f:
            self.assertEqual(json.load(f)["downloaded_at"],
                             "2026-08-08T17:57:00+0800")

    def test_offline_keeps_existing_record(self):
        """offline 沿用既有記錄:時間反映下載,不反映重跑。"""
        record_downloaded_at(self.dir, "2026-08-08T17:57:00+0800")
        path = record_downloaded_at(
            self.dir, "2026-08-20T12:00:00+0800", offline=True)
        with open(path, encoding="utf-8") as f:
            self.assertEqual(json.load(f)["downloaded_at"],
                             "2026-08-08T17:57:00+0800")

    def test_offline_without_record_writes_nothing(self):
        """offline 且從未記錄過 → 不寫檔也不報錯(footer 那行省略即可)。"""
        path = record_downloaded_at(
            self.dir, "2026-08-20T12:00:00+0800", offline=True)
        self.assertFalse(os.path.exists(path))


class DownloadAllTest(unittest.TestCase):
    """下載殼縫:注入假 fetch,驗「全部成功才寫時間記錄、單一失敗不寫」。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = self.tmp.name
        self.record = os.path.join(self.dir, "downloaded_at.json")
        self.genesys = {"data": [{"id": 1, "misc_info": [{"genesys_points": 5}]}]}

    def fetch_json(self, url):
        if "page=" in url:
            return []
        if "banlist=" in url:
            return {"data": [{"id": 1, "banlist_info": {"ban_ocg": "Limited"}}]}
        return self.genesys

    def test_all_sources_succeed_writes_record(self):
        download_all(self.dir, "2026-08-08T17:57:00+0800",
                     fetch=lambda url: b"cdb", fetch_json=self.fetch_json)
        with open(self.record, encoding="utf-8") as f:
            self.assertEqual(json.load(f)["downloaded_at"],
                             "2026-08-08T17:57:00+0800")

    def test_downloads_banlists_too(self):
        """一鍵更新連禁限來源一起抓:回傳的路徑存在且內容已寫入。"""
        *_, banlist_paths, _ = download_all(
            self.dir, "2026-08-08T17:57:00+0800",
            fetch=lambda url: b"cdb", fetch_json=self.fetch_json)
        for path in banlist_paths.values():
            self.assertTrue(os.path.exists(path))

    def test_downloads_ocg_dates_too(self):
        """一鍵更新連 OCG 首發日來源一起抓:回傳的路徑存在。"""
        *_, ocg_dates_path = download_all(
            self.dir, "2026-08-08T17:57:00+0800",
            fetch=lambda url: b"cdb", fetch_json=self.fetch_json)
        self.assertTrue(os.path.exists(ocg_dates_path))

    def test_one_source_fails_writes_nothing(self):
        def boom(url):
            raise OSError("boom")
        with self.assertRaises(RuntimeError):
            download_all(self.dir, "2026-08-08T17:57:00+0800",
                         fetch=lambda url: b"cdb", fetch_json=boom)
        self.assertFalse(os.path.exists(self.record))

    def test_failure_keeps_previous_record(self):
        download_all(self.dir, "2026-08-01T00:00:00+0800",
                     fetch=lambda url: b"cdb", fetch_json=self.fetch_json)
        def boom(url):
            raise OSError("boom")
        with self.assertRaises(RuntimeError):
            download_all(self.dir, "2026-08-08T17:57:00+0800",
                         fetch=boom, fetch_json=self.fetch_json)
        with open(self.record, encoding="utf-8") as f:
            self.assertEqual(json.load(f)["downloaded_at"],
                             "2026-08-01T00:00:00+0800")

    def test_offline_keeps_record_untouched(self):
        download_all(self.dir, "2026-08-01T00:00:00+0800",
                     fetch=lambda url: b"cdb", fetch_json=self.fetch_json)
        def no_net(url):
            raise AssertionError("offline 不應連網")
        download_all(self.dir, "2026-08-20T12:00:00+0800", offline=True,
                     fetch=no_net, fetch_json=no_net)
        with open(self.record, encoding="utf-8") as f:
            self.assertEqual(json.load(f)["downloaded_at"],
                             "2026-08-01T00:00:00+0800")


class DownloadGenesysTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = self.tmp.name

    def test_extracts_password_points_map(self):
        """從 YGOPRODeck dump 萃取有 genesys_points 的卡 → {密碼: 點數}。"""
        dump = {"data": [
            {"id": 55144522, "misc_info": [{"genesys_points": 30}]},
            {"id": 46986414, "misc_info": [{"konami_id": 4041}]},   # 未列點
            {"id": 89631139, "misc_info": [{"genesys_points": 0}]},  # 明確 0 點
        ]}
        path = download_genesys(self.dir, fetch_json=lambda url: dump)
        with open(path, encoding="utf-8") as f:
            self.assertEqual(json.load(f),
                             {"55144522": 30, "89631139": 0})

    def test_failure_keeps_existing_and_offline_cache(self):
        """失敗指明 genesys 來源且不毀既有檔;offline 沿用快取、缺檔報錯。"""
        with self.assertRaises(RuntimeError) as ctx:
            download_genesys(self.dir, fetch_json=None, offline=True)
        self.assertIn("genesys", str(ctx.exception))
        dump = {"data": [{"id": 1, "misc_info": [{"genesys_points": 5}]}]}
        path = download_genesys(self.dir, fetch_json=lambda url: dump)
        def boom(url):
            raise OSError("boom")
        with self.assertRaises(RuntimeError) as ctx:
            download_genesys(self.dir, fetch_json=boom)
        self.assertIn("genesys", str(ctx.exception))
        with open(path, encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"1": 5})
        self.assertEqual(
            download_genesys(self.dir, fetch_json=None, offline=True), path)


class DownloadOcgDatesTest(unittest.TestCase):
    """OCG 首發日來源:自 YGOPRODeck 全量 dump 萃取 {密碼: ocg_date}。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = self.tmp.name

    def test_extracts_password_date_map(self):
        """dump → {密碼: 首發日字串};查無 ocg_date 的條目不入檔(不硬猜)。"""
        dump = {"data": [
            {"id": 89631139, "misc_info": [{"ocg_date": "1999-02-04"}]},
            {"id": 46986414, "misc_info": [{"konami_id": 4041}]},  # TCG 限定等
            {"id": 12345678},                                      # 無 misc_info
        ]}
        path = download_ocg_dates(self.dir, fetch_json=lambda url: dump)
        with open(path, encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"89631139": "1999-02-04"})

    def test_fetches_full_dump_without_format_filter(self):
        """端點是全量 dump(misc=yes)且不帶 format= 卡池篩選——
        genesys 端點那種 format=genesys 會漏卡,首發日要全庫都有機會對到。"""
        fetched = []
        download_ocg_dates(
            self.dir,
            fetch_json=lambda url: fetched.append(url) or {"data": []})
        self.assertEqual(len(fetched), 1)
        self.assertIn("misc=yes", fetched[0])
        self.assertNotIn("format=", fetched[0])

    def test_failure_keeps_existing_and_offline_cache(self):
        """失敗指明 ocg-dates 來源且不毀既有檔;offline 沿用快取、缺檔報錯。"""
        with self.assertRaises(RuntimeError) as ctx:
            download_ocg_dates(self.dir, fetch_json=None, offline=True)
        self.assertIn("ocg-dates", str(ctx.exception))
        dump = {"data": [{"id": 1, "misc_info": [{"ocg_date": "2014-03-21"}]}]}
        path = download_ocg_dates(self.dir, fetch_json=lambda url: dump)
        def boom(url):
            raise OSError("boom")
        with self.assertRaises(RuntimeError) as ctx:
            download_ocg_dates(self.dir, fetch_json=boom)
        self.assertIn("ocg-dates", str(ctx.exception))
        with open(path, encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"1": "2014-03-21"})
        self.assertEqual(
            download_ocg_dates(self.dir, fetch_json=None, offline=True), path)


class CheckOcgDateCoverageTest(unittest.TestCase):
    """更新後的首發日覆蓋率回報:有日期/查無日期張數,異圖歸主卡。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "ocg-dates.json")

    @staticmethod
    def _card(id_, alt_ids=()):
        return {"id": id_, "alt_ids": list(alt_ids)}

    def test_reports_dated_and_missing_counts(self):
        """主卡直接對到、異圖對到都算有日期;對不到的計入查無日期。"""
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump({"111": "2004-01-01", "223": "2015-06-20"}, f)
        lines = check_ocg_date_coverage(
            [self._card(111), self._card(222, alt_ids=[223]),
             self._card(333)], self.path)
        text = "\n".join(lines)
        self.assertIn("2 張", text)  # 有日期
        self.assertIn("1 張", text)  # 查無日期
        self.assertIn("三級分類報表", text)  # 指出查無日期的卡歸「日期不明」

    def test_missing_source_file_skips_check(self):
        """尚未抓過首發日來源:略過回報而非報錯。"""
        lines = check_ocg_date_coverage(
            [self._card(111)], os.path.join(self.tmp.name, "nope.json"))
        self.assertIn("略過", "\n".join(lines))


class DownloadBanlistsTest(unittest.TestCase):
    """OCG 禁限來源:自 YGOPRODeck 禁限端點萃取 {密碼: 原始禁限值}。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = self.tmp.name

    def test_extracts_password_status_map(self):
        """各賽制端點的 dump → {密碼: 原始值};缺該賽制欄位的條目略過。"""
        dumps = {
            "ocg": {"data": [
                {"id": 21044178, "banlist_info": {"ban_ocg": "Forbidden"}},
                {"id": 23434538, "banlist_info": {"ban_ocg": "Limited"}},
                {"id": 4031928, "banlist_info": {"ban_goat": "Forbidden"}},
            ]},
            "tcg": {"data": [
                {"id": 23434538, "banlist_info": {"ban_tcg": "Forbidden"}},
                {"id": 4031928, "banlist_info": {"ban_goat": "Forbidden"}},
            ]},
        }
        def fetch_json(url):
            return dumps[url.split("banlist=")[1]]
        paths = download_banlists(self.dir, fetch_json=fetch_json)
        self.assertEqual(set(paths), {"ocg", "tcg"})
        self.assertEqual(set(paths), set(BANLIST_FORMATS))
        with open(paths["ocg"], encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"21044178": "Forbidden",
                                            "23434538": "Limited"})
        with open(paths["tcg"], encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"23434538": "Forbidden"})

    def test_fetches_each_format_endpoint(self):
        """每個賽制打自己的端點(banlist=ocg / …)。"""
        fetched = []
        download_banlists(
            self.dir,
            fetch_json=lambda url: fetched.append(url) or {"data": []})
        for fmt in BANLIST_FORMATS:
            self.assertTrue(any(f"banlist={fmt}" in url for url in fetched),
                            f"{fmt} 端點沒有被抓")

    def test_failure_keeps_existing_and_offline_cache(self):
        """失敗指明禁限來源且不毀既有檔;offline 沿用快取、缺檔報錯。"""
        with self.assertRaises(RuntimeError) as ctx:
            download_banlists(self.dir, fetch_json=None, offline=True)
        self.assertIn("banlist", str(ctx.exception))
        dump = {"data": [{"id": 1, "banlist_info": {"ban_ocg": "Limited"}}]}
        paths = download_banlists(self.dir, fetch_json=lambda url: dump)
        def boom(url):
            raise OSError("boom")
        with self.assertRaises(RuntimeError) as ctx:
            download_banlists(self.dir, fetch_json=boom)
        self.assertIn("banlist", str(ctx.exception))
        with open(paths["ocg"], encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"1": "Limited"})
        self.assertEqual(
            download_banlists(self.dir, fetch_json=None, offline=True), paths)


class CheckFaqGapTest(unittest.TestCase):
    """差值更新後的官方 Q&A 對帳:純本地比對,只回報不自動補爬。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.faq_path = os.path.join(self.tmp.name, "faq_info.json")

    def _write_faq(self, entries):
        with open(self.faq_path, "w", encoding="utf-8") as f:
            json.dump(entries, f)

    @staticmethod
    def _card(id_, ot=1, name_ja="カード"):
        return {"id": id_, "ot": ot, "alt_ids": [], "name_ja": name_ja,
                "name_zh": "卡"}

    def test_missing_cards_reported_with_refill_hint(self):
        """有缺口:報張數、列出卡,並指出用哪支腳本補齊。"""
        self._write_faq([{"cid": 1, "password": 111}])
        lines = check_faq_gap([self._card(111), self._card(222, name_ja="新卡")],
                              self.faq_path)
        text = "\n".join(lines)
        self.assertIn("1 張", text)
        self.assertIn("222", text)
        self.assertIn("新卡", text)
        self.assertIn("refill_faq.py", text)

    def test_no_gap_reports_clean_without_hint(self):
        """無缺口:不提補齊指令,免得每次更新都像有事要做。"""
        self._write_faq([{"cid": 1, "password": 111}])
        lines = check_faq_gap([self._card(111)], self.faq_path)
        text = "\n".join(lines)
        self.assertIn("無缺口", text)
        self.assertNotIn("refill_faq.py", text)

    def test_tcg_only_cards_not_counted_as_gap(self):
        """TCG 限定卡官方無日文頁,不算缺口。"""
        self._write_faq([])
        lines = check_faq_gap([self._card(111, ot=2)], self.faq_path)
        self.assertIn("無缺口", "\n".join(lines))

    def test_missing_faq_json_skips_check(self):
        """尚未建過 faq_info.json:略過對帳而非報錯。"""
        lines = check_faq_gap([self._card(111)],
                              os.path.join(self.tmp.name, "nope.json"))
        self.assertIn("略過", "\n".join(lines))


if __name__ == "__main__":
    unittest.main()
