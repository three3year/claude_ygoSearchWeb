"""段抽取:一個區塊的原文 → 段(扁平)+ 段樹 + 物件(寫進整卡共用的物件表)。

規則是句型層級的,不針對任何一張卡:
- 句子以「。」切;「その後、」開頭的句子與前一句連接為「先後」;區塊開頭的「また、」是接著詞。
- 發動句(…発動できる / …発動する):
    (前提)(條件子句)(時|場合|際)(に)、(代價子句)て  → 條件段 + 代價段
  條件段帶觸發形;代價子句以て形結尾才算代價。前提(`premise` 模組:「〜に存在する場合、」
  「相手ターンに」)先剝掉、寫進第一個段的前提格(段的範圍從前提起算);整句只有前提的
  (「自分メインフェイズに発動できる」)開一個沒有動作詞的條件段放它;效果句開頭的前提同樣。
- 舊式的「(條件子句)(時|場合|際)、(效果子句)」(沒有発動できる)→ 條件段 + 效果段。
- 舊式的「(代價子句)る事で、(效果子句)」(= 新式「〜て発動できる。〜」)→ 代價段 + 效果段。
- 效果子句以「代わりに」開頭的是代替(票 08):條件段改標「被代替」(不更新位置)、效果段記 `replaces`。
- 其他句子是效果段;連用形串接(「〜に戻り、その攻撃力は〜になる」「〜手札に加え、〜に戻す」)切成
  多段、連接「同時」、後段與前段同一時機(`clause_join`);性質變更句「その攻撃力は〜倍になる」
  走 `segment_fields.parse_modify`。極性由述語語尾判(できない → 不能…);「〜を…できる」是可選的
  效果(可選格 `optional`,極性仍是做,查詢預設算命中),「〜は…できる」是永續的許可(極性 可以)
  (`segment_fields.resolve_polarity`)。
- 延遲(票 08):「次のスタンバイフェイズに」記時機延遲;序列中段出現條件段之後的段也算延遲(沒有字面);
  延遲段指回被點名物件的線不標取對象。
- 發動句的代價子句也可連用形串接(「〜を墓地へ送り、〜を対象として発動できる」,票 06),
  同樣切段、連接「同時」;句子以上的結構(● 分歧、內嵌效果、先後連接)在 `segment_tree`。
- 簡單子句:[誰が][到に][從から|從の|從に存在する][物件](を|が|は)[數量][取對象][原因][時機][形式][從から][到に][受方に]述語
  (物件前的「到に」只在助詞是「が」時:「自分フィールドにモンスターが特殊召喚された」;
  「從」寫在物件後的記 placement 述語前;受方是「相手に見せて」的相手,或物件的回指
  「この効果で特殊召喚したモンスターに装備」(票 06);形式「装備魔法カード扱いで、」是裝備時
  到的形式、到本身推得(票 06);「Xの効果を発動」的
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
- 存在前提:「(容器)の中に(物件)が(あった|ある|存在する)」→ 條件段,物件是容器的子集。
- 物件:このカード = 物件0;その/それらの モンスター|カード 指回本區塊最近的同大類物件
  (從條件段指回來的不標取對象;回指字面記在對象線 `ref`);「めくったカード」這類動作回指
  也指回;助詞後的數量(「を全て」「を２枚まで」)記在對象線 `count`,屬於這次提及;「残りのX」是
  剩餘物件(容器 − 最近的子集);其餘是新建物件,頭名詞給大類、數量給數量,修飾語從左到右認:
  「X」以外の = 非(卡名∋X);「X」と名のついた、緊接頭名詞的「X」= 字段(依字段表換成 setcode);
  カード名に「X」を含む = 卡名包含;「X」１体 = 卡名∋X;種族、屬性、レベルN = 屬性比較
  (「・」列舉的種族/屬性是「或」,種族接屬性是「且」,`attribute_atoms`);頭名詞 チューナー =
  怪獸 且 子類型 協調。認不得的修飾語整截標「解析不出」;「X」對不到卡名與字段的,
  物件標「不認得的「」名稱」。
- 位置:處理完一段把「到」寫回物件目前位置;「從」沒寫先繼承目前位置(沒動過就是初始位置),
  再查推得表;推得值與繼承自推得值的標 inferred,查詢開關開才算。
  區域的方沒寫(「墓地から」)照慣例歸我方但記 side_source 預設,場上系沒寫方不預設(任一方的
  場上);明寫「自分の」記明寫,反向檢查沒有字面時只在明寫才寫出來。
- 上游切分:整句是場上唯一或次數限制句(`OMITTED_SENTENCES`)的進略過文本、不產生段;
  句首時間狀語(このターン、/この効果の発動後、ターン終了時まで/〜を発動するターン、)剝成期間、
  套到整句的段;前提「〜限り、」整句的段期間持續;「Xしか〜できない」的しか是助詞、極性只能。
- 「選んで」:不另成段,字面留在原述語字面開頭、不標取對象;區域當物件(「自分の手札を
  １枚選んで捨てる」)新建沒有條件的卡物件、從 = 那個區域;對象線加 pick(ランダムに)、count 的
  each(それぞれ/ずつ)與算式(任意の数だけ、〜した数だけ);到的方可為持有者(持ち主の);述語前的
  「〜まで」記期間;句中「、その後」與前一段先後連接。
- 抗性/限制:述語槽開頭可帶攻擊次數/全體與「攻撃を」「効果を」「表示形式を」
  「コントロールは」這幾個含を/は的名詞;「Xの表示形式を」的の是助詞;助詞後的讀點記進助詞字面;
  原因可帶物件(「Xとの戦闘では」「Xの効果を受けない」的 X);「それぞれ１ターンに１度だけ」記 per_turn;
  句型把「が」當助詞切錯而述語解不出時(「〜に１回ずつ攻撃が可能」),整句當主語省略的子句再試。
- 去除:對象是超量素材「(Xの)X素材」(`of` 所屬卡;沒寫時是隱含的新建超量怪獸,初始位置 = 從)
  與計數器「(Xの)魔力カウンター」(`counter` 種類名);數量單位「つ」;舊式代價「〜く事で、」。
  另收:「このカードを対象とする(Xの)効果が発動した」(物件條件 以此卡為對象)、超量素材行「×N」、
  物件前的「〜の数まで、」、片假名子類型(リンク…)、修飾語連接字與預設不同時記 `joiner`。
- 抽牌(`draw`):「[誰]デッキから[カードを]N枚ドローする」另開句型,抽到的卡是新建物件(「カードを」
  沒寫時沒有字面)、張數在對象線、從牌組到手牌(推得);誰可為「お互いは」與指回抽牌段的「ドローしたプレイヤーは」
  (`agent` {ref, segment});原因加規則(通常の)與方法(「ドロー以外の方法で」,exclude);「自身の手札」的方是自身;
  回指後接數量(「そのカード１枚を」)記在對象線。
抽不出的段與物件一律標原因,不丟例外,全庫建置不中斷。
"""
import re

import damage
import draw
from archetype_table import fold_width
from attribute_atoms import is_param_atom, joiner, parse_modifier as parse_param_group
from attribute_words import ATTRIBUTE_JA, RACE_JA
from clause_join import JOIN, split_continuative
from condition_atoms import (TARGETING_THIS_FORMS, parse_modifier as parse_atom_modifier,
                             targeting_this_atom)
from names_attributes import REASON_NAME_UNKNOWN, TREAT_PREDICATE, parse_treat_as
from premise import is_lasting, split_premises
from segment_fields import (CAUSE_PATTERN, CLAUSE_DURATION_PATTERN, DISPLAY_PATTERN,
                            EFFECT_HOLDER_PREFIX,
                            DURATION_TURN, ORDER_PATTERN,
                            OWNER_JOINER, OWNER_PATTERN, OWNER_TEXT, PER_TURN_PATTERN,
                            REPLACEMENT_PREFIX,
                            TIMING_PATTERN, TREAT_DELTA_PATTERN, TREAT_PATTERN, implicit_delay,
                            is_delayed, parse_treat_delta,
                            MENTION_FORMS, inherited_duration, lasting, mention_head, parse_cause,
                            find_battle_duration, parse_duration, parse_leading_duration,
                            parse_modify, parse_per_turn,
                            parse_placement_form, parse_timing, resolve_polarity)
from structure_shape import (AMOUNT_FORMULA, BATTLE_TRIGGERS, DEFAULT_ZONE_WORD, DISPLAY_WORD,
                             ZONE_WORDS, new_line, new_object,
                             new_segment, position, unparsed, zone)
from synonyms import (
    ACTION_PAST, ACTIVATION_SUFFIXES, ATTACK_PREFIX_PATTERN, COST_GLUE, MODIFY_ACTION,
    MODIFY_PREDICATE, ONLY_MARKER, PREDICATE_NOUN_PATTERN, SELECT_PREFIX, SUMMON_NOUNS,
    TARGET_REF,
    TARGETING_PREFIXES, action_ancestors, attack_times,
    merged_voice, parse_predicates)

# 推得表:動作詞 → (沒寫「從」時的出發地, 沒寫「到」時的終點)。
INFERENCE_TABLE = {
    "破壞": ("場上", "墓地"),
    "解放": ("場上", "墓地"),
    "捨棄": ("手牌", "墓地"),
    "特殊召喚": (None, "場上"),
    "裝備": (None, "魔陷區"),
    "放置": (None, "魔陷區"),
    "覆蓋": (None, "魔陷區"),
    "抽牌": ("牌組", "手牌"),
}
# 區域字面表在 structure_shape.ZONE_WORDS(三處共用)。
# 場上系區域:沒寫方時不預設(手札・デッキ・墓地沒寫方照慣例是自己的,場上不是)。
FIELD_ZONES = ("場上", "EX怪獸區", "怪獸區", "魔陷區", "P區", "場地區")
# 從的助詞:新式「墓地の」「墓地から」;舊式連體修飾「墓地に存在するX」(= 墓地のX)。
FROM_PARTICLES = ("から", "の", "に存在する")
HEAD_CATEGORY = {"モンスター": "怪獸", "魔法カード": "魔法", "罠カード": "陷阱",
                 "魔法・罠カード": ("魔法", "陷阱"), "カード": "卡"}
# 帶子類型的頭名詞:大類 且 屬性比較(卡片子類型 = 協調,與票 07 的 Xモンスター 同一種原子)。
HEAD_SUBTYPE = {"チューナー": ("怪獸", "協調")}
_HEADS = "|".join(sorted(list(HEAD_CATEGORY) + list(HEAD_SUBTYPE), key=len,
                         reverse=True))
# 「持ち主の手札に戻す」的持ち主:值持有者,靜態判不了是哪一方,查詢指定我方/對手時不命中。
# 「お互いは」(誰,雙方各自);「自身の手札」的自身 = 這一段的誰那一方(「ドローしたプレイヤーは
# 自身の手札を」),同持有者靜態判不了,查詢指定我方/對手時不命中。
SIDE_WORDS = {"自分": "我方", "相手": "對手", "自分か相手": "任一方", "持ち主": "持有者",
              "お互い": "雙方各自", "自身": "自身"}
EXIST_WORDS = ("あった", "ある", "存在する", "存在した")
FULLWIDTH_DIGITS = str.maketrans("０１２３４５６７８９", "0123456789")

_ZONE_WORDS_ALT = "|".join(w for w, _ in ZONE_WORDS)
# 區域短語:[自分の|相手の|自分か相手の]區域(・區域|か區域)*;「・」與「か」都是列舉
# (自分の手札・フィールド、自分のフィールドか墓地),字面由從/到的 text 還原(票 06)。
_ZONE_PHRASE = (f"(?:(?:自分か相手|自分|相手|持ち主|自身)の?)?(?:{_ZONE_WORDS_ALT})"
                f"(?:[・か](?:{_ZONE_WORDS_ALT}))*")
