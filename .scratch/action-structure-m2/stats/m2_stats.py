# 動作搜尋里程碑二規格引用的統計數字(讀卡片結構產物,只印 stdout,不寫報告)。
# 跑法:python -X utf8 .scratch/action-structure-m2/stats/m2_stats.py <repo 根>
# 只用標準庫:不 import repo 的模組,產物讀法自己做(見 load_cards / iter_segments)。
# 輸出決定性:排序固定、不印時間;每個數字一行,格式「<標籤>: <數字>」(卡號清單一行逗號分隔)。
#
# 名詞(GLOSSARY.md「## 動作搜尋」):
#   段 = 區塊(含內嵌效果節點的內容區塊)裡的 segments;段原文 = 區塊 text[span[0]:span[1]]。
#   述語解析不出段 = 段的 unparsed.reason == "述語解析不出"(milestone_stats.py 的 REASON)。
#   全庫區塊 = 每張卡的頂層 blocks(內嵌效果的內容區塊原文是頂層區塊原文的子字串,不另算,免得重複)。
#   「段 / 張」:段數與這些段所屬的不重複卡數;「區塊 / 張」同理;「句」= 正規式在原文上的出現次數。
#   一段可以落在多列(旗標),除非該節註明「先中先贏」(一段只落一列,沒中進「其他」)。
import json
import os
import re
import sys
from collections import Counter

ROOT = sys.argv[1] if len(sys.argv) > 1 else "."
REASON = "述語解析不出"


# ── 讀產物 ──────────────────────────────────────────────────────────
def iter_nodes(items):
    """段樹節點(含分歧各支),同 structure_shape.iter_nodes。"""
    for node in items:
        yield node
        if node.get("node") == "分歧":
            for branch in node.get("branches", []):
                yield from iter_nodes(branch.get("items", []))


def iter_segments(block):
    """區塊與其內嵌效果的所有段,同 structure_shape.iter_segments;產生 (所屬區塊, 段)。"""
    for seg in block.get("segments", []):
        yield block, seg
    for node in iter_nodes(block.get("tree", {}).get("items", [])):
        if node.get("node") == "內嵌效果" and node.get("block"):
            yield from iter_segments(node["block"])


def iter_blocks(block, offset=0):
    """區塊與其內嵌效果的內容區塊,附「內容區塊原文在頂層區塊原文裡的起點」。"""
    yield block, offset
    for node in iter_nodes(block.get("tree", {}).get("items", [])):
        if node.get("node") == "內嵌效果" and node.get("block"):
            inner = node["block"]
            yield from iter_blocks(inner, offset + inner["span"][0])


with open(os.path.join(ROOT, "data", "action_structure.json"), encoding="utf-8") as f:
    CARDS = json.load(f)

WITH_TEXT = [c for c in CARDS if not c.get("unparsed")]

SEGS = []  # 全庫段
for card in CARDS:
    for top in card.get("blocks", []):
        for blk, seg in iter_segments(top):
            start, end = seg["span"]
            SEGS.append({
                "cid": card["id"],
                "kind": seg["kind"],
                "text": blk["text"][start:end],
                "predicate": seg.get("predicate") or "",
                "reason": (seg.get("unparsed") or {}).get("reason"),
            })
UNPARSED = [s for s in SEGS if s["reason"] == REASON]

BLOCKS = [(card, top) for card in CARDS for top in card.get("blocks", [])]  # 全庫頂層區塊


# ── 輸出 ────────────────────────────────────────────────────────────
def out(label, n):
    print(f"{label}: {n}")


def seg_count(label, segs):
    out(f"{label} 段", len(segs))
    out(f"{label} 張", len({s["cid"] for s in segs}))


def pick(segs, pattern, field="text"):
    r = re.compile(pattern)
    return [s for s in segs if r.search(s[field])]


def first_match(segs, rules, field="text"):
    """先中先贏:依 rules 順序,一段只落第一個比中的列;沒比中的進「其他」。"""
    groups = {label: [] for label, _ in rules}
    groups["其他"] = []
    for s in segs:
        for label, pattern in rules:
            if re.search(pattern, s[field]):
                groups[label].append(s)
                break
        else:
            groups["其他"].append(s)
    return groups


