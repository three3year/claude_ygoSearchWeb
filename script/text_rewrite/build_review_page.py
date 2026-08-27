"""子批審查檔 → 網頁審核台:站主逐行審查用的單檔 HTML(text-rewrite 子批流程)。

審查檔一批 50 卡、上千行 markdown,在終端機裡逐行讀三欄對照很吃力,而站主要做
的事其實只有兩件:看清楚這一卡改了什麼、標放行或退回。本殼把審查檔原樣解析成
一頁可操作的網頁——**內容全部來自審查檔,不另抄一份**,審查檔改了重跑即可同步。

三件事是終端機給不了而這裡給得出的:

1. **字元級 diff**:新文本對照查牌網舊譯逐字標出增刪,一眼看得出這一卡到底動了
   什麼。改寫的絕大多數卡只是補圈號與發動句,diff 讓那些卡幾秒就審完,把注意力
   留給真正動了句構的少數。
2. **裁示留在頁面上**:每卡放行/退回加批註,存在瀏覽器本機,關掉再開還在;
   審完一鍵匯出成 markdown 貼回對話,不必人工謄。
3. **待裁點可篩**:審查檔裡標了「待裁」的欄位(判斷點、詞彙表殘留)在索引側欄
   可以單獨篩出來,不必從頭捲。

單檔、零外部資源(Artifact 的 CSP 下 CDN 一律連不出去),深淺色主題都調過。

用法(於 repo 任意位置執行皆可):
    python script/text_rewrite/build_review_page.py .scratch/text-rewrite/review-41-monster-02.md
    python script/text_rewrite/build_review_page.py <審查檔> --out <輸出 HTML>

產出後以 Artifact 發佈給站主審(2026-08-27 站主定案:**審查票一律附審核網頁**)。
"""
import argparse
import io
import json
import os
import re
import sys

HEAD = re.compile(r"^## (\d+)\. `(\d+)` (.+?)(?:\((.+)\))?$")
BULLET = re.compile(r"^- \*\*(.+?)\*\*(?:[:：])?(.*(?:\n(?![-#]|\n).*)*)", re.M)
WAIT_KEYS = ("待裁", "裁示", "待查")


def join_cjk(lines):
    """續行接回:兩側都是 ASCII 英數才補空格,中日文直接黏。"""
    out = ""
    for line in lines:
        piece = line.strip()
        if not piece:
            continue
        if out and (out[-1].isascii() and out[-1].isalnum()
                    and piece[0].isascii() and piece[0].isalnum()):
            out += " "
        out += piece
    return out


def rich(text):
    """極簡 markdown → HTML:粗體、行內碼、[[詞條]];連結只留文字。"""
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    text = re.sub(r"\[\[(.+?)\]\]", r'<em class="term">\1</em>', text)
    text = re.sub(r"\[(.+?)\]\((.+?)\)", r"\1", text)
    return text


def quoted(block, label):
    """`**標籤**` 後緊接的 `>` 引用區 → 行清單(空行或非引用行即止)。"""
    i = block.find("**" + label + "**")
    if i < 0:
        return []
    lines = []
    for line in block[i:].splitlines()[1:]:
        if line.startswith("> "):
            lines.append(line[2:].rstrip())
        elif line.strip() == "":
            if lines:
                break
        else:
            break
    return lines


def notes_of(block):
    """卡片小節的 `- **標籤**:內文` 條列(「審查」欄不進頁面,那是裁示欄)。"""
    notes = []
    for label, body in BULLET.findall(block):
        if label.startswith("審查"):
            continue
        items, para = [], []
        for line in body.splitlines():
            if re.match(r"^\s{2,}\d+\.\s", line):
                items.append([line.strip()])
            elif items and line.strip():
                items[-1].append(line.strip())
            else:
                para.append(line)
        notes.append({
            "label": re.sub(r"\(.*\)$", "", label).strip(),
            "flag": "待裁" if any(k in label for k in WAIT_KEYS) else "",
            "text": rich(join_cjk(para)),
            "items": [rich(join_cjk(it)) for it in items],
        })
    return notes


def parse_review(md_text):
    """審查檔全文 → 每卡的三欄、註記與狀態。

    `skipped` 認的是新文本欄寫「不進站」的卡(建議排除),與 check_draft.py
    同一條判準;`backfill` 認小節裡的遞補註記。
    """
    cards = []
    for block in re.split(r"\n(?=## \d+\. `)", md_text):
        head = HEAD.match(block.splitlines()[0])
        if not head:
            continue
        draft = quoted(block, "新文本")
        cards.append({
            "no": int(head.group(1)),
            "id": head.group(2),
            "name": head.group(3).strip(),
            "nameJa": (head.group(4) or "").strip(),
            "ja": quoted(block, "日文原文"),
            "old": quoted(block, "查牌網舊譯"),
            "draft": draft,
            "skipped": any("不進站" in line for line in draft),
            "backfill": bool(re.search(r"遞補第 \d+ 張", block)),
            "notes": notes_of(block),
        })
    return cards


