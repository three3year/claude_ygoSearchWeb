"""段樹:一個區塊的原文 → 段(扁平)+ 段樹(段、分歧、內嵌效果,節點帶連接)+ 物件。

句子層級的規則在 `segment_extract.parse_sentence`(條件/代價/效果段、「〜し、〜」的同時連接);
這裡管句子以上的結構(spec「段樹」):

- 序列:句子依序成節點;「その後、」開頭的句子與前一節點連接為「先後」,同一句裡
  「〜し、〜」切出的子句以「同時」連接。
- 分歧:● 列舉一律是分歧、不切區塊。● 前的引導句決定方式(閉集 `BRANCH_HEADERS`):
  「以下の効果から１つを選択して発動できる」= 選1(選者我方)、「以下の効果をそれぞれ適用できる」
  = 各自可以;引導句帶前提的(「自分の墓地に「X」が存在する場合、〜それぞれ適用できる。
  存在しない場合、〜から１つを選んで適用する」)是「依前提」:每個前提一支,支內再放
  那個方式的分歧,● 列舉共用。「存在しない場合」省略了物件與區域,對回前一個前提的存在原子
  (原子標 `elided`,模板只寫「存在しない場合」)。引導句認不得時分歧的方式標解析不出
  (節點帶 `unparsed`),引導句仍照一般句子解析。
- 每支各一份位置(`fork_state`):物件目前位置、本區塊提過的物件、被取對象的物件列都從分歧前的
  狀態複製,支走完取各支聯集(沒動過的支算分歧前的位置)。
- 內嵌效果:「Xは以下の効果を得る」→ 內嵌效果節點,綁定 自己 = X 的物件,內容是一個區塊
  (● 列舉成「各自可以」的分歧);區塊內「このカード」指 X。區塊 id `<區塊id>e<偏移>`,
  段與物件 id 照它的 text 算偏移。
- 「重複到停為止」(未結構化)尚未抽取。

反向檢查的模板:`tree_glue(block, ...)` 給出分歧引導句與內嵌效果引導句的字面,區塊原文
扣掉各段後只能剩它們與固定接著詞。
"""
import re

from premise import NoPremiseTemplate, render_premise, split_premises
from segment_extract import (BlockState, parse_from, parse_sentence, sentences,
                             zone_literal)
from structure_shape import (branch_node, embedded_node, new_block, segment_node,
                             unparsed)

# ● 分歧的引導句(閉集):「以下の効果」後的字面 → (方式, 選者)。模板由方式 + form 寫回。
BRANCH_HEADERS = (
    ("から１つを選択して発動できる", "選1", "我方"),
    ("から１つを選択して発動する", "選1", "我方"),
    ("から１つを選んで適用する", "選1", "我方"),
    ("から１つを選んで適用できる", "選1", "我方"),
    ("をそれぞれ適用できる", "各自可以", None),
)
_HEADER_FORMS = {form: (mode, chooser) for form, mode, chooser in BRANCH_HEADERS}
_HEADER_RE = re.compile(
    "^(?P<pre>.*?)以下の効果(?P<form>"
    + "|".join(re.escape(form) for form, _, _ in BRANCH_HEADERS) + ")$")
_EMBED_RE = re.compile("^(?P<subject>.+?)は以下の効果を得る$")
_ELIDED_RE = re.compile("^存在しない場合、?")
_ITEM_RE = re.compile("(?:^|\n)●")

REASON_BRANCH_MODE = "分歧方式判不出"
REASON_BRANCH_PREMISE = "分歧前提解析不出"
EMBED_HEADER = "は以下の効果を得る"


