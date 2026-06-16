import unittest

from app import app
from seo_pages import SEO_LANDING_PAGES


class SeoRoutesTests(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_robots_txt_exposes_sitemap(self):
        response = self.client.get("/robots.txt")

        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("Sitemap: https://blackseaconnect.com/sitemap.xml", body)

    def test_sitemap_xml_exposes_public_pages(self):
        response = self.client.get("/sitemap.xml")

        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("https://blackseaconnect.com", body)
        self.assertIn("/services", body)
        self.assertIn("/guest/a-302", body)
        self.assertIn("/concierge-bulgaria", body)
        self.assertIn("/property-management-bulgaria", body)
        self.assertIn("/guest-experience-services", body)
        self.assertIn("/vacation-rental-operations", body)
        self.assertIn("/sveti-vlas-concierge-services", body)

    def test_homepage_includes_canonical_url(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn('<link rel="canonical" href="https://blackseaconnect.com/">', body)

    def test_homepage_includes_json_ld(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn('application/ld+json', body)
        self.assertIn('"@type": "Organization"', body)
        self.assertIn('"@type": "WebSite"', body)

    def test_services_page_includes_service_json_ld(self):
        response = self.client.get("/services")

        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn('application/ld+json', body)
        self.assertIn('"@type": "Service"', body)

    def test_seo_landing_pages_are_indexable_and_canonical(self):
        for path in [
            "/concierge-bulgaria",
            "/property-management-bulgaria",
            "/guest-experience-services",
            "/vacation-rental-operations",
            "/sveti-vlas-concierge-services",
        ]:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                body = response.get_data(as_text=True)
                self.assertIn(f'<link rel="canonical" href="https://blackseaconnect.com{path}">', body)
                self.assertIn('application/ld+json', body)
                self.assertIn('"@type": "Service"', body)

    def test_seo_landing_pages_do_not_expose_raw_jinja_placeholders(self):
        placeholders = (
            "{{ page.title }}",
            "{{ page.description }}",
            "{{ page.slug }}",
        )

        for path in [
            "/concierge-bulgaria",
            "/property-management-bulgaria",
            "/guest-experience-services",
            "/vacation-rental-operations",
            "/sveti-vlas-concierge-services",
        ]:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                body = response.get_data(as_text=True)
                for placeholder in placeholders:
                    self.assertNotIn(placeholder, body)

    def test_seo_landing_pages_render_all_supported_languages(self):
        for path in [
            "/concierge-bulgaria",
            "/property-management-bulgaria",
            "/guest-experience-services",
            "/vacation-rental-operations",
            "/sveti-vlas-concierge-services",
        ]:
            for lang in ["bg", "en", "fr", "ru"]:
                with self.subTest(path=path, lang=lang):
                    response = self.client.get(f"{path}?lang={lang}")
                    self.assertEqual(response.status_code, 200)
                    body = response.get_data(as_text=True)
                    self.assertNotIn("{{ page.title }}", body)
                    self.assertNotIn("{{ page.description }}", body)
                    self.assertNotIn("{{ page.slug }}", body)

    def test_concierge_bulgaria_bg_is_not_english(self):
        response = self.client.get("/concierge-bulgaria?lang=bg")

        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertNotIn("Should remove friction", body)
        self.assertIn("Консиерж услуги в България", body)

    def test_concierge_bulgaria_fr_contains_french_text(self):
        response = self.client.get("/concierge-bulgaria?lang=fr")

        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("Services de conciergerie en Bulgarie", body)

    def test_concierge_bulgaria_ru_contains_russian_text(self):
        response = self.client.get("/concierge-bulgaria?lang=ru")

        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("Консьерж-услуги в Болгарии", body)

    def test_seo_pages_render_distinct_localized_bodies(self):
        for path in [
            "/concierge-bulgaria",
            "/property-management-bulgaria",
            "/guest-experience-services",
            "/vacation-rental-operations",
            "/sveti-vlas-concierge-services",
        ]:
            with self.subTest(path=path):
                english_hero = SEO_LANDING_PAGES[path]["h1"]
                localized_bodies = {}

                for lang in ["bg", "fr", "ru"]:
                    response = self.client.get(f"{path}?lang={lang}")
                    self.assertEqual(response.status_code, 200)
                    body = response.get_data(as_text=True)
                    localized_bodies[lang] = body
                    self.assertNotIn(english_hero, body)

                self.assertNotEqual(localized_bodies["bg"], localized_bodies["fr"])
                self.assertNotEqual(localized_bodies["bg"], localized_bodies["ru"])
                self.assertNotEqual(localized_bodies["fr"], localized_bodies["ru"])
