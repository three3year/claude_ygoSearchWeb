"""前端索引的建置管線。

單一接縫:`build_index(卡片總表條目, 效果標記表條目) → (index, report)`。純函式;
讀檔、寫 `web/data.js`、印報告都在這個模組之外(CLI 薄殼)。

索引是查卡網站唯一讀的資料檔,形態是 `window.CARD_DATA=…` 的 `.js` 而不是 `.json`
——`file://` 下 `fetch` 會被 CORS 擋而 `<script src>` 不會(ADR-0007)。

**四道一致性檢查長在 report 裡**,不另開接縫(與 tag_card 把驗收條件放進
`build_tag_cards` 的 report 同一個結構):卡片總表有卡而索引沒有、索引出現正典沒有
的值、效果句缺效果類型、效果句串接後出現已知兩種以外的覆蓋缺口。加上兩道同族的:
`type` 出現正典沒解釋的位元、不變式「大類是怪獸 ⟺ 有種族與屬性」。全部匯總進
`report["problems"]`,非空即建置失敗——把沉默的失效換成吵鬧的失效(ADR-0008)。

詞彙見 CONTEXT.md:前端索引、值域正典、效果句、效果類型、同名異圖卡。
"""
import json
import re

import vocab

TYPE_MONSTER = 0x1
TYPE_PENDULUM = 0x1000000
TYPE_LINK = 0x4000000
# 不變式的欄位清單。故意不 import cardlist 的 MONSTER_PARAMS:這道斷言是
# card-list 票07 的閘門退化時的防線,兩邊共用一份常數的話就會一起走鐘。
MONSTER_PARAMS = ("race", "attribute", "level", "atk", "def")

# 攻守的 `?`(攻 83 張、守 54 張)。cdb 的哨兵值原樣帶進索引:`?` 與 0 是不同的
# 東西,範圍條件不得把 `?` 當 0 納入(票05)。連結怪獸沒有守備欄,那是「沒有這個
# 參數」而不是 `?`,由下面的欄位閘門省略掉。
UNKNOWN_STAT = -2

# 效果句串接後與卡文的兩種已知缺口(spec「卡文的組裝」)。第三種即建置失敗——
# 那代表拆句或卡文出了預期外的變化。
#   1. 段落標頭:靈擺卡的【靈擺效果】/【怪獸效果】,與靈擺通常怪獸的【怪獸敘述】
#   2. `※` 別名:117 張卡文末尾的另一種中文譯名
FLAVOR_HEADER = "【怪獸敘述】"
SECTION_HEADERS = ("【靈擺效果】", "【怪獸效果】", FLAVOR_HEADER)
ALIAS_MARK = "※"
GAP_HEADER = "header"
GAP_ALIAS = "alias"

# `※` 別名(117 張):卡文末尾自成一行的另一種中文譯名。抽出來進 `ax`,不留在
# 卡文裡——它不是效果文,而且卡名搜尋要比對它(票03)。行內的 `※` 不算:別名的
# 形狀是「換行 + ※ + 一行到底」。
ALIAS_RE = re.compile(r"\n[ \t]*" + ALIAS_MARK + r"[ \t]*([^\n" + ALIAS_MARK
                      + r"]+?)[ \t]*\Z")

PENDULUM_SECTION = "pendulum"

# 索引欄位 → 值域(是不是陣列)。「索引出現正典沒有的值即建置失敗」這道檢查照這張
# 表走,後面的票補欄位時在這裡加一行就自動被蓋到。子類型的值域名是 None:它由卡片
# 的大類決定(`0x80` 在怪獸側是儀式怪獸、在魔法側是儀式魔法,一側一份)。
CODED_FIELDS = (
    ("c", vocab.CAT, False),
    ("s", None, True),
    ("at", vocab.ATTR, False),
    ("r", vocab.RACE, False),
    ("lm", vocab.LINK_MARKER, True),
    ("ra", vocab.RARITY, False),
    ("ot", vocab.OT, False),
    ("bo", vocab.BAN_O, False),
    ("bt", vocab.BAN_T, False),
    ("k", vocab.KIND, True),
    ("o", vocab.OPTIONAL, True),
    ("ro", vocab.ROLE, True),
)