# ── 抽取 ─────────────────────────────────────────────────────
def extract_block(block, card, lookups=None, self_id="o0"):
    """就地把段、段樹寫進 block,物件寫進 card["objects"];lookups 見 card_structure.build_lookups。"""
    state = BlockState(block, card, lookups, self_id=self_id)
    text = block["text"]
    body_start = 2 if block["label"] else 0  # 「①：」兩個字元
    if text.startswith("また、", body_start):
        body_start += 3  # 區塊開頭的接著詞
    items = [m.end() for m in _ITEM_RE.finditer(text, body_start)]
    if not items:
        block["tree"]["items"] = _parse_run(state, sentences(text, body_start))
        return block
    head_spans = sentences(text, body_start, items[0] - 1)
    headers, plain = _split_headers(state, head_spans)
    nodes = _parse_run(state, plain)
    if headers and headers[-1][0] == "內嵌":
        # 內嵌效果:● 列舉是內容區塊的事,外層不解析它們。主語解析不出就退回分歧路徑
        # (引導句照一般句子解析、分歧方式標解析不出),原文不會被靜默略過。
        for extra in headers[:-1]:
            _parse_header_as_sentence(state, extra)
        _, subject, _, start, join = headers[-1]
        node = _embedded(state, subject, start, join, lookups)
        if node is not None:
            nodes.append(node)
            block["tree"]["items"] = nodes
            return block
        headers = []
    branches = _parse_items(state, items)
    nodes.append(_branch(state, headers, branches))
    block["tree"]["items"] = nodes
    return block


def _parse_run(state, spans):
    """一串句子 → 段節點(「その後、」是先後連接);段寫進區塊的扁平列表。"""
    nodes = []
    for start, end in spans:
        join = None
        if state.block["text"].startswith("その後、", start):
            join, start = "先後", start + 4
        for seg, seg_join in parse_sentence(state, start, end):
            state.block["segments"].append(seg)
            nodes.append(segment_node(seg["id"], seg_join or join))
            join = None
    return nodes


def _header_of(text):
    """句子是不是分歧/內嵌效果的引導句 → ("分歧", 前提字面, form) / ("內嵌", 主語, None) / None。
    只看字面,不動狀態(前提要等確定是引導句才解析)。"""
    m = _HEADER_RE.match(text)
    if m:
        return "分歧", m.group("pre"), m.group("form")
    m = _EMBED_RE.match(text)
    if m:
        return "內嵌", m.group("subject"), None
    return None


def _split_headers(state, spans):
    """● 前的句子:結尾連續的引導句歸分歧,其餘照一般句子解析。回傳 (引導句列表, 一般句子範圍)。
    引導句 = (種類, 前提字面, form, 起點, 連接)。"""
    headers = []
    plain = list(spans)
    while plain:
        start, end = plain[-1]
        text = state.block["text"][start:end]
        join = None
        if text.startswith("その後、"):
            join, text, start = "先後", text[4:], start + 4
        header = _header_of(text)
        if header is None:
            break
        headers.insert(0, header + (start, join))
        plain.pop()
    return headers, plain


def _parse_items(state, items):
    """● 列舉的每一支:各自一份狀態,支內句子成序列;回傳各支 {"premise", "items"}。"""
    text = state.block["text"]
    bounds = []
    for i, start in enumerate(items):
        end = items[i + 1] - 1 if i + 1 < len(items) else len(text)
        bounds.append((start, end))
    runs = [lambda s=start, e=end: _parse_run(state, sentences(text, s, e))
            for start, end in bounds]
    return [{"premise": None, "items": nodes} for nodes in fork_state(state, runs)]


def fork_state(state, runs):
    """分歧時每支各一份位置:每個 run 從分歧前的狀態出發,走完把位置取聯集、提過的物件與
    取對象集合合併。回傳各 run 的結果列表。"""
    base_positions = {k: dict(v) for k, v in state.positions.items()}
    base_recent, base_targeted = list(state.recent), list(state.targeted)
    base_acted = {k: list(v) for k, v in state.acted.items()}
    results, branch_positions = [], []
    added_recent, targeted, acted = [], list(base_targeted), {}
    for run in runs:
        state.positions = {k: dict(v) for k, v in base_positions.items()}
        state.recent, state.targeted = list(base_recent), list(base_targeted)
        state.acted = {k: list(v) for k, v in base_acted.items()}
        results.append(run())
        branch_positions.append(state.positions)
        added_recent.extend(i for i in state.recent
                            if i not in base_recent and i not in added_recent)
        targeted.extend(i for i in state.targeted if i not in targeted)
        for obj_id, actions in state.acted.items():
            known = acted.setdefault(obj_id, [])
            known.extend([a for a in actions if a not in known])
    state.positions = _union_positions(state, base_positions, branch_positions)
    state.recent, state.targeted, state.acted = base_recent + added_recent, targeted, acted
    return results


