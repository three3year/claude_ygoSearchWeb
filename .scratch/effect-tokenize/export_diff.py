# -*- coding: utf-8 -*-
"""匯出檔比對(summon-procedure 票 01):召喚手續框進匯出檔是只加不改——剝掉召喚手續的部分後,
data/action_frames.json 要和加之前的匯出檔逐句相同。

- strip(doc):剝掉召喚手續後要比的部分(STRIPPED_SECTIONS):
    值域      每張值清單剝掉 召喚手續(位置的值域多一個值)
    目錄      每列 cards/hash 剝掉 召喚手續 那一格(大類、中類列同)
    統計位置  統計.位置 剝掉 召喚手續 那一格
    卡面      原樣
    句        每句的框列剝掉位置是 召喚手續 的框列(句本身不增不減:沒有框的句也匯成一列)
  不比:版本(格式版本 2 → 3 是預期的)、說明(文字跟著改)、統計的動作對象部分(框架、卡、理由…是全部框合計,
  剝不出召喚手續框那一份;逐框的動作對象由下游基準 patient 尺在剝框重編後守)。
- diff(base, cur) → [(區, 鍵, 基準值, 現值)]:兩份匯出文件剝完後逐區、逐鍵比;一邊沒有的記 MISSING。
  區依 STRIPPED_SECTIONS 序;鍵是 值域欄名、目錄路徑(tuple)、位置、卡片密碼、句鍵 (卡片密碼, 段落, index)。
- stripped_md5(doc):剝完的 md5(鍵排序、緊湊 JSON)。
- freeze(loc) 寫 <digest_dir>/export-digest.json(入版控:輸入檔的 md5 與剝完的 md5)並把匯出檔複製成
  baseline/action_frames.json(gitignore,逐列比對用);check_digest(loc) → (ok|mismatch|skip, 說明):
  輸入(語料 tokens.json、卡面 cards.json、目錄 catalog.json)變了就 skip 並要求重新凍結。

CLI:PYTHONIOENCODING=utf-8 python .scratch/effect-tokenize/export_diff.py [--baseline P] [--freeze] [--limit N]
  不帶 --freeze:印 digest 守門,有基準檔(預設 baseline/action_frames.json;也可給
  `git show main:data/action_frames.json` 存下的檔)再逐列列差異;差異非 0 或 mismatch 時 exit 1。
"""
import argparse
from collections import namedtuple
import hashlib
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from catalog import CATALOG  # noqa: E402
from constraints import POS_PROCEDURE  # noqa: E402
from export_common import CARDS, TOKENS  # noqa: E402
from export_frames import OUT as EXPORT  # noqa: E402

BASELINE_DIR = os.path.join(HERE, "baseline")
DIGEST_NAME = "export-digest.json"

Locations = namedtuple("Locations", "export inputs baseline_dir digest_dir")
DEFAULT = Locations(EXPORT, (TOKENS, CARDS, CATALOG), BASELINE_DIR, HERE)

STRIPPED_SECTIONS = ("值域", "目錄", "統計位置", "卡面", "句")
MISSING = "(沒有這一列)"


def _without_procedure(cells):
    return {position: value for position, value in cells.items() if position != POS_PROCEDURE}


def strip(doc):
    """匯出文件 → 剝掉召喚手續後要比的部分({區: 值},區見 STRIPPED_SECTIONS)。"""
    return {
        "值域": {field: [v for v in values if v != POS_PROCEDURE] for field, values in doc["值域"].items()},
        "目錄": [dict(row, cards=_without_procedure(row["cards"]), hash=_without_procedure(row["hash"]))
                 for row in doc["目錄"]],
        "統計位置": _without_procedure(doc["統計"]["位置"]),
        "卡面": doc["卡面"],
        "句": [dict(row, frames=[fr for fr in row["frames"] if fr.get("position") != POS_PROCEDURE])
               for row in doc["句"]],
    }


def _keyed(stripped):
    """剝完的部分 → {區: {鍵: 值}}(依原序)。"""
    return {
        "值域": stripped["值域"],
        "目錄": {tuple(row["path"]): row for row in stripped["目錄"]},
        "統計位置": stripped["統計位置"],
        "卡面": {card: face for card, face in stripped["卡面"]},
        "句": {(row["card"], row["section"], row["index"]): row for row in stripped["句"]},
    }


