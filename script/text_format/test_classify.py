"""三級分類器的純函式測試:餵合成卡片記錄,不做 IO(先例:tag_card 的勘誤
同步測試 test_sync_errata.py 與本資料夾的 test_ocg_dates.py)。

邊界照票02:9 期界日(2014-03-21,ST14 發售日)前一日/當日/後一日、查無日期、
有①但帶無編號段的靈擺卡(11067666 型,段分級不同)、純通常怪獸排除、
只剩風味文的靈擺通常怪獸(5 張型)。另有對真實資料的同一把尺迴歸(見檔尾)。
"""
import json
import os
import unittest

# 先 import classify:tag_card 的搜尋路徑由它在載入時 append,tagcard 那行
# 才找得到模組——這兩行的順序是依賴,不是字母序巧合
from classify import (TIER_NEW, TIER_OLD, TIER_REWRITTEN, TIER_UNDATED,
                      classify_card)
from tagcard import (TYPE_MONSTER, TYPE_NORMAL, TYPE_PENDULUM,
                     build_tag_cards)

_DATA_CARDS = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "..", "..", "data", "cards.json")

EFFECT_MONSTER = TYPE_MONSTER
NORMAL_MONSTER = TYPE_MONSTER | TYPE_NORMAL
PENDULUM_NORMAL = TYPE_MONSTER | TYPE_NORMAL | TYPE_PENDULUM
PENDULUM_EFFECT = TYPE_MONSTER | TYPE_PENDULUM

NEW_DESC = "①：1回合1次，可以以場上1張卡為對象發動。破壞那張卡。"
OLD_DESC = "這張卡召喚成功時，可以破壞場上1張卡。"
FLAVOR = "傳說中的最強之龍。任何對手都能粉碎。"


def _card(desc, ctype=EFFECT_MONSTER):
    return {"id": 0, "desc": desc, "type": ctype}


def _tiers(card, ocg_date):
    return [(seg["section"], seg["tier"])
            for seg in classify_card(card, ocg_date)]


class DateBoundaryTest(unittest.TestCase):
    def test_day_before_era9_is_rewritten(self):
        """有①且界日前一日首發 → 官方已改寫(優先稽核佇列)。"""
        self.assertEqual(_tiers(_card(NEW_DESC), "2014-03-20"),
                         [("main", TIER_REWRITTEN)])

    def test_era9_start_day_is_new(self):
        """界日當日(ST14 發售日)首發 → 新格式新卡:界日含以後算新。"""
        self.assertEqual(_tiers(_card(NEW_DESC), "2014-03-21"),
                         [("main", TIER_NEW)])

    def test_day_after_era9_is_new(self):
        """界日後一日首發 → 新格式新卡。"""
        self.assertEqual(_tiers(_card(NEW_DESC), "2014-03-22"),
                         [("main", TIER_NEW)])

    def test_numbered_without_date_is_undated(self):
        """有①但查無日期 → 日期不明,不硬塞進任何一級;空字串同 None。"""
        for date in (None, ""):
            self.assertEqual(_tiers(_card(NEW_DESC), date),
                             [("main", TIER_UNDATED)])


class OldTextTest(unittest.TestCase):
    def test_unnumbered_is_old_regardless_of_date(self):
        """無①段 → 舊文本;①有無是單一判準,日期不參與。"""
        for date in ("1999-02-04", "2020-01-01", None):
            self.assertEqual(_tiers(_card(OLD_DESC), date),
                             [("main", TIER_OLD)])


