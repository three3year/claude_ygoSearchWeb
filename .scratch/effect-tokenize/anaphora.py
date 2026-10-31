# -*- coding: utf-8 -*-
"""[[回指]](.scratch/action-patient-anaphora;named-queries 票 03 改讀論元片語):動作框架受事者位的指示詞
實際指的目標。

執行位置:框架抽取的既有步驟(主題延續、回填、列舉、正規化)與片語結構化(phrases.mark)之後、其餘第四版
論元之前(frames.py 的處理順序段)。受事者片語的第一段是指示詞(段的 demonstrative 旗標;その、それ、それら、
対象の、この効果の対象 起頭)而且中心詞是卡、屬性或事件類的框架帶可選欄 anaphora:

    text     目標字面(上游原值,不是框架序號)
    place    目標框架的所在或來源字面(推得的不算)
    player   玩家:從 place 或目標字面開頭的 自分/相手/お互い
    subject  事件主語或效果類的主人(相手がモンスターを特殊召喚した時、このカードの攻撃宣言時)
    count    目標的數量只寫在子句裡時的數量字面(モンスターを１体選んで;片語段的 取自子句 數量)
    via      找到的方法:対象/欄位/字面/事件
    moving   目標框架的動作是不是移動類(frame-args-v4 票 09;enrich.py 在事後補,這裡不寫)

目標框架:解析時把目標是哪幾個框架(欄位候選的框架;候選自己是解到底的指示詞時連同它鏈上的
目標;事件框架)記在框架的內部鍵 _anaphora_targets(回指回填要判目標是不是移動類;enrich.py 讀完
pop 掉,不進 frames.json);字面備援的目標不是框架,清單空。

找法(不變):対象の、この効果の対象 → 該效果的 対象とする 框架;效果類 → 最近的事件框架;其餘往前找框架
的對象、主語、主題,都沒有才找字面。候選多個時先比限定語與中心詞,都對得上取最近的。單數或複數
都不回指字面只是 このカード 的值;並列含此卡的算。範圍是整個編號效果,● 選項只看共同部分與自己
這個選項。指示詞只修飾另一張卡時不是回指(modifier)。

讀法(票 03):指示詞字面與候選都讀論元片語的段(phrases.segment:中心詞、中心詞類、修飾語的類與字面、
數量、玩家、區域、指示詞旗標),不再自己拆字面——
- 指示詞字面:受事者片語的第一段。中心詞類 卡 → 卡類回指(モンスター/トークン/チューナー 尾是怪獸、其餘是卡);
  屬性類而中心詞不是事件詞(攻撃力、種族…)→ 跟著主人走(中心詞前最後一個 の 之前的字面再切一段);
  事件詞(発動/効果/攻撃/〜召喚)→ 主人是卡時跟著卡、否則效果類;指示詞類(それ/それら/内/只剩數量的段)→
  中心詞不限。限定語 = 段的玩家、修飾語(玩家/卡片子類型/表示形式/種族/屬性/字段 依類與字面比;其他 類裡的
  動作詞 攻撃/破壊/… 也比候選所在的子句)與中心詞自帶的卡種(効果モンスター、チューナー、魔法カード)。
  指示詞綁的修飾語不是卡的屬性/事件、而是屬性詞(その属性のモンスター)、區域(その手札のカード)、
  時間/程度詞(その場合、その同名)或 以外 時,指示詞只修飾另一張卡(modifier);綁的是卡而中心詞是別的卡
  (そのモンスターのX素材/装備カード/攻撃対象)時是另一張實體卡,不回指也不算修飾語。
- 候選:框架欄位的段(frames 的 phrases 欄;切區域前的字面)與字面備援片語的段;中心詞是屬性時目標是主人,
  同士/のいずれか 收尾的去尾。中心詞相符:卡類 vs 怪獸類(そのモンスター×カード１枚 勉強算);單複數看
  段的數量與段數;子句裡的數量讀段的 取自子句 數量。
封閉表在模組頂,一份;判定讀表。沒有正則式。

對外的介面:resolve(ctx, tokens, frames, phrases)(frames.py 呼叫)、field_reference(ctx, frame, key) → Reference |
MODIFIER | None(llm_check 的回指分層用;ctx 從 frames.context() 拿)、is_demonstrative(text)(切區域後的字面是不是指示詞
起頭)、only_this_card(text)、patient_key(frame);patient.py 只讀常數 THIS_CARD/INTRANSITIVE/VIA_EVENT。
"""
from collections import namedtuple

import places
import phrases
from closed_values import HEAD_ATTRIBUTE, HEAD_CARD, HEAD_DEMONSTRATIVE, MODIFIER_KINDS, OTHER, PLACE_PLAYER
from places import PLAYER_BOTH, PLAYER_OPP, PLAYER_PREFIXES, PLAYER_SELF

VIA_TARGET, VIA_FIELD, VIA_LITERAL, VIA_EVENT = "対象", "欄位", "字面", "事件"
# 回指目標的中心詞要求:怪獸、卡(怪獸也算卡)、不限
TARGET_MONSTER, TARGET_CARD, TARGET_ANY = "monster", "card", "any"
MOD_RACE, MOD_ATTRIBUTE, MOD_ARCHETYPE, MOD_SUBTYPE, MOD_NUMERIC, MOD_ZONE, MOD_PLAYER, MOD_POSITION = MODIFIER_KINDS[:8]

THIS_CARD = "このカード"
TARGET_ACTIONS = ("対象とする", "対象にする")
INTRANSITIVE = ("自動", "受身")

