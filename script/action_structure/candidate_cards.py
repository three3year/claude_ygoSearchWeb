"""候選卡:卡片總表裡代得進一條對象線的物件的卡(spec「建置與門檻」、Q13)。

判法照查詢判斷(`action_query._Judge.card_fits`),這裡只改算法,四招:
- 候選池:先照條件式從卡片總表的索引(卡名、setcode、大類,與屬性比較用到的各屬性值)取出
  「一定包含全部答案」的一批卡,只對池裡的卡逐張判。池只能多不能少,答案與逐張掃整份總表相同;
  放不窄的條件(非、記載、異同、狀態…)就退回整份總表。
- 拆項:且 = 每一項都判 True,或 = 有一項判 True(`eval_condition` 的三值邏輯),所以判 True 的卡
  是各項判 True 的卡取交集/聯集;各項分開算,不同物件的同一項(「表側表示の」「自分フィールドの」)只算一次。
- 共用:答案照「判法讀得到的東西」記住(`_shared_key`),不同卡、不同線只要這些相同就共用。
- 引用:含引用的物件不拆,對池裡的卡逐張判 `card_fits`;被引用物件的候選卡去掉代入結果一定相同的
  (`sharing_pool`),只在被引用物件都不是此卡、不再含引用時共用。此卡只試這張卡自己。
"""
import json

from action_query import (SUBSTITUTABLE_KINDS, STATE_ATOMS, _compared_values, _fold, _Judge,
                          _name_text, card_attr, compare_attr,
                          eval_condition, is_this_card, same_different_undecidable)
from archetype_table import setcode_matches
from condition_atoms import referenced_objects
from same_different import SAME, SAME_DIFFERENT
from structure_shape import zone_names

EVERY_CARD = None   # 候選池:不設限,整份總表
ALL_KEY = "整份總表"  # 每張卡都判 True 的條件式共用的鍵
# 這幾種原子判不了(None)只看條件式本身(名稱解析不出、字段沒列 setcode),與代入哪張卡無關:
# 一張卡判不了就張張判不了,否則張張是 True/False,所以「非」它 = 總表減去它判 True 的卡。
TWO_VALUED_OPS = ("大類", "卡名", "卡名包含", "字段")


