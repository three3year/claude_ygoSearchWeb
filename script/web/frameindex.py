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

DOMAIN_PLAYER, DOMAIN_ZONE = "玩家", "區域"
# 框列鍵 → 述詞欄(值域的鍵),元組序;對照來自參考評估器的 EXPORT_PATH,這裡不 import 分詞鏈才抄這一份
SCALAR_KEYS = (("position", "位置"), ("polarity", "極性"), ("voice", "態"), ("negation", "否定形"),
               ("agent", "施事者"), ("manner_kind", "方式類"), ("patient_mode", "動作對象"))
REGION_KEYS = (("source", "來源"), ("goal", "目的"), ("place", "所在"))
# 片語鍵 → 它的中心詞欄,元組序
PHRASE_KEYS = (("patient", "受事者中心詞"), ("goal", "目的中心詞"))
FIELD_LEMMA, FIELD_HEAD_KIND, FIELD_QUANTITY, FIELD_MODIFIERS = "詞元", "中心詞類", "數量類", "修飾語類"
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
        found.extend({"field": field, "value": pair} for pair in regions.get(key) or ()
                     if pair[0] not in domains[DOMAIN_PLAYER] or pair[1] not in domains[DOMAIN_ZONE])
    for phrase, head_field in PHRASE_KEYS:
        for seg in _segments(frame, phrase):
            if seg.get("head") is None:
                found.append({"field": head_field, "value": None})
            for key, field in (("head_kind", FIELD_HEAD_KIND), ("quantity", FIELD_QUANTITY)):
                if seg.get(key) is not None and seg[key] not in domains[field]:
                    found.append({"field": field, "value": seg[key]})
            found.extend({"field": FIELD_MODIFIERS, "value": kind} for kind in seg.get("modifiers") or ()
                         if kind not in domains[FIELD_MODIFIERS])
    return found


def _region_item_ok(item, domains):
    return (isinstance(item, (list, tuple)) and len(item) == 2
            and (item[0] is None or item[0] in domains[DOMAIN_PLAYER]) and item[1] in domains[DOMAIN_ZONE])


def predicate_problems(predicate, domains):
    """目錄述詞 → 不認得的欄 [{field}] 與值域外的值 [{field, value}](全部列)。詞元與中心詞沒有值域:
    「編得出來、至少命中一張」已在分詞鏈匯出步驟檢查,這裡不重做。"""
    closed = set(domains) - {DOMAIN_PLAYER, DOMAIN_ZONE}
    regions = {field for _, field in REGION_KEYS}
    found = []
    for field, value in predicate.items():
        values = [value] if isinstance(value, str) else list(value)
        if field in regions:
            found.extend({"field": field, "value": item} for item in values if not _region_item_ok(item, domains))
        elif field in closed:
            found.extend({"field": field, "value": item} for item in values if item not in domains[field])
        elif field not in OPEN_FIELDS:
            found.append({"field": field})
    return found


def frame_tables(frames, domains):
    """全語料的框列 + 值域 → 編碼要查的表(詞元表與中心詞表就是 VOCAB.frame 的那兩張)。"""
    frames = list(frames)
    lemmas = sorted({frame["action"] for frame in frames})
    counts = Counter(seg["head"] for frame in frames for phrase, _ in PHRASE_KEYS for seg in _segments(frame, phrase))
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


def _cut(items, keep):
    """截掉尾端的空值(0 或空清單),至少留 keep 欄。"""
    while len(items) > keep and items[-1] in (0, []):
        items.pop()
    return items


def _encode_segment(seg, tables):
    return _cut([tables.head_code[seg["head"]],
                 _enum(tables, FIELD_HEAD_KIND, seg.get("head_kind")),
                 _enum(tables, FIELD_QUANTITY, seg.get("quantity")),
                 sum(tables.modifier_bit[kind] for kind in seg.get("modifiers") or ())], 1)


def encode_frame(frame, tables):
    """匯出的框列 → 框元組。值不在值域或表內就 KeyError(建置先由 frame_problems 擋,這裡不會遇到)。"""
    regions = frame.get("regions") or {}
    return _cut([tables.lemma_code[frame["action"]],
                 *(_enum(tables, field, frame.get(key)) for key, field in SCALAR_KEYS),
                 *([tables.pair_code[tuple(pair)] for pair in regions.get(key) or ()] for key, _ in REGION_KEYS),
                 *([_encode_segment(seg, tables) for seg in _segments(frame, phrase)] for phrase, _ in PHRASE_KEYS)], 1)
