import unittest
from pathlib import Path


class PublicCardSystemTests(unittest.TestCase):
    def setUp(self):
        self.styles_path = Path(__file__).resolve().parents[1] / "static" / "css" / "styles.css"
        self.template_path = Path(__file__).resolve().parents[1] / "templates" / "index.html"
        self.i18n_path = Path(__file__).resolve().parents[1] / "static" / "js" / "i18n.js"
        self.styles = self.styles_path.read_text(encoding="utf-8")
        self.template = self.template_path.read_text(encoding="utf-8")
        self.i18n = self.i18n_path.read_text(encoding="utf-8")

    def test_shared_card_tokens_are_defined(self):
        for token in [
            "--card-bg",
            "--card-bg-strong",
            "--card-border",
            "--card-text",
            "--card-muted",
            "--card-accent",
            "--card-shadow",
        ]:
            with self.subTest(token=token):
                self.assertIn(token, self.styles)

    def test_surface_component_classes_are_defined(self):
        for selector in [
            ".surface-light",
            ".surface-dark",
            ".surface-form",
            ".surface-empty",
            ".surface-kpi",
            ".surface-hero",
        ]:
            with self.subTest(selector=selector):
                self.assertIn(selector, self.styles)

    def test_public_card_system_covers_key_selectors(self):
        for selector in [
            ".glass-card",
            ".hero-card",
            ".feature-card",
            ".trust-card",
            ".partner-card",
            ".professional-card",
            ".network-card",
            ".resource-card",
            ".home-resource-card",
            ".empty-state",
            ".request-card",
            ".cta-panel",
            ".operations-panel",
            ".operations-workflow__step",
            ".operations-list__item",
            ".operations-notification",
            ".site-footer",
            "body.home-page .trust-card",
            "body.home-page .owner-portal-section",
            "body.home-page .owner-fit-section",
            "body.home-page .home-light-section",
            "body.partners-page .partner-card",
            "body.professionals-page .trust-card",
            "body.guest-homepage-page .guest-portal-card",
            "body.operations-demo-page .operations-panel",
            "body.seo-longform-page .trust-card",
        ]:
            with self.subTest(selector=selector):
                self.assertIn(selector, self.styles)

    def test_public_override_tail_avoids_black_card_values(self):
        start = self.styles.index("/* Service-card readability pass: keep the light coastal panels readable. */")
        tail = self.styles[start:]

        self.assertNotIn("#000", tail)
        self.assertNotIn("rgba(0,0,0", tail)
        self.assertIn("color: #10223D !important;", tail)
        self.assertIn("color: rgba(16, 34, 61, 0.82) !important;", tail)
        self.assertIn("color: #B9892B !important;", tail)

    def test_homepage_light_sections_use_shared_glass_container(self):
        for selector in [
            'class="home-product"',
            'class="owner-portal-section home-light-section"',
            'class="owner-fit-section home-light-section"',
            'class="cta-panel home-light-section"',
        ]:
            with self.subTest(selector=selector):
                self.assertIn(selector, self.template)

        for selector in [
            "body.home-page .home-light-section {",
            "body.home-page .home-light-section .feature-card,",
            "body.home-page .home-light-section .owner-portal-card,",
            "body.home-page .home-light-section .owner-fit-card {",
            "body.home-page .home-light-section .cta-panel__content {",
        ]:
            with self.subTest(selector=selector):
                self.assertIn(selector, self.styles)

        for removed in [
            'class="credibility-layer home-light-section"',
            'class="trust-layer home-light-section"',
            'class="trust-layer home-resources home-light-section"',
        ]:
            with self.subTest(removed=removed):
                self.assertNotIn(removed, self.template)

        for value in [
            "border-radius: clamp(28px, 4vw, 56px);",
            "background:\n    linear-gradient(135deg, rgba(248, 250, 252, 0.96), rgba(232, 239, 248, 0.90)) !important;",
            "box-shadow:\n    0 28px 80px rgba(8, 24, 44, 0.18),\n    inset 0 1px 0 rgba(255, 255, 255, 0.92) !important;",
            "backdrop-filter: blur(18px) saturate(130%) !important;",
            "overflow: hidden;",
            "max-width: 22ch;",
        ]:
            with self.subTest(value=value):
                self.assertIn(value, self.styles)

    def test_homepage_language_switcher_and_aria_labels_are_scoped(self):
        for selector in [
            'data-lang-switch="bg"',
            'data-lang-switch="en"',
            'data-lang-switch="fr"',
            'data-lang-switch="ru"',
            'data-i18n-attr="aria-label:homePrimaryNavLabel"',
            'data-i18n-attr="aria-label:homeSiteNavLabel"',
            'data-i18n-attr="aria-label:homeLanguageSwitcherLabel"',
            'data-i18n-attr="aria-label:homePlatformSignalsLabel"',
            'data-i18n-attr="aria-label:homePreviewMetricsLabel"',
            'data-i18n-attr="aria-label:homeKpiOverviewLabel"',
            'data-i18n-attr="aria-label:homeFooterLinksLabel"',
        ]:
            with self.subTest(selector=selector):
                self.assertIn(selector, self.template)

        for snippet in [
            "url.pathname",
            "url.searchParams.set(\"lang\", lang)",
            "url.hash",
            "window.history.replaceState",
            "syncLanguageControls(activeLang)",
        ]:
            with self.subTest(snippet=snippet):
                self.assertIn(snippet, self.i18n)

    def test_i18n_resolver_stays_within_the_requested_namespace(self):
        for snippet in [
            "for (const section of Object.values(dictionary))",
            "for (const section of Object.values(fallbackDictionary))",
            "const leafKey = key.split(\".\").pop();",
            "Object.prototype.hasOwnProperty.call(section, leafKey)",
        ]:
            with self.subTest(snippet=snippet):
                self.assertNotIn(snippet, self.i18n)

    def test_mobile_override_covers_bottom_surfaces(self):
        start = self.styles.index("@media (max-width: 768px) {\n  .cta-panel,")
        tail = self.styles[start:]

        for selector in [
            ".site-footer",
            ".cta-panel",
            "body.home-page .home-resource-card",
            "body.home-page .home-light-section",
            "body.owner-portal-page .admin-cockpit-panel",
            "body.guest-homepage-page .guest-kpi-card",
            "body.operations-demo-page .operations-mobile-dock",
            "body.seo-longform-page .trust-layer",
        ]:
            with self.subTest(selector=selector):
                self.assertIn(selector, tail)

        self.assertIn("body.home-page.home-page .hero.hero--home", self.styles)
        self.assertIn("body.home-page.home-page .hero.hero--home .hero__content", self.styles)
        self.assertIn("body.home-page.home-page .hero__content--home", self.styles)
        self.assertIn("@media (max-width: 768px) {\n  .section-heading {\n    margin-bottom: 14px !important;\n  }\n}", self.styles)
        self.assertIn("min-height: 0 !important;", self.styles)
        self.assertIn("color: #F8F6F2 !important;", self.styles)
        self.assertIn("-webkit-text-fill-color: #F8F6F2 !important;", self.styles)
        self.assertIn("rgba(255, 250, 243, 0.96)", tail)
        self.assertIn("#10223D !important;", tail)
        self.assertIn("body.home-page .home-light-section {", tail)

    def test_mobile_operations_preview_rows_do_not_overlap(self):
        start = self.styles.index("/* Final mobile operations preview fit EOF anchor. */")
        tail = self.styles[start:]

        for selector in [
            "body.operations-demo-page .operations-preview-card__notes > div",
            "body.operations-demo-page .operations-stack .operations-feed__item",
            "body.operations-demo-page .operations-preview-card__notes > div > span",
            "body.operations-demo-page .operations-stack .operations-feed__item > time",
            "body.operations-demo-page .operations-stack .operations-feed__badge",
            "body.operations-demo-page .operations-stack .operations-property-card__metric span",
            "body.operations-demo-page .operations-stack .operations-property-card__metric strong",
            ".home-product .home-product__preview-row",
        ]:
            with self.subTest(selector=selector):
                self.assertIn(selector, tail)

        for value in [
            "grid-template-columns: auto minmax(0, 1fr) !important;",
            "min-width: 0 !important;",
            "overflow-wrap: anywhere !important;",
            "white-space: normal !important;",
            "white-space: nowrap !important;",
            "-webkit-text-fill-color: #F8F6F2 !important;",
        ]:
            with self.subTest(value=value):
                self.assertIn(value, tail)

    def test_services_mobile_override_is_scoped_to_credibility_layer(self):
        for selector in [
            ".credibility-layer,\n  .trust-layer {\n    --card-coastal-text: #F8F6F2;",
            ".credibility-layer .feature-grid",
            ".credibility-layer .feature-card",
            ".credibility-layer .feature-card h3",
            ".credibility-layer .feature-card p",
            ".credibility-layer .feature-card .feature-card__icon",
            ".credibility-layer .section-heading",
            ".credibility-layer .section-heading__eyebrow",
        ]:
            with self.subTest(selector=selector):
                self.assertIn(selector, self.styles)

        self.assertIn("grid-auto-rows: auto !important;", self.styles)
        self.assertIn("aspect-ratio: auto !important;", self.styles)
        self.assertIn("--card-coastal-text: #F8F6F2;", self.styles)
        self.assertIn("color: #F8F6F2 !important;", self.styles)
        self.assertIn("color: rgba(248, 246, 242, 0.86) !important;", self.styles)
        self.assertIn("color: #E7D7A5 !important;", self.styles)

    def test_mobile_credibility_spacing_is_compact(self):
        for selector in [
            ".credibility-layer > .section-heading",
            ".trust-layer > .section-heading",
            ".trust-layer > .section-heading--trust",
            ".credibility-layer > .feature-grid",
            ".trust-layer > .trust-grid",
            ".credibility-layer > .feature-grid > .feature-card",
            ".trust-layer > .trust-grid > .trust-card",
        ]:
            with self.subTest(selector=selector):
                self.assertIn(selector, self.styles)

        for value in [
            "padding-top: 22px !important;",
            "margin-bottom: 10px !important;",
            "margin-top: 0 !important;",
            "gap: 12px !important;",
            "margin-bottom: 14px !important;",
            "min-height: 0 !important;",
            "padding: 22px 22px 20px !important;",
            "margin: 0 0 10px !important;",
            "margin-bottom: 12px !important;",
        ]:
            with self.subTest(value=value):
                self.assertIn(value, self.styles)

    def test_mobile_card_overlays_render_below_content(self):
        for selector in [
            ".credibility-layer > .feature-grid > .feature-card::before",
            ".credibility-layer > .feature-grid > .feature-card::after",
            ".trust-layer > .trust-grid > .trust-card::before",
            ".trust-layer > .trust-grid > .trust-card::after",
            ".credibility-layer > .feature-grid > .feature-card > *",
            ".trust-layer > .trust-grid > .trust-card > *",
        ]:
            with self.subTest(selector=selector):
                self.assertIn(selector, self.styles)

        self.assertIn("isolation: isolate !important;", self.styles)
        self.assertIn("z-index: 0 !important;", self.styles)
        self.assertIn("z-index: 1 !important;", self.styles)

    def test_mobile_trust_card_text_override_wins_late_cascade(self):
        for selector in [
            ".trust-layer > .trust-grid > .trust-card h3",
            ".trust-layer > .trust-grid > .trust-card p",
            ".credibility-layer > .feature-grid > .feature-card h3",
            ".credibility-layer > .feature-grid > .feature-card p",
        ]:
            with self.subTest(selector=selector):
                self.assertIn(selector, self.styles)

        self.assertIn("#F8F6F2", self.styles)
        self.assertIn("-webkit-text-fill-color", self.styles)

    def test_mobile_partner_network_light_cards_use_navy_text(self):
        start = self.styles.index("/* Final mobile partner network contrast: light pearl cards use navy text. */")
        tail = self.styles[start:]

        for selector in [
            'body.partners-page .trust-layer > .trust-grid > .trust-card h3',
            'body.partners-page .trust-layer > .trust-grid > .trust-card p',
            'body.home-page .trust-layer[aria-labelledby="partners-title"] > .trust-grid > .trust-card h3',
            'body.home-page .trust-layer[aria-labelledby="partners-title"] > .trust-grid > .trust-card p',
            'body.partners-page .trust-layer .section-heading__eyebrow',
            'body.home-page .trust-layer[aria-labelledby="partners-title"] .section-heading__eyebrow',
        ]:
            with self.subTest(selector=selector):
                self.assertIn(selector, tail)

        for value in [
            "color: #0B2742 !important;",
            "-webkit-text-fill-color: #0B2742 !important;",
            "color: rgba(11, 39, 66, 0.78) !important;",
            "-webkit-text-fill-color: rgba(11, 39, 66, 0.78) !important;",
            "color: #B9892B !important;",
        ]:
            with self.subTest(value=value):
                self.assertIn(value, tail)

    def test_mobile_guest_kpi_light_cards_assign_role_colors(self):
        start = self.styles.index("/* Final mobile guest KPI light-card role contrast. */")
        tail = self.styles[start:]

        for selector in [
            "body.guest-homepage-page .guest-kpi-grid > .guest-kpi-card .guest-kpi-card__value",
            "body.guest-homepage-page .guest-kpi-grid > .guest-kpi-card .guest-kpi-card__label",
            "body.guest-homepage-page .guest-kpi-grid > .guest-kpi-card .feature-card__icon",
            "body.guest-homepage-page .guest-kpi-grid > .guest-kpi-card > p:not(.guest-kpi-card__label)",
        ]:
            with self.subTest(selector=selector):
                self.assertIn(selector, tail)

        for value in [
            "color: #0B2742 !important;",
            "-webkit-text-fill-color: #0B2742 !important;",
            "color: #C58A00 !important;",
            "-webkit-text-fill-color: #C58A00 !important;",
            "color: rgba(11, 39, 66, 0.78) !important;",
            "-webkit-text-fill-color: rgba(11, 39, 66, 0.78) !important;",
        ]:
            with self.subTest(value=value):
                self.assertIn(value, tail)

    def test_shared_topbar_wrap_guard_keeps_navigation_horizontal(self):
        start = self.styles.index("/* Shared desktop navbar wrap guard: keep pills horizontal and wrap whole buttons only. */")
        tail = self.styles[start:]

        for selector in [
            ".topbar,",
            ".operations-topbar,",
            ".hero--home .topbar {",
            ".topbar__actions,",
            ".operations-topbar__actions,",
            ".operations-topbar__status {",
            ".site-nav,",
            ".operations-topbar .site-nav {",
            ".site-nav__link,",
            ".language-switcher__button,",
            ".topbar__portal,",
            ".operations-button {",
        ]:
            with self.subTest(selector=selector):
                self.assertIn(selector, tail)

        for value in [
            "white-space: nowrap !important;",
            "min-width: max-content !important;",
            "flex: 0 0 auto !important;",
            "overflow-wrap: normal !important;",
            "word-break: normal !important;",
        ]:
            with self.subTest(value=value):
                self.assertIn(value, tail)

    def test_mobile_home_credibility_light_cards_use_navy_text(self):
        start = self.styles.index(".home-page .credibility-layer > .feature-grid > .home-kpi-card {")
        tail = self.styles[start:]

        for selector in [
            ".home-page .credibility-layer > .feature-grid > .home-kpi-card",
            ".home-page .credibility-layer > .feature-grid > .home-kpi-card .home-kpi-card__icon",
            ".home-page .credibility-layer > .feature-grid > .home-kpi-card__label",
            ".home-page .credibility-layer > .feature-grid > .home-kpi-card p",
            ".home-page .credibility-layer > .feature-grid > .home-kpi-card__value",
        ]:
            with self.subTest(selector=selector):
                self.assertIn(selector, tail)

        for value in [
            "color: #0f2345 !important;",
            "-webkit-text-fill-color: #0f2345 !important;",
            "background: linear-gradient(135deg, rgba(236, 220, 182, 0.94), rgba(210, 226, 232, 0.74)) !important;",
            "font-weight: 800 !important;",
            "font-size: clamp(2.05rem, 10.8vw, 2.9rem) !important;",
        ]:
            with self.subTest(value=value):
                self.assertIn(value, tail)

    def test_mobile_public_card_readability_pass_covers_light_cards(self):
        start = self.styles.index("/* Final mobile public-card readability pass. */")
        tail = self.styles[start:]

        for selector in [
            "body.home-page .feature-card",
            "body.home-page .trust-card",
            "body.home-page .owner-portal-section .owner-portal-card",
            "body.home-page .owner-fit-section .owner-fit-card",
            "body.home-page .cta-panel",
            "body.operations-demo-page .operations-panel",
            "body.guest-homepage-page .guest-kpi-card",
            "body.partners-page .trust-card",
            "body.professionals-page .cta-panel",
            "body.owner-portal-page .admin-cockpit-panel",
            "body.home-page .feature-card .feature-card__icon",
            "body.home-page .trust-strip__chip",
        ]:
            with self.subTest(selector=selector):
                self.assertIn(selector, tail)

        for value in [
            "border-color: rgba(15, 35, 69, 0.16) !important;",
            "color: #0f2345 !important;",
            "-webkit-text-fill-color: #0f2345 !important;",
            "opacity: 1 !important;",
            "font-weight: 700 !important;",
            "line-height: 1.55 !important;",
            "background:\n      linear-gradient(135deg, rgba(236, 220, 182, 0.72), rgba(210, 226, 232, 0.60)) !important;",
        ]:
            with self.subTest(value=value):
                self.assertIn(value, tail)