# 受方可以是物件的回指(「この効果で特殊召喚したモンスターに装備できる」,票 06)。
_RECIPIENT_REF = ("(?:この効果で)?(?:その|それらの|" + "|".join(ACTION_PAST.values())
                  + f")(?:モンスター|カード)|{TARGET_REF}(?:モンスター|カード)")
_ACTIVATION_RE = re.compile("^(?P<body>.*?)(?P<suffix>" + "|".join(ACTIVATION_SUFFIXES) + ")$")
# 次數限制字面(「１ターンに１度、」):spec 說不記,出現在句中時進略過文本(原因 次數限制),
# 反向檢查比對時扣掉。
INTERVAL_PATTERN = "(?:１ターンに|デュエル中に)[１-９]度、"
INTERVAL_RE = re.compile(INTERVAL_PATTERN)
INTERVAL_REASON = "次數限制"
# 整句不記、進略過文本的句子:場上唯一「Xは自分フィールドに１体しか表側表示で存在
# できない」;次數限制「この効果は１ターンに１度しか使用できない」型(區塊切分只在它自成一句、
# 沒被補足情報的『』引用黏進效果區塊時才略過,黏進去的由這裡收)。
UNIQUE_REASON = "場上唯一"
_UNIQUE_RE = re.compile(
    "^[^、。]+?は、?(?:自分フィールド上|自分フィールド|フィールド上|フィールド|自分のモンスターゾーン)"
    "に１(?:体|枚)しか表側表示で存在できない$")
_LIMIT_SENTENCE_RE = re.compile(
    "^(?:「[^「」]+」の|このカード名の)?(?:この)?効果は(?:お互いに)?"
    "(?:１ターンに|デュエル中に)[１-９]度しか(?:使用|適用)できない$")
OMITTED_SENTENCES = ((_UNIQUE_RE, UNIQUE_REASON), (_LIMIT_SENTENCE_RE, INTERVAL_REASON))
# 同一句次數限制寫成句尾括號注記(「〜発動できる（このカード名のこの効果は１ターンに１度しか使用できない）」)。
_LIMIT_NOTE_RE = re.compile("（(?P<note>[^（）]+)）$")
# 原因(票 09 加):「「X」の効果で」= 某張卡的效果(物件);「融合召喚及び以下の方法で」= 召喚方式
# (「以下の方法」指後面的 ● 列舉)。閉集字面(戦闘で…)在 segment_fields.CAUSE_FORMS。
_NAMED_CAUSE = "「[^「」]+」の効果で"
SUMMON_METHODS = ("融合召喚", "S召喚", "X召喚", "L召喚", "儀式召喚", "P召喚", "以下の方法")
_METHOD_CAUSE = (f"(?:{'|'.join(SUMMON_METHODS)})(?:及び(?:{'|'.join(SUMMON_METHODS)}))*で")
# 「Xとの戦闘では」:戰鬥的對手是物件。「〜の(効果を受けない)」:誰的效果(OWNER_PATTERN)。
_BATTLE_CAUSE = "(?:「[^「」]*」|[^を、「」])+?との(?:戦闘では|戦闘で|戦闘によって)"
_BATTLE_CAUSE_RE = re.compile("^(?P<phrase>.+?)との(?P<tail>戦闘では|戦闘で|戦闘によって)$")
# 「ドロー以外の方法で手札に加わった」:原因是方法,`exclude` 記被排除的動作詞;
# 「X以外の」的 X 是同義表的述語字幹(目前只收ドロー,全庫 33 處)。
EXCLUDE_METHOD_TAIL = "以外の方法で"
EXCLUDE_METHOD_PATTERN = f"ドロー{EXCLUDE_METHOD_TAIL}"
CAUSE_EXCLUDE = "方法"
_CAUSE_ALT = (f"{CAUSE_PATTERN}|{_NAMED_CAUSE}|{_METHOD_CAUSE}|{_BATTLE_CAUSE}|{OWNER_PATTERN}"
              f"|{EXCLUDE_METHOD_PATTERN}")
_NAMED_CAUSE_RE = re.compile(f"^(?P<name>「[^「」]+」)の効果で$")
_METHOD_CAUSE_RE = re.compile(f"^{_METHOD_CAUSE}$")
CAUSE_EFFECT_OF = "の効果で"
CAUSE_METHOD = "召喚方式"
# 主語省略的子句(「〜できず、「X」の効果でのみ特殊召喚できる」「〜した場合にEXデッキから特殊召喚できる」):
# 沒有物件與助詞,主語是前一個「は」子句的物件或このカード,對象線標 elided。
# 述語槽開頭可帶攻擊次數/全體(「２回攻撃」「相手モンスター全てに１回ずつ攻撃」)與含「を/は」的
# 名詞(攻撃を、効果を、表示形式を、コントロールは),其餘不收「を」。
_PRED_HEAD = f"(?:{ATTACK_PREFIX_PATTERN})?(?:{PREDICATE_NOUN_PATTERN})?"
_SUBJECTLESS_RE = re.compile(
    f"^(?P<cause>{_CAUSE_ALT})?"
    f"(?P<timing>{TIMING_PATTERN})?"
    f"(?:(?P<from2>{_ZONE_PHRASE})から)?"
    f"(?:(?P<to>{_ZONE_PHRASE})(?P<to_particle>に|へ))?"
    f"(?P<pred>{_PRED_HEAD}[^を]+)$")
TOPIC_UNKNOWN = object()
# 句首的「Xは」(「「A」または「B」は」的「または」屬於 X)。
_TOPIC_RE = re.compile("^(?P<topic>(?:または|[^をがは、])+?)は")
# 觸發形:戰鬥時點排在「時」前面,「〜戦闘を行うダメージ計算時」的觸發形是整個時點字面;
# 後接「(、)または」的是「A時點、またはB時」兩個觸發的或,維持切在後面的「時」。
_TRIGGERS = f"(?:{'|'.join(BATTLE_TRIGGERS)})(?!、?または)|時|場合|際"
# 條件子句不在「」中間結束:「「時械神」モンスター」的「時」不是觸發形。
_COND = "(?P<cond>(?:「[^「」]*」|[^「」])+?)"
_TRIGGER_RE = re.compile(f"^{_COND}(?P<trig>{_TRIGGERS})に?、?(?P<rest>.*)$")
# 發動句裡單獨的戰鬥時點:「そのダメージ計算前に発動する」「ダメージ計算時に、〜て発動できる」
# 開一個沒有動作詞的條件段;「その」指回同一句前一個條件段(前提 段已執行)。後面要接「に」「、」或句尾,
# 「ダメージステップ終了時まで」不是。
BATTLE_TIMING_REF = "その"
_BATTLE_TIMING_RE = re.compile(
    f"^(?P<ref>{BATTLE_TIMING_REF})?(?P<trig>{'|'.join(BATTLE_TRIGGERS)})(?=に|、|$)に?、?(?P<rest>.*)$")
PREMISE_DONE = "段已執行"
# 舊式的條件句:觸發形後一定有「、」才算,免得「終了時に」這類句中的時被當觸發。
_OLD_TRIGGER_RE = re.compile(f"^{_COND}(?P<trig>{_TRIGGERS})(?:に)?、(?P<rest>.+)$")
# 召喚條件區塊的召喚手續句(票 09):「〜をリリースした場合に特殊召喚できる」「〜を除外した場合のみ
# EXデッキから特殊召喚できる」,觸發形後可接「に」、「、」或直接接「のみ」。
_SUMMON_TRIGGER_RE = re.compile(f"^{_COND}(?P<trig>時|場合)(?:に、|に|、)?(?P<rest>.+)$")
BLOCK_SUMMON, BLOCK_MATERIAL = "召喚條件", "素材"
KIND_PROCEDURE, KIND_RESTRICTION, KIND_MODIFIER = "召喚手續", "限制", "修飾"
ROLE_MATERIAL = "素材"
MATERIAL_JOINER = "＋"
MATERIAL_TIMES = "×"
_MATERIAL_TIMES_RE = re.compile(f"^(?P<phrase>.+?)(?P<times>{MATERIAL_TIMES}(?P<digits>[０-９]+))$")
# 「〜したターン、」(票 09):句首的動作子句 + ターン 是條件段(觸發形 ターン),後面的段的前提引用它
# (`本回合發生過`);「相手ターンに」是遊戲狀態前提,不走這裡(前面要有 した/成功した)。
TURN_TRIGGER = "ターン"
_TURN_RE = re.compile("^(?P<cond>[^、]+?(?:した|に成功した))ターン、(?P<rest>.+)$")
PREMISE_HAPPENED = "本回合發生過"
# 重複到停為止(spec 故事 28、GLOSSARY「未結構化」):「「〜」処理を繰り返す」「〜までこの効果を
# (最大で７回)繰り返す」「〜処理を〜の数だけ繰り返す」。要有「処理を」或「この効果を」才算,
# 通常怪獸的故事文「攻撃を繰り返す」不是效果。句尾可帶「（最大４回）」。
REPEAT_RE = re.compile("^(?=.*(?:処理|この効果)を).*繰り返す(?:（[^）]*）)?$")
# 舊式的代價句:「(代價子句)る事で、(效果子句)」= 新式「(代價子句)て発動できる。(效果子句)」。
# 代價子句以非過去形收尾(る/う/す/く;く 是「取り除く事で」)才算,「〜された事で」是條件意味、不切。
_OLD_COST_RE = re.compile("^(?P<cost>.+?[るうすく])" + COST_GLUE + "、?(?P<rest>.+)$")
# 對象線的數量字面:N体/N枚(まで)、全て;「それぞれ」「ずつ」是每一份各 N(`each`);
# 變數數量「任意の数だけ」記算式字面。寫在物件前的變數數量(「破壊した数だけ相手フィールドの
# カードを」)與寫在述語前「從」之後的數量(「自分の墓地から１枚選んで」)另帶 placement。
EACH_PREFIX, EACH_SUFFIX, FORMULA_COUNT_TAIL = "それぞれ", "ずつ", "数だけ"
# 單位「つ」:超量素材、計數器的「１つ」「２つまで」。
COUNT_UNITS = "体|枚|つ"
COUNT_PATTERN = (f"(?:{EACH_PREFIX})?[０-９]+(?:{COUNT_UNITS})(?:まで|{EACH_SUFFIX})?|全て"
                 f"|任意の{FORMULA_COUNT_TAIL}")
_COUNT_RE = re.compile(f"^(?P<each>{EACH_PREFIX})?(?P<digits>[０-９]+)(?P<unit>{COUNT_UNITS})"
                       f"(?P<upto>まで)?(?P<per>{EACH_SUFFIX})?$")
# 物件前的變數數量另收上限「〜の数まで、」(「自分フィールドの「＠イグニスター」モンスターの
# 数まで、相手フィールドの〜を選んで破壊する」),算式帶 cmp ≤。
FORMULA_UPTO_TAIL = "数まで"
FORMULA_COUNT_TAILS = (FORMULA_COUNT_TAIL, FORMULA_UPTO_TAIL)
FRONT_COUNT_PATTERN = f"[^、を]+?(?:{'|'.join(FORMULA_COUNT_TAILS)})、?"
ZONE_AS_OBJECT = "物件"
RANDOM_PICK = "ランダムに"
PICK_RANDOM = "隨機"
# 物件前的「到に」:主語形「自分フィールドにモンスターが特殊召喚された」(助詞が時才有);
# 後接「存在する」的是舊式從的助詞(フィールド上に存在するモンスター),不是到。
_TO_FRONT = f"(?:(?P<to_front>{_ZONE_PHRASE})に(?!(?:{DISPLAY_WORD}で)?存在する))?"
# 誰:玩家字面「自分/相手/お互い」與動作回指「ドローしたプレイヤー」(指回本區塊最近做過
# 那個動作的段);助詞 が/は(「お互いに」也是誰),後面可帶讀點。
PLAYER_REF_HEAD = "プレイヤー"
AGENT_PLAYER_WORDS = {"お互いのプレイヤー": "雙方各自", "相手プレイヤー": "對手",
                      "自分": "我方", "相手": "對手", "お互い": "雙方各自"}
