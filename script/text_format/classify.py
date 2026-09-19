"""三級分類器:一張卡的繁中卡文段落 + OCG 首發日 → 各段的文本世代分級。

純函式、不做 IO。分段沿用 tagcard 管線的同一把尺(排除純通常怪獸與【怪獸
敘述】風味文段、靈擺卡各段獨立),判為舊文本的段集合因此等於 tagcard 報告的
pending_split **扣掉[[無效果怪獸]]**(`is_effectless_monster`,test_classify.py
的迴歸釘住這個等式與扣掉的張數)。那 88 張是本分類器獨有的排除:它們的卡文
全是效果外文本,對改寫佇列無事可做,但對 tagcard 那條線仍是要拆的段——實測
88 張在現行[[效果標記表]]裡的 89 行全數已判效果外文本,兩條線各自都對。

分級判準(spec:.scratch/text-format/spec.md):
    舊文本      = 無①段(判準單一,日期不參與)→ 改寫佇列
    官方已改寫  = 有① 且 9 期界日前首發        → 優先稽核佇列
    新格式新卡  = 有① 且 界日(含)以後首發     → 一般稽核佇列
    日期不明    = 有① 但查無 ocg_date           → 獨立列出,不猜

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
from tagcard import (FOOTNOTE_RE, MATERIAL_TYPES, TYPE_EFFECT,  # noqa: E402
                     TYPE_MONSTER, TYPE_NORMAL, TYPE_PENDULUM,
                     _looks_like_material_line, _segments, _unit_role,
                     _zh_sections, _zh_unit_spans, is_pure_normal)

# 9 期界日:OCG 首個新格式產品 ST14 的發售日(官方商品頁,spec Further Notes)
ERA9_START = "2014-03-21"

TIER_OLD = "舊文本"
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
    #
    # **「此卡可以」的排除只在「的場合」那一支生效**(2026-08-27,text-rewrite#12)。
    # 原本一律排除,把**帶觸發事件**的手牌特召誘發効果一起吃掉了——那一族要
    # 發動、會形成連鎖區塊(庫內 kind=誘發效果的手牌特召 201 條全部有「發動」、
    # 零例外),漏抓等於讓它們落進 §4.1 群、票裡不會有任何提示。
    # 兩族的分界在**觸發子句的形狀**,實測乾淨:
    #   「〜時，…此卡可以…」  誘發効果 17 / 無種類效果 **0** → 不排除
    #   狀態場合(〜存在/多/少的場合)  無種類效果 40 / 誘發効果 **0** → 排除
    # 剩 4 條事件形場合(2:2)靠人工,那一支維持排除、保守不擴。
    ("誘發缺發動", "§4.4",
     (r"(?:時|的場合)，(?![^。\n]*發動)(?![^。\n]*代替)(?![^。\n]*隨後)"
      r"(?![^。\n]*可以(?:當作|改成))(?:(?<=時，)|(?![^。\n]*此卡可以))"
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


def _unnumbered_texts(card):
    """卡文各段的無編號整團文字;任一段帶①時回 None(帶①就有效果句)。

    段裡什麼都沒有(空卡文、只剩風味文)時回 None——「沒有段可看」不是
    「看過了都是效果外文本」,那條路歸 `classify_card` 的無段可判。
    """
    sections, _ = _zh_sections(FOOTNOTE_RE.sub("", card.get("desc") or ""))
    texts = []
    for _, text in sections:
        _, numbered, unnumbered = _segments(text)
        if numbered:
            return None
        if unnumbered is not None:
            start, end = unnumbered
            texts.append(text[start:end])
    return texts or None


def _all_units_non_effect(text, ctype):
    """整團文字逐句判 role,全部判得出來 → 整段都是[[效果外文本]]。

    單位切法與 role 判準都沿用 tagcard 的前言段那一套(`_zh_unit_spans` /
    `_unit_role`),第一行的素材行另由呼叫端認——素材行是名詞片語,逐句
    掃描的正規式抓不到它。
    """
    units = _zh_unit_spans(text, (0, len(text)))
    if not units:
        return False
    material_first = _looks_like_material_line(text, ctype)
    for pos, (start, end) in enumerate(units):
        if pos == 0 and material_first:
            continue
        if _unit_role(text[start:end]) is None:
            return False
    return True


def is_effectless_monster(card):
    """無效果怪獸嗎?整張排除在掃描基準之外(text-rewrite#08 站主裁示)。

    融合/儀式/同調/超量/連結怪獸的卡文只有素材行、降臨句或召喚限制時,句面
    本就是[[效果外文本]],沒有可改寫之處。分類器原本對「無①段且非通常怪獸」
    一律計舊,把這批結構性誤收進改寫佇列——其中副話術士 克拉拉&洛希卡
    (2017)、天威的鬼神(2019)、無之畢竟 終歸虛空(2021)還是新格式時代的
    卡。比照[[純通常怪獸]]的既有排除(`is_pure_normal`),整張不進三級分類。

    兩條判準,任一成立即是無效果怪獸:
    官方型別**沒有效果位元**——官方自己就標了這隻怪獸沒有效果(85 張);
    有效果位元、但卡文每段都以素材行起頭且逐句皆判得出效果外文本的 role
    (3 張,如副話術士:素材行+連結召喚限制)。官方把只寫召喚限制的怪獸
    也標成效果怪獸,只看位元會漏掉這一族。

    「以素材行起頭」是第二條的防線,不是修辭:只用 role 掃全庫會誤收 20 張
    真有效果的上級召喚系怪獸(「解放…上級召喚成功時…」被召喚條件式命中)。
    帶①段的卡一律不排除——①段的定義就是效果句,這道閘門保證排除永遠不會
    把新格式卡從稽核佇列裡靜靜拿掉。
    """
    ctype = card.get("type", 0)
    # 兩條判準都只在特殊召喚系怪獸上成立(第二條的素材行更是直接要求它),
    # 閘門提到最前面:主牌組怪獸沒有「整張沒有效果」這回事,通常怪獸另有排除
    if not (ctype & TYPE_MONSTER and ctype & MATERIAL_TYPES):
        return False
    texts = _unnumbered_texts(card)
    if texts is None:
        return False
    if not ctype & (TYPE_NORMAL | TYPE_EFFECT | TYPE_PENDULUM):
        return True
    return all(_looks_like_material_line(text, ctype)
               and _all_units_non_effect(text, ctype) for text in texts)


def _dated_tier(ocg_date):
    """有①的段依首發日分級;日期是 ISO 字串,比大小即比日期。

    None 與空字串都算查無日期——來源檔存原始樣貌,空值不進日期比較硬猜。
    """
    if not ocg_date:
        return TIER_UNDATED
    return TIER_REWRITTEN if ocg_date < ERA9_START else TIER_NEW


def classify_card(card, ocg_date):
    """卡片總表條目 + OCG 首發日 → [{"section", "tier", "labels"}, ...]。

    card 需 desc / type;ocg_date 來自 align_ocg_dates(查無日期為 None)。
    純通常怪獸整張排除、風味文段不進清單、無段可判時回空列表——與
    build_tag_cards 對段的取捨完全一致(別名註記剝除也同一條規則)。
    labels 是舊文本段命中的對應表條目(`old_pattern_labels`);其他分級
    恆為空列表——對應表只服務改寫佇列。
    """
    if is_pure_normal(card.get("type", 0)) or is_effectless_monster(card):
        return []
    sections, _ = _zh_sections(FOOTNOTE_RE.sub("", card.get("desc") or ""))
    tiers = []
    for section, text in sections:
        preamble, numbered, unnumbered = _segments(text)
        if preamble is None and not numbered and unnumbered is None:
            continue
        if numbered:
            tier, labels = _dated_tier(ocg_date), []
        else:
            start, end = unnumbered
            tier, labels = TIER_OLD, old_pattern_labels(text[start:end])
        tiers.append({"section": section, "tier": tier, "labels": labels})
    return tiers
