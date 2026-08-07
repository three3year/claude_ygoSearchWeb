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

    迭代解析:alias 目標若已被併入他卡,沿合併結果追到最終主卡(鏈式異圖);
    目標不存在、卡名不同、或互指成環者保留為獨立條目並列入例外。
    """
    exceptions = []
    merged = 0
    cards = {}
    pending = []
    merged_into = {}
    for cid, (card, alias) in entries.items():
        if alias == 0:
            cards[cid] = card
        else:
            pending.append((cid, card, alias))
    progress = True
    while pending and progress:
        progress = False
        deferred = []
        for cid, card, alias in pending:
            target_id = merged_into.get(alias, alias)
            if target_id in cards:
                if cards[target_id]["name_zh"] == card["name_zh"]:
                    cards[target_id]["alt_ids"].append(cid)
                    merged_into[cid] = target_id
                    merged += 1
                else:
                    exceptions.append(
                        {"id": cid, "alias": alias, "reason": "name_mismatch"})
                    cards[cid] = card
                progress = True
            elif target_id not in entries:
                exceptions.append(
                    {"id": cid, "alias": alias, "reason": "target_missing"})
                cards[cid] = card
                progress = True
            else:
                deferred.append((cid, card, alias))  # 目標尚未解析,下輪再試
        pending = deferred
    for cid, card, alias in pending:  # 互指成環,無法解析
        exceptions.append({"id": cid, "alias": alias, "reason": "unresolved"})
        cards[cid] = card
    for card in cards.values():
        card["alt_ids"].sort()
    exceptions.sort(key=lambda e: e["id"])
    return list(cards.values()), merged, exceptions


def serialize_card_list(cards):
    """總表 → JSON 文字:一卡一行、鍵序固定、不 escape 中文,git diff 可讀。"""
    lines = [json.dumps(card, ensure_ascii=False, separators=(", ", ": "))
             for card in cards]
    return "[\n" + ",\n".join(lines) + "\n]\n"


def _read_names(path):
    """讀取多語卡名 cdb → {密碼: 卡名}。"""
    con = sqlite3.connect(path)
    try:
        rows = con.execute("SELECT id, name FROM texts").fetchall()
    finally:
        con.close()
    return dict(rows)


def _fill_names(cards, field, names):
    """以主卡密碼對齊填入卡名;缺漏留空。回傳覆蓋統計。"""
    named = 0
    for card in cards:
        name = names.get(card["id"], "")
        card[field] = name
        if name:
            named += 1
    return {"named": named, "missing": len(cards) - named}


def _diff_cards(existing, cards):
    """比對既有總表與新總表 → 變動報告(不處理刪除:官方卡不會消失)。"""
    old_by_id = {c["id"]: c for c in existing}
    added = []
    changed = []
    for card in cards:
        old = old_by_id.get(card["id"])
        if old is None:
            added.append(card["id"])
            continue
        fields = sorted(k for k in card if card[k] != old.get(k))
        if fields:
            changed.append({"id": card["id"], "fields": fields})
    return {"added": added, "changed": changed}


def build_card_list(zh_path, ja_path=None, en_path=None, existing=None):
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
    if ja_path is not None or en_path is not None:
        coverage = {}
        if ja_path is not None:
            coverage["ja"] = _fill_names(cards, "name_ja", _read_names(ja_path))
        if en_path is not None:
            coverage["en"] = _fill_names(cards, "name_en", _read_names(en_path))
        report["name_coverage"] = coverage
    if existing is not None:
        report["changes"] = _diff_cards(existing, cards)
    return cards, report