class CandidateCards(_Judge):
    """一份卡片總表與全庫卡片結構上的候選卡計算。"""

    def __init__(self, cards, structures):
        super().__init__(cards, structures)
        self._index = None
        self._answers = {}     # 整個條件式的 _shared_key → 候選卡(總表條目,照總表順序)
        # 條件式或其中一項的鍵 → 判 True 的卡在總表的位置;ALL_KEY 是整份總表。
        self._true_sets = {ALL_KEY: set(range(len(cards)))}
        self._distinct = {}    # (卡號, 物件 id, 被引用物件 id) → 被引用物件去掉同值後的候選卡
        self._position = {entry["id"]: i for i, entry in enumerate(cards)}

    def of_line(self, owner, line):
        """`owner` 這張卡的一條對象線上,物件的候選卡(卡片總表條目,照總表順序)。
        位置條件看這條線的「從」。"""
        obj = self.objects_of(owner)[line["object"]]
        names = {row["id"]: row for row in owner["names"]}
        from_zones = line["from"]["zones"] if line["from"] else None
        return self._fitting(owner, obj, names, from_zones)

    def candidates(self, owner, ref_obj, names):
        """被引用物件的候選卡(條件式含引用時 `card_fits` 會來要):與 `_Judge.candidates` 同一個快取
        與成環保護,只是改走這裡的算法。"""
        key = (owner["id"], ref_obj["id"])
        if key not in self.candidate_cache:
            self.candidate_cache[key] = []
            self.candidate_cache[key] = self._fitting(owner, ref_obj, names, None)
        return self.candidate_cache[key]

    def _fitting(self, owner, obj, names, from_zones):
        # 與 card_fits 開頭同一組判斷:不看代入的是哪張卡,整個物件就代不進去。
        if (obj["unparsed"] or obj["kind"] not in SUBSTITUTABLE_KINDS
                or same_different_undecidable(obj)):
            return []
        if is_this_card(obj, self.objects_of(owner)):
            # 此卡只有這張卡(含別號)代得進去。
            ids = {owner["id"], *owner.get("alt_ids", ())}
            pool = sorted(self._position[cid] for cid in ids if cid in self._position)
            return self._judge_pool(pool, owner, obj, names, from_zones)
        referenced = self.referenced(obj, owner)
        if referenced is None:
            return []   # 被引用物件找不到或解析不出:card_fits 一律不符
        if referenced:
            return self._referencing(owner, obj, referenced, names, from_zones)
        # 不含引用、不是此卡時 card_fits 就是條件式判 True(開頭的判斷上面做過了)。
        key, found = self._true_set(obj["condition"], names, from_zones)
        if key not in self._answers:
            self._answers[key] = [self.cards[i] for i in sorted(found)]
        return self._answers[key]

    def _true_set(self, condition, names, from_zones):
        """條件式判 True 的卡 → (鍵, 總表位置的集合;呼叫方不可改)。判 True 的卡相同的條件式盡量同鍵:
        且裡每張卡都判 True 的項(「表側表示の」「自分フィールドの」這類狀態)拿掉不影響交集,
        「モンスター１体」與「表側表示のモンスター１体」就共用同一份答案。"""
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
        """含引用的物件:對候選池逐張判 card_fits(要在被引用物件的候選卡裡找一組代入)。
        被引用物件都是不含引用、不是此卡的物件時,card_fits 讀得到的只有條件式、名稱字面、「從」
        與各被引用物件的候選卡,而後者又由它自己的共用鍵決定,所以照這些共用;否則答案看這張卡的物件表,不共用。"""
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
        """被引用物件要逐張試代入的候選卡(取代 `_Judge.sharing_pool`,只會更少、不會漏掉找得到的那一組):
        - 判法從代入的卡讀到的值(`_binding_reads`)相同的只留第一張:它們代入的結果一定相同,
          而 card_fits 只問找不找得到一組。幾千張候選卡常只有幾十種值。
        - 條件式頂層每個對這個物件的異同 相同,每個屬性都要有交集才成立(`same_different_fits`),
          所以只取每個屬性都與代入的卡有交集的(`_Judge.sharing_pool` 只看第一個屬性)。
        「與那張卡同族同屬性不同名」這類物件因此不必對每張卡試幾千次。"""
        key = (owner["id"], obj["id"], ref_id)
        if key not in self._distinct:
            self._distinct[key] = (*_distinct_bindings(obj["condition"], ref_id, pool), {})
        distinct, tables, narrowed = self._distinct[key]
        if not tables:
            return distinct
        # 篩法只看代入的卡在這幾個屬性上的值(多數卡的種族、屬性與別張相同),同值的篩一次。
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
        """被引用物件的候選卡(「從」不看)由什麼決定:代不進去的物件一律沒有候選卡;
        不含引用、不是此卡的物件看共用鍵;其餘(此卡、又有引用)回 None,不共用。"""
        if (obj["unparsed"] or obj["kind"] not in SUBSTITUTABLE_KINDS
                or same_different_undecidable(obj)):
            return "代不進去"
        if is_this_card(obj, self.objects_of(owner)) or self.referenced(obj, owner) != []:
            return None
        return self._shared_key(obj["condition"], names, None)

    def _referencing_pool(self, condition, names, from_zones):
        """含引用的條件式的候選池:頂層是且時,不含引用的那幾項與綁哪張卡無關,
        都要判 True,取它們判 True 的卡;其餘照索引。"""
        found = self.index.pool(condition, names)
        pool = set(range(len(self.cards))) if found is EVERY_CARD else set(found)
        if condition["op"] == "且":
            for arg in condition["args"]:
                if not referenced_objects(arg):
                    pool &= self._true_set(arg, names, from_zones)[1]
        return pool

    def _shared_key(self, condition, names, from_zones):
        """不含引用、不是此卡的物件,判法讀得到的只有:條件式、條件式用到的名稱字面(名稱 id 是各卡自己的),
        與「從」——而「從」只透過卡片屬性表的位置條件起作用,只記它落在條件式讀的那幾種列提到的區域
        (「モンスター１体」只讀大類的列;全庫大類的列幾乎不帶位置條件,各種「從」就共用一份答案)。
        物件的種類、數量、來源在 `_fitting` 開頭已判完。"""
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
    """條件式引用到的名稱 id → 字面(解析不出的給 None),給快取鍵用。"""
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
    """→ (讀到的值各留一張的候選卡, [(異同 相同 原子, 屬性, 值 → 那些卡在清單裡的位置)])。"""
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
    """`eval_condition` 從代入 `ref_id` 的卡 `bound` 讀到的全部值:只有引用它的屬性比較(讀 card_attr)
    與異同(讀 `_compared_values`)會讀綁定的卡。"""
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


# 原子 → 它的判法讀卡片屬性表的哪種列(`CardView.rows` 的鍵);只有這些列帶位置條件,判法才看「從」。
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
    """卡片總表的索引:值 → 卡在總表裡的位置集合。卡名、setcode、大類取卡片屬性表裡每一列
    (不看位置條件),屬性比較用到的屬性第一次用到才分組。"""

    def __init__(self, cards, views):
        self.cards = cards
        self.views = views
        # 每種列:值 → 位置集合,與這種列的位置條件提到過的區域。
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
        """一定包含「條件式判 True 的卡」的位置集合;放不窄回 EVERY_CARD。
        分派順序與 `eval_condition` 相同;它判 None 的原子(認不得、名稱解析不出)不會是 True,池是空的。"""
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
        """屬性比較(比值,不比引用)只看代入的卡這個屬性的值:同值的卡結果相同,每組判一張就好。"""
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
