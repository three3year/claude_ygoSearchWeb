"""卡片結構的形狀:值域、各層的工廠函式與走訪。

形狀說明見 `card_structure.py` 的模組 docstring。獨立成一檔是因為抽取
(`block_split`、`segment_extract`)與建置管線都要用,放在管線裡會互相 import。
"""

BLOCK_KINDS = ("素材", "召喚條件", "卡片發動", "靈擺效果", "編號效果")
SEGMENT_KINDS = ("條件", "代價", "效果", "被代替", "召喚手續", "限制", "修飾")
POLARITIES = ("做", "不能", "不會", "可以", "只能", "必須")
TRIGGER_FORMS = ("時", "場合", "際")
ROLES = ("施事", "受事", "被召喚", "素材")
POSITION_SOURCES = ("明寫", "繼承", "推得")
JOINS = ("同時", "先後")
BRANCH_MODES = ("選1", "各自可以", "依前提")
SIDES = ("我方", "對手", "任一方", "雙方各自")
OBJECT_KINDS = ("卡", "玩家", "計數器", "格位", "宣言值")
OBJECT_SOURCES = ("自己", "新建", "子集", "剩餘", "聯集")
ZONES = ("手牌", "牌組", "牌組頂", "牌組底", "額外牌組", "場上", "怪獸區",
         "魔陷區", "P區", "場地區", "EX怪獸區", "墓地", "除外", "素材")
# 子區域 → 上位區域;查「牌組」要含牌組頂、牌組底,查「場上」要含各區。
ZONE_PARENT = {"牌組頂": "牌組", "牌組底": "牌組", "怪獸區": "場上",
               "魔陷區": "場上", "P區": "場上", "場地區": "場上",
               "EX怪獸區": "場上"}
ATTRIBUTE_TABLES = ("name", "archetype", "attribute", "race", "level",
                    "category")

NO_OFFICIAL_TEXT = "無官方日文"


def unparsed(reason):
    """「解析不出」的格:原因一律帶著,覆蓋報告依原因分類。"""
    return {"reason": reason}


def zone(name, side=None):
    return {"zone": name, "side": side}


def position(zones, source, inferred=False):
    """從/到:區域集合 + 來源標記;`inferred` = 推得值或繼承自推得值,
    查詢預設不算、開關開才算(spec:推得的終點預設不算命中)。"""
    return {"zones": list(zones), "source": source, "inferred": inferred}


def new_line(obj_id, role, targeting=False, from_=None, to=None):
    """對象線:物件、取對象標記、角色、從、到。"""
    return {"object": obj_id, "targeting": targeting, "role": role,
            "from": from_, "to": to}


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
        "duration": None,    # 期間
        "timing": None,      # 時機
        "trigger": None,     # 觸發形(僅條件段)
        "premise": None,     # 前提(條件式)
        "modified": None,    # 被改的屬性
        "amount": None,      # 數量(段可無物件,例:支付 1000LP)
        "optional": None,    # 可選
        "replaces": None,    # 代替誰(段 id)
        "span": list(span),  # 原文範圍(相對於區塊 text)
        "text": text,
        "predicate": predicate,  # 原述語字面
        "voice": voice,          # 態
        "unparsed": None,
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
        "count": count,                # {"text", "value", "unit", "cmp"}
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


def attribute_row(value, where=None, source=None, span=None, text=None):
    """卡片屬性表的一列:值、位置條件(None = 任何位置)、來源、原文範圍與字面。"""
    return {"value": value, "where": where, "source": source,
            "span": list(span) if span else None, "text": text}


def name_row(name_id, text, source):
    """名稱表的一列:來源是「」引用或宣言。"""
    return {"id": name_id, "text": text, "source": source}


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


