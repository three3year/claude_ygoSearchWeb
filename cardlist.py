"""卡片總表管線。

單一接縫:build_card_list(zh_path[, ja_path, en_path, existing]) → (cards, report)。
輸入為來源 cdb 檔路徑;下載與檔案輸出在此模組之外。
詞彙見 CONTEXT.md:卡片密碼、卡片總表、衍生物、同名異圖卡、差值更新。
"""
import json
import sqlite3

TYPE_PENDULUM = 0x1000000
TYPE_LINK = 0x4000000  # Link 怪獸位元;勿與 TYPE_TOKEN 混用
TYPE_TOKEN = 0x4000    # 衍生物位元

FIELD_ORDER = [
    "id", "alt_ids", "name_zh", "name_ja", "name_en", "desc",
    "type", "atk", "def", "level", "race", "attribute",
    "scale", "link_marker", "setcode", "ot",
]


def _read_cdb(path):
    con = sqlite3.connect(path)
    try:
        rows = con.execute(
            "SELECT d.id, d.ot, d.alias, d.setcode, d.type, d.atk, d.def,"
            " d.level, d.race, d.attribute, t.name, t.desc"
            " FROM datas d JOIN texts t ON d.id = t.id").fetchall()
    finally:
        con.close()
    return rows


def _make_card(row):
    (cid, ot, alias, setcode, ctype, atk, def_, level, race, attribute,
     name, desc) = row
    is_link = bool(ctype & TYPE_LINK)
    return {
        "id": cid,
        "alt_ids": [],
        "name_zh": name,
        "name_ja": "",
        "name_en": "",
        "desc": desc,
        "type": ctype,
        "atk": atk,
        "def": None if is_link else def_,
        "level": level & 0xff,
        "race": race,
        "attribute": attribute,
        "scale": (level >> 24) & 0xff if ctype & TYPE_PENDULUM else 0,
        "link_marker": def_ if is_link else 0,
        "setcode": setcode,
        "ot": ot,
    }


MAX_PASSWORD = 100000000  # 正式卡片密碼為 8 位數;9 位數為先行卡暫時編號


def _merge_alt_arts(entries):
    """同名異圖卡合併:alias 指向同名主卡者併入其 alt_ids。

    entries: {id: (card, alias)}。回傳 (cards, merged_alt 數, 例外清單)。
    """
    exceptions = []
    merged = 0
    cards = {}
    alts = []
    for cid, (card, alias) in entries.items():
        if alias == 0:
            cards[cid] = card
        else:
            alts.append((cid, card, alias))
    for cid, card, alias in alts:
        target = entries.get(alias)
        if target is None:
            exceptions.append(
                {"id": cid, "alias": alias, "reason": "target_missing"})
            cards[cid] = card
        elif target[0]["name_zh"] != card["name_zh"]:
            exceptions.append(
                {"id": cid, "alias": alias, "reason": "name_mismatch"})
            cards[cid] = card
        else:
            cards[alias]["alt_ids"].append(cid)
            merged += 1
    for card in cards.values():
        card["alt_ids"].sort()
    exceptions.sort(key=lambda e: e["id"])
    return list(cards.values()), merged, exceptions


def serialize_card_list(cards):
    """總表 → JSON 文字:一卡一行、鍵序固定、不 escape 中文,git diff 可讀。"""
    lines = [json.dumps(card, ensure_ascii=False, separators=(", ", ": "))
             for card in cards]
    return "[\n" + ",\n".join(lines) + "\n]\n"


def build_card_list(zh_path):
    excluded = {"no_password": 0, "token": 0}
    entries = {}
    for row in _read_cdb(zh_path):
        card = _make_card(row)
        if card["id"] >= MAX_PASSWORD:
            excluded["no_password"] += 1
            continue
        if card["type"] & TYPE_TOKEN:
            excluded["token"] += 1
            continue
        entries[card["id"]] = (card, row[2])
    cards, merged, exceptions = _merge_alt_arts(entries)
    cards.sort(key=lambda c: c["id"])
    report = {
        "included": len(cards),
        "excluded": excluded,
        "merged_alt": merged,
        "alias_exceptions": exceptions,
    }
    return cards, report
