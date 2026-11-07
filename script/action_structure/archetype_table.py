"""字段表(純函式):上游 ja-JP strings.conf 的 `!setname` → 日文名與 setcode,
中文名從同 setcode 卡的繁中卡文「」引用配對,本站補丁覆蓋;產物一筆一行。

單一接縫:`build_archetypes(setnames, patches, cards, faq_entries) → (rows, report)`。
讀檔、寫檔、印報告在薄殼 `build_archetypes.py`;報告正文不含時間,同一輸入兩次相同。

- 來源 strings.conf(`data/sources_vendored/strings.conf`,入版控)格式:`!setname <0x碼> <名稱>`,
  名稱後若有 tab,tab 之後是註解;`#!setname` 是被註解掉的系列,不算(筆記 06)。
- 名稱的兩種寫法都登記:「漢字（読み）」(古代の機械（アンティーク・ギア）)與「A／B」
  (融合／フュージョン),官方卡文用哪一半不固定。名稱是全形英數、卡文是半形,
  比對一律先 `fold_width`。
- 中文名配對:一張卡的日文「」引用與繁中「」引用數量相同時,依位置成對;對每個字段,
  只數 setcode 符合的卡裡「字段日文名 ↔ 中文」的成對次數,取最多的。沒有任何成對的
  列 `unmatched`;最多的不是唯一候選時列 `ambiguous`(仍取最多的,站主可用補丁改)。
- 補丁(`data/archetype_patches.json`,來源檔):每筆 {"setcode": "0x..", "names_ja"?,
  "name_zh"?, "remove"?, "reason"}。setcode 不在上游的就是補上游缺漏;欄位不認得或
  setcode 不是十六進位進 `problems`,薄殼以非 0 結束。
- setcode 比對照 ygopro-core `check_setcode`:低 12 位是系列本體、高 4 位是子系列旗標。
"""
import json
import re
from collections import Counter, defaultdict

_FOLD = {i: i - 0xFEE0 for i in range(0xFF01, 0xFF5F)}
_FOLD[0x3000] = 0x20
_READING_RE = re.compile("^(?P<kanji>.+?)（(?P<reading>.+)）$")
_QUOTE_RE = re.compile("「([^「」]+)」")
_HEX_RE = re.compile("^0x[0-9a-fA-F]+$")
PATCH_FIELDS = {"setcode", "names_ja", "name_zh", "remove", "reason"}
SOURCE_UPSTREAM = "strings.conf"
SOURCE_PATCH = "補丁"


def fold_width(text):
    """全形英數符號與全形空白折成半形;假名、漢字、「」、・ 不動。"""
    return text.translate(_FOLD)


def parse_setnames(conf_text):
    """strings.conf 全文 → [(setcode, 名稱)],照檔案順序。"""
    out = []
    for line in conf_text.lstrip("﻿").splitlines():
        if not line.startswith("!setname "):
            continue
        parts = line.split(" ", 2)
        if len(parts) < 3:
            continue
        name = parts[2].split("\t")[0].strip()
        if name:
            out.append((int(parts[1], 16), name))
    return out


def name_variants(name):
    """一個 setname → 卡文可能用的寫法列表(括號讀音、／ 兩種都收)。"""
    m = _READING_RE.match(name)
    if m:
        return [m.group("kanji"), m.group("reading")]
    for sep in ("／", "/"):
        parts = name.split(sep)
        # 「／バスター」的 ／ 是名稱的一部分(卡文就寫「／バスター」),只有兩邊都有字才是兩種寫法。
        if len(parts) == 2 and all(parts):
            return parts
    return [name]


def split_setcode(value):
    """cards.json 的 setcode(64 位整數)→ 最多 4 個 16 位系列碼。"""
    return [(value >> (16 * i)) & 0xFFFF for i in range(4)
            if (value >> (16 * i)) & 0xFFFF]


def setcode_matches(card_code, want):
    """ygopro-core card_data.h check_setcode:本體相同,且卡帶有查詢要求的子系列旗標。"""
    return ((card_code & 0x0FFF) == (want & 0x0FFF)
            and (card_code & (want & 0xF000)) == (want & 0xF000))


def card_has_setcode(entry_setcode, want):
    return any(setcode_matches(code, want) for code in split_setcode(entry_setcode))


def quoted_names(text):
    return _QUOTE_RE.findall(text or "")


