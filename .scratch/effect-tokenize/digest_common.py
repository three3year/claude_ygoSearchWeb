"""digest 守門的共用件(summon-procedure code review):剝鍵比對 baseline_diff、下游基準 downstream_baseline、
匯出檔比對 export_diff 三道守門同形——凍結時記輸入檔的 md5 與「剝完的內容」的 md5;比對時輸入變了就略過(要重凍),
輸入沒變而內容 md5 不同就是既有值被改了。這裡放三者共用的算法與寫檔,各守門自己決定記哪些輸入、剝什麼、說明怎麼寫。

接縫:
- file_md5(path) → 檔案位元組的 md5。
- json_md5(obj) → 鍵排序、緊湊 JSON 的 md5(和檔案排版無關)。
- changed_input(inputs, recorded) → 第一個 md5 和凍結值不同的輸入 (名, 路徑, 現值, 凍結值);都沒變時 None。
  inputs 是 [(名, 路徑)],recorded 是 {名: md5}。
- write_digest(path, digest):digest 寫成縮排 2 的 JSON、LF 換行、檔尾換行。
"""
import hashlib
import json


def file_md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def json_md5(obj):
    payload = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.md5(payload.encode("utf-8")).hexdigest()


def changed_input(inputs, recorded):
    for name, path in inputs:
        actual = file_md5(path)
        if actual != recorded.get(name):
            return name, path, actual, recorded.get(name)
    return None


def write_digest(path, digest):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(digest, f, indent=2, ensure_ascii=False)
        f.write("\n")