def block_count(label, pattern):
    """含字面的頂層區塊數 / 張數。"""
    r = re.compile(pattern)
    hit = [(c["id"], b["id"]) for c, b in BLOCKS if r.search(b["text"])]
    out(f"{label} 區塊", len(hit))
    out(f"{label} 張", len({cid for cid, _ in hit}))
    return hit


def sentence_count(label, pattern):
    """字面在頂層區塊原文上的出現次數 / 張數。"""
    r = re.compile(pattern)
    hits = [c["id"] for c, b in BLOCKS for _ in r.finditer(b["text"])]
    out(f"{label} 句", len(hits))
    out(f"{label} 張", len(set(hits)))
    return hits


def section(title):
    print(f"\n# {title}")


# ══ A. 母體 ══════════════════════════════════════════════════════════
section("A. 母體")
out("A.有官方日文 張", len(WITH_TEXT))
out("A.全庫段(含內嵌效果) 段", len(SEGS))
seg_count("A.述語解析不出", UNPARSED)


# ══ B. 六類字面粗篩(milestone_stats.py 的 MARKERS 原樣照抄;段原文,可重疊)══════
# 「六類」= 抗性、表示で、ダメージ、アップ/ダウン、選んで、ドロー+取り除(第 6 類分兩列)。
# 第 6b 列照 MARKERS 是 (エクシーズ素材|取り除),所以「カウンターを取り除く」與「X素材としている」也在內。
section("B. 六類字面粗篩(述語解析不出段)")
MARKERS = [
    ("抗性/限制(されない|できない|受けない 收尾)", r"(されない|できない|受けない)$"),
    ("〜表示で", r"表示で"),
    ("ダメージ", r"ダメージ"),
    ("アップ/ダウン(アップ|ダウン)する", r"(アップ|ダウン)する"),
    ("選んで", r"選んで"),
    ("ドロー", r"ドロー"),
    ("取り除いて(エクシーズ素材|取り除)", r"(エクシーズ素材|取り除)"),
]
CLASS = {}
for label, pattern in MARKERS:
    CLASS[label] = pick(UNPARSED, pattern)
    seg_count(f"B.{label}", CLASS[label])
union = [s for s in UNPARSED if any(re.search(p, s["text"]) for _, p in MARKERS)]
seg_count("B.六類聯集", union)


# ══ C. 跨類(述語解析不出段)══════════════════════════════════════════
section("C. 跨類(述語解析不出段)")
seg_count("C.段原文含「限り」", pick(UNPARSED, r"限り"))
seg_count("C.原述語字面含「、」", pick(UNPARSED, r"、", "predicate"))


# ══ D. 抗性/限制細分 ══════════════════════════════════════════════════
# 母體 = B 的抗性/限制類(述語解析不出、段原文以 されない|できない|受けない 收尾)。
# 細分先中先贏,規則順序照 scratchpad analyze.py cat1(順序影響歸屬:召喚限制在召喚不能前、
# 攻擊對象限制在取對象抗性與攻擊限制前)。旗標可重疊。
section("D. 抗性/限制細分(B 抗性/限制類)")
SUMMON_WORDS = (r"(?:特殊召喚|召喚|P召喚|Ｐ召喚|S召喚|X召喚|L召喚|リンク召喚|アドバンス召喚|反転召喚"
                r"|シンクロ召喚|エクシーズ召喚|融合召喚)")
ENDCAN = r"(?:する事は|する事が|事は|事が|が)?できない$"
D_RULES = [
    ("しか…召喚できない", r"しか[^、]*?" + SUMMON_WORDS + r"(?:・" + SUMMON_WORDS + r")*" + ENDCAN),
    ("しか表側表示で存在できない", r"しか表側表示で存在できない$"),
    ("〜度しか使用/選択/適用/発動できない", r"度(?:だけ)?しか(?:使用|選択|適用|発動)" + ENDCAN),
    ("素材にできない/しか使用できない",
     r"(?:素材(?:に|と(?:する事は|する事が)?|として使用(?:する事は|する事が)?)できない|にしか使用できない"
     r"|素材(?:モンスター)?として使用(?:する事は|する事が)?できない)$"),
    ("破壊されない", r"破壊されない$"),
    ("効果を受けない", r"受けない$"),
    ("無効化されない", r"無効化されない$"),
    ("攻撃対象に選択できない", r"攻撃対象に(?:選択)?" + ENDCAN + r"|攻撃対象にされない$"),
    ("効果の対象にできない/ならない", r"対象に" + ENDCAN),
    ("攻撃(宣言)できない", r"攻撃(?:宣言)?" + ENDCAN),
    ("発動できない", r"発動" + ENDCAN),
    ("召喚・特殊召喚できない(不含しか)", SUMMON_WORDS + r"(?:・" + SUMMON_WORDS + r")*" + ENDCAN),
    ("表示形式/コントロールは変更できない", r"変更" + ENDCAN),
    ("其他動作不能(リリース/除外/セット/ドロー/適用…)",
     r"(?:リリース|除外|セット|ドロー|適用|戻る|捨て|確認|行う|出す)" + ENDCAN + r"|適用されない$"),
]
for label, segs in first_match(CLASS[MARKERS[0][0]], D_RULES).items():
    seg_count(f"D.細分(先中先贏) {label}", segs)
