"""卡片結構的形狀:值域、各層的工廠函式與走訪。

形狀說明見 `card_structure.py` 的模組 docstring。獨立成一檔是因為抽取
(`block_split`、`segment_extract`)與建置管線都要用,放在管線裡會互相 import。
"""

BLOCK_KINDS = ("素材", "召喚條件", "卡片發動", "靈擺效果", "編號效果")
SEGMENT_KINDS = ("條件", "代價", "效果", "被代替", "召喚手續", "限制", "修飾")
POLARITIES = ("做", "不能", "不會", "可以", "只能", "必須")
# ターン:「〜したターン、」的動作子句是條件段,後面的段以前提 `本回合發生過` 引用它(票 09)。
# 戰鬥時點:「〜戦闘を行うダメージ計算時に」的觸發形是整個時點字面,不是「時」。
BATTLE_TRIGGERS = ("ダメージ計算前", "ダメージ計算時", "ダメージ計算後",
                   "ダメージステップ開始時", "ダメージステップ終了時",
                   # 舊式的寫法(m3 票 02);「戦闘ダメージ計算時」的字面留在觸發形裡,不併成「ダメージ計算時」。
                   "ダメージステップ時", "戦闘ダメージ計算時")
TRIGGER_FORMS = ("時", "場合", "際", "ターン") + BATTLE_TRIGGERS
ROLES = ("施事", "受事", "被召喚", "素材")
POSITION_SOURCES = ("明寫", "繼承", "推得")
JOINS = ("同時", "先後")
BRANCH_MODES = ("選1", "各自可以", "依前提")
SIDES = ("我方", "對手", "任一方", "雙方各自", "持有者",   # 持有者:「持ち主の」
         "自身")   # 自身:「自身の手札」= 這一段的誰那一方
OBJECT_KINDS = ("卡", "玩家", "計數器", "格位", "宣言值", "超量素材",
                "效果")   # 被發動的效果(「魔法・罠・モンスターの効果」),條件式是誰的效果
OBJECT_SOURCES = ("自己", "新建", "子集", "剩餘", "聯集")
VOICE_ACTIVE, VOICE_PASSIVE, VOICE_MIXED = "主動", "被動", "混合"
VOICES = (VOICE_ACTIVE, VOICE_PASSIVE, VOICE_MIXED)  # 混合:て形串接的多個述語態不同
ZONES = ("手牌", "牌組", "牌組頂", "牌組底", "額外牌組", "場上", "怪獸區",
         "魔陷區", "P區", "場地區", "EX怪獸區", "墓地", "除外", "素材",
         "主要怪獸區")
# 區域字面 ↔ 區域名(長的在前,EXデッキ 不能被 デッキ 先吃掉);同一區域多個字面時最後一個是
# 預設寫法(反向檢查沒有原文字面時用它)。段抽取、條件原子、卡片屬性表的位置條件都用這一張表。
ZONE_WORDS = (("エクストラデッキ", "額外牌組"),   # 全寫;預設寫法是 EXデッキ
              ("EXデッキ", "額外牌組"), ("デッキの一番下", "牌組底"),
              ("デッキの一番上", "牌組頂"), ("デッキの上", "牌組頂"),
              ("デッキ", "牌組"), ("手札", "手牌"),
              ("EXモンスターゾーン", "EX怪獸區"), ("メインモンスターゾーン", "主要怪獸區"),
              ("モンスターゾーン", "怪獸區"),
              ("魔法＆罠カードゾーン", "魔陷區"),   # 舊式
              ("魔法＆罠ゾーン", "魔陷區"),
              ("Pゾーン", "P區"),   # 縮寫;預設寫法照舊是全寫
              ("ペンデュラムゾーン", "P區"),
              ("フィールドゾーン", "場地區"),
              ("フィールド上", "場上"),  # 舊式:フィールド上の = フィールドの
              ("フィールド", "場上"), ("墓地", "墓地"),
              # 除外的卡所在的地方(「自分の墓地・除外状態のモンスター」);「除外する」的到不寫區域。
              ("除外状態", "除外"))
