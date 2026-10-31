# -*- coding: utf-8 -*-
"""框架述詞的字彙與參考評估器(named-queries 票 06,ADR-0018)。

述詞字彙只有這一份:述詞的欄名(FIELDS,GLOSSARY「框架述詞」條的詞)、每欄對到匯出框列的哪個鍵(EXPORT_PATH;
匯出鍵名 FRAME_KEYS/PHRASE_KEYS/SEGMENT_KEYS 是票 05 定的拼法,export_frames.py 從這裡 import)、每欄的值域(DOMAIN
讀 closed_values/constraints/action_lemmas 的封閉表,不抄第二份)。具名查詢目錄(票 07)寫述詞、檢查述詞,命中與張數
(票 08)跑評估器,都 import 這裡。

接縫:matches(述詞, 匯出的框列) → 命中與否。讀的是 data/action_frames.json 的框列(句[].frames[] 的一個 dict,只在
有值時帶鍵),**不讀 frames.json 的框架**;規格 3 的 JS 評估器讀同一份輸入、語意同這裡,例子夾具 predicate-fixture.json
兩邊共用。

述詞是一個 dict,欄 → 值(規格「參考評估器」段的語意):
    欄間 AND、同欄多值 OR,全部在同一框列上;沒寫的欄不看,空述詞全中;框列沒有該鍵就不中。
    每欄的值是清單(單一字串等於一項的清單);區域欄的每項是 [玩家或 None, 區域七值],None 是不看玩家
    (規格「玩家相對與無」(a):相對/無 是值域裡的值,述詞可選,不折值)。
    詞元/位置/極性/否定形/態/施事者/方式類/動作對象  框列的單值鍵與清單任一值相等
    來源/目的/所在          框列 regions 該欄的 (玩家, 區域) 清單與述詞清單任一項相配:區域相等、述詞有玩家時玩家相等
    受事者中心詞/目的中心詞  框列 phrases.patient/goal 的任一段中心詞以述詞任一值**結尾**(規格「中心詞尾綴」(a):
                            モンスター 中 効果モンスター、不中 モンスターカード)
    中心詞類/數量類/修飾語類  受事者片語任一段的 head_kind/quantity 在清單、或任一段的 modifiers 與清單有交集;
                            各欄獨立看段,不要求同一段
極性省略不是「肯定與可能」——那是目錄的預設(票 07 載入時補成明文清單),評估器對沒寫的欄一律不看。
規格裁定的具名查詢寫法:詞元節點 = {詞元, 極性: [肯定, 可能]};(耐性) = 否定形 [受身, 不成不受];(限制) = 否定形 [不可能]。

problems(述詞) → 違反字彙的清單(不認得的欄、值不在值域、區域項形狀、詞元不是正規詞元);matches 遇到不認得的欄
直接 raise,其餘不檢查(目錄載入時先 problems)。
card_sets(述詞清單, 句列) → 每個述詞三個位置各一個卡集合(票 08 的目錄張數);cards_hash(卡集合) → 卡片密碼依數值
排序、十進位以逗號連寫後 sha1 前 16 碼(規格說「連寫」;加逗號是讓 12,345 與 123,45 不同串),規格 3 重算要相同。
"""
import hashlib

import action_lemmas
from closed_values import (AGENTS, HEAD_KINDS, MANNER_KINDS, MODIFIER_KINDS, NEGATION_FORMS, PATIENT_MODES, PLAYERS,
                           QUANTITY_KINDS, REGION_GOAL, REGION_PLACE, REGION_SOURCE, ZONES)
from constraints import POL_AFFIRM, POL_CAN, POL_NEG, POSITIONS

# ── 匯出框列的鍵名(票 05 定,匯出序;export_frames.py 從這裡 import,拼法不改)──
FRAME_KEYS = ("action", "position", "polarity", "voice", "negation", "regions", "agent",
              "manner_kind", "manner_value", "phrases", "patient_mode")
PHRASE_KEYS = ("patient", "goal")
SEGMENT_KEYS = ("head", "head_kind", "quantity", "modifiers")

