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

from attribute_atoms import is_param_atom, joiner, render_group, render_level
from premise import NoPremiseTemplate, render_premise, split_premise
from condition_atoms import render_atom
from segment_extract import (ACTION_PAST, ACTIVATION_REF, EXIST_WORDS,
                             FROM_PARTICLES, HEAD_CATEGORY, HEAD_SUBTYPE,
                             SIDE_WORDS, ZONE_WORDS, parse_from)
from segment_extract import _ACTION_REF_RE, _REF_RE, _TARGET_REF_RE  # 回指字面的句型,與抽取端同一把尺
from segment_fields import (REPLACEMENT_PREFIX, render_cause, render_modify,
                            render_timing, resolve_polarity)
from segment_tree import (NoTreeTemplate, embedded_bindings, render_premise_prefix,
                          tree_glue)
from synonyms import (ACTIVATION_SUFFIXES, COST_GLUE, MODIFY_ACTION, parse_predicates,
                      split_targeting)

REASON_NO_TEMPLATE = "無模板"
REASON_MISMATCH = "字面不符"
REASON_RESIDUE = "段外殘留"

# 簡單子句模板會寫的格;其餘格一有值就是「無模板」。
TEMPLATE_SLOTS = {"id", "kind", "actions", "lines", "agent", "recipient", "polarity",
                  "trigger", "span", "text", "predicate", "voice", "unparsed",
                  "optional", "cause", "premise", "timing", "duration", "modified",
                  "replaces", "amount"}
# 被代替段是改了類別的條件段,模板同條件段(帶觸發形)。
TEMPLATE_KINDS = ("條件", "代價", "效果", "被代替")
# 區塊裡不屬於任何段的固定接著詞:發動句語尾(含舊式「発動する事ができる」,長的在前)、
# 舊式代價句的「事で」、先後連接、區塊開頭的「また」。去掉標點後只能剩這些。
# 分歧的「●」也是接著詞;段樹引導句另由 tree_glue 扣掉(票 06)。
GLUE = ACTIVATION_SUFFIXES + (COST_GLUE, "その後", "また", "●")
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
    """修飾語原子 → 字面:字段(「X」/「X」と名のついた)、「X」以外の、カード名に「X」を含む、
    屬性比較(種族名、「レベル１」、「光属性」);票 07 的原子(記載、卡名範圍、位置、
    卡片子類型、引用)的模板在 condition_atoms.render_atom,先問它。"""
    rendered = render_atom(atom, names)
    if rendered is not None:
        return rendered
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
    level = render_level(atom)   # レベル１、レベル４以下、レベル５以上
    if level is not None:
        return level
    if op == "屬性比較" and atom.get("cmp") == "=":
        if atom["attr"] == "種族":
            return atom["value"]
        if atom["attr"] == "屬性":
            return atom["value"] + "属性"
        raise NoTemplate(f"屬性比較無模板:{atom['attr']}")
    if op == "解析不出":
        raise NoTemplate("物件條件無模板:解析不出")
    raise NoTemplate(f"物件條件無模板:{op}")


def _render_head(condition):
    """大類(與 魔法・罠 的或)、大類 且 子類型(チューナー)→ 頭名詞;不是頭名詞回 None。"""
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
        if (category.get("op") == "大類" and subtype.get("op") == "屬性比較"
                and subtype.get("attr") == "卡片子類型" and subtype.get("cmp") == "="):
            return _SUBTYPE_HEAD_TEXT.get((category["value"], subtype.get("value")))
    return None


def _render_modifiers(mods, names):
    """修飾語列表 → 字面:屬性比較之間與後面的「・」「の」照 attribute_atoms.joiner
    (魔法使い族・光属性、獣族・獣戦士族の炎属性、ドラゴン族の「ドラグニティ」)。"""
    out = []
    for i, atom in enumerate(mods):
        if not is_param_atom(atom):
            out.append(_render_atom(atom, names))
            continue
        text = render_group(atom) if atom.get("op") == "或" else _render_atom(atom, names)
        if text is None:
            raise NoTemplate("屬性比較無模板")
        out.append(text + joiner(atom, mods[i + 1] if i + 1 < len(mods) else None))
    return "".join(out)


