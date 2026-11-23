"""動作索引:攤平出來的列 → 網站讀的 `web/action-data.js`(spec「動作索引」「建置與門檻」、ADR-0013)。

單一接縫:`build_action_index(卡片結構, 卡片總表, 前端索引的卡, 字段表, tag_cards=效果標記表)
→ (文字, 報告)`;
`decode_action_index(文字)` 是格式的唯一讀法(測試與之後的工具用它,不各自解碼)。
讀檔、寫檔、印報告在薄殼 `build_action_index.py`。

格式:`window.ACTION_DATA={…};`,JSON 物件,每個鍵一行;候選卡集合一個一行、卡一張一行,
版控的差異看得出是哪張卡、哪個集合變了。不帶時間與來源雜湊,同樣的輸入兩次產出逐位元組相同。

- `ids`:前端索引的卡號,照前端索引的順序。候選卡集合與字段成員存的是這個順序的位置。
- `actions` `zones` `sides` `kinds` `polarities` `blockKinds` `agents` `causes`:值的清單(照字串排序,
  新值只插進一格),列裡存的是在清單裡的位置;`actions` `zones` `causes` 帶列數:[值, 列數]。
  `causes` 是原因的種類,另含 null(沒寫原因的主動句)與「不限定」(沒寫原因的被動句)。
- `sets`:候選卡集合,鍵是內容的雜湊(內容相同共用一份,別的集合增減不會改到它的鍵)。
  值是位置的清單,或位元集(第 i 位 = 位置 i,little-endian,base64),兩種取短的。
- `cards`:一張卡一行 [卡號, 區塊, 段, 未解析的來源, 引用列, 效果, 誰, 受方, 原因],只列有東西的卡。
  - 區塊:[區塊種類]…,照卡片結構的頂層區塊順序;段與引用列用位置指它。
  - 段:[段 id, 區塊, 段類別, 極性, 是不是做代替的段, [動作詞], [線], 被改的屬性(有才寫)]。
  - 線:[旗標(1 做動作的一方、2 取對象), 從, 到, 物件];從、到是 0(沒有)或 [推得, 區域碼…],
    區域碼 = 區域位置 × 8 + 方的位置;物件是 0(物件表裡找不到:沒有物件)或 [泛用, 集合鍵, 種類];
    種類只在不是候選卡集合時寫(票 12,加在最後一格):1 此卡、2 判不了、3 代不進去。此卡的集合照舊是
    這張卡(指定卡比得到),判不了、代不進去的集合是空的。
  - 未解析的來源:[段類別, 極性, 區塊種類, 旗標, [原文字面的動作詞]];旗標 1 做代替的段、
    2 區塊種類判不出、4 不代入卡時判不了、8 代入卡時判不了、16 引用節點(段類別、極性為 null)。
    字面不含任何動作詞的不寫(帶動作詞的查詢才看未解析組,字面要含查詢的全部動作詞)。
  - 引用列:[區塊, 泛用, 集合鍵, 指定的部分, 效果];指定的部分是 `parts` 的位置。
  - 效果:與段同序的清單,每段對回前端索引的效果句序號(`tx` 的位置),對不回是 null(`clause_map`);
    引用列的效果是引用節點所在的效果句。兩者都加在最後一格,先前的讀法照舊。
  - 誰(票 10):與段同序的清單,每段的誰在 `agents` 的位置;值是寫明的(我方、對手、雙方各自)、
    算我方或不限定(`action_rows.agent_of`)。
  - 受方(票 11):與段同序的清單,每段的受方在 `sides` 的位置;受方是卡、沒有受方的是 null 的位置。
  - 原因(票 11):與段同序的清單,每段的原因碼 = 種類在 `causes` 的位置 × 8 + 方在 `sides` 的位置
    (沒寫方是 null 的位置),同區域碼。
- `parts`:[效果, [[位置, [區塊]]…]]…:引用列的候選卡上,指定的部分不是整張的卡與它的區塊;沒列的看整張。
- `archetypes`:[setcode, 中文名, 集合鍵]…,成員照卡片屬性表(位置條件不設限的列),沒有成員的不寫。
- `noText`:無官方日文的卡號。
"""
import base64
import gzip
import hashlib
import json
import time

