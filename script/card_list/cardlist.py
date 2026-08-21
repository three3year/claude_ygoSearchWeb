"""卡片總表管線。

單一接縫:build_card_list(zh_path[, ja_path, en_path, existing]) → (cards, report)。
輸入為來源 cdb 檔路徑;下載與檔案輸出在此模組之外。
詞彙見 CONTEXT.md:卡片密碼、卡片總表、衍生物、同名異圖卡、差值更新。
"""
import json
import sqlite3

TYPE_MONSTER = 0x1     # 大類怪獸位元(相對於魔法 0x2、陷阱 0x4)
TYPE_PENDULUM = 0x1000000
TYPE_LINK = 0x4000000  # Link 怪獸位元;勿與 TYPE_TOKEN 混用
TYPE_TOKEN = 0x4000    # 衍生物位元

# 大類非怪獸的卡沒有怪獸參數。cdb 為 79 張罠モンスター(如伯吉斯異獸、死亡訊息)
# 存著完整的 race/attribute/level/atk/def,但那是它「變成怪獸之後」的形態、寫在
# 效果文的括號裡而不是印在卡面上,是給遊戲引擎用的。決定性證據是鏡像的沼澤人
# 50277973 與量子貓 87772572:種族與屬性由玩家結算時宣言,cdb 那兩欄因此空著。
# 留著這些值等於要每個消費端各自記得過濾一次,漏掉就是無聲的錯誤結果。
MONSTER_PARAMS = ("race", "attribute", "level", "atk", "def")


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
    is_monster = bool(ctype & TYPE_MONSTER)
    is_link = bool(ctype & TYPE_LINK)
    # 大類閘門(見 MONSTER_PARAMS):與「連結怪獸沒有守備欄」、「scale 只在靈擺卡填」
    # 同一條原則——欄位只在卡片真的有那個參數時才填。setcode 不在閘門內。
    return {
        "id": cid,
        "alt_ids": [],
        "name_zh": name,
        "name_ja": "",
        "name_en": "",
        "desc": desc,
        "type": ctype,
        "atk": atk if is_monster else None,
        "def": None if (is_link or not is_monster) else def_,
        "level": level & 0xff if is_monster else 0,
        "race": race if is_monster else 0,
        "attribute": attribute if is_monster else 0,
        "scale": (level >> 24) & 0xff if ctype & TYPE_PENDULUM else 0,
        "link_marker": def_ if is_link else 0,
        "setcode": setcode,
        "ot": ot,
        "md_rarity": "",
        "genesys_points": 0,
        "ban_ocg": "",
        "ban_tcg": "",
        "ban_md": "",
    }


# [[禁限狀態]]:來源原始值 → 統一三值(2026-08-22 使用者裁示,三賽制共用)。
# 表以外的字串即建置失敗——來源哪天冒出新值要吵不要靜(值域正典原則)。
BAN_ZH = {"Forbidden": "禁止", "Limited": "限制", "Semi-Limited": "準限制"}
BAN_FIELDS = {"ocg": "ban_ocg", "tcg": "ban_tcg"}
# MD 來源(masterduelmeta)有自己的一套字面,語意對應同一組三值
MD_BAN_ZH = {"Forbidden": "禁止", "Limited 1": "限制", "Limited 2": "準限制"}


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


def _apply_errata(cards, errata):
    """套用[[卡文勘誤表]](ADR-0011):來源卡文的誤譯在建置期修,不手改總表。

    原文子字串必須在該卡卡文出現**恰好一次**,失配即整批列舉後拋錯——上游
    哪天自己修好了,要的是建置吵出來、人來刪掉那筆勘誤,而不是無聲跳過讓
    「勘誤還生不生效」變成猜測(與值域正典同一個「吵鬧失效」精神)。
    """
    by_id = {card["id"]: card for card in cards}
    problems = []
    for entry in errata:
        card = by_id.get(entry["id"])
        if card is None:
            problems.append(f"id={entry['id']} 不在總表(被排除或併入異圖?)")
            continue
        count = card["desc"].count(entry["from"])
        if count != 1:
            problems.append(f"id={entry['id']} 原文子字串出現 {count} 次"
                            f"(需恰好 1 次):{entry['from']}")
            continue
        card["desc"] = card["desc"].replace(entry["from"], entry["to"])
    if problems:
        raise ValueError("卡文勘誤套用失敗:\n" + "\n".join(problems))
    return len(errata)


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


