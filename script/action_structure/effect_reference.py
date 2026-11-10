"""引用他卡效果:複製他卡效果的句子 → 沒有內容區塊的內嵌效果節點。

兩組句型(閉集):
- 「(この効果|このカードの効果)は、<被引用物件><部分>と同じになる」:部分是「発動時の効果」(卡片發動)、
  「発動時の儀式召喚する効果」(含儀式召喚的區塊)、「の、自身を手札から捨てて発動する効果」(代價是捨棄
  此卡的區塊)、「の効果」(整張)。
- 「[期間、]このカードは[期間、]<被引用物件><尾>」:尾是「の元々のカード名・効果と同じカード名・効果を得る」
  「と同じ、元々のカード名・効果を得る」「と同名カードとして扱い、同じ効果を得る」「と同じ効果を得る」,
  部分一律整張。前面可有一截連用形子句(「〜アップし、このカードは〜を得る」),那截照一般句子解析、
  節點與它同時。

節點(`structure_shape.embedded_node` 加鍵;其他內嵌效果節點的 `ref` 是主語字面字串,這裡的 `ref`
是物件,用 `is_reference` 分辨——沒有內容區塊的就是引用節點):
  {"node": "內嵌效果", "binding": None, "block": None, "join",
   "ref": {"object": 被引用物件 id, "text": 物件的回指字面(「その罠カード」;首次出現的物件為 None),
           "effect": {"part": 卡片發動|含動作|代價|整張, "action": 動作詞(含動作、代價才有)},
           "candidates": [候選卡號]},
   "form": 句型(「と同じになる」或得る句的尾), "subject": 主語字面, "span": 句子範圍,
   "duration": 期間(得る句有寫才有;寫在主語前的帶 placement 主語前),
   "any": True(被引用物件是泛用物件), "unparsed": {"reason": 引用其他效果}(被引用物件解析不出)}

候選卡清單在建置的第二輪求(`action_query.resolve_references`,條件式判斷在查詢層);被引用卡只看
`effect` 指定的部分(`selected_blocks`)。引用循環(`reference_cycles`)在覆蓋報告列出;查詢展開時遇到
循環就停。
"""
import re

from block_split import KIND_ACTIVATION
from clause_join import split_continuative
from segment_extract import HEAD_CATEGORY, REF_RE, TARGET_REF_RE
from segment_fields import CLAUSE_DURATION_PATTERN, parse_duration, render_duration
from structure_shape import NoTemplate, embedded_node, iter_nodes, unparsed
from synonyms import PREDICATE_STEMS, action_ancestors

REASON_REFERENCE = "引用其他效果"
PART_ACTIVATION, PART_WITH, PART_COST, PART_WHOLE = "卡片發動", "含動作", "代價", "整張"
BEFORE_SUBJECT = "主語前"

BECOME_SUBJECTS = ("この効果", "このカードの効果")
BECOME_FORM = "と同じになる"
BECOME_PARTS = (
    ("発動時の儀式召喚する効果", {"part": PART_WITH, "action": "儀式召喚"}),
    ("発動時の効果", {"part": PART_ACTIVATION}),
    ("の、自身を手札から捨てて発動する効果", {"part": PART_COST, "action": "捨棄"}),
    ("の効果", {"part": PART_WHOLE}),
)
GAIN_SUBJECT = "このカード"
GAIN_FORMS = ("の元々のカード名・効果と同じカード名・効果を得る",
              "と同じ、元々のカード名・効果を得る",
              "と同名カードとして扱い、同じ効果を得る",
              "と同じ効果を得る")

_BECOME_RE = re.compile(
    f"^(?P<subject>{'|'.join(BECOME_SUBJECTS)})は、?(?P<object>.+?)"
    f"(?P<part>{'|'.join(re.escape(lit) for lit, _ in BECOME_PARTS)}){BECOME_FORM}$")
_DURATION = f"(?:{CLAUSE_DURATION_PATTERN})"
_GAIN_RE = re.compile(
    f"(?:^|、)(?:(?P<lead>{_DURATION})、)?(?P<subject>{GAIN_SUBJECT})は、?"
    f"(?:(?P<mid>{_DURATION})、)?(?P<object>[^、]+?)"
    f"(?P<form>{'|'.join(re.escape(form) for form in GAIN_FORMS)})$")
