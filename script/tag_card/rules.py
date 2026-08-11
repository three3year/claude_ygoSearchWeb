"""效果類型規則層的規則登記處。

一條規則是一筆資料:編號、判別條件(人看的敘述 + 機器跑的樣式)、對應類型、
新增票號、變更記錄。規則只寫影子預測、不寫 `kind`(ADR-0002),因此每一條都必須
能被獨立驗證——[[官方明示]]的那批效果句就是現成的驗證集,判定票的判定結果是
第二份。

**覆蓋條數不寫在這裡**:由建置流程統計後回寫 `docs/effect_kind_rules.md`
(票06「不靠人工計數」)。這裡只放定義,數字全部是算出來的。

規則變更僅限 CHANGE_REASONS 的三種情況,每次變更都要留下理由與票號;合併的舊條
標記 `merged_into` 而不刪行,規則的來歷因此永遠可追溯。

給 tagcard.build_tag_cards 用,不是對外接縫。詞彙見 CONTEXT.md。
"""
import hashlib
import re

from official import (KIND_CONTINUOUS, KIND_IGNITION, KIND_NON_EFFECT,
                      KIND_QUICK, KIND_TRIGGER, KIND_UNCLASSIFIED, KINDS)

# 覆蓋不足這個條數的規則不進規則層——過擬合的單卡特例不得偽裝成通則(Story 46)
MIN_COVERAGE = 8
# 規則對官方明示的一致率門檻。低於門檻不自動停用(那會把問題藏起來),而是在報告
# 裡標 FAIL 並列出全部不一致,由使用者決定收緊條件還是留著。
AGREEMENT_THRESHOLD = 0.99

# 判別條件掃描的範圍
SCOPE_ACTIVATION = "發動子句"
SCOPE_CLAUSE = "效果句"
SCOPES = (SCOPE_ACTIVATION, SCOPE_CLAUSE)

# 規則變更的三種正當理由,以外的理由一律不接受(spec「規則變更僅三種情況」)
CHANGE_TOO_BROAD = "too_broad"
CHANGE_OVERLAP = "overlap"
CHANGE_MERGE = "merge"
CHANGE_REASONS = {
    CHANGE_TOO_BROAD: "判別條件太寬(同票內 2 筆以上影子預測不一致)",
    CHANGE_OVERLAP: "與新規則判別條件重疊且結論不同",
    CHANGE_MERGE: "兩條相似規則合併",
}

_ID_RE = re.compile(r"^R[1-9][0-9]*$")

# 觸發事件的寫法。句子裡有事件就會形成連鎖,不可能是永續效果或無種類效果;
# 這一組是幾條「不發動」規則的共同排除條件。
_EVENT = r"た場合|た時|時に|時、|度に|毎に|ダメージ計算|宣言"
# 「発動」二字出現在句中即代表這一句會形成連鎖
_ACTIVATES = r"発動"


def define(rid, kind, scope, condition, pattern, ticket, exclude=None,
           changes=(), merged_into=None):
    """一條規則。pattern/exclude 是判別條件的機器形式,condition 是它的人話。

    新增規則就是在 RULES 裡多寫一次 define();合併舊規則則是給舊條補上
    merged_into 與一筆 CHANGE_MERGE 變更記錄,不刪行。
    """
    return {
        "id": rid,
        "kind": kind,
        "scope": scope,
        "condition": condition,
        "ticket": ticket,
        "pattern": re.compile(pattern),
        "exclude": re.compile(exclude) if exclude else None,
        "changes": tuple(changes),
        "merged_into": merged_into,
    }


