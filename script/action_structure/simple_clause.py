"""簡單子句:句型、填格(`fill_clause`)與句型模板(`render_clause`)成對放在一起。

其他句型(存在前提、傷害與回復、戰鬥、抽牌、性質變更)都不是時走這裡;動作詞由同義表(`synonyms`)給,
這裡只管各格在句子裡的位置。
- 簡單子句:[誰が][到に][從から|從の|從に存在する][物件](を|が|は)[數量][取對象][原因][時機][形式][從から][到に][受方に]述語
  (物件前的「到に」只在助詞是「が」時:「自分フィールドにモンスターが特殊召喚された」;
  「從」寫在物件後的記 placement 述語前;受方是「相手に見せて」的相手,或物件的回指
  「この効果で特殊召喚したモンスターに装備」;形式「装備魔法カード扱いで、」是裝備時
  到的形式、到本身推得;「Xの効果を発動」的
  「の効果」記進對象線的助詞字面;「「A」または「B」」是兩個卡名的或;
  「EXデッキから特殊召喚された」的「から」是修飾語,不是從)。
  述語字面經同義表(`synonyms`)收成動作詞,語尾決定態與極性;て形串接的多個述語
  (めくられて墓地へ送られた)是多個動作詞。從/到保留含助詞的原文字面(`text`:「墓地の」
  「自分のデッキの上から」「デッキの一番下に」「墓地に存在する」),反向檢查據此還原
  (の/から/に存在する、に/へ 是字面的選擇,結構上都是明寫的從/到)。
- 取對象:舊式「Xを選択して(述語)」、新式「Xを対象として(述語)」把 X 的對象線標 `targeting`,
  字面留在原述語字面的開頭(「選択して破壊する」);述語空的(「Xを選択して発動できる」)是
  發動句的取對象宣告,代價段、沒有動作詞。之後效果段裡指回被點名物件的線(そのモンスター、
  舊式 選択したモンスター)也標取對象。「選択」不是動作詞。
  連用形的「Xを選択し、」「Xを対象とし、」是連用形串接左半的取對象宣告:同一句後面省略的
  物件、沒寫出來的裝備對象(段的受方)指回它;出發地是牌組、手牌的「選択し」是選擇,不標取對象
  (`is_private_selection`)。
- 「選んで」:不另成段,字面留在原述語字面開頭、不標取對象;區域當物件(「自分の手札を
  １枚選んで捨てる」)新建沒有條件的卡物件、從 = 那個區域;對象線加 pick(ランダムに)、count 的
  each(それぞれ/ずつ)與算式(任意の数だけ、〜した数だけ);到的方可為持有者(持ち主の);述語前的
  「〜まで」記期間;句中「、その後」與前一段先後連接。
- 抗性/限制:述語槽開頭可帶攻擊次數/全體與「攻撃を」「効果を」「表示形式を」
  「コントロールは」這幾個含を/は的名詞;「Xの表示形式を」的の是助詞;助詞後的讀點記進助詞字面;
  原因可帶物件(「Xとの戦闘では」「Xの効果を受けない」的 X);「それぞれ１ターンに１度だけ」記 per_turn;
  句型把「が」當助詞切錯而述語解不出時(「〜に１回ずつ攻撃が可能」),整句當主語省略的子句再試。
- 物件切點:物件槽往前吞進前文時(`swallowed_front`),前文由 `clause_front` 先填進段
  (前提、子句前的期間與時機、誰、主語的施事線、名詞前的原因),這裡只解析切點之後的本體;
  「Aと、B」的讀點記在後一條線的 `lead`。模板把主語線寫在誰的位置、子句前的時機寫在最前面。
- 「Xが Yに 攻撃する」:被攻擊的 Y 以「に」標,記成助詞「に」的對象線(同「Yを攻撃する」);
  只在一般句型解析不出時才試,被動的「Yに攻撃された」不收。
- 「〜召喚に成功した」:「モンスターの特殊召喚に成功」的「の」是助詞、「墓地からの特殊召喚に成功」的
  「からの」是從;「この効果で特殊召喚に成功した」主語省略時,被召喚的是原因指向的那一段召喚的物件
  (`cause_phrase.summoned_by`)。對象線的角色照召喚系的根算(`synonyms.is_summon`)。
- 素材:述語前多一格「誰的素材」(`xyz_material.OWNER_SLOT`)——「XをYの下に重ねてX素材とする」
  「XをYのX素材とする」是 成為超量素材,線的到是 Y 的超量素材物件;「XをYのL素材とする場合」是 作為素材,
  Y 記在受方。「Xも融合素材とする事ができる」的「も」是助詞。素材寫在召喚句裡的(「Xを素材としてS召喚する」)
  不走這裡,在 `material_summon`。
- 離場:「フィールドから離れた」的「フィールドから」是述語的一部分(字幹連出發地一起寫),不佔述語前的「從」;
  對象線的從是述語寫明的 場上(明寫、沒有字面),主語另寫了位置(「自分フィールドの〜が」)就用那個位置。
"""

import re

import damage
import draw
import same_different
import xyz_material

from agent_phrase import AGENT_PATTERN, agent_side, fill_agent, render_agent
from block_state import (INFERENCE_TABLE, INTERVAL_PATTERN, INTERVAL_REASON, OBJECT_COUNTER,
                         update_positions)
from cause_phrase import (CAUSE_ALT, EXCLUDE_METHOD_PATTERN, fill_cause, render_cause_phrase,
                          summoned_by)
from clause_front import (PLACEMENT_AFTER_SUBJECT, front_duration, front_timing,
                          render_front_duration, render_front_timing, subject_line)
from condition_atoms import TARGETING_THIS_FORMS
from object_boundary import find_cut
from object_render import render_object, render_ref
from predicate_literal import join_predicate_literal, render_predicate
from quantity import COUNT_PATTERN, FRONT_COUNT_PATTERN, floating_count, render_count
from segment_fields import (CLAUSE_DURATION_PATTERN, DISPLAY_PATTERN, EFFECT_HOLDER_PREFIX,
                            ORDER_PATTERN, PER_TURN_PATTERN, TIMING_PATTERN, TREAT_DELTA_PATTERN,
                            TREAT_PATTERN, is_delayed, parse_cause, parse_duration, parse_per_turn,
                            parse_placement_form, parse_timing, render_display, render_per_turn,
                            render_placement_form, render_timing, resolve_polarity)