def _fill_md_rarity(cards, path):
    """MD 來源 JSON({密碼字串: {rarity, banStatus}})以密碼填入稀有度與
    MD [[禁限狀態]];主卡沒對到時試異圖密碼。

    banStatus 先過 MD_BAN_ZH 正規化(Limited 1/2 → 限制/準限制),表外字串
    整批列舉後拋錯(吵鬧失效)。**無稀有度的 banStatus 不採計**——那是來源對
    未收錄卡的預掛,MD 的收錄與否由稀有度欄位定義,採了會讓「未發行」與
    「上榜」同時成立;筆數進報告(skipped_unrated)。
    回傳 (稀有度覆蓋, MD 禁限統計)。
    """
    with open(path, encoding="utf-8") as f:
        entries = {int(k): v for k, v in json.load(f).items()}
    unknown = [f"md 密碼 {pw} 的值 {e['banStatus']!r}"
               for pw, e in sorted(entries.items())
               if e.get("banStatus") and e["banStatus"] not in MD_BAN_ZH]
    if unknown:
        raise ValueError("MD 禁限出現對應表以外的字串:\n" + "\n".join(unknown))
    skipped_unrated = sum(1 for e in entries.values()
                          if e.get("banStatus") and not e.get("rarity"))
    rated = 0
    listed = 0
    for card in cards:
        entry = next((entries[pw] for pw in (card["id"], *card["alt_ids"])
                      if pw in entries and entries[pw].get("rarity")), None)
        if entry is None:
            continue
        card["md_rarity"] = entry["rarity"]
        rated += 1
        ban = entry.get("banStatus")
        if ban:
            card["ban_md"] = MD_BAN_ZH[ban]
            listed += 1
    return ({"rated": rated, "missing": len(cards) - rated},
            {"listed": listed, "skipped_unrated": skipped_unrated})


def _fill_genesys_points(cards, path):
    """Genesys 點數 JSON({密碼字串: 點數})以密碼填入;主卡沒對到時試異圖密碼。

    官方點數表未列的卡為 0。回傳有點數(非 0)的卡數。
    """
    with open(path, encoding="utf-8") as f:
        points = {int(k): v for k, v in json.load(f).items()}
    listed = 0
    for card in cards:
        value = points.get(card["id"])
        if value is None:
            for alt in card["alt_ids"]:
                value = points.get(alt)
                if value is not None:
                    break
        card["genesys_points"] = value if value is not None else 0
        if value:
            listed += 1
    return listed


def _fill_banlist(cards, paths):
    """禁限來源 JSON({密碼字串: 原始禁限值})逐賽制填入;主卡沒對到時試異圖密碼。

    原始值先過 BAN_ZH 正規化,表以外的字串整批列舉後拋錯(吵鬧失效)。
    來源含本站不收錄的卡屬正常,對不上的筆數進報告(unmatched)而不失敗。
    """
    coverage = {}
    unknown = []
    for fmt, path in sorted(paths.items()):
        with open(path, encoding="utf-8") as f:
            raw = {int(k): v for k, v in json.load(f).items()}
        for pw, value in sorted(raw.items()):
            if value not in BAN_ZH:
                unknown.append(f"banlist-{fmt} 密碼 {pw} 的值 {value!r}")
        statuses = {pw: BAN_ZH[v] for pw, v in raw.items() if v in BAN_ZH}
        matched = 0
        for card in cards:
            value = statuses.pop(card["id"], "")
            if not value:
                for alt in card["alt_ids"]:
                    value = statuses.pop(alt, "")
                    if value:
                        break
            card[BAN_FIELDS[fmt]] = value
            if value:
                matched += 1
        coverage[fmt] = {"listed": matched, "unmatched": len(statuses)}
    if unknown:
        raise ValueError("禁限來源出現三值以外的字串:\n" + "\n".join(unknown))
    return coverage


