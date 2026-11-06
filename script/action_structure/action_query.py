"""查詢判斷(純函式):全庫卡片結構 + 查詢 → 命中的卡、命中段與分組。

查詢(spec「查詢判斷」;鍵名英文,值用 GLOSSARY 的詞):
  actions           動作詞列表,全部都要在段內
  from_zones / to_zones  區域(字串,或 {"zone", "side"}),逐條對象線比;子區域算在上位區域內
  card              指定卡(卡片密碼),代入對象物件
  condition         只給條件:卡片總表裡存在一張實卡同時滿足查詢條件與物件條件
  targeting         True 時只算有標取對象的線
  kinds             段類別範圍(預設 效果、代價、召喚手續)
  block_kinds       區塊種類範圍(預設全部)
  include_condition 條件段開關(預設關)
  include_inferred  推得終點開關(預設關):推得值與繼承自推得值只在開時算
  replacement       查詢含「代替」時才看被代替段(票 08)
  polarities        極性範圍(預設只算「做」)
  generic_only      只查泛用組(票 07)

結果:{"hits": [{"id", "segments", "group"}], "groups": {"特定", "泛用", "全部"},
      "unparsed": [...]}(未解析組由票 03 填)。
"""
import json

from structure_shape import ZONE_PARENT, iter_segments

DEFAULT_KINDS = ("效果", "代價", "召喚手續")
CATEGORY_BITS = {"怪獸": 0x1, "魔法": 0x2, "陷阱": 0x4}
GENERIC_ATOMS = ("大類", "位置", "控制方")


def _zone_names(name):
    """一個區域與它的全部上位區域:線上寫「牌組頂」,查「牌組」也要對得上。"""
    names = [name]
    while name in ZONE_PARENT:
        name = ZONE_PARENT[name]
        names.append(name)
    return names


def _as_zone(spec):
    return spec if isinstance(spec, dict) else {"zone": spec, "side": None}


def zones_match(query_zones, pos, include_inferred):
    if pos is None:
        return False
    if pos["inferred"] and not include_inferred:
        return False
    for want in map(_as_zone, query_zones):
        for have in pos["zones"]:
            if want["zone"] in _zone_names(have["zone"]) and (
                    want["side"] is None or want["side"] == have["side"]):
                return True
    return False


def eval_condition(condition, entry):
    """條件式對一張卡片總表條目:True / False / None(含解析不出,判不了)。"""
    if condition is None:
        return True
    op = condition["op"]
    if op == "且":
        results = [eval_condition(a, entry) for a in condition["args"]]
        return None if None in results else all(results)
    if op == "或":
        results = [eval_condition(a, entry) for a in condition["args"]]
        if True in results:
            return True
        return None if None in results else False
    if op == "非":
        inner = eval_condition(condition["arg"], entry)
        return None if inner is None else not inner
    if op == "大類":
        if condition["value"] == "卡":
            return True
        return bool(entry["type"] & CATEGORY_BITS[condition["value"]])
    return None


def is_generic(obj):
    """泛用物件:條件式裡除大類、位置、控制方外沒有任何條件;物件0 是特定的卡。"""
    if obj["unparsed"] or obj["source"]["kind"] == "自己":
        return False
    return _only_generic_atoms(obj["condition"])


def _only_generic_atoms(condition):
    if condition is None:
        return True
    op = condition["op"]
    if op in ("且", "或"):
        return all(_only_generic_atoms(a) for a in condition["args"])
    if op == "非":
        return _only_generic_atoms(condition["arg"])
    return op in GENERIC_ATOMS