# ── 封閉表(2026-11-01 票 03:原本的正則式收成表;來源 action-patient-anaphora 票 01〜04 與 anaphora-round1/2)──
# 指示詞字面的起頭(字面 API 與候選過濾用;指示詞是不是綁在定語子句裡讀段的 demonstrative 旗標)
DEMONSTRATIVE_BARE = ("それ", "それら")
DEMONSTRATIVE_PREFIXES = ("それらの", "それの", "その", "対象の", "この効果の対象")
TARGETED_PREFIXES = ("対象の", "この効果の対象")           # → 找該效果的 対象とする 框架
TARGET_WORD = "対象"                                       # この効果の対象 的中心詞;対象のモンスター 的第一個修飾語
WITHIN = "内"                                              # その内の1枚:目標是前面確認的區域/群,複數
ORIGINAL = "元々"                                          # 元々の攻撃力 的 元々 不是主人
MONSTER_HEAD_SUFFIXES = ("モンスター", "モンスターカード", "トークン", "チューナー")   # 中心詞類 卡 之中的怪獸
CARD_SUFFIX = "カード"                                     # 魔法カード 的 魔法 是卡種限定語
MONSTER_COUNTER, CARD_COUNTER = "体", "枚"                 # 只剩數量的段(その2体)與候選的量詞 → 怪獸/卡
MATERIAL = "素材"                                          # 融合素材 不算 融合;中心詞是素材時卡片子類型限定語對不上
# 事件類:中心詞(或字面片語的事件名詞)→ 事件組;召喚 看尾字(特殊召喚、S召喚)
EVENT_HEADS = {"発動": "発動", "効果": "発動", "攻撃": "攻撃", "宣言": "攻撃"}
EVENT_SUMMON, SUMMON_SUFFIX = "召喚", "召喚"
SUMMON_SUCCESS = "召喚成功"                                 # 特殊召喚成功時:段尾是 成功 的召喚事件
EVENT_WORDS = ("発動", "効果", "攻撃", "召喚")             # 事件詞不當限定語
OWNER_EVENT_WORDS = ("攻撃", "発動", "効果")               # 子句裡「Xの攻撃宣言/攻撃/発動/効果」的主人 X
EVENT_TAILS = ("処理", "発動")                             # 効果の処理/効果の発動:字面片語尾的事件後綴
PROCESSING_TAIL = "の処理"                                 # 回指值的字面去掉 の処理(效果本身才是目標)
ACTIVATION_TIME = "発動時"                                 # その魔法カード発動時の効果 跟著那張卡
ATTACK_ACTIONS = ("攻撃宣言", "攻撃", "直接攻撃", "攻撃対象にする")
# 主語是被攻擊的那張,不是主人(攻撃対象になった 是自動,攻撃対象に選択された 是受身)
TARGETED_EVENTS = ("攻撃対象にする",)
# 效果類的中心詞 → (事件框架的動作判準, 字面片語允許的事件組)
_EVENTS = {"発動": (lambda action: action == "発動", ("発動",)),
           "攻撃": (ATTACK_ACTIONS.__contains__, ("攻撃",)),
           EVENT_SUMMON: (lambda action: action.endswith(SUMMON_SUFFIX), (EVENT_SUMMON,)),
           TARGET_ANY: (lambda action: action == "発動" or action.endswith(SUMMON_SUFFIX), ("発動", EVENT_SUMMON))}
# 指示詞綁的詞是時間、程度、數值的修飾(その場合このカード、その時のS素材モンスター、その同名カード):不是回指
NON_REFERENCE_BOUND = ("場合", "時", "中", "後", "他", "度", "まま", "差", "数", "同名")
MODIFIER_TAILS = ("以外",)                                 # そのモンスター以外の…:指示詞只修飾另一張卡
# 其他 類修飾語裡的這些字:那段是帶格助詞/比較的定語子句(そのモンスターが装備可能な…、…と同じカード名),指示詞只修飾
# 另一張卡——片語的指示詞旗標認不出的定語(述語不在詞典)與被 ・ 切到後段的子句由這張表補
CLAUSE_MARKS = ("が", "を", "と", "より", "に記", "に使用")
# 整個字面裡的比較(そのモンスターと同名のXモンスター、そのカードと同じ種類の…):並列切段後比較詞落在後段,從字面補
COMPARE_MARKS = ("と同名", "と同じ", "と異なる", "と違う")
ACTIVATED = ("発動", "した")                                # Xの発動した効果:主人仍是 X
# 限定語:動作(その破壊されたモンスター)也比候選所在的子句;其餘只比候選自己的段
ACTION_QUALIFIERS = ("攻撃", "装備", "破壊", "特殊召喚", "発動", "除外", "戦闘", "無効") \
    + tuple(sorted(word + "召喚" for word in phrases.SUMMON_METHOD_WORDS))   # そのP召喚されたモンスター 的 P召喚
# 中心詞自帶的卡種與召喚法(その効果モンスター、その魔法カード、その儀式魔法カード;召喚法詞是片語的那一份)
HEAD_QUALIFIERS = ("チューナー", "効果", "通常", "魔法", "罠") + tuple(sorted(phrases.SUMMON_METHOD_WORDS))
PLAYER_QUALIFIERS = (PLACE_PLAYER[PLAYER_SELF], PLACE_PLAYER[PLAYER_OPP])   # 其他玩家值不當限定語
TYPED_QUALIFIER_KINDS = (MOD_PLAYER, MOD_SUBTYPE, MOD_POSITION, MOD_RACE, MOD_ATTRIBUTE, MOD_ARCHETYPE)
QUALIFIER_ACTION, QUALIFIER_HEAD, QUALIFIER_MATERIAL = "動作", "卡種", "素材"   # 修飾語類之外的限定語類
GROUP_TAILS = ("同士", "のいずれか")                        # 候選字面的群組尾巴:モンスター同士 → モンスター
GROUP_HEADS = ("いずれか",)                                 # 「X」のいずれか1枚:中心詞是群組詞時目標是 X(字面不改)
LISTING_WORDS = ("と", "及び", "および", "または", "か", "や")   # 並列含此卡(このカードと…)不是只有此卡
OWNER_STOP_PARTICLES = ("p:が", "p:を", "p:は", "p:に", "p:で")   # 主人的「Xの」不跨格助詞
NAME_OPEN = "「"

