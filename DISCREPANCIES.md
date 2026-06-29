# DISCREPANCIES — friendsofhollinhills.org clone

- **Source:** https://www.friendsofhollinhills.org/ (Weebly site, behind Cloudflare)
- **Live clone:** https://friendsofhollinhills-clone.vercel.app/
- **Approach:** static mirror of the **raw server HTML** + asset localization, self-hosted fonts,
  preserved client JS (so the Weebly slideshow, mobile hamburger menu, ScrollReveal, social
  icons, chatbot and Google-map iframe all initialise and behave like the origin).
- **Pages:** 91 (entire sitemap.xml). Desktop + mobile pixel-diff vs origin: every page
  essentially pixel-identical (≈0%) except auto-rotating slideshow pages (see LOW below).

## Final discrepancy table
| page | element | original | clone | severity | status |
|------|---------|----------|-------|----------|--------|
| home, events, living-modern, program, supporters, turkey-trot, drinks-with-friends | full-width image slideshow | rotating | rotating (same images, independent timing) | LOW | by-design; not fixable in a static diff |
| all pages | header "Cart (N)" | `Cart (0)` from live backend | `Cart (0)` forced by clone-fixes script | — | FIXED (matches) |

No HIGH or MEDIUM discrepancies remain. Remaining differences are LOW (independently-timed
slideshow frames) and do not represent layout/content/style defects — text, layout, fonts,
colours, spacing, nav (incl. mobile hamburger), embeds, link hrefs and metadata all match.

## Manual handling (dynamic features that cannot function on a static host)
- **Weebly Store / Cart / Checkout** — every `/store/...` product & category page renders
  visually, but Add-to-Cart / Checkout POST to Weebly's commerce backend. Inert on the clone.
  The header cart widget fires `/ajax/api/JsonRPC/Commerce…getMiniCart` and
  `…CustomerAccounts…getAccountDetails`, which 404 on a static host (the ONLY clone-side audit
  findings — expected, non-visual; the visible "Cart (0)" is forced by a small script).
- **Contact / subscribe forms** — Weebly form blocks (reCAPTCHA-protected) POST to Weebly's
  backend; render correctly, submission inert.
- **Blog comment form** (news posts) — `showCommentForm` loads live from www.weebly.com;
  submission inert.
- **Donate buttons** — link to store product pages (e.g.
  `/store/p36/Support_Friends_of_Hollin_Hills!.html`); display correctly, payment inert.

## Third-party widgets kept LIVE (load from their own origins — faithful to origin)
- **DocsBot.ai chatbot** ("Hollin Hills Assistant") — `widget.docsbot.ai/chat.js` (init id preserved).
- **POWr.io social-media-icons** iframe — `www.powr.io`.
- **Google Map** (contact, program) — `//www.weebly.com/weebly/apps/generateMap.php?…` iframe
  redirects to editmysite.com → Google Maps JS; renders the same live map as the origin.
- **Google Analytics** `ssl.google-analytics.com/ga.js` (UA-7870337-1, Weebly's GA) — preserved.
- **Google reCAPTCHA** `www.gstatic.com/recaptcha` — preserved for form widgets.
- Weebly runtime helper scripts (snowday262.js etc.) referenced from inline JS load from
  cdn2/cdn11.editmysite.com cross-origin (benign).

## Source-side / third-party breakage (NOT clone defects; reproduced or benign)
- `bam.nr-data.net` New Relic beacon (403/ERR_ABORTED) — fired from inside the POWr social-icons
  iframe; third-party, also occurs on the origin. Benign.

## Notes
- `og:image` meta tags retain absolute origin URLs (exact reproduction of the original tags).
- Cloudflare email-obfuscation in the raw HTML was decoded to plain `mailto:` links (the rendered
  origin shows them decoded too).
