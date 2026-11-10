"""段樹:一個區塊的原文 → 段(扁平)+ 段樹(段、分歧、內嵌效果,節點帶連接)+ 物件。

句子層級的規則在 `segment_extract.parse_sentence`(條件/代價/效果段、「〜し、〜」的同時連接);
這裡管句子以上的結構(spec「段樹」):

- 序列:句子依序成節點;「その後、」開頭的句子與前一節點連接為「先後」,「さらに、」開頭的
  連接為「同時」,同一句裡「〜し、〜」切出的子句以「同時」連接。
- 分歧:● 列舉一律是分歧、不切區塊。● 前的引導句決定方式(閉集 `BRANCH_HEADERS`):
  「以下の効果から１つを選択して発動できる」= 選1(選者我方)、「以下の効果をそれぞれ適用できる」
  = 各自可以;引導句帶前提的(「自分の墓地に「X」が存在する場合、〜それぞれ適用できる。
  存在しない場合、〜から１つを選んで適用する」)是「依前提」:每個前提一支,支內再放
  那個方式的分歧,● 列舉共用。「存在しない場合」省略了物件與區域,對回前一個前提的存在原子
  (原子標 `elided`,模板只寫「存在しない場合」)。引導句認不得時分歧的方式標解析不出
  (節點帶 `unparsed`),引導句仍照一般句子解析。
- 每支各一份位置(`fork_state`):物件目前位置、本區塊提過的物件、被取對象的物件列、延遲狀態
  都從分歧前的狀態複製,支走完取各支聯集(沒動過的支算分歧前的位置)。
- 內嵌效果:「Xは以下の効果を得る」→ 內嵌效果節點,綁定 自己 = X 的物件,內容是一個區塊
  (● 列舉成「各自可以」的分歧);區塊內「このカード」指 X。區塊 id `<區塊id>e<偏移>`,
  段與物件 id 照它的 text 算偏移。
- 引用他卡效果:「この効果は、その罠カード発動時の効果と同じになる」型的句子(前面可有連用形
  子句)成沒有內容區塊的內嵌效果節點,規則在 `effect_reference`。
- 「重複到停為止」(「〜処理を繰り返す」「〜までこの効果を繰り返す」,`segment_extract.REPEAT_RE`):
  那一句成一個沒有動作詞的段、標 `unstructured`(段與段樹節點都標),第一輪就是它前面的句子。

反向檢查的模板:`tree_glue(block, ...)` 給出分歧引導句與內嵌效果引導句的字面,區塊原文
扣掉各段後只能剩它們與固定接著詞。
"""
import re

from block_split import body_start
from block_state import BlockState, INTERVAL_RE, INTERVAL_REASON
from clause_join import JOIN, is_continuative, split_continuative
from effect_reference import is_reference, match_reference, reference_node, render_reference
from premise import render_premise, split_premises, timepoint_glue
from segment_extract import fill_clause, limit_note, parse_sentence, sentences
from segment_fields import EFFECT_HOLDER_PREFIX
from structure_shape import (DISPLAY_WORD, NoTemplate, branch_node, display_value, display_word,
                             embedded_node, new_block, segment_node, swap_sides, unparsed)
from synonyms import ACTIVATION_SUFFIXES
from turn_phase import build_timepoints, match_timepoints
from zone_phrase import parse_from, zone_literal

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
# 依值分支型:「Xは(このカードの)表示形式によって以下の効果を得る」,`by` 是「によって」前的字面。
_EMBED_RE = re.compile("^(?P<subject>.+?)は(?:(?P<by>[^、]+?)によって)?以下の効果を得る$")
# 召喚條件的 ● 列舉(票 09):「〜は(融合召喚及び)以下の方法でのみ特殊召喚できる」。引導句本身是
# 限制段(極性只能,原因 召喚方式 含「以下の方法」),分歧節點記 `header` = 那個段的 id、方式 選1、
# 選者 我方;● 各支是召喚手續。
_METHOD_HEADER_RE = re.compile("以下の方法でのみ(?:EXデッキから)?特殊召喚できる$")
_ELIDED_RE = re.compile("^存在しない場合、?")
# ● 列舉:行首,或緊接句號(官方文本有些不換行:「〜を得る。●攻撃表示：」)。
_ITEM_RE = re.compile("(?:^|\n|(?<=。))●")