class PendulumTest(unittest.TestCase):
    MIXED_DESC = ("【靈擺效果】\n①：1回合1次，可以宣言1個卡名發動。\n"
                  "【怪獸效果】\n此卡在規則上當作「同調龍」卡使用。")

    def test_mixed_pendulum_sections_tiered_apart(self):
        """有①但帶無編號段的靈擺卡(11067666 型):各段獨立判級。"""
        self.assertEqual(_tiers(_card(self.MIXED_DESC, PENDULUM_EFFECT),
                                "2016-07-09"),
                         [("pendulum", TIER_NEW), ("main", TIER_OLD)])

    def test_mixed_pendulum_undated_only_hits_numbered_section(self):
        """同一張查無日期:有①段歸日期不明,無①段仍是舊文本。"""
        self.assertEqual(_tiers(_card(self.MIXED_DESC, PENDULUM_EFFECT), None),
                         [("pendulum", TIER_UNDATED), ("main", TIER_OLD)])

    def test_pendulum_normal_flavor_section_dropped(self):
        """靈擺通常怪獸:【怪獸敘述】段整段排除,只剩靈擺效果段受判。"""
        desc = f"【靈擺效果】\n{NEW_DESC}\n【怪獸敘述】\n{FLAVOR}"
        self.assertEqual(_tiers(_card(desc, PENDULUM_NORMAL), "2015-01-10"),
                         [("pendulum", TIER_NEW)])

    def test_pendulum_normal_flavor_only_yields_no_segments(self):
        """只剩風味文的靈擺通常怪獸(5 張型):靈擺段空白,無段可判。"""
        desc = f"【靈擺效果】\n【怪獸敘述】\n{FLAVOR}"
        self.assertEqual(_tiers(_card(desc, PENDULUM_NORMAL), "2015-01-10"),
                         [])


class LabelTest(unittest.TestCase):
    """對應條目標籤(規範 §4):餵合成卡文斷言(分級, 標籤)輸出,不測 regex 構造。"""

    def _labels(self, desc):
        segs = classify_card(_card(desc), None)
        self.assertEqual([seg["tier"] for seg in segs], [TIER_OLD])
        return segs[0]["labels"]

    def test_new_format_segment_has_no_labels(self):
        """非舊文本的段不帶對應條目標籤——對應表只服務改寫佇列。"""
        segs = classify_card(_card(NEW_DESC), "2020-01-01")
        self.assertEqual(segs[0]["labels"], [])

    def test_trigger_without_activation_collector(self):
        """「…時，可以…」誘發句無「發動」收尾 → 誘發缺發動(§4.4)。"""
        self.assertEqual(self._labels(OLD_DESC), ["誘發缺發動"])

    def test_flip_label_and_selection_stack(self):
        """「反轉：選擇…破壞」同段命中兩條:標籤是多標籤,順序照條目序。"""
        self.assertEqual(self._labels("反轉：選擇場上1隻守備表示怪獸破壞。"),
                         ["反轉標籤", "選擇取對象"])

    def test_named_card_usage_limit(self):
        """具卡名的次數限制句 → 具卡名限制(§4.7)。"""
        self.assertEqual(self._labels("「我我我搭檔」在1回合只能發動1張。"),
                         ["具卡名限制"])

    def test_ritual_material_line_is_not_cost_idiom(self):
        """儀式素材行「藉由「〜」降臨」是效果外文本,不是藉由代價句。"""
        self.assertEqual(self._labels("藉由「電腦網儀式」降臨。"), [])

    def test_base_only_segment_has_empty_labels(self):
        """沒命中任何條目的舊段:標籤空列表=僅基礎條目(§4.1)群。"""
        self.assertEqual(self._labels("我方牌組抽2張卡。"), [])


class ExclusionTest(unittest.TestCase):
    def test_pure_normal_monster_excluded(self):
        """純通常怪獸整張排除:風味文不是效果文,不進任何佇列。"""
        self.assertEqual(_tiers(_card(FLAVOR, NORMAL_MONSTER), "1999-02-04"),
                         [])

    def test_empty_desc_yields_no_segments(self):
        """空卡文無段可判。"""
        self.assertEqual(_tiers(_card(""), "2015-01-10"), [])


@unittest.skipUnless(os.path.exists(_DATA_CARDS), "需要 data/cards.json")
class SameRulerRegressionTest(unittest.TestCase):
    def test_old_text_count_matches_pending_split(self):
        """同一把尺迴歸:判舊文本的段數 == tagcard 報告的 pending_split。

        pending_split 的定義就是「無編號整團」,但拆句表套用後那些段會離開
        清單,所以要對「不套拆句表」的報告比;日期不參與舊文本判定,全部
        餵 None 即可。基準集合 3,805 段(票02),資料更新後兩邊會一起動。
        """
        with open(_DATA_CARDS, encoding="utf-8") as f:
            cards = json.load(f)
        _, report = build_tag_cards(cards, [], splits=None)
        old = sum(1 for card in cards
                  for seg in classify_card(card, None)
                  if seg["tier"] == TIER_OLD)
        self.assertEqual(old, len(report["pending_split"]))
        self.assertEqual(old, 3805)


if __name__ == "__main__":
    unittest.main()