RES = CLASS[MARKERS[0][0]]
seg_count("D.原因帶「は」(戦闘では/効果では/によっては)",
          pick(RES, r"(?:戦闘|効果|戦闘・効果)(?:で|によって)は"))
seg_count("D.「Ｎ度(だけ|まで)」且不是「〜度しか使用できない」", pick(RES, r"[０-９]度(?:だけ|まで)(?!しか)"))
seg_count("D.「この効果は１ターンに１度しか使用できない」型",
          pick(RES, r"この効果は[^、]*?１ターンに１度しか使用できない$"))


# ══ E. 攻擊句型(全庫頂層區塊原文,可重疊)═════════════════════════════
section("E. 攻擊句型(全庫區塊)")
E_RULES = [
    ("直接攻撃できる(含する事ができる)", r"直接攻撃(?:する事が|が)?できる"),
    ("２回攻撃できる類(２回(まで)攻撃(する事が)できる)", r"２回(?:まで)?攻撃(?:を)?(?:する事が|が)?できる"),
    ("３回攻撃できる類", r"３回(?:まで)?攻撃(?:を)?(?:する事が|が)?できる"),
    ("もう１度(だけ)(続けて)攻撃", r"もう１度(?:だけ)?(?:続けて)?(?:[^。、]{0,12}?)攻撃"),
    ("全て(のモンスター)に１回ずつ攻撃(含「相手モンスター全てに」)", r"全て(?:の[^。、]{0,20}?モンスター)?に１回ずつ攻撃"),
    ("攻撃(宣言)できない/できず(含直接攻撃)", r"攻撃(?:宣言)?(?:を)?(?:する事は|する事が|は)?でき(?:ない|ず)"),
    ("攻撃対象に(選択)できない/されない/ならない",
     r"攻撃対象に(?:選択)?(?:する事は|する事が)?(?:できない|されない|ならない)"),
    ("攻撃(宣言)しなければならない/ならず", r"攻撃(?:宣言)?しなければなら(?:ない|ず)"),
]
for label, pattern in E_RULES:
    block_count(f"E.{label}", pattern)


# ══ F. 表示形式(全庫段,不限解析不出)═══════════════════════════════════
# 規則照 scratchpad roles.py:「」內字面先遮掉;母體是含表示形式字面
# ((表側|裏側)(攻撃|守備)?表示|(攻撃|守備)表示|表示形式)的段,每處字面依後文判角色,一段可有多角色:
#   1 述語本身(〜表示にする/になる/に変更、表示形式を変更、しか表示で存在できない)
#   2 述語前放置形式(表示で + 其他動詞)
#   3 物件修飾(表示で存在する + 名詞、表側表示モンスター/〜の)
#   4 前提/條件(表示で存在する 場合/時/限り/間/状態、Xが守備表示の場合、〜表示になった時、表示形式が変更された時)
#   5 其他(●攻撃表示:分支標籤等)
section("F. 表示形式(全庫段)")
COND = re.compile(r"^[^、。]*?(?:場合|時|際|限り|間|状態で)")
POS = re.compile(r"(?:表側|裏側)(?:攻撃|守備)?表示|(?:攻撃|守備)表示|表示形式")
ROLE_NAMES = {1: "述語本身", 2: "述語前放置形式", 3: "物件修飾", 4: "前提/條件", 5: "其他"}


def strip_quotes(t):
    return re.sub(r"「[^「」]*」", lambda m: "＿" * len(m.group()), t)