from action_rows import (OBJECT_CANDIDATES, OBJECT_THIS, OBJECT_UNDECIDABLE,
                         OBJECT_UNSUBSTITUTABLE, flatten)
from archetype_table import setcode_matches
from clause_map import NUMBER, POSITION, ClauseMap

GLOBAL = "window.ACTION_DATA="
DEFAULT_SIZE_LIMIT = 8_000_000      # spec Q12:8 MB
SIDE_SLOTS = 8                       # 區域碼裡方的位置佔的格數
KEY_LENGTH = 6                       # 集合鍵的起始長度;撞了就整份加長
_B36 = "0123456789abcdefghijklmnopqrstuvwxyz"

FLAG_DOER, FLAG_TARGETING = 1, 2
U_REPLACING, U_BLOCK, U_REASON, U_REASON_SUBSTITUTING, U_REFERENCE = 1, 2, 4, 8, 16
OBJECT_CODES = {OBJECT_THIS: 1, OBJECT_UNDECIDABLE: 2, OBJECT_UNSUBSTITUTABLE: 3}
OBJECT_KINDS = {code: kind for kind, code in OBJECT_CODES.items()}


def build_action_index(structures, cards, frontend_cards, archetypes, tag_cards=(),
                       size_limit=DEFAULT_SIZE_LIMIT):
    """→ (產物文字, 報告)。報告的 problems 非空就是建置失敗(前端索引對不上時文字為 None)。

    `tag_cards` 是效果標記表的卡(效果對應用);沒給時每張卡都沒有效果句,段的效果全留空。"""
    timings = {}
    order = [entry["id"] for entry in frontend_cards]
    at = {cid: i for i, cid in enumerate(order)}
    problems = _missing(structures, cards, at) + _clause_counts(frontend_cards, tag_cards)
    if problems:
        return None, {"problems": problems, "timings": timings}

    started = time.perf_counter()
    index = flatten(structures, cards)
    timings["攤平"] = time.perf_counter() - started

    started = time.perf_counter()
    for row in index.rows:
        if row.line is not None and row.line.object is not None:
            row.line.object.candidates.mask      # 全部對象線的候選卡先算好
    timings["候選卡"] = time.perf_counter() - started

    started = time.perf_counter()
    encoder = _Encoder(index, cards, order, at, ClauseMap(tag_cards, index.texts))
    sections, report = encoder.encode(archetypes)
    problems.extend(encoder.problems)
    text = _serialize(sections)
    timings["編碼"] = time.perf_counter() - started

    data = text.encode("utf-8")
    report["bytes"] = len(data)
    report["gzip_bytes"] = len(gzip.compress(data, compresslevel=6, mtime=0))
    report["size_limit"] = size_limit
    report["section_bytes"] = {name: len(_section(name, value).encode("utf-8"))
                               for name, value in sections}
    if len(data) > size_limit:
        problems.append(f"動作索引 {len(data):,} 位元組,超過門檻 {size_limit:,} 位元組")
    report["problems"] = problems
    report["timings"] = timings
    return text, report


def _missing(structures, cards, at):
    """卡片結構或卡片總表的卡不在前端索引裡:候選卡與列對不到網站上的卡,建置失敗。"""
    problems = []
    for label, ids in (("卡片結構", [s["id"] for s in structures]),
                       ("卡片總表", [entry["id"] for entry in cards])):
        missing = [cid for cid in ids if cid not in at]
        if missing:
            problems.append(f"{label}有 {len(missing)} 張卡不在前端索引裡:"
                            + ", ".join(map(str, missing[:20]))
                            + (" …" if len(missing) > 20 else ""))
    return problems