class _Judge:
    """一次查詢的環境:卡片總表索引與「只給條件」的存在性快取。"""

    def __init__(self, cards, query):
        self.query = query
        self.cards = cards
        self.by_id = {}
        for entry in cards:
            self.by_id[entry["id"]] = entry
            for alt in entry.get("alt_ids", ()):
                self.by_id.setdefault(alt, entry)
        self.exists_cache = {}

    def card_fits(self, entry, obj, owner):
        if obj["unparsed"]:
            return False
        if obj["source"]["kind"] == "自己":
            return entry["id"] == owner["id"] or entry["id"] in owner.get(
                "alt_ids", ())
        return eval_condition(obj["condition"], entry) is True

    def object_matches(self, obj, owner):
        q = self.query
        if q["card"] is not None:
            entry = self.by_id.get(q["card"])
            return entry is not None and self.card_fits(entry, obj, owner)
        if q["condition"] is not None:
            if obj["unparsed"]:
                return False
            key = json.dumps([obj["condition"], obj["source"]], sort_keys=True,
                             ensure_ascii=False)
            if key not in self.exists_cache:
                self.exists_cache[key] = any(
                    eval_condition(q["condition"], entry) is True
                    and self.card_fits(entry, obj, owner)
                    for entry in self.cards)
            return self.exists_cache[key]
        return True


def _normalise(query):
    q = {"actions": [], "from_zones": None, "to_zones": None, "card": None,
         "condition": None, "targeting": False, "kinds": None,
         "block_kinds": None, "include_condition": False,
         "include_inferred": False, "replacement": False,
         "polarities": ("做",), "generic_only": False}
    unknown = set(query) - set(q)
    if unknown:
        raise KeyError(f"查詢有不認得的欄位: {sorted(unknown)}")
    q.update(query)
    # 條件段看開關:沒指定段類別時,開關開就把條件段加進預設範圍;
    # 指定了段類別仍受開關閘門,開關關就不看條件段。
    kinds = set(q["kinds"] or DEFAULT_KINDS)
    if q["include_condition"]:
        if q["kinds"] is None:
            kinds.add("條件")
    else:
        kinds.discard("條件")
    if not q["replacement"]:
        kinds.discard("被代替")
    q["allowed_kinds"] = kinds
    q["line_constrained"] = any((q["from_zones"], q["to_zones"],
                                 q["card"] is not None,
                                 q["condition"] is not None, q["targeting"]))
    return q


def _objects_by_id(card):
    return {obj["id"]: obj for obj in card["objects"]}


def segment_hit_lines(seg, card, q, judge, objects):
    """段命中時回傳命中的對象線(可為空列表);不命中回 None。"""
    if seg["unparsed"] or seg["kind"] not in q["allowed_kinds"]:
        return None
    if seg["polarity"] not in q["polarities"]:
        return None
    if any(a not in seg["actions"] for a in q["actions"]):
        return None
    if not q["line_constrained"]:
        return list(seg["lines"])
    hit = []
    for line in seg["lines"]:
        if q["targeting"] and not line["targeting"]:
            continue
        if q["from_zones"] and not zones_match(q["from_zones"], line["from"],
                                               q["include_inferred"]):
            continue
        if q["to_zones"] and not zones_match(q["to_zones"], line["to"],
                                             q["include_inferred"]):
            continue
        obj = objects.get(line["object"])
        if obj is None or not judge.object_matches(obj, card):
            continue
        hit.append(line)
    return hit or None


def run_query(structures, cards, query):
    """全庫結構 + 卡片總表 + 查詢 → 命中結果;一張卡任一分支、任一段命中即命中。"""
    q = _normalise(query)
    judge = _Judge(cards, q)
    hits = []
    for card in structures:
        if card["unparsed"]:
            continue
        objects = _objects_by_id(card)
        matched, generic = [], True
        for block in card["blocks"]:
            if q["block_kinds"] and block["kind"] not in q["block_kinds"]:
                continue
            for _, seg in iter_segments(block):
                lines = segment_hit_lines(seg, card, q, judge, objects)
                if lines is None:
                    continue
                matched.append(seg["id"])
                if not all(is_generic(objects[l["object"]]) for l in lines):
                    generic = False
        if not matched:
            continue
        group = "泛用" if generic else "特定"
        if q["generic_only"] and group != "泛用":
            continue
        hits.append({"id": card["id"], "segments": matched, "group": group})
    groups = {"特定": [h["id"] for h in hits if h["group"] == "特定"],
              "泛用": [h["id"] for h in hits if h["group"] == "泛用"],
              "全部": [h["id"] for h in hits]}
    return {"hits": hits, "groups": groups, "unparsed": []}
