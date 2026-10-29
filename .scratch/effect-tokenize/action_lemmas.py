# -*- coding: utf-8 -*-
"""動作詞元的正規化(frame-lemma-unify,ADR-0016):框架線的兩份封閉表——詞元對照表與補語
不併判準。框架抽取、類別線與檢驗腳本讀同一份。

詞元對照表:原詞元(框架抽取內部用的述語歸組——動詞的辭書形、サ変名詞、召喚法+召喚、併入補語的
N に/と する/なる)→ 動作詞元(正規形)與態。框架抽取在一句的框架都抽完(回填、延續之後)才過這張
表,內部規則(移動類、回填、位置)仍看原詞元;原詞元的寫法留在框架的子句字面裡,不另加欄。三條:
    態歸一    同一個動作的他動/自動/受身是同一個詞元、以他動形為名,差別記在態欄:
              詞對(戻る→戻す 自動…)、なる→する 一條規則(N に/と なる → N に/と する,
              態 自動)、無効化→無効にする;數值升降以卡文主流的 アップ/ダウン 為名
              (上げる/上がる→アップ…),アップ/ダウン 本身不分自他,態由受事者的助詞判
              (對象欄有原文 を 的值→他動,受事者在框架自己的主語/主題→自動,都沒有→空)
    寫法歸一  全名 → 現行官方縮寫(アドバンス召喚→A召喚、リンク召喚→L召喚、
              リンク素材にする→L素材にする),與 S召喚/X召喚/P召喚 同一體例
    受身      述語錨點判出被動的框架,不論詞元都是 受身(取代 2026-10-27 前的被動旗標)
他動/自動只記在被統一的詞元上:詞對與 なる→する 規則合併出的詞元(UNIFIED_SURU 列出 する 形;
なる 形一律 自動)。其餘框架態是空(None)——空是「沒判」,不是他動;対象とする 這類沒有 なる 形被併
進來的詞元也是空。

補語不併判準(FrameExtractor._fold_complement 用):N に/と なる/する 的補語最後一個詞是
封閉值域字面(COMPLEMENT_VALUE_CLASSES)、屬性名詞(COMPLEMENT_ATTRIBUTES)或 効果(COMPLEMENT_VALUE_HEADS,
「效果變成什麼」;frame-lemma-variants 票 05)時整段不併入詞元,詞元是 にする/とする 形、補語原文字面
進目的欄;狀態/角色詞(対象、無効、素材、倍、半分…)照舊併。補語與 なる/する 之間夾 も 時照沒有 も
處理(対象にもならない)。
"""

VOICE_ACTIVE, VOICE_INTRANSITIVE, VOICE_PASSIVE = "他動", "自動", "受身"
VOICES = (VOICE_ACTIVE, VOICE_INTRANSITIVE, VOICE_PASSIVE)

# ── 詞元對照表 ──
# 寫法歸一:全名 → 縮寫(整個詞元);素材系以字首對照(リンク素材にする/とする)
SPELLING = {"アドバンス召喚": "A召喚", "リンク召喚": "L召喚"}
SPELLING_PREFIXES = (("リンク素材", "L素材"),)
# 態歸一的詞對:原詞元 → (動作詞元, 態)
VOICE_PAIRS = {"戻す": ("戻す", VOICE_ACTIVE), "戻る": ("戻す", VOICE_INTRANSITIVE),
               "上げる": ("アップ", VOICE_ACTIVE), "上がる": ("アップ", VOICE_INTRANSITIVE),
               "下げる": ("ダウン", VOICE_ACTIVE), "下がる": ("ダウン", VOICE_INTRANSITIVE),
               "無効化": ("無効にする", VOICE_ACTIVE)}
