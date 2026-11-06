"""查詢判斷(純函式):全庫卡片結構 + 查詢 → 命中的卡、命中段與分組。

查詢(spec「查詢判斷」;鍵名英文,值用 GLOSSARY 的詞):
  actions           動作詞列表,全部都要在段內
  from_zones / to_zones  區域(字串,或 {"zone", "side"}),逐條對象線比;子區域算在上位區域內
  card              指定卡(卡片密碼),代入對象物件
  condition         只給條件:卡片總表裡存在一張實卡同時滿足查詢條件與物件條件
                    (查詢側的原子不帶名稱表,直接寫值:{"op": "字段", "setcodes": [...]}、
                    {"op": "卡名", "text": ...}、{"op": "卡名包含", "text": ...})
  targeting         True 時只算有標取對象的線
  kinds             段類別範圍(預設 效果、代價、召喚手續)
  block_kinds       區塊種類範圍(預設全部)
  include_condition 條件段開關(預設關)
  include_inferred  推得終點開關(預設關):推得值與繼承自推得值只在開時算
  replacement       查詢含「代替」時才看被代替段(票 08)
  polarities        極性範圍(預設只算「做」)
  generic_only      只查泛用組(票 07)

結果:{"hits": [{"id", "segments", "group"}],
      "groups": {"特定", "泛用", "全部", "未解析"}(各組是卡片密碼列表;未解析組的張數 = 長度),
      "unparsed": [{"id", "reason", "segments": [{"segment", "reason", "text"}]}]}

未解析組(spec「解析不出的段怎麼呈現」):不靜默略過。兩種來源:
- 整張無官方日文的卡:任何查詢都列,`reason` = 無官方日文、`segments` 為空。
- 字面含查詢動作詞、但結構不完整所以沒命中的段:段本身標解析不出,或段的對象線
  引用的物件標解析不出(指定卡代入時判不了),或所在區塊標解析不出。
  「字面」比的是整段原文而不是只比原述語字面:子句切錯時原述語字面也是錯的
  (「このカードが特殊召喚に成功した時、…めくる事ができる」切出的述語是「めくる…」),
  多列總比漏列好。動作詞經同義表換成述語字面(「破壞」→「破壊」)再比。
一張卡任一段命中就在命中組、不再列進未解析組;段類別、極性的篩選對未解析組同樣生效;
區塊種類被篩掉的區塊,只有種類判不出(標解析不出)的才列,因為那才可能是靜默漏掉。

判斷卡 X 能否當某物件(spec「條件式」):X 的卡名與字段來自它自己的卡片結構的卡片屬性表
(官方卡名、setcode,加「〜として扱う」的列);帶位置條件的列只在該對象線的「從」落在
該位置時算,「從」沒寫就只算任何位置的列。無官方日文的卡沒有結構,退回卡片總表的
name_ja 與 setcode。名稱比對雙方先全半形折疊。
"""
import json

from archetype_table import fold_width, setcode_matches, split_setcode
from attribute_words import ATTRIBUTE_JA, RACE_JA
from segment_extract import PREDICATE_STEMS
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


class CardView:
    """代入物件的那張卡:卡片總表條目 + 它自己的卡片結構(可無),依位置給出卡名與 setcode。"""

    def __init__(self, entry, structure=None):
        self.entry = entry
        tables = structure["attributes"] if structure and not structure["unparsed"] else None
        if tables:
            name_rows, archetype_rows = tables["name"], tables["archetype"]
        else:
            name_rows = [{"value": entry["name_ja"], "where": None}]
            archetype_rows = [{"value": code, "where": None}
                              for code in split_setcode(entry.get("setcode") or 0)]
        # 折疊與位置條件只算一次:只給條件的查詢會對幾千張卡反覆代入。
        self._names = [(fold_width(r["value"]), self._where(r)) for r in name_rows]
        self._codes = [(r["value"], self._where(r)) for r in archetype_rows]

    @staticmethod
    def _where(row):
        return None if row["where"] is None else {w["zone"] for w in row["where"]}

    @staticmethod
    def _pick(rows, from_zones):
        """位置條件 None 任何位置都算;有條件的要「從」落在那些區域(含上位區域)。"""
        have = None
        out = []
        for value, where in rows:
            if where is None:
                out.append(value)
                continue
            if not from_zones:
                continue
            if have is None:
                have = {name for z in from_zones for name in _zone_names(z["zone"])}
            if where & have:
                out.append(value)
        return out

    def names(self, from_zones):
        return self._pick(self._names, from_zones)

    def setcodes(self, from_zones):
        return self._pick(self._codes, from_zones)


