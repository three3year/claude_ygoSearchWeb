"""X素材的查詢層與反向檢查斷言:輸入真實卡的官方 DB 文本與卡片參數,看查詢結果。

只驗接縫一(查詢判斷)與接縫二(反向檢查),不驗結構內部的格。
"""
import unittest

from action_query import run_query
from card_structure import build_structures
from reverse_check import check_card
from test_golden import SPELL, card, faq

SITRIS = 1688285   # シトリスの蟲惑魔(その内の１体をこのカードのX素材とする)
SITRIS_TEXT = (
    "レベル４モンスター×２\nこのカード名の②③の効果はそれぞれ１ターンに１度しか使用できない。\n"
    "①：X素材を持っているこのカードは、このカードがX素材としているモンスターと同じ種族のモンスター"
    "（このカードを除く）が発動した効果及び罠カードの効果を受けない。\n"
    "②：このカードのX素材を１つ取り除いて発動できる。デッキから「蟲惑魔」モンスター１体を手札に加える。\n"
    "③：元々の持ち主が相手となるモンスターが効果で、墓地へ送られた場合または表側で除外された場合に"
    "発動できる。その内の１体をこのカードのX素材とする。")
SITRIS_ATTACH = "その内の１体をこのカードのX素材とする"
ZENMAICON = 1735088   # 発条補修ゼンマイコン(このカードをそのモンスターの下に重ねてX素材とする)
ZENMAICON_TEXT = (
    "「ゼンマイ」モンスター２体\nこのカード名の①②の効果はそれぞれ１ターンに１度しか使用できない。"
    "①：このカードがリンク召喚に成功した場合に発動できる。デッキから「ゼンマイ」カード１枚を手札に加える。"
    "②：自分フィールドの表側表示の「ゼンマイ」モンスター１体を裏側表示で除外して発動できる。"
    "それと同名のモンスター１体をデッキから特殊召喚する。③：このカードが破壊され墓地へ送られた場合、"
    "自分フィールドの「ゼンマイ」Xモンスター１体を対象として発動できる。"
    "このカードをそのモンスターの下に重ねてX素材とする。")
ZENMAICON_ATTACH = "このカードをそのモンスターの下に重ねてX素材とする"
RAIZEOL_DUO_DRIVE = 7511613   # ライゼオル・デュオドライブ(自分の墓地の「ライゼオル」モンスター１体をこのカードのX素材とする)
RAIZEOL_DUO_DRIVE_TEXT = (
    "レベル４モンスター×２体以上\nこのカード名の①③の効果はそれぞれ１ターンに１度しか使用できない。\n"
    "①：このカードが特殊召喚した場合に発動できる。自分の墓地の「ライゼオル」モンスター１体をこのカードの"
    "X素材とする。\n②：このカードのX素材の数×１００だけ、自分フィールドのモンスターの攻撃力はアップし、"
    "相手フィールドのモンスターの攻撃力はダウンする。\n③：自分メインフェイズに発動できる。"
    "自分フィールドのX素材を２つ取り除き、デッキから「ライゼオル」カード２枚を手札に加える"
    "（同名カードは１枚まで）。")
RAIZEOL_ATTACH = "自分の墓地の「ライゼオル」モンスター１体をこのカードのX素材とする"
CODE_MAGICIAN = 64865   # サイバース・コード・マジシャン(XをYのL素材とする場合;手札のこのカードもL素材にできる)
CODE_MAGICIAN_TEXT = (
    "「サイバネット・リチューアル」により降臨\nこのカード名の①②の効果はそれぞれ１ターンに１度しか使用できない。\n"
    "①：自分フィールドのLモンスターをサイバース族LモンスターのL素材とする場合、手札のこのカードもL素材にできる。\n"
    "②：このカードが手札・フィールドから墓地へ送られた場合に発動できる。デッキからサイバース族モンスター１体を"
    "墓地へ送る。儀式召喚したこのカードが墓地へ送られていた場合、デッキから墓地へ送らず特殊召喚する事もできる。"
    "このターン、自分はサイバース族モンスターしか特殊召喚できない。")
CODE_MAGICIAN_CONDITION = "自分フィールドのLモンスターをサイバース族LモンスターのL素材とする場合"
CODE_MAGICIAN_PERMISSION = "手札のこのカードもL素材にできる"
RUBICANTE = 734741   # 彼岸の悪鬼 ラビキャント(召喚條件區塊:このカードをS素材とする場合)
RUBICANTE_TEXT = (
    "「彼岸の悪鬼 ラビキャント」の①の効果は１ターンに１度しか使用できない。このカードをS素材とする場合、"
    "「彼岸」モンスターのS召喚にしか使用できない。①：自分フィールドに魔法・罠カードが存在しない場合に"
    "発動できる。このカードを手札から特殊召喚する。②：自分フィールドに「彼岸」モンスター以外のモンスターが"
    "存在する場合にこのカードは破壊される。")
RUBICANTE_PROCEDURE = "このカードをS素材とする場合"
HOODY = 1410324   # トリックスター・フーディ(「トリックスター」LモンスターのL素材として墓地へ送られた場合)
HOODY_TEXT = (
    "このカード名の①②の効果はそれぞれ１ターンに１度しか使用できない。\n"
    "①：自分フィールドに「トリックスター」融合・Lモンスターのいずれかが存在する場合に発動できる。"
    "このカードを手札から特殊召喚する。\n②：このカードが「トリックスター」LモンスターのL素材として"
    "墓地へ送られた場合に発動できる。デッキから「トリックスター・フュージョン」か"
    "「トリックスター・ディフュージョン」１枚を手札に加える。")