def _union_positions(state, base, branches):
    """各支走完的位置取聯集;某支沒動過的物件算它在分歧前的位置(目前位置或初始位置)。"""
    merged = {}
    for obj_id in {k for pos in branches for k in pos}:
        union = {"zones": [], "inferred": False}
        for pos in branches:
            current = pos.get(obj_id) or base.get(obj_id)
            if current is None:
                obj = state.find(obj_id)
                if not obj or not obj["initial_position"]:
                    continue
                current = {"zones": obj["initial_position"], "inferred": False}
            for z in current["zones"]:
                if z not in union["zones"]:
                    union["zones"].append(dict(z))
            union["inferred"] = union["inferred"] or current["inferred"]
        merged[obj_id] = union
    return merged


def _branch(state, headers, branches):
    """引導句 + 各支 → 分歧節點。"""
    if not headers:
        node = branch_node(None, branches=branches)
        node["unparsed"] = unparsed(REASON_BRANCH_MODE)
        return node
    if len(headers) == 1 and not headers[0][1]:
        _, _, form, _, join = headers[0]
        mode, chooser = _HEADER_FORMS[form]
        node = branch_node(mode, chooser, branches, join)
        node["form"] = form
        node["span"] = _headers_span(state, headers)
        return node
    # 依前提:每個引導句帶前提,各成一支、支內是那個方式的分歧(● 列舉共用)。
    outer = []
    previous = None
    for _, pre, form, start, join in headers:
        premise = _header_premise(state, pre, start, previous)
        if premise is None:
            node = branch_node(None, branches=branches, join=headers[0][4])
            node["unparsed"] = unparsed(REASON_BRANCH_PREMISE)
            for header in headers:
                _parse_header_as_sentence(state, header)
            return node
        previous = premise
        mode, chooser = _HEADER_FORMS[form]
        inner = branch_node(mode, chooser, branches)
        inner["form"] = form
        outer.append({"premise": premise, "items": [inner]})
    node = branch_node("依前提", None, outer, headers[0][4])
    node["span"] = _headers_span(state, headers)
    return node


def _headers_span(state, headers):
    """引導句(連續的幾句)的原文範圍;反向檢查寫不出引導句時據此扣掉、只列無模板。"""
    text = state.block["text"]
    start = headers[0][3]
    end = text.find("。", headers[-1][3])
    return [start, len(text) if end < 0 else end]


def _header_premise(state, pre, start, previous):
    """引導句前的前提字面 → 條件式;「存在しない場合、」對回前一個前提的存在/位置原子。
    字面沒被前提規則吃完就回 None。"""
    if not pre:
        return None
    if _ELIDED_RE.match(pre):
        atom = _existence_atom(previous)
        if atom is None or _ELIDED_RE.match(pre).end() != len(pre):
            return None
        elided = {k: v for k, v in atom.items() if k != "order"}
        elided["elided"] = True
        return {"op": "非", "arg": elided}
    premise, _, clause_start = split_premises(pre, state, start, parse_from,
                                              zone_literal)
    if premise is None or clause_start != start + len(pre):
        return None
    return premise


def _existence_atom(premise):
    if premise is None:
        return None
    atoms = premise["args"] if premise.get("op") == "且" else [premise]
    for atom in atoms:
        if atom.get("op") == "存在" and "zones" in atom:
            return atom
        if atom.get("op") == "位置":
            return {"op": "存在", "object": atom["object"], "zones": atom["zones"],
                    "form": atom.get("form")}
    return None


def _parse_header_as_sentence(state, header):
    """引導句認不成分歧時照一般句子解析(段會標解析不出,原文不會被靜默略過)。"""
    _, _, _, start, _ = header
    text = state.block["text"]
    end = text.find("。", start)
    end = len(text) if end < 0 else end
    for seg, _ in parse_sentence(state, start, end):
        state.block["segments"].append(seg)