_HEADS = "|".join(sorted(HEAD_CATEGORY, key=len, reverse=True))
REFERRED_RE = re.compile(f"^(?P<ref>その|選択した)(?P<mods>.*?)(?P<head>{_HEADS})$")
_TARGETED = "選択した"


def match_reference(text):
    """一句(不含句號)是不是引用句 → {"start": 引用子句在句中的起點, "subject", "object_start",
    "object", "effect", "form", "duration"};不是回 None。前面有連用形子句時 start > 0。"""
    m = _BECOME_RE.match(text)
    if m:
        effect = next(effect for lit, effect in BECOME_PARTS if lit == m.group("part"))
        return {"start": 0, "subject": m.group("subject"), "object_start": m.start("object"),
                "object": m.group("object"), "effect": dict(effect), "form": BECOME_FORM,
                "duration": None}
    m = _GAIN_RE.search(text)
    if not m:
        return None
    start = m.start() + 1 if m.start() > 0 else 0
    if start and start not in {offset for offset, _ in split_continuative(text)}:
        return None
    duration = None
    literal = m.group("lead") or m.group("mid")
    if literal:
        duration = parse_duration(literal)
        if m.group("lead"):
            duration["placement"] = BEFORE_SUBJECT
    return {"start": start, "subject": m.group("subject"), "object_start": m.start("object"),
            "object": m.group("object"), "effect": {"part": PART_WHOLE},
            "form": m.group("form"), "duration": duration}


def reference(obj_id, text, effect):
    """節點的 `ref`:被引用物件、回指字面、引用的部分、候選卡(建置第二輪填)。"""
    return {"object": obj_id, "text": text, "effect": effect, "candidates": []}


def reference_node(state, found, offset, end, join):
    """引用句(`match_reference` 的結果,`offset` 是引用子句在區塊原文的起點)→ 引用節點。
    被引用物件找不到、解析不出、或不是卡(超量素材、計數器)時節點標解析不出(引用其他效果)。"""
    obj_id, text = _resolve_object(state, found["object"], offset + found["object_start"])
    node = embedded_node(None, None, join)
    node["ref"] = reference(obj_id, text, found["effect"])
    node["form"] = found["form"]
    node["subject"] = found["subject"]
    if found["duration"]:
        node["duration"] = found["duration"]
    node["span"] = [offset, end]
    obj = state.find(obj_id) if obj_id else None
    if obj is None or obj["unparsed"] or obj.get("kind", "卡") != "卡":
        node["unparsed"] = unparsed(REASON_REFERENCE)
    return node


def _resolve_object(state, phrase, start):
    """被引用物件短語 → (物件 id, 回指字面);「その罠カード」型指回本區塊最近的同大類物件、
    「選択した通常罠カード」指回最近被取對象的;其餘照一般物件短語(回指或新建)。"""
    m = REFERRED_RE.match(phrase)
    if m and not REF_RE.match(phrase) and not TARGET_REF_RE.match(phrase):
        among = state.targeted if m.group("ref") == _TARGETED else None
        return state.recent_of(m.group("head"), among=among), phrase
    obj_id, ref, _ = state.object_at(phrase, start)
    return obj_id, ref


def is_reference(node):
    """引用節點:沒有內容區塊的內嵌效果節點。"""
    return node.get("node") == "內嵌效果" and node.get("block") is None \
        and isinstance(node.get("ref"), dict)


def iter_references(block):
    """區塊(含內嵌效果的區塊、分歧各支)裡的引用節點。"""
    for node in iter_nodes(block["tree"]["items"]):
        if is_reference(node):
            yield node
        elif node.get("node") == "內嵌效果" and node.get("block"):
            yield from iter_references(node["block"])


def card_references(card):
    return [node for block in card["blocks"] for node in iter_references(block)]


