# DISCREPANCIES — friendsofhollinhills.org clone

Source: https://www.friendsofhollinhills.org/ (Weebly site, behind Cloudflare)
Approach: raw-HTML static mirror of rendered DOM + asset localization, self-hosted fonts.

## Manual handling (dynamic features that cannot work on a static host)
- **Weebly Store / Cart / Checkout** — All `/store/...` product & category pages render
  visually, but Add-to-Cart and Checkout POST to Weebly's commerce backend
  (`/cart`, `/store/checkout`, commerce-core.js endpoints). These are inert on the static
  clone. The "Donate" buttons link to store product pages (e.g.
  `/store/p36/Support_Friends_of_Hollin_Hills!.html`) which display correctly but cannot
  process payment. NOT a visual defect.
- **Contact / subscribe forms** — Weebly form blocks (reCAPTCHA-protected) POST to Weebly's
  backend; submission is inert on the static clone. Render visually correctly.
- **Cart counter "Cart (0)"** — driven by Weebly commerce JS; shows 0 statically.

## Third-party widgets kept LIVE (load from their own origins, not cloned)
- **DocsBot.ai chatbot** ("Hollin Hills Assistant") — `widget.docsbot.ai/chat.js`,
  DocsBotAI.init id preserved. Loads live.
- **POWr.io social-media-icons** iframe — `www.powr.io`. Loads live.
- **Google Analytics** `ssl.google-analytics.com/ga.js` (UA-7870337-1, Weebly's GA) — preserved.
- **Google reCAPTCHA** `www.gstatic.com/recaptcha` — preserved for form widgets.
- Weebly runtime helper scripts referenced from inline JS (snowday262.js, etc.) load from
  `cdn2/cdn11.editmysite.com` cross-origin (benign).

## Metadata
- `og:image` meta tags retain absolute origin URLs (exact reproduction of the original tags;
  they reference the live origin's image files). Not rendered visually.

## Source-side issues (reproduced as-is; NOT clone defects)
- (none found yet — see audit results)
