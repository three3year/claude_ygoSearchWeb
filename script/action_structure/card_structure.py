"""卡片結構的形狀與建置管線(純函式)。

單一接縫:`build_structures(卡片總表條目, 官方 DB 文本條目, 字段表列) → (structures, report)`。
讀檔、寫檔、印報告都在薄殼 `build_structure.py`;時間與來源雜湊由薄殼給進來、
只進 report 不進產物,所以同一份輸入兩次建置的產物逐位元組相同。
字段表(`data/archetypes.json`,由 build_archetypes.py 建出)把「X」換成 setcode;
名稱表與卡片屬性表的規則在 `names_attributes`。

形狀(鍵名英文、值用 GLOSSARY 的詞;每格都允許 None 或「解析不出」,
後面的票只填值、不改形狀):

卡片 card
  id / name_ja / unparsed(整張未解析:{"reason": "無官方日文"})
  attributes  卡片屬性表:{屬性名: [{"value", "where"(位置條件,None=任何位置), "source", "span", "text"}]}
  names       名稱表:[{"id", "text", "source"(「」引用 / 宣言), "unparsed"}]
  objects     物件表(整張卡共用;objects[0] 是物件0 = 這張卡自己)
  blocks      區塊列表
  omitted     略過文本:[{"span", "text", "reason"}](次數限制前言等不記的字面)

區塊 block
  id / kind(區塊種類)/ label(①②③)/ source(card_text / pen_effect)/ span / text
  segments    段(扁平列表,段樹以 id 引用)
  tree        段樹:{"items": [節點]};節點 = {"node": "段", "segment", "join"}
              | {"node": "分歧", "mode", "chooser", "branches": [{"premise", "items"}], "join"}
              | {"node": "內嵌效果", "binding", "block", "join"}
              join = 同時 / 先後 / None;"unstructured": True 標「未結構化」
  unparsed

段 segment:見 `new_segment`;物件 object:見 `new_object`。
穩定 id:區塊 `b<偏移>`(pen_effect 為 `p<偏移>`)、段 `<區塊id>.s<偏移>`、
物件 `<區塊id>.o<偏移>`,偏移是原文裡的字元位置,插入一段不會讓別的 id 移位;
物件0 固定 `o0`。
"""
import json

from archetype_table import archetype_lookup, fold_width
from block_split import split_blocks
from names_attributes import (SOURCE_OFFICIAL_NAME, extract_names,
                              extract_treat_as, fill_from_card_list)
from segment_extract import extract_block
from structure_shape import (  # noqa: F401  形狀的詞與工廠從這裡再匯出
    ATTRIBUTE_TABLES, BLOCK_KINDS, BRANCH_MODES, JOINS, NO_OFFICIAL_TEXT,
    OBJECT_KINDS, OBJECT_SOURCES, POLARITIES, POSITION_SOURCES, ROLES,
    SEGMENT_KINDS, SIDES, TRIGGER_FORMS, ZONE_PARENT, ZONES, attribute_row,
    branch_node,
    embedded_node, iter_nodes, iter_segments, name_row, new_block, new_card,
    new_line, new_object, new_segment, position, segment_node, self_object,
    unparsed, zone)

# ── 建置 ─────────────────────────────────────────────────────
def build_card(entry, faq_entry, lookups):
    """一張卡:官方 DB 文本 → 名稱表、卡片屬性表 → 區塊 → 段 → 卡片結構。
    沒有官方文本整張標未解析。`lookups` = {"card_names": 折疊後卡名集合,
    "archetypes": 折疊後字段名 → setcode 列表}。"""
    if faq_entry is None:
        card = new_card(entry["id"], entry["name_ja"])
        card["unparsed"] = unparsed(NO_OFFICIAL_TEXT)
        return card
    card = new_card(entry["id"], faq_entry["name_ja"])
    # 卡名列:官方卡名,任何位置都算(位置條件 None)。
    card["attributes"]["name"].append(
        attribute_row(faq_entry["name_ja"], source=SOURCE_OFFICIAL_NAME))
    fill_from_card_list(card, entry)
    texts = [("card_text", faq_entry.get("card_text", "")),
             ("pen_effect", faq_entry.get("pen_effect"))]
    extract_names(card, texts, lookups)
    extract_treat_as(card, texts, lookups)
    blocks, omitted = split_blocks(faq_entry.get("card_text", ""),
                                   faq_entry.get("pen_effect"))
    card["omitted"] = omitted
    for block in blocks:
        extract_block(block, card, lookups)
        card["blocks"].append(block)
    return card


