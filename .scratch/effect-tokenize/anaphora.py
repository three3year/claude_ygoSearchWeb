# -*- coding: utf-8 -*-
"""[[回指]](.scratch/action-patient-anaphora):動作框架受事者位的指示詞實際指的目標。

框架抽取最後一步(frames.py,主題延續、回填、列舉、正規化之後),在一個編號效果的動作框架上
解析;受事者字面開頭是 その、それ、それら、対象の、この効果の対象,而且中心詞是卡、屬性或效果類的
框架帶可選欄 anaphora:

    text     目標字面(上游原值,不是框架序號)
    place    目標框架的所在或來源字面(推得的不算)
    player   玩家:從 place 或目標字面開頭的 自分/相手/お互い
    subject  事件主語或效果類的主人(相手がモンスターを特殊召喚した時、このカードの攻撃宣言時)
    count    目標的數量只寫在子句裡時的數量字面(モンスターを１体選んで)
    via      找到的方法:対象/欄位/字面/事件

找法:対象の、この効果の対象 → 該效果的 対象とする 框架;效果類 → 最近的事件框架;其餘往前找框架
的對象、主語、主題,都沒有才找字面。候選多個時先比限定語與中心詞,都對得上取最近的。單數或複數
都不回指字面只是 このカード 的值;並列含此卡的算。範圍是整個編號效果,● 選項只看共同部分與自己
這個選項。指示詞只修飾另一張卡時不是回指(modifier)。
"""
from collections import namedtuple
import re

from places import PLAYER_BOTH, PLAYER_OPP, PLAYER_PREFIXES, PLAYER_SELF, ZONE_TERMS

VIA_TARGET, VIA_FIELD, VIA_LITERAL, VIA_EVENT = "対象", "欄位", "字面", "事件"
HEAD_MONSTER, HEAD_CARD, HEAD_ANY = "monster", "card", "any"

THIS_CARD = "このカード"
TARGET_ACTIONS = ("対象とする", "対象にする")
INTRANSITIVE = ("自動", "受身")

_SPACES = re.compile(r"\s+")
_DEMONSTRATIVE = re.compile(r"^(?:それら?(?:の|$)|その|対象の|この効果の対象)")
_TARGETED = re.compile(r"^(?:対象の|この効果の対象)")
# 卡片名詞的尾巴與數量;多一個 組(その１組)是指示詞才有的寫法,動作對象的數量表不收
_QUANTITY = r"[0-9０-９]+(?:枚|体|つ|種類|ヵ所|箇所|個|組)"
_COUNT_TAIL = re.compile(r"(%s)?(?:まで|以上)?$" % _QUANTITY)
_CLAUSE_COUNT = re.compile(r"を(%s)|数まで|任意の数|好きな数" % _QUANTITY)
_ALL_OF_THEM = re.compile(r"全て")
_PLURAL_COUNT = re.compile(r"^(?:[2-9２-９]|[0-9０-９]{2,})")
VALUE_HEADS = ("攻撃力", "守備力", "レベル", "ランク", "Pスケール", "属性", "種族", "カード名",
               "表示形式", "コントロール", "位置")
