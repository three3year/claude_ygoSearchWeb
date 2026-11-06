"""反向檢查(純函式):卡片結構 → 句型模板 → 日文,正規化後與該段原文範圍全等才通過。

接縫二(spec「測試決策」):`check_card(卡片結構) → 不通過清單`,清單空 = 整張通過,
票 02 之後每張標準卡的驗收都靠它;`check_structures(全庫結構) → 報告資料`、
`render_report(報告資料) → md` 給 CLI 薄殼 `build_reverse_check.py` 產全庫報告。

嚴格(spec 決定):模板只從結構的格產生日文,不抄段的字面——物件由條件式與數量
產生、述語字面必須能拆回動作詞+態+極性。結構裡有格填了值但模板不會寫的,
記「無模板」算不通過,所以後面的票每填一格就得補一段模板。

不通過的原因(報告依此分類,每筆附卡號):
- 無模板:段本身解析不出、或有填值的格這裡還沒有模板;detail 指出是哪一格。
- 字面不符:產生得出日文,正規化後與原文不等;detail 附產生的日文與原文。
- 段外殘留:區塊裡有段沒涵蓋、又不是固定接著詞(①：、。、、発動できる…)的文字。
  每段各自全等還不夠,整個區塊的字都要有人認——否則漏掉一整句也看不出來。

正規化只做空白與全半形:自己寫,不用 NFKC(NFKC 會把 ① 折成 1,筆記 00 第 4 點)。
"""
import re

from attribute_atoms import is_param_atom, render_modifier
from premise import NoPremiseTemplate, render_premise
from segment_extract import (HEAD_CATEGORY, HEAD_SUBTYPE, SIDE_WORDS, ZONE_WORDS,
                             category_of, parse_predicate)
from structure_shape import iter_segments

REASON_NO_TEMPLATE = "無模板"
REASON_MISMATCH = "字面不符"
REASON_RESIDUE = "段外殘留"

# 簡單子句模板會寫的格;其餘格一有值就是「無模板」。
TEMPLATE_SLOTS = {"id", "kind", "actions", "lines", "agent", "polarity",
                  "trigger", "premise", "span", "text", "predicate", "voice",
                  "unparsed"}
TEMPLATE_KINDS = ("條件", "代價", "效果")
# 區塊裡不屬於任何段的固定接著詞:發動句語尾、先後連接。去掉標點後只能剩這些。
GLUE = ("発動できる", "発動する", "その後")
_GLUE_RE = re.compile("|".join(GLUE))
_PUNCT_RE = re.compile("[。、\n ]")
_WS_RE = re.compile(r"[\s　]+")

_SIDE_TEXT = {v: k for k, v in SIDE_WORDS.items()}           # 我方 → 自分
_ZONE_TEXT = {name: word for word, name in ZONE_WORDS}      # 手牌 → 手札
_HEAD_TEXT = {v: k for k, v in HEAD_CATEGORY.items() if isinstance(v, str)}
_HEAD_TEXT[("魔法", "陷阱")] = "魔法・罠カード"
_SUBTYPE_HEAD_TEXT = {v: k for k, v in HEAD_SUBTYPE.items()}  # (怪獸, 協調) → チューナー
_FULLWIDTH_ASCII = {i: i - 0xFEE0 for i in range(0xFF01, 0xFF5F)}
_TO_FULLWIDTH_DIGITS = str.maketrans("0123456789", "０１２３４５６７８９")


def normalise(text):
    """去空白(含全形空白)、全形英數符號折成半形;①②③ 等編號字元保持原樣。"""
    return _WS_RE.sub("", text).translate(_FULLWIDTH_ASCII)


class NoTemplate(Exception):
    """模板寫不出這一段:訊息是 detail(哪一格、什麼原因)。"""


# ── 模板 ─────────────────────────────────────────────────────
def _quoted(atom, names):
    """名稱原子 → 「X」:只從名稱表取字面(查詢側才會直接帶 text,結構裡不會)。"""
    row = names.get(atom.get("name"))
    if row is None:
        raise NoTemplate("名稱原子引用的名稱列找不到")
    return f"「{row['text']}」"


