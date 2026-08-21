"""來源下載殼測試:注入假 fetch,不實際連網。"""
import json
import os
import tempfile
import unittest

from update_cards import (SOURCES, check_faq_gap, download_all,
                          download_genesys, download_md_rarity,
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

    def test_paged_fetch_builds_password_rarity_map(self):
        """分頁抓到空頁為止,彙整成 {密碼: 稀有度} JSON;略過無效條目。"""
        pages = {
            1: [{"konamiID": "89631139", "rarity": "UR"},
                {"konamiID": "12345678", "rarity": "N"}],
            2: [{"konamiID": None, "rarity": "R"},        # 無密碼 → 略過
                {"konamiID": "23456789", "rarity": ""}],   # 無稀有度 → 略過
            3: [],
        }
        def fetch_json(url):
            page = int(url.split("page=")[1].split("&")[0])
            return pages[page]
        path = download_md_rarity(self.dir, fetch_json=fetch_json)
        with open(path, encoding="utf-8") as f:
            self.assertEqual(json.load(f),
                             {"12345678": "N", "89631139": "UR"})

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
            self.assertEqual(json.load(f), {"1": "N"})

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
        return [] if "page=" in url else self.genesys

    def test_all_sources_succeed_writes_record(self):
        download_all(self.dir, "2026-08-08T17:57:00+0800",
                     fetch=lambda url: b"cdb", fetch_json=self.fetch_json)
        with open(self.record, encoding="utf-8") as f:
            self.assertEqual(json.load(f)["downloaded_at"],
                             "2026-08-08T17:57:00+0800")

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