def roles_pos(text):
    t = strip_quotes(text)
    occ = list(POS.finditer(t))
    roles = []
    for i, m in enumerate(occ):
        f = t[m.end():]
        if re.match(r"^(?:か|または|・|、|及び|と)", f) and i + 1 < len(occ) and occ[i + 1].start() - m.end() <= 4:
            roles.append(None)
            continue
        if re.match(r"^：", f):
            roles.append(5)
            continue
        if re.match(r"^(?:から|を|は|が)?", f) and i + 1 < len(occ) and m.group() == "表示形式" \
                and occ[i + 1].start() - m.end() <= 2:
            roles.append(None)
            continue
        if re.match(r"^から", f) and i + 1 < len(occ):
            roles.append(None)
            continue
        if m.group() == "表示形式":
            g = re.match(r"^(?:を|は|が|も)?[^、。]{0,12}?(?:変更|入れ替え|変わ)"
                         r"(?:する|し|され|された|できない|する事|でき|した|して)?", f)
            if g:
                roles.append(4 if COND.match(f[g.end():]) and not re.match(r"^[^、]*?できない", f) else 1)
            else:
                roles.append(3 if re.match(r"^(?:が|の)", f) else 5)
            continue
        if re.match(r"^で(?:しか|のみ)?存在できない", f) or re.match(r"^で(?:１|１体|１枚)?しか存在できない", f):
            roles.append(1)
        elif re.match(r"^で(?:[^、。]{0,14}?(?:が|は))?存在(?:する|している|し|しない|しなく)?"
                      r"(?:場合|時|限り|間|状態|、|ならば)", f):
            roles.append(4)
        elif re.match(r"^で(?:[^、。]{0,14}?が)?存在(?:する|している)", f):
            roles.append(3)
        elif re.match(r"^で", f):
            roles.append(2)
        elif re.match(r"^に(?:変更|戻|変わ)?(?:する|し|なる|なり|なった|された|した|して|できる|され|なっ|った)", f):
            g = re.match(r"^に(?:変更|戻|変わ)?(?:する事ができる|された|され|して|した|する|し|なった|なっ|なる|なり"
                         r"|できる|った)", f)
            rest = f[g.end():]
            if re.match(r"^(?:た|ている|ていた)?(?:モンスター|カード)", rest):
                roles.append(3)
            elif COND.match(rest):
                roles.append(4)
            else:
                roles.append(1)
        elif re.match(r"^の(?:場合|時|とき|状態で|間)", f):
            roles.append(4)
        elif re.match(r"^(?:の|モンスター|カード|状態)", f):
            roles.append(3)
        else:
            roles.append(5)
    for i in range(len(roles) - 1, -1, -1):  # 「か/または」前一個補成後一個的角色
        if roles[i] is None:
            roles[i] = roles[i + 1] if i + 1 < len(roles) and roles[i + 1] else 5
    return occ, roles


POS_SEGS = []
placement = Counter()
for s in SEGS:
    t = strip_quotes(s["text"])
    if not POS.search(t):
        continue
    occ, roles = roles_pos(s["text"])
    s["_roles"] = set(roles)
    POS_SEGS.append(s)
    for m, role in zip(occ, roles):
        if role == 2 and t[m.end():m.end() + 1] == "で":
            placement[m.group() + "で"] += 1
seg_count("F.含表示形式字面的段", POS_SEGS)
seg_count("F.其中含「表示で」或「表示に」的段", [s for s in POS_SEGS if re.search(r"表示[でに]", strip_quotes(s["text"]))])
for role, name in ROLE_NAMES.items():
    segs = [s for s in POS_SEGS if role in s["_roles"]]
    seg_count(f"F.角色{role} {name}", segs)
    out(f"F.角色{role} {name} 其中段解析不出(任何原因) 段", sum(1 for s in segs if s["reason"]))
seg_count("F.同一段兩種以上角色", [s for s in POS_SEGS if len(s["_roles"]) >= 2])
x_or_y = [s for s in SEGS if re.search(r"表示か(?:表側|裏側)?(?:攻撃|守備)?表示で", strip_quotes(s["text"]))]
out("F.「X表示かY表示で」句", sum(len(re.findall(r"表示か(?:表側|裏側)?(?:攻撃|守備)?表示で", strip_quotes(s["text"])))
                                 for s in x_or_y))
