"""三級分類器:一張卡的繁中卡文段落 + OCG 首發日 → 各段的文本世代分級。

純函式、不做 IO。分段沿用 tagcard 管線的同一把尺(排除純通常怪獸與【怪獸
敘述】風味文段、靈擺卡各段獨立),判為舊文本的段集合因此永遠等於 tagcard
報告的 pending_split 定義(3,805 段,test_classify.py 的迴歸釘住這個等式)。

分級判準(spec:.scratch/text-format/spec.md、.scratch/text-rewrite/spec.md):
    舊文本      = 無①段(判準單一,日期不參與)→ 改寫佇列
    本站已改寫  = 有① 且 該卡在[[文本改寫表]]    → 獨立成區(改寫進度)
    官方已改寫  = 有① 且 9 期界日前首發        → 優先稽核佇列
    新格式新卡  = 有① 且 界日(含)以後首發     → 一般稽核佇列
    日期不明    = 有① 但查無 ocg_date           → 獨立列出,不猜

「本站已改寫」在日期分級之前判:被本站改寫的卡首發日多在 9 期界日前,
不獨立成級的話會誤歸「官方已改寫」污染優先稽核佇列。

舊文本段另帶「所需對應表條目」標籤(規範 §4,`OLD_PATTERNS`),供報表
把改寫佇列分群——同一群共用同一組舊→新對應規則。
"""
import os
import re
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
TIER_SITE_REWRITTEN = "本站已改寫"
TIER_REWRITTEN = "官方已改寫"
TIER_NEW = "新格式新卡"
TIER_UNDATED = "日期不明"

# 舊→新句型對應條目的偵測樣式(規範 docs/text_format_guide.md §4,一列 =
# (條目名, 規範章節, regex 清單),任一 regex 命中即帶該標籤)。它服務報表
# 分群,不是建置關卡:訊號是近似的,各條目的覆蓋與誤報樣態記錄在 §4 逐條。
# 基礎條目 §4.1(缺圈號分層)不在此列——它的判準就是分級本身,全部舊段適用,
# 沒命中任何條目的舊段(標籤空列表)構成報表的「僅基礎條目」群。
OLD_PATTERNS = (
    # 「また、〜」把第二個獨立效果接在同段 → 各自圈號起段
    ("此外接續", "§4.2", (r"此外，",)),
    # 「リバース：」化石標籤 → 一般誘發句式(規範 §3.18)
    ("反轉標籤", "§4.3", (r"反轉[:：]",)),
    # 「〜した時、〜(できる)。」誘發處理一句寫完,無「發動」收尾 → 發動句+
    # 處理句。只抓任意形(句內有「可以」);強制形與結算敘述句難以regex區分,
    # 靠人工。排除的都是新式合法同形句:代替/隨後/當作/改成/此卡可以(許可)
    ("誘發缺發動", "§4.4",
     (r"(?:時|的場合)，(?![^。\n]*發動)(?![^。\n]*代替)(?![^。\n]*隨後)"
      r"(?![^。\n]*可以(?:當作|改成))(?![^。\n]*此卡可以)"
      r"[^。\n]*可以[^。\n]*。",)),
    # 「〜を選択して発動」+「選択した〜」回指 → 「以…為對象」+「那隻/那張」。
    # 排除「被選擇」「不能選擇…(作為攻擊)對象」「各能選擇1次」等新式合法句
    ("選擇取對象", "§4.5",
     (r"(?<!被)(?<!能)選擇(?![1-9]?個)(?![^。●\n]*對象)[^。●\n]*[。，]",
      r"選擇的",)),
    # 「〜する事で、〜」舊代價句 → cost 進發動句。排除儀式素材行「藉由
    # 「〜」降臨」與召喚條件「只能藉由…」
    ("藉由代價", "§4.6", (r"(?<!只能)藉由(?![^，。]*降臨)",)),
    # 「「〈卡名〉」の効果は…しか使用できない」具卡名限制 → 「這個卡名」
    # 句型並移至圈號前(規範 §3.8/§3.9)
    ("具卡名限制", "§4.7",
     (r"「[^」]+」的(?:這個)?效果[^。]*只能(?:使用|發動)",
      r"「[^」]+」(?:在)?1回合只能發動1張",
      r"決鬥中只能(?:使用|發動)1次")),
    # 「フィールド上に表側表示で存在」舊場所指涉 → 區域指涉(怪獸區域等)
    ("場上表側表示", "§4.8", (r"場上表側表示存在",)),
    # TCG 限定卡的 PSCT 冒號分號直譯 → 中文固定句式(規範 §2 不使用分號)
    ("冒號分號", "§4.9", (r"[;；]",)),
)
_COMPILED_PATTERNS = tuple((key, tuple(re.compile(p) for p in patterns))
                           for key, _, patterns in OLD_PATTERNS)


def old_pattern_labels(text):
    """舊段文字 → 命中的對應條目標籤清單(順序照 `OLD_PATTERNS` 條目序)。"""
    return [key for key, patterns in _COMPILED_PATTERNS
            if any(pattern.search(text) for pattern in patterns)]


def _dated_tier(ocg_date):
    """有①的段依首發日分級;日期是 ISO 字串,比大小即比日期。

    None 與空字串都算查無日期——來源檔存原始樣貌,空值不進日期比較硬猜。
    """
    if not ocg_date:
        return TIER_UNDATED
    return TIER_REWRITTEN if ocg_date < ERA9_START else TIER_NEW


def classify_card(card, ocg_date, site_rewritten=False):
    """卡片總表條目 + OCG 首發日 → [{"section", "tier", "labels"}, ...]。

    card 需 desc / type;ocg_date 來自 align_ocg_dates(查無日期為 None);
    site_rewritten 是「該卡已被本站改寫」(在[[文本改寫表]]即為真,由呼叫端
    查表——分類器維持純函式不做 IO)。已改寫卡的①段一律判「本站已改寫」,
    日期不參與(改寫是本站的動作,與首發日無關);無①段照樣判舊文本——
    「舊文本段 = tagcard pending_split」的同尺等式不因改寫旗標而動搖。
    純通常怪獸整張排除、風味文段不進清單、無段可判時回空列表——與
    build_tag_cards 對段的取捨完全一致(別名註記剝除也同一條規則)。
    labels 是舊文本段命中的對應表條目(`old_pattern_labels`);其他分級
    恆為空列表——對應表只服務改寫佇列。
    """
    if is_pure_normal(card.get("type", 0)):
        return []
    sections, _ = _zh_sections(FOOTNOTE_RE.sub("", card.get("desc") or ""))
    tiers = []
    for section, text in sections:
        preamble, numbered, unnumbered = _segments(text)
        if preamble is None and not numbered and unnumbered is None:
            continue
        if numbered:
            tier = (TIER_SITE_REWRITTEN if site_rewritten
                    else _dated_tier(ocg_date))
            labels = []
        else:
            start, end = unnumbered
            tier, labels = TIER_OLD, old_pattern_labels(text[start:end])
        tiers.append({"section": section, "tier": tier, "labels": labels})
    return tiers
