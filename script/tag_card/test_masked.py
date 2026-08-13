"""遮蔽測試模組的測試。

兩個接縫:
  masked.sample_masked(標記表, 卡片總表, 補足情報, ...) → (樣本, 報告)
  masked.score_masked(標記表, 樣本, 判定[, 已知歧義, 管線缺陷]) → 報告

fixture 於測試內程式化建立,不碰網路與真實資料檔(與 test_tagcard.py 同規)。
"""
import unittest

import masked
from official import (KIND_CONTINUOUS, KIND_IGNITION, KIND_NON_EFFECT,
                      KIND_QUICK, KIND_TRIGGER, KIND_UNCLASSIFIED)

SEED = 20260809


def clause(index="①", section="main", kind=KIND_TRIGGER, source="official",
           text_zh="繁中", text_ja="日文"):
    return {"index": index, "section": section, "text_zh": text_zh,
            "text_ja": text_ja, "text_hash": "0", "kind": kind,
            "optional": None, "role": None, "source": source,
            "needs_review": False, "rule_predicted": None,
            "confidence": "high", "tags": []}


def entry(cid=1000, clauses=None):
    return {"id": cid, "clauses": list(clauses or [])}


def card(cid=1000, name_zh="測試卡", name_ja="テストカード"):
    return {"id": cid, "name_zh": name_zh, "name_ja": name_ja}


def faq(password=1000, supplement="", pen_supplement=""):
    return {"password": password, "name_ja": "テストカード",
            "supplement": supplement, "pen_supplement": pen_supplement}


def pool(kind, count, start=1000, source="official"):
    """同一類型的 count 張單效果卡,卡片密碼由 start 起算。"""
    entries = [entry(start + i, [clause(kind=kind, source=source,
                                        text_ja=f"日文{start + i}")])
               for i in range(count)]
    return entries, [card(start + i) for i in range(count)], \
        [faq(start + i) for i in range(count)]


def population(*specs):
    """[(類型, 張數), ...] → (標記表, 卡片總表, 補足情報)。"""
    entries, cards, faqs = [], [], []
    start = 1000
    for kind, count in specs:
        e, c, f = pool(kind, count, start=start)
        entries += e
        cards += c
        faqs += f
        start += count
    return entries, cards, faqs


def key(row):
    return (row["id"], row["section"], row["index"])


def answer(row, kind):
    return {"id": row["id"], "section": row["section"], "index": row["index"],
            "kind": kind}