# 本批規則由 票06 從官方明示的效果句歸納,每一條都以整份官方明示驗證過(見
# docs/effect_kind_rules.md 的獨立驗證一節)。判別條件一律看日文原文:效果類型是
# 官方裁定概念,繁中譯文經過翻譯會失真(docs/effect_kind_guide.md §0)。
RULES = (
    define("R1", KIND_TRIGGER, SCOPE_ACTIVATION,
           "發動子句含完成式事件「〜た場合に(…)発動」,但不含狀態條件「だった場合」",
           r"た場合に.{0,14}?発動", "票06", exclude=r"だった場合"),
    define("R2", KIND_TRIGGER, SCOPE_ACTIVATION,
           "發動子句以「リバース：」起首",
           r"^リバース[：:]", "票06"),
    define("R3", KIND_TRIGGER, SCOPE_ACTIVATION,
           "發動子句含固定時點「(エンド|スタンバイ)フェイズに(…)発動」",
           r"(エンド|スタンバイ)フェイズに.{0,10}?発動", "票06"),
    define("R4", KIND_IGNITION, SCOPE_ACTIVATION,
           "發動子句含「自分メインフェイズに(…)発動」",
           r"自分メインフェイズに.{0,8}?発動", "票06"),
    define("R5", KIND_QUICK, SCOPE_ACTIVATION,
           "發動子句含「自分・相手ターンに」,且效果句不含「存在する限り」"
           "(「〜存在する限り、自分は…発動できる」是賦予他卡發動權的永續效果)",
           r"自分・相手ターンに", "票06", exclude=r"存在する限り"),
    define("R6", KIND_UNCLASSIFIED, SCOPE_CLAUSE,
           "效果句含自我特殊召喚程序「手札から特殊召喚できる」,"
           "且不含「発動」與任何觸發事件",
           r"手札から特殊召喚できる", "票06",
           exclude=_ACTIVATES + "|" + _EVENT),
    define("R7", KIND_CONTINUOUS, SCOPE_CLAUSE,
           "效果句是單一句子、含「(フィールド|モンスターゾーン)…存在する限り」,"
           "且不含「発動」「として扱う」「フェイズ」「事ができる」"
           "「以下の効果を得る」與任何觸發事件",
           r"^[^。]*(フィールド|モンスターゾーン)[^。]*存在する限り[^。]*。?$",
           "票06",
           exclude=_ACTIVATES + r"|として扱う|フェイズ|事ができる"
                   r"|以下の効果を得る|" + _EVENT,
           changes=({"reason": CHANGE_OVERLAP, "ticket": "票22",
                     "note": "與 R13 在存在する限り+以下の効果を得る的單句領起句"
                             "上重疊且結論不同;官方對那一族 3 筆全判效果外文本"
                             "(15419596/34244455/69058960),R7 排除領起句。"},)),
    define("R8", KIND_CONTINUOUS, SCOPE_CLAUSE,
           "效果句含「効果を受けない」,且不含「発動」「として扱う」、素材/召喚時的"
           "一次性限定(「素材とした」「使用した」「召喚に成功したターン」"
           "「リリースした」)與任何觸發事件",
           r"効果を受けない", "票06",
           exclude=_ACTIVATES + r"|として扱う|素材とした|使用した"
                   r"|召喚に成功したターン|リリースした|" + _EVENT,
           changes=({"reason": CHANGE_TOO_BROAD, "ticket": "票23",
                     "note": "票23 拆句後 30492798(儀式魔人ディザーズ)的"
                             "「このカードを儀式召喚に使用した儀式モンスターは"
                             "罠カードの効果を受けない」取得官方明示無種類效果"
                             "(§5.5 分界四:效果賦予給別的怪獸),R8 預測永續效果"
                             "而 FAIL(69/70)。比照 R9 既有的儀式排除(「使用して」)"
                             "補「使用した」,賦予型不受影響句整族排除。"},)),
    define("R9", KIND_CONTINUOUS, SCOPE_CLAUSE,
           "效果句含「対象に(…)ならない」,且不含「発動」「として扱う」、"
           "素材/儀式的一次性限定(「素材とした」「使用して」)與任何觸發事件",
           r"対象に.{0,6}ならない", "票06",
           exclude=_ACTIVATES + r"|として扱う|素材とした|使用して|" + _EVENT),
    # R10–R12 是 docs/effect_kind_guide.md §5.5 早就寫下、卻一直沒登記的三族
    # 「長得像永續效果的無種類效果」。票19 量到三條的覆蓋都過了 MIN_COVERAGE,
    # 對官方明示各 83 / 11 / 10 條全部一致,才補進來。
    define("R10", KIND_UNCLASSIFIED, SCOPE_CLAUSE,
           "效果句含同名卡唯一性限制「〜しか表側表示で存在できない」,"
           "且不含「発動」與任何觸發事件",
           r"しか表側表示で存在できない", "票19",
           exclude=_ACTIVATES + "|" + _EVENT),
    define("R11", KIND_UNCLASSIFIED, SCOPE_CLAUSE,
           "效果句含「〜召喚は無効化されない」,且不含「発動」"
           "、賦予他卡的「存在する限り」與任何觸發事件"
           "(「このカードがモンスターゾーンに存在する限り、〈他卡〉の召喚は無効化"
           "されない」是在場上賦予別人的永續效果)",
           r"召喚は無効化されない", "票19",
           exclude=_ACTIVATES + r"|存在する限り|" + _EVENT),
    define("R12", KIND_UNCLASSIFIED, SCOPE_CLAUSE,
           "效果句含離場時的自我除外「フィールドから離れた場合に除外される」,"
           "且不含「発動」與「存在する限り」",
           r"フィールドから離れた場合に除外される", "票19",
           exclude=_ACTIVATES + r"|存在する限り"),
    # R13 是 §5.5 分界四旁的「自己得到型」純領起句:單一句子、主語このカード自己、
    # 以「以下の効果を得る」收尾且沒有發動子句。票22 全表量測:官方給過答案的
    # 41/41 全是「効果の扱いではありません」,無一判成其他類型。多句的效果句
    # (發動子句在前、得る收尾)不在此列——單句限定就是為了排除它們。
    define("R13", KIND_NON_EFFECT, SCOPE_CLAUSE,
           "效果句是單一句子的自己得到型領起句「このカードは…以下の効果を得る。」,"
           "且不含「発動」與任何觸發事件",
           r"^[^。]*このカードは[^。]*以下の効果を得る。?$", "票22",
           exclude=_ACTIVATES + "|" + _EVENT),
    # R14 是 §5.5 分界一「適用場所超出場上 → 無種類效果」的機器形式:同一句話裡
    # 適用範圍寫到墓地(フィールド・墓地/墓地またはフィールド)又做「として扱う」的
    # 規則視為。票30 全表量測:命中 98 條、官方給過答案的 87/87 全是無種類效果,
    # 反例 0。範圍限在怪獸區域的那一半(「モンスターゾーンに存在する限り、通常
    # モンスターとして扱う」)不命中,照分界一仍是永續效果。
    define("R14", KIND_UNCLASSIFIED, SCOPE_CLAUSE,
           "效果句同一句裡把適用範圍寫到墓地"
           "「(フィールド・墓地|墓地・フィールド|墓地またはフィールド)…として扱う」,"
           "且不含「発動」與任何觸發事件",
           r"(フィールド・墓地|墓地・フィールド|墓地またはフィールド上?)"
           r"[^。]*として扱う", "票30",
           exclude=_ACTIVATES + "|" + _EVENT),
    # R15 是聯合怪獸(ユニオン)「自分メインフェイズに装備カード扱いとして〜に装備、
    # または装備を解除して〜特殊召喚できる」那一句。官方對它一律判起動効果,即使
    # 句子裡一個「発動」字都沒有——句型本身(玩家主動指定對象 + 裝備/解除)就是發動,
    # 與 §2.2 註記的「主動指定對象 + 把自己當裝備卡裝備」同一族。票33 全表量測:
    # 單句命中 18 條、官方給過答案的 17/17 全是啟動效果,反例 0。單句限定是刻意的:
    # 尚未拆句的整團(87564935、87798440)含多個效果,整團預測沒有意義。
    define("R15", KIND_IGNITION, SCOPE_CLAUSE,
           "效果句是單一句子、含聯合怪獸的裝備/解除句"
           "「装備カード扱い…に装備、または装備を解除して」",
           r"^[^。]*装備カード扱い[^。]*に装備、または装備を解除して[^。]*。?$",
           "票33"),
    # R16 是[[賦予型領起句]]會發動的那一半:アルカナフォース族的「〜した時、
    # コイントスを１回行い(その裏表によって)以下の効果を得る」。判準9 說賦予型
    # 領起句自己是效果外文本,那說的是二重(デュアル)那一族(「再度召喚する事で〜
    # 以下の効果を得る」,全表 22/22 效果外文本);領起句自己帶觸發事件又做了一個
    # 動作(擲硬幣)時,官方判它是那個動作的誘發效果。票35 全表量測:命中 12 條、
    # 官方給過答案的 10/10 全是誘發效果(1速),反例 0。
    define("R16", KIND_TRIGGER, SCOPE_CLAUSE,
           "效果句是硬幣型的賦予領起句「…コイントス…以下の効果を得る」"
           "(領起句自己就是擲硬幣的那個誘發效果,● 是被賦予的子效果)",
           r"コイントス[^。]*以下の効果を得る", "票35"),
    # R17 是[[直接攻擊]]的許可/限制。攻擊方式是怪獸在場上的持續狀態,不論寫成
    # 許可(「このカードは直接攻撃できる」)、附條件的許可(「〜しか存在しない場合、
    # 直接攻撃できる」)還是禁止(「このカードは直接攻撃できない」),官方一律判永續
    # 效果。票36 全表量測:命中 160 條、官方給過答案的 134/134 全是永續效果,反例 0。
    # 三個排除條件各有依據,不是為了湊分數:「リバース」是 §2.5 列的觸發事件而
    # _EVENT 剛好收不到它(5257687);「召喚に成功したターン」是 §5.5 分界五的無種類
    # 效果(32825095);「手札から特殊召喚」是 R6 的判別條件本身(18861006 那一句的
    # 主體是自我特殊召喚程序),少了它兩條規則會在同一句上結論不同而雙雙不寫。
    # 排除是保守的:「リバース」順帶砍掉一條答案本來就對的永續效果(93724592 ④
    # 「また、このカードがリバースしたターン、このカードは相手プレイヤーに直接攻撃
    # する事ができる」),少一條覆蓋換整條規則不必開後門,划得來。
    define("R17", KIND_CONTINUOUS, SCOPE_CLAUSE,
           "效果句含直接攻擊的許可或限制「直接攻撃」,且不含「発動」「リバース」、"
           "召喚時的一次性限定「召喚に成功したターン」、自我特殊召喚程序"
           "「手札から特殊召喚」與任何觸發事件",
           r"直接攻撃", "票36",
           exclude=_ACTIVATES + r"|リバース|召喚に成功したターン"
                   r"|手札から特殊召喚|" + _EVENT),
)