HOODY_SENT = "このカードが「トリックスター」LモンスターのL素材として墓地へ送られた場合"
CROWLEY = 875572   # 天賦の魔導士クロウリー(〜を融合素材とし、〜を融合召喚する)
CROWLEY_TEXT = (
    "このカード名の①②の効果はそれぞれ１ターンに１度しか使用できない。\n"
    "①：このカードがドロー以外の方法で手札に加わった場合に発動できる。このカードを特殊召喚する。\n"
    "②：このカードが召喚・特殊召喚した場合に発動できる。自分の手札・フィールドのモンスターを融合素材とし、"
    "「マギストス」融合モンスターか「召喚獣」融合モンスター１体を融合召喚する。\n"
    "③：フィールドの表側表示のこのカードを融合素材とする場合、カード名を「召喚師アレイスター」として"
    "扱う事ができる。")
CROWLEY_FUSION = ("自分の手札・フィールドのモンスターを融合素材とし、「マギストス」融合モンスターか"
                  "「召喚獣」融合モンスター１体を融合召喚する")
LUCIFER = 4167084   # 黎明の堕天使ルシフェル(「X」を素材としてこのカードが融合召喚に成功した場合)
LUCIFER_TEXT = (
    "天使族・闇属性モンスター×３\nこのカード名の①③の効果は１ターンに１度、いずれか１つしか使用できない。"
    "①：「堕天使ルシフェル」を素材としてこのカードが融合召喚に成功した場合に発動できる。"
    "相手フィールドのカードを全て破壊する。②：このカードがモンスターゾーンに存在する限り、"
    "自分フィールドの天使族モンスターは相手の効果の対象にならない。③：自分・相手のメインフェイズに"
    "１０００LPを払って発動できる。自分の手札・墓地から天使族モンスター１体を選んで守備表示で特殊召喚する。")
LUCIFER_FUSED = "「堕天使ルシフェル」を素材としてこのカードが融合召喚に成功した場合"
FALLEN_LUCIFER = 25451652   # 堕天使ルシフェル(素材代入用)
ASOPHIEL = 41524885   # エクソシスター・アソフィール(このカードが「X」モンスターを素材としてX召喚した場合)
ASOPHIEL_TEXT = (
    "レベル４モンスター×２\nこのカード名の①③の効果はそれぞれ１ターンに１度しか使用できない。\n"
    "①：このカードが「エクソシスター」モンスターを素材としてX召喚した場合に発動できる。"
    "このターン、お互いに墓地のカードの効果を発動できない。\n"
    "②：フィールドのこのカードは墓地から特殊召喚されたモンスターが発動した効果では破壊されない。\n"
    "③：このカードのX素材を１つ取り除き、相手フィールドのモンスター１体を対象として発動できる。"
    "そのモンスターを手札に戻す。")
ASOPHIEL_SUMMONED = "このカードが「エクソシスター」モンスターを素材としてX召喚した場合"
STACK_REVIVER = 9523599   # スタック・リバイバー(このカードを素材としてリンク召喚した場合)
STACK_REVIVER_TEXT = (
    "このカード名の効果はデュエル中に１度しか使用できない。①：このカードを素材としてリンク召喚した場合、"
    "このカード以外の自分の墓地の、そのリンク召喚の素材としたレベル４以下のサイバース族モンスター１体を"
    "対象として発動できる。そのモンスターを守備表示で特殊召喚する。")
STACK_REVIVER_USED = "このカードを素材としてリンク召喚した場合"
PSY_CIRCUIT = 575512   # ＰＳＹフレーム・サーキット(〜モンスターのみをS素材としてS召喚する)
PSY_CIRCUIT_TEXT = (
    "①：自分フィールドに「PSYフレーム」モンスターが特殊召喚された場合に発動できる。"
    "自分フィールドの「PSYフレーム」モンスターのみをS素材としてS召喚する。"
    "②：自分の「PSYフレーム」モンスターが相手モンスターと戦闘を行うダメージステップ開始時に、"
    "手札の「PSYフレーム」モンスター１体を捨てて発動できる。その戦闘を行う自分のモンスターの攻撃力は"
    "ターン終了時まで、この効果を発動するために捨てたモンスターの攻撃力分アップする。")
PSY_CIRCUIT_SYNCHRO = "自分フィールドの「PSYフレーム」モンスターのみをS素材としてS召喚する"
TEMPLE_GUARDIAN = 96687733   # 神殿の守護神(標準卡:融合素材とし、/融合素材とする場合/〜も融合素材とする事ができる)
TEMPLE_GUARDIAN_TEXT = (
    "このカード名の②の効果は１ターンに１度しか使用できない。\n"
    "①：自分の手札・フィールドのモンスターを融合素材とし、地属性の融合モンスター１体を融合召喚する。"
    "「王家の神殿」のカード名が記された自分フィールドのモンスターを融合素材とする場合、"
    "相手フィールドの表側表示モンスターも融合素材とする事ができる。\n"
    "②：自分フィールドに「王家の神殿」が存在する場合、墓地のこのカードを除外して発動できる。"
    "デッキから「神の怒り」１枚を手札に加える。")
TEMPLE_FUSION = "自分の手札・フィールドのモンスターを融合素材とし、地属性の融合モンスター１体を融合召喚する"
TEMPLE_CONDITION = "「王家の神殿」のカード名が記された自分フィールドのモンスターを融合素材とする場合"
TEMPLE_ALSO = "相手フィールドの表側表示モンスターも融合素材とする事ができる"
XYZ_REBORN = 26708437   # エクシーズ・リボーン(標準卡:このカードを下に重ねてX素材とする,沒寫所屬卡)
XYZ_REBORN_TEXT = ("①：自分の墓地のXモンスター１体を対象として発動できる。"
                   "そのモンスターを特殊召喚し、このカードを下に重ねてX素材とする。")