def _render_condition(condition, names):
    """條件式 → 名詞短語:且 = 修飾語(照字面順序,相鄰的屬性比較以「・」連)+ 頭名詞(且 的末項);
    單獨的卡名 = 「X」。"""
    if condition is None:
        raise NoTemplate("物件條件無模板:空")
    head = _render_head(condition)
    if head:
        return head
    op = condition.get("op")
    if op == "卡名":
        return _quoted(condition, names)
    if op == "或" and all(a.get("op") == "卡名" for a in condition["args"]):
        return "または".join(_quoted(a, names) for a in condition["args"])
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
    if count.get("cmp") == "全部":
        return "全て"
    if count.get("cmp") not in ("=", "≤") or not count.get("unit"):
        raise NoTemplate("物件數量無模板")
    # 官方卡文的數字是全形,照它寫(正規化時兩邊都會折成半形,這裡只為報告好讀)。
    digits = str(count["value"]).translate(_TO_FULLWIDTH_DIGITS)
    return f"{digits}{count['unit']}{'まで' if count['cmp'] == '≤' else ''}"


def _head_of(obj):
    """回指時的頭名詞:條件式裡第一個大類(剩餘物件的條件帶「非」,不能整個條件式去拼)。"""
    return "モンスター" if _first_category(obj["condition"]) == "怪獸" else "カード"


def _first_category(condition):
    if not condition:
        return None
    if condition.get("op") == "大類":
        return condition["value"]
    if condition.get("op") == "且":
        for arg in condition["args"]:
            found = _first_category(arg)
            if found:
                return found
    return None


def _all_blocks(card):
    """區塊與內嵌效果的區塊(票 06)。"""
    stack = list(card["blocks"])
    while stack:
        block = stack.pop()
        yield block
        for node in _iter_nodes(block["tree"]["items"]):
            if node.get("node") == "內嵌效果" and node.get("block"):
                stack.append(node["block"])


def _iter_nodes(items):
    for node in items:
        yield node
        if node.get("node") == "分歧":
            for branch in node["branches"]:
                yield from _iter_nodes(branch["items"])


def _last_action_on(obj_id, seg, card):
    """同一區塊裡、這一段之前最後一個作用在該物件上的動作詞(動作回指「めくったカード」用)。"""
    block_id = seg["id"].split(".")[0]
    for block in _all_blocks(card):
        if block["id"] != block_id:
            continue
        found = None
        for other in block["segments"]:
            if other["id"] == seg["id"]:
                break
            if other["actions"] and any(l["object"] == obj_id for l in other["lines"]):
                found = other["actions"][-1]
        return found
    return None


def _render_object(obj, seg, card, names, line=None, with_count=True, self_id="o0"):
    """物件在這一段的字面:物件0(內嵌效果裡是綁定的物件)是このカード;本段首次出現的寫全名
    (條件+數量);回指的照對象線的回指字面(驗過句型);剩餘物件寫 残りの+頭名詞。
    助詞後的數量在對象線上,由呼叫端接在助詞後。`seg` 為 None 時是段樹引導句裡的物件,
    一律寫全名(票 06)。"""
    ref = line["ref"] if line else None
    if ref is not None:
        # 回指字面優先:「この効果で特殊召喚したモンスター」也可以指這張卡自己(票 06 的動作回指)。
        return _render_ref(ref, obj, seg, card)
    if obj["source"]["kind"] == "自己" or obj["id"] == self_id:
        return "このカード"
    if obj["unparsed"]:
        raise NoTemplate(f"物件無模板:{obj['unparsed']['reason']}")
    kind = obj["source"]["kind"]
    if kind == "剩餘":
        return "残りの" + _head_of(obj)
    if kind not in ("新建", "子集"):
        raise NoTemplate(f"物件來源無模板:{kind}")
    defined_here = seg is None
    if seg is not None:
        start, end = seg["span"]
        defined_here = (obj["span"] and obj["block"] == seg["id"].split(".")[0]
                        and start <= obj["span"][0] and obj["span"][1] <= end)
    if not defined_here:
        return "その" + _head_of(obj)
    text = _render_condition(obj["condition"], names)
    if with_count and obj["count"]:
        text += _render_count(obj["count"])
    return text


_POSITION_PARTICLES = FROM_PARTICLES + ("に", "へ")


def _targeted_earlier(obj_id, seg, card):
    """這一段之前,同一區塊裡有沒有一段以取對象字面(選択して/対象として)點名過該物件。"""
    block_id = seg["id"].split(".")[0]
    for block in _all_blocks(card):
        if block["id"] != block_id:
            continue
        for other in block["segments"]:
            if other["id"] == seg["id"]:
                return False
            prefix, _ = split_targeting(other["predicate"] or "")
            if prefix and any(l["object"] == obj_id and l["targeting"]
                              for l in other["lines"]):
                return True
    return False


