"""官方 Q&A 快取抽取管線:官方頁 HTML → 補足情報結構化資料。

接縫:extract_faq_info((cid, html) 序列[, cid→密碼對應]) → (entries, report)。
純函式,不碰網路與檔案系統。
"""
from html.parser import HTMLParser

# 兩個抽取目標區塊的 id;「補足情報」只應出現在這兩個區塊內
SECTION_IDS = ("card_info", "pen_info")
# 區塊內要捕捉的文字 div id → 輸出欄位名
TEXT_FIELDS = {
    "card_text": "card_text",
    "supplement": "supplement",
    "pen_effect": "pen_effect",
    "pen_supplement": "pen_supplement",
}
# 各區塊的補足情報日期欄位名
DATE_FIELD = {"card_info": "supplement_date", "pen_info": "pen_supplement_date"}
SUPPLEMENT_WORD = "補足情報"
NO_NAME_TITLE = "カードに関連するＱ＆Ａ"


class _FaqPageParser(HTMLParser):
    """單頁解析:捕捉 title、兩區塊內的文字欄位與補足日期,
    並記錄出現在區塊外的「補足情報」字樣。"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.fields = {}          # 欄位名 → 文字
        self.title = None
        self.outside_hits = []    # 區塊外「補足情報」的前後文
        self._section = None      # 目前所在區塊 id
        self._section_depth = 0   # 區塊內 div 巢狀深度
        self._capture = None      # 目前捕捉中的欄位名
        self._capture_depth = 0
        self._chunks = []
        self._in_title = False
        self._in_update_span = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "title":
            self._in_title = True
            self._chunks = []
            return
        if tag == "br":
            if self._capture is not None:
                self._chunks.append("\n")
            return
        if tag == "div":
            div_id = attrs.get("id", "")
            if self._capture is not None:
                self._capture_depth += 1
            elif self._section is not None:
                field = TEXT_FIELDS.get(div_id)
                if field is not None:
                    # 捕捉 div 的開閉由 _capture_depth 自己配對,
                    # 不計入 _section_depth
                    self._capture = field
                    self._capture_depth = 1
                    self._chunks = []
                else:
                    self._section_depth += 1
            elif div_id in SECTION_IDS:
                self._section = div_id
                self._section_depth = 1
            return
        if (tag == "span" and self._section is not None
                and "update" in attrs.get("class", "").split()):
            self._in_update_span = True
            self._chunks = []

    def handle_endtag(self, tag):
        if tag == "title":
            self.title = "".join(self._chunks).strip()
            self._in_title = False
            self._chunks = []
            return
        if tag == "span" and self._in_update_span:
            date = "".join(self._chunks).strip()
            if date and self._section is not None:
                self.fields.setdefault(DATE_FIELD[self._section], date)
            self._in_update_span = False
            self._chunks = []
            return
        if tag != "div":
            return
        if self._capture is not None:
            self._capture_depth -= 1
            if self._capture_depth == 0:
                text = "".join(self._chunks).strip()
                if text:
                    self.fields[self._capture] = text
                self._capture = None
                self._chunks = []
                return
        if self._section is not None and self._capture is None:
            self._section_depth -= 1
            if self._section_depth == 0:
                self._section = None

    def handle_data(self, data):
        if self._in_title or self._capture is not None or self._in_update_span:
            self._chunks.append(data)
        elif self._section is None and SUPPLEMENT_WORD in data:
            self.outside_hits.append(data.strip()[:80])

    def handle_comment(self, data):
        # 註解不會進 handle_data,場外檢查需另行涵蓋
        if self._section is None and SUPPLEMENT_WORD in data:
            self.outside_hits.append(data.strip()[:80])

    def name_ja(self):
        if not self.title:
            return None
        first = self.title.split(" | ")[0].strip()
        if not first or first == NO_NAME_TITLE:
            return None
        return first


def parse_faq_page(html):
    """解析單一官方 Q&A 頁,回傳 (fields, name_ja, outside_hits)。"""
    parser = _FaqPageParser()
    parser.feed(html)
    parser.close()
    return parser.fields, parser.name_ja(), parser.outside_hits


def extract_faq_info(pages, cid_to_password=None):
    """抽取官方 Q&A 快取。

    pages: iterable of (cid, html 字串)。
    回傳 (entries, report):entries 依 cid 升冪;無資料的欄位省略。
    """
    entries = []
    report = {
        "included": 0,
        "no_supplement": [],
        "pendulum": 0,
        "no_card_info": [],
        "outside_supplement": [],
    }
    if cid_to_password is not None:
        report["password_missing"] = []
    for cid, html in pages:
        fields, name_ja, outside = parse_faq_page(html)
        for context in outside:
            report["outside_supplement"].append(
                {"cid": cid, "context": context})
        if "card_text" not in fields:
            report["no_card_info"].append(cid)
            continue
        entry = {"cid": cid}
        if cid_to_password is not None:
            entry["password"] = cid_to_password.get(cid)
            if entry["password"] is None:
                report["password_missing"].append(cid)
        if name_ja:
            entry["name_ja"] = name_ja
        for key in ("card_text", "supplement", "supplement_date",
                    "pen_effect", "pen_supplement", "pen_supplement_date"):
            if key in fields:
                entry[key] = fields[key]
        if "supplement" not in entry:
            report["no_supplement"].append(cid)
        if "pen_effect" in entry:
            report["pendulum"] += 1
        entries.append(entry)
        report["included"] += 1
    entries.sort(key=lambda e: e["cid"])
    report["no_supplement"].sort()
    report["no_card_info"].sort()
    return entries, report
