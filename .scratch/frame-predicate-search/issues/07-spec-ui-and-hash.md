# 寫規格 4:介面與網址

Type: task
Mode: HITL
Status: open
Blocked by: 06, 03
Map: ../map.md

## Question

跑 `/mattpocock-skills:to-spec` 再 `/mattpocock-skills:to-tickets`(spec.md 先過 `review-mirror`)。範圍:query.js 的側欄——類別樹改為具名查詢目錄導覽,點葉填入一張述詞卡,卡上欄位可改、可加、可刪,新增空白卡,排除卡;「含代價」勾選與「動作對象」全軸 radiogroup 退場(成為卡上欄位);hash.js——沒改過的具名查詢用葉路徑、改過的展開成欄位對,多張卡、排除、多值的寫法,未知參數安靜忽略;render.js——句尾標籤與命中強調;acat.js 改讀目錄。以「述詞卡與樹導覽的靜態原型」為基礎。

to-spec 裡要順手定的細節:句尾標籤在不互斥下顯示什麼(使用者述詞命中的框、所有命中的具名查詢、或命中框的詞元)、hash 的分隔符與葉名/字面裡 › : | ; 的轉義、卡名改了之後怎麼顯示、手機寬度的摺疊。

答案記 spec.md 與 issues/ 的路徑。
