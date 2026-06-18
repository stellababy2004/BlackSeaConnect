import unittest
from pathlib import Path


class PublicCardSystemTests(unittest.TestCase):
    def setUp(self):
        self.styles_path = Path(__file__).resolve().parents[1] / "static" / "css" / "styles.css"
        self.styles = self.styles_path.read_text(encoding="utf-8")

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

    def test_mobile_override_covers_bottom_surfaces(self):
        start = self.styles.rindex("@media (max-width: 768px) {")
        tail = self.styles[start:]

        for selector in [
            ".site-footer",
            ".cta-panel",
            "body.home-page .home-resource-card",
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
