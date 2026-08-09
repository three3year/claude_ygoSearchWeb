"""tag_card 四支 CLI 薄殼共用的檔案位置與 JSON 讀寫。

管線本身是純函式、不碰檔案系統(`tagcard.py` / `masked.py`),路徑與 I/O 因此全部
集中在這裡,四支薄殼都從這裡拿——不然「哪一份是標記表」會有四個答案。

`data/` 底下那幾份的名字以**檔案**為準而不是以某一支薄殼的角色為準:
`data/tag_cards.json` 對建置是輸出、對批次與遮蔽測試是輸入,叫 DEFAULT_TAG_CARDS
四支才讀得懂;各自的旗標(`--out` / `--sheet` / `--tag-cards`)才是角色。
"""
import json
import os

ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DEFAULT_CARDS = os.path.join(ROOT, "data", "cards.json")
DEFAULT_FAQ_INFO = os.path.join(ROOT, "data", "sources", "faq_info.json")
DEFAULT_TAG_CARDS = os.path.join(ROOT, "data", "tag_cards.json")
DEFAULT_SPLITS = os.path.join(ROOT, "data", "clause_splits.json")
DEFAULT_RULES_DOC = os.path.join(ROOT, "docs", "effect_kind_rules.md")


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_optional(path, missing=None):
    """來源檔還不存在時不是錯誤——拆句表與標記表都是一票一票長出來的。"""
    return load_json(path) if os.path.exists(path) else missing


def dump_json(path, payload):
    """寫出 JSON:indent=2、不 escape 中文、LF 結尾,與入版控的來源檔同一套格式。"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")