def selected_blocks(card, effect):
    """被引用卡上 `effect` 指定的部分(頂層區塊):
    卡片發動 = card_text 的 ① 區塊(新式魔陷的卡片發動效果),沒有編號就是卡片發動區塊(舊式整段);
    含動作 = 原文含該動作詞述語字面的區塊;代價 = 有代價段做該動作、對象是此卡的區塊;整張 = 全部。"""
    part = effect.get("part")
    blocks = card["blocks"]
    if part == PART_ACTIVATION:
        first = [b for b in blocks if b["source"] == "card_text" and b["label"] == "①"]
        return first or [b for b in blocks if b["kind"] == KIND_ACTIVATION]
    if part == PART_WITH:
        stems = [stem for stem, action, _ in PREDICATE_STEMS
                 if effect.get("action") in action_ancestors(action)]
        return [b for b in blocks if any(stem in b["text"] for stem in stems)]
    if part == PART_COST:
        return [b for b in blocks if any(
            seg["kind"] == "代價" and effect.get("action") in (seg["actions"] or ())
            and any(line["object"] == "o0" for line in seg["lines"])
            for seg in b["segments"])]
    return list(blocks)


def render_reference(node, render_object):
    """引用節點 → 引導句字面(反向檢查從區塊殘留扣掉);`render_object(物件 id, 回指字面)` 由反向檢查
    提供。句型、部分、期間對不上就丟 NoTemplate。"""
    ref = node["ref"]
    text = ref.get("text")
    obj_text = text if text and REFERRED_RE.match(text) else render_object(ref["object"], text)
    if node.get("form") == BECOME_FORM:
        part = next((lit for lit, effect in BECOME_PARTS if effect == ref["effect"]), None)
        if node.get("subject") not in BECOME_SUBJECTS or part is None or node.get("duration"):
            raise NoTemplate("引用句無模板")
        return f"{node['subject']}は、{obj_text}{part}{BECOME_FORM}"
    if node.get("form") not in GAIN_FORMS or node.get("subject") != GAIN_SUBJECT \
            or ref["effect"] != {"part": PART_WHOLE}:
        raise NoTemplate("引用句無模板")
    lead = mid = ""
    duration = node.get("duration")
    if duration:
        literal = render_duration({k: v for k, v in duration.items() if k != "placement"})
        if literal is None or duration.get("placement") not in (None, BEFORE_SUBJECT):
            raise NoTemplate("引用句的期間無模板")
        if duration.get("placement"):
            lead = literal + "、"
        else:
            mid = literal + "、"
    return f"{lead}{GAIN_SUBJECT}は{mid}{obj_text}{node['form']}"


def reference_edges(structures):
    """引用圖:卡號 → 它經引用會展開到的卡號(排序);只看解析出、非泛用的節點,而且被引用卡在
    指定部分裡自己也有引用節點時才算一條邊(展開會繼續往下走的才可能成環)。"""
    by_id = {card["id"]: card for card in structures}
    edges = {}
    for card in structures:
        if card["unparsed"]:
            continue
        for node in card_references(card):
            if node.get("unparsed") or node.get("any"):
                continue
            for cid in node["ref"]["candidates"]:
                target = by_id.get(cid)
                if target is None or target["unparsed"]:
                    continue
                if any(not n.get("unparsed") and not n.get("any")
                       for b in selected_blocks(target, node["ref"]["effect"])
                       for n in iter_references(b)):
                    edges.setdefault(card["id"], set()).add(cid)
    return {cid: sorted(targets) for cid, targets in sorted(edges.items())}


def reference_cycles(structures):
    """引用循環:引用圖的強連通分量(兩張以上,或自己引用自己),每個是排序的卡號列表,依最小卡號排序。"""
    edges = reference_edges(structures)
    index, low, on_stack, stack, found = {}, {}, set(), [], []

    def visit(cid):
        index[cid] = low[cid] = len(index)
        stack.append(cid)
        on_stack.add(cid)
        for nxt in edges.get(cid, ()):
            if nxt not in index:
                visit(nxt)
                low[cid] = min(low[cid], low[nxt])
            elif nxt in on_stack:
                low[cid] = min(low[cid], index[nxt])
        if low[cid] == index[cid]:
            component = []
            while True:
                top = stack.pop()
                on_stack.discard(top)
                component.append(top)
                if top == cid:
                    break
            if len(component) > 1 or cid in edges.get(cid, ()):
                found.append(sorted(component))

    for cid in edges:
        if cid not in index:
            visit(cid)
    return sorted(found)
