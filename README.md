# friendsofhollinhills.org — static clone

A high-fidelity static mirror of **https://www.friendsofhollinhills.org/** (a Weebly site for
the Friends of Hollin Hills nonprofit, Alexandria VA).

## How it was built
- **capture.js** / **batch_capture.js** — Playwright capture (deviceScaleFactor 1,
  ignoreHTTPSErrors, fixed 1440×900 / 390×844 viewports, segmented scroll-capture ≤1500px,
  auto-downscale to ≤1500px). Produces per-page spec under `captures/<slug>/`:
  screenshot-desktop*.png, screenshot-mobile*.png, page.html (rendered DOM), styles.json,
  assets.txt, fonts.txt, embeds.txt, meta.txt, links.txt.
- **mirror.py** — downloads every localizable asset into `site/assets/<host>/<path>`,
  processes CSS recursively for `url()`/`@import`, self-hosts the Weebly Google-fonts
  (Josefin Sans, Karla, Open Sans, Work Sans), and rewrites each page's asset + internal-link
  URLs to local root-relative paths. Pages written to their mirrored filesystem paths under
  `site/` (store product names URL-decoded so `%21`→`!`, `%24`→`$`).
- **compare_native.js** — Phase-6 objective pixel diff (origin vs live clone, native-res
  segments, no downscale artifact).
- **audit.js** — logs every >=400 response / requestfailed on the live clone.

## Layout
- `site/` — deployable static mirror (deployed to Vercel).
- `captures/<slug>/` — full capture spec per page (91 pages).
- `urls.txt`, `url_slug_map.tsv` — page inventory (from Weebly sitemap.xml).
- `DISCREPANCIES.md` — manual-handling list + any source-side breakage.

## Deploy
Static directory deploy: `cd site && vercel deploy --prod --yes`.
`vercel.json`: `{ "cleanUrls": false, "trailingSlash": false }`.
