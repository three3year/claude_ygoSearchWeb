'use strict';
/* 驗收腳本共用:紀錄器(每步的檢查項)與 Site(操作網站的 DOM)。只讀網站,不改。 */

const path = require('node:path');

const OUT = __dirname;
const SHOTS = path.join(OUT, 'shots');

/* ---------- 紀錄器 ---------- */

class Recorder {
  constructor() {
    this.steps = [];
    this.looks = [];   // 請站主看
    this.cur = null;
  }

  /* list: 'web' | 'cov';id: 例 '載入時機 3' */
  begin(mode, list, id, did, expect) {
    const s = { mode, list, id, did, expect, checks: [], notes: [], shots: [], error: null };
    this.steps.push(s);
    this.cur = s;
    return s;
  }

  check(name, expected, actual, ok) {
    this.cur.checks.push({ name, expected: String(expected), actual: String(actual), kind: ok ? 'pass' : 'fail' });
    return ok;
  }

  eq(name, expected, actual) {
    return this.check(name, expected, actual, expected === actual);
  }

  na(name, reason) {
    this.cur.checks.push({ name, expected: '', actual: reason, kind: 'na' });
  }

  note(text) { this.cur.notes.push(text); }

  look(desc, shot) {
    this.looks.push({ mode: this.cur.mode, list: this.cur.list, id: this.cur.id, desc, shot });
  }

  status(s) {
    if (s.error) return 'error';
    if (s.checks.some(c => c.kind === 'fail')) return 'fail';
    if (s.checks.length && s.checks.every(c => c.kind === 'na')) return 'na';
    return 'pass';
  }
}

/* ---------- 操作網站 ---------- */

const fmt = n => (n == null ? '—' : Number(n).toLocaleString('en-US'));

class Site {
  constructor(page, base, rec, mode) {
    this.page = page;
    this.base = base;
    this.rec = rec;
    this.mode = mode;
  }

  async open(url) {
    await this.page.goto(url || this.base);
    await this.page.waitForFunction(() => document.getElementById('dbInfo').textContent.length > 0);
  }

  /* 截圖:回傳檔名(相對 browser-acceptance/) */
  async shot(name, opts) {
    const file = `${this.mode}-${name}.png`;
    const full = path.join(SHOTS, file);
    if (opts && opts.locator) await opts.locator.screenshot({ path: full });
    else await this.page.screenshot({ path: full, fullPage: !!(opts && opts.fullPage) });
    if (this.rec.cur) this.rec.cur.shots.push(`shots/${file}`);
    return `shots/${file}`;
  }

  async clearAll() {
    await this.page.click('#btnClear');
  }

  async actionOpen() {
    return (await this.page.getAttribute('#actionHead', 'aria-expanded')) === 'true';
  }

  async openAction() {
    if (!(await this.actionOpen())) await this.page.click('#actionHead');
    await this.page.waitForSelector('#actionFields button[data-word]', { timeout: 30000 });
  }

  async selectedWords() {
    return this.page.$$eval('#actionFields button[data-word][data-st="in"]', bs => bs.map(b => b.dataset.word));
  }

  async moreIsOpen() {
    const t = await this.page.$eval('#actionFields button[data-more]', b => b.textContent).catch(() => '');
    return t.includes('收起');
  }

  /* 讓動作詞恰好是 list */
  async words(list) {
    for (const w of await this.selectedWords()) {
      if (!list.includes(w)) await this.page.click(`#actionFields button[data-word="${w}"]`);
    }
    for (const w of list) {
      let btn = this.page.locator(`#actionFields button[data-word="${w}"]`);
      if ((await btn.count()) === 0) {
        await this.page.click('#actionFields button[data-more]');
        btn = this.page.locator(`#actionFields button[data-word="${w}"]`);
      }
      if ((await btn.getAttribute('data-st')) !== 'in') await btn.click();
    }
  }

  async zone(key, zone, side) {
    await this.page.selectOption(`#actionFields select[data-zone="${key}"]`, zone || '');
    await this.page.selectOption(`#actionFields select[data-side="${key}"]`, side || '');
  }

  /* kinds:要勾的集合(eff/cost/cond)。先勾再取消,免得碰到「只剩一個不能取消」 */
  async kinds(set) {
    for (const k of set) {
      const box = this.page.locator(`#actionFields input[data-kind="${k}"]`);
      if (!(await box.isChecked())) await box.click();
    }
    for (const k of ['eff', 'cost', 'cond']) {
      if (set.includes(k)) continue;
      const box = this.page.locator(`#actionFields input[data-kind="${k}"]`);
      if (await box.isChecked()) await box.click();
    }
  }

  async pol(k) { await this.page.click(`#actionFields button[data-pol="${k}"]`); }
  async agent(v) { await this.page.click(`#actionFields button[data-agent="${v}"]`); }
  async recipient(v) { await this.page.click(`#actionFields button[data-recipient="${v}"]`); }

  async cause(kind, side) {
    await this.page.selectOption('#actionFields select[data-cause-kind]', kind || '');
    await this.page.selectOption('#actionFields select[data-cause-side]', side || '');
  }

  async unrestricted(on) {
    const box = this.page.locator('#actionFields input[data-include-unrestricted]');
    if ((await box.isChecked()) !== on) await box.click();
  }

  async target(mode) { await this.page.click(`#actionFields button[data-mode="${mode}"]`); }

  async givenBtn(key, zh) {
    const re = new RegExp(`^\\s*${zh}\\s*$`);
    await this.page.locator(`#actionFields button[data-gkey="${key}"]`, { hasText: re }).first().click();
  }

