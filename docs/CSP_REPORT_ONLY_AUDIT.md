# Content Security Policy: report-only audit

Audited 2026-09-21 on `audit/launch-readiness`. Scope: all templates, text assets in
`static`, and URL/resource generation in `app.py`. This is a source audit, supplemented
by vendor documentation, not a production browser network capture. Runtime provider
records, deployment settings and remote SDK behavior can introduce additional URLs.

## Current header

The existing `_apply_security_headers` hook adds this single HTTP header on all
responses. It does not add an enforcing `Content-Security-Policy` header.

```http
Content-Security-Policy-Report-Only: default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'self'; script-src 'self' 'unsafe-inline' https://www.googletagmanager.com https://*.clarity.ms; style-src 'self' 'unsafe-inline'; img-src 'self' blob: https:; font-src 'self'; connect-src 'self' https://www.googletagmanager.com https://*.google-analytics.com https://*.google.com https://*.clarity.ms https://c.bing.com; form-action 'self' https://checkout.stripe.com https://connect.stripe.com; frame-src 'self'; worker-src 'self'; manifest-src 'self'
```

This policy does not block resources or provide enforcing CSP protection. Existing
security headers, HSTS conditions, consent, sessions and admin rate limiting are unchanged.
There is no report collector, `report-uri`, `report-to` or `Reporting-Endpoints`
configuration in this change. Inspect report-only violations in browser DevTools;
reports are not collected centrally. No `report-sample` is enabled.

## Browser resource inventory and allowed external origins

`'self'` means the origin serving the response, including its scheme and port.
Wildcard host expressions below are source patterns, not individual origins.

| Resource | Evidence | Policy decision |
| --- | --- | --- |
| GA4 script | `static/js/analytics.js`, `configureAndLoad`, loads `https://www.googletagmanager.com/gtag/js` | `https://www.googletagmanager.com` in `script-src` and `connect-src` |
| GA4 telemetry | SDK-generated requests; no-Ads configuration, with Google Signals disabled in `analytics.js` | `https://*.google-analytics.com` and `https://*.google.com` in `connect-src`, following Google's no-Ads guidance; includes regional collectors |
| Clarity script and telemetry | `analytics.js` loads `https://www.clarity.ms/tag/`; SDK selects collection hosts | `https://*.clarity.ms` in `script-src` and `connect-src`; `https://c.bing.com` in `connect-src` for Clarity compatibility |
| Images, including analytics pixels | Local CSS backgrounds/icons, owner media/evidence routes; `provider.photo_url` and `provider.logo_url` in network/detail/request-service templates | `img-src 'self' blob: https:`. **All HTTPS image origins are allowed**, including the analytics origins above. This is intentionally broader than the script/connect allowlists because provider URLs are stored data with no finite origin list in source. HTTP/data images would produce reports, not be blocked by this rollout. |
| Local upload previews | `templates/professionals_task_detail.html`, `URL.createObjectURL(file)` assigned to an image | `blob:` only in `img-src`; stored IndexedDB Blob objects do not themselves require a CSP scheme allowance |
| Scripts/styles/fonts | Local `/static` files, inline code and system font stacks; no remote font stylesheet or `@font-face` found | Self-hosted scripts/styles/fonts; temporary inline allowances for scripts/styles only. Font family names such as Inter do not imply a Google Fonts request. |
| Fetch/XHR | Pilot form, concierge, language switching, calendar/admin updates, professional uploads, PWA sync/health | `'self'` in `connect-src`; no application WebSocket/EventSource origin found |
| Form submissions | Forms submit locally, including finance/Stripe endpoints | `'self'` in `form-action` |
| Stripe redirects after forms | `owner_stripe_checkout`, `professional_stripe_connect`, `professional_stripe_dashboard`, `admin_professional_stripe_connect` return SDK URLs after POST | `https://checkout.stripe.com` and `https://connect.stripe.com` in `form-action`, covering hosted destinations in browsers that check form redirect chains. No Stripe.js/Elements/embedded Checkout found, so no Stripe script/connect/frame allowance. Custom Stripe domains are not configured in source and need verification before enforcement. |
| Frames | Admin operations task drawer opens a same-origin task URL with `embed=1`, then clears to `about:blank` | `frame-src 'self'`; no external iframe, object or embed dependency found. No blanket `about:` allowance. `frame-ancestors 'self'` matches the existing SAMEORIGIN intent. |
| PWA | `pwa.js` registers `/service-worker.js`; local manifest and icons | `worker-src 'self'`, `manifest-src 'self'` |
| Data URLs | Only a URL-filter exclusion in `static/js/i18n.js`; no actual resource construction/use found | No `data:` allowance |

The complete external source expressions are `https://www.googletagmanager.com`,
`https://*.google-analytics.com`, `https://*.google.com`, `https://*.clarity.ms`,
`https://c.bing.com`, `https://checkout.stripe.com`, `https://connect.stripe.com`,
plus **every HTTPS origin for images only**. There is no blanket `https:` allowance
for scripts, connections, fonts, forms or frames.

