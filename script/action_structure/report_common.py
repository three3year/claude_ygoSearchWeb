"""報告「附卡號、列全部」的共用規則(覆蓋報告與反向檢查報告):

- 卡號排序:整數照數值;不是整數的(產物格式壞掉)排在最後、照字面——仍列出,不丟。
- 原因、細項當標題:不是字串、空字串或含換行的(產物格式壞掉)照 repr 收成一類,
  報告列得出、標題不斷行,也不會因為 None 與字串混排而排不了序。
產物由 `card_structure.load_structures` 讀回時只補省略的格、不驗值,所以壞值會走到這裡;
報告的責任是把它列出來,不是把它藏起來(ADR-0008:把沉默的失效換成吵鬧的失效)。
"""


def card_order(cid):
    return (0, cid, "") if isinstance(cid, int) else (1, 0, str(cid))


def safe_label(label):
    if isinstance(label, str) and label and "\n" not in label:
        return label
    return f"(格式壞掉:{label!r})"
