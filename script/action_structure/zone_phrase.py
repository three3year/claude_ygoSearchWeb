"""區域短語:抽取與句型模板成對放在一起。

- 抽取:`parse_from`(「自分の手札・フィールド」→ 區域列表,帶方與方的來源);`ZONE_PHRASE` 是
  各句型共用的區域短語正規式片段;`zone_literal` 判短語是不是用了非預設字面(要留原文)。
- 模板:`render_zone_text`(明寫的從/到)、`render_zones`(沒有原文字面時由區域拼回)、
  `render_premise_zones`(前提的區域)。
- 區域字面表本身在 `structure_shape.ZONE_WORDS`;方的字面在這裡的 `SIDE_WORDS`。
"""

import re

from segment_fields import render_display
from structure_shape import DEFAULT_ZONE_WORD, NoTemplate, ZONE_WORDS, zone


# 區域字面表在 structure_shape.ZONE_WORDS(三處共用)。
# 場上系區域:沒寫方時不預設(手札・デッキ・墓地沒寫方照慣例是自己的,場上不是)。
FIELD_ZONES = ("場上", "EX怪獸區", "怪獸區", "魔陷區", "P區", "場地區", "主要怪獸區")
# 從的助詞:新式「墓地の」「墓地から」;舊式連體修飾「墓地に存在するX」(= 墓地のX)。
FROM_PARTICLES = ("から", "の", "に存在する")
# 「持ち主の手札に戻す」的持ち主:值持有者,靜態判不了是哪一方,查詢指定我方/對手時不命中。
# 「お互いは」(誰,雙方各自);「自身の手札」的自身 = 這一段的誰那一方(「ドローしたプレイヤーは
# 自身の手札を」),同持有者靜態判不了,查詢指定我方/對手時不命中。
SIDE_WORDS = {"自分": "我方", "相手": "對手", "自分か相手": "任一方", "持ち主": "持有者",
              "お互い": "雙方各自", "自身": "自身"}
_ZONE_WORDS_ALT = "|".join(w for w, _ in ZONE_WORDS)
# 區域短語:[自分の|相手の|自分か相手の]區域(・區域|か區域)*;「・」與「か」都是列舉
# (自分の手札・フィールド、自分のフィールドか墓地),字面由從/到的 text 還原。
ZONE_PHRASE = (f"(?:(?:自分か相手|自分|相手|持ち主|自身)の?)?(?:{_ZONE_WORDS_ALT})"
               f"(?:[・か](?:{_ZONE_WORDS_ALT}))*")
_FROM_RE = re.compile("^(?:(?P<side>自分か相手|自分|相手|持ち主|自身)の?)?(?P<zones>.+)$")
# 區域短語裡的列舉連接字:「・」「か」,與「または」(「墓地またはフィールド上に」是區域的或,
# 同樣記成區域集合)。`ZONE_PHRASE` 不收「または」,只有自己帶句型的呼叫端(前提)會把這種短語交進來。
_ZONE_SEPARATOR_RE = re.compile("・|または|か")
ZONE_PHRASE_RE = re.compile(f"^{ZONE_PHRASE}$")
SIDE_TEXT = {v: k for k, v in SIDE_WORDS.items()}
# 「墓地からの(特殊召喚に成功した)」的「からの」排在「の」前:先比長的,才拆得回區域短語。
_POSITION_PARTICLES = ("からの",) + FROM_PARTICLES + ("に", "へ")


def parse_from(phrase):
    """「自分の手札・フィールド」→ 區域列表;任何一截不是區域字面就回 None。"""
    m = _FROM_RE.match(phrase)
    if not m:
        return None
    zones = []
    for part in _ZONE_SEPARATOR_RE.split(m.group("zones")):
        for word, name in ZONE_WORDS:
            if part == word:
                break
        else:
            return None
        if m.group("side"):
            side, side_source = SIDE_WORDS[m.group("side")], "明寫"
        elif name in FIELD_ZONES:
            # 「フィールドに「海」が存在する場合」是任一方的場上:場上系沒寫方就不預設。
            side, side_source = None, None
        else:
            side, side_source = "我方", "預設"
        zones.append(zone(name, side, side_source))
    return zones


def zone_literal(phrase):
    """區域短語用了非預設的字面(舊式「フィールド上」)就回短語本身(要留原文字面),否則 None。
    前提的區域平常照方的來源還原,只有這種情形還原不回原文。"""
    m = _FROM_RE.match(phrase)
    parts = _ZONE_SEPARATOR_RE.split(m.group("zones")) if m else []
    if "か" in phrase or "または" in phrase or any(
            part != DEFAULT_ZONE_WORD.get(dict(ZONE_WORDS).get(part)) for part in parts):
        return phrase   # 「か」「または」列舉(自分のフィールドか墓地)沒有預設寫法,也留字面
    return None


def render_zone_text(pos, particle):
    """明寫的從/到:有含助詞的原文字面且與區域一致就照字面寫;否則由區域拼回、接上預設助詞。"""
    zones = pos["zones"]
    text = pos.get("text")
    display = render_display(pos.get("form")) if particle == "から" else ""
    if text:
        # 「自分フィールドの、」的讀點是字面的一部分,驗區域時先去掉。
        bare = text[:-1] if text.endswith("、") else text
        particles = (f"に{display}存在する",) if display else _POSITION_PARTICLES
        phrase = next((bare[:-len(p)] for p in particles
                       if bare.endswith(p)), None)
        if phrase is None or parse_from(phrase) != zones:
            raise NoTemplate("從/到的字面與區域不一致")
        return text
    if display:
        raise NoTemplate("從的表示形式沒有字面")
    return render_zones(zones) + particle


def render_zones(zones):
    """區域列表 → 字面(沒有原文字面時用):方明寫才加「自分の/相手の」,只有一個區域且是
    フィールド時不加「の」(「自分フィールド」「自分の手札・フィールド」「自分の墓地」是官方的
    寫法);明寫的方是整個列表共用的前綴,沒寫的(預設或沒有方)各區域可以不同
    (「手札・フィールド」:手牌預設我方、場上沒有方)。"""
    written = {z["side"] for z in zones if z.get("side_source") == "明寫"}
    if len(written) > 1 or (written and any(
            z.get("side_source") != "明寫" for z in zones)):
        raise NoTemplate("從的區域分屬兩方")
    try:
        words = [DEFAULT_ZONE_WORD[z["zone"]] for z in zones]
    except KeyError as e:
        raise NoTemplate(f"區域無模板:{e.args[0]}") from None
    prefix = ""
    if written:
        side = written.pop()
        if side not in SIDE_TEXT:
            raise NoTemplate(f"方無模板:{side}")
        prefix = SIDE_TEXT[side] + ("" if words == ["フィールド"] else "の")
    return prefix + "・".join(words)


def render_premise_zones(zones, text):
    """前提的區域:帶原文字面(舊式「フィールド上」)時先驗過與區域一致再照字面,否則照方的來源還原。"""
    if text is None:
        return render_zones(zones)
    if parse_from(text) != zones:
        raise NoTemplate("前提的區域字面與區域不一致")
    return text
