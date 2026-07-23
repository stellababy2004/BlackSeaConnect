# BlackSea Connect localization system

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