Reference = namedtuple("Reference", "kind head qualifiers plural within counted")
# 字面片語:句序、起點、選項、字面、前面的 が 片語、「Xが発動した」的 X、詞序列(tuple;主人用)
Phrase = namedtuple("Phrase", "sentence start option text agent activator run")
KIND_TARGETED, KIND_CARD, KIND_EVENT = "targeted", "card", "event"
# 指示詞只修飾另一張卡(reference_of 的回傳之一;patient 的修飾語組)
MODIFIER = "modifier"


def _clean(text):
    return "".join((text or "").split())


def is_demonstrative(text):
    """字面(切區域後的受事者、段、字面片語)是不是指示詞起頭。"""
    text = _clean(text)
    return text in DEMONSTRATIVE_BARE or text.startswith(DEMONSTRATIVE_PREFIXES)


def _strip_demonstrative(text):
    for prefix in DEMONSTRATIVE_PREFIXES:
        if text.startswith(prefix):
            return text[len(prefix):]
    return text


def _is_region_word(word):
    return bool(word) and bool(places.parse_place(word)[1])


def _zone_only(text):
    """整段只是一個區域詞,前面至多一個裸玩家詞(相手の手札、自分フィールド)。"""
    for player in places.BARE_PLAYERS:
        prefix = next((p for p in (player + "の", player) if text.startswith(p)), None)
        if prefix:
            text = text[len(prefix):]
            break
    return any(text == term for term, _ in places.ZONE_TERMS)


def _is_monster_head(head):
    return head.endswith(MONSTER_HEAD_SUFFIXES)


def _is_material(seg):
    """中心詞是素材(X素材)、或素材緊接在中心詞前(融合素材モンスター)。"""
    mods = seg["modifiers"]
    return (seg["head"] or "").endswith(MATERIAL) or bool(mods and mods[-1]["text"] == MATERIAL)


def _event_group(head):
    """中心詞 → 事件組(発動/攻撃/召喚)或 None。"""
    if not head:
        return None
    return EVENT_HEADS.get(head) or (EVENT_SUMMON if head.endswith(SUMMON_SUFFIX) else None)


def _event_of(seg):
    """候選的一段是事件名詞(Xの発動/効果/攻撃/〜召喚、〜召喚成功)→ 事件組 | None。"""
    return _event_group(seg["head"]) or (EVENT_SUMMON if seg["text"].endswith(SUMMON_SUCCESS) else None)


def _plural_count(quantity):
    return bool(quantity and quantity["number"] is not None and quantity["number"] >= 2)


def _segments(ctx, text):
    """沒有現成段的字面(指示詞的主人、字面備援片語、過渡期的字面 API)→ 片語的段清單。"""
    run = ctx.tokenize(text) if text else []
    return [phrases.segment(ctx, chunk) for chunk in phrases.split(ctx, run)] if run else []


def field_reference(ctx, frame, key):
    """框架欄位 → Reference | MODIFIER | None:切區域後的字面(frame[key])要以指示詞起頭(その墓地のモンスター 切成
    所在 その墓地 與對象 モンスター 後,對象不是指示詞)。"""
    literal = _clean(frame.get(key))
    if not is_demonstrative(literal):
        return None
    return reference_of(ctx, _field_segments(ctx, frame, key), literal)


def _field_segments(ctx, frame, key):
    """框架欄位的段:片語結構化已寫在 frame["phrases"];沒有時(手寫框架)把字面切段。"""
    literal = _clean(frame.get(key))
    found = (frame.get("phrases") or {}).get(key)
    if not found:
        return _segments(ctx, literal)
    segments = found["segments"]
    # 段是切區域前的字面(墓地のそのモンスター2体);指示詞在切後的字面開頭時照切後的字面切段
    if segments and is_demonstrative(literal) and not is_demonstrative(segments[0]["text"]):
        return _segments(ctx, literal)
    return segments


def _owner_of(ctx, text, head):
    """字面 → 主人字面 | None:中心詞(合記的 特殊|召喚 佔兩格)前最後一個 の 格之前是主人,の 與中心詞之間只能是
    名詞格(そのモンスターの|攻撃力、相手モンスターの|直接攻撃宣言;このカードを対象とする効果 沒有 の、相手がこの
    カードの効果を無効にする効果 的 の 後有格助詞,都沒有主人);元々の 不是主人(そのモンスターの元々の攻撃力)。"""
    run = ctx.tokenize(text)
    surfaces = [ctx.surface(t) for t in run]
    # 中心詞的格:第一個收在段尾(字面尾、・、並列詞之前)的;モンスターの攻撃力・守備力、モンスターの召喚・特殊召喚 取第一段的
    ends = [i for i in range(len(run)) if "".join(surfaces[:i + 1]).endswith(head)]
    end = next((i for i in ends if i == len(run) - 1 or run[i + 1] == "・" or ctx.coordinates(run, i + 1)),
               ends[-1] if ends else None)
    if end is None:
        return None
    start = end
    while start > 0 and len("".join(surfaces[start:end + 1])) < len(head):
        start -= 1
    if start >= len(ACTIVATED) and tuple(surfaces[start - len(ACTIVATED):start]) == ACTIVATED:
        start -= len(ACTIVATED)
    k = start - 1
    while k >= 0:
        if run[k] == "p:の":
            if k > 0 and surfaces[k - 1].endswith(ORIGINAL):
                k -= 2
                continue
            return "".join(surfaces[:k]) or None
        if not ctx.is_noun_like(run[k]):
            return None
        k -= 1
    return None


def _is_clause(text):
    return any(mark in text for mark in CLAUSE_MARKS)


