import base64
import os
import shutil
import unittest
from datetime import datetime, timedelta, timezone
from io import BytesIO
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


class ReservationEngineTests(unittest.TestCase):
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
        self._tmpdir = Path(self._cwd) / f".tmp_reservation_engine_tests_{uuid.uuid4().hex}"
        self._tmpdir.mkdir(exist_ok=True)
        os.chdir(self._tmpdir)
        self.owner_db_path = self._tmpdir / "data" / "blacksea_owner.db"
        self.env = {
            **self.ADMIN_ENV,
            **self.SMTP_ENV,
            "OWNER_DB_PATH": str(self.owner_db_path),
        }
        self._env_patcher = patch.dict(os.environ, self.env, clear=True)
        self._env_patcher.start()
        app.config["TESTING"] = True
        app_module._PUBLIC_FORM_RATE_LIMITS.clear()
        self.client = app.test_client()

    def tearDown(self):
        self._env_patcher.stop()
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
            "notes": "Seeded owner profile for reservation tests.",
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
            "operating_mode": "year-round",
            "notes": "Reservation seed property.",
            "status": "ACTIVE",
            "guest_guide_ready": 1,
            "access_instructions_ready": 1,
            "emergency_contact_ready": 1,
            "cleaning_partner_ready": 1,
            "admin_notes": "",
        })

    def _login_owner(self, email):
        with patch.dict(os.environ, self.env, clear=True), patch("app.Thread", ImmediateThread), patch("app.smtplib.SMTP", FakeSMTP), patch("app.smtplib.SMTP_SSL", FakeSMTP):
            self.client.post("/owners/login", data={"email": email})
            token = app_module._load_owner_magic_tokens()[-1]["token"]
            self.client.get(f"/auth/owner-magic/{token}")

    def _reservation_payload(self, *, property_id, guest_first_name, guest_last_name, guest_email, status="CONFIRMED", reservation_kind="reservation", arrival=None, departure=None, notes=""):
        now = datetime.now(timezone.utc)
        arrival = arrival or now
        departure = departure or (now + timedelta(days=1))
        return {
            "reservation_kind": reservation_kind,
            "property_id": property_id,
            "reservation_source": "Manual Reservation",
            "external_reference": "MAN-001",
            "guest_first_name": guest_first_name,
            "guest_last_name": guest_last_name,
            "guest_email": guest_email,
            "guest_phone": "+359888000000",
            "adults": "2",
            "children": "1",
            "infants": "0",
            "pets": "0",
            "arrival_datetime": arrival.strftime("%Y-%m-%dT%H:%M"),
            "departure_datetime": departure.strftime("%Y-%m-%dT%H:%M"),
            "status": status,
            "notes": notes,
        }

    def test_reservation_creation_syncs_calendar_operations_dashboards_and_visibility(self):
        with patch.dict(os.environ, self.env, clear=True), patch("app.Thread", ImmediateThread), patch("app.smtplib.SMTP", FakeSMTP), patch("app.smtplib.SMTP_SSL", FakeSMTP):
            owner_one = self._seed_owner(owner_id="owner-1", email="owner-one@example.com", full_name="Elena Petrova", city="Varna")
            self._seed_property(property_id="property-1", owner_id="owner-1", name="Sea View Villa", location="Varna")
            owner_two = self._seed_owner(owner_id="owner-2", email="owner-two@example.com", full_name="Marta Ivanova", city="Burgas", property_name="Golden Bay Villa")
            self._seed_property(property_id="property-2", owner_id="owner-2", name="Golden Bay Villa", location="Burgas")

            self._login_owner("owner-one@example.com")
            owner_one_response = self.client.post("/owners/reservations", data=self._reservation_payload(
                property_id="property-1",
                guest_first_name="Anna",
                guest_last_name="Ivanova",
                guest_email="anna@example.com",
                status="CONFIRMED",
                notes="Owner one stay.",
            ))
            self.assertEqual(owner_one_response.status_code, 302)
            reservation_one = app_module._load_reservations()[0]
            owner_one_dashboard = self.client.get("/owners/dashboard")
            owner_one_reservations = self.client.get("/owners/reservations")

            self.client.get("/owners/logout")
            self._login_owner("owner-two@example.com")
            owner_two_response = self.client.post("/owners/reservations", data=self._reservation_payload(
                property_id="property-2",
                guest_first_name="Boris",
                guest_last_name="Petrov",
                guest_email="boris@example.com",
                status="PENDING",
                arrival=datetime.now(timezone.utc) + timedelta(days=2),
                departure=datetime.now(timezone.utc) + timedelta(days=4),
                notes="Owner two stay.",
            ))
            self.assertEqual(owner_two_response.status_code, 302)

        reservations = app_module._load_reservations()
        self.assertEqual(len(reservations), 2)
        self.assertEqual(reservations[0]["status"], "CONFIRMED")

        reservation_one = next(item for item in reservations if item["guest_email"] == "anna@example.com")
        linked_operations = [task for task in app_module._load_operations_tasks() if task["source_type"] == "RESERVATION" and task["source_id"] == reservation_one["id"]]
        self.assertEqual(len(linked_operations), 4)

        calendar_events = app_module._load_calendar_events()
        reservation_event = next(event for event in calendar_events if event.get("metadata", {}).get("reservation_id") == reservation_one["id"])
        self.assertEqual(reservation_event["event_type"], "Reservation")
        self.assertEqual(reservation_event["status"], "SCHEDULED")

        with patch.dict(os.environ, self.env, clear=True):
            admin_dashboard = self.client.get("/admin", headers=self._auth_headers())
            admin_reservations = self.client.get("/admin/reservations", headers=self._auth_headers())
            filtered = self.client.get("/admin/reservations?q=anna", headers=self._auth_headers())
            admin_detail = self.client.get(f"/admin/reservations/{reservation_one['id']}", headers=self._auth_headers())

        admin_dashboard_html = admin_dashboard.get_data(as_text=True)
        owner_dashboard_html = owner_one_dashboard.get_data(as_text=True)
        admin_reservations_html = admin_reservations.get_data(as_text=True)
        owner_reservations_html = owner_one_reservations.get_data(as_text=True)
        filtered_html = filtered.get_data(as_text=True)
        admin_detail_html = admin_detail.get_data(as_text=True)

        self.assertIn("Reservation engine", admin_dashboard_html)
        self.assertIn("Booking and availability", admin_dashboard_html)
        self.assertIn("Резервации и заетост", owner_dashboard_html)
        self.assertIn("Предстоящи пристигания", owner_dashboard_html)
        self.assertIn("Today's check-ins", admin_dashboard_html)
        self.assertIn("Anna Ivanova", admin_reservations_html)
        self.assertIn("Boris Petrov", admin_reservations_html)
        self.assertIn("Anna Ivanova", owner_reservations_html)
        self.assertNotIn("Boris Petrov", owner_reservations_html)
        self.assertIn("Anna Ivanova", filtered_html)
        self.assertNotIn("Boris Petrov", filtered_html)
        self.assertIn("Reservation created", admin_detail_html)
        self.assertIn("Reservation activity", admin_detail_html)
        self.assertIn("Occupied", admin_detail_html)

        with patch.dict(os.environ, self.env, clear=True):
            comment_response = self.client.post(
                f"/admin/reservations/{reservation_one['id']}",
                data={
                    "reservation_action": "comment",
                    "comment": "Internal note for operations.",
                },
                headers=self._auth_headers(),
            )

        self.assertEqual(comment_response.status_code, 302)
        self._login_owner("owner-one@example.com")
        owner_detail = self.client.get(f"/owners/reservations/{reservation_one['id']}")
        owner_detail_html = owner_detail.get_data(as_text=True)
        self.assertNotIn("Internal note for operations.", owner_detail_html)
        self.assertIn("Occupancy", admin_dashboard_html)

    def test_blocked_dates_reservation_skips_operations_and_marks_property_blocked(self):
        with patch.dict(os.environ, self.env, clear=True), patch("app.Thread", ImmediateThread), patch("app.smtplib.SMTP", FakeSMTP), patch("app.smtplib.SMTP_SSL", FakeSMTP):
            self._seed_owner(owner_id="owner-1", email="owner-one@example.com", full_name="Elena Petrova", city="Varna")
            self._seed_property(property_id="property-1", owner_id="owner-1", name="Sea View Villa", location="Varna")
            self._login_owner("owner-one@example.com")
            response = self.client.post("/owners/reservations", data=self._reservation_payload(
                property_id="property-1",
                guest_first_name="",
                guest_last_name="",
                guest_email="",
                status="CONFIRMED",
                reservation_kind="blocked_dates",
                notes="Owner blocked the villa.",
            ))

        self.assertEqual(response.status_code, 302)
        reservation = app_module._load_reservations()[0]
        self.assertEqual(reservation["metadata"]["kind"], "blocked_dates")
        self.assertEqual(reservation["status"], "CONFIRMED")

        calendar_event = next(event for event in app_module._load_calendar_events() if event.get("metadata", {}).get("reservation_id") == reservation["id"])
        self.assertEqual(calendar_event["event_type"], "Blocked Dates")
        self.assertEqual(calendar_event["status"], "BLOCKED")

        linked_operations = [task for task in app_module._load_operations_tasks() if task["source_type"] == "RESERVATION" and task["source_id"] == reservation["id"]]
        self.assertEqual(linked_operations, [])

        with patch.dict(os.environ, self.env, clear=True):
            admin_detail = self.client.get(f"/admin/reservations/{reservation['id']}", headers=self._auth_headers())

        admin_detail_html = admin_detail.get_data(as_text=True)
        self.assertIn("Blocked", admin_detail_html)
        self.assertIn("Reservation activity", admin_detail_html)

    def test_reservation_import_csv_preview_and_commit(self):
        csv_text = (
            "Property,Guest,Arrival,Departure,Adults,Children,Email,Phone,Notes,External Reference\n"
            "Sea View Villa,Anna Ivanova,2026-07-01T14:00,2026-07-05T11:00,2,1,anna@example.com,+359888111222,CSV note,CSV-001\n"
        )

        with patch.dict(os.environ, self.env, clear=True), patch("app.Thread", ImmediateThread), patch("app.smtplib.SMTP", FakeSMTP), patch("app.smtplib.SMTP_SSL", FakeSMTP):
            self._seed_owner(owner_id="owner-1", email="owner-one@example.com", full_name="Elena Petrova", city="Varna")
            self._seed_property(property_id="property-1", owner_id="owner-1", name="Sea View Villa", location="Varna")
            preview_response = self.client.post(
                "/admin/reservations/import",
                data={
                    "source": "csv",
                    "import_action": "preview",
                    "csv_text": csv_text,
                },
                headers=self._auth_headers(),
            )
            self.assertEqual(preview_response.status_code, 200)
            preview_html = preview_response.get_data(as_text=True)
            self.assertIn("Anna Ivanova", preview_html)

            preview = app_module._reservation_importer().preview(
                "csv",
                {"csv_text": csv_text},
                context={"created_by": "admin", "manual_property_id": "property-1"},
            )
            self.assertTrue(preview["report"]["ready_to_import"])
            self.assertEqual(preview["report"]["new_reservations"][0]["validation_state"], "new")
            import_result = app_module._reservation_importer().import_preview(preview, created_by="admin")

        self.assertTrue(import_result["ok"])
        reservations = app_module._load_reservations()
        self.assertEqual(len(reservations), 1)
        reservation = reservations[0]
        self.assertEqual(reservation["guest_first_name"], "Anna")
        self.assertEqual(reservation["reservation_source"], "CSV")
        self.assertEqual(reservation["channel_name"], "CSV")
        self.assertEqual(reservation["channel_status"], "SYNCED")
        self.assertEqual(reservation["reservation_reference"], "CSV-001")
        self.assertNotEqual(reservation["last_sync"], "")
        self.assertEqual(reservation["sync_status"], "IMPORTED")
        self.assertNotEqual(reservation["import_batch_id"], "")
        self.assertNotEqual(reservation["external_last_sync"], "")
        self.assertEqual(reservation["source_metadata"]["adapter"], "csv")

        linked_operations = [task for task in app_module._load_operations_tasks() if task["source_type"] == "RESERVATION" and task["source_id"] == reservation["id"]]
        self.assertEqual(len(linked_operations), 4)
        calendar_event = next(event for event in app_module._load_calendar_events() if event.get("metadata", {}).get("reservation_id") == reservation["id"])
        self.assertEqual(calendar_event["event_type"], "Reservation")

    def test_reservation_lifecycle_transitions_sync_operations_timeline_and_availability(self):
        arrival = datetime.now(timezone.utc) - timedelta(days=1)
        departure = datetime.now(timezone.utc) + timedelta(days=4)

        with patch.dict(os.environ, self.env, clear=True), patch("app.Thread", ImmediateThread), patch("app.smtplib.SMTP", FakeSMTP), patch("app.smtplib.SMTP_SSL", FakeSMTP):
            self._seed_owner(owner_id="owner-1", email="owner-one@example.com", full_name="Elena Petrova", city="Varna")
            property_record = self._seed_property(property_id="property-1", owner_id="owner-1", name="Sea View Villa", location="Varna")
            reservation = app_module._create_reservation({
                "property_id": "property-1",
                "reservation_source": "Airbnb",
                "reservation_reference": "AIR-OTA-001",
                "channel_name": "Airbnb",
                "channel_status": "SYNCED",
                "last_sync": datetime.now(timezone.utc).isoformat(),
                "external_payload": {"adapter": "airbnb", "reservation_id": "AIR-OTA-001"},
                "guest_first_name": "Mila",
                "guest_last_name": "Stone",
                "guest_email": "mila@example.com",
                "arrival_datetime": arrival.strftime("%Y-%m-%dT%H:%M"),
                "departure_datetime": departure.strftime("%Y-%m-%dT%H:%M"),
                "status": "CONFIRMED",
                "notes": "OTA lifecycle test.",
            }, created_by="system:test")

            checked_in = app_module._update_reservation_status(reservation["id"], "CHECKED_IN", author="admin:test")
            checked_out = app_module._update_reservation_status(reservation["id"], "CHECKED_OUT", author="admin:test")

            cleaning_task = next(task for task in app_module._load_operations_tasks() if task["source_id"] == reservation["id"] and "Cleaning" in task["category"])
            with app.test_request_context("/admin/operations"):
                completed_task = app_module._update_operations_task_status(cleaning_task["id"], "COMPLETED", source="test")

        self.assertEqual(checked_in["status"], "CHECKED_IN")
        self.assertEqual(checked_out["status"], "CHECKED_OUT")
        self.assertEqual(completed_task["status"], "COMPLETED")

        refreshed = app_module._find_reservation(reservation["id"])
        timeline_titles = [event["title"] for event in app_module._reservation_timeline_events(refreshed)]
        self.assertIn("Imported from Airbnb", timeline_titles)
        self.assertIn("Guest checked in", timeline_titles)
        self.assertIn("Guest checked out", timeline_titles)
        self.assertIn("Cleaning completed", timeline_titles)

        linked_operations = [task for task in app_module._load_operations_tasks() if task["source_type"] == "RESERVATION" and task["source_id"] == reservation["id"]]
        categories = {task["category"] for task in linked_operations}
        self.assertIn("Arrival Cleaning", categories)
        self.assertIn("Check-in Preparation", categories)
        self.assertIn("Welcome Pack", categories)
        self.assertIn("Guest Inspection", categories)
        self.assertIn("Departure Cleaning", categories)
        self.assertIn("Maintenance Review", categories)

        reservation_event = next(event for event in app_module._load_calendar_events() if event.get("metadata", {}).get("reservation_id") == reservation["id"])
        self.assertEqual(reservation_event["status"], "COMPLETED")

        availability = app_module._property_availability_engine(property_record, app_module._load_reservations(property_ids=["property-1"]))
        self.assertGreaterEqual(availability["availability_percent"], 0)
        self.assertGreaterEqual(availability["occupancy_percent"], 0)
        self.assertTrue(availability["cleaning_required"])

    def test_reservation_import_ical_parsing_duplicate_detection_and_rollback(self):
        ics_text = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:ical-001
