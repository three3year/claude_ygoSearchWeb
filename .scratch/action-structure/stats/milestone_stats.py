# 票 12 里程碑摘要用的排序統計(讀卡片結構產物,只印 stdout,不寫報告):
# 1. 整張通過反向檢查的張數;不通過的卡若只差一種原因,依原因計張數(補掉那一種就整張通過);
# 2. 各段解析不出原因的段數、「述語解析不出」的段類別分布與常見寫法(粗篩,可重疊);
# 3. 幾個常用動作詞的查詢(預設開關):命中張數與未解析組張數;
# 4. 「述語解析不出」的段依字面結尾(去句讀後末 6 個假名/漢字/全形數字)粗分的段數、張數。
# 粗分只為排優先順序,同一動作的不同寫法會分到不同列。
# 跑法:python -X utf8 stats/milestone_stats.py [repo 根,預設目前目錄] [結尾列數,預設 40]
import json
import os
import re
import sys
from collections import Counter

ROOT = sys.argv[1] if len(sys.argv) > 1 else "."
TOP = int(sys.argv[2]) if len(sys.argv) > 2 else 40
sys.path.insert(0, os.path.join(ROOT, "script", "action_structure"))

from action_query import run_query  # noqa: E402
from card_structure import load_structures  # noqa: E402
from reverse_check import REASON_NO_TEMPLATE, check_card  # noqa: E402
from structure_shape import iter_segments  # noqa: E402

REASON = "述語解析不出"
TAIL_RE = re.compile(r"([ぁ-んァ-ヶー一-龠０-９]{0,6})$")
# 段字面裡常見、子句規則還沒收的寫法(粗篩,一段可落在多列)
MARKERS = [
    ("攻撃力・守備力的增減(アップ/ダウン)", r"(アップ|ダウン)する"),
    ("「選んで」+ 述語", r"選んで"),
    ("含「〜表示で」(表側表示で存在する、守備表示で特殊召喚する…)", r"表示で"),
    ("抗性/限制(されない・できない・受けない)", r"(されない|できない|受けない)$"),
    ("傷害(ダメージ)", r"ダメージ"),
    ("ドロー", r"ドロー"),
    ("超量素材(エクシーズ素材/取り除)", r"(エクシーズ素材|取り除)"),
]

with open(os.path.join(ROOT, "data", "action_structure.json"), encoding="utf-8") as f:
    cards = load_structures(f.read())

with_text = [c for c in cards if not c["unparsed"]]
passed, only_one = 0, Counter()
for card in with_text:
    failures = check_card(card)
    if not failures:
        passed += 1
        continue
    keys = {f["detail"] if f["reason"] == REASON_NO_TEMPLATE else f["reason"] for f in failures}
    if len(keys) == 1:
        only_one[keys.pop()] += 1
print(f"有官方日文 {len(with_text):,} 張;整張通過反向檢查 {passed:,} 張;"
      f"只差一種原因 {sum(only_one.values()):,} 張:")
for key, n in sorted(only_one.items(), key=lambda kv: (-kv[1], kv[0])):
    print(f"  {key}:{n:,} 張")
print()

reasons, kinds, tails, tail_cards = Counter(), Counter(), Counter(), {}
unparsed_texts = []
for card in cards:
    for block in card["blocks"]:
        for _, seg in iter_segments(block):
            if not seg["unparsed"]:
                continue
            reasons[seg["unparsed"]["reason"]] += 1
            if seg["unparsed"]["reason"] != REASON:
                continue
            kinds[seg["kind"]] += 1
            unparsed_texts.append((card["id"], seg["text"]))
            tail = TAIL_RE.search(re.sub(r"[。、]+$", "", seg["text"])).group(1)
            tails[tail] += 1
            tail_cards.setdefault(tail, set()).add(card["id"])

print("段解析不出的原因(段數):", ", ".join(f"{r} {n:,}" for r, n in reasons.most_common()))
print(f"{REASON}的段類別:", ", ".join(f"{k} {n:,}" for k, n in kinds.most_common()))
print(f"\n{REASON}的段裡含下列字面的(可重疊):")
for label, pattern in MARKERS:
    hit = [cid for cid, text in unparsed_texts if re.search(pattern, text)]
    print(f"  {label}:{len(hit):,} 段 / {len(set(hit)):,} 張")
with open(os.path.join(ROOT, "data", "cards.json"), encoding="utf-8") as f:
    card_list = json.load(f)
print("\n常用動作詞的查詢(預設開關):")
for action in ("特殊召喚", "破壞", "送墓", "除外", "加入手牌", "捨棄", "返回"):
    result = run_query(cards, card_list, {"actions": [action]})
    print(f"  {action}:命中 {len(result['hits']):,} 張、"
          f"未解析組 {len(result['groups']['未解析']):,} 張")
print("\n段數\t張數\t末尾字面")
for tail, n in sorted(tails.items(), key=lambda kv: (-kv[1], kv[0]))[:TOP]:
    print(f"{n:,}\t{len(tail_cards[tail]):,}\t{tail or '(非假名漢字結尾)'}")
