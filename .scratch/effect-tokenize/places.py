# -*- coding: utf-8 -*-
"""區域辨識(frame-args-v3 票 01):一段地點字面 → (玩家, 區域清單)。

框架線與類別線共用這一份:框架抽取(frames.py)用它判斷受事者片語裡哪一段是區域、
切成來源/所在(票 04);動作類別(categories.py)用它把來源/目的/所在字面映成區域七值、
再組葉名。框架裡存的仍是原文字面,區域七值只在類別線用。

區域七值:手牌/牌組/額外牌組/墓地/除外/場上/靈擺區(值域正典的區域,與動作類別第一版同一組)。
玩家:自分/相手/雙方/相對/無——parse_place 給各段明示的玩家合起來(框架類別檔的來源玩家/
目的玩家欄);parse_zones 給逐區域的玩家(類別樹的玩家條件比對用,category-tree-restart
票 02)。相對(自身の/持ち主の:看主語或持有者是誰)另記一值、不算明示玩家,類別樹的葉
不能宣告它(類別線票 06,2026-10-27 站主裁定)。
"""
import re

PLAYER_SELF, PLAYER_OPP, PLAYER_BOTH = "自分", "相手", "雙方"
PLAYER_RELATIVE, PLAYER_NONE = "相對", "無"
# 玩家前綴(長的在前);自身の/持ち主の 是主語或持有者相對的,記 相對、不算明示玩家
PLAYER_PREFIXES = (
    ("自分か相手の", PLAYER_BOTH), ("自分・相手の", PLAYER_BOTH),
    ("自分または相手の", PLAYER_BOTH), ("お互いの", PLAYER_BOTH),
    ("自分か相手", PLAYER_BOTH), ("自分・相手", PLAYER_BOTH), ("自分または相手", PLAYER_BOTH),
    ("自分の", PLAYER_SELF), ("相手の", PLAYER_OPP), ("自分", PLAYER_SELF),
    ("相手", PLAYER_OPP), ("元々の持ち主の", PLAYER_RELATIVE), ("持ち主の", PLAYER_RELATIVE),
    ("自身の", PLAYER_RELATIVE),
)
PREFIX_PLAYER = dict(PLAYER_PREFIXES)
# 整個字面就是玩家(相手に…ダメージ 的目的):記玩家、沒有區域
BARE_PLAYERS = {"自分": PLAYER_SELF, "相手": PLAYER_OPP, "お互い": PLAYER_BOTH}
# 區域詞 → 區域七值(同前綴者長的在前);場上的各種ゾーン歸場上,Pゾーン 自成靈擺區
ZONE_TERMS = (
    ("エクストラデッキ", "額外牌組"), ("EXモンスターゾーン", "場上"),
    ("メインモンスターゾーン", "場上"), ("モンスターゾーン", "場上"),
    ("魔法＆罠ゾーン", "場上"), ("フィールドゾーン", "場上"), ("EXデッキ", "額外牌組"),
    ("フィールド", "場上"), ("Pゾーン", "靈擺區"), ("手札", "手牌"), ("デッキ", "牌組"),
    ("墓地", "墓地"), ("除外状態", "除外"), ("除外", "除外"),
)
_ZONE_ALT = "|".join(re.escape(term) for term, _ in ZONE_TERMS)
# 複合字面的分隔(只在整段認不出時才拆,免得拆到 一番上か一番下)
PLACE_SEPARATOR = re.compile(r"・|及び|または|か")
# 區域詞後面可接的尾巴:括號註記(表側表示)、牌組頂/底(歸牌組)、「の+描述」
# (墓地のモンスター、フィールドの表側表示モンスターの中;描述裡不能再有分隔或區域詞,
# 也不能收在 上/下——フィールドのこのカードの上 是疊放,不是區域;描述是數量
# (の数、のレベル、カウンター)時整個字面是數值,不是區域)
PAREN = re.compile(r"（[^）]*）")
DECK_POSITION = re.compile(r"の(?:一番)?[上下](?:(?:または|か)(?:一番)?[上下])?")
_PLAIN = r"(?:(?!・|及び|または|%s).)*" % _ZONE_ALT
DESCRIPTION = re.compile(r"の(?!.*(?:数|レベル|カウンター))%s(?<![上下])" % _PLAIN)
# 除外されている自分のモンスターの中:區域在動詞裡
BANISHED = re.compile(r"除外されている(?:(自分|相手)の?)?%s" % _PLAIN)
# 區域前的限定語(その縦列の、このカードのリンク先となる、他の、全ての、可能な限り):
# 不含區域詞與玩家詞、收在 の/となる/限り、後面緊接玩家或區域詞;整段認不出時才剝掉
# 再認一次
QUALIFIER = re.compile(r"(?:(?!自分|相手|お互い|・|及び|または|%s).)*?(?:の|となる|限り)"
                       r"(?=自分|相手|お互い|%s)" % (_ZONE_ALT, _ZONE_ALT))