_WS = re.compile(r"\s+")


def _norm(text):
    """覆蓋檢查用的正規化:忽略空白(卡文的換行不屬於任何效果句)。"""
    return _WS.sub("", text)


def _split_alias(desc):
    """卡文 → (去掉別名的卡文, 別名或空字串)。"""
    match = ALIAS_RE.search(desc)
    if not match:
        return desc, ""
    return desc[:match.start()], match.group(1)


def _flavor(desc, has_clauses):
    """故事文:沒有效果句的 689 張純通常怪獸,與靈擺通常怪獸的【怪獸敘述】段。

    抽出來當 `d` 而不是留在卡文裡不管,是為了讓覆蓋檢查只剩兩種已知缺口——
    故事文有實際文字,放它過去等於在檢查上開一個吃掉真文字的洞。
    """
    if FLAVOR_HEADER in desc:
        return desc.split(FLAVOR_HEADER, 1)[1].strip()
    return desc.strip() if not has_clauses else ""


def _coded(unknown, field, domain, value):
    """來源值 → 短碼,對不到就記進 unknown。空值回傳 None(呼叫端省略欄位)。"""
    code = vocab.code_of(domain, value)
    if code is None and value:
        unknown.append({"field": field, "value": value,
                        "reason": "來源值對不到短碼"})
    return code


def _monster_face(card, out):
    """怪獸的卡面參數。

    **欄位的有無由大類與子類型決定,不由值決定**:攻 0 與刻度 0 是真的值(刻度 0
    有 28 張),而連結怪獸的守備是「沒有這個欄位」。反過來說,非怪獸一律不帶這五個
    參數——罠モンスター的種族是它變成怪獸之後的形態,不是卡片的參數。這是索引的
    形狀決定;來源層真的漏出參數時由 `_monster_invariant` 吵著讓建置失敗,不是靠
    這裡靜靜濾掉(清理在 card-list 票07)。
    """
    unknown = []
    if not card["type"] & TYPE_MONSTER:
        return unknown
    out["at"] = _coded(unknown, "at", vocab.ATTR, card["attribute"])
    out["r"] = _coded(unknown, "r", vocab.RACE, card["race"])
    if card["type"] & TYPE_LINK:
        # cdb 把連結值存在 `level` 欄(實測 468 張全等於連結標記的數量)
        out["lk"] = card["level"]
        out["lm"] = list(vocab.bitmask_codes(vocab.LINK_MARKER,
                                             card["link_marker"]))
    else:
        out["lv"] = card["level"]
    if card["type"] & TYPE_PENDULUM:
        out["sc"] = card["scale"]
    out["atk"] = card["atk"]
    if not card["type"] & TYPE_LINK:
        out["df"] = card["def"]
    return unknown


