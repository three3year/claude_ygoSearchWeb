# -*- coding: utf-8 -*-
"""第四版論元各模組的機械規則(CODING_STANDARDS.md 把它們交給這裡,審查者不再用眼睛找)。

- 步驟模組(enrich 與它呼叫的 phrases/regions/agent/manner/negation、封閉表 closed_values)不 import frames:
  frames.py import 它們,反向 import 是循環;需要的常數從 constraints/action_lemmas/places 拿。
- 步驟模組不 `sys.path.insert`:它們只被 frames.py 這類入口載入,路徑由入口設。
- 位置與極性常數只在 constraints.py 定義:其他模組出現 "代價"/"效果"/"條件" 字面就是抄了一份。
- enrich.STEPS 裡的每個步驟模組自己宣告 mark(ctx, tokens, frame)、batch_cells(frame) 與 FILL_RATE_ROWS(retro
  第 9 項:收集端只有 STEPS 一張表;步驟模組一定加了新鍵,新鍵就要有填充率列與批次檔格;REPORT_SECTIONS 可選)。
  步驟模組清單也從 enrich.py 的 STEPS 讀,不另抄。

只讀原始碼(ast),不執行模組。執行:PYTHONIOENCODING=utf-8 python -m unittest discover -s .scratch/effect-tokenize
"""
import ast
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

    def test_position_literals_live_only_in_constraints(self):
        offenders = {name: [line for line, text in string_literals(parse(name)) if text in POSITION_LITERALS]
                     for name in STEP_MODULES + ("report", "llm_check", "prepare_view")}
        self.assertEqual({k: v for k, v in offenders.items() if v}, {},
                         "位置用 constraints.POS_COST/POS_EFFECT/POS_COND,別抄字面")


if __name__ == "__main__":
    unittest.main()
