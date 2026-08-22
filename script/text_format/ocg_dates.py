"""OCG 首發日來源的消費端:以卡片密碼對齊卡片總表,異圖歸主卡。

來源檔 data/sources/ocg-dates.json 由 update_cards.py 下載(YGOPRODeck 全量
dump 的 misc_info.ocg_date),存原始樣貌;對齊在這裡做,與 genesys/禁限的
消費慣例一致(主卡沒對到時試異圖密碼)。首發日只服務三級分類報表與稽核
排序,不進前端索引、不做搜尋軸。
"""
import json


def load_ocg_dates(path):
    """讀來源檔 {密碼字串: 首發日字串} → {int 密碼: 首發日字串}。"""
    with open(path, encoding="utf-8") as f:
        return {int(k): v for k, v in json.load(f).items()}


def align_ocg_dates(cards, dates):
    """對齊卡片總表 → {主卡密碼: 首發日或 None}。

    每張主卡一筆:主卡密碼先對,沒對到時試異圖密碼(異圖歸主卡);
    都查無日期記 None——可辨識、不硬猜,報表端歸「日期不明」。
    """
    aligned = {}
    for card in cards:
        value = dates.get(card["id"])
        if value is None:
            for alt in card["alt_ids"]:
                value = dates.get(alt)
                if value is not None:
                    break
        aligned[card["id"]] = value
    return aligned
