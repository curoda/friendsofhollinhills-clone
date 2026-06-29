#!/usr/bin/env python3
"""
Static-mirror builder for friendsofhollinhills.org (Weebly site).

Reads captures/<slug>/page.html (rendered DOM) + url_slug_map.tsv,
downloads every localizable asset into site/assets/<host>/<path>,
processes CSS recursively for url() refs, rewrites HTML asset/link URLs
to local root-relative paths, and writes each page to its mirrored
filesystem path under site/.

External/live hosts (analytics, chatbot, social widgets, recaptcha,
youtube/fb/ig, external sites) are left untouched.
"""
import os, re, sys, json, hashlib, urllib.parse, urllib.request, ssl, time
from concurrent.futures import ThreadPoolExecutor

ROOT = "/tmp/foh"
SITE = os.path.join(ROOT, "site")
ASSETS = os.path.join(SITE, "assets")
PAGE_HOST = "www.friendsofhollinhills.org"

# Hosts whose assets we download and serve locally.
CDN_HOSTS = {"cdn11.editmysite.com", "cdn2.editmysite.com", "cdn.editmysite.com",
             "www.weebly.com", "editmysite.com"}
# Hosts to KEEP live (never download/rewrite).
KEEP_HOSTS = {"www.powr.io", "powr.io", "widget.docsbot.ai", "ssl.google-analytics.com",
              "www.google-analytics.com", "www.googletagmanager.com", "www.gstatic.com",
              "www.google.com", "fonts.googleapis.com", "fonts.gstatic.com",
              "www.youtube.com", "youtube.com", "youtu.be", "www.facebook.com",
              "facebook.com", "www.instagram.com", "instagram.com", "www.hollinhills.org",
              "hollinhills.org", "maps.google.com", "www.paypal.com", "paypalobjects.com",
              "www.paypalobjects.com", "static.weebly.com"}

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

downloaded = {}      # original_url(no-frag) -> local_abs_path or None(failed)
download_log = []    # (url, status)

def safe_segment(seg):
    seg = urllib.parse.unquote(seg)
    if len(seg) > 100:
        name, dot, ext = seg.rpartition(".")
        h = hashlib.md5(seg.encode()).hexdigest()[:10]
        if dot:
            seg = name[:60] + "_" + h + "." + ext[:12]
        else:
            seg = seg[:60] + "_" + h
    # filesystem-unsafe chars
    return re.sub(r'[<>:"\\|?*]', "_", seg)

def local_path_for(host, path):
    """Return absolute filesystem path for a given host+path (no query).
    friendsofhollinhills.org assets keep their ORIGINAL root path under SITE/ (so root-relative
    refs like /uploads/.. and the slideshow JS's /uploads/..X_orig.ext both resolve); CDN-host
    assets go under SITE/assets/<host>/<path>."""
    path = path.split("?")[0].split("#")[0]
    if not path or path == "/":
        path = "/index"
    parts = [safe_segment(p) for p in path.split("/") if p != ""]
    if not parts:
        parts = ["index"]
    if host in (PAGE_HOST, "friendsofhollinhills.org"):
        return os.path.join(SITE, *parts)
    return os.path.join(ASSETS, host, *parts)

def normalize_url(u, base):
    """Absolutize a URL against base; return (scheme_host, host, path_with_query) or None."""
    u = u.strip()
    if not u or u.startswith(("data:", "javascript:", "mailto:", "tel:", "sms:", "#")):
        return None
    if u.startswith("//"):
        u = "https:" + u
    try:
        absu = urllib.parse.urljoin(base, u)
    except Exception:
        return None
    p = urllib.parse.urlparse(absu)
    if p.scheme not in ("http", "https"):
        return None
    return absu, p.netloc, p.path, p.query

def fetch(url, dest):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": "https://www.friendsofhollinhills.org/"})
    try:
        with urllib.request.urlopen(req, timeout=45, context=ctx) as r:
            data = r.read()
        with open(dest, "wb") as f:
            f.write(data)
        download_log.append((url, r.status))
        return data
    except urllib.error.HTTPError as e:
        download_log.append((url, e.code))
        return None
    except Exception as e:
        download_log.append((url, f"ERR {e}"))
        return None

