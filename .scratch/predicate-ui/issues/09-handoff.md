# 09: 交件

**What to build:** 整合分支上全部合併並重跑,在使用者跑的入口確認新搜尋照規格運作,文件與新介面一致,把結果交給站主。

**Blocked by:** 06, 08

**Status:** ready-for-agent

- [ ] 全套:effect-tokenize、node 測試、script/* 五套;全鏈與索引建置兩次,data.js 逐位元組相同;數字記進 Comments
- [ ] 真瀏覽器桌面與手機寬,規格 User Stories 1〜32 每條互動一次,網址貼到新分頁重開,console 無錯;偏離規格的逐條寫進 Comments
- [ ] 真瀏覽器實測 AND 1〜5 張、OR 2〜5 張的耗時與 data.js 最終體積,對照規格 Further Notes
- [ ] GLOSSARY:搜尋軸條與框架述詞條改成 AND、OR 兩區、拿掉「從空白建一個」;動作類別第三版段與軸條改成上層節點只展開;前端索引條與動作類別段拿掉舊欄與舊樹檔
- [ ] ADR-0018 Consequences 補 OR 兩區、切換完成、實測體積;README 與建置產物文件照清單更新
- [ ] 地圖 Decisions「寫規格 4」補交件註記與票 08 記下的刪除前 commit
- [ ] 分支是否併進 main 由站主決定,本票只 commit 本地,不 push