def _render_ref(ref, obj, seg, card):
    """回指字面:その/それらの+頭名詞照字面;動作回指(「めくったカード」)的動詞必須是
    這一段之前最後一個作用在該物件上的動作詞的過去形;「選択したモンスター」必須指回
    先前被取對象的物件。"""
    if _REF_RE.match(ref):
        return ref
    if ref == ACTIVATION_REF:
        # 「その発動」指回本區塊先前被發動的那張卡(票 09)。
        if _last_action_on(obj["id"], seg, card) != "發動":
            raise NoTemplate("「その発動」回指的物件先前沒被發動")
        return ref
    if _TARGET_REF_RE.match(ref):
        if not _targeted_earlier(obj["id"], seg, card):
            raise NoTemplate("「選択した」回指的物件先前沒被取對象")
        return ref
    m = _ACTION_REF_RE.match(ref)
    if m and m.group("past") in ACTION_PAST.values():
        action = _last_action_on(obj["id"], seg, card)
        if ACTION_PAST.get(action) != m.group("past"):
            raise NoTemplate("動作回指與先前的動作不符")
        return ref
    raise NoTemplate(f"回指字面無模板:{ref}")


def _render_zone_text(pos, particle):
    """明寫的從/到:有含助詞的原文字面且與區域一致就照字面寫;否則由區域拼回、接上預設助詞。"""
    zones = pos["zones"]
    text = pos.get("text")
    if text:
        # 「自分フィールドの、」的讀點是字面的一部分,驗區域時先去掉。
        bare = text[:-1] if text.endswith("、") else text
        phrase = next((bare[:-len(p)] for p in _POSITION_PARTICLES
                       if bare.endswith(p)), None)
        if phrase is None or parse_from(phrase) != zones:
            raise NoTemplate("從/到的字面與區域不一致")
        return text
    return _render_zones(zones) + particle


def _render_zones(zones):
    """區域列表 → 字面(沒有原文字面時用):方明寫才加「自分の/相手の」,只有一個區域且是
    フィールド時不加「の」(「自分フィールド」「自分の手札・フィールド」「自分の墓地」是官方的
    寫法);明寫的方是整個列表共用的前綴,沒寫的(預設或沒有方)各區域可以不同
    (「手札・フィールド」:手牌預設我方、場上沒有方)。"""
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


def _render_from(lines):
    """所有對象線共用一個明寫的「從」才有字面 → (字面, 寫在物件前還是述語前);
    繼承、推得的不寫。"""
    written = [line["from"] for line in lines
               if line["from"] and line["from"]["source"] == "明寫"]
    if not written:
        return "", "名詞前"
    if len(written) != len(lines) or any(w != written[0] for w in written):
        raise NoTemplate("對象線的從不一致")
    return _render_zone_text(written[0], "から"), written[0].get("placement") or "名詞前"


def _render_to(lines, predicate_to):
    """明寫、不在述語裡的「到」(「デッキの一番下に」),可帶放置形式(「好きな順番で」)
    → (字面, 寫在物件前還是述語前):「自分フィールドにモンスターが特殊召喚された」的到在
    物件前(placement 名詞前),其餘在述語前。"""
    written = [line["to"] for line in lines
               if line["to"] and line["to"]["source"] == "明寫"]
    if not written or predicate_to:
        if any(w.get("form") for w in written):
            raise NoTemplate("到的形式無模板")
        # 到是推得的但形式明寫(「装備魔法カード扱いで、〜に装備できる」,票 06):只寫形式。
        forms = {line["to"].get("form") for line in lines if line["to"]}
        if len(forms) == 1 and None not in forms:
            return forms.pop(), "述語前"
        if len(forms) > 1:
            raise NoTemplate("對象線的到不一致")
        return "", "述語前"
    if len(written) != len(lines) or any(w != written[0] for w in written):
        raise NoTemplate("對象線的到不一致")
    return ((written[0].get("form") or "") + _render_zone_text(written[0], "に"),
            written[0].get("placement") or "述語前")