CSS_URL_RE = re.compile(r'url\(\s*([^)]*?)\s*\)')
CSS_IMPORT_RE = re.compile(r'@import\s+([\'"])([^\'"]+)\1')

def clean_css_url(raw):
    """Strip surrounding quotes / HTML entity-quotes from a captured url() inner string."""
    s = raw.strip()
    for ent in ('&quot;', '&#34;', '&#x22;', '&apos;', '&#39;', '&#x27;'):
        if s.startswith(ent):
            s = s[len(ent):]
        if s.endswith(ent):
            s = s[:-len(ent)]
    s = s.strip().strip('\'"').strip()
    return s

def asset_local_ref(absu, host, path):
    """Return root-relative /assets/... ref for a localizable asset and ensure download/queue."""
    lp = local_path_for(host, path)
    rel = "/" + os.path.relpath(lp, SITE).replace(os.sep, "/")
    key = absu.split("#")[0]
    if key not in downloaded:
        downloaded[key] = (lp, host, path)
    return rel

def is_page_url(host, path):
    if host not in (PAGE_HOST, "friendsofhollinhills.org"):
        return False
    pl = path.lower()
    if pl in ("", "/"):
        return True
    if pl.endswith(".html"):
        return True
    if pl.startswith("/store") or pl.startswith("/news/"):
        return True
    return False

def rewrite_url_in_html(u, base):
    """Given a URL attribute value, return its rewritten value (or None to leave unchanged)."""
    n = normalize_url(u, base)
    if n is None:
        return None
    absu, host, path, query = n
    if host in (PAGE_HOST, "friendsofhollinhills.org"):
        if is_page_url(host, path):
            # page link -> root-relative path (keep original encoding for file match)
            pr = urllib.parse.urlparse(absu)
            newp = pr.path
            if pr.query:
                newp += "?" + pr.query
            if pr.fragment:
                newp += "#" + pr.fragment
            if newp == "" or newp == "/":
                newp = "/"
            return newp
        else:
            return asset_local_ref(absu, host, path)
    if host in CDN_HOSTS:
        return asset_local_ref(absu, host, path)
    # keep external
    return None

def process_css(css_text, css_url):
    """Rewrite url() and @import in CSS; queue referenced assets. Returns new css text."""
    def repl_url(m):
        u = clean_css_url(m.group(1))
        if not u or u.startswith("data:") or u.startswith("#"):
            return m.group(0)
        n = normalize_url(u, css_url)
        if n is None:
            return m.group(0)
        absu, host, path, query = n
        if host in CDN_HOSTS or host in (PAGE_HOST, "friendsofhollinhills.org"):
            rel = asset_local_ref(absu, host, path)
            return f"url({rel})"
        return m.group(0)
    def repl_import(m):
        q, u = m.group(1), m.group(2)
        n = normalize_url(u, css_url)
        if n is None:
            return m.group(0)
        absu, host, path, query = n
        if host in CDN_HOSTS or host in (PAGE_HOST, "friendsofhollinhills.org"):
            rel = asset_local_ref(absu, host, path)
            return f"@import {q}{rel}{q}"
        return m.group(0)
    css_text = CSS_IMPORT_RE.sub(repl_import, css_text)
    css_text = CSS_URL_RE.sub(repl_url, css_text)
    return css_text