def _render_atom(atom, names):
    """修飾語原子 → 字面:字段(「X」/「X」と名のついた)、「X」以外の、カード名に「X」を含む。"""
    op = atom.get("op")
    if op == "字段":
        form = atom.get("form")
        if form not in (None, "と名のついた"):
            raise NoTemplate(f"字段寫法無模板:{form}")
        return _quoted(atom, names) + (form or "")
    if op == "非" and atom.get("arg", {}).get("op") == "卡名":
        return _quoted(atom["arg"], names) + "以外の"
    if op == "卡名包含":
        return "カード名に" + _quoted(atom, names) + "を含む"
    if op == "解析不出":
        raise NoTemplate("物件條件無模板:解析不出")
    raise NoTemplate(f"物件條件無模板:{op}")


def _render_head(condition):
    """大類(與 魔法・罠 的或)、大類 且 子類型 → 頭名詞。"""
    op = condition.get("op")
    if op == "大類":
        return _HEAD_TEXT[condition["value"]]
    if op == "或":
        values = tuple(a.get("value") for a in condition["args"]
                       if a.get("op") == "大類")
        if len(values) == len(condition["args"]) and values in _HEAD_TEXT:
            return _HEAD_TEXT[values]
    if op == "且" and len(condition["args"]) == 2:
        category, subtype = condition["args"]
        if category.get("op") == "大類" and subtype.get("op") == "子類型":
            return _SUBTYPE_HEAD_TEXT.get((category["value"], subtype["value"]))
    return None


def _render_modifiers(mods, names):
    """修飾語列表 → 字面:相鄰的屬性比較以「・」相連(魔法使い族・光属性),但前一個是
    多個種族的「或」時以「の」相連(獣族・獣戦士族・鳥獣族の炎属性,官方 14:7);
    屬性比較後面接「」名稱時補「の」(ドラゴン族の「ドラグニティ」);接頭名詞不補。"""
    out = []
    for i, atom in enumerate(mods):
        if not is_param_atom(atom):
            out.append(_render_atom(atom, names))
            continue
        text = render_modifier(atom)
        if text is None:
            raise NoTemplate("屬性比較無模板")
        following = mods[i + 1] if i + 1 < len(mods) else None
        if following is not None:
            joined = is_param_atom(following) and atom.get("op") != "或"
            text += "・" if joined else "の"
        out.append(text)
    return "".join(out)


def _render_condition(condition, names):
    """條件式 → 名詞短語:且 = 修飾語(照字面順序)+ 頭名詞;單獨的卡名 = 「X」。"""
    if condition is None:
        raise NoTemplate("物件條件無模板:空")
    head = _render_head(condition)
    if head:
        return head
    op = condition.get("op")
    if op == "卡名":
        return _quoted(condition, names)
    if op == "且":
        *mods, last = condition["args"]
        head = _render_head(last)
        if head is None:
            raise NoTemplate("物件條件無模板:且 的末項不是大類")
        return _render_modifiers(mods, names) + head
    return _render_atom(condition, names)


def _render_count(count):
    if not count:
        return ""
    if count.get("cmp") not in ("=", "≤") or not count.get("unit"):
        raise NoTemplate("物件數量無模板")
    # 官方卡文的數字是全形,照它寫(正規化時兩邊都會折成半形,這裡只為報告好讀)。
    digits = str(count["value"]).translate(_TO_FULLWIDTH_DIGITS)
    return f"{digits}{count['unit']}{'まで' if count['cmp'] == '≤' else ''}"