def diff(base, cur):
    """兩份匯出文件 → 差異清單 [(區, 鍵, 基準值, 現值)](剝掉召喚手續後)。"""
    b_all, c_all = _keyed(strip(base)), _keyed(strip(cur))
    out = []
    for section in STRIPPED_SECTIONS:
        b, c = b_all[section], c_all[section]
        for key in list(b) + [k for k in c if k not in b]:
            b_value, c_value = b.get(key, MISSING), c.get(key, MISSING)
            if b_value != c_value:
                out.append((section, key, b_value, c_value))
    return out


def stripped_md5(doc):
    payload = json.dumps(strip(doc), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.md5(payload.encode("utf-8")).hexdigest()


def file_md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def digest_path(loc=DEFAULT):
    return os.path.join(loc.digest_dir, DIGEST_NAME)


def baseline_path(loc=DEFAULT):
    return os.path.join(loc.baseline_dir, os.path.basename(loc.export))


def freeze(loc=DEFAULT):
    """現行匯出檔凍結成基準:輸入檔與剝完的 md5 寫 export-digest.json,匯出檔複製到 baseline/。"""
    digest = {"inputs_md5": {os.path.basename(path): file_md5(path) for path in loc.inputs},
              "stripped_export_md5": stripped_md5(_load(loc.export))}
    with open(digest_path(loc), "w", encoding="utf-8", newline="\n") as f:
        json.dump(digest, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.makedirs(loc.baseline_dir, exist_ok=True)
    shutil.copyfile(loc.export, baseline_path(loc))
    return digest


def check_digest(loc=DEFAULT):
    """→ (ok|mismatch|skip, 說明)。skip:沒有 digest、匯出檔或輸入檔,或輸入變了(要重新凍結);
    mismatch:輸入沒變而剝完的匯出檔變了——既有框列、目錄格或統計位置被改了。"""
    for path in (digest_path(loc), loc.export) + tuple(loc.inputs):
        if not os.path.exists(path):
            return "skip", "沒有 %s(%s)" % (os.path.basename(path), path)
    digest = _load(digest_path(loc))
    for path in loc.inputs:
        name = os.path.basename(path)
        actual = file_md5(path)
        if actual != digest["inputs_md5"].get(name):
            return "skip", ("%s 變了(md5 %s,digest 記 %s):匯出檔守門這次略過;確認變化是輸入造成的之後 "
                            "python export_diff.py --freeze 重新凍結" % (name, actual, digest["inputs_md5"].get(name)))
    actual, expected = stripped_md5(_load(loc.export)), digest["stripped_export_md5"]
    if actual != expected:
        return "mismatch", "剝掉召喚手續後匯出檔的 md5 %s ≠ digest 記的 %s:既有的匯出內容被改了" % (actual, expected)
    return "ok", "剝掉召喚手續後匯出檔的 md5 與 digest 相同(%s)" % actual


def main(argv=None, loc=DEFAULT):
    parser = argparse.ArgumentParser(description="匯出檔剝掉召喚手續後與基準比對")
    parser.add_argument("--baseline", default=None, help="基準匯出檔(預設 baseline/action_frames.json)")
    parser.add_argument("--freeze", action="store_true", help="把現行匯出檔凍結成基準(確認差異是要的之後)")
    parser.add_argument("--limit", type=int, default=30, help="最多列幾處差異")
    args = parser.parse_args(argv)
    if args.freeze:
        digest = freeze(loc)
        print("已凍結匯出檔:剝完 %s → %s;基準檔 %s" % (
            digest["stripped_export_md5"], digest_path(loc), baseline_path(loc)))
        return 0
    status, message = check_digest(loc)
    print("digest 守門(匯出檔):%s——%s" % (status, message))
    base = args.baseline or baseline_path(loc)
    if not os.path.exists(base) or not os.path.exists(loc.export):
        print("沒有基準檔或匯出檔:%s(只有 digest 守門)" % base, file=sys.stderr)
        return 1 if status == "mismatch" else 0
    differences = diff(_load(base), _load(loc.export))
    for section, key, b, c in differences[:args.limit]:
        print("差異:%s %s:基準 %s → 現在 %s" % (section, key, json.dumps(b, ensure_ascii=False)[:300],
                                                json.dumps(c, ensure_ascii=False)[:300]))
    print("匯出檔比對:差異 %d 處(基準 %s)" % (len(differences), base))
    return 1 if differences or status == "mismatch" else 0


if __name__ == "__main__":
    sys.exit(main())