def download_all_assets():
    """Iteratively download queued assets; process CSS to discover nested assets."""
    processed = set()
    rounds = 0
    while True:
        rounds += 1
        pending = [(k, v) for k, v in downloaded.items() if v is not None and k not in processed and isinstance(v, tuple)]
        if not pending:
            break
        for key, (lp, host, path) in pending:
            processed.add(key)
        # download in parallel
        def work(item):
            key, (lp, host, path) = item
            if os.path.exists(lp) and os.path.getsize(lp) > 0:
                with open(lp, "rb") as f:
                    return key, lp, host, f.read()
            data = fetch(key, lp)
            return key, lp, host, data
        with ThreadPoolExecutor(max_workers=12) as ex:
            results = list(ex.map(work, pending))
        # process CSS results for nested refs
        for key, lp, host, data in results:
            downloaded[key] = lp if data is not None else None
            if data is not None and lp.lower().endswith(".css"):
                try:
                    txt = data.decode("utf-8", "replace")
                except Exception:
                    continue
                new = process_css(txt, key)
                with open(lp, "w", encoding="utf-8") as f:
                    f.write(new)
        if rounds > 8:
            break

ATTR_RE = re.compile(r'(\s(?:src|href|data|poster)\s*=\s*)(["\'])(.*?)\2', re.IGNORECASE)
SRCSET_RE = re.compile(r'(\ssrcset\s*=\s*)(["\'])(.*?)\2', re.IGNORECASE)
STYLE_ATTR_RE = re.compile(r'(\sstyle\s*=\s*)(["\'])(.*?)\2', re.IGNORECASE | re.DOTALL)
INLINE_STYLE_TAG_RE = re.compile(r'(<style[^>]*>)(.*?)(</style>)', re.IGNORECASE | re.DOTALL)

SLIDESHOW_OPEN_RE = re.compile(r'<div id="(\d+)-slideshow"[^>]*>', re.IGNORECASE)

def empty_slideshow_containers(html):
    """Empty Weebly slideshow containers (<div id="N-slideshow" class="wslide">...</div>) that
    the captured DOM froze mid-animation. wSlideshow.render() rebuilds them fresh on load so the
    slideshow rotates (and uses /uploads/..X_orig paths, which we now serve at root)."""
    out = []
    pos = 0
    count = 0
    for m in SLIDESHOW_OPEN_RE.finditer(html):
        start = m.start()
        if start < pos:
            continue
        open_end = m.end()
        # find matching </div> by scanning nested <div>/</div> from open_end
        depth = 1
        i = open_end
        tag_re = re.compile(r'<(/?)div\b', re.IGNORECASE)
        while depth > 0:
            tm = tag_re.search(html, i)
            if not tm:
                i = len(html); break
            if tm.group(1) == '/':
                depth -= 1
            else:
                depth += 1
            i = tm.end()
        # i now points just after the matching </div>'s "</div"; find the '>'
        close_gt = html.find('>', i)
        close_gt = close_gt + 1 if close_gt != -1 else len(html)
        out.append(html[pos:open_end])   # keep opening <div ...>
        out.append('</div>')             # emptied content + close
        pos = close_gt
        count += 1
    out.append(html[pos:])
    return ''.join(out), count


SLIDE_CFG_RE = re.compile(r'wSlideshow\.render\((\{.*?\})\)', re.DOTALL)
SLIDE_IMG_RE = re.compile(r'"url"\s*:\s*"([^"]+)"')

def queue_slideshow_images(html):
    """Parse wSlideshow.render configs and queue the /uploads/<path>_orig.<ext> binaries the
    client JS will request, so they exist on the clone even though we emptied the container."""
    n = 0
    for cfg in SLIDE_CFG_RE.findall(html):
        for url in SLIDE_IMG_RE.findall(cfg):
            u = url.lstrip("/")
            if u.startswith("uploads/"):
                u = u[len("uploads/"):]
            m = re.match(r'^(.*)\.([^.]+)$', u)
            orig = f"{m.group(1)}_orig.{m.group(2)}" if m else (u + "_orig")
            absu = f"https://{PAGE_HOST}/uploads/{orig}"
            asset_local_ref(absu, PAGE_HOST, f"/uploads/{orig}")
            n += 1
    return n

