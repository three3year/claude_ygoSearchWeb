"""官方 DB 頁面(Q&A/卡片頁)與 ygoprodeck 的網路存取(重爬/補爬薄殼共用)。

只負責取得位元組,不做解析。有禮貌的請求間隔由 sleep_between 統一。
"""
import json
import ssl
import time
import urllib.request

FAQ_URL = ("https://www.db.yugioh-card.com/yugiohdb/faq_search.action"
           "?ope=4&cid={cid}&request_locale=ja")
# 卡片頁(収録シリーズ後備日期用):必須 ja locale——英文頁同區塊是 TCG 發售日
CARD_URL = ("https://www.db.yugioh-card.com/yugiohdb/card_search.action"
            "?ope=2&cid={cid}&request_locale=ja")
# 官方站對預設的 Python UA 會擋,沿用瀏覽器 UA。
FAQ_USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/126.0 Safari/537.36")

# 完整 dump:misc=yes 才會帶 misc_info.konami_id
YGOPRO_DUMP_URL = "https://db.ygoprodeck.com/api/v7/cardinfo.php?misc=yes"
YGOPRO_USER_AGENT = "ygoSearchWeb/1.0"


def fetch_faq_page(cid, timeout=30):
    """抓取單一官方 Q&A 頁,回傳 HTML 字串。"""
    req = urllib.request.Request(
        FAQ_URL.format(cid=cid), headers={"User-Agent": FAQ_USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8")


def fetch_card_page(cid, timeout=30):
    """抓取單一官方卡片頁(日文),回傳 HTML 字串。"""
    req = urllib.request.Request(
        CARD_URL.format(cid=cid), headers={"User-Agent": FAQ_USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8")


def fetch_ygopro_dump(timeout=300):
    """抓取 ygoprodeck 完整 dump,回傳已解析的 dict。"""
    ctx = ssl.create_default_context()
    req = urllib.request.Request(
        YGOPRO_DUMP_URL, headers={"User-Agent": YGOPRO_USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        return json.loads(resp.read())


def sleep_between(index, delay):
    """第一筆不等待,其餘每筆之前等 delay 秒。"""
    if index:
        time.sleep(delay)