HOLDER_EQUIP_HEADER = "裝備"
REASON_BRANCH_MODE = "分歧方式判不出"
REASON_BRANCH_PREMISE = "分歧前提解析不出"
EMBED_TAIL = "以下の効果を得る"
EMBED_HEADER = "は" + EMBED_TAIL
# 句首的接著詞 → 與前一節點的連接:「その後、」先後;「さらに、」同時(追加處理與前面同時進行)。
# 反向檢查把兩者都當固定接著詞(`reverse_check.GLUE`)。
SENTENCE_JOINS = (("その後、", "先後"), ("さらに、", JOIN))


def extract_block(block, card, lookups=None, self_id="o0"):
    """就地把段、段樹寫進 block,物件寫進 card["objects"];lookups 見 card_structure.build_lookups。"""
    state = BlockState(block, card, lookups, self_id=self_id)
    text = block["text"]
    start = body_start(block)
    items = [m.end() for m in _ITEM_RE.finditer(text, start)]
    if not items:
        block["tree"]["items"] = _parse_run(state, sentences(text, start))
        return block
    head_spans = sentences(text, start, items[0] - 1)
    headers, plain = _split_headers(state, head_spans)
    nodes = _parse_run(state, plain)
    if headers and headers[-1][0] == "方法":
        # 召喚條件的 ● 列舉:引導句照一般句子解析成限制段(記在節點 header),● 各支是召喚手續。
        for extra in headers[:-1]:
            _parse_header_as_sentence(state, extra)
        header_segs = _parse_header_as_sentence(state, headers[-1])
        nodes.extend(segment_node(seg["id"], seg_join) for seg, seg_join in header_segs)
        branches = _parse_items(state, items)
        node = branch_node("選1", "我方", branches, headers[-1][4])
        node["header"] = header_segs[-1][0]["id"] if header_segs else None
        if not header_segs or header_segs[-1][0]["unparsed"]:
            node["unparsed"] = unparsed(REASON_BRANCH_MODE)
        nodes.append(node)
        block["tree"]["items"] = nodes
        return block
    if headers and headers[-1][0] == HOLDER_EQUIP_HEADER:
        for extra in headers[:-1]:
            _parse_header_as_sentence(state, extra)
        header_segs = _parse_header_as_sentence(state, headers[-1])
        nodes.extend(segment_node(seg["id"], seg_join or (headers[-1][4] if i == 0 else None))
                     for i, (seg, seg_join) in enumerate(header_segs))
        holder = _equip_holder(header_segs)
        if holder is not None:
            seg, obj_id = holder
            node = _embedded_content(state, obj_id, headers[-1][3], JOIN, lookups)
            node["header"] = seg["id"]
            nodes.append(node)
            block["tree"]["items"] = nodes
            return block
        nodes.extend(_branch(state, [], _parse_items(state, items)))
        block["tree"]["items"] = nodes
        return block
    if headers and headers[-1][0] == "內嵌":
        # 內嵌效果:● 列舉是內容區塊的事,外層不解析它們。主語解析不出就退回分歧路徑
        # (引導句照一般句子解析、分歧方式標解析不出),原文不會被靜默略過。
        for extra in headers[:-1]:
            _parse_header_as_sentence(state, extra)
        _, subject, by, start, join = headers[-1]
        end = text.find("。", start)
        end = len(text) if end < 0 else end
        subject_start = end - len(subject + "は" + (f"{by}によって" if by else "") + EMBED_TAIL)
        if subject_start > start:
            for i, (seg, seg_join) in enumerate(parse_sentence(state, start, subject_start - 1)):
                state.block["segments"].append(seg)
                nodes.append(segment_node(seg["id"], seg_join or (join if i == 0 else None)))
            start, join = subject_start, JOIN
        node = _embedded(state, subject, start, join, lookups, by)
        if node is not None:
            nodes.append(node)
            block["tree"]["items"] = nodes
            return block
        headers = []
    # 引導句前面整個是時點(m3 票 11)的先認;不是時點才看連用形串接的子句(m3 票 07)。
    timepoints = _header_timepoints(state, headers)
    if timepoints is None:
        lead_nodes, headers = _lead_in(state, headers)
        nodes.extend(lead_nodes)
    branches = _parse_items(state, items)
    nodes.extend(_branch(state, headers, branches, timepoints))
    block["tree"]["items"] = nodes
    return block


