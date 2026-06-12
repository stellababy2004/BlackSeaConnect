import base64
import json
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
    ADMIN_ENV = {
        "ADMIN_USERNAME": "admin",
        "ADMIN_PASSWORD": "secret",
    }

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

    def _read_requests(self):
        path = Path("data") / "pilot_requests.jsonl"
        if not path.exists():
            return []

        records = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line))
        return records

    def _seed_requests(self, records):
        data_dir = Path("data")
        data_dir.mkdir(exist_ok=True)
        path = data_dir / "pilot_requests.jsonl"
        with path.open("w", encoding="utf-8") as f:
            for record in records:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _auth_headers(self):
        token = base64.b64encode(f"{self.ADMIN_ENV['ADMIN_USERNAME']}:{self.ADMIN_ENV['ADMIN_PASSWORD']}".encode("utf-8")).decode("ascii")
        return {"Authorization": f"Basic {token}"}

    def test_missing_fields_returns_400(self):
        payload = {
            "email": "owner@example.com",
            "property_type": "villa_residence",
            "apartment_count": "12",
        }

        response = self.client.post("/api/pilot-request", json=payload)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json(), {"ok": False, "error": "missing_fields"})

    def test_admin_route_returns_200_when_jsonl_missing(self):
        with patch.dict(os.environ, self.ADMIN_ENV, clear=True):
            response = self.client.get("/admin/pilot-requests", headers=self._auth_headers())

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("No pilot requests yet.", html)
        self.assertIn("Submitted requests will appear here", html)

    def test_admin_route_returns_503_when_admin_env_missing(self):
        response = self.client.get("/admin/pilot-requests")

        self.assertEqual(response.status_code, 503)

    def test_admin_route_returns_401_without_credentials(self):
        with patch.dict(os.environ, self.ADMIN_ENV, clear=True):
            response = self.client.get("/admin/pilot-requests")

        self.assertEqual(response.status_code, 401)
        self.assertIn("WWW-Authenticate", response.headers)

    def test_admin_route_returns_200_with_valid_credentials(self):
        self._seed_requests([])
        with patch.dict(os.environ, self.ADMIN_ENV, clear=True):
            response = self.client.get("/admin/pilot-requests", headers=self._auth_headers())

        self.assertEqual(response.status_code, 200)

    def test_valid_payload_returns_200_and_saves_id_and_status(self):
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

        records = self._read_requests()
        self.assertEqual(len(records), 1)
        self.assertTrue(records[0]["id"])
        self.assertEqual(records[0]["status"], "new")
        self.assertEqual(records[0]["city"], "Varna Marina")

        self.assertTrue(FakeSMTP.sent_messages)
        message = FakeSMTP.sent_messages[0]
        self.assertEqual(message["Subject"], "New BlackSea Connect pilot request")
        body = message.get_content()
        self.assertIn("Property type: villa_residence", body)
        self.assertIn("City / location: Varna Marina", body)
        self.assertIn("Concierge needs: Arrivals, cleaning, transfers", body)
        self.assertIn("Language: en", body)

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
        self.assertEqual(len(self._read_requests()), 1)

    def test_api_pilot_request_remains_public(self):
        payload = {
            "property_type": "villa_residence",
            "apartment_count": "12",
            "city": "Varna Marina",
            "concierge_needs": "Arrivals, cleaning, transfers",
            "email": "owner@example.com",
        }

        with patch.dict(os.environ, {}, clear=True), patch("app.Thread", ImmediateThread), patch("app.smtplib.SMTP", side_effect=TimeoutError("connect timeout")):
            response = self.client.post("/api/pilot-request", json=payload)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"ok": True})

    def test_list_page_shows_saved_requests_newest_first(self):
        older = {
            "id": "older-id",
            "created_at": "2026-01-01T10:00:00Z",
            "status": "new",
            "name": "Old Request",
            "email": "old@example.com",
            "property_type": "apartment",
            "apartment_count": "3",
            "city": "Old Port",
            "concierge_needs": "Cleaning",
            "current_language": "en",
            "submitted_from": "/pilot-access",
            "location": "Old Port",
            "needs": "Cleaning",
        }
        newer = {
            "id": "newer-id",
            "created_at": "2026-01-02T10:00:00Z",
            "status": "contacted",
            "name": "New Request",
            "email": "new@example.com",
            "property_type": "villa",
            "apartment_count": "7",
            "city": "New Marina",
            "concierge_needs": "Arrivals",
            "current_language": "en",
            "submitted_from": "/demo/operations",
            "location": "New Marina",
            "needs": "Arrivals",
        }

        self._seed_requests([older, newer])

        with patch.dict(os.environ, self.ADMIN_ENV, clear=True):
            response = self.client.get("/admin/pilot-requests", headers=self._auth_headers())

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("/admin/pilot-requests/newer-id", html)
        self.assertIn("/admin/pilot-requests/older-id", html)
        self.assertLess(html.index("New Request"), html.index("Old Request"))
        self.assertIn("contacted", html)

    def test_detail_page_works(self):
        record = {
            "id": "detail-id",
            "created_at": "2026-01-02T10:00:00Z",
            "status": "qualified",
            "name": "Detail Request",
            "email": "detail@example.com",
            "property_type": "villa",
            "apartment_count": "7",
            "city": "Detail Marina",
            "concierge_needs": "Arrivals",
            "current_language": "en",
            "submitted_from": "/demo/operations",
            "location": "Detail Marina",
            "needs": "Arrivals",
        }
        self._seed_requests([record])

        with patch.dict(os.environ, self.ADMIN_ENV, clear=True):
            response = self.client.get("/admin/pilot-requests/detail-id", headers=self._auth_headers())

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Detail Request", html)
        self.assertIn("qualified", html)
        self.assertIn("Detail Marina", html)
        self.assertIn("detail@example.com", html)

    def test_status_update_works(self):
        record = {
            "id": "status-id",
            "created_at": "2026-01-02T10:00:00Z",
            "status": "new",
            "name": "Status Request",
            "email": "status@example.com",
            "property_type": "villa",
            "apartment_count": "7",
            "city": "Status Marina",
            "concierge_needs": "Arrivals",
            "current_language": "en",
            "submitted_from": "/demo/operations",
            "location": "Status Marina",
            "needs": "Arrivals",
        }
        self._seed_requests([record])

        with patch.dict(os.environ, self.ADMIN_ENV, clear=True):
            response = self.client.post("/admin/pilot-requests/status-id/status", data={"status": "contacted"}, headers=self._auth_headers())

        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/pilot-requests/status-id", response.headers["Location"])

        updated = self._read_requests()[0]
        self.assertEqual(updated["status"], "contacted")

    def test_invalid_status_returns_400(self):
        record = {
            "id": "invalid-status-id",
            "created_at": "2026-01-02T10:00:00Z",
            "status": "new",
            "name": "Invalid Status Request",
            "email": "status@example.com",
            "property_type": "villa",
            "apartment_count": "7",
            "city": "Status Marina",
            "concierge_needs": "Arrivals",
            "current_language": "en",
            "submitted_from": "/demo/operations",
            "location": "Status Marina",
            "needs": "Arrivals",
        }
        self._seed_requests([record])

        with patch.dict(os.environ, self.ADMIN_ENV, clear=True):
            response = self.client.post("/admin/pilot-requests/invalid-status-id/status", data={"status": "invalid"}, headers=self._auth_headers())

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json(), {"ok": False, "error": "invalid_status"})

    def test_status_update_route_is_protected(self):
        record = {
            "id": "protected-status-id",
            "created_at": "2026-01-02T10:00:00Z",
            "status": "new",
            "name": "Protected Status Request",
            "email": "status@example.com",
            "property_type": "villa",
            "apartment_count": "7",
            "city": "Status Marina",
            "concierge_needs": "Arrivals",
            "current_language": "en",
            "submitted_from": "/demo/operations",
            "location": "Status Marina",
            "needs": "Arrivals",
        }
        self._seed_requests([record])

        with patch.dict(os.environ, self.ADMIN_ENV, clear=True):
            response = self.client.post("/admin/pilot-requests/protected-status-id/status", data={"status": "contacted"})

        self.assertEqual(response.status_code, 401)
        self.assertIn("WWW-Authenticate", response.headers)

    def test_missing_request_returns_404(self):
        with patch.dict(os.environ, self.ADMIN_ENV, clear=True):
            response = self.client.get("/admin/pilot-requests/missing-id", headers=self._auth_headers())

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
