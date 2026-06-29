#!/usr/bin/env node
/*
 * Batch Phase-2 capture using one browser instance.
 * Reads url_slug_map.tsv (URL<TAB>slug), writes captures/<slug>/ spec files.
 * Desktop: full spec (page.html, styles.json, assets.txt, fonts.txt, embeds.txt,
 *          meta.txt, links.txt, screenshot-desktop*.png).
 * Mobile: screenshot-mobile*.png only.
 * Enforces the 1500px screenshot cap exactly like capture.js.
 *
 * Usage: node batch_capture.js [startIndex] [endIndex]
 */
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const VIEWPORTS = { desktop: { width: 1440, height: 900 }, mobile: { width: 390, height: 844 } };
const SEG_MAX = 1500, DOWNSCALE = 1500;
const ROOT = '/tmp/foh';
const UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36';

function downscale(file) {
  try { execSync(`mogrify -resize ${DOWNSCALE}x${DOWNSCALE}\\> ${JSON.stringify(file)}`); } catch (e) {}
  try { const o = execSync(`identify -format "%wx%h" ${JSON.stringify(file)}`).toString().trim();
    if (o.split('x').some(n => +n > 1500)) console.log('  !!OVERSIZE', file, o); } catch (e) {}
}
async function autoScroll(page) {
  await page.evaluate(async () => {
    await new Promise((resolve) => {
      let y = 0; const tot = document.body.scrollHeight;
      const t = setInterval(() => { window.scrollTo(0, y); y += Math.floor(window.innerHeight*0.9);
        if (y >= tot) { clearInterval(t); resolve(); } }, 90);
    });
  });
  await page.waitForTimeout(700);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(300);
}
async function segmentedCapture(page, outBase, vp) {
  const totalHeight = await page.evaluate(() => document.body.scrollHeight);
  const vh = vp.height; let segIdx = 0, y = 0; const files = [];
  while (y < totalHeight) {
    await page.evaluate((yy) => window.scrollTo(0, yy), y);
    await page.waitForTimeout(250);
    const fname = segIdx === 0 ? `${outBase}.png` : `${outBase}-${segIdx+1}.png`;
    const clipH = Math.min(vh, totalHeight - y);
    await page.screenshot({ path: fname, clip: { x:0, y:0, width: vp.width, height: clipH } });
    files.push(fname); segIdx++; y += vh; if (segIdx > 40) break;
  }
  files.forEach(downscale);
}
async function collectSpec(page, url) {
  return await page.evaluate(() => {
    const abs = (u) => { try { return new URL(u, document.baseURI).href; } catch (e) { return u; } };
    const props = ['font-family','font-size','font-weight','line-height','letter-spacing','color','background-color','background-image','text-align','margin','padding','display','flex-direction','justify-content','align-items','grid-template-columns','gap','max-width','border-radius','box-shadow','position','width','height'];
    const styles = []; const all = document.querySelectorAll('*'); let idx = 0;
    for (const el of all) {
      const r = el.getBoundingClientRect(); const cs = getComputedStyle(el);
      if (cs.display==='none'||cs.visibility==='hidden'||(r.width<=0&&r.height<=0)) continue;
      if (idx++ > 4000) break;
      const o = { tag: el.tagName.toLowerCase() };
      if (el.id) o.id = el.id; if (el.className && typeof el.className==='string') o.class = el.className;
      const s = {}; for (const p of props) s[p] = cs.getPropertyValue(p); o.styles = s; styles.push(o);
    }
    const assets = new Set();
    document.querySelectorAll('img[src]').forEach(i=>assets.add(abs(i.getAttribute('src'))));
    document.querySelectorAll('img[srcset], source[srcset]').forEach(i=>{(i.getAttribute('srcset')||'').split(',').forEach(p=>{const u=p.trim().split(/\s+/)[0]; if(u)assets.add(abs(u));});});
    document.querySelectorAll('source[src]').forEach(i=>assets.add(abs(i.getAttribute('src'))));
    document.querySelectorAll('video[src],audio[src],video[poster]').forEach(i=>{if(i.getAttribute('src'))assets.add(abs(i.getAttribute('src')));if(i.getAttribute('poster'))assets.add(abs(i.getAttribute('poster')));});
    for (const el of all){const bg=getComputedStyle(el).backgroundImage;if(bg&&bg!=='none'){const re=/url\((['"]?)(.*?)\1\)/g;let m;while((m=re.exec(bg))!==null){if(m[2]&&!m[2].startsWith('data:'))assets.add(abs(m[2]));}}}
    document.querySelectorAll('link[rel*="icon"],link[rel="apple-touch-icon"],link[rel="mask-icon"]').forEach(l=>{if(l.getAttribute('href'))assets.add(abs(l.getAttribute('href')));});
    const fonts=new Set();document.querySelectorAll('link[rel="stylesheet"]').forEach(l=>{const h=l.getAttribute('href')||'';if(/font/i.test(h))fonts.add(abs(h));});
    const famSet=new Set();for(const el of all){const ff=getComputedStyle(el).fontFamily;if(ff)famSet.add(ff);}
    const embeds=[];document.querySelectorAll('iframe,embed,object').forEach(e=>{const src=e.getAttribute('src')||e.getAttribute('data')||'';embeds.push(`${e.tagName.toLowerCase()}\t${src?abs(src):''}`);});
    const meta={};meta.title=document.title;document.querySelectorAll('meta').forEach(m=>{const k=m.getAttribute('name')||m.getAttribute('property')||m.getAttribute('http-equiv');const v=m.getAttribute('content');if(k&&v)meta[k]=v;});
    const canon=document.querySelector('link[rel="canonical"]');if(canon)meta.canonical=canon.getAttribute('href');
    const links=[];document.querySelectorAll('a[href]').forEach(a=>{links.push({href:a.getAttribute('href'),text:(a.textContent||'').trim().slice(0,80)});});
    return {styles,assets:[...assets],fonts:[...fonts],fontFamilies:[...famSet],embeds,meta,links};
  });
}
function writeSpec(dir, spec, url) {
  fs.writeFileSync(path.join(dir,'styles.json'), JSON.stringify(spec.styles,null,1));
  fs.writeFileSync(path.join(dir,'assets.txt'), spec.assets.join('\n')+'\n');
  fs.writeFileSync(path.join(dir,'fonts.txt'),'FONT CSS URLS:\n'+spec.fonts.join('\n')+'\n\nCOMPUTED FONT-FAMILIES:\n'+spec.fontFamilies.join('\n')+'\n');
  fs.writeFileSync(path.join(dir,'embeds.txt'), spec.embeds.join('\n')+'\n');
  fs.writeFileSync(path.join(dir,'meta.txt'), Object.entries(spec.meta).map(([k,v])=>`${k}\t${v}`).join('\n')+'\n');
  const host=new URL(url).host;
  const lines=spec.links.map(l=>{let cls='EXTERNAL';const h=l.href||'';if(h.startsWith('#')||h.startsWith('/')||h.startsWith('?'))cls='INTERNAL';else{try{if(new URL(h,url).host===host)cls='INTERNAL';}catch(e){}}if(/^(mailto:|tel:|sms:|javascript:)/i.test(h))cls='EXTERNAL';return `${cls}\t${h}\t${(l.text||'').replace(/\s+/g,' ')}`;});
  fs.writeFileSync(path.join(dir,'links.txt'), lines.join('\n')+'\n');
}

async function main() {
  const start = parseInt(process.argv[2]||'0',10);
  const end = parseInt(process.argv[3]||'9999',10);
  const map = fs.readFileSync(path.join(ROOT,'url_slug_map.tsv'),'utf8').trim().split('\n').map(l=>l.split('\t'));
  const browser = await chromium.launch();
  for (let i = start; i < Math.min(end, map.length); i++) {
    const [url, slug] = map[i];
    const dir = path.join(ROOT,'captures',slug);
    fs.mkdirSync(dir,{recursive:true});
    const doneMarker = path.join(dir,'page.html');
    if (fs.existsSync(doneMarker) && fs.existsSync(path.join(dir,'screenshot-mobile.png'))) {
      console.log(`[${i}] SKIP ${slug} (done)`); continue;
    }
    try {
      // DESKTOP + spec
      const ctxD = await browser.newContext({ viewport: VIEWPORTS.desktop, deviceScaleFactor:1, ignoreHTTPSErrors:true, userAgent: UA });
      const pD = await ctxD.newPage();
      console.log(`[${i}] desktop ${slug} <- ${url}`);
      await pD.goto(url, { waitUntil:'networkidle', timeout:90000 }).catch(e=>console.error('  goto warn', e.message));
      await pD.waitForTimeout(1000);
      await autoScroll(pD);
      await segmentedCapture(pD, path.join(dir,'screenshot-desktop'), VIEWPORTS.desktop);
      fs.writeFileSync(path.join(dir,'page.html'), await pD.content());
      writeSpec(dir, await collectSpec(pD, url), url);
      await ctxD.close();
      // MOBILE screenshots
      const ctxM = await browser.newContext({ viewport: VIEWPORTS.mobile, deviceScaleFactor:1, ignoreHTTPSErrors:true, userAgent: UA, isMobile:true, hasTouch:true });
      const pM = await ctxM.newPage();
      console.log(`[${i}] mobile  ${slug}`);
      await pM.goto(url, { waitUntil:'networkidle', timeout:90000 }).catch(e=>console.error('  goto warn', e.message));
      await pM.waitForTimeout(1000);
      await autoScroll(pM);
      await segmentedCapture(pM, path.join(dir,'screenshot-mobile'), VIEWPORTS.mobile);
      await ctxM.close();
    } catch (e) {
      console.error(`[${i}] ERROR ${slug}:`, e.message);
    }
  }
  await browser.close();
}
main().catch(e=>{console.error(e);process.exit(1);});