def _lead_in(state, headers):
    """引導句前面連用形串接的子句(「Xを対象とし、以下の効果から１つを選択して発動できる」,m3 票 07):
    先照一般子句解析成段——宣告的對象要在各支之前點名,各支的回指(対象のモンスター、そのモンスター)
    才指得回它;引導句只剩「以下の効果〜」,與前面的段同時。發動句的引導句(〜発動できる)前面是代價子句。
    回傳 (段節點, 引導句列表);不是這種引導句時原樣交回。"""
    if len(headers) != 1 or headers[0][0] != "分歧":
        return [], headers
    kind, pre, form, start, join = headers[0]
    clause = pre[:-1] if pre.endswith("、") else ""
    if not is_continuative(clause):
        return [], headers
    nodes = []
    for seg, seg_join in parse_sentence(state, start, start + len(clause),
                                        activation_lead=form.endswith(ACTIVATION_SUFFIXES)):
        state.block["segments"].append(seg)
        nodes.append(segment_node(seg["id"], seg_join or (None if nodes else join)))
    return nodes, [(kind, "", form, start + len(pre), JOIN)]


def _parse_run(state, spans):
    """一串句子 → 段節點(「その後、」是先後連接、「さらに、」是同時連接);段寫進區塊的扁平列表。
    句尾是「その効果は「…」となる」的,那一截成內嵌效果節點(與前面的段同時)。"""
    nodes = []
    for start, end in spans:
        join = None
        for word, sentence_join in SENTENCE_JOINS:
            if state.block["text"].startswith(word, start):
                join, start = sentence_join, start + len(word)
                break
        replaced = _replaced_effect(state, start, end)
        if replaced is not None:
            end = replaced["prefix_end"]
        referenced = match_reference(state.block["text"][start:end])
        sentence_end = end
        if referenced is not None:
            ref_start = start + referenced["start"]
            end = ref_start - 1 if referenced["start"] else start
        for seg, seg_join in parse_sentence(state, start, end) if end > start else ():
            state.block["segments"].append(seg)
            node = segment_node(seg["id"], seg_join or join)
            if seg["unstructured"]:
                node["unstructured"] = True   # 段樹也標,走樹的人不必翻段
            nodes.append(node)
            join = None
        if referenced is not None:
            nodes.append(reference_node(state, referenced, ref_start, sentence_end,
                                        JOIN if end > start else join))
        if replaced is not None:
            nodes.append(_replaced_node(state, replaced, JOIN if end > start else join))
    return nodes


# 效果被換掉:「(〜し、)その(相手の)効果は「…」となる」。主語指回本區塊最近被發動的
# 那張卡(與「その発動」同一把尺);引號裡是換上去的效果,寫的是那張卡持有者的視角。
REPLACED_SUBJECTS = ("その効果", "その相手の効果", "その相手が発動した効果")
REPLACED_OPEN, REPLACED_CLOSE = "は「", "」となる"
_REPLACED_RE = re.compile(
    f"(?:^|、)(?P<subject>{'|'.join(REPLACED_SUBJECTS)}){REPLACED_OPEN}"
    f"(?P<content>[^。]+){REPLACED_CLOSE}$")
SIDE_SWAP = {"我方": "對手"}