from segment_history import declared_earlier, targeted_earlier
from structure_shape import (DISPLAY_WORD, FULLWIDTH_DIGITS, REASON_CLAUSE, REASON_REF,
                             REASON_TWICE, TO_FULLWIDTH_DIGITS, NoTemplate, new_line, position,
                             unparsed, zone, zone_names)
from synonyms import (ACTION_PAST, ATTACK_PREFIX_PATTERN, LEAVE_VERB, ONLY_MARKER,
                      PREDICATE_FROM, PREDICATE_NOUN_PATTERN, SELECT_PREFIX, SUMMON_NOUNS,
                      SUMMON_SUCCESS_AHEAD, TARGETING_PATTERN, TARGET_REF, XYZ_ATTACH_ACTION,
                      action_ancestors, attack_times, is_summon, merged_voice,
                      parse_material_predicates, parse_predicates)
from zone_phrase import (FROM_PARTICLES, SIDE_TEXT, SIDE_WORDS, ZONE_PHRASE, ZONE_PHRASE_RE,
                         parse_from, render_zone_text)


# 受方可以是物件的回指(「この効果で特殊召喚したモンスターに装備できる」),或裝備段的此卡
# (「Xをこのカードに装備する」:被裝上去的 X 是對象線;只收緊接「装備」的,「このカードに１体のみ装備」不收)。
_RECIPIENT_REF = ("(?:この効果で)?(?:その|それらの|" + "|".join(ACTION_PAST.values())
                  + f")(?:モンスター|カード)|{TARGET_REF}(?:モンスター|カード)"
                  + "|このカード(?=に装備)")
# 主語省略的子句(「〜できず、「X」の効果でのみ特殊召喚できる」「〜した場合にEXデッキから特殊召喚できる」):
# 沒有物件與助詞,主語是前一個「は」子句的物件或このカード,對象線標 elided。
# 述語槽開頭可帶攻擊次數/全體(「２回攻撃」「相手モンスター全てに１回ずつ攻撃」)與含「を/は」的
# 名詞(攻撃を、効果を、表示形式を、コントロールは),其餘不收「を」。
_PRED_HEAD = f"(?:{ATTACK_PREFIX_PATTERN})?(?:{PREDICATE_NOUN_PATTERN})?"
# 寫在述語前的「從」(XをデッキからYに加える);「墓地からの特殊召喚に成功した」的「からの」也是從
# ,助詞字面記在 `from2_particle`。「フィールドから離れた」的「フィールドから」是述語的一部分
# (離場的字幹),不是這一格。
_FROM_BEFORE_PREDICATE = (f"(?:(?P<from2>{ZONE_PHRASE})"
                          f"(?P<from2_particle>から(?!{LEAVE_VERB})(?:の{SUMMON_SUCCESS_AHEAD})?))?")
_SUBJECTLESS_RE = re.compile(
    f"^(?P<cause>{CAUSE_ALT})?"
    f"(?P<timing>{TIMING_PATTERN})?"
    f"{_FROM_BEFORE_PREDICATE}"
    f"(?:(?P<to>{ZONE_PHRASE})(?P<to_particle>に|へ))?"
    # 物件省略時到的表示形式照樣寫在述語前(「Xを選択し、表側攻撃表示で特殊召喚する」)。
    f"(?P<display>{DISPLAY_PATTERN})?"
    f"(?P<pred>{_PRED_HEAD}[^を]+)$")
ZONE_AS_OBJECT = "物件"
# 後面(隔著數量)是「〜素材と/に」的述語的位置:「も」當助詞只在這裡認。
ALSO_MATERIAL_AHEAD = "(?=[^を、]*?素材(?:と|に))"
OBJECT_PAUSE = "、"
RANDOM_PICK = "ランダムに"
PICK_RANDOM = "隨機"
# 物件前的「到に」:主語形「自分フィールドにモンスターが特殊召喚された」(助詞が時才有);
# 後接「存在する」的是舊式從的助詞(フィールド上に存在するモンスター),不是到。
_TO_FRONT = f"(?:(?P<to_front>{ZONE_PHRASE})に(?!(?:{DISPLAY_WORD}で)?存在する))?"
_AGENT = (f"(?:(?P<agent>{AGENT_PATTERN})(?P<agent_marker>が|は|(?<=お互い)に)"
          "(?P<agent_pause>、)?)?")