def _render_predicate(seg, marker):
    """述語字面必須能拆回段的動作詞、態、極性(多動作詞是て形串接;「Xは〜できる」的極性是可以,
    與抽取端同一把尺 resolve_polarity);開頭的取對象字面(「選択して」「対象として」)拆出來、
    單獨出現時是沒有動作詞的取對象宣告。回傳 (取對象字面或 None, 述語字面, 述語寫明的終點)。"""
    if not seg["predicate"]:
        raise NoTemplate("段無動作詞")
    prefix, rest = split_targeting(seg["predicate"])
    if not rest:
        if seg["actions"] or (seg["voice"], seg["polarity"], seg["optional"]) != (None, "做", None):
            raise NoTemplate("取對象宣告帶了動作詞")
        return prefix, "", None
    if not seg["actions"]:
        raise NoTemplate("段無動作詞")
    parsed, _ = parse_predicates(rest)
    if parsed is None or [p[0] for p in parsed] != seg["actions"]:
        raise NoTemplate("述語字面與動作詞、態、極性不一致")
    voices = {p[1] for p in parsed}
    voice = voices.pop() if len(voices) == 1 else "混合"
    polarity, optional = resolve_polarity(parsed, marker)
    if (voice, polarity, optional) != (seg["voice"], seg["polarity"], seg["optional"]):
        raise NoTemplate("述語字面與動作詞、態、極性不一致")
    return prefix, rest, next((p[3] for p in parsed if p[3]), None)


def _render_cause(cause):
    text = render_cause(cause)
    if text is None:
        raise NoTemplate(f"原因無模板:{cause.get('kind')}")
    return text


def _render_timing(timing):
    text = render_timing(timing)
    if text is None:
        raise NoTemplate(f"時機無模板:{timing.get('kind')}")
    return text


def _render_modify(seg, objects):
    """性質變更句:[提及][屬性]は[期間][值]になる;提及字面在對象線的 ref(物件0 是「このカードの」)。"""
    if len(seg["lines"]) != 1 or seg["actions"] != [MODIFY_ACTION] or not seg["modified"]:
        raise NoTemplate("性質變更段的格不齊")
    line = seg["lines"][0]
    obj = objects.get(line["object"])
    mention = line["ref"]
    if obj is None or (obj["source"]["kind"] == "自己") != (mention == "このカードの"):
        raise NoTemplate("性質變更段的提及與物件不符")
    text = render_modify(mention, seg["modified"], seg["duration"])
    if text is None:
        raise NoTemplate("被改的屬性無模板")
    return text


def _render_existence(seg, premise, card, objects):
    """存在前提(票 10 的形狀,帶容器 `in`):「(容器回指)の中に(子集全名)が(あった)」。"""
    if premise.get("op") != "存在" or seg["actions"] or seg["kind"] != "條件":
        raise NoTemplate(f"前提無模板:{premise.get('op')}")
    if seg["predicate"] not in EXIST_WORDS:
        raise NoTemplate("存在述語無模板")
    container = next((l for l in seg["lines"] if l["object"] == premise.get("in")), None)
    if container is None or premise.get("object") not in objects:
        raise NoTemplate("存在前提缺容器或子集")
    inner = objects[premise["object"]]
    names = {row["id"]: row for row in card["names"]}
    return (_render_object(objects[container["object"]], seg, card, names, container)
            + "の中に" + _render_object(inner, seg, card, names, with_count=False)
            + "が" + seg["predicate"])


def _render_premise_zones(zones, text):
    """前提的區域:帶原文字面(舊式「フィールド上」)時先驗過與區域一致再照字面,否則照方的來源還原。"""
    if text is None:
        return _render_zones(zones)
    if parse_from(text) != zones:
        raise NoTemplate("前提的區域字面與區域不一致")
    return text


def _render_leading_premise(leading, seg, card, objects, names, followed, self_id="o0"):
    """句首的前提(位置、存在、遊戲狀態)→ 字面;區域與物件的字面規則借這裡的。"""
    try:
        return render_premise(
            leading, _render_premise_zones,
            lambda obj_id: _render_object(objects[obj_id], seg, card, names,
                                          self_id=self_id),
            followed=followed)
    except NoPremiseTemplate as e:
        raise NoTemplate(str(e)) from None


