import base64
import json
import os
import shutil
import unittest
from pathlib import Path
import uuid
import urllib.error
import urllib.parse
from unittest.mock import patch

from app import app


class FakeTelegramResponse:
    def __init__(self, status=200):
        self.status = status
        self.code = status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class ImmediateThread:
    def __init__(self, target=None, args=(), kwargs=None, daemon=None):
        self.target = target
        self.args = args
        self.kwargs = kwargs or {}

    def start(self):
        if self.target:
            self.target(*self.args, **self.kwargs)


class ProfessionalApplicationTests(unittest.TestCase):
    ADMIN_ENV = {
        "ADMIN_USERNAME": "admin",
        "ADMIN_PASSWORD": "secret",
    }

    def setUp(self):
        self._cwd = os.getcwd()
        self._tmpdir = Path(self._cwd) / f".tmp_professional_tests_{uuid.uuid4().hex}"
        self._tmpdir.mkdir(exist_ok=True)
        os.chdir(self._tmpdir)
        self._repo_root = Path(__file__).resolve().parents[1]
        app.config["TESTING"] = True
        self.client = app.test_client()

    def tearDown(self):
        os.chdir(self._cwd)
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def _auth_headers(self):
        token = base64.b64encode(f"{self.ADMIN_ENV['ADMIN_USERNAME']}:{self.ADMIN_ENV['ADMIN_PASSWORD']}".encode("utf-8")).decode("ascii")
        return {"Authorization": f"Basic {token}"}

    def _seed_applications(self, records):
        data_dir = Path("data")
        data_dir.mkdir(exist_ok=True)
        path = data_dir / "professional_applications.jsonl"
        with path.open("w", encoding="utf-8") as f:
            for record in records:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _read_applications(self):
        path = Path("data") / "professional_applications.jsonl"
        if not path.exists():
            return []

        records = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line))
        return records

    def _seed_service_requests(self, records):
        data_dir = Path("data")
        data_dir.mkdir(exist_ok=True)
        path = data_dir / "service_requests.jsonl"
        with path.open("w", encoding="utf-8") as f:
            for record in records:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _read_service_requests(self):
        path = Path("data") / "service_requests.jsonl"
        if not path.exists():
            return []

        records = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line))
        return records

    def _valid_payload(self):
        return {
            "full_name": "Elena Petrova",
            "company_name": "Sea Breeze Services",
            "service_type": "Cleaning",
            "city": "Varna",
            "phone": "+359888123456",
            "email": "elena@example.com",
            "languages": "Bulgarian, English",
            "experience_years": "8",
            "description": "Premium coastal cleaning and turnaround support.",
            "website_or_social": "https://example.com",
            "consent": "1",
        }

    def _service_request_payload(self):
        return {
            "name": "Maria Dimitrova",
            "email": "maria@example.com",
            "phone": "+359888777666",
            "property_city": "Varna",
            "property_type": "Villa",
            "service_category": "Cleaning",
            "preferred_date": "2026-07-15",
            "description": "Turnover cleaning and linen setup before arrival.",
        }

    def _network_seed_records(self):
        return [
            {
                "id": "provider-1",
                "created_at": "2026-01-05T10:00:00Z",
                "status": "approved",
                "full_name": "Elena Petrova",
                "company_name": "Sea Breeze Cleaning",
                "service_type": "Cleaning",
                "city": "Varna",
                "phone": "+359888123456",
                "email": "elena@example.com",
                "languages": "Bulgarian, English",
                "experience_years": 8,
                "description": "Premium coastal cleaning and turnaround support for villas and apartments.",
                "website_or_social": "https://example.com",
                "featured": True,
                "badges": ["Premium", "Verified"],
                "photo_url": "https://example.com/sea-breeze.jpg",
                "logo_url": "",
                "consent": True,
                "internal_notes": "",
                "timeline": [],
            },
            {
                "id": "provider-2",
                "created_at": "2026-01-06T10:00:00Z",
                "status": "approved",
                "full_name": "Nikolay Ivanov",
                "company_name": "Black Sea Transfers",
                "service_type": "Airport transfer",
                "city": "Burgas",
                "phone": "+359888654321",
                "email": "nikolay@example.com",
                "languages": "Bulgarian, English, Russian",
                "experience_years": 6,
                "description": "Reliable airport and marina transfers across the coast.",
                "website_or_social": "",
                "featured": False,
                "badges": ["Fast response"],
                "photo_url": "",
                "logo_url": "https://example.com/transfers-logo.png",
                "consent": True,
                "internal_notes": "",
                "timeline": [],
            },
            {
                "id": "provider-3",
                "created_at": "2026-01-07T10:00:00Z",
                "status": "pending",
                "full_name": "Marina Georgieva",
                "company_name": "Blue Coast Laundry",
                "service_type": "Laundry",
                "city": "Nessebar",
                "phone": "+359888111222",
                "email": "marina@example.com",
                "languages": "Bulgarian, English",
                "experience_years": 4,
                "description": "Laundry support for short-stay properties.",
                "website_or_social": "",
                "featured": False,
                "badges": [],
                "photo_url": "",
                "logo_url": "",
                "consent": True,
                "internal_notes": "",
                "timeline": [],
            },
            {
                "id": "provider-4",
                "created_at": "2026-01-08T10:00:00Z",
                "status": "rejected",
                "full_name": "Peter Dimitrov",
                "company_name": "Coastal Electric",
                "service_type": "Electrical",
                "city": "Varna",
                "phone": "+359888333444",
                "email": "peter@example.com",
                "languages": "Bulgarian",
                "experience_years": 11,
                "description": "Electrical maintenance for coastal properties.",
                "website_or_social": "",
                "featured": False,
                "badges": [],
                "photo_url": "",
                "logo_url": "",
                "consent": True,
                "internal_notes": "",
                "timeline": [],
            },
        ]

    def test_professional_application_saves_successfully(self):
        payload = self._valid_payload()
        telegram_token = "telegram-test-token"
        telegram_chat_id = "123456789"
        captured_requests = []

        def fake_urlopen(req, timeout=10):
            if req.full_url == f"https://api.telegram.org/bot{telegram_token}/sendMessage":
                captured_requests.append(req)
                return FakeTelegramResponse(status=200)
            raise AssertionError(f"Unexpected URL: {req.full_url}")

        env = {
            "TELEGRAM_BOT_TOKEN": telegram_token,
            "TELEGRAM_CHAT_ID": telegram_chat_id,
        }

        with patch.dict(os.environ, env, clear=True), patch("app.Thread", ImmediateThread), patch("app.urllib.request.urlopen", side_effect=fake_urlopen):
            response = self.client.post("/professionals/apply", data=payload)

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("pending review", html.lower())

        records = self._read_applications()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["status"], "pending")
        self.assertEqual(records[0]["full_name"], "Elena Petrova")
        self.assertTrue(records[0]["consent"])
        self.assertEqual(len(records[0]["timeline"]), 1)
        self.assertEqual(records[0]["timeline"][0]["type"], "PROFESSIONAL_APPLICATION_CREATED")
        self.assertEqual(len(captured_requests), 1)
        telegram_payload = urllib.parse.parse_qs(captured_requests[0].data.decode("utf-8"))
        self.assertEqual(telegram_payload["chat_id"], [telegram_chat_id])
        self.assertEqual(telegram_payload["disable_web_page_preview"], ["true"])
        self.assertIn("New Professional Application", telegram_payload["text"][0])
        self.assertIn("full_name: Elena Petrova", telegram_payload["text"][0])
        self.assertIn("status: PENDING", telegram_payload["text"][0])
        self.assertIn("/admin/professionals/", telegram_payload["text"][0])

    def test_required_fields_are_validated(self):
        response = self.client.post("/professionals/apply", data={
            "full_name": "",
            "company_name": "",
            "service_type": "",
            "city": "",
            "phone": "",
            "email": "",
            "languages": "",
            "experience_years": "",
            "description": "",
            "website_or_social": "",
        })

        self.assertEqual(response.status_code, 400)
        html = response.get_data(as_text=True)
        self.assertIn("This field is required.", html)
        self.assertIn("Consent is required.", html)
        self.assertEqual(self._read_applications(), [])

    def test_professionals_page_loads_with_language_buttons(self):
        response = self.client.get("/professionals")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('data-lang-switch="bg"', html)
        self.assertIn('data-lang-switch="en"', html)
        self.assertIn('data-lang-switch="fr"', html)
        self.assertIn('/professionals', html)
        self.assertIn('/professionals/apply', html)
        self.assertIn('Professionals', html)

    def test_professionals_apply_page_loads_with_language_buttons(self):
        response = self.client.get("/professionals/apply")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('data-lang-switch="bg"', html)
        self.assertIn('data-lang-switch="en"', html)
        self.assertIn('data-lang-switch="fr"', html)
        self.assertIn('/professionals', html)
        self.assertIn('/professionals/apply', html)
        self.assertIn('Registration', html)

    def test_admin_professionals_page_loads(self):
        record = {
            "id": "prof-1",
            "created_at": "2026-01-02T10:00:00Z",
            "status": "pending",
            "full_name": "Elena Petrova",
            "company_name": "Sea Breeze Services",
            "service_type": "Cleaning",
            "city": "Varna",
            "phone": "+359888123456",
            "email": "elena@example.com",
            "languages": "Bulgarian, English",
            "experience_years": 8,
            "description": "Premium coastal cleaning and turnaround support.",
            "website_or_social": "https://example.com",
            "consent": True,
            "internal_notes": "",
            "timeline": [],
        }
        self._seed_applications([record])

        with patch.dict(os.environ, self.ADMIN_ENV, clear=True):
            response = self.client.get("/admin/professionals", headers=self._auth_headers())

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Professional applications", html)
        self.assertIn("Elena Petrova", html)
        self.assertIn("Sea Breeze Services", html)
        self.assertIn("PENDING", html)
        self.assertIn('data-lang-switch="bg"', html)
        self.assertIn('data-lang-switch="en"', html)
        self.assertIn('data-lang-switch="fr"', html)

    def test_admin_detail_page_loads(self):
        record = {
            "id": "prof-2",
            "created_at": "2026-01-02T10:00:00Z",
            "status": "pending",
            "full_name": "Nikolay Ivanov",
            "company_name": "Black Sea Transfers",
            "service_type": "Airport transfer",
            "city": "Burgas",
            "phone": "+359888654321",
            "email": "nikolay@example.com",
            "languages": "Bulgarian, English, Russian",
            "experience_years": 6,
            "description": "Reliable airport transfer coverage along the coast.",
            "website_or_social": "",
            "consent": True,
            "internal_notes": "Priority candidate.",
            "timeline": [
                {
                    "type": "PROFESSIONAL_APPLICATION_CREATED",
                    "created_at": "2026-01-02T10:00:00Z",
                    "title": "Professional application created: Nikolay Ivanov",
                    "detail": "Airport transfer · Burgas",
                    "status": "pending",
                }
            ],
        }
        self._seed_applications([record])

        with patch.dict(os.environ, self.ADMIN_ENV, clear=True):
            response = self.client.get("/admin/professionals/prof-2", headers=self._auth_headers())

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Professional application detail", html)
        self.assertIn("Black Sea Transfers", html)
        self.assertIn("Priority candidate.", html)
        self.assertIn("Activity timeline", html)
        self.assertIn('data-lang-switch="bg"', html)
        self.assertIn('data-lang-switch="en"', html)
        self.assertIn('data-lang-switch="fr"', html)

    def test_status_update_works(self):
        record = {
            "id": "prof-3",
            "created_at": "2026-01-02T10:00:00Z",
            "status": "pending",
            "full_name": "Marina Georgieva",
            "company_name": "Blue Coast Laundry",
            "service_type": "Laundry",
            "city": "Nessebar",
            "phone": "+359888111222",
            "email": "marina@example.com",
            "languages": "Bulgarian, English",
            "experience_years": 4,
            "description": "Laundry support for short-stay properties.",
            "website_or_social": "",
            "consent": True,
            "internal_notes": "",
            "timeline": [],
        }
        self._seed_applications([record])

        with patch.dict(os.environ, self.ADMIN_ENV, clear=True):
            response = self.client.post(
                "/admin/professionals/prof-3/update",
                data={
                    "status": "approved",
                    "internal_notes": "Approved after review.",
                    "featured": "1",
                    "badges": "Premium, Verified",
                    "photo_url": "https://example.com/laundry.jpg",
                    "logo_url": "https://example.com/laundry-logo.png",
                },
                headers=self._auth_headers(),
            )

        self.assertEqual(response.status_code, 302)
        updated = self._read_applications()[0]
        self.assertEqual(updated["status"], "approved")
        self.assertEqual(updated["internal_notes"], "Approved after review.")
        self.assertTrue(updated["featured"])
        self.assertEqual(updated["badges"], ["Premium", "Verified"])
        self.assertEqual(updated["photo_url"], "https://example.com/laundry.jpg")
        self.assertEqual(updated["logo_url"], "https://example.com/laundry-logo.png")
        self.assertEqual(len(updated["timeline"]), 1)
        self.assertEqual(updated["timeline"][0]["type"], "PROFESSIONAL_APPLICATION_STATUS_UPDATED")

    def test_telegram_notification_is_attempted_when_env_vars_are_present(self):
        payload = self._valid_payload()
        telegram_token = "telegram-test-token"
        telegram_chat_id = "123456789"
        captured_requests = []

        def fake_urlopen(req, timeout=10):
            if req.full_url == f"https://api.telegram.org/bot{telegram_token}/sendMessage":
                captured_requests.append(req)
                return FakeTelegramResponse(status=200)
            raise AssertionError(f"Unexpected URL: {req.full_url}")

        env = {
            "TELEGRAM_BOT_TOKEN": telegram_token,
            "TELEGRAM_CHAT_ID": telegram_chat_id,
        }

        with patch.dict(os.environ, env, clear=True), patch("app.Thread", ImmediateThread), patch("app.urllib.request.urlopen", side_effect=fake_urlopen):
            response = self.client.post("/professionals/apply", data=payload)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(captured_requests), 1)
        telegram_payload = captured_requests[0].data.decode("utf-8")
        self.assertIn("chat_id=123456789", telegram_payload)
        self.assertIn("disable_web_page_preview=true", telegram_payload)

    def test_public_response_does_not_leak_internal_details(self):
        payload = self._valid_payload()

        def fake_urlopen(req, timeout=10):
            raise urllib.error.HTTPError(
                req.full_url,
                500,
                "Internal Server Error",
                hdrs=None,
                fp=None,
            )

        env = {
            "TELEGRAM_BOT_TOKEN": "telegram-test-token",
            "TELEGRAM_CHAT_ID": "123456789",
        }

        with patch.dict(os.environ, env, clear=True), patch("app.Thread", ImmediateThread), patch("app.urllib.request.urlopen", side_effect=fake_urlopen):
            response = self.client.post("/professionals/apply", data=payload)

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertNotIn("telegram-test-token", html)
        self.assertNotIn("Internal Server Error", html)
        self.assertNotIn("data/", html)

    def test_service_request_saves_successfully(self):
        self._seed_applications(self._network_seed_records())
        payload = self._service_request_payload()
        telegram_token = "telegram-test-token"
        telegram_chat_id = "123456789"
        captured_requests = []

        def fake_urlopen(req, timeout=10):
            if req.full_url == f"https://api.telegram.org/bot{telegram_token}/sendMessage":
                captured_requests.append(req)
                return FakeTelegramResponse(status=200)
            raise AssertionError(f"Unexpected URL: {req.full_url}")

        env = {
            "TELEGRAM_BOT_TOKEN": telegram_token,
            "TELEGRAM_CHAT_ID": telegram_chat_id,
        }

        with patch.dict(os.environ, env, clear=True), patch("app.Thread", ImmediateThread), patch("app.urllib.request.urlopen", side_effect=fake_urlopen):
            response = self.client.post("/request-service", data=payload)

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("service request has been saved", html.lower())
        self.assertIn("Sea Breeze Cleaning", html)
        self.assertNotIn("Black Sea Transfers", html)

        records = self._read_service_requests()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["status"], "new")
        self.assertEqual(records[0]["name"], "Maria Dimitrova")
        self.assertEqual(records[0]["service_category"], "Cleaning")
        self.assertEqual(len(records[0]["timeline"]), 1)
        self.assertEqual(records[0]["timeline"][0]["type"], "SERVICE_REQUEST_CREATED")
        self.assertEqual(len(captured_requests), 1)
        telegram_payload = urllib.parse.parse_qs(captured_requests[0].data.decode("utf-8"))
        self.assertEqual(telegram_payload["chat_id"], [telegram_chat_id])
        self.assertIn("New Service Request", telegram_payload["text"][0])
        self.assertIn("Maria Dimitrova", telegram_payload["text"][0])
        self.assertIn("/admin/service-requests/", telegram_payload["text"][0])

        with patch.dict(os.environ, self.ADMIN_ENV, clear=True):
            admin_response = self.client.get("/admin/service-requests", headers=self._auth_headers())

        self.assertEqual(admin_response.status_code, 200)
        admin_html = admin_response.get_data(as_text=True)
        self.assertIn("Maria Dimitrova", admin_html)
        self.assertIn("Varna", admin_html)
        self.assertIn('data-i18n="backToCockpit"', admin_html)

    def test_service_request_required_fields_are_validated(self):
        response = self.client.post("/request-service", data={})

        self.assertEqual(response.status_code, 400)
        html = response.get_data(as_text=True)
        self.assertIn("This field is required.", html)
        self.assertEqual(self._read_service_requests(), [])

    def test_service_request_page_loads_with_language_buttons(self):
        response = self.client.get("/request-service")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('data-lang-switch="bg"', html)
        self.assertIn('data-lang-switch="en"', html)
        self.assertIn('data-lang-switch="fr"', html)
        self.assertIn('data-lang-switch="ru"', html)
        self.assertIn('data-i18n="navRequestService"', html)
        self.assertIn('data-i18n="heroTitle"', html)
        self.assertIn('/request-service', html)
        self.assertIn('/network', html)

    def test_request_service_template_uses_translation_hooks(self):
        template = self._repo_root / "templates" / "request_service.html"
        content = template.read_text(encoding="utf-8")

        self.assertIn('data-i18n="navRequestService"', content)
        self.assertIn('data-i18n="heroTitle"', content)
        self.assertIn('data-i18n-attr="placeholder:namePlaceholder"', content)
        self.assertIn('data-i18n="serviceCategoryEmpty"', content)
        self.assertIn('data-i18n="submitCta"', content)

    def test_admin_service_request_templates_use_translation_hooks(self):
        list_template = self._repo_root / "templates" / "admin_service_requests.html"
        detail_template = self._repo_root / "templates" / "admin_service_request_detail.html"

        list_content = list_template.read_text(encoding="utf-8")
        detail_content = detail_template.read_text(encoding="utf-8")

        self.assertIn('data-i18n="backToCockpit"', list_content)
        self.assertIn('data-i18n="publicFormCta"', list_content)
        self.assertIn('serviceRequestStatusNew', list_content)
        self.assertIn('data-i18n="backToList"', detail_content)
        self.assertIn('data-i18n-attr="placeholder:internalNotesPlaceholder"', detail_content)
        self.assertIn('serviceRequestEventCreated', detail_content)

    def test_i18n_bootstrap_prefers_query_language_over_storage(self):
        content = self._repo_root / "static" / "js" / "i18n.js"
        text = content.read_text(encoding="utf-8")

        self.assertIn('const urlLanguage = getLanguageFromUrl();', text)
        self.assertIn('initialLanguage = getStoredLanguage();', text)
        self.assertIn('localStorage.getItem(STORAGE_KEY)', text)
        self.assertIn('window.history.replaceState', text)
        self.assertIn('applyLanguage(initialLanguage, { syncUrl: false });', text)

    def test_public_templates_do_not_keep_obvious_english_fallbacks(self):
        expectations = {
            "templates/index.html": ["Live now", "Guest operations"],
            "templates/network.html": ["Featured providers</p>", "Featured providers</h3>", "{{ total_providers }} approved providers"],
            "templates/network_detail.html": ["<span class=\"trust-strip__chip\">Featured</span>", "Available for requests\"", "Requests paused\""],
            "templates/request_service.html": ["View providers", "Status: new"],
            "templates/admin_service_requests.html": ["Back to cockpit", "Open public form", "No service requests yet."],
            "templates/admin_service_request_detail.html": ["Back to requests", "Open public form", "No provider selected", "Private notes for the admin team"],
        }

        for relative_path, forbidden_strings in expectations.items():
            content = (self._repo_root / relative_path).read_text(encoding="utf-8")
            for forbidden in forbidden_strings:
                self.assertNotIn(forbidden, content, msg=f"{relative_path} still contains {forbidden!r}")

    def test_service_request_public_response_does_not_leak_internal_details(self):
        payload = self._service_request_payload()

        def fake_urlopen(req, timeout=10):
            raise urllib.error.HTTPError(
                req.full_url,
                500,
                "Internal Server Error",
                hdrs=None,
                fp=None,
            )

        env = {
            "TELEGRAM_BOT_TOKEN": "telegram-test-token",
            "TELEGRAM_CHAT_ID": "123456789",
        }

        with patch.dict(os.environ, env, clear=True), patch("app.Thread", ImmediateThread), patch("app.urllib.request.urlopen", side_effect=fake_urlopen):
            response = self.client.post("/request-service", data=payload)

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertNotIn("telegram-test-token", html)
        self.assertNotIn("Internal Server Error", html)
        self.assertNotIn("data/", html)

    def test_admin_service_requests_page_loads(self):
        self._seed_service_requests([
            {
                "id": "req-1",
                "created_at": "2026-02-01T10:00:00Z",
                "status": "new",
                "name": "Maria Dimitrova",
                "email": "maria@example.com",
                "phone": "+359888777666",
                "property_city": "Varna",
                "property_type": "Villa",
                "service_category": "Cleaning",
                "preferred_date": "2026-07-15",
                "description": "Turnover cleaning and linen setup before arrival.",
                "assigned_provider_id": "",
                "assigned_provider_name": "",
                "assigned_provider_company": "",
                "internal_notes": "",
                "timeline": [],
            },
            {
                "id": "req-2",
                "created_at": "2026-02-02T10:00:00Z",
                "status": "assigned",
                "name": "Ivan Petrov",
                "email": "ivan@example.com",
                "phone": "+359888111222",
                "property_city": "Burgas",
                "property_type": "Apartment",
                "service_category": "Transfers",
                "preferred_date": "2026-07-20",
                "description": "Airport pickup.",
                "assigned_provider_id": "provider-2",
                "assigned_provider_name": "Nikolay Ivanov",
                "assigned_provider_company": "Black Sea Transfers",
                "internal_notes": "",
                "timeline": [],
            },
            {
                "id": "req-3",
                "created_at": "2026-02-03T10:00:00Z",
                "status": "completed",
                "name": "Elena Georgieva",
                "email": "elena@example.com",
                "phone": "+359888333444",
                "property_city": "Nessebar",
                "property_type": "House",
                "service_category": "Plumbing",
                "preferred_date": "2026-07-22",
                "description": "Urgent plumbing support.",
                "assigned_provider_id": "provider-1",
                "assigned_provider_name": "Elena Petrova",
                "assigned_provider_company": "Sea Breeze Cleaning",
                "internal_notes": "",
                "timeline": [],
            },
        ])

        with patch.dict(os.environ, self.ADMIN_ENV, clear=True):
            response = self.client.get("/admin/service-requests", headers=self._auth_headers())

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Публични заявки за услуги", html)
        self.assertIn("Общо заявки", html)
        self.assertIn("Maria Dimitrova", html)
        self.assertIn("Ivan Petrov", html)
        self.assertIn("Elena Georgieva", html)
        self.assertIn('data-i18n="backToCockpit"', html)
        self.assertIn('data-lang-switch="bg"', html)
        self.assertIn('data-lang-switch="en"', html)
        self.assertIn('data-lang-switch="fr"', html)
        self.assertIn('data-lang-switch="ru"', html)

    def test_admin_service_request_detail_page_loads(self):
        self._seed_service_requests([
            {
                "id": "req-4",
                "created_at": "2026-02-04T10:00:00Z",
                "status": "new",
                "name": "Petya Ivanova",
                "email": "petya@example.com",
                "phone": "+359888555444",
                "property_city": "Varna",
                "property_type": "Villa",
                "service_category": "Cleaning",
                "preferred_date": "2026-07-25",
                "description": "Weekly turnover cleaning.",
                "assigned_provider_id": "",
                "assigned_provider_name": "",
                "assigned_provider_company": "",
                "internal_notes": "Urgent before arrival.",
                "timeline": [
                    {
                        "type": "SERVICE_REQUEST_CREATED",
                        "created_at": "2026-02-04T10:00:00Z",
                        "title": "Service request created: Petya Ivanova",
                        "detail": "Cleaning · Varna",
                        "status": "new",
                    }
                ],
            }
        ])

        with patch.dict(os.environ, self.ADMIN_ENV, clear=True):
            response = self.client.get("/admin/service-requests/req-4", headers=self._auth_headers())

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Подробности за заявката", html)
        self.assertIn("Petya Ivanova", html)
        self.assertIn("Urgent before arrival.", html)
        self.assertIn("Хронология на активността", html)
        self.assertIn('data-i18n="backToList"', html)
        self.assertIn('data-i18n="serviceRequestStatusNew"', html)
        self.assertIn('data-lang-switch="bg"', html)
        self.assertIn('data-lang-switch="en"', html)
        self.assertIn('data-lang-switch="fr"', html)
        self.assertIn('data-lang-switch="ru"', html)

    def test_service_request_status_update_works(self):
        self._seed_applications(self._network_seed_records())
        self._seed_service_requests([
            {
                "id": "req-5",
                "created_at": "2026-02-05T10:00:00Z",
                "status": "new",
                "name": "Maya Nikolova",
                "email": "maya@example.com",
                "phone": "+359888222333",
                "property_city": "Varna",
                "property_type": "Apartment",
                "service_category": "Cleaning",
                "preferred_date": "2026-07-26",
                "description": "Mid-stay cleaning and linen change.",
                "assigned_provider_id": "",
                "assigned_provider_name": "",
                "assigned_provider_company": "",
                "internal_notes": "",
                "timeline": [],
            }
        ])

        with patch.dict(os.environ, self.ADMIN_ENV, clear=True):
            response = self.client.post(
                "/admin/service-requests/req-5/update",
                data={
                    "status": "assigned",
                    "assigned_provider_id": "provider-1",
                    "internal_notes": "Assigned to featured cleaning partner.",
                },
                headers=self._auth_headers(),
            )

        self.assertEqual(response.status_code, 302)
        updated = self._read_service_requests()[0]
        self.assertEqual(updated["status"], "assigned")
        self.assertEqual(updated["assigned_provider_id"], "provider-1")
        self.assertEqual(updated["assigned_provider_company"], "Sea Breeze Cleaning")
        self.assertEqual(updated["internal_notes"], "Assigned to featured cleaning partner.")
        self.assertGreaterEqual(len(updated["timeline"]), 1)
        self.assertEqual(updated["timeline"][0]["type"], "SERVICE_REQUEST_STATUS_UPDATED")

    def test_homepage_counters_loads(self):
        self._seed_applications(self._network_seed_records())
        self._seed_service_requests([
            {
                "id": "req-6",
                "created_at": "2026-02-06T10:00:00Z",
                "status": "new",
                "name": "Viktor Kolev",
                "email": "viktor@example.com",
                "phone": "+359888444555",
                "property_city": "Varna",
                "property_type": "Villa",
                "service_category": "Laundry",
                "preferred_date": "2026-07-28",
                "description": "Laundry support.",
                "assigned_provider_id": "",
                "assigned_provider_name": "",
                "assigned_provider_company": "",
                "internal_notes": "",
                "timeline": [],
            }
        ])

        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Providers", html)
        self.assertIn("Cities", html)
        self.assertIn("Service requests", html)
        self.assertIn(">2<", html)

    def test_network_directory_loads_and_shows_only_approved_providers(self):
        self._seed_applications(self._network_seed_records())

        response = self.client.get("/network")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('data-lang-switch="bg"', html)
        self.assertIn('data-lang-switch="en"', html)
        self.assertIn('data-lang-switch="fr"', html)
        self.assertIn("Избрани доставчици", html)
        self.assertIn("Sea Breeze Cleaning", html)
        self.assertIn("Black Sea Transfers", html)
        self.assertIn("Premium", html)
        self.assertIn("Verified", html)
        self.assertNotIn("Blue Coast Laundry", html)
        self.assertNotIn("Coastal Electric", html)
        self.assertIn("Cleaning", html)
        self.assertIn("Transfers", html)

    def test_network_directory_filters_by_city(self):
        self._seed_applications(self._network_seed_records())

        response = self.client.get("/network?city=Varna")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Sea Breeze Cleaning", html)
        self.assertNotIn("Black Sea Transfers", html)
        self.assertNotIn("Blue Coast Laundry", html)
        self.assertNotIn("Coastal Electric", html)

    def test_network_directory_filters_by_category(self):
        self._seed_applications(self._network_seed_records())

        response = self.client.get("/network?category=Transfers")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Black Sea Transfers", html)
        self.assertNotIn("Sea Breeze Cleaning", html)
        self.assertNotIn("Blue Coast Laundry", html)

    def test_network_detail_page_loads(self):
        self._seed_applications(self._network_seed_records())

        response = self.client.get("/network/provider-2")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Black Sea Transfers", html)
        self.assertIn("Burgas", html)
        self.assertIn("Airport transfer", html)
        self.assertIn("Fast response", html)
        self.assertIn("https://example.com/transfers-logo.png", html)
        self.assertIn('data-lang-switch="bg"', html)
        self.assertIn('data-lang-switch="en"', html)
        self.assertIn('data-lang-switch="fr"', html)


if __name__ == "__main__":
    unittest.main()
