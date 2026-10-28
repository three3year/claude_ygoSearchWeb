# -*- coding: utf-8 -*-
"""LLM 檢驗(票 09/10/15):分層抽樣固定一批卡、切批給子代理「看原文與框架挑錯」,
再把各批回報彙整成錯誤類型報告。

兩種抽樣:
- 全語料(票 09;round1〜4):依卡種與效果數分層——單效果怪獸 100、多效果怪獸 100、
  魔陷 70、靈擺 30,切 8 批。
- 受影響卡(票 15;round5 起):● 合併(ADR-0015)影響到的卡——有子效果句的卡加上
  含未拆 ● 的卡;依領起句家族分層(賦予型/發動時選/處理時選/適用/依條件發動/其他/
  未拆●),抽 100 張、切 4 批。
- 第二版論元(frame-args-v2 票 05;v2-round1 起):受列舉/か 並列/回填/回合階段四型規則影響
  的卡——依框架資料分層(純列舉/か並列/選ぶ鏈/回合階段,一張卡依序歸入第一個符合的層),
  各抽 25 張、切 4 批;錯誤類型在既有五類外加 列舉掛錯/漏、連接群組錯、回填錯、回合條件錯。
- 第三版論元(frame-args-v3 票 07;v3-round1 起):受區域切分/並列多區域/推得/主題延續/主語/被動
  受事者/回填轉欄七型規則影響的卡——依框架資料分層(一張卡依序歸入第一個符合的層),共 100 張、
  切 4 批;錯誤類型在既有五類外加 區域切錯/漏切、推得錯、主題/主語錯、延續錯、回填錯。
- 動作詞元統一(frame-lemma-unify 票 06;lemma-round1):受寫法歸一/攻撃宣言・直接攻撃/補語不併/
  態歸一/態欄五型影響的卡——依框架資料分層(一張卡依序歸入第一個符合的層),共 100 張、切 4 批;
  錯誤類型在既有五類外加 詞元錯、態錯、補語錯欄;批次檔的框架列多「態=」。
- 動作類別(action-categories 票 07;category-round1 起):單位是動作框架、不是卡——依類別樹的
  樹序每葉從帶該葉、還沒被抽過的已歸框架抽 5 個(不足全取),未歸框架另抽 50 個;樣本依框架的
  詞元節點分組(節點的葉清單列一次)連續切 8 批,沒有節點的未歸框架輪流分到各批末尾,另寫
  tree.md(整棵樹)。批次檔的歸組讀當下的框架類別檔(先跑 categories.py;複檢時是修後的歸組)。
  錯誤三類 歸錯葉/該歸未歸/葉定義有問題,另記成因 規則/樹 或 框架抽取。
種子固定,同一種子重抽得到同一批(複檢沿用);不同種子抽新樣本(過擬合抽驗)。

    sample   --round R --seed S   全語料抽樣:寫 llm-check/round<R>/sample.json 與 batch-<k>.md
    affected --round R --seed S   受影響卡抽樣(同上,另寫 meta.json 記分層與批數)
    v2       --round R --seed S   第二版論元受影響卡抽樣(寫 llm-check/v2-round<R>/)
    v3       --round R --seed S   第三版論元受影響卡抽樣(寫 llm-check/v3-round<R>/)
    lemma    --round R --seed S   動作詞元統一受影響卡抽樣(寫 llm-check/lemma-round<R>/)
    categories --round R --seed S 動作類別依葉分層抽框架(寫 llm-check/category-round<R>/)
    report   --round R            讀 llm-check/round<R>/findings-<k>.json 寫 report.md
    recheck  --round R --from R0  用 round R0 的樣本重出批次檔(同批複檢)
    (report/recheck 加 --line constraints、v2、v3、lemma 或 categories 走各自的目錄)

批次檔一張卡一節、一句效果句一段:整段效果句(含 ● 選項;拆開的領起句與子效果句
各標 index 與效果類型)與它的框架(含選項欄「●n 標籤」)。

子代理回報格式(findings-<k>.json):[{"card": 卡號, "index": "①", "frame": 框架序或 null,
"type": 錯誤類型, "reason": 理由, "merge_related": true/false}];錯誤類型固定五種:
漏抽動作/論元抽錯/位置判錯/極性判錯/多抽(不是動作);merge_related 標這筆是否和
● 合併有關(round5 起)。動作類別的回報一筆指一個樣本:{"sample": 樣本號, "type": 錯誤類型,
"expected": [該歸的葉], "cause": 成因, "reason": 理由}。
"""
import argparse
import json
import os
import random
import re
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import constraints  # noqa: E402
import action_lemmas  # noqa: E402
import categories  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
CARDS = os.path.join(ROOT, "data", "cards.json")
TOKENS = os.path.join(HERE, "tokens.json")
FRAMES = os.path.join(HERE, "frames.json")
FRAME_CATEGORIES = os.path.join(HERE, "frame_categories.json")
CHECK_DIR = os.path.join(HERE, "llm-check")

QUOTA = {"mono": 100, "multi": 100, "st": 70, "pendulum": 30}
STRATUM_LABEL = {"mono": "單效果怪獸", "multi": "多效果怪獸", "st": "魔陷",
                 "pendulum": "靈擺"}
BATCHES = 8
# 受影響卡(票 15):領起句家族 → 配額(合計 100);某家族不足額時缺口補給 未拆●
FAMILIES = ("賦予型", "發動時選", "處理時選", "適用", "依條件發動", "其他", "未拆●")
QUOTA_AFFECTED = {"賦予型": 22, "發動時選": 18, "處理時選": 8, "適用": 15,
                  "依條件發動": 8, "其他": 4, "未拆●": 25}
