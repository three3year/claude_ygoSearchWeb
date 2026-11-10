"""票 13:逐票的數字軌跡——里程碑二的產物與每張票合進整合分支後重建的產物,各用當時的程式跑 m3_compare.py。
跑法(repo 根):python -X utf8 .scratch/action-structure-m3/stats/m3_trajectory.py [最後一列的 commit,預設 HEAD]
  每個 commit:git archive <commit> script/action_structure data/action_structure.json data/cards.json 解到暫存資料夾,
  當 <repo 根> 跑本目錄的 m3_compare.py,取其中幾項排成 markdown 表(一列一個 commit)。
  最後一列是參數給的 commit(預設 HEAD;要已 commit 的產物,工作樹沒 commit 的改動不算)。
輸出決定性:列的順序固定、不印時間與路徑。12 列約 6 分鐘。
"""
import io
import os
import subprocess
import sys
import tarfile
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
LAST = sys.argv[1] if len(sys.argv) > 1 else "HEAD"

# (說明, commit):整合分支上「合進整合分支後重建產物與報告」的 commit,照合入順序。
STEPS = [
    ("里程碑二(前)", "834f518"),
    ("票 02 小型寫法", "c0afb7b"),
    ("票 07 宣告左半", "7f1a99b"),
    ("票 08 召喚動作詞", "324091e"),
    ("票 11 時點與降臨", "a73dbaf"),
    ("票 03 物件切點", "ef94482"),
    ("票 09 X素材", "c9b0906"),
    ("票 04 修飾:閉集", "174864c"),
    ("票 05 修飾:回指與此卡", "b51014c"),
    ("票 12 前提", "abf206a"),
    ("票 10 離場", "850dc55"),
    ("票 06 異同", "67b15a3"),
    ("收尾(後)", LAST),
]
PATHS = ["script/action_structure", "data/action_structure.json", "data/cards.json"]
COLUMNS = ["段", "段解析出", "段解析出比例", "反向檢查通過 段", "整張通過 張",
           "解析不出物件", "查詢 特殊召喚", "查詢 破壞", "查詢 送墓", "查詢 解放"]


def numbers(commit):
    """那個 commit 的 m3_compare.py 輸出 → {項: 值}。"""
    archive = subprocess.run(["git", "-C", REPO, "archive", commit, *PATHS],
                             check=True, capture_output=True).stdout
    with tempfile.TemporaryDirectory() as root:
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            tar.extractall(root, filter="data")
        out = subprocess.run([sys.executable, "-X", "utf8", os.path.join(HERE, "m3_compare.py"), root],
                             check=True, capture_output=True, encoding="utf-8").stdout
    return dict(line.split(": ", 1) for line in out.splitlines() if ": " in line)


def short_query(value):
    """「命中 / 經引用 / 未解析」→「命中 / 未解析」。"""
    parts = value.split(" / ")
    return f"{int(parts[0]):,} / {int(parts[2]):,}" if len(parts) == 3 else value


def cell(column, value):
    if column.startswith("查詢"):
        return short_query(value)
    return f"{int(value):,}" if value.isdigit() else value


print("| 合入 | commit | " + " | ".join(
    c + "(命中 / 未解析)" if c.startswith("查詢") else c for c in COLUMNS) + " |")
print("|---|---|" + "---|" * len(COLUMNS))
for label, commit in STEPS:
    row = numbers(commit)
    resolved = subprocess.run(["git", "-C", REPO, "rev-parse", "--short=7", commit],
                              check=True, capture_output=True, encoding="utf-8").stdout.strip()
    print(f"| {label} | {resolved} | " + " | ".join(cell(c, row.get(c, "—")) for c in COLUMNS) + " |")
