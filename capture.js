#!/usr/bin/env node
/*
 * Reusable capture script for website cloning.
 * GUARANTEES the screenshot size cap at the moment of capture:
 *   - deviceScaleFactor = 1  (saved pixels == CSS viewport)
 *   - ignoreHTTPSErrors = true (Cloudflare / cert chains)
 *   - fixed viewport: 1440x900 desktop, 390x844 mobile
 *   - long pages captured in scroll segments, each <= 1500px tall,
 *     advancing scroll by viewport HEIGHT between segments
 *   - every saved PNG downscaled so its longest side <= 1500px (mogrify -resize 1500x1500>)
 *   - prints final pixel dimensions of every saved file
 *
 * Usage:
 *   node capture.js <url> <outdir> <desktop|mobile> [--spec]
 *   node capture.js shot <url> <outfile.png> <desktop|mobile>   # single bounded shot
 *
 * In <outdir> with --spec it writes the full Phase-2 spec files:
 *   screenshot-<device>.png (+ -2,-3 segments), page.html, styles.json,
 *   assets.txt, fonts.txt, embeds.txt, meta.txt, links.txt
 */
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const VIEWPORTS = {
  desktop: { width: 1440, height: 900 },
  mobile: { width: 390, height: 844 },
};
const SEG_MAX = 1500;       // max segment height in px
const DOWNSCALE = 1500;     // longest side cap for model-attached images

function downscale(file) {
  try {
    execSync(`mogrify -resize ${DOWNSCALE}x${DOWNSCALE}\\> ${JSON.stringify(file)}`);
  } catch (e) {
    console.error('mogrify failed for', file, e.message);
  }
  try {
    const out = execSync(`identify -format "%wx%h" ${JSON.stringify(file)}`).toString().trim();
    console.log(`  SAVED ${path.basename(file)} -> ${out}px`);
  } catch (e) {
    console.log(`  SAVED ${path.basename(file)} (identify failed)`);
  }
}

async function autoScroll(page, vh) {
  // Scroll the full height to trigger lazy-load / background images, then back to top.
  await page.evaluate(async (vh) => {
    await new Promise((resolve) => {
      let y = 0;
      const tot = document.body.scrollHeight;
      const timer = setInterval(() => {
        window.scrollTo(0, y);
        y += Math.floor(window.innerHeight * 0.9);
        if (y >= tot) { clearInterval(timer); resolve(); }
      }, 120);
    });
  }, vh);
  await page.waitForTimeout(800);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(400);
}

async function segmentedCapture(page, outBase, vp) {
  const totalHeight = await page.evaluate(() => document.body.scrollHeight);
  const vh = vp.height;
  const files = [];
  let segIdx = 0;
  let y = 0;
  while (y < totalHeight) {
    const remaining = totalHeight - y;
    const segH = Math.min(SEG_MAX, Math.max(remaining, 1), vh > SEG_MAX ? SEG_MAX : Math.max(vh, Math.min(SEG_MAX, remaining)));
    // We capture exactly the viewport (height vp.height) but to cover up to SEG_MAX we
    // capture in viewport-sized shots; simpler + robust: shot the viewport at each scroll y.
    await page.evaluate((yy) => window.scrollTo(0, yy), y);
    await page.waitForTimeout(350);
    const fname = segIdx === 0 ? `${outBase}.png` : `${outBase}-${segIdx + 1}.png`;
    // Clamp clip to not exceed page bottom
    const clipH = Math.min(vh, totalHeight - y);
    await page.screenshot({ path: fname, clip: { x: 0, y: 0, width: vp.width, height: clipH } });
    files.push(fname);
    segIdx++;
    y += vh; // advance by viewport HEIGHT
    if (segIdx > 40) break; // safety
  }
  files.forEach(downscale);
  return files;
}

