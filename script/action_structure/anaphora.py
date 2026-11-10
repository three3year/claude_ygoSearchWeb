"""物件短語的兩種「指誰」寫法(m3 票 05):帶狀態的此卡、帶修飾語的回指。只看字面與修飾語規則,
物件由 `block_state.BlockState.object_at` 建或指;模板在 `object_render`。

- 帶狀態的此卡:「〈狀態〉このカード」(この効果で特殊召喚したこのカード、装備状態のこのカード、
  表側表示のこのカード)。狀態是修飾語原子(`self_state_atoms`):開頭可以是只修飾此卡的狀態字面
  (`state_atoms.parse_self_state`),其餘照一般修飾語認;整截認得全才算。物件是母體為此卡的子集,
  條件式是那些原子(沒有大類的頭名詞)。
- 帶修飾語的回指:「その相手モンスター」「その融合モンスター」「対象の墓地のモンスター」。修飾語只是重述
  (站主裁定),留在回指字面裡、不建新物件、不加條件。重述的修飾語限卡片自身的性質與狀態
  (`RESTATING_OPS`:控制方、位置、表示形式、不帶引用的屬性比較);「その同名カード」「その内のモンスター」
  不是重述,不在這裡。指回哪一個:最近的同大類物件裡,與重述不衝突的那個(`contradicts`:方、位置、
  同一個屬性的值);一個都沒有就是指回的物件找不到。
"""
import re
from typing import NamedTuple

from noun_phrase import parse_modifiers
from state_atoms import parse_self_state
from structure_shape import zone_names
from synonyms import TARGET_REF

SELF_TAIL = "このカード"
RESTATING_OPS = ("控制方", "位置", "表示形式", "屬性比較")
_RESTATED_RE = re.compile(
    f"^(?P<prefix>その|それらの|{TARGET_REF})(?P<mods>.+?)(?P<head>モンスター|カード)$")
REF_PREFIXES = ("その", "それらの")


class _NoNames:
    """重述的修飾語不看名稱表、不解回指:「」名稱與引用一律認不得。"""
    self_id = None

    @staticmethod
    def name_atom(op, name, form=None):
        return None, "重述的修飾語不收名稱"

    @staticmethod
    def resolve_reference(phrase):
        return None


class Restated(NamedTuple):
    """帶修飾語的回指拆出的格:指向先前被取對象的物件(対象の、選択した)還是最近提過的(その)、
    頭名詞、重述的原子。"""
    targeted: bool
    head: str
    atoms: list


def restating_atoms(mods):
    """重述的修飾語 → 原子列表;認不全、或有不是重述的原子回 None。抽取與模板共用這一把尺。"""
    atoms, reason = parse_modifiers(_NoNames, mods)
    if reason or any(not _restates(atom) for atom in atoms):
        return None
    return atoms


def _restates(atom):
    if atom.get("op") == "或":
        return all(_restates(arg) for arg in atom["args"])
    return atom.get("op") in RESTATING_OPS and "ref" not in atom


def restated_reference(phrase):
    """「その相手モンスター」「対象の墓地のモンスター」→ `Restated`;不是帶修飾語的回指回 None。"""
    m = _RESTATED_RE.match(phrase)
    atoms = m and restating_atoms(m.group("mods"))
    if not atoms:
        return None
    return Restated(m.group("prefix") not in REF_PREFIXES, m.group("head"), atoms)


def _side_of(obj, zones):
    """物件是哪一方的:條件式裡的控制方,沒有就看目前位置(各區域同一方才算);判不出回 None。"""
    for atom in _top_atoms(obj["condition"]):
        if atom.get("op") == "控制方":
            return atom.get("value")
    sides = {z.get("side") for z in zones or ()}
    return sides.pop() if len(sides) == 1 else None


def _top_atoms(condition):
    if not condition:
        return []
    return condition["args"] if condition.get("op") == "且" else [condition]


def _same_place(have, want):
    """兩個區域對不對得上:一個在另一個裡面(或相同),而且方沒有寫成不同的兩方。"""
    return ((want["zone"] in zone_names(have["zone"]) or have["zone"] in zone_names(want["zone"]))
            and (not have.get("side") or not want.get("side") or have["side"] == want["side"]))


def contradicts(obj, atoms, zones):
    """物件與重述的修飾語衝突:方不同(「その自分のモンスター」不會指相手モンスター)、同一個屬性寫了
    不同的值(「その融合モンスター」不會指 Sモンスター)、或不在重述的位置(「対象の墓地のモンスター」不會指
    場上的那張)。`zones` 是物件的目前位置(區域列,不知道是 None);沒寫的、不知道的不算衝突。"""
    for atom in atoms:
        if atom.get("op") == "控制方":
            side = _side_of(obj, zones)
            if side in ("我方", "對手") and side != atom["value"]:
                return True
        elif atom.get("op") == "位置":
            if zones and not any(_same_place(have, want) for have in zones for want in atom["zones"]):
                return True
        elif atom.get("op") == "屬性比較" and atom.get("cmp") == "=":
            for have in _top_atoms(obj["condition"]):
                if (have.get("op") == "屬性比較" and have.get("cmp") == "=" and "ref" not in have
                        and have.get("attr") == atom["attr"] and have.get("value") != atom["value"]):
                    return True
    return False


def self_state_atoms(state, phrase):
    """「〈狀態〉このカード」→ 狀態的原子列表;不是這個寫法、或狀態認不全回 None。"""
    if not phrase.endswith(SELF_TAIL) or phrase == SELF_TAIL:
        return None
    mods = phrase[:-len(SELF_TAIL)]
    atoms = []
    own, length = parse_self_state(mods)
    if own is not None:
        atoms.append(own)
        mods = mods[length:]
    if mods:
        more, reason = parse_modifiers(state, mods)
        if reason or any(atom.get("op") == "解析不出" for atom in more):
            return None
        atoms.extend(more)
    return atoms
