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
    """Return absolute filesystem path under ASSETS for a given host+path (no query)."""
    path = path.split("?")[0].split("#")[0]
    if not path or path == "/":
        path = "/index"
    parts = [safe_segment(p) for p in path.split("/") if p != ""]
    if not parts:
        parts = ["index"]
    # if ends without extension and not clearly a file, keep as-is
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

def rewrite_html(html, base):
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
        cap = os.path.join(ROOT, "captures", slug, "page.html")
        if not os.path.exists(cap):
            print("MISSING capture:", slug)
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
