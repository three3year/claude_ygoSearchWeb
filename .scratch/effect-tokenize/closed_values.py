# -*- coding: utf-8 -*-
"""第四版論元(frame-args-v4)的封閉表:每個新封閉類一張表,表就是值域(票 01 建,各票補值)。

和移動類清單、推得值表同一種東西——框架線的封閉表。全語料出現表外值的欄,建置失敗
(frames.py main() 寫檔前呼叫 violations(),有表外值就列出來並以非 0 結束);test_v4.py 也用它。
「其他」只在中心詞類、修飾語類與方式類的表裡(規格的方式段列了 なしで/ままで 這類記 其他);
施事者、否定形、數量類等表沒有它,出現就是表外值。

玩家拼法:結構化值與片語的玩家用 GLOSSARY 論元條的 自分/相手/お互い/相對/無——places.py 的
雙方 在這裡寫成 お互い(PLACE_PLAYER 對照);既有的類別檔仍是 雙方,規格 2 改讀時統一。
"""
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import places  # noqa: E402
from constraints import KIND_ACTION  # noqa: E402

OTHER = "其他"

# 中心詞類(票 02):段的中心詞是哪一類
HEAD_KINDS = ("卡", "屬性", "非卡", "指示詞", OTHER)
HEAD_CARD, HEAD_ATTRIBUTE, HEAD_NON_CARD, HEAD_DEMONSTRATIVE = HEAD_KINDS[:4]
# 中心詞類判定表(規格 Implementation Decisions 的中心詞類段;依中心詞字面比,表外落 其他):
# 卡——モンスター/カード/トークン/チューナー/素材、卡名「…」、卡種+カード 與 子類型+モンスター 這類封閉值域
# 複合詞(以尾字比)、受事者本身是區域(手札、デッキ、墓地、自分フィールド…,交給 places 認);
# 屬性——數值與性質欄位,與跟主人走的事件類(効果/発動/攻撃/各召喚);非卡——傷害/LP/指示物/數/擲幣/
# 戰鬥/ゾーン 與純數值;指示詞——沒有名詞中心的段(それ/それら/いずれか/内/対象/残り,與只剩數量的段
# 「1枚」「2体以上」:名詞省略了,指的是上文的卡)
_HEAD_CARD_WORDS = frozenset({"モンスター", "カード", "トークン", "チューナー", "素材", "魔法", "罠"})
_HEAD_CARD_SUFFIXES = ("カード", "モンスター", "素材", "トークン", "魔法", "罠")
_HEAD_ATTRIBUTE_WORDS = frozenset({
    "攻撃力", "守備力", "レベル", "ランク", "Pスケール", "属性", "種族", "カード名", "表示形式", "コントロール",
    "位置", "効果", "発動", "攻撃", "召喚"})
_HEAD_ATTRIBUTE_SUFFIXES = ("召喚", "カード名")
_HEAD_NON_CARD_WORDS = frozenset({"ダメージ", "LP", "カウンター", "数", "コイントス", "戦闘", "ゾーン"})
_HEAD_NON_CARD_SUFFIXES = ("ダメージ", "カウンター")
_HEAD_DEMONSTRATIVE_WORDS = frozenset({"それ", "それら", "いずれか", "内", "対象", "残り", "両方", "どちらか"})
_NUMERIC = re.compile(r"[0-9]+")
_QUANTITY_ONLY = re.compile(r"[0-9]+(?:枚|体|つ|種類|個|組|回|ヵ所)(?:まで|以上|以下|未満)?")


def head_kind(head):
    """中心詞字面 → 中心詞類(HEAD_KINDS 之一);None 與表外的落 其他。"""
    if not head:
        return OTHER
    if head.startswith("「") and head.endswith("」"):
        return HEAD_CARD
    if head in _HEAD_CARD_WORDS or head.endswith(_HEAD_CARD_SUFFIXES):
        return HEAD_CARD
    if head in _HEAD_ATTRIBUTE_WORDS or head.endswith(_HEAD_ATTRIBUTE_SUFFIXES):
        return HEAD_ATTRIBUTE
    if head in _HEAD_NON_CARD_WORDS or head.endswith(_HEAD_NON_CARD_SUFFIXES) or _NUMERIC.fullmatch(head):
        return HEAD_NON_CARD
    if head in _HEAD_DEMONSTRATIVE_WORDS or _QUANTITY_ONLY.fullmatch(head):
        return HEAD_DEMONSTRATIVE
    if places.parse_place(head)[1]:
        return HEAD_CARD
    return OTHER