def cf_decode_html(html):
    """Decode Cloudflare email-obfuscation in the raw server HTML (rendered DOM had it decoded,
    but we mirror raw HTML). Replaces /cdn-cgi/l/email-protection#HEX hrefs with mailto: and
    __cf_email__ spans / data-cfemail with the plaintext email."""
    def dec(h):
        try:
            r = int(h[:2], 16)
            return ''.join(chr(int(h[i:i+2], 16) ^ r) for i in range(2, len(h), 2))
        except Exception:
            return ''
    # 1) hrefs
    def repl_href(m):
        email = dec(m.group(1))
        return f'href="mailto:{email}"' if email else m.group(0)
    html = re.sub(r'href="/cdn-cgi/l/email-protection#([0-9a-fA-F]+)"', repl_href, html)
    html = re.sub(r"href='/cdn-cgi/l/email-protection#([0-9a-fA-F]+)'", repl_href, html)
    # 1b) anchors that carry the email in data-cfemail (bare href, visible "[email protected]")
    def repl_anchor(m):
        email = dec(m.group(1))
        return f'<a href="mailto:{email}">{email}</a>' if email else m.group(0)
    html = re.sub(r'<a\b[^>]*\bdata-cfemail="([0-9a-fA-F]+)"[^>]*>.*?</a>', repl_anchor, html, flags=re.DOTALL)
    # 2) visible __cf_email__ spans
    def repl_span(m):
        email = dec(m.group(1))
        return email if email else '[email protected]'
    html = re.sub(r'<span class="__cf_email__"[^>]*data-cfemail="([0-9a-fA-F]+)"[^>]*>.*?</span>',
                  repl_span, html, flags=re.DOTALL)
    # 3) any leftover data-cfemail attributes -> decode into text node fallback / strip attr
    html = re.sub(r'\sdata-cfemail="[0-9a-fA-F]+"', '', html)
    # 4) drop the now-unneeded cloudflare email-decode script (path 404s on static host)
    html = re.sub(r'<script[^>]*email-decode\.min\.js[^>]*></script>', '', html, flags=re.IGNORECASE)
    return html

def rewrite_html(html, base):
    # Remove POWr's runtime-injected helper div that gets frozen into <head> in the captured
    # DOM. When re-parsed as static markup a <div> inside <head> is foster-parented to the top
    # of <body> (its &shy; text renders an ~18px line) and shifts the whole page down. powr.js
    # recreates whatever it needs at runtime, so dropping the stale snapshot is faithful.
    queue_slideshow_images(html)
    html = cf_decode_html(html)
    html = re.sub(r'<div id="powrIframeLoader">.*?</div>', '', html, flags=re.DOTALL)
    # Reset Weebly slideshow containers so the client JS re-renders & rotates them.
    html, _ssn = empty_slideshow_containers(html)
    # Belt-and-suspenders: even if the live powr.js re-creates #powrIframeLoader at runtime,
    # ensure it can never contribute layout height (origin renders it at height 0). The visible
    # social-icons widget is a separate .powr-social-media-icons element and is unaffected.
    override = '<style id="clone-fixes">#powrIframeLoader{display:none!important;height:0!important;line-height:0!important;}</style>'
    if '</head>' in html:
        html = html.replace('</head>', override + '</head>', 1)
    # The Weebly commerce JS can't reach its cart backend on a static host and renders "Cart (-)".
    # Force the accurate empty state "Cart (0)" (the store is non-functional/Manual-handling anyway).
    cartfix = ("<script id=\"clone-cartfix\">(function(){function f(){var a=document.getElementById('wsite-nav-cart-a');"
               "if(a&&!/\\(0\\)/.test(a.textContent)){a.textContent='Cart (0)';}}var n=0,iv=setInterval(function(){f();"
               "if(++n>30)clearInterval(iv);},400);if(document.readyState!=='loading')f();"
               "else document.addEventListener('DOMContentLoaded',f);})();</script>")
    if '</body>' in html:
        html = html.replace('</body>', cartfix + '</body>', 1)
    def repl_attr(m):
        pre, q, val = m.group(1), m.group(2), m.group(3)
        new = rewrite_url_in_html(val, base)
        if new is None:
            return m.group(0)
        return f"{pre}{q}{new}{q}"
    def repl_srcset(m):
        pre, q, val = m.group(1), m.group(2), m.group(3)
        out = []
        for part in val.split(","):
            part = part.strip()
            if not part:
                continue
            bits = part.split()
            u = bits[0]
            desc = " ".join(bits[1:])
            new = rewrite_url_in_html(u, base)
            u2 = new if new is not None else u
            out.append((u2 + (" " + desc if desc else "")))
        return f"{pre}{q}{', '.join(out)}{q}"
    def repl_style_attr(m):
        pre, q, val = m.group(1), m.group(2), m.group(3)
        newval = process_inline_style(val, base)
        return f"{pre}{q}{newval}{q}"
    def repl_style_tag(m):
        return m.group(1) + process_css(m.group(2), base) + m.group(3)

    html = ATTR_RE.sub(repl_attr, html)
    html = SRCSET_RE.sub(repl_srcset, html)
    html = STYLE_ATTR_RE.sub(repl_style_attr, html)
    html = INLINE_STYLE_TAG_RE.sub(repl_style_tag, html)
    return html

