"""動作框架的索引編碼(predicate-index 票 02,規格「索引形狀」段)。

接縫:`frame_tables(框列清單, 值域) → FrameTables`、`encode_frame(框列, 表) → 框元組`,純函式;
`webindex.build_index` 與編碼夾具(票 03)用同一支,所以 JS 評估器讀到的形狀只有這一個定義。

框元組(定序、尾端空值截掉):
    [詞元, 位置, 極性, 態, 否定形, 施事者, 方式類, 動作對象, [來源對…], [目的對…], [所在對…], [受事者段…], [目的段…]]
    詞元        詞元表(字典序)的序號
    列舉欄      值域序號加一,0 是沒有值
    區域對      玩家序號 × 區域數 + 區域序號,一個整數
    段          [中心詞碼, 中心詞類, 數量類, 修飾語位元];中心詞碼是中心詞表(次數遞減、同次數字典序)的序號,
                修飾語位元的第 n 位是修飾語類值域第 n 個

輸入是匯出檔 data/action_frames.json 的框列與它的「值域」:`script/web` 不 import 分詞鏈,值域隨匯出檔進來(規格
「封閉類的值域放哪?」(a))。`manner_value` 沒有述詞欄,不進索引。
"""
from collections import Counter, namedtuple

# 值域裡玩家與區域兩張的鍵(predicate.DOMAIN_PLAYER/ZONE,2026-11-01 規格 3「封閉類的值域放哪?」(a));值域隨匯出檔進來,
# 鍵名是讀它的入口,留在這裡,由 test_webindex.EncodedFixtureTest 守與 predicate 相同
DOMAIN_PLAYER, DOMAIN_ZONE = "玩家", "區域"
# 述詞欄 → 匯出框列的路徑,排列就是元組序(predicate.EXPORT_PATH,2026-11-01 規格 2「參考評估器」段;元組序是規格 3「索引形狀」
# 段)。匯出檔的值域只帶值、不帶鍵對照,script/web 又不 import 分詞鏈,所以這張留不掉;整張由同一條測試守與 predicate 相同
EXPORT_PATH = {
    "詞元": ("action",), "位置": ("position",), "極性": ("polarity",), "態": ("voice",), "否定形": ("negation",),
    "施事者": ("agent",), "方式類": ("manner_kind",), "動作對象": ("patient_mode",),
    "來源": ("regions", "source"), "目的": ("regions", "goal"), "所在": ("regions", "place"),
    "受事者中心詞": ("phrases", "patient", "head"), "目的中心詞": ("phrases", "goal", "head"),
    "中心詞類": ("phrases", "patient", "head_kind"), "數量類": ("phrases", "patient", "quantity"),
    "修飾語類": ("phrases", "patient", "modifiers"),
}
FIELD_LEMMA, FIELD_MODIFIERS = "詞元", "修飾語類"
# 以下都由 EXPORT_PATH 推得,不是另一份:(框列鍵, 述詞欄),依元組序
SCALAR_KEYS = tuple((path[0], field) for field, path in EXPORT_PATH.items() if len(path) == 1 and field != FIELD_LEMMA)
REGION_KEYS = tuple((path[1], field) for field, path in EXPORT_PATH.items() if path[0] == "regions")
PHRASE_KEYS = tuple((path[1], field) for field, path in EXPORT_PATH.items() if path[-1] == "head")
SEGMENT_ENUM_KEYS = tuple((path[2], field) for field, path in EXPORT_PATH.items()
                          if path[0] == "phrases" and path[2] != "head" and field != FIELD_MODIFIERS)
# 述詞欄裡沒有值域可比的三欄(詞元與中心詞是開放的,不在語料就是不中)
OPEN_FIELDS = (FIELD_LEMMA,) + tuple(field for _, field in PHRASE_KEYS)

FrameTables = namedtuple("FrameTables", "lemmas heads lemma_code head_code enum_code modifier_bit pair_code")


def _segments(frame, phrase):
    return (frame.get("phrases") or {}).get(phrase) or ()


def _enum_codes(domains):
    return {field: {value: n + 1 for n, value in enumerate(values)} for field, values in domains.items()}


def _pair_codes(domains):
    zones = domains[DOMAIN_ZONE]
    return {(player, zone): p * len(zones) + z
            for p, player in enumerate(domains[DOMAIN_PLAYER]) for z, zone in enumerate(zones)}


def _is_pair(item):
    return isinstance(item, (list, tuple)) and len(item) == 2


def _as_list(value):
    """單項或清單 → 清單;沒有值是空清單。殘缺的輸入(單一數字、字串)因此逐項被值域檢查擋下,不是在迭代時崩。"""
    if value is None:
        return []
    return value if isinstance(value, (list, tuple)) else [value]


