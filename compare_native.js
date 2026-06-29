#!/usr/bin/env node
/*
 * compare_native.js — objective pixel diff of ORIGIN vs LIVE CLONE.
 * Loads both pages at the SAME viewport, scrolls lockstep by viewport HEIGHT,
 * diffs each NATIVE-resolution segment (no downscale -> no resample artifact).
 * Masks the bottom-right chat widget + right-edge social icons (async third-party).
 *
 * Usage: node compare_native.js <device> [slug1 slug2 ...]   (default: all, desktop)
 * Writes compare_out/<device>/<slug>.diff.png for segments over threshold + prints table.
 */
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const { PNG } = require('pngjs');
const pixelmatch = require('pixelmatch');

const ROOT = '/tmp/foh';
const ORIGIN = 'https://www.friendsofhollinhills.org';
const CLONE = 'https://friendsofhollinhills-clone.vercel.app';
const VP = { desktop: { width: 1440, height: 900 }, mobile: { width: 390, height: 844 } };
const UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36';

function originToClone(u) { return u.replace(ORIGIN, CLONE).replace('https://www.friendsofhollinhills.org', CLONE); }

async function prep(page, vp) {
  await page.evaluate(async () => {
    await new Promise((resolve) => {
      let y = 0; const tot = document.body.scrollHeight;
      const t = setInterval(() => { window.scrollTo(0, y); y += Math.floor(window.innerHeight*0.9);
        if (y >= tot) { clearInterval(t); resolve(); } }, 60);
    });
  });
  await page.waitForTimeout(700);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(400);
}

function maskCtx(ctx, vp) {
  // hide async third-party widgets to avoid false positives
  return ctx.addInitScript(() => {
    const css = `#docsbotai-root,.powr-social-media-icons,[class*="docsbot"],iframe[src*="powr.io"],
      .wsite-social,.w-social,#chat-widget-container,div[id^="powr-"]{visibility:hidden !important;}`;
    const s = document.createElement('style'); s.textContent = css;
    (document.head||document.documentElement).appendChild(s);
    document.addEventListener('DOMContentLoaded',()=>{const s2=document.createElement('style');s2.textContent=css;document.head.appendChild(s2);});
  });
}

async function diffPage(browser, originUrl, vp, slug, device, outDir) {
  const ctxA = await browser.newContext({ viewport: vp, deviceScaleFactor: 1, ignoreHTTPSErrors: true, userAgent: UA });
  const ctxB = await browser.newContext({ viewport: vp, deviceScaleFactor: 1, ignoreHTTPSErrors: true, userAgent: UA });
  await maskCtx(ctxA, vp); await maskCtx(ctxB, vp);
  const a = await ctxA.newPage(), b = await ctxB.newPage();
  let err = null;
  try {
    await a.goto(originUrl, { waitUntil: 'networkidle', timeout: 60000 }).catch(()=>{});
    await b.goto(originToClone(originUrl), { waitUntil: 'networkidle', timeout: 60000 }).catch(()=>{});
    await a.waitForTimeout(800); await b.waitForTimeout(800);
    await prep(a, vp); await prep(b, vp);
    const ha = await a.evaluate(() => document.body.scrollHeight);
    const hb = await b.evaluate(() => document.body.scrollHeight);
    const totalH = Math.min(ha, hb);
    let diffPx = 0, totalPx = 0, worst = 0, segIdx = 0;
    for (let y = 0; y < totalH; y += vp.height) {
      const clipH = Math.min(vp.height, totalH - y);
      await a.evaluate(yy => window.scrollTo(0, yy), y);
      await b.evaluate(yy => window.scrollTo(0, yy), y);
      await a.waitForTimeout(150); await b.waitForTimeout(150);
      const bufA = await a.screenshot({ clip: { x:0, y:0, width: vp.width, height: clipH } });
      const bufB = await b.screenshot({ clip: { x:0, y:0, width: vp.width, height: clipH } });
      const pa = PNG.sync.read(bufA), pb = PNG.sync.read(bufB);
      const w = Math.min(pa.width, pb.width), h = Math.min(pa.height, pb.height);
      const diff = new PNG({ width: w, height: h });
      const d = pixelmatch(cropTo(pa,w,h).data, cropTo(pb,w,h).data, diff.data, w, h, { threshold: 0.12 });
      diffPx += d; totalPx += w*h;
      const segPct = d/(w*h)*100;
      if (segPct > worst) worst = segPct;
      if (segPct > 1.0) {
        fs.mkdirSync(outDir, { recursive: true });
        fs.writeFileSync(path.join(outDir, `${slug}.seg${segIdx}.diff.png`), PNG.sync.write(diff));
      }
      segIdx++;
      if (segIdx > 40) break;
    }
    const pct = totalPx ? diffPx/totalPx*100 : 0;
    return { slug, pct: +pct.toFixed(3), worst: +worst.toFixed(3), ha, hb, dh: ha-hb };
  } catch (e) {
    err = e.message;
    return { slug, pct: -1, worst: -1, ha:0, hb:0, dh:0, err };
  } finally {
    await ctxA.close(); await ctxB.close();
  }
}
function cropTo(png, w, h) {
  if (png.width === w && png.height === h) return png;
  const out = new PNG({ width: w, height: h });
  for (let y=0;y<h;y++) for (let x=0;x<w;x++){ const i=(png.width*y+x)<<2, o=(w*y+x)<<2;
    out.data[o]=png.data[i];out.data[o+1]=png.data[i+1];out.data[o+2]=png.data[i+2];out.data[o+3]=png.data[i+3]; }
  return out;
}

async function main() {
  const device = process.argv[2] || 'desktop';
  const vp = VP[device];
  const rows = fs.readFileSync(path.join(ROOT,'url_slug_map.tsv'),'utf8').trim().split('\n').map(l=>l.split('\t'));
  let filter = process.argv.slice(3);
  const sel = filter.length ? rows.filter(r => filter.includes(r[1])) : rows;
  const outDir = path.join(ROOT, 'compare_out', device);
  const browser = await chromium.launch();
  const results = [];
  for (const [url, slug] of sel) {
    const r = await diffPage(browser, url, vp, slug, device, outDir);
    results.push(r);
    const flag = r.pct < 0 ? 'ERR' : (r.pct > 2 || Math.abs(r.dh) > 60 ? 'CHECK' : 'ok');
    console.log(`${String(r.pct).padStart(7)}%  worst ${String(r.worst).padStart(7)}%  dh=${String(r.dh).padStart(5)}  ${flag.padEnd(5)} ${slug}${r.err?'  '+r.err:''}`);
  }
  await browser.close();
  fs.writeFileSync(path.join(ROOT, `compare_${device}.json`), JSON.stringify(results,null,1));
  const bad = results.filter(r => r.pct > 2 || Math.abs(r.dh) > 60 || r.pct < 0);
  console.log(`\n${device}: ${results.length} pages, ${bad.length} need review (>2% or dh>60 or err).`);
}
main().catch(e=>{console.error(e);process.exit(1);});
