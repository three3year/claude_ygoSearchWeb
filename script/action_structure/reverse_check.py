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
- 未結構化:重複到停為止的那一句(段標 `unstructured`),不算通過也不算不通過,另列一類。

模板在哪:`render_segment` 照兩張分流表(`WHOLE_TEMPLATES`、`CLAUSE_TEMPLATES`)把段交給各句型模組的
模板(與該句型的抽取放在同一個模組);物件、區域、數量、誰、原因的字面各在 `object_render`、
`zone_phrase`、`quantity`、`agent_phrase`、`cause_phrase`。這裡只留整段的框架、段外殘留與報告。

正規化只做空白與全半形:自己寫,不用 NFKC(NFKC 會把 ① 折成 1,docs/data_sources.md)。
"""
import re
from typing import Callable, NamedTuple

import battle_clause
import clause_front
import damage
import draw
import existence_clause
import material_line
import material_summon
import simple_clause
import stat_modify
from archetype_table import fold_width
from block_split import LABEL_WIDTH
from block_state import ACTION_REF_RE, REF_RE
from object_render import render_object
from premise import render_premise, split_premise, timepoint_glue
from report_common import card_order, safe_label
from segment_extract import BATTLE_TIMING_REF, PREMISE_DONE
from segment_fields import REPLACEMENT_PREFIX, is_clause_duration, split_duration
from segment_history import all_blocks
from segment_tree import embedded_bindings, render_premise_prefix, tree_glue
from structure_shape import BATTLE_TRIGGERS, NoTemplate, iter_nodes, swap_sides
from synonyms import ACTION_PAST, ACTIVATION_SUFFIXES, COST_GLUE, MODIFY_ACTION
from treat_as import render_treat_as_segment
from zone_phrase import render_premise_zones

REASON_NO_TEMPLATE = "無模板"
REASON_MISMATCH = "字面不符"
REASON_RESIDUE = "段外殘留"
# 重複到停為止的段(spec 故事 28):不算通過也不算不通過,報告另列一類、detail 固定。
REASON_UNSTRUCTURED = "未結構化"
DETAIL_REPEAT = "重複到停為止"

# 簡單子句模板會寫的格;其餘格一有值就是「無模板」。
TEMPLATE_SLOTS = {"id", "kind", "actions", "lines", "agent", "recipient", "polarity",
                  "trigger", "span", "text", "predicate", "voice", "unparsed",
                  "optional", "cause", "premise", "timing", "duration", "modified",
                  "replaces", "amount", "times", "per_turn", "derived_from"}
# 被代替段是改了類別的條件段,模板同條件段(帶觸發形);召喚手續、限制(票 09)是召喚條件區塊裡
# 改了類別的條件/效果段,模板同簡單子句(有觸發形就寫)。
TEMPLATE_KINDS = ("條件", "代價", "效果", "被代替", "召喚手續", "限制", "修飾")
# 區塊裡不屬於任何段的固定接著詞:發動句語尾(含舊式「発動する事ができる」,長的在前)、
# 舊式代價句的「事で」、先後連接、區塊開頭的「また」。去掉標點後只能剩這些。
# 分歧的「●」也是接著詞;段樹引導句另由 tree_glue 扣掉(票 06)。
GLUE = ACTIVATION_SUFFIXES + (COST_GLUE, "その後", "さらに", "また", "●")
_GLUE_RE = re.compile("|".join(GLUE))
_PUNCT_RE = re.compile("[。、\n ]")
_WS_RE = re.compile(r"[\s　]+")


def normalise(text):
    """去空白(含全形空白)、全形英數符號折成半形(與名稱比對同一張折疊表 `fold_width`);
    ①②③ 等編號字元保持原樣。"""
    return fold_width(_WS_RE.sub("", text))


def _render_leading_premise(leading, seg, card, objects, names, followed, self_id="o0"):
    """句首的前提(位置、存在、遊戲狀態)→ 字面;區域與物件的字面規則借這裡的。"""
    return render_premise(
        leading, render_premise_zones,
        lambda obj_id, ref: render_object(objects[obj_id], seg, card, names,
                                          {"ref": ref} if ref else None,
                                          self_id=self_id),
        followed=followed)


def _is_segment_done(premise):
    """前提 段已執行(戰鬥時點的「その」,指回同一句前一個條件段)。"""
    return (premise is not None and set(premise) == {"op", "segment"}
            and premise["op"] == PREMISE_DONE and bool(premise["segment"]))


# 句中期間(`split_duration` 的後半:有字面、不在句首的期間)各模板的去向。
INNER_OWN = "模板自己寫"            # 性質變更句的「〜ターン終了時まで〜になる」、傷害值變更的「このターン」
INNER_BEFORE_PREDICATE = "述語前"   # 簡單子句的「エンドフェイズまで除外する」;只收 `is_clause_duration` 的字面
INNER_NONE = "不收"                 # 這個句型沒有寫期間的位置:段有句中期間就是無模板


class TemplateInput(NamedTuple):
    """模板拿得到的東西:段、卡片結構、物件表與名稱表(id → 列)、「このカード」指的物件;
    子句模板另有票 10 的存在前提原子與句中期間。"""
    seg: dict
    card: dict
    objects: dict
    names: dict
    self_id: str
    existence: dict | None = None
    inner_duration: dict | None = None


class SegmentTemplate(NamedTuple):
    """分流表的一列:模板名、這一段歸不歸它(`applies`)、怎麼寫(`render`)、句中期間的去向。"""
    name: str
    applies: Callable[[TemplateInput], bool]
    render: Callable[[TemplateInput], str]
    inner_duration: str = INNER_NONE


# 整段模板:整段的字面由模板自己寫,不套句首期間、前提、「代わりに」與觸發形。依序試。
WHOLE_TEMPLATES = (
    SegmentTemplate("衍生的性質變更", lambda t: t.seg["derived_from"] is not None,
                    lambda t: stat_modify.render_derived(t.seg)),
    SegmentTemplate("修飾", lambda t: t.seg["kind"] == "修飾",
                    lambda t: render_treat_as_segment(t.seg, t.names, t.objects, t.self_id)),
    SegmentTemplate("素材行",
                    lambda t: bool(t.seg["lines"]) and not t.seg["actions"]
                    and all(line["role"] == "素材" for line in t.seg["lines"]),
                    lambda t: material_line.render_line(t.seg, t.card, t.names, t.objects,
                                                        t.self_id)),
)
# 子句模板:寫段的子句本體,前後由 `render_segment` 套上句首期間、前提、「代わりに」與觸發形。
# 依序試、第一個適用的負責寫(最後一列永遠適用);加一種句型的模板 = 在它前面加一列。
# 存在前提與抽牌的模板不吃 `self_id`:裡面的「このカード」一律照物件0 寫。
SIMPLE_TEMPLATE = "簡單子句"
CLAUSE_TEMPLATES = (
    SegmentTemplate("存在前提", lambda t: t.existence is not None,
                    lambda t: existence_clause.render_clause(t.seg, t.existence, t.card,
                                                             t.objects)),
    SegmentTemplate("傷害值變更",
                    lambda t: damage.is_damage_segment(t.seg) and t.seg["actions"] == [MODIFY_ACTION],
                    lambda t: damage.render_clause(t.seg, t.card, t.objects, t.names, t.self_id,
                                                   t.inner_duration),
                    INNER_OWN),
    SegmentTemplate("傷害與回復", lambda t: damage.is_damage_segment(t.seg),
                    lambda t: damage.render_clause(t.seg, t.card, t.objects, t.names, t.self_id,
                                                   t.inner_duration)),
    SegmentTemplate("性質變更", lambda t: t.seg["actions"] == [MODIFY_ACTION],
                    lambda t: stat_modify.render_clause(t.seg, t.card, t.objects, t.names,
                                                        t.self_id, t.inner_duration),
                    INNER_OWN),
    SegmentTemplate("戰鬥", lambda t: battle_clause.is_battle_segment(t.seg),
                    lambda t: battle_clause.render_clause(t.seg, t.card, t.objects, t.names,
                                                          t.self_id)),
    SegmentTemplate("抽牌", lambda t: draw.is_draw_segment(t.seg, t.objects),
                    lambda t: draw.render_clause(t.seg, t.card, t.objects, t.names)),
    SegmentTemplate("召喚段帶素材線", lambda t: material_summon.is_material_summon(t.seg),
                    lambda t: material_summon.render_clause(t.seg, t.card, t.objects, t.names,
                                                            t.self_id, t.inner_duration),
                    INNER_BEFORE_PREDICATE),
    SegmentTemplate(SIMPLE_TEMPLATE, lambda t: True,
                    lambda t: simple_clause.render_clause(t.seg, t.card, t.objects, t.names,
                                                          t.self_id, t.inner_duration),
                    INNER_BEFORE_PREDICATE),
)


def _first_template(templates, t):
    return next((template for template in templates if template.applies(t)), None)


def render_segment(seg, card, self_id="o0"):
    """一段 → 日文;寫不出就丟 NoTemplate。整段模板(`WHOLE_TEMPLATES`)適用的直接由它寫;其餘是
    [句首期間][前提][代わりに]子句本體[觸發形]:子句本體由 `CLAUSE_TEMPLATES` 第一個適用的模板寫
    (「代わりに」在做代替的段前;被代替段同條件段帶觸發形;只有前提的條件段只寫前提)。
    句中期間照模板那一列的去向分流:模板自己寫的原樣交給它,述語前的要是 `is_clause_duration` 的字面,
    不收的有句中期間就是無模板。`self_id` 是「このカード」指的物件(內嵌效果裡是綁定的物件,票 06)。"""
    if seg["unparsed"]:
        raise NoTemplate(f"段解析不出:{seg['unparsed']['reason']}")
    if seg["kind"] not in TEMPLATE_KINDS:
        raise NoTemplate(f"段類別無模板:{seg['kind']}")
    for slot, value in seg.items():
        if slot not in TEMPLATE_SLOTS and value not in (None, [], {}, False):
            raise NoTemplate(f"格 {slot} 無模板")
    objects = {o["id"]: o for o in card["objects"]}
    names = {row["id"]: row for row in card["names"]}
    t = TemplateInput(seg, card, objects, names, self_id)
    whole = _first_template(WHOLE_TEMPLATES, t)
    if whole is not None:
        return whole.render(t)
    leading, existence = split_premise(seg["premise"])
    premise_only = (seg["kind"] == "條件" and leading is not None
                    and existence is None and not seg["actions"] and not seg["lines"])
    # 物件切點切出來的期間(「ダメージステップ終了時まで」):寫在子句前的接在前提之後、子句本體之前;
    # 寫在誰/主語後的只有簡單子句模板寫得出(它自己讀段的期間)。
    front_period = ""
    placement = clause_front.front_duration(seg["duration"])
    if placement:
        prefix, inner_duration = "", None
        if placement == clause_front.PLACEMENT_FRONT:
            front_period = clause_front.render_front_duration(seg["duration"])
    else:
        prefix, inner_duration = split_duration(seg["duration"])
    t = t._replace(existence=existence, inner_duration=inner_duration)
    template = _first_template(CLAUSE_TEMPLATES, t)
    if placement == clause_front.PLACEMENT_AFTER_SUBJECT and template.name != SIMPLE_TEMPLATE:
        raise NoTemplate("期間無模板:主語後")
    if (inner_duration is not None and template.inner_duration != INNER_OWN
            and not is_clause_duration(inner_duration)):
        raise NoTemplate("期間無模板:句中")
    if (seg["kind"] == "條件" and seg["trigger"] in BATTLE_TRIGGERS
            and not seg["actions"] and not seg["lines"]):
        if _is_segment_done(seg["premise"]):
            return prefix + BATTLE_TIMING_REF + seg["trigger"]
        if leading is not None:
            prefix += _render_leading_premise(leading, seg, card, objects, names,
                                              followed=True, self_id=self_id)
        return prefix + seg["trigger"]
    if leading is not None:
        prefix += _render_leading_premise(leading, seg, card, objects, names,
                                          followed=not premise_only, self_id=self_id)
    if premise_only:
        return prefix
    prefix += front_period
    if not seg["lines"] and not seg["amount"] and not damage.is_damage_segment(seg):
        raise NoTemplate("段無對象線")
    if seg["replaces"]:
        prefix += REPLACEMENT_PREFIX   # 做代替的段:「代わりに」在段的範圍內
    if inner_duration is not None and template.inner_duration == INNER_NONE:
        raise NoTemplate("期間無模板:句中")
    text = template.render(t)
    if seg["kind"] in ("條件", "被代替") and not seg["trigger"]:
        raise NoTemplate("條件段無觸發形")
    if seg["trigger"]:
        text += seg["trigger"]   # 召喚手續的「〜した場合」也帶觸發形(票 09)
    return prefix + text


def _failure(card, block, seg_id, reason, detail, rendered=None, original=None):
    return {"card": card["id"], "name_ja": card["name_ja"], "block": block["id"],
            "segment": seg_id, "reason": reason, "detail": detail,
            "rendered": rendered, "original": original}


def _tree_glue(block, card, names):
    """段樹引導句的字面(分歧、內嵌效果;票 06),去掉標點後供殘留比對;節點無模板就丟 NoTemplate。"""
    objects = {o["id"]: o for o in card["objects"]}

    def render_tree_object(obj_id, ref):
        if ref is None:
            return render_object(objects[obj_id], None, card, names)
        # 引導句主語的回指(その/動作回指):字面照句型驗過就照寫,動作與先前的段對不對在段上驗。
        m = ACTION_REF_RE.match(ref)
        if REF_RE.match(ref) or (m and m.group("past") in ACTION_PAST.values()):
            return ref
        raise NoTemplate(f"回指字面無模板:{ref}")

    def render_premise_text(premise):
        return render_premise_prefix(premise, render_premise_zones, render_tree_object)

    return [_PUNCT_RE.sub("", piece)
            for piece in tree_glue(block, render_premise_text, render_tree_object)]


def _timepoint_glue(block):
    """段的前提裡時點列舉前面各支的字面(「の〈階段〉及び、」,在段外),去掉標點後供殘留比對。
    前提無模板的段自己已列無模板,這裡略過。"""
    pieces = []
    for seg in block["segments"]:
        try:
            pieces.extend(_PUNCT_RE.sub("", piece) for piece in timepoint_glue(seg["premise"]))
        except NoTemplate:
            continue
    return pieces


def _holes(block, card):
    """區塊裡不記的字面(句中的次數限制,票 09)的範圍,相對於區塊原文:段的比對與殘留都扣掉它。"""
    start, end = block["span"]
    return [(o["span"][0] - start, o["span"][1] - start) for o in card["omitted"]
            if o["source"] == block["source"] and start <= o["span"][0] and o["span"][1] <= end]


def _without_holes(text, span, holes):
    """段的原文扣掉落在它範圍內的不記字面。"""
    start, _ = span
    out, pos = [], 0
    for h_start, h_end in sorted(holes):
        a, b = h_start - start, h_end - start
        if a < 0 or b > len(text):
            continue
        out.append(text[pos:a])
        pos = b
    out.append(text[pos:])
    return "".join(out)


def _residue(block, glue, glue_failed=False, holes=()):
    """區塊原文扣掉各段範圍、內嵌效果的區塊範圍、不記的字面(`holes`)與標點後剩下的片段;不是
    段樹引導句(`glue`)也不是固定接著詞的就是殘留。引導句寫不出字面(`glue_failed`,已列無模板)
    時扣掉節點的原文範圍,不重複列成殘留;寫得出時靠字面比對,引導句與原文不符就會留下來。"""
    text = block["text"]
    cut = [(s["span"][0], s["span"][1], bool(s["trigger"]) or s["kind"] in ("條件", "被代替"))
           for s in block["segments"]]
    cut.extend((a, b, False) for a, b in holes)
    for node in iter_nodes(block["tree"]["items"]):
        if node.get("node") == "內嵌效果" and node.get("block"):
            inner = node["block"]
            cut.append((inner["span"][0] - block["span"][0],
                        inner["span"][1] - block["span"][0], None))
        if glue_failed and node.get("span"):
            cut.append((node["span"][0], node["span"][1], None))
        if glue_failed and node.get("node") == "分歧":
            cut.extend((b["label"][0], b["label"][1], None) for b in node["branches"]
                       if b.get("label"))
    if block["label"]:
        cut.append((0, LABEL_WIDTH, False))   # 「①：」不是任何段的字
    cut.sort()
    pieces, pos, after = [], 0, False
    for start, end, triggered in cut:
        if start > pos:
            pieces.append((after, text[pos:start]))
        pos, after = max(pos, end), triggered
    if pos < len(text):
        pieces.append((after, text[pos:]))
    residue = []
    for triggered, piece in pieces:
        rest = _PUNCT_RE.sub("", piece)
        # 帶觸發形的段(條件段、召喚手續的「〜した場合」)範圍到觸發形為止,「場合に」「時に」的
        # 「に」留在段外(segment_extract 的 _TRIGGER_RE),只有緊接在它後面的「に」算接著詞。
        if triggered and rest.startswith("に"):
            rest = rest[1:]
        for header in glue:
            rest = rest.replace(header, "")
        if _GLUE_RE.sub("", rest):
            residue.append(piece)
    return residue


def check_card(card):
    """一張卡的不通過清單;空清單 = 整張通過。無官方日文的卡沒有段,清單也是空的。
    內嵌效果的區塊也各自檢查,段裡的「このカード」是綁定的物件。"""
    failures = []
    bindings = embedded_bindings(card)
    names = {row["id"]: row for row in card["names"]}
    for block in all_blocks(card):
        binding = bindings.get(block["id"]) or {}
        self_id = binding.get("自己", "o0")
        holes = _holes(block, card)
        view = card
        if binding.get("我方") == "對手":
            view = {**card, "objects": [swap_sides(o) if o["block"] == block["id"] else o
                                        for o in card["objects"]]}
        for seg in block["segments"]:
            if view is not card:
                seg = swap_sides(seg)
            if seg["unstructured"]:
                # 重複到停為止:不算通過也不算字面不符,另列一類(spec 故事 28)。
                failures.append(_failure(card, block, seg["id"], REASON_UNSTRUCTURED,
                                         DETAIL_REPEAT, None, seg["text"]))
                continue
            try:
                rendered = render_segment(seg, view, self_id=self_id)
            except NoTemplate as e:
                failures.append(_failure(card, block, seg["id"],
                                         REASON_NO_TEMPLATE, str(e)))
                continue
            original = _without_holes(seg["text"], seg["span"], holes)
            if normalise(rendered) != normalise(original):
                failures.append(_failure(card, block, seg["id"], REASON_MISMATCH,
                                         None, rendered, seg["text"]))
        glue, glue_failed = [], False
        try:
            glue = _tree_glue(block, card, names)
        except NoTemplate as e:
            failures.append(_failure(card, block, None, REASON_NO_TEMPLATE, str(e)))
            glue_failed = True
        glue = glue + _timepoint_glue(block)
        for piece in _residue(block, glue, glue_failed, holes):
            failures.append(_failure(card, block, None, REASON_RESIDUE,
                                     piece.strip("。、\n ")))
    return failures


def check_structures(structures):
    """全庫 → 報告資料:段數、通過、不通過、無官方日文張數與全部不通過筆。"""
    segments = 0
    no_text = 0
    failures = []
    for card in sorted(structures, key=lambda c: card_order(c["id"])):
        if card["unparsed"]:
            no_text += 1
            continue
        segments += sum(len(block["segments"]) for block in all_blocks(card))
        failures.extend(check_card(card))
    unstructured = sum(1 for f in failures if f["reason"] == REASON_UNSTRUCTURED)
    failed_segments = sum(1 for f in failures
                          if f["segment"] and f["reason"] != REASON_UNSTRUCTURED)
    residue_blocks = len({(f["card"], f["block"]) for f in failures
                          if f["reason"] == REASON_RESIDUE})
    return {"cards": len(structures), "no_official_text": no_text,
            "segments": segments, "passed": segments - failed_segments - unstructured,
            "failed": failed_segments, "unstructured": unstructured,
            "residue_blocks": residue_blocks, "failures": failures}


def _group(failures, key):
    groups = {}
    for f in failures:
        groups.setdefault(key(f), []).append(f)
    return groups


def _count_line(title, items, unit):
    cards = sorted({f["card"] for f in items}, key=card_order)
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
    details = _group(items, lambda f: safe_label(f["detail"]))
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
        "沒有模板的句型記「無模板」算不通過;重複到停為止的段記「未結構化」,通過與不通過都不計。"
        "判法在 script/action_structure/reverse_check.py。",
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
        f"| 未結構化(不計) | {report['unstructured']} |",
        f"| 有段外殘留的區塊 | {report['residue_blocks']} |",
        "",
        "## 不通過",
        "",
    ]
    by_reason = _group(report["failures"], lambda f: f["reason"])
    for reason in (REASON_NO_TEMPLATE, REASON_MISMATCH, REASON_RESIDUE, REASON_UNSTRUCTURED):
        if reason in by_reason:
            lines.extend(_reason_section(reason, by_reason[reason]))
    if not report["failures"]:
        lines.append("全部通過。")
        lines.append("")
    return "\n".join(lines)