seg_count("F.「X表示かY表示で」", x_or_y)
# 放置形式字面次數:表示形式只算角色 2 的那一處(最長字面,「裏側守備表示で」不再算進「守備表示で」);
# 「好きな順番で」「〜カード扱いで」在全庫段原文(遮掉「」)上直接數,不分角色。
for s in SEGS:
    t = strip_quotes(s["text"])
    placement["好きな順番で"] += len(re.findall(r"好きな順番で", t))
    for m in re.finditer(r"(?:装備魔法|永続魔法|永続罠|通常魔法|通常罠|装備|魔法|罠)カード扱いで", t):
        placement[m.group()] += 1
F_ORDER = ["表側表示で", "守備表示で", "裏側守備表示で", "表側攻撃表示で", "攻撃表示で", "表側守備表示で",
           "裏側表示で", "好きな順番で", "装備魔法カード扱いで", "永続魔法カード扱いで", "永続罠カード扱いで",
           "魔法カード扱いで"]
for key in F_ORDER + sorted(k for k in placement if k not in F_ORDER):
    out(f"F.放置形式字面「{key}」次", placement[key])
put = [s for s in SEGS if re.search(r"(?<!位)置(?:く|ける|き|いて)(?:事ができる)?$", strip_quotes(s["text"]))]
seg_count("F.段原文以「置く/置ける/置き/置いて」收尾", put)
seg_count("F.其中述語解析不出", [s for s in put if s["reason"] == REASON])


# ══ G. 傷害(B ダメージ類)════════════════════════════════════════════
# 細分先中先贏,規則與順序照 scratchpad analyze.py cat3;旗標可重疊。
section("G. 傷害(B ダメージ類)")
G_RULES = [
    ("ダメージは０/半分/倍になる", r"ダメージ(?:は|を)[^、]*?(?:０|半分|倍)(?:になる|にする)$|ダメージ(?:は|を)(?:０|半分|倍)"),
    ("ダメージを受けない", r"ダメージを受けない$"),
    ("給予(效果)与える", r"ダメージを(?:[^、]*?に)?与える(?:事ができる)?$"),
    ("給予(條件)与えた", r"ダメージを(?:[^、]*?に)?与えた"),
    ("受到(效果)受ける", r"ダメージを受ける$"),
    ("受到(條件)受けた", r"ダメージを受けた"),
    ("時點 ダメージ計算時/ダメージステップ", r"ダメージ(?:計算|ステップ)"),
    ("代わりに相手が受ける", r"代わりに.*受ける$"),
]
DMG = CLASS[MARKERS[2][0]]
for label, segs in first_match(DMG, G_RULES).items():
    seg_count(f"G.細分(先中先贏) {label}", segs)
seg_count("G.固定數值「N(ポイント)(の)ダメージ」", pick(DMG, r"[０-９]+(?:ポイント)?(?:の)?ダメージ"))
seg_count("G.算式數值「×N/分の/分だけの/数値分の/半分の ダメージ」",
          pick(DMG, r"(?:×[０-９]+(?:ポイント)?|分の|分だけの|数値分の|半分の)ダメージ"))
seg_count("G.「相手ライフに」", pick(DMG, r"相手ライフに"))
hits = sentence_count("G.全庫「ダメージ…受けない」(ダメージ[^。、]{0,8}受けない)", r"ダメージ[^。、]{0,8}受けない")
print(f"G.全庫「ダメージ…受けない」卡號: {', '.join(str(c) for c in sorted(set(hits)))}")


# ══ H. 攻守增減(B アップ/ダウン類)════════════════════════════════════
# 細分先中先贏,順序:算式(×N 或 につき)→ 引用(分/半分/だけ アップ)→ 固定(N アップ)→ 沒數值 → 其他。
# 與 analyze.py cat4 的差別:那邊算式只認 ×N,「〜１体につき、…５００アップする」歸固定值;
# 這裡依規格把「につき」併進算式。原規則的「につき」段數另列旗標,可對回去。
section("H. 攻守增減(B アップ/ダウン類)")
H_RULES = [
    ("算式(×N 或 につき)", r"×[０-９]+(?:ポイント)?(?:アップ|ダウン)する|につき"),
    ("引用其他值(分/半分/だけ アップ)", r"(?:分|半分|だけ)(?:アップ|ダウン)する"),
    ("固定值(N(ポイント)アップ)", r"[０-９]+(?:ポイント)?(?:アップ|ダウン)する"),
    ("沒數值(は|が アップする)", r"(?:は|が)(?:アップ|ダウン)する"),
]
UD = CLASS[MARKERS[3][0]]
for label, segs in first_match(UD, H_RULES).items():
    seg_count(f"H.細分(先中先贏) {label}", segs)
