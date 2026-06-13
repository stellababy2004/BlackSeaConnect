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
        self.assertIn("As soon as a pilot form is saved", html)

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

    def test_admin_dashboard_calculates_kpis(self):
        pilot_records = [
            {
                "id": "p1",
                "created_at": "2026-01-03T10:00:00Z",
                "status": "new",
                "name": "Lead One",
                "email": "one@example.com",
                "property_type": "villa",
                "apartment_count": "4",
                "city": "Varna",
                "concierge_needs": "Arrivals",
                "current_language": "en",
                "submitted_from": "/demo/operations",
                "location": "Varna",
                "needs": "Arrivals",
            },
            {
                "id": "p2",
                "created_at": "2026-01-04T10:00:00Z",
                "status": "qualified",
                "name": "Lead Two",
                "email": "two@example.com",
                "property_type": "hotel",
                "apartment_count": "8",
                "city": "Burgas",
                "concierge_needs": "Cleaning",
                "current_language": "en",
                "submitted_from": "/demo/operations",
                "location": "Burgas",
                "needs": "Cleaning",
            },
            {
                "id": "p3",
                "created_at": "2026-01-05T10:00:00Z",
                "status": "converted",
                "name": "Lead Three",
                "email": "three@example.com",
                "property_type": "apartment",
                "apartment_count": "12",
                "city": "Sofia",
                "concierge_needs": "Transfers",
                "current_language": "bg",
                "submitted_from": "/demo/operations",
                "location": "Sofia",
                "needs": "Transfers",
            },
            {
                "id": "p4",
                "created_at": "2026-01-06T10:00:00Z",
                "status": "lost",
                "name": "Lead Four",
                "email": "four@example.com",
                "property_type": "apartment",
                "apartment_count": "2",
                "city": "Nessebar",
                "concierge_needs": "Owner support",
                "current_language": "en",
                "submitted_from": "/demo/operations",
                "location": "Nessebar",
                "needs": "Owner support",
            },
        ]
        concierge_records = [
            {
                "created_at": "2026-01-06T09:00:00Z",
                "name": "Guest One",
                "email": "guest@example.com",
                "service_type": "cleaning",
                "message": "Need cleaning",
            }
        ]
        self._seed_requests(pilot_records)
        concierge_dir = Path("data")
        concierge_dir.mkdir(exist_ok=True)
        with (concierge_dir / "concierge_requests.jsonl").open("w", encoding="utf-8") as f:
            for record in concierge_records:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

        with patch.dict(os.environ, self.ADMIN_ENV, clear=True):
            response = self.client.get("/admin", headers=self._auth_headers())

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Total Leads", html)
        self.assertIn("4", html)
        self.assertIn("New", html)
        self.assertIn("Contacted", html)
        self.assertIn("Qualified", html)
        self.assertIn("Converted", html)
        self.assertIn("Lost", html)
        self.assertIn("Concierge Requests", html)

    def test_export_route_is_protected(self):
        with patch.dict(os.environ, self.ADMIN_ENV, clear=True):
            response = self.client.get("/admin/pilot-requests/export")

        self.assertEqual(response.status_code, 401)
        self.assertIn("WWW-Authenticate", response.headers)

    def test_csv_export_downloads_requested_columns(self):
        record = {
            "id": "csv-id",
            "created_at": "2026-01-02T10:00:00Z",
            "status": "contacted",
            "owner": "Marina Team",
            "notes": "Private note",
            "name": "CSV Request",
            "email": "csv@example.com",
            "property_type": "villa",
            "apartment_count": "7",
            "city": "CSV Marina",
            "concierge_needs": "Arrivals",
            "current_language": "en",
            "submitted_from": "/demo/operations",
            "location": "CSV Marina",
            "needs": "Arrivals",
        }
        self._seed_requests([record])

        with patch.dict(os.environ, self.ADMIN_ENV, clear=True):
            response = self.client.get("/admin/pilot-requests/export", headers=self._auth_headers())

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response.headers.get("Content-Type", ""))
        csv_body = response.get_data(as_text=True)
        self.assertIn("id;created_at;status;owner;email;property_type;apartment_count;city;concierge_needs", csv_body)
        self.assertIn("csv-id", csv_body)
        self.assertIn("CSV Marina", csv_body)

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
            "ADMIN_EMAIL": "stoyanova@orange.fr",
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
        self.assertEqual(records[0]["notes"], "")
        self.assertEqual(records[0]["owner"], "")
        self.assertEqual(len(records[0]["timeline"]), 1)
        self.assertEqual(records[0]["timeline"][0]["type"], "lead_created")
        self.assertEqual(records[0]["city"], "Varna Marina")

        self.assertTrue(FakeSMTP.sent_messages)
        message = FakeSMTP.sent_messages[0]
        self.assertEqual(message["Subject"], "New BlackSea Connect pilot request")
        body = message.get_content()
        self.assertIn("Property type: villa_residence", body)
        self.assertIn("City / location: Varna Marina", body)
        self.assertIn("Concierge needs: Arrivals, cleaning, transfers", body)
        self.assertIn("Language: en", body)

        internal_message = FakeSMTP.sent_messages[1]
        self.assertEqual(internal_message["Subject"], "[BlackSea Connect] New Pilot Lead Received")
        self.assertEqual(internal_message["From"], "noreply@example.com")
        self.assertEqual(internal_message["To"], "stoyanova@orange.fr")
        self.assertEqual(internal_message["Reply-To"], "noreply@example.com")
        self.assertNotIn("contact@blackseaconnect.com", str(internal_message))

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
            "owner": "Concierge Desk",
            "notes": "Call after 17:00.",
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
        self.assertIn("QUALIFIED", html)
        self.assertIn("Detail Marina", html)
        self.assertIn("detail@example.com", html)
        self.assertIn("Concierge Desk", html)
        self.assertIn("Internal notes", html)
        self.assertIn("Activity timeline", html)
        self.assertIn("Lead created", html)

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
        self.assertEqual(len(updated.get("timeline", [])), 1)
        self.assertEqual(updated["timeline"][0]["type"], "status_changed")

    def test_update_route_saves_notes_owner_and_status(self):
        record = {
            "id": "update-id",
            "created_at": "2026-01-02T10:00:00Z",
            "status": "new",
            "name": "Update Request",
            "email": "update@example.com",
            "property_type": "villa",
            "apartment_count": "7",
            "city": "Update Marina",
            "concierge_needs": "Arrivals",
            "current_language": "en",
            "submitted_from": "/demo/operations",
            "location": "Update Marina",
            "needs": "Arrivals",
        }
        self._seed_requests([record])

        with patch.dict(os.environ, self.ADMIN_ENV, clear=True):
            response = self.client.post(
                "/admin/pilot-requests/update-id/update",
                data={
                    "status": "qualified",
                    "owner": "Marina Desk",
                    "notes": "Follow up with the owner next week.",
                },
                headers=self._auth_headers(),
            )

        self.assertEqual(response.status_code, 302)
        updated = self._read_requests()[0]
        self.assertEqual(updated["status"], "qualified")
        self.assertEqual(updated["owner"], "Marina Desk")
        self.assertEqual(updated["notes"], "Follow up with the owner next week.")
        self.assertEqual([event["type"] for event in updated.get("timeline", [])], [
            "status_changed",
            "owner_assigned",
            "note_added",
        ])

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

    def test_legacy_record_defaults_to_new_and_empty_fields(self):
        record = {
            "id": "legacy-id",
            "created_at": "2026-01-02T10:00:00Z",
            "name": "Legacy Request",
            "email": "legacy@example.com",
            "property_type": "villa",
            "apartment_count": "7",
            "city": "Legacy Marina",
            "concierge_needs": "Arrivals",
            "current_language": "en",
            "submitted_from": "/demo/operations",
            "location": "Legacy Marina",
            "needs": "Arrivals",
        }
        self._seed_requests([record])

        with patch.dict(os.environ, self.ADMIN_ENV, clear=True):
            response = self.client.get("/admin/pilot-requests/legacy-id", headers=self._auth_headers())

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("NEW", html)
        self.assertIn("Unassigned", html)


if __name__ == "__main__":
    unittest.main()