_VALUE = r"(?:元々の)?(?:%s)" % "|".join(VALUE_HEADS)
_VALUE_TAIL = re.compile(r"^(.*?)の*%s(?:(?:・|と|及び|および)%s)*$" % (_VALUE, _VALUE))
# 卡的效果、發動:そのモンスターの効果 跟著卡走,光禿禿的 その効果 是效果類
_EFFECT_TAIL = re.compile(r"^(.*?)の(?:発動した)?(?:効果|発動)(?:の発動)?$")
# 字面片語裡事件名詞前的主人:モンスターの特殊召喚、相手モンスターの直接攻撃宣言
_EVENT_NOUN_TAIL = re.compile(r"^(.*?)の(?:[^の]*召喚(?:成功)?|(?:直接)?攻撃(?:宣言)?|発動|効果)(?:の発動|の処理)?$")
# その魔法カード発動時の効果、その儀式魔法カード発動時の儀式召喚する効果:跟著那張卡
_ACTIVATION_EFFECT = re.compile(r"^(.+?)発動時の.*効果$")
_PROCESSING_TAIL = re.compile(r"の処理$")
_EVENT_WORDS = (("発動", "発動"), ("効果", "発動"), ("攻撃", "攻撃"), ("召喚", "召喚"))
_ATTACK_ACTIONS = ("攻撃宣言", "攻撃", "直接攻撃", "攻撃対象にする")
# 主語是被攻擊的那張,不是主人(攻撃対象になった 是自動,攻撃対象に選択された 是受身)
_TARGETED_EVENTS = ("攻撃対象にする",)
NOT_CARD_HEADS = ("ダメージ", "LP", "ライフポイント", "カウンター", "サイコロ", "コイントス",
                  "フェイズ", "ダメージ計算", "召喚条件", "数値", "数", "ターン", "目", "枚数",
                  "合計", "種類")
_ZONES = "|".join(re.escape(term) for term, _ in ZONE_TERMS)
_MONSTER_TAIL = re.compile(r"(?:モンスター(?:カード)?|トークン|チューナー)$")
_CARD_TAIL = re.compile(r"(?:カード|カード\)|魔法|罠|」|素材)$")
_ZONE_ONLY = re.compile(r"^(?:自分の?|相手の?|お互いの?)?(?:%s)$" % _ZONES)
_LEADING_ZONE = re.compile(r"^((?:自分|相手|お互い)?の?(?:%s))の(.+)$" % _ZONES)
# 不是指目標的 その:時間、程度、數值的修飾(その場合このカード、その時のS素材モンスター)
_NOT_REFERENCE = re.compile(r"^その(?:場合|時|中|後|他|度|まま|差|数|属性の|種族の|レベルの|カード名が"
                            r"|同名|手札)")
# 指示詞只修飾另一張卡:關係詞之後才是受事者的中心詞
_MODIFIER = re.compile(r"より|と同じ|と同名|とは|と元々|とカード名|と異|と種類|と属性|と種族|とリンク"
                       r"|以外|以下|以上|未満|を持つ|が|に記|にカード名|に自身|を含む|の同名|の中|に使用")
# 另一張實體卡:そのモンスターのX素材、そのモンスターの装備カード、その相手モンスターの攻撃対象
_ATTACHED = re.compile(r"(?<!そ)の(?:X素材|装備|攻撃対象)")
_LISTING = re.compile(r"(?:と|及び|および|または|か|や)(?!は)")
_LISTED_THIS_CARD = re.compile(r"(?:と|及び|および|または|か|や).*%s$" % THIS_CARD)
_THIS_CARD_TAIL = re.compile(r"%s(?:の.*)?$" % THIS_CARD)
_TYPE_QUALIFIERS = ("融合", "シンクロ", "S", "エクシーズ", "X", "リンク", "儀式", "ペンデュラム", "P")
# 限定語:玩家、卡種這些比候選自己的字面;動作(その破壊されたモンスター)也比它所在的子句
_ACTION_QUALIFIERS = ("攻撃", "装備", "破壊", "特殊召喚", "発動", "除外", "戦闘", "無効")
_QUALIFIERS = ("相手", "自分") + _TYPE_QUALIFIERS + (
    "チューナー", "守備", "表側", "裏側", "効果", "通常", "魔法", "罠") + _ACTION_QUALIFIERS
# 主人的「Xの」不跨格助詞:相手がこのカードの効果を… 的主人不是「相手がこのカード」
_OWNER_IN_CLAUSE = re.compile(r"^([^がをはにで]+?)の(?:攻撃宣言|攻撃|発動|効果)")
# 比限定語時,融合素材 不算 融合、S素材 不算 S
_MATERIAL = re.compile(r"(?:融合|シンクロ|エクシーズ|リンク|S|X|L)?素材(?:モンスター)?")
_MATERIAL_TAIL = re.compile(r"素材(?:モンスター)?(?:%s)?$" % _QUANTITY)
_GROUP_TAIL = re.compile(r"(?:同士|のいずれか)$")


