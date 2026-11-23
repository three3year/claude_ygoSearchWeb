import json

from action_query import (SUBSTITUTABLE_KINDS, STATE_ATOMS, _compared_values, _fold, _Judge,
                          _name_text, card_attr, compare_attr,
                          eval_condition, is_this_card, same_different_undecidable)
from archetype_table import setcode_matches
from condition_atoms import referenced_objects
from same_different import SAME, SAME_DIFFERENT
from structure_shape import zone_names

EVERY_CARD = None
ALL_KEY = "整份總表"
TWO_VALUED_OPS = ("大類", "卡名", "卡名包含", "字段")


class CandidateCards(_Judge):

    def __init__(self, cards, structures):
        super().__init__(cards, structures)
        self._index = None
        self._answers = {}
        self._true_sets = {ALL_KEY: set(range(len(cards)))}
        self._distinct = {}
        self._position = {entry["id"]: i for i, entry in enumerate(cards)}

    def of_line(self, owner, line):
        obj = self.objects_of(owner)[line["object"]]
        names = {row["id"]: row for row in owner["names"]}
        from_zones = line["from"]["zones"] if line["from"] else None
        return self._fitting(owner, obj, names, from_zones)

    def candidates(self, owner, ref_obj, names):
        key = (owner["id"], ref_obj["id"])
        if key not in self.candidate_cache:
            self.candidate_cache[key] = []
            self.candidate_cache[key] = self._fitting(owner, ref_obj, names, None)
        return self.candidate_cache[key]

    def _fitting(self, owner, obj, names, from_zones):
        if (obj["unparsed"] or obj["kind"] not in SUBSTITUTABLE_KINDS
                or same_different_undecidable(obj)):
            return []
        if is_this_card(obj, self.objects_of(owner)):
            ids = {owner["id"], *owner.get("alt_ids", ())}
            pool = sorted(self._position[cid] for cid in ids if cid in self._position)
            return self._judge_pool(pool, owner, obj, names, from_zones)
        referenced = self.referenced(obj, owner)
        if referenced is None:
            return []
        if referenced:
            return self._referencing(owner, obj, referenced, names, from_zones)
        key, found = self._true_set(obj["condition"], names, from_zones)
        if key not in self._answers:
            self._answers[key] = [self.cards[i] for i in sorted(found)]
        return self._answers[key]

    def _true_set(self, condition, names, from_zones):
        op = condition["op"] if condition else None
        if op in ("且", "或") and condition["args"]:
            parts = {}
            for arg in condition["args"]:
                key, found = self._true_set(arg, names, from_zones)
                parts[key] = found
            if op == "且":
                parts = {key: found for key, found in parts.items() if key != ALL_KEY}
                combine = set.intersection
            elif ALL_KEY in parts:
                return ALL_KEY, self._true_sets[ALL_KEY]
            else:
                combine = set.union
            if not parts:
                return ALL_KEY, self._true_sets[ALL_KEY]
            if len(parts) == 1:
                return next(iter(parts.items()))
            key = json.dumps([op, sorted(parts)], ensure_ascii=False)
            if key not in self._true_sets:
                self._true_sets[key] = combine(*parts.values())
            return key, self._true_sets[key]
        key = self._shared_key(condition, names, from_zones)
        if key not in self._true_sets and op == "非" and condition["arg"]["op"] in TWO_VALUED_OPS:
            inner = condition["arg"]
            views = self.index.views
            if views and eval_condition(inner, views[0], names, from_zones) is not None:
                self._true_sets[key] = (self._true_sets[ALL_KEY]
                                        - self._true_set(inner, names, from_zones)[1])
            else:
                self._true_sets[key] = set()
        if key not in self._true_sets:
            found = self.index.pool(condition, names)
            pool = range(len(self.cards)) if found is EVERY_CARD else found
            views = self.index.views
            self._true_sets[key] = {i for i in pool if eval_condition(
                condition, views[i], names, from_zones) is True}
        if len(self._true_sets[key]) == len(self.cards):
            return ALL_KEY, self._true_sets[ALL_KEY]
        return key, self._true_sets[key]

    def _referencing(self, owner, obj, referenced, names, from_zones):
        ref_keys = [self._plain_key(owner, ref_obj, names) for ref_obj in referenced]
        key = None
        if None not in ref_keys:
            key = json.dumps([self._shared_key(obj["condition"], names, from_zones),
                              [ref_obj["id"] for ref_obj in referenced], ref_keys],
                             ensure_ascii=False)
            if key in self._answers:
                return self._answers[key]
        found = self._judge_pool(sorted(self._referencing_pool(obj["condition"], names,
                                                               from_zones)),
                                 owner, obj, names, from_zones)
        if key is not None:
            self._answers[key] = found
        return found

    def sharing_pool(self, owner, obj, ref_id, pool, view, from_zones):
        key = (owner["id"], obj["id"], ref_id)
        if key not in self._distinct:
            self._distinct[key] = (*_distinct_bindings(obj["condition"], ref_id, pool), {})
        distinct, tables, narrowed = self._distinct[key]
        if not tables:
            return distinct
        mine = tuple(frozenset(_compared_values(atom, attr, view.entry, view, from_zones))
                     for atom, attr, _ in tables)
        if mine not in narrowed:
            keep = None
            for values, (_, _, table) in zip(mine, tables):
                at = set().union(*(table.get(value, ()) for value in values))
                keep = at if keep is None else keep & at
            narrowed[mine] = [distinct[i] for i in sorted(keep)]
        return narrowed[mine]

    def _plain_key(self, owner, obj, names):
        if (obj["unparsed"] or obj["kind"] not in SUBSTITUTABLE_KINDS
                or same_different_undecidable(obj)):
            return "代不進去"
        if is_this_card(obj, self.objects_of(owner)) or self.referenced(obj, owner) != []:
            return None
        return self._shared_key(obj["condition"], names, None)

    def _referencing_pool(self, condition, names, from_zones):
        found = self.index.pool(condition, names)
        pool = set(range(len(self.cards))) if found is EVERY_CARD else set(found)
        if condition["op"] == "且":
            for arg in condition["args"]:
                if not referenced_objects(arg):
                    pool &= self._true_set(arg, names, from_zones)[1]
        return pool

    def _shared_key(self, condition, names, from_zones):
        have = {name for z in from_zones or () for name in zone_names(z["zone"])}
        seen = set().union(*(self.index.where_zones[kind] for kind in _rows_read(condition)))
        return json.dumps([condition, _referenced_names(condition, names), sorted(have & seen)],
                          sort_keys=True, ensure_ascii=False)

    def _judge_pool(self, pool, owner, obj, names, from_zones):
        return [self.cards[i] for i in pool
                if self.card_fits(self.cards[i], obj, owner, names, from_zones)]

    @property
    def index(self):
        if self._index is None:
            self._index = CardIndex(self.cards, [self.view(entry) for entry in self.cards])
        return self._index