async function collectSpec(page) {
  return await page.evaluate(() => {
    const abs = (u) => { try { return new URL(u, document.baseURI).href; } catch (e) { return u; } };
    // ----- styles.json : computed styles for every visible element -----
    const props = ['font-family','font-size','font-weight','line-height','letter-spacing','color',
      'background-color','background-image','text-align','margin','padding','display',
      'flex-direction','justify-content','align-items','grid-template-columns','gap',
      'max-width','border-radius','box-shadow','position','width','height'];
    const styles = [];
    const all = document.querySelectorAll('*');
    let idx = 0;
    for (const el of all) {
      const r = el.getBoundingClientRect();
      const cs = getComputedStyle(el);
      const visible = cs.display !== 'none' && cs.visibility !== 'hidden' && (r.width > 0 || r.height > 0);
      if (!visible) continue;
      if (idx++ > 4000) break;
      const o = { tag: el.tagName.toLowerCase() };
      if (el.id) o.id = el.id;
      if (el.className && typeof el.className === 'string') o.class = el.className;
      const s = {};
      for (const p of props) s[p] = cs.getPropertyValue(p);
      o.styles = s;
      styles.push(o);
    }
    // ----- assets -----
    const assets = new Set();
    document.querySelectorAll('img[src]').forEach(i => assets.add(abs(i.getAttribute('src'))));
    document.querySelectorAll('img[srcset], source[srcset]').forEach(i => {
      (i.getAttribute('srcset')||'').split(',').forEach(p => { const u=p.trim().split(/\s+/)[0]; if(u) assets.add(abs(u)); });
    });
    document.querySelectorAll('source[src]').forEach(i => assets.add(abs(i.getAttribute('src'))));
    document.querySelectorAll('video[src], audio[src], video[poster]').forEach(i => {
      if (i.getAttribute('src')) assets.add(abs(i.getAttribute('src')));
      if (i.getAttribute('poster')) assets.add(abs(i.getAttribute('poster')));
    });
    // background images from computed styles for EVERY element
    for (const el of all) {
      const bg = getComputedStyle(el).backgroundImage;
      if (bg && bg !== 'none') {
        const re = /url\((['"]?)(.*?)\1\)/g; let m;
        while ((m = re.exec(bg)) !== null) { if (m[2] && !m[2].startsWith('data:')) assets.add(abs(m[2])); }
      }
    }
    // favicons / app icons
    document.querySelectorAll('link[rel*="icon"], link[rel="apple-touch-icon"], link[rel="mask-icon"]').forEach(l => {
      if (l.getAttribute('href')) assets.add(abs(l.getAttribute('href')));
    });
    // ----- fonts -----
    const fonts = new Set();
    document.querySelectorAll('link[rel="stylesheet"]').forEach(l => { const h=l.getAttribute('href')||''; if(/font/i.test(h)) fonts.add(abs(h)); });
    const famSet = new Set();
    for (const el of all) { const ff = getComputedStyle(el).fontFamily; if (ff) famSet.add(ff); }
    // ----- embeds -----
    const embeds = [];
    document.querySelectorAll('iframe, embed, object').forEach(e => {
      const src = e.getAttribute('src') || e.getAttribute('data') || '';
      embeds.push(`${e.tagName.toLowerCase()}\t${src ? abs(src) : ''}`);
    });
    // ----- meta -----
    const meta = {};
    meta.title = document.title;
    document.querySelectorAll('meta').forEach(m => {
      const k = m.getAttribute('name') || m.getAttribute('property') || m.getAttribute('http-equiv');
      const v = m.getAttribute('content');
      if (k && v) meta[k] = v;
    });
    const canon = document.querySelector('link[rel="canonical"]');
    if (canon) meta.canonical = canon.getAttribute('href');
    // ----- links -----
    const links = [];
    document.querySelectorAll('a[href]').forEach(a => {
      const href = a.getAttribute('href');
      links.push({ href, text: (a.textContent||'').trim().slice(0,80) });
    });
    return { styles, assets: [...assets], fonts: [...fonts], fontFamilies: [...famSet], embeds, meta, links };
  });
}

async function main() {
  const argv = process.argv.slice(2);
  if (argv[0] === 'shot') {
    const [, url, outfile, device] = argv;
    const vp = VIEWPORTS[device || 'desktop'];
    const browser = await chromium.launch();
    const ctx = await browser.newContext({ viewport: vp, deviceScaleFactor: 1, ignoreHTTPSErrors: true,
      userAgent: 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36' });
    const page = await ctx.newPage();
    await page.goto(url, { waitUntil: 'networkidle', timeout: 90000 }).catch(()=>{});
    await autoScroll(page, vp.height);
    await page.screenshot({ path: outfile, clip: { x:0, y:0, width: vp.width, height: Math.min(vp.height, await page.evaluate(()=>document.body.scrollHeight)) } });
    downscale(outfile);
    await browser.close();
    return;
  }

  const url = argv[0];
  const outdir = argv[1];
  const device = argv[2] || 'desktop';
  const doSpec = argv.includes('--spec');
  const vp = VIEWPORTS[device];
  fs.mkdirSync(outdir, { recursive: true });

  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: vp, deviceScaleFactor: 1, ignoreHTTPSErrors: true,
    userAgent: 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36' });
  const page = await ctx.newPage();
  console.log(`[capture] ${device} ${url}`);
  await page.goto(url, { waitUntil: 'networkidle', timeout: 90000 }).catch(e => console.error('goto warn:', e.message));
  await page.waitForTimeout(1200);
  await autoScroll(page, vp.height);

  const outBase = path.join(outdir, `screenshot-${device}`);
  await segmentedCapture(page, outBase, vp);

  if (doSpec) {
    const html = await page.content();
    fs.writeFileSync(path.join(outdir, 'page.html'), html);
    const spec = await collectSpec(page);
    fs.writeFileSync(path.join(outdir, 'styles.json'), JSON.stringify(spec.styles, null, 1));
    fs.writeFileSync(path.join(outdir, 'assets.txt'), spec.assets.join('\n') + '\n');
    fs.writeFileSync(path.join(outdir, 'fonts.txt'),
      'FONT CSS URLS:\n' + spec.fonts.join('\n') + '\n\nCOMPUTED FONT-FAMILIES:\n' + spec.fontFamilies.join('\n') + '\n');
    fs.writeFileSync(path.join(outdir, 'embeds.txt'), spec.embeds.join('\n') + '\n');
    const metaLines = Object.entries(spec.meta).map(([k,v]) => `${k}\t${v}`);
    fs.writeFileSync(path.join(outdir, 'meta.txt'), metaLines.join('\n') + '\n');
    // links marked INTERNAL/EXTERNAL
    const host = new URL(url).host;
    const linkLines = spec.links.map(l => {
      let cls = 'EXTERNAL';
      const h = l.href || '';
      if (h.startsWith('#') || h.startsWith('/') || h.startsWith('?')) cls = 'INTERNAL';
      else { try { if (new URL(h, url).host === host) cls = 'INTERNAL'; } catch(e){} }
      if (/^(mailto:|tel:|sms:|javascript:)/i.test(h)) cls = 'EXTERNAL';
      return `${cls}\t${h}\t${l.text.replace(/\s+/g,' ')}`;
    });
    fs.writeFileSync(path.join(outdir, 'links.txt'), linkLines.join('\n') + '\n');
    console.log(`  spec written: ${spec.styles.length} styled els, ${spec.assets.length} assets, ${spec.links.length} links`);
  }
  await browser.close();
}

main().catch(e => { console.error(e); process.exit(1); });
