import json
import re
import unittest
from pathlib import Path

from app import app


class PwaFoundationTests(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()
        self.static_dir = Path(app.static_folder)

    def test_manifest_is_available_with_correct_mime(self):
        response = self.client.get("/static/site.webmanifest")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/manifest+json")

    def test_manifest_is_complete_and_icons_exist(self):
        response = self.client.get("/static/site.webmanifest")
        manifest = json.loads(response.get_data(as_text=True))

        self.assertEqual(manifest["name"], "BlackSeaConnect")
        self.assertEqual(manifest["short_name"], "BlackSea")
        self.assertEqual(manifest["display"], "standalone")
        self.assertEqual(manifest["orientation"], "portrait")
        self.assertEqual(manifest["scope"], "/")
        self.assertTrue(manifest["start_url"].startswith("/professionals/dashboard"))
        purposes = {icon["purpose"] for icon in manifest["icons"]}
        sizes = {icon["sizes"] for icon in manifest["icons"]}
        self.assertIn("any", purposes)
        self.assertIn("maskable", purposes)
        self.assertTrue({"192x192", "512x512"}.issubset(sizes))
        for icon in manifest["icons"]:
            self.assertTrue((Path(app.root_path) / icon["src"].lstrip("/")).is_file())

    def test_service_worker_is_registered_on_public_shell(self):
        response = self.client.get("/?lang=en")
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("/static/js/pwa.js", body)
        self.assertIn("apple-mobile-web-app-capable", body)
        runtime = (self.static_dir / "js" / "pwa.js").read_text(encoding="utf-8")
        self.assertIn('register("/service-worker.js", {scope: "/"})', runtime)

    def test_offline_page_is_available(self):
        response = self.client.get("/offline")

        self.assertEqual(response.status_code, 200)
        self.assertIn("You are offline.", response.get_data(as_text=True))
        self.assertEqual(response.headers["X-Robots-Tag"], "noindex, nofollow")

    def test_service_worker_has_versioned_navigation_fallback(self):
        response = self.client.get("/service-worker.js")
        source = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/javascript")
        self.assertEqual(response.headers["Service-Worker-Allowed"], "/")
        self.assertIn("no-store", response.headers["Cache-Control"])
        self.assertRegex(source, r'CACHE_VERSION = "bsc-pwa-v\d+"')
        self.assertIn('const OFFLINE_URL = "/offline"', source)
        self.assertIn('request.mode === "navigate"', source)
        self.assertIn("caches.match(OFFLINE_URL)", source)

    def test_service_worker_never_caches_private_or_mutating_requests(self):
        source = (self.static_dir / "service-worker.js").read_text(encoding="utf-8")

        self.assertIn('request.method !== "GET"', source)
        self.assertIn('contentType.includes("application/json")', source)
        for excluded in ("/api/", "/auth/", "/admin", "/webhooks", "/workspace", "/owners/finance/", "/professionals/stripe/"):
            self.assertIn(f'"{excluded}"', source)
        for marker in ("login", "logout", "magic", "token", "session", "payment", "upload", "evidence"):
            self.assertRegex(source, rf'\b{re.escape(marker)}\b')


if __name__ == "__main__":
    unittest.main()
