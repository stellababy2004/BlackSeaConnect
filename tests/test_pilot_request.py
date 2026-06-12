import os
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

from app import app


class FakeSMTP:
    sent_messages = []

    def __init__(self, host, port, timeout=None):
        self.host = host
        self.port = port
        self.timeout = timeout

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def ehlo(self):
        return None

    def starttls(self):
        return None

    def login(self, username, password):
        self.username = username
        self.password = password

    def send_message(self, message):
        FakeSMTP.sent_messages.append(message)


class PilotRequestApiTests(unittest.TestCase):
    def setUp(self):
        self._cwd = os.getcwd()
        self._tmpdir = Path(self._cwd) / ".tmp_pilot_request_tests"
        self._tmpdir.mkdir(exist_ok=True)
        os.chdir(self._tmpdir)
        app.config["TESTING"] = True
        self.client = app.test_client()

    def tearDown(self):
        os.chdir(self._cwd)
        shutil.rmtree(self._tmpdir, ignore_errors=True)
        FakeSMTP.sent_messages.clear()

    def test_missing_fields_returns_400(self):
        payload = {
            "email": "owner@example.com",
            "property_type": "villa_residence",
            "apartment_count": "12",
        }

        response = self.client.post("/api/pilot-request", json=payload)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json(), {"ok": False, "error": "missing_fields"})

    def test_valid_payload_returns_200(self):
        payload = {
            "property_type": "villa_residence",
            "apartment_count": "12",
            "city": "Varna Marina",
            "concierge_needs": "Arrivals, cleaning, transfers",
            "email": "owner@example.com",
            "current_language": "en",
        }

        env = {
            "SMTP_HOST": "smtp.example.com",
            "SMTP_PORT": "587",
            "SMTP_USERNAME": "user",
            "SMTP_PASSWORD": "secret",
            "SMTP_FROM": "noreply@example.com",
            "PILOT_REQUEST_TO": "concierge@blackseaconnect.com",
        }

        with patch.dict(os.environ, env, clear=True), patch("app.smtplib.SMTP", FakeSMTP):
            response = self.client.post("/api/pilot-request", json=payload)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"ok": True})

        self.assertTrue(FakeSMTP.sent_messages)
        message = FakeSMTP.sent_messages[0]
        self.assertEqual(message["Subject"], "New BlackSea Connect pilot request")
        body = message.get_content()
        self.assertIn("Property type: villa_residence", body)
        self.assertIn("City / location: Varna Marina", body)
        self.assertIn("Concierge needs: Arrivals, cleaning, transfers", body)
        self.assertIn("Language: en", body)

        record_path = Path("data") / "pilot_requests.jsonl"
        self.assertTrue(record_path.exists())

    def test_missing_smtp_config_returns_controlled_failure(self):
        payload = {
            "property_type": "villa_residence",
            "apartment_count": "12",
            "city": "Varna Marina",
            "concierge_needs": "Arrivals, cleaning, transfers",
            "email": "owner@example.com",
        }

        with patch.dict(os.environ, {}, clear=True):
            response = self.client.post("/api/pilot-request", json=payload)

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json(), {"ok": False, "error": "smtp_not_configured"})


if __name__ == "__main__":
    unittest.main()