  async givenName(text) {
    await this.page.fill('#actionFields input[data-gname]', text);
  }

  /* 側欄三態鈕:點到 data-st 等於 want 為止(先展開它所在的各層摺疊) */
  async sideTri(axis, code, want) {
    const sel = `#critParams .axis[data-axis="${axis}"] .tri[data-code="${code}"]`;
    await this.page.evaluate(s => {
      const btn = document.querySelector(s);
      const heads = [];
      for (let el = btn.parentElement; el && el.id !== 'critParams'; el = el.parentElement) {
        if (el.classList.contains('axis-body') && el.hidden) {
          heads.unshift(el.parentElement.querySelector(':scope > .axis-hrow > .axis-head'));
        }
      }
      heads.forEach(h => h && h.click());
    }, sel);
    for (let i = 0; i < 3; i++) {
      const st = await this.page.getAttribute(sel, 'data-st');
      if ((st || '') === want) return;
      await this.page.click(sel);
    }
    throw new Error(`側欄 ${axis}/${code} 點不到 ${want}`);
  }

  async searchOnly() {
    await this.page.click('#btnSearch');
    await this.settle();
  }

  /* 等結果區離開「載入中」 */
  async settle() {
    await this.page.waitForFunction(() => {
      const r = document.getElementById('results');
      return !/動作索引載入中/.test(r.textContent);
    }, null, { timeout: 60000 });
  }

  async counts() {
    return this.page.evaluate(() => {
      const info = document.getElementById('resultInfo').textContent;
      const u = document.getElementById('unsureInfo');
      const m = info.match(/共 (\d+) 張/);
      const um = u.hidden ? null : u.textContent.match(/另有 (\d+) 張無法確認/);
      const idle = !!document.querySelector('#results .idle');
      return { n: m ? +m[1] : (info.includes('沒有符合') ? 0 : null), unsure: um ? +um[1] : 0,
               unsureShown: !u.hidden, info, unsureText: u.hidden ? '' : u.textContent, idle };
    });
  }

  async search() {
    await this.searchOnly();
    return this.counts();
  }

  /* 用畫面翻頁收集全部結果的卡片密碼(每頁 500 筆),收完改回原本每頁筆數 */
  async ids(findId) {
    const res = await this.page.evaluate(findId => {
      const per = document.getElementById('perPage');
      const old = per.value;
      const setPer = v => { per.value = v; per.dispatchEvent(new Event('change', { bubbles: true })); };
      setPer('500');
      const ids = [];
      let page = 1;
      let found = null;
      for (;;) {
        document.querySelectorAll('#results article.card').forEach(a => ids.push(+a.dataset.cid));
        if (findId != null && found == null && document.querySelector(`#results article.card[data-cid="${findId}"]`)) {
          found = page;
          break;
        }
        const m = document.getElementById('resultInfo').textContent.match(/第 (\d+)\/(\d+) 頁/);
        if (!m || +m[1] >= +m[2]) break;
        const btns = document.querySelectorAll('#pagerTop button');
        btns[btns.length - 1].click();
        page++;
      }
      if (findId == null) setPer(old);
      return { ids, found, old };
    }, findId == null ? null : findId);
    return res;
  }

  async idSet() {
    return new Set((await this.ids()).ids);
  }

  /* 找到卡片所在頁(每頁 500),回傳那張卡的標示資訊;可順便截那張卡的圖。看完改回每頁 100。 */
  async cardInfo(id, shotName) {
    const r = await this.ids(id);
    let info = null;
    let shot = null;
    if (r.found != null) {
      const loc = this.page.locator(`#results article.card[data-cid="${id}"]`);
      info = await loc.evaluate(a => ({
        name: a.querySelector('.card-name').textContent,
        hits: [...a.querySelectorAll('.card-text:not(.og-text) .eff.hit')].map(p => ({
          ei: +p.dataset.ei,
          text: p.textContent.replace(/\s+/g, ' ').trim(),
          badge: p.querySelector('.eff-hit') ? p.querySelector('.eff-hit').textContent : '',
          kw: [...p.querySelectorAll('mark.kw')].map(m => m.textContent),
        })),
      }));
      if (shotName) {
        await loc.scrollIntoViewIfNeeded();
        shot = await this.shot(shotName, { locator: loc });
      }
    }
    await this.page.evaluate(() => {
      const per = document.getElementById('perPage');
      per.value = '100';
      per.dispatchEvent(new Event('change', { bubbles: true }));
    });
    return { found: r.found != null, info, shot };
  }

  /* 逐字打字,每打一個字檢查輸入值與游標 */
  async typeCheck(selector, text) {
    const loc = this.page.locator(selector);
    await loc.click();
    await loc.fill('');
    let typed = '';
    const bad = [];
    for (const ch of text) {
      await this.page.keyboard.type(ch);
      typed += ch;
      const el = this.page.locator(selector);
      const r = await el.evaluate(e => {
        let s = null;
        try { s = e.selectionStart; } catch (_) { s = null; }
        return { v: e.value, s, focus: document.activeElement === e, type: e.type };
      }).catch(() => ({ v: null, s: null, focus: false, type: '?' }));
      const caretOk = r.type === 'number' ? true : r.s === typed.length;
      if (r.v !== typed || !caretOk || !r.focus) bad.push(`打到「${typed}」時:值=${r.v} 游標=${r.s} 焦點=${r.focus}`);
    }
    return bad;
  }

  async url() { return this.page.url(); }
}

module.exports = { Recorder, Site, fmt, OUT, SHOTS };
