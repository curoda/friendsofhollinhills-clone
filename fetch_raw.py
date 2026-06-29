#!/usr/bin/env python3
import urllib.parse, urllib.request, ssl, os, time
ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
os.makedirs("/tmp/foh/raw", exist_ok=True)
rows=[l.split("\t") for l in open("/tmp/foh/url_slug_map.tsv").read().strip().split("\n")]
ok=0; fail=[]
for url, slug in rows:
    dest=f"/tmp/foh/raw/{slug}.html"
    if os.path.exists(dest) and os.path.getsize(dest)>2000:
        ok+=1; continue
    req=urllib.request.Request(url, headers={"User-Agent":UA})
    try:
        with urllib.request.urlopen(req, timeout=45, context=ctx) as r:
            data=r.read()
        open(dest,"wb").write(data)
        ok+=1
        if len(data)<2000: fail.append((slug,f"small {len(data)}"))
    except Exception as e:
        fail.append((slug,str(e)))
    time.sleep(0.15)
print(f"fetched OK: {ok}, problems: {len(fail)}")
for s,e in fail: print("  ", s, e)
