from dataclasses import replace
import unittest

import app


class PublicAnalyticsTests(unittest.TestCase):
    def setUp(self):
        self.settings = app.SETTINGS
        self.testing = app.app.testing
        app.app.testing = False
        self.client = app.app.test_client()

    def tearDown(self):
        app.SETTINGS = self.settings
        app.app.testing = self.testing

    def test_analytics_is_absent_when_disabled_or_unconfigured(self):
        app.SETTINGS = replace(self.settings, environment="production", analytics_enabled=False)
        self.assertNotIn(b"data-analytics-consent", self.client.get("/").data)
        app.SETTINGS = replace(self.settings, environment="production", analytics_enabled=True, ga4_measurement_id="", microsoft_clarity_project_id="")
        self.assertNotIn(b"data-analytics-consent", self.client.get("/").data)

    def test_enabled_configuration_is_consent_gated_and_localized(self):
        app.SETTINGS = replace(
            self.settings,
            environment="production",
            analytics_enabled=True,
            ga4_measurement_id="G-ABC1234567",
            microsoft_clarity_project_id="abc123def",
        )
        body = self.client.get("/?lang=fr").get_data(as_text=True)
        self.assertIn("data-analytics-consent", body)
        self.assertIn("G-ABC1234567", body)
        self.assertIn("Accepter les analyses", body)
        self.assertNotIn("name@example.com", body[body.index("data-analytics-consent"):])

    def test_private_portals_are_not_included(self):
        app.SETTINGS = replace(self.settings, environment="production", analytics_enabled=True, ga4_measurement_id="G-ABC1234567")
        self.assertNotIn(b"data-analytics-consent", self.client.get("/owners/dashboard").data)


if __name__ == "__main__":
    unittest.main()
