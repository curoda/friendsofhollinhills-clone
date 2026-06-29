#!/usr/bin/env python3
import urllib.parse, re

BASE = "https://www.friendsofhollinhills.org"
urls = []
with open("/tmp/foh/sitemap_urls.txt") as f:
    for line in f:
        u = line.strip()
        if u:
            urls.append(u)

# Normalize: index.html -> homepage "/"
norm = []
seen = set()
# ensure homepage present
norm.append(BASE + "/")
seen.add(BASE + "/")
for u in urls:
    if u.rstrip("/") == BASE or u.endswith("/index.html"):
        continue  # homepage already added
    if u not in seen:
        norm.append(u)
        seen.add(u)

def slug_for(u):
    p = urllib.parse.urlparse(u)
    path = p.path
    if path in ("", "/"):
        return "home"
    # decode percent-encoding for readability in slug
    dec = urllib.parse.unquote(path)
    dec = dec.lstrip("/")
    if dec.endswith(".html"):
        dec = dec[:-5]
    # replace path separators and unsafe chars
    s = re.sub(r"[^A-Za-z0-9._-]+", "-", dec)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "home"

with open("/tmp/foh/urls.txt", "w") as f:
    for u in norm:
        f.write(u + "\n")

with open("/tmp/foh/url_slug_map.tsv", "w") as f:
    for u in norm:
        f.write(f"{u}\t{slug_for(u)}\n")

print(f"Total pages: {len(norm)}")
for u in norm:
    print(f"{slug_for(u):60s} <- {u}")