_CLAUSE_PATTERN = (
    f"^{_AGENT}"
    # 寫在主語後、物件前的方法原因(「相手がドロー以外の方法でデッキからモンスターを手札に加えた」)。
    f"(?P<cause_front>{EXCLUDE_METHOD_PATTERN})?"
    f"{_TO_FRONT}"
    f"(?P<count_front>{FRONT_COUNT_PATTERN})?"
    # 物件前的「從」:「EXデッキから特殊召喚されたモンスター」的「から」是修飾語(曾被特殊召喚),
    # 不是這一段的從;「自分フィールドの、「A」または「B」が」的讀點記進從的字面。
    # 舊式「フィールド上に表側表示で存在するX」:表示形式記在從的放置形式。
    f"(?:(?P<from>{ZONE_PHRASE})(?P<from_particle>{'|'.join(FROM_PARTICLES)}"
    f"|に(?P<from_display>{DISPLAY_WORD})で存在する)"
    "(?P<from_pause>、)?(?!特殊召喚され))?"
    # 物件短語裡的「を含む」(カード名に「X」を含む)、「を持つ」(…と同じ数値のレベルを持つ)
    # 不是受詞助詞;述語裡沒有を,所以切錯時會回頭把「を含む」吃進物件短語。
    # 「Xの効果を発動」:物件是 X,「の効果」記進對象線的助詞字面;「「A」または「B」が」的
    # 「または」整個屬於物件短語,裡面的「は」不是助詞。
    # 「Xしか〜できない」:「しか」緊接物件時當助詞,極性只能(`resolve_polarity`);
    # 「〜の効果でしか」「メインフェイズにしか」「手札からしか」的しか接在原因/時機/從後,不是助詞。
    "(?P<objects>(?:を含む|を持つ|または|[^を])+?)(?P<of_effect>の効果)?"
    # 「Xの表示形式を変更」「Xのコントロールは変更」:X 是物件、助詞「の」。
    # 「Xモンスター１体のX召喚を行う」:X 是物件、助詞「の」。
    f"(?P<marker>を|が|は|(?<!で)(?<!に)(?<!から){ONLY_MARKER}"
    f"|の(?=表示形式|コントロール|(?:{'|'.join(SUMMON_NOUNS)})行)"
    # 「モンスターの特殊召喚に成功した」「このカードの召喚に成功した」:物件 + 助詞「の」。
    f"|の{SUMMON_SUCCESS_AHEAD}"
    # 「デッキのモンスターも(１体まで)融合素材とする事ができる」:助詞「も」只在後面是素材的述語時認。
    f"|も{ALSO_MATERIAL_AHEAD})"
    # 助詞後的讀點(「水属性モンスターは、〜」)記進助詞字面。
    "(?P<marker_pause>、)?"
    f"(?P<pick>{RANDOM_PICK})?"
    f"(?P<count>{COUNT_PATTERN})?"
    # 次數限制不記(spec):「「X」は１ターンに１度、〜でのみ特殊召喚できる」的這截進略過文本。
    f"(?P<interval>{INTERVAL_PATTERN})?"
    # 抗性的每回合次數「それぞれ１ターンに１度だけ」:段的 per_turn。
    f"(?P<per_turn>{PER_TURN_PATTERN})?"
    # 取對象字面(舊式 選択して、新式 対象として):單獨出現(述語空)是發動句的取對象宣告。
    f"(?P<targeting>{TARGETING_PATTERN})?"
    f"(?P<cause>{CAUSE_ALT})?"
    f"(?P<timing>{TIMING_PATTERN})?"
    # 到的放置形式(segment_fields.parse_placement_form):順序「好きな順番で」;
    # 卡片種類視同「装備魔法カード扱いで、」是裝備時到的形式(到本身推得)。
    # 「攻撃力３００アップの装備カード扱いで」的增減前綴屬於 treat 字面,另拆一段衍生段。
    f"(?:(?P<treat>(?:{TREAT_DELTA_PATTERN}|{EFFECT_HOLDER_PREFIX})?{TREAT_PATTERN})"
    f"|(?P<order>{ORDER_PATTERN}))?"
    # 「從」也可寫在物件後(XをデッキからYに加える);受方(相手に見せて)緊接述語前。
    f"{_FROM_BEFORE_PREDICATE}"
    f"(?P<count2>{COUNT_PATTERN})?"
    # 「選んで」:字面留在原述語字面開頭、不標取對象;單獨出現是發動句的選取宣告。
    f"(?P<select>{SELECT_PREFIX})?"
    # 述語前的期間:「エンドフェイズまで除外する」。
    f"(?P<duration>{CLAUSE_DURATION_PATTERN})?"
    f"(?:(?P<to>{ZONE_PHRASE})(?P<to_particle>に|へ))?"
    f"(?:(?P<recipient>自分|相手|{_RECIPIENT_REF})に)?"
    # 誰的素材:「そのモンスターの下に(重ねてX素材とする)」「このカードの(X素材とする)」。
    f"{xyz_material.OWNER_SLOT}"
    # 到的表示形式:「〜に表側表示で置く」「表側攻撃表示か裏側守備表示で特殊召喚する」。
    f"(?P<display>{DISPLAY_PATTERN})?"
    # 述語裡的「しか」只能在開頭(「融合召喚でしか特殊召喚できない」);句中出現時回頭讓它當助詞。
    f"(?P<pred>(?:{ONLY_MARKER})?{_PRED_HEAD}(?:(?!{ONLY_MARKER})[^を])*)$")
_CLAUSE_RE = re.compile(_CLAUSE_PATTERN)
# 「このカードを対象とする(Xの)効果が発動した」:物件是效果所屬的卡,修飾語「このカードを
# 対象とする」含を,一般句型會把它切成物件「このカード」+ 述語;另開句型,沒寫 X 時助詞字面是「効果が」。
_OBJECTS_GROUPS = "(?P<objects>(?:を含む|を持つ|または|[^を])+?)(?P<of_effect>の効果)?"
_TARGETING_THIS_CLAUSE_RE = re.compile(_CLAUSE_PATTERN.replace(
    _OBJECTS_GROUPS,
    f"(?P<objects>(?:{'|'.join(TARGETING_THIS_FORMS)})(?:[^を、]+?)?)"
    "(?P<of_effect>の効果|(?<=する)効果)", 1))
# 「Xが Yに 攻撃する」:被攻擊的 Y 以「に」標(同「Yを攻撃する」的 Y),助詞字面記「に」。
# 一般句型先中「が」、把「Yに攻撃する」整截當述語,所以只在那樣解析不出時才用這個句型(`_match_clause`)。
# 被動的「Xが Yに 攻撃された」Y 是攻擊的一方,不是這個讀法,不收。
ATTACK_TARGET_MARKER = "に"
_MARKER_GROUP = slice(_CLAUSE_PATTERN.index("(?P<marker>"), _CLAUSE_PATTERN.index("(?P<marker_pause>"))
_ATTACK_TARGET_CLAUSE_RE = re.compile(
    _CLAUSE_PATTERN[:_MARKER_GROUP.start]
    + f"(?P<marker>{ATTACK_TARGET_MARKER}(?=攻撃(?!され|力|表示|対象)))"
    + _CLAUSE_PATTERN[_MARKER_GROUP.stop:])
# 助詞不是「が」時物件前那截不是到,而是物件修飾的一部分(相手フィールド上にセットされたカード):
# 拿掉「到に」再比一次。
_CLAUSE_NO_TO_FRONT_RE = re.compile(_CLAUSE_PATTERN.replace(_TO_FRONT, "", 1))
# 回指後接數量(「そのカード１枚を相手に見せて」):數量屬於這次提及,記在對象線、placement 物件後。
_REF_COUNT_RE = re.compile("^(?P<phrase>(?:その|それらの)(?:モンスター|カード))(?P<count>[０-９]+(?:体|枚))$")
COUNT_AFTER_OBJECT = "物件後"
# 數量格(spec「數量」:支付 1000LP,段可無物件):「１０００LP」當受詞時不是物件。
# 單位閉集:「LP」與舊式全寫「ライフポイント」,單位字面留在數量格的 `unit`。
AMOUNT_UNITS = ("LP", "ライフポイント")
_AMOUNT_RE = re.compile(f"^(?P<digits>[０-９]+)(?P<unit>{'|'.join(AMOUNT_UNITS)})$")
# 不能取對象的區域(spec 預設 11):「デッキから/手札から〜を選択し、」是選擇,不是取對象宣告——
# 字面一樣留在原述語字面,對象線不標取對象、物件不進被取對象的清單。只收連用形的「選択し」;
# 「選択して」照取對象字面判。
PRIVATE_ZONES = ("牌組", "手牌", "額外牌組")
SELECTION_LITERAL = "選択し"
EQUIP_ACTION = "裝備"
REASON_FROM = "從解析不出"
REASON_TO = "到解析不出"
REASON_DISPLAY = "表示形式沒有到"


