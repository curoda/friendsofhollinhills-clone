#!/usr/bin/env node
/*
 * audit.js — load every clone page in Playwright, log responses with status >= 400 and every
 * requestfailed event. Distinguishes clone-side defects from source-side/3rd-party breakage.
 * Usage: node audit.js [clone|origin]
 */
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const ROOT = '/tmp/foh';
const BASES = { clone: 'https://friendsofhollinhills-clone.vercel.app', origin: 'https://www.friendsofhollinhills.org' };
const UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36';

(async () => {
  const which = process.argv[2] || 'clone';
  const BASE = BASES[which];
  const rows = fs.readFileSync(path.join(ROOT, 'url_slug_map.tsv'), 'utf8').trim().split('\n').map(l => l.split('\t'));
  const browser = await chromium.launch();
  const findings = {};
  for (const [url, slug] of rows) {
    const target = which === 'clone' ? url.replace(BASES.origin, BASE) : url;
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1, ignoreHTTPSErrors: true, userAgent: UA });
    const page = await ctx.newPage();
    const bad = [];
    page.on('response', r => { if (r.status() >= 400) bad.push(`${r.status()} ${r.url()}`); });
    page.on('requestfailed', r => { const f = r.failure(); bad.push(`FAILED ${r.url()} :: ${f ? f.errorText : '?'}`); });
    try {
      await page.goto(target, { waitUntil: 'networkidle', timeout: 60000 });
      await page.waitForTimeout(1500);
    } catch (e) { bad.push('GOTO_ERR ' + e.message); }
    if (bad.length) findings[slug] = bad;
    await ctx.close();
  }
  await browser.close();
  // categorize
  const out = [];
  const isThirdParty = (u) => /powr\.io|docsbot\.ai|google-analytics|googletagmanager|gstatic|doubleclick|facebook|instagram|youtube|recaptcha|editmysite\.com\/(ajax|api)|weebly\.com|snowday|paypal|cloudflareinsights/i.test(u);
  for (const [slug, list] of Object.entries(findings)) {
    for (const item of list) {
      const url = item.split(' ').slice(1).join(' ').split(' :: ')[0];
      const cat = isThirdParty(url) ? '3RDPARTY' : (/friendsofhollinhills-clone\.vercel\.app/.test(url) ? 'CLONE' : 'OTHER');
      out.push(`${cat}\t${slug}\t${item}`);
    }
  }
  fs.writeFileSync(path.join(ROOT, `audit_${which}.txt`), out.join('\n') + '\n');
  const counts = out.reduce((a, l) => { const c = l.split('\t')[0]; a[c] = (a[c] || 0) + 1; return a; }, {});
  console.log(`audit ${which}: ${out.length} findings across ${Object.keys(findings).length} pages`, counts);
  // show CLONE/OTHER (potential defects) deduped
  const defects = [...new Set(out.filter(l => l.startsWith('CLONE') || l.startsWith('OTHER')).map(l => l.split('\t').slice(2).join('\t')))];
  console.log('--- non-3rdparty findings (deduped) ---');
  defects.slice(0, 60).forEach(d => console.log(d));
})();