def _render_object(obj, seg, names):
    """物件在這一段的字面 → (名詞短語, 述語前的數量):物件0 是このカード;本段首次出現的
    寫全名(條件+名詞內的數量,述語前的數量另回傳);別段建立、本段指回的寫 その+頭名詞
    (抽取端 _REF_RE 只認 モンスター|カード)。"""
    if obj["source"]["kind"] == "自己":
        return "このカード", ""
    if obj["source"]["kind"] != "新建":
        raise NoTemplate(f"物件來源無模板:{obj['source']['kind']}")
    if obj["unparsed"]:
        raise NoTemplate(f"物件無模板:{obj['unparsed']['reason']}")
    start, end = seg["span"]
    defined_here = (obj["span"] and obj["block"] == seg["id"].split(".")[0]
                    and start <= obj["span"][0] and obj["span"][1] <= end)
    if defined_here:
        noun = _render_condition(obj["condition"], names)
        count = _render_count(obj["count"])
        if obj["count"] and obj["count"].get("placement") == "述語前":
            return noun, count
        return noun + count, ""
    # 指回的物件:怪獸寫 そのモンスター(含チューナー),其餘寫 そのカード。
    return "その" + ("モンスター" if category_of(obj["condition"]) == "怪獸"
                   else "カード"), ""


def _render_zones(zones):
    """區域列表 → 字面:方明寫時加「自分の/相手の」(只有一個區域且是フィールド時不加「の」:
    「自分フィールド」「自分の手札・フィールド」「自分の墓地」是官方的寫法);
    方沒寫(預設)不加。"""
    # 明寫的方是整個列表共用的一個前綴;沒寫的(預設或沒有方)各區域可以不同
    # (「手札・フィールド」:手牌預設我方、場上沒有方)。
    written = {z["side"] for z in zones if z.get("side_source") == "明寫"}
    if len(written) > 1 or (written and any(
            z.get("side_source") != "明寫" for z in zones)):
        raise NoTemplate("從的區域分屬兩方")
    try:
        words = [_ZONE_TEXT[z["zone"]] for z in zones]
    except KeyError as e:
        raise NoTemplate(f"區域無模板:{e.args[0]}") from None
    prefix = ""
    if written:
        side = written.pop()
        if side not in _SIDE_TEXT:
            raise NoTemplate(f"方無模板:{side}")
        prefix = _SIDE_TEXT[side] + ("" if words == ["フィールド"] else "の")
    return prefix + "・".join(words)


def _written_position(lines, key):
    """所有對象線共用一個明寫的 從/到 才有字面;繼承、推得的不寫。"""
    written = [line[key] for line in lines
               if line[key] and line[key]["source"] == "明寫"]
    if not written:
        return None
    if len(written) != len(lines) or any(w != written[0] for w in written):
        raise NoTemplate(f"對象線的{'從' if key == 'from' else '到'}不一致")
    return written[0]["zones"]


def _render_from(lines):
    zones = _written_position(lines, "from")
    return _render_zones(zones) + "から" if zones else ""


def _render_to_prefix(seg):
    """主語形的「<到>に」前綴:到是明寫、且不是述語自己寫的終點(「墓地へ送る」)。"""
    zones = _written_position(seg["lines"], "to")
    if not zones:
        return ""
    parsed, _ = parse_predicate(seg["predicate"])
    if parsed and parsed[3] is not None:
        return ""
    return _render_zones(zones) + "に"


def _render_predicate(seg):
    if len(seg["actions"]) != 1 or not seg["predicate"]:
        raise NoTemplate("多動作詞無模板" if seg["actions"] else "段無動作詞")
    parsed, _ = parse_predicate(seg["predicate"])
    # 自動(主語形、非被動語尾)的述語字面與主動相同,只差句型。
    voice = "主動" if seg["voice"] == "自動" else seg["voice"]
    if parsed is None or parsed[:3] != (seg["actions"][0], voice,
                                       seg["polarity"]):
        raise NoTemplate("述語字面與動作詞、態、極性不一致")
    return seg["predicate"]


