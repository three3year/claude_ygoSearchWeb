"""來源檔雜湊:五支薄殼共用同一算法(sha256 前 16 hex)。"""
import hashlib
import os
import tempfile
import unittest

from digest import file_digest


class FileDigestTest(unittest.TestCase):

    def test_sha256_prefix_of_file_bytes(self):
        data = "卡片總表\n".encode("utf-8") * 3
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "cards.json")
            with open(path, "wb") as f:
                f.write(data)
            self.assertEqual(file_digest(path), hashlib.sha256(data).hexdigest()[:16])
            self.assertEqual(len(file_digest(path)), 16)


if __name__ == "__main__":
    unittest.main()
