# -*- coding: utf-8 -*-
"""PreToolUse hook(Bash/PowerShell):擋下兩件 2026-11-01 讓 data/sources/ 全失的事。

1. 建連結(mklink、New-Item -ItemType Junction/SymbolicLink、ln -s、fsutil hardlink):
   工作樹需要建置輸入時用 script/dev/worktree_bootstrap.py 複製,不建連結。
2. `git worktree remove` 的目標底下還有 reparse point(junction/symlink)時:git 會穿過連結
   刪掉連結目標的真檔;先把連結拆掉再刪。

stdin 是 Claude Code 的 hook JSON;要擋時印 permissionDecision=deny 的 JSON、exit 0。
手動測:echo '{"tool_input":{"command":"mklink /J a b"}}' | python .claude/hooks/guard_links.py
"""
import json
import os
import re
import stat
import sys

LINK_COMMANDS = re.compile(
    r"\bmklink\b|-ItemType\s+(?:Junction|SymbolicLink|HardLink)\b|\bln\s+-s|"
    r"\bfsutil\s+(?:hardlink|reparsepoint)\b", re.IGNORECASE)
WORKTREE_REMOVE = re.compile(r"\bgit\s+worktree\s+remove\s+([^&|;\n]*)")


def deny(reason):
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse", "permissionDecision": "deny",
        "permissionDecisionReason": reason}}, ensure_ascii=False))
    sys.exit(0)


def is_reparse_point(path):
    try:
        st = os.lstat(path)
    except OSError:
        return False
    if stat.S_ISLNK(st.st_mode):
        return True
    attributes = getattr(st, "st_file_attributes", 0)
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def reparse_points_under(root):
    """root 底下(含自己)的連結清單;掃到連結不往裡走。"""
    found = []
    if is_reparse_point(root):
        return [root]
    for dirpath, dirnames, filenames in os.walk(root):
        keep = []
        for name in dirnames:
            full = os.path.join(dirpath, name)
            if is_reparse_point(full):
                found.append(full)
            else:
                keep.append(name)
        dirnames[:] = keep
        for name in filenames:
            full = os.path.join(dirpath, name)
            if is_reparse_point(full):
                found.append(full)
    return found


def worktree_targets(command, cwd):
    out = []
    for m in WORKTREE_REMOVE.finditer(command):
        for arg in m.group(1).split():
            if arg.startswith("-"):
                continue
            arg = arg.strip("\"'")
            out.append(arg if os.path.isabs(arg) else os.path.join(cwd, arg))
    return out


def main():
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return 0
    command = (data.get("tool_input") or {}).get("command") or ""
    if LINK_COMMANDS.search(command):
        deny("建連結(junction/symlink/hardlink)被擋下:工作樹要建置輸入時用 "
             "python script/dev/worktree_bootstrap.py <工作樹路徑> 複製進去。"
             "原因:git worktree remove/clean 會穿過連結刪掉目標的真檔(2026-11-01 data/sources 全失)。")
    cwd = data.get("cwd") or os.getcwd()
    for target in worktree_targets(command, cwd):
        if not os.path.isdir(target):
            continue
        links = reparse_points_under(target)
        if links:
            deny("git worktree remove 被擋下:%s 底下還有連結,git 會穿過它刪掉目標的真檔。"
                 "先拆掉連結(PowerShell:(Get-Item <連結> -Force).Delete())再刪工作樹。連結:%s"
                 % (target, "、".join(links[:5])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