def main(argv=None):
    parser = argparse.ArgumentParser(description="子批審查檔 → 網頁審核台")
    parser.add_argument("review", help="子批審查檔 md 路徑")
    parser.add_argument("--out", help="輸出 HTML 路徑 (預設與審查檔同名 .html)")
    args = parser.parse_args(argv)

    with io.open(args.review, encoding="utf-8") as f:
        cards = parse_review(f.read())
    if not cards:
        print(args.review + ":找不到 `## N. `密碼` 卡名` 的卡片小節")
        return 1

    out = args.out or os.path.splitext(args.review)[0] + ".html"
    payload = json.dumps({"cards": cards}, ensure_ascii=False).replace("<", "\\u003c")
    with io.open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(TEMPLATE.replace("__DATA__", payload))
    live = [c for c in cards if not c["skipped"]]
    wait = sum(1 for c in cards for n in c["notes"] if n["flag"])
    print("已寫出 {}:{} 卡({} 待審、{} 排除)、待裁點 {} 處".format(
        out, len(cards), len(live), len(cards) - len(live), wait))
    return 0


TEMPLATE = r'''<title>§4.1×怪獸 子批 2 審查台</title>
<style>
:root{
  --paper:#f4f6f8; --surface:#ffffff; --surface-2:#eef1f5;
  --ink:#1b1f27; --muted:#5c6472; --faint:#8b93a1;
  --rule:#dce0e7; --rule-soft:#e8ebf0;
  --accent:#96661a; --accent-soft:#f3e6cd; --accent-line:#c99a3f;
  --ok:#2c7359; --ok-soft:#dfeee8;
  --back:#a8412c; --back-soft:#f7e2dc;
  --skip:#5c6472; --skip-soft:#e6e9ee;
  --ins:#e8f0d9; --ins-ink:#3f5c1c;
  --del-ink:#EEEEEE;
  --shadow:0 1px 2px rgba(27,31,39,.06), 0 8px 24px -16px rgba(27,31,39,.28);
  --serif:"Noto Serif TC","Source Han Serif TC","Songti TC","PMingLiU",
    "MingLiU",Georgia,serif;
  --sans:"Noto Sans TC","PingFang TC","Microsoft JhengHei","Heiti TC",
    system-ui,-apple-system,"Segoe UI",sans-serif;
  --mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,monospace;
}
@media (prefers-color-scheme:dark){
  :root{
    --paper:#10131a; --surface:#181c24; --surface-2:#1f242e;
    --ink:#e6e9ee; --muted:#98a1b0; --faint:#6d7686;
    --rule:#2a303b; --rule-soft:#232935;
    --accent:#dda953; --accent-soft:#3a2f19; --accent-line:#9a7430;
    --ok:#63b596; --ok-soft:#1c3830;
    --back:#e28b74; --back-soft:#3d251e;
    --skip:#98a1b0; --skip-soft:#232935;
    --ins:#2b3a1c; --ins-ink:#b6d189;
    --del-ink:#EEEEEE;
    --shadow:0 1px 2px rgba(0,0,0,.4), 0 8px 24px -16px rgba(0,0,0,.8);
  }
}
:root[data-theme="light"]{
  --paper:#f4f6f8; --surface:#ffffff; --surface-2:#eef1f5;
  --ink:#1b1f27; --muted:#5c6472; --faint:#8b93a1;
  --rule:#dce0e7; --rule-soft:#e8ebf0;
  --accent:#96661a; --accent-soft:#f3e6cd; --accent-line:#c99a3f;
  --ok:#2c7359; --ok-soft:#dfeee8;
  --back:#a8412c; --back-soft:#f7e2dc;
  --skip:#5c6472; --skip-soft:#e6e9ee;
  --ins:#e8f0d9; --ins-ink:#3f5c1c; --del-ink:#EEEEEE;
  --shadow:0 1px 2px rgba(27,31,39,.06), 0 8px 24px -16px rgba(27,31,39,.28);
}
:root[data-theme="dark"]{
  --paper:#10131a; --surface:#181c24; --surface-2:#1f242e;
  --ink:#e6e9ee; --muted:#98a1b0; --faint:#6d7686;
  --rule:#2a303b; --rule-soft:#232935;
  --accent:#dda953; --accent-soft:#3a2f19; --accent-line:#9a7430;
  --ok:#63b596; --ok-soft:#1c3830;
  --back:#e28b74; --back-soft:#3d251e;
  --skip:#98a1b0; --skip-soft:#232935;
  --ins:#2b3a1c; --ins-ink:#b6d189; --del-ink:#EEEEEE;
  --shadow:0 1px 2px rgba(0,0,0,.4), 0 8px 24px -16px rgba(0,0,0,.8);
}

*{box-sizing:border-box}
.page{
  background:var(--paper); color:var(--ink); font-family:var(--sans);
  font-size:16px; line-height:1.75; margin:0 auto; padding:0 0 7rem;
  -webkit-font-smoothing:antialiased;
}
h1,h2,h3{font-family:var(--serif); text-wrap:balance; margin:0; font-weight:600}
code{font-family:var(--mono); font-size:.86em; background:var(--surface-2);
  padding:.08em .35em; border-radius:3px}
.term{font-style:normal; border-bottom:1px dotted var(--accent-line);
  padding-bottom:1px}

/* ── 頁首 ───────────────────────────── */
.masthead{
  border-bottom:1px solid var(--rule); background:var(--surface);
  padding:2.6rem 1.5rem 1.6rem;
}
.masthead-in{max-width:1180px; margin:0 auto;
  display:flex; flex-wrap:wrap; gap:1.5rem; align-items:flex-end;
  justify-content:space-between}
.eyebrow{
  font-family:var(--mono); font-size:.72rem; letter-spacing:.16em;
  text-transform:uppercase; color:var(--accent); margin-bottom:.5rem;
}
.masthead h1{font-size:clamp(1.6rem,3.4vw,2.3rem); line-height:1.3}
.masthead .sub{color:var(--muted); font-size:.92rem; margin-top:.4rem}
.progress-wrap{min-width:230px}
.progress-nums{display:flex; align-items:baseline; gap:.4rem;
  font-family:var(--mono); font-variant-numeric:tabular-nums}
.progress-nums b{font-size:1.9rem; font-weight:600; letter-spacing:-.02em}
.progress-nums span{color:var(--muted); font-size:.85rem}
.bar{height:6px; border-radius:3px; background:var(--surface-2);
  margin-top:.55rem; overflow:hidden; display:flex}
.bar i{display:block; height:100%}
.bar .b-ok{background:var(--ok)} .bar .b-back{background:var(--back)}

/* ── 摘要 ───────────────────────────── */
.wrap{max-width:1180px; margin:0 auto; padding:0 1.5rem}
.stats{display:grid; gap:1px; background:var(--rule-soft);
  grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
  border:1px solid var(--rule-soft); border-radius:8px; overflow:hidden;
  margin:1.8rem 0}
.stat{background:var(--surface); padding:1rem 1.15rem}
.stat dt{font-size:.75rem; letter-spacing:.06em; color:var(--muted);
  margin-bottom:.25rem}
.stat dd{margin:0; font-family:var(--mono); font-size:1.45rem;
  font-variant-numeric:tabular-nums; letter-spacing:-.02em}
.stat dd small{font-size:.72rem; color:var(--faint); letter-spacing:0;
  margin-left:.3rem; font-family:var(--sans)}
.stat.good dd{color:var(--ok)}

/* ── 版面 ───────────────────────────── */
.layout{display:grid; grid-template-columns:250px minmax(0,1fr); gap:2.5rem}
@media (max-width:900px){.layout{grid-template-columns:1fr; gap:1.5rem}}

.rail{position:sticky; top:1rem; align-self:start; max-height:calc(100vh - 2rem);
  display:flex; flex-direction:column; gap:.7rem}
@media (max-width:900px){.rail{position:static; max-height:none}}
.rail h2{font-size:.78rem; font-family:var(--mono); letter-spacing:.14em;
  text-transform:uppercase; color:var(--faint)}
.filters{display:flex; flex-wrap:wrap; gap:.35rem}
.filters button{
  font:inherit; font-size:.76rem; padding:.25rem .6rem; cursor:pointer;
  background:var(--surface); color:var(--muted);
  border:1px solid var(--rule); border-radius:999px;
}
.filters button[aria-pressed="true"]{
  background:var(--ink); color:var(--paper); border-color:var(--ink)}
.index{list-style:none; margin:0; padding:0; overflow-y:auto; flex:1;
  border-top:1px solid var(--rule-soft)}
.index li{border-bottom:1px solid var(--rule-soft)}
.index a{
  display:grid; grid-template-columns:2.1rem 1fr auto; gap:.5rem;
  align-items:center; padding:.42rem .3rem; text-decoration:none;
  color:var(--ink); font-size:.85rem;
}
.index a:hover,.index a:focus-visible{background:var(--surface-2)}
.index .n{font-family:var(--mono); font-size:.75rem; color:var(--faint);
  font-variant-numeric:tabular-nums; text-align:right}
.index .nm{overflow:hidden; text-overflow:ellipsis; white-space:nowrap}
.dot{width:8px; height:8px; border-radius:50%; background:var(--rule);
  box-shadow:0 0 0 1px var(--rule)}
.dot.ok{background:var(--ok); box-shadow:none}
.dot.back{background:var(--back); box-shadow:none}
.dot.skip{background:transparent; box-shadow:0 0 0 1px var(--faint)}

/* ── 群級裁示 ────────────────────────── */
.calls{border:1px solid var(--accent-line); border-radius:8px;
  background:var(--surface); margin-bottom:2.2rem; overflow:hidden}
.calls > h2{font-size:1.02rem; padding:.9rem 1.2rem; background:var(--accent-soft);
  color:var(--accent); border-bottom:1px solid var(--accent-line)}
.call{padding:1.15rem 1.2rem; border-bottom:1px solid var(--rule-soft)}
.call:last-child{border-bottom:0}
.call h3{font-size:.98rem; margin-bottom:.4rem}
.call p{margin:.35rem 0; color:var(--muted); font-size:.9rem}
.call p.opt{color:var(--ink)}
.call .tag{font-family:var(--mono); font-size:.7rem; letter-spacing:.1em;
  color:var(--accent); text-transform:uppercase; display:block;
  margin-bottom:.3rem}

/* ── 卡片 ───────────────────────────── */
.card{background:var(--surface); border:1px solid var(--rule);
  border-radius:8px; box-shadow:var(--shadow); margin-bottom:1.6rem;
  scroll-margin-top:1rem; overflow:hidden}
.card[data-state="ok"]{border-color:var(--ok)}
.card[data-state="back"]{border-color:var(--back)}
.card.is-skip{background:var(--surface-2); box-shadow:none}
.card-head{display:flex; flex-wrap:wrap; gap:.5rem 1rem; align-items:baseline;
  padding:1rem 1.3rem; border-bottom:1px solid var(--rule-soft)}
.card-head .no{font-family:var(--mono); font-size:.8rem; color:var(--faint);
  font-variant-numeric:tabular-nums}
.card-head h3{font-size:1.12rem}
.card-head .ja{color:var(--faint); font-size:.85rem}
.card-head .pw{font-family:var(--mono); font-size:.8rem; color:var(--muted);
  margin-left:auto; font-variant-numeric:tabular-nums}
.chip{font-size:.72rem; padding:.1rem .5rem; border-radius:999px;
  letter-spacing:.04em; white-space:nowrap}
.chip.ok{background:var(--ok-soft); color:var(--ok)}
.chip.back{background:var(--back-soft); color:var(--back)}
.chip.skip{background:var(--skip-soft); color:var(--skip)}
.chip.wait{background:var(--accent-soft); color:var(--accent)}

.texts{padding:.3rem 1.3rem 1rem}
.text-row{padding:.85rem 0; border-bottom:1px dashed var(--rule-soft)}
.text-row:last-child{border-bottom:0}
.text-row > .lab{font-family:var(--mono); font-size:.7rem; letter-spacing:.12em;
  text-transform:uppercase; color:var(--faint); display:block;
  margin-bottom:.3rem}
.text-row p{margin:0; white-space:pre-wrap}
.t-ja p{font-size:.94rem; color:var(--muted); line-height:1.85}
.t-old p{color:var(--muted)}
.t-new{background:var(--surface-2); border-left:3px solid var(--accent-line);
  padding:.8rem 1rem; border-radius:0 5px 5px 0; margin-top:.3rem}
.t-new > .lab{color:var(--accent)}
.t-new p{font-size:1.04rem; line-height:1.9}
ins{background:var(--ins); color:var(--ins-ink); text-decoration:none;
  border-radius:2px; padding:0 .06em}
del{color:var(--del-ink); opacity:.75}

.notes{list-style:none; margin:0; padding:.9rem 1.3rem 1rem;
  border-top:1px solid var(--rule-soft)}
.notes > li{display:grid; grid-template-columns:5.2rem 1fr; gap:.9rem;
  padding:.4rem 0; font-size:.88rem}
@media (max-width:640px){.notes > li{grid-template-columns:1fr; gap:.2rem}}
.notes .lab{font-size:.78rem; color:var(--faint); text-align:right;
  padding-top:.12rem}
@media (max-width:640px){.notes .lab{text-align:left}}
.notes .lab.wait{color:var(--accent); font-weight:600}
.notes ol{margin:.4rem 0 0; padding-left:1.3rem; color:var(--muted)}
.notes ol li{margin:.2rem 0}
.notes .body{color:var(--muted)}

.verdict{display:flex; flex-wrap:wrap; gap:.6rem; align-items:center;
  padding:.9rem 1.3rem; background:var(--surface-2);
  border-top:1px solid var(--rule-soft)}
.verdict button{font:inherit; font-size:.86rem; padding:.34rem .95rem;
  border-radius:5px; cursor:pointer; border:1px solid var(--rule);
  background:var(--surface); color:var(--muted)}
.verdict button:hover{border-color:var(--faint)}
.verdict button[aria-pressed="true"].v-ok{background:var(--ok);
  border-color:var(--ok); color:#fff}
.verdict button[aria-pressed="true"].v-back{background:var(--back);
  border-color:var(--back); color:#fff}
.verdict input{flex:1; min-width:200px; font:inherit; font-size:.86rem;
  padding:.34rem .6rem; border-radius:5px; border:1px solid var(--rule);
  background:var(--surface); color:var(--ink)}
.verdict input::placeholder{color:var(--faint)}

/* ── 匯出列 ──────────────────────────── */
.dock{position:fixed; left:0; right:0; bottom:0; z-index:20;
  background:var(--surface); border-top:1px solid var(--rule);
  box-shadow:0 -6px 24px -18px rgba(0,0,0,.5)}
.dock-in{max-width:1180px; margin:0 auto; padding:.7rem 1.5rem;
  display:flex; flex-wrap:wrap; gap:.8rem; align-items:center}
.dock .tally{font-family:var(--mono); font-size:.82rem; color:var(--muted);
  font-variant-numeric:tabular-nums}
.dock .tally b{color:var(--ink)}
.dock .spacer{flex:1}
.dock button{font:inherit; font-size:.86rem; padding:.42rem 1rem;
  border-radius:5px; cursor:pointer; border:1px solid var(--rule);
  background:var(--surface); color:var(--ink)}
.dock button.primary{background:var(--ink); color:var(--paper);
  border-color:var(--ink)}
.dock button:hover{border-color:var(--faint)}

dialog{border:1px solid var(--rule); border-radius:8px; padding:0;
  background:var(--surface); color:var(--ink); max-width:min(760px,92vw);
  width:100%; box-shadow:var(--shadow)}
dialog::backdrop{background:rgba(10,12,16,.55)}
.dlg-head{display:flex; align-items:center; gap:1rem; padding:.9rem 1.2rem;
  border-bottom:1px solid var(--rule-soft)}
.dlg-head h2{font-size:1rem; flex:1}
dialog textarea{width:100%; min-height:46vh; border:0; resize:vertical;
  font-family:var(--mono); font-size:.8rem; line-height:1.65; padding:1rem 1.2rem;
  background:var(--surface); color:var(--ink)}
dialog textarea:focus{outline:none}
.dlg-foot{padding:.8rem 1.2rem; border-top:1px solid var(--rule-soft);
  display:flex; gap:.6rem; justify-content:flex-end; align-items:center}
.dlg-foot .hint{margin-right:auto; font-size:.82rem; color:var(--muted)}

:where(a,button,input,textarea,summary):focus-visible{
  outline:2px solid var(--accent-line); outline-offset:2px}
@media (prefers-reduced-motion:no-preference){
  .card{transition:border-color .18s ease}
  .verdict button{transition:background .15s ease,border-color .15s ease,
    color .15s ease}
}
.hidden{display:none !important}
</style>

<div class="page">
<header class="masthead">
  <div class="masthead-in">
    <div>
      <div class="eyebrow">text-rewrite #11 · 舊卡文翻新</div>
      <h1>僅基礎條目(§4.1)× 怪獸 — 子批 2</h1>
      <p class="sub">50 張改寫待逐行審查、2 張建議不進站。放行後才寫入
        <code>data/text_rewrites.json</code>,依慣例只在你明說 commit 才提交。</p>
    </div>
    <div class="progress-wrap">
      <div class="progress-nums"><b id="doneN">0</b><span>/ 50 已裁</span></div>
      <div class="bar"><i class="b-ok" id="barOk" style="width:0"></i><i
        class="b-back" id="barBack" style="width:0"></i></div>
    </div>
  </div>
</header>

<div class="wrap">
  <dl class="stats">
    <div class="stat"><dt>進站候選</dt><dd>50<small>張</small></dd></div>
    <div class="stat"><dt>建議不進站</dt><dd>2<small>張</small></dd></div>
    <div class="stat good"><dt>詞彙表改寫引入</dt><dd>0<small>筆</small></dd></div>
    <div class="stat"><dt>詞彙表殘留</dt><dd>7<small>筆待裁</small></dd></div>
    <div class="stat"><dt>逐卡判斷點</dt><dd>4<small>處待裁</small></dd></div>
    <div class="stat good"><dt>進站前關卡</dt><dd>50<small>張全過</small></dd></div>
  </dl>

  <section class="calls" id="calls">
    <h2>群級裁示 — 這三項先決,再進逐卡</h2>

    <div class="call">
      <span class="tag">裁示 1 · 已照票10 預設處理</span>
      <h3>2 張無可改寫,跳過並往後遞補</h3>
      <p><code>11067666</code> 白翼的魔術師 — 佇列命中的【怪獸效果】欄兩句,
        補足情報都明示「効果の扱いではありません」,沒有效果句可以編號。</p>
      <p><code>12206212</code> 神鷹女郎三姊妹 — 全卡只有召喚條件一段,
        效果標記表判效果外文本,同樣沒有效果句可以編號。</p>
      <p class="opt">遞補群內第 51、52 名(<code>12953226</code> 女邪神茹雅、
        <code>12965761</code> 死亡石斛),子批 3 自第 53 名起算。</p>
    </div>

    <div class="call">
      <span class="tag">裁示 2 · 待你決定</span>
      <h3>票10 的「3 張永久地板」低估了,要不要另開票重數?</h3>
      <p>票10 那個數字是用票08 的 role 正規式數的。改用效果標記表已判 kind
        ——票10 自己引用的證據面——重數是 <strong>33 張</strong>;再加欄位層級的
        殘留(靈擺卡舊文本那一欄全是效果外文本,如本批的白翼的魔術師)還不只。</p>
      <p class="opt">對本批的操作沒有影響,但 map「收尾驗收」條記的地板量級要修
        (已先修進 map)。是否另開票重數,本票不代開。</p>
    </div>

    <div class="call">
      <span class="tag">裁示 3 · 待你決定</span>
      <h3>逐卡判斷點 4 處,其餘 46 張零爭議</h3>
      <p>強制/任意與取對象全數依官方補足情報明示判定。要決定的是:
        <a href="#c10">10 無限地獄猛獸</a>(領起句留效果外 vs 折進條件位)、
        <a href="#c28">28 赫爾阿克帝</a>(勝利句依 §3.2 上移 vs 維持原句序)、
        <a href="#c38">38 墓穴看守者</a>(場域現代化 vs 保守照譯)、
        <a href="#c42">42 連爆魔人</a>(本批唯一無官方分類明示)。</p>
      <p class="opt">另有 <a href="#c11">11</a>、<a href="#c52">52</a> 兩張聯合怪獸
        改用庫內新式聯合骨架,是本批最大的結構變動,依據逐句列在卡片裡。</p>
    </div>
  </section>

  <div class="layout">
    <nav class="rail" aria-label="卡片索引">
      <h2>索引</h2>
      <div class="filters" role="group" aria-label="篩選">
        <button type="button" data-filter="all" aria-pressed="true">全部</button>
        <button type="button" data-filter="todo" aria-pressed="false">未裁</button>
        <button type="button" data-filter="wait" aria-pressed="false">待裁點</button>
        <button type="button" data-filter="back" aria-pressed="false">退回</button>
      </div>
      <ul class="index" id="index"></ul>
    </nav>
    <main id="stream"></main>
  </div>
</div>

<div class="dock">
  <div class="dock-in">
    <span class="tally" id="tally"></span>
    <span class="spacer"></span>
    <button type="button" id="btnDiff" aria-pressed="true">對照舊譯:開</button>
    <button type="button" id="btnReset">清除所有裁示</button>
    <button type="button" class="primary" id="btnExport">匯出審查結果</button>
  </div>
</div>

<dialog id="dlg">
  <div class="dlg-head"><h2>審查結果</h2>
    <button type="button" id="dlgClose">關閉</button></div>
  <textarea id="out" readonly></textarea>
  <div class="dlg-foot">
    <span class="hint" id="copyHint">整段複製後貼回對話,我依此進站。</span>
    <button type="button" class="primary" id="btnCopy">複製</button>
  </div>
</dialog>
</div>

<script id="data" type="application/json">__DATA__</script>
<script>
(function(){
  "use strict";
  var DATA = JSON.parse(document.getElementById("data").textContent);
  var CARDS = DATA.cards;
  var KEY = "text-rewrite-11-verdicts";
  var state = {};
  try { state = JSON.parse(localStorage.getItem(KEY) || "{}"); } catch (e) {}
  var showDiff = true, filter = "all";

  function esc(s){ return s.replace(/&/g,"&amp;").replace(/</g,"&lt;")
    .replace(/>/g,"&gt;"); }

  /* 字元級 diff:LCS 回溯,舊譯→新文本。新增標 ins,刪去標 del。 */
  function diff(a, b){
    var n = a.length, m = b.length;
    if (!n || !m || n * m > 400000) return esc(b);
    var prev = new Uint32Array(m + 1), cur = new Uint32Array(m + 1), rows = [];
    for (var i = 1; i <= n; i++){
      for (var j = 1; j <= m; j++){
        cur[j] = a[i-1] === b[j-1] ? prev[j-1] + 1 : Math.max(prev[j], cur[j-1]);
      }
      rows.push(cur.slice()); prev = cur; cur = new Uint32Array(m + 1);
    }
    var out = [], i2 = n, j2 = m;
    function row(r){ return r === 0 ? new Uint32Array(m + 1) : rows[r-1]; }
    while (i2 > 0 || j2 > 0){
      if (i2 > 0 && j2 > 0 && a[i2-1] === b[j2-1]){
        out.push(["=", b[j2-1]]); i2--; j2--;
      } else if (j2 > 0 && (i2 === 0 || row(i2)[j2-1] >= row(i2-1)[j2])){
        out.push(["+", b[j2-1]]); j2--;
      } else { out.push(["-", a[i2-1]]); i2--; }
    }
    out.reverse();
    var html = "", mode = "", buf = "";
    function flush(){
      if (!buf) return;
      if (mode === "+") html += "<ins>" + esc(buf) + "</ins>";
      else if (mode === "-") html += "<del>" + esc(buf) + "</del>";
      else html += esc(buf);
      buf = "";
    }
    out.forEach(function(t){
      if (t[0] !== mode){ flush(); mode = t[0]; }
      buf += t[1];
    });
    flush();
    return html;
  }

  function newHtml(c){
    var draft = c.draft.join("\n");
    if (!showDiff || c.skipped) return esc(draft);
    return diff(c.old.join("\n"), draft);
  }

  function waitCount(c){
    return c.notes.filter(function(n){ return n.flag; }).length;
  }

  function cardHtml(c){
    var v = state[c.id] || {};
    var chips = "";
    if (c.backfill) chips += '<span class="chip wait">遞補</span>';
    if (c.skipped) chips += '<span class="chip skip">建議不進站</span>';
    else if (v.verdict === "ok") chips += '<span class="chip ok">放行</span>';
    else if (v.verdict === "back") chips += '<span class="chip back">退回</span>';
    if (waitCount(c)) chips += '<span class="chip wait">待裁 ' +
      waitCount(c) + '</span>';

    var notes = c.notes.map(function(n){
      var body = n.text ? '<span class="body">' + n.text + "</span>" : "";
      if (n.items.length) body += "<ol>" + n.items.map(function(x){
        return "<li>" + x.replace(/^\d+\.\s*/, "") + "</li>"; }).join("") + "</ol>";
      return '<li><span class="lab' + (n.flag ? " wait" : "") + '">' +
        esc(n.label) + "</span>" + body + "</li>";
    }).join("");

    return '<article class="card' + (c.skipped ? " is-skip" : "") +
      (match(c) ? "" : " hidden") +
      '" id="c' + c.no + '" data-no="' + c.no + '" data-state="' +
      (v.verdict || "") + '">' +
      '<div class="card-head"><span class="no">' +
        String(c.no).padStart(2, "0") + "</span>" +
        "<h3>" + esc(c.name) + "</h3>" +
        '<span class="ja">' + esc(c.nameJa) + "</span>" + chips +
        '<span class="pw">' + c.id + "</span></div>" +
      '<div class="texts">' +
        '<div class="text-row t-ja"><span class="lab">日文原文</span><p>' +
          esc(c.ja.join("\n")) + "</p></div>" +
        '<div class="text-row t-old"><span class="lab">查牌網舊譯</span><p>' +
          esc(c.old.join("\n")) + "</p></div>" +
        '<div class="text-row t-new"><span class="lab">新文本</span><p>' +
          newHtml(c) + "</p></div>" +
      "</div>" +
      '<ul class="notes">' + notes + "</ul>" +
      (c.skipped ? "" :
      '<div class="verdict" data-id="' + c.id + '">' +
        '<button type="button" class="v-ok" data-v="ok" aria-pressed="' +
          (v.verdict === "ok") + '">放行</button>' +
        '<button type="button" class="v-back" data-v="back" aria-pressed="' +
          (v.verdict === "back") + '">退回</button>' +
        '<input type="text" placeholder="批註(退回請說明;裁示也可寫在這)" ' +
          'value="' + esc(v.note || "").replace(/"/g, "&quot;") + '">' +
      "</div>") +
      "</article>";
  }

  function match(c){
    var v = state[c.id] || {};
    if (filter === "todo") return !c.skipped && !v.verdict;
    if (filter === "wait") return waitCount(c) > 0;
    if (filter === "back") return v.verdict === "back";
    return true;
  }

  function renderIndex(){
    document.getElementById("index").innerHTML = CARDS.map(function(c){
      var v = state[c.id] || {};
      var cls = c.skipped ? "skip" : (v.verdict === "ok" ? "ok" :
        v.verdict === "back" ? "back" : "");
      return '<li class="' + (match(c) ? "" : "hidden") + '"><a href="#c' +
        c.no + '"><span class="n">' + String(c.no).padStart(2, "0") +
        '</span><span class="nm">' + esc(c.name) + '</span><span class="dot ' +
        cls + '"></span></a></li>';
    }).join("");
  }

  function renderStream(){
    document.getElementById("stream").innerHTML = CARDS.map(cardHtml).join("");
  }

  function tally(){
    var live = CARDS.filter(function(c){ return !c.skipped; });
    var ok = 0, back = 0;
    live.forEach(function(c){
      var v = state[c.id] || {};
      if (v.verdict === "ok") ok++; else if (v.verdict === "back") back++;
    });
    document.getElementById("doneN").textContent = ok + back;
    document.getElementById("barOk").style.width =
      (ok / live.length * 100) + "%";
    document.getElementById("barBack").style.width =
      (back / live.length * 100) + "%";
    document.getElementById("tally").innerHTML = "放行 <b>" + ok +
      "</b> · 退回 <b>" + back + "</b> · 未裁 <b>" +
      (live.length - ok - back) + "</b> · 排除 <b>" +
      (CARDS.length - live.length) + "</b>";
  }

  function save(){
    try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) {}
  }

  function refresh(){ renderIndex(); renderStream(); tally(); }

  document.getElementById("stream").addEventListener("click", function(e){
    var btn = e.target.closest(".verdict button");
    if (!btn) return;
    var id = btn.closest(".verdict").dataset.id;
    var v = state[id] || (state[id] = {});
    v.verdict = v.verdict === btn.dataset.v ? "" : btn.dataset.v;
    save();
    var card = btn.closest(".card");
    card.dataset.state = v.verdict || "";
    card.querySelectorAll(".verdict button").forEach(function(b){
      b.setAttribute("aria-pressed", String(b.dataset.v === v.verdict));
    });
    var head = card.querySelector(".card-head");
    var old = head.querySelector(".chip.ok, .chip.back");
    if (old) old.remove();
    if (v.verdict){
      var chip = document.createElement("span");
      chip.className = "chip " + v.verdict;
      chip.textContent = v.verdict === "ok" ? "放行" : "退回";
      head.insertBefore(chip, head.querySelector(".chip.wait") ||
        head.querySelector(".pw"));
    }
    renderIndex(); tally();
  });

  document.getElementById("stream").addEventListener("input", function(e){
    if (!e.target.matches(".verdict input")) return;
    var id = e.target.closest(".verdict").dataset.id;
    (state[id] || (state[id] = {})).note = e.target.value;
    save();
  });

  document.querySelectorAll(".filters button").forEach(function(b){
    b.addEventListener("click", function(){
      filter = b.dataset.filter;
      document.querySelectorAll(".filters button").forEach(function(o){
        o.setAttribute("aria-pressed", String(o === b));
      });
      refresh();
    });
  });

  document.getElementById("btnDiff").addEventListener("click", function(){
    showDiff = !showDiff;
    this.setAttribute("aria-pressed", String(showDiff));
    this.textContent = "對照舊譯:" + (showDiff ? "開" : "關");
    renderStream();
  });

  document.getElementById("btnReset").addEventListener("click", function(){
    if (!confirm("清除全部裁示與批註?")) return;
    state = {}; save(); refresh();
  });

  function report(){
    var lines = ["## text-rewrite#11 子批 2 審查結果", ""];
    var ok = [], back = [], todo = [];
    CARDS.forEach(function(c){
      if (c.skipped) return;
      var v = state[c.id] || {};
      (v.verdict === "ok" ? ok : v.verdict === "back" ? back : todo).push(c);
    });
    lines.push("放行 " + ok.length + " 張、退回 " + back.length +
      " 張、未裁 " + todo.length + " 張;排除 2 張(11067666 白翼的魔術師、" +
      "12206212 神鷹女郎三姊妹)。", "");
    if (back.length){
      lines.push("### 退回(" + back.length + ")", "");
      back.forEach(function(c){
        lines.push("- " + c.no + " `" + c.id + "` " + c.name + " — " +
          ((state[c.id] || {}).note || "(未寫批註)"));
      });
      lines.push("");
    }
    var noted = ok.filter(function(c){ return (state[c.id] || {}).note; });
    if (noted.length){
      lines.push("### 放行帶批註(" + noted.length + ")", "");
      noted.forEach(function(c){
        lines.push("- " + c.no + " `" + c.id + "` " + c.name + " — " +
          state[c.id].note);
      });
      lines.push("");
    }
    if (todo.length){
      lines.push("### 未裁(" + todo.length + ")", "");
      lines.push(todo.map(function(c){ return c.no + " " + c.name; })
        .join("、"));
      lines.push("");
    }
    if (ok.length && !back.length && !todo.length){
      lines.push("### 全數放行", "", "50 張全數放行,可進站。");
    }
    return lines.join("\n");
  }

  var dlg = document.getElementById("dlg");
  document.getElementById("btnExport").addEventListener("click", function(){
    document.getElementById("out").value = report();
    document.getElementById("copyHint").textContent =
      "整段複製後貼回對話,我依此進站。";
    if (dlg.showModal) dlg.showModal(); else dlg.setAttribute("open", "");
  });
  document.getElementById("dlgClose").addEventListener("click", function(){
    if (dlg.close) dlg.close(); else dlg.removeAttribute("open");
  });
  document.getElementById("btnCopy").addEventListener("click", function(){
    var ta = document.getElementById("out");
    ta.select();
    var done = function(){
      document.getElementById("copyHint").textContent = "已複製。";
    };
    if (navigator.clipboard && navigator.clipboard.writeText){
      navigator.clipboard.writeText(ta.value).then(done, function(){
        try { document.execCommand("copy"); done(); } catch (e) {}
      });
    } else {
      try { document.execCommand("copy"); done(); } catch (e) {}
    }
  });

  refresh();
})();
</script>
'''


if __name__ == "__main__":
    sys.exit(main())
