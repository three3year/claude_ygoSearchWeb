# 中鍵快速捲動卡頓 — 診斷紀錄(2026-08-17)

症狀:結果頁按滑鼠中鍵快速滾動時一卡一卡。

回饋迴圈:`scroll-jank-loop.js`——headful Chrome + CDP 送真的中鍵事件觸發
**原生 autoscroll**(主執行緒驅動,與使用者同一條路),CDN 卡圖攔截改為本地
固定圖+40ms 固定延遲(釘死網路變因),CPU 8x 節流放大訊號;量 rAF 幀間隔,
長幀(>33.4ms)比例 >8% 即紅。標準指令:

    node scroll-jank-loop.js --browser=chrome --per=100 --runs=5 --cpu=8

量測結果(中位數長幀比例,cpu=8x):

| 情境 | 長幀比例 |
|---|---|
| 修正前(lazy) | **10.0%(紅)** |
| 對照組:全 eager | 4.5% |
| `decoding="async"`(採用) | **5.9%(綠)** |
| 再加 `content-visibility: auto`(撤回) | 11.4%,p95 飆到 ~100–130ms |

結論:
- 成因是懶載入圖片在捲動途中「抵達→解碼→重繪」佔用主執行緒;`decoding="async"`
  把解碼移出繪製幀後掉幀近乎砍半、貼近 eager 地板。真實條件(CPU 不節流+真實
  CDN 冷載)下修正後為 0.0%。
- `content-visibility: auto` **反而更糟**:快速捲動時每張卡變成進視窗當下才
  render,主執行緒吃進 100–200ms 的大塊工作。已撤回並在 style.css 留註。
- 迴圈在乾淨瀏覽器+此機器上重現不了使用者原始強度的卡頓(1x 全綠),8x 節流是
  站在使用者環境放大器(Edge 本尊的擴充/分頁負載,企業政策擋住無法自動化)的
  替身。若修正後實際使用仍卡,請用 Edge InPrivate(停用擴充)重試一次以分辨
  頁面因素與環境因素。
- 迴歸測試接縫:`script/web/frontend_harness.js` 是 node:vm 沙箱、無渲染管線,
  量不到捲動掉幀——本迴圈就是這個 bug 的迴歸測試,無法收進單元測試。