def _entry(card, clauses):
    """一張卡 → (索引條目, 對不到短碼的來源值清單)。

    鍵序固定;空值一律省略而不是寫 null(gzip 便宜得多)。

    大類解不出來(`type` 沒有怪獸/魔法/陷阱位元,或同時有兩個)時條目為 None:那張卡
    連一顆按鈕都對不到,進了索引也是搜不到的死資料。呼叫端會讓它落進「卡片總表有
    卡而索引沒有」那一道檢查,建置因此失敗——這正是 Story 60 要擋的形狀。
    """
    cat, subs = vocab.subtypes(card["type"])
    if not cat:
        return None, []
    unknown = []
    desc, alias = _split_alias(card["desc"])
    out = {"id": card["id"]}
    if card["alt_ids"]:
        out["al"] = list(card["alt_ids"])
    out["n"] = card["name_zh"]
    if card["name_ja"]:
        out["nj"] = card["name_ja"]
    if card["name_en"]:
        out["ne"] = card["name_en"]
    if alias:
        out["ax"] = alias
    out["c"] = cat
    out["s"] = list(subs)
    unknown.extend(_monster_face(card, out))
    out["ra"] = _coded(unknown, "ra", vocab.RARITY, card["md_rarity"])
    out["ot"] = _coded(unknown, "ot", vocab.OT, card["ot"])
    # [[禁限狀態]]:只有上榜卡帶(欄位的有無由上榜與否決定,未上榜省略)
    out["bo"] = _coded(unknown, "bo", vocab.BAN_O, card["ban_ocg"])
    out["bt"] = _coded(unknown, "bt", vocab.BAN_T, card["ban_tcg"])
    if card["genesys_points"]:
        out["gy"] = card["genesys_points"]
    if clauses:
        out["tx"] = [cl["text_zh"] for cl in clauses]
        # 對不到時留空字串佔位:建置已經因為檢查失敗,佔位只是讓 `tx` / `k` / `ro`
        # 保持同索引,好讓報告指得出是哪一句。
        out["k"] = [_coded(unknown, "k", vocab.KIND, cl.get("kind")) or ""
                    for cl in clauses]
        # 22,942 個效果句不承載[[必發/選發]];空字串佔位讓 `tx` / `k` / `o` / `ro`
        # 保持同索引,整批都空時整個欄位省略(空值省略而不是寫 null)
        opts = [_coded(unknown, "o", vocab.OPTIONAL, cl.get("optional")) or ""
                for cl in clauses]
        if any(opts):
            out["o"] = opts
        roles = [_coded(unknown, "ro", vocab.ROLE, cl.get("role")) or ""
                 for cl in clauses]
        if any(roles):
            out["ro"] = roles
        pz = [i for i, cl in enumerate(clauses)
              if cl.get("section") == PENDULUM_SECTION]
        if pz:
            out["pz"] = pz
    flavor = _flavor(desc, bool(clauses))
    if flavor:
        out["d"] = flavor
    return {k: v for k, v in out.items() if v is not None}, unknown


def _original_desc(desc, entries):
    """勘誤後卡文 → 勘誤前原樣(逆向套用,由後往前)。

    修正後子字串必須恰出現一次才逆推得回去;不唯一(或勘誤是純刪除,`to` 為空)
    時回 None,由 `errata_not_reversible` 那一道讓建置失敗——「顯示原文」給的
    是承諾過的原樣,逆推不出來就不該裝作推得出來。
    """
    for entry in reversed(entries):
        if not entry["to"] or desc.count(entry["to"]) != 1:
            return None
        desc = desc.replace(entry["to"], entry["from"])
    return desc


def _coverage(desc, pieces):
    """效果句(加故事文)串接後對卡文的覆蓋。→ (缺口清單, 對不上的片段清單)。

    效果句的 `text_zh` 是卡文的連續子字串,依序往後找;找不到代表拆句與卡文對不
    上(卡文變動而拆句沒跟上就是這個形狀)。
    """
    text = _norm(desc)
    pos = 0
    gaps, unmatched = [], []
    for piece in pieces:
        needle = _norm(piece)
        if not needle:
            continue
        found = text.find(needle, pos)
        if found < 0:
            unmatched.append(piece)
            continue
        if found > pos:
            gaps.append(text[pos:found])
        pos = found + len(needle)
    if pos < len(text):
        gaps.append(text[pos:])
    return gaps, unmatched


def _classify_gap(gap):
    """缺口分類;認不出來回傳空字串(→ 建置失敗)。"""
    rest = gap
    for header in SECTION_HEADERS:
        rest = rest.replace(header, "")
    if not rest:
        return GAP_HEADER
    if rest.startswith(ALIAS_MARK):
        return GAP_ALIAS
    return ""


