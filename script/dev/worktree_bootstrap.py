# -*- coding: utf-8 -*-
"""把分詞鏈需要、又不入版控的建置輸入複製進一個 git worktree(永遠是複製,不建連結)。

    python script/dev/worktree_bootstrap.py <工作樹路徑> [--build]

從主 repo(git 的 common dir 的上一層)複製:
- data/sources/            下載來源(tokenize.py 讀 ocg-dates.json、official-dates.json;build_index.py 讀 downloaded_at.json)
- .scratch/effect-tokenize/tokens.json   分詞結果(有它就不必跑 tokenize.py)
- .scratch/effect-tokenize/baseline/     剝鍵比對的基準檔(有才複製)
--build 另外跑 frames.py 生 frames.json。已存在且內容相同的檔跳過;可以重跑。
純標準庫。
"""
import argparse
import filecmp
import os
import shutil
import subprocess
import sys

INPUTS = ("data/sources", ".scratch/effect-tokenize/tokens.json", ".scratch/effect-tokenize/baseline")


def main_repo_of(worktree):
    common = subprocess.check_output(["git", "rev-parse", "--git-common-dir"], cwd=worktree,
                                     text=True).strip()
    if not os.path.isabs(common):
        common = os.path.join(worktree, common)
    return os.path.dirname(os.path.abspath(common))


def copy(src, dst):
    """檔或目錄,相同就跳過;回複製了幾個檔。"""
    if os.path.isdir(src):
        return sum(copy(os.path.join(src, name), os.path.join(dst, name)) for name in sorted(os.listdir(src)))
    if os.path.exists(dst) and filecmp.cmp(src, dst, shallow=False):
        return 0
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copyfile(src, dst)
    return 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("worktree")
    parser.add_argument("--build", action="store_true", help="複製完跑 frames.py")
    args = parser.parse_args(argv)
    worktree = os.path.abspath(args.worktree)
    main_repo = main_repo_of(worktree)
    if os.path.normcase(main_repo) == os.path.normcase(worktree):
        print("這是主 repo,不是工作樹:%s" % worktree, file=sys.stderr)
        return 2
    for rel in INPUTS:
        src = os.path.join(main_repo, rel)
        if not os.path.exists(src):
            print("主 repo 沒有 %s,略過(data/sources 要先 python script/card_list/update_cards.py)" % rel)
            continue
        print("%s:複製 %d 個檔" % (rel, copy(src, os.path.join(worktree, rel))))
    if args.build:
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        return subprocess.call([sys.executable, os.path.join(worktree, ".scratch", "effect-tokenize", "frames.py")],
                               cwd=worktree, env=env)
    return 0


if __name__ == "__main__":
    sys.exit(main())