BATCHES_AFFECTED = 4
ERROR_TYPES = ("漏抽動作", "論元抽錯", "位置判錯", "極性判錯", "多抽(不是動作)")
# 約束框架(票 07):分層 → 配額(合計 300;一張卡依序歸入第一個符合的層)
STRATA_CONSTRAINT = ("事件回合禁用", "誓約", "召喚條件", "素材", "時機", "發動句內次數",
                     "只有註記次數")
QUOTA_CONSTRAINT = {"事件回合禁用": 20, "誓約": 50, "召喚條件": 50, "素材": 40, "時機": 60,
                    "發動句內次數": 50, "只有註記次數": 30}
BATCHES_CONSTRAINT = 8
ERROR_TYPES_CONSTRAINT = ("漏認約束", "誤認約束", "類別/子類判錯", "欄位抽錯", "取代錯誤",
                          "次數歸屬判錯")
# 第二版論元(frame-args-v2 票 05):四型分層各 25 張;錯誤類型五類+四類
STRATA_V2 = ("純列舉", "か並列", "選ぶ鏈", "回合階段")
QUOTA_V2 = {k: 25 for k in STRATA_V2}
BATCHES_V2 = 4
ERROR_TYPES_V2 = ERROR_TYPES + ("列舉掛錯/漏", "連接群組錯", "回填錯", "回合條件錯")
# 第三版論元(frame-args-v3 票 07):七型分層(依序歸入第一個符合的層;較少見的型在前),合計 100
STRATA_V3 = ("回填轉欄", "並列多區域", "被動受事者", "主題延續", "區域切分", "主語", "推得")
QUOTA_V3 = {"回填轉欄": 14, "並列多區域": 14, "被動受事者": 14, "主題延續": 14, "區域切分": 16,
            "主語": 14, "推得": 14}
BATCHES_V3 = 4
ERROR_TYPES_V3 = ERROR_TYPES + ("區域切錯/漏切", "推得錯", "主題/主語錯", "延續錯", "回填錯")
# 動作詞元統一(frame-lemma-unify 票 06):五型分層(依序歸入第一個符合的層;較少見的型在前),
# 合計 100;錯誤類型五類+三類
STRATA_LEMMA = ("寫法歸一", "攻撃宣言/直接攻撃", "補語不併", "態歸一", "態欄")
QUOTA_LEMMA = {"寫法歸一": 20, "攻撃宣言/直接攻撃": 20, "補語不併": 20, "態歸一": 25, "態欄": 15}
BATCHES_LEMMA = 4
ERROR_TYPES_LEMMA = ERROR_TYPES + ("詞元錯", "態錯", "補語錯欄")
# 寫法歸一:全名與分詞殘片(子句字面裡看得到)→ 縮寫的詞元字首,取自 action_lemmas 的對照表
FULL_SPELLINGS = tuple(action_lemmas.SPELLING) + tuple(
    full for full, _short in action_lemmas.SPELLING_PREFIXES) + ("そのX素材",)
SHORT_SPELLINGS = tuple(action_lemmas.SPELLING.values()) + tuple(
    short for _full, short in action_lemmas.SPELLING_PREFIXES) + ("X素材",)
# 併進 アップ/ダウン 的詞對(上げる/上がる…)在子句字面裡的詞幹
RAISE_LOWER = tuple(raw[:-1] for raw, (canonical, _voice) in action_lemmas.VOICE_PAIRS.items()
                    if canonical in action_lemmas.PARTICLE_VOICED)
# 動作類別(action-categories 票 07):依葉分層抽框架——每葉 5 個(不足全取)、未歸另抽 50 個,
# 切 8 批;錯誤三類,另記成因(歸組規則或樹/框架抽取的錯連帶歸錯)
PER_LEAF = 5
UNPLACED_QUOTA = 50
STRATUM_UNPLACED = "(未歸類)"
BATCHES_CATEGORY = 8
ERROR_TYPES_CATEGORY = ("歸錯葉", "該歸未歸", "葉定義有問題")
CATEGORY_CAUSES = ("規則/樹", "框架抽取")
TYPE_PENDULUM, TYPE_SPELL, TYPE_TRAP = 0x1000000, 0x2, 0x4
OPTION = "●"


def load():
    with open(CARDS, encoding="utf-8") as f:
        cards = {c["id"]: c for c in json.load(f)}
    with open(TOKENS, encoding="utf-8") as f:
        tokens = json.load(f)
    with open(FRAMES, encoding="utf-8") as f:
        frames = json.load(f)
    return cards, tokens, frames


def stratum_of(card, effect_count):
    t = card["type"]
    if t & TYPE_PENDULUM:
        return "pendulum"
    if t & (TYPE_SPELL | TYPE_TRAP):
        return "st"
    return "mono" if effect_count <= 1 else "multi"


def sample(seed):
    cards, tokens, _ = load()
    effect_count = Counter(s["card"] for s in tokens if s["stratum"] == "effect")
    pools = defaultdict(list)
    for cid in sorted({s["card"] for s in tokens}):
        pools[stratum_of(cards[cid], effect_count[cid])].append(cid)
    rng = random.Random(seed)
    picked = []
    for key in ("mono", "multi", "st", "pendulum"):
        chosen = sorted(rng.sample(pools[key], QUOTA[key]))
        picked += [{"card": cid, "stratum": key} for cid in chosen]
    return picked


# ── 受影響卡(票 15)──