DEFAULT_ZONE_WORD = {name: word for word, name in ZONE_WORDS}
# 區域的方從哪來:明寫(自分の/相手の)、預設(沒寫,照慣例歸我方)。
SIDE_SOURCES = ("明寫", "預設")
# 遊戲狀態原子(只出現在前提):回合方的值是我方/對手;階段的值是階段名、另帶方;
# 傷害步驟沒有值。
GAME_STATES = ("回合方", "階段", "傷害步驟")
PHASES = ("抽牌階段", "準備階段", "主要階段", "主要階段1", "主要階段2", "戰鬥階段",
          "結束階段")
# 子區域 → 上位區域;查「牌組」要含牌組頂、牌組底,查「場上」要含各區。
ZONE_PARENT = {"牌組頂": "牌組", "牌組底": "牌組", "怪獸區": "場上",
               "魔陷區": "場上", "P區": "場上", "場地區": "場上",
               "EX怪獸區": "場上", "主要怪獸區": "怪獸區"}
# 到的放置形式三槽(`placement_form`):treat 的卡片種類視同、display 的表示形式值域。
PLACEMENT_TREAT_KINDS = ("裝備卡", "永續魔法", "永續陷阱", "魔法")
FACES = ("表側", "裏側")
BATTLE_POSITIONS = ("攻擊", "守備")
# 表示形式字面 ↔ (表裏, 攻守);沒寫的一半是 None。到的放置形式 display、前提的位置/存在原子、
# 從的表示形式共用這張表。正規式依長度排(「守備表示」不能先吃掉「裏側守備表示」的尾巴)。
DISPLAY_WORDS = (("表側攻撃表示", "表側", "攻擊"), ("表側守備表示", "表側", "守備"),
                 ("裏側守備表示", "裏側", "守備"), ("表側表示", "表側", None),
                 ("裏側表示", "裏側", None), ("攻撃表示", None, "攻擊"),
                 ("守備表示", None, "守備"))
DISPLAY_WORD = "(?:" + "|".join(
    sorted((w for w, _, _ in DISPLAY_WORDS), key=len, reverse=True)) + ")"
# 到的表示形式另收省略「表示」的寫法(「エンドフェイズまで表側で除外できる」「裏側で除外する」),
# 值同 表側表示/裏側表示;前提與從不收(由值拼回字面時用上面的完整寫法)。
SHORT_DISPLAY_WORDS = (("表側", "表側", None), ("裏側", "裏側", None))
PLACEMENT_DISPLAY_WORD = "(?:" + "|".join(
    sorted((w for w, _, _ in DISPLAY_WORDS + SHORT_DISPLAY_WORDS), key=len, reverse=True)) + ")"
_DISPLAY_VALUE = {w: {"face": f, "position": p} for w, f, p in DISPLAY_WORDS + SHORT_DISPLAY_WORDS}
_DISPLAY_TEXT = {(f, p): w for w, f, p in DISPLAY_WORDS}
# 性質變更段的 `modified`:attr 是清單(攻守同時改時兩項);form 是改法;limit 是門檻 {"cmp", "text"}。
MODIFY_ATTRS = ("攻擊力", "守備力", "等級", "屬性", "種族", "卡名", "傷害")
MODIFY_FORMS = ("倍", "半分", "數值", "增", "減")
# 段的 `duration`(任何段都可有):{"kind", "text", "range"(選填,只配本回合)}。
DURATION_KINDS = ("本回合", "到X為止", "持續", "該戰鬥")
DURATION_RANGES = ("整回合", "發動後")
# 段的 `amount`:固定值 {"text", "value", "unit", "cmp"(選填)};算式 {"kind": "算式", "text", "cmp"(選填)}。
AMOUNT_FORMULA = "算式"
ATTRIBUTE_TABLES = ("name", "archetype", "attribute", "race", "level",
                    "category")

NO_OFFICIAL_TEXT = "無官方日文"


class NoTemplate(Exception):
    """句型模板寫不出這一格、這一段或這個段樹節點:訊息是反向檢查報告的 detail
    (哪一格、什麼原因)。前提、段樹、段的各格與反向檢查本體共用這一個例外,
    寫不出一律丟它、不回 None(回 None 只留給「不是我管的原子」那種分派)。"""


def unparsed(reason):
    """「解析不出」的格:原因一律帶著,覆蓋報告依原因分類。"""
    return {"reason": reason}


def zone(name, side=None, side_source=None):
    """區域 + 方 + 方的來源(明寫/預設;None = 沒有方)。反向檢查只在明寫時寫「自分の」。"""
    return {"zone": name, "side": side, "side_source": side_source}