seg_count("H.含「につき」", pick(UD, r"につき"))
seg_count("H.攻守同時「攻撃力・守備力」", pick(UD, r"攻撃力・守備力"))
seg_count("H.主語「装備モンスターの」", pick(UD, r"装備モンスターの(?:攻撃力|守備力)"))
seg_count("H.主語群體「(フィールド|全て)…モンスターの」", pick(UD, r"(?:フィールド|全て)[^、]*モンスターの(?:攻撃力|守備力)"))
seg_count("H.主語回指「その/そのモンスターの/対象のモンスターの/選択したモンスターの/それらのモンスターの」",
          pick(UD, r"(?:その|そのモンスターの|対象のモンスターの|選択したモンスターの|それらのモンスターの)(?:攻撃力|守備力)"))
seg_count("H.主語「このカードの」", pick(UD, r"このカードの(?:攻撃力|守備力)"))
seg_count("H.「ダメージ計算時のみ/ダメージステップの間/ダメージステップ時のみ」",
          pick(UD, r"ダメージ計算時のみ|ダメージステップ(?:の間|時のみ)"))
sentence_count("H.全庫「(アップ|ダウン)の装備(魔法)カード扱い」", r"(?:アップ|ダウン)の装備(?:魔法)?カード扱い")
block_count("H.全庫「以下の効果を持つ装備(魔法)カード扱いで」", r"以下の効果を持つ装備(?:魔法)?カード扱いで")


# ══ I. 選んで(B 選んで類)══════════════════════════════════════════════
# 後接動作細分先中先贏,規則與順序照 analyze.py cat5;依段數排序印全部列(含兜底列)。
section("I. 選んで(B 選んで類)")
I_RULES = [
    ("分歧引導「１つを選んで適用」", r"１つを選んで適用"),
    ("選んで特殊召喚", r"選んで[^、]*?特殊召喚"),
    ("選んで手札に加える", r"選んで[^、]*?手札に加え"),
    ("選んで捨てる", r"選んで捨て"),
    ("選んで破壊", r"選んで破壊"),
    ("選んで墓地へ送る", r"選んで墓地へ送"),
    ("選んで除外", r"選んで[^、]*?除外"),
    ("選んで〜セット", r"選んで[^、]*?セット"),
    ("選んで〜戻す", r"選んで[^、]*?戻"),
    ("選んで〜置く", r"選んで[^、]*?置"),
    ("選んで 裝備/X素材/其他", r"選んで"),
]
SEL = CLASS[MARKERS[4][0]]
groups = first_match(SEL, I_RULES)
for label, segs in sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0])):
    seg_count(f"I.後接動作(先中先贏) {label}", segs)
seg_count("I.「ランダムに」", pick(SEL, r"ランダムに"))
seg_count("I.「それぞれ…ずつ」", pick(SEL, r"それぞれ[^。]*?ずつ"))
seg_count("I.「数だけ/数まで/任意の数」", pick(SEL, r"数だけ|数まで|任意の数"))
seg_count("I.區域當物件「手札を(ランダムに)N枚(まで)選んで」", pick(SEL, r"手札を(?:ランダムに)?[０-９]+枚(?:まで)?選んで"))
hits = block_count("I.全庫「持ち主の(手札|デッキ)に」", r"持ち主の(?:手札|デッキ)に")
seg_count("I.代價段原文以「選んで」收尾(全庫段,任何狀態)", [s for s in SEGS if s["kind"] == "代價" and s["text"].endswith("選んで")])
seg_count("I.代價段原文以「選んで」收尾(B 選んで類)", [s for s in SEL if s["kind"] == "代價" and s["text"].endswith("選んで")])