def process_inline_style(style_text, base):
    def repl_url(m):
        u = clean_css_url(m.group(1))
        if not u or u.startswith("data:"):
            return m.group(0)
        n = normalize_url(u, base)
        if n is None:
            return m.group(0)
        absu, host, path, query = n
        if host in CDN_HOSTS or host in (PAGE_HOST, "friendsofhollinhills.org"):
            rel = asset_local_ref(absu, host, path)
            return f"url({rel})"
        return m.group(0)
    return CSS_URL_RE.sub(repl_url, style_text)

def page_output_path(url):
    pr = urllib.parse.urlparse(url)
    path = urllib.parse.unquote(pr.path)
    if path in ("", "/"):
        return os.path.join(SITE, "index.html")
    path = path.lstrip("/")
    # store/news pages without .html -> add /index.html style? They are routes; serve as .html files.
    if not path.endswith(".html"):
        # e.g. /news/<slug>  -> create <slug>.html under news/? Keep as folder/index.html
        return os.path.join(SITE, path, "index.html")
    return os.path.join(SITE, path)

def main():
    os.makedirs(ASSETS, exist_ok=True)
    rows = [l.split("\t") for l in open(os.path.join(ROOT, "url_slug_map.tsv")).read().strip().split("\n")]
    pages = []
    for url, slug in rows:
        cap = os.path.join(ROOT, "raw", slug + ".html")
        if not os.path.exists(cap):
            print("MISSING raw html:", slug)
            continue
        html = open(cap, encoding="utf-8", errors="replace").read()
        new = rewrite_html(html, url)
        pages.append((url, slug, new))
    print(f"Rewriting done for {len(pages)} pages; queued {len(downloaded)} assets (pre-css).")
    # download all assets (CSS discovery expands the set)
    download_all_assets()
    print(f"Total assets after css expansion: {len(downloaded)}")
    # After CSS may have added assets, re-run html rewrite NOT needed (refs already point to /assets).
    # write pages
    for url, slug, html in pages:
        outp = page_output_path(url)
        os.makedirs(os.path.dirname(outp), exist_ok=True)
        with open(outp, "w", encoding="utf-8") as f:
            f.write(html)
    # stats
    ok = sum(1 for v in downloaded.values() if v and v is not None and not isinstance(v, tuple))
    fail = [k for k, v in downloaded.items() if v is None]
    print(f"Assets downloaded OK: {ok}, failed: {len(fail)}")
    with open(os.path.join(ROOT, "download_log.txt"), "w") as f:
        for u, s in sorted(download_log, key=lambda x: str(x[1])):
            f.write(f"{s}\t{u}\n")
    with open(os.path.join(ROOT, "failed_assets.txt"), "w") as f:
        for k in fail:
            f.write(k + "\n")
    print("Wrote pages + logs.")

if __name__ == "__main__":
    main()