# ── 述詞的欄名(GLOSSARY「框架述詞」條;目錄檔與使用者述詞都用這些字)──
FIELD_LEMMA, FIELD_POSITION, FIELD_POLARITY, FIELD_NEGATION, FIELD_VOICE = "詞元", "位置", "極性", "否定形", "態"
FIELD_SOURCE, FIELD_GOAL, FIELD_PLACE = "來源", "目的", "所在"
FIELD_PATIENT_HEAD, FIELD_GOAL_HEAD = "受事者中心詞", "目的中心詞"
FIELD_HEAD_KIND, FIELD_QUANTITY, FIELD_MODIFIERS = "中心詞類", "數量類", "修飾語類"
FIELD_AGENT, FIELD_MANNER, FIELD_PATIENT_MODE = "施事者", "方式類", "動作對象"
FIELDS = (FIELD_LEMMA, FIELD_POSITION, FIELD_POLARITY, FIELD_NEGATION, FIELD_VOICE,
          FIELD_SOURCE, FIELD_GOAL, FIELD_PLACE, FIELD_PATIENT_HEAD, FIELD_GOAL_HEAD,
          FIELD_HEAD_KIND, FIELD_QUANTITY, FIELD_MODIFIERS, FIELD_AGENT, FIELD_MANNER, FIELD_PATIENT_MODE)

# 述詞欄 ↔ 匯出鍵的路徑(欄讀框列的哪裡;manner_value 表示形式值沒有述詞欄,規格的述詞欄表沒列它)
EXPORT_PATH = {
    FIELD_LEMMA: ("action",), FIELD_POSITION: ("position",), FIELD_POLARITY: ("polarity",),
    FIELD_NEGATION: ("negation",), FIELD_VOICE: ("voice",), FIELD_AGENT: ("agent",),
    FIELD_MANNER: ("manner_kind",), FIELD_PATIENT_MODE: ("patient_mode",),
    FIELD_SOURCE: ("regions", REGION_SOURCE), FIELD_GOAL: ("regions", REGION_GOAL),
    FIELD_PLACE: ("regions", REGION_PLACE),
    FIELD_PATIENT_HEAD: ("phrases", "patient", "head"), FIELD_GOAL_HEAD: ("phrases", "goal", "head"),
    FIELD_HEAD_KIND: ("phrases", "patient", "head_kind"), FIELD_QUANTITY: ("phrases", "patient", "quantity"),
    FIELD_MODIFIERS: ("phrases", "patient", "modifiers"),
}
REGION_FIELDS = (FIELD_SOURCE, FIELD_GOAL, FIELD_PLACE)
HEAD_FIELDS = (FIELD_PATIENT_HEAD, FIELD_GOAL_HEAD)
# 相等比對的單值欄 → 值域(封閉表就是值域;極性的三值在 constraints)
POLARITIES = (POL_AFFIRM, POL_NEG, POL_CAN)
DOMAIN = {
    FIELD_POSITION: POSITIONS, FIELD_POLARITY: POLARITIES, FIELD_NEGATION: NEGATION_FORMS,
    FIELD_VOICE: action_lemmas.VOICES, FIELD_AGENT: AGENTS, FIELD_MANNER: MANNER_KINDS,
    FIELD_PATIENT_MODE: PATIENT_MODES, FIELD_HEAD_KIND: HEAD_KINDS, FIELD_QUANTITY: QUANTITY_KINDS,
    FIELD_MODIFIERS: MODIFIER_KINDS,
}
SEGMENT_FIELDS = (FIELD_HEAD_KIND, FIELD_QUANTITY, FIELD_MODIFIERS)


def values_of(predicate, field):
    """述詞一欄的值清單(單一字串視為一項)。"""
    value = predicate[field]
    return [value] if isinstance(value, str) else list(value)


def lemma_problems(lemma):
    """詞元要是框架抽取產得出的正規詞元(沿用 action_lemmas 的對照表與 frames 的補語不併判準;
    frames 延後 import——評估器本身不需要它)。"""
    canonical = action_lemmas.normalize(lemma)[0]
    if canonical != lemma:
        return ["%s 不是框架抽取產得出的正規詞元:%s(正規詞元是 %s)" % (FIELD_LEMMA, lemma, canonical)]
    import frames
    if frames.default_extractor().splits_complement(lemma):
        return ["%s 的補語是值或屬性,框架抽取不併入詞元:%s(詞元寫 にする/とする、補語用%s)"
                % (FIELD_LEMMA, lemma, FIELD_GOAL_HEAD)]
    return []