# ══ J. 抽牌/去除 ══════════════════════════════════════════════════════
# ドロー細分先中先贏,規則與順序照 analyze.py cat6(先排除修飾語/規則抽牌/條件,再分張數)。
# 全庫「取り除」依去除對象:同一子句(往前到最近的 、。：● 或區塊開頭)裡最後出現的
# 「X素材/エクシーズ素材」或「カウンター」決定;兩者都沒有歸「其他(回指/否定…)」。
section("J. 抽牌/去除")
DRAW = CLASS[MARKERS[5][0]]
seg_count("J.ドロー 述語解析不出", DRAW)
J_RULES = [
    ("「ドロー以外の方法で」等ドロー以外", r"ドロー以外"),
    ("「通常のドロー」", r"通常のドロー"),
    ("條件「ドローした」", r"ドローした"),
    ("固定張數「N枚ドロー」", r"[０-９]+枚ドロー(?:する|できる|する事ができる|し)"),
    ("変数張數「数(だけ)…ドロー」", r"(?:数|枚数)(?:だけ|分)?[^、]*?ドロー(?:する|できる|し)"),
    ("其他「ドローする/できる」", r"ドロー(?:する|できる|し|できない)"),
    ("階段字面「ドローフェイズ」", r"ドローフェイズ"),
]
for label, segs in first_match(DRAW, J_RULES).items():
    seg_count(f"J.ドロー細分(先中先贏) {label}", segs)
sentence_count("J.全庫「通常のドロー」", r"通常のドロー")
sentence_count("J.全庫「ドロー以外の方法で」", r"ドロー以外の方法で")
seg_count("J.取り除 述語解析不出", pick(UNPARSED, r"取り除"))
removal = Counter()
removal_cards = {}
for card, b in BLOCKS:
    t = b["text"]
    for m in re.finditer(r"取り除", t):
        clause = re.split(r"[、。：●]", t[:m.start()])[-1]
        xm = max((x.end() for x in re.finditer(r"(?:X|エクシーズ)素材", clause)), default=-1)
        cm = max((x.end() for x in re.finditer(r"カウンター", clause)), default=-1)
        key = "X素材/エクシーズ素材" if xm > cm else ("カウンター" if cm > xm else "其他(回指/否定…)")
        removal[key] += 1
        removal_cards.setdefault(key, set()).add(card["id"])
for key in ("X素材/エクシーズ素材", "カウンター", "其他(回指/否定…)"):
    out(f"J.全庫「取り除」對象 {key} 次", removal[key])
    out(f"J.全庫「取り除」對象 {key} 張", len(removal_cards.get(key, ())))
mat = pick(SEGS, r"(?:X|エクシーズ)素材と(?:している|する)")
seg_count("J.「X素材としている/とする」(全庫段)", mat)
seg_count("J.「X素材としている/とする」(述語解析不出)", [s for s in mat if s["reason"] == REASON])


# ══ K. 內嵌效果與引用(全庫頂層區塊)═════════════════════════════════════
# 複製他卡效果:效果と同じになる | 同じ(元々の)(攻撃力と)効果を得る | カード名・効果を得る
#   (「同名カードとして扱い、同じ効果を得る」由第二式收;正規式都要「効果」,
#    「レベル/攻撃力…と同じになる」自然排除;「このカード名の②の効果を得る」「それぞれの効果を得る」不算)。
# 被引用物件:這些句子所在的段全是解析不出、沒有對象線,所以改用字面位置:同一頂層區塊
#   (含其內嵌效果內容區塊,span 換算回頂層原文)裡、首次出現位置在該句之前最近的物件(不含物件0)。
#   物件 unparsed 為空 → 物件解析得出;reason 物件修飾解析不出 → 物件修飾解析不出;其他 reason 另列;
#   找不到 → 沒抽出物件。
# 泛用:條件式只由 大類/位置/控制方/表示形式 原子以 且/或/非 組成(GLOSSARY 泛用物件),或沒有條件式。
section("K. 內嵌效果與引用(全庫區塊)")
block_count("K.含「効果を得る」", r"効果を得る")
gain = block_count("K.含「以下の効果を得る」", r"以下の効果を得る")
gain_ids = set(gain)
embedded = [(c["id"], b["id"]) for c, b in BLOCKS if (c["id"], b["id"]) in gain_ids
            and any(n.get("node") == "內嵌效果" for n in iter_nodes(b.get("tree", {}).get("items", [])))]