class SamplingTest(unittest.TestCase):
    """抽樣:只抽官方明示、六類分層、不足者全取。"""

    def test_只抽官方明示的效果句(self):
        entries = [entry(1000, [clause(source="official"),
                                clause(index="②", source="rule"),
                                clause(index="③", source=None)])]
        sample, _ = masked.sample_masked(entries, [card(1000)], [faq(1000)],
                                         size=3, per_kind_min=1, seed=SEED)
        self.assertEqual([row["index"] for row in sample], ["①"])

    def test_六類各抽滿下限(self):
        entries, cards, faqs = population(
            (KIND_TRIGGER, 50), (KIND_IGNITION, 50), (KIND_CONTINUOUS, 50),
            (KIND_QUICK, 50), (KIND_NON_EFFECT, 50), (KIND_UNCLASSIFIED, 50))
        sample, report = masked.sample_masked(entries, cards, faqs, size=60,
                                              per_kind_min=10, seed=SEED)
        self.assertEqual(len(sample), 60)
        for kind in masked.KINDS:
            self.assertGreaterEqual(report["taken"][kind], 10)
        self.assertEqual(report["shortfall"], [])

    def test_不足下限的類別全取並記進報告(self):
        entries, cards, faqs = population(
            (KIND_TRIGGER, 50), (KIND_UNCLASSIFIED, 3))
        sample, report = masked.sample_masked(entries, cards, faqs, size=20,
                                              per_kind_min=10, seed=SEED)
        self.assertEqual(report["taken"][KIND_UNCLASSIFIED], 3)
        self.assertEqual(report["population"][KIND_UNCLASSIFIED], 3)
        self.assertIn(KIND_UNCLASSIFIED, report["shortfall"])
        self.assertEqual(len(sample), 20)

    def test_剩餘配額依母體比例分配(self):
        entries, cards, faqs = population(
            (KIND_TRIGGER, 100), (KIND_UNCLASSIFIED, 20))
        _, report = masked.sample_masked(entries, cards, faqs, size=30,
                                         per_kind_min=10, seed=SEED)
        # 下限 10+10 之後多出的 10 條,母體大的那一類該拿到多數
        self.assertGreater(report["taken"][KIND_TRIGGER],
                           report["taken"][KIND_UNCLASSIFIED])

    def test_母體不足時抽到多少算多少(self):
        entries, cards, faqs = population((KIND_TRIGGER, 5))
        sample, report = masked.sample_masked(entries, cards, faqs, size=300,
                                              per_kind_min=40, seed=SEED)
        self.assertEqual(len(sample), 5)
        self.assertEqual(report["size"], 5)

    def test_每類下限的總和超過size時下限優先(self):
        entries, cards, faqs = population(
            (KIND_TRIGGER, 50), (KIND_IGNITION, 50))
        sample, report = masked.sample_masked(entries, cards, faqs, size=30,
                                              per_kind_min=20, seed=SEED)
        self.assertEqual(len(sample), 40)  # 逐類別的分母不為了湊總數被砍
        self.assertEqual(report["requested_size"], 30)
        self.assertEqual(report["per_kind_min"], 20)

    def test_排除的卡整張不抽(self):
        entries, cards, faqs = population((KIND_TRIGGER, 10))
        sample, report = masked.sample_masked(
            entries, cards, faqs, size=10, per_kind_min=1, seed=SEED,
            exclude_ids=[1000, 1001, 1002])
        self.assertEqual(len(sample), 7)
        self.assertEqual(report["population"][KIND_TRIGGER], 7)
        self.assertEqual(report["excluded_ids"], 3)
        self.assertNotIn(1000, [row["id"] for row in sample])

    def test_排除是整張卡而不是單一效果句(self):
        entries = [entry(1000, [clause(index="①"), clause(index="②")]),
                   entry(1001, [clause(index="①")])]
        cards = [card(1000), card(1001)]
        faqs = [faq(1000), faq(1001)]
        sample, _ = masked.sample_masked(entries, cards, faqs, size=10,
                                         per_kind_min=1, seed=SEED,
                                         exclude_ids=[1000])
        self.assertEqual([row["id"] for row in sample], [1001])

    def test_先前輪次的樣本排掉之後兩輪互斥(self):
        entries, cards, faqs = population((KIND_TRIGGER, 40))
        first, _ = masked.sample_masked(entries, cards, faqs, size=10,
                                        per_kind_min=1, seed=SEED)
        second, _ = masked.sample_masked(
            entries, cards, faqs, size=10, per_kind_min=1, seed=SEED,
            exclude_ids=[row["id"] for row in first])
        self.assertEqual(len(second), 10)
        self.assertEqual(set(key(r) for r in first)
                         & set(key(r) for r in second), set())

    def test_同一組輸入與種子抽出同一份樣本(self):
        entries, cards, faqs = population(
            (KIND_TRIGGER, 50), (KIND_IGNITION, 50))
        first, _ = masked.sample_masked(entries, cards, faqs, size=20,
                                        per_kind_min=5, seed=SEED)
        second, _ = masked.sample_masked(entries, cards, faqs, size=20,
                                         per_kind_min=5, seed=SEED)
        self.assertEqual([key(r) for r in first], [key(r) for r in second])

    def test_樣本依卡片密碼穩定排序(self):
        entries, cards, faqs = population((KIND_TRIGGER, 50))
        sample, _ = masked.sample_masked(entries, cards, faqs, size=20,
                                         per_kind_min=5, seed=SEED)
        self.assertEqual([key(r) for r in sample],
                         sorted(key(r) for r in sample))

    def test_樣本不帶任何答案欄位(self):
        entries, cards, faqs = population((KIND_TRIGGER, 10))
        sample, _ = masked.sample_masked(entries, cards, faqs, size=5,
                                         per_kind_min=1, seed=SEED)
        for row in sample:
            self.assertEqual(set(row), set(masked.SAMPLE_FIELDS))

    def test_樣本帶卡名與繁中日文原文(self):
        entries = [entry(1000, [clause(text_zh="繁中文", text_ja="日本文")])]
        cards = [card(1000, name_zh="卡名", name_ja="カード名")]
        sample, _ = masked.sample_masked(entries, cards, [], size=1,
                                         per_kind_min=1, seed=SEED)
        self.assertEqual(sample[0]["name_zh"], "卡名")
        self.assertEqual(sample[0]["name_ja"], "カード名")
        self.assertEqual(sample[0]["text_zh"], "繁中文")
        self.assertEqual(sample[0]["text_ja"], "日本文")

    def test_樣本帶同卡同段的前言段(self):
        """§5.6 閘門二第三種:跨回合許可可能只寫在前言段,樣本要帶得過去。"""
        entries = [entry(1000, [
            clause(index="0", kind=KIND_NON_EFFECT, text_ja="前言段の日本文"),
            clause(index="②", text_ja="②：日本文"),
        ])]
        sample, _ = masked.sample_masked(entries, [card(1000)], [], size=2,
                                         per_kind_min=1, seed=SEED)
        rows = {row["index"]: row for row in sample}
        self.assertEqual(rows["②"]["preamble"], "前言段の日本文")
        self.assertEqual(rows["0"]["preamble"], "")

    def test_沒有前言段時留空(self):
        entries = [entry(1000, [clause(index="②")])]
        sample, _ = masked.sample_masked(entries, [card(1000)], [], size=1,
                                         per_kind_min=1, seed=SEED)
        self.assertEqual(sample[0]["preamble"], "")

    def test_前言段不跨段落取(self):
        """靈擺段的行不會拿到怪獸段的前言段。"""
        entries = [entry(1000, [
            clause(index="0", kind=KIND_NON_EFFECT, text_ja="怪獸段の前言"),
            clause(index="①", section="pendulum", text_ja="P①：日本文"),
        ])]
        sample, _ = masked.sample_masked(entries, [card(1000)], [], size=2,
                                         per_kind_min=1, seed=SEED)
        rows = {(row["section"], row["index"]): row for row in sample}
        self.assertEqual(rows[("pendulum", "①")]["preamble"], "")

    def test_靈擺段取靈擺補足情報(self):
        entries = [entry(1000, [clause(section="pendulum")])]
        faqs = [faq(1000, supplement="■怪獸段的補足。",
                    pen_supplement="■靈擺段的補足。")]
        sample, _ = masked.sample_masked(entries, [card(1000)], faqs, size=1,
                                         per_kind_min=1, seed=SEED)
        self.assertEqual(sample[0]["supplement"], "■靈擺段的補足。")