def _referenced_names(condition, names):
    found = {}
    stack = [condition]
    while stack:
        node = stack.pop()
        if not isinstance(node, dict):
            continue
        if "name" in node:
            found[node["name"]] = _name_text(node, names)
        for name_id in node.get("names", ()):
            found[name_id] = _name_text({"name": name_id}, names)
        stack.extend(node.get("args", ()))
        if "arg" in node:
            stack.append(node["arg"])
    return found


def _distinct_bindings(condition, ref_id, pool):
    seen, distinct = set(), []
    for bound in pool:
        reads = _binding_reads(condition, ref_id, bound)
        if reads not in seen:
            seen.add(reads)
            distinct.append(bound)
    tables = []
    for atom in condition["args"] if condition["op"] == "且" else [condition]:
        if (atom["op"] == SAME_DIFFERENT and atom["cmp"] == SAME
                and (atom.get("ref") or {}).get("object") == ref_id):
            for attr in atom["attrs"]:
                table = {}
                for i, bound in enumerate(distinct):
                    for value in _compared_values(atom, attr, bound):
                        table.setdefault(value, set()).add(i)
                tables.append((atom, attr, table))
    return distinct, tables


def _binding_reads(condition, ref_id, bound):
    reads = []
    stack = [condition]
    while stack:
        node = stack.pop()
        if not isinstance(node, dict):
            continue
        if (node.get("ref") or {}).get("object") == ref_id:
            if node["op"] == "屬性比較":
                value = card_attr(bound, node["ref"]["attr"])
                reads.append(frozenset(value) if isinstance(value, set) else value)
            elif node["op"] == SAME_DIFFERENT:
                reads.extend(frozenset(_compared_values(node, attr, bound))
                             for attr in node["attrs"])
        stack.extend(node.get("args", ()))
        if "arg" in node:
            stack.append(node["arg"])
    return tuple(reads)


