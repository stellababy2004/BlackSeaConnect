import html
import json
import re
import unittest
import xml.etree.ElementTree as ET

import app as app_module

app = app_module.app
from seo_pages import SEO_LANDING_PAGES


class SeoRoutesTests(unittest.TestCase):
    def setUp(self):
        self.original_site_url = app_module.SITE_URL
        self.original_google_verification = app_module.GOOGLE_SITE_VERIFICATION
        self.original_bing_verification = app_module.BING_SITE_VERIFICATION
        app_module.SITE_URL = "https://blackseaconnect.com"
        app_module.GOOGLE_SITE_VERIFICATION = ""
        app_module.BING_SITE_VERIFICATION = ""
        app.config["TESTING"] = True
        self.client = app.test_client()

    def tearDown(self):
        app_module.SITE_URL = self.original_site_url
        app_module.GOOGLE_SITE_VERIFICATION = self.original_google_verification
        app_module.BING_SITE_VERIFICATION = self.original_bing_verification

    def test_robots_txt_exposes_sitemap(self):
        response = self.client.get("/robots.txt")

        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("Disallow: /admin", body)
        self.assertIn("Disallow: /auth", body)
        self.assertIn("Disallow: /owners", body)
        self.assertNotIn("Disallow: /static", body)
        self.assertIn("Sitemap: https://blackseaconnect.com/sitemap.xml", body)

    def test_sitemap_xml_exposes_public_pages(self):
        response = self.client.get("/sitemap.xml")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content_type, "application/xml; charset=utf-8")
        root = ET.fromstring(response.get_data(as_text=True))
        namespace = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        urls = [node.text for node in root.findall("sm:url/sm:loc", namespace)]
        self.assertEqual(len(urls), len(set(urls)))
        self.assertTrue(all(url.startswith("https://blackseaconnect.com/") for url in urls))
        for path in ("/services", "/concierge-bulgaria", "/property-management-bulgaria", "/guest-experience-services", "/vacation-rental-operations", "/sveti-vlas-concierge-services"):
            self.assertIn(f"https://blackseaconnect.com{path}", urls)
        for path in ("/admin", "/auth", "/guest/a-302", "/owners/register", "/partners/apply", "/professionals/apply", "/request-service"):
            self.assertFalse(any(path in url for url in urls), msg=path)

    def test_homepage_includes_canonical_url(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn('<link rel="canonical" href="https://blackseaconnect.com/">', body)
        self.assertNotIn("noindex", body.lower())
        self.assertNotIn("X-Robots-Tag", response.headers)

    def test_homepage_metadata_is_localized_for_bg_en_fr(self):
        expected = {
            "bg": "Платформа за имотни и хотелски операции",
            "en": "Property &amp; hospitality operations platform",
            "fr": "Plateforme d’opérations immobilières et hôtelières",
        }
        for lang, title_fragment in expected.items():
            with self.subTest(lang=lang):
                response = self.client.get(f"/?lang={lang}")
                body = response.get_data(as_text=True)
                self.assertIn(f'<html lang="{lang}">', body)
                self.assertIn(title_fragment, body)
                canonical = "https://blackseaconnect.com/" if lang == "bg" else f"https://blackseaconnect.com/?lang={lang}"
                self.assertIn(f'<link rel="canonical" href="{canonical}">', body)
                self.assertIn('<link rel="alternate" hreflang="bg" href="https://blackseaconnect.com/">', body)
                self.assertIn('<link rel="alternate" hreflang="x-default" href="https://blackseaconnect.com/">', body)

    def test_homepage_redirects_bare_url_to_stored_non_bulgarian_language(self):
        for lang in ("en", "fr", "ru"):
            with self.subTest(lang=lang):
                client = app.test_client()
                explicit_response = client.get(f"/?lang={lang}")
                self.assertEqual(explicit_response.status_code, 200)

                bare_response = client.get("/", follow_redirects=False)
                self.assertEqual(bare_response.status_code, 302)
                self.assertEqual(bare_response.headers["Location"], f"/?lang={lang}")

                redirected_response = client.get(bare_response.headers["Location"])
                redirected_body = redirected_response.get_data(as_text=True)
                self.assertEqual(redirected_response.status_code, 200)
                self.assertIn(f'<html lang="{lang}">', redirected_body)
                self.assertIn(
                    f'<link rel="canonical" href="https://blackseaconnect.com/?lang={lang}">',
                    redirected_body,
                )
                title = re.search(r"<title>(.*?)</title>", redirected_body).group(1)
                description = re.search(r'<meta name="description" content="(.*?)">', redirected_body).group(1)
                self.assertIn(f'<meta property="og:title" content="{title}">', redirected_body)
                self.assertIn(f'<meta name="twitter:title" content="{title}">', redirected_body)
                self.assertIn(f'<meta property="og:description" content="{description}">', redirected_body)
                self.assertIn(f'<meta name="twitter:description" content="{description}">', redirected_body)
                self.assertIn(
                    f'<meta property="og:url" content="https://blackseaconnect.com/?lang={lang}">',
                    redirected_body,
                )
                for alternate_lang in ("bg", "en", "fr", "ru"):
                    alternate_url = (
                        "https://blackseaconnect.com/"
                        if alternate_lang == "bg"
                        else f"https://blackseaconnect.com/?lang={alternate_lang}"
                    )
                    self.assertIn(
                        f'<link rel="alternate" hreflang="{alternate_lang}" href="{alternate_url}">',
                        redirected_body,
                    )

    def test_homepage_explicit_language_overrides_stored_language(self):
        self.assertEqual(self.client.get("/?lang=en").status_code, 200)

        explicit_fr = self.client.get("/?lang=fr", follow_redirects=False)
        explicit_body = explicit_fr.get_data(as_text=True)
        self.assertEqual(explicit_fr.status_code, 200)
        self.assertIn('<html lang="fr">', explicit_body)
        self.assertIn(
            '<link rel="canonical" href="https://blackseaconnect.com/?lang=fr">',
            explicit_body,
        )

        bare_response = self.client.get("/", follow_redirects=False)
        self.assertEqual(bare_response.status_code, 302)
        self.assertEqual(bare_response.headers["Location"], "/?lang=fr")

    def test_homepage_bare_url_stays_bulgarian_for_bulgarian_session(self):
        explicit_response = self.client.get("/?lang=bg")
        self.assertEqual(explicit_response.status_code, 200)

        bare_response = self.client.get("/", follow_redirects=False)
        body = bare_response.get_data(as_text=True)
        self.assertEqual(bare_response.status_code, 200)
        self.assertIn('<html lang="bg">', body)
        self.assertIn('<link rel="canonical" href="https://blackseaconnect.com/">', body)

    def test_homepage_verification_tags_are_optional(self):
        body = self.client.get("/").get_data(as_text=True)
        self.assertNotIn("google-site-verification", body)
        self.assertNotIn("msvalidate.01", body)

        app_module.GOOGLE_SITE_VERIFICATION = "google-test-token"
        app_module.BING_SITE_VERIFICATION = "bing-test-token"
        configured = self.client.get("/").get_data(as_text=True)
        self.assertIn('<meta name="google-site-verification" content="google-test-token">', configured)
        self.assertIn('<meta name="msvalidate.01" content="bing-test-token">', configured)

    def test_homepage_includes_json_ld(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn('application/ld+json', body)
        self.assertIn('"@type": "Organization"', body)
        self.assertIn('"@type": "WebSite"', body)
        match = re.search(r'<script type="application/ld\+json">\s*(.*?)\s*</script>', body, re.DOTALL)
        self.assertIsNotNone(match)
        payload = json.loads(html.unescape(match.group(1)))
        organization, website = payload["@graph"]
        self.assertEqual(organization["name"], "BlackSea Connect")
        self.assertEqual(organization["alternateName"], "BlackSeaConnect")
        self.assertEqual(organization["url"], "https://blackseaconnect.com/")
        self.assertEqual(website["url"], "https://blackseaconnect.com/")

    def test_private_and_transactional_routes_send_noindex_header(self):
        for path in ("/admin", "/auth/owner-magic/not-a-token", "/owners/login", "/professionals/login", "/guest/a-302", "/request-service"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.headers.get("X-Robots-Tag"), "noindex, nofollow")

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
                    canonical = f"https://blackseaconnect.com{path}" if lang == "en" else f"https://blackseaconnect.com{path}?lang={lang}"
                    self.assertIn(f'<link rel="canonical" href="{canonical}">', body)
                    self.assertIn(f'<link rel="alternate" hreflang="en" href="https://blackseaconnect.com{path}">', body)

    def test_concierge_bulgaria_bg_is_not_english(self):
        response = self.client.get("/concierge-bulgaria?lang=bg")

        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertNotIn("Should remove friction", body)
        self.assertIn('Консиерж услуги в България', body)

    def test_concierge_bulgaria_fr_contains_french_text(self):
        response = self.client.get("/concierge-bulgaria?lang=fr")

        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("Services de conciergerie en Bulgarie", body)

    def test_concierge_bulgaria_ru_contains_russian_text(self):
        response = self.client.get("/concierge-bulgaria?lang=ru")

        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn('Консьерж-услуги в Болгарии', body)

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