XYZ_REBORN_ATTACH = "このカードを下に重ねてX素材とする"
DOYON = 88413677   # ドヨン＠イグニスター(標準卡:サイバース族リンクモンスターのリンク素材として墓地へ送られた場合)
DOYON_TEXT = (
    "このカード名の①②の効果はそれぞれ１ターンに１度しか使用できない。①：このカードが召喚・特殊召喚に"
    "成功した場合、自分の墓地の「＠イグニスター」モンスター１体を対象として発動できる。"
    "そのモンスターを手札に加える。②：このカードがサイバース族リンクモンスターのリンク素材として"
    "墓地へ送られた場合、自分の墓地の「Ai」魔法・罠カード１枚を対象として発動できる。"
    "そのカードを手札に加える。")
DOYON_SENT = "このカードがサイバース族リンクモンスターのリンク素材として墓地へ送られた場合"
BAHAMUT_SHARK = 21044178   # 深淵に潜む者(このカードが水属性モンスターをX素材としている場合)
BAHAMUT_SHARK_TEXT = (
    "レベル４モンスター×２\n①：このカードが水属性モンスターをX素材としている場合、"
    "自分フィールドの水属性モンスターの攻撃力は５００アップする。\n"
    "②：自分・相手ターンに１度、このカードのX素材を１つ取り除いて発動できる。"
    "このターン、相手は墓地のカードの効果を発動できない。")
BAHAMUT_SHARK_BOOST = ("このカードが水属性モンスターをX素材としている場合、"
                       "自分フィールドの水属性モンスターの攻撃力は５００アップする")
FUTURE_FUSION_NOVA = 92058902   # 未来融合－フューチャー・フュージョン・ノヴァ(左半的素材解不出)
FUTURE_FUSION_NOVA_TEXT = (
    "このカード名のカードは１ターンに１枚しか発動できない。\n"
    "①：このカードの発動時の効果処理として、「サイバー・ドラゴン」を含む自分のデッキのモンスターを"
    "融合素材とし、機械族・光属性の融合モンスター１体を融合召喚する。"
    "このカードがフィールドから離れる時にそのモンスターは破壊される。"
    "そのモンスターが破壊される時にこのカードは破壊される。"
    "このカードの発動後、ターン終了時まで自分は、機械族モンスターしか特殊召喚できず、"
    "この効果で特殊召喚したモンスターでしか攻撃宣言できない。")
FUSION_MONSTER = 0x61
ARCHETYPES = [
    {"setcode": 0x135, "hex": "0x135", "names_ja": ["＠イグニスター"], "name_zh": "@伊格尼斯者",
     "source": "strings.conf"},
    {"setcode": 0x136, "hex": "0x136", "names_ja": ["Ａｉ"], "name_zh": "A.i.",
     "source": "strings.conf"},
    {"setcode": 0x150, "hex": "0x150", "names_ja": ["マギストス"], "name_zh": "偉魔",
     "source": "strings.conf"},
    {"setcode": 0xf4, "hex": "0xf4", "names_ja": ["召喚獣"], "name_zh": "召喚獸",
     "source": "strings.conf"},
    {"setcode": 0x172, "hex": "0x172", "names_ja": ["エクソシスター"], "name_zh": "驅魔修女",
     "source": "strings.conf"},
    {"setcode": 0xc1, "hex": "0xc1", "names_ja": ["PSYフレーム"], "name_zh": "PSY骨架",
     "source": "strings.conf"},
    {"setcode": 0xfb, "hex": "0xfb", "names_ja": ["トリックスター"], "name_zh": "花樣明星",
     "source": "strings.conf"},
    {"setcode": 0xb1, "hex": "0xb1", "names_ja": ["彼岸"], "name_zh": "彼岸",
     "source": "strings.conf"},
    {"setcode": 0x108a, "hex": "0x108a", "names_ja": ["蟲惑魔"], "name_zh": "蟲惑魔",
     "source": "strings.conf"},
    {"setcode": 0x58, "hex": "0x58", "names_ja": ["ゼンマイ"], "name_zh": "發條",
     "source": "strings.conf"},
    {"setcode": 0x1be, "hex": "0x1be", "names_ja": ["ライゼオル"], "name_zh": "雷熱渦爐",
     "source": "strings.conf"},
]
XYZ_MONSTER = 0x800021
LINK_MONSTER = 0x4000021
CYBERSE = 0x1000000