# 分詞器的省略寫法 自分(フィールド)・相手フィールド:半形括號裡是省略掉的詞尾,補回再認
ELIDED = re.compile(r"\(([^()]*)\)")


def _strip_player(text):
    """去掉開頭的玩家前綴 → (明示的玩家或 None, 其餘字面)。"""
    for prefix, player in PLAYER_PREFIXES:
        if text.startswith(prefix):
            return player, text[len(prefix):]
    return None, text


def _parse_part(text):
    """一個區域段(可帶自己的玩家前綴與限定語)→ (明示的玩家或 None, 區域);認不出時
    None。"""
    found = _parse_zone(text)
    if found is None:
        outer, rest = _strip_player(text)
        m = QUALIFIER.match(rest)
        if m:
            found = _parse_zone(rest[m.end():])
            if found and outer and not found[0]:
                found = (outer, found[1])
    return found


def _parse_zone(text):
    m = BANISHED.fullmatch(text)
    if m:
        return PREFIX_PLAYER.get(m.group(1)), "除外"
    player, rest = _strip_player(text)
    for term, zone in ZONE_TERMS:
        if rest.startswith(term):
            tail = rest[len(term):]
            paren = PAREN.match(tail)
            if paren:
                tail = tail[paren.end():]
            if (not tail or DESCRIPTION.fullmatch(tail)
                    or (zone == "牌組" and DECK_POSITION.fullmatch(tail))):
                return player, zone
            return None
    return None


def parse_zones(literal):
    """地點字面 → 逐區域的 [(玩家, 區域)…](依字面順序、區域去重),或 None(沒有字面)、
    [](整個字面就是玩家,或認不出區域)。

    每個區域的玩家是該段自己的前綴,沒有時沿用字面開頭的前綴,都沒有記無(自分の手札・
    相手フィールド → 手札 自分、フィールド 相手;自身の/持ち主の 記相對);同一區域出現
    兩次時玩家合起來(自分フィールド・相手フィールド → フィールド 雙方)。複合字面只要
    有一段認不出就整段不認。
    """
    if not literal:
        return None
    literal = ELIDED.sub(r"\1", literal)
    if literal in BARE_PLAYERS:
        return []
    outer, rest = _strip_player(literal)
    whole = _parse_part(rest)
    parts = [whole] if whole else [_parse_part(p) for p in PLACE_SEPARATOR.split(rest)]
    if None in parts:
        return []
    zones = {}
    for player, zone in parts:
        zones.setdefault(zone, set()).add(player or outer or PLAYER_NONE)
    return [(_merge_players(players), zone) for zone, players in zones.items()]


def _merge_players(players):
    """幾個玩家值 → 一個:兩者都有或含雙方 → 雙方;只有無/相對與某方時取那方;沒有明示
    的玩家時,有相對取相對、否則無。"""
    if PLAYER_BOTH in players or {PLAYER_SELF, PLAYER_OPP} <= players:
        return PLAYER_BOTH
    named = players - {PLAYER_NONE, PLAYER_RELATIVE}
    if named:
        return named.pop()
    return PLAYER_RELATIVE if PLAYER_RELATIVE in players else PLAYER_NONE


def parse_place(literal):
    """地點字面 → (玩家, 區域清單)。

    玩家是各段明示的玩家合起來:只有自分 → 自分、只有相手 → 相手、兩者都有或「自分か
    相手の」這類 → 雙方、只有 自身の/持ち主の → 相對、都沒寫 → 無。區域清單依字面順序、
    去重。整個字面就是玩家
    (相手)時回 (該玩家, []);認不出區域的字面回 (None, [])——需要區域的葉因此不匹配,
    玩家欄也是 null(null = 沒有字面,或字面不是地點:その中、以下の効果、0、
    このカード)。複合字面只要有一段認不出就整段不認(不保留認出的部分)。
    """
    if not literal:
        return None, []
    bare = BARE_PLAYERS.get(ELIDED.sub(r"\1", literal))
    if bare:
        return bare, []
    zones = parse_zones(literal)
    if not zones:
        return None, []
    return _merge_players({player for player, _ in zones}), [zone for _, zone in zones]
