# 票 14:里程碑二之後仍「述語解析不出」的段,依寫法粗分(字面規則,排下一步優先順序用;只印 stdout)。
# 跑法:python -X utf8 .scratch/action-structure-m2/stats/m2_residue.py <repo 根>
# 只用標準庫、自己讀產物(同 m2_stats.py)。一段只落一類(先中先贏,照 CATEGORIES 順序),沒中進「其他」;
# 另印段類別分布。每類印「段 / 張」與前三個卡號。輸出決定性:排序固定、不印時間。
import json
import os
import re
import sys
from collections import Counter, defaultdict

ROOT = sys.argv[1] if len(sys.argv) > 1 else "."
REASON = "述語解析不出"

CATEGORIES = [
    ("X素材とする/としている/融合素材とし(下個里程碑)", r"素材(と|に)(する|し|して|している)"),
    ("〜に成功した時/場合(舊式召喚成功)", r"に成功(した|する)"),
    ("〜を得る(效果・控制權)", r"を得る|を得て|を得た"),
    ("〜を適用する/できる", r"適用(する|できる|し)"),
    ("〜として扱う/扱い", r"として扱|扱いとな"),
    ("〜しなければならない/必須", r"なければならない|ならず"),
    ("〜の攻撃宣言時/攻撃宣言した", r"攻撃宣言"),
    ("〜から離れた/離れる", r"離れ"),
    ("裝備限制/儀式降臨(のみ装備可能、降臨)", r"装備可能|降臨"),
    ("被動條件「〜された場合/時」", r"(され|られ)た(場合|時)"),
    ("主動條件「〜した場合/時」", r"(し|っ|い|け|せ|べ|め)た(場合|時)"),
    ("存在(しない)場合", r"存在(する|しない)(場合|時)"),
    ("被動結果「〜される/られる」", r"(され|られ)る$"),
    ("抗性/限制(されない/できない/受けない)", r"(されない|できない|受けない)$"),
    ("可選的做「〜事ができる/もできる」", r"事(が|も)できる$"),
    ("特殊召喚する(句中雜項)", r"特殊召喚(する|できる)$"),
]

with open(os.path.join(ROOT, "data", "action_structure.json"), encoding="utf-8") as f:
    CARDS = json.load(f)


def iter_nodes(items):
    for node in items:
        yield node
        if node.get("node") == "分歧":
            for branch in node.get("branches", []):
                yield from iter_nodes(branch.get("items", []))


def iter_segments(block):
    for seg in block.get("segments", []):
        yield block, seg
    for node in iter_nodes(block.get("tree", {}).get("items", [])):
        if node.get("node") == "內嵌效果" and node.get("block"):
            yield from iter_segments(node["block"])


rows = []
for card in CARDS:
    for top in card.get("blocks", []):
        for blk, seg in iter_segments(top):
            if (seg.get("unparsed") or {}).get("reason") != REASON:
                continue
            start, end = seg["span"]
            rows.append((card["id"], seg["kind"], re.sub(r"[。、]+$", "", blk["text"][start:end])))

print(f"述語解析不出 段: {len(rows)}")
print(f"述語解析不出 張: {len({cid for cid, _, _ in rows})}")
for kind, n in sorted(Counter(k for _, k, _ in rows).items(), key=lambda kv: (-kv[1], kv[0])):
    print(f"段類別 {kind} 段: {n}")

bucket = defaultdict(list)
for cid, _, text in rows:
    label = next((name for name, pattern in CATEGORIES if re.search(pattern, text)), "其他")
    bucket[label].append(cid)
for name in [n for n, _ in CATEGORIES] + ["其他"]:
    cids = bucket[name]
    examples = ", ".join(str(c) for c in sorted(set(cids))[:3])
    print(f"類(先中先贏) {name}: {len(cids)} 段 / {len(set(cids))} 張(例 {examples})")