ROWS_READ = {"大類": "大類", "卡名": "卡名", "卡名包含": "卡名", "卡名範圍": "卡名",
             SAME_DIFFERENT: "卡名", "字段": "字段"}


def _rows_read(condition):
    if condition is None:
        return set()
    found = {ROWS_READ[condition["op"]]} if condition["op"] in ROWS_READ else set()
    for arg in condition.get("args", ()):
        found |= _rows_read(arg)
    return found | _rows_read(condition.get("arg"))


class CardIndex:

    def __init__(self, cards, views):
        self.cards = cards
        self.views = views
        self.by_value = {kind: {} for kind in ("卡名", "字段", "大類")}
        self.where_zones = {kind: set() for kind in self.by_value}
        for i, view in enumerate(views):
            for kind, rows in view.rows().items():
                for value, where in rows:
                    self.by_value[kind].setdefault(value, set()).add(i)
                    self.where_zones[kind] |= where or set()
        self.by_name, self.by_code, self.by_category = (
            self.by_value["卡名"], self.by_value["字段"], self.by_value["大類"])
        self._by_attr = {}
        self._containing = {}

    def pool(self, condition, names):
        if condition is None:
            return EVERY_CARD
        op = condition["op"]
        if op == "且":
            pools = [p for p in (self.pool(a, names) for a in condition["args"])
                     if p is not EVERY_CARD]
            return set.intersection(*pools) if pools else EVERY_CARD
        if op == "或":
            pools = [self.pool(a, names) for a in condition["args"]]
            return EVERY_CARD if EVERY_CARD in pools else set().union(*pools)
        if op == "非":
            return EVERY_CARD
        if op == "大類":
            if condition["value"] == "卡":
                return EVERY_CARD
            return self.by_category.get(condition["value"], set())
        if op in STATE_ATOMS:
            return EVERY_CARD
        if op == "屬性比較":
            return EVERY_CARD if "ref" in condition else self._compared(condition)
        if op == "字段":
            wants = condition.get("setcodes") or []
            return {i for code, at in self.by_code.items()
                    if any(setcode_matches(code, want) for want in wants) for i in at}
        if op in ("卡名", "卡名包含"):
            text = _name_text(condition, names)
            if text is None:
                return set()
            folded = _fold(text)
            if op == "卡名":
                return self.by_name.get(folded, set())
            return self._names_containing(folded)
        if op in ("記載", "卡名範圍", SAME_DIFFERENT):
            return EVERY_CARD
        return set()

    def _compared(self, condition):
        groups = self._by_attr.get(condition["attr"])
        if groups is None:
            groups = self._by_attr[condition["attr"]] = {}
            for i, entry in enumerate(self.cards):
                value = card_attr(entry, condition["attr"])
                key = frozenset(value) if isinstance(value, set) else value
                groups.setdefault(key, (entry, set()))[1].add(i)
        return {i for sample, at in groups.values()
                if compare_attr(condition, sample, None) is True for i in at}

    def _names_containing(self, folded):
        if folded not in self._containing:
            self._containing[folded] = {i for name, at in self.by_name.items()
                                        if folded in name for i in at}
        return self._containing[folded]