def _is_activation(action):
    return action == "発動"


def _is_summon(action):
    return action.endswith("召喚")


# 效果類的中心詞 → (事件框架的動作, 字面片語的尾巴)
_EVENTS = {"発動": (_is_activation, re.compile(r"の(?:発動|効果)(?:の発動|の処理)?$")),
           "攻撃": (_ATTACK_ACTIONS.__contains__, re.compile(r"の(?:直接)?攻撃(?:宣言)?$")),
           "召喚": (_is_summon, re.compile(r"召喚$")),
           HEAD_ANY: (lambda action: _is_activation(action) or _is_summon(action),
                      re.compile(r"の(?:発動|効果|[^の]*召喚)(?:の発動|の処理)?$"))}

Reference = namedtuple("Reference", "kind head qualifiers plural within counted")
# 字面片語:句序、起點、選項、字面、前面的 が 片語、「Xが発動した」的 X
Phrase = namedtuple("Phrase", "sentence start option text agent activator")
KIND_TARGETED, KIND_CARD, KIND_EVENT = "targeted", "card", "event"


def _clean(text):
    return _SPACES.sub("", text or "")


def _strip_count(text):
    return _COUNT_TAIL.sub("", text)


def is_demonstrative(text):
    return bool(_DEMONSTRATIVE.match(_clean(text)))


def modifier(text):
    """受事者開頭是指示詞,但指示詞只修飾另一張卡(そのモンスターより…Xモンスター):受事者照自己
    的字面判。"""
    text = _clean(text)
    if not is_demonstrative(text) or _is_not_card(text):
        return False
    # 屬性與效果跟著卡走:そのモンスター以外の…カードの効果 的中心詞是那些卡
    tail = _VALUE_TAIL.match(text) or _EFFECT_TAIL.match(text)
    core = _strip_count(tail.group(1) if tail else text)
    if not _is_card_tail(core):
        return False
    return bool(_NOT_REFERENCE.match(text) or _MODIFIER.search(_DEMONSTRATIVE.sub("", core)))


def _is_not_card(text):
    return _strip_count(text).endswith(NOT_CARD_HEADS)


def _is_card_tail(core):
    return bool(_MONSTER_TAIL.search(core) or _CARD_TAIL.search(core))


def reference(text):
    """受事者字面 → Reference;不是回指(不是指示詞、修飾語、不是卡、另一張實體卡)時 None。"""
    text = _clean(text)
    if not is_demonstrative(text) or _NOT_REFERENCE.match(text) or modifier(text) \
            or _is_not_card(text) or _ATTACHED.search(text):
        return None
    targeted = bool(_TARGETED.match(text))
    # そのモンスターとこのカード:並列時回指只關於開頭那段;〜分このカードの攻撃力 不是指示詞的受事者
    if _THIS_CARD_TAIL.search(text) and not re.search(r"(?:と|及び|および)%s" % THIS_CARD, text):
        return None
    rest = _DEMONSTRATIVE.sub("", text)
    value = _VALUE_TAIL.match(_strip_count(rest))
    body = value.group(1) if value else rest
    owner = _ACTIVATION_EFFECT.match(body) or _EFFECT_TAIL.match(body)
    if owner and _is_card_tail(_strip_count(owner.group(1))):
        body = owner.group(1)
    elif text.startswith("それ") and body in ("効果", "発動"):
        body = ""
    body = _LISTING.split(body, maxsplit=1)[0]
    within = "内" in body
    plural = text.startswith("それら") or within
    count = _COUNT_TAIL.search(body).group(1)
    core = _strip_count(body)
    if count and _PLURAL_COUNT.match(count):
        plural = True
    qualifiers = tuple(q for q in _QUALIFIERS if q in core)
    if targeted:
        return Reference(KIND_TARGETED, _head_of(core, count), qualifiers, plural, within, bool(count))
    if not value and core.endswith(tuple(word for word, _ in _EVENT_WORDS)):
        event = next(action for word, action in _EVENT_WORDS if core.endswith(word))
        return Reference(KIND_EVENT, event, tuple(q for q in qualifiers if q not in ("効果", "発動", "攻撃")),
                         False, False, False)
    head = _head_of(core, count)
    return Reference(KIND_CARD, head, qualifiers, plural, within, bool(count)) if head else None


