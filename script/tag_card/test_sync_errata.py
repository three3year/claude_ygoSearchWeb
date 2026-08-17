"""卡文勘誤下游同步的測試。

接縫:`sync_errata_texts.sync_texts(勘誤表, 拆句表, 標記表) → report`,就地修改。
fixture 於測試內程式化建立(先例:test_tagcard.py 的拆句 fixture 以 split_hash
現算雜湊,雜湊因此自然一致)。
"""
import unittest

from sync_errata_texts import sync_texts
from tagcard import _text_hash, split_hash

ZH_A = "解放2隻怪獸上級召喚成功時，可以從以下效果選擇1個效果發動。"
ZH_A_FIXED = "解放2隻怪獸上級召喚成功時，從以下效果選擇1個效果發動。"
ZH_B = "●場上的卡全部破壞。"
JA_A = "アドバンス召喚に成功した時、以下の効果から１つを選択して発動する。"
JA_B = "●フィールド上のカードを全て破壊する。"
ERRATA = [{"id": 84488827, "from": "可以從以下效果", "to": "從以下效果"}]


def split_record(zh_segs, ja_segs, **kw):
    record = {"id": 84488827, "section": "main", "ticket": "票33",
              "text_hash": split_hash("".join(zh_segs), "".join(ja_segs)),
              "segments": [{"index": str(i + 1), "text_zh": z, "text_ja": j}
                           for i, (z, j) in enumerate(zip(zh_segs, ja_segs))]}
    record.update(kw)
    return record


def tag_entry(zh, ja):
    return {"id": 84488827, "clauses": [{
        "index": "1", "section": "main", "text_zh": zh, "text_ja": ja,
        "text_hash": _text_hash(ja, zh), "kind": "誘發效果(1速)",
        "optional": "必發", "source": "official"}]}


class SyncErrataTest(unittest.TestCase):
    def test_sync_replaces_and_rehashes(self):
        """段落與標記行替換文字;拆句雜湊重算,日文基礎的標記雜湊不變。"""
        splits = [split_record([ZH_A, ZH_B], [JA_A, JA_B])]
        tags = [tag_entry(ZH_A + "\n" + ZH_B, JA_A + JA_B)]
        old_tag_hash = tags[0]["clauses"][0]["text_hash"]
        report = sync_texts(ERRATA, splits, tags)
        self.assertEqual(report["problems"], [])
        self.assertEqual(report["splits_changed"], 1)
        self.assertEqual(report["clauses_changed"], 1)
        seg = splits[0]["segments"][0]
        self.assertEqual(seg["text_zh"], ZH_A_FIXED)
        self.assertEqual(splits[0]["text_hash"],
                         split_hash(ZH_A_FIXED + ZH_B, JA_A + JA_B))
        clause = tags[0]["clauses"][0]
        self.assertEqual(clause["text_zh"], ZH_A_FIXED + "\n" + ZH_B)
        self.assertEqual(clause["text_hash"], old_tag_hash)  # 判定基礎是日文
        self.assertEqual(clause["optional"], "必發")  # 判定欄位原封不動

    def test_idempotent(self):
        """重跑第二次:找不到原文子字串即無事,不報問題也不改動。"""
        splits = [split_record([ZH_A, ZH_B], [JA_A, JA_B])]
        tags = [tag_entry(ZH_A + "\n" + ZH_B, JA_A + JA_B)]
        sync_texts(ERRATA, splits, tags)
        report = sync_texts(ERRATA, splits, tags)
        self.assertEqual(report["problems"], [])
        self.assertEqual(report["splits_changed"], 0)
        self.assertEqual(report["clauses_changed"], 0)

    def test_from_across_split_point_fails(self):
        """原文子字串橫跨拆點 → 吵鬧失敗,不動資料。"""
        zh1 = "召喚成功時，可以"
        zh2 = "從以下效果選擇1個效果發動。"
        splits = [split_record([zh1, zh2], [JA_A, JA_B])]
        report = sync_texts(ERRATA, splits, [])
        self.assertEqual(report["splits_changed"], 0)
        self.assertTrue(any("橫跨拆點" in p for p in report["problems"]))
        self.assertEqual(splits[0]["segments"][0]["text_zh"], zh1)

    def test_unrebuildable_hash_fails(self):
        """紀錄雜湊無法由段落重建 → 不動這筆,報問題。"""
        splits = [split_record([ZH_A], [JA_A], text_hash="0000000000000000")]
        report = sync_texts(ERRATA, splits, [])
        self.assertTrue(any("無法由段落重建" in p for p in report["problems"]))
        self.assertEqual(splits[0]["segments"][0]["text_zh"], ZH_A)

    def test_zh_only_record_rehashes_zh(self):
        """繁中單側(ADR-0006):標記行雜湊以繁中計,同步後跟著換。"""
        tags = [tag_entry(ZH_A, "")]
        report = sync_texts(ERRATA, [], tags)
        self.assertEqual(report["clauses_changed"], 1)
        self.assertEqual(tags[0]["clauses"][0]["text_hash"],
                         _text_hash("", ZH_A_FIXED))


if __name__ == "__main__":
    unittest.main()
