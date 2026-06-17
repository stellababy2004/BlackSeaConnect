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