# ---------------------------------------------------------------- 查詢

def active(rules=RULES):
    """尚在規則層裡的規則——被合併掉的舊條留在清單上,但不再參與預測。"""
    return [rule for rule in rules if rule["merged_into"] is None]


def merged_groups(rules=RULES):
    """{合併去向: [被合併的規則編號, ...]},給報告印成「R12 + R15 → R31」。"""
    groups = {}
    for rule in rules:
        if rule["merged_into"] is not None:
            groups.setdefault(rule["merged_into"], []).append(rule["id"])
    return groups


def hits(rule, text_ja, activation):
    """這條規則命中這個效果句嗎?

    掃描範圍由 scope 決定:發動子句範圍的規則講的是「這一句怎麼發動」,整句範圍的
    規則講的是「這一句在做什麼」。排除條件一律看整句——排除的目的是擋掉整句裡的
    反證(觸發事件、「として扱う」),只看發動子句會漏掉寫在處理段的那些。
    """
    text = activation if rule["scope"] == SCOPE_ACTIVATION else text_ja
    if not text or not rule["pattern"].search(text):
        return False
    return not (rule["exclude"] is not None and rule["exclude"].search(text_ja))


def matching(text_ja, activation, rules):
    return [rule for rule in rules if hits(rule, text_ja, activation)]


