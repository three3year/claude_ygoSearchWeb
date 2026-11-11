"""里程碑三摘要裁定要改的五個小項(m3b 票 07):「取り除けない」不再解析、召喚進推得表、
出發地含牌組/手牌/額外牌組的「選択して」記選擇、スキヤナー 的反向檢查模板、
數量恰好一張又沒寫比較對象的異同原子判不了。

走接縫一(查詢判斷)與接縫二(反向檢查);標準卡的官方文本逐字寫在測試裡
(`data/sources/` 不入版控)。
"""
import unittest

from action_query import run_query
from card_structure import build_structures
from reverse_check import check_card
from structure_shape import iter_segments
from test_golden import ARCHETYPES, card, faq


def build(cards, faqs, archetypes=ARCHETYPES):
    structures, _ = build_structures(cards, faqs, archetypes=archetypes)
    return structures


def own(structures, cid):
    return next(s for s in structures if s["id"] == cid)


def hit_segments(structures, cards, cid, **query):
    result = run_query(structures, cards, query)
    ids = next((h["segments"] for h in result["hits"] if h["id"] == cid), [])
    return [seg for b in own(structures, cid)["blocks"] for _, seg in iter_segments(b)
            if seg["id"] in ids]


def unparsed_texts(structures, cards, cid, **query):
    """查詢結果未解析組裡這張卡列出的段原文。"""
    result = run_query(structures, cards, query)
    entry = next((u for u in result["unparsed"] if u["id"] == cid), None)
    return [s["text"] for s in entry["segments"]] if entry else []


CRYSTAL_CORE = 22790789         # 巨大戦艦 クリスタル・コア
CRYSTAL_CORE_TEXT = (
    "①：このカードが召喚した場合に発動する。このカードにカウンターを３つ置く。\n"
    "②：このカードは戦闘では破壊されない。\n"
    "③：１ターンに１度、相手フィールドの表側攻撃表示モンスター１体を対象として発動できる。"
    "その相手の表側攻撃表示モンスターを表側守備表示にする。\n"
    "④：このカードが戦闘を行ったダメージステップ終了時に発動する。"
    "このカードのカウンターを１つ取り除く。取り除けない場合、このカードを破壊する。")


class CannotRemoveTest(unittest.TestCase):
    """去除的語尾沒有「けない」:「取り除けない場合」省略的受詞是前一句的計數器,
    照主語省略規則會記成此卡,所以那一段回到解析不出。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = [card(CRYSTAL_CORE, name_ja="巨大戦艦 クリスタル・コア", level=5,
                          race=0x20, attribute=0x2, atk=2100, setcode=0x15)]
        cls.structures = build(cls.cards, [faq(CRYSTAL_CORE, "巨大戦艦 クリスタル・コア",
                                               CRYSTAL_CORE_TEXT)])

    def test_cannot_remove_condition_is_unparsed(self):
        """開條件段查「去除,極性 不能」並指定此卡:不命中;那一段解析不出,
        開條件段查「去除」時列進未解析組(解析不出的段極性照預設的做)。"""
        query = dict(actions=["去除"], kinds=["條件"], include_condition=True, card=CRYSTAL_CORE)
        self.assertEqual(hit_segments(self.structures, self.cards, CRYSTAL_CORE,
                                      polarities=["不能"], **query), [])
        self.assertEqual(unparsed_texts(self.structures, self.cards, CRYSTAL_CORE, **query),
                         ["取り除けない場合"])

    def test_removing_the_counter_still_hits(self):
        """前一句「このカードのカウンターを１つ取り除く」照舊命中去除。"""
        removes = hit_segments(self.structures, self.cards, CRYSTAL_CORE, actions=["去除"])
        self.assertEqual([s["text"] for s in removes], ["このカードのカウンターを１つ取り除く"])


if __name__ == "__main__":
    unittest.main()