def family_of(lead_text):
    """領起句(第一個 ● 之前的文字)→ 領起句家族。順序:賦予型 → 發動時選 → 處理時選
    → 適用 → 依條件發動 → 其他。"""
    t = lead_text
    if "効果を得る" in t or "効果を持つ" in t:
        return "賦予型"
    if re.search(r"(選択|選ん)で?(して)?発動", t):
        return "發動時選"
    if re.search(r"選択|選ん|選び", t):
        return "處理時選"
    if "適用" in t:
        return "適用"
    if "発動できる" in t or "発動する" in t:
        return "依條件發動"
    return "其他"


def affected_pools(tokens):
    """{家族: [卡號]}:有子效果句的卡依它第一句含子效果句的效果句分家族;只含
    未拆 ● 的卡歸 未拆●。"""
    family_by_card = {}
    unsplit_cards = set()
    for s in tokens:
        if len(s["parts"]) > 1:
            if s["card"] not in family_by_card:
                lead = s["text_ja"][:s["parts"][1]["start"]]
                family_by_card[s["card"]] = family_of(lead)
        elif OPTION in s["tokens"]:
            unsplit_cards.add(s["card"])
    pools = defaultdict(list)
    for cid, fam in family_by_card.items():
        pools[fam].append(cid)
    for cid in unsplit_cards - set(family_by_card):
        pools["未拆●"].append(cid)
    return {k: sorted(v) for k, v in pools.items()}


def sample_affected(seed):
    _cards, tokens, _ = load()
    pools = affected_pools(tokens)
    rng = random.Random(seed)
    quota = dict(QUOTA_AFFECTED)
    short = sum(max(0, quota[k] - len(pools.get(k, []))) for k in FAMILIES)
    quota["未拆●"] += short                   # 不足額的家族,缺口補給 未拆●
    picked = []
    for key in FAMILIES:
        pool = pools.get(key, [])
        chosen = sorted(rng.sample(pool, min(quota[key], len(pool))))
        picked += [{"card": cid, "stratum": key} for cid in chosen]
    print("母體:" + "、".join("%s %d" % (k, len(pools.get(k, []))) for k in FAMILIES))
    return picked


# ── 約束框架(票 07)──

def constraint_stratum(records):
    """一張卡的框架紀錄 → 約束框架分層(依 STRATA_CONSTRAINT 順序取第一個符合的;
    沒有任何約束框架回 None)。發動句內次數=效果句裡對象是 この効果 的次數框架;
    只有註記次數=只有前言段註記那種次數框架。"""
    labels = set()
    for r in records:
        for f in r["frames"]:
            if f.get("kind") != constraints.KIND_CONSTRAINT:
                continue
            if f["subtype"] == constraints.SUB_COUNT:
                labels.add("發動句內次數" if f["target"] == constraints.THIS_EFFECT
                           else "只有註記次數")
            else:
                labels.add(f["subtype"] or f["category"])
    return next((k for k in STRATA_CONSTRAINT if k in labels), None)


def sample_constraints(seed):
    _cards, _tokens, frames = load()
    by_card = defaultdict(list)
    for r in frames:
        by_card[r["card"]].append(r)
    pools = defaultdict(list)
    for cid in sorted(by_card):
        stratum = constraint_stratum(by_card[cid])
        if stratum:
            pools[stratum].append(cid)
    rng = random.Random(seed)
    picked = []
    for key in STRATA_CONSTRAINT:
        pool = pools.get(key, [])
        chosen = sorted(rng.sample(pool, min(QUOTA_CONSTRAINT[key], len(pool))))
        picked += [{"card": cid, "stratum": key} for cid in chosen]
    print("母體:" + "、".join("%s %d" % (k, len(pools.get(k, [])))
                            for k in STRATA_CONSTRAINT))
    return picked


# ── 第二版論元(票 05)──

def v2_stratum(records):
    """一張卡的框架紀錄 → 第二版論元分層(依 STRATA_V2 順序取第一個符合的):純列舉=有框架
    帶列舉欄;か並列=有框架帶群組;選ぶ鏈=有框架帶回填(且不在 か 群組);回合階段=有框架帶
    回合條件;都沒有回 None。"""
    labels = set()
    for r in records:
        for f in r["frames"]:
            if f.get("enumeration"):
                labels.add("純列舉")
            if f.get("group") is not None:
                labels.add("か並列")
            if f.get("backfill") and f.get("group") is None:
                labels.add("選ぶ鏈")
            if f.get("turn"):
                labels.add("回合階段")
    return next((k for k in STRATA_V2 if k in labels), None)


def sample_by_frames(seed, stratum_of_records, strata, quota):
    """依框架資料分層抽樣(第二、三版論元共用):一張卡的框架紀錄 → 分層(None 不入母體),
    各層依配額以固定種子抽。"""
    _cards, _tokens, frames = load()
    by_card = defaultdict(list)
    for r in frames:
        by_card[r["card"]].append(r)
    pools = defaultdict(list)
    for cid in sorted(by_card):
        stratum = stratum_of_records(by_card[cid])
        if stratum:
            pools[stratum].append(cid)
    rng = random.Random(seed)
    picked = []
    for key in strata:
        pool = pools.get(key, [])
        chosen = sorted(rng.sample(pool, min(quota[key], len(pool))))
        picked += [{"card": cid, "stratum": key} for cid in chosen]
    print("母體:" + "、".join("%s %d" % (k, len(pools.get(k, []))) for k in strata))
    return picked


def sample_v2(seed):
    return sample_by_frames(seed, v2_stratum, STRATA_V2, QUOTA_V2)


# ── 第三版論元(票 07)──

