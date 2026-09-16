# BlackSea Connect localization system

## Global language selection and deployment

`_resolve_current_language()` is the single server policy for public/SEO pages,
Owner, Professional, Admin, and Workspace. Supported languages remain exactly
`bg`, `en`, `fr`, and `ru`. Priority is a valid `?lang=`, then the existing
`site_lang` session preference, then a configured trusted country header, then
English. BG maps to Bulgarian, FR to French, RU to Russian; every other value
(including missing, unknown, malformed, or multiple country codes) maps to English.
Only explicit query selections are saved. Existing session preferences are
preserved, including values saved by the previous resolver: there is no historical
marker that distinguishes its automatic Bulgarian fallback from a manual choice.
Unsupported query values do not overwrite preferences. Form fields, browser
language, and IP strings do not determine the language.

The checked-in `render.yaml` does not configure a trusted country source.
Leave `TRUSTED_COUNTRY_HEADER` unset until the actual ingress is verified.
`TRUST_PROXY_HEADERS`/ProxyFix and `_current_request_ip()` are not geolocation
services and do not authorize country-header trust. There is no geolocation API,
IP-prefix guessing, or request-time network lookup.

To enable country detection, configure exactly one of `CF-IPCountry`,
`CloudFront-Viewer-Country`, or `X-Vercel-IP-Country` as the environment variable
`TRUSTED_COUNTRY_HEADER`. This is an explicit deployment trust assertion:

1. The chosen CDN must generate/overwrite that header, removing client-supplied
   values. For Cloudflare, enable proxying and IP Geolocation.
2. Prevent untrusted direct access to the origin (including alternate Render
   hostnames), or enforce header removal/overwrite on every ingress path. Merely
   pointing Cloudflare DNS at Render or enabling ProxyFix is insufficient.
3. Verify requests through the CDN and attempted direct/spoofed requests before
   enabling the variable. If these guarantees cannot be established, leave it unset.
4. Keep dynamic HTML out of shared CDN caches, or vary by both session cookie and
   the configured country header. Responses include the country header in `Vary`;
   Flask adds cookie variation when the resolver reads the session.

See [Cloudflare IP Geolocation](https://developers.cloudflare.com/network/ip-geolocation/)
and [Render Cloudflare DNS configuration](https://render.com/docs/configure-cloudflare-dns).
Live Render/CDN settings cannot be established from repository configuration alone.

Browser initialization respects server `data-page-lang`/HTML language before URL
fallback and defaults to English only when no supported language is available.
A missing translation bundle must not change the selected language. Manual
switches use the existing query/session synchronization, including clicks on the
already active language. Admin keeps native navigation; Owner dashboard keeps
its server reload. Existing internal links/forms continue carrying `lang`.
Following such a link counts as an explicit selection under the query precedence.

## Source of truth

Each public namespace is owned by one file in `static/js/i18n/`:

- `common.js` owns shared navigation and reusable public labels.
- `home.js` owns the homepage.
- `owners-request-service.js` owns the owner service-request page.
- `owners-dashboard.js` owns the owner dashboard.
- `professionals.js` owns professional pages.
- `admin-runtime.js` owns the legacy admin calendar and other admin runtime labels.

Jinja templates reference these keys with `data-i18n`, `data-i18n-attr`, or
`public_i18n(namespace, key)`. Templates must not maintain an independent
translated copy of visible text.

## Adding or changing copy

1. Add one semantic key to the owning namespace.
2. Add natural translations for `bg`, `en`, `fr`, and `ru` in the same change.
3. Bind the template to the key. Avoid a translated Jinja fallback string.
4. Run `python scripts/check_i18n.py`.
5. Run `pytest -q tests/test_multilingual_routes.py`.

All four languages are required. Empty values are treated as missing.

## Missing translations

Development and tests render `[MISSING: namespace.key]`; they never silently
substitute English. Production may use the English fallback, and logs a clear
warning containing the namespace, key, and requested language.

The browser-side runtime follows the same principle: missing values must remain
visible during local development instead of being hidden by fallback copy.

## Terminology

Use these concepts consistently:

| English | Bulgarian | French | Russian |
|---|---|---|---|
| request | заявка | demande | заявка |
| task | задача | tâche | задача |
| service provider | доставчик на услуги | prestataire | поставщик услуг |
| owner | собственик | propriétaire | владелец |
| property | имот | propriété / bien | объект недвижимости |
| photos and documents | снимки и документи | photos et documents | фотографии и документы |
| deadline | краен срок | échéance | срок |

Do not use runtime machine translation. Product copy should be reviewed by a
fluent human before release, especially legal, payment, and guest-facing text.