def split_objects(phrase):
    """以「と」切物件,但「」裡的と、「X」と名のついた 的と(字段的舊式寫法)、「このカードを対象とする」
    的と不算;後面接比較的と(「そのモンスターとはカード名が異なる〜」)是修飾語的一部分。"""
    parts, depth, buf = [], 0, ""
    for i, ch in enumerate(phrase):
        if ch == "「":
            depth += 1
        elif ch == "」":
            depth -= 1
        if (ch == "と" and depth == 0
                and not phrase.startswith(("と名のついた", "と同じ", "とする"), i)
                and not same_different.compares_after(phrase, i)):
            parts.append(buf)
            buf = ""
        else:
            buf += ch
    parts.append(buf)
    return [p for p in parts if p]


def _segment_by_id(state, seg_id):
    """已抽出的段(自己的區塊與前面的區塊)裡找 id。"""
    return next(seg for block in (state.block, *state.card["blocks"])
                for seg in block["segments"] if seg["id"] == seg_id)


def is_private_selection(literal, zones):
    """取對象字面其實是選擇:「選択し」而且明寫的出發地含牌組、手牌或額外牌組。
    抽取與模板共用這一把尺(`zones` 是明寫的從的區域列,沒寫是 None)。"""
    return literal == SELECTION_LITERAL and any(z["zone"] in PRIVATE_ZONES for z in zones or ())


def _placed_on_card(obj):
    """計數器放在卡上(「対象のモンスターにフォッグカウンターを置く」),不在任何區域:
    推得表的「放置 → 魔陷區」不適用。卡能放到別張卡上的只有計數器,所以只看物件種類。"""
    return obj.get("kind") == OBJECT_COUNTER


def _clause_predicate(m):
    """句型比對結果 → (述語字面, 到的短語, 解析結果或 None, 原因);「墓地へ送る」「手札に加える」的
    到在述語裡:先試整串當述語。"""
    g = m.groupdict().get
    pred, to_phrase, parsed, reason = g("pred"), g("to"), None, None
    if to_phrase:
        parsed, _ = parse_predicates(to_phrase + g("to_particle") + pred)
        if parsed is not None:
            pred, to_phrase = to_phrase + g("to_particle") + pred, None
    if parsed is None and pred:
        # 述語前寫了「Yの」(「このカードのX素材とする」)時,所屬的「の」接回去再查同義表。
        parsed, reason = parse_material_predicates(
            pred, xyz_material.is_owned(g("material_owner"), g("under")))
    return pred, to_phrase, parsed, reason


def _has_own_destination(m):
    """述語那邊自己寫了到(述語前的「Yに」,或述語本身寫明終點的「墓地へ送られた」):物件前的「〜に」就不是到,
    是物件修飾的一部分(「魔法＆罠ゾーンにセットされたこのカードが墓地へ送られた」)。"""
    _, to_phrase, parsed, _ = _clause_predicate(m)
    return bool(to_phrase) or any(p.to for p in parsed or ())


def _match_clause(clause_text):
    """簡單子句的句型比對(物件 + 助詞 + 述語);不是這個句型回 None。"""
    m = _TARGETING_THIS_CLAUSE_RE.match(clause_text) or _CLAUSE_RE.match(clause_text)
    if m and m.group("to_front") and (m.group("marker") != "が" or _has_own_destination(m)):
        m = _CLAUSE_NO_TO_FRONT_RE.match(clause_text)
    if m and m.group("marker") != "の" and parse_cause(m.group("objects") + m.group("marker")):
        # 「戦闘では破壊されない」:「戦闘で」+「は」是原因字面,不是物件 + 助詞;主語省略。
        m = None
    if m is None or (m.group("pred") and _clause_predicate(m)[2] is None):
        # 物件前的數量算式(「〜の数まで」)什麼字面都收,會把主語吞進去:這個句型不收它。
        attack = _ATTACK_TARGET_CLAUSE_RE.match(clause_text)
        if attack and not attack.group("count_front") and _clause_predicate(attack)[2] is not None:
            return attack
    return m


def swallowed_front(state, clause_text):
    """句型的物件槽往前吞進了多少不屬於物件的字面(從子句開頭起算的字數;0 = 沒有)。
    物件短語照現有規則認得全就不找(`BlockState.parses_cleanly`);切點在 `object_boundary.find_cut`。"""
    m = _match_clause(clause_text)
    if not m or not (m.group("pred") or m.group("targeting") or m.group("select")):
        return 0
    phrases = split_objects(m.group("objects"))
    if not phrases or state.parses_cleanly(phrases[0]):
        return 0
    cut = find_cut(phrases[0])
    # 切完剩下的要像個受詞(有頭名詞的物件短語、此卡、回指、超量素材…,或當受詞的區域、數量);
    # 「以下の効果から１つ」這種本來就不是物件的不切。
    rest = phrases[0][cut:]
    if not cut or not (state.names_object(rest) or _AMOUNT_RE.match(rest)
                       or (ZONE_PHRASE_RE.match(rest) and parse_from(rest))):
        return 0
    return m.start("objects") + cut