def problems(predicate):
    """述詞 → 違反字彙的清單(空清單就是合字彙);目錄載入與使用者述詞的檢查都用這一條。"""
    found = []
    for field in predicate:
        if field not in FIELDS:
            found.append("不認得的欄:%s" % field)
            continue
        values = values_of(predicate, field)
        if field in REGION_FIELDS:
            for item in values:
                if not (isinstance(item, (list, tuple)) and len(item) == 2):
                    found.append("%s 的每項要是 [玩家或 null, 區域]:%s" % (field, item))
                    continue
                player, zone = item
                if player is not None and player not in PLAYERS:
                    found.append("%s 的玩家不在值域:%s" % (field, player))
                if zone not in ZONES:
                    found.append("%s 的區域不在值域:%s" % (field, zone))
        elif field in HEAD_FIELDS:
            found.extend("%s 的值要是非空字串:%r" % (field, v) for v in values if not (isinstance(v, str) and v))
        elif field == FIELD_LEMMA:
            for lemma in values:
                found.extend(lemma_problems(lemma))
        else:
            found.extend("%s 的值不在值域:%s" % (field, v) for v in values if v not in DOMAIN[field])
    return found


def _region_check(key, wanted):
    def check(row):
        pairs = (row.get("regions") or {}).get(key) or ()
        return any(zone == z and (player is None or player == p) for player, zone in wanted for p, z in pairs)
    return check


def _head_check(phrase, wanted):
    def check(row):
        segments = (row.get("phrases") or {}).get(phrase) or ()
        return any(seg["head"].endswith(w) for seg in segments for w in wanted)
    return check


def _segment_check(key, wanted):
    def check(row):
        segments = (row.get("phrases") or {}).get("patient") or ()
        if key == "modifiers":
            return any(kind in wanted for seg in segments for kind in seg.get(key) or ())
        return any(seg.get(key) in wanted for seg in segments)
    return check


def _value_check(key, wanted):
    return lambda row: row.get(key) in wanted


def matcher(predicate):
    """述詞 → 框列的判定函式(全語料跑時只編一次);不認得的欄 raise ValueError。"""
    unknown = [field for field in predicate if field not in FIELDS]
    if unknown:
        raise ValueError("不認得的欄:" + "、".join(unknown))
    checks = []
    for field in FIELDS:            # 依 FIELDS 序——詞元先比,大多數框列在第一欄就淘汰
        if field not in predicate:
            continue
        path, wanted = EXPORT_PATH[field], values_of(predicate, field)
        if field in REGION_FIELDS:
            checks.append(_region_check(path[1], [tuple(item) for item in wanted]))
        elif field in HEAD_FIELDS:
            checks.append(_head_check(path[1], wanted))
        elif field in SEGMENT_FIELDS:
            checks.append(_segment_check(path[2], set(wanted)))
        else:
            checks.append(_value_check(path[0], set(wanted)))
    return lambda row: all(check(row) for check in checks)


def matches(predicate, row):
    """接縫:(述詞, 匯出的框列)→ 命中與否。"""
    return matcher(predicate)(row)


def card_sets(predicates, sentences):
    """述詞清單 × 匯出檔的句列(句[]) → 每個述詞 {位置: 命中的卡片密碼集合}(票 08 的目錄張數;
    三個位置各自算,一張卡多框算一張)。"""
    matchers = [matcher(p) for p in predicates]
    out = [{position: set() for position in POSITIONS} for _ in predicates]
    for row in sentences:
        card = row["card"]
        for fr in row["frames"]:
            position = fr["position"]
            for sets, match in zip(out, matchers):
                if match(fr):
                    sets[position].add(card)
    return out


def cards_hash(cards):
    """卡集合 → 雜湊:卡片密碼依數值排序、十進位以逗號連寫,sha1 前 16 碼。"""
    return hashlib.sha1(",".join(str(card) for card in sorted(cards)).encode("utf-8")).hexdigest()[:16]