def _monster_invariant(cards):
    """不變式「大類是怪獸 ⟺ 有種族與屬性」的雙向檢查。

    → 靠來源資料成立(9,280 張怪獸無一缺種族或屬性),← 靠[[卡片總表]]的大類閘門
    成立。任一邊非空即代表搜尋與呈現不能再以大類決定要不要顯示怪獸參數:
    罠モンスター的種族是它變成怪獸之後的形態,不是卡片的參數(card-list 票07)。
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


def _unexported_codes(index_cards, exported):
    """索引的短碼有沒有出現在 `window.VOCAB` 的按鈕清單裡。

    這是「索引出現正典沒有的值」的另一半:值域登記了碼卻沒做成按鈕(不可篩選、
    或漏排進分組)時,那批卡在畫面上點不出來——與漏一個碼的失效模式一模一樣,
    只是換了個地方發生,所以 ADR-0008 要求「正典住建置期」與「按鈕由正典生成」
    必須一起成立。空短碼不算:那是缺效果類型那一道檢查的事。
    """
    buttons = {name: {item["code"] for item in dom["items"]}
               for name, dom in exported.items()}
    unknown = []
    for card in index_cards:
        for field, domain, is_list in CODED_FIELDS:
            value = card.get(field)
            if value is None:
                continue
            domain = domain or vocab.SUB[card["c"]]
            for code in (value if is_list else [value]):
                if code and code not in buttons.get(domain, ()):
                    unknown.append({"id": card["id"], "field": field,
                                    "code": code,
                                    "reason": "短碼不在按鈕清單"})
    return unknown


def _census(cards, clauses_by_id):
    """每一個值域的成員數與對應卡數(Story 58)。

    某個值突然掉到 0 就看得見——這是「值域漏一碼、某批卡無聲消失」的另一面:
    碼還在但沒有卡對得上,一樣是壞了。`no_value` 記的是沒有這個參數的卡數
    (非怪獸沒有屬性、MD 未實裝沒有稀有度),它們不是值域成員。
    """
    counts = {name: dict.fromkeys(vocab.codes(name), 0)
              for name in vocab.DOMAINS}
    no_value = dict.fromkeys(vocab.DOMAINS, 0)
    for card in cards:
        cat, subs = vocab.subtypes(card["type"])
        if cat:
            counts[vocab.CAT][cat] += 1
            for code in subs:
                counts[vocab.SUB[cat]][code] += 1
        else:
            no_value[vocab.CAT] += 1
        for name, field in ((vocab.ATTR, "attribute"), (vocab.RACE, "race"),
                            (vocab.RARITY, "md_rarity"), (vocab.OT, "ot"),
                            (vocab.BAN_O, "ban_ocg"),
                            (vocab.BAN_T, "ban_tcg")):
            code = vocab.code_of(name, card[field])
            if code:
                counts[name][code] += 1
            else:
                no_value[name] += 1
        markers = vocab.bitmask_codes(vocab.LINK_MARKER, card["link_marker"])
        for code in markers:
            counts[vocab.LINK_MARKER][code] += 1
        if not markers:
            no_value[vocab.LINK_MARKER] += 1
        for clause in clauses_by_id.get(card["id"]) or ():
            for name, field in ((vocab.KIND, "kind"),
                                (vocab.OPTIONAL, "optional"),
                                (vocab.ROLE, "role")):
                code = vocab.code_of(name, clause.get(field))
                if code:
                    counts[name][code] += 1
                else:
                    no_value[name] += 1
    return {"counts": counts, "no_value": no_value}


def _cross_type_counts(cards, clauses_by_id):
    """魔陷十值各自的**跨類型卡數**(ADR-0010)。

    跨類型 = 有該值的效果句、且自身卡片種類與該值不一致(本類對應由[[值域正典]]
    宣告;靈擺魔法卡效果的本類是靈擺怪獸)。這個數字決定按鈕的去留:0 張的值不
    生成按鈕——本類卡不進成員,按鈕留著就是一顆永遠 0 筆的鈕。
    """
    own = vocab.own_types()
    counts = dict.fromkeys(own, 0)
    for card in cards:
        cat, subs = vocab.subtypes(card["type"])
        codes = {vocab.code_of(vocab.KIND, cl.get("kind"))
                 for cl in clauses_by_id.get(card["id"]) or ()}
        for code in codes & set(own):
            own_cat, own_sub = own[code]
            if not (cat == own_cat and own_sub in subs):
                counts[code] += 1
    return counts


def _drop_buttonless_kinds(exported, cross):
    """跨類型 0 張的值從按鈕分組移除;整組空了連組標題一起拿掉。

    只動 `groups`(按鈕),不動 `items`(顯示詞彙表):本類卡的效果句照樣掛著
    該值的類型標籤,中文查表(`Util.zhTable`)不能因為按鈕沒了而查不到。
    """
    dropped = sorted(code for code, n in cross.items() if not n)
    if not dropped:
        return dropped
    kind = exported[vocab.KIND]
    kind["groups"] = [
        dict(g, codes=codes) for g in kind["groups"]
        if (codes := [c for c in g["codes"] if c not in dropped])]
    return dropped


def _summarise_problems(report):
    """報告 → 問題清單。非空即建置失敗;CLI 薄殼照這一份決定 exit code。"""
    checks = report["checks"]
    found = list(report["vocab"]["problems"])
    inv = report["monster_invariant"]
    pairs = (
        ("卡片總表有卡而索引沒有", checks["missing_cards"]),
        ("卡片密碼重複導致索引掉卡", checks["duplicate_ids"]),
        ("卡片沒有效果標記表條目", checks["cards_without_clause_entry"]),
        ("索引出現值域正典沒有的值", checks["unknown_values"]),
        ("效果句缺效果類型", checks["clauses_without_kind"]),
        ("必發/選發出現在不承載的效果類型上",
         checks["optional_on_non_carrier"]),
        ("效果句串接後出現已知兩種以外的覆蓋缺口", checks["coverage_gaps"]),
        ("效果句在卡文裡找不到", checks["clauses_not_in_desc"]),
        ("type 出現值域正典沒解釋的位元", checks["unexplained_type_bits"]),
        ("※ 別名的缺口與抽取結果對不上", checks["alias_gap_not_extracted"]),
        ("卡文勘誤逆推不回原文", checks["errata_not_reversible"]),
        ("怪獸卻缺種族或屬性", inv["monster_missing_race_or_attribute"]),
        ("非怪獸卻帶怪獸參數", inv["non_monster_with_monster_params"]),
    )
    for label, items in pairs:
        if items:
            found.append(f"{label}: {len(items)} 筆")
    return found


def build_index(cards, tag_cards, built_at="", sources=None, errata=None,
                data_updated_at=None):
    """[[卡片總表]]條目 + [[效果標記表]]條目 → (index, report)。

    `built_at`、`sources`(來源檔雜湊)與 `data_updated_at`([[資料更新時間]],
    來源檔的下載時間)由呼叫端給:讀時鐘與讀檔都是薄殼的事,純函式不碰,
    同一份輸入因此兩次建置產物逐位元組相同。`data_updated_at` 為空
    (None 或空字串)時 META 不帶該欄位——footer 那一行由前端整行省略,
    不是顯示空字串。

    `errata` 是[[卡文勘誤表]](ADR-0011):被勘誤的卡多帶一個 `og` 欄位——
    勘誤**前**的來源卡文原樣,前端「顯示原文」讀它。只有這批卡帶(目前 1 張),
    全量帶原文 gzip 要多 340 KB,而未勘誤的卡的原文就是畫面上那份文字。
    """
    clauses_by_id = {t["id"]: t.get("clauses") or [] for t in tag_cards}
    errata_by_id = {}
    for e in errata or []:
        errata_by_id.setdefault(e["id"], []).append(e)
    checks = {"missing_cards": [], "duplicate_ids": [],
              "cards_without_clause_entry": [], "unknown_values": [],
              "clauses_without_kind": [], "coverage_gaps": [],
              "clauses_not_in_desc": [], "unexplained_type_bits": [],
              "alias_gap_not_extracted": [], "optional_on_non_carrier": [],
              "errata_not_reversible": []}
    known_gaps = {GAP_HEADER: 0, GAP_ALIAS: 0}
    carriers = set(vocab.carriers(vocab.OPTIONAL))
    entries = {}
    clause_total = 0
    for card in cards:
        cid = card["id"]
        clauses = clauses_by_id.get(cid)
        if clauses is None:
            checks["cards_without_clause_entry"].append(cid)
            clauses = []
        entry, unknown = _entry(card, clauses)
        if entry is None:
            continue  # 大類解不出來,由 missing_cards 那一道報上去
        if cid in entries:
            checks["duplicate_ids"].append(cid)
        if cid in errata_by_id:
            og = _original_desc(card["desc"], errata_by_id[cid])
            if og is None:
                checks["errata_not_reversible"].append(cid)
            else:
                entry["og"] = og
        entries[cid] = entry
        clause_total += len(clauses)
        checks["unknown_values"].extend(dict(u, id=cid) for u in unknown)
        opts = entry.get("o") or ()
        for i, clause in enumerate(clauses):
            if not clause.get("kind"):
                checks["clauses_without_kind"].append(
                    {"id": cid, "index": clause.get("index", i)})
            # 不承載[[必發/選發]]的效果類型帶著值 = 一個永遠零結果的條件在等著
            # 使用者設出來(搜尋介面照正典的承載關係決定條件出不出得來,Story 25)
            if opts and opts[i] and entry["k"][i] not in carriers:
                checks["optional_on_non_carrier"].append(
                    {"id": cid, "index": clause.get("index", i),
                     "kind": entry["k"][i], "o": opts[i]})
        pieces = list(entry.get("tx", []))
        if entry.get("d"):
            pieces.append(entry["d"])
        gaps, unmatched = _coverage(card["desc"], pieces)
        for gap in gaps:
            kind = _classify_gap(gap)
            if kind:
                known_gaps[kind] += 1
            else:
                checks["coverage_gaps"].append({"id": cid, "gap": gap})
        # 缺口分類器認得的別名,抽取器必須也抽得到。兩邊的形狀定義漂開的話,那一段
        # 文字就 `tx`、`ax`、`d` 三處都沒有——放它過去等於在覆蓋檢查上開一個洞。
        if any(_classify_gap(g) == GAP_ALIAS for g in gaps) != ("ax" in entry):
            checks["alias_gap_not_extracted"].append(cid)
        for piece in unmatched:
            checks["clauses_not_in_desc"].append({"id": cid, "text": piece})
        bits = vocab.unexplained_type_bits(card["type"])
        if bits:
            checks["unexplained_type_bits"].append({"id": cid,
                                                    "bits": f"{bits:#x}"})
    index_cards = [entries[cid] for cid in sorted(entries)]
    exported = vocab.export()
    cross = _cross_type_counts(cards, clauses_by_id)
    dropped = _drop_buttonless_kinds(exported, cross)
    checks["missing_cards"] = sorted({c["id"] for c in cards} - set(entries))
    checks["unknown_values"].extend(_unexported_codes(index_cards, exported))
    index = {
        "cards": index_cards,
        "vocab": exported,
        "meta": {
            "built_at": built_at,
            **({"data_updated_at": data_updated_at} if data_updated_at else {}),
            "cards": len(index_cards),
            "clauses": clause_total,
            "vocab_digest": vocab.digest(),
            "sources": dict(sources or {}),
        },
    }
    report = {
        "cards": len(index_cards),
        "clauses": clause_total,
        "vocab": {"digest": vocab.digest(), "problems": vocab.problems(),
                  "sizes": {name: len(vocab.codes(name))
                            for name in vocab.DOMAINS}},
        "census": _census(cards, clauses_by_id),
        "kind_cross": {"cards": cross, "dropped": dropped},
        "known_gaps": known_gaps,
        "checks": checks,
        "monster_invariant": _monster_invariant(cards),
    }
    report["problems"] = _summarise_problems(report)
    return index, report


def serialize_index(index):
    """索引 → `web/data.js` 的文字。

    一卡一行、值域一行、META 一鍵一行:`data.js` 入版控(GitHub Pages 直接吃 repo
    內容),而這個 repo 的每一份資料都刻意做成 diff 可讀。卡片那一段用最省的分隔
    符——7.8 MB 裡有 14,207 行,每行省下的空白會被乘上一萬四千倍。
    """
    dump = lambda o: json.dumps(  # noqa: E731
        o, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    cards = ",\n".join(
        json.dumps(c, ensure_ascii=False, separators=(",", ":"))
        for c in index["cards"])
    vocab_lines = ",\n".join(f"{json.dumps(k)}:{dump(v)}"
                             for k, v in sorted(index["vocab"].items()))
    meta_lines = ",\n".join(f"{json.dumps(k)}:{dump(v)}"
                            for k, v in sorted(index["meta"].items()))
    return ("window.CARD_DATA=[\n" + cards + "\n];\n"
            "window.VOCAB={\n" + vocab_lines + "\n};\n"
            "window.META={\n" + meta_lines + "\n};\n")