def cut_region(f):
    """框架的來源/所在是不是從受事者片語切出來的(不是原文 から、不是推得或回填)→ 欄名或 None。"""
    marked = set(f.get("inferred") or ()) | set(f.get("backfill") or ())
    if f.get("place") and "place" not in marked:
        return "place"
    clause = f["clause"].replace(" ", "")
    if f.get("source") and "source" not in marked and f["source"] + "から" not in clause:
        return "source"
    return None


def v3_labels(f):
    """一個動作框架命中的第三版論元型。"""
    labels = set()
    backfill = f.get("backfill") or []
    if "place" in backfill or "source" in backfill:
        labels.add("回填轉欄")
    if "topic" in backfill:
        labels.add("主題延續")
    region = cut_region(f)
    if region:
        labels.add("並列多區域" if "・" in f[region] and any(
            c in (f.get("object") or "") for c in ("と", "か", "及び", "または")) else "區域切分")
        if f.get("voice") == action_lemmas.VOICE_PASSIVE:
            labels.add("被動受事者")
    if f.get("subject"):
        labels.add("主語")
    if f.get("inferred"):
        labels.add("推得")
    return labels


def v3_stratum(records):
    labels = set()
    for r in records:
        for f in r["frames"]:
            if f.get("kind") == constraints.KIND_ACTION:
                labels |= v3_labels(f)
    return next((k for k in STRATA_V3 if k in labels), None)


def sample_v3(seed):
    return sample_by_frames(seed, v3_stratum, STRATA_V3, QUOTA_V3)


# ── 動作詞元統一(frame-lemma-unify 票 06)──

_VALUE_ENDINGS = []


def value_endings():
    """補語不併判準的字尾:封閉值域字面(lexicon 的 closed 類)與屬性名詞;第一次用到時讀詞典。"""
    if not _VALUE_ENDINGS:
        with open(os.path.join(HERE, "lexicon.json"), encoding="utf-8") as f:
            _VALUE_ENDINGS.extend(e["surface"] for e in json.load(f)
                                  if e.get("closed") in action_lemmas.COMPLEMENT_VALUE_CLASSES)
        _VALUE_ENDINGS.extend(action_lemmas.COMPLEMENT_ATTRIBUTES)
    return tuple(_VALUE_ENDINGS)


def lemma_labels(f):
    """一個動作框架命中的動作詞元統一型(子句字面看原文寫法,框架欄位看正規化後的值)。"""
    labels = set()
    clause = f["clause"].replace(" ", "")
    action, voice = f["action"], f.get("voice")
    if any(s in clause for s in FULL_SPELLINGS) and action.startswith(SHORT_SPELLINGS):
        labels.add("寫法歸一")
    if action == "直接攻撃" or (action == "攻撃宣言" and "攻撃宣言時" not in clause):
        labels.add("攻撃宣言/直接攻撃")
    if action in ("にする", "とする") and (f.get("goal") or "").endswith(value_endings()):
        labels.add("補語不併")
    if (voice == action_lemmas.VOICE_INTRANSITIVE
            or (action == "無効にする" and voice == action_lemmas.VOICE_PASSIVE)
            or (action in action_lemmas.PARTICLE_VOICED
                and any(s in clause for s in RAISE_LOWER))):
        labels.add("態歸一")
    if voice in (action_lemmas.VOICE_ACTIVE, action_lemmas.VOICE_PASSIVE):
        labels.add("態欄")
    return labels


def lemma_stratum(records):
    labels = set()
    for r in records:
        for f in r["frames"]:
            if f.get("kind") == constraints.KIND_ACTION:
                labels |= lemma_labels(f)
    return next((k for k in STRATA_LEMMA if k in labels), None)


def sample_lemma(seed):
    return sample_by_frames(seed, lemma_stratum, STRATA_LEMMA, QUOTA_LEMMA)


# ── 批次檔 ──

def sentence_label(s):
    """效果句的標籤(批次檔「### 句」後的寫法):靈擺段加前綴、效果外文本標明。"""
    return ("靈擺 " if s["section"] == "pendulum" else "") + (
        "效果外文本 " + s["index"] if s["stratum"] == "extra" else s["index"])


def sentence_lines(s):
    """效果句的原文:拆開的 ● 子效果句各段標 index・效果類型,否則整句一行。"""
    if len(s["parts"]) <= 1:
        return ["原文:%s" % s["text_ja"].replace("\n", " ")]
    lines = ["原文(效果句含 %d 個 ● 子效果句,各段的效果類型如標):" % (len(s["parts"]) - 1)]
    for p in s["parts"]:
        lines.append("  [%s・%s] %s" % (
            p["index"], p["kind"], s["text_ja"][p["start"]:p["end"]].replace("\n", " ")))
    return lines


def frame_line(k, f):
    """一個框架 → 批次檔的一列(動作框架列出位置、極性・態、論元欄、內容、選項與子句)。"""
    opt = ""
    if f.get("option") is not None:
        opt = " | 選項=●%d%s" % (f["option"], " " + f["label"] if f.get("label") else "")
    if f.get("kind") == constraints.KIND_CONSTRAINT:
        return "框架 %d:[約束 %s] %s%s | 子句=%s" % (
            k, constraints.label_of(f), constraints.describe(f), opt, f["clause"])
    extra = constraints.describe_action(f)
    return "框架 %d:[%s] %s(%s%s)| %s%s%s | 子句=%s" % (
        k, f["position"], f["action"], f["polarity"],
        "・態=" + f["voice"] if f.get("voice") else "",
        " | ".join(argument_cells(f)), " | " + extra if extra else "", opt, f["clause"])


