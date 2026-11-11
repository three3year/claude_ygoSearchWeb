# m3b 收尾前後對比:先跑里程碑三的 m3_compare.py(總數字、只差一種原因、常用動作詞的查詢),
# 再加這份補票牽動的查詢(反轉、裝備、選択して、召喚進推得表、取り除けない、裝備中)。
# 跑法:python -X utf8 .scratch/action-structure-m3b/stats/m3b_compare.py <repo 根>
#   前 = 里程碑三收尾:git archive 9ebd797 script/action_structure data/action_structure.json data/cards.json
#        解到一個空資料夾當 <repo 根>(用當時的程式讀當時的產物)
#   後 = 整合分支:repo 根本身
# 輸出:m3b_compare_before.txt、m3b_compare_after.txt。決定性;約 1 分鐘。
# 查詢欄是「命中 / 經引用 / 未解析組」張數;該根的程式不認得的動作詞印「不認得」。
import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
COMPARE = os.path.join(HERE, "..", "..", "action-structure-m3", "stats", "m3_compare.py")

main = runpy.run_path(COMPARE, run_name="__main__")
query = main["query"]

RAISE_DEAD = 83764718   # 死者蘇生(通常魔法,不可能是裝備卡)
POWER = 83746708        # 魔導師の力(裝備魔法)

EXTRA = (
    ("反轉", {"actions": ["反轉"]}),
    ("反轉,條件段開", {"actions": ["反轉"], "include_condition": True}),
    ("反轉召喚,條件段開", {"actions": ["反轉召喚"], "include_condition": True}),
    ("裝備,只看取對象", {"actions": ["裝備"], "targeting": True}),
    ("裝備,從 額外牌組", {"actions": ["裝備"], "from_zones": ["額外牌組"]}),
    ("裝備,從 墓地", {"actions": ["裝備"], "from_zones": ["墓地"]}),
    ("裝備,指定 死者蘇生", {"actions": ["裝備"], "card": RAISE_DEAD}),
    ("裝備,指定 魔導師の力", {"actions": ["裝備"], "card": POWER}),
    ("破壞,指定 死者蘇生", {"actions": ["破壞"], "card": RAISE_DEAD}),
    ("破壞,指定 死者蘇生,代替開", {"actions": ["破壞"], "card": RAISE_DEAD, "replacement": True}),
    ("破壞,指定 魔導師の力,代替開", {"actions": ["破壞"], "card": POWER, "replacement": True}),
    ("捨棄,只看取對象", {"actions": ["捨棄"], "targeting": True}),
    ("召喚,到 場上,推得開", {"actions": ["召喚"], "to_zones": ["場上"], "include_inferred": True}),
    ("上級召喚,到 場上,推得開", {"actions": ["上級召喚"], "to_zones": ["場上"], "include_inferred": True}),
    ("去除,極性不能,條件段開", {"actions": ["去除"], "polarities": ["不能"], "include_condition": True}),
    ("解放,條件段開", {"actions": ["解放"], "include_condition": True}),
)

print("m3b 補票牽動的查詢(命中 / 經引用 / 未解析):")
for name, q in EXTRA:
    print(f"查詢 {name}: {query(q)}")