def _replaced_effect(state, start, end):
    """句尾的「その効果は「…」となる」→ {前一截的結束偏移, 主語字面與物件, 內容範圍};
    不是這種句子、或主語指不回被發動的卡時回 None(整句照一般句子解析)。"""
    text = state.block["text"]
    m = _REPLACED_RE.search(text[start:end])
    if not m:
        return None
    obj_id = state.recent_of("カード", action="發動")
    if obj_id is None:
        return None
    return {"prefix_end": start + m.start(), "subject": m.group("subject"),
            "subject_start": start + m.start("subject"), "object": obj_id,
            "content": (start + m.start("content"), start + m.end("content")),
            "end": end}


def _replaced_node(state, replaced, join):
    """效果被換掉 → 內嵌效果節點:綁定 {自己: 效果所屬的物件, 我方: 對手},內容區塊照一般規則抽取
    (「このカード」指那張卡)後把方對調再存(引號裡的「相手」是我方)。"""
    text = state.block["text"]
    first, last = replaced["content"]
    inner = new_block(f"{state.block['id']}e{first}", "編號效果", None,
                      state.block["source"],
                      (state.block["span"][0] + first, state.block["span"][0] + last),
                      text[first:last])
    extract_block(inner, state.card, state.lookups, self_id=replaced["object"])
    inner["segments"] = [swap_sides(seg) for seg in inner["segments"]]
    state.card["objects"] = [swap_sides(obj) if obj["block"] == inner["id"] else obj
                             for obj in state.card["objects"]]
    node = embedded_node({"自己": replaced["object"], **SIDE_SWAP}, inner, join)
    node["form"] = REPLACED_CLOSE
    node["subject"] = replaced["subject"]
    node["span"] = [replaced["subject_start"], replaced["end"]]
    return node


def _header_of(text):
    m = _HEADER_RE.match(text)
    if m:
        return "分歧", m.group("pre"), m.group("form")
    m = _EMBED_RE.match(text)
    if m:
        if "、" in m.group("subject"):
            # 「このカードを手札から特殊召喚し、このカードは以下の効果を得る」:連用形切開後
            # 最後一截才是引導句,前面照一般句子解析(`extract_block`)。
            pieces = split_continuative(text)
            last = _EMBED_RE.match(pieces[-1][1]) if len(pieces) > 1 else None
            if last and "、" not in last.group("subject"):
                m = last
        return "內嵌", m.group("subject"), m.group("by")
    if _METHOD_HEADER_RE.search(text):
        return "方法", None, None
    if EFFECT_HOLDER_PREFIX in text:
        return HOLDER_EQUIP_HEADER, None, None
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
        note = limit_note(text)
        if header is None and note:
            # 分歧引導句後的括號版次數限制(m3 票 02):扣掉注記再認;注記在 `_branch` 進略過文本。
            header = _header_of(text[:note.start()])
            if header is not None and header[0] != "分歧":
                header = None
        if header is None:
            break
        headers.insert(0, header + (start, join))
        plain.pop()
    return headers, plain


def _strip_interval(state, pre, start):
    """引導句開頭的「１ターンに１度、」(票 09):次數限制不記、進略過文本;回傳 (其餘前提字面, 起點)。"""
    m = INTERVAL_RE.match(pre)
    if not m:
        return pre, start
    state.omit(start, m.group(), INTERVAL_REASON)
    return pre[m.end():], start + m.end()


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
    base_acted, base_delayed = {k: list(v) for k, v in state.acted.items()}, state.delayed
    results, branch_positions = [], []
    added_recent, targeted, acted, delayed = [], list(base_targeted), {}, base_delayed
    for run in runs:
        state.positions = {k: dict(v) for k, v in base_positions.items()}
        state.recent, state.targeted = list(base_recent), list(base_targeted)
        state.acted, state.delayed = {k: list(v) for k, v in base_acted.items()}, base_delayed
        results.append(run())
        delayed = delayed or state.delayed
        branch_positions.append(state.positions)
        added_recent.extend(i for i in state.recent
                            if i not in base_recent and i not in added_recent)
        targeted.extend(i for i in state.targeted if i not in targeted)
        for obj_id, actions in state.acted.items():
            known = acted.setdefault(obj_id, [])
            known.extend([a for a in actions if a not in known])
    state.positions = _union_positions(state, base_positions, branch_positions)
    state.recent, state.targeted, state.acted = base_recent + added_recent, targeted, acted
    state.delayed = delayed
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