def _other_modifiers(seg):
    return [m["text"] for m in seg["modifiers"] if m["kind"] == OTHER]


def _tail_count(ctx, text):
    """字面尾的數量(その内の1枚:中心詞 内 之後隔著 の 的數量,段的數量欄沒收)→ Quantity | None。"""
    run = ctx.tokenize(text)
    for i in range(max(0, len(run) - 3), len(run)):
        found = phrases.match_quantity(ctx, run, i)
        if found and found[1] == len(run):
            return found[0]
    return None


# ── 指示詞字面 → Reference ──
def reference_of(ctx, segments, literal=None):
    """受事者片語的段清單(與整個字面)→ Reference;指示詞只修飾另一張卡時 MODIFIER;不是回指(不是指示詞起頭、
    不是卡、另一張實體卡、字面只是此卡)時 None。並列(そのモンスターとこのカード)時回指只關於第一段。"""
    if not segments:
        return None
    seg = segments[0]
    text = seg["text"]
    if not is_demonstrative(text):
        return None
    if literal and any(mark in literal for mark in COMPARE_MARKS):
        return MODIFIER      # そのモンスターと同名のXモンスター、そのカードと同じ種類の手札:比較的對象
    if len(segments) == 1 and text.endswith(THIS_CARD):
        return None          # その場合このカード、〜分このカードの攻撃力:受事者是此卡
    if len(segments) > 1:
        if segments[-1]["head_kind"] not in (HEAD_CARD, HEAD_ATTRIBUTE, HEAD_DEMONSTRATIVE):
            return None      # その攻撃モンスターと対象のモンスターの攻撃力の差分のダメージ:受事者整個不是卡
        for later in segments[1:]:
            if is_demonstrative(later["text"]):
                continue         # そのモンスター及びその同名モンスター:後段自己是另一個指示詞,不影響第一段
            # 被 ・/並列 切到後段的定語子句(…攻撃力を持つ「X」1体):指示詞只修飾另一張卡
            if any(_is_clause(t) for t in _other_modifiers(later)):
                return MODIFIER
        # その召喚・反転召喚・特殊召喚されたモンスター:「・」切開的是定語,指示詞綁的是最後一段的中心詞
        if not seg["modifiers"] and _event_group(seg["head"]) and segments[-1]["head_kind"] == HEAD_CARD:
            seg = dict(segments[-1], demonstrative=True)
    return _reference_segment(ctx, seg, text.startswith(TARGETED_PREFIXES))


def _reference_segment(ctx, seg, targeted):
    head, kind, text = seg["head"], seg["head_kind"], seg["text"]
    if head is None or text.endswith(THIS_CARD):
        return None
    if not seg["demonstrative"]:
        return MODIFIER      # そのモンスターと同じ種族のモンスター:指示詞綁在定語子句裡的另一張卡
    modifiers = seg["modifiers"]
    if targeted and modifiers and modifiers[0]["text"] == TARGET_WORD:
        modifiers = modifiers[1:]
    if kind == HEAD_DEMONSTRATIVE:
        return _demonstrative_reference(ctx, seg, head, text, targeted)
    if kind == HEAD_ATTRIBUTE:
        return _attribute_reference(ctx, seg, head, text, modifiers, targeted)
    if kind != HEAD_CARD or _is_region_word(head):
        return None          # 非卡(その数、そのダメージ)、其他(その場合)、玩家、區域(その手札)
    if any(_strip_demonstrative(t).startswith(NON_REFERENCE_BOUND) or t.endswith(MODIFIER_TAILS) or _is_clause(t)
           for t in _other_modifiers(seg) if not (targeted and t == TARGET_WORD)):
        return MODIFIER      # その同名カード、その場合このカード、その中から…、そのモンスター以外の…、そのモンスターが装備可能な…
    owner = _owner_of(ctx, text, head)
    if owner is not None and not (targeted and owner == TARGET_WORD):
        owner_segments = _segments(ctx, owner)
        owner_seg = owner_segments[0] if owner_segments else None
        if owner_seg is not None:
            owner_head, owner_kind = owner_seg["head"], owner_seg["head_kind"]
            owner_quantity = owner_seg["quantity"] or (_tail_count(ctx, owner) if owner_head == WITHIN else None)
            if owner_head in NON_REFERENCE_BOUND or (owner_kind == HEAD_ATTRIBUTE and owner_head not in EVENT_WORDS):
                return MODIFIER  # その手札のカード、その属性のモンスター:指示詞只修飾另一張卡
            if (owner_kind == HEAD_CARD and not _is_region_word(owner_head)) \
                    or (owner_kind == HEAD_DEMONSTRATIVE and owner_quantity is not None):
                return None      # そのモンスターのX素材/装備カード、その内の1体のX素材:另一張實體卡
    quantity = seg["quantity"]
    return Reference(KIND_TARGETED if targeted else KIND_CARD,
                     TARGET_MONSTER if _is_monster_head(head) else TARGET_CARD,
                     _qualifiers(seg, modifiers), _within(seg) or _plural_count(quantity), _within(seg),
                     quantity is not None)


def _within(seg):
    return seg["head"] == WITHIN or any(_strip_demonstrative(m["text"]) == WITHIN for m in seg["modifiers"])


def _demonstrative_reference(ctx, seg, head, text, targeted):
    """中心詞類 指示詞 的段:それ/それら、その内の1枚、只剩數量的 その2体、この効果の対象。"""
    quantity = seg["quantity"] or (_tail_count(ctx, text) if head == WITHIN else None)
    if quantity and quantity["from_clause"]:
        quantity = None
    if not (head == WITHIN or head in DEMONSTRATIVE_BARE or (quantity and head == quantity["text"])
            or (targeted and head == TARGET_WORD)):
        return None          # その相手モンスターの攻撃対象(另一張實體卡)、その両方、そのいずれか
    target = TARGET_ANY
    if quantity:
        target = TARGET_MONSTER if MONSTER_COUNTER in quantity["text"] else TARGET_CARD
    plural = head == DEMONSTRATIVE_BARE[1] or head == WITHIN or _plural_count(quantity)
    return Reference(KIND_TARGETED if targeted else KIND_CARD, target, _qualifiers(seg, seg["modifiers"]),
                     plural, head == WITHIN, quantity is not None)


