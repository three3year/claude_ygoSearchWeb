"""查詢判斷(純函式):全庫卡片結構 + 卡片總表 + 查詢 → 命中的卡、命中段與分組(`run_query`)。
一張卡代不代得進某物件的條件式判斷在 `condition_judge`。

查詢(spec「查詢判斷」;鍵名英文,值用 GLOSSARY 的詞):
  actions           動作詞列表,全部都要在段內
  from_zones / to_zones  區域(字串,或 {"zone", "side"}),逐條對象線比;子區域算在上位區域內
  card              指定卡(卡片密碼),代入對象物件
  this_card         這張卡自己(True):只算物件是此卡(物件0 或帶狀態的此卡)的對象線;物件是條件式、
                    這張卡剛好滿足的不算。this_card、card、condition 三者擇一,給兩個以上拋 ValueError
  condition         只給條件:卡片總表裡存在一張實卡同時滿足查詢條件與物件條件
                    (查詢側的原子不帶名稱表,直接寫值:{"op": "字段", "setcodes": [...]}、
                    {"op": "卡名"|"卡名包含"|"記載", "text": ...}、{"op": "卡名範圍", "texts": [A, B]}、
                    {"op": "屬性比較", "attr", "cmp", "value"})。
                    查詢側的卡名包含比中日英名與別名、支援 `%`,先換成卡號集合(`query_names`);
                    只有空白或 `%` 的等於沒給。卡文裡的卡名包含照舊只比日文
  targeting         True 時只算有標取對象的線;受方是被取對象的物件(裝備對象)的段也算
  kinds             段類別範圍(預設 效果、代價、召喚手續)
  block_kinds       區塊種類範圍(預設全部)
  include_condition 條件段開關(預設關)
  include_inferred  推得終點開關(預設關):推得值與繼承自推得值只在開時算
  replacement       查詢含「代替」時才看被代替段與做代替的段(帶「代替誰」的「代わりに〜」);
                    命中的被代替段在 hit 的 "replaced_by"(被代替段 id → 做代替的段 id)指出做代替的段
  polarities        極性範圍(預設只算「做」;不能、不會、可以、只能、必須要指定才算)
  generic_only      只查泛用組
  modified          被改的屬性:{"attr", "form", "value"} 任一子集,比段的 `modified`;
                    attr 比「段的 attr 清單含它」(「性質變更,屬性傷害,數值 0」= 全部防傷害段)

  generic_reference 泛用引用開關(預設關):開時被引用物件是泛用物件的引用節點也展開
  agent             誰:我方或對手,比段。段寫明的值相同或是雙方各自命中;沒寫時效果段、代價段、
                    召喚手續段的主動句算我方,其餘(條件段、被動句、限制段、修飾段)是不限定
  include_unrestricted 不限定開關(預設關):開時不限定的段也命中(誰沒寫、沒寫原因的被動句);
                    寫得比查詢寬的不歸它管
  recipient         受方:我方或對手,比段。只比受方是玩家的段(寫雙方各自的也算);受方是卡、
                    沒有受方的段不命中
  cause             原因:種類,或 {"kind": 種類, "side": 我方/對手},比段。寫的種類相同命中;
                    寫戰鬥或效果的查戰鬥、效果都命中,寫戰鬥以外的查效果命中;給了方時段沒寫方、
                    方相同或雙方各自命中。沒寫原因:被動句是不限定(看不限定開關),主動句不命中

結果:{"hits": [{"id", "segments", "group", "replaced_by"(有命中被代替段才有),
                "via"、"mark"(經引用組才有)}],
      "groups": {"特定", "泛用", "全部", "經引用", "未解析"}(各組是卡片密碼列表;未解析組的張數 = 長度;
                全部 = 特定 + 泛用,不含經引用),
      "unparsed": [{"id", "reason", "segments": [{"segment", "reason", "text"}]}]}

經引用組(GLOSSARY「經引用」):直接沒命中、但引用節點的候選卡在節點指定的部分命中的卡;
hit 的 `segments` 是空的,`via` 列經由的卡與它的命中段(展開到底,遇到循環就停)。

未解析組(spec「解析不出的段怎麼呈現」):不靜默略過。兩種來源:
- 整張無官方日文的卡:任何查詢都列,`reason` = 無官方日文、`segments` 為空。
- 字面含查詢動作詞、但結構不完整所以沒命中的段:段本身標解析不出,或段的對象線
  引用的物件標解析不出(指定卡代入時判不了),或所在區塊標解析不出;查詢要代入卡(指定卡、只給條件)時,
  物件數量恰好一張又有沒寫比較對象的異同原子也判不了(原因 異同判不了)。
  「字面」比的是整段原文而不是只比原述語字面:子句切錯時原述語字面也是錯的
  (「このカードが特殊召喚に成功した時、…めくる事ができる」切出的述語是「めくる…」),
  多列總比漏列好。動作詞經同義表換成述語字面(「破壞」→「破壊」)再比。
一張卡任一段命中就在命中組、不再列進未解析組;段類別、極性的篩選對未解析組同樣生效;
區塊種類被篩掉的區塊,只有種類判不出(標解析不出)的才列,因為那才可能是靜默漏掉。
未結構化的段(重複到停為止,spec 決定只寫第一輪)不是解析不出:不命中、也不列未解析組。
"""
from action_rows import index_of
from condition_judge import Judge, is_generic, objects_by_id
from effect_reference import card_references
from row_match import match_rows


def run_query(structures, cards, query):
    """全庫結構 + 卡片總表 + 查詢 → 命中結果(形狀見模組說明)。輸入在兩次呼叫之間不可就地修改。"""
    return match_rows(index_of(structures, cards), query)


def resolve_references(structures, cards):
    """建置第二輪:每個解析出的引用節點求被引用物件的候選卡(卡片總表裡滿足它條件式的卡,
    排序的卡號),被引用物件是泛用物件時節點記 `any`。就地改結構。"""
    judge = Judge(cards, structures)
    for card in structures:
        if card["unparsed"]:
            continue
        nodes = card_references(card)
        if not nodes:
            continue
        objects = objects_by_id(card)
        names = {row["id"]: row for row in card["names"]}
        for node in nodes:
            if node.get("unparsed"):
                continue
            obj = objects[node["reference"]["object"]]
            if is_generic(obj, objects):
                node["any"] = True
            node["reference"]["candidates"] = sorted(
                {entry["id"] for entry in judge.candidates(card, obj, names)})