# 本身不分自他的詞元:態由受事者的助詞判
PARTICLE_VOICED = {"アップ", "ダウン"}
# なる→する 規則:N に/と なる 的字尾 → N に/と する 的字尾(態 自動)
NARU_TO_SURU = (("になる", "にする"), ("となる", "とする"))
# 有素材詞元的召喚法(正規寫法):「法(・法)*召喚の素材に/と する/なる」展開成各法的
# 法+素材にする/とする(frame-lemma-variants 票 02;リンク 由寫法歸一成 L)
MATERIAL_METHODS = ("融合", "S", "X", "L")
# なる→する 規則合併出的詞元(する 形,態 他動):規格 2026-10-27 決定(a)列的統一組——
# 倍/半分/同じ/裸 になる 與其他折疊的 N になる/となる;補語不併後的 にする/とする 也在內;
# 「法召喚の素材となる」展開後有 なる 形併進來的各法素材詞元(frame-lemma-variants 票 03)
UNIFIED_SURU = {"にする", "とする", "倍にする", "半分にする", "同じにする", "無効にする",
                "対象にする", "攻撃対象にする", "直接攻撃にする", "素材にする", "素材とする",
                "チューナーにする", "攻撃可能にする"} | {
                    method + "素材" + suru for method in MATERIAL_METHODS for _naru, suru in NARU_TO_SURU}
# 目的併入詞元:(原詞元, 目的的收尾) → 原詞元——目的清空(所有格只留子句字面;票 04)
GOAL_FOLDS = {("選択", "攻撃対象"): "攻撃対象にする"}

# ── 補語不併判準 ──
# 封閉值域(lexicon.json 的 closed 類):補語收在這些類的字面時是「值」,留目的欄
COMPLEMENT_VALUE_CLASSES = {"種族", "表示形式", "階段名", "區域名", "玩家+區域", "卡片子類型",
                            "卡種+カード", "傷害種類"}
# 屬性名詞:框架抽取的屬性主語清單(「Xが Yの N」的 X;frames.ATTR_NOUNS 取自這裡)
ATTRIBUTE_NOUNS = {"レベル", "ランク", "攻撃力", "守備力", "種族", "属性", "カード名", "数",
                   "数値", "Pスケール", "リンクマーカー", "名", "合計", "レベル・ランク",
                   "攻撃力・守備力", "種族・属性", "元々の攻撃力", "元々の守備力"}
# 補語收在屬性名詞時是「屬性」:屬性主語清單加 合計値、合計分(合計|値 兩詞連起來比)
COMPLEMENT_ATTRIBUTES = ATTRIBUTE_NOUNS | {"合計値", "合計分"}
# 補語收在這些詞時也是「值」(その効果は以下の効果となる:效果變成什麼;frame-lemma-variants 票 05)
COMPLEMENT_VALUE_HEADS = {"効果"}


def spell(action):
    """寫法歸一:全名 → 縮寫;「・」並列的召喚法鏈(約束框架的 召喚・アドバンス召喚)逐段對照。"""
    if "・" in action:
        return "・".join(spell(part) for part in action.split("・"))
    action = SPELLING.get(action, action)
    for full, short in SPELLING_PREFIXES:
        if action.startswith(full):
            return short + action[len(full):]
    return action


def fold_goal(action, goal):
    """目的併入詞元(GOAL_FOLDS;frame-lemma-variants 票 04):選択 的目的以 攻撃対象 收尾
    (攻撃対象に選択、相手モンスターの攻撃対象に選択)是 攻撃対象にする,目的清空。
    回 (原詞元, 目的)。"""
    for (folded, ending), lemma in GOAL_FOLDS.items():
        if action == folded and (goal or "").endswith(ending):
            return lemma, None
    return action, goal


def normalize(action, passive=False, has_object=False, has_subject=False):
    """原詞元 → (動作詞元, 態);態 None 是沒判。passive:述語錨點判出被動;has_object:對象欄有
    原文的 を 值;has_subject:受事者在框架自己的主語或主題(は/が)——後兩者只給 アップ/ダウン 判態。"""
    canonical, voice = spell(action), None
    if canonical in VOICE_PAIRS:
        canonical, voice = VOICE_PAIRS[canonical]
    elif canonical in PARTICLE_VOICED:
        voice = VOICE_ACTIVE if has_object else VOICE_INTRANSITIVE if has_subject else None
    else:
        for naru, suru in NARU_TO_SURU:
            if canonical.endswith(naru):
                canonical, voice = canonical[:-len(naru)] + suru, VOICE_INTRANSITIVE
                break
        else:
            if canonical in UNIFIED_SURU:
                voice = VOICE_ACTIVE
    if passive:
        voice = VOICE_PASSIVE
    return canonical, voice