def _attribute_reference(ctx, seg, head, text, modifiers, targeted):
    """中心詞類 屬性 的段:跟著主人走(そのモンスターの攻撃力 → そのモンスター);事件詞(発動/効果/攻撃/〜召喚)
    主人是卡時也跟著卡(その魔法カード発動時の効果 也是),否則是效果類;沒有主人的屬性(その攻撃力)指前一個選的卡。"""
    event = _event_group(head)
    activation = text.find(ACTIVATION_TIME + "の") if event else -1
    owner = text[:activation] if activation > 0 else _owner_of(ctx, text, head)
    if owner is not None:
        owner_text = owner
        owner_segments = _segments(ctx, owner_text)
        found = _reference_segment(ctx, owner_segments[0], targeted or owner_text.startswith(TARGETED_PREFIXES)) \
            if owner_segments else None
        if found is not None and found != MODIFIER and found.kind != KIND_EVENT and event in (None, "発動"):
            return found      # そのモンスターの攻撃力/効果 跟著卡;そのモンスターの攻撃 是事件
        if not event:
            return found      # 主人不是卡(その数の…)、或主人是修飾語(そのモンスター以外の…カードの効果)
    if event:
        qualifiers = tuple(q for q in _qualifiers(seg, modifiers) if q[1] not in EVENT_WORDS)
        return Reference(KIND_EVENT, event, qualifiers, False, False, False)
    return Reference(KIND_TARGETED if targeted else KIND_CARD, TARGET_ANY, (), False, False, False)


def _qualifiers(seg, modifiers):
    """段 → 限定語 ((類, 字面)…):玩家、依類比的修飾語、其他類修飾語裡的動作詞、中心詞自帶的卡種。"""
    out = []
    if seg["player"] in PLAYER_QUALIFIERS:
        out.append((MOD_PLAYER, seg["player"]))
    for m in modifiers:
        text = _strip_demonstrative(m["text"])
        if m["kind"] in TYPED_QUALIFIER_KINDS:
            if m["kind"] != MOD_PLAYER or text in PLAYER_QUALIFIERS:
                out.append((m["kind"], text))
        elif m["kind"] == OTHER:
            out.extend((QUALIFIER_ACTION, word) for word in ACTION_QUALIFIERS if word in text)
    head = seg["head"] or ""
    out.extend((QUALIFIER_HEAD, word) for word in HEAD_QUALIFIERS if word in head)
    return tuple(dict.fromkeys(out))


def modifier_of(ctx, segments):
    """受事者片語的段清單 → 指示詞只修飾另一張卡(そのモンスターより…Xモンスター):受事者照自己的字面判。"""
    return reference_of(ctx, segments) == MODIFIER


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


def only_this_card(text):
    """字面只是此卡(帶定語的也算:S召喚したこのカード);並列含此卡的不算。"""
    text = _clean(text)
    return text.endswith(THIS_CARD) and not any(word in text[:-len(THIS_CARD)] for word in LISTING_WORDS)


# ── 候選 ──
# 一個候選:輸出用的字面、目標段 [(字面, 段)…]、各類限定語的值 {類: 集合}、所在的子句字面、組回指值的函式
_Candidate = namedtuple("_Candidate", "text targets qualifiers clause build")


def _target_of(ctx, text, seg):
    """候選的一段 → (目標字面, 目標段):中心詞是屬性或事件名詞時目標是主人(自分のモンスターの攻撃力 →
    自分のモンスター、モンスターの特殊召喚 → モンスター);同士/のいずれか 收尾的去尾;其餘照段。"""
    head = seg["head"]
    if head is None:
        return text, seg
    if seg["head_kind"] == HEAD_ATTRIBUTE or _event_of(seg):
        owner = _owner_of(ctx, text, head)
        if owner is not None:
            found = _segments(ctx, owner)
            return _target_of(ctx, owner, found[0]) if found else (text, seg)   # モンスターの効果の発動 → モンスター
        return text, seg
    for tail in GROUP_TAILS:
        if text.endswith(tail) and len(text) > len(tail):
            found = _segments(ctx, text[:-len(tail)])
            return (text[:-len(tail)], found[0]) if found else (text, seg)
    if head in GROUP_HEADS:
        owner = _owner_of(ctx, text, head)
        found = _segments(ctx, owner) if owner else []
        if found:
            return text, found[0]
    return text, seg


def _candidate(ctx, text, segments, extra_texts, clause, build):
    """候選:目標段與各類限定語的值 {類: 集合}(玩家也從區域/主語字面收;中心詞是素材時卡片子類型不收)。"""
    if segments and all(seg["head_kind"] == HEAD_ATTRIBUTE or _event_of(seg) for seg in segments):
        targets = [_target_of(ctx, text, segments[0])]       # モンスターの召喚・特殊召喚、相手モンスターの攻撃力・守備力:一個目標
    else:
        targets = [_target_of(ctx, seg["text"], seg) for seg in segments]
    values = {kind: set() for kind in TYPED_QUALIFIER_KINDS}
    values[QUALIFIER_HEAD] = set()
    values[QUALIFIER_MATERIAL] = any(_is_material(seg) for _, seg in targets)
    texts = [seg["text"] for seg in segments] + [t for t, _ in targets] + [_clean(t) for t in extra_texts if t]
    for _, seg in targets:
        if seg["player"]:
            values[MOD_PLAYER].add(seg["player"])
        mods = seg["modifiers"]
        for i, m in enumerate(mods):
            # 融合|素材:素材之前的召喚法不算卡片子類型(X素材の無いXモンスター 的後一個 X 仍算)
            if m["kind"] in TYPED_QUALIFIER_KINDS and not (
                    m["kind"] == MOD_SUBTYPE and i + 1 < len(mods) and mods[i + 1]["text"] == MATERIAL):
                values[m["kind"]].add(_strip_demonstrative(m["text"]))
        head = seg["head"] or ""
        if not _is_material(seg):
            values[QUALIFIER_HEAD].add(head)
            values[QUALIFIER_HEAD].update(word for word in HEAD_QUALIFIERS if word in head)
    for extra in extra_texts:
        player = _player(extra)
        if player:
            values[MOD_PLAYER].add(PLACE_PLAYER[player])
    values[QUALIFIER_ACTION] = {word for word in ACTION_QUALIFIERS if any(word in t for t in texts)}
    return _Candidate(text, targets, values, clause, build)


