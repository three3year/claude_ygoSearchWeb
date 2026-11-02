# 04: 中心詞只能挑清單

**What to build:** 抽屜的受事者中心詞、目的中心詞兩欄,打字只是縮小清單,只能從清單挑;清單是目前條件下有命中的全部中心詞,打了清單外的字不收。見規格「判定」段中心詞一條、「中心詞框怎麼收字?」與「條件列與抽屜」段。

**Blocked by:** 02

**Status:** resolved

- [x] 抽屜選項的中心詞欄回候選清單:其他欄成立的框上這一欄出現過的中心詞,依中心詞表順序,不含已加入的,沒有 300 個上限
- [x] 詞元在這一欄沒有任何中心詞、也沒有已加入的詞時不畫這一欄
- [x] Enter、離開框、點抽屜別的鈕時,字等於清單裡某一項才加入;否則清空框、不改標籤
- [x] 票 09 的「框裡有字時按下不搶焦點」保留:框裡是清單內的字時按抽屜別的鈕,字照樣收進去、按到的鈕照樣生效
- [x] 網址帶進來的清單外的詞照列為已加入的項、可刪
- [x] 條件模型測試:候選只含命中的、順序、不含已加入的;條件列事件測試(先例 typed_commit):清單內收、清單外不送 `onEdit` 且框被清空
- [x] 全套 node 測試通過

## Comments

- 2026-11-02 交件。node 全套 369 → 380 全過(新檔 `head-options.test.js` 8 條;`typed_commit.test.js` 夾具補 FRAMES 與中心詞表,原 7 條照過,新增 3 條:清單外的字 Enter/離開框不送 `onEdit` 且框被清空、中心詞表有但不在這張標籤清單上的字一樣不收、框裡是清單外的字時點抽屜的鈕字被清掉而鈕照樣生效;`field-pairs` 的「候選前 300 個」改成「值域是整個中心詞表」);`test_lint` 7 條全過。
- 做法:`cond.js` 的 `textOptions(tag, field)` 候選 = `Engine.fieldValues(tag.pred, field)` 去掉已加入的(引擎已依中心詞表順序解回),沒有候選也沒有已加入的詞回 null(整欄不列);網址帶進來的清單外的詞照 `Cond.values` 列為已加入的項、可刪(模型的 `orderedValues` 不查表,照收)。`HEAD_CANDIDATES = 300` 刪掉,`editor` 的中心詞欄回整個中心詞表當值域(`press_stats.js` 只讀 kind 與 values,不受影響)。`strip.js` 的 `onDrawerChange` 收中心詞前查 `candidatesOf(tag, field)`(從 `Cond.drawerOptions` 取那一欄的候選),不在清單就清空框、不呼叫 `onEdit`;票 09 的 `holdFocus`/`commitTyped` 不動,清單內的字照樣先收再做鈕的動作。
- 真資料(node,`Cond.drawerOptions` 20 次平均):特殊召喚 受事者中心詞候選 315 個(超過舊上限 300)、目的中心詞 10,約 8 ms;にする 31/62 約 2 ms;破壊 21/2 約 3.5 ms。
- 和規格的出入:無。真 Chrome 走一輪留給交件票 05。