def render_segment(seg, card):
    """簡單子句模板:[前提][誰が][從から][物件を]述語[觸發形];主語形(態是被動或自動)
    [前提][到に][物件が][從から]述語[觸發形];只有前提的條件段寫前提。
    回傳日文;寫不出就丟 NoTemplate。"""
    if seg["unparsed"]:
        raise NoTemplate(f"段未解析:{seg['unparsed']['reason']}")
    if seg["kind"] not in TEMPLATE_KINDS:
        raise NoTemplate(f"段類別無模板:{seg['kind']}")
    for slot, value in seg.items():
        if slot not in TEMPLATE_SLOTS and value not in (None, [], {}, False):
            raise NoTemplate(f"格 {slot} 無模板")
    objects = {o["id"]: o for o in card["objects"]}
    names = {row["id"]: row for row in card["names"]}
    parts = []
    premise_only = (seg["kind"] == "條件" and seg["premise"] is not None
                    and not seg["actions"] and not seg["lines"])
    if seg["premise"] is not None:
        try:
            parts.append(render_premise(
                seg["premise"], _render_zones,
                lambda obj_id: _render_object(objects[obj_id], seg, names)[0],
                followed=not premise_only))
        except NoPremiseTemplate as e:
            raise NoTemplate(str(e)) from None
    if premise_only:
        return "".join(parts)
    if not seg["lines"]:
        raise NoTemplate("段無對象線")
    if seg["agent"] is not None:
        if seg["agent"] not in _SIDE_TEXT:
            raise NoTemplate(f"誰無模板:{seg['agent']}")
        parts.append(_SIDE_TEXT[seg["agent"]] + "が")
    words, postcount = [], ""
    for line in seg["lines"]:
        if line["targeting"]:
            raise NoTemplate("取對象線無模板")
        if line["role"] not in ("受事", "被召喚"):
            raise NoTemplate(f"角色無模板:{line['role']}")
        noun, count = _render_object(objects[line["object"]], seg, names)
        words.append(noun)
        if count:
            if postcount or len(seg["lines"]) != 1:
                raise NoTemplate("述語前的數量只能屬於唯一的物件")
            postcount = count
    if seg["voice"] in ("被動", "自動"):
        if postcount:
            raise NoTemplate("主語形的述語前數量無模板")
        parts.append(_render_to_prefix(seg))
        parts.append("と".join(words) + "が")
        parts.append(_render_from(seg["lines"]))
    else:
        parts.append(_render_from(seg["lines"]))
        parts.append("と".join(words) + "を" + postcount)
    parts.append(_render_predicate(seg))
    if seg["kind"] == "條件":
        if not seg["trigger"]:
            raise NoTemplate("條件段無觸發形")
        parts.append(seg["trigger"])
    return "".join(parts)


# ── 檢查 ─────────────────────────────────────────────────────
def _failure(card, block, seg_id, reason, detail, rendered=None, original=None):
    return {"card": card["id"], "name_ja": card["name_ja"], "block": block["id"],
            "segment": seg_id, "reason": reason, "detail": detail,
            "rendered": rendered, "original": original}


def _residue(block):
    """區塊原文扣掉各段範圍與標點後剩下的片段;不是固定接著詞的就是殘留。"""
    text = block["text"]
    cut = [(s["span"][0], s["span"][1], s["kind"]) for s in block["segments"]]
    if block["label"]:
        cut.append((0, 2, None))  # 「①：」
    cut.sort()
    pieces, pos, after = [], 0, None
    for start, end, kind in cut:
        if start > pos:
            pieces.append((after, text[pos:start]))
        pos, after = max(pos, end), kind
    if pos < len(text):
        pieces.append((after, text[pos:]))
    residue = []
    for kind, piece in pieces:
        rest = _PUNCT_RE.sub("", piece)
        # 條件段的範圍到觸發形為止,「場合に」「時に」的「に」留在段外(segment_extract
        # 的 _TRIGGER_RE),只有緊接在條件段後面的「に」算接著詞。
        if kind == "條件" and rest.startswith("に"):
            rest = rest[1:]
        if _GLUE_RE.sub("", rest):
            residue.append(piece)
    return residue