def _qualified(ref, candidate):
    """指示詞的限定語候選都有:玩家、卡種、修飾語依類比字面(融合素材 不算 融合);動作也比候選所在的子句。"""
    values = candidate.qualifiers
    for kind, value in ref.qualifiers:
        if kind == QUALIFIER_ACTION:
            if value not in values[kind] and value not in candidate.clause:
                return False
        elif kind in (MOD_SUBTYPE, QUALIFIER_HEAD):
            if value not in values[MOD_SUBTYPE] and value not in values[QUALIFIER_HEAD]:
                return False
        elif value not in values[kind]:
            return False
    return True


def _segment_fit(ref, seg):
    """目標中心詞 × 候選的一段 → 2 對得上、1 勉強(そのモンスター×カード１枚)、0 不行。"""
    head, kind, quantity = seg["head"], seg["head_kind"], seg["quantity"]
    if quantity and quantity["from_clause"]:
        quantity = None         # 子句裡的數量不是段自己的(相手がランダムに１枚選び 的 相手 不是卡)
    if head is None:
        return 0
    if kind == HEAD_DEMONSTRATIVE:
        # それ、いずれか、両方、只剩數量(モンスターが１体のみの場合 的 1体)不是目標;「X」の内2体 的數量尾說的是怪獸/卡
        if not quantity or head == quantity["text"]:
            return 0
        monster = MONSTER_COUNTER in quantity["text"]
        if not (monster or CARD_COUNTER in quantity["text"]):
            return 0
        return 2 if monster or ref.head != TARGET_MONSTER else 1
    region = _is_region_word(head)
    if ref.within and region and not quantity and _zone_only(seg["text"]):
        return 2                # 相手の手札:整段只是(玩家)區域(自分か相手のEXデッキ、自身の手札・デッキ 不算)
    counted_monster = bool(quantity and MONSTER_COUNTER in quantity["text"])
    counted_card = bool(quantity and CARD_COUNTER in quantity["text"])
    monster = (kind == HEAD_CARD and not region and _is_monster_head(head)) or counted_monster
    card = (kind == HEAD_CARD and not region) or counted_card or (region and quantity is not None)
    if not (monster or card):
        return 0
    if ref.head == TARGET_MONSTER:
        return 2 if monster or head.startswith(NAME_OPEN) else 1
    return 2


def _head_fit(ref, candidate):
    """候選看最後一段(字面的尾巴:このカードとモンスター1体 是怪獸、モンスター1体とカード1枚 是卡);字面只是此卡的不是候選。"""
    if not candidate.targets or (len(candidate.targets) == 1 and only_this_card(candidate.targets[0][0])):
        return 0                # このカードのレベル 的目標是此卡
    segments = [seg for _, seg in candidate.targets]
    while len(segments) > 1 and segments[-1]["quantity"] and segments[-1]["head"] == segments[-1]["quantity"]["text"]:
        segments.pop()          # 通常罠カード3枚または6枚:尾段只剩數量,看前一段
    return _segment_fit(ref, segments[-1])


def _plural_fit(ref, candidate):
    if not ref.plural:
        return True
    counts = [seg["quantity"]["number"] for _, seg in candidate.targets
              if seg["quantity"] and seg["quantity"]["number"] is not None and not seg["quantity"]["from_clause"]]
    return len(candidate.targets) > 1 or any(word in candidate.text for word in LISTING_WORDS) \
        or any(n >= 2 for n in counts) or not counts


def _target_text(ctx, literal, segments):
    """候選欄位的字面 → 目標本身:單段、或各段都是屬性/事件名詞時照第一段取主人(相手モンスターの攻撃力・守備力 →
    相手モンスター、モンスターの効果の発動 → モンスター);群組尾去掉(モンスター同士 → モンスター)。"""
    if segments and (len(segments) == 1
                     or all(seg["head_kind"] == HEAD_ATTRIBUTE or _event_of(seg) for seg in segments)):
        return _target_of(ctx, literal, segments[0])[0]
    if segments and segments[-1]["head_kind"] == HEAD_ATTRIBUTE and not _event_of(segments[-1]):
        last = segments[-1]["text"]
        owner = _owner_of(ctx, last, segments[-1]["head"])
        if owner is not None and literal.endswith(last[len(owner):]):
            return literal[:len(literal) - (len(last) - len(owner))]   # このカード及び…モンスターの攻撃力 → …モンスター
    for tail in GROUP_TAILS:
        if literal.endswith(tail) and len(literal) > len(tail):
            return literal[:-len(tail)]
    return literal


