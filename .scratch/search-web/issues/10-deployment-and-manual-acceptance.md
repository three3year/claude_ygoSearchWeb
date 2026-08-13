# 10 — 部署形態與人工驗收

**What to build:** repo 擺成 GitHub Pages 吃得下的形狀,並把自動化測不到的那些事情
用人工走過一遍。這是上線里程碑。

GitHub Pages 以**本 repo 根目錄**為來源:根目錄放 `.nojekyll`(否則 Jekyll 會吃掉底線開頭
的檔案)與一個轉址到 `web/index.html` 的 `index.html`。沿用 oldProject 的現成做法。

**本票不含 push。** 專案規則是只 commit 本地、永不 push;推上 GitHub 由使用者手動執行
或明確授權。已知且已被接受的代價要在票的 Comments 裡再記一次,好讓按下按鈕的人看得到。

人工驗收清單涵蓋的是**自動化測不到、但壞了很明顯**的那些:DOM 渲染結果、CSS、卡圖載入、
`file://` 行為、瀏覽器歷史。這些在 ADR-0007 就講明了走人工——引入 Playwright 會推翻
零安裝原則。

**Blocked by:** 01、02、03、04、05、06、07、08、09 — 全部

**Status:** ready-for-agent

- [ ] 根目錄有 `.nojekyll`
- [ ] 根目錄 `index.html` 轉址到 `web/index.html`
- [ ] `web/data.js` 入版控(GitHub Pages 直接吃 repo 內容,產物不進版控就沒有站)
- [ ] 以本機 static server 從**根目錄**起站,走一次完整流程確認相對路徑沒有壞
- [ ] 人工驗收清單逐項勾過並記錄結果:
  - [ ] 雙擊 `web/index.html`(`file://`)可跑,不需要起 server
  - [ ] 卡圖實際顯示;隨機抽查數張確認對得上卡
  - [ ] 異圖切換實際可用(以黑魔導 `46986414` 的 17 版驗證)
  - [ ] 缺圖的卡安靜隱藏,不留破圖
  - [ ] 深色配色在實機上不刺眼,標亮與 badge 的對比足夠
  - [ ] 手機寬度版面(實機或裝置模擬)
  - [ ] 分享網址在**另一台裝置**開得起來且條件正確還原
  - [ ] 「上一頁」行為符合預期
- [ ] 首次載入時間實測並記錄(索引約 7.8 MB / gzip 1.75 MB)

## Comments

推上 GitHub 的已知代價(2026-08-13 實測),按下按鈕之前要看過:

- repo 必須公開,`data/`(33 MB)與 `.scratch/`(判定票、[[遮蔽測試]]樣本與標準答案)
  都會變成公開可下載
- `.git` 已 192 MB / 49 commit,因為[[效果標記表]]每次判定票都整檔改寫;加上每次重生的
  `web/data.js`(7.8 MB)只會更快。GitHub 對單一 repo 的軟性上限 1 GB、750 MB 開始警告

這兩點在 grilling 階段已向使用者說明並由使用者選定「本 repo 根目錄發佈」。
