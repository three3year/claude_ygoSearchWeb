"""拆句判準的交叉驗證器:一條新判準會不會把官方 `『原文』` 引用切開?

[[拆句表]]的驗證二只驗**已經寫進表裡**的拆點,擋不住「一條寫太寬的判準」——那條
判準要等它真的拆錯了才會被發現,而那時錯誤資料已經在表裡。這支程式反過來:拿一條
**還沒用**的判準,在全部未拆整團上假設照它切,看有沒有任何官方引用橫跨拆點。
判準要先過這一關才寫進 `docs/effect_kind_guide.md` §8——與票06 歸納效果類型規則時
「先拿整份[[官方明示]]驗證過才寫進去」同一個要求。

判準以正則表示**拆點落在哪裡**:比對整團的日文原文,每一個 match 的起點就是一個
拆點。用 `(?=…)` 之類的零寬斷言把 match 對準切割位置。

用法:
    # 票13 判準13:尾端以卡名指稱全卡效果的次數限制句獨立成段
    python script/tag_card/check_split_rule.py \\
        "(?=(?:「[^」]+」|このカード名)[^。]*?(?:効果|発動)[^。]*?しか(?:使用|発動)できない。\\s*$)" \\
        --not-matching "この効果|この方法"

`--not-matching` 是判準的例外條款:命中它的那一句不切(例:`「聖騎士ガラハド」の
**この効果**は１ターンに１度しか使用できない` 講的是那一個效果,不是全卡)。
"""
import argparse
import re
import sys

import official
from store import (DEFAULT_CARDS, DEFAULT_FAQ_INFO, DEFAULT_SPLITS,
                   DEFAULT_TAG_CARDS, load_json, load_optional)
from tagcard import SECTION_PENDULUM, build_tag_cards


def cut_points(text, rule, exception):
    """判準在這一團上切在哪些位置;0 與 len(text) 不算(那不是拆點)。"""
    points = []
    for match in rule.finditer(text):
        at = match.start()
        if at <= 0 or at >= len(text):
            continue
        # 例外條款只看**被切下來的那一句**(到下一個句號為止),不是整段後文
        sentence = text[at:].split("。", 1)[0]
        if exception is not None and exception.search(sentence):
            continue
        points.append(at)
    return points


def violations(blob, supplement, points):
    """橫跨任何一個拆點的官方引用。比對前先正規化,與管線的驗證二同一套。"""
    body = official.normalise(blob)
    cuts = [len(official.normalise(blob[:at])) for at in points]
    cut = []
    for quote in official.quotes(supplement):
        needle = official.normalise(quote)
        if not needle:
            continue
        at = body.find(needle)
        if at < 0:
            continue
        if any(at < point < at + len(needle) for point in cuts):
            cut.append(quote)
    return cut


def main(argv=None):
    parser = argparse.ArgumentParser(description="拆句判準的官方引用交叉驗證")
    parser.add_argument("rule", help="判準:每個 match 的起點就是一個拆點")
    parser.add_argument("--not-matching",
                        help="例外條款:拆點之後的文字命中它就不切")
    parser.add_argument("--cards", default=DEFAULT_CARDS)
    parser.add_argument("--faq-info", default=DEFAULT_FAQ_INFO)
    parser.add_argument("--sheet", default=DEFAULT_TAG_CARDS)
    parser.add_argument("--splits", default=DEFAULT_SPLITS)
    args = parser.parse_args(argv)

    rule = re.compile(args.rule)
    exception = (re.compile(args.not_matching) if args.not_matching else None)
    faqs = load_json(args.faq_info)
    _entries, report = build_tag_cards(
        load_json(args.cards), faqs,
        existing=load_optional(args.sheet),
        splits=load_optional(args.splits))
    by_id = {entry["password"]: entry for entry in faqs
             if entry.get("password")}

    fires = quoted = broken = 0
    for row in report["pending_split"]:
        points = cut_points(row["text_ja"], rule, exception)
        if not points:
            continue
        fires += 1
        faq = by_id.get(row["id"], {})
        supplement = (faq.get("pen_supplement")
                      if row["section"] == SECTION_PENDULUM
                      else faq.get("supplement")) or ""
        cut = violations(row["text_ja"], supplement, points)
        if official.quotes(supplement):
            quoted += 1
        if cut:
            broken += 1
            print(f"  引用被切開 id={row['id']} section={row['section']}")
            for quote in cut:
                print(f"    『{quote[:60]}』")
    print(f"未拆整團 {len(report['pending_split'])} 段;判準開火 {fires} 段"
          f"(其中 {quoted} 段的補足情報有 『原文』 引用可驗);"
          f"引用被切開 {broken} 段")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
