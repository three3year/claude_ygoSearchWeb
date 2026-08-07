"""官方 Q&A 快取的缺口盤點與 cid 對應表管理(純函式)。

接縫:
- find_missing_cards(cards, faq_entries) → 有卡片密碼卻沒有官方 Q&A 資料的卡
- extract_konami_ids(dump) → {卡片密碼: konami_id}
- build_cid_to_password(dump 序列) → {cid: 卡片密碼}
- diff_cid_mapping(old, new) → 新舊對應表差異與「只增不減」判定

不碰網路與檔案系統(DEFAULT_CACHE 只是由模組位置推算的路徑字串)。
"""
import os

# 快取預設位置:以 repo 根為基準的相對路徑,與執行目錄無關。
ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_CACHE = os.path.normpath(
    os.path.join(ROOT, "..", "data_ygoFaqCache", "_cache"))

# TCG 限定卡(ot=2)在 KONAMI 日文資料庫沒有頁面,結構性不可能有補足情報,
# 因此不列入缺口。ot=1(OCG 限定)與 ot=3(兩者)都有日文頁。
TCG_ONLY_OT = 2


def _covered_passwords(faq_entries):
    return {e["password"] for e in faq_entries if e.get("password") is not None}


def find_missing_cards(cards, faq_entries, with_excluded=False):
    """找出卡片總表中沒有對應官方 Q&A 資料的卡,依卡片密碼升冪。

    主卡密碼或任一異圖密碼命中即視為已涵蓋(總表把異圖併入主卡,
    但官方 Q&A 可能是以異圖密碼登錄的)。
    with_excluded=True 時回傳 (missing, excluded),excluded 為 TCG 限定卡。
    """
    covered = _covered_passwords(faq_entries)
    missing, excluded = [], []
    for c in cards:
        if c["id"] in covered or any(a in covered for a in c.get("alt_ids", ())):
            continue
        (excluded if c.get("ot") == TCG_ONLY_OT else missing).append(c)
    missing.sort(key=lambda c: c["id"])
    excluded.sort(key=lambda c: c["id"])
    return (missing, excluded) if with_excluded else missing


def extract_konami_ids(dump):
    """自一份 ygoprodeck dump 取 {卡片密碼: konami_id};無 konami_id 的卡略過。"""
    result = {}
    for card in dump.get("data", []):
        for misc in card.get("misc_info") or ():
            kid = misc.get("konami_id")
            if kid is not None:
                result[card["id"]] = kid
                break
    return result


def build_cid_to_password(dumps):
    """由多份 ygoprodeck dump 建 {cid: 卡片密碼};先出現者優先,後者不覆寫。"""
    mapping = {}
    for dump in dumps:
        for password, kid in extract_konami_ids(dump).items():
            mapping.setdefault(kid, password)
    return mapping


def diff_cid_mapping(old, new):
    """比對新舊 cid→卡片密碼 對應表。

    is_safe 為 True 表示「只增不減」:沒有任何 cid 消失,也沒有任何 cid 改指
    到不同的卡片密碼。為 False 時呼叫端應停下回報,不要拿新表覆蓋既有資料。
    """
    added = sorted(set(new) - set(old))
    removed = sorted(set(old) - set(new))
    changed = sorted((cid, old[cid], new[cid])
                     for cid in set(old) & set(new) if old[cid] != new[cid])
    return {"added": added, "removed": removed, "changed": changed,
            "is_safe": not removed and not changed}


def build_password_to_card(cards):
    """{任一卡片密碼(主卡或異圖): 主卡密碼}。"""
    result = {}
    for c in cards:
        result[c["id"]] = c["id"]
        for alt in c.get("alt_ids", ()):
            result[alt] = c["id"]
    return result


def split_alt_artwork_changes(changed, cards):
    """把 diff_cid_mapping 的 changed 拆成 (同卡異圖, 真的改指別張卡)。

    ygoprodeck dump 的排序會影響同一張卡由哪個密碼代表(主卡或異圖),
    所以 cid 從某密碼改指到同一張卡的另一個密碼是良性的,不必擋下流程。
    認不出來的密碼(不在卡片總表內)一律歸為真的改指,由人判讀。
    """
    to_card = build_password_to_card(cards)
    benign, real = [], []
    for item in changed:
        _, old_pw, new_pw = item
        old_card = to_card.get(old_pw)
        new_card = to_card.get(new_pw)
        if old_card is not None and old_card == new_card:
            benign.append(item)
        else:
            real.append(item)
    return benign, real


def format_gap_report(missing, excluded, sample=10):
    """把缺口盤點結果格式化成可列印的行序列。"""
    if not missing:
        return ["官方 Q&A 缺口: 無缺口"
                f"(另有 {len(excluded)} 張 TCG 限定卡不列入)"]
    lines = [f"官方 Q&A 缺口: {len(missing)} 張卡沒有官方 Q&A 資料"
             f"(另有 {len(excluded)} 張 TCG 限定卡不列入)"]
    shown = missing[:sample]
    for c in shown:
        lines.append(f"  {c['id']} {c.get('name_ja') or c.get('name_zh', '')}")
    if len(missing) > len(shown):
        lines.append(f"  ...(其餘 {len(missing) - len(shown)} 張略)")
    return lines