def position(zones, source, inferred=False, text=None, form=None):
    """從/到:區域集合 + 來源標記;`inferred` = 推得值或繼承自推得值,
    查詢預設不算、開關開才算(spec:推得的終點預設不算命中)。
    `text` 是明寫時含助詞的原文字面(「自分のデッキの上から」「墓地の」「デッキの一番下に」,
    反向檢查據此還原、解析時驗過與 zones 一致);
    `form` 是到的放置形式 `placement_form(...)`,沒有任何一槽時是 None。
    明寫的「到」寫在物件前(自分フィールドにXが特殊召喚された)時另帶 `placement`: 名詞前(票 05);
    明寫的「從」寫在物件後(XをデッキからYに加える)時另帶 `placement`: 述語前(票 07),
    模板據此放回原位;寫在物件前(預設)不帶。"""
    return {"zones": list(zones), "source": source, "inferred": inferred,
            "text": text, "form": form}


def display_value(word):
    """表示形式字面(不含「で」)→ {"face", "position"}。"""
    return dict(_DISPLAY_VALUE[word])


def display_word(face, position):
    """(表裏, 攻守) → 表示形式字面;沒有這種寫法丟 NoTemplate。"""
    word = _DISPLAY_TEXT.get((face, position))
    if word is None:
        raise NoTemplate(f"表示形式無模板:{face}{position}")
    return word


def placement_form(treat=None, display=None, order=None):
    """到的放置形式,三個具名槽(沒寫的槽是 None):
    `treat` 卡片種類視同 {"text", "kind"}(「装備魔法カード扱いで、」,kind 見 PLACEMENT_TREAT_KINDS);
    `display` 表示形式 {"text", "alternatives": [{"face", "position"}]}(單值一項、「X表示かY表示で」兩項);
    `order` 順序 {"text"}(「好きな順番で」)。反向檢查依槽寫回固定位置。"""
    return {"treat": treat, "display": display, "order": order}


def new_line(obj_id, role, targeting=False, from_=None, to=None, marker=None,
             ref=None, count=None, pick=None):
    """對象線:物件、取對象標記、角色、從、到;另記這一次提及的字面:`marker` 是助詞
    (を/が/は,None = を),`ref` 是回指字面(None = 本段首次出現;「そのモンスター」
    「それらのカード」「めくったカード」),`count` 是助詞後的數量(「を全て」「を２枚まで」,
    屬於這次提及、不屬於物件);`pick` 是怎麼選(「ランダムに」→ 隨機,None = 由選者選)。"""
    return {"object": obj_id, "targeting": targeting, "role": role,
            "from": from_, "to": to, "marker": marker, "ref": ref, "count": count,
            "pick": pick}


def new_segment(seg_id, kind, span, text, predicate=None, voice=None):
    """段的全部格(spec「段」表);值可為 None 或 `unparsed(...)`。"""
    return {
        "id": seg_id,
        "kind": kind,
        "actions": [],
        "lines": [],
        "agent": None,       # 誰
        "recipient": None,   # 受方
        "cause": None,       # 原因
        "polarity": "做",    # 極性
        "duration": None,    # 期間(任何段;本回合可帶 range)
        "timing": None,      # 時機
        "trigger": None,     # 觸發形(僅條件段)
        "premise": None,     # 前提(條件式)
        "modified": None,    # 被改的屬性(性質變更:attr 是清單)
        "amount": None,      # 數量(段可無物件,例:支付 1000LP;算式 {"kind": "算式", "text"})
        "optional": None,    # 可選
        "replaces": None,    # 代替誰(段 id)
        "times": None,       # 多次攻擊的次數 {"value", "text"}(字面在原述語字面裡)
        "per_turn": None,    # 抗性的每回合次數 {"value", "text"}(「１ターンに１度だけ」)
        "derived_from": None,  # 衍生自哪一段(段 id;「Nアップの装備カード扱いで」的性質變更段)
        "span": list(span),  # 原文範圍(相對於區塊 text)
        "text": text,
        "predicate": predicate,  # 原述語字面
        "voice": voice,          # 態
        "unparsed": None,
        "unstructured": None,    # 未結構化:重複到停為止的那一句(spec 故事 28),只寫第一輪
    }