def _head_of(core, count):
    if _MONSTER_TAIL.search(core):
        return HEAD_MONSTER
    if _CARD_TAIL.search(core):
        return HEAD_CARD
    if core and not core.endswith("内") and not core.endswith("の"):
        return None
    if count and "体" in count:
        return HEAD_MONSTER
    if count:
        return HEAD_CARD
    return HEAD_ANY


def patient_key(frame):
    """受事者在哪一欄:他動(與沒判態的)是對象,自動/受身是主語、沒有時主題。"""
    if frame.get("voice") in INTRANSITIVE:
        return "subject" if frame.get("subject") else "topic"
    return "object"


def _region(frame):
    inferred = frame.get("inferred") or ()
    source = None if "source" in inferred else frame.get("source")
    return source or frame.get("place")


def _player(*texts):
    for text in texts:
        text = _clean(text)
        if "を対象" in text:      # 自分フィールドの…を対象とする魔法カード:開頭是被針對的,不是玩家
            continue
        for prefix, player in PLAYER_PREFIXES:
            if text.startswith(prefix) and player in (PLAYER_SELF, PLAYER_OPP, PLAYER_BOTH):
                return player
    return None


def _bare_target(text):
    """候選字面 → 目標本身:去掉屬性、事件名詞與群組的尾巴(相手モンスターの攻撃力 → 相手モンスター、
    モンスター同士 → モンスター)。"""
    found = _VALUE_TAIL.match(text) or _EVENT_NOUN_TAIL.match(text)
    return _GROUP_TAIL.sub("", found.group(1) if found and found.group(1) else text)


def only_this_card(text):
    """字面只是此卡(帶定語的也算:S召喚したこのカード);並列含此卡的不算。"""
    text = _clean(text)
    return text.endswith(THIS_CARD) and not _LISTED_THIS_CARD.search(text)


def _head_fit(ref, literal):
    """目標中心詞 × 候選字面 → 2 對得上、1 勉強(そのモンスター×カード１枚)、0 不行。"""
    text = _bare_target(literal)
    if only_this_card(text):
        return 0
    core = _strip_count(text)
    if not core:              # 只剩數量(モンスターが１体のみの場合 的 1体)不是目標
        return 0
    if ref.within and _ZONE_ONLY.search(core):
        return 2
    counted = core != text
    monster = bool(_MONSTER_TAIL.search(core)) or (counted and text.endswith("体"))
    card = bool(_CARD_TAIL.search(core)) or (counted and text.endswith("枚"))
    if not (monster or card) and counted and _ZONE_ONLY.search(core):
        card = True
    if not (monster or card):
        return 0
    if ref.head == HEAD_MONSTER:
        return 2 if monster or core.endswith("」") else 1
    return 2


def _plural_fit(ref, literal):
    if not ref.plural:
        return True
    count = _COUNT_TAIL.search(literal).group(1)
    return bool(_LISTING.search(literal)) or bool(count and _PLURAL_COUNT.match(count)) \
        or not count


# 一個候選:比對用的字面、候選自己的字面(含區域、主語)、它所在的子句、組回指值的函式
_Candidate = namedtuple("_Candidate", "text own clause build")


def _qualified(ref, candidate):
    """指示詞的限定語候選都有:融合素材 不算 融合;玩家、卡種只比候選自己,不比同子句別的片語。"""
    own = _MATERIAL.sub("", candidate.own)
    clause = _MATERIAL.sub("", candidate.clause)
    return all(q in own or (q in _ACTION_QUALIFIERS and q in clause) for q in ref.qualifiers)