def fill_clause(ctx, clause_text):
    """把簡單子句解析進段;失敗就在段上標原因。`ctx.inherited_timing` 是連用形串接(同時)的前一段的
    時機:「次のスタンバイフェイズに戻り、その攻撃力は〜になる」的第二段同一時點。
    主語省略的子句(「〜できず、「X」の効果でのみ特殊召喚できる」「〜場合にEXデッキから特殊召喚できる」)
    的物件是本句「Xは」的物件或このカード,對象線標 `elided`。
    段上可能已有子句前文填好的格(`clause_front`:誰、原因、時機、主語的對象線),同一格兩處都寫就不猜。"""
    seg, state, sentence_start = ctx.seg, ctx.state, ctx.sentence_start
    kind = ctx.kind
    m = _match_clause(clause_text)
    elided = None
    if not m or not (m.group("pred") or m.group("targeting") or m.group("select")):
        m = _SUBJECTLESS_RE.match(clause_text)
        if not m or not m.group("pred"):
            seg["unparsed"] = unparsed(REASON_CLAUSE)
            return
        elided = state.elided_subject()
        if elided is None:
            seg["unparsed"] = unparsed(REASON_REF)
            return
        pred, to_phrase, parsed, reason = _clause_predicate(m)
    else:
        pred, to_phrase, parsed, reason = _clause_predicate(m)
        whole = _SUBJECTLESS_RE.match(clause_text) if parsed is None and pred else None
        if whole and whole.group("pred"):
            # 句型把述語前的「が」當助詞切錯時(「〜に１回ずつ攻撃が可能」):整句當主語省略的子句
            # 述語解析得出才改用它。
            retry = _clause_predicate(whole)
            if retry[2] is not None:
                elided = state.elided_subject()
                if elided is None:
                    seg["unparsed"] = unparsed(REASON_REF)
                    return
                m, (pred, to_phrase, parsed, reason) = whole, retry
    g = m.groupdict().get
    targeting = g("targeting")
    to_front = g("to_front")
    if xyz_material.attaches_without_owner(parsed, pred, kind):
        parsed, reason = parse_material_predicates(pred, True)
    seg["predicate"] = join_predicate_literal(targeting, g("select"), pred)
    if parsed is None and pred:
        seg["unparsed"] = unparsed(reason)
        return
    if parsed and any(p.action == damage.RECOVER_ACTION for p in parsed):
        seg["unparsed"] = unparsed(REASON_CLAUSE)
        return
    if parsed is None:
        # 發動句的取對象宣告(「Xを選択して発動できる」):沒有動作詞,只把物件標成取對象。
        parsed = []
    seg["actions"] = [p.action for p in parsed]
    seg["voice"] = merged_voice(parsed)
    marker = None if elided else (g("of_effect") or "") + g("marker") + (g("marker_pause") or "")
    seg["times"] = attack_times(pred)
    if parsed:
        seg["polarity"], seg["optional"] = resolve_polarity(parsed, marker)
    written_to = next((p.to for p in reversed(parsed) if p.to), None)
    # 述語本身寫明的出發地(「フィールドから離れた」)。
    written_from = next((PREDICATE_FROM[p.action] for p in parsed if p.action in PREDICATE_FROM),
                        None)
    if g("agent"):
        reason = fill_agent(seg, state, g("agent"), g("agent_marker"), g("agent_pause"), kind)
        if reason:
            seg["unparsed"] = unparsed(reason)
            return
    agent = seg["agent"]
    if g("recipient") in SIDE_WORDS:
        seg["recipient"] = SIDE_WORDS[g("recipient")]
    elif g("recipient"):
        # 受方是物件的回指(裝備的對象):{"object", "ref"},找不到就整段標原因。
        obj_id, ref, reason = state.object_at(g("recipient"), sentence_start)
        if obj_id is None:
            seg["unparsed"] = unparsed(reason)
            return
        seg["recipient"] = {"object": obj_id, "ref": ref}
    elif EQUIP_ACTION in seg["actions"] and not elided and state.declared_object() is not None:
        # 「Xを対象とし、このカードを装備魔法カード扱いで装備する」:沒寫出來的裝備對象
        # 是左半宣告的物件;模板不寫字面。
        seg["recipient"] = {"object": state.declared_object(), "ref": None, "elided": True}
    if g("cause") and g("cause_front"):
        seg["unparsed"] = unparsed(REASON_TWICE)
        return
    if g("cause") or g("cause_front"):
        reason = fill_cause(seg, state, g("cause") or g("cause_front"), sentence_start,
                            seg["actions"], "名詞前" if g("cause_front") else None)
        if reason:
            seg["unparsed"] = unparsed(reason)
            return
        if elided and seg["cause"].get("segment"):
            # 主語省略的「この効果で特殊召喚に成功した」:被召喚的是那一段召喚的物件,不一定是此卡。
            elided = summoned_by(_segment_by_id(state, seg["cause"]["segment"]))
            if elided is None:
                seg["unparsed"] = unparsed(REASON_REF)
                return
    if g("per_turn"):
        seg["per_turn"] = parse_per_turn(g("per_turn"))
    if g("interval"):
        state.omit(m.start("interval") + sentence_start, g("interval"), INTERVAL_REASON)
    if g("duration"):
        if seg["duration"] is not None:
            seg["unparsed"] = unparsed(REASON_TWICE)
            return
        seg["duration"] = parse_duration(g("duration"))
    if g("timing"):
        if seg["timing"] is not None:
            seg["unparsed"] = unparsed(REASON_TWICE)
            return
        seg["timing"] = parse_timing(g("timing"))
    elif seg["timing"] is None:
        ctx.inherit_timing()
    # 延遲段(次のスタンバイフェイズに、序列中段的條件段之後)指回被點名物件的線不標取對象。
    targetable = kind == "效果" and not is_delayed(seg)
    if (isinstance(seg["recipient"], dict) and targetable
            and seg["recipient"]["object"] in state.targeted):
        # 受方是被取對象的物件(裝備對象):與對象線同一把尺標取對象,查詢「只看取對象」時算。
        seg["recipient"]["targeting"] = True
    from_zones = None
    # 「從」寫在物件後(XをデッキからYに加える)記 placement 述語前,模板放回原位。
    from_text, from_placement = None, "名詞前"
    if g("from"):
        from_text = g("from") + g("from_particle") + (g("from_pause") or "")
    elif g("from2"):
        from_text, from_placement = g("from2") + g("from2_particle"), "述語前"
    if from_text:
        from_zones = parse_from(g("from") or g("from2"))
        if from_zones is None:
            seg["unparsed"] = unparsed(REASON_FROM)
            return
    to_zones, to_text = None, None
    if to_phrase:
        to_zones, to_text = parse_from(to_phrase), to_phrase + g("to_particle")
    elif to_front:
        to_zones, to_text = parse_from(to_front), to_front + "に"
    if to_text and to_zones is None:
        seg["unparsed"] = unparsed(REASON_TO)
        return
    inferred_from, inferred_to = (None, None)
    if len(parsed) == 1:
        # 推得表照上位詞查:融合召喚沒寫「到」也是場上。
        inferred_from, inferred_to = next(
            (INFERENCE_TABLE[a] for a in action_ancestors(seg["actions"][0])
             if a in INFERENCE_TABLE), (None, None))
    # 推得的場上/墓地歸誰:特殊召喚(含下位詞)到施事者的場上;其餘不知道就不標方。
    summoning = any("特殊召喚" in action_ancestors(a) for a in seg["actions"])
    inferred_side = (agent_side(agent) or "我方") if summoning else None
    written_counts = [(g(group), placement) for group, placement in
                      (("count", None), ("count2", "述語前"), ("count_front", "名詞前"))
                      if g(group)]
    if len(written_counts) > 1:
        seg["unparsed"] = unparsed(REASON_TWICE)
        return
    count = floating_count(*written_counts[0]) if written_counts else None
    amount = _AMOUNT_RE.match(g("objects") or "")
    if amount:
        # 「１０００LPを払って」:數量格,段無物件。
        seg["amount"] = {"text": g("objects"),
                         "value": int(amount.group("digits").translate(FULLWIDTH_DIGITS)),
                         "unit": amount.group("unit")}
        return
    if g("display") and not (to_zones or written_to or inferred_to):
        seg["unparsed"] = unparsed(REASON_DISPLAY)
        return
    attached, owner_new = None, []
    if g("material_owner") or g("under") or XYZ_ATTACH_ACTION in seg["actions"]:
        # 誰的素材:成為超量素材的到是 Y 的超量素材物件;作為素材的 Y 記在受方。
        if to_text:
            seg["unparsed"] = unparsed(REASON_TWICE)
            return
        known = list(state.recent)
        attached = xyz_material.fill_owner(seg, state, g("material_owner"), g("under"),
                                           sentence_start + m.start("pred"), sentence_start)
        if seg["unparsed"]:
            return
        # 所屬(Y)是這一句才建的物件時,寫在它前面的 X 的回指(「そのカードを…XモンスターのX素材とする」)
        # 不能指到它:解 X 的時候先拿掉,解完照原文順序放回去。
        owner_new = [i for i in state.recent if i not in known]
    phrases = [None] if elided else split_objects(g("objects"))
    zone_object = (not elided and from_text is None and len(phrases) == 1
                   and (g("of_effect") or "") + g("marker") == "を"
                   and ZONE_PHRASE_RE.match(phrases[0]) and parse_from(phrases[0]))
    if zone_object:
        from_zones, from_text, from_placement = zone_object, phrases[0], ZONE_AS_OBJECT
    marks_targeting = bool(targeting) and not is_private_selection(targeting, from_zones)
    for phrase in phrases:
        # 「Aと、B」:「と」後的讀點記在後一條線(`lead`),不屬於 B 的物件短語。
        lead = OBJECT_PAUSE if (phrase or "").startswith(OBJECT_PAUSE) else None
        if lead:
            phrase = phrase[len(lead):]
        ref_count = _REF_COUNT_RE.match(phrase or "")
        if ref_count and (count is not None or len(phrases) > 1 or state.object_at(
                ref_count.group("phrase"), sentence_start)[0] is None):
            ref_count = None
        if ref_count:
            phrase = ref_count.group("phrase")
            count = floating_count(ref_count.group("count"), COUNT_AFTER_OBJECT)
        if phrase is None:
            obj_id, ref = elided, None
        elif zone_object:
            obj_id, ref = state.zone_object(phrase, sentence_start), None
        else:
            owner_from = ((g("from"), from_zones)
                          if g("from") and from_placement == "名詞前" else None)
            state.recent = [i for i in state.recent if i not in owner_new]
            obj_id, ref, reason = state.object_at(phrase, sentence_start, owner_from)
            state.recent.extend(owner_new)
            if obj_id is None:
                seg["unparsed"] = unparsed(reason)
                return
        if attached is not None and xyz_material.owner_of(state, attached()) == obj_id:
            # 所屬卡的回指只找得到被疊的這張卡自己(它真正指的物件修飾語認不得):指回的物件找不到。
            seg["unparsed"] = unparsed(REASON_REF)
            return
        obj = state.find(obj_id)
        if count is not None and count.get("cmp") == "全部" and obj["source"]["kind"] == "子集":
            obj["source"]["select"] = "全部"
        # 角色照召喚系的根算:召喚、反轉召喚與通常召喚的對象也是被召喚的那一方。
        role = "被召喚" if any(is_summon(a) for a in seg["actions"]) else "受事"
        if marks_targeting:
            state.targeted.append(obj_id)
        # 取對象標記:這一句點名的,或效果段裡指回先前被點名的物件(そのモンスター、選択したモンスター)。
        line = new_line(obj_id, role,
                        targeting=marks_targeting or (targetable
                                                      and obj_id in state.targeted),
                        marker=marker, ref=ref, count=count)
        if g("pick"):
            line["pick"] = PICK_RANDOM
        if lead:
            line["lead"] = lead
        if phrase is None:
            line["elided"] = True
        elif marker.rstrip("、") == "は" and len(phrases) == 1:
            state.subject = obj_id
        if from_zones is not None:
            line["from"] = position(
                from_zones, "明寫", text=from_text,
                form=g("from_display") and parse_placement_form(
                    display_literal=g("from_display") + "で"))
            if from_placement != "名詞前":
                line["from"]["placement"] = from_placement
            if obj["source"]["kind"] == "新建" and obj["initial_position"] is None:
                obj["initial_position"] = list(from_zones)
        elif written_from:
            line["from"] = position([zone(written_from, None)], "明寫")
        else:
            current = state.current_position(obj_id)
            if current is not None:
                line["from"] = position(current["zones"], "繼承",
                                        inferred=current["inferred"])
            elif seg["actions"] == [draw.DRAW_ACTION]:
                # 「相手がこのカードをドローした時」:推得的牌組照抽牌者標方。
                line["from"] = position(draw.inferred_deck(agent_side(agent)), "推得",
                                        inferred=True)
            elif inferred_from:
                side = "我方" if inferred_from == "手牌" else None
                line["from"] = position([zone(inferred_from, side, side and "預設")],
                                        "推得", inferred=True)
        form = parse_placement_form(g("treat"), g("order"), g("display"))
        if attached is not None:
            line["to"] = attached()
        elif to_zones is not None:
            line["to"] = position(to_zones, "明寫", text=to_text,
                                  form=form)
            if to_front:
                line["to"]["placement"] = "名詞前"
        elif written_to:
            line["to"] = position([zone(written_to, None)], "明寫", form=form)
        elif inferred_to and not _placed_on_card(obj):
            line["to"] = position([zone(inferred_to, inferred_side,
                                        inferred_side and "預設")], "推得",
                                  inferred=True, form=form)
        seg["lines"].append(line)
        if obj_id != state.self_id and obj_id not in state.recent:
            state.recent.append(obj_id)
        state.acted.setdefault(obj_id, []).extend(seg["actions"])
    if not parsed:
        state.declare([line["object"] for line in seg["lines"]])
    update_positions(seg, state)
    state.note_actions(seg)