# ---------------------------------------------------------------- 規則清單自檢

def problems(rules=RULES):
    """規則清單本身的毛病;必須是空的,否則規則層不上工。"""
    found = []
    ids = [rule["id"] for rule in rules]
    for rid in sorted({rid for rid in ids if ids.count(rid) > 1}):
        found.append(f"{rid}: 編號重複")
    for rule in rules:
        rid = rule["id"]
        if not _ID_RE.match(rid):
            found.append(f"{rid}: 編號格式須為 R + 正整數")
        if rule["kind"] not in KINDS:
            found.append(f"{rid}: 對應類型不是六種效果類型之一")
        if rule["scope"] not in SCOPES:
            found.append(f"{rid}: 掃描範圍不是 {SCOPES}")
        if not rule["condition"] or not rule["ticket"]:
            found.append(f"{rid}: 判別條件與新增票號不得為空")
        found.extend(_change_problems(rule))
        found.extend(_merge_problems(rule, ids))
    return found


def _change_problems(rule):
    for change in rule["changes"]:
        reason = change.get("reason")
        if reason not in CHANGE_REASONS:
            yield (f"{rule['id']}: 變更理由 {reason!r} 不在三種正當理由之內 "
                   f"{tuple(CHANGE_REASONS)}")
        if not change.get("ticket"):
            yield f"{rule['id']}: 變更未記票號"
        if not change.get("note"):
            yield f"{rule['id']}: 變更未記說明"


def _merge_problems(rule, ids):
    target = rule["merged_into"]
    if target is None:
        return
    if target not in ids:
        yield f"{rule['id']}: 合併去向 {target} 不在規則清單上"
    elif target == rule["id"]:
        yield f"{rule['id']}: 合併去向指向自己"
    if not any(change.get("reason") == CHANGE_MERGE
               for change in rule["changes"]):
        yield f"{rule['id']}: 標了合併去向卻沒有 {CHANGE_MERGE} 變更記錄"


def digest(rules=RULES):
    """規則**定義**的指紋。覆蓋條數不算在內——資料長出新卡不算規則有異動。"""
    parts = []
    for rule in rules:
        parts.append("|".join((
            rule["id"], rule["kind"], rule["scope"], rule["condition"],
            rule["pattern"].pattern,
            rule["exclude"].pattern if rule["exclude"] else "",
            rule["ticket"], rule["merged_into"] or "",
            ";".join(f"{c.get('ticket')}:{c.get('reason')}:{c.get('note')}"
                     for c in rule["changes"]))))
    return hashlib.sha1("\n".join(parts).encode("utf-8")).hexdigest()[:16]