def _position_sensitive(condition):
    """條件式裡有沒有看位置的原子(卡名、卡名包含、字段:卡片屬性表的列帶位置條件)。"""
    stack = [condition]
    while stack:
        node = stack.pop()
        if not isinstance(node, dict):
            continue
        if node.get("op") in ("卡名", "卡名包含", "字段"):
            return True
        stack.extend(node.get("args", ()))
        if "arg" in node:
            stack.append(node["arg"])
    return False


def _referenced_names(condition, names):
    """條件式引用到的名稱 id → 字面(解析不出的給 None),給快取鍵用。"""
    found = {}
    stack = [condition]
    while stack:
        node = stack.pop()
        if not isinstance(node, dict):
            continue
        if "name" in node:
            found[node["name"]] = _name_text(node, names)
        stack.extend(node.get("args", ()))
        if "arg" in node:
            stack.append(node["arg"])
    return found


def _name_text(condition, names):
    """原子引用名稱表的 id(結構側)或直接帶字面(查詢側)。"""
    if "text" in condition:
        return condition["text"]
    row = names.get(condition.get("name"))
    return None if row is None or row["unparsed"] else row["text"]


def eval_condition(condition, view, names=None, from_zones=None):
    """條件式對一張卡(CardView):True / False / None(含解析不出,判不了)。
    `names` 是物件所屬那張卡的名稱表(id → 列),`from_zones` 是該對象線的「從」。"""
    if condition is None:
        return True
    names = names or {}
    op = condition["op"]
    if op == "且":
        results = [eval_condition(a, view, names, from_zones)
                   for a in condition["args"]]
        return None if None in results else all(results)
    if op == "或":
        results = [eval_condition(a, view, names, from_zones)
                   for a in condition["args"]]
        if True in results:
            return True
        return None if None in results else False
    if op == "非":
        inner = eval_condition(condition["arg"], view, names, from_zones)
        return None if inner is None else not inner
    if op == "大類":
        if condition["value"] == "卡":
            return True
        return bool(view.entry["type"] & CATEGORY_BITS[condition["value"]])
    if op == "字段":
        wants = condition.get("setcodes") or []
        if not wants:
            return None
        return any(setcode_matches(have, want)
                   for have in view.setcodes(from_zones) for want in wants)
    if op in ("卡名", "卡名包含"):
        text = _name_text(condition, names)
        if text is None:
            return None
        folded = fold_width(text)
        if op == "卡名":
            return folded in view.names(from_zones)
        return any(folded in name for name in view.names(from_zones))
    if op == "屬性比較":
        return compare_attribute(condition, view.entry)
    return None


_COMPARATORS = {"=": lambda a, b: a == b, "≥": lambda a, b: a >= b,
                "≤": lambda a, b: a <= b, ">": lambda a, b: a > b,
                "<": lambda a, b: a < b}


def compare_attribute(condition, entry):
    """屬性比較原子(種族、屬性、等級)對一張卡片總表條目;魔陷沒有種族等級,判 False。"""
    attr, cmp, value = condition["attr"], condition["cmp"], condition["value"]
    if not entry["type"] & CATEGORY_BITS["怪獸"]:
        return False
    if attr == "種族":
        return cmp == "=" and bool(entry["race"] & RACE_JA.get(value, 0))
    if attr == "屬性":
        return cmp == "=" and bool(entry["attribute"] & ATTRIBUTE_JA.get(value, 0))
    if attr == "等級":
        if entry["level"] is None or cmp not in _COMPARATORS:
            return None
        return _COMPARATORS[cmp](entry["level"], value)
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

    def __init__(self, cards, structures, query):
        self.query = query
        self.cards = cards
        self.by_id = {}
        for entry in cards:
            self.by_id[entry["id"]] = entry
            for alt in entry.get("alt_ids", ()):
                self.by_id.setdefault(alt, entry)
        self.structure_by_id = {s["id"]: s for s in structures}
        self.views = {}
        self.exists_cache = {}

    def view(self, entry):
        if entry["id"] not in self.views:
            self.views[entry["id"]] = CardView(
                entry, self.structure_by_id.get(entry["id"]))
        return self.views[entry["id"]]

    def card_fits(self, entry, obj, owner, names, from_zones):
        if obj["unparsed"]:
            return False
        if obj["source"]["kind"] == "自己":
            return entry["id"] == owner["id"] or entry["id"] in owner.get(
                "alt_ids", ())
        return eval_condition(obj["condition"], self.view(entry), names,
                              from_zones) is True

    def object_matches(self, obj, owner, names, line):
        q = self.query
        from_zones = line["from"]["zones"] if line["from"] else None
        if q["card"] is not None:
            entry = self.by_id.get(q["card"])
            return entry is not None and self.card_fits(entry, obj, owner, names,
                                                        from_zones)
        if q["condition"] is not None:
            if obj["unparsed"]:
                return False
            # 快取鍵只看條件式本身(名稱換成字面)與來源:幾千張卡的「モンスター１体」只對
            # 總表掃一次;「從」只在條件式有看位置的原子(卡名、字段)時才進鍵。
            referenced = _referenced_names(obj["condition"], names)
            key = json.dumps([obj["condition"], obj["source"], referenced,
                              from_zones if _position_sensitive(obj["condition"]) else None],
                             sort_keys=True, ensure_ascii=False)
            if key not in self.exists_cache:
                self.exists_cache[key] = any(
                    self.card_fits(entry, obj, owner, names, from_zones)
                    for entry in self.query_matches())
            return self.exists_cache[key]
        return True

    def query_matches(self):
        """滿足查詢條件的卡片總表條目,整次查詢只算一次。"""
        if not hasattr(self, "_query_matches"):
            self._query_matches = [
                entry for entry in self.cards
                if eval_condition(self.query["condition"], self.view(entry)) is True]
        return self._query_matches


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