def render_from(lines, predicate_from=None):
    """所有對象線共用一個明寫的「從」才有字面 → (字面, 寫在物件前還是述語前);
    繼承、推得的不寫。`predicate_from` 是述語本身寫明的出發地(「フィールドから離れた」的場上):
    每條線的從都要是明寫、落在那個區域裡;沒有自己字面的從就是述語寫的那一個,不另寫。"""
    if predicate_from:
        for line in lines:
            pos = line["from"] or {}
            if pos.get("source") != "明寫" or not all(
                    predicate_from in zone_names(z["zone"]) for z in pos["zones"]):
                raise NoTemplate("對象線的從與述語寫明的出發地不一致")
        lines = [line for line in lines if line["from"].get("text")]
    written = [line["from"] for line in lines
               if line["from"] and line["from"]["source"] == "明寫" and not _is_zone_object(line)]
    if not written:
        return "", "名詞前"
    if len(written) != len(lines) or any(w != written[0] for w in written):
        raise NoTemplate("對象線的從不一致")
    return render_zone_text(written[0], "から"), written[0].get("placement") or "名詞前"


def _is_zone_object(line):
    return bool(line["from"]) and line["from"].get("placement") == ZONE_AS_OBJECT


def _render_zone_object(line, obj):
    """區域當物件(「自分の手札を１枚選んで捨てる」):物件是新建、條件同頭名詞カード、沒有物件數量,
    字面是「從」的區域短語(先驗過與區域一致)。"""
    pos = line["from"]
    if (obj["source"]["kind"] != "新建" or obj["condition"] != {"op": "大類", "value": "卡"}
            or obj["count"] or obj["unparsed"] or line["ref"] or pos["source"] != "明寫"
            or not pos.get("text") or parse_from(pos["text"]) != pos["zones"]):
        raise NoTemplate("區域當物件無模板")
    return pos["text"]