def _branch(state, headers, branches, timepoints=None):
    """引導句 + 各支 → [分歧節點];引導句的前提是時點(「〜したターンの〈階段〉に、以下の効果から〜」,
    `timepoints` 是 `_header_timepoints` 先解析好的)時,各時點的條件段排在分歧節點前面。"""
    if not headers:
        node = branch_node(None, branches=branches)
        node["unparsed"] = unparsed(REASON_BRANCH_MODE)
        return [node]
    if len(headers) == 1:
        kind, pre, form, start, join = headers[0]
        pre, start = _strip_interval(state, pre, start)
        headers = [(kind, pre, form, start, join)]
    if len(headers) == 1 and not headers[0][1]:
        _, _, form, _, join = headers[0]
        mode, chooser = _HEADER_FORMS[form]
        node = branch_node(mode, chooser, branches, join)
        node["form"] = form
        node["span"] = _headers_span(state, headers)
        _omit_header_notes(state, headers)
        return [node]
    # 依前提:每個引導句帶前提,各成一支、支內是那個方式的分歧(● 列舉共用)。
    outer = []
    previous = None
    turn_segs = []
    for _, pre, form, start, join in headers:
        if timepoints is not None:
            premise, turn_segs = timepoints
        else:
            premise = _header_premise(state, pre, start, previous)
        if premise is None:
            node = branch_node(None, branches=branches, join=headers[0][4])
            node["unparsed"] = unparsed(REASON_BRANCH_PREMISE)
            for header in headers:
                _parse_header_as_sentence(state, header)
            return [node]
        previous = premise
        mode, chooser = _HEADER_FORMS[form]
        inner = branch_node(mode, chooser, branches)
        inner["form"] = form
        outer.append({"premise": premise, "items": [inner]})
    nodes = [segment_node(seg["id"], headers[0][4] if i == 0 else None)
             for i, seg in enumerate(turn_segs)]
    node = branch_node("依前提", None, outer, None if turn_segs else headers[0][4])
    node["span"] = _headers_span(state, headers)
    _omit_header_notes(state, headers)
    return nodes + [node]


def _header_timepoints(state, headers):
    """單一分歧引導句的前提字面整個是時點(`turn_phase`,可列舉;開頭可有「１ターンに１度、」)→
    (條件式, 各時點的條件段);不是就回 None、不開段。條件段在這裡就寫進區塊的扁平列表:時點的動作
    發生在各支之前,要在解析各支之前填格(條件段動過的位置傳給各支,各支動過的位置不倒流回條件段),
    所以由 `extract_block` 在 `_parse_items` 前呼叫。引導句有兩句以上(依前提的多支)時不認。"""
    if len(headers) != 1 or headers[0][0] != "分歧":
        return None
    _, pre, _, start, _ = headers[0]
    interval = INTERVAL_RE.match(pre)
    skip = interval.end() if interval else 0
    matched = match_timepoints(pre[skip:])
    if matched is None or matched[-1] != len(pre) - skip:
        return None
    points = build_timepoints(state, pre[skip:], start + skip, matched, fill_clause,
                              parse_from, zone_literal)
    state.block["segments"].extend(points.segs)
    premise = points.atoms[0] if len(points.atoms) == 1 else {"op": "且", "args": points.atoms}
    return premise, points.segs


def _omit_header_notes(state, headers):
    """認成分歧的引導句,句尾的括號版次數限制(「〜発動できる（このカード名の以下の効果はそれぞれ
    １ターンに１度しか選択できない）」)進略過文本。引導句認不成分歧時照一般句子解析,由 `parse_sentence` 剝。"""
    text = state.block["text"]
    for _, _, _, start, _ in headers:
        end = text.find("。", start)
        note = limit_note(text[start:len(text) if end < 0 else end])
        if note:
            state.omit(start + note.start(), note.group(), INTERVAL_REASON)


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
        elided["form"] = "場合、" if pre.endswith("、") else "場合"
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
    segs = parse_sentence(state, start, end)
    for seg, _ in segs:
        state.block["segments"].append(seg)
    return segs