SUMMARY:Anna Ivanova
DESCRIPTION:Imported from iCal
DTSTART:20260710T140000Z
DTEND:20260714T110000Z
LOCATION:Sea View Villa
STATUS:CONFIRMED
END:VEVENT
BEGIN:VEVENT
UID:ical-001
SUMMARY:Anna Ivanova
DESCRIPTION:Imported from iCal
DTSTART:20260710T140000Z
DTEND:20260714T110000Z
LOCATION:Sea View Villa
STATUS:CONFIRMED
END:VEVENT
END:VCALENDAR"""

        with patch.dict(os.environ, self.env, clear=True), patch("app.Thread", ImmediateThread), patch("app.smtplib.SMTP", FakeSMTP), patch("app.smtplib.SMTP_SSL", FakeSMTP):
            self._seed_owner(owner_id="owner-1", email="owner-one@example.com", full_name="Elena Petrova", city="Varna")
            self._seed_property(property_id="property-1", owner_id="owner-1", name="Sea View Villa", location="Varna")

            preview = app_module._reservation_importer().preview(
                "ical",
                {"ics_text": ics_text},
                context={"created_by": "admin"},
            )

            self.assertEqual(len(preview["items"]), 2)
            self.assertEqual(preview["items"][0]["property_id"], "property-1")
            self.assertEqual(preview["items"][0]["validation_state"], "new")
            self.assertFalse(preview["report"]["ready_to_import"])
            self.assertEqual(len(preview["report"]["duplicates"]), 1)

            import_result = app_module._reservation_importer().import_preview(preview, created_by="admin")

        self.assertFalse(import_result["ok"])
        self.assertEqual(app_module._load_reservations(), [])
        self.assertFalse(any(task["source_type"] == "RESERVATION" for task in app_module._load_operations_tasks()))


if __name__ == "__main__":
    unittest.main()