def action_literals(actions):
    """查詢動作詞 → 每個動作詞在同義表裡的述語字面列表;同義表沒有的動作詞給空列表,
    字面就不可能含它。"""
    return [[stem for stem, action, _ in PREDICATE_STEMS if action == want]
            for want in actions]


def literal_has_actions(text, literals):
    """段的原文字面含每一個查詢動作詞(各取任一述語字面)才算「字面含查詢動作詞」;
    查詢沒給動作詞時沒有字面可比,不算。"""
    if not literals:
        return False
    return all(any(stem in text for stem in stems) for stems in literals)


def incomplete_reason(seg, objects):
    """段沒命中時,它結構不完整的原因;結構完整(只是不符查詢)回 None。
    先看段自己,再看對象線引用的物件(物件解析不出時指定卡代入判不了)。"""
    if seg["unparsed"]:
        return seg["unparsed"]["reason"]
    for line in seg["lines"]:
        obj = objects.get(line["object"])
        if obj is not None and obj["unparsed"]:
            return obj["unparsed"]["reason"]
    return None


def segment_in_scope(seg, q):
    """段類別、極性的篩選;命中與未解析組共用,被篩掉的段兩邊都不列。"""
    return seg["kind"] in q["allowed_kinds"] and seg["polarity"] in q["polarities"]


def segment_hit_lines(seg, card, q, judge, objects, names):
    """段命中時回傳命中的對象線(可為空列表);不命中回 None。"""
    if seg["unparsed"] or not segment_in_scope(seg, q):
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
        if obj is None or not judge.object_matches(obj, card, names, line):
            continue
        hit.append(line)
    return hit or None


def run_query(structures, cards, query):
    """全庫結構 + 卡片總表 + 查詢 → 命中結果;一張卡任一分支、任一段命中即命中。"""
    q = _normalise(query)
    judge = _Judge(cards, structures, q)
    literals = action_literals(q["actions"])
    hits, unparsed = [], []
    for card in structures:
        if card["unparsed"]:
            unparsed.append({"id": card["id"],
                             "reason": card["unparsed"]["reason"],
                             "segments": []})
            continue
        objects = _objects_by_id(card)
        names = {row["id"]: row for row in card["names"]}
        matched, generic, incomplete = [], True, []
        for block in card["blocks"]:
            # 區塊種類被篩掉:種類判不出的區塊才可能是靜默漏掉,列進未解析組。
            skipped = q["block_kinds"] and block["kind"] not in q["block_kinds"]
            if skipped and not block["unparsed"]:
                continue
            for _, seg in iter_segments(block):
                lines = None if skipped else segment_hit_lines(
                    seg, card, q, judge, objects, names)
                if lines is not None:
                    matched.append(seg["id"])
                    if not all(is_generic(objects[l["object"]]) for l in lines):
                        generic = False
                    continue
                if not segment_in_scope(seg, q):
                    continue
                reason = (block["unparsed"]["reason"] if skipped
                          else incomplete_reason(seg, objects))
                if reason and literal_has_actions(seg["text"], literals):
                    incomplete.append({"segment": seg["id"], "reason": reason,
                                       "text": seg["text"]})
        if matched:
            group = "泛用" if generic else "特定"
            if q["generic_only"] and group != "泛用":
                continue
            hits.append({"id": card["id"], "segments": matched, "group": group})
        elif incomplete:
            unparsed.append({"id": card["id"], "reason": None,
                             "segments": incomplete})
    groups = {"特定": [h["id"] for h in hits if h["group"] == "特定"],
              "泛用": [h["id"] for h in hits if h["group"] == "泛用"],
              "全部": [h["id"] for h in hits],
              "未解析": [u["id"] for u in unparsed]}
    return {"hits": hits, "groups": groups, "unparsed": unparsed}