def _pair_counts(cards, faq_entries):
    """每張卡 → {(折疊後日文引用, 中文引用): 次數};引用數不同的卡不配(譯文有時增減引用)。"""
    by_password = {f["password"]: f for f in faq_entries}
    per_card = []
    for entry in cards:
        f = by_password.get(entry["id"])
        if f is None:
            continue
        ja = quoted_names(f.get("card_text", "")) + quoted_names(f.get("pen_effect"))
        zh = quoted_names(entry.get("desc"))
        if len(ja) != len(zh):
            continue
        per_card.append((entry["setcode"], Counter(
            (fold_width(j), z) for j, z in zip(ja, zh))))
    return per_card


def _candidates(per_card, folded_names, code):
    """字段日文名 ↔ 中文引用的成對次數;code 給了只數 setcode 符合的卡,None 數全部。"""
    cands = Counter()
    for entry_setcode, counts in per_card:
        if code is not None and not card_has_setcode(entry_setcode, code):
            continue
        for (ja, zh), n in counts.items():
            if ja in folded_names:
                cands[zh] += n
    return cands


def _check_patch(patch):
    unknown = set(patch) - PATCH_FIELDS
    if unknown:
        return f"補丁欄位不認得:{sorted(unknown)}"
    code = patch.get("setcode")
    if not isinstance(code, str) or not _HEX_RE.match(code):
        return f"補丁 setcode 要是 0x 開頭的十六進位字串:{code!r}"
    if "names_ja" in patch and (not isinstance(patch["names_ja"], list)
                                or not all(isinstance(n, str) for n in patch["names_ja"])):
        return f"補丁 names_ja 要是字串列表:{code}"
    return None


def build_archetypes(setnames, patches, cards, faq_entries):
    """→ (字段列,依 setcode 排序; 報告)。列:{"setcode", "hex", "names_ja", "name_zh", "source"}。"""
    rows = {}
    for code, name in setnames:
        rows[code] = {"setcode": code, "hex": hex(code),
                      "names_ja": name_variants(name), "name_zh": None,
                      "source": SOURCE_UPSTREAM}
    per_card = _pair_counts(cards, faq_entries)
    ambiguous, fallback = [], []
    for code, row in rows.items():
        folded = {fold_width(n) for n in row["names_ja"]}
        cands = _candidates(per_card, folded, code)
        if not cands:
            # 同 setcode 的卡都沒引用字段名(字段名只在卡名裡、或引用它的是別系列的卡):
            # 退而用全部卡的成對,報告標明,站主覺得不對就寫補丁。
            cands = _candidates(per_card, folded, None)
            if cands:
                fallback.append({"setcode": code, "names_ja": row["names_ja"]})
        if not cands:
            continue
        ranked = sorted(cands.items(), key=lambda kv: (-kv[1], kv[0]))
        row["name_zh"] = ranked[0][0]
        if len(ranked) > 1:
            ambiguous.append({"setcode": code, "names_ja": row["names_ja"],
                              "name_zh": row["name_zh"],
                              "candidates": [[zh, n] for zh, n in ranked]})
    applied, problems = [], []
    for patch in patches:
        problem = _check_patch(patch)
        if problem:
            problems.append(problem)
            continue
        code = int(patch["setcode"], 16)
        if patch.get("remove"):
            rows.pop(code, None)
            applied.append({"setcode": code, "names_ja": None, "name_zh": None,
                            "remove": True, "reason": patch.get("reason", "")})
            continue
        row = rows.setdefault(code, {"setcode": code, "hex": hex(code),
                                     "names_ja": [], "name_zh": None,
                                     "source": SOURCE_PATCH})
        if "names_ja" in patch:
            row["names_ja"] = list(patch["names_ja"])
        if "name_zh" in patch:
            row["name_zh"] = patch["name_zh"]
        row["source"] = SOURCE_PATCH
        applied.append({"setcode": code, "names_ja": row["names_ja"],
                        "name_zh": row["name_zh"], "reason": patch.get("reason", "")})
    patched = {p["setcode"] for p in applied}
    ordered = [rows[code] for code in sorted(rows)]
    # 配不到:補丁套完後仍沒有中文名的列;候選不唯一:補丁沒碰過的才列。
    report = {
        "total": len(ordered),
        "matched": sum(1 for r in ordered if r["name_zh"] is not None),
        "unmatched": [{"setcode": r["setcode"], "names_ja": r["names_ja"]}
                      for r in ordered if r["name_zh"] is None],
        "ambiguous": sorted((a for a in ambiguous if a["setcode"] not in patched),
                            key=lambda a: a["setcode"]),
        "fallback": sorted((f for f in fallback if f["setcode"] not in patched),
                           key=lambda f: f["setcode"]),
        "patches": applied,
        "problems": problems,
    }
    return ordered, report