def _render_recipient(recipient, seg, card, objects):
    """受方:我方/對手寫「自分に/相手に」;物件的回指(裝備的對象,票 06)照回指字面。"""
    if isinstance(recipient, dict):
        obj = objects.get(recipient.get("object"))
        if obj is None or not recipient.get("ref"):
            raise NoTemplate("受方的物件找不到")
        return _render_ref(recipient["ref"], obj, seg, card) + "に"
    if recipient not in _SIDE_TEXT:
        raise NoTemplate(f"受方無模板:{recipient}")
    return _SIDE_TEXT[recipient] + "に"


def render_segment(seg, card, self_id="o0"):
    """簡單子句模板:[代わりに][前提][誰が][到に][從から|の|に存在する][物件][助詞][數量][取對象][原因][時機][形式][從から][到に][受方に]述語[觸發形]
    (物件前的「到に」只在助詞是「が」時;「從」只在物件前或述語前其中一處,照 placement;
    「代わりに」在做代替的段前;時機只寫有字面的延遲;被代替段同條件段帶觸發形);
    存在前提、性質變更句另有模板;只有前提的條件段寫前提。`self_id` 是「このカード」指的物件
    (內嵌效果裡是綁定的物件,票 06)。
    回傳日文;寫不出就丟 NoTemplate。
    取對象線只有兩種寫得出:這一段的述語帶取對象字面(每條線都標),或這一條線指回
    本區塊先前被取對象字面點名的物件(その/選択したモンスター)。"""
    if seg["unparsed"]:
        raise NoTemplate(f"段未解析:{seg['unparsed']['reason']}")
    if seg["kind"] not in TEMPLATE_KINDS:
        raise NoTemplate(f"段類別無模板:{seg['kind']}")
    for slot, value in seg.items():
        if slot not in TEMPLATE_SLOTS and value not in (None, [], {}, False):
            raise NoTemplate(f"格 {slot} 無模板")
    objects = {o["id"]: o for o in card["objects"]}
    names = {row["id"]: row for row in card["names"]}
    leading, existence = split_premise(seg["premise"])
    premise_only = (seg["kind"] == "條件" and leading is not None
                    and existence is None and not seg["actions"] and not seg["lines"])
    prefix = ""
    if leading is not None:
        prefix = _render_leading_premise(leading, seg, card, objects, names,
                                         followed=not premise_only, self_id=self_id)
    if premise_only:
        return prefix
    if not seg["lines"] and not seg["amount"]:
        raise NoTemplate("段無對象線")
    if seg["replaces"]:
        prefix += REPLACEMENT_PREFIX   # 做代替的段:「代わりに」在段的範圍內
    if existence is not None:
        text = _render_existence(seg, existence, card, objects)
    elif seg["actions"] == [MODIFY_ACTION]:
        text = _render_modify(seg, objects)
    else:
        parts = []
        if seg["agent"] is not None:
            if seg["agent"] not in _SIDE_TEXT:
                raise NoTemplate(f"誰無模板:{seg['agent']}")
            # 誰的助詞:條件子句是「相手が〜した時」,效果句是「自分は〜する」(全庫 66:0、31:1)。
            parts.append(_SIDE_TEXT[seg["agent"]] + (
                "が" if seg["kind"] in ("條件", "被代替") else "は"))
        markers = {line["marker"] or "を" for line in seg["lines"]} or {"を"}
        if len(markers) != 1:
            raise NoTemplate("對象線的助詞或數量不一致")
        marker = markers.pop()
        targeting_text, predicate, predicate_to = _render_predicate(seg, marker)
        words, counts = [], set()
        if seg["amount"]:
            # 數量格(「１０００LPを払って」):段無物件,數量當受詞寫。
            if seg["lines"] or seg["amount"].get("unit") != "LP" \
                    or not isinstance(seg["amount"].get("value"), int):
                raise NoTemplate("數量無模板")
            words.append(str(seg["amount"]["value"]).translate(_TO_FULLWIDTH_DIGITS) + "LP")
            counts.add("")
        for line in seg["lines"]:
            if targeting_text and not line["targeting"]:
                raise NoTemplate("取對象字面下有線沒標取對象")
            if line["targeting"] and not targeting_text and not (
                    line["ref"] and _targeted_earlier(line["object"], seg, card)):
                raise NoTemplate("取對象線無模板")
            if line["role"] not in ("受事", "被召喚"):
                raise NoTemplate(f"角色無模板:{line['role']}")
            words.append(_render_object(objects[line["object"]], seg, card, names, line,
                                        self_id=self_id))
            counts.add(_render_count(line["count"]))
        if len(counts) != 1:
            raise NoTemplate("對象線的助詞或數量不一致")
        to_text, to_placement = _render_to(seg["lines"], predicate_to)
        from_text, from_placement = _render_from(seg["lines"])
        # 物件前的到(自分フィールドにモンスターが特殊召喚された)照 placement 放回。
        if to_placement == "名詞前":
            parts.append(to_text)
        if from_placement == "名詞前":
            parts.append(from_text)
        parts.append("と".join(words) + marker)
        parts.append(counts.pop())
        parts.append(targeting_text or "")
        parts.append(_render_cause(seg["cause"]))
        parts.append(_render_timing(seg["timing"]))
        if from_placement == "述語前":
            parts.append(from_text)
        if to_placement == "述語前":
            parts.append(to_text)
        if seg["recipient"] is not None:
            parts.append(_render_recipient(seg["recipient"], seg, card, objects))
        parts.append(predicate)
        text = "".join(parts)
    if seg["kind"] in ("條件", "被代替"):
        if not seg["trigger"]:
            raise NoTemplate("條件段無觸發形")
        text += seg["trigger"]
    return prefix + text