def build_lookups(cards, faq_entries, archetypes):
    """「」名稱的對照:卡名(卡片總表與官方 DB 文本的 name_ja 都收,兩者全半形有別)
    與字段表,都折疊後再比。"""
    card_names = {fold_width(c["name_ja"]) for c in cards if c.get("name_ja")}
    card_names.update(fold_width(f["name_ja"]) for f in faq_entries
                      if f.get("name_ja"))
    return {"card_names": card_names,
            "archetypes": archetype_lookup(archetypes or [])}


def build_structures(cards, faq_entries, archetypes=None, built_at="",
                     sources=None):
    """卡片總表 + 官方 DB 文本 + 字段表 → (一卡一結構的列表, report)。

    `built_at` 與 `sources` 只寫進 report:產物不含時間,入版控後 git diff 才讀得出
    改了什麼(筆記 03 第 6 點)。
    """
    by_password = {}
    for faq in faq_entries:
        by_password[faq["password"]] = faq
    lookups = build_lookups(cards, faq_entries, archetypes)
    structures = []
    no_text = []
    for entry in sorted(cards, key=lambda c: c["id"]):
        faq = by_password.get(entry["id"])
        if faq is None:
            no_text.append(entry["id"])
        structures.append(build_card(entry, faq, lookups))
    report = {
        "built_at": built_at,
        "sources": sources or {},
        "cards": len(structures),
        "no_official_text": no_text,
        "blocks": 0, "segments": 0, "objects": 0,
        "unparsed_blocks": 0, "unparsed_segments": 0, "unparsed_objects": 0,
    }
    for card in structures:
        report["objects"] += len(card["objects"])
        report["unparsed_objects"] += sum(
            1 for o in card["objects"] if o["unparsed"])
        for block in card["blocks"]:
            report["blocks"] += 1
            report["unparsed_blocks"] += 1 if block["unparsed"] else 0
            for _, seg in iter_segments(block):
                report["segments"] += 1
                report["unparsed_segments"] += 1 if seg["unparsed"] else 0
    return structures, report


def _compact(value):
    """產物省略空格(None、[]、{}、False):五萬多個段每個二十格,空格寫滿佔產物一半。
    形狀仍由 `structure_shape` 的工廠定義,`load_structures` 讀回時補齊。"""
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if item is None or item is False or item == [] or item == {}:
                continue
            out[key] = _compact(item)
        return out
    if isinstance(value, list):
        return [_compact(item) for item in value]
    return value


def _compact_card(card):
    card = _compact(card)
    for block in card.get("blocks", ()):
        _compact_block(block)
    return card


def _compact_block(block):
    # 段的字面可由區塊原文與原文範圍推回,不重複寫。
    for seg in block.get("segments", ()):
        seg.pop("text", None)
    for node in iter_nodes(block.get("tree", {}).get("items", ())):
        if node.get("node") == "內嵌效果" and node.get("block"):
            _compact_block(node["block"])


def serialize_structures(structures):
    """一卡一行、不 escape 中文、LF;鍵序由建構時決定(不 sort_keys),
    與 `cards.json` 同一種包法(`[` / `]` 各獨立一行)。空格省略,見 `_compact`。"""
    lines = [json.dumps(_compact_card(card), ensure_ascii=False,
                        separators=(",", ":"))
             for card in structures]
    return "[\n" + ",\n".join(lines) + "\n]\n"