def _embedded(state, subject, start, join, lookups):
    """「Xは以下の効果を得る」→ 內嵌效果節點:綁定 自己 = X,內容是 ● 列舉組成的區塊;
    X 解析不出回 None(引導句已照一般句子解析)。"""
    obj_id, ref, reason = state.object_at(subject, start)
    if obj_id is None:
        _parse_header_as_sentence(state, (None, None, None, start, None))
        return None
    text = state.block["text"]
    first = text.find("●", start)
    inner = new_block(f"{state.block['id']}e{first}", "編號效果", None,
                      state.block["source"],
                      (state.block["span"][0] + first, state.block["span"][1]),
                      text[first:])
    # 內容區塊自己抽取(「このカード」綁定成 X),段與物件 id 照內層區塊的偏移算。
    extract_block(inner, state.card, lookups, self_id=obj_id)
    inner_items = inner["tree"]["items"]
    if len(inner_items) == 1 and inner_items[0]["node"] == "分歧" \
            and inner_items[0].get("unparsed", {}).get("reason") == REASON_BRANCH_MODE:
        inner_items[0].pop("unparsed")
        inner_items[0]["mode"] = "各自可以"
    node = embedded_node({"自己": obj_id}, inner, join)
    end = text.find("。", start)
    node["span"] = [start, len(text) if end < 0 else end]  # 引導句的原文範圍(殘留檢查扣掉它)
    if ref is not None:
        node["ref"] = ref   # 主語的回指字面(「この効果で特殊召喚したモンスター」),模板照它寫
    return node


# ── 模板(反向檢查)────────────────────────────────────────────
class NoTreeTemplate(Exception):
    """分歧或內嵌效果的引導句寫不出字面:訊息是 detail。"""


def embedded_bindings(card):
    """區塊 id → 內嵌效果的綁定(反向檢查渲染內嵌區塊的段時「このカード」要寫成綁定的物件)。"""
    found = {}
    stack = list(card["blocks"])
    while stack:
        block = stack.pop()
        for node in iter_tree(block["tree"]["items"]):
            if node["node"] == "內嵌效果" and node.get("block"):
                found[node["block"]["id"]] = node.get("binding")
                stack.append(node["block"])
    return found


def iter_tree(items):
    for node in items:
        yield node
        if node["node"] == "分歧":
            for branch in node["branches"]:
                yield from iter_tree(branch["items"])


def tree_glue(block, render_premise_text, render_object):
    """區塊段樹裡所有引導句的字面(分歧的「以下の効果〜」、依前提各支的「前提、以下の効果〜」、
    內嵌效果的「Xは以下の効果を得る」);長的在前,反向檢查從區塊殘留裡逐一扣掉。
    `render_premise_text(條件式) → 字面`、`render_object(物件id, 回指字面或 None) → 字面`
    由反向檢查提供。
    節點的方式判不出就丟 NoTreeTemplate。"""
    pieces = []
    for node in iter_tree(block["tree"]["items"]):
        if node.get("unparsed"):
            raise NoTreeTemplate(f"段樹無模板:{node['unparsed']['reason']}")
        if node["node"] == "分歧":
            pieces.extend(_branch_headers(node, render_premise_text))
        elif node["node"] == "內嵌效果":
            binding = node.get("binding") or {}
            if "自己" not in binding:
                raise NoTreeTemplate("內嵌效果無綁定")
            pieces.append(render_object(binding["自己"], node.get("ref")) + EMBED_HEADER)
    return sorted(set(pieces), key=len, reverse=True)


def _branch_headers(node, render_premise_text):
    mode = node.get("mode")
    if mode == "依前提":
        out = []
        for branch in node["branches"]:
            if branch.get("premise") is None or len(branch["items"]) != 1 \
                    or branch["items"][0]["node"] != "分歧":
                raise NoTreeTemplate("依前提的支無模板")
            inner = branch["items"][0]
            if inner.get("unparsed"):
                raise NoTreeTemplate(f"段樹無模板:{inner['unparsed']['reason']}")
            out.append(render_premise_text(branch["premise"])
                       + _header_text(inner))
        return out
    if node.get("form") is None and mode == "各自可以":
        return []   # 內嵌效果裡的 ● 列舉:引導句在內嵌效果節點上
    return [_header_text(node)]


def _header_text(node):
    form = node.get("form")
    expected = _HEADER_FORMS.get(form)
    if expected is None or expected != (node.get("mode"), node.get("chooser")):
        raise NoTreeTemplate("分歧引導句無模板")
    return "以下の効果" + form


def render_premise_prefix(premise, render_zones, render_object):
    """依前提各支的前提字面(後面接引導句,所以帶讀點)。"""
    try:
        return render_premise(premise, render_zones,
                              lambda obj_id: render_object(obj_id, None), followed=True)
    except NoPremiseTemplate as e:
        raise NoTreeTemplate(str(e)) from None