# 修飾語類(票 03)
MODIFIER_KINDS = ("種族", "屬性", "字段", "卡片子類型", "數值", "區域", "玩家", "表示形式", OTHER)
# 數量類(票 04);引用量(数の分だけ/同じ数)類空,不在表裡
QUANTITY_KINDS = ("定數", "上限", "下限", "任意", "全部")
# 方式類(票 06)
MANNER_KINDS = ("手段:效果", "手段:戰鬥", "手段:方法", "表示形式", "視同", "順序", OTHER)
# 施事者與它的來源(票 07)
AGENTS = ("自分", "相手", "お互い", "此卡", "其他卡")
AGENT_SOURCES = ("主題", "主語", "事件主語", "によって", "預設")
# 否定形(票 08)
NEGATION_FORMS = ("受身", "不成不受", "不可能", "一般")
# 轉欄記號(票 05/06)與回指回填記號(票 09)
TRANSFERS = ("取自來源", "取自で")
REGION_BACKFILLS = ("source", "place")
# 玩家(結構化值與片語);places 的玩家值 → 這裡的拼法
PLAYERS = ("自分", "相手", "お互い", "相對", "無")
PLACE_PLAYER = {places.PLAYER_SELF: "自分", places.PLAYER_OPP: "相手", places.PLAYER_BOTH: "お互い",
                places.PLAYER_RELATIVE: "相對", places.PLAYER_NONE: "無"}
# 區域七值(places.ZONE_TERMS 的值域,依字典序)
ZONES = tuple(sorted({zone for _, zone in places.ZONE_TERMS}))

# 片語與結構化值放在哪些欄
PHRASE_KEYS = ("object", "topic", "subject", "goal")
REGION_KEYS = ("source", "goal", "place")

# 頂層新鍵 → 它的表(值是單一字串)
_TOP_LEVEL = (("transfer", TRANSFERS), ("agent", AGENTS), ("agent_source", AGENT_SOURCES),
              ("manner_kind", MANNER_KINDS), ("negation", NEGATION_FORMS),
              ("region_backfill", REGION_BACKFILLS))


def _check(found, path, value, table, allow_none=False):
    if value is None and allow_none:
        return
    if value not in table:
        found[(path, value)] += 1


def _check_frame(found, frame):
    for key, table in _TOP_LEVEL:
        if key in frame:
            _check(found, key, frame[key], table)
    for key, phrase in (frame.get("phrases") or {}).items():
        _check(found, "phrases", key, PHRASE_KEYS)
        for seg in phrase.get("segments") or ():
            _check(found, "phrases.segments.head_kind", seg.get("head_kind"), HEAD_KINDS)
            _check(found, "phrases.segments.player", seg.get("player"), PLAYERS, allow_none=True)
            for zone in seg.get("zones") or ():
                _check(found, "phrases.segments.zones", zone, ZONES)
            for mod in seg.get("modifiers") or ():
                _check(found, "phrases.segments.modifiers.kind", mod.get("kind"), MODIFIER_KINDS)
            quantity = seg.get("quantity")
            if quantity is not None:
                _check(found, "phrases.segments.quantity.kind", quantity.get("kind"),
                       QUANTITY_KINDS, allow_none=True)
    for key, pairs in (frame.get("regions") or {}).items():
        _check(found, "regions", key, REGION_KEYS)
        for player, zone in pairs:
            _check(found, "regions.player", player, PLAYERS)
            _check(found, "regions.zone", zone, ZONES)


def violations(records):
    """frames.json 的紀錄 → [(欄位路徑, 表外值, 框數)],依路徑、值排序;只掃動作框架。
    空清單就是全部在表內。"""
    found = Counter()
    for rec in records:
        for frame in rec["frames"]:
            if frame.get("kind") == KIND_ACTION:
                _check_frame(found, frame)
    return sorted((path, value, count) for (path, value), count in found.items())


def report(found, out=sys.stderr):
    """把 violations() 的結果印成一行一筆;給 frames.py main() 用。"""
    for path, value, count in found:
        print("封閉表外的值:%s = %r(%d 框)" % (path, value, count), file=out)