AGENT_PATTERN = ("|".join(AGENT_PLAYER_WORDS) + "|(?:"
                 + "|".join(sorted(ACTION_PAST.values(), key=len, reverse=True))
                 + f"){PLAYER_REF_HEAD}")
_AGENT = (f"(?:(?P<agent>{AGENT_PATTERN})(?P<agent_marker>が|は|(?<=お互い)に)"
          "(?P<agent_pause>、)?)?")
_DRAW_RE = draw.clause_pattern(AGENT_PATTERN)
_CLAUSE_PATTERN = (
    f"^{_AGENT}"
    # 寫在主語後、物件前的方法原因(「相手がドロー以外の方法でデッキからモンスターを手札に加えた」)。
    f"(?P<cause_front>{EXCLUDE_METHOD_PATTERN})?"
    f"{_TO_FRONT}"
    f"(?P<count_front>{FRONT_COUNT_PATTERN})?"
    # 物件前的「從」:「EXデッキから特殊召喚されたモンスター」的「から」是修飾語(曾被特殊召喚),
    # 不是這一段的從;「自分フィールドの、「A」または「B」が」的讀點記進從的字面(票 08)。
    # 舊式「フィールド上に表側表示で存在するX」:表示形式記在從的放置形式。
    f"(?:(?P<from>{_ZONE_PHRASE})(?P<from_particle>{'|'.join(FROM_PARTICLES)}"
    f"|に(?P<from_display>{DISPLAY_WORD})で存在する)"
    "(?P<from_pause>、)?(?!特殊召喚され))?"
    # 物件短語裡的「を含む」(カード名に「X」を含む)、「を持つ」(…と同じ数値のレベルを持つ)
    # 不是受詞助詞;述語裡沒有を,所以切錯時會回頭把「を含む」吃進物件短語。
    # 「Xの効果を発動」:物件是 X,「の効果」記進對象線的助詞字面;「「A」または「B」が」的
    # 「または」整個屬於物件短語,裡面的「は」不是助詞(票 08)。
    # 「Xしか〜できない」:「しか」緊接物件時當助詞,極性只能(`resolve_polarity`);
    # 「〜の効果でしか」「メインフェイズにしか」「手札からしか」的しか接在原因/時機/從後,不是助詞。
    "(?P<objects>(?:を含む|を持つ|または|[^を])+?)(?P<of_effect>の効果)?"
    # 「Xの表示形式を変更」「Xのコントロールは変更」:X 是物件、助詞「の」。
    # 「Xモンスター１体のX召喚を行う」:X 是物件、助詞「の」。
    f"(?P<marker>を|が|は|(?<!で)(?<!に)(?<!から){ONLY_MARKER}"
    f"|の(?=表示形式|コントロール|(?:{'|'.join(SUMMON_NOUNS)})行))"
    # 助詞後的讀點(「水属性モンスターは、〜」)記進助詞字面。
    "(?P<marker_pause>、)?"
    f"(?P<pick>{RANDOM_PICK})?"
    f"(?P<count>{COUNT_PATTERN})?"
    # 次數限制不記(spec):「「X」は１ターンに１度、〜でのみ特殊召喚できる」的這截進略過文本。
    f"(?P<interval>{INTERVAL_PATTERN})?"
    # 抗性的每回合次數「それぞれ１ターンに１度だけ」:段的 per_turn。
    f"(?P<per_turn>{PER_TURN_PATTERN})?"
    # 取對象字面(舊式 選択して、新式 対象として):單獨出現(述語空)是發動句的取對象宣告。
    f"(?P<targeting>{'|'.join(TARGETING_PREFIXES)})?"
    f"(?P<cause>{_CAUSE_ALT})?"
    f"(?P<timing>{TIMING_PATTERN})?"
    # 到的放置形式(segment_fields.parse_placement_form):順序「好きな順番で」;
    # 卡片種類視同「装備魔法カード扱いで、」是裝備時到的形式(到本身推得)。
    # 「攻撃力３００アップの装備カード扱いで」的增減前綴屬於 treat 字面,另拆一段衍生段。
    f"(?:(?P<treat>(?:{TREAT_DELTA_PATTERN}|{EFFECT_HOLDER_PREFIX})?{TREAT_PATTERN})"
    f"|(?P<order>{ORDER_PATTERN}))?"
    # 「從」也可寫在物件後(XをデッキからYに加える);受方(相手に見せて)緊接述語前。
    f"(?:(?P<from2>{_ZONE_PHRASE})から)?"
    f"(?P<count2>{COUNT_PATTERN})?"
    # 「選んで」:字面留在原述語字面開頭、不標取對象;單獨出現是發動句的選取宣告。
    f"(?P<select>{SELECT_PREFIX})?"
    # 述語前的期間:「エンドフェイズまで除外する」。
    f"(?P<duration>{CLAUSE_DURATION_PATTERN})?"
    f"(?:(?P<to>{_ZONE_PHRASE})(?P<to_particle>に|へ))?"
    f"(?:(?P<recipient>自分|相手|{_RECIPIENT_REF})に)?"
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
# 助詞不是「が」時物件前那截不是到,而是物件修飾的一部分(相手フィールド上にセットされたカード):
# 拿掉「到に」再比一次。
_CLAUSE_NO_TO_FRONT_RE = re.compile(_CLAUSE_PATTERN.replace(_TO_FRONT, "", 1))
_EXIST_RE = re.compile(
    "^(?P<container>.+?)の中に(?P<objects>.+?)が(?P<pred>" + "|".join(EXIST_WORDS) + ")$")
# 戰鬥子句:述語「戦闘を行う」含「を」,一般句型的述語槽吃不到,另開句型。
# 施事寫在前、受事(「Yと」)可省;物件短語裡沒有讀點(「自分のモンスターが、〜と」不收)。
BATTLE_AGENT_MARKER, BATTLE_PARTNER_MARKER = "が", "と"
BATTLE_PREDICATE = "戦闘を行"
_BATTLE_RE = re.compile(
    f"^(?P<agent>[^、]+?){BATTLE_AGENT_MARKER}"
    f"(?:(?P<partner>[^、]+?){BATTLE_PARTNER_MARKER})?(?P<pred>{BATTLE_PREDICATE}[^を、]*)$")
_FROM_RE = re.compile("^(?:(?P<side>自分か相手|自分|相手|持ち主|自身)の?)?(?P<zones>.+)$")
_ZONE_PHRASE_RE = re.compile(f"^{_ZONE_PHRASE}$")
_SELF_RE = re.compile("^このカード$")
REF_RE = re.compile("^(?P<ref>その|それらの)(?P<head>モンスター|カード)$")
# 回指後接數量(「そのカード１枚を相手に見せて」):數量屬於這次提及,記在對象線、placement 物件後。
_REF_COUNT_RE = re.compile("^(?P<phrase>(?:その|それらの)(?:モンスター|カード))(?P<count>[０-９]+(?:体|枚))$")
COUNT_AFTER_OBJECT = "物件後"
# 「その発動」:指回本區塊最近被發動的那張卡(「罠カードが発動した時、…その発動を無効にし」,票 09)。
ACTIVATION_REF = "その発動"
# 數量格(spec「數量」:支付 1000LP,段可無物件):「１０００LP」當受詞時不是物件。
_AMOUNT_RE = re.compile("^(?P<digits>[０-９]+)(?P<unit>LP)$")
_REMAINDER_RE = re.compile("^残りの(?P<head>モンスター|カード)$")
# 去除的對象:超量素材「(Xの)X素材」、計數器「(Xの)魔力カウンター」;「の」前是所屬的物件
# (`of`,このカード/そのモンスター…)。超量素材沒寫所屬卡時(「自分フィールドのX素材」的
# 「自分フィールドの」是從),所屬卡是隱含的新建超量怪獸,初始位置 = 從;字面沒有它(`text` 是 None)。
OBJECT_MATERIAL, OBJECT_COUNTER = "超量素材", "計數器"
MATERIAL_WORDS = ("X素材", "エクシーズ素材")
_MATERIAL_RE = re.compile(f"^(?:(?P<owner>.+)の)?(?P<word>{'|'.join(MATERIAL_WORDS)})$")
_COUNTER_RE = re.compile("^(?:(?P<owner>.+)の)?(?P<counter>[^「」のをにがは、]*カウンター)$")


def xyz_monster_condition():
    """超量怪獸的條件式(與「Xモンスター」解析出的相同)。"""
    return {"op": "且", "args": [
        {"op": "屬性比較", "attr": "卡片子類型", "cmp": "=", "value": "超量"},
        {"op": "大類", "value": "怪獸"}]}
# 「選択したモンスター」:指回本區塊最近被取對象的同大類物件(舊式;新式用 そのモンスター)。
TARGET_REF_RE = re.compile(f"^{TARGET_REF}(?P<head>モンスター|カード)$")
TARGET_OF = "対象の"
# 動作回指可帶「この効果で」(この効果で除外したモンスター);字面整個記進對象線 ref(票 08)。
ACTION_REF_RE = re.compile("^(?:この効果で)?(?P<past>.+?)(?P<head>モンスター|カード)$")
_NOUN_RE = re.compile(
    f"^(?P<mods>.*?)(?P<head>{_HEADS})"
    "(?P<count>[０-９]+(?P<unit>体|枚)(?P<upto>まで)?)?$")
# 「X」１体:只有卡名、沒有頭名詞的物件;「A」または「B」是兩個卡名的「或」(票 08)。
_NAMED_RE = re.compile(
    "^(?P<names>「[^「」]+」(?:または「[^「」]+」)*)"
    "(?P<count>[０-９]+(?P<unit>体|枚)(?P<upto>まで)?)?$")
# 名稱修飾語(從左到右逐個認;「X」單獨出現只能緊接頭名詞,所以要在字串尾)。
_MOD_RES = (
    ("以外", re.compile("^「(?P<name>[^「」]+)」以外の")),
    ("と名のついた", re.compile("^「(?P<name>[^「」]+)」と名のついた")),
    ("卡名包含", re.compile("^カード名に「(?P<name>[^「」]+)」を含む")),
    ("字段", re.compile("^「(?P<name>[^「」]+)」$")),
)

REASON_NOT_ARCHETYPE = "「」名稱不是字段"
REASON_CLAUSE = "子句解析不出"
REASON_FROM = "從解析不出"
REASON_TO = "到解析不出"
REASON_OBJECT = "物件解析不出"
REASON_MODS = "物件修飾解析不出"
REASON_REF = "指回的物件找不到"
REASON_ACTIVATION = "發動句解析不出"
REASON_CAUSE = "原因解析不出"
# 同一格(原因、期間、數量)在句中寫了兩處:不猜哪一處算數。
REASON_TWICE = "同一格寫了兩處"
REASON_DISPLAY = "表示形式沒有到"


def agent_particle(kind):
    """誰的預設接法:條件子句是「相手が〜した時」,效果句是「自分は〜する」(全庫 66:0、31:1)。"""
    return "が" if kind in ("條件", "被代替") else "は"


def agent_side(agent):
    """agent 格 → 方(字串或玩家字面的 side);動作回指沒有靜態的方,回 None。"""
    if isinstance(agent, dict):
        return agent.get("side")
    return agent


def parse_from(phrase):
    """「自分の手札・フィールド」→ 區域列表;任何一截不是區域字面就回 None。"""
    m = _FROM_RE.match(phrase)
    if not m:
        return None
    zones = []
    for part in re.split("[・か]", m.group("zones")):
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


def parse_count(m):
    if not m.group("count"):
        return None
    digits = m.group("count")[:-len(m.group("unit")) - len(m.group("upto") or "")]
    return {"text": m.group("count"),
            "value": int(digits.translate(FULLWIDTH_DIGITS)),
            "unit": m.group("unit"), "cmp": "≤" if m.group("upto") else "="}


def zone_literal(phrase):
    """區域短語用了非預設的字面(舊式「フィールド上」)就回短語本身(要留原文字面),否則 None。
    前提的區域平常照方的來源還原(票 05),只有這種情形還原不回原文。"""
    m = _FROM_RE.match(phrase)
    parts = re.split("[・か]", m.group("zones")) if m else []
    if "か" in phrase or any(
            part != DEFAULT_ZONE_WORD.get(dict(ZONE_WORDS).get(part)) for part in parts):
        return phrase   # 「か」列舉(自分のフィールドか墓地)沒有預設寫法,也留字面(票 06)
    return None


def floating_count(text, placement=None):
    """對象線的數量(「カードを２枚まで」「それらのモンスターを全て」),記在對象線上;
    變數數量(「任意の数だけ」「破壊した数だけ」)是算式字面;「それぞれ」「ずつ」帶 `each`;
    寫在物件前或述語前的帶 `placement`(有值才寫)。"""
    if text == "全て":
        count = {"text": text, "cmp": "全部"}
    elif text.rstrip("、").endswith(FORMULA_COUNT_TAILS):
        count = {"kind": AMOUNT_FORMULA, "text": text}
        if text.rstrip("、").endswith(FORMULA_UPTO_TAIL):
            count["cmp"] = "≤"
    else:
        m = _COUNT_RE.match(text)
        count = {"text": text, "value": int(m.group("digits").translate(FULLWIDTH_DIGITS)),
                 "unit": m.group("unit"), "cmp": "≤" if m.group("upto") else "="}
        if m.group("each") or m.group("per"):
            count["each"] = True
    if placement:
        count["placement"] = placement
    return count


OR_FORM = "か"


def split_alternatives(mods, head):
    """物件短語的修飾語裡,頂層(「」外)的「か」左邊是完整名詞短語(帶頭名詞、沒有數量)時才算列舉:
    回傳各截名詞短語(最後一截接回頭名詞);不是列舉回 None(「自分か相手の」是方,不在此列)。"""
    pieces, depth, last = [], 0, 0
    for i, ch in enumerate(mods):
        if ch == "「":
            depth += 1
        elif ch == "」":
            depth -= 1
        elif ch == OR_FORM and depth == 0:
            left = _NOUN_RE.match(mods[last:i])
            if left and not left.group("count"):
                pieces.append(mods[last:i])
                last = i + 1
    if not pieces:
        return None
    return pieces + [mods[last:] + head]


def _noun_condition(atoms, head):
    condition = category_condition(head)
    return {"op": "且", "args": atoms + [condition]} if atoms else condition


def category_condition(head):
    if head in HEAD_SUBTYPE:
        category, subtype = HEAD_SUBTYPE[head]
        return {"op": "且", "args": [{"op": "大類", "value": category},
                                    {"op": "屬性比較", "attr": "卡片子類型",
                                     "cmp": "=", "value": subtype}]}
    value = HEAD_CATEGORY[head]
    if isinstance(value, tuple):
        return {"op": "或", "args": [{"op": "大類", "value": v} for v in value]}
    return {"op": "大類", "value": value}


# ── 條件式:屬性比較的修飾語(種族、屬性);等級(レベルN、N以上/以下)與「・」列舉在
# attribute_atoms,名稱類的在 BlockState.parse_modifiers ──
def parse_modifier(part):
    """一截修飾語 → 屬性比較原子;認不得回 None。"""
    if part in RACE_JA:
        return {"op": "屬性比較", "attr": "種族", "cmp": "=", "value": part}
    if part.endswith("属性") and part[:-2] in ATTRIBUTE_JA:
        return {"op": "屬性比較", "attr": "屬性", "cmp": "=", "value": part[:-2]}
    return None


def split_objects(phrase):
    """以「と」切物件,但「」裡的と、「X」と名のついた 的と(字段的舊式寫法)、「このカードを対象とする」
    的と不算。"""
    parts, depth, buf = [], 0, ""
    for i, ch in enumerate(phrase):
        if ch == "「":
            depth += 1
        elif ch == "」":
            depth -= 1
        if (ch == "と" and depth == 0
                and not phrase.startswith(("と名のついた", "と同じ", "とする"), i)):
            parts.append(buf)
            buf = ""
        else:
            buf += ch
    parts.append(buf)
    return [p for p in parts if p]


# 物件的目前位置:{"zones": [區域], "inferred": bool}(推得的或繼承自推得的才是 True)。
CurrentPosition = dict[str, object]


class BlockState:
    """一個區塊抽取時的工作狀態:物件目前位置、本區塊提過的物件(給その指回)、
    名稱表(「X」→ 名稱列)與字段對照。"""

    def __init__(self, block, card, lookups=None, self_id="o0"):
        self.block = block
        self.card = card
        self.lookups = lookups or {"card_names": set(), "archetypes": {}}
        self.names = {row["text"]: row for row in card["names"]}
        # 物件目前位置:{物件 id: {"zones": [區域], "inferred": 是不是推得的}},與 current_position 同形。
        self.positions: dict[str, CurrentPosition] = {}
        self.recent = []      # 本區塊建立或引用過的物件 id(其後者優先)
        self.targeted = []     # 被取對象的物件 id(「を選択して」「を対象として」點名的,後者優先)
        self.delayed = False  # 序列中段出現條件段之後:後面的段算延遲、不標取對象(票 08)
        self.acted = {}       # 物件 id → 本區塊對它做過的動作詞(動作回指「〜したモンスター」用;票 06)
        self.self_id = self_id  # 「このカード」指誰:內嵌效果裡綁定成被賦予效果的物件(票 06)
        self.subject = None   # 本句「Xは」的物件:後面主語省略的子句(「〜できず、〜できる」)沿用(票 09)
        self.topic = None
        self.last_segment_of_action = {}

    def note_actions(self, seg):
        """段解析完後記下它做過的動作詞,給之後的「〜したプレイヤー」指回。"""
        for action in seg["actions"]:
            self.last_segment_of_action[action] = seg["id"]

    def agent_of(self, word, marker, pause, kind):
        """誰的字面 → (agent 格, 原因)。玩家字面寫成預設接法(條件段「相手が」、其餘「自分は」)時
        是方的字串;其他接法(「お互いに」「自分は、」)記 `{"side", "text"}`(同受方的玩家字面);
        「ドローしたプレイヤー」記 `{"ref", "segment"}`,接法要是預設的。"""
        text = word + marker + (pause or "")
        if word not in AGENT_PLAYER_WORDS:
            past = word[:-len(PLAYER_REF_HEAD)]
            action = next(a for a, p in ACTION_PAST.items() if p == past)
            seg_id = self.last_segment_of_action.get(action)
            if seg_id is None:
                return None, REASON_REF
            if marker + (pause or "") != agent_particle(kind):
                return None, REASON_CLAUSE
            return {"ref": word, "segment": seg_id}, None
        side = AGENT_PLAYER_WORDS[word]
        if text == word + agent_particle(kind) and SIDE_WORDS.get(word) == side:
            return side, None
        return {"side": side, "text": text}, None

    def elided_subject(self):
        """主語省略的子句的物件:本句「Xは」的物件,沒有就是此卡;前一截解析不出時是它的「Xは」,
        它沒有「Xは」或認不出物件就判不了(None),不退回此卡。"""
        if self.subject is None and self.topic is not None:
            if self.topic is TOPIC_UNKNOWN:
                return None
            phrase, sentence_start = self.topic
            self.subject, _, _ = self.object_at(phrase, sentence_start)
            self.topic = None if self.subject else TOPIC_UNKNOWN
            return self.subject
        return self.subject or self.self_id

    def omit(self, offset, text, reason):
        """句中不記的字面(次數限制)進整卡的略過文本;範圍相對於來源文本。"""
        start = self.block["span"][0] + offset
        self.card["omitted"].append({"source": self.block["source"],
                                     "span": [start, start + len(text)],
                                     "text": text, "reason": reason})

    def cause_at(self, text, sentence_start):
        """原因字面 → (cause 格, 原因):閉集字面(戦闘で…)、「「X」の効果で」(物件)、
        「融合召喚及び以下の方法で」(召喚方式);「Xとの戦闘では」(戰鬥的對手)與
        「Xの(効果を受けない)」(誰的效果,「A及びB」多個),物件記在 `objects`。"""
        cause = parse_cause(text)
        if cause is not None:
            return cause, None
        if text.endswith(EXCLUDE_METHOD_TAIL):
            parsed, reason = parse_predicates(text[:-len(EXCLUDE_METHOD_TAIL)])
            if parsed is None:
                return None, REASON_CAUSE
            return {"kind": CAUSE_EXCLUDE, "exclude": [p.action for p in parsed],
                    "text": text}, None
        named = _NAMED_CAUSE_RE.match(text)
        if named:
            obj_id, _, reason = self.object_at(named.group("name"), sentence_start)
            if obj_id is None:
                return None, reason
            return {"kind": "效果", "text": CAUSE_EFFECT_OF, "object": obj_id}, None
        if _METHOD_CAUSE_RE.match(text):
            return {"kind": CAUSE_METHOD, "text": text,
                    "methods": text[:-1].split("及び")}, None
        battle = _BATTLE_CAUSE_RE.match(text)
        if battle:
            obj_id, _, reason = self.object_at(battle.group("phrase"), sentence_start)
            if obj_id is None:
                return None, reason
            return {"kind": "戰鬥", "text": "との" + battle.group("tail"),
                    "objects": [obj_id]}, None
        if text.endswith(OWNER_TEXT):
            objects = []
            for phrase in text[:-len(OWNER_TEXT)].split(OWNER_JOINER):
                obj_id, _, reason = self.object_at(phrase, sentence_start)
                if obj_id is None:
                    return None, reason
                objects.append(obj_id)
            return {"kind": "效果", "text": OWNER_TEXT, "objects": objects}, None
        return None, REASON_CAUSE

    def name_atom(self, op, name, form=None):
        """「X」→ (條件式原子, 原因):名稱列對不到卡名與字段 → 不認得的「」名稱;
        字段原子的 X 不是字段(只是卡名)→ 「」名稱不是字段。原子只引用名稱列的 id,
        字段原子另帶換好的 setcode(查詢不必再查字段表)。"""
        row = self.names.get(name)
        if row is None:
            return None, REASON_NAME_UNKNOWN
        atom = {"op": op, "name": row["id"]}
        reason = REASON_NAME_UNKNOWN if row["unparsed"] else None
        if op == "字段":
            atom["setcodes"] = self.lookups["archetypes"].get(fold_width(name), [])
            if form:
                atom["form"] = form
            if reason is None and not atom["setcodes"]:
                reason = REASON_NOT_ARCHETYPE
        return atom, reason

    def parse_modifiers(self, mods):
        """修飾語 → (原子列表, 原因):名稱類的句型逐個認,其餘以「・」切成一截截給
        `parse_modifier`(種族、屬性、レベルN);認不得的那截以「解析不出」原子收尾。
        種族/屬性/等級原子與下一個修飾語之間實際寫的字(「・」「の」或沒有)與模板的預設寫法
        (`attribute_atoms.joiner`)不同時,記進該原子的 `joiner`(素材行「水属性レベル４」、
        「ドラゴン族のシンクロモンスター」)。"""
        atoms, reason, rest = [], None, mods
        dot_before, written_after = [], []
        dot = False

        def add(new_atoms, tail=""):
            nonlocal dot
            atoms.extend(new_atoms)
            dot_before.extend([dot] + [False] * (len(new_atoms) - 1))
            written_after.extend([tail] + [""] * (len(new_atoms) - 1))
            dot = False

        while rest:
            # 種族/屬性的「・」列舉(含後面的「の」)整組先認:「ドラゴン族・鳥獣族」是或、
            # 「光・闇属性」逐截切會把「光」認不出。
            atom, length = parse_param_group(rest)
            if atom is not None:
                literal = rest[:length]
                dot = dot or literal.startswith("・")
                add([atom], "の" if is_param_atom(atom) and literal.endswith("の") else "")
                rest = rest[length:]
                continue
            if rest.startswith("・"):  # 列舉後接的其他修飾語(植物族・レベル１)
                dot = True
                rest = rest[1:]
            for kind, pattern in _MOD_RES:
                m = pattern.match(rest)
                if m:
                    break
            else:
                piece, sep, remainder = rest.partition("・")
                atom = parse_modifier(piece)
                if atom is not None:
                    add([atom])
                    dot = bool(sep)
                    rest = remainder
                    continue
                extra = parse_atom_modifier(rest, self)   # 票 07 的原子(condition_atoms)
                if extra is None:
                    atoms.append({"op": "解析不出", "text": rest})
                    return atoms, reason or REASON_MODS
                new_atoms, why, end = extra
                if not new_atoms:
                    atoms.append({"op": "解析不出", "text": rest})
                    return atoms, reason or why
                add(new_atoms)
                reason = reason or why
                rest = rest[end:]
                continue
            if kind == "以外":
                atom, why = self.name_atom("卡名", m.group("name"))
                if atom:
                    atom = {"op": "非", "arg": atom}
            elif kind == "卡名包含":
                atom, why = self.name_atom("卡名包含", m.group("name"))
            else:
                atom, why = self.name_atom(
                    "字段", m.group("name"),
                    form=kind if kind == "と名のついた" else None)
            if atom is None:
                atoms.append({"op": "解析不出", "text": rest})
                return atoms, reason or why
            add([atom])
            reason = reason or why
            rest = rest[m.end():]
        for i, atom in enumerate(atoms):
            if not is_param_atom(atom):
                continue
            following = atoms[i + 1] if i + 1 < len(atoms) else None
            written = written_after[i] + (
                "・" if following is not None and dot_before[i + 1] else "")
            if written != joiner(atom, following):
                atom["joiner"] = written
        return atoms, reason

    def find(self, obj_id):
        for obj in self.card["objects"]:
            if obj["id"] == obj_id:
                return obj
        return None

    def current_position(self, obj_id):
        """物件目前位置:動過就是最後的「到」,沒動過就是初始位置;都沒有回 None。"""
        if obj_id in self.positions:
            return self.positions[obj_id]
        obj = self.find(obj_id)
        if obj and obj["initial_position"]:
            return {"zones": list(obj["initial_position"]), "inferred": False}
        return None

    def recent_of(self, head, among=None, action=None):
        """本區塊最近提過的同大類物件(頭名詞 カード 任何大類都算);`among` 可改成別的候選列;
        給了 `action` 就只找本區塊被做過那個動作的(動作回指,票 06)。「このカード」不進 recent
        (その 不會指它),但動作回指可以:「このカードを特殊召喚する。〜この効果で特殊召喚した
        モンスターに装備」;它的大類看卡片屬性表。"""
        want = HEAD_CATEGORY[head]
        candidates = list(reversed(self.recent if among is None else among))
        if action is not None and among is None:
            candidates.append(self.self_id)
        for obj_id in candidates:
            if action is not None and action not in self.acted.get(obj_id, ()):
                continue
            obj = self.find(obj_id)
            category = (self._self_category() if obj["source"]["kind"] == "自己"
                        else _category_of(obj["condition"]))
            if want == "卡" or category == want:
                return obj_id
        return None

    def _self_category(self):
        rows = self.card["attributes"]["category"]
        return rows[0]["value"] if rows else None

    def is_action_reference(self, phrase):
        m = ACTION_REF_RE.match(phrase)
        return bool(m and m.group("past") in ACTION_PAST.values())

    def action_reference(self, phrase):
        """動作回指短語 → 物件 id 或 None(找不到)。"""
        m = ACTION_REF_RE.match(phrase)
        action = next(a for a, past in ACTION_PAST.items() if past == m.group("past"))
        return self.recent_of(m.group("head"), action=action)

    def resolve_reference(self, phrase):
        """修飾語裡指回的物件短語(「そのモンスターのランク」「見せたモンスターと同じ」的
        その/それらの+頭名詞、動作回指)→ 物件 id 或 None;與 object_at 同一把尺。"""
        ref = REF_RE.match(phrase)
        if ref:
            return self.recent_of(ref.group("head"))
        if self.is_action_reference(phrase):
            return self.action_reference(phrase)
        return None

    def add_object(self, obj):
        self.card["objects"].append(obj)
        self.recent.append(obj["id"])
        return obj["id"]

    def offset_of(self, phrase, sentence_start):
        """短語在區塊原文的起點(從句子起點往後找;找不到就是句子起點):新建物件的 id 用它。"""
        offset = self.block["text"].find(phrase, sentence_start)
        return offset if offset >= 0 else sentence_start

    def object_at(self, phrase, sentence_start, owner_from=None):
        """物件短語 → (物件 id, 回指字面, 原因);回指字面 None = 本段首次出現。
        `owner_from` 是寫在物件前的從 (字面, 區域):超量素材沒寫所屬卡時用它建隱含的所屬卡。"""
        if _MATERIAL_RE.match(phrase) or _COUNTER_RE.match(phrase):
            return self.detach_object(phrase, sentence_start, owner_from)
        if _SELF_RE.match(phrase):
            return self.self_id, None, None
        if phrase == f"「{self.card['name_ja']}」":
            # 本卡以自己的卡名當主語(「「滅びの黒魔術師」は〜でのみ特殊召喚できる」,票 09):物件0,
            # 回指字面是卡名。
            return self.self_id, phrase, None
        ref = REF_RE.match(phrase)
        if ref:
            obj_id = self.recent_of(ref.group("head"))
            return obj_id, phrase, (None if obj_id else REASON_REF)
        if phrase == ACTIVATION_REF:
            obj_id = self.recent_of("カード", action="發動")
            return obj_id, phrase, (None if obj_id else REASON_REF)
        remainder = _REMAINDER_RE.match(phrase)
        if remainder:
            return self.remainder_object(phrase, remainder.group("head"),
                                         sentence_start)
        target_ref = TARGET_REF_RE.match(phrase)
        if target_ref:
            obj_id = self.recent_of(target_ref.group("head"), among=self.targeted)
            if obj_id is not None or not phrase.startswith(TARGET_OF):
                return obj_id, phrase, (None if obj_id else REASON_REF)
        if self.is_action_reference(phrase):
            obj_id = self.action_reference(phrase)
            return obj_id, phrase, (None if obj_id else REASON_REF)
        return self.new_object(phrase, sentence_start, {"kind": "新建"})

    def new_object(self, phrase, sentence_start, source, initial_position=None):
        named = _NAMED_RE.match(phrase)
        m = named or _NOUN_RE.match(phrase)
        if not m and phrase in TARGETING_THIS_FORMS:
            offset = self.offset_of(phrase, sentence_start)
            obj = new_object(f"{self.block['id']}.o{offset}", source, text=phrase,
                             span=(offset, offset + len(phrase)), block=self.block["id"],
                             condition=targeting_this_atom(self, phrase))
            return self.add_object(obj), None, None
        if not m:
            return None, None, REASON_OBJECT
        if named:
            # 「A」または「B」= 或(卡名∋A, 卡名∋B);任一個對不到就整個標解析不出。
            atoms, reason = [], None
            for name in re.findall("「([^「」]+)」", named.group("names")):
                atom, why = self.name_atom("卡名", name)
                atoms.append(atom)
                reason = reason or why
            if None in atoms:
                condition = {"op": "解析不出", "text": phrase}
            else:
                condition = atoms[0] if len(atoms) == 1 else {"op": "或", "args": atoms}
        elif split_alternatives(m.group("mods"), m.group("head")):
            atoms, reason, alternatives = [], None, []
            for piece in split_alternatives(m.group("mods"), m.group("head")):
                piece_m = _NOUN_RE.match(piece)
                piece_atoms, why = self.parse_modifiers(piece_m.group("mods"))
                alternatives.append(_noun_condition(piece_atoms, piece_m.group("head")))
                atoms.extend(piece_atoms)
                reason = reason or why
            condition = {"op": "或", "args": alternatives, "form": OR_FORM}
        else:
            atoms, reason = self.parse_modifiers(m.group("mods"))
            condition = _noun_condition(atoms, m.group("head"))
            # 名詞修飾的位置(「墓地のモンスター」「EXデッキの「No.」Xモンスター」)就是
            # 物件的初始位置:後續段「從」沒寫時由此繼承(spec「初始位置」;票 06)。
            if initial_position is None:
                located = [z for a in atoms if a.get("op") == "位置" for z in a["zones"]]
                initial_position = [dict(z) for z in located] or None
        offset = self.offset_of(phrase, sentence_start)
        obj = new_object(f"{self.block['id']}.o{offset}", source,
                         text=phrase, span=(offset, offset + len(phrase)),
                         block=self.block["id"], condition=condition,
                         count=parse_count(m), initial_position=initial_position)
        if reason:
            obj["unparsed"] = unparsed(reason)
        return self.add_object(obj), None, None

    def detach_object(self, phrase, sentence_start, owner_from=None):
        """超量素材或計數器→ (物件 id, None, 原因):`of` 是所屬的物件(有寫才有,回指字面記
        `of_ref`);超量素材沒寫所屬卡要靠 `owner_from` 建隱含的所屬卡,沒有就解析不出;
        計數器另帶種類名 `counter`。這幾個鍵有值才寫(接在工廠的格後面)。"""
        material = _MATERIAL_RE.match(phrase)
        m = material or _COUNTER_RE.match(phrase)
        of, of_ref = None, None
        if m.group("owner"):
            of, of_ref, reason = self.object_at(m.group("owner"), sentence_start)
            if of is None:
                return None, None, reason
        elif material:
            if owner_from is None:
                return None, None, REASON_OBJECT
            of = self.implicit_owner(*owner_from, sentence_start)
        offset = self.offset_of(phrase, sentence_start)
        obj = new_object(f"{self.block['id']}.o{offset}", {"kind": "新建"},
                         text=phrase, span=(offset, offset + len(phrase)),
                         block=self.block["id"],
                         kind=OBJECT_MATERIAL if material else OBJECT_COUNTER)
        if not material:
            obj["counter"] = m.group("counter")
        if of is not None:
            obj["of"] = of
        if of_ref is not None:
            obj["of_ref"] = of_ref
        return self.add_object(obj), None, None

    def implicit_owner(self, from_phrase, zones, sentence_start):
        """超量素材隱含的所屬卡:新建的超量怪獸,初始位置 = 寫在物件前的從;id 取從的字面位置。"""
        offset = self.offset_of(from_phrase, sentence_start)
        obj = new_object(f"{self.block['id']}.o{offset}", {"kind": "新建"},
                         block=self.block["id"], condition=xyz_monster_condition(),
                         initial_position=[dict(z) for z in zones])
        self.card["objects"].append(obj)
        return obj["id"]

    def zone_object(self, phrase, sentence_start):
        """區域當物件(「自分の手札を１枚選んで捨てる」):新建、沒有條件的卡(條件同頭名詞
        カード),初始位置由呼叫端以對象線的「從」寫入;與「手札からカードを１枚捨てる」同一結構。"""
        offset = self.offset_of(phrase, sentence_start)
        obj = new_object(f"{self.block['id']}.o{offset}", {"kind": "新建"},
                         text=phrase, span=(offset, offset + len(phrase)),
                         block=self.block["id"], condition=category_condition("カード"))
        return self.add_object(obj)

    def subset_object(self, phrase, container_id, sentence_start):
        """容器的子集:條件是子集自己的條件,初始位置繼承容器目前位置;
        來源的 select(全部/選)、chooser、random 有值才寫(產物省略空格)。"""
        current = self.current_position(container_id)
        obj_id, _, reason = self.new_object(
            phrase, sentence_start,
            {"kind": "子集", "of": container_id},
            initial_position=current["zones"] if current else None)
        return obj_id, None, reason

    def remainder_object(self, phrase, head, sentence_start):
        """「残りのX」= 最近的子集的容器 − 那個子集;子集是「全部」時剩餘 = 容器條件且非子集條件。"""
        subset = next((self.find(i) for i in reversed(self.recent)
                       if self.find(i)["source"]["kind"] == "子集"), None)
        if subset is None:
            return None, None, REASON_REF
        container = self.find(subset["source"]["of"])
        current = self.current_position(container["id"])
        condition = container["condition"]
        if subset["source"].get("select") == "全部":
            condition = {"op": "且", "args": [condition,
                                              {"op": "非", "arg": subset["condition"]}]}
        offset = self.offset_of(phrase, sentence_start)
        obj = new_object(f"{self.block['id']}.o{offset}",
                         {"kind": "剩餘", "of": container["id"], "minus": subset["id"]},
                         text=phrase, span=(offset, offset + len(phrase)),
                         block=self.block["id"], condition=condition,
                         initial_position=current["zones"] if current else None)
        return self.add_object(obj), None, None


def _category_of(condition):
    if not condition:
        return None
    if condition.get("op") == "大類":
        return condition["value"]
    if condition.get("op") == "且":
        for arg in condition["args"]:
            found = _category_of(arg)
            if found:
                return found
    if condition.get("op") == "或" and all(a.get("op") == "大類" for a in condition["args"]):
        return tuple(a["value"] for a in condition["args"])
    if condition.get("op") == "或" and condition.get("form") == OR_FORM:
        found = {_category_of(arg) for arg in condition["args"]}
        return found.pop() if len(found) == 1 else None
    return None


def _fill_existence(seg, m, state, sentence_start):
    """存在前提:「(容器)の中に(物件)があった」→ 容器回指線 + 子集物件。"""
    container_id, ref, reason = state.object_at(m.group("container"), sentence_start)
    if container_id is None:
        seg["unparsed"] = unparsed(reason)
        return
    subset_id, _, reason = state.subset_object(m.group("objects"), container_id,
                                               sentence_start)
    if subset_id is None:
        seg["unparsed"] = unparsed(reason)
        return
    seg["predicate"] = m.group("pred")
    seg["lines"] = [new_line(container_id, "受事", ref=ref),
                    new_line(subset_id, "受事")]
    seg["premise"] = {"op": "存在", "object": subset_id, "in": container_id}


def _fill_battle(seg, m, state, sentence_start):
    """戰鬥子句「Xが(Yと)戦闘を行う」:X 是施事(助詞 が)、Y 是受事(助詞 と),兩者都是物件;
    戰鬥不移動卡片,線沒有從/到。"""
    parsed, reason = parse_predicates(m.group("pred"))
    seg["predicate"] = m.group("pred")
    if parsed is None:
        seg["unparsed"] = unparsed(reason)
        return
    seg["actions"] = [p.action for p in parsed]
    seg["voice"] = merged_voice(parsed)
    seg["polarity"], seg["optional"] = resolve_polarity(parsed, BATTLE_AGENT_MARKER)
    mentions = [(m.group("agent"), "施事", BATTLE_AGENT_MARKER)]
    if m.group("partner"):
        mentions.append((m.group("partner"), "受事", BATTLE_PARTNER_MARKER))
    for phrase, role, marker in mentions:
        obj_id, ref, reason = state.object_at(phrase, sentence_start)
        if obj_id is None:
            seg["lines"] = []
            seg["unparsed"] = unparsed(reason)
            return
        seg["lines"].append(new_line(obj_id, role, marker=marker, ref=ref))
        if obj_id != state.self_id and obj_id not in state.recent:
            state.recent.append(obj_id)
        state.acted.setdefault(obj_id, []).extend(seg["actions"])


def _fill_clause(seg, clause_text, kind, state, sentence_start, inherited_timing=None):
    """把簡單子句解析進段;失敗就在段上標原因。`inherited_timing` 是連用形串接(同時)的前一段的
    時機:「次のスタンバイフェイズに戻り、その攻撃力は〜になる」的第二段同一時點。
    主語省略的子句(「〜できず、「X」の効果でのみ特殊召喚できる」「〜場合にEXデッキから特殊召喚できる」)
    的物件是本句「Xは」的物件或このカード,對象線標 `elided`(票 09)。"""
    exist = _EXIST_RE.match(clause_text)
    if exist:
        _fill_existence(seg, exist, state, sentence_start)
        return
    if _fill_damage(seg, clause_text, kind, state, sentence_start, inherited_timing):
        return
    battle = _BATTLE_RE.match(clause_text)
    if battle:
        _fill_battle(seg, battle, state, sentence_start)
        return
    drawing = _DRAW_RE.match(clause_text)
    if drawing:
        _fill_draw(seg, drawing, kind, state, sentence_start, inherited_timing)
        return
    m = _TARGETING_THIS_CLAUSE_RE.match(clause_text) or _CLAUSE_RE.match(clause_text)
    if m and m.group("to_front") and m.group("marker") != "が":
        m = _CLAUSE_NO_TO_FRONT_RE.match(clause_text)
    if m and m.group("marker") != "の" and parse_cause(m.group("objects") + m.group("marker")):
        # 「戦闘では破壊されない」:「戦闘で」+「は」是原因字面,不是物件 + 助詞;主語省略。
        m = None
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
    seg["predicate"] = (targeting or "") + (g("select") or "") + pred
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
    agent = None
    if g("agent"):
        agent, reason = state.agent_of(g("agent"), g("agent_marker"), g("agent_pause"), kind)
        if agent is None:
            seg["unparsed"] = unparsed(reason)
            return
    seg["agent"] = agent
    if g("recipient") in SIDE_WORDS:
        seg["recipient"] = SIDE_WORDS[g("recipient")]
    elif g("recipient"):
        # 受方是物件的回指(裝備的對象):{"object", "ref"},找不到就整段標原因(票 06)。
        obj_id, ref, reason = state.object_at(g("recipient"), sentence_start)
        if obj_id is None:
            seg["unparsed"] = unparsed(reason)
            return
        seg["recipient"] = {"object": obj_id, "ref": ref}
    if g("cause") and g("cause_front"):
        seg["unparsed"] = unparsed(REASON_TWICE)
        return
    if g("cause") or g("cause_front"):
        seg["cause"], reason = state.cause_at(g("cause") or g("cause_front"), sentence_start)
        if seg["cause"] is None:
            seg["unparsed"] = unparsed(reason)
            return
        if g("cause_front"):
            seg["cause"]["placement"] = "名詞前"
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
        seg["timing"] = parse_timing(g("timing"))
    else:
        _inherit_timing(seg, state, kind, inherited_timing)
    # 延遲段(次のスタンバイフェイズに、序列中段的條件段之後)指回被點名物件的線不標取對象。
    targetable = kind == "效果" and not is_delayed(seg)
    from_zones = None
    # 「從」寫在物件後(XをデッキからYに加える)記 placement 述語前,模板放回原位。
    from_text, from_placement = None, "名詞前"
    if g("from"):
        from_text = g("from") + g("from_particle") + (g("from_pause") or "")
    elif g("from2"):
        from_text, from_placement = g("from2") + "から", "述語前"
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
    phrases = [None] if elided else split_objects(g("objects"))
    zone_object = (not elided and from_text is None and len(phrases) == 1
                   and (g("of_effect") or "") + g("marker") == "を"
                   and _ZONE_PHRASE_RE.match(phrases[0]) and parse_from(phrases[0]))
    if zone_object:
        from_zones, from_text, from_placement = zone_object, phrases[0], ZONE_AS_OBJECT
    for phrase in phrases:
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
            obj_id, ref, reason = state.object_at(phrase, sentence_start, owner_from)
            if obj_id is None:
                seg["unparsed"] = unparsed(reason)
                return
        obj = state.find(obj_id)
        if count is not None and count.get("cmp") == "全部" and obj["source"]["kind"] == "子集":
            obj["source"]["select"] = "全部"
        role = "被召喚" if summoning else "受事"
        if targeting:
            state.targeted.append(obj_id)
        # 取對象標記:這一句點名的,或效果段裡指回先前被點名的物件(そのモンスター、選択したモンスター)。
        line = new_line(obj_id, role,
                        targeting=bool(targeting) or (targetable
                                                      and obj_id in state.targeted),
                        marker=marker, ref=ref, count=count)
        if g("pick"):
            line["pick"] = PICK_RANDOM
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
        else:
            current = state.current_position(obj_id)
            if current is not None:
                line["from"] = position(current["zones"], "繼承",
                                        inferred=current["inferred"])
            elif inferred_from:
                side = "我方" if inferred_from == "手牌" else None
                line["from"] = position([zone(inferred_from, side, side and "預設")],
                                        "推得", inferred=True)
        form = parse_placement_form(g("treat"), g("order"), g("display"))
        if to_zones is not None:
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
    _update_positions(seg, state)
    state.note_actions(seg)


def _fill_draw(seg, m, kind, state, sentence_start, inherited_timing=None):
    """抽牌子句(`draw`):抽到的卡是新建物件(「カードを」沒寫時物件沒有字面)、張數在對象線、
    從牌組(明寫或推得)到手牌(推得);玩家主語進 `agent`。"""
    g = m.groupdict().get
    parsed, reason = parse_predicates(g("pred"))
    seg["predicate"] = g("pred")
    if parsed is None or [p.action for p in parsed] != [draw.DRAW_ACTION]:
        seg["unparsed"] = unparsed(reason or REASON_CLAUSE)
        return
    seg["actions"] = [draw.DRAW_ACTION]
    seg["voice"] = merged_voice(parsed)
    seg["polarity"], seg["optional"] = resolve_polarity(parsed, None)
    if g("agent"):
        seg["agent"], reason = state.agent_of(g("agent"), g("agent_marker"),
                                              g("agent_pause"), kind)
        if seg["agent"] is None:
            seg["unparsed"] = unparsed(reason)
            return
    count, ambiguous = draw.parse_count(g("count"), g("count_front"), g("count_lead"), g("each"))
    if ambiguous or (g("cause") and g("rule")):
        seg["unparsed"] = unparsed(REASON_TWICE)
        return
    if g("each") and count is None:
        seg["unparsed"] = unparsed(REASON_CLAUSE)
        return
    if g("cause"):
        seg["cause"], reason = state.cause_at(g("cause"), sentence_start)
        if seg["cause"] is None:
            seg["unparsed"] = unparsed(reason)
            return
    elif g("rule"):
        seg["cause"] = draw.rule_cause()
    _inherit_timing(seg, state, kind, inherited_timing)
    if g("object"):
        obj_id, _, _ = state.new_object(g("object"), sentence_start, {"kind": "新建"})
    else:
        offset = state.offset_of(g("pred"), sentence_start)
        obj_id = state.add_object(new_object(
            f"{state.block['id']}.o{offset}", {"kind": "新建"}, block=state.block["id"],
            condition=category_condition(draw.DRAWN_OBJECT)))
    if g("from"):
        from_ = position(draw.drawer_deck(parse_from(g("from")), agent_side(seg["agent"])),
                         "明寫", text=g("from") + "から")
        state.find(obj_id)["initial_position"] = list(from_["zones"])
    else:
        from_ = position([zone(INFERENCE_TABLE[draw.DRAW_ACTION][0], None)], "推得",
                         inferred=True)
    line = new_line(obj_id, "受事", marker=draw.DRAWN_MARKER if g("object") else None,
                    count=count)
    line["from"] = from_
    line["to"] = position([zone(INFERENCE_TABLE[draw.DRAW_ACTION][1], None)], "推得",
                          inferred=True)
    seg["lines"] = [line]
    state.acted.setdefault(obj_id, []).extend(seg["actions"])
    _update_positions(seg, state)
    state.note_actions(seg)


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
        parsed, reason = parse_predicates(pred)
    return pred, to_phrase, parsed, reason


def _fill_damage(seg, clause_text, kind, state, sentence_start, inherited_timing=None):
    """傷害、回復與傷害值變更的句型(`damage`)→ 填格回 True;不是這些句型回 False。
    玩家主語/受方進 `agent`/`recipient`、不建物件;物件主語(「このカードが」)是角色施事的對象線。"""
    found = damage.match_clause(clause_text)
    if found is None:
        return False
    form, m = found
    g = m.groupdict().get
    pred = g("pred") or damage.MODIFY_DAMAGE_PREDICATE
    seg["predicate"], seg["voice"] = pred, "主動"
    if form == damage.MODIFY or pred == damage.NEGATED_RECEIVE:
        seg["actions"] = [MODIFY_ACTION]
        seg["modified"] = (damage.parse_value(g("value")) if form == damage.MODIFY
                           else damage.parse_value("０"))
        if g("limit"):
            seg["modified"]["limit"] = damage.parse_limit(g("limit"))
    else:
        parsed, reason = parse_predicates(
            (damage.DAMAGE_OBJECT if form != damage.RECOVER else "") + pred)
        if parsed is None:
            seg["unparsed"] = unparsed(reason)
            return True
        seg["actions"] = [p.action for p in parsed]
        seg["voice"] = merged_voice(parsed)
        seg["polarity"], seg["optional"] = resolve_polarity(parsed, None)
    if g("recipient"):
        seg["recipient"] = damage.player(g("recipient"), g("recipient_tail") or "に")
    elif g("recipient_pre"):
        seg["recipient"] = damage.player(g("recipient_pre"), "に", damage.PLACEMENT_BEFORE_NOUN)
    noun = g("noun") or damage.PLAIN_NOUN
    cause = damage.noun_cause(noun) if g("noun") else None
    verbal = g("cause") or g("cause_pre")
    if verbal:
        if cause is not None:
            seg["unparsed"] = unparsed(REASON_TWICE)
            return True
        cause, reason = state.cause_at(verbal, sentence_start)
        if cause is None:
            seg["unparsed"] = unparsed(reason)
            return True
        if g("cause_pre"):
            cause["placement"] = damage.CAUSE_BEFORE_SUBJECT
    if g("source_that") or g("source_object"):
        if cause is None:
            seg["unparsed"] = unparsed(REASON_CAUSE)
            return True
        source = {"text": g("source_that") or g("source_tail")}
        if g("source_object"):
            obj_id, ref, reason = state.object_at(g("source_object"), sentence_start)
            if obj_id is None:
                seg["unparsed"] = unparsed(reason)
                return True
            source["object"] = obj_id
            if ref:
                source["ref"] = ref
        cause["source"] = source
    seg["cause"] = cause
    if g("amount_pre") and g("amount"):
        seg["unparsed"] = unparsed(REASON_TWICE)
        return True
    amount_text = g("amount_pre") or g("amount")
    if amount_text:
        seg["amount"] = damage.parse_amount(amount_text, noun)
        if seg["amount"] is None:
            seg["unparsed"] = unparsed(REASON_CLAUSE)
            return True
    if g("duration"):
        seg["duration"] = {"kind": DURATION_TURN, "text": g("duration")}
    _inherit_timing(seg, state, kind, inherited_timing)
    subject = g("subject")
    if subject in SIDE_WORDS and g("subject_marker"):
        seg["agent"] = SIDE_WORDS[subject]
    elif subject:
        obj_id, ref, reason = state.object_at(subject, sentence_start)
        if obj_id is None:
            seg["unparsed"] = unparsed(reason)
            return True
        seg["lines"] = [new_line(obj_id, "施事", marker=g("subject_marker"), ref=ref)]
        if obj_id != state.self_id and obj_id not in state.recent:
            state.recent.append(obj_id)
    return True


def _update_positions(seg, state):
    """位置自動規則:極性「做」的條件/代價/效果/召喚手續段,把「到」寫回目前位置。"""
    if seg["polarity"] != "做" or seg["kind"] not in ("條件", "代價", "效果",
                                                      "召喚手續"):
        return
    for line in seg["lines"]:
        if line["to"]:
            state.positions[line["object"]] = {
                "zones": line["to"]["zones"], "inferred": line["to"]["inferred"]}


def _segment(state, kind, start, end):
    text = state.block["text"]
    return new_segment(f"{state.block['id']}.s{start}", kind, (start, end),
                       text[start:end])


def sentences(text, body_start, end=None):
    """以「。」切句,回傳 (start, end) 且去掉頭尾空白換行;句號不含在範圍內。
    `end` 限定只切到這個偏移(● 分支的範圍,票 06)。"""
    limit = len(text) if end is None else end
    spans = []
    pos = body_start
    while pos < limit:
        stop = text.find("。", pos, limit)
        if stop < 0:
            stop = limit
        start, stop_at = pos, stop
        while start < stop_at and text[start] in "\n ":
            start += 1
        while stop_at > start and text[stop_at - 1] in "\n ":
            stop_at -= 1
        if start < stop_at:
            spans.append((start, stop_at))
        pos = stop + 1
    return spans


def _condition_and_rest(state, seg_start, clause_start, body, trig, segs, kind="條件"):
    """觸發子句 → 條件段(範圍從 seg_start 起算:前面可能有前提;「〜場合、代わりに」的是被代替段,
    不更新位置);回傳 (剩下的子句, 它的起點)。"""
    cond_end = clause_start + len(trig.group("cond"))
    seg = _segment(state, kind, seg_start, cond_end + len(trig.group("trig")))
    seg["trigger"] = trig.group("trig")
    _fill_clause(seg, trig.group("cond"), kind, state, clause_start)
    segs.append(seg)
    rest = trig.group("rest")
    return rest, clause_start + body.rfind(rest) if rest else None


def _battle_timing(state, body, body_start, seg_start, segs):
    """發動句子句開頭的戰鬥時點 → 條件段(觸發形是時點字面、沒有動作詞),append 進 segs;
    回傳 (剩下的子句, 它的起點),不是就回 None。「その」沒有同一句的前一個條件段可指時不認。"""
    m = _BATTLE_TIMING_RE.match(body)
    if not m or (m.group("ref") and not segs):
        return None
    seg = _segment(state, "條件", seg_start, body_start + m.end("trig"))
    seg["trigger"] = m.group("trig")
    if m.group("ref"):
        seg["premise"] = {"op": PREMISE_DONE, "segment": segs[-1]["id"]}
    segs.append(seg)
    return m.group("rest"), body_start + m.start("rest")


def _attach_premise(seg, premise):
    """前提寫進段;段已有前提(存在前提的條件段)時依字面順序組成「且」。"""
    if seg["premise"] is None:
        seg["premise"] = premise
        return
    atoms = premise["args"] if premise.get("op") == "且" else [premise]
    seg["premise"] = {"op": "且", "args": atoms + [seg["premise"]]}


def _cost_and_effect(state, clause, start, seg_start, replaces=None):
    """效果子句 → [(效果段, 連接)],或舊式代價句「(代價)る事で、(效果)」→ 代價段 + 效果段。
    效果子句若是連用形串接(「〜に戻り、その攻撃力は〜になる」)切成多段、連接「同時」(票 08);
    第一個段的範圍從 seg_start 起算(前面可能有前提)。`replaces` 是做代替的段要記的被代替段 id。"""
    segs = []
    cost = _OLD_COST_RE.match(clause)
    if cost:
        cost_text = cost.group("cost")
        cost_seg = _segment(state, "代價", seg_start, start + len(cost_text))
        _fill_clause(cost_seg, cost_text, "代價", state, start)
        segs.append((cost_seg, None))
        # 效果子句接在「事で、」後面,它的段範圍從自己起算(前提已在代價段上)。
        start += len(clause) - len(cost.group("rest"))
        clause, seg_start = cost.group("rest"), None
    for i, (offset, piece) in enumerate(split_continuative(clause)):
        piece_start = start + offset
        join = JOIN if i else None
        then = _THEN_RE.match(piece) if i else None
        if then:
            piece_start += then.end()
            piece = piece[then.end():]
            join = SEQUENCE_JOIN
        seg = _segment(state, "效果", seg_start if (i == 0 and seg_start is not None)
                       else piece_start, piece_start + len(piece))
        if replaces:
            seg["replaces"] = replaces
        _fill_effect(seg, piece, "效果", state, piece_start,
                     segs[-1][0]["timing"] if i and not then else None)
        _hold_topic(seg, piece, state, piece_start)
        segs.append((seg, join))
        derived = _derived_modify(seg, state)
        if derived is not None:
            segs.append((derived, JOIN))
    return segs


SEQUENCE_JOIN = "先後"
_THEN_RE = re.compile("^その後、?")


def _derived_modify(seg, state):
    """「攻撃力３００アップの装備カード扱いで〜に装備する」的裝備段 → 衍生的性質變更段:
    範圍是 treat 字面裡的「攻撃力３００アップ」、記 `derived_from` = 裝備段、對象線是裝備的對象
    (裝備段的受方物件);與裝備段同時。沒有增減前綴、或受方不是物件時回 None。"""
    recipient = seg["recipient"]
    if seg["unparsed"] or not isinstance(recipient, dict) or "object" not in recipient:
        return None
    treats = [((line["to"] or {}).get("form") or {}).get("treat") for line in seg["lines"]]
    delta = next((parse_treat_delta(t["text"]) for t in treats if t), None)
    if delta is None:
        return None
    literal, modified, predicate = delta
    start = seg["span"][0] + seg["text"].index(literal)
    derived = _segment(state, "效果", start, start + len(literal))
    derived.update(actions=[MODIFY_ACTION], predicate=predicate, voice="主動",
                   modified=modified, derived_from=seg["id"],
                   lines=[new_line(recipient["object"], "受事")])
    return derived


def _hold_topic(seg, piece, state, piece_start):
    """左半解不出時,它句首的「Xは」仍是後面主語省略的子句的主語(「装備モンスターは相手の効果の
    対象にならず、戦闘では破壊されない」);物件等用到時才建(`BlockState.elided_subject`)。"""
    if not seg["unparsed"]:
        return
    m = _TOPIC_RE.match(piece)
    state.subject = None
    state.topic = ((m.group("topic"), piece_start) if m and not parse_cause(m.group())
                   else TOPIC_UNKNOWN)


def _inherit_timing(seg, state, kind, inherited_timing):
    """沒寫時機的段:連用形串接(同時)的後一段與前一段同一時點(時機照抄、字面只在前一段);
    延遲序列裡的效果段是隱含的延遲。"""
    if inherited_timing:
        seg["timing"] = {k: v for k, v in inherited_timing.items() if k != "text"}
    elif state.delayed and kind == "效果":
        seg["timing"] = implicit_delay()


def _fill_effect(seg, clause, kind, state, clause_start, inherited_timing=None):
    """效果子句:性質變更句(「その攻撃力は〜倍になる」)走它的句型,其餘是簡單子句。"""
    modify = parse_modify(clause)
    if modify is None:
        seg["duration"] = find_battle_duration(clause)
        _fill_clause(seg, clause, kind, state, clause_start, inherited_timing)
        return
    line, reason = _modify_subject(modify["subject"], modify["marker"], state, clause_start)
    if line is None:
        seg["unparsed"] = unparsed(reason)
        return
    seg["actions"] = [MODIFY_ACTION]
    seg["predicate"], seg["voice"] = modify["predicate"], "主動"
    seg["modified"] = modify["modified"]
    seg["duration"] = modify["duration"] or seg["duration"]
    _inherit_timing(seg, state, kind, inherited_timing)
    line["targeting"] = line["object"] in state.targeted and not is_delayed(seg)
    seg["lines"] = [line]


# 性質變更句的主語:「[區域の][全ての]物件短語の」;區域照簡單子句記成對象線的從,
# 「全ての」記成對象線的數量(屬於這次提及)。
_MODIFY_SUBJECT_RE = re.compile(
    f"^(?:(?P<from>{_ZONE_PHRASE})の)?(?P<all>全ての)?(?P<phrase>.+)の$")
ALL_PREFIX = "全ての"


def _modify_subject(subject, marker, state, sentence_start):
    """性質變更句的主語 → (對象線, None) 或 (None, 原因)。回指字面(その、このカードの、
    そのモンスターの…)照舊記在 `ref`;其餘是「物件短語 + の」,物件照一般規則解析。"""
    if subject in MENTION_FORMS:
        head = mention_head(subject)
        obj_id = state.self_id if head is None else state.recent_of(head)
        if obj_id is None:
            return None, REASON_REF
        return new_line(obj_id, "受事", marker=marker, ref=subject), None
    m = _MODIFY_SUBJECT_RE.match(subject)
    if not m:
        return None, REASON_OBJECT
    from_zones = parse_from(m.group("from")) if m.group("from") else None
    phrase = m.group("phrase")
    if m.group("from") and from_zones is None:
        phrase = subject[:-1]
        if m.group("all"):
            return None, REASON_OBJECT
    obj_id, ref, reason = state.object_at(phrase, sentence_start)
    if obj_id is None:
        return None, reason
    count = {"text": ALL_PREFIX, "cmp": "全部"} if m.group("all") else None
    line = new_line(obj_id, "受事", marker=marker, ref=ref, count=count)
    if from_zones is not None:
        line["from"] = position(from_zones, "明寫", text=m.group("from") + "の")
        obj = state.find(obj_id)
        if obj["source"]["kind"] == "新建" and obj["initial_position"] is None:
            obj["initial_position"] = list(from_zones)
    return line, None


def _material_segment(state, start, end):
    """素材行(「「ブラック・マジシャン」＋光・闇属性モンスター」)→ 召喚手續段:沒有動作詞,
    每個素材一條角色「素材」的對象線(以「＋」分);素材短語認不得的整段標原因。"""
    seg = _segment(state, KIND_PROCEDURE, start, end)
    phrase_start = start
    for phrase in seg["text"].split(MATERIAL_JOINER):
        times = _MATERIAL_TIMES_RE.match(phrase)
        count = None
        if times:
            phrase = times.group("phrase")
            count = {"text": times.group("times"), "unit": MATERIAL_TIMES,
                     "value": int(times.group("digits").translate(FULLWIDTH_DIGITS)), "cmp": "="}
        obj_id, ref, reason = state.object_at(phrase, phrase_start)
        if obj_id is None:
            seg["unparsed"] = unparsed(reason)
            return seg
        seg["lines"].append(new_line(obj_id, ROLE_MATERIAL, ref=ref, count=count))
        written = phrase + (times.group("times") if times else "")
        phrase_start += len(written) + len(MATERIAL_JOINER)
    return seg


def _treat_as_segment(state, start, end, treat):
    """「〜として扱う」句 → 修飾段(卡片屬性表的列由 names_attributes 另記):被改的屬性是卡名/字段
    (名稱換成名稱列 id)或大類/子類型,述語字面 として扱う,對象線是此卡。"""
    seg = _segment(state, KIND_MODIFIER, start, end)
    seg["predicate"], seg["voice"] = TREAT_PREDICATE, "主動"
    seg["lines"] = [new_line(state.self_id, "受事", marker="は")]
    modified = dict(treat)
    if "items" in modified:
        items = []
        for item in modified["items"]:
            row = state.names.get(item["text"])
            if row is None:
                seg["unparsed"] = unparsed(REASON_NAME_UNKNOWN)
                return seg
            items.append({"name": row["id"], "tail": item["tail"]})
        modified["items"] = items
        # 「X」後接 カード/モンスター 的是字段,否則是卡名(與 names_attributes 同一把尺)。
        tails = [i["tail"] for i in items[:-1]] + [items[-1]["tail"] or modified.get("suffix")]
        modified["attr"] = "字段" if any(tails) else "卡名"
    seg["modified"] = modified
    return seg


def _apply_duration(segs, duration):
    for seg, _ in segs:
        if seg["duration"] is None:
            seg["duration"] = dict(duration)


def parse_sentence(state, start, end):
    """一句 → [(段, 與前一段的連接)](發動句可產生條件段 + 代價段;舊式條件句產生條件段 + 效果段;
    舊式代價句產生代價段 + 效果段;連用形串接的效果句、代價子句切成多段、連接「同時」)。
    句首的前提先剝掉,掛在第一個段上、段的範圍從前提起算;「〜場合、代わりに〜」的條件段改標
    被代替、後面的段記代替誰(「代わりに」留在它的範圍內)。"""
    text = state.block["text"]
    sent = text[start:end]
    state.subject = state.topic = None
    summon_block = state.block["kind"] == BLOCK_SUMMON
    if state.block["kind"] == BLOCK_MATERIAL:
        return [(_material_segment(state, start, end), None)]
    treat = parse_treat_as(sent)
    if treat is not None:
        return [(_treat_as_segment(state, start, end, treat), None)]
    for pattern, reason in OMITTED_SENTENCES:
        if pattern.match(sent):
            state.omit(start, sent, reason)
            return []
    note = _LIMIT_NOTE_RE.search(sent)
    if note and _LIMIT_SENTENCE_RE.match(note.group("note")):
        state.omit(start + note.start(), note.group(), INTERVAL_REASON)
        end = start + note.start()
        sent = text[start:end]
    if REPEAT_RE.match(sent):
        # 重複到停為止(spec 故事 28):第一輪已由前面的句子(或「」裡的字面)寫出,這一句只標未結構化,
        # 不抽動作詞、不更新位置;反向檢查與覆蓋報告各另列一類。
        seg = _segment(state, "效果", start, end)
        seg["unstructured"] = True
        return [(seg, None)]
    act = _ACTIVATION_RE.match(sent)
    body = act.group("body") if act else sent
    turn_seg = None
    turn = _TURN_RE.match(body)
    if turn:
        # 「〜したターン、」:動作子句是條件段(觸發形 ターン),後面的第一個段以前提引用它。
        turn_seg = _segment(state, "條件", start, start + len(turn.group("cond")) + len(TURN_TRIGGER))
        turn_seg["trigger"] = TURN_TRIGGER
        _fill_clause(turn_seg, turn.group("cond"), "條件", state, start)
        start += turn.start("rest")
        body = turn.group("rest")
    interval = INTERVAL_RE.match(body)
    if interval:
        # 句首的「１ターンに１度、」(①：１ターンに１度、〜):次數限制不記,進略過文本。
        state.omit(start, interval.group(), INTERVAL_REASON)
        start += interval.end()
        body = body[interval.end():]
    seg_from = start
    lead, lead_length = parse_leading_duration(body)
    if lead is not None:
        start += lead_length
        body = body[lead_length:]
    premise, premise_end, clause_start = split_premises(body, state, start,
                                                        parse_from, zone_literal)
    body = text[clause_start:start + len(body)]
    if act and premise and body in ("", "に"):
        seg = _segment(state, "條件", seg_from, premise_end)
        seg["premise"] = premise
        if lead is not None:
            seg["duration"] = lead
        return [(seg, None)]
    segs = []
    trigger_re = _TRIGGER_RE if act else (_SUMMON_TRIGGER_RE if summon_block
                                         else _OLD_TRIGGER_RE)
    rest, rest_start, seg_start = body, clause_start, seg_from
    timing = _battle_timing(state, body, clause_start, seg_from, segs) if act else None
    trig = None if timing else trigger_re.match(body)
    replaced = trig is not None and trig.group("rest").startswith(REPLACEMENT_PREFIX)
    if trig:
        rest, rest_start = _condition_and_rest(state, seg_from, clause_start, body,
                                               trig, segs,
                                               "被代替" if replaced else "條件")
        seg_start = rest_start
        timing = (_battle_timing(state, rest, rest_start, rest_start, segs)
                  if act and rest else None)
    if timing:
        rest, rest_start = timing
        seg_start = rest_start
    if segs and state.block["segments"] and not summon_block:
        state.delayed = True
    segs = [(seg, None) for seg in segs]
    if rest and not act:
        if replaced:
            rest_start += len(REPLACEMENT_PREFIX)
            rest = rest[len(REPLACEMENT_PREFIX):]
        segs += _cost_and_effect(state, rest, rest_start, seg_start,
                                 replaces=segs[0][0]["id"] if replaced else None)
    elif rest:
        # 代價子句也可連用形串接(「〜を墓地へ送り、〜を対象として発動できる」,票 06):
        # 最後一截要以て形收尾才算代價。
        pieces = split_continuative(rest)
        for i, (offset, piece) in enumerate(pieces):
            piece_start = rest_start + offset
            seg = _segment(state, "代價", seg_start if i == 0 else piece_start,
                           piece_start + len(piece))
            if i < len(pieces) - 1 or piece.endswith(("て", "で")):
                _fill_clause(seg, piece, "代價", state, piece_start)
                _hold_topic(seg, piece, state, piece_start)
            else:
                seg["unparsed"] = unparsed(REASON_ACTIVATION)
            segs.append((seg, JOIN if i else None))
    if premise and segs:
        _attach_premise(segs[0][0], premise)
    if lead is not None:
        _apply_duration(segs[:1], lead)
        _apply_duration(segs[1:], inherited_duration(lead))
    if is_lasting(premise):
        _apply_duration(segs, lasting())
    if turn_seg is not None:
        if segs:
            _attach_premise(segs[0][0], {"op": PREMISE_HAPPENED, "segment": turn_seg["id"]})
        segs.insert(0, (turn_seg, None))
    if summon_block:
        # 召喚條件區塊的段類別(spec):做的是召喚手續(含「〜した場合」的手續子句),
        # 不能/只能/必須的是限制。
        for seg, _ in segs:
            if seg["kind"] in ("條件", "代價", "效果") and seg["trigger"] != TURN_TRIGGER:
                seg["kind"] = (KIND_PROCEDURE if seg["polarity"] == "做"
                               else KIND_RESTRICTION)
    return segs
