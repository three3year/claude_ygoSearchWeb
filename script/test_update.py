"""來源下載殼測試:注入假 fetch,不實際連網。"""
import os
import tempfile
import unittest

from update_cards import SOURCES, download_sources


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


if __name__ == "__main__":
    unittest.main()