def check_card(card):
    """一張卡的不通過清單;空清單 = 整張通過。無官方日文的卡沒有段,清單也是空的。"""
    failures = []
    for block in card["blocks"]:
        for owner, seg in iter_segments(block):
            try:
                rendered = render_segment(seg, card)
            except NoTemplate as e:
                failures.append(_failure(card, owner, seg["id"],
                                         REASON_NO_TEMPLATE, str(e)))
                continue
            if normalise(rendered) != normalise(seg["text"]):
                failures.append(_failure(card, owner, seg["id"], REASON_MISMATCH,
                                         None, rendered, seg["text"]))
        for piece in _residue(block):
            failures.append(_failure(card, block, None, REASON_RESIDUE,
                                     piece.strip("。、\n ")))
    return failures


def check_structures(structures):
    """全庫 → 報告資料:段數、通過、不通過、無官方日文張數與全部不通過筆。"""
    segments = 0
    no_text = 0
    failures = []
    for card in sorted(structures, key=lambda c: c["id"]):
        if card["unparsed"]:
            no_text += 1
            continue
        segments += sum(1 for block in card["blocks"]
                        for _ in iter_segments(block))
        failures.extend(check_card(card))
    failed_segments = sum(1 for f in failures if f["segment"])
    residue_blocks = len({(f["card"], f["block"]) for f in failures
                          if f["reason"] == REASON_RESIDUE})
    return {"cards": len(structures), "no_official_text": no_text,
            "segments": segments, "passed": segments - failed_segments,
            "failed": failed_segments, "residue_blocks": residue_blocks,
            "failures": failures}


# ── 報告 ─────────────────────────────────────────────────────
def _group(failures, key):
    groups = {}
    for f in failures:
        groups.setdefault(key(f), []).append(f)
    return groups


def _count_line(title, items, unit):
    cards = sorted({f["card"] for f in items})
    return f"{title}({len(items)} {unit} / {len(cards)} 張)", cards


def _reason_section(reason, items):
    lines = []
    unit = "筆" if reason == REASON_RESIDUE else "段"   # 殘留是區塊裡的片段,不是段
    title, _ = _count_line(f"### {reason}", items, unit)
    lines.append(title)
    lines.append("")
    if reason == REASON_MISMATCH:
        lines.append("每筆:卡號、卡名、段 id、產生的日文、原文(全部列出,依卡號)。")
        lines.append("")
        for f in items:
            lines.append(f"- `{f['card']}` {f['name_ja']} `{f['segment']}` "
                         f"產生「{f['rendered']}」原文「{f['original']}」")
        lines.append("")
        return lines
    lines.append("各細項附全部卡號(依卡號),細項依段數多的在前。")
    lines.append("")
    details = _group(items, lambda f: f["detail"])
    for detail, group in sorted(details.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        title, cards = _count_line(detail, group, unit)
        lines.append(f"- {title}:{', '.join(map(str, cards))}")
    lines.append("")
    return lines


def render_report(report):
    """報告 md:不寫時間(同一輸入兩次產出相同),排序全部固定。"""
    lines = [
        "# 反向檢查報告",
        "",
        "<!-- 由 script/action_structure/build_reverse_check.py 產生,不要手改;"
        "重建結構後重跑即刷新。 -->",
        "",
        "每段由卡片結構套句型模板產生日文,正規化(空白、全半形)後與該段原文範圍全等才通過;"
        "沒有模板的句型記「無模板」算不通過。判法在 script/action_structure/reverse_check.py。",
        "",
        "## 總覽",
        "",
        "| 項目 | 數 |",
        "|---|---|",
        f"| 卡片 | {report['cards']} |",
        f"| 無官方日文(不計) | {report['no_official_text']} |",
        f"| 段 | {report['segments']} |",
        f"| 通過 | {report['passed']} |",
        f"| 不通過 | {report['failed']} |",
        f"| 有段外殘留的區塊 | {report['residue_blocks']} |",
        "",
        "## 不通過",
        "",
    ]
    by_reason = _group(report["failures"], lambda f: f["reason"])
    for reason in (REASON_NO_TEMPLATE, REASON_MISMATCH, REASON_RESIDUE):
        if reason in by_reason:
            lines.extend(_reason_section(reason, by_reason[reason]))
    if not report["failures"]:
        lines.append("全部通過。")
        lines.append("")
    return "\n".join(lines)
