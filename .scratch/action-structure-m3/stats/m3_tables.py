"""票 13:把統計輸出排成收尾摘要用的 markdown 表(只印 stdout;摘要裡這幾張表是它的原樣輸出)。
跑法(repo 根):python -X utf8 .scratch/action-structure-m3/stats/m3_tables.py
讀同目錄的 m3_compare_before.txt、m3_compare_after.txt(m3_compare.py 前後各跑一次的輸出)與
m3_golden_check.txt(m3_golden_check.py 的輸出)。印四節:總數字、只差一種原因、查詢、標準卡。
輸出決定性:列的順序照「後」那份(只在「前」出現的接在後面)。
"""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))


def read(name):
    rows = {}
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if ": " in line:
                key, value = line.split(": ", 1)
                rows[key] = value
    return rows


def num(value):
    """數字加千分位;「12 段 / 3 張」「1 / 2 / 3」「123;解析出 45」裡的數字也加。"""
    return re.sub(r"\d{4,}", lambda m: f"{int(m.group()):,}", value)


before, after = read("m3_compare_before.txt"), read("m3_compare_after.txt")
keys = list(after) + [k for k in before if k not in after]


def table(title, wanted, strip=""):
    print(f"### {title}\n")
    print("| 項 | 前 | 後 |")
    print("|---|---|---|")
    for key in keys:
        if wanted(key):
            label = key[len(strip):] if strip and key.startswith(strip) else key
            print(f"| {label} | {num(before.get(key, '—'))} | {num(after.get(key, '—'))} |")
    print()


table("總數字", lambda k: not k.startswith(("只差一種原因 ", "查詢 ")))
table("只差一種原因", lambda k: k.startswith("只差一種原因 "), "只差一種原因 ")

print("### 查詢\n")
print("| 查詢 | 前 命中 / 經引用 / 未解析 | 後 命中 / 經引用 / 未解析 |")
print("|---|---|---|")
for key in keys:
    if key.startswith("查詢 "):
        print(f"| {key[3:]} | {num(before.get(key, '—'))} | {num(after.get(key, '—'))} |")
print()

print("### 標準卡\n")
print("| 票 | 角色 | 卡號 | 卡名 | 段 | 反向檢查 | 還卡在哪 |")
print("|---|---|---|---|---|---|---|")
row, stuck = None, []


def flush():
    if row:
        print("| " + " | ".join(row) + " | " + ";".join(stuck).replace("|", "｜") + " |")


with open(os.path.join(HERE, "m3_golden_check.txt"), encoding="utf-8") as f:
    for line in f:
        line = line.rstrip("\n")
        m = re.match(r"  票 (\d+) (\S+) (\d+) (.+):段 (\d+),(.+)$", line)
        if m:
            flush()
            row, stuck = list(m.groups()), []
        elif row and line.startswith("      - "):
            # 「原因/細節:段的原文」;細節本身是「段解析不出:述語解析不出」這種,只留最後一截。
            reason, _, text = line[8:].rpartition(":")
            reason = reason.split("/", 1)[1].split(":")[-1]
            stuck.append(f"{reason}「{text}」" if text else reason)
        elif row and not line.strip():
            flush()
            row = None
flush()