out("K.其中已成內嵌效果節點 區塊", len(embedded))
out("K.其中已成內嵌效果節點 張", len({cid for cid, _ in embedded}))
sentence_count("K.「効果は「…」となる」(同一行內最短比對,「」內可含。)", r"効果は、?「.*?」となる")

COPY_RE = re.compile(r"効果と同じになる|同じ(?:元々の)?(?:攻撃力と)?効果を得る|カード名・効果を得る")
GENERIC_OPS = {"大類", "位置", "控制方", "表示形式"}


def is_generic(cond):
    if cond is None:
        return True
    op = cond.get("op")
    if op in ("且", "或"):
        return all(is_generic(a) for a in cond.get("args", []))
    if op == "非":
        return is_generic(cond.get("arg"))
    return op in GENERIC_OPS


copy_state = Counter()
copy_cards = {}
generic_cards = set()
for card, b in BLOCKS:
    inner_ids = {}
    for blk, offset in iter_blocks(b):
        inner_ids[blk["id"]] = offset
    objs = []
    for o in card["objects"]:
        if o["id"] != "o0" and o.get("block") in inner_ids and o.get("span"):
            objs.append((inner_ids[o["block"]] + o["span"][0], o["id"], o))
    objs.sort(key=lambda x: (x[0], x[1]))
    for m in COPY_RE.finditer(b["text"]):
        before = [o for pos, _, o in objs if pos < m.start()]
        if not before:
            state = "沒抽出物件"
        else:
            obj = before[-1]
            reason = (obj.get("unparsed") or {}).get("reason")
            state = "物件解析得出" if reason is None else (
                "物件修飾解析不出" if reason == "物件修飾解析不出" else f"物件{reason}")
            if is_generic(obj.get("condition")):
                generic_cards.add(card["id"])
        copy_state[state] += 1
        copy_cards.setdefault(state, set()).add(card["id"])
out("K.複製他卡效果 句", sum(copy_state.values()))
out("K.複製他卡效果 張", len(set().union(*copy_cards.values())) if copy_cards else 0)
for state in ["物件解析得出", "物件修飾解析不出", "沒抽出物件"] + sorted(
        k for k in copy_state if k not in ("物件解析得出", "物件修飾解析不出", "沒抽出物件")):
    out(f"K.複製他卡效果 被引用物件狀態={state} 句", copy_state[state])
    out(f"K.複製他卡效果 被引用物件狀態={state} 張", len(copy_cards.get(state, ())))
out("K.複製他卡效果 被引用物件是泛用 張", len(generic_cards))
print(f"K.複製他卡效果 被引用物件是泛用 卡號: {', '.join(str(c) for c in sorted(generic_cards))}")


# ══ L. 誓約與期間(全庫頂層區塊,句 = 出現次數)═════════════════════════
section("L. 誓約與期間(全庫區塊)")
sentence_count("L.「(このカード|この効果)を発動するターン、」", r"(?:このカード|この効果)を発動するターン、")
sentence_count("L.「効果を発動するターン、」(全部)", r"効果を発動するターン、")
sentence_count("L.「効果を発動するターン、」(不含「この効果を」)", r"(?<!この)効果を発動するターン、")
sentence_count("L.「発動したターン、」", r"発動したターン、")
sentence_count("L.「この効果の発動後、ターン終了時まで」", r"この効果の発動後、ターン終了時まで")
sentence_count("L.句首「このターン、」(區塊開頭或 。：●換行 之後)", r"(?:^|(?<=[。：●\n]))このターン、")


# ══ M. 性質變更擴充(全庫頂層區塊,句 = 出現次數)═══════════════════════
# 「<屬性>(は|を|が)、?…(30 字內,不含 、。を は)…(になる|になり|となる|となり|にする|にし|変更|上げ|下げ|上が|下が)」,
# 後面緊接 モンスター/カード/X素材/ように/場合/時 的不算(那是物件修飾或條件,「カード名が「X」となるモンスター」)。
section("M. 性質變更擴充(全庫區塊)")
for attr in ("レベル", "属性", "種族", "カード名"):
    sentence_count(f"M.{attr} になる/変更/上げ下げ",
                   attr + r"(?:は|を|が)、?[^。、をは]{0,30}?(?:になる|になり|となる|となり|にする|にし|変更|上げ|下げ|上が|下が)"
                   r"(?!モンスター|カード|X素材|ように|場合|時)")
