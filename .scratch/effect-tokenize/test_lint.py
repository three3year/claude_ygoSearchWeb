# -*- coding: utf-8 -*-
"""第四版論元各模組的機械規則(CODING_STANDARDS.md 把它們交給這裡,審查者不再用眼睛找)。

- 步驟模組(enrich 與它呼叫的 phrases/regions/agent/manner/negation、封閉表 closed_values)不 import frames:
  frames.py import 它們,反向 import 是循環;需要的常數從 constraints/action_lemmas/places 拿。
- 步驟模組不 `sys.path.insert`:它們只被 frames.py 這類入口載入,路徑由入口設。
- 位置與極性常數只在 constraints.py 定義:其他模組出現 "代價"/"效果"/"條件" 字面就是抄了一份。
- enrich.STEPS 裡的每個步驟模組自己宣告 mark(ctx, tokens, frame)、batch_cells(frame) 與 FILL_RATE_ROWS(retro
  第 9 項:收集端只有 STEPS 一張表;步驟模組一定加了新鍵,新鍵就要有填充率列與批次檔格;REPORT_SECTIONS 可選)。
  步驟模組清單也從 enrich.py 的 STEPS 讀,不另抄。
- 具名查詢目錄線的模組(predicate、catalog、catalog_hits)不 import 舊歸葉程式(categories、export_categories):規格 4 刪舊的時它們留下。
- 回指(anaphora)、動作對象(patient)與它們共用的小表(referent)沒有正則式、不呼叫區域辨識解字面(places.parse_zones/
  parse_place):named-queries 票 03/04 改讀論元片語——封閉表在模組頂、判定讀片語的段,區域交給 regions.zones_of。
- 宣告 BEFORE_ANAPHORA = True 的步驟模組(片語)要排在 STEPS 前段(named-queries 票 02:enrich 依宣告分回指前後
  兩段跑,STEPS 的順序才仍是執行順序;後段模組夾在前段模組之前就是順序寫錯了)。

只讀原始碼(ast),不執行模組。執行:PYTHONIOENCODING=utf-8 python -m unittest discover -s .scratch/effect-tokenize
"""
import ast
import itertools
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
POSITION_LITERALS = ("代價", "效果", "條件")
REQUIRED_HOOKS = ("mark", "batch_cells")
REQUIRED_DECLARATIONS = ("FILL_RATE_ROWS",)


def parse(name):
    with open(os.path.join(HERE, name + ".py"), encoding="utf-8") as f:
        return ast.parse(f.read(), name + ".py")


def enrich_steps():
    """enrich.py 的 STEPS = (模組, …) 列的模組名(只讀原始碼)。"""
    for node in ast.walk(parse("enrich")):
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "STEPS" for t in node.targets):
            return tuple(elt.id for elt in node.value.elts)
    raise AssertionError("enrich.py 沒有 STEPS = (模組, …)")


ENRICH_STEPS = enrich_steps()
STEP_MODULES = ("enrich", *ENRICH_STEPS, "closed_values")
# 具名查詢目錄線的模組與它們不能 import 的舊歸葉程式(named-queries 票 07;票 08 加命中)
CATALOG_MODULES = ("predicate", "catalog", "catalog_hits")
OLD_CLASSIFIER_MODULES = frozenset(("categories", "export_categories"))
# 改讀論元片語的模組(named-queries 票 03/04)與它們共用的小表:沒有正則式、不自己解區域字面
PHRASE_READERS = ("anaphora", "patient", "referent")
LITERAL_ZONE_PARSERS = frozenset(("parse_zones", "parse_place"))


def declares_true(tree, name):
    """頂層 `name = True` 的宣告(只讀原始碼)。"""
    return any(isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) and node.value.value is True
               and any(isinstance(t, ast.Name) and t.id == name for t in node.targets)
               for node in tree.body)


def top_level_defs(tree):
    return {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}


def top_level_assignments(tree):
    return {target.id for node in tree.body if isinstance(node, ast.Assign)
            for target in node.targets if isinstance(target, ast.Name)}