def _value_from_field(frame, key, literal):
    literal = _bare_target(literal)
    out = {"text": literal}
    if key == patient_key(frame) and _region(frame):
        out["place"] = _region(frame)
    if key == "object":
        agent = frame.get("subject") or frame.get("topic")
        if agent:
            out["subject"] = agent
    player = _player(out.get("place"), literal)
    if player:
        out["player"] = player
    clause = _clean(frame.get("clause"))
    if not _COUNT_TAIL.search(literal).group(1) and not _ALL_OF_THEM.search(clause):
        count = _CLAUSE_COUNT.search(clause)
        if count:
            out["count"] = count.group(1) or count.group(0)
    return dict(out, via=VIA_FIELD)


def _field_candidates(earlier):
    """往前的框架 → 候選(近的在前);字面是指示詞的用它解到的值(解到底)。回填來的對象與主題
    不算候選:提供它的框架更前面,值相同,數量也寫在那裡。"""
    for frame in reversed(earlier):
        filled = frame.get("backfill") or ()
        for key in ("object", "subject", "topic"):
            if not frame.get(key) or (key != "subject" and key in filled):
                continue
            literal = _clean(frame[key])
            if reference(literal):
                resolved = frame.get("anaphora")
                if key == patient_key(frame) and resolved:
                    yield _Candidate(resolved["text"],
                                     resolved["text"] + (resolved.get("place") or "")
                                     + (resolved.get("subject") or ""),
                                     _clean(frame.get("clause")), lambda r=resolved: dict(r))
                continue
            if is_demonstrative(literal) and not modifier(literal):
                continue
            yield _Candidate(literal, literal + _clean(_region(frame)) + _clean(frame.get("subject")),
                             _clean(frame.get("clause")),
                             lambda f=frame, k=key, v=literal: _value_from_field(f, k, v))


def _value_from_phrase(phrase, agent=None):
    event = _EVENT_NOUN_TAIL.match(phrase)
    phrase = _bare_target(phrase)
    found = _LEADING_ZONE.match(phrase)
    out = {"text": found.group(2), "place": found.group(1)} if found else {"text": phrase}
    # 相手がモンスターの特殊召喚に成功した時:片語是事件時,前面的 が 片語是事件主語
    if event and agent:
        out["subject"] = agent
    player = _player(out.get("place"), phrase, out.get("subject"))
    if player:
        out["player"] = player
    return dict(out, via=VIA_LITERAL)


def _phrase_candidates(phrases):
    for phrase in reversed(phrases):
        if is_demonstrative(phrase.text):
            continue
        yield _Candidate(phrase.text, phrase.text, "",
                         lambda p=phrase: _value_from_phrase(p.text, p.agent))


def _best(ref, fields, phrases):
    """欄位對得上 → 字面對得上 → 欄位勉強(限定語對不上)→ 字面勉強;同層取最近。"""
    def tier(candidates, strict):
        for candidate in candidates:
            fit = _head_fit(ref, candidate.text)
            if not fit:
                continue
            # その融合モンスター 不指融合素材モンスター:中心詞是素材時卡種限定語對不上
            material = _MATERIAL_TAIL.search(candidate.text) \
                and any(q in _TYPE_QUALIFIERS for q in ref.qualifiers)
            exact = not material and _qualified(ref, candidate) and _plural_fit(ref, candidate.text)
            if not strict or (exact and fit == 2):
                return candidate
        return None
    for candidates, strict in ((fields, True), (phrases, True), (fields, False), (phrases, False)):
        found = tier(candidates, strict)
        if found:
            return found.build()
    return None


def _owner(frame):
    """事件框架 → 事件的主人:主語、主題,再來是 Xの効果 的對象,子句字面的「Xの」。受身的主語是被
    攻擊、被召喚的那張,不是主人。"""
    passive = frame.get("voice") == "受身" or frame["action"] in _TARGETED_EVENTS
    agent = None if passive else (frame.get("subject") or frame.get("topic"))
    if agent:
        found = _EFFECT_TAIL.match(_clean(agent))
        return found.group(1) if found else _clean(agent)
    if passive:
        return None
    found = _EFFECT_TAIL.match(_clean(frame.get("object")))
    if found:
        return found.group(1)
    found = _OWNER_IN_CLAUSE.match(_clean(frame.get("clause")))
    return found.group(1) if found else None