The GA4 entry point uses Google's tag host; no separate `GTM-...` container, GTM
Preview, Custom JavaScript variables, Ads or third-party tag configuration was found.
Those features are not grounds to add `unsafe-eval`, DoubleClick, remote fonts or
external frames. Analytics source allowances do not load analytics or change consent.

## Other domains/URLs found, outside browser subresource loading

| Origin or URL source | Use; why it is not added to browser resource directives |
| --- | --- |
| `https://wa.me` | User-initiated WhatsApp navigation from guest portal links |
| `https://www.google.com`, `https://maps.apple.com` | `window.open` map navigation in professional task detail; Google also appears independently in the analytics connection pattern |
| Provider `website`, generated magic/invitation links, configured `SITE_URL` | Navigation or email links, not remote scripts/fonts |
| `https://api.telegram.org`, `https://api.resend.com` | Server-side notification HTTP calls in `app.py` |
| Configured Formspree endpoint, SMTP host, `OLLAMA_BASE_URL` (default `http://localhost:11434`), imported ICS URLs | Server-side HTTP/mail integrations; arbitrary configured/imported destinations cannot be enumerated from source |
| Stripe SDK API traffic (`api.stripe.com`) | Server-side API calls, distinct from the browser redirects listed above |
| `http://127.0.0.1:5000` | Local application URL fallback |
| `https://schema.org`, `http://www.w3.org/2000/svg`, `http://www.sitemaps.org/schemas/sitemap/0.9` | Structured-data/XML namespace identifiers; not resource fetches |
| `https://example.com`, `https://.../calendar.ics` | Input placeholders |

Browser CSP does not restrict server-side network access. This audit does not change
these integrations or their authorization/input-validation behavior.

## Inline technical debt

A raw source scan of templates found 33 `<style>` blocks, 19 script tags without
`src` (including JSON/JSON-LD data blocks), 97 `style=` occurrences and 10 inline
event-handler occurrences (including generated HTML strings). These counts describe
source occurrences, not rendered DOM counts or 19 executable scripts.

- Executable inline scripts: home page, calendar, admin operations task drawer,
  professional task details and other templates.
- Inline style blocks: calendar layout overrides, admin screens, professional
  task detail; also two HTML templates embedded in `app.py` for admin demo/workspace.
- Inline style attributes: layout overrides, provider image sizing, progress widths,
  dynamic workload/checklist percentages and embedded workspace HTML.
- Inline `onsubmit`/`onclick`: confirmation/actions in admin operations details,
  owners dashboard/property detail and professional task detail. Nonces on script
  tags alone will not authorize these attributes.
- JSON/JSON-LD blocks need an explicit browser-tested handling strategy; they are
  not equivalent to executable inline JavaScript.
- `translations.js` generates same-origin script tags with `document.write`.
  This is allowed by the current host policy and does not require `unsafe-eval`;
  revisit it when adopting nonce/strict-dynamic loading.
- JavaScript writes dynamic style properties in calendar/progress/preview code.
  Do not assume every CSSOM property assignment requires `unsafe-inline`; verify
  those flows separately from literal style attributes during migration.

The `unsafe-inline` exceptions are **report-only migration debt**, not a policy to
copy into an enforcing header. No application `eval`/`new Function` use was found.
HTML email styles generated by `app.py` are outside the site's document CSP.

## Migration to enforcement

1. Exercise public/admin/owner/professional pages, all languages, accepted/rejected
   analytics consent, uploads/previews, task iframe, PWA/offline flows and Stripe
   redirects in staging browsers. Capture actual SDK origins and redirect chains;
   this source audit and Flask tests cannot validate remote SDK network behavior.
2. Configure a report collector with bounded payloads, rate limits and URL/query
   redaction before collecting production reports; add reporting directives only
   when that endpoint exists. Avoid collecting document content or credentials.
3. Move executable inline JS into static modules and event handlers into
   `addEventListener`. Use JSON/data attributes for server values. If inline script
   remains, use fresh per-response nonces or reviewed hashes; never a fixed nonce.
4. Move inline CSS into static styles/classes. For indispensable style blocks,
   use nonces/hashes and audit dynamic values separately. Remove style attributes;
   a nonce on a `<style>` block does not cover them.
5. Inventory approved provider image origins and replace the image-wide `https:`
   allowance with exact hosts, or serve managed images from the application.
   Verify deployment-specific Stripe custom domains and analytics settings.
6. Remove `unsafe-inline` in a stricter report-only candidate after migration.
   The current permissive inline policy will not report allowed inline constructs.
   Resolve unexpected reports before enabling enforcement; do not auto-allow every
   reported origin. Re-run regression and browser checks, then stage an explicit
   change to the enforcing header. Keep `unsafe-eval` absent.

## Vendor references

- [Google CSP guide, Analytics without Ads](https://developers.google.com/tag-platform/security/guides/csp)
- [Microsoft Clarity CSP guidance](https://learn.microsoft.com/en-us/clarity/setup-and-installation/clarity-csp)
- [Stripe Checkout Sessions](https://docs.stripe.com/api/checkout/sessions)
- [Stripe account links](https://docs.stripe.com/api/account_links/create)
- [Stripe official web destinations](https://support.stripe.com/questions/verify-you-are-on-an-official-stripe-webpage)