def _embedded(state, subject, start, join, lookups, by=None):
    """「Xは以下の効果を得る」→ 內嵌效果節點:綁定 自己 = X,內容是 ● 列舉組成的區塊;
    X 解析不出回 None(引導句已照一般句子解析)。依值分支型(「Xは表示形式によって〜」,`by`)
    的內容區塊是依前提分歧,每個 ● 的標籤是那一支的前提(`_extract_labelled`)。"""
    obj_id, ref, reason = state.object_at(subject, start)
    if obj_id is None:
        _parse_header_as_sentence(state, (None, None, None, start, None))
        return None
    node = _embedded_content(state, obj_id, start, join, lookups, by)
    if by is not None:
        node["by"] = by
    text = state.block["text"]
    end = text.find("。", start)
    node["span"] = [start, len(text) if end < 0 else end]
    if ref is not None:
        node["subject"] = ref
    return node


def _embedded_content(state, obj_id, start, join, lookups, by=None):
    text = state.block["text"]
    first = text.find("●", start)
    inner = new_block(f"{state.block['id']}e{first}", "編號效果", None,
                      state.block["source"],
                      (state.block["span"][0] + first, state.block["span"][1]),
                      text[first:])
    # 內容區塊自己抽取(「このカード」綁定成 X),段與物件 id 照內層區塊的偏移算。
    if by is not None:
        _extract_labelled(inner, state.card, lookups, obj_id, by)
    else:
        extract_block(inner, state.card, lookups, self_id=obj_id)
    inner_items = inner["tree"]["items"]
    if len(inner_items) == 1 and inner_items[0]["node"] == "分歧" \
            and inner_items[0].get("unparsed", {}).get("reason") == REASON_BRANCH_MODE:
        inner_items[0].pop("unparsed")
        inner_items[0]["mode"] = "各自可以"
    return embedded_node({"自己": obj_id}, inner, join)


def _equip_holder(segs):
    """「以下の効果を持つ装備魔法カード扱いで〜に装備する」的裝備段 → (段, 被當成裝備卡的物件);
    沒有這種段回 None。"""
    for seg, _ in segs:
        if seg["unparsed"]:
            continue
        for line in seg["lines"]:
            treat = ((line["to"] or {}).get("form") or {}).get("treat") or {}
            if (treat.get("text") or "").startswith(EFFECT_HOLDER_PREFIX):
                return seg, line["object"]
    return None


# ● 的標籤:「●攻撃表示：」;依值是表示形式時標籤是表示形式字面 → 前提原子
# {"op": "表示形式", "object": 綁定物件, "face"/"position": 有寫的一半}。
LABEL_FORM = "標籤"
LABEL_MARK = "："
BY_DISPLAY = ("表示形式", "このカードの表示形式")
_LABEL_RE = re.compile(f"(?P<label>[^{LABEL_MARK}。\n●]+){LABEL_MARK}")
DISPLAY_ATOM = "表示形式"


def _label_premise(label, by, obj_id):
    if by in BY_DISPLAY and re.fullmatch(DISPLAY_WORD, label):
        atom = {"op": DISPLAY_ATOM, "object": obj_id}
        atom.update({k: v for k, v in display_value(label).items() if v})
        return atom
    return None


def _extract_labelled(block, card, lookups, self_id, by):
    """依值分支型的內容區塊:每個 ● 一支,標籤是那支的前提、標籤後的句子照一般規則解析;
    有一支的標籤認不得,分歧節點標「分歧前提解析不出」(段照常抽取)。"""
    state = BlockState(block, card, lookups, self_id=self_id)
    text = block["text"]
    items = [m.end() for m in _ITEM_RE.finditer(text)]
    bounds, premises, labels = [], [], []
    for i, start in enumerate(items):
        end = items[i + 1] - 1 if i + 1 < len(items) else len(text)
        label = _LABEL_RE.match(text, start)
        premises.append(label and _label_premise(label.group("label"), by, self_id))
        labels.append([start, label.end()] if label else None)
        bounds.append((label.end() if label else start, end))
    runs = [lambda s=start, e=end: _parse_run(state, sentences(text, s, e))
            for start, end in bounds]
    branches = [{"premise": premise, "items": nodes, "label": label}
                for premise, nodes, label in zip(premises, fork_state(state, runs), labels)]
    node = branch_node("依前提", None, branches)
    node["form"] = LABEL_FORM
    if None in premises:
        node["unparsed"] = unparsed(REASON_BRANCH_PREMISE)
    block["tree"]["items"] = [node]
    return block