class MaskingTest(unittest.TestCase):
    """遮蔽:類型結論句消失,其餘補足情報原樣保留。"""

    def mask(self, supplement):
        entries = [entry(1000, [clause()])]
        sample, _ = masked.sample_masked(entries, [card(1000)],
                                         [faq(1000, supplement=supplement)],
                                         size=1, per_kind_min=1, seed=SEED)
        return sample[0]["supplement"]

    def test_類型結論句整句消失(self):
        for word in ("誘発即時効果", "誘発効果", "起動効果", "永続効果"):
            self.assertEqual(self.mask(f"■フィールドで発動する{word}です。"), "")

    def test_否定句形式的類型結論同樣消失(self):
        self.assertEqual(
            self.mask("■起動効果・誘発効果・誘発即時効果・永続効果の"
                      "いずれにも分類されない効果です。"), "")

    def test_效果外文本的官方明示消失(self):
        self.assertEqual(self.mask("■効果として扱いません。"), "")

    def test_效果外文本的八種變體都消失(self):
        """票10 認的八種等義寫法,遮蔽也要全認——只認一種等於漏遮官方答案。"""
        for tail in ("効果として扱いません", "効果として扱われません",
                     "効果としては扱いません", "効果としては扱われません",
                     "効果としての扱いではありません", "効果としての扱いません",
                     "効果の扱いではありません", "効果の扱いにはなりません"):
            self.assertEqual(self.mask(f"■『①：〜』は{tail}。"), "", tail)

    def test_效果後面夾了別的詞的不算結論句(self):
        """『効果で破壊された扱いにはなりません』講的是別件事,不得遮掉。"""
        for line in ("■このカードは効果で破壊された扱いにはなりません。",
                     "■このダメージは効果ダメージの扱いではありません。"):
            self.assertEqual(self.mask(line), line)

    def test_必發明示消失(self):
        self.assertEqual(self.mask("■必ず発動する効果です。"), "")

    def test_非結論句原樣保留(self):
        line = "■このカードの効果でセットしたカードは、セットしたターンには発動できません。"
        self.assertEqual(self.mask(line), line)

    def test_同一行只遮結論句其餘留著(self):
        self.assertEqual(
            self.mask("■このカードは手札から発動します。"
                      "モンスターゾーンで発動できる起動効果です。"),
            "■このカードは手札から発動します。")

    def test_括號裡的結論句遮掉後不留孤零零的括號(self):
        self.assertEqual(
            self.mask("■モンスターゾーンで発動する誘発効果です。"
                      "（必ず発動する効果です。）"), "")
        self.assertEqual(
            self.mask("■手札で使えます。（必ず発動する効果です。）"),
            "■手札で使えます。")

    def test_標頭保留而同一行的結論消失(self):
        self.assertEqual(
            self.mask("【①の効果について】\n■発動できる起動効果です。"),
            "【①の効果について】")
        self.assertEqual(
            self.mask("【①の効果について】■発動できる起動効果です。"),
            "【①の効果について】")

    def test_禁用句型連同其中的類型詞一起遮掉(self):
        self.assertEqual(self.mask("■永続効果ではありません。"), "")

    def test_沒有補足情報時為空字串(self):
        entries = [entry(1000, [clause()])]
        sample, _ = masked.sample_masked(entries, [card(1000)], [], size=1,
                                         per_kind_min=1, seed=SEED)
        self.assertEqual(sample[0]["supplement"], "")