def imported_modules(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            yield node.module


def sys_path_inserts(tree):
    return [node.lineno for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == "insert" and isinstance(node.func.value, ast.Attribute)
            and node.func.value.attr == "path"]


def string_literals(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node.lineno, node.value


def imported_names(tree):
    """`from X import a, b` 的 X.a、X.b 與 `import X` 的 X。"""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                yield node.module + "." + alias.name


def attribute_uses(tree, owner):
    """`owner.xxx` 的 xxx(owner 是模組名)。"""
    return [node.attr for node in ast.walk(tree)
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == owner]


class TestStepModules(unittest.TestCase):
    """步驟模組的 import 形狀。"""

    def test_step_modules_do_not_import_frames(self):
        offenders = [name for name in STEP_MODULES if "frames" in set(imported_modules(parse(name)))]
        self.assertEqual(offenders, [], "import frames 會循環;常數改從 constraints/action_lemmas/places 拿")

    def test_step_modules_do_not_touch_sys_path(self):
        offenders = {name: sys_path_inserts(parse(name)) for name in STEP_MODULES}
        self.assertEqual({k: v for k, v in offenders.items() if v}, {}, "路徑由入口模組設")

    def test_steps_declare_required_hooks(self):
        missing = {}
        for name in ENRICH_STEPS:
            tree = parse(name)
            defs, assigned = top_level_defs(tree), top_level_assignments(tree)
            missing[name] = ([hook for hook in REQUIRED_HOOKS if hook not in defs]
                             + [decl for decl in REQUIRED_DECLARATIONS if decl not in assigned])
        self.assertEqual({k: v for k, v in missing.items() if v}, {},
                         "enrich.STEPS 的模組要自己定義 mark(ctx, tokens, frame)、batch_cells(frame) 與 FILL_RATE_ROWS,"
                         "enrich 只迭代清單")

    def test_before_anaphora_steps_lead_the_list(self):
        flags = [declares_true(parse(name), "BEFORE_ANAPHORA") for name in ENRICH_STEPS]
        leading = len(flags) - len(list(itertools.dropwhile(lambda f: f, flags)))
        self.assertEqual(flags[leading:], [False] * (len(flags) - leading),
                         "宣告 BEFORE_ANAPHORA 的模組排 STEPS 前段:enrich 先跑它們、再回指、再跑其餘,STEPS 順序才是執行順序")

    def test_position_literals_live_only_in_constraints(self):
        offenders = {name: [line for line, text in string_literals(parse(name)) if text in POSITION_LITERALS]
                     for name in STEP_MODULES + ("report", "llm_check", "prepare_view")}
        self.assertEqual({k: v for k, v in offenders.items() if v}, {},
                         "位置用 constraints.POS_COST/POS_EFFECT/POS_COND,別抄字面")


class TestPhraseReaders(unittest.TestCase):
    """回指、動作對象與共用小表(named-queries 票 03/04):沒有正則式、不呼叫區域辨識解字面。"""

    def test_phrase_readers_have_no_regex(self):
        offenders = {name: sorted(set(attribute_uses(parse(name), "re")) | {n for n in imported_names(parse(name))
                                                                             if n == "re" or n.startswith("re.")})
                     for name in PHRASE_READERS}
        self.assertEqual({k: v for k, v in offenders.items() if v}, {}, "封閉表在模組頂,判定讀片語的段,不拆字面")

    def test_phrase_readers_do_not_parse_zone_literals(self):
        offenders = {name: sorted({n for n in imported_names(parse(name)) if n.split(".")[-1] in LITERAL_ZONE_PARSERS}
                                  | (set(attribute_uses(parse(name), "places")) & LITERAL_ZONE_PARSERS))
                     for name in PHRASE_READERS}
        self.assertEqual({k: v for k, v in offenders.items() if v}, {}, "區域讀段的 zones 或交給 regions.zones_of")


class TestCatalogModules(unittest.TestCase):
    """具名查詢目錄與述詞字彙(named-queries 票 06/07)不 import 舊歸葉程式:類別線退場後它們留下,
    舊的 categories/export_categories 在規格 4 刪。"""

    def test_catalog_modules_do_not_import_the_old_classifier(self):
        offenders = {name: sorted(set(imported_modules(parse(name))) & OLD_CLASSIFIER_MODULES)
                     for name in CATALOG_MODULES}
        self.assertEqual({k: v for k, v in offenders.items() if v}, {}, "目錄模組只讀 predicate 與封閉表")


if __name__ == "__main__":
    unittest.main()