def frame_problems(frame, domains):
    """框列 → 值域外的值 [{field, value}](述詞欄名;全部列,編碼前先擋)。缺詞元或中心詞也算:編不出元組。"""
    found = []
    if frame.get("action") is None:
        found.append({"field": FIELD_LEMMA, "value": None})
    for key, field in SCALAR_KEYS:
        value = frame.get(key)
        if value is not None and value not in domains[field]:
            found.append({"field": field, "value": value})
    regions = frame.get("regions") or {}
    for key, field in REGION_KEYS:
        found.extend({"field": field, "value": pair} for pair in _as_list(regions.get(key))
                     if not _is_pair(pair) or pair[0] not in domains[DOMAIN_PLAYER] or pair[1] not in domains[DOMAIN_ZONE])
    for phrase, head_field in PHRASE_KEYS:
        for seg in _segments(frame, phrase):
            if seg.get("head") is None:
                found.append({"field": head_field, "value": None})
            for key, field in SEGMENT_ENUM_KEYS:
                if seg.get(key) is not None and seg[key] not in domains[field]:
                    found.append({"field": field, "value": seg[key]})
            found.extend({"field": FIELD_MODIFIERS, "value": kind} for kind in seg.get("modifiers") or ()
                         if kind not in domains[FIELD_MODIFIERS])
    return found


def _region_item_ok(item, domains):
    return _is_pair(item) and (item[0] is None or item[0] in domains[DOMAIN_PLAYER]) and item[1] in domains[DOMAIN_ZONE]


def predicate_problems(predicate, domains):
    """目錄述詞 → 不認得的欄 [{field}] 與值域外或形狀不對的值 [{field, value}](全部列)。詞元與中心詞沒有值域,
    只看是不是字串:「編得出來、至少命中一張」已在分詞鏈匯出步驟檢查,這裡不重做。"""
    closed = set(domains) - {DOMAIN_PLAYER, DOMAIN_ZONE}
    regions = {field for _, field in REGION_KEYS}
    found = []
    for field, value in predicate.items():
        if field not in regions and field not in closed and field not in OPEN_FIELDS:
            found.append({"field": field})
        elif not isinstance(value, (str, list)):
            found.append({"field": field, "value": value})
        else:
            items = [value] if isinstance(value, str) else value
            if field in regions:
                bad = [item for item in items if not _region_item_ok(item, domains)]
            elif field in closed:
                bad = [item for item in items if item not in domains[field]]
            else:
                bad = [item for item in items if not isinstance(item, str)]
            found.extend({"field": field, "value": item} for item in bad)
    return found


def frame_tables(frame_rows, domains):
    """全語料的框列 + 值域 → 編碼要查的表(詞元表與中心詞表就是 VOCAB.frame 的那兩張)。"""
    frame_rows = list(frame_rows)
    lemmas = sorted({frame["action"] for frame in frame_rows})
    counts = Counter(seg["head"] for frame in frame_rows for phrase, _ in PHRASE_KEYS
                     for seg in _segments(frame, phrase))
    heads = [head for head, _ in sorted(counts.items(), key=lambda item: (-item[1], item[0]))]
    return FrameTables(lemmas=lemmas, heads=heads,
                       lemma_code={lemma: n for n, lemma in enumerate(lemmas)},
                       head_code={head: n for n, head in enumerate(heads)},
                       enum_code=_enum_codes(domains),
                       modifier_bit={kind: 1 << n for n, kind in enumerate(domains[FIELD_MODIFIERS])},
                       pair_code=_pair_codes(domains))


def _enum(tables, field, value):
    """沒有值是 0;值域外的值 KeyError——靜靜變成 0 會讓述詞默默查不到。"""
    return 0 if value is None else tables.enum_code[field][value]


def _cut(items):
    """截掉尾端的空值(0 或空清單),第一欄(詞元或中心詞碼)一定留。"""
    while len(items) > 1 and items[-1] in (0, []):
        items.pop()
    return items


def _encode_segment(seg, tables):
    return _cut([tables.head_code[seg["head"]],
                 *(_enum(tables, field, seg.get(key)) for key, field in SEGMENT_ENUM_KEYS),
                 sum(tables.modifier_bit[kind] for kind in seg.get("modifiers") or ())])


def encode_frame(frame, tables):
    """匯出的框列 → 框元組。值不在值域或表內就 KeyError(建置先由 frame_problems 擋,這裡不會遇到)。"""
    regions = frame.get("regions") or {}
    return _cut([tables.lemma_code[frame["action"]],
                 *(_enum(tables, field, frame.get(key)) for key, field in SCALAR_KEYS),
                 *([tables.pair_code[tuple(pair)] for pair in regions.get(key) or ()] for key, _ in REGION_KEYS),
                 *([_encode_segment(seg, tables) for seg in _segments(frame, phrase)] for phrase, _ in PHRASE_KEYS)])
