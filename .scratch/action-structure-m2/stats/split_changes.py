# 多子句切法改變清單(里程碑二票 02):比對兩份卡片結構產物,列出段切法不同的地方(交站主看)。
# 跑法(repo 根):
#   git show <改切法前的 commit>:data/action_structure.json > before.json
#   python -X utf8 script/action_structure/build_structure.py -o after.json
#   python -X utf8 .scratch/action-structure-m2/stats/split_changes.py before.json after.json \
#       .scratch/action-structure-m2/report/split-changes.md
# 改切法前的產物:整合分支 action-structure-m2 的 ffe6e5c(里程碑一產物)。
# 只用標準庫:不 import repo 的模組。輸出決定性:排序固定、不寫時間與路徑。
#
# 「切法改變」= 同一區塊(含內嵌效果的內容區塊)裡,兩份產物的段範圍不同。兩邊各自多出來的段範圍
# 依重疊併成一處,每處列卡號、卡名、前後各段字面(以「｜」分段)。兩截切開的那個「、」不屬於任何段,
# 所以「前」是一段、「後」是兩段時,後者以「、」接回就是前者的字面。
import json
import sys
from collections import Counter


def iter_nodes(items):
    """段樹節點(含分歧各支),同 structure_shape.iter_nodes。"""
    for node in items:
        yield node
        if node.get("node") == "分歧":
            for branch in node.get("branches", []):
                yield from iter_nodes(branch.get("items", []))


def iter_blocks(block):
    """區塊與其內嵌效果的內容區塊。"""
    yield block
    for node in iter_nodes(block.get("tree", {}).get("items", [])):
        if node.get("node") == "內嵌效果" and node.get("block"):
            yield from iter_blocks(node["block"])


def load(path):
    """產物 → {卡號: (卡名, {區塊 id: (區塊原文, [段範圍])})}。"""
    with open(path, encoding="utf-8") as f:
        cards = json.load(f)
    out = {}
    for card in cards:
        blocks = {}
        for top in card.get("blocks", []):
            for block in iter_blocks(top):
                blocks[block["id"]] = (block["text"],
                                       sorted(tuple(s["span"]) for s in block.get("segments", [])))
        out[card["id"]] = (card.get("name_ja", ""), blocks)
    return out


def regions(before, after):
    """兩邊各自多出來的段範圍,依重疊併成一處 → [(前的範圍們, 後的範圍們)]。"""
    only = sorted([(s, "前") for s in set(before) - set(after)]
                  + [(s, "後") for s in set(after) - set(before)])
    groups = []
    for span, side in only:
        if groups and span[0] < groups[-1]["end"]:
            group = groups[-1]
        else:
            group = {"end": span[1], "前": [], "後": []}
            groups.append(group)
        group[side].append(span)
        group["end"] = max(group["end"], span[1])
    return [(g["前"], g["後"]) for g in groups]


def kind(old, new):
    if len(new) > len(old):
        return "多切"
    if len(new) < len(old):
        return "少切"
    return "切點不同"


def pieces(text, spans):
    return "｜".join(text[a:b] for a, b in spans)


def render(before, after):
    rows = []
    for cid in sorted(after, key=str):
        if cid not in before:
            continue
        name, blocks = after[cid]
        old_blocks = before[cid][1]
        for block_id in sorted(blocks):
            if block_id not in old_blocks:
                continue
            text, new_spans = blocks[block_id]
            _, old_spans = old_blocks[block_id]
            for old, new in regions(old_spans, new_spans):
                rows.append((cid, name, kind(old, new), pieces(text, old), pieces(text, new)))
    kinds = Counter(r[2] for r in rows)
    lines = ["# 多子句切法改變清單", "",
             "里程碑二票 02:連用形語尾加「、」就切(不再要求左半先解析成簡單子句)前後,"
             "段範圍不同的地方。重跑方式見 `.scratch/action-structure-m2/stats/split_changes.py`。", "",
             f"- 共 {len(rows)} 處、{len({r[0] for r in rows})} 張"
             + "".join(f";{k} {n} 處" for k, n in sorted(kinds.items())),
             "- 字面以「｜」分段;「後」各段以「、」接回即「前」的字面。", ""]
    for k in sorted(kinds):
        lines += [f"## {k}({kinds[k]} 處)", "", "| 卡號 | 卡名 | 前 | 後 |", "|---|---|---|---|"]
        for cid, name, row_kind, old, new in rows:
            if row_kind == k:
                lines.append(f"| {cid} | {cell(name)} | {cell(old)} | {cell(new)} |")
        lines.append("")
    return "\n".join(lines)


def cell(text):
    return text.replace("|", "\\|").replace("\n", " ")


def main(argv):
    if len(argv) != 4:
        print("用法:split_changes.py before.json after.json out.md", file=sys.stderr)
        return 1
    md = render(load(argv[1]), load(argv[2]))
    with open(argv[3], "w", encoding="utf-8", newline="\n") as f:
        f.write(md)
    print(md.splitlines()[4])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
