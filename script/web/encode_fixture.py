"""參考評估器夾具 → 編碼夾具(predicate-index 票 03,規格 Testing Decisions「夾具」)。

接縫:`encoded_fixture(夾具, 值域) → 編碼夾具`,純函式,編碼用建置的同一支(`frameindex`);薄殼寫檔。
參考評估器的夾具是匯出形狀,JS 評估器讀編碼形狀,node 測試讀這份、經 `Engine.runQuery` 跑。

編碼夾具的欄位(其餘原樣照抄,期望值只有夾具一個來源):
    vocab       VOCAB.frame 形狀的表:lemmas、heads、domains。詞元與中心詞表是夾具全部框列算的,不是真語料的
    框列        名 → 框元組
    張數.句[]   frames 換成框元組清單,其餘鍵原樣

值域讀匯出檔的「值域」:`script/web` 不 import 分詞鏈(規格「封閉類的值域放哪?」(a))。
"""
import json
import os

from frameindex import encode_frame, frame_tables

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
CHAIN_DIR = os.path.join(ROOT, ".scratch", "effect-tokenize")
DEFAULT_SOURCE = os.path.join(CHAIN_DIR, "predicate-fixture.json")
DEFAULT_EXPORT = os.path.join(ROOT, "data", "action_frames.json")
DEFAULT_OUT = os.path.join(HERE, "predicate-fixture-encoded.json")


def encoded_fixture(fixture, domains):
    block = fixture["張數"]
    tables = frame_tables([*fixture["框列"].values(), *(row for line in block["句"] for row in line["frames"])], domains)
    return {
        "說明": "由 python script/web/encode_fixture.py 產生,不手改;來源 .scratch/effect-tokenize/predicate-fixture.json。",
        "版本": fixture["版本"],
        "vocab": {"lemmas": tables.lemmas, "heads": tables.heads, "domains": domains},
        "框列": {name: encode_frame(row, tables) for name, row in fixture["框列"].items()},
        "例子": fixture["例子"],
        "雜湊": fixture["雜湊"],
        "張數": {"句": [{**line, "frames": [encode_frame(row, tables) for row in line["frames"]]}
                        for line in block["句"]],
                 "例子": block["例子"]},
    }


def main():
    with open(DEFAULT_SOURCE, encoding="utf-8") as f:
        fixture = json.load(f)
    with open(DEFAULT_EXPORT, encoding="utf-8") as f:
        domains = json.load(f)["值域"]
    with open(DEFAULT_OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(encoded_fixture(fixture, domains), f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("已寫出", DEFAULT_OUT)


if __name__ == "__main__":
    main()