def _event_value(text, owner):
    out = {"text": text}
    if owner:
        out["subject"] = owner
        player = _player(owner)
        if player:
            out["player"] = player
    return dict(out, via=VIA_EVENT)


def _event_target(ref, earlier, phrases):
    wanted, tail = _EVENTS[ref.head]
    events = [f for f in reversed(earlier) if wanted(f["action"])]
    for frame in events:
        if all(q in _clean(frame.get("clause")) for q in ref.qualifiers):
            return _event_value(_clean(frame.get("object")) or frame["action"], _owner(frame))
    if events:
        return _event_value(_clean(events[0].get("object")) or events[0]["action"], _owner(events[0]))
    # 字面:要有「Xの」主人,光禿禿的 発動(発動できる)不是事件;相手が発動した〜 的主人是相手
    for phrase in reversed(phrases):
        if is_demonstrative(phrase.text) or not tail.search(phrase.text):
            continue
        found = _OWNER_IN_CLAUSE.match(phrase.text)
        return _event_value(_PROCESSING_TAIL.sub("", phrase.text),
                            phrase.activator or (found.group(1) if found else None))
    return None


def _targeted(ref, earlier):
    targets = [f for f in earlier if f["action"] in TARGET_ACTIONS and f.get("object")]
    candidates = [c for c in _field_candidates(targets)
                  if not only_this_card(c.text)]
    for candidate in candidates:
        if _qualified(ref, candidate):
            return dict(candidate.build(), via=VIA_TARGET)
    return dict(candidates[0].build(), via=VIA_TARGET) if candidates else None


def _in_scope(option, other):
    return other is None or other == option


def _phrases_before(phrases, frame, option):
    """指示詞之前的字面片語:到子句裡受事者自己那個片語為止,述語前的片語也算在前面。"""
    literal = _clean(frame.get(patient_key(frame)))
    out = []
    for phrase in phrases:
        at = (phrase.sentence, phrase.start)
        if at >= (frame["sentence"], frame["span"][1]):
            break
        if at >= (frame["sentence"], frame["span"][0]) and (
                literal.startswith(phrase.text) or phrase.text.startswith(literal)):
            break
        if _in_scope(option, phrase.option):
            out.append(phrase)
    return out


def resolve(frames, phrases):
    """一個編號效果依原文排序的框架清單(含約束框架),與它的字面片語(Phrase):
    → 動作框架上就地寫 anaphora 欄;找不到不寫。"""
    actions = [f for f in frames if f["kind"] == "動作"]
    for k, frame in enumerate(actions):
        ref = reference(frame.get(patient_key(frame)))
        if ref is None:
            continue
        option = frame.get("option")
        start = (frame["sentence"], frame["span"][0])
        earlier = [f for f in actions[:k] if _in_scope(option, f.get("option"))
                   and (f["sentence"], f["span"][0]) < start]
        before = _phrases_before(phrases, frame, option)
        # それを無効にし:無效的是事件,不是剛提到的卡
        if frame["action"] == "無効にする" and _clean(frame.get(patient_key(frame))) == "それ":
            ref = ref._replace(kind=KIND_EVENT)
        if ref.kind == KIND_TARGETED:
            found = _targeted(ref, earlier)
        elif ref.kind == KIND_EVENT:
            # 魔法カードがその効果を発動した時:主人就是這個框架的主語
            found = ({"text": frame["action"], "subject": _clean(frame["subject"]), "via": VIA_EVENT}
                     if frame.get("subject") and frame["action"] == "発動"
                     else _event_target(ref, earlier, before))
        else:
            found = _best(ref, list(_field_candidates(earlier)), list(_phrase_candidates(before)))
        if found:
            # その相手モンスター:指示詞自己寫的玩家優先
            own = next((q for q in ref.qualifiers if q in ("相手", "自分")), None)
            if own and ref.kind != KIND_EVENT:
                found["player"] = own
            frame["anaphora"] = found