def render_label(premise):
    """● 標籤的前提原子 → 標籤字面(含「：」)。"""
    if premise is None or premise.get("op") != DISPLAY_ATOM:
        raise NoTemplate("標籤無模板")
    return display_word(premise.get("face"), premise.get("position")) + LABEL_MARK


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
    節點的方式判不出就丟 NoTemplate。"""
    pieces = []
    for node in iter_tree(block["tree"]["items"]):
        if node.get("unparsed"):
            raise NoTemplate(f"段樹無模板:{node['unparsed']['reason']}")
        if node["node"] == "分歧":
            pieces.extend(_branch_headers(node, render_premise_text))
        elif is_reference(node):
            pieces.append(render_reference(node, render_object))
        elif node["node"] == "內嵌效果":
            binding = node.get("binding") or {}
            if "自己" not in binding:
                raise NoTemplate("內嵌效果無綁定")
            if node.get("header"):
                holder = _equip_holder([(seg, None) for seg in block["segments"]
                                        if seg["id"] == node["header"]])
                if holder is None or holder[1] != binding["自己"]:
                    raise NoTemplate("內嵌效果的裝備段無模板")
                continue
            if node.get("form") == REPLACED_CLOSE:
                if node.get("subject") not in REPLACED_SUBJECTS \
                        or {k: v for k, v in binding.items() if k != "自己"} != SIDE_SWAP:
                    raise NoTemplate("效果被換掉的引導句無模板")
                pieces.extend((node["subject"] + REPLACED_OPEN, REPLACED_CLOSE))
                continue
            by = node.get("by")
            if by is not None and by not in BY_DISPLAY:
                raise NoTemplate("依值分支的引導句無模板")
            pieces.append(render_object(binding["自己"], node.get("subject"))
                          + (f"は{by}によって" + EMBED_TAIL if by else EMBED_HEADER))
    return sorted(set(pieces), key=len, reverse=True)


def _branch_headers(node, render_premise_text):
    mode = node.get("mode")
    if mode == "依前提" and node.get("form") == LABEL_FORM:
        return [render_label(branch.get("premise")) for branch in node["branches"]]
    if mode == "依前提":
        out = []
        for branch in node["branches"]:
            if branch.get("premise") is None or len(branch["items"]) != 1 \
                    or branch["items"][0]["node"] != "分歧":
                raise NoTemplate("依前提的支無模板")
            inner = branch["items"][0]
            if inner.get("unparsed"):
                raise NoTemplate(f"段樹無模板:{inner['unparsed']['reason']}")
            out.append(render_premise_text(branch["premise"])
                       + _header_text(inner))
            out.extend(timepoint_glue(branch["premise"]))
        return out
    if node.get("form") is None and mode == "各自可以":
        return []   # 內嵌效果裡的 ● 列舉:引導句在內嵌效果節點上
    if node.get("header") and node.get("form") is None:
        return []   # 召喚條件的 ● 列舉:引導句是限制段,段自己比對(票 09)
    return [_header_text(node)]


def _header_text(node):
    form = node.get("form")
    expected = _HEADER_FORMS.get(form)
    if expected is None or expected != (node.get("mode"), node.get("chooser")):
        raise NoTemplate("分歧引導句無模板")
    return "以下の効果" + form


def render_premise_prefix(premise, render_zones, render_object):
    """依前提各支的前提字面(後面接引導句,所以帶讀點)。"""
    return render_premise(premise, render_zones,
                          render_object, followed=True)