def record_lines(s, fr):
    """一句效果句 → 批次檔的一段:整段原文(拆開的各段標 index・效果類型)+ 框架。"""
    lines = ["### 句 %s" % sentence_label(s)] + sentence_lines(s)
    if not fr:
        lines.append("框架:(無)")
    lines += [frame_line(k, f) for k, f in enumerate(fr, 1)]
    lines.append("")
    return lines


# 動作框架的論元欄(批次檔的顯示順序;frame-args-v3 起多主題/主語/所在)
ARGUMENT_CELLS = (("topic", "主題"), ("subject", "主語"), ("object", "對象"), ("source", "來源"),
                  ("place", "所在"), ("goal", "目的"))


def argument_cells(f):
    """動作框架 → 「欄=值」清單;回填的格標「(回填)」、推得的格標「(推得)」——子代理回報時
    分「抽錯」「回填錯/延續錯」「推得錯」。主題/主語/所在沒有值時不列。"""
    backfill, inferred = f.get("backfill") or [], f.get("inferred") or []
    cells = []
    for key, label in ARGUMENT_CELLS:
        if not f.get(key) and key in ("topic", "subject", "place"):
            continue
        mark = "(回填)" if key in backfill else "(推得)" if key in inferred else ""
        cells.append("%s=%s%s" % (label, f.get(key) or "", mark))
    return cells


def card_block(cid, cards, recs, frames_by_key):
    c = cards[cid]
    lines = ["## 卡 %d %s(%s)" % (cid, c["name_ja"], c["name_zh"]), ""]
    for s in recs:
        lines += record_lines(s, frames_by_key[(s["card"], s["section"], s["index"])])
    return lines


def write_batches(round_dir, picked, meta):
    cards, tokens, frames = load()
    frames_by_key = {(r["card"], r["section"], r["index"]): r["frames"]
                     for r in frames}
    recs_by_card = defaultdict(list)
    for s in tokens:
        recs_by_card[s["card"]].append(s)
    write_sample_meta(round_dir, picked, meta)
    # 輪流分配:每批混合各分層(連續切會一批幾乎同一分層)
    batches = meta["batches"]
    for k in range(batches):
        chunk = picked[k::batches]
        lines = ["# 批次 %d(%d 張卡)" % (k, len(chunk)), ""]
        for p in chunk:
            lines += card_block(p["card"], cards, recs_by_card[p["card"]],
                                frames_by_key)
        with open(os.path.join(round_dir, "batch-%d.md" % k), "w",
                  encoding="utf-8", newline="\n") as f:
            f.write("\n".join(lines))
        print("written batch-%d.md (%d cards)" % (k, len(chunk)))