def _render_to(lines, predicate_to):
    """明寫、不在述語裡的「到」(「デッキの一番下に」)與到的放置形式 →
    (形式字面, 區域字面, 區域寫在物件前還是述語前, 表示形式字面)。
    「自分フィールドにモンスターが特殊召喚された」的到在物件前(placement 名詞前),其餘在述語前。
    形式字面(treat、order,`render_placement_form`)照句型槽寫在述語前的「從」之前(「魔法カード扱いで
    手札から魔法＆罠ゾーンにセットできる」);到是推得或在述語裡時只寫形式(「装備魔法カード扱いで、
    〜に装備できる」)。表示形式不論到怎麼來都寫在述語前,由呼叫端接在述語前。"""
    displays = {render_display(line["to"].get("form")) for line in lines if line["to"]}
    forms = {render_placement_form(line["to"].get("form")) for line in lines if line["to"]}
    if len(displays) > 1 or len(forms) > 1:
        raise NoTemplate("對象線的到不一致")
    display = displays.pop() if displays else ""
    form = forms.pop() if forms else ""
    written = [line["to"] for line in lines
               if line["to"] and line["to"]["source"] == "明寫"]
    if not written or predicate_to:
        if form and predicate_to:
            raise NoTemplate("到的形式無模板")
        return form, "", "述語前", display
    if len(written) != len(lines) or any(w != written[0] for w in written):
        raise NoTemplate("對象線的到不一致")
    return (form, render_zone_text(written[0], "に"),
            written[0].get("placement") or "述語前", display)


def _render_recipient(recipient, seg, card, objects, names, self_id):
    """受方:我方/對手寫「自分に/相手に」;物件的回指(裝備的對象)照回指字面;裝備到此卡寫「このカードに」;
    作為素材的受方(要召喚的怪獸)寫物件 +「の」。"""
    if isinstance(recipient, dict):
        if recipient.get("particle"):
            return xyz_material.render_recipient_of(recipient, seg, card, objects, names, self_id)
        obj = objects.get(recipient.get("object"))
        if obj is not None and recipient.get("elided"):
            # 沒寫出來的裝備對象:要是本區塊先前的宣告段點名過的物件。
            if recipient.get("ref") or not declared_earlier(obj["id"], seg, card):
                raise NoTemplate("省略的受方無模板")
            return ""
        if obj is not None and not recipient.get("ref") and recipient["object"] == self_id:
            return render_object(obj, seg, card, names, self_id=self_id) + "に"   # 裝備到此卡
        if obj is None or not recipient.get("ref"):
            raise NoTemplate("受方的物件找不到")
        return render_ref(recipient["ref"], obj, seg, card) + "に"
    if recipient not in SIDE_TEXT:
        raise NoTemplate(f"受方無模板:{recipient}")
    return SIDE_TEXT[recipient] + "に"