def _value_from_field(ctx, frame, key, literal, segments):
    literal = _target_text(ctx, literal, segments)
    out = {"text": literal, "_targets": [frame]}
    if key == patient_key(frame) and _region(frame):
        out["place"] = _region(frame)
    if key == "object":
        agent = frame.get("subject") or frame.get("topic")
        if agent:
            out["subject"] = agent
    player = _player(out.get("place"), literal)
    if player:
        out["player"] = player
    # 目標的數量只寫在子句裡(モンスターを１体選んで):片語段的 取自子句 數量;全て 不是數量
    quantity = next((seg["quantity"] for seg in segments if seg["quantity"] and seg["quantity"]["from_clause"]), None)
    if quantity and quantity["kind"] != phrases.Q_ALL:
        out["count"] = quantity["text"]
    return dict(out, via=VIA_FIELD)


def _field_candidates(ctx, earlier):
    """往前的框架 → 候選(近的在前);字面是指示詞的用它解到的值(解到底)。回填來的對象與主題
    不算候選:提供它的框架更前面,值相同,數量也寫在那裡。"""
    for frame in reversed(earlier):
        filled = frame.get("backfill") or ()
        clause = _clean(frame.get("clause"))
        for key in ("object", "subject", "topic"):
            if not frame.get(key) or (key != "subject" and key in filled):
                continue
            literal = _clean(frame[key])
            segments = _field_segments(ctx, frame, key)
            ref = field_reference(ctx, frame, key)
            if ref is not None and ref != MODIFIER:
                resolved = frame.get("anaphora")
                if key == patient_key(frame) and resolved:
                    yield _candidate(ctx, resolved["text"], _segments(ctx, resolved["text"]),
                                     (resolved.get("place"), resolved.get("subject")), clause,
                                     lambda r=resolved, f=frame: dict(
                                         r, _targets=[f] + list(f.get("_anaphora_targets") or [])))
                continue
            if ref is None and is_demonstrative(literal):
                continue          # 指示詞但不是卡(その数)、另一張實體卡:不是候選
            yield _candidate(ctx, literal, segments, (_region(frame), frame.get("subject")), clause,
                             lambda f=frame, k=key, v=literal, s=segments: _value_from_field(ctx, f, k, v, s))


def _leading_zone(text, seg):
    """字面片語開頭的區域(自分の墓地のモンスター → 自分の墓地、モンスター):段的第一個區域修飾語,前面至多一個玩家詞。"""
    zone = next((m for m in seg["modifiers"] if m["kind"] == MOD_ZONE), None)
    if zone is None or zone["text"] not in text:
        return None, text
    at = text.index(zone["text"])
    before = text[:at]
    if before and before.rstrip("の") not in places.BARE_PLAYERS:
        return None, text
    end = at + len(zone["text"])
    if end >= len(text) or text[end] != "の" or not text[end + 1:]:
        return None, text
    return text[:end], text[end + 1:]


def _value_from_phrase(ctx, phrase, segments):
    text = phrase.text
    seg = segments[0] if segments else None
    event = seg is not None and _event_of(seg) is not None
    if seg is not None:
        text, seg = _target_of(ctx, text, seg)
        found_place, text = _leading_zone(text, seg)
    else:
        found_place = None
    out = {"text": text, "place": found_place} if found_place else {"text": text}
    # 相手がモンスターの特殊召喚に成功した時:片語是事件時,前面的 が 片語是事件主語
    if event and phrase.agent:
        out["subject"] = phrase.agent
    player = _player(out.get("place"), text, out.get("subject"))
    if player:
        out["player"] = player
    return dict(out, via=VIA_LITERAL)


def _phrase_candidates(ctx, phrase_list, segmented):
    for phrase in reversed(phrase_list):
        segments = segmented[phrase]
        if not segments or is_demonstrative(segments[0]["text"]):
            continue
        yield _candidate(ctx, phrase.text, segments, (), "",
                         lambda p=phrase, s=segments: _value_from_phrase(ctx, p, s))


def _best(ref, fields, phrase_candidates):
    """欄位對得上 → 字面對得上 → 欄位勉強(限定語對不上)→ 字面勉強;同層取最近。"""
    def tier(candidates, strict):
        for candidate in candidates:
            fit = _head_fit(ref, candidate)
            if not fit:
                continue
            # その融合モンスター 不指融合素材モンスター:中心詞是素材時卡種限定語對不上
            material = candidate.qualifiers[QUALIFIER_MATERIAL] and any(kind == MOD_SUBTYPE for kind, _ in ref.qualifiers)
            exact = not material and _qualified(ref, candidate) and _plural_fit(ref, candidate)
            if not strict or (exact and fit == 2):
                return candidate
        return None
    for candidates, strict in ((fields, True), (phrase_candidates, True), (fields, False), (phrase_candidates, False)):
        found = tier(candidates, strict)
        if found:
            return found.build()
    return None


# ── 事件 ──
def _owner_in_run(ctx, run):
    """詞序列裡「Xの攻撃宣言/攻撃/発動/効果」的 X(不跨格助詞:相手がこのカードの効果を… 的主人不是「相手がこのカード」)。"""
    for i, token in enumerate(run):
        if token in OWNER_STOP_PARTICLES:
            return None
        if token == "p:の" and i + 1 < len(run) and ctx.word(run[i + 1]) in OWNER_EVENT_WORDS:
            return "".join(ctx.surface(t) for t in run[:i]) or None
    return None


def _effect_owner(ctx, frame, key):
    """欄位字面是「Xの効果/発動」時的 X,否則字面本身。"""
    literal = _clean(frame.get(key))
    segments = _field_segments(ctx, frame, key)
    if len(segments) == 1 and _event_group(segments[0]["head"]) == "発動":
        owner = _owner_of(ctx, literal, segments[0]["head"])
        if owner is not None:
            return owner
    return literal


