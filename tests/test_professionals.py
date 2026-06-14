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
                data={"status": "approved", "internal_notes": "Approved after review."},
                headers=self._auth_headers(),
            )

        self.assertEqual(response.status_code, 302)
        updated = self._read_applications()[0]
        self.assertEqual(updated["status"], "approved")
        self.assertEqual(updated["internal_notes"], "Approved after review.")
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


if __name__ == "__main__":
    unittest.main()
