import os
import shutil
import unittest
from pathlib import Path
import uuid
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


class ImmediateThread:
    def __init__(self, target=None, args=(), kwargs=None, daemon=None):
        self.target = target
        self.args = args
        self.kwargs = kwargs or {}

    def start(self):
        if self.target:
            self.target(*self.args, **self.kwargs)


class PilotRequestApiTests(unittest.TestCase):
    def setUp(self):
        self._cwd = os.getcwd()
        self._tmpdir = Path(self._cwd) / f".tmp_pilot_request_tests_{uuid.uuid4().hex}"
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

        with patch.dict(os.environ, env, clear=True), patch("app.Thread", ImmediateThread), patch("app.smtplib.SMTP", FakeSMTP):
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

    def test_valid_payload_returns_200_when_smtp_times_out(self):
        payload = {
            "property_type": "villa_residence",
            "apartment_count": "12",
            "city": "Varna Marina",
            "concierge_needs": "Arrivals, cleaning, transfers",
            "email": "owner@example.com",
        }

        env = {
            "SMTP_HOST": "smtp.zoho.eu",
            "SMTP_PORT": "587",
            "SMTP_USERNAME": "user",
            "SMTP_PASSWORD": "secret",
            "SMTP_FROM": "noreply@example.com",
        }

        with patch.dict(os.environ, env, clear=True), patch("app.Thread", ImmediateThread), patch("app.smtplib.SMTP", side_effect=TimeoutError("connect timeout")):
            response = self.client.post("/api/pilot-request", json=payload)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"ok": True})

        record_path = Path("data") / "pilot_requests.jsonl"
        self.assertTrue(record_path.exists())

        with record_path.open("r", encoding="utf-8") as f:
            saved_lines = [line.strip() for line in f if line.strip()]

        self.assertEqual(len(saved_lines), 1)
        saved_record = saved_lines[0]
        self.assertIn('"city": "Varna Marina"', saved_record)


if __name__ == "__main__":
    unittest.main()
