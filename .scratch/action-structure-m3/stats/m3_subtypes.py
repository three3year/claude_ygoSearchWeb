"""票 13:m3 各類統計腳本(c1、c2、c3、c5、c6)前後兩份輸出裡的子型表,逐表並列成 markdown(只印 stdout)。
跑法:python -X utf8 .scratch/action-structure-m3/stats/m3_subtypes.py <前.txt> <後.txt>
  前 = 834f518 產物上跑的輸出(同目錄已入版控的 c*.txt);後 = 整合分支產物上重跑的輸出(c*_after.txt)。
  只取每張表的前三欄(子型、段或物件、張),例句不印;表上面那一行前後並成一行(「說明:前 → 後」),說明文字前後不同時分兩行印(「前:」「後:」)。
  兩份的表照出現順序一一對應;子型以名稱對,只在一邊出現的另一邊印「—」。輸出決定性:照「前」的列順序,後才有的列接在後面。
"""
import sys


def read(path):
    """[(表前一行, 欄名, {子型: (數, 張)})],照檔案順序。"""
    tables, previous, current = [], "", None
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\n")
            if line.startswith("|"):
                cells = [c.strip() for c in line.strip("|").split("|")]
                if current is None:
                    current = (previous, cells[1], {})
                    tables.append(current)
                elif not set(cells[0]) <= set("-"):
                    current[2][cells[0]] = (cells[1], cells[2])
            else:
                current = None
                if line.strip():
                    previous = line.strip()
    return tables


def num(value):
    return f"{int(value):,}" if value.isdigit() else value


def main(before_path, after_path):
    before, after = read(before_path), read(after_path)
    if len(before) != len(after):
        sys.exit(f"兩份的表數不同:前 {len(before)}、後 {len(after)}")
    for (title_b, unit, rows_b), (title_a, _, rows_a) in zip(before, after):
        label_b, _, value_b = title_b.rpartition(": ")
        label_a, _, value_a = title_a.rpartition(": ")
        if label_b and label_b == label_a:
            print(f"{label_b}:{value_b} → {value_a}\n")
        else:
            print(f"前:{title_b}")
            print(f"後:{title_a}\n")
        print(f"| 子型 | 前 {unit} / 張 | 後 {unit} / 張 |")
        print("|---|---|---|")
        for name in list(rows_b) + [n for n in rows_a if n not in rows_b]:
            b = " / ".join(num(v) for v in rows_b[name]) if name in rows_b else "—"
            a = " / ".join(num(v) for v in rows_a[name]) if name in rows_a else "—"
            print(f"| {name.replace('|', '｜')} | {b} | {a} |")
        print()


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
