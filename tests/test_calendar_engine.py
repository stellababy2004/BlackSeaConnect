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

    def _admin_csrf(self):
        response = self.client.get("/admin/calendar", headers=self._auth_headers())
        self.assertEqual(response.status_code, 200)
        with self.client.session_transaction() as session_state:
            return session_state["_admin_csrf_token"]

    def _seed_calendar_event(self, *, event_id, property_id="", owner_id="owner-1", event_type="Cleaning", title="Cleaning", start="2026-07-12T10:00:00+00:00", end="2026-07-12T12:00:00+00:00", status="SCHEDULED", professional="", priority="HIGH", property_name="Sea View Villa", city="Varna"):
        metadata = {"source": "operations_task", "source_type": "OWNER_SERVICE_REQUEST", "property_name": property_name, "property_location": city, "owner_name": "Elena Petrova", "priority": priority}
        record = {
            "id": event_id, "created_at": "2026-07-01T10:00:00+00:00", "updated_at": "2026-07-01T10:00:00+00:00",
            "property_id": property_id, "owner_id": owner_id, "operation_task_id": "", "event_type": event_type,
            "title": title, "description": title, "start_datetime": start, "end_datetime": end, "all_day": False,
            "status": status, "assigned_professional": professional, "created_by": "test", "color": "green",
            "metadata": metadata, "metadata_json": app_module.json.dumps(metadata, ensure_ascii=False, separators=(",", ":")), "organization_id": app_module.GLOBAL_ORGANIZATION_ID,
        }
        app_module._admin_calendar_persist_record(record)
        return record

    def _seed_professional(self, professional_id, name, category="Cleaning"):
        return app_module._upsert_professional_account({
            "id": professional_id, "created_at": "2026-07-01T09:00:00+00:00", "email": f"{professional_id}@example.com",
            "full_name": name, "phone": "+359888000111", "company": "", "service_categories": category,
            "status": "ACTIVE", "last_login_at": "", "organization_id": app_module.GLOBAL_ORGANIZATION_ID,
        })

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

    def test_admin_calendar_event_crud_api(self):
        with patch.dict(os.environ, self.env, clear=True):
            self._seed_owner(owner_id="owner-api", email="api-owner@example.com", full_name="API Owner", city="Varna")
            self._seed_property(property_id="property-api", owner_id="owner-api", name="API Villa", location="Varna")
            calendar_response = self.client.get("/admin/calendar", headers=self._auth_headers())
            self.assertEqual(calendar_response.status_code, 200)
            with self.client.session_transaction() as session_state:
                csrf_token = session_state["_admin_csrf_token"]

            create_response = self.client.post(
                "/admin/api/calendar/events",
                headers={**self._auth_headers(), "X-CSRF-Token": csrf_token},
                json={
                    "csrf_token": csrf_token,
                    "event_type": "Cleaning",
                    "property_id": "property-api",
                    "owner": "API Owner",
                    "professional": "Elena Cleaner",
                    "priority": "HIGH",
                    "status": "SCHEDULED",
                    "notes": "Created from admin calendar.",
                    "start_datetime": "2026-07-12T10:00:00+00:00",
                    "end_datetime": "2026-07-12T12:00:00+00:00",
                },
            )
            self.assertEqual(create_response.status_code, 201)
            created = create_response.get_json()["event"]
            event_id = created["id"]
            self.assertTrue(event_id)
            self.assertEqual(created["property_id"], "property-api")

            update_response = self.client.patch(
                f"/admin/api/calendar/events/{event_id}",
                headers={**self._auth_headers(), "X-CSRF-Token": csrf_token},
                json={
                    "csrf_token": csrf_token,
                    "event_type": "Inspection",
                    "property_id": "property-api",
                    "owner": "API Owner",
                    "professional": "Elena Cleaner",
                    "priority": "URGENT",
                    "status": "IN_PROGRESS",
                    "notes": "Updated in place.",
                    "start_datetime": "2026-07-12T11:00:00+00:00",
                    "end_datetime": "2026-07-12T12:30:00+00:00",
                },
            )
            self.assertEqual(update_response.status_code, 200)
            self.assertEqual(update_response.get_json()["event"]["event_type"], "Inspection")
            self.assertTrue(any(event["id"] == event_id for event in app_module._load_calendar_events(owner_id="owner-api")))
            for view in ("month", "week", "day", "timeline"):
                refreshed = self.client.get(f"/admin/calendar?view={view}", headers=self._auth_headers())
                self.assertEqual(refreshed.status_code, 200)
                self.assertIn(event_id, refreshed.get_data(as_text=True))
                self.assertIn("API Villa", refreshed.get_data(as_text=True))
            self._login_owner("api-owner@example.com")
            owner_calendar = self.client.get("/owners/calendar?view=month")
            self.assertEqual(owner_calendar.status_code, 200)
            self.assertIn("API Villa", owner_calendar.get_data(as_text=True))

            delete_response = self.client.delete(
                f"/admin/api/calendar/events/{event_id}",
                headers={**self._auth_headers(), "X-CSRF-Token": csrf_token},
                json={"csrf_token": csrf_token},
            )
            self.assertEqual(delete_response.status_code, 200)
            self.assertEqual(delete_response.get_json()["event_id"], event_id)
            self.assertFalse(any(event["id"] == event_id for event in app_module._load_calendar_events()))

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

    def test_property_reconciliation_suggestions_and_persistence(self):
        with patch.dict(os.environ, self.env, clear=True):
            self._seed_owner(owner_id="owner-1", email="owner@example.com", full_name="Elena Petrova", city="Varna")
            self._seed_property(property_id="property-1", owner_id="owner-1", name="Sea View Villa", location="Varna")
            self._seed_calendar_event(event_id="already-linked", property_id="property-1")
            self._seed_calendar_event(event_id="legacy-exact")
            self._seed_calendar_event(event_id="legacy-none", property_name="Missing Villa")
            csrf = self._admin_csrf()

            linked = self.client.get("/admin/api/calendar/events/already-linked/property-matches", headers=self._auth_headers())
            exact = self.client.get("/admin/api/calendar/events/legacy-exact/property-matches", headers=self._auth_headers())
            none = self.client.get("/admin/api/calendar/events/legacy-none/property-matches", headers=self._auth_headers())
            self.assertEqual(linked.status_code, 200)
            self.assertEqual(linked.get_json()["safe_match_id"], "property-1")
            self.assertEqual(exact.status_code, 200)
            self.assertEqual(exact.get_json()["state"], "exact")
            self.assertEqual(exact.get_json()["safe_match_id"], "property-1")
            self.assertEqual(none.get_json()["state"], "none")
            self.assertEqual(none.get_json()["matches"], [])

            self._seed_property(property_id="property-duplicate", owner_id="owner-1", name="Sea View Villa", location="Varna")
            ambiguous = self.client.get("/admin/api/calendar/events/legacy-exact/property-matches", headers=self._auth_headers())
            self.assertEqual(ambiguous.get_json()["state"], "ambiguous")
            self.assertEqual(len(ambiguous.get_json()["matches"]), 2)

            reconcile = self.client.post(
                "/admin/api/calendar/events/legacy-exact/reconcile-property",
                headers={**self._auth_headers(), "X-CSRF-Token": csrf},
                json={"csrf_token": csrf, "property_id": "property-1"},
            )
            self.assertEqual(reconcile.status_code, 200)
            self.assertEqual(reconcile.get_json()["event"]["property_id"], "property-1")
            persisted = next(item for item in app_module._load_calendar_events() if item["id"] == "legacy-exact")
            self.assertEqual(persisted["property_id"], "property-1")
            html = self.client.get("/admin/calendar?lang=bg", headers=self._auth_headers()).get_data(as_text=True)
            self.assertIn('data-property-id="property-1"', html)

    def test_property_reconciliation_modal_has_localized_empty_state_actions(self):
        with patch.dict(os.environ, self.env, clear=True):
            html_by_language = {
                language: self.client.get(f"/admin/calendar?lang={language}", headers=self._auth_headers()).get_data(as_text=True)
                for language in ("bg", "en", "fr")
            }

        for html in html_by_language.values():
            self.assertIn('<html lang="', html)
            self.assertIn('data-reconcile-selection', html)
            self.assertIn('data-reconcile-empty hidden', html)
            self.assertIn('data-reconcile-create hidden', html)
            self.assertIn('data-reconcile-properties hidden', html)
            self.assertIn('data-reconcile-submit disabled', html)
            self.assertIn('href="/owners/property/new"', html)
            self.assertIn('href="/admin/properties"', html)

        template_source = (Path(self._cwd) / "templates" / "calendar.html").read_text(encoding="utf-8")
        self.assertIn('submitButton.disabled = empty || !select.value;', template_source)
        self.assertIn('selection.hidden = empty;', template_source)
        self.assertIn('dialog[data-reconcile-dialog] .admin-ops-actions-grid.is-empty { grid-template-columns:1fr; }', template_source)

        translations = (Path(self._cwd) / "static" / "js" / "i18n" / "admin-runtime.js").read_text(encoding="utf-8")
        for text in (
            "Календарният запис няма свързан каноничен имот.",
            "This calendar record has no linked canonical property.",
            "Cet enregistrement du calendrier n’est associé à aucun bien de référence.",
            "Създай нов имот",
            "Create a new property",
            "Créer un nouveau bien",
        ):
            self.assertIn(text, translations)

    def test_persistent_assignment_conflict_and_override(self):
        with patch.dict(os.environ, self.env, clear=True):
            self._seed_owner(owner_id="owner-1", email="owner@example.com", full_name="Elena Petrova", city="Varna")
            self._seed_property(property_id="property-1", owner_id="owner-1", name="Sea View Villa", location="Varna")
            self._seed_professional("pro-1", "Stella Test Pro")
            self._seed_professional("pro-2", "Free Cleaner")
            self._create_task({
                "id": "assign-target",
                "request_id": "assign-target",
                "source_type": "OWNER_SERVICE_REQUEST",
                "source_id": "assign-target",
                "created_at": "2026-07-01T10:00:00+00:00",
                "updated_at": "2026-07-01T10:00:00+00:00",
                "title": "Target cleaning",
                "category": "Cleaning",
                "owner_id": "owner-1",
                "owner_name": "Elena Petrova",
                "owner_email": "owner@example.com",
                "property_id": "property-1",
                "property_name": "Sea View Villa",
                "property_location": "Varna",
                "assigned_to": "",
                "assigned_professional_id": "",
                "priority": "HIGH",
                "status": "NEW",
                "due_date": "2026-07-12T10:00:00+00:00",
                "notes": "Assignment target.",
                "organization_id": app_module.GLOBAL_ORGANIZATION_ID,
            })
            self._create_task({
                "id": "conflicting",
                "request_id": "conflicting",
                "source_type": "OWNER_SERVICE_REQUEST",
                "source_id": "conflicting",
                "created_at": "2026-07-01T10:00:00+00:00",
                "updated_at": "2026-07-01T10:00:00+00:00",
                "title": "Conflicting cleaning",
                "category": "Cleaning",
                "owner_id": "owner-1",
                "owner_name": "Elena Petrova",
                "owner_email": "owner@example.com",
                "property_id": "property-1",
                "property_name": "Sea View Villa",
                "property_location": "Varna",
                "assigned_to": "Stella Test Pro",
                "assigned_professional_id": "pro-1",
                "priority": "HIGH",
                "status": "ASSIGNED",
                "due_date": "2026-07-12T10:30:00+00:00",
                "notes": "Existing assignment conflict.",
                "organization_id": app_module.GLOBAL_ORGANIZATION_ID,
            })
            csrf = self._admin_csrf()

            options = self.client.get("/admin/api/calendar/events/assign-target/assignment-options", headers=self._auth_headers())
            self.assertEqual(options.status_code, 200)
            stella = next(item for item in options.get_json()["professionals"] if item["id"] == "pro-1")
            self.assertTrue(stella["conflicts"])

            rejected = self.client.post(
                "/admin/api/calendar/events/assign-target/assign",
                headers={**self._auth_headers(), "X-CSRF-Token": csrf},
                json={"csrf_token": csrf, "professional_id": "pro-1", "override_conflict": False},
            )
            self.assertEqual(rejected.status_code, 409)
            self.assertEqual(rejected.get_json()["code"], "schedule_conflict")

            overridden = self.client.post(
                "/admin/api/calendar/events/assign-target/assign",
                headers={**self._auth_headers(), "X-CSRF-Token": csrf},
                json={"csrf_token": csrf, "professional_id": "pro-1", "override_conflict": True},
            )
            self.assertEqual(overridden.status_code, 200)
            self.assertTrue(overridden.get_json()["conflict_overridden"])
            self.assertEqual(overridden.get_json()["event"]["professional"], "Stella Test Pro")
            self.assertEqual(overridden.get_json()["event"]["id"], "assign-target")
            self.assertEqual(overridden.get_json()["event"]["property_id"], "property-1")
            self.assertEqual(overridden.get_json()["event"]["status"], "ASSIGNED")
            self.assertNotIn("urgent_without_professional", overridden.get_json()["event"]["data_quality"]["issue_codes"])
            persisted = next(item for item in app_module._load_calendar_events() if item["id"] == "assign-target")
            self.assertEqual(persisted["assigned_professional"], "Stella Test Pro")

            persisted_task = app_module._find_operations_task("assign-target")
            self.assertIsNotNone(persisted_task)
            self.assertEqual(persisted_task["assigned_professional_id"], "pro-1")
            self.assertEqual(persisted_task["assigned_to"], "Stella Test Pro")
            self.assertEqual(persisted_task["status"], "ASSIGNED")

            assignment_events = app_module._load_operations_task_events("assign-target")
            self.assertTrue(
                any(
                    event["event_type"] in {"assigned", "professional_assigned"}
                    for event in assignment_events
                )
            )
            detail_html = self.client.get("/admin/operations/assign-target", headers=self._auth_headers()).get_data(as_text=True)
            self.assertIn("Възложен", detail_html)
            self.assertIn("Превъзложи", detail_html)
            self.assertNotIn("Няма точно съвпадение", detail_html)
            class FixedDateTime(datetime):
                @classmethod
                def now(cls, tz=None):
                    fixed = cls(2026, 7, 12, 9, 0, tzinfo=timezone.utc)
                    return fixed.astimezone(tz) if tz else fixed.replace(tzinfo=None)

            with patch("app.datetime", FixedDateTime):
                board_html = self.client.get("/admin/operations", headers=self._auth_headers()).get_data(as_text=True)
            self.assertIn("Team Workload", board_html)
            self.assertIn("Who can take the next task right now?", board_html)
            self.assertIn("Stella Test Pro", board_html)
            self.assertIn("Free Cleaner", board_html)
            self.assertIn("2 / 5 tasks · 40%", board_html)
            self.assertIn("default capacity", board_html)
            self.assertIn("Today's schedule", board_html)
            self.assertIn("10:00", board_html)
            self.assertIn("10:30", board_html)
            self.assertLess(board_html.index("Stella Test Pro"), board_html.index("Free Cleaner"))
            self.assertNotIn("ATTENTION MAP", board_html)
            self.assertNotIn("admin-heatmap", board_html)

    def test_assignment_validation_and_standalone_persistence(self):
        with patch.dict(os.environ, self.env, clear=True):
            self._seed_owner(owner_id="owner-1", email="owner@example.com", full_name="Elena Petrova", city="Varna")
            self._seed_property(property_id="property-1", owner_id="owner-1", name="Sea View Villa", location="Varna")
            self._seed_professional("pro-1", "Stella Test Pro")
            self._seed_calendar_event(event_id="standalone-target", property_id="property-1")
            self._seed_calendar_event(event_id="missing-property")
            csrf = self._admin_csrf()
            headers = {**self._auth_headers(), "X-CSRF-Token": csrf}

            missing_professional = self.client.post(
                "/admin/api/calendar/events/standalone-target/assign",
                headers=headers,
                json={"csrf_token": csrf, "override_conflict": False},
            )
            self.assertEqual(missing_professional.status_code, 400)
            self.assertEqual(missing_professional.get_json()["code"], "professional_required")

            display_name_fallback = self.client.post(
                "/admin/api/calendar/events/standalone-target/assign",
                headers=headers,
                json={"csrf_token": csrf, "professional_id": "Stella Test Pro", "override_conflict": False},
            )
            self.assertEqual(display_name_fallback.status_code, 400)
            self.assertEqual(display_name_fallback.get_json()["code"], "professional_invalid")

            missing_property = self.client.post(
                "/admin/api/calendar/events/missing-property/assign",
                headers=headers,
                json={"csrf_token": csrf, "professional_id": "pro-1", "override_conflict": False},
            )
            self.assertEqual(missing_property.status_code, 409)
            self.assertEqual(missing_property.get_json()["code"], "property_required")

            invalid_event = self.client.post(
                "/admin/api/calendar/events/not-a-real-event/assign",
                headers=headers,
                json={"csrf_token": csrf, "professional_id": "pro-1", "override_conflict": False},
            )
            self.assertEqual(invalid_event.status_code, 404)
            self.assertEqual(invalid_event.get_json()["code"], "event_not_found")

            assigned = self.client.post(
                "/admin/api/calendar/events/standalone-target/assign",
                headers=headers,
                json={"csrf_token": csrf, "professional_id": "pro-1", "override_conflict": False},
            )
            self.assertEqual(assigned.status_code, 200)
            response_event = assigned.get_json()["event"]
            self.assertEqual(response_event["id"], "standalone-target")
            self.assertEqual(response_event["property_id"], "property-1")
            self.assertEqual(response_event["professional"], "Stella Test Pro")
            self.assertEqual(response_event["status"], "ASSIGNED")
            persisted = next(item for item in app_module._load_calendar_events() if item["id"] == "standalone-target")
            self.assertEqual(persisted["assigned_professional"], "Stella Test Pro")
            self.assertEqual(persisted["status"], "ASSIGNED")

    def test_assignment_predicates_support_explicit_and_legacy_records(self):
        self.assertTrue(app_module._record_is_assigned({"status": "assigned", "assigned_provider_id": "pro-1"}))
        self.assertTrue(app_module._record_is_assigned({"status": "new", "assigned_provider_company": "Legacy Provider"}))
        self.assertTrue(app_module._calendar_event_is_assigned({"status": "ASSIGNED", "assigned_professional": ""}))
        self.assertTrue(app_module._calendar_event_is_assigned({"status": "SCHEDULED", "assigned_professional": "Legacy Team"}))
        self.assertFalse(app_module._calendar_event_is_assigned({"status": "SCHEDULED", "assigned_professional": ""}))
        self.assertTrue(app_module._operations_task_is_assigned({"status": "ASSIGNED", "assigned_professional_id": "", "assigned_to": ""}))
        self.assertTrue(app_module._operations_task_is_assigned({"status": "NEW", "assigned_professional_id": "", "assigned_to": "Legacy Team"}))
        self.assertTrue(app_module._operations_task_is_assigned({"status": "NEW", "assigned_professional_id": "legacy-pro", "assigned_to": ""}))
        self.assertFalse(app_module._operations_task_is_assigned({"status": "NEW", "assigned_professional_id": "", "assigned_to": ""}))
        self.assertFalse(app_module._calendar_event_tracks_operations({"event_type": "Blocked Dates"}))
        self.assertFalse(app_module._calendar_event_tracks_operations({"event_type": "Reservation"}))
        self.assertTrue(app_module._calendar_event_tracks_operations({"event_type": "Cleaning"}))
        blocked_quality = app_module._admin_calendar_data_quality({
            "id": "blocked-passive",
            "property_id": "property-1",
            "event_type": "Blocked Dates",
            "start_datetime": "2026-07-01T10:00:00+00:00",
            "end_datetime": "2026-07-08T10:00:00+00:00",
            "status": "BLOCKED",
            "priority": "URGENT",
            "assigned_professional": "",
            "metadata": {},
        })
        self.assertNotIn("urgent_without_professional", blocked_quality["issue_codes"])
        blocked_enriched = app_module._calendar_enrich_event({
            "id": "blocked-passive",
            "event_type": "Blocked Dates",
            "start_datetime": "2026-07-01T10:00:00+00:00",
            "end_datetime": "2026-07-08T10:00:00+00:00",
            "status": "BLOCKED",
            "metadata": {},
        })
        self.assertFalse(blocked_enriched["is_overdue"])

    def test_admin_calendar_dialogs_share_readable_visual_contract(self):
        with patch.dict(os.environ, self.env, clear=True):
            html = self.client.get("/admin/calendar?lang=bg", headers=self._auth_headers()).get_data(as_text=True)
            for dialog_attribute in (
                "data-admin-create-dialog",
                "data-reconcile-dialog",
                "data-assignment-dialog",
                "data-time-dialog",
            ):
                self.assertIn(f'<dialog class="admin-ops-create" {dialog_attribute}>', html)
            self.assertIn(":is(dialog[data-admin-create-dialog],dialog[data-reconcile-dialog],dialog[data-assignment-dialog],dialog[data-time-dialog]) { background:#fff !important; color:#10243a !important; }", html)
            self.assertIn(".admin-inline-error { color:#b42318 !important; }", html)
            self.assertIn('class="admin-assignment-card__content"', html)
            self.assertIn('data-assignment-submit disabled', html)
            self.assertIn("grid-template-columns: 150px minmax(0, 1fr);", html)
            self.assertIn(".admin-ops-toast :is(strong,span,p) { color:#fff !important; -webkit-text-fill-color:#fff !important; }", html)
            self.assertIn('const weekGridColumns = "56px repeat(7, minmax(106px, 1fr))";', html)

    def test_persistent_time_correction_and_data_quality_rules(self):
        with patch.dict(os.environ, self.env, clear=True):
            self._seed_owner(owner_id="owner-1", email="owner@example.com", full_name="Elena Petrova", city="Varna")
            self._seed_property(property_id="property-1", owner_id="owner-1", name="Sea View Villa", location="Varna")
            self._seed_calendar_event(event_id="time-target", property_id="property-1", end="2026-07-12T18:30:00+00:00")
            csrf = self._admin_csrf()

            invalid = self.client.patch(
                "/admin/api/calendar/events/time-target/time",
                headers={**self._auth_headers(), "X-CSRF-Token": csrf},
                json={"csrf_token": csrf, "start_datetime": "2026-07-12T12:00:00+00:00", "end_datetime": "2026-07-12T11:59:00+00:00"},
            )
            self.assertEqual(invalid.status_code, 400)
            self.assertEqual(invalid.get_json()["code"], "invalid_time_range")

            corrected = self.client.patch(
                "/admin/api/calendar/events/time-target/time",
                headers={**self._auth_headers(), "X-CSRF-Token": csrf},
                json={"csrf_token": csrf, "start_datetime": "2026-07-12T12:00:00+00:00", "end_datetime": "2026-07-12T14:00:00+00:00"},
            )
            self.assertEqual(corrected.status_code, 200)
            self.assertEqual(corrected.get_json()["event"]["end_datetime"], "2026-07-12T14:00:00+00:00")

            suspicious = app_module._admin_calendar_data_quality({"id": "q1", "property_id": "property-1", "event_type": "Cleaning", "start_datetime": "2026-07-01T00:00:00+00:00", "end_datetime": "2026-07-01T10:00:00+00:00", "status": "SCHEDULED", "priority": "URGENT", "assigned_professional": "", "metadata": {}})
            self.assertIn("suspicious_duration", suspicious["issue_codes"])
            self.assertIn("urgent_without_professional", suspicious["issue_codes"])
            self.assertIn("stale_overdue_event", suspicious["issue_codes"])
            malformed = app_module._admin_calendar_data_quality({"event_type": "", "start_datetime": "bad", "end_datetime": "", "status": ""})
            self.assertIn("malformed_legacy_data", malformed["issue_codes"])
            self.assertIn("invalid_end_time", malformed["issue_codes"])

    def test_calendar_completion_persists_backing_task(self):
        with patch.dict(os.environ, self.env, clear=True):
            self._seed_owner(
                owner_id="owner-1",
                email="owner@example.com",
                full_name="Elena Petrova",
                city="Varna",
            )
            self._seed_property(
                property_id="property-1",
                owner_id="owner-1",
                name="Sea View Villa",
                location="Varna",
            )
            self._seed_professional("pro-1", "Stella Test Pro")

            self._create_task({
                "id": "completion-target",
                "request_id": "completion-target",
                "source_type": "OWNER_SERVICE_REQUEST",
                "source_id": "completion-target",
                "created_at": "2026-07-01T10:00:00+00:00",
                "updated_at": "2026-07-01T10:00:00+00:00",
                "title": "Completion target",
                "category": "Cleaning",
                "owner_id": "owner-1",
                "owner_name": "Elena Petrova",
                "owner_email": "owner@example.com",
                "property_id": "property-1",
                "property_name": "Sea View Villa",
                "property_location": "Varna",
                "assigned_to": "Stella Test Pro",
                "assigned_professional_id": "pro-1",
                "priority": "HIGH",
                "status": "IN_PROGRESS",
                "due_date": "2026-07-12T10:00:00+00:00",
                "notes": "Ready for completion.",
                "organization_id": app_module.GLOBAL_ORGANIZATION_ID,
            })

            csrf = self._admin_csrf()
            response = self.client.post(
                "/admin/api/calendar/events/completion-target/complete",
                headers={
                    **self._auth_headers(),
                    "X-CSRF-Token": csrf,
                },
                json={"csrf_token": csrf},
            )

            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["event"]["status"], "COMPLETED")

            persisted_task = app_module._find_operations_task("completion-target")
            self.assertIsNotNone(persisted_task)
            self.assertEqual(persisted_task["status"], "COMPLETED")
            self.assertTrue(persisted_task["completed_at"])

            persisted_event = next(
                item
                for item in app_module._load_calendar_events()
                if item["id"] == "completion-target"
            )
            self.assertEqual(persisted_event["status"], "COMPLETED")

            task_events = app_module._load_operations_task_events(
                "completion-target"
            )
            self.assertTrue(
                any(
                    event["event_type"] == "completed"
                    for event in task_events
                )
            )
    def test_owner_visibility_unchanged_after_admin_reconciliation(self):
        with patch.dict(os.environ, self.env, clear=True), patch("app.smtplib.SMTP", FakeSMTP), patch("app.smtplib.SMTP_SSL", FakeSMTP):
            self._seed_owner(owner_id="owner-1", email="one@example.com", full_name="Elena Petrova", city="Varna")
            self._seed_property(property_id="property-1", owner_id="owner-1", name="Sea View Villa", location="Varna")
            self._seed_owner(owner_id="owner-2", email="two@example.com", full_name="Marta Ivanova", city="Burgas", property_name="Other Villa")
            self._seed_property(property_id="property-2", owner_id="owner-2", name="Other Villa", location="Burgas")
            self._seed_calendar_event(event_id="visibility-event", title="Visibility unique event")
            csrf = self._admin_csrf()
            response = self.client.post("/admin/api/calendar/events/visibility-event/reconcile-property", headers={**self._auth_headers(), "X-CSRF-Token": csrf}, json={"csrf_token": csrf, "property_id": "property-1"})
            self.assertEqual(response.status_code, 200)
            self._login_owner("one@example.com")
            owner_one = self.client.get("/owners/calendar").get_data(as_text=True)
            self.client.get("/owners/logout")
            self._login_owner("two@example.com")
            owner_two = self.client.get("/owners/calendar").get_data(as_text=True)
            self.assertIn("Visibility unique event", owner_one)
            self.assertNotIn("Visibility unique event", owner_two)


if __name__ == "__main__":
    unittest.main()