def _hydrate(target, template):
    """把工廠給的預設格補回省略掉的鍵;已有的值優先、鍵序照工廠,
    讀回再序列化才與原產物逐位元組相同。"""
    merged = dict(template)
    merged.update(target)
    return merged


def _hydrate_zones(zones):
    return [_hydrate(z, zone(z["zone"])) for z in zones or []]


def _hydrate_position(pos):
    if not pos:
        return None
    pos = _hydrate(pos, position([], None))
    pos["zones"] = _hydrate_zones(pos["zones"])
    return pos


def _hydrate_attribute_row(row):
    row = _hydrate(row, attribute_row(row["value"]))
    if row["where"]:
        row["where"] = _hydrate_zones(row["where"])
    return row


def _hydrate_line(line):
    line = _hydrate(line, new_line(line["object"], line["role"]))
    line["from"] = _hydrate_position(line["from"])
    line["to"] = _hydrate_position(line["to"])
    return line


def _hydrate_condition(condition):
    """條件式裡帶區域的原子(前提的位置、存在)把區域補齊;其餘原子原樣。"""
    if not isinstance(condition, dict):
        return condition
    out = dict(condition)
    if "zones" in out:
        out["zones"] = _hydrate_zones(out["zones"])
    if "args" in out:
        out["args"] = [_hydrate_condition(a) for a in out["args"]]
    if "arg" in out:
        out["arg"] = _hydrate_condition(out["arg"])
    return out


def _hydrate_nodes(items):
    out = []
    for node in items:
        if node["node"] == "段":
            node = _hydrate(node, segment_node(node["segment"]))
        elif node["node"] == "分歧":
            node = _hydrate(node, branch_node(node["mode"]))
            node["branches"] = [
                {"premise": None, **branch,
                 "items": _hydrate_nodes(branch.get("items", []))}
                for branch in node["branches"]]
        elif node["node"] == "內嵌效果":
            node = _hydrate(node, embedded_node(None, None))
            if node["block"]:
                node["block"] = _hydrate_block(node["block"])
        out.append(node)
    return out


def _hydrate_block(block):
    block = _hydrate(block, new_block(block["id"], block["kind"], None,
                                     block["source"], block["span"],
                                     block["text"]))
    text = block["text"]
    segments = []
    for seg in block["segments"]:
        start, end = seg["span"]
        seg = _hydrate(seg, new_segment(seg["id"], seg["kind"], seg["span"],
                                        text[start:end]))
        seg["lines"] = [_hydrate_line(line) for line in seg["lines"]]
        seg["premise"] = _hydrate_condition(seg["premise"])
        segments.append(seg)
    block["segments"] = segments
    block["tree"] = {**block["tree"],
                     "items": _hydrate_nodes(block["tree"].get("items", []))}
    return block


def load_structures(text):
    """讀回產物並補齊省略的格:`load_structures(serialize_structures(s)) == s`,
    再序列化也與原產物逐位元組相同。"""
    structures = []
    for card in json.loads(text):
        card = _hydrate(card, new_card(card["id"], card["name_ja"]))
        card["attributes"] = {
            name: [_hydrate_attribute_row(row)
                   for row in card["attributes"].get(name, [])]
            for name in ATTRIBUTE_TABLES}
        card["names"] = [_hydrate(row, name_row(row["id"], row["text"], None))
                         for row in card["names"]]
        objects = []
        for obj in card["objects"]:
            obj = _hydrate(obj, new_object(obj["id"], obj["source"]))
            if obj["initial_position"]:
                obj["initial_position"] = _hydrate_zones(obj["initial_position"])
            obj["condition"] = _hydrate_condition(obj["condition"])
            objects.append(obj)
        card["objects"] = objects
        card["blocks"] = [_hydrate_block(block) for block in card["blocks"]]
        structures.append(card)
    return structures