def _clause_counts(frontend_cards, tag_cards):
    """效果句的序號是前端索引 `tx` 的位置:每張卡的效果句數要和效果標記表相同,否則序號對不上。"""
    counts = {entry["id"]: len(entry.get("clauses") or []) for entry in tag_cards}
    wrong = [f"{entry['id']}(前端索引 {len(entry.get('tx') or [])}、效果標記表 "
             f"{counts.get(entry['id'], 0)})"
             for entry in frontend_cards
             if len(entry.get("tx") or []) != counts.get(entry["id"], 0)]
    if not wrong:
        return []
    return [f"效果句數與前端索引不符 {len(wrong)} 張:" + ", ".join(wrong[:20])
            + (" …" if len(wrong) > 20 else "")]


class _Vocab:
    """值 → 在清單裡的位置;清單照字串排序(None 排最前),所以要先收齊再編號。"""

    def __init__(self):
        self.count = {}

    def add(self, value, rows=0):
        self.count[value] = self.count.get(value, 0) + rows

    def freeze(self):
        self.items = sorted(self.count, key=lambda v: (v is not None, v or ""))
        self.at = {v: i for i, v in enumerate(self.items)}

    def __getitem__(self, value):
        return self.at[value]


class _Encoder:

    def __init__(self, index, cards, order, at, clauses):
        self.index = index
        self.clauses = clauses
        self.order = order
        self.at = at
        self.problems = []
        # 卡片總表位置 → 前端索引位置;順序相同時位元集不必重排。
        self.remap = [at[entry["id"]] for entry in cards]
        self.identity = self.remap == list(range(len(cards)))
        self.cards = cards
        self._mask_sets = {}       # 卡片總表位置的位元集 → 前端位置的 tuple
        self.sets = {}             # 前端位置的 tuple → 集合鍵(最後才定)

    # -- 候選卡集合 --------------------------------------------------------

    def set_of_mask(self, mask):
        if mask not in self._mask_sets:
            positions = _bits(mask)
            if not self.identity:
                positions = sorted(self.remap[i] for i in positions)
            self._mask_sets[mask] = tuple(positions)
        return self.add_set(self._mask_sets[mask])

    def add_set(self, positions):
        self.sets.setdefault(positions, None)
        return positions

    def set_of_ids(self, ids, what):
        positions = set()
        for cid in ids:
            if cid in self.at:
                positions.add(self.at[cid])
            elif cid in self.index.position:
                positions.add(self.remap[self.index.position[cid]])
            else:
                self.problems.append(f"{what}的卡 {cid} 不在前端索引裡")
        return self.add_set(tuple(sorted(positions)))

    # -- 整份 --------------------------------------------------------------

    def encode(self, archetypes):
        index = self.index
        vocab = {name: _Vocab() for name in
                 ("actions", "zones", "sides", "kinds", "polarities", "blockKinds", "agents",
                  "causes")}
        self.vocab = vocab
        for row in index.rows:
            vocab["kinds"].add(row.kind)
            vocab["polarities"].add(row.polarity)
            vocab["blockKinds"].add(row.block_kind)
            vocab["agents"].add(row.agent)
            vocab["sides"].add(row.recipient)
            kind, side = row.cause or (None, None)
            vocab["causes"].add(kind, 1)
            vocab["sides"].add(side)
            for action in row.actions:
                vocab["actions"].add(action, 1)
            zones = set()
            if row.line is not None:
                for pos in (row.line.from_, row.line.to):
                    if pos is not None:
                        zones |= pos.names
                        for _, side in pos.zones:
                            vocab["sides"].add(side)
            for zone in zones:
                vocab["zones"].add(zone, 1)
        for source in index.unresolved:
            vocab["kinds"].add(source.kind)
            vocab["polarities"].add(source.polarity)
            vocab["blockKinds"].add(source.block_kind)
            for action in source.literal_actions:
                vocab["actions"].add(action)
        for blocks in index.blocks.values():
            for _, kind in blocks:
                vocab["blockKinds"].add(kind)
        for v in vocab.values():
            v.freeze()

        card_lines, parts = self.card_lines()
        archetype_rows, empty_archetypes = self.archetypes(archetypes)
        keys = _keys(self.sets)
        sets = sorted(((keys[p], p) for p in self.sets), key=lambda kp: kp[0])

        def keyed(line):
            return _replace_sets(line, keys)

        sections = [
            ("ids", self.order),
            ("actions", [[a, vocab["actions"].count[a]] for a in vocab["actions"].items]),
            ("zones", [[z, vocab["zones"].count[z]] for z in vocab["zones"].items]),
            ("sides", vocab["sides"].items),
            ("kinds", vocab["kinds"].items),
            ("polarities", vocab["polarities"].items),
            ("blockKinds", vocab["blockKinds"].items),
            ("agents", vocab["agents"].items),
            ("causes", [[c, vocab["causes"].count[c]] for c in vocab["causes"].items]),
            ("noText", [cid for cid, _ in index.no_text]),
            ("parts", parts),
            ("archetypes", _Lines([keyed(row) for row in archetype_rows])),
            ("sets", _Keyed([(key, self.encode_set(p)) for key, p in sets])),
            ("cards", _Lines([keyed(line) for line in card_lines])),
        ]
        list_sets = sum(1 for _, p in sets if isinstance(self.encode_set(p), list))
        report = {
            "rows": len(index.rows),
            "segments": len({row.seq for row in index.rows}),
            "line_rows": sum(1 for row in index.rows if row.line is not None),
            "object_lines": sum(1 for row in index.rows
                                if row.line is not None and row.line.object is not None),
            "unresolved": len(index.unresolved),
            "unresolved_written": sum(1 for s in index.unresolved if s.literal_actions),
            "unresolved_references": sum(1 for s in index.unresolved if s.segment is None),
            "references": sum(len(refs) for refs in index.references.values()),
            "part_entries": sum(len(entries) for _, entries in parts),
            "no_text": len(index.no_text),
            "cards": len(card_lines),
            "sets": len(sets),
            "list_sets": list_sets,
            "bitset_sets": len(sets) - list_sets,
            "set_members": sum(len(p) for _, p in sets),
            "largest_set": max((len(p) for _, p in sets), default=0),
            "archetypes": len(archetype_rows),
            "empty_archetypes": empty_archetypes,
            "vocab": {name: len(v.items) for name, v in vocab.items()},
            "clause_mapping": self.mapping,
        }
        return sections, report

    def encode_set(self, positions):
        listed = "[" + ",".join(map(str, positions)) + "]"
        bits = bytearray((len(self.order) + 7) // 8)
        if len(listed) <= 4 * len(bits) // 3 + 4:   # 清單比位元集短就不必做位元集
            return list(positions)
        for p in positions:
            bits[p >> 3] |= 1 << (p & 7)
        return base64.b64encode(bytes(bits)).decode("ascii")

    def card_lines(self):
        index = self.index
        vocab = self.vocab
        by_card = {}

        def entry(card):
            if card not in by_card:
                blocks = index.blocks.get(card, [])
                by_card[card] = {"blocks": {bid: i for i, (bid, _) in enumerate(blocks)},
                                 "kinds": [vocab["blockKinds"][k] for _, k in blocks],
                                 "segments": [], "unresolved": [], "references": [],
                                 "clauses": [], "agents": [], "recipients": [],
                                 "causes": []}
            return by_card[card]

        mapping = {NUMBER: 0, POSITION: 0, None: 0}
        unmapped_cards = set()
        current = None
        for row in index.rows:
            e = entry(row.card)
            if current is None or current[0] != row.seq:
                clause, how = self.clauses.of(row.card, row.place)
                mapping[how] += 1
                if clause is None:
                    unmapped_cards.add(row.card)
                e["clauses"].append(clause)
                e["agents"].append(vocab["agents"][row.agent])
                e["recipients"].append(vocab["sides"][row.recipient])
                kind, side = row.cause or (None, None)
                e["causes"].append(vocab["causes"][kind] * SIDE_SLOTS + vocab["sides"][side])
                segment = [row.segment, e["blocks"][row.block], vocab["kinds"][row.kind],
                           vocab["polarities"][row.polarity], int(row.replacing),
                           sorted(vocab["actions"][a] for a in row.actions), []]
                if row.modified:
                    segment.append(row.modified)
                e["segments"].append(segment)
                current = (row.seq, segment)
            if row.line is not None:
                current[1][6].append(self.line(row.line))
        for source in index.unresolved:
            if not source.literal_actions:
                continue
            flags = ((U_REPLACING if source.replacing else 0)
                     | (U_BLOCK if source.block_reason else 0)
                     | (U_REASON if source.reason else 0)
                     | (U_REASON_SUBSTITUTING if source.reason_substituting else 0)
                     | (U_REFERENCE if source.segment is None else 0))
            entry(source.card)["unresolved"].append([
                None if source.kind is None else vocab["kinds"][source.kind],
                None if source.polarity is None else vocab["polarities"][source.polarity],
                vocab["blockKinds"][source.block_kind], flags,
                sorted(vocab["actions"][a] for a in source.literal_actions)])
        effects = sorted({ref.effect for refs in index.references.values() for ref in refs})
        effect_at = {effect: i for i, effect in enumerate(effects)}
        part_entries = {effect: {} for effect in effects}
        unmapped_references = 0
        for (card, _), refs in sorted(index.references.items(),
                                      key=lambda kv: (index.card_order[kv[0][0]], kv[0][1])):
            e = entry(card)
            for ref in refs:
                clause, _ = self.clauses.of(card, ref.place)
                unmapped_references += clause is None
                e["references"].append([
                    e["blocks"][ref.block], int(ref.generic),
                    self.set_of_ids(ref.candidates, f"卡 {card} 的引用列"),
                    effect_at[ref.effect], clause])
                for cid in ref.candidates:
                    if cid not in index.blocks or cid not in self.at:
                        continue
                    part = index.part(cid, ref.effect)
                    blocks = [bid for bid, _ in index.blocks[cid]]
                    if list(part) != blocks:
                        part_entries[ref.effect][self.at[cid]] = sorted(
                            blocks.index(bid) for bid in part)
        parts = [[json.loads(effect), [[p, b] for p, b in sorted(part_entries[effect].items())]]
                 for effect in effects]
        lines = []
        for card in sorted(by_card, key=lambda cid: self.at[cid]):
            e = by_card[card]
            lines.append([card, e["kinds"], e["segments"], e["unresolved"], e["references"],
                          e["clauses"], e["agents"], e["recipients"], e["causes"]])
        self.mapping = {"segments": sum(mapping.values()), "by_number": mapping[NUMBER],
                        "by_position": mapping[POSITION], "unmapped": mapping[None],
                        "unmapped_cards": sorted(unmapped_cards, key=lambda cid: self.at[cid]),
                        "references": sum(len(refs) for refs in index.references.values()),
                        "unmapped_references": unmapped_references}
        return lines, parts

    def line(self, line):
        flags = (FLAG_DOER if line.doer else 0) | (FLAG_TARGETING if line.targeting else 0)
        obj = 0
        if line.object is not None:
            obj = [int(line.object.generic), self.set_of_mask(line.object.candidates.mask)]
            if line.object.kind != OBJECT_CANDIDATES:
                obj.append(OBJECT_CODES[line.object.kind])
        return [flags, self.position(line.from_), self.position(line.to), obj]

    def position(self, pos):
        if pos is None:
            return 0
        codes = sorted(self.vocab["zones"][zone] * SIDE_SLOTS + self.vocab["sides"][side]
                       for zone, side in pos.zones)
        return [int(pos.inferred), *codes]

    def archetypes(self, archetypes):
        """字段的成員:卡片屬性表裡位置條件不設限的 setcode 列(與查詢「給條件 字段」同一判法)。"""
        wants = {}
        for row in archetypes:
            wants.setdefault(row["setcode"] & 0x0FFF, []).append(row["setcode"])
        members = {row["setcode"]: [] for row in archetypes}
        for i, view in enumerate(self.index.views):
            found = set()
            for have in view.setcodes(None):
                for want in wants.get(have & 0x0FFF, ()):
                    if setcode_matches(have, want):
                        found.add(want)
            for want in found:
                members[want].append(self.remap[i])
        rows, empty = [], 0
        for row in sorted(archetypes, key=lambda r: r["setcode"]):
            if not members[row["setcode"]]:
                empty += 1
                continue
            rows.append([row["setcode"], row.get("name_zh"),
                         self.add_set(tuple(sorted(members[row["setcode"]])))])
        return rows, empty


def _bits(mask):
    """位元集 → 設了的位(由小到大)。"""
    text = bin(mask)[:1:-1]
    out = []
    i = text.find("1")
    while i >= 0:
        out.append(i)
        i = text.find("1", i + 1)
    return out


def _keys(sets):
    """集合(位置的 tuple)→ 鍵:內容雜湊的 base36 前綴。撞了就整份加長一格,鍵仍只看內容。"""
    digests = {}
    for positions in sets:
        raw = hashlib.sha1(",".join(map(str, positions)).encode("ascii")).digest()
        n = int.from_bytes(raw, "big")
        chars = []
        while n:
            n, r = divmod(n, 36)
            chars.append(_B36[r])
        digests[positions] = "".join(chars)
    length = KEY_LENGTH
    while len({d[:length] for d in digests.values()}) < len(digests):
        length += 1
    return {positions: d[:length] for positions, d in digests.items()}


def _replace_sets(value, keys):
    """列裡暫放的集合(tuple)換成鍵。"""
    if isinstance(value, tuple):
        return keys[value]
    if isinstance(value, list):
        return [_replace_sets(v, keys) for v in value]
    return value


class _Lines(list):
    """一個元素一行的陣列。"""


class _Keyed(list):
    """一個鍵一行的物件:[(鍵, 值)]。"""


def _dump(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _section(name, value):
    if isinstance(value, _Lines):
        body = "[\n" + ",\n".join(map(_dump, value)) + "\n]"
    elif isinstance(value, _Keyed):
        body = "{\n" + ",\n".join(f"{_dump(k)}:{_dump(v)}" for k, v in value) + "\n}"
    else:
        body = _dump(value)
    return f"{_dump(name)}:{body}"


def _serialize(sections):
    return GLOBAL + "{\n" + ",\n".join(_section(n, v) for n, v in sections) + "\n};\n"


# -- 讀回 --------------------------------------------------------------------

def decode_action_index(text):
    """產物文字 → 讀好的動作索引(卡號、值都換回來,候選卡是卡號的 frozenset)。

    {"actions": {動作詞: 列數}, "zones": {區域: 列數}, "no_text": [卡號],
     "archetypes": {setcode: {"name", "members"}},
     "cards": {卡號: {"blocks": [區塊種類], "segments": [段], "unresolved": [...],
                      "references": [...]}}}
    段與引用列的 `clause` 是對回的效果句序號(前端索引 `tx` 的位置),對不回是 None。
    段的 `agent` 是誰(寫明的值、算我方或不限定);`recipient` 是受方是玩家時的方(否則 None);
    `cause` 是 (種類, 方或 None),沒寫原因的被動句是 (不限定, None)、主動句是 None。
    """
    if not (text.startswith(GLOBAL) and text.endswith(";\n")):
        raise ValueError("不是動作索引")
    raw = json.loads(text[len(GLOBAL):-2])
    ids = raw["ids"]
    sides = raw["sides"]
    zones = [z for z, _ in raw["zones"]]
    actions = [a for a, _ in raw["actions"]]
    kinds, polarities, block_kinds = raw["kinds"], raw["polarities"], raw["blockKinds"]
    agents = raw["agents"]
    causes = [c for c, _ in raw["causes"]]

    def cause(code):
        kind, side = causes[code // SIDE_SLOTS], sides[code % SIDE_SLOTS]
        return None if kind is None else (kind, side)

    sets = {key: _decode_set(value, ids) for key, value in raw["sets"].items()}
    parts = [(effect, {ids[p]: blocks for p, blocks in entries})
             for effect, entries in raw["parts"]]

    def position(value):
        if value == 0:
            return None
        inferred, *codes = value
        return {"inferred": bool(inferred),
                "zones": frozenset((zones[c // SIDE_SLOTS], sides[c % SIDE_SLOTS])
                                   for c in codes)}

    def line(value):
        flags, frm, to, obj = value
        return {"doer": bool(flags & FLAG_DOER), "targeting": bool(flags & FLAG_TARGETING),
                "from": position(frm), "to": position(to),
                "object": None if obj == 0 else {
                    "generic": bool(obj[0]), "candidates": sets[obj[1]],
                    "kind": OBJECT_KINDS[obj[2]] if len(obj) > 2 else OBJECT_CANDIDATES}}

    def segment(value):
        sid, block, kind, pol, replacing, acts, lines, *modified = value
        return {"id": sid, "block": block, "kind": kinds[kind], "polarity": polarities[pol],
                "replacing": bool(replacing), "actions": frozenset(actions[a] for a in acts),
                "lines": [line(v) for v in lines],
                "modified": modified[0] if modified else None}

    def unresolved(value):
        kind, pol, block_kind, flags, acts = value
        return {"kind": None if kind is None else kinds[kind],
                "polarity": None if pol is None else polarities[pol],
                "block_kind": block_kinds[block_kind],
                "replacing": bool(flags & U_REPLACING), "block_reason": bool(flags & U_BLOCK),
                "reason": bool(flags & U_REASON),
                "reason_substituting": bool(flags & U_REASON_SUBSTITUTING),
                "reference": bool(flags & U_REFERENCE),
                "literal_actions": frozenset(actions[a] for a in acts)}

    def reference(value):
        block, generic, key, part, clause = value
        effect, blocks = parts[part]
        return {"block": block, "generic": bool(generic), "candidates": sets[key],
                "effect": effect, "parts": blocks, "clause": clause}

    cards = {}
    for cid, blocks, segs, unres, refs, clauses, segment_agents, recipients, seg_causes             in raw["cards"]:
        cards[cid] = {"blocks": [block_kinds[k] for k in blocks],
                      "segments": [dict(segment(v), clause=c, agent=agents[a],
                                        recipient=sides[r], cause=cause(k))
                                   for v, c, a, r, k in zip(segs, clauses, segment_agents,
                                                            recipients, seg_causes)],
                      "unresolved": [unresolved(v) for v in unres],
                      "references": [reference(v) for v in refs]}
    return {"ids": ids,
            "actions": dict(map(tuple, raw["actions"])),
            "zones": dict(map(tuple, raw["zones"])),
            "no_text": raw["noText"],
            "archetypes": {code: {"name": name, "members": sets[key]}
                           for code, name, key in raw["archetypes"]},
            "cards": cards}


def _decode_set(value, ids):
    if isinstance(value, list):
        return frozenset(ids[p] for p in value)
    bits = int.from_bytes(base64.b64decode(value), "little")
    return frozenset(ids[p] for p in _bits(bits))