def write_sample_meta(round_dir, picked, meta):
    """樣本清單與抽樣設定寫進該輪目錄(複檢與報告都從這兩份讀)。"""
    os.makedirs(round_dir, exist_ok=True)
    for name, data, indent in (("sample.json", picked, 0), ("meta.json", meta, 1)):
        with open(os.path.join(round_dir, name), "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, ensure_ascii=False, indent=indent)
            f.write("\n")


def load_findings(round_dir, batches):
    """各批的 findings-<k>.json 合起來(每筆記批號);缺的批印出來、略過。"""
    findings = []
    for k in range(batches):
        path = os.path.join(round_dir, "findings-%d.json" % k)
        if not os.path.exists(path):
            print("missing", path)
            continue
        with open(path, encoding="utf-8") as f:
            for item in json.load(f):
                item["batch"] = k
                findings.append(item)
    return findings


def read_meta(round_dir):
    path = os.path.join(round_dir, "meta.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {"mode": "sample", "batches": BATCHES, "strata": list(QUOTA)}


def round_dir_of(line, round_no):
    prefix = {"constraints": "constraint-round", "v2": "v2-round", "v3": "v3-round",
              "lemma": "lemma-round", "categories": "category-round"}.get(line, "round")
    return os.path.join(CHECK_DIR, "%s%d" % (prefix, round_no))


# ── 報告 ──

def report(round_dir):
    meta = read_meta(round_dir)
    findings = load_findings(round_dir, meta["batches"])
    with open(os.path.join(round_dir, "sample.json"), encoding="utf-8") as f:
        picked = json.load(f)
    strata = meta["strata"]
    error_types = tuple(meta.get("error_types", ERROR_TYPES))
    label = {k: STRATUM_LABEL.get(k, k) for k in strata}
    stratum_of_card = {p["card"]: p["stratum"] for p in picked}
    quota = Counter(p["stratum"] for p in picked)
    by_type = Counter(f["type"] for f in findings)
    by_type_stratum = Counter((f["type"], stratum_of_card.get(f["card"], "?"))
                              for f in findings)
    cards_with = len({f["card"] for f in findings})
    merge_related = [f for f in findings if f.get("merge_related")]
    lines = [
        "# LLM 檢驗報告:%s" % os.path.basename(round_dir),
        "",
        "樣本 %d 張卡(%s);回報 %d 筆,涉及 %d 張卡(%.1f%%)。" % (
            len(picked), "/".join("%s %d" % (label[k], quota[k]) for k in strata),
            len(findings), cards_with, 100.0 * cards_with / max(1, len(picked))),
        "",
        "| 錯誤類型 | 筆數 | " + " | ".join(label[k] for k in strata) + " |",
        "|---|---|" + "---|" * len(strata),
    ]
    for t in error_types:
        lines.append("| %s | %d | %s |" % (
            t, by_type.get(t, 0),
            " | ".join(str(by_type_stratum.get((t, k), 0)) for k in strata)))
    other = [f for f in findings if f["type"] not in error_types]
    if other:
        lines.append("| (其他) | %d | %s |" % (len(other), " | ".join(
            str(sum(1 for f in other if stratum_of_card.get(f["card"]) == k))
            for k in strata)))
    cards_per = Counter(stratum_of_card[c] for c in {f["card"] for f in findings}
                        if c in stratum_of_card)
    lines.append("| 涉及卡 | %d | %s |" % (
        cards_with, " | ".join("%d/%d" % (cards_per.get(k, 0), quota[k])
                               for k in strata)))
    lines.append("")
    if meta.get("mode") == "affected":
        by_type_merge = Counter(f["type"] for f in merge_related)
        lines += [
            "和 ● 合併有關的回報 %d 筆(%s);其餘 %d 筆是合併前就有的規則問題。" % (
                len(merge_related),
                "、".join("%s %d" % (t, by_type_merge[t]) for t in ERROR_TYPES
                          if by_type_merge[t]) or "無",
                len(findings) - len(merge_related)),
            "",
        ]
    for t in error_types + ("其他",):
        items = [f for f in findings
                 if (f["type"] == t if t != "其他" else f["type"] not in error_types)]
        if not items:
            continue
        lines += ["## %s(%d 筆)" % (t, len(items)), ""]
        for f in items:
            tag = "【合併】" if f.get("merge_related") else ""
            lines.append("- `%s` %s 框架 %s:%s%s" % (
                f["card"], f.get("index", ""), f.get("frame", "—"), tag,
                f.get("reason", "").replace("\n", " ")))
        lines.append("")
    path = os.path.join(round_dir, "report.md")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    print("written", path, "findings", len(findings))


# ── 動作類別(action-categories 票 07)──

def category_frames():
    """框架類別檔的每列與它在 frames.json 的動作框架,依框架類別檔的順序:[(列, 框架)]。"""
    with open(FRAME_CATEGORIES, encoding="utf-8") as f:
        rows = json.load(f)
    _cards, _tokens, frames = load()
    by_key = {(r["card"], r["section"], r["index"], fr["order"]): fr
              for r in frames for fr in r["frames"]}
    return [(row, by_key[frame_key(row)]) for row in rows]


# 框架在框架類別檔與 frames.json 裡的鍵(卡號、段落、句序、框架序);樣本每筆也帶這四欄
FRAME_KEY_FIELDS = ("card", "section", "index", "order")


def frame_key(row):
    """框架類別檔的一列(或樣本的一筆)→ 對齊 frames.json 的鍵。"""
    return tuple(row[k] for k in FRAME_KEY_FIELDS)


def sample_categories(seed):
    """依葉分層抽框架:依樹序每葉從帶該葉、還沒被抽過的已歸框架抽 PER_LEAF 個(不足全取),
    再從未歸框架抽 UNPLACED_QUOTA 個;同一種子重抽相同。每筆記樣本號、框架鍵與抽自的葉
    (未歸記 STRATUM_UNPLACED)。"""
    tree = categories.load_tree()
    rows = [row for row, _f in category_frames()]
    rng = random.Random(seed)
    picked, taken = [], set()

    def take(pool, quota, stratum):
        chosen = sorted(rng.sample(pool, min(quota, len(pool))))
        for i in chosen:
            taken.add(i)
            picked.append(dict(zip(FRAME_KEY_FIELDS, frame_key(rows[i])), stratum=stratum))

    for leaf in tree.leaves:
        take([i for i, row in enumerate(rows) if leaf.name in row["leaves"] and i not in taken],
             PER_LEAF, leaf.name)
    take([i for i, row in enumerate(rows) if row["status"] == categories.STATUS_UNPLACED],
         UNPLACED_QUOTA, STRATUM_UNPLACED)
    for n, p in enumerate(picked, 1):
        p["id"] = "c%04d" % n
    print("葉 %d(有框架 %d)、樣本 %d(已歸 %d、未歸 %d)" % (
        len(tree.leaves), len({p["stratum"] for p in picked} - {STRATUM_UNPLACED}), len(picked),
        sum(p["stratum"] != STRATUM_UNPLACED for p in picked),
        sum(p["stratum"] == STRATUM_UNPLACED for p in picked)))
    return picked


def leaf_conditions(leaf):
    """葉的條件欄(詞元與極性類之外)→ 一行描述;沒有條件的是預設葉。"""
    parts = []
    for field in categories.ZONE_FIELDS:
        zone = getattr(leaf, field)
        if zone:
            player = leaf.players.get(field)
            parts.append("%s=%s%s" % (categories.LEAF_LABELS[field], zone,
                                      "(玩家 %s)" % player if player else ""))
    if leaf.keywords:
        parts.append("關鍵詞=" + "|".join(leaf.keywords))
    if leaf.goal_keywords:
        parts.append("目的關鍵詞=" + "|".join(leaf.goal_keywords))
    return "・".join(parts) or "(預設葉:不看論元)"


def node_lines(tree, key):
    """詞元節點(詞元, 極性類)→ 它的葉清單(樹序;條件與路徑),批次檔與樹檔共用。"""
    lines = []
    for n, leaf in enumerate(tree.by_key[key], 1):
        lines.append("%d. **%s** — %s — 路徑 %s" % (
            n, leaf.name, leaf_conditions(leaf), " › ".join(leaf.path)))
    return lines


def node_title(key):
    """(詞元, 極性類)→ 批次檔與樹檔裡的節點標題。"""
    lemma, polarity = key
    return "%s(極性類 %s)" % (lemma, polarity)


def tree_lines(tree):
    """整棵樹的詞元節點與葉(樹序),給子代理查「該歸哪一葉」。"""
    lines = ["# 類別樹(詞元節點與葉,樹序)", "",
             "每個詞元節點列它的葉;同一節點內寫在前面的先比(見說明的比對規則)。", ""]
    for key in tree.by_key:
        lines += ["## " + node_title(key)] + node_lines(tree, key) + [""]
    return lines


def sample_block(p, row, f, s, card):
    """一個樣本 → 批次檔的一節:卡、句、原文、框架與它現在的歸組。"""
    if row["status"] == categories.STATUS_PLACED:
        placed = "已歸 → %s(大類 %s)" % ("、".join(row["leaves"]), row["major"])
    else:
        placed = row["status"]
    players = "、".join("%s=%s" % (label, row[field]) for field, label in (
        ("source_player", "來源玩家"), ("goal_player", "目的玩家")) if row[field])
    return ["### 樣本 %s(抽自 %s)" % (p["id"], p["stratum"]),
            "卡 %d %s(%s)· 句 %s · 框架 %d" % (
                p["card"], card["name_ja"], card["name_zh"], sentence_label(s),
                f["order"] + 1)] + sentence_lines(s) + [
            frame_line(f["order"] + 1, f),
            "歸組:%s%s" % (placed, "(%s)" % players if players else ""), ""]


def write_category_batches(round_dir, picked, meta):
    """樣本依框架的詞元節點分組(樹序;同一節點的樣本同批、節點的葉清單列一次),連續切成
    meta["batches"] 批;沒有節點的(未歸類)樣本輪流分到各批末尾。另寫 tree.md(整棵樹)。
    歸組讀現在的框架類別檔(複檢時是修後的歸組)。"""
    tree = categories.load_tree()
    cards, tokens, _frames = load()
    sentences = {(s["card"], s["section"], s["index"]): s for s in tokens}
    current = {frame_key(row): (row, f) for row, f in category_frames()}
    groups = {key: [] for key in tree.by_key}
    loose = []
    for p in picked:
        row, f = current[frame_key(p)]
        key = (f["action"], categories.polarity_class(f))
        (groups[key] if key in groups else loose).append((p, row, f))
    groups = [(key, items) for key, items in groups.items() if items]
    batches = meta["batches"]
    target = sum(len(items) for _k, items in groups) / batches
    chunks, size = [[]], 0
    for key, items in groups:
        if size >= target * len(chunks) and len(chunks) < batches:
            chunks.append([])
        chunks[-1].append((key, items))
        size += len(items)
    write_sample_meta(round_dir, picked, meta)

    def block(p, row, f):
        return sample_block(p, row, f, sentences[(p["card"], p["section"], p["index"])],
                            cards[p["card"]])

    with open(os.path.join(round_dir, "tree.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(tree_lines(tree)) + "\n")
    for k in range(batches):
        chunk = chunks[k] if k < len(chunks) else []
        extra = loose[k::batches]
        count = sum(len(items) for _key, items in chunk) + len(extra)
        lines = ["# 批次 %d(%d 個框架)" % (k, count), ""]
        for key, items in chunk:
            lines += ["## 詞元節點 " + node_title(key), "", "本節點的葉(樹序):"]
            lines += node_lines(tree, key) + [""]
            for p, row, f in items:
                lines += block(p, row, f)
        if extra:
            lines += ["## 沒有詞元節點的框架(未歸類)", "",
                      "這些框架的(詞元, 極性類)在樹上沒有節點;對照 tree.md 看有沒有該歸的葉。", ""]
            for p, row, f in extra:
                lines += block(p, row, f)
        with open(os.path.join(round_dir, "batch-%d.md" % k), "w", encoding="utf-8",
                  newline="\n") as f:
            f.write("\n".join(lines))
        print("written batch-%d.md (%d frames)" % (k, count))


def report_categories(round_dir):
    """讀 findings-<k>.json(每筆指一個樣本)→ report.md:依錯誤類型、成因、樣本層(已歸/
    未歸)與詞元節點計數,逐筆列卡號、句、框架、現在的歸組、該歸的葉與理由。「現在的歸組」讀
    當下的框架類別檔,所以報告要在修規則前跑(round1 的報告記的是修前的落點)。"""
    meta = read_meta(round_dir)
    with open(os.path.join(round_dir, "sample.json"), encoding="utf-8") as f:
        picked = {p["id"]: p for p in json.load(f)}
    current = {frame_key(row): (row, f) for row, f in category_frames()}
    findings = load_findings(round_dir, meta["batches"])
    unknown = [x for x in findings if x.get("sample") not in picked]
    if unknown:
        raise SystemExit("findings 指到不在樣本裡的樣本號:%s" % ", ".join(
            str(x.get("sample")) for x in unknown))
    error_types = tuple(meta["error_types"])

    def layer(p):
        return "未歸" if p["stratum"] == STRATUM_UNPLACED else "已歸"

    total = Counter(layer(p) for p in picked.values())
    wrong = {x["sample"] for x in findings}
    wrong_by_layer = Counter(layer(picked[i]) for i in wrong)
    by_type = Counter(x["type"] for x in findings)
    by_cause = Counter(x.get("cause", "?") for x in findings)
    lines = [
        "# LLM 檢驗報告:%s" % os.path.basename(round_dir), "",
        "樣本 %d 個框架(已歸 %d:依樹序每葉抽 %d、不足全取;未歸 %d;種子 %s);回報 %d 筆,涉及 "
        "%d 個框架(%.1f%%):已歸樣本 %d/%d(%.1f%%)、未歸樣本 %d/%d(%.1f%%)。" % (
            len(picked), total["已歸"], PER_LEAF, total["未歸"], meta.get("seed"), len(findings),
            len(wrong), 100.0 * len(wrong) / max(1, len(picked)),
            wrong_by_layer["已歸"], total["已歸"],
            100.0 * wrong_by_layer["已歸"] / max(1, total["已歸"]),
            wrong_by_layer["未歸"], total["未歸"],
            100.0 * wrong_by_layer["未歸"] / max(1, total["未歸"])), "",
        "| 錯誤類型 | 筆數 | " + " | ".join(CATEGORY_CAUSES) + " |",
        "|---|---|" + "---|" * len(CATEGORY_CAUSES)]
    for t in error_types + tuple(sorted(set(by_type) - set(error_types))):
        lines.append("| %s | %d | %s |" % (t, by_type[t], " | ".join(
            str(sum(1 for x in findings if x["type"] == t and x.get("cause") == c))
            for c in CATEGORY_CAUSES)))
    lines += ["| 合計 | %d | %s |" % (len(findings), " | ".join(
        str(by_cause[c]) for c in CATEGORY_CAUSES)), ""]
    by_node = Counter()
    for x in findings:
        _row, f = current[frame_key(picked[x["sample"]])]
        by_node[(f["action"], categories.polarity_class(f) or "一般否定")] += 1
    lines += ["## 依詞元節點(筆數)", "", "、".join(
        "%s(%s) %d" % (lemma, cls, n) for (lemma, cls), n in sorted(
            by_node.items(), key=lambda kv: (-kv[1], kv[0]))), ""]
    for t in error_types + tuple(sorted(set(by_type) - set(error_types))):
        items = [x for x in findings if x["type"] == t]
        if not items:
            continue
        lines += ["## %s(%d 筆)" % (t, len(items)), ""]
        for x in sorted(items, key=lambda x: x["sample"]):
            p = picked[x["sample"]]
            row, f = current[frame_key(p)]
            now = "、".join(row["leaves"]) or row["status"]
            expected = "、".join(x.get("expected") or []) or "—"
            lines.append("- %s `%s` %s 框架 %d %s〔抽自 %s;現 %s → 該 %s;%s〕%s" % (
                x["sample"], p["card"], p["index"], p["order"] + 1, f["action"], p["stratum"],
                now, expected, x.get("cause", "?"), x.get("reason", "").replace("\n", " ")))
        lines.append("")
    path = os.path.join(round_dir, "report.md")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    print("written", path, "findings", len(findings))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=("sample", "affected", "constraints", "v2", "v3",
                                        "lemma", "categories", "report", "recheck"))
    ap.add_argument("--round", type=int, required=True)
    ap.add_argument("--seed", type=int, default=20261009)
    ap.add_argument("--from", dest="from_round", type=int)
    ap.add_argument("--line", choices=("frames", "constraints", "v2", "v3", "lemma", "categories"),
                    default="frames")
    args = ap.parse_args()
    line = (args.command if args.command in ("constraints", "v2", "v3", "lemma", "categories")
            else args.line)
    round_dir = round_dir_of(line, args.round)
    if args.command == "categories":
        write_category_batches(round_dir, sample_categories(args.seed),
                               {"mode": "categories", "seed": args.seed,
                                "batches": BATCHES_CATEGORY,
                                "error_types": list(ERROR_TYPES_CATEGORY)})
    elif args.command == "recheck" and line == "categories":
        src = round_dir_of(line, args.from_round)
        with open(os.path.join(src, "sample.json"), encoding="utf-8") as f:
            picked = json.load(f)
        write_category_batches(round_dir, picked, dict(read_meta(src), recheck_of=args.from_round))
    elif args.command == "report" and line == "categories":
        report_categories(round_dir)
    elif args.command == "lemma":
        write_batches(round_dir, sample_lemma(args.seed),
                      {"mode": "lemma", "seed": args.seed, "batches": BATCHES_LEMMA,
                       "strata": list(STRATA_LEMMA), "error_types": list(ERROR_TYPES_LEMMA)})
    elif args.command == "v3":
        write_batches(round_dir, sample_v3(args.seed),
                      {"mode": "v3", "seed": args.seed, "batches": BATCHES_V3,
                       "strata": list(STRATA_V3), "error_types": list(ERROR_TYPES_V3)})
    elif args.command == "v2":
        write_batches(round_dir, sample_v2(args.seed),
                      {"mode": "v2", "seed": args.seed, "batches": BATCHES_V2,
                       "strata": list(STRATA_V2), "error_types": list(ERROR_TYPES_V2)})
    elif args.command == "constraints":
        write_batches(round_dir, sample_constraints(args.seed),
                      {"mode": "constraints", "seed": args.seed,
                       "batches": BATCHES_CONSTRAINT, "strata": list(STRATA_CONSTRAINT),
                       "error_types": list(ERROR_TYPES_CONSTRAINT)})
    elif args.command == "sample":
        write_batches(round_dir, sample(args.seed),
                      {"mode": "sample", "seed": args.seed, "batches": BATCHES,
                       "strata": list(QUOTA)})
    elif args.command == "affected":
        write_batches(round_dir, sample_affected(args.seed),
                      {"mode": "affected", "seed": args.seed,
                       "batches": BATCHES_AFFECTED, "strata": list(FAMILIES)})
    elif args.command == "recheck":
        src = round_dir_of(line, args.from_round)
        with open(os.path.join(src, "sample.json"), encoding="utf-8") as f:
            picked = json.load(f)
        meta = dict(read_meta(src), recheck_of=args.from_round)
        write_batches(round_dir, picked, meta)
    else:
        report(round_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
