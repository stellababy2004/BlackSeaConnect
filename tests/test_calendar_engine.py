import base64
import os
import shutil
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
import uuid
from unittest.mock import patch

import app as app_module
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


class CalendarEngineTests(unittest.TestCase):
    ADMIN_ENV = {
        "ADMIN_USERNAME": "admin",
        "ADMIN_PASSWORD": "secret",
    }

    SMTP_ENV = {
        "SMTP_HOST": "smtp.example.com",
        "SMTP_PORT": "587",
        "SMTP_FROM": "BlackSea Connect <concierge@blackseaconnect.com>",
        "SMTP_USERNAME": "smtp-user",
        "SMTP_PASSWORD": "smtp-pass",
        "SERVICE_REQUEST_ADMIN_EMAIL": "admin-requests@example.com",
    }

    def setUp(self):
        self._cwd = os.getcwd()
        self._tmpdir = Path(self._cwd) / f".tmp_calendar_engine_tests_{uuid.uuid4().hex}"
        self._tmpdir.mkdir(exist_ok=True)
        os.chdir(self._tmpdir)
        self.owner_db_path = self._tmpdir / "data" / "blacksea_owner.db"
        self.env = {
            **self.ADMIN_ENV,
            **self.SMTP_ENV,
            "OWNER_DB_PATH": str(self.owner_db_path),
        }
        app.config["TESTING"] = True
        app_module._PUBLIC_FORM_RATE_LIMITS.clear()
        self.client = app.test_client()

    def tearDown(self):
        os.chdir(self._cwd)
        shutil.rmtree(self._tmpdir, ignore_errors=True)
        FakeSMTP.sent_messages.clear()

    def _auth_headers(self):
        token = base64.b64encode(f"{self.ADMIN_ENV['ADMIN_USERNAME']}:{self.ADMIN_ENV['ADMIN_PASSWORD']}".encode("utf-8")).decode("ascii")
        return {"Authorization": f"Basic {token}"}

    def _seed_owner(self, *, owner_id, email, full_name, city, property_type="Villa", property_name="Sea View Villa", units=2):
        return app_module._upsert_owner_account({
            "id": owner_id,
            "created_at": "2026-06-01T10:00:00+00:00",
            "full_name": full_name,
            "email": email,
            "phone": "+359888111222",
            "property_type": property_type,
            "city": city,
            "property_name": property_name,
            "number_of_units": units,
            "notes": "Seeded owner profile for calendar tests.",
            "language": "bg",
            "status": "ACTIVE",
        })

    def _seed_property(self, *, property_id, owner_id, name, location, property_type="Villa"):
        return app_module._append_owner_property({
            "id": property_id,
            "owner_id": owner_id,
            "created_at": "2026-06-01T10:15:00+00:00",
            "name": name,
            "property_type": property_type,
            "location": location,
            "bedrooms": 3,
            "bathrooms": 2,
            "guest_capacity": 6,
            "operating_mode": "Short stay",
            "notes": "Calendar seed property.",
            "status": "ACTIVE",
            "guest_guide_ready": 1,
            "access_instructions_ready": 1,
            "emergency_contact_ready": 1,
            "cleaning_partner_ready": 1,
            "admin_notes": "",
        })

    def _login_owner(self, email):
        with patch.dict(os.environ, self.env, clear=True), patch("app.smtplib.SMTP", FakeSMTP), patch("app.smtplib.SMTP_SSL", FakeSMTP):
            self.client.post("/owners/login", data={"email": email})
            token = app_module._load_owner_magic_tokens()[-1]["token"]
            self.client.get(f"/auth/owner-magic/{token}")

    def _create_task(self, payload):
        with patch.dict(os.environ, self.env, clear=True):
            return app_module._upsert_operations_task(payload, append_created_event=True, notify=False)

    def test_owner_created_events_and_task_sync(self):
        with patch.dict(os.environ, self.env, clear=True), patch("app.smtplib.SMTP", FakeSMTP), patch("app.smtplib.SMTP_SSL", FakeSMTP):
            owner = self._seed_owner(owner_id="owner-1", email="owner-one@example.com", full_name="Elena Petrova", city="Varna")
            property_record = self._seed_property(property_id="property-1", owner_id="owner-1", name="Sea View Villa", location="Varna")
            self._login_owner("owner-one@example.com")

            blocked_response = self.client.post(
                "/owners/calendar",
                data={
                    "property_id": "property-1",
                    "event_type": "Blocked Dates",
                    "title": "Family trip",
                    "description": "Owner is staying in the villa.",
                    "start_datetime": "2026-06-24T10:00",
                    "end_datetime": "2026-06-27T10:00",
                    "all_day": "1",
                },
            )

        self.assertEqual(blocked_response.status_code, 302)
        events = app_module._load_calendar_events()
        self.assertGreaterEqual(len(events), 1)
        owner_event = next(event for event in events if event["title"] == "Family trip")
        self.assertEqual(owner_event["event_type"], "Blocked Dates")
        self.assertEqual(owner_event["status"], "BLOCKED")
        self.assertEqual(owner_event["owner_id"], "owner-1")
        self.assertEqual(owner_event["property_id"], "property-1")

        with patch.dict(os.environ, self.env, clear=True), patch("app.Thread", ImmediateThread), patch("app.smtplib.SMTP", FakeSMTP), patch("app.smtplib.SMTP_SSL", FakeSMTP):
            request_response = self.client.post(
                "/owners/request-service",
                data={
                    "category": "Cleaning",
                    "preferred_date": "2026-06-25",
                    "property_id": "property-1",
                    "property": "Sea View Villa",
                    "description": "Need cleaning before the next guest.",
                    "urgency": "Standard",
                    "contact_preference": "Email",
                },
            )

        self.assertEqual(request_response.status_code, 302)
        task = app_module._load_operations_tasks()[0]
        self.assertEqual(task["source_type"], "OWNER_SERVICE_REQUEST")

        with patch.dict(os.environ, self.env, clear=True):
            due_date_update = self.client.post(
                f"/admin/operations/{task['id']}",
                data={
                    "due_date": "2026-06-28",
                },
                headers=self._auth_headers(),
            )

        self.assertEqual(due_date_update.status_code, 302)
        updated_event = next(event for event in app_module._load_calendar_events() if event["operation_task_id"] == task["id"])
        self.assertIn("2026-06-28", updated_event["start_datetime"])
        self.assertEqual(updated_event["event_type"], "Cleaning")
        self.assertEqual(updated_event["color"], "green")

        with patch.dict(os.environ, self.env, clear=True):
            completed_response = self.client.post(
                f"/admin/operations/{task['id']}/status",
                json={"status": "DONE"},
                headers=self._auth_headers(),
            )

        self.assertEqual(completed_response.status_code, 200)
        completed_event = next(event for event in app_module._load_calendar_events() if event["operation_task_id"] == task["id"])
        self.assertEqual(completed_event["status"], "COMPLETED")
        self.assertEqual(completed_event["color"], "dark-green")

    def test_visibility_filters_widgets_and_property_pages(self):
        with patch.dict(os.environ, self.env, clear=True), patch("app.smtplib.SMTP", FakeSMTP), patch("app.smtplib.SMTP_SSL", FakeSMTP):
            self._seed_owner(owner_id="owner-1", email="owner-one@example.com", full_name="Elena Petrova", city="Varna")
            self._seed_property(property_id="property-1", owner_id="owner-1", name="Sea View Villa", location="Varna")
            self._seed_owner(owner_id="owner-2", email="owner-two@example.com", full_name="Marta Ivanova", city="Burgas", property_name="Golden Bay Villa")
            self._seed_property(property_id="property-2", owner_id="owner-2", name="Golden Bay Villa", location="Burgas")
            self._login_owner("owner-one@example.com")
            self.client.post(
                "/owners/calendar",
                data={
                    "property_id": "property-1",
                    "event_type": "Personal Stay",
                    "title": "Owner stay",
                    "description": "Private use only.",
                    "start_datetime": "2026-06-25T10:00",
                    "end_datetime": "2026-06-27T10:00",
                },
            )
            owner_one_calendar = self.client.get("/owners/calendar")
            self.client.get("/owners/logout")
            self._login_owner("owner-two@example.com")
            self.client.post(
                "/owners/calendar",
                data={
                    "property_id": "property-2",
                    "event_type": "Blocked Dates",
                    "title": "Maintenance block",
                    "description": "Guest access is paused.",
                    "start_datetime": "2026-06-28T10:00",
                    "end_datetime": "2026-06-29T10:00",
                },
            )
            owner_two_calendar = self.client.get("/owners/calendar")

            self._create_task({
                "id": "checkin-task",
                "request_id": "checkin-task",
                "source_type": "SERVICE_REQUEST",
                "source_id": "checkin-task",
                "created_at": "2026-06-24T09:00:00+00:00",
                "updated_at": "2026-06-24T09:00:00+00:00",
                "title": "Guest check-in",
                "category": "SERVICE",
                "owner_name": "Elena Petrova",
                "owner_email": "owner-one@example.com",
                "property_id": "property-1",
                "property_name": "Sea View Villa",
                "assigned_to": "Front Desk",
                "priority": "NORMAL",
                "status": "NEW",
                "due_date": "2026-06-24",
                "notes": "Guest check-in",
                "completed_at": "",
                "owner_id": "owner-1",
                "property_location": "Varna",
                "admin_notes": "",
                "request_status": "new",
                "checklist_json": "[]",
                "attachments_json": "[]",
                "comments_json": "[]",
            })
            self._create_task({
                "id": "checkout-task",
                "request_id": "checkout-task",
                "source_type": "SERVICE_REQUEST",
                "source_id": "checkout-task",
                "created_at": "2026-06-24T11:00:00+00:00",
                "updated_at": "2026-06-24T11:00:00+00:00",
                "title": "Guest check-out",
                "category": "SERVICE",
                "owner_name": "Elena Petrova",
                "owner_email": "owner-one@example.com",
                "property_id": "property-1",
                "property_name": "Sea View Villa",
                "assigned_to": "Front Desk",
                "priority": "NORMAL",
                "status": "NEW",
                "due_date": "2026-06-25",
                "notes": "Guest check-out",
                "completed_at": "",
                "owner_id": "owner-1",
                "property_location": "Varna",
                "admin_notes": "",
                "request_status": "new",
                "checklist_json": "[]",
                "attachments_json": "[]",
                "comments_json": "[]",
            })
            self._create_task({
                "id": "cleaning-task",
                "request_id": "cleaning-task",
                "source_type": "SERVICE_REQUEST",
                "source_id": "cleaning-task",
                "created_at": "2026-06-24T13:00:00+00:00",
                "updated_at": "2026-06-24T13:00:00+00:00",
                "title": "Cleaning turnover",
                "category": "SERVICE",
                "owner_name": "Elena Petrova",
                "owner_email": "owner-one@example.com",
                "property_id": "property-1",
                "property_name": "Sea View Villa",
                "assigned_to": "Housekeeping",
                "priority": "NORMAL",
                "status": "NEW",
                "due_date": "2026-06-24",
                "notes": "Cleaning turnover",
                "completed_at": "",
                "owner_id": "owner-1",
                "property_location": "Varna",
                "admin_notes": "",
                "request_status": "new",
                "checklist_json": "[]",
                "attachments_json": "[]",
                "comments_json": "[]",
            })
            self._create_task({
                "id": "overdue-task",
                "request_id": "overdue-task",
                "source_type": "SERVICE_REQUEST",
                "source_id": "overdue-task",
                "created_at": "2026-06-20T09:00:00+00:00",
                "updated_at": "2026-06-20T09:00:00+00:00",
                "title": "Maintenance visit",
                "category": "SERVICE",
                "owner_name": "Elena Petrova",
                "owner_email": "owner-one@example.com",
                "property_id": "property-1",
                "property_name": "Sea View Villa",
                "assigned_to": "Maintenance Team",
                "priority": "HIGH",
                "status": "NEW",
                "due_date": "2026-06-21",
                "notes": "Maintenance visit",
                "completed_at": "",
                "owner_id": "owner-1",
                "property_location": "Varna",
                "admin_notes": "",
                "request_status": "new",
                "checklist_json": "[]",
                "attachments_json": "[]",
                "comments_json": "[]",
            })

        with patch.dict(os.environ, self.env, clear=True):
            self._login_owner("owner-one@example.com")
            owner_dashboard = self.client.get("/owners/dashboard")
            owner_property = self.client.get("/owners/properties/property-1")
            owner_calendar = self.client.get("/owners/calendar")
            admin_calendar = self.client.get("/admin/calendar", headers=self._auth_headers())
            admin_dashboard = self.client.get("/admin", headers=self._auth_headers())
            admin_property = self.client.get("/admin/properties/property-1", headers=self._auth_headers())

        owner_one_html = owner_one_calendar.get_data(as_text=True)
        owner_two_html = owner_two_calendar.get_data(as_text=True)
        owner_html = owner_calendar.get_data(as_text=True)
        admin_html = admin_calendar.get_data(as_text=True)
        owner_dashboard_html = owner_dashboard.get_data(as_text=True)
        admin_dashboard_html = admin_dashboard.get_data(as_text=True)
        owner_property_html = owner_property.get_data(as_text=True)
        admin_property_html = admin_property.get_data(as_text=True)

        self.assertIn("Sea View Villa", owner_one_html)
        self.assertNotIn("Golden Bay Villa", owner_one_html)
        self.assertIn("Golden Bay Villa", owner_two_html)
        self.assertNotIn("Sea View Villa", owner_two_html)
        self.assertIn("Golden Bay Villa", admin_html)
        self.assertIn("Sea View Villa", admin_html)
        self.assertIn("Предстоящи събития", owner_dashboard_html)
        self.assertIn("/owners/calendar?lang=bg", owner_dashboard_html)
        self.assertIn("Виж календара", owner_dashboard_html)
        self.assertIn("Днес", owner_dashboard_html)
        self.assertIn("Събития, планирани за утре", owner_dashboard_html)
        self.assertIn("Тази седмица", owner_dashboard_html)
        self.assertIn("Calendar engine", admin_dashboard_html)
        self.assertIn("/admin/calendar", admin_dashboard_html)
        self.assertIn("View calendar", admin_dashboard_html)
        self.assertIn("Today's Operations", admin_dashboard_html)
        self.assertIn("Upcoming Check-ins", admin_dashboard_html)
        self.assertIn("Upcoming Check-outs", admin_dashboard_html)
        self.assertIn("Today's Cleaning", admin_dashboard_html)
        self.assertIn("Overdue Events", admin_dashboard_html)
        self.assertIn("Mini calendar", owner_property_html)
        self.assertIn("/owners/calendar?property=property-1&amp;lang=bg", owner_property_html)
        self.assertIn("Open full calendar", owner_property_html)
        self.assertIn("Blocked dates", owner_property_html)
        self.assertIn("Mini calendar", admin_property_html)
        self.assertIn("/admin/calendar?property=property-1", admin_property_html)
        self.assertIn("Open admin calendar", admin_property_html)
        self.assertIn("Owner calendar blocks", admin_property_html)

    def test_filters_and_timeline_view(self):
        with patch.dict(os.environ, self.env, clear=True), patch("app.smtplib.SMTP", FakeSMTP), patch("app.smtplib.SMTP_SSL", FakeSMTP):
            self._seed_owner(owner_id="owner-1", email="owner-one@example.com", full_name="Elena Petrova", city="Varna")
            self._seed_property(property_id="property-1", owner_id="owner-1", name="Sea View Villa", location="Varna")
            self._login_owner("owner-one@example.com")
            self.client.post(
                "/owners/calendar",
                data={
                    "property_id": "property-1",
                    "event_type": "Blocked Dates",
                    "title": "Owner block",
                    "description": "Private block for the family.",
                    "start_datetime": "2026-06-25T10:00",
                    "end_datetime": "2026-06-27T10:00",
                },
            )
            self._create_task({
                "id": "filter-cleaning",
                "request_id": "filter-cleaning",
                "source_type": "SERVICE_REQUEST",
                "source_id": "filter-cleaning",
                "created_at": "2026-06-24T08:00:00+00:00",
                "updated_at": "2026-06-24T08:00:00+00:00",
                "title": "Cleaning turnover",
                "category": "SERVICE",
                "owner_name": "Elena Petrova",
                "owner_email": "owner-one@example.com",
                "property_id": "property-1",
                "property_name": "Sea View Villa",
                "assigned_to": "Housekeeping",
                "priority": "NORMAL",
                "status": "NEW",
                "due_date": "2026-06-24",
                "notes": "Cleaning turnover",
                "completed_at": "",
                "owner_id": "owner-1",
                "property_location": "Varna",
                "admin_notes": "",
                "request_status": "new",
                "checklist_json": "[]",
                "attachments_json": "[]",
                "comments_json": "[]",
            })

        with patch.dict(os.environ, self.env, clear=True):
            timeline_response = self.client.get("/admin/calendar?view=timeline", headers=self._auth_headers())
            filtered_response = self.client.get("/admin/calendar?view=month&category=Blocked+Dates&property=Sea+View+Villa", headers=self._auth_headers())

        timeline_html = timeline_response.get_data(as_text=True)
        filtered_html = filtered_response.get_data(as_text=True)

        self.assertIn("Timeline", timeline_html)
        self.assertIn("Owner block", timeline_html)
        self.assertIn("Cleaning turnover", timeline_html)
        self.assertIn("Blocked Dates", filtered_html)
        self.assertIn("Owner block", filtered_html)
        self.assertNotIn("Cleaning turnover", filtered_html)


if __name__ == "__main__":
    unittest.main()
