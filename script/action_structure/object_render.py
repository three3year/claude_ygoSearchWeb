"""物件的句型模板:物件在某一段的字面(`render_object`)。

此卡寫「このカード」;本段首次出現的寫全名(條件式 → 名詞短語在 `noun_phrase.render_condition`,
加數量);回指照對象線的回指字面(`render_ref`,驗過與先前的段相符);超量素材、計數器另有寫法。
帶狀態的此卡(母體是此卡的子集,m3 票 05)寫「〈狀態〉このカード」;帶修飾語的回指(「その相手モンスター」)
照字面,修飾語要是 `anaphora.restating_atoms` 認得的重述。
抽取端是 `block_state.BlockState.object_at`。
"""

from anaphora import SELF_TAIL, restated_reference
from block_state import (ACTION_REF_RE, ACTIVATION_REF, MATERIAL_WORDS, OBJECT_COUNTER,
                         OBJECT_MATERIAL, REF_RE, TARGET_REF_RE, xyz_monster_condition)
from noun_phrase import render_condition, render_modifiers
from quantity import render_count
from segment_history import last_action_on, targeted_earlier
from structure_shape import NoTemplate
from synonyms import ACTION_PAST


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


def render_object(obj, seg, card, names, line=None, with_count=True, self_id="o0"):
    """物件在這一段的字面:物件0(內嵌效果裡是綁定的物件)是このカード;本段首次出現的寫全名
    (條件+數量);回指的照對象線的回指字面(驗過句型);剩餘物件寫 残りの+頭名詞。
    助詞後的數量在對象線上,由呼叫端接在助詞後。`seg` 為 None 時是段樹引導句裡的物件,
    一律寫全名(票 06)。"""
    ref = line["ref"] if line else None
    if ref is not None:
        # 回指字面優先:「この効果で特殊召喚したモンスター」也可以指這張卡自己(票 06 的動作回指)。
        return render_ref(ref, obj, seg, card)
    if obj["source"]["kind"] == "自己" or obj["id"] == self_id:
        return "このカード"
    if obj["unparsed"]:
        raise NoTemplate(f"物件無模板:{obj['unparsed']['reason']}")
    if obj["kind"] in (OBJECT_MATERIAL, OBJECT_COUNTER):
        return _render_detach_object(obj, seg, card, names, self_id)
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
    if kind == "子集" and obj["source"].get("of") == self_id:
        # 帶狀態的此卡(m3 票 05):〈狀態〉このカード;每次提及各建一個,只在提到它的那一段寫得出。
        if not defined_here or obj["count"]:
            raise NoTemplate("帶狀態的此卡無模板")
        return render_modifiers(obj["condition"], names) + SELF_TAIL
    if not defined_here:
        return "その" + _head_of(obj)
    text = render_condition(obj["condition"], names)
    if with_count and obj["count"]:
        text += render_count(obj["count"])
    return text


def _render_detach_object(obj, seg, card, names, self_id):
    """超量素材、計數器:[所屬物件の]X素材|種類名。所屬物件照一般物件寫(回指字面在
    `of_ref`);隱含的所屬卡(超量怪獸、沒有字面)不寫,它的位置由對象線的從寫出。
    超量素材的名詞取 X素材/エクシーズ素材 閉集裡物件字面結尾的那個。"""
    if (obj["source"]["kind"] != "新建" or seg is None or not obj["span"]
            or obj["block"] != seg["id"].split(".")[0]
            or not (seg["span"][0] <= obj["span"][0] and obj["span"][1] <= seg["span"][1])):
        raise NoTemplate("去除對象無模板")
    if obj["kind"] == OBJECT_MATERIAL and obj["condition"] is not None:
        return _render_held_material(obj, seg, card, names, self_id)
    if obj["condition"] is not None or obj["count"]:
        raise NoTemplate("去除對象無模板")
    if obj["kind"] == OBJECT_COUNTER:
        word = obj.get("counter") or ""
        if not word.endswith("カウンター"):
            raise NoTemplate("計數器種類無模板")
    else:
        word = next((w for w in MATERIAL_WORDS if (obj["text"] or "").endswith(w)), None)
        if word is None:
            raise NoTemplate("超量素材無模板")
    owner_id = obj.get("of")
    if owner_id is None:
        if obj["kind"] == OBJECT_MATERIAL:
            raise NoTemplate("超量素材沒有所屬卡")
        return word
    owner = next(o for o in card["objects"] if o["id"] == owner_id)
    if owner["text"] is None:
        if (owner["source"]["kind"] != "新建" or owner["condition"] != xyz_monster_condition()
                or not owner["initial_position"]):
            raise NoTemplate("隱含的所屬卡無模板")
        return word
    return render_object(owner, seg, card, names, {"ref": obj.get("of_ref")},
                         self_id=self_id) + "の" + word


HOLDER_MARKER, HELD_MARKER = "が", "を"


def _render_held_material(obj, seg, card, names, self_id):
    """帶條件式的超量素材物件(「Xが「Y」をX素材としている」的 Y,m3 票 09):[所屬物件]が[條件+數量]を。
    素材名詞與「としている」由前提的模板接在後面。"""
    owner = next((o for o in card["objects"] if o["id"] == obj.get("of")), None)
    if owner is None or obj["unparsed"]:
        raise NoTemplate("持有的超量素材無模板")
    text = render_condition(obj["condition"], names)
    if obj["count"]:
        text += render_count(obj["count"])
    return (render_object(owner, seg, card, names, {"ref": obj.get("of_ref")}, self_id=self_id)
            + HOLDER_MARKER + text + HELD_MARKER)


def render_ref(ref, obj, seg, card):
    """回指字面:その/それらの+頭名詞照字面;動作回指(「めくったカード」)的動詞必須是
    這一段之前最後一個作用在該物件上的動作詞的過去形;「選択したモンスター」必須指回
    先前被取對象的物件。"""
    if REF_RE.match(ref):
        return ref
    if obj["source"]["kind"] == "自己" and ref == f"「{card['name_ja']}」":
        return ref   # 本卡以自己的卡名當主語(票 09)
    if ref == ACTIVATION_REF:
        # 「その発動」指回本區塊先前被發動的那張卡(票 09)。
        if last_action_on(obj["id"], seg, card) != "發動":
            raise NoTemplate("「その発動」回指的物件先前沒被發動")
        return ref
    if TARGET_REF_RE.match(ref):
        if not targeted_earlier(obj["id"], seg, card):
            raise NoTemplate("「選択した」回指的物件先前沒被取對象")
        return ref
    m = ACTION_REF_RE.match(ref)
    if m and m.group("past") in ACTION_PAST.values():
        action = last_action_on(obj["id"], seg, card)
        if ACTION_PAST.get(action) != m.group("past"):
            raise NoTemplate("動作回指與先前的動作不符")
        return ref
    restated = restated_reference(ref)
    if restated:
        # 帶修飾語的回指(「その相手モンスター」「対象の墓地のモンスター」,m3 票 05):修飾語照
        # `anaphora.restating_atoms` 認得全才寫;指向被取對象物件的要先前真的被取對象。
        if restated.targeted and not targeted_earlier(obj["id"], seg, card):
            raise NoTemplate("「対象の」回指的物件先前沒被取對象")
        return ref
    raise NoTemplate(f"回指字面無模板:{ref}")