class MaterialFixture(unittest.TestCase):
    """固定夾:各種「素材」寫法的真實卡。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = [
            card(SITRIS, name_ja="シトリスの蟲惑魔", type=XYZ_MONSTER, level=4, race=0x400,
                 attribute=0x1, atk=2500, setcode=0x108a),
            card(ZENMAICON, name_ja="発条補修ゼンマイコン", type=LINK_MONSTER, level=2, race=0x20,
                 attribute=0x10, atk=1800, setcode=0x58),
            card(RAIZEOL_DUO_DRIVE, name_ja="ライゼオル・デュオドライブ", type=XYZ_MONSTER, level=4,
                 race=0x1000, attribute=0x4, atk=2500, setcode=0x1be),
            card(1001, name_ja="ライゼオルの怪獸", level=4, race=0x1000, attribute=0x10,
                 setcode=0x1be),
            card(1002, name_ja="無字段的怪獸", level=4, race=0x1, attribute=0x1),
            card(CODE_MAGICIAN, name_ja="サイバース・コード・マジシャン", type=0xa1, level=7,
                 race=CYBERSE, attribute=0x20, atk=2500, setcode=0x93),
            card(RUBICANTE, name_ja="彼岸の悪鬼 ラビキャント", type=0x1021, level=3, race=0x8,
                 attribute=0x20, atk=100, setcode=0xb1),
            card(HOODY, name_ja="トリックスター・フーディ", level=2, race=0x4, attribute=0x10,
                 atk=600, setcode=0xfb),
            card(1003, name_ja="サイバース族的連結怪獸", type=LINK_MONSTER, level=2, race=CYBERSE,
                 attribute=0x20),
            card(1004, name_ja="戰士族的連結怪獸", type=LINK_MONSTER, level=2, race=0x1,
                 attribute=0x20),
            card(CROWLEY, name_ja="天賦の魔導士クロウリー", level=4, race=0x2, attribute=0x20,
                 atk=1800, setcode=0x150),
            card(LUCIFER, name_ja="黎明の堕天使ルシフェル", type=FUSION_MONSTER, level=12, race=0x4,
                 attribute=0x20, atk=4000, setcode=0xef),
            card(FALLEN_LUCIFER, name_ja="堕天使ルシフェル", level=11, race=0x4, attribute=0x20,
                 atk=3000, setcode=0xef),
            card(ASOPHIEL, name_ja="エクソシスター・アソフィール", type=XYZ_MONSTER, level=4,
                 race=0x1, attribute=0x10, atk=2100, setcode=0x172),
            card(STACK_REVIVER, name_ja="スタック・リバイバー", level=2, race=CYBERSE,
                 attribute=0x20, atk=100),
            card(PSY_CIRCUIT, name_ja="ＰＳＹフレーム・サーキット", type=0x80002, setcode=0xc1),
            card(1005, name_ja="マギストス的融合怪獸", type=FUSION_MONSTER, level=8, race=0x2,
                 attribute=0x20, setcode=0x150),
            card(1006, name_ja="エクソシスター的怪獸", level=4, race=0x1, attribute=0x10,
                 setcode=0x172),
            card(1007, name_ja="PSYフレーム的怪獸", level=2, race=0x100000, attribute=0x10,
                 setcode=0xc1),
            card(TEMPLE_GUARDIAN, name_ja="神殿の守護神", type=SPELL),
            card(29762407, name_ja="王家の神殿", type=0x20002),
            card(22082432, name_ja="神の怒り", type=0x10002),
            card(XYZ_REBORN, name_ja="エクシーズ・リボーン", type=0x4, setcode=0x73),
            card(DOYON, name_ja="ドヨン@イグニスター", level=4, race=CYBERSE, attribute=0x20,
                 atk=400, setcode=0x135),
            card(BAHAMUT_SHARK, name_ja="深淵に潜む者", type=XYZ_MONSTER, level=4, race=0x40000,
                 attribute=0x2, atk=1700),
            card(1008, name_ja="地屬性的融合怪獸", type=FUSION_MONSTER, level=6, race=0x1,
                 attribute=0x1),
            card(FUTURE_FUSION_NOVA, name_ja="未来融合－フューチャー・フュージョン・ノヴァ",
                 type=0x20002, setcode=0x46),
            card(70095154, name_ja="サイバー・ドラゴン", level=5, race=0x20, attribute=0x10,
                 atk=2100, setcode=0x1093),
        ]
        cls.faq = [
            faq(FUTURE_FUSION_NOVA, "未来融合－フューチャー・フュージョン・ノヴァ",
                FUTURE_FUSION_NOVA_TEXT),
            faq(TEMPLE_GUARDIAN, "神殿の守護神", TEMPLE_GUARDIAN_TEXT),
            faq(XYZ_REBORN, "エクシーズ・リボーン", XYZ_REBORN_TEXT),
            faq(DOYON, "ドヨン＠イグニスター", DOYON_TEXT),
            faq(BAHAMUT_SHARK, "深淵に潜む者", BAHAMUT_SHARK_TEXT),
            faq(CROWLEY, "天賦の魔導士クロウリー", CROWLEY_TEXT),
            faq(LUCIFER, "黎明の堕天使ルシフェル", LUCIFER_TEXT),
            faq(ASOPHIEL, "エクソシスター・アソフィール", ASOPHIEL_TEXT),
            faq(STACK_REVIVER, "スタック・リバイバー", STACK_REVIVER_TEXT),
            faq(PSY_CIRCUIT, "ＰＳＹフレーム・サーキット", PSY_CIRCUIT_TEXT),
            faq(CODE_MAGICIAN, "サイバース・コード・マジシャン", CODE_MAGICIAN_TEXT),
            faq(RUBICANTE, "彼岸の悪鬼 ラビキャント", RUBICANTE_TEXT),
            faq(HOODY, "トリックスター・フーディ", HOODY_TEXT),
            faq(SITRIS, "シトリスの蟲惑魔", SITRIS_TEXT),
            faq(ZENMAICON, "発条補修ゼンマイコン", ZENMAICON_TEXT),
            faq(RAIZEOL_DUO_DRIVE, "ライゼオル・デュオドライブ", RAIZEOL_DUO_DRIVE_TEXT),
        ]
        cls.structures, cls.report = build_structures(cls.cards, cls.faq, archetypes=ARCHETYPES)

    def run_query(self, **query):
        return run_query(self.structures, self.cards, query)

    def hits(self, **query):
        return [hit["id"] for hit in self.run_query(**query)["hits"]]

    def hit_texts(self, cid, **query):
        """那張卡的命中段原文;沒命中回空列表。"""
        structure = next(c for c in self.structures if c["id"] == cid)
        texts = {seg["id"]: seg["text"] for block in structure["blocks"]
                 for seg in block["segments"]}
        return [texts[seg_id] for hit in self.run_query(**query)["hits"] if hit["id"] == cid
                for seg_id in hit["segments"]]

    def failures(self, cid):
        """那張卡反向檢查不通過的段原文(段外殘留等沒有段的記 None)。"""
        structure = next(c for c in self.structures if c["id"] == cid)
        texts = {seg["id"]: seg["text"] for block in structure["blocks"]
                 for seg in block["segments"]}
        return [texts.get(f["segment"]) for f in check_card(structure)]


class AttachAsXyzMaterialTest(MaterialFixture):
    """效果把卡疊成超量素材是動作詞 成為超量素材,和召喚用的 作為素材 分開(spec 故事 11、12)。"""

    def test_attach_to_this_card_hits_become_xyz_material(self):
        """ライゼオル・デュオドライブ「自分の墓地の「ライゼオル」モンスター１体をこのカードのX素材とする」:
        查「成為超量素材」命中。"""
        self.assertEqual(self.hit_texts(RAIZEOL_DUO_DRIVE, actions=["成為超量素材"]), [RAIZEOL_ATTACH])

    def test_unresolved_object_lists_the_attach_segment_as_unparsed(self):
        """シトリスの蟲惑魔「その内の１体をこのカードのX素材とする」:「その内の１体」指回的那一群在解析不出的
        條件段裡,這一段判不了——查「成為超量素材」時列在未解析組(字面比得中),查「作為素材」時不列這一段。"""
        result = self.run_query(actions=["成為超量素材"])
        self.assertNotIn(SITRIS, [hit["id"] for hit in result["hits"]])
        listed = next(u for u in result["unparsed"] if u["id"] == SITRIS)
        self.assertEqual([s["text"] for s in listed["segments"]], [SITRIS_ATTACH])
        as_material = self.run_query(actions=["作為素材"], include_condition=True)
        self.assertNotIn(SITRIS_ATTACH, [s["text"] for u in as_material["unparsed"]
                                         if u["id"] == SITRIS for s in u["segments"]])

    def test_stack_under_a_monster_hits_become_xyz_material(self):
        """発条補修ゼンマイコン「このカードをそのモンスターの下に重ねてX素材とする」:查「成為超量素材」命中,
        指定此卡當物件也命中。"""
        self.assertEqual(self.hit_texts(ZENMAICON, actions=["成為超量素材"]), [ZENMAICON_ATTACH])
        self.assertEqual(self.hit_texts(ZENMAICON, actions=["成為超量素材"], card=ZENMAICON),
                         [ZENMAICON_ATTACH])

    def test_attach_is_not_use_as_material(self):
        """查「作為素材」不命中上面兩段,也不把它們列進未解析組。"""
        result = self.run_query(actions=["作為素材"], include_condition=True)
        for cid in (SITRIS, ZENMAICON):
            self.assertNotIn(cid, [hit["id"] for hit in result["hits"]])
        self.assertNotIn(ZENMAICON, result["groups"]["未解析"])

    def test_attached_card_is_judged_by_its_condition(self):
        """ライゼオル・デュオドライブ「自分の墓地の「ライゼオル」モンスター１体をこのカードのX素材とする」:
        查「成為超量素材,從墓地」ライゼオル怪獸代入命中,別的怪獸不命中。"""
        query = {"actions": ["成為超量素材"], "from_zones": ["墓地"]}
        self.assertEqual(self.hit_texts(RAIZEOL_DUO_DRIVE, card=1001, **query), [RAIZEOL_ATTACH])
        self.assertEqual(self.hit_texts(RAIZEOL_DUO_DRIVE, card=1002, **query), [])

    def test_attach_segments_render_back(self):
        """兩種寫法(Yの、Yの下に重ねて)的段都寫得回原文。"""
        self.assertNotIn(ZENMAICON_ATTACH, self.failures(ZENMAICON))
        self.assertNotIn(RAIZEOL_ATTACH, self.failures(RAIZEOL_DUO_DRIVE))


class UseAsMaterialTest(MaterialFixture):
    """「このカードをS素材とする場合」「XをYのL素材とする場合」是條件段,動作詞 作為素材(spec 故事 13)。"""

    def test_condition_segment_hits_only_with_the_condition_switch(self):
        """サイバース・コード・マジシャン「自分フィールドのLモンスターをサイバース族LモンスターのL素材とする場合」:
        開條件段查「作為素材」命中那一段;關掉時不因那一段命中(命中的是後半的效果段)。"""
        self.assertIn(CODE_MAGICIAN_CONDITION,
                      self.hit_texts(CODE_MAGICIAN, actions=["作為素材"], include_condition=True))
        self.assertEqual(self.hit_texts(CODE_MAGICIAN, actions=["作為素材"]),
                         [CODE_MAGICIAN_PERMISSION])

    def test_material_and_summoned_monster_are_judged_separately(self):
        """同一段:被拿來當素材的是「自分フィールドのLモンスター」(任何連結怪獸代入都命中),
        要召喚的「サイバース族Lモンスター」不是這一段的對象。"""
        query = {"actions": ["作為素材"], "include_condition": True, "kinds": ["條件"]}
        self.assertEqual(self.hit_texts(CODE_MAGICIAN, card=1004, from_zones=["場上"], **query),
                         [CODE_MAGICIAN_CONDITION])
        self.assertEqual(self.hit_texts(CODE_MAGICIAN, card=1002, **query), [])

    def test_also_usable_as_material_is_optional_do(self):
        """「手札のこのカードもL素材にできる」:作為素材、可選、極性 做;查「作為素材,從手牌」此卡代入命中。"""
        self.assertEqual(self.hit_texts(CODE_MAGICIAN, actions=["作為素材"], from_zones=["手牌"],
                                        card=CODE_MAGICIAN), [CODE_MAGICIAN_PERMISSION])

    def test_summon_condition_block_is_a_procedure_hit_by_default(self):
        """彼岸の悪鬼 ラビキャント「このカードをS素材とする場合」寫在召喚條件區塊,是召喚手續段:
        不開條件段開關查「作為素材」就命中,此卡代入也命中。"""
        self.assertEqual(self.hit_texts(RUBICANTE, actions=["作為素材"]), [RUBICANTE_PROCEDURE])
        self.assertEqual(self.hit_texts(RUBICANTE, actions=["作為素材"], card=RUBICANTE),
                         [RUBICANTE_PROCEDURE])

    def test_material_conditions_render_back(self):
        """兩張卡的 作為素材 段都寫得回原文。"""
        for cid, texts in ((CODE_MAGICIAN, (CODE_MAGICIAN_CONDITION, CODE_MAGICIAN_PERMISSION)),
                           (RUBICANTE, (RUBICANTE_PROCEDURE,))):
            failed = self.failures(cid)
            for text in texts:
                self.assertNotIn(text, failed)


class MaterialInSummonSegmentTest(MaterialFixture):
    """素材寫在召喚的句子裡時是那個召喚段的角色 素材 的線,不另成段(spec 故事 14、預設 10)。"""

    def test_fusion_material_left_half_joins_the_fusion_summon_segment(self):
        """天賦の魔導士クロウリー「自分の手札・フィールドのモンスターを融合素材とし、〜を融合召喚する」:
        左半不是另一段,查「融合召喚」命中整句那一段;不是「作為素材」的段。"""
        self.assertEqual(self.hit_texts(CROWLEY, actions=["融合召喚"]), [CROWLEY_FUSION])
        self.assertEqual(self.hit_texts(CROWLEY, actions=["特殊召喚"])[-1], CROWLEY_FUSION)
        self.assertNotIn(CROWLEY_FUSION, self.hit_texts(CROWLEY, actions=["作為素材"],
                                                        include_condition=True))
        self.assertNotIn(CROWLEY_FUSION, self.failures(CROWLEY))

    def test_fused_monster_and_materials_are_both_judged(self):
        """同一段裡:被融合召喚的是「マギストス」融合怪獸(代入命中),素材是手牌、場上的怪獸
        (查「融合召喚,從手牌」任何怪獸代入命中;魔法卡代不進去)。"""
        self.assertEqual(self.hit_texts(CROWLEY, actions=["融合召喚"], card=1005), [CROWLEY_FUSION])
        self.assertEqual(self.hit_texts(CROWLEY, actions=["融合召喚"], from_zones=["手牌"],
                                        card=1002), [CROWLEY_FUSION])
        self.assertEqual(self.hit_texts(CROWLEY, actions=["融合召喚"], card=PSY_CIRCUIT), [])

    def test_unresolved_materials_do_not_take_the_summon_down(self):
        """未来融合－フューチャー・フュージョン・ノヴァ「このカードの発動時の効果処理として、〜を融合素材とし、
        機械族・光属性の融合モンスター１体を融合召喚する」:左半的素材解不出時不併段,只有左半標解析不出,
        查「融合召喚」照舊命中右半。"""
        self.assertEqual(self.hit_texts(FUTURE_FUSION_NOVA, actions=["融合召喚"]),
                         ["機械族・光属性の融合モンスター１体を融合召喚する"])

    def test_material_before_the_summoned_card(self):
        """黎明の堕天使ルシフェル「「堕天使ルシフェル」を素材としてこのカードが融合召喚に成功した場合」:
        開條件段查「融合召喚」命中,此卡(被召喚)與「堕天使ルシフェル」(素材)代入都命中,別的怪獸不命中。"""
        query = {"actions": ["融合召喚"], "include_condition": True}
        self.assertEqual(self.hit_texts(LUCIFER, **query), [LUCIFER_FUSED])
        self.assertEqual(self.hit_texts(LUCIFER, card=LUCIFER, **query), [LUCIFER_FUSED])
        self.assertEqual(self.hit_texts(LUCIFER, card=FALLEN_LUCIFER, **query), [LUCIFER_FUSED])
        self.assertEqual(self.hit_texts(LUCIFER, card=1002, **query), [])
        self.assertNotIn(LUCIFER_FUSED, self.failures(LUCIFER))

    def test_material_after_the_summoned_card(self):
        """エクソシスター・アソフィール「このカードが「エクソシスター」モンスターを素材としてX召喚した場合」:
        開條件段查「X召喚」命中,此卡與「エクソシスター」怪獸代入都命中。"""
        query = {"actions": ["X召喚"], "include_condition": True}
        self.assertEqual(self.hit_texts(ASOPHIEL, **query), [ASOPHIEL_SUMMONED])
        self.assertEqual(self.hit_texts(ASOPHIEL, card=ASOPHIEL, **query), [ASOPHIEL_SUMMONED])
        self.assertEqual(self.hit_texts(ASOPHIEL, card=1006, **query), [ASOPHIEL_SUMMONED])
        self.assertEqual(self.hit_texts(ASOPHIEL, card=1002, **query), [])
        self.assertNotIn(ASOPHIEL_SUMMONED, self.failures(ASOPHIEL))

    def test_only_materials_written(self):
        """只寫素材、沒寫誰被召喚:スタック・リバイバー「このカードを素材としてリンク召喚した場合」、
        ＰＳＹフレーム・サーキット「〜「PSYフレーム」モンスターのみをS素材としてS召喚する」。
        查那種召喚命中,素材代入命中;兩段都寫得回原文。"""
        self.assertEqual(self.hit_texts(STACK_REVIVER, actions=["L召喚"], include_condition=True,
                                        card=STACK_REVIVER), [STACK_REVIVER_USED])
        self.assertEqual(self.hit_texts(PSY_CIRCUIT, actions=["S召喚"], card=1007),
                         [PSY_CIRCUIT_SYNCHRO])
        self.assertEqual(self.hit_texts(PSY_CIRCUIT, actions=["S召喚"], card=1002), [])
        self.assertNotIn(STACK_REVIVER_USED, self.failures(STACK_REVIVER))
        self.assertNotIn(PSY_CIRCUIT_SYNCHRO, self.failures(PSY_CIRCUIT))


class SentAsMaterialTest(MaterialFixture):
    """「「X」LモンスターのL素材として墓地へ送られた」:原因 作為素材 帶被召喚怪獸的物件(spec 故事 15)。"""

    def test_sent_to_graveyard_as_link_material_hits_send(self):
        """トリックスター・フーディ:開條件段查「送墓」命中那一段,此卡代入也命中;不是「作為素材」的段。"""
        query = {"actions": ["送墓"], "include_condition": True}
        self.assertEqual(self.hit_texts(HOODY, **query), [HOODY_SENT])
        self.assertEqual(self.hit_texts(HOODY, card=HOODY, **query), [HOODY_SENT])
        self.assertEqual(self.hit_texts(HOODY, actions=["作為素材"], include_condition=True), [])

    def test_sent_as_material_renders_back(self):
        self.assertNotIn(HOODY_SENT, self.failures(HOODY))


class HeldMaterialPremiseTest(MaterialFixture):
    """「Xが「Y」をX素材としている場合」是前提(狀態),不是條件段也不是動作(spec 預設 10)。"""

    def test_held_material_premise_is_stripped_and_renders_back(self):
        """深淵に潜む者「このカードが水属性モンスターをX素材としている場合、〜攻撃力は５００アップする」:
        前提剝掉後是一個性質變更的效果段,預設就命中、那一段寫回原文相符。"""
        self.assertEqual(self.hit_texts(BAHAMUT_SHARK, actions=["性質變更"]), [BAHAMUT_SHARK_BOOST])
        self.assertNotIn(BAHAMUT_SHARK_BOOST, self.failures(BAHAMUT_SHARK))

    def test_holding_material_is_not_an_action(self):
        """持有素材不是動作:查「作為素材」「成為超量素材」不命中,也不因字面「X素材としている」列進未解析組。"""
        for action in ("作為素材", "成為超量素材"):
            result = self.run_query(actions=[action], include_condition=True)
            self.assertNotIn(BAHAMUT_SHARK, [hit["id"] for hit in result["hits"]])
            self.assertNotIn(BAHAMUT_SHARK, result["groups"]["未解析"])


class GoldenCardsTest(MaterialFixture):
    """標準卡:整張通過反向檢查,加各自的查詢斷言。"""

    def test_golden_cards_pass_reverse_check(self):
        for cid in (TEMPLE_GUARDIAN, XYZ_REBORN, DOYON, LUCIFER):
            self.assertEqual(self.failures(cid), [], cid)

    def test_temple_guardian(self):
        """神殿の守護神:①「〜を融合素材とし、〜を融合召喚する」查「融合召喚」命中(地屬性融合怪獸代入命中);
        「〜を融合素材とする場合」開條件段查「作為素材」才命中;「〜も融合素材とする事ができる」是
        作為素材、可選,預設就命中(查「作為素材,從對手場上」任何怪獸代入命中)。"""
        self.assertEqual(self.hit_texts(TEMPLE_GUARDIAN, actions=["融合召喚"], card=1008),
                         [TEMPLE_FUSION])
        self.assertEqual(self.hit_texts(TEMPLE_GUARDIAN, actions=["作為素材"]), [TEMPLE_ALSO])
        self.assertEqual(self.hit_texts(TEMPLE_GUARDIAN, actions=["作為素材"], include_condition=True),
                         [TEMPLE_CONDITION, TEMPLE_ALSO])
        self.assertEqual(self.hit_texts(TEMPLE_GUARDIAN, actions=["作為素材"], card=1002,
                                        from_zones=[{"zone": "場上", "side": "對手"}]),
                         [TEMPLE_ALSO])

    def test_xyz_reborn(self):
        """エクシーズ・リボーン「そのモンスターを特殊召喚し、このカードを下に重ねてX素材とする」:
        查「成為超量素材」此卡代入命中;查「作為素材」不命中;查「特殊召喚,從墓地」只看取對象命中前一段。"""
        self.assertEqual(self.hit_texts(XYZ_REBORN, actions=["成為超量素材"], card=XYZ_REBORN),
                         [XYZ_REBORN_ATTACH])
        self.assertEqual(self.hit_texts(XYZ_REBORN, actions=["作為素材"], include_condition=True), [])
        self.assertEqual(self.hit_texts(XYZ_REBORN, actions=["特殊召喚"], from_zones=["墓地"],
                                        targeting=True), ["そのモンスターを特殊召喚し"])

    def test_doyon(self):
        """ドヨン＠イグニスター「このカードがサイバース族リンクモンスターのリンク素材として墓地へ送られた場合」:
        開條件段查「送墓」此卡代入命中;關條件段不命中。"""
        self.assertEqual(self.hit_texts(DOYON, actions=["送墓"], include_condition=True, card=DOYON),
                         [DOYON_SENT])
        self.assertEqual(self.hit_texts(DOYON, actions=["送墓"]), [])


SACRED_TEMPEST = 4820694   # セイクリッド・テンペスト(その墓地のモンスターを、そのXモンスターの下に重ねてX素材とする)
SACRED_TEMPEST_TEXT = (
    "「セイクリッド・テンペスト」の①の効果はデュエル中に１度しか使用できない。①：自分エンドフェイズに"
    "自分フィールドのX素材を持った「セイクリッド」Xモンスター２体を対象として発動できる。"
    "そのXモンスター２体のX素材を全て取り除き、相手LPを半分にする。②：自分スタンバイフェイズに"
    "自分フィールドの「セイクリッド」Xモンスター１体と自分の墓地の「セイクリッド」モンスター１体を"
    "対象として発動できる。その墓地のモンスターを、そのXモンスターの下に重ねてX素材とする。")
SACRED_TEMPEST_ATTACH = "その墓地のモンスターを、そのXモンスターの下に重ねてX素材とする"
SACRED_ARCHETYPES = [{"setcode": 0x53, "hex": "0x53", "names_ja": ["セイクリッド"],
                      "name_zh": "星聖", "source": "strings.conf"}]
SACRED_MONSTER, SACRED_XYZ, PLAIN_MONSTER = 10005001, 10005002, 10005003   # 合成卡(代入用)
BARIAN = 30761649   # 冀望郷－バリアン－(その相手モンスターをそのXモンスターの下に重ねてX素材とする)
BARIAN_TEXT = (
    "このカード名はルール上「バリアンズ」カードとしても扱う。①：自分フィールドの、「CX」モンスター、"
    "「CNo.」モンスター、「No.101」～「No.107」の「No.」モンスターは相手の効果の対象にならず、"
    "相手の効果では破壊されない。②：１ターンに１度、自分が「RUM」魔法カードの効果でXモンスターの"
    "特殊召喚に成功した場合、そのXモンスター１体と相手フィールドのモンスター１体を対象として発動できる。"
    "その相手モンスターをそのXモンスターの下に重ねてX素材とする。")
BARIAN_ATTACH = "その相手モンスターをそのXモンスターの下に重ねてX素材とする"
TWIN_HEAD_EAGLE = 19310321   # 紋章獣ツインヘッド・イーグル(所屬卡的回指指不回)
TWIN_HEAD_EAGLE_TEXT = (
    "墓地のこのカードをゲームから除外し、自分フィールド上のエクシーズ素材の無いエクシーズモンスター１体と、"
    "自分の墓地の「紋章獣」と名のついたモンスター２体を選択して発動できる。"
    "選択した墓地のモンスターを、選択したエクシーズモンスターの下に重ねてエクシーズ素材とする。"
    "「紋章獣ツインヘッド・イーグル」の効果は１ターンに１度しか使用できない。")
TWIN_HEAD_EAGLE_ATTACH = "選択した墓地のモンスターを、選択したエクシーズモンスターの下に重ねてエクシーズ素材とする"
HERALDIC_ARCHETYPES = [{"setcode": 0x76, "hex": "0x76", "names_ja": ["紋章獣"],
                        "name_zh": "紋章獸", "source": "strings.conf"}]


def attach_fixture(cid, name, text, archetypes=()):
    cards = [card(cid, name_ja=name, type=SPELL),
             card(SACRED_MONSTER, name_ja="聖", setcode=0x53),
             card(SACRED_XYZ, name_ja="聖X", type=XYZ_MONSTER, setcode=0x53),
             card(PLAIN_MONSTER, name_ja="凡")]
    structures, _ = build_structures(cards, [faq(cid, name, text)], list(archetypes))
    return cards, structures, next(s for s in structures if s["id"] == cid)


def attach_hits(cards, structures, own, **query):
    result = run_query(structures, cards, {"actions": ["成為超量素材"], **query})
    ids = next((h["segments"] for h in result["hits"] if h["id"] == own["id"]), [])
    return [s["text"] for b in own["blocks"] for s in b["segments"] if s["id"] in ids]


def failed_texts(own):
    texts = {s["id"]: s["text"] for b in own["blocks"] for s in b["segments"]}
    return [texts.get(f["segment"]) for f in check_card(own)]


class StackUnderTheRestatedXyzMonsterTest(unittest.TestCase):
    """「XをそのXモンスターの下に重ねてX素材とする」:所屬卡是「そのXモンスター」指回的那一隻
    (先前寫明是Xモンスター的物件),不是被疊的 X 自己。"""

    def test_sacred_tempest_stacks_the_graveyard_monster_under_the_xyz_monster(self):
        """セイクリッド・テンペスト ②:被疊的是墓地的「セイクリッド」怪獸(代入它命中,別的怪獸不命中);
        所屬卡指回場上的「セイクリッド」Xモンスター,那一段寫回原文相符。"""
        cards, structures, own = attach_fixture(SACRED_TEMPEST, "セイクリッド・テンペスト",
                                                SACRED_TEMPEST_TEXT, SACRED_ARCHETYPES)
        self.assertEqual(attach_hits(cards, structures, own, card=SACRED_MONSTER,
                                     from_zones=["墓地"]), [SACRED_TEMPEST_ATTACH])
        self.assertEqual(attach_hits(cards, structures, own, card=PLAIN_MONSTER), [])
        self.assertNotIn(SACRED_TEMPEST_ATTACH, failed_texts(own))

    def test_barian_stacks_the_opponent_monster_under_the_summoned_xyz_monster(self):
        """冀望郷－バリアン－ ②「その相手モンスターをそのXモンスターの下に重ねてX素材とする」:所屬卡指回
        條件裡被特殊召喚的Xモンスター;那一段寫回原文相符,被疊的是對手場上的怪獸。"""
        cards, structures, own = attach_fixture(BARIAN, "冀望郷－バリアン－", BARIAN_TEXT)
        self.assertEqual(attach_hits(cards, structures, own, card=PLAIN_MONSTER,
                                     from_zones=[{"zone": "場上", "side": "對手"}]),
                         [BARIAN_ATTACH])
        self.assertNotIn(BARIAN_ATTACH, failed_texts(own))

    def test_owner_reference_that_only_finds_the_stacked_card_is_unresolved(self):
        """紋章獣ツインヘッド・イーグル「選択した墓地のモンスターを、選択したエクシーズモンスターの下に
        重ねてエクシーズ素材とする」:先前的「エクシーズ素材の無いエクシーズモンスター」修飾語認不得,
        「選択したエクシーズモンスター」指不回它——不當成指向被疊的墓地怪獸自己:查「成為超量素材」
        不命中,列進未解析組。"""
        cards, structures, own = attach_fixture(TWIN_HEAD_EAGLE, "紋章獣ツインヘッド・イーグル",
                                                TWIN_HEAD_EAGLE_TEXT, HERALDIC_ARCHETYPES)
        result = run_query(structures, cards, {"actions": ["成為超量素材"]})
        self.assertNotIn(TWIN_HEAD_EAGLE, [hit["id"] for hit in result["hits"]])
        self.assertEqual(
            [(u["id"], [s["text"] for s in u["segments"]]) for u in result["unparsed"]
             if u["segments"]],
            [(TWIN_HEAD_EAGLE, [TWIN_HEAD_EAGLE_ATTACH])])


if __name__ == "__main__":
    unittest.main()