def _owner(ctx, tokens, frame):
    """事件框架 → 事件的主人:主語、主題,再來是 Xの効果 的對象,子句詞序列的「Xの」。受身的主語是被
    攻擊、被召喚的那張,不是主人。"""
    passive = frame.get("voice") == "受身" or frame["action"] in TARGETED_EVENTS
    agent_key = None if passive else next((k for k in ("subject", "topic") if frame.get(k)), None)
    if agent_key:
        return _effect_owner(ctx, frame, agent_key)
    if passive:
        return None
    if frame.get("object"):
        owner = _effect_owner(ctx, frame, "object")
        if owner != _clean(frame["object"]):
            return owner
    span = frame.get("span") or (0, 0)
    return _owner_in_run(ctx, tokens[span[0]:span[1]])


def _event_value(text, owner, frame=None):
    out = {"text": text, "_targets": [frame] if frame is not None else []}
    if owner:
        out["subject"] = owner
        player = _player(owner)
        if player:
            out["player"] = player
    return dict(out, via=VIA_EVENT)


def _event_phrase(ctx, phrase):
    """字面片語是事件(Xの発動/効果(の処理)、Xの攻撃(宣言)、〜召喚)→ (事件組, 目標字面);不是 None。
    要有「Xの」主人,光禿禿的 発動(発動できる)不是事件;召喚 例外(特殊召喚に成功した)。"""
    base = phrase.text
    for tail in EVENT_TAILS:
        if base.endswith("の" + tail) and len(base) > len(tail) + 1:
            base = base[:-len(tail) - 1]
            break
    segments = _segments(ctx, base)
    if not segments:
        return None
    head = segments[-1]["head"]
    group = _event_of(segments[-1])
    if group is None or not head:
        return None
    owner = _owner_of(ctx, base, head)
    if owner is None and group != EVENT_SUMMON:
        return None
    text = phrase.text[:-len(PROCESSING_TAIL)] if phrase.text.endswith(PROCESSING_TAIL) else phrase.text
    return group, text


def _event_target(ctx, tokens, ref, earlier, phrase_list):
    wanted, groups = _EVENTS[ref.head]
    events = [f for f in reversed(earlier) if wanted(f["action"])]
    for frame in events:
        if all(value in _clean(frame.get("clause")) for _, value in ref.qualifiers):
            return _event_value(_clean(frame.get("object")) or frame["action"], _owner(ctx, tokens, frame), frame)
    if events:
        return _event_value(_clean(events[0].get("object")) or events[0]["action"], _owner(ctx, tokens, events[0]),
                            events[0])
    # 字面:相手が発動した〜 的主人是相手(activator),否則片語裡「Xの」的 X
    for phrase in reversed(phrase_list):
        if is_demonstrative(phrase.text):
            continue
        found = _event_phrase(ctx, phrase)
        if not found or found[0] not in groups:
            continue
        return _event_value(found[1], phrase.activator or _owner_in_run(ctx, list(phrase.run)))
    return None


def _targeted(ctx, ref, earlier):
    targets = [f for f in earlier if f["action"] in TARGET_ACTIONS and f.get("object")]
    candidates = [c for c in _field_candidates(ctx, targets) if not only_this_card(c.text)]
    for candidate in candidates:
        if _qualified(ref, candidate):
            return dict(candidate.build(), via=VIA_TARGET)
    return dict(candidates[0].build(), via=VIA_TARGET) if candidates else None


def _in_scope(option, other):
    return other is None or other == option


def _phrases_before(phrase_list, frame, option):
    """指示詞之前的字面片語:到子句裡受事者自己那個片語為止,述語前的片語也算在前面。"""
    literal = _clean(frame.get(patient_key(frame)))
    out = []
    for phrase in phrase_list:
        at = (phrase.sentence, phrase.start)
        if at >= (frame["sentence"], frame["span"][1]):
            break
        if at >= (frame["sentence"], frame["span"][0]) and (
                literal.startswith(phrase.text) or phrase.text.startswith(literal)):
            break
        if _in_scope(option, phrase.option):
            out.append(phrase)
    return out


def resolve(ctx, tokens, frames, phrase_list):
    """一個編號效果依原文排序的框架清單(含約束框架;片語結構化已做)、它的詞序列與字面片語(Phrase):
    → 動作框架上就地寫 anaphora 欄;找不到不寫。ctx 是 enrich.Context(切段與中心詞用片語的函式)。"""
    actions = [f for f in frames if f["kind"] == "動作"]
    segmented = {phrase: _segments(ctx, phrase.text) for phrase in phrase_list}
    for k, frame in enumerate(actions):
        key = patient_key(frame)
        if not frame.get(key):
            continue
        ref = field_reference(ctx, frame, key)
        if ref is None or ref == MODIFIER:
            continue
        option = frame.get("option")
        start = (frame["sentence"], frame["span"][0])
        earlier = [f for f in actions[:k] if _in_scope(option, f.get("option"))
                   and (f["sentence"], f["span"][0]) < start]
        before = _phrases_before(phrase_list, frame, option)
        # それを無効にし:無效的是事件,不是剛提到的卡
        if frame["action"] == "無効にする" and _clean(frame[key]) == DEMONSTRATIVE_BARE[0]:
            ref = ref._replace(kind=KIND_EVENT, head=TARGET_ANY)
        if ref.kind == KIND_TARGETED:
            found = _targeted(ctx, ref, earlier)
        elif ref.kind == KIND_EVENT:
            # 魔法カードがその効果を発動した時:主人就是這個框架的主語
            found = ({"text": frame["action"], "subject": _clean(frame["subject"]), "via": VIA_EVENT}
                     if frame.get("subject") and frame["action"] == "発動"
                     else _event_target(ctx, tokens, ref, earlier, before))
        else:
            found = _best(ref, list(_field_candidates(ctx, earlier)), list(_phrase_candidates(ctx, before, segmented)))
        if found:
            # その相手モンスター:指示詞自己寫的玩家優先
            own = next((value for kind, value in ref.qualifiers if kind == MOD_PLAYER), None)
            if own and ref.kind != KIND_EVENT:
                found["player"] = own
            frame["_anaphora_targets"] = found.pop("_targets", [])
            frame["anaphora"] = found
