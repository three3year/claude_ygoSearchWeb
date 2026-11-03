# 02: 鎖住的欄——區域欄打通,含網址讀回

**What to build:** 站主點 破壊@相手フィールド、特殊召喚←墓地、加える:デッキ→手札 這類條件葉加的標籤,打開抽屜:鎖住的區域欄只留一行、列出鎖住的項、按不掉、滑鼠停上去說「由 X 決定」;其他欄只列「詞元+鎖住的欄」出現過的值,被細分條件擋掉的灰鈕不再出現。重整或貼網址後照規格的規則仍鎖。見規格 Solution 2〜6 與 Implementation Decisions「條件模型」「抽屜畫面」。

**Blocked by:** None (can start immediately)

**Status:** resolved

- [x] 條件模型定出標籤的鎖住的欄:來源那一列述詞中詞元、極性以外的欄;沒有來源或來源列沒有這種欄時沒有
- [x] 對鎖住的欄 `addValue`、`removeValue`、`toggleValue` 回傳原標籤
- [x] 抽屜選項:鎖住的區域欄只帶鎖住的項並標明鎖住、帶來源名字;不帶玩家、區域選單
- [x] 隱藏名單用 詞元 + 鎖住的欄(三個位置、三種極性)問引擎;沒有鎖住欄的標籤和現在一樣;灰色判定不變
- [x] 抽屜畫面:鎖住的區域欄畫一行(欄名 + 值,樣式同按不掉的鈕、不可按、項不帶 ×),說明「由 X 決定」
- [x] 從詞元節點加、改成和條件葉一樣的標籤不鎖;還原、切換包含/排除不影響鎖
- [x] 讀網址:欄位等於條件葉時鎖(只寫路徑與寫欄位對都一樣)、另加一欄時不鎖、只差位置時仍鎖;舊網址照樣讀得進來
- [x] 條件模型接縫的測試(手寫小框表;先例:drawer-options、drawer-regions 測試檔)涵蓋上面各條;node 測試全過

## Comments

- 2026-11-03 交件(7f4a663):鎖住的欄的判定在 `Cond.lockedPred(標籤)`(來源那一列述詞去掉詞元、極性;`isLockedField` 讀它),對所有欄通用——改值回原標籤、隱藏名單已涵蓋否定形與中心詞欄;抽屜選項只有區域欄回鎖住的形狀(`LOCKED_OPTIONS = { region }`,`{field, kind, lock, items}`),Strip 的 `lockedHtml` 照 `lock` 畫、`LOCKED_ITEM_TEXT` 只有 region。票 03 補 `LOCKED_OPTIONS` 的 values、text 與 `LOCKED_ITEM_TEXT` 即可;在那之前否定形與中心詞欄照常畫,但按了不變。
- 測試:新 `script/web/drawer-lock.test.js` 9 例;`field-pairs.test.js` 三例原本改 特殊召喚←墓地 的來源欄(現在鎖住),改從欄位相同、沒有來源的標籤起。node 394 全過。`drawer_browser.js` 桌面與手機走 破壊@相手フィールド:可按的鈕都有卡、console 錯誤 0,唯一違規是舊工具預期鎖住鈕的提示「至少要留一個」,新提示「由 X 決定」,工具留給票 04 更新。