def _has_stale_monster_params(row):
    """cdb 這一列是否「大類非怪獸卻帶怪獸參數」——大類閘門清掉的就是這些值。"""
    ctype, atk, def_, level, race, attribute = row[4:10]
    if ctype & TYPE_MONSTER:
        return False
    return any((race, attribute, level & 0xff, atk, def_))


def _check_monster_invariant(cards):
    """驗「大類是怪獸 ⟺ 有種族與屬性」,兩個方向各自列出違反者(預期皆空)。

    → 方向靠來源資料成立(9,280 張怪獸無一缺種族或屬性),
    ← 方向靠大類閘門成立。任一邊非空即代表下游不能再用「有種族」判怪獸。
    """
    monsters = [c for c in cards if c["type"] & TYPE_MONSTER]
    return {
        "monsters": len(monsters),
        "monster_missing_race_or_attribute": [
            c["id"] for c in monsters if not c["race"] or not c["attribute"]],
        "non_monster_with_monster_params": [
            c["id"] for c in cards if not c["type"] & TYPE_MONSTER
            and any(c[f] for f in MONSTER_PARAMS)],
    }


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


def build_card_list(zh_path, ja_path=None, en_path=None, md_rarity_path=None,
                    genesys_path=None, banlist_paths=None, existing=None,
                    errata=None):
    excluded = {"no_password": 0, "token": 0}
    entries = {}
    stale = set()
    for row in _read_cdb(zh_path):
        card = _make_card(row)
        if card["id"] >= MAX_PASSWORD:
            excluded["no_password"] += 1
            continue
        if card["type"] & TYPE_TOKEN:
            excluded["token"] += 1
            continue
        if _has_stale_monster_params(row):
            stale.add(card["id"])
        entries[card["id"]] = (card, row[2])
    cards, merged, exceptions = _merge_alt_arts(entries)
    cards.sort(key=lambda c: c["id"])
    # 勘誤在異圖合併後套用:勘誤表以主卡密碼記,合併前套的話被併入的異圖
    # 條目找不到主卡文字。差值報告在最後算,勘誤後的文字才是本站的正式卡文。
    errata_applied = _apply_errata(cards, errata) if errata else 0
    report = {
        "included": len(cards),
        "errata_applied": errata_applied,
        "excluded": excluded,
        "merged_alt": merged,
        "cleared_monster_params": sum(1 for c in cards if c["id"] in stale),
        "monster_invariant": _check_monster_invariant(cards),
        "alias_exceptions": exceptions,
    }
    if ja_path is not None or en_path is not None:
        coverage = {}
        if ja_path is not None:
            coverage["ja"] = _fill_names(cards, "name_ja", _read_names(ja_path))
        if en_path is not None:
            coverage["en"] = _fill_names(cards, "name_en", _read_names(en_path))
        report["name_coverage"] = coverage
    if md_rarity_path is not None:
        rarity_cov, md_ban = _fill_md_rarity(cards, md_rarity_path)
        report["md_rarity_coverage"] = rarity_cov
        report.setdefault("banlist_coverage", {})["md"] = md_ban
    if genesys_path is not None:
        report["genesys_listed"] = _fill_genesys_points(cards, genesys_path)
    if banlist_paths is not None:
        report.setdefault("banlist_coverage", {}).update(
            _fill_banlist(cards, banlist_paths))
    if existing is not None:
        report["changes"] = _diff_cards(existing, cards)
    return cards, report
