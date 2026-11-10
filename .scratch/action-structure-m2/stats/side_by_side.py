# m2_stats.py 兩份輸出逐節並列成 markdown 表(票 14 前後對比;只印 stdout)。
# 跑法:python -X utf8 .scratch/action-structure-m2/stats/side_by_side.py <前.txt> <後.txt>
# 列的順序照「前」那份;同一項的「段/張」「句/張」「區塊/張」「次/張」併成一格(以「 / 」分隔)。
# 卡號清單照原樣並列;項名裡的「|」換成全形「｜」以免切斷表格。兩份標籤集合不同時以非 0 結束(m2_stats.py 的標籤是固定的,只有排序隨數字變)。
import sys

UNITS = ("段", "張", "句", "區塊", "次", "卡號")


def read(path):
    """[(節標題, [(項, 單位, 值)])],照檔案順序。"""
    sections, current = [], None
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if line.startswith("# "):
                current = (line[2:], [])
                sections.append(current)
            elif line:
                label, value = line.split(": ", 1)
                base, _, unit = label.rpartition(" ")
                if unit not in UNITS:
                    base, unit = label, ""
                current[1].append((base, unit, value))
    return sections


def num(value):
    return f"{int(value):,}" if value.isdigit() else value


def main(before_path, after_path):
    before, after = read(before_path), read(after_path)
    after_values = {(base, unit): value for _, rows in after for base, unit, value in rows}
    before_keys = {(base, unit) for _, rows in before for base, unit, _ in rows}
    if before_keys != set(after_values):
        sys.exit(f"兩份標籤不同:{sorted(before_keys ^ set(after_values))}")
    for title, rows in before:
        print(f"### {title}\n")
        print("| 項 | 單位 | 前 | 後 |")
        print("|---|---|---|---|")
        merged = {}  # base → [(unit, 前, 後)],保留首次出現順序
        for base, unit, value in rows:
            merged.setdefault(base, []).append((unit, value, after_values[(base, unit)]))
        for base, cells in merged.items():
            units = " / ".join(u for u, _, _ in cells)
            b = " / ".join(num(v) for _, v, _ in cells)
            a = " / ".join(num(v) for _, _, v in cells)
            print(f"| {base.replace('|', '｜')} | {units} | {b} | {a} |")
        print()


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