def serialize_archetypes(rows):
    """一筆一行、不 escape 中文、LF,與 cards.json 同一種包法。"""
    lines = [json.dumps(row, ensure_ascii=False, separators=(",", ":"))
             for row in rows]
    return "[\n" + ",\n".join(lines) + "\n]\n"


def load_archetypes(text):
    return json.loads(text)


def archetype_lookup(rows):
    """折疊後的日文名 → setcode 列表(排序);名稱表與條件式用它把「X」換成 setcode。"""
    lookup = defaultdict(set)
    for row in rows:
        for name in row["names_ja"]:
            lookup[fold_width(name)].add(row["setcode"])
    return {name: sorted(codes) for name, codes in lookup.items()}


def _names(names_ja):
    return "／".join(names_ja or [])


def render_report(report):
    """字段表建置報告 md:不寫時間,排序固定。"""
    lines = [
        "# 字段表建置報告",
        "",
        "<!-- 由 script/action_structure/build_archetypes.py 產生,不要手改;"
        "更新 strings.conf 或補丁後重跑即刷新。 -->",
        "",
        "字段表 `data/archetypes.json` 以上游 ja-JP strings.conf 的 `!setname` 為日文名 → setcode "
        "起點;中文名從同 setcode 卡的繁中卡文「」引用依位置配對;本站補丁 "
        "`data/archetype_patches.json` 覆蓋。判法在 script/action_structure/archetype_table.py。",
        "",
        "## 總覽",
        "",
        "| 項目 | 數 |",
        "|---|---|",
        f"| 字段 | {report['total']} |",
        f"| 配到中文名 | {report['matched']} |",
        f"| 配不到中文名 | {len(report['unmatched'])} |",
        f"| 候選不唯一 | {len(report['ambiguous'])} |",
        f"| 用全部卡配對 | {len(report['fallback'])} |",
        f"| 套用補丁 | {len(report['patches'])} |",
        "",
        f"## 配不到中文名({len(report['unmatched'])} 筆)",
        "",
        "同 setcode 的卡沒有一張的日文「」引用對得到字段名(常見:字段只出現在卡名裡、"
        "或還沒有卡)。要補中文名就寫補丁。",
        "",
    ]
    for u in report["unmatched"]:
        lines.append(f"- `{hex(u['setcode'])}` {_names(u['names_ja'])}")
    if not report["unmatched"]:
        lines.append("(無)")
    lines += ["", f"## 候選不唯一({len(report['ambiguous'])} 筆)", "",
              "取成對次數最多的;各候選附次數,取錯了就寫補丁。", ""]
    for a in report["ambiguous"]:
        cands = "、".join(f"{zh} {n}" for zh, n in a["candidates"])
        lines.append(f"- `{hex(a['setcode'])}` {_names(a['names_ja'])}:{cands}")
    if not report["ambiguous"]:
        lines.append("(無)")
    lines += ["", f"## 用全部卡配對({len(report['fallback'])} 筆)", "",
              "同 setcode 的卡沒引用字段名,中文名取自其他卡的「」引用成對;"
              "配錯了就寫補丁。", ""]
    for f in report["fallback"]:
        lines.append(f"- `{hex(f['setcode'])}` {_names(f['names_ja'])}")
    if not report["fallback"]:
        lines.append("(無)")
    lines += ["", f"## 套用補丁({len(report['patches'])} 筆)", ""]
    for p in report["patches"]:
        if p.get("remove"):
            lines.append(f"- `{hex(p['setcode'])}` 移除({p['reason']})")
        else:
            lines.append(f"- `{hex(p['setcode'])}` {_names(p['names_ja'])} → "
                         f"{p['name_zh']}({p['reason']})")
    if not report["patches"]:
        lines.append("(無)")
    lines.append("")
    return "\n".join(lines)