class ScoringTest(unittest.TestCase):
    """對答案:逐類別 recall、錯判清單、已知歧義不計入分母。"""

    def fixture(self, *kinds):
        entries = [entry(1000 + i, [clause(kind=kind, text_ja=f"日文{i}")])
                   for i, kind in enumerate(kinds)]
        sample = [{"id": 1000 + i, "section": "main", "index": "①",
                   "name_zh": "卡", "name_ja": "カード", "text_zh": "繁",
                   "text_ja": f"日文{i}", "supplement": ""}
                  for i, _ in enumerate(kinds)]
        return entries, sample

    def test_全對時逐類別recall為一且通過(self):
        entries, sample = self.fixture(KIND_TRIGGER, KIND_IGNITION)
        answers = [answer(sample[0], KIND_TRIGGER),
                   answer(sample[1], KIND_IGNITION)]
        report = masked.score_masked(entries, sample, answers)
        self.assertEqual(report["per_kind"][KIND_TRIGGER]["recall"], 1.0)
        self.assertEqual(report["per_kind"][KIND_IGNITION]["recall"], 1.0)
        self.assertEqual(report["overall"]["accuracy"], 1.0)
        self.assertTrue(report["passed"])

    def test_錯判列出類型與句型且拉低該類recall(self):
        entries, sample = self.fixture(KIND_TRIGGER, KIND_TRIGGER)
        answers = [answer(sample[0], KIND_TRIGGER),
                   answer(sample[1], KIND_CONTINUOUS)]
        report = masked.score_masked(entries, sample, answers)
        self.assertEqual(report["per_kind"][KIND_TRIGGER]["recall"], 0.5)
        self.assertFalse(report["passed"])
        self.assertEqual(len(report["errors"]), 1)
        error = report["errors"][0]
        self.assertEqual(error["official"], KIND_TRIGGER)
        self.assertEqual(error["answered"], KIND_CONTINUOUS)
        self.assertEqual(error["text_ja"], "日文1")

    def test_留空不算答對且另立清單(self):
        entries, sample = self.fixture(KIND_TRIGGER)
        report = masked.score_masked(entries, sample,
                                     [answer(sample[0], None)])
        self.assertEqual(report["per_kind"][KIND_TRIGGER]["recall"], 0.0)
        self.assertEqual(len(report["blank"]), 1)
        self.assertEqual(len(report["errors"]), 1)
        self.assertFalse(report["passed"])

    def test_未出現的類別不列入逐類別報告(self):
        entries, sample = self.fixture(KIND_TRIGGER)
        report = masked.score_masked(entries, sample,
                                     [answer(sample[0], KIND_TRIGGER)])
        self.assertNotIn(KIND_QUICK, report["per_kind"])

    def test_少答一條進missing且判定不通過(self):
        entries, sample = self.fixture(KIND_TRIGGER, KIND_IGNITION)
        report = masked.score_masked(entries, sample,
                                     [answer(sample[0], KIND_TRIGGER)])
        self.assertEqual(len(report["missing"]), 1)
        self.assertFalse(report["passed"])

    def test_多答一條進extra且判定不通過(self):
        entries, sample = self.fixture(KIND_TRIGGER)
        answers = [answer(sample[0], KIND_TRIGGER),
                   {"id": 9999, "section": "main", "index": "①",
                    "kind": KIND_TRIGGER}]
        report = masked.score_masked(entries, sample, answers)
        self.assertEqual(len(report["extra"]), 1)
        self.assertFalse(report["passed"])

    def test_值域外的類型進invalid且判定不通過(self):
        entries, sample = self.fixture(KIND_TRIGGER)
        report = masked.score_masked(entries, sample,
                                     [answer(sample[0], "沒有這種類型")])
        self.assertEqual(len(report["invalid"]), 1)
        self.assertEqual(report["blank"], [])  # 值域外不是「留空」
        self.assertFalse(report["passed"])

    def test_對不回標記表的樣本行進stale且不計入分母(self):
        entries, sample = self.fixture(KIND_TRIGGER)
        sample.append({"id": 4242, "section": "main", "index": "①",
                       "name_zh": "卡", "name_ja": "カード", "text_zh": "繁",
                       "text_ja": "日", "supplement": ""})
        report = masked.score_masked(entries, sample,
                                     [answer(sample[0], KIND_TRIGGER)])
        self.assertEqual(len(report["stale"]), 1)
        self.assertEqual(report["per_kind"][KIND_TRIGGER]["scored"], 1)
        self.assertEqual(report["missing"], [])
        self.assertFalse(report["passed"])

    def test_日文原文變了的樣本行進stale且不計入分母(self):
        """票16:拆句把 `●` 切出去之後,母句剩下的已經不是判定者看過的那一段。

        鍵還在,但那一行的身分變了——拿舊答案對新句子會把管線的改動記成判定
        錯誤,那是最難察覺的一種假訊號。
        """
        entries, sample = self.fixture(KIND_TRIGGER, KIND_TRIGGER)
        entries[1]["clauses"][0]["text_ja"] += "●子效果。"
        report = masked.score_masked(entries, sample,
                                     [answer(sample[0], KIND_TRIGGER),
                                      answer(sample[1], KIND_CONTINUOUS)])
        self.assertEqual(len(report["stale"]), 1)
        self.assertEqual(report["per_kind"][KIND_TRIGGER]["scored"], 1)
        self.assertEqual(report["errors"], [])  # 不記成判定錯誤
        self.assertEqual(report["extra"], [])   # 答了不算多判
        self.assertFalse(report["passed"])

    def test_官方答案被撤回的樣本行不計入分母也不判不通過(self):
        entries, sample = self.fixture(KIND_TRIGGER, KIND_TRIGGER)
        entries[1]["clauses"][0]["kind"] = None  # 票11 撤掉未拆整團的官方明示
        report = masked.score_masked(entries, sample,
                                     [answer(sample[0], KIND_TRIGGER)])
        self.assertEqual(len(report["withdrawn"]), 1)
        self.assertEqual(report["per_kind"][KIND_TRIGGER]["scored"], 1)
        self.assertEqual(report["missing"], [])  # 撤回的行不答不算漏判
        self.assertEqual(report["stale"], [])    # key 還在,不是樣本過期
        self.assertTrue(report["passed"])

    def test_判定填回來的類型不是標準答案(self):
        """票11 撤掉的官方明示,票13 拆完會以 llm 填回來。

        那是判定者自己的產出——拿它當標準答案等於讓判定者跟自己對答案,分數會
        虛高。標準答案只認 source: "official"(見 sample_masked)。
        """
        entries, sample = self.fixture(KIND_TRIGGER, KIND_TRIGGER)
        judged = entries[1]["clauses"][0]
        judged["kind"], judged["source"] = KIND_CONTINUOUS, "llm"
        report = masked.score_masked(entries, sample,
                                     [answer(sample[0], KIND_TRIGGER)])
        self.assertEqual(len(report["withdrawn"]), 1)
        self.assertEqual(report["per_kind"][KIND_TRIGGER]["scored"], 1)
        self.assertNotIn(KIND_CONTINUOUS, report["per_kind"])
        self.assertEqual(report["stale"], [])
        self.assertTrue(report["passed"])

    def test_雙重確認的行仍然不是標準答案(self):
        """llm_then_rule 是判定 + 規則,兩個都不是官方。"""
        entries, sample = self.fixture(KIND_TRIGGER)
        entries[0]["clauses"][0]["source"] = "llm_then_rule"
        report = masked.score_masked(entries, sample, [])
        self.assertEqual(len(report["withdrawn"]), 1)
        self.assertEqual(report["missing"], [])

    def test_答了官方答案已撤回的行不算多判(self):
        entries, sample = self.fixture(KIND_TRIGGER, KIND_TRIGGER)
        entries[1]["clauses"][0]["kind"] = None
        answers = [answer(sample[0], KIND_TRIGGER),
                   answer(sample[1], KIND_CONTINUOUS)]
        report = masked.score_masked(entries, sample, answers)
        self.assertEqual(report["extra"], [])
        self.assertEqual(report["overall"]["scored"], 1)
        self.assertTrue(report["passed"])

    def test_已知歧義不計入分母(self):
        entries, sample = self.fixture(KIND_TRIGGER, KIND_TRIGGER)
        answers = [answer(sample[0], KIND_TRIGGER),
                   answer(sample[1], KIND_CONTINUOUS)]
        ambiguous = [{"id": sample[1]["id"], "section": "main", "index": "①",
                      "reason": "官方在同款句型上兩種都判過"}]
        report = masked.score_masked(entries, sample, answers, ambiguous)
        self.assertEqual(report["per_kind"][KIND_TRIGGER]["scored"], 1)
        self.assertEqual(report["per_kind"][KIND_TRIGGER]["recall"], 1.0)
        self.assertEqual(report["errors"], [])
        self.assertTrue(report["passed"])

    def test_管線缺陷不計入分母且與歧義分開記(self):
        entries, sample = self.fixture(KIND_TRIGGER, KIND_TRIGGER)
        answers = [answer(sample[0], KIND_TRIGGER),
                   answer(sample[1], KIND_CONTINUOUS)]
        pipeline = [{"id": sample[1]["id"], "section": "main", "index": "①",
                     "reason": "官方類型講的是還沒拆開的子效果"}]
        report = masked.score_masked(entries, sample, answers, (), pipeline)
        self.assertEqual(len(report["pipeline"]), 1)
        self.assertEqual(report["ambiguous"], [])  # 兩個桶不混
        self.assertEqual(report["per_kind"][KIND_TRIGGER]["scored"], 1)
        self.assertEqual(report["per_kind"][KIND_TRIGGER]["pipeline"], 1)
        self.assertEqual(report["errors"], [])
        self.assertTrue(report["passed"])

    def test_管線缺陷超過上限時停下(self):
        kinds = [KIND_TRIGGER] * 7
        entries, sample = self.fixture(*kinds)
        answers = [answer(row, KIND_TRIGGER) for row in sample]
        pipeline = [{"id": row["id"], "section": "main", "index": "①",
                     "reason": "管線"} for row in sample[:6]]
        report = masked.score_masked(entries, sample, answers, (), pipeline)
        self.assertFalse(report["passed"])

    def test_已知歧義超過上限時停下(self):
        kinds = [KIND_TRIGGER] * 7
        entries, sample = self.fixture(*kinds)
        answers = [answer(row, KIND_TRIGGER) for row in sample]
        ambiguous = [{"id": row["id"], "section": "main", "index": "①",
                      "reason": "歧義"} for row in sample[:6]]
        report = masked.score_masked(entries, sample, answers, ambiguous)
        self.assertTrue(report["over_cap"]["ambiguous"])
        self.assertFalse(report["passed"])

    def test_兩個桶的上限各報各的(self):
        """歧義 0 條的一輪不該因為管線超限而被印成歧義超限。"""
        entries, sample = self.fixture(*([KIND_TRIGGER] * 7))
        answers = [answer(row, KIND_TRIGGER) for row in sample]
        pipeline = [{"id": row["id"], "section": "main", "index": "①",
                     "reason": "管線"} for row in sample[:6]]
        report = masked.score_masked(entries, sample, answers, (), pipeline)
        self.assertTrue(report["over_cap"]["pipeline"])
        self.assertFalse(report["over_cap"]["ambiguous"])

    def test_不在樣本內的已知歧義進報告(self):
        entries, sample = self.fixture(KIND_TRIGGER)
        ambiguous = [{"id": 4242, "section": "main", "index": "①",
                      "reason": "歧義"}]
        report = masked.score_masked(entries, sample,
                                     [answer(sample[0], KIND_TRIGGER)],
                                     ambiguous)
        self.assertEqual(len(report["unknown"]["ambiguous"]), 1)
        self.assertEqual(report["unknown"]["pipeline"], [])
        self.assertFalse(report["passed"])

    def test_不在樣本內的管線缺陷歸管線那一桶(self):
        """管線缺陷與歧義分開記,報成「歧義不在樣本內」會誤導分流。"""
        entries, sample = self.fixture(KIND_TRIGGER)
        pipeline = [{"id": 4242, "section": "main", "index": "①",
                     "reason": "管線"}]
        report = masked.score_masked(entries, sample,
                                     [answer(sample[0], KIND_TRIGGER)],
                                     (), pipeline)
        self.assertEqual(len(report["unknown"]["pipeline"]), 1)
        self.assertEqual(report["unknown"]["ambiguous"], [])
        self.assertFalse(report["passed"])

    def test_總體準確率照算但不影響通過與否(self):
        entries, sample = self.fixture(KIND_TRIGGER, KIND_TRIGGER,
                                       KIND_TRIGGER, KIND_IGNITION)
        answers = [answer(sample[0], KIND_TRIGGER),
                   answer(sample[1], KIND_TRIGGER),
                   answer(sample[2], KIND_TRIGGER),
                   answer(sample[3], KIND_TRIGGER)]
        report = masked.score_masked(entries, sample, answers)
        self.assertEqual(report["overall"]["accuracy"], 0.75)
        # 誘發效果(1速)三條全中,但啟動效果 0/1 —— 逐類別才是門檻
        self.assertEqual(report["per_kind"][KIND_TRIGGER]["recall"], 1.0)
        self.assertEqual(report["per_kind"][KIND_IGNITION]["recall"], 0.0)
        self.assertFalse(report["passed"])


if __name__ == "__main__":
    unittest.main()