# ── 檢查 ─────────────────────────────────────────────────────
def _failure(card, block, seg_id, reason, detail, rendered=None, original=None):
    return {"card": card["id"], "name_ja": card["name_ja"], "block": block["id"],
            "segment": seg_id, "reason": reason, "detail": detail,
            "rendered": rendered, "original": original}


def _tree_glue(block, card, names):
    """段樹引導句的字面(分歧、內嵌效果;票 06),去掉標點後供殘留比對;節點無模板就丟 NoTemplate。"""
    objects = {o["id"]: o for o in card["objects"]}

    def render_object(obj_id, ref):
        if ref is None:
            return _render_object(objects[obj_id], None, card, names)
        # 引導句主語的回指(その/動作回指):字面照句型驗過就照寫,動作與先前的段對不對在段上驗。
        m = _ACTION_REF_RE.match(ref)
        if _REF_RE.match(ref) or (m and m.group("past") in ACTION_PAST.values()):
            return ref
        raise NoTemplate(f"回指字面無模板:{ref}")

    def render_premise_text(premise):
        return render_premise_prefix(premise, _render_premise_zones, render_object)

    try:
        return [_PUNCT_RE.sub("", piece)
                for piece in tree_glue(block, render_premise_text, render_object)]
    except NoTreeTemplate as e:
        raise NoTemplate(str(e)) from None


def _residue(block, glue, glue_failed=False):
    """區塊原文扣掉各段範圍、內嵌效果的區塊範圍與標點後剩下的片段;不是段樹引導句(`glue`)
    也不是固定接著詞的就是殘留。引導句寫不出字面(`glue_failed`,已列無模板)時扣掉節點的
    原文範圍,不重複列成殘留;寫得出時靠字面比對,引導句與原文不符就會留下來。"""
    text = block["text"]
    cut = [(s["span"][0], s["span"][1], s["kind"]) for s in block["segments"]]
    for node in _iter_nodes(block["tree"]["items"]):
        if node.get("node") == "內嵌效果" and node.get("block"):
            inner = node["block"]
            cut.append((inner["span"][0] - block["span"][0],
                        inner["span"][1] - block["span"][0], None))
        if glue_failed and node.get("span"):
            cut.append((node["span"][0], node["span"][1], None))
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
        if kind in ("條件", "被代替") and rest.startswith("に"):
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
    for block in _all_blocks(card):
        self_id = (bindings.get(block["id"]) or {}).get("自己", "o0")
        for seg in block["segments"]:
            try:
                rendered = render_segment(seg, card, self_id=self_id)
            except NoTemplate as e:
                failures.append(_failure(card, block, seg["id"],
                                         REASON_NO_TEMPLATE, str(e)))
                continue
            if normalise(rendered) != normalise(seg["text"]):
                failures.append(_failure(card, block, seg["id"], REASON_MISMATCH,
                                         None, rendered, seg["text"]))
        glue, glue_failed = [], False
        try:
            glue = _tree_glue(block, card, names)
        except NoTemplate as e:
            failures.append(_failure(card, block, None, REASON_NO_TEMPLATE, str(e)))
            glue_failed = True
        for piece in _residue(block, glue, glue_failed):
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
        segments += sum(len(block["segments"]) for block in _all_blocks(card))
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
