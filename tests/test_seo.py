import unittest

from app import app


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