def render_clause(t):
    """簡單子句模板:[誰が][到に][數量(名詞前)][從から|の|に存在する][物件|區域][助詞][ランダムに][數量][取對象][原因][時機][形式][從から][數量(述語前)][選んで][期間][到に][受方に][表示形式]述語
    (物件前的「到に」只在助詞是「が」時;「從」只在物件前或述語前其中一處,照 placement;
    時機只寫有字面的延遲;期間是段的句中期間 `t.inner_duration`,反向檢查驗過是述語前寫得出的字面)。
    取對象線只有兩種寫得出:這一段的述語帶取對象字面(每條線都標),或這一條線指回
    本區塊先前被取對象字面點名的物件(その/選択したモンスター)。"""
    seg, card, objects, names, self_id = t.seg, t.card, t.objects, t.names, t.self_id
    parts = []
    timing_front = front_timing(seg["timing"])
    if timing_front:
        parts.append(render_front_timing(seg["timing"]))
    if seg["agent"] is not None:
        parts.append(render_agent(seg["agent"], seg, card))
    # 主語的對象線(角色施事:「このカードが戦闘によって相手モンスターを破壊した」的このカード)寫在
    # 誰的位置,助詞照線上記的;其餘的線才是物件槽的線。
    subject = subject_line(seg)
    lines = [line for line in seg["lines"] if line is not subject]
    if subject is not None:
        parts.append(render_object(objects[subject["object"]], seg, card, names, subject,
                                   self_id=self_id) + subject["marker"])
    if front_duration(seg["duration"]) == PLACEMENT_AFTER_SUBJECT:
        # 寫在誰/主語後的期間(「相手はダメージステップ終了時まで魔法・罠カードを発動できない」)。
        if subject is None and seg["agent"] is None:
            raise NoTemplate("期間無模板:主語後")
        parts.append(render_front_duration(seg["duration"]))
    cause_front = bool(seg["cause"]) and seg["cause"].get("placement") == "名詞前"
    if cause_front:
        parts.append(render_cause_phrase({k: v for k, v in seg["cause"].items() if k != "placement"},
                                         seg, card, objects, names, self_id))
    # 主語省略的線不寫物件與助詞;其餘線的助詞要一致。
    spoken = [line for line in lines if not line.get("elided")]
    if len(spoken) != len(lines) and len(lines) != 1:
        raise NoTemplate("主語省略的段只能有一條線")
    markers = {line["marker"] or "を" for line in spoken}
    if len(markers) > 1:
        raise NoTemplate("對象線的助詞或數量不一致")
    marker = markers.pop() if markers else None
    # 誰的素材:成為超量素材的所屬格,或作為素材的受方「Yの」;兩者都寫在述語前。
    owner_text = xyz_material.render_owner(seg, lines, card, objects, names, self_id)
    recipient_text = ""
    if seg["recipient"] is not None:
        recipient_text = _render_recipient(seg["recipient"], seg, card, objects, names, self_id)
    attached = any(map(xyz_material.is_attached, lines))
    owned = xyz_material.is_owned(attached or recipient_text.endswith(xyz_material.RECIPIENT_OF),
                                  owner_text.endswith(xyz_material.STACK_UNDER))
    targeting_text, select_text, predicate, predicate_to = render_predicate(seg, marker, owned)
    words, counts, picks = [], set(), set()
    if seg["amount"]:
        # 數量格(「１０００LPを払って」):段無物件,數量當受詞寫。
        if lines or seg["amount"].get("unit") not in AMOUNT_UNITS \
                or not isinstance(seg["amount"].get("value"), int):
            raise NoTemplate("數量無模板")
        words.append(str(seg["amount"]["value"]).translate(TO_FULLWIDTH_DIGITS)
                     + seg["amount"]["unit"])
        counts.add(("", None))
        marker = "を"
    for line in spoken:
        written_from = line["from"]["zones"] if (line["from"] or {}).get("source") == "明寫" else None
        selects = is_private_selection(targeting_text, written_from)
        if targeting_text and not selects and not line["targeting"]:
            raise NoTemplate("取對象字面下有線沒標取對象")
        if line["targeting"] and (selects or not targeting_text) and not (
                line["ref"] and targeted_earlier(line["object"], seg, card)):
            raise NoTemplate("取對象線無模板")
        if line["role"] not in ("受事", "被召喚"):
            raise NoTemplate(f"角色無模板:{line['role']}")
        if _is_zone_object(line):
            words.append(_render_zone_object(line, objects[line["object"]]))
        else:
            words.append(render_object(objects[line["object"]], seg, card, names, line,
                                       self_id=self_id))
        if line.get("lead"):
            if line["lead"] != OBJECT_PAUSE or len(words) < 2:
                raise NoTemplate("對象線前的讀點無模板")
            words[-1] = line["lead"] + words[-1]
        counts.add((render_count(line["count"]), (line["count"] or {}).get("placement")))
        picks.add(line.get("pick"))
    if len(counts) > 1 or len(picks) > 1:
        raise NoTemplate("對象線的助詞或數量不一致")
    count_text, count_placement = counts.pop() if counts else ("", None)
    pick = picks.pop() if picks else None
    if pick not in (None, PICK_RANDOM):
        raise NoTemplate(f"選法無模板:{pick}")
    if attached:
        to_form, to_text, to_placement, display = "", "", "述語前", ""
    else:
        to_form, to_text, to_placement, display = _render_to(lines, predicate_to)
    from_text, from_placement = render_from(
        lines, next((PREDICATE_FROM[a] for a in seg["actions"] if a in PREDICATE_FROM), None))
    # 物件前的到(自分フィールドにモンスターが特殊召喚された)照 placement 放回。
    if to_placement == "名詞前":
        parts.append(to_text)
    if count_placement == "名詞前":
        parts.append(count_text)
    if from_placement == "名詞前":
        parts.append(from_text)
    if count_placement == COUNT_AFTER_OBJECT:
        if len(words) != 1:
            raise NoTemplate("對象線的助詞或數量不一致")
        words[0] += count_text
    if words:
        parts.append("と".join(words) + marker)
    parts.append(RANDOM_PICK if pick else "")
    if count_placement is None:
        parts.append(count_text)
    parts.append(render_per_turn(seg["per_turn"]))
    parts.append(targeting_text or "")
    if seg["cause"] and not cause_front:
        parts.append(render_cause_phrase(seg["cause"], seg, card, objects, names, self_id))
    if not timing_front:
        parts.append(render_timing(seg["timing"]))
    parts.append(to_form)
    if from_placement == "述語前":
        parts.append(from_text)
    if count_placement == "述語前":
        parts.append(count_text)
    parts.append(select_text or "")
    parts.append(t.inner_duration["text"] if t.inner_duration else "")
    if to_placement == "述語前":
        parts.append(to_text)
    parts.append(recipient_text)
    parts.append(owner_text)
    parts.append(display)
    parts.append(predicate)
    return "".join(parts)