def new_object(obj_id, source, text=None, span=None, block=None,
               condition=None, initial_position=None, count=None,
               kind="卡"):
    return {
        "id": obj_id,
        "source": source,              # {"kind": 自己/新建/子集/剩餘/聯集, ...}
        "kind": kind,                  # 物件種類
        "condition": condition,        # 條件式
        "initial_position": initial_position,
        "count": count,                # {"text", "value", "unit", "cmp"};助詞後的數量在對象線上
        "block": block,                # 首次出現的區塊 id
        "span": list(span) if span else None,
        "text": text,
        "unparsed": None,
    }


def self_object():
    """物件0:這張卡自己;條件來自卡片屬性表(查詢時以卡片密碼對)。"""
    return new_object("o0", {"kind": "自己"}, text="このカード")


def new_block(block_id, kind, label, source, span, text):
    return {"id": block_id, "kind": kind, "label": label, "source": source,
            "span": list(span), "text": text, "segments": [],
            "tree": {"items": []}, "unparsed": None}


def segment_node(seg_id, join=None):
    """段樹節點:一段;join 是與前一節點的連接(同時/先後/None)。"""
    return {"node": "段", "segment": seg_id, "join": join}


def branch_node(mode, chooser=None, branches=(), join=None):
    """段樹節點:分歧;每支 {"premise": 條件式, "items": [節點]}。"""
    return {"node": "分歧", "mode": mode, "chooser": chooser,
            "branches": list(branches), "join": join}


def embedded_node(binding, block, join=None):
    """段樹節點:內嵌效果;binding 例 {"自己": "o3", "我方": "對手"}、block 是一個區塊。"""
    return {"node": "內嵌效果", "binding": binding, "block": block,
            "join": join}


_SWAPPED_SIDE = {"我方": "對手", "對手": "我方"}
# 方的值落在哪些鍵:區域與階段原子的 side、段的 agent/recipient(玩家字串)、
# 控制方原子與回合方遊戲狀態原子的 value。
_SIDE_KEYS = ("side", "agent", "recipient")


def swap_sides(value):
    """內嵌效果綁定「我方 = 對手」(效果被換掉):把一個段或物件裡所有的方對調後回傳新的
    (深複製);對調兩次等於原值,反向檢查用同一個函式對調回去。"""
    if isinstance(value, list):
        return [swap_sides(item) for item in value]
    if not isinstance(value, dict):
        return value
    out = {key: swap_sides(item) for key, item in value.items()}
    for key in _SIDE_KEYS:
        if isinstance(out.get(key), str) and out[key] in _SWAPPED_SIDE:
            out[key] = _SWAPPED_SIDE[out[key]]
    side_valued = out.get("op") == "控制方" or (
        out.get("op") == "遊戲狀態" and out.get("state") == "回合方")
    if side_valued and out.get("value") in _SWAPPED_SIDE:
        out["value"] = _SWAPPED_SIDE[out["value"]]
    return out


def attribute_row(value, where=None, source=None, span=None, text=None):
    """卡片屬性表的一列:值、位置條件(None = 任何位置)、來源、原文範圍與字面。"""
    return {"value": value, "where": where, "source": source,
            "span": list(span) if span else None, "text": text}


def name_row(name_id, text, source):
    """名稱表的一列:來源是「」引用或宣言;對不到卡名也對不到字段的標 unparsed。"""
    return {"id": name_id, "text": text, "source": source, "unparsed": None}


def new_card(card_id, name_ja):
    return {
        "id": card_id,
        "name_ja": name_ja,
        "unparsed": None,
        "attributes": {name: [] for name in ATTRIBUTE_TABLES},
        "names": [],
        "objects": [self_object()],
        "blocks": [],
        "omitted": [],
    }


def iter_segments(block):
    """遞迴走過區塊與其內嵌效果的所有段;一張卡任一分支、任一段命中即命中。"""
    for seg in block["segments"]:
        yield block, seg
    for node in iter_nodes(block["tree"]["items"]):
        if node.get("node") == "內嵌效果" and node.get("block"):
            yield from iter_segments(node["block"])


def iter_nodes(items):
    for node in items:
        yield node
        if node.get("node") == "分歧":
            for branch in node["branches"]:
                yield from iter_nodes(branch["items"])


