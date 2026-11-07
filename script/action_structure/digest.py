"""來源檔雜湊:各 CLI 薄殼印到 stdout 的 digest 都用同一算法(sha256 前 16 hex),
看得出報告或產物是哪份輸入生出來的。只印不寫進產物與報告正文。"""
import hashlib


def file_digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]
