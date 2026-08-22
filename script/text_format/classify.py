"""三級分類器:一張卡的繁中卡文段落 + OCG 首發日 → 各段的文本世代分級。

純函式、不做 IO。分段沿用 tagcard 管線的同一把尺(排除純通常怪獸與【怪獸
敘述】風味文段、靈擺卡各段獨立),判為舊文本的段集合因此永遠等於 tagcard
報告的 pending_split 定義(3,805 段,test_classify.py 的迴歸釘住這個等式)。

分級判準(spec:.scratch/text-format/spec.md):
    舊文本      = 無①段(判準單一,日期不參與)→ 改寫佇列
    官方已改寫  = 有① 且 9 期界日前首發        → 優先稽核佇列
    新格式新卡  = 有① 且 界日(含)以後首發     → 一般稽核佇列
    日期不明    = 有① 但查無 ocg_date           → 獨立列出,不猜
"""
import os
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
# 分段邏輯復用 tag_card 的 tagcard.py(跨資料夾,需手動加入搜尋路徑)。
# 用 append 而非 insert:不讓這個目錄有機會遮蔽標準庫或既有模組。
sys.path.append(os.path.join(_ROOT, "script", "tag_card"))
from tagcard import (FOOTNOTE_RE, _segments, _zh_sections,  # noqa: E402
                     is_pure_normal)

# 9 期界日:OCG 首個新格式產品 ST14 的發售日(官方商品頁,spec Further Notes)
ERA9_START = "2014-03-21"

TIER_OLD = "舊文本"
TIER_REWRITTEN = "官方已改寫"
TIER_NEW = "新格式新卡"
TIER_UNDATED = "日期不明"


def _dated_tier(ocg_date):
    """有①的段依首發日分級;日期是 ISO 字串,比大小即比日期。

    None 與空字串都算查無日期——來源檔存原始樣貌,空值不進日期比較硬猜。
    """
    if not ocg_date:
        return TIER_UNDATED
    return TIER_REWRITTEN if ocg_date < ERA9_START else TIER_NEW


def classify_card(card, ocg_date):
    """卡片總表條目 + OCG 首發日 → [{"section": 段, "tier": 分級}, ...]。

    card 需 desc / type;ocg_date 來自 align_ocg_dates(查無日期為 None)。
    純通常怪獸整張排除、風味文段不進清單、無段可判時回空列表——與
    build_tag_cards 對段的取捨完全一致(別名註記剝除也同一條規則)。
    """
    if is_pure_normal(card.get("type", 0)):
        return []
    sections, _ = _zh_sections(FOOTNOTE_RE.sub("", card.get("desc") or ""))
    tiers = []
    for section, text in sections:
        preamble, numbered, unnumbered = _segments(text)
        if preamble is None and not numbered and unnumbered is None:
            continue
        tiers.append({"section": section,
                      "tier": TIER_OLD if not numbered
                      else _dated_tier(ocg_date)})
    return tiers
