import base64
import io
import html as html_lib
from html.parser import HTMLParser
import json
import os
import re
import sqlite3
import shutil
import smtplib
import unittest
from email.message import EmailMessage
from pathlib import Path
import uuid
from unittest.mock import patch

import app as app_module
from app import app, _mask_email


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


class RejectingSMTP:
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
        return None

    def send_message(self, message):
        raise smtplib.SMTPRecipientsRefused({"owner@example.com": (550, b"Rejected")})


class ImmediateThread:
    def __init__(self, target=None, args=(), kwargs=None, daemon=None):
        self.target = target
        self.args = args
        self.kwargs = kwargs or {}

    def start(self):
        if self.target:
            self.target(*self.args, **self.kwargs)


class FakeUrlopenResponse:
    def __init__(self, status=200, body=b'{"ok": true}'):
        self.status = status
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self._body

    def getcode(self):
        return self.status


def fake_urlopen(request, timeout=None):
    FakeUrlopenResponse.calls.append({
        "url": getattr(request, "full_url", str(request)),
        "data": getattr(request, "data", b""),
        "timeout": timeout,
    })
    return FakeUrlopenResponse()


FakeUrlopenResponse.calls = []


class OwnerPortalTests(unittest.TestCase):
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
        self._tmpdir = Path(self._cwd) / f".tmp_owner_portal_tests_{uuid.uuid4().hex}"
        self._tmpdir.mkdir(exist_ok=True)
        os.chdir(self._tmpdir)
        self.owner_db_path = self._tmpdir / "data" / "blacksea_owner.db"
        self.ADMIN_ENV = {**self.ADMIN_ENV, "OWNER_DB_PATH": str(self.owner_db_path)}
        self.SMTP_ENV = {**self.SMTP_ENV, "OWNER_DB_PATH": str(self.owner_db_path)}
        self._env_patcher = patch.dict(
            os.environ,
            {"OWNER_DB_PATH": str(self.owner_db_path)},
        )
        self._env_patcher.start()
        app.config["TESTING"] = True
        app_module._PUBLIC_FORM_RATE_LIMITS.clear()
        self.client = app.test_client()

    def tearDown(self):
        self._env_patcher.stop()
        os.chdir(self._cwd)
        shutil.rmtree(self._tmpdir, ignore_errors=True)
        FakeSMTP.sent_messages.clear()
        FakeUrlopenResponse.calls.clear()

    def _auth_headers(self):
        token = base64.b64encode(f"{self.ADMIN_ENV['ADMIN_USERNAME']}:{self.ADMIN_ENV['ADMIN_PASSWORD']}".encode("utf-8")).decode("ascii")
        return {"Authorization": f"Basic {token}"}

    def _read_jsonl(self, filename):
        owner_table_map = {
            "owner_accounts.jsonl": "owner_accounts",
            "owner_properties.jsonl": "owner_properties",
            "owner_magic_tokens.jsonl": "owner_magic_tokens",
            "owner_magic_email_events.jsonl": "owner_magic_email_events",
        }
        table_name = owner_table_map.get(filename)
        db_path = Path(os.getenv("OWNER_DB_PATH", str(Path("data") / "blacksea_owner.db")))
        if table_name and db_path.exists():
            conn = sqlite3.connect(db_path)
            try:
                conn.row_factory = sqlite3.Row
                order_by = "sequence ASC" if table_name == "owner_magic_email_events" else "created_at ASC"
                rows = conn.execute(f"SELECT * FROM {table_name} ORDER BY {order_by}").fetchall()
            finally:
                conn.close()

            records = []
            for row in rows:
                record = dict(row)
                if table_name == "owner_magic_email_events":
                    account_found = record.get("account_found")
                    record["account_found"] = None if account_found is None else bool(account_found)
                records.append(record)
            return records

        path = Path("data") / filename
        if not path.exists():
            return []

        records = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line))
        return records

    def _read_owner_db_rows(self, table_name):
        db_path = Path(os.getenv("OWNER_DB_PATH", str(Path("data") / "blacksea_owner.db")))
        if not db_path.exists():
            return []

        conn = sqlite3.connect(db_path)
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(f"SELECT * FROM {table_name}").fetchall()
        finally:
            conn.close()
        return [dict(row) for row in rows]

    def _seed_jsonl(self, filename, records):
        data_dir = Path("data")
        data_dir.mkdir(exist_ok=True)
        path = data_dir / filename
        with path.open("w", encoding="utf-8") as f:
            for record in records:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _insert_owner_db_rows(self, table_name, rows):
        db_path = Path(os.getenv("OWNER_DB_PATH", str(Path("data") / "blacksea_owner.db")))
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with app_module._owner_db_connection() as conn:
            app_module._ensure_owner_db_schema(conn)
            if table_name == "professional_accounts":
                conn.executemany(
                    """
                    INSERT INTO professional_accounts (email, id, created_at, full_name, phone, company, service_categories, status, last_login_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(email) DO UPDATE SET
                        id = excluded.id,
                        created_at = excluded.created_at,
                        full_name = excluded.full_name,
                        phone = excluded.phone,
                        company = excluded.company,
                        service_categories = excluded.service_categories,
                        status = excluded.status,
                        last_login_at = excluded.last_login_at
                    """,
                    [
                        (
                            row.get("email", ""),
                            row.get("id", ""),
                            row.get("created_at", ""),
                            row.get("full_name", ""),
                            row.get("phone", ""),
                            row.get("company", ""),
                            row.get("service_categories", ""),
                            row.get("status", "PENDING"),
                            row.get("last_login_at", ""),
                        )
                        for row in rows
                    ],
                )
            elif table_name == "calendar_events":
                conn.executemany(
                    """
                    INSERT INTO calendar_events (
                        id, created_at, updated_at, property_id, owner_id, operation_task_id, event_type, title, description,
                        start_datetime, end_datetime, all_day, status, assigned_professional, created_by, color, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        created_at = excluded.created_at,
                        updated_at = excluded.updated_at,
                        property_id = excluded.property_id,
                        owner_id = excluded.owner_id,
                        operation_task_id = excluded.operation_task_id,
                        event_type = excluded.event_type,
                        title = excluded.title,
                        description = excluded.description,
                        start_datetime = excluded.start_datetime,
                        end_datetime = excluded.end_datetime,
                        all_day = excluded.all_day,
                        status = excluded.status,
                        assigned_professional = excluded.assigned_professional,
                        created_by = excluded.created_by,
                        color = excluded.color,
                        metadata_json = excluded.metadata_json
                    """,
                    [
                        (
                            row.get("id", ""),
                            row.get("created_at", ""),
                            row.get("updated_at", row.get("created_at", "")),
                            row.get("property_id", ""),
                            row.get("owner_id", ""),
                            row.get("operation_task_id", ""),
                            row.get("event_type", "Other"),
                            row.get("title", ""),
                            row.get("description", ""),
                            row.get("start_datetime", ""),
                            row.get("end_datetime", ""),
                            int(row.get("all_day", 0) or 0),
                            row.get("status", "SCHEDULED"),
                            row.get("assigned_professional", ""),
                            row.get("created_by", ""),
                            row.get("color", "grey"),
                            row.get("metadata_json", "{}"),
                        )
                        for row in rows
                    ],
                )
            elif table_name == "reservations":
                conn.executemany(
                    """
                    INSERT INTO reservations (
                        id, created_at, updated_at, property_id, reservation_source, reservation_reference, channel_name,
                        channel_status, last_sync, external_payload, external_reference, external_last_sync,
                        import_batch_id, sync_status, source_metadata_json, guest_first_name, guest_last_name, guest_email,
                        guest_phone, adults, children, infants, pets, arrival_datetime, departure_datetime, status, notes,
                        language, created_by, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        created_at = excluded.created_at,
                        updated_at = excluded.updated_at,
                        property_id = excluded.property_id,
                        reservation_source = excluded.reservation_source,
                        reservation_reference = excluded.reservation_reference,
                        channel_name = excluded.channel_name,
                        channel_status = excluded.channel_status,
                        last_sync = excluded.last_sync,
                        external_payload = excluded.external_payload,
                        external_reference = excluded.external_reference,
                        external_last_sync = excluded.external_last_sync,
                        import_batch_id = excluded.import_batch_id,
                        sync_status = excluded.sync_status,
                        source_metadata_json = excluded.source_metadata_json,
                        guest_first_name = excluded.guest_first_name,
                        guest_last_name = excluded.guest_last_name,
                        guest_email = excluded.guest_email,
                        guest_phone = excluded.guest_phone,
                        adults = excluded.adults,
                        children = excluded.children,
                        infants = excluded.infants,
                        pets = excluded.pets,
                        arrival_datetime = excluded.arrival_datetime,
                        departure_datetime = excluded.departure_datetime,
                        status = excluded.status,
                        notes = excluded.notes,
                        language = excluded.language,
                        created_by = excluded.created_by,
                        metadata_json = excluded.metadata_json
                    """,
                    [
                        (
                            row.get("id", ""),
                            row.get("created_at", ""),
                            row.get("updated_at", row.get("created_at", "")),
                            row.get("property_id", ""),
                            row.get("reservation_source", "Manual"),
                            row.get("reservation_reference", ""),
                            row.get("channel_name", "Manual"),
                            row.get("channel_status", "SYNCED"),
                            row.get("last_sync", ""),
                            row.get("external_payload", "{}"),
                            row.get("external_reference", ""),
                            row.get("external_last_sync", ""),
                            row.get("import_batch_id", ""),
                            row.get("sync_status", "IDLE"),
                            row.get("source_metadata_json", "{}"),
                            row.get("guest_first_name", ""),
                            row.get("guest_last_name", ""),
                            row.get("guest_email", ""),
                            row.get("guest_phone", ""),
                            int(row.get("adults", 1) or 1),
                            int(row.get("children", 0) or 0),
                            int(row.get("infants", 0) or 0),
                            int(row.get("pets", 0) or 0),
                            row.get("arrival_datetime", ""),
                            row.get("departure_datetime", ""),
                            row.get("status", "PENDING"),
                            row.get("notes", ""),
                            row.get("language", "en"),
                            row.get("created_by", ""),
                            row.get("metadata_json", "{}"),
                        )
                        for row in rows
                    ],
                )
            elif table_name == "operations_tasks":
                conn.executemany(
                    """
                    INSERT INTO operations_tasks (
                        id, request_id, source_type, source_id, owner_id, property_id, created_at, updated_at, title,
                        category, property_name, property_location, owner_name, owner_email, assigned_to, assigned_professional_id,
                        priority, status, due_date, notes, completed_at, completion_report_json, admin_notes, request_status,
                        checklist_json, attachments_json, comments_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        request_id = excluded.request_id,
                        source_type = excluded.source_type,
                        source_id = excluded.source_id,
                        owner_id = excluded.owner_id,
                        property_id = excluded.property_id,
                        created_at = excluded.created_at,
                        updated_at = excluded.updated_at,
                        title = excluded.title,
                        category = excluded.category,
                        property_name = excluded.property_name,
                        property_location = excluded.property_location,
                        owner_name = excluded.owner_name,
                        owner_email = excluded.owner_email,
                        assigned_to = excluded.assigned_to,
                        assigned_professional_id = excluded.assigned_professional_id,
                        priority = excluded.priority,
                        status = excluded.status,
                        due_date = excluded.due_date,
                        notes = excluded.notes,
                        completed_at = excluded.completed_at,
                        completion_report_json = excluded.completion_report_json,
                        admin_notes = excluded.admin_notes,
                        request_status = excluded.request_status,
                        checklist_json = excluded.checklist_json,
                        attachments_json = excluded.attachments_json,
                        comments_json = excluded.comments_json
                    """,
                    [
                        (
                            row.get("id", ""),
                            row.get("request_id", ""),
                            row.get("source_type", ""),
                            row.get("source_id", ""),
                            row.get("owner_id", ""),
                            row.get("property_id", ""),
                            row.get("created_at", ""),
                            row.get("updated_at", row.get("created_at", "")),
                            row.get("title", ""),
                            row.get("category", ""),
                            row.get("property_name", ""),
                            row.get("property_location", ""),
                            row.get("owner_name", ""),
                            row.get("owner_email", ""),
                            row.get("assigned_to", ""),
                            row.get("assigned_professional_id", ""),
                            row.get("priority", "NORMAL"),
                            row.get("status", "NEW"),
                            row.get("due_date", ""),
                            row.get("notes", ""),
                            row.get("completed_at", ""),
                            row.get("completion_report_json", "{}"),
                            row.get("admin_notes", ""),
                            row.get("request_status", "new"),
                            row.get("checklist_json", "[]"),
                            row.get("attachments_json", "[]"),
                            row.get("comments_json", "[]"),
                        )
                        for row in rows
                    ],
                )
            elif table_name == "operations_task_events":
                conn.executemany(
                    """
                    INSERT INTO operations_task_events (id, task_id, created_at, event_type, title, detail, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        task_id = excluded.task_id,
                        created_at = excluded.created_at,
                        event_type = excluded.event_type,
                        title = excluded.title,
                        detail = excluded.detail,
                        status = excluded.status
                    """,
                    [
                        (
                            row.get("id", ""),
                            row.get("task_id", ""),
                            row.get("created_at", ""),
                            row.get("event_type", ""),
                            row.get("title", ""),
                            row.get("detail", ""),
                            row.get("status", "NEW"),
                        )
                        for row in rows
                    ],
                )
            else:
                raise ValueError(f"Unsupported table: {table_name}")

    def _owner_payload(self, email="owner@example.com"):
        return {
            "full_name": "Elena Petrova",
            "email": email,
            "phone": "+359888111222",
            "property_type": "Villa",
            "city": "Varna",
            "property_name": "Sea View Villa",
            "number_of_units": "2",
            "notes": "Prefers WhatsApp updates.",
        }

    def _demo_login_payload(self, email="owner@blackseaconnect.com", password=None):
        return {"email": email}

    def _seed_owner_property(self, owner_id="owner-1", owner_email="owner@blackseaconnect.com", name="Sea View Villa", location="Varna", operating_mode="year-round"):
        self._seed_jsonl("owner_properties.jsonl", [{
            "id": "property-1",
            "owner_id": owner_id,
            "created_at": "2026-06-15T10:30:00Z",
            "name": name,
            "property_type": "Villa",
            "location": location,
            "bedrooms": 3,
            "bathrooms": 2,
            "guest_capacity": 6,
            "operating_mode": operating_mode,
            "notes": "",
        }])

    def _seed_owner_property_assets(self, property_id="property-1", **overrides):
        record = {
            "profile": {
                "address": "12 Marina Street",
                "city": "Varna",
                "country": "Bulgaria",
                "capacity": "6",
                "bedrooms": "3",
                "bathrooms": "2",
                "floor": "3",
                "elevator": "yes",
                "parking": "Garage",
            },
            "photos": [
                {
                    "id": "photo-1",
                    "kind": "photo",
                    "filename": "cover.jpg",
                    "stored_filename": "photo-1.jpg",
                    "content_type": "image/jpeg",
                    "size": 12,
                    "uploaded_at": "2026-06-15T10:45:00Z",
                    "is_cover": True,
                }
            ],
            "documents": [],
            "amenities": {"wifi": True},
            "house_rules": {},
            "access_information": {},
            "welcome_instructions": "Welcome to the property.",
            "last_updated_at": "2026-06-15T10:45:00Z",
        }
        record.update(overrides)
        app_module._owner_property_save_assets(property_id, record)

    def _login_owner_via_magic(self, email="owner@blackseaconnect.com", seed_property=True):
        self._seed_owner_account(email=email)
        if seed_property:
            self._seed_owner_property(owner_id="owner-1", owner_email=email)
        with patch.dict(os.environ, self.SMTP_ENV, clear=True), patch("app.smtplib.SMTP", FakeSMTP), patch("app.smtplib.SMTP_SSL", FakeSMTP):
            response = self.client.post("/owners/login", data={"email": email})
        self.assertEqual(response.status_code, 302)
        self.assertIn("/owners/login?magic_sent=1", response.headers["Location"])
        self.assertIn("delivery=sent", response.headers["Location"])
        self.assertIn(f"magic_recipient={_mask_email(email)}", response.headers["Location"])
        self.assertIn("lang=bg", response.headers["Location"])

        tokens = self._read_jsonl("owner_magic_tokens.jsonl")
        self.assertTrue(tokens)
        token = tokens[-1]["token"]

        login_response = self.client.get(f"/auth/owner-magic/{token}")
        self.assertEqual(login_response.status_code, 302)
        self.assertIn("/owners/dashboard", login_response.headers["Location"])
        self.assertIn("lang=bg", login_response.headers["Location"])
        return login_response

    def _request_owner_magic_link(self, email="owner@blackseaconnect.com", seed_property=False):
        self._seed_owner_account(email=email)
        if seed_property:
            self._seed_owner_property(owner_id="owner-1", owner_email=email)
        with patch.dict(os.environ, self.SMTP_ENV, clear=True), patch("app.smtplib.SMTP", FakeSMTP), patch("app.smtplib.SMTP_SSL", FakeSMTP):
            response = self.client.post("/owners/login", data={"email": email})
        self.assertEqual(response.status_code, 302)
        self.assertIn("/owners/login?magic_sent=1", response.headers["Location"])
        self.assertIn("delivery=sent", response.headers["Location"])
        self.assertIn(f"magic_recipient={_mask_email(email)}", response.headers["Location"])
        self.assertIn("lang=bg", response.headers["Location"])

        tokens = self._read_jsonl("owner_magic_tokens.jsonl")
        self.assertTrue(tokens)
        return response, tokens[-1]["token"]

    def _demo_owner_request(self, **overrides):
        record = {
            "id": "owner-request-1",
            "created_at": "2026-06-15T11:00:00Z",
            "last_update_at": "2026-06-15T11:00:00Z",
            "status": "new",
            "request_source": "owner",
            "owner_id": "owner-demo",
            "owner_email": "owner@blackseaconnect.com",
            "owner_name": "Elena Petrova",
            "owner_phone": "+359888111222",
            "name": "Elena Petrova",
            "email": "owner@blackseaconnect.com",
            "phone": "+359888333444",
            "property": "Sea View Villa",
            "property_city": "Varna",
            "property_type": "Villa",
            "number_of_units": "2",
            "service_category": "Concierge",
            "preferred_date": "2026-07-15",
            "description": "Need airport pickup.",
            "assigned_provider_id": "",
            "assigned_provider_name": "",
            "assigned_provider_company": "",
            "assigned_professional_id": "",
            "assigned_professional_name": "",
            "assigned_professional_company": "",
            "internal_notes": "",
            "timeline": [],
        }
        record.update(overrides)
        return record

    def _service_request_payload(self):
        return {
            "category": "Concierge",
            "preferred_date": "2026-07-15",
            "property": "Sea View Villa",
            "description": "Need airport pickup and welcome coordination.",
            "contact_phone": "+359888333444",
        }

    def _seed_owner_account(self, email="owner@blackseaconnect.com", **overrides):
        record = {
            "id": "owner-1",
            "created_at": "2026-06-15T10:00:00Z",
            "full_name": "Elena Petrova",
            "email": email,
            "phone": "+359888111222",
            "property_type": "Villa",
            "city": "Varna",
            "property_name": "Sea View Villa",
            "number_of_units": 2,
            "notes": "",
            "status": "PILOT",
            "language": "bg",
            "last_login_at": "",
            "internal_notes": "",
        }
        record.update(overrides)
        self._seed_jsonl("owner_accounts.jsonl", [record])

    def test_owner_registration_creates_account_and_sends_magic_flow(self):
        smtp_env = {**self.SMTP_ENV, "ADMIN_NOTIFICATION_EMAIL": "ops@example.com"}
        with patch.dict(os.environ, smtp_env, clear=True), patch("app.smtplib.SMTP", FakeSMTP), patch("app.smtplib.SMTP_SSL", FakeSMTP):
            response = self.client.post("/owners/register", data=self._owner_payload())

        self.assertEqual(response.status_code, 302)
        self.assertIn("/owners/login?registered=1&magic_sent=1", response.headers["Location"])
        self.assertIn("delivery=sent", response.headers["Location"])
        self.assertIn(f"magic_recipient={_mask_email('owner@example.com')}", response.headers["Location"])
        self.assertIn("lang=bg", response.headers["Location"])

        page = self.client.get(response.headers["Location"])
        self.assertEqual(page.status_code, 200)
        html = page.get_data(as_text=True)
        self.assertIn(f"Изпратихме защитен линк до {_mask_email('owner@example.com')}. Проверете входящата поща и Spam.", html)

        with self.client.session_transaction() as sess:
            self.assertNotIn("owner_logged_in", sess)
            self.assertNotIn("owner_id", sess)

        accounts = self._read_jsonl("owner_accounts.jsonl")
        self.assertEqual(len(accounts), 1)
        self.assertEqual(accounts[0]["full_name"], "Elena Petrova")
        self.assertEqual(accounts[0]["number_of_units"], 2)

        tokens = self._read_jsonl("owner_magic_tokens.jsonl")
        self.assertEqual(len(tokens), 1)
        self.assertEqual(tokens[0]["email"], "owner@example.com")
        self.assertEqual(len(FakeSMTP.sent_messages), 3)
        admin_message = next(message for message in FakeSMTP.sent_messages if message["Subject"] == "[BlackSea Owners] New owner registration")
        owner_message = next(message for message in FakeSMTP.sent_messages if message["Subject"] == "BlackSea Connect — Вход в портала за собственици")
        operations_message = next(message for message in FakeSMTP.sent_messages if message["Subject"] == "[BlackSeaConnect] Operations task notification")

        self.assertEqual(admin_message["From"], "BlackSea Connect <concierge@blackseaconnect.com>")
        self.assertEqual(admin_message["To"], "ops@example.com")
        self.assertIn("Full name: Elena Petrova", admin_message.get_content())
        self.assertIn("Email: owner@example.com", admin_message.get_content())
        self.assertIn("Phone: +359888111222", admin_message.get_content())
        self.assertIn("Property name: Sea View Villa", admin_message.get_content())
        self.assertIn("Property type: Villa", admin_message.get_content())
        self.assertIn("City/location: Varna", admin_message.get_content())
        self.assertIn("Number of units: 2", admin_message.get_content())
        self.assertIn("Language: bg", admin_message.get_content())
        self.assertIn("Created at:", admin_message.get_content())
        self.assertIn("Source URL: http://localhost/owners/register", admin_message.get_content())
        self.assertIn("Task title: Elena Petrova", operations_message.get_content())

        self.assertIn("BlackSea Connect Owner Portal", owner_message["From"])
        self.assertIn("concierge@blackseaconnect.com", owner_message["From"])
        self.assertEqual(owner_message["Reply-To"], "concierge@blackseaconnect.com")
        self.assertIn("mailto:concierge@blackseaconnect.com?subject=unsubscribe", owner_message["List-Unsubscribe"])
        self.assertTrue(owner_message["Message-ID"].startswith("<"))
        self.assertTrue(owner_message.is_multipart())
        plain_part = owner_message.get_body(preferencelist=("plain",))
        self.assertIsNotNone(plain_part)
        self.assertIn(
            "You are receiving this email because you requested access to your BlackSea Connect owner portal.",
            plain_part.get_content(),
        )
        html_part = owner_message.get_body(preferencelist=("html",))
        self.assertIsNotNone(html_part)
        self.assertIn("Влезте в портала", html_part.get_content())

        events = self._read_jsonl("owner_magic_email_events.jsonl")
        self.assertEqual([event["event"] for event in events], ["owner_registration_notification_sent", "token_created", "sent"])
        self.assertTrue(all(event["email_masked"] == _mask_email("owner@example.com") for event in events))
        self.assertTrue(all(event["submitted_email"] == "owner@example.com" for event in events))
        self.assertEqual(events[0]["smtp_message_id"], "")
        self.assertEqual(events[1]["smtp_message_id"], "")
        self.assertEqual(events[2]["smtp_message_id"], owner_message["Message-ID"])

    def test_owner_registration_email_field_starts_empty_and_preserves_user_input_only(self):
        response = self.client.get("/owners/register")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('id="owner-register-email"', html)
        self.assertIn('name="email" value=""', html)
        self.assertNotIn('name="email" value="/owners/register"', html)

        invalid_post = self.client.post(
            "/owners/register",
            data={
                "full_name": "",
                "email": "owner@example.com",
                "phone": "",
                "property_type": "",
                "city": "",
                "property_name": "",
                "number_of_units": "",
                "notes": "",
            },
        )
        self.assertEqual(invalid_post.status_code, 400)
        invalid_html = invalid_post.get_data(as_text=True)
        self.assertIn('name="email" value="owner@example.com"', invalid_html)
        self.assertNotIn('value="/owners/register"', invalid_html)

    def test_owner_registration_honeypot_blocks_account_creation(self):
        payload = {
            **self._owner_payload(),
            "website": "https://spam.example.com",
        }

        smtp_env = {**self.SMTP_ENV, "ADMIN_NOTIFICATION_EMAIL": "ops@example.com"}
        with patch.dict(os.environ, smtp_env, clear=True), patch("app.smtplib.SMTP", FakeSMTP), patch("app.smtplib.SMTP_SSL", FakeSMTP):
            response = self.client.post("/owners/register", data=payload)

        self.assertEqual(response.status_code, 302)
        self.assertIn("/owners/login?magic_sent=1&delivery=generic", response.headers["Location"])
        self.assertFalse((Path("data") / "owner_accounts.jsonl").exists())
        self.assertFalse((Path("data") / "owner_magic_tokens.jsonl").exists())
        self.assertEqual(FakeSMTP.sent_messages, [])

    def test_owner_routes_require_login(self):
        response_dashboard = self.client.get("/owners/dashboard")
        response_request = self.client.get("/owners/request-service")
        response_property_new = self.client.get("/owners/property/new")

        self.assertEqual(response_dashboard.status_code, 302)
        self.assertTrue(response_dashboard.headers["Location"].startswith("/owners/login"))
        self.assertEqual(response_request.status_code, 302)
        self.assertTrue(response_request.headers["Location"].startswith("/owners/login"))
        self.assertEqual(response_property_new.status_code, 302)
        self.assertTrue(response_property_new.headers["Location"].startswith("/owners/login"))

    def test_owner_dashboard_shows_empty_state_without_properties(self):
        self._login_owner_via_magic(seed_property=False)
        response = self.client.get("/owners/dashboard")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Добре дошли в BlackSea Connect", html)
        self.assertIn("Добавете първия си имот, за да започнем оперативната подготовка.", html)
        self.assertIn('href="/owners/property/new?lang=bg"', html)

    def test_owner_dashboard_renders_french_copy_and_preserves_lang_links(self):
        self._login_owner_via_magic(seed_property=False)

        response = self.client.get("/owners/dashboard?lang=fr")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('<html lang="fr">', html)
        self.assertIn("Aperçu premium du bien.", html)
        self.assertIn("Retour au site", html)
        self.assertIn('href="/owners/request-service?lang=fr"', html)
        self.assertIn('href="/owners/property/new?lang=fr"', html)

    def test_owner_property_creation_saves_and_redirects(self):
        self._login_owner_via_magic(seed_property=False)

        response = self.client.post(
            "/owners/property/new",
            data={
                "name": "Sea View Villa",
                "property_type": "Villa",
                "location": "Varna, Bulgaria",
                "bedrooms": "3",
                "bathrooms": "2",
                "guest_capacity": "6",
                "operating_mode": "year-round",
                "notes": "Prefers weekend updates.",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("/owners/dashboard?property_added=1", response.headers["Location"])
        self.assertIn("lang=bg", response.headers["Location"])

        properties = self._read_jsonl("owner_properties.jsonl")
        self.assertEqual(len(properties), 1)
        self.assertEqual(properties[0]["name"], "Sea View Villa")
        self.assertEqual(properties[0]["location"], "Varna, Bulgaria")
        self.assertEqual(properties[0]["operating_mode"], "year-round")

    def test_owner_property_new_renders_french_copy_and_hidden_lang(self):
        self._login_owner_via_magic(seed_property=False)

        response = self.client.get("/owners/property/new?lang=fr")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('<html lang="fr">', html)
        self.assertIn("Ajouter un bien", html)
        self.assertIn("Renseignez votre premier bien pour lancer la préparation opérationnelle.", html)
        self.assertIn("Que se passe-t-il ensuite ?", html)
        self.assertIn('name="lang" value="fr"', html)
        self.assertIn('href="/owners/dashboard?lang=fr"', html)
        self.assertIn('href="/owners/logout?lang=fr"', html)

    def test_owner_property_new_prefills_name_without_creating_property(self):
        self._login_owner_via_magic(seed_property=False)

        response = self.client.get("/owners/property/new?name=Missing+Villa&lang=en")

        self.assertEqual(response.status_code, 200)
        self.assertIn('name="name" value="Missing Villa"', response.get_data(as_text=True))
        self.assertEqual(self._read_jsonl("owner_properties.jsonl"), [])

    def test_owner_property_creation_preserves_language_on_redirect(self):
        self._login_owner_via_magic(seed_property=False)

        response = self.client.post(
            "/owners/property/new",
            data={
                "lang": "fr",
                "name": "Sea View Villa",
                "property_type": "Villa",
                "location": "Varna, Bulgaria",
                "bedrooms": "3",
                "bathrooms": "2",
                "guest_capacity": "6",
                "operating_mode": "year-round",
                "notes": "Prefers weekend updates.",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("/owners/dashboard?property_added=1", response.headers["Location"])
        self.assertIn("lang=fr", response.headers["Location"])

    def test_owner_property_wizard_creates_assets_and_gallery(self):
        self._login_owner_via_magic(seed_property=False)

        step_one_response = self.client.post(
            "/owners/property/new",
            data={
                "wizard_step": "basic",
                "name": "Sea View Villa",
                "property_type": "Villa",
                "address": "12 Marina Street",
                "city": "Varna",
                "country": "Bulgaria",
                "capacity": "6",
                "bedrooms": "3",
                "bathrooms": "2",
                "floor": "3",
                "elevator": "yes",
                "parking": "Garage access",
                "notes": "Premium onboarding",
            },
        )

        self.assertEqual(step_one_response.status_code, 302)
        self.assertIn("step=photos", step_one_response.headers["Location"])
        self.assertIn("property_id=", step_one_response.headers["Location"])

        property_rows = self._read_owner_db_rows("owner_properties")
        self.assertEqual(len(property_rows), 1)
        property_id = property_rows[0]["id"]

        step_two_response = self.client.post(
            "/owners/property/new",
            data={
                "wizard_step": "photos",
                "property_id": property_id,
                "photos": (io.BytesIO(b"fake-photo-bytes"), "cover.jpg"),
                "documents": (io.BytesIO(b"%PDF-1.4 fake"), "manual.pdf"),
                "amenity_wifi": "1",
                "welcome_instructions": "Please enjoy your stay.",
                "access_wifi_name": "BlackSea-Guest",
                "access_wifi_password": "calmwater",
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(step_two_response.status_code, 302)
        self.assertIn(f"/owners/properties/{property_id}", step_two_response.headers["Location"])

        property_row = self._read_owner_db_rows("owner_properties")[0]
        assets = json.loads(property_row["knowledge_json"])

        self.assertEqual(assets["profile"]["city"], "Varna")
        self.assertEqual(assets["photos"][0]["filename"], "cover.jpg")
        self.assertTrue(assets["amenities"]["wifi"])
        self.assertEqual(assets["welcome_instructions"], "Please enjoy your stay.")

        detail_response = self.client.get(f"/owners/properties/{property_id}")
        self.assertEqual(detail_response.status_code, 200)
        detail_html = detail_response.get_data(as_text=True)
        self.assertIn("Gallery", detail_html)
        self.assertIn("Access information", detail_html)
        self.assertIn("Amenities", detail_html)
        self.assertIn("Knowledge hub", detail_html)
        self.assertIn("Property Health", detail_html)

    def test_owner_property_knowledge_hub_persists_and_syncs_calendar(self):
        self._seed_owner_account(email="owner@example.com")
        self._seed_owner_property(owner_id="owner-1", owner_email="owner@example.com", name="Sea View Villa", location="Varna")
        self._login_owner_via_magic(email="owner@example.com")

        response = self.client.post(
            "/owners/properties/property-1",
            data={
                "status": "ACTIVE",
                "notes": "Ready for guests.",
                "guest_guide_ready": "1",
                "access_instructions_ready": "1",
                "emergency_contact_ready": "1",
                "cleaning_partner_ready": "1",
                "knowledge_description": "Premium coastal villa.",
                "knowledge_building": "Marina Residence",
                "knowledge_apartment": "A3",
                "knowledge_neighbourhood": "Sea Garden",
                "knowledge_languages_spoken": "BG, EN",
                "knowledge_emergency_contacts": "Local concierge desk",
                "access_building_entrance_code": "1234",
                "access_apartment_code": "A3",
                "access_key_safe_code": "5566",
                "wifi_network_name": "BlackSea",
                "wifi_password": "calmwater",
                "provider_electrician_name": "Blue Spark",
                "provider_electrician_phone": "+359888000111",
                "provider_electrician_preferred": "1",
                "seasonal_open_pool_active": "1",
                "seasonal_open_pool_target_date": "2026-07-01",
                "seasonal_open_pool_cadence": "Seasonal",
                "seasonal_open_pool_notes": "Coordinate with maintenance.",
            },
        )

        self.assertEqual(response.status_code, 302)

        property_row = self._read_owner_db_rows("owner_properties")[0]
        knowledge = json.loads(property_row["knowledge_json"])
        self.assertEqual(knowledge["general"]["description"], "Premium coastal villa.")
        self.assertEqual(knowledge["access"]["building_entrance_code"], "1234")
        self.assertEqual(knowledge["wifi"]["network_name"], "BlackSea")
        self.assertEqual(knowledge["service_providers"]["electrician"]["name"], "Blue Spark")
        self.assertTrue(knowledge["seasonal_tasks"]["open_pool"]["active"])

        calendar_rows = self._read_owner_db_rows("calendar_events")
        self.assertTrue(any(row["created_by"] == "owner-knowledge-hub" and row["property_id"] == "property-1" for row in calendar_rows))

    def test_owner_properties_dashboard_shows_cover_photo_and_readiness(self):
        self._seed_owner_account(email="owner@example.com")
        self._seed_owner_property(owner_id="owner-1", owner_email="owner@example.com", name="Sea View Villa", location="Varna")
        self._seed_owner_property_assets()
        self._login_owner_via_magic(email="owner@example.com")

        response = self.client.get("/owners/properties")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("/owners/properties/property-1/media/photo-1", html)
        self.assertIn("Ready", html)

    def test_owner_dashboard_lists_properties(self):
        self._seed_owner_account()
        self._seed_jsonl("owner_properties.jsonl", [
            {
                "id": "property-1",
                "owner_id": "owner-1",
                "created_at": "2026-06-15T10:30:00Z",
                "name": "Sea View Villa",
                "property_type": "Villa",
                "location": "Varna",
                "bedrooms": 3,
                "bathrooms": 2,
                "guest_capacity": 6,
                "operating_mode": "year-round",
                "notes": "",
            },
            {
                "id": "property-2",
                "owner_id": "owner-1",
                "created_at": "2026-06-15T10:45:00Z",
                "name": "Marina Apartment",
                "property_type": "Apartment",
                "location": "Sveti Vlas",
                "bedrooms": 2,
                "bathrooms": 1,
                "guest_capacity": 4,
                "operating_mode": "seasonal",
                "notes": "",
            },
        ])
        self._seed_jsonl("service_requests.jsonl", [self._demo_owner_request()])
        with self.client.session_transaction() as session:
            session["owner_logged_in"] = True
            session["owner_id"] = "owner-1"
            session["owner_email"] = "owner@blackseaconnect.com"
            session["owner_name"] = "Elena Petrova"

        response = self.client.get("/owners/dashboard")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Sea View Villa", html)
        self.assertIn("Marina Apartment", html)
        self.assertIn("Sveti Vlas", html)
        self.assertIn("Сезонен", html)
        self.assertIn("Целогодишен", html)

    def test_owner_dashboard_shows_onboarding_progress_after_first_property(self):
        self._seed_owner_account()
        self._seed_owner_property()
        self._login_owner_via_magic(seed_property=False)

        response = self.client.get("/owners/dashboard")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Подготвяме операциите на имота ви.", html)
        self.assertIn("50%", html)

    def test_owner_login_and_dashboard_visibility(self):
        self._seed_jsonl("service_requests.jsonl", [
            self._demo_owner_request(),
            self._demo_owner_request(
                id="public-request-1",
                created_at="2026-06-15T12:00:00Z",
                last_update_at="2026-06-15T12:00:00Z",
                request_source="public",
                owner_id="",
                owner_email="",
                name="Public Request",
                email="owner@blackseaconnect.com",
                phone="+359888555666",
                property="Shared Property",
                number_of_units="",
                service_category="Cleaning",
                preferred_date="2026-07-16",
                description="This should not appear on the owner dashboard.",
            ),
        ])

        self._login_owner_via_magic()
        response = self.client.get("/owners/dashboard")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Elena Petrova", html)
        self.assertIn("owner-request-1", html)
        self.assertNotIn("public-request-1", html)

    def test_owner_dashboard_uses_portal_sections_and_quick_actions(self):
        self._seed_jsonl("service_requests.jsonl", [self._demo_owner_request()])

        self._login_owner_via_magic()
        response = self.client.get("/owners/dashboard")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        for phrase in [
            'data-i18n="ownerDashboardPropertyOverview"',
            'data-i18n="ownerDashboardOperationsSnapshot"',
            'data-i18n="ownerDashboardPropertyHealth"',
            'data-i18n="ownerDashboardTrustedLocalTeam"',
            'data-i18n="ownerDashboardMonthlySummary"',
            'data-i18n="ownerDashboardPerformanceSnapshot"',
            'data-i18n="ownerDashboardActivityTimeline"',
            'data-i18n="ownerDashboardQuickActions"',
            'data-i18n="ownerDashboardNotificationCenter"',
            'data-i18n="ownerDashboardRecentPropertyUpdates"',
            'data-i18n="ownerDashboardPrimaryCta"',
            'data-i18n="navOwnerLogout"',
        ]:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, html)
        self.assertIn('body class="owner-portal-page owner-portal-dashboard-page owner-dashboard-page"', html)
        self.assertIn("owner-dashboard-page", html)
        self.assertIn("owner-dashboard-masthead", html)
        self.assertIn("owner-dashboard-main", html)
        self.assertIn("owner-dashboard-section", html)
        self.assertIn("owner-operational-command", html)
        self.assertIn("owner-operational-kpis", html)
        self.assertIn("owner-dashboard-disclosure", html)
        self.assertIn("owner-kpi-card--summary", html)
        self.assertIn("owner-portal-card--performance", html)
        self.assertIn("owner-timeline-item", html)
        self.assertIn("/static/img/saint-vlas.jpg", html)
        self.assertNotIn('<footer class="site-footer"', html)
        self.assertIn("owner-request-1", html)
        self.assertNotRegex(html, r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")

    def test_owner_property_management_lists_detail_and_persists_updates(self):
        self._seed_owner_account(email="owner@example.com")
        self._seed_owner_property(owner_id="owner-1", owner_email="owner@example.com", name="Sea View Villa", location="Varna")
        self._seed_jsonl("service_requests.jsonl", [
            self._demo_owner_request(owner_id="owner-1", owner_email="owner@example.com", property_id="property-1", property="Sea View Villa")
        ])

        self._login_owner_via_magic(email="owner@example.com")

        list_response = self.client.get("/owners/properties")
        self.assertEqual(list_response.status_code, 200)
        list_html = list_response.get_data(as_text=True)
        self.assertIn("Property Management", list_html)
        self.assertIn("Sea View Villa", list_html)
        self.assertIn("/owners/properties/property-1", list_html)
        self.assertIn("Setup", list_html)

        detail_response = self.client.get("/owners/properties/property-1")
        self.assertEqual(detail_response.status_code, 200)
        detail_html = detail_response.get_data(as_text=True)
        self.assertIn("Property snapshot", detail_html)
        self.assertIn("data-property-edit-toggle", detail_html)
        self.assertIn("Future integrations", detail_html)
        self.assertIn('role="tablist"', detail_html)
        self.assertIn('data-property-workspace-tab="overview"', detail_html)
        self.assertIn('data-property-workspace-tab="equipment"', detail_html)
        self.assertIn('data-property-tab-section="operations"', detail_html)
        self.assertIn("owner-property-equipment-list", detail_html)
        self.assertIn("Readiness checklist", detail_html)
        self.assertIn("Recent requests", detail_html)
        self.assertIn("Sea View Villa", detail_html)
        self.assertIn("Concierge", detail_html)
        self.assertIn("property_id=property-1", detail_html)

        update_response = self.client.post(
            "/owners/properties/property-1",
            data={
                "status": "ACTIVE",
                "notes": "Ready for guests.",
                "guest_guide_ready": "1",
                "access_instructions_ready": "1",
                "emergency_contact_ready": "1",
            },
        )

        self.assertEqual(update_response.status_code, 302)
        self.assertIn("/owners/properties/property-1", update_response.headers["Location"])

        property_row = self._read_owner_db_rows("owner_properties")[0]
        self.assertEqual(property_row["status"], "ACTIVE")
        self.assertEqual(property_row["notes"], "Ready for guests.")
        self.assertEqual(property_row["guest_guide_ready"], 1)
        self.assertEqual(property_row["access_instructions_ready"], 1)
        self.assertEqual(property_row["emergency_contact_ready"], 1)
        self.assertEqual(property_row["cleaning_partner_ready"], 0)

        activity_rows = self._read_owner_db_rows("owner_activity_events")
        self.assertTrue(any(row["event_type"] == "status_changed" for row in activity_rows))
        self.assertTrue(any(row["event_type"] == "note_added" for row in activity_rows))

        with patch.dict(os.environ, self.SMTP_ENV, clear=True), patch("app.Thread", ImmediateThread), patch("app.smtplib.SMTP", FakeSMTP), patch("app.smtplib.SMTP_SSL", FakeSMTP):
            request_response = self.client.post(
                "/owners/request-service",
                data={**self._service_request_payload(), "property_id": "property-1"},
            )

        self.assertEqual(request_response.status_code, 302)
        service_records = self._read_jsonl("service_requests.jsonl")
        self.assertEqual(service_records[-1]["property_id"], "property-1")

    def test_owner_request_service_category_query_prefills_category(self):
        self._login_owner_via_magic()

        response = self.client.get("/owners/request-service?category=cleaning")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('body class="owner-portal-page owner-request-service-page"', html)
        self.assertIn('data-i18n="ownerRequestServicePreselected"', html)
        self.assertIn("Cleaning", html)

    def test_owner_pages_include_language_switcher_and_i18n_hooks(self):
        self._login_owner_via_magic()

        page_paths = [
            "/owners/register",
            "/owners/login",
            "/owners/property/new",
            "/owners/dashboard",
            "/owners/properties",
            "/owners/request-service",
        ]

        for path in page_paths:
            for lang in ("bg", "en", "fr", "ru"):
                response = self.client.get(f"{path}?lang={lang}")
                self.assertEqual(response.status_code, 200, msg=f"{path}?lang={lang}")
                html = response.get_data(as_text=True)
                self.assertIn('<a class="language-switcher__button', html, msg=path)
                for control_lang in ("bg", "en", "fr", "ru"):
                    self.assertIn(f'data-lang-switch="{control_lang}"', html, msg=path)
                    self.assertIn(f'href="{path}?lang={control_lang}"', html, msg=path)
                self.assertIn('data-i18n="', html, msg=path)
                self.assertIn('data-i18n-attr="', html, msg=path)
                self.assertNotIn('noindex', html.lower(), msg=path)
                self.assertNotIn('x-robots-tag', response.headers.get("X-Robots-Tag", "").lower(), msg=path)
                if path == "/owners/login":
                    self.assertIn('data-i18n="ownerLoginEmail"', html, msg=path)
                    self.assertIn('data-i18n="ownerLoginSendMagicLink"', html, msg=path)
                    self.assertIn('body class="owner-portal-page owner-login-page"', html, msg=path)
                elif path == "/owners/property/new":
                    self.assertIn('data-i18n="ownerPropertyNewFormTitle"', html, msg=path)
                    self.assertIn('body class="owner-portal-page owner-property-new-page owner-property-page"', html, msg=path)
                elif path == "/owners/dashboard":
                    self.assertIn('data-i18n="ownerDashboardPropertyOverview"', html, msg=path)
                    self.assertIn('body class="owner-portal-page owner-portal-dashboard-page owner-dashboard-page"', html, msg=path)
                elif path == "/owners/properties":
                    self.assertIn('data-i18n="ownerProfileDropdownProperties"', html, msg=path)
                    self.assertIn('body class="owner-properties-page"', html, msg=path)
                elif path == "/owners/request-service":
                    self.assertIn('data-i18n="ownerRequestServiceCategoryLabel"', html, msg=path)
                    self.assertIn('body class="owner-portal-page owner-request-service-page"', html, msg=path)

    def test_owner_gateway_page_is_public_and_language_aware(self):
        response = self.client.get("/owners?lang=en")
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn('<html lang="en">', html)
        self.assertIn('href="/owners/login?lang=en"', html)
        self.assertIn('href="/owners/register?lang=en"', html)
        self.assertIn('href="/owners/request-service?lang=en"', html)
        self.assertIn('data-i18n="ownerLandingSignInCta"', html)
        self.assertIn('data-i18n="ownerLandingCreateAccountCta"', html)
        self.assertIn('data-i18n="ownerLandingRequestServiceCta"', html)
        self.assertIn("Sign in", html)
        self.assertIn("Create account", html)
        self.assertIn("Request service", html)
        self.assertNotIn("404", html)

    def test_owner_gateway_preserves_selected_language(self):
        response = self.client.get("/owners?lang=fr")
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn('<html lang="fr">', html)
        self.assertIn('href="/owners/login?lang=fr"', html)
        self.assertIn('href="/owners/register?lang=fr"', html)
        self.assertIn('href="/owners/request-service?lang=fr"', html)
        self.assertNotIn("404", html)

    def test_owner_gateway_renders_supported_languages_without_mixed_copy(self):
        expectations = {
            "bg": {
                "eyebrow": "Портал за собственици",
                "title": "Едно място за имота ви.",
            },
            "en": {
                "eyebrow": "Owner portal",
                "title": "One place for your property.",
            },
            "fr": {
                "eyebrow": "Portail propriétaire",
                "title": "Un seul endroit pour votre bien.",
            },
            "ru": {
                "eyebrow": "Портал владельца",
                "title": "Одно место для вашего объекта.",
            },
        }

        for lang, expected in expectations.items():
            with self.subTest(lang=lang):
                response = self.client.get(f"/owners?lang={lang}")
                html = response.get_data(as_text=True)
                text_content = re.sub(r"<[^>]+>", " ", html)

                self.assertEqual(response.status_code, 200)
                self.assertIn(f'<html lang="{lang}">', html)
                self.assertIn(f'href="/owners/login?lang={lang}"', html)
                self.assertIn(f'href="/owners/register?lang={lang}"', html)
                self.assertIn(f'href="/owners/request-service?lang={lang}"', html)
                self.assertIn(expected["eyebrow"], html)
                self.assertIn(expected["title"], html)

                for other_lang, other_expected in expectations.items():
                    if other_lang == lang:
                        continue
                    self.assertNotIn(other_expected["eyebrow"], text_content)
                    self.assertNotIn(other_expected["title"], text_content)

    def test_logged_in_owner_is_redirected_from_gateway_to_dashboard(self):
        self._login_owner_via_magic(seed_property=False)

        response = self.client.get("/owners?lang=ru")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/owners/dashboard", response.headers["Location"])
        self.assertIn("lang=ru", response.headers["Location"])

    def test_owner_dashboard_translation_keys_remain_available(self):
        repo_root = Path(__file__).resolve().parents[1]
        files = {
            "owners-dashboard.js": [
                "ownerDashboardTitle",
                "ownerDashboardPropertyOverview",
                "ownerDashboardOperationsSnapshot",
                "ownerDashboardActivityTimeline",
                "ownerDashboardRequestCleaning",
            ],
            "owners.js": [
                "ownerStatusNew",
                "ownerTimelineCreated",
                "ownerMetricScheduled",
            ],
            "owners-request-service.js": [
                "ownerRequestIdLabel",
                "ownerRequestLastUpdateLabel",
            ],
        }

        for filename, keys in files.items():
            content = (repo_root / "static" / "js" / "i18n" / filename).read_text(encoding="utf-8")
            for key in keys:
                with self.subTest(filename=filename, key=key):
                    self.assertIn(key, content)

    def test_owner_login_rejects_unknown_email(self):
        response = self.client.post("/owners/login", data={"email": "missing@example.com"})

        self.assertEqual(response.status_code, 302)
        self.assertIn("/owners/login?magic_sent=1", response.headers["Location"])
        self.assertIn("delivery=generic", response.headers["Location"])
        self.assertIn("lang=bg", response.headers["Location"])

        page = self.client.get(response.headers["Location"])
        self.assertEqual(page.status_code, 200)
        html = page.get_data(as_text=True)
        self.assertIn("Ако имейлът е регистриран, ще получите защитен линк.", html)
        self.assertNotIn("ownerAccountNotFoundError", html)
        self.assertEqual(self._read_jsonl("owner_magic_tokens.jsonl"), [])

        events = self._read_jsonl("owner_magic_email_events.jsonl")
        self.assertEqual(len(events), 2)
        login_attempt = next(event for event in events if event["event"] == "owner_login_attempt")
        self.assertFalse(login_attempt["account_found"])
        self.assertEqual(login_attempt["delivery"], "generic")
        self.assertEqual(login_attempt["submitted_email"], "missing@example.com")
        self.assertEqual(login_attempt["reason"], "unknown_email")
        self.assertTrue(any(event["event"] == "unknown_email" for event in events))

    def test_owner_login_sends_magic_flow(self):
        self._seed_owner_account()
        with patch.dict(os.environ, self.SMTP_ENV, clear=True), patch("app.smtplib.SMTP", FakeSMTP), patch("app.smtplib.SMTP_SSL", FakeSMTP):
            response = self.client.post("/owners/login", data=self._demo_login_payload())

        self.assertEqual(response.status_code, 302)
        self.assertIn("/owners/login?magic_sent=1", response.headers["Location"])
        self.assertIn("delivery=sent", response.headers["Location"])
        self.assertIn(f"magic_recipient={_mask_email('owner@blackseaconnect.com')}", response.headers["Location"])
        self.assertIn("lang=bg", response.headers["Location"])

        page = self.client.get(response.headers["Location"])
        self.assertEqual(page.status_code, 200)
        html = page.get_data(as_text=True)
        self.assertIn(f"Изпратихме защитен линк до {_mask_email('owner@blackseaconnect.com')}. Проверете входящата поща и Spam.", html)

        tokens = self._read_jsonl("owner_magic_tokens.jsonl")
        self.assertEqual(len(tokens), 1)
        self.assertEqual(tokens[0]["email"], "owner@blackseaconnect.com")
        self.assertEqual(len(FakeSMTP.sent_messages), 1)

        events = self._read_jsonl("owner_magic_email_events.jsonl")
        self.assertEqual([event["event"] for event in events], ["token_created", "sent"])
        self.assertTrue(all(event["submitted_email"] == "owner@blackseaconnect.com" for event in events))

    def test_owner_login_smtp_failure_redirects_failed(self):
        self._seed_owner_account()

        with patch.dict(os.environ, self.SMTP_ENV, clear=True), patch("app.smtplib.SMTP", RejectingSMTP), patch("app.smtplib.SMTP_SSL", RejectingSMTP):
            response = self.client.post("/owners/login", data=self._demo_login_payload())

        self.assertEqual(response.status_code, 302)
        self.assertIn("/owners/login?magic_sent=0", response.headers["Location"])
        self.assertIn("delivery=failed", response.headers["Location"])
        self.assertIn("lang=bg", response.headers["Location"])

        page = self.client.get(response.headers["Location"])
        self.assertEqual(page.status_code, 200)
        self.assertIn("Не успяхме да изпратим линка. Моля, опитайте отново след малко.", page.get_data(as_text=True))

        self.assertEqual(self._read_jsonl("owner_magic_tokens.jsonl"), [])
        events = self._read_jsonl("owner_magic_email_events.jsonl")
        self.assertEqual([event["event"] for event in events], ["token_created", "failed", "owner_login_attempt"])
        self.assertTrue(all(event["reason"] == "smtp_send_failed" for event in events if event["event"] == "failed"))
        self.assertTrue(events[-1]["account_found"])
        self.assertEqual(events[-1]["delivery"], "failed")
        self.assertEqual(events[-1]["submitted_email"], "owner@blackseaconnect.com")

    def test_owner_registration_smtp_failure_redirects_failed(self):
        with patch.dict(os.environ, self.SMTP_ENV, clear=True), patch("app.smtplib.SMTP", RejectingSMTP), patch("app.smtplib.SMTP_SSL", RejectingSMTP):
            response = self.client.post("/owners/register", data=self._owner_payload())

        self.assertEqual(response.status_code, 302)
        self.assertIn("/owners/login?registered=1&magic_sent=0", response.headers["Location"])
        self.assertIn("delivery=failed", response.headers["Location"])
        self.assertIn("lang=bg", response.headers["Location"])

        page = self.client.get(response.headers["Location"])
        self.assertEqual(page.status_code, 200)
        self.assertIn("Профилът е създаден, но имейлът не беше изпратен. Моля, опитайте вход отново или се свържете с нас.", page.get_data(as_text=True))

        accounts = self._read_jsonl("owner_accounts.jsonl")
        self.assertEqual(len(accounts), 1)
        self.assertEqual(accounts[0]["email"], "owner@example.com")
        self.assertEqual(self._read_jsonl("owner_magic_tokens.jsonl"), [])
        events = self._read_jsonl("owner_magic_email_events.jsonl")
        self.assertEqual([event["event"] for event in events], ["owner_registration_notification_failed", "token_created", "failed"])
        self.assertTrue(all(event["submitted_email"] == "owner@example.com" for event in events))
        self.assertTrue(all(event["account_found"] is None for event in events))

    def test_owner_registration_notification_failure_does_not_block_magic_link(self):
        smtp_env = {**self.SMTP_ENV, "ADMIN_NOTIFICATION_EMAIL": "ops@example.com"}
        with patch.dict(os.environ, smtp_env, clear=True), patch("app._send_owner_registration_notification_email", return_value={"ok": False, "reason": "smtp_send_failed"}), patch("app.smtplib.SMTP", FakeSMTP), patch("app.smtplib.SMTP_SSL", FakeSMTP):
            response = self.client.post("/owners/register", data=self._owner_payload())

        self.assertEqual(response.status_code, 302)
        self.assertIn("/owners/login?registered=1&magic_sent=1", response.headers["Location"])
        self.assertIn("delivery=sent", response.headers["Location"])
        self.assertEqual(len(FakeSMTP.sent_messages), 2)
        self.assertTrue(any(message["Subject"] == "BlackSea Connect — Вход в портала за собственици" for message in FakeSMTP.sent_messages))
        self.assertTrue(any(message["Subject"] == "[BlackSeaConnect] Operations task notification" for message in FakeSMTP.sent_messages))

    def test_owner_registration_validation_errors_do_not_send_admin_notification(self):
        with patch.dict(os.environ, self.SMTP_ENV, clear=True), patch("app._send_owner_registration_notification_email") as notify_mock, patch("app.smtplib.SMTP", FakeSMTP), patch("app.smtplib.SMTP_SSL", FakeSMTP):
            response = self.client.post(
                "/owners/register",
                data={
                    "full_name": "",
                    "email": "owner@example.com",
                    "phone": "",
                    "property_type": "",
                    "city": "",
                    "property_name": "",
                    "number_of_units": "",
                    "notes": "",
                },
            )

        self.assertEqual(response.status_code, 400)
        notify_mock.assert_not_called()
        self.assertEqual(FakeSMTP.sent_messages, [])

    def test_admin_owner_accounts_page_shows_loaded_accounts(self):
        self._seed_owner_account(email="stoyanova@orange.fr")

        with patch.dict(os.environ, {**self.ADMIN_ENV, **self.SMTP_ENV}, clear=True):
            response = self.client.get("/admin/owner-accounts", headers=self._auth_headers())

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("CRM на собственици", html)
        self.assertIn("<strong>1</strong> показани", html)
        self.assertIn("stoyanova@orange.fr", html)
        self.assertIn("2026-06-15T10:00:00Z", html)
        self.assertIn("Отвори профила", html)
        self.assertIn("PILOT", html)
        self.assertIn("BG", html)

    def test_admin_seed_owner_creates_account_and_enables_login_delivery_sent(self):
        with patch.dict(os.environ, {**self.ADMIN_ENV, **self.SMTP_ENV}, clear=True), patch("app._send_owner_registration_notification_email") as notify_mock:
            seed_response = self.client.post("/admin/seed-owner", headers=self._auth_headers())

        self.assertEqual(seed_response.status_code, 302)
        self.assertIn("/admin/owner-accounts?seeded=1", seed_response.headers["Location"])
        notify_mock.assert_not_called()

        with patch.dict(os.environ, {**self.ADMIN_ENV, **self.SMTP_ENV}, clear=True):
            accounts_response = self.client.get(seed_response.headers["Location"], headers=self._auth_headers())

        self.assertEqual(accounts_response.status_code, 200)
        html = accounts_response.get_data(as_text=True)
        self.assertIn("CRM на собственици", html)
        self.assertIn("<strong>1</strong> показани", html)
        self.assertIn("stoyanova@orange.fr", html)
        self.assertIn("Акаунтът на собственика е създаден успешно.", html)

        with patch.dict(os.environ, self.SMTP_ENV, clear=True), patch("app.smtplib.SMTP", FakeSMTP), patch("app.smtplib.SMTP_SSL", FakeSMTP):
            login_response = self.client.post("/owners/login", data={"email": "stoyanova@orange.fr"})

        self.assertEqual(login_response.status_code, 302)
        self.assertIn("delivery=sent", login_response.headers["Location"])
        self.assertIn("magic_recipient=", login_response.headers["Location"])
        self.assertIn("lang=bg", login_response.headers["Location"])
        self.assertEqual(self._read_jsonl("owner_accounts.jsonl")[0]["phone"], "+35987927767")
        self.assertEqual(self._read_jsonl("owner_accounts.jsonl")[0]["property_name"], "Stella Appart")
        self.assertEqual(self._read_jsonl("owner_accounts.jsonl")[0]["city"], "Sveti Vlas")
        self.assertEqual(self._read_jsonl("owner_accounts.jsonl")[0]["property_type"], "Apartment")
        self.assertEqual(self._read_jsonl("owner_accounts.jsonl")[0]["number_of_units"], 1)

    def test_admin_seed_owner_is_idempotent(self):
        with patch.dict(os.environ, {**self.ADMIN_ENV, **self.SMTP_ENV}, clear=True):
            first = self.client.post("/admin/seed-owner", headers=self._auth_headers())
            second = self.client.post("/admin/seed-owner", headers=self._auth_headers())

        self.assertEqual(first.status_code, 302)
        self.assertEqual(second.status_code, 302)

        with patch.dict(os.environ, {**self.ADMIN_ENV, **self.SMTP_ENV}, clear=True):
            response = self.client.get("/admin/owner-accounts", headers=self._auth_headers())

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("<strong>1</strong> показани", html)
        self.assertIn("stoyanova@orange.fr", html)

    def test_admin_owner_accounts_support_search_and_filters(self):
        self._seed_jsonl("owner_accounts.jsonl", [
            {
                "id": "owner-a",
                "created_at": "2026-06-10T10:00:00Z",
                "full_name": "Elena Petrova",
                "email": "elena@example.com",
                "phone": "+359888111222",
                "property_type": "Villa",
                "city": "Varna",
                "property_name": "Sea View Villa",
                "number_of_units": 2,
                "notes": "",
                "status": "ACTIVE",
                "language": "en",
                "last_login_at": "2026-06-20T09:15:00Z",
                "internal_notes": "",
            },
            {
                "id": "owner-b",
                "created_at": "2026-06-11T10:00:00Z",
                "full_name": "Maya Ivanova",
                "email": "maya@example.com",
                "phone": "+359888333444",
                "property_type": "Apartment",
                "city": "Burgas",
                "property_name": "Harbor Apartment",
                "number_of_units": 1,
                "notes": "",
                "status": "INACTIVE",
                "language": "bg",
                "last_login_at": "",
                "internal_notes": "",
            },
        ])

        with patch.dict(os.environ, {**self.ADMIN_ENV, **self.SMTP_ENV}, clear=True):
            response = self.client.get("/admin/owner-accounts?q=Varna&status=active&language=en", headers=self._auth_headers())

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("<strong>1</strong> показани", html)
        self.assertIn('data-testid="owner-total-count"><strong>2</strong>', html)
        self.assertIn("elena@example.com", html)
        self.assertNotIn("maya@example.com", html)

    def test_admin_owner_account_detail_shows_timeline_and_persists_notes_and_status(self):
        self._seed_owner_account(email="owner@example.com")
        self._seed_owner_property(owner_id="owner-1", owner_email="owner@example.com", name="Sea View Villa", location="Varna")
        self._seed_jsonl("service_requests.jsonl", [self._demo_owner_request(owner_id="owner-1", owner_email="owner@example.com")])

        with patch.dict(os.environ, self.SMTP_ENV, clear=True), patch("app.smtplib.SMTP", FakeSMTP), patch("app.smtplib.SMTP_SSL", FakeSMTP):
            self.client.post("/owners/login", data={"email": "owner@example.com"})

        token = self._read_jsonl("owner_magic_tokens.jsonl")[-1]["token"]
        self.client.get(f"/auth/owner-magic/{token}")

        with patch.dict(os.environ, {**self.ADMIN_ENV, **self.SMTP_ENV}, clear=True):
            response = self.client.get("/admin/owner-accounts/owner-1", headers=self._auth_headers())

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Owner profile", html)
        self.assertIn("Magic link sent", html)
        self.assertIn("Magic link login", html)
        self.assertIn("Property added", html)
        self.assertIn("Service request submitted", html)
        self.assertIn("Sea View Villa", html)
        self.assertIn("Account activity summary", html)

        with patch.dict(os.environ, {**self.ADMIN_ENV, **self.SMTP_ENV}, clear=True):
            update_response = self.client.post(
                "/admin/owner-accounts/owner-1",
                data={
                    "status": "active",
                    "internal_notes": "Prefers SMS follow-up.",
                },
                headers=self._auth_headers(),
            )

        self.assertEqual(update_response.status_code, 302)
        self.assertIn("/admin/owner-accounts/owner-1", update_response.headers["Location"])

        account_row = self._read_owner_db_rows("owner_accounts")[0]
        self.assertEqual(account_row["status"], "ACTIVE")
        self.assertEqual(account_row["internal_notes"], "Prefers SMS follow-up.")
        self.assertTrue(account_row["last_login_at"])

        activity_rows = self._read_owner_db_rows("owner_activity_events")
        self.assertTrue(any(row["event_type"] == "status_changed" for row in activity_rows))
        self.assertTrue(any(row["event_type"] == "note_added" for row in activity_rows))

    def test_admin_property_operations_list_and_detail_persist_notes_and_timeline(self):
        self._seed_owner_account(email="owner@example.com")
        self._seed_owner_property(owner_id="owner-1", owner_email="owner@example.com", name="Sea View Villa", location="Varna")

        with patch.dict(os.environ, self.SMTP_ENV, clear=True), patch("app.smtplib.SMTP", FakeSMTP), patch("app.smtplib.SMTP_SSL", FakeSMTP):
            self.client.post("/owners/login", data={"email": "owner@example.com"})

        token = self._read_jsonl("owner_magic_tokens.jsonl")[-1]["token"]
        self.client.get(f"/auth/owner-magic/{token}")

        with patch.dict(os.environ, self.SMTP_ENV, clear=True), patch("app.Thread", ImmediateThread), patch("app.smtplib.SMTP", FakeSMTP), patch("app.smtplib.SMTP_SSL", FakeSMTP):
            request_response = self.client.post(
                "/owners/request-service",
                data={**self._service_request_payload(), "property_id": "property-1"},
            )

        self.assertEqual(request_response.status_code, 302)
        request_record = self._read_jsonl("service_requests.jsonl")[0]
        self.assertEqual(request_record["property_id"], "property-1")

        with patch.dict(os.environ, {**self.ADMIN_ENV, **self.SMTP_ENV}, clear=True):
            cockpit = self.client.get("/admin", headers=self._auth_headers())

        self.assertEqual(cockpit.status_code, 200)
        cockpit_html = cockpit.get_data(as_text=True)
        self.assertIn('href="/admin/properties"', cockpit_html)
        self.assertRegex(cockpit_html, r"<span>Total Properties</span>\s*<strong>1</strong>")

        with patch.dict(os.environ, {**self.ADMIN_ENV, **self.SMTP_ENV}, clear=True):
            listing = self.client.get("/admin/properties?q=Sea+View&status=setup&property_type=Villa", headers=self._auth_headers())

        self.assertEqual(listing.status_code, 200)
        listing_html = listing.get_data(as_text=True)
        self.assertIn("Property Operations", listing_html)
        self.assertIn("Sea View Villa", listing_html)
        self.assertIn("owner@example.com", listing_html)
        self.assertIn("Setup", listing_html)
        self.assertRegex(listing_html, r"<strong>1</strong> показани")

        with patch.dict(os.environ, {**self.ADMIN_ENV, **self.SMTP_ENV}, clear=True):
            detail = self.client.get("/admin/properties/property-1", headers=self._auth_headers())

        self.assertEqual(detail.status_code, 200)
        detail_html = detail.get_data(as_text=True)
        self.assertIn("ПРОФИЛ НА ИМОТА", detail_html)
        self.assertIn('data-testid="property-owner-information"', detail_html)
        self.assertIn("Readiness Checklist", detail_html)
        self.assertIn("Service Request History", detail_html)
        self.assertIn("Internal Notes", detail_html)
        self.assertIn('data-testid="property-timeline"', detail_html)
        self.assertIn("Property created", detail_html)
        self.assertIn("Owner assigned", detail_html)
        self.assertIn("Service request submitted", detail_html)

        with patch.dict(os.environ, {**self.ADMIN_ENV, **self.SMTP_ENV}, clear=True):
            note_response = self.client.post(
                "/admin/properties/property-1",
                data={"admin_notes": "Keep an eye on the guest guide."},
                headers=self._auth_headers(),
            )

        self.assertEqual(note_response.status_code, 302)
        self.assertIn("/admin/properties/property-1", note_response.headers["Location"])
        self.assertEqual(self._read_owner_db_rows("owner_properties")[0]["admin_notes"], "Keep an eye on the guest guide.")
        self.assertTrue(any(row["event_type"] == "note_added" for row in self._read_owner_db_rows("owner_property_activity_events")))

        request_id = request_record["id"]
        with patch.dict(os.environ, {**self.ADMIN_ENV, **self.SMTP_ENV}, clear=True), patch("app.Thread", ImmediateThread), patch("app.smtplib.SMTP", FakeSMTP), patch("app.smtplib.SMTP_SSL", FakeSMTP):
            completed_response = self.client.post(
                f"/admin/service-requests/{request_id}/update",
                data={"status": "completed", "internal_notes": "Wrapped up."},
                headers=self._auth_headers(),
            )

        self.assertEqual(completed_response.status_code, 302)
        self.assertIn("service_request_completed", {row["event_type"] for row in self._read_owner_db_rows("owner_property_activity_events")})

        with patch.dict(os.environ, {**self.ADMIN_ENV, **self.SMTP_ENV}, clear=True):
            refreshed_detail = self.client.get("/admin/properties/property-1", headers=self._auth_headers())

        refreshed_html = refreshed_detail.get_data(as_text=True)
        self.assertIn("Keep an eye on the guest guide.", refreshed_html)
        self.assertIn("Service request completed", refreshed_html)

    def test_admin_operation_create_get_has_utf8_labels_and_navigation(self):
        self._seed_owner_property(name="Морска вила", location="Варна")

        with patch.dict(os.environ, self.ADMIN_ENV, clear=True):
            response = self.client.get("/admin/operations/new", headers=self._auth_headers())
            operator_response = self.client.get("/admin/operator", headers=self._auth_headers())
            english_response = self.client.get("/admin/operations/new?lang=en", headers=self._auth_headers())
            french_bundle = self.client.get("/static/js/i18n/admin-runtime.js")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html; charset=utf-8", response.headers["Content-Type"])
        html = response.get_data(as_text=True)
        self.assertNotIn("????", html)
        self.assertNotIn("\ufffd", html)
        for label in (
            "Имот *",
            "Тип операция *",
            "Заглавие *",
            "Приоритет",
            "Краен срок",
            "Професионалист",
            "Описание / бележки",
            "Почистване",
            "Поддръжка",
            "Проверка",
            "Настаняване",
            "Напускане",
            "Ремонт",
            "Друга",
            "Нисък",
            "Нормален",
            "Висок",
            "Критичен",
            "Създай операция",
            "Отказ",
        ):
            self.assertIn(label, html)
        for value in ("CLEANING", "MAINTENANCE", "INSPECTION", "CHECK_IN", "CHECK_OUT", "REPAIR", "OTHER"):
            self.assertIn(f'value="{value}"', html)
        for value in ("LOW", "NORMAL", "HIGH", "URGENT"):
            self.assertIn(f'value="{value}"', html)
        self.assertIn('href="/admin/operations"', html)
        self.assertIn('href="/admin/operations/new"', html)
        self.assertIn('href="/admin/operations/new"', operator_response.get_data(as_text=True))
        self.assertIn('<html lang="en">', english_response.get_data(as_text=True))

        bundle = french_bundle.get_data(as_text=True)
        self.assertIn('"Create operation · BlackSea Connect"', bundle)
        self.assertIn('"Créer une opération · BlackSea Connect"', bundle)
        self.assertIn('"Repair", "Réparation"', bundle)
        self.assertNotIn("????", bundle)

    def test_admin_operation_create_post_uses_canonical_task_and_detail_route(self):
        self._seed_owner_property(owner_id="owner-1", owner_email="owner@example.com", name="Sea View Villa", location="Varna")
        self._insert_owner_db_rows("professional_accounts", [{
            "id": "professional-1",
            "email": "mira@example.com",
            "created_at": "2026-07-18T08:00:00Z",
            "full_name": "Mira Ivanova",
            "company": "Black Sea Care",
            "status": "APPROVED",
        }])

        with patch.dict(os.environ, self.ADMIN_ENV, clear=True):
            get_response = self.client.get("/admin/operations/new", headers=self._auth_headers())
            self.assertEqual(get_response.status_code, 200)
            with self.client.session_transaction() as session_data:
                csrf_token = session_data["_admin_csrf_token"]
            response = self.client.post(
                "/admin/operations/new",
                data={
                    "csrf_token": csrf_token,
                    "property_id": "property-1",
                    "category": "CLEANING",
                    "title": "Почистване преди пристигане",
                    "priority": "URGENT",
                    "due_date": "2026-07-20T10:30",
                    "assigned_professional_id": "professional-1",
                    "notes": "Проверете инструкциите за достъп.",
                },
                headers=self._auth_headers(),
            )

        self.assertEqual(response.status_code, 302)
        self.assertRegex(response.headers["Location"], r"/admin/operations/[0-9a-f]{32}$")
        tasks = self._read_owner_db_rows("operations_tasks")
        created_tasks = [row for row in tasks if row["source_type"] == "ADMIN_OPERATION"]
        self.assertEqual(len(created_tasks), 1)
        task = created_tasks[0]
        self.assertEqual(task["source_id"], task["id"])
        self.assertEqual(task["request_id"], task["id"])
        self.assertEqual(task["property_id"], "property-1")
        self.assertEqual(task["category"], "CLEANING")
        self.assertEqual(task["priority"], "URGENT")
        self.assertEqual(task["assigned_professional_id"], "professional-1")
        self.assertEqual(task["assigned_to"], "Mira Ivanova / Black Sea Care")
        self.assertEqual(task["status"], "ASSIGNED")
        self.assertEqual(task["notes"], "Проверете инструкциите за достъп.")

        with patch.dict(os.environ, self.ADMIN_ENV, clear=True):
            detail_response = self.client.get(response.headers["Location"], headers=self._auth_headers())
        self.assertEqual(detail_response.status_code, 200)
        self.assertIn("Проверете инструкциите за достъп.", detail_response.get_data(as_text=True))

    def test_admin_operation_create_rejects_invalid_form_values(self):
        self._seed_owner_property(name="Sea View Villa", location="Varna")

        with patch.dict(os.environ, self.ADMIN_ENV, clear=True):
            self.client.get("/admin/operations/new", headers=self._auth_headers())
            with self.client.session_transaction() as session_data:
                csrf_token = session_data["_admin_csrf_token"]

            valid_payload = {
                "csrf_token": csrf_token,
                "property_id": "property-1",
                "category": "REPAIR",
                "title": "Repair balcony door",
                "priority": "HIGH",
                "due_date": "2026-07-21T09:00",
                "assigned_professional_id": "",
                "notes": "",
            }
            invalid_cases = (
                ({"title": ""}, "Въведете заглавие."),
                ({"property_id": "missing-property"}, "Изберете валиден имот."),
                ({"category": "UNSUPPORTED"}, "Изберете валиден тип операция."),
                ({"priority": "EMERGENCY"}, "Изберете валиден приоритет."),
                ({"due_date": "not-a-date"}, "Въведете валиден краен срок."),
                ({"assigned_professional_id": "missing-professional"}, "Изберете валиден професионалист."),
            )

            for overrides, expected_error in invalid_cases:
                with self.subTest(overrides=overrides):
                    response = self.client.post(
                        "/admin/operations/new",
                        data={**valid_payload, **overrides},
                        headers=self._auth_headers(),
                    )
                    self.assertEqual(response.status_code, 400)
                    html = response.get_data(as_text=True)
                    self.assertIn(expected_error, html)
                    self.assertNotIn("????", html)

        self.assertEqual(self._read_owner_db_rows("operations_tasks"), [])

    def test_admin_operations_board_updates_sqlite_and_syncs_service_requests(self):
        self._seed_owner_account(email="owner@example.com")
        self._seed_owner_property(owner_id="owner-1", owner_email="owner@example.com", name="Sea View Villa", location="Varna")

        with patch.dict(os.environ, self.SMTP_ENV, clear=True), patch("app.smtplib.SMTP", FakeSMTP), patch("app.smtplib.SMTP_SSL", FakeSMTP):
            self.client.post("/owners/login", data={"email": "owner@example.com"})

        token = self._read_jsonl("owner_magic_tokens.jsonl")[-1]["token"]
        self.client.get(f"/auth/owner-magic/{token}")

        with patch.dict(os.environ, self.SMTP_ENV, clear=True), patch("app.Thread", ImmediateThread), patch("app.smtplib.SMTP", FakeSMTP), patch("app.smtplib.SMTP_SSL", FakeSMTP):
            request_response = self.client.post(
                "/owners/request-service",
                data={**self._service_request_payload(), "property_id": "property-1"},
            )

        self.assertEqual(request_response.status_code, 302)
        request_record = self._read_jsonl("service_requests.jsonl")[0]
        request_id = request_record["id"]

        with patch.dict(os.environ, {**self.ADMIN_ENV, **self.SMTP_ENV}, clear=True):
            cockpit = self.client.get("/admin", headers=self._auth_headers())
            board_link = cockpit.get_data(as_text=True)
            self.assertIn('href="/admin/operations"', board_link)
            board = self.client.get(
                "/admin/operations",
                query_string={
                    "q": "Sea View",
                    "property": "Sea View Villa",
                    "owner": "Elena Petrova",
                    "category": "SERVICE",
                    "status": "NEW",
                },
                headers=self._auth_headers(),
            )

        self.assertEqual(board.status_code, 200)
        board_html = board.get_data(as_text=True)
        self.assertIn("Operations Board", board_html)
        self.assertIn("Open Tasks", board_html)
        self.assertIn("Sea View Villa", board_html)
        self.assertIn("Elena Petrova", board_html)
        self.assertIn("SERVICE", board_html)
        self.assertIn("Priority", board_html)
        self.assertIn('draggable="true"', board_html)

        task_rows = self._read_owner_db_rows("operations_tasks")
        service_task_rows = [row for row in task_rows if row["source_type"] == "OWNER_SERVICE_REQUEST"]
        self.assertEqual(len(task_rows), 2)
        self.assertEqual(len(service_task_rows), 1)
        self.assertEqual(service_task_rows[0]["status"], "NEW")
        self.assertEqual(service_task_rows[0]["priority"], "HIGH")

        with patch.dict(os.environ, {**self.ADMIN_ENV, **self.SMTP_ENV}, clear=True):
            detail_update = self.client.post(
                f"/admin/operations/{request_id}",
                data={
                    "status": "ASSIGNED",
                    "assigned_to": "Mira Ivanova",
                    "priority": "HIGH",
                    "due_date": "2026-07-20",
                    "admin_notes": "Follow up with housekeeping.",
                },
                headers=self._auth_headers(),
            )

        self.assertEqual(detail_update.status_code, 302)
        task_rows = self._read_owner_db_rows("operations_tasks")
        service_task_rows = [row for row in task_rows if row["source_type"] == "OWNER_SERVICE_REQUEST"]
        self.assertEqual(service_task_rows[0]["status"], "ASSIGNED")
        self.assertEqual(service_task_rows[0]["assigned_to"], "Mira Ivanova")
        self.assertEqual(service_task_rows[0]["priority"], "HIGH")
        self.assertEqual(service_task_rows[0]["due_date"], "2026-07-20")
        task_events = self._read_owner_db_rows("operations_task_events")
        self.assertEqual(sum(row["event_type"] == "assigned" for row in task_events), 1)
        self.assertFalse(any(row["event_type"] == "status_changed" for row in task_events))
        self.assertTrue(any(row["event_type"] == "note_added" for row in task_events))

        with patch.dict(os.environ, {**self.ADMIN_ENV, **self.SMTP_ENV}, clear=True):
            board_after_assignment = self.client.get("/admin/operations", headers=self._auth_headers())

        self.assertEqual(board_after_assignment.status_code, 200)
        assignment_board_html = board_after_assignment.get_data(as_text=True)
        self.assertRegex(assignment_board_html, r"Assigned Tasks</span>\s*<strong>1</strong>")
        self.assertRegex(assignment_board_html, r"Open Tasks</span>\s*<strong>2</strong>")
        self.assertRegex(assignment_board_html, r"Completed Tasks</span>\s*<strong>0</strong>")

        with patch.dict(os.environ, {**self.ADMIN_ENV, **self.SMTP_ENV}, clear=True):
            in_progress_response = self.client.post(
                f"/admin/operations/{request_id}/status",
                json={"status": "IN_PROGRESS"},
                headers=self._auth_headers(),
            )

        self.assertEqual(in_progress_response.status_code, 200)
        self.assertEqual(in_progress_response.get_json()["task"]["status"], "IN_PROGRESS")
        task_rows = self._read_owner_db_rows("operations_tasks")
        service_task_rows = [row for row in task_rows if row["source_type"] == "OWNER_SERVICE_REQUEST"]
        self.assertEqual(service_task_rows[0]["status"], "IN_PROGRESS")
        self.assertEqual(self._read_jsonl("service_requests.jsonl")[0]["status"], "in_progress")
        self.assertTrue(any(row["event_type"] == "status_changed" for row in self._read_owner_db_rows("operations_task_events")))

        with patch.dict(os.environ, {**self.ADMIN_ENV, **self.SMTP_ENV}, clear=True), patch("app.Thread", ImmediateThread), patch("app.smtplib.SMTP", FakeSMTP), patch("app.smtplib.SMTP_SSL", FakeSMTP):
            completed_response = self.client.post(
                f"/admin/operations/{request_id}/status",
                json={"status": "DONE"},
                headers=self._auth_headers(),
            )

        self.assertEqual(completed_response.status_code, 200)
        self.assertIn(completed_response.get_json()["task"]["status"], {"DONE", "COMPLETED"})
        task_rows = self._read_owner_db_rows("operations_tasks")
        service_task_rows = [row for row in task_rows if row["source_type"] == "OWNER_SERVICE_REQUEST"]
        self.assertIn(service_task_rows[0]["status"], {"DONE", "COMPLETED"})
        self.assertEqual(self._read_jsonl("service_requests.jsonl")[0]["status"], "completed")
        self.assertTrue(any(row["event_type"] == "completed" for row in self._read_owner_db_rows("operations_task_events")))
        self.assertTrue(any(row.get("completed_at") for row in service_task_rows))

        with patch.dict(os.environ, {**self.ADMIN_ENV, **self.SMTP_ENV}, clear=True):
            comment_response = self.client.post(
                f"/admin/operations/{request_id}",
                data={
                    "task_action": "comment",
                    "comment_type": "Urgent",
                    "comment": "Owner needs a quick closeout call.",
                },
                headers=self._auth_headers(),
            )

        self.assertEqual(comment_response.status_code, 302)

        with patch.dict(os.environ, {**self.ADMIN_ENV, **self.SMTP_ENV}, clear=True):
            refreshed = self.client.get(f"/admin/operations/{request_id}", headers=self._auth_headers())

        refreshed_html = refreshed.get_data(as_text=True)
        self.assertIn("Mira Ivanova", refreshed_html)
        self.assertIn("Follow up with housekeeping.", refreshed_html)
        self.assertIn("Completed", refreshed_html)
        self.assertIn("Task activity", refreshed_html)
        self.assertIn('class="admin-operations-sticky-bar"', refreshed_html)
        self.assertIn("Open Calendar", refreshed_html)
        self.assertIn("Notify Owner", refreshed_html)
        self.assertIn("Notify Professional", refreshed_html)
        self.assertIn("Owner -> Operations -> Professional -> Completed", refreshed_html)
        self.assertIn("Operational deadline", refreshed_html)
        self.assertIn("Time remaining", refreshed_html)
        self.assertIn("Assigned professional", refreshed_html)
        self.assertIn("Owner and property", refreshed_html)
        self.assertRegex(refreshed_html, r"Checklist:\s*\d+\s*/\s*\d+\s*completed")
        self.assertIn("admin-operations-timeline-rail", refreshed_html)
        self.assertIn("Professional closeout", refreshed_html)
        self.assertIn("Urgent", refreshed_html)

        with patch.dict(os.environ, {**self.ADMIN_ENV, **self.SMTP_ENV}, clear=True):
            completed_board = self.client.get("/admin/operations", headers=self._auth_headers())

        completed_board_html = completed_board.get_data(as_text=True)
        self.assertRegex(completed_board_html, r"Open Tasks</span>\s*<strong>1</strong>")
        self.assertRegex(completed_board_html, r"Assigned Tasks</span>\s*<strong>1</strong>")
        self.assertRegex(completed_board_html, r"Completed Tasks</span>\s*<strong>1</strong>")

    def test_admin_owner_finance_payment_and_payout_persist_with_valid_forms(self):
        class FormAuditParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.form_stack = []
                self.forms = []
                self.has_nested_form = False

            def handle_starttag(self, tag, attrs):
                attributes = dict(attrs)
                if tag == "form":
                    self.has_nested_form = self.has_nested_form or bool(self.form_stack)
                    form = {"attributes": attributes, "fields": {}}
                    self.form_stack.append(form)
                    self.forms.append(form)
                elif tag == "input" and self.form_stack and attributes.get("name"):
                    self.form_stack[-1]["fields"][attributes["name"]] = attributes.get("value", "")

            def handle_endtag(self, tag):
                if tag == "form" and self.form_stack:
                    self.form_stack.pop()

        task_id = "owner-finance-demo-92d261da3feb"
        admin_env = {**self.ADMIN_ENV, **self.SMTP_ENV}

        with patch.dict(os.environ, admin_env, clear=True):
            app_module._upsert_operations_task_from_source(
                {
                    "id": task_id,
                    "request_id": task_id,
                    "source_type": "OWNER_SERVICE_REQUEST",
                    "source_id": task_id,
                    "title": "Owner finance integration test",
                    "owner_name": "Finance Owner",
                    "owner_email": "finance-owner@example.com",
                    "status": "NEW",
                },
                force_create=True,
                notify=False,
            )
            with app_module._owner_db_connection() as conn:
                conn.execute(
                    """
                    UPDATE operations_tasks
                    SET professional_quote_amount = 100,
                        platform_fee_type = 'FIXED',
                        platform_fee_value = 20,
                        owner_total_amount = 120,
                        currency = 'EUR',
                        quote_status = 'APPROVED',
                        owner_approval_status = 'APPROVED',
                        payment_status = 'PENDING',
                        payout_status = 'NOT_READY',
                        quote_locked = 1
                    WHERE id = ?
                    """,
                    (task_id,),
                )

            with self.client.session_transaction() as session_data:
                session_data["_admin_csrf_token"] = "finance-csrf"

            initial = self.client.get(
                f"/admin/operations/{task_id}?lang=bg",
                headers=self._auth_headers(),
            )
            initial_html = initial.get_data(as_text=True)
            self.assertEqual(initial.status_code, 200)
            self.assertIn('id="owner-payment-confirm-form"', initial_html)
            self.assertIn('name="task_action" value="finance_payment"', initial_html)
            self.assertIn('name="csrf_token" value="finance-csrf"', initial_html)
            form_audit = FormAuditParser()
            form_audit.feed(initial_html)
            self.assertFalse(form_audit.has_nested_form)
            payment_forms = [
                form for form in form_audit.forms
                if form["attributes"].get("id") == "owner-payment-confirm-form"
            ]
            self.assertEqual(len(payment_forms), 1)
            self.assertEqual(
                payment_forms[0]["fields"],
                {"task_action": "finance_payment", "csrf_token": "finance-csrf"},
            )

            missing_csrf = self.client.post(
                f"/admin/operations/{task_id}",
                data={"task_action": "finance_payment"},
                headers=self._auth_headers(),
            )
            self.assertEqual(missing_csrf.status_code, 400)
            self.assertEqual(app_module._find_operations_task(task_id)["payment_status"], "PENDING")

            received_payloads = []
            payment_transition = app_module._transition_operations_task_payment

            def capture_payload(captured_task_id, action):
                received_payloads.append(app_module.request.form.to_dict(flat=False))
                return payment_transition(captured_task_id, action)

            with patch("app._transition_operations_task_payment", side_effect=capture_payload):
                payment = self.client.post(
                    f"/admin/operations/{task_id}",
                    data={"task_action": "finance_payment", "csrf_token": "finance-csrf"},
                    headers=self._auth_headers(),
                )

            self.assertEqual(
                received_payloads,
                [{"task_action": ["finance_payment"], "csrf_token": ["finance-csrf"]}],
            )
            self.assertEqual(payment.status_code, 302)
            self.assertIn("finance_notice=payment_recorded", payment.headers["Location"])
            self.assertTrue(payment.headers["Location"].endswith("#operations-finance"))

            funded = app_module._find_operations_task(task_id)
            self.assertEqual(funded["quote_status"], "FUNDED")
            self.assertEqual(funded["payment_status"], "PAID")
            self.assertEqual(funded["payout_status"], "READY")
            self.assertEqual(funded["payment_provider"], "MANUAL")
            self.assertTrue(funded["payment_reference"].startswith("MANUAL-"))
            self.assertTrue(funded["paid_at"])
            self.assertTrue(funded["quote_locked"])

            funded_refresh = self.client.get(
                f"/admin/operations/{task_id}?lang=bg",
                headers=self._auth_headers(),
            ).get_data(as_text=True)
            self.assertIn("Платено", funded_refresh)
            self.assertIn("Готово за изплащане", funded_refresh)
            self.assertIn("Освободи плащането към професионалиста", funded_refresh)
            funded_form_audit = FormAuditParser()
            funded_form_audit.feed(funded_refresh)
            self.assertFalse(funded_form_audit.has_nested_form)
            payout_forms = [
                form for form in funded_form_audit.forms
                if form["attributes"].get("id") == "professional-payout-release-form"
            ]
            self.assertEqual(len(payout_forms), 1)
            self.assertEqual(
                payout_forms[0]["fields"],
                {"task_action": "finance_release", "csrf_token": "finance-csrf"},
            )

            repeated_payment = self.client.post(
                f"/admin/operations/{task_id}",
                data={"task_action": "finance_payment", "csrf_token": "finance-csrf"},
                headers=self._auth_headers(),
            )
            self.assertIn("finance_notice=already_processed", repeated_payment.headers["Location"])

            payout = self.client.post(
                f"/admin/operations/{task_id}",
                data={"task_action": "finance_release", "csrf_token": "finance-csrf"},
                headers=self._auth_headers(),
            )
            self.assertEqual(payout.status_code, 302)
            self.assertIn("finance_notice=payout_released", payout.headers["Location"])
            self.assertTrue(payout.headers["Location"].endswith("#operations-finance"))

            paid_out = app_module._find_operations_task(task_id)
            self.assertEqual(paid_out["quote_status"], "PAID_OUT")
            self.assertEqual(paid_out["payment_status"], "PAID")
            self.assertEqual(paid_out["payout_status"], "PAID")
            self.assertTrue(paid_out["released_at"])

            repeated_payout = self.client.post(
                f"/admin/operations/{task_id}",
                data={"task_action": "finance_release", "csrf_token": "finance-csrf"},
                headers=self._auth_headers(),
            )
            self.assertIn("finance_notice=already_processed", repeated_payout.headers["Location"])

            final_refresh = self.client.get(
                f"/admin/operations/{task_id}?lang=bg",
                headers=self._auth_headers(),
            ).get_data(as_text=True)
            self.assertIn("Изплатено", final_refresh)
            self.assertIn("Финансовият цикъл е приключен успешно.", final_refresh)
            self.assertNotIn('id="owner-payment-confirm-form"', final_refresh)
            self.assertNotIn('id="professional-payout-release-form"', final_refresh)

            english_refresh = self.client.get(
                f"/admin/operations/{task_id}?lang=en",
                headers=self._auth_headers(),
            ).get_data(as_text=True)
            french_refresh = self.client.get(
                f"/admin/operations/{task_id}?lang=fr",
                headers=self._auth_headers(),
            ).get_data(as_text=True)
            self.assertIn("The financial cycle has been completed successfully.", english_refresh)
            self.assertIn("Le cycle financier s’est terminé avec succès.", french_refresh)

            events = [
                row["event_type"]
                for row in self._read_owner_db_rows("operations_task_events")
                if row["task_id"] == task_id
            ]
            self.assertEqual(events.count("finance_payment_recorded"), 1)
            self.assertEqual(events.count("finance_payout_released"), 1)

    def test_admin_executive_dashboard_computed_layers_surface_alerts_risk_workload_and_recommendations(self):
        self._seed_owner_account(email="owner@example.com")
        self._seed_owner_property(owner_id="owner-1", owner_email="owner@example.com", name="Sea View Villa", location="Varna")
        self._seed_jsonl("service_requests.jsonl", [self._demo_owner_request(
            id="owner-request-old",
            created_at="2026-06-22T08:00:00+00:00",
            last_update_at="2026-06-22T08:00:00+00:00",
            owner_id="owner-1",
            owner_email="owner@example.com",
            property="Sea View Villa",
            property_city="Varna",
            status="new",
        )])

        app_module._load_owner_properties()

        self._insert_owner_db_rows("professional_accounts", [{
            "email": "mira@example.com",
            "id": "pro-1",
            "created_at": "2026-06-20T09:00:00+00:00",
            "full_name": "Mira Ivanova",
            "phone": "+359888444555",
            "company": "Mira Cleaning",
            "service_categories": "Cleaning",
            "status": "ACTIVE",
            "last_login_at": "2026-06-24T09:00:00+00:00",
        }])

        task_rows = [
            {
                "id": "alert-overdue",
                "request_id": "alert-overdue",
                "source_type": "SERVICE_REQUEST",
                "source_id": "alert-overdue",
                "owner_id": "owner-1",
                "property_id": "property-1",
                "created_at": "2026-06-24T08:00:00+00:00",
                "updated_at": "2026-06-24T08:00:00+00:00",
                "title": "Overdue cleaning",
                "category": "CLEANING",
                "property_name": "Sea View Villa",
                "property_location": "Varna",
                "owner_name": "Elena Petrova",
                "owner_email": "owner@example.com",
                "assigned_to": "",
                "assigned_professional_id": "",
                "priority": "HIGH",
                "status": "NEW",
                "due_date": "2026-06-24",
                "notes": "Turnover is late.",
                "completed_at": "",
                "completion_report_json": "{}",
                "admin_notes": "",
                "request_status": "new",
                "checklist_json": "[]",
                "attachments_json": "[]",
                "comments_json": "[]",
            },
            {
                "id": "alert-nodue",
                "request_id": "alert-nodue",
                "source_type": "SERVICE_REQUEST",
                "source_id": "alert-nodue",
                "owner_id": "owner-1",
                "property_id": "property-1",
                "created_at": "2026-06-25T08:00:00+00:00",
                "updated_at": "2026-06-25T08:00:00+00:00",
                "title": "Inspection preparation",
                "category": "INSPECTION",
                "property_name": "Sea View Villa",
                "property_location": "Varna",
                "owner_name": "Elena Petrova",
                "owner_email": "owner@example.com",
                "assigned_to": "",
                "assigned_professional_id": "",
                "priority": "NORMAL",
                "status": "NEW",
                "due_date": "",
                "notes": "No due date set.",
                "completed_at": "",
                "completion_report_json": "{}",
                "admin_notes": "",
                "request_status": "new",
                "checklist_json": "[]",
                "attachments_json": "[]",
                "comments_json": "[]",
            },
        ]
        for index in range(6):
            timestamp = f"2026-06-25T0{index}:30:00+00:00"
            task_rows.append({
                "id": f"pro-task-{index + 1}",
                "request_id": f"pro-task-{index + 1}",
                "source_type": "SERVICE_REQUEST",
                "source_id": f"pro-task-{index + 1}",
                "owner_id": "owner-1",
                "property_id": "property-1",
                "created_at": timestamp,
                "updated_at": timestamp,
                "title": f"Assigned task {index + 1}",
                "category": "SERVICE",
                "property_name": "Sea View Villa",
                "property_location": "Varna",
                "owner_name": "Elena Petrova",
                "owner_email": "owner@example.com",
                "assigned_to": "Mira Ivanova",
                "assigned_professional_id": "pro-1",
                "priority": "NORMAL",
                "status": "ASSIGNED",
                "due_date": "2026-06-27",
                "notes": "Busy workload",
                "completed_at": "",
                "completion_report_json": "{}",
                "admin_notes": "",
                "request_status": "new",
                "checklist_json": "[]",
                "attachments_json": "[]",
                "comments_json": "[]",
            })
        self._insert_owner_db_rows("operations_tasks", task_rows)

        self._insert_owner_db_rows("reservations", [
            {
                "id": "res-1",
                "created_at": "2026-06-24T07:00:00+00:00",
                "updated_at": "2026-06-24T07:00:00+00:00",
                "property_id": "property-1",
                "reservation_source": "Manual",
                "reservation_reference": "R1",
                "channel_name": "Manual",
                "channel_status": "SYNCED",
                "last_sync": "2026-06-24T07:00:00+00:00",
                "external_payload": "{}",
                "external_reference": "R1",
                "external_last_sync": "2026-06-24T07:00:00+00:00",
                "import_batch_id": "",
                "sync_status": "IDLE",
                "source_metadata_json": "{}",
                "guest_first_name": "Anna",
                "guest_last_name": "Petrova",
                "guest_email": "anna@example.com",
                "guest_phone": "+359888100100",
                "adults": 2,
                "children": 0,
                "infants": 0,
                "pets": 0,
                "arrival_datetime": "2026-06-25T10:00:00+00:00",
                "departure_datetime": "2026-06-26T10:00:00+00:00",
                "status": "CONFIRMED",
                "notes": "",
                "language": "en",
                "created_by": "system",
                "metadata_json": "{\"timeline\":[],\"comments\":[]}",
            },
            {
                "id": "res-2",
                "created_at": "2026-06-24T08:00:00+00:00",
                "updated_at": "2026-06-24T08:00:00+00:00",
                "property_id": "property-1",
                "reservation_source": "Manual",
                "reservation_reference": "R2",
                "channel_name": "Manual",
                "channel_status": "SYNCED",
                "last_sync": "2026-06-24T08:00:00+00:00",
                "external_payload": "{}",
                "external_reference": "R2",
                "external_last_sync": "2026-06-24T08:00:00+00:00",
                "import_batch_id": "",
                "sync_status": "IDLE",
                "source_metadata_json": "{}",
                "guest_first_name": "Nina",
                "guest_last_name": "Koleva",
                "guest_email": "nina@example.com",
                "guest_phone": "+359888100101",
                "adults": 2,
                "children": 0,
                "infants": 0,
                "pets": 0,
                "arrival_datetime": "2026-06-25T18:00:00+00:00",
                "departure_datetime": "2026-06-27T10:00:00+00:00",
                "status": "CONFIRMED",
                "notes": "",
                "language": "en",
                "created_by": "system",
                "metadata_json": "{\"timeline\":[],\"comments\":[]}",
            },
        ])

        self._insert_owner_db_rows("calendar_events", [{
            "id": "calendar-conflict-1",
            "created_at": "2026-06-25T09:00:00+00:00",
            "updated_at": "2026-06-25T09:00:00+00:00",
            "property_id": "property-1",
            "owner_id": "owner-1",
            "operation_task_id": "",
            "event_type": "Inspection",
            "title": "Inspection block",
            "description": "Overlaps with arrival.",
            "start_datetime": "2026-06-25T12:00:00+00:00",
            "end_datetime": "2026-06-25T13:00:00+00:00",
            "all_day": 0,
            "status": "SCHEDULED",
            "assigned_professional": "",
            "created_by": "admin",
            "color": "blue",
            "metadata_json": "{}",
        }])

        with patch.dict(os.environ, {**self.ADMIN_ENV, **self.SMTP_ENV}, clear=True):
            response = self.client.get("/admin", headers=self._auth_headers())

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Изпълнителни сигнали", html)
        self.assertIn("Оперативен риск", html)
        self.assertIn("Единна хронология", html)
        self.assertIn("Разпределение на живото натоварване", html)
        self.assertIn("SLA наблюдение", html)
        self.assertIn("Умни препоръки", html)
        self.assertIn("Overdue Operations", html)
        self.assertIn("Properties Without Readiness", html)
        self.assertIn("Operations Without Due Dates", html)
        self.assertIn("Professionals Overloaded", html)
        self.assertIn("Assign cleaner to Sea View Villa", html)
        self.assertIn("Move operation to another team", html)
        self.assertIn("Sea View Villa", html)
        self.assertRegex(html, r"Risk\s*\d+/100")
        self.assertIn("Средно време за завършване", html)
        self.assertIn("Средно време за възлагане", html)
        self.assertIn("Средно време за отговор", html)
        self.assertIn("Mira Ivanova", html)
        self.assertIn("Varna", html)

    def test_admin_executive_timeline_orders_newest_first_and_sla_metrics_render(self):
        self._seed_owner_account(email="owner@example.com")
        self._seed_owner_property(owner_id="owner-1", owner_email="owner@example.com", name="Sea View Villa", location="Varna")
        app_module._load_owner_properties()

        self._insert_owner_db_rows("operations_tasks", [{
            "id": "sla-task-1",
            "request_id": "sla-task-1",
            "source_type": "SERVICE_REQUEST",
            "source_id": "sla-task-1",
            "owner_id": "owner-1",
            "property_id": "property-1",
            "created_at": "2026-06-24T08:00:00+00:00",
            "updated_at": "2026-06-24T10:00:00+00:00",
            "title": "SLA maintenance",
            "category": "SERVICE",
            "property_name": "Sea View Villa",
            "property_location": "Varna",
            "owner_name": "Elena Petrova",
            "owner_email": "owner@example.com",
            "assigned_to": "Mira Ivanova",
            "assigned_professional_id": "pro-2",
            "priority": "NORMAL",
            "status": "COMPLETED",
            "due_date": "2026-06-24",
            "notes": "SLA test task",
            "completed_at": "2026-06-24T10:00:00+00:00",
            "completion_report_json": "{}",
            "admin_notes": "",
            "request_status": "completed",
            "checklist_json": "[]",
            "attachments_json": "[]",
            "comments_json": "[]",
        }])
        self._insert_owner_db_rows("operations_task_events", [
            {
                "id": "sla-task-1-event-1",
                "task_id": "sla-task-1",
                "created_at": "2026-06-24T07:50:00+00:00",
                "event_type": "note_added",
                "title": "Older event",
                "detail": "older",
                "status": "NEW",
            },
            {
                "id": "sla-task-1-event-2",
                "task_id": "sla-task-1",
                "created_at": "2026-06-24T08:10:00+00:00",
                "event_type": "comment_added_internal",
                "title": "First response",
                "detail": "response",
                "status": "NEW",
            },
            {
                "id": "sla-task-1-event-3",
                "task_id": "sla-task-1",
                "created_at": "2026-06-24T08:30:00+00:00",
                "event_type": "assigned",
                "title": "Assigned",
                "detail": "assignment",
                "status": "ASSIGNED",
            },
            {
                "id": "sla-task-1-event-4",
                "task_id": "sla-task-1",
                "created_at": "2026-06-24T10:00:00+00:00",
                "event_type": "completed",
                "title": "Completed",
                "detail": "done",
                "status": "COMPLETED",
            },
        ])
        self._insert_owner_db_rows("calendar_events", [{
            "id": "timeline-calendar-latest",
            "created_at": "2026-06-25T11:00:00+00:00",
            "updated_at": "2026-06-25T11:00:00+00:00",
            "property_id": "property-1",
            "owner_id": "owner-1",
            "operation_task_id": "",
            "event_type": "Inspection",
            "title": "Latest event",
            "description": "Newest timeline item",
            "start_datetime": "2026-06-25T11:00:00+00:00",
            "end_datetime": "2026-06-25T12:00:00+00:00",
            "all_day": 0,
            "status": "SCHEDULED",
            "assigned_professional": "",
            "created_by": "admin",
            "color": "blue",
            "metadata_json": "{}",
        }])

        with patch.dict(os.environ, {**self.ADMIN_ENV, **self.SMTP_ENV}, clear=True):
            response = self.client.get("/admin", headers=self._auth_headers())

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Единна хронология", html)
        self.assertLess(html.index("Latest event"), html.index("Older event"))
        self.assertIn("2h 00m", html)
        self.assertIn("30m", html)
        self.assertIn("Средно време за завършване", html)
        self.assertIn("Средно време за възлагане", html)
        self.assertIn("Средно време за отговор", html)

    def test_operations_tasks_are_created_for_public_intakes(self):
        smtp_env = {
            **self.SMTP_ENV,
            "ADMIN_NOTIFICATION_EMAIL": "ops@example.com",
            "TELEGRAM_BOT_TOKEN": "bot-token",
            "TELEGRAM_CHAT_ID": "chat-1",
        }
        with patch.dict(os.environ, smtp_env, clear=True), patch("app.Thread", ImmediateThread), patch("app.smtplib.SMTP", FakeSMTP), patch("app.smtplib.SMTP_SSL", FakeSMTP), patch("app.urllib.request.urlopen", fake_urlopen):
            pilot_response = self.client.post(
                "/api/pilot-request",
                json={
                    "name": "Pilot Lead",
                    "email": "pilot@example.com",
                    "property_type": "Villa",
                    "apartment_count": "2",
                    "city": "Varna",
                    "concierge_needs": "Need pilot support for guest check-in.",
                    "current_language": "en",
                    "website": "",
                },
            )
            partner_response = self.client.post(
                "/partners/apply",
                data={
                    "company_name": "Sea Breeze Partners",
                    "contact_person": "Marta Ivanova",
                    "email": "partner@example.com",
                    "phone": "+359888222333",
                    "website": "",
                    "company_website": "https://example.com",
                    "city": "Varna",
                    "country": "Bulgaria",
                    "service_category": "Concierge",
                    "description": "Partnership request for concierge support.",
                    "years_in_business": "4",
                },
            )
            professional_response = self.client.post(
                "/professionals/apply",
                data={
                    "full_name": "Nikolai Petrov",
                    "email": "pro@example.com",
                    "phone": "+359888444555",
                    "city": "Burgas",
                    "country": "Bulgaria",
                    "professional_category": "Concierge",
                    "languages": "en, bg",
                    "experience": "6",
                    "short_bio": "Guest-facing operations specialist for premium stays.",
                    "website": "",
                },
            )
            concierge_response = self.client.post(
                "/request-service",
                data={
                    "name": "Guest Support",
                    "email": "concierge@example.com",
                    "phone": "+359888555666",
                    "property_city": "Sofia",
                    "property_type": "Apartment",
                    "service_category": "Concierge",
                    "preferred_date": "2026-07-15",
                    "description": "Need guest check-in coordination.",
                    "website": "",
                },
            )
            owner_registration_response = self.client.post(
                "/owners/register",
                data={
                    "full_name": "Owner Example",
                    "email": "owner-register@example.com",
                    "phone": "+359888777888",
                    "property_type": "Villa",
                    "city": "Varna",
                    "property_name": "Harbor View Villa",
                    "number_of_units": "2",
                    "notes": "Prefers email updates.",
                    "website": "",
                },
            )

        self.assertEqual(pilot_response.status_code, 200)
        self.assertEqual(partner_response.status_code, 200)
        self.assertEqual(professional_response.status_code, 200)
        self.assertEqual(concierge_response.status_code, 200)
        self.assertEqual(owner_registration_response.status_code, 302)

        tasks = self._read_owner_db_rows("operations_tasks")
        categories = [row["category"] for row in tasks]
        source_types = [row["source_type"] for row in tasks]

        self.assertIn("LEAD", categories)
        self.assertIn("PARTNER", categories)
        self.assertIn("PROFESSIONAL", categories)
        self.assertIn("CONCIERGE", categories)
        self.assertIn("OWNER", categories)
        self.assertIn("PILOT_REQUEST", source_types)
        self.assertIn("PARTNER_APPLICATION", source_types)
        self.assertIn("PROFESSIONAL_APPLICATION", source_types)
        self.assertIn("CONCIERGE_REQUEST", source_types)
        self.assertIn("OWNER_REGISTRATION", source_types)
        self.assertTrue(all(row["status"] == "NEW" for row in tasks))
        self.assertTrue(all(row["priority"] == "NORMAL" for row in tasks))

        notifications = self._read_owner_db_rows("operations_notifications")
        task_notifications = [row for row in notifications if row["metadata"] == "task_created"]
        self.assertGreaterEqual(len(task_notifications), 10)
        self.assertTrue(any(row["event_type"] == "notification_sent" and row["channel"] == "EMAIL" for row in task_notifications))
        self.assertTrue(any(row["event_type"] == "notification_sent" and row["channel"] == "TELEGRAM" for row in task_notifications))

    def test_owner_service_request_creates_notification_records(self):
        self._seed_owner_account(email="owner@example.com")
        self._seed_owner_property(owner_id="owner-1", owner_email="owner@example.com")

        with patch.dict(os.environ, self.SMTP_ENV, clear=True), patch("app.smtplib.SMTP", FakeSMTP), patch("app.smtplib.SMTP_SSL", FakeSMTP):
            self.client.post("/owners/login", data={"email": "owner@example.com"})

        token = self._read_jsonl("owner_magic_tokens.jsonl")[-1]["token"]
        self.client.get(f"/auth/owner-magic/{token}")

        with patch.dict(os.environ, {**self.SMTP_ENV, "ADMIN_NOTIFICATION_EMAIL": "ops@example.com", "TELEGRAM_BOT_TOKEN": "bot-token", "TELEGRAM_CHAT_ID": "chat-1"}, clear=True), patch("app.Thread", ImmediateThread), patch("app.smtplib.SMTP", FakeSMTP), patch("app.smtplib.SMTP_SSL", FakeSMTP), patch("app.urllib.request.urlopen", fake_urlopen):
            response = self.client.post("/owners/request-service", data={**self._service_request_payload(), "property_id": "property-1"})

        self.assertEqual(response.status_code, 302)
        notifications = self._read_owner_db_rows("operations_notifications")
        owner_notifications = [row for row in notifications if row["source_type"] == "OWNER_SERVICE_REQUEST"]
        self.assertTrue(owner_notifications)
        self.assertTrue(any(row["channel"] == "EMAIL" and row["event_type"] == "notification_sent" for row in owner_notifications))
        self.assertTrue(any(row["channel"] == "TELEGRAM" and row["event_type"] == "notification_sent" for row in owner_notifications))

    def test_admin_notifications_page_runs_overdue_scan_and_persists_report(self):
        overdue_due_date = (app_module.datetime.now(app_module.timezone.utc) - app_module.timedelta(days=2)).isoformat(timespec="seconds").replace("+00:00", "Z")
        with patch.dict(os.environ, {**self.ADMIN_ENV, **self.SMTP_ENV, "ADMIN_NOTIFICATION_EMAIL": "ops@example.com", "TELEGRAM_BOT_TOKEN": "bot-token", "TELEGRAM_CHAT_ID": "chat-1"}, clear=True):
            app_module._set_operations_notification_preferences("admin", operator_name="admin", email_enabled=True, telegram_enabled=True)
            app_module._upsert_operations_task_from_source(
                {
                    "id": "overdue-1",
                    "request_id": "overdue-1",
                    "source_type": "PILOT_REQUEST",
                    "source_id": "overdue-1",
                    "created_at": "2026-06-20T10:00:00Z",
                    "updated_at": "2026-06-20T10:00:00Z",
                    "title": "Overdue pilot request",
                    "category": "LEAD",
                    "owner_name": "Pilot Lead",
                    "owner_email": "pilot@example.com",
                    "property_name": "Sea View Villa",
                    "assigned_to": "Mira Ivanova",
                    "priority": "HIGH",
                    "status": "ASSIGNED",
                    "due_date": overdue_due_date,
                    "notes": "Follow up.",
                    "completed_at": "",
                    "owner_id": "",
                    "property_location": "Varna",
                    "admin_notes": "",
                    "request_status": "new",
                    "timeline_detail": "Pilot request overdue",
                },
                append_created_event=True,
                force_create=True,
                notify=False,
            )
            app_module._upsert_operations_task_from_source(
                {
                    "id": "overdue-2",
                    "request_id": "overdue-2",
                    "source_type": "PARTNER_APPLICATION",
                    "source_id": "overdue-2",
                    "created_at": "2026-06-20T11:00:00Z",
                    "updated_at": "2026-06-20T11:00:00Z",
                    "title": "Overdue partner application",
                    "category": "PARTNER",
                    "owner_name": "Marta Ivanova",
                    "owner_email": "partner@example.com",
                    "property_name": "Sea Breeze Partners",
                    "assigned_to": "",
                    "priority": "URGENT",
                    "status": "NEW",
                    "due_date": overdue_due_date,
                    "notes": "Needs review.",
                    "completed_at": "",
                    "owner_id": "",
                    "property_location": "Varna",
                    "admin_notes": "",
                    "request_status": "new",
                    "timeline_detail": "Partner application overdue",
                },
                append_created_event=True,
                force_create=True,
                notify=False,
            )

        FakeSMTP.sent_messages.clear()
        with patch.dict(os.environ, {**self.ADMIN_ENV, **self.SMTP_ENV, "ADMIN_NOTIFICATION_EMAIL": "ops@example.com", "TELEGRAM_BOT_TOKEN": "bot-token", "TELEGRAM_CHAT_ID": "chat-1"}, clear=True), patch("app.Thread", ImmediateThread), patch("app.smtplib.SMTP", FakeSMTP), patch("app.smtplib.SMTP_SSL", FakeSMTP), patch("app.urllib.request.urlopen", fake_urlopen):
            response = self.client.get("/admin/notifications", headers=self._auth_headers())

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Operations Notification Center", html)
        self.assertIn("Overdue alerts", html)
        self.assertIn("Failed notifications", html)
        self.assertIn("Save preferences", html)
        self.assertGreaterEqual(len(FakeSMTP.sent_messages), 1)
        self.assertTrue(any("Daily overdue tasks report" in message["Subject"] for message in FakeSMTP.sent_messages))
        self.assertGreaterEqual(len(FakeUrlopenResponse.calls), 1)

        notifications = self._read_owner_db_rows("operations_notifications")
        self.assertTrue(any(row["event_type"] == "overdue_detected" and row["task_id"] == "overdue-1" for row in notifications))
        self.assertTrue(any(row["event_type"] == "overdue_detected" and row["task_id"] == "overdue-2" for row in notifications))
        report_rows = [row for row in notifications if row["source_id"] == "daily-overdue-report"]
        self.assertTrue(any(row["event_type"] == "notification_sent" and row["channel"] == "EMAIL" for row in report_rows))
        self.assertTrue(any(row["event_type"] == "notification_sent" and row["channel"] == "TELEGRAM" for row in report_rows))
        self.assertTrue(any("open_overdue_tasks" in row["metadata"] for row in report_rows))

        with patch.dict(os.environ, {**self.ADMIN_ENV, **self.SMTP_ENV}, clear=True):
            preference_response = self.client.post(
                "/admin/notifications",
                data={},
                headers=self._auth_headers(),
            )

        self.assertEqual(preference_response.status_code, 302)
        preferences = self._read_owner_db_rows("operations_notification_preferences")
        self.assertEqual(preferences[0]["email_enabled"], 0)
        self.assertEqual(preferences[0]["telegram_enabled"], 0)

    def test_jsonl_migration_imports_old_records_idempotently(self):
        self._seed_jsonl("owner_accounts.jsonl", [{
            "id": "owner-legacy",
            "created_at": "2026-06-15T10:00:00Z",
            "full_name": "Legacy Owner",
            "email": "legacy@example.com",
            "phone": "+359888111222",
            "property_type": "Villa",
            "city": "Varna",
            "property_name": "Legacy Villa",
            "number_of_units": 1,
            "notes": "",
        }])
        self._seed_jsonl("owner_properties.jsonl", [{
            "id": "property-legacy",
            "owner_id": "owner-legacy",
            "created_at": "2026-06-15T10:30:00Z",
            "name": "Legacy Villa",
            "property_type": "Villa",
            "location": "Varna",
            "bedrooms": 3,
            "bathrooms": 2,
            "guest_capacity": 6,
            "operating_mode": "year-round",
            "notes": "",
        }])
        self._seed_jsonl("owner_magic_tokens.jsonl", [{
            "token": "legacy-token",
            "email": "legacy@example.com",
            "created_at": "2026-06-15T10:40:00Z",
        }])
        self._seed_jsonl("owner_magic_email_events.jsonl", [{
            "id": "event-legacy",
            "created_at": "2026-06-15T10:50:00Z",
            "timestamp": "2026-06-15T10:50:00Z",
            "event": "sent",
            "submitted_email": "legacy@example.com",
            "account_found": True,
            "delivery": "sent",
            "email_masked": _mask_email("legacy@example.com"),
            "reason": "sent",
            "source": "login",
            "language": "bg",
            "smtp_message_id": "<legacy-message-id>",
        }])

        with patch.dict(os.environ, {**self.ADMIN_ENV, **self.SMTP_ENV}, clear=True):
            first_accounts = self.client.get("/admin/owner-accounts", headers=self._auth_headers())
            first_events = self.client.get("/admin/owner-magic-events", headers=self._auth_headers())
            second_accounts = self.client.get("/admin/owner-accounts", headers=self._auth_headers())

        self.assertEqual(first_accounts.status_code, 200)
        self.assertEqual(first_events.status_code, 200)
        self.assertEqual(second_accounts.status_code, 200)
        self.assertEqual(len(self._read_owner_db_rows("owner_accounts")), 1)
        self.assertEqual(len(self._read_owner_db_rows("owner_properties")), 1)
        self.assertEqual(len(self._read_owner_db_rows("owner_magic_tokens")), 1)
        self.assertEqual(len(self._read_owner_db_rows("owner_magic_email_events")), 1)
        self.assertEqual(self._read_owner_db_rows("owner_accounts")[0]["email"], "legacy@example.com")
        self.assertEqual(self._read_owner_db_rows("owner_properties")[0]["name"], "Legacy Villa")
        self.assertEqual(self._read_owner_db_rows("owner_magic_tokens")[0]["token"], "legacy-token")
        self.assertEqual(self._read_owner_db_rows("owner_magic_email_events")[0]["id"], "event-legacy")

    def test_admin_owner_magic_events_page_requires_admin(self):
        with patch.dict(os.environ, {**self.ADMIN_ENV, **self.SMTP_ENV}, clear=True):
            response = self.client.get("/admin/owner-magic-events")

        self.assertEqual(response.status_code, 401)

        self._seed_owner_account()

        with patch.dict(os.environ, {**self.ADMIN_ENV, **self.SMTP_ENV}, clear=True), patch("app.smtplib.SMTP", FakeSMTP), patch("app.smtplib.SMTP_SSL", FakeSMTP):
            login_response = self.client.post("/owners/login", data=self._demo_login_payload())

        self.assertEqual(login_response.status_code, 302)
        login_tokens = self._read_jsonl("owner_magic_tokens.jsonl")
        self.assertTrue(login_tokens)
        login_token = login_tokens[-1]["token"]

        with patch.dict(os.environ, {**self.ADMIN_ENV, **self.SMTP_ENV}, clear=True):
            admin_response = self.client.get("/admin/owner-magic-events", headers=self._auth_headers())

        self.assertEqual(admin_response.status_code, 200)
        html = admin_response.get_data(as_text=True)
        self.assertIn("Owner Magic Events", html)
        self.assertIn(_mask_email("owner@blackseaconnect.com"), html)
        self.assertNotIn("owner@blackseaconnect.com", html)
        self.assertNotIn(login_token, html)
        self.assertIn("Message-ID", html)

        events = self._read_jsonl("owner_magic_email_events.jsonl")
        sent_event = next(event for event in events if event["event"] == "sent")
        self.assertTrue(sent_event["smtp_message_id"])
        self.assertIn(html_lib.escape(sent_event["smtp_message_id"]), html)
        self.assertIn(sent_event["smtp_message_id"][1:17], html)

    def test_mask_email_helper(self):
        self.assertEqual(_mask_email("stoyanova@orange.fr"), "s*******@orange.fr")
        self.assertEqual(_mask_email("ab@example.com"), "a*@example.com")

    def test_owner_magic_link_logs_user_in(self):
        _, token = self._request_owner_magic_link()

        response = self.client.get(f"/auth/owner-magic/{token}")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/owners/dashboard", response.headers["Location"])
        self.assertIn("lang=bg", response.headers["Location"])
        with self.client.session_transaction() as session:
            self.assertTrue(session.get("owner_logged_in"))
            self.assertEqual(session.get("owner_email"), "owner@blackseaconnect.com")

    def test_owner_magic_link_token_is_consumed_after_login(self):
        _, token = self._request_owner_magic_link()

        self.client.get(f"/auth/owner-magic/{token}")

        tokens = self._read_jsonl("owner_magic_tokens.jsonl")
        self.assertEqual(tokens, [])

    def test_owner_magic_link_rejects_expired_token(self):
        self._seed_owner_account()
        expired_token = "expired-token-1"
        self._seed_jsonl("owner_magic_tokens.jsonl", [{
            "token": expired_token,
            "email": "owner@blackseaconnect.com",
            "created_at": "2026-06-15T09:00:00Z",
        }])

        response = self.client.get(f"/auth/owner-magic/{expired_token}")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/owners/login?expired_token=1", response.headers["Location"])
        self.assertIn("lang=bg", response.headers["Location"])
        self.assertEqual(self._read_jsonl("owner_magic_tokens.jsonl"), [])

    def test_owner_magic_link_rejects_invalid_token(self):
        self._seed_owner_account()

        response = self.client.get("/auth/owner-magic/does-not-exist")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/owners/login?invalid_token=1", response.headers["Location"])
        self.assertIn("lang=bg", response.headers["Location"])

    def test_owner_logout_clears_session(self):
        self._login_owner_via_magic()

        response = self.client.get("/owners/logout")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/owners/login", response.headers["Location"])
        self.assertIn("lang=bg", response.headers["Location"])
        with self.client.session_transaction() as session:
            self.assertFalse(session.get("owner_logged_in"))

    def test_owner_dashboard_and_admin_detail_use_styled_request_components(self):
        self._seed_jsonl("professional_applications.jsonl", [{
            "id": "pro-1",
            "created_at": "2026-06-10T10:00:00Z",
            "status": "converted",
            "full_name": "Approved Concierge",
            "email": "pro@example.com",
            "phone": "+359888999000",
            "city": "Varna",
            "country": "Bulgaria",
            "professional_category": "Concierge",
            "languages": "Bulgarian, English",
            "experience": "5 years",
            "short_bio": "Approved profile.",
            "owner": "",
            "notes": "",
            "internal_notes": "",
            "timeline": [],
        }])
        self._seed_jsonl("service_requests.jsonl", [self._demo_owner_request(
            status="assigned",
            assigned_provider_id="pro-1",
            assigned_provider_name="Approved Concierge",
            assigned_provider_company="Approved Concierge",
            assigned_professional_id="pro-1",
            assigned_professional_name="Approved Concierge",
            assigned_professional_company="Approved Concierge",
        )])

        self._login_owner_via_magic()
        owner_html = self.client.get("/owners/dashboard").get_data(as_text=True)

        with patch.dict(os.environ, {**self.ADMIN_ENV, **self.SMTP_ENV}, clear=True):
            admin_html = self.client.get("/admin/service-requests/owner-request-1", headers=self._auth_headers()).get_data(as_text=True)

        self.assertIn("owner-portal-card--activity", owner_html)
        self.assertIn("owner-activity-item", owner_html)
        self.assertIn("owner-status-badge", owner_html)
        self.assertIn("admin-request-detail-card", admin_html)
        self.assertIn("admin-request-detail-form__control", admin_html)
        self.assertIn('class="admin-request-detail-form__control" name="status"', admin_html)
        self.assertIn('class="admin-request-detail-form__control" name="assigned_provider_id"', admin_html)
        self.assertNotIn("No professional selected", admin_html)
        self.assertIn('value="pro-1" selected', admin_html)
        self.assertIn("Approved Concierge · Assigned", admin_html)
        self.assertIn('class="admin-request-detail-form__control admin-request-detail-form__textarea"', admin_html)
        self.assertIn("admin-request-detail-description", admin_html)
        self.assertIn("admin-request-detail-timeline", admin_html)

    def test_public_owner_ctas_are_visible(self):
        response_home = self.client.get("/")
        response_services = self.client.get("/services")
        response_professionals = self.client.get("/professionals")
        response_pilot = self.client.get("/pilot-access")

        self.assertEqual(response_home.status_code, 200)
        self.assertEqual(response_services.status_code, 200)
        self.assertEqual(response_professionals.status_code, 200)
        self.assertEqual(response_pilot.status_code, 200)

        self.assertIn('<body class="home-page">', response_home.get_data(as_text=True))
        self.assertIn('<body class="pilot-access-page">', response_pilot.get_data(as_text=True))
        self.assertIn('href="/owners/register?lang=bg"', response_home.get_data(as_text=True))
        self.assertIn('href="/owners/register?lang=bg"', response_services.get_data(as_text=True))
        self.assertIn('href="/owners/register?lang=bg"', response_professionals.get_data(as_text=True))
        self.assertIn('href="/owners/register?lang=bg"', response_pilot.get_data(as_text=True))


    def test_homepage_owner_first_conversion_layer_uses_premium_language(self):
        html = self.client.get("/").get_data(as_text=True)

        for phrase in [
            "Пълен контрол за собствениците.",
            "Подходящо за",
            "Отвори портала за собственици",
            "Заявете пилотен достъп и тествайте оперативния модел.",
            "Регистрирайте се, получете сигурен достъп, управлявайте имотите, заявявайте услуги и си почивайте.",
            "Пилотен достъп",
            "Демо",
            "Услуги",
        ]:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, html)

        for phrase in [
            "Жив преглед на мрежата",
            "Какво покрива",
            "Ниво на доверие",
            "Доверени партньори",
            "Ресурси",
            "SEO страниците",
        ]:
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, html)

    def test_homepage_translates_across_supported_languages(self):
        import subprocess
        import textwrap

        repo_root = Path(__file__).resolve().parents[1]

        def load_home_translation(lang):
            script = textwrap.dedent(
                """
                const fs = require('fs');
                const vm = require('vm');

                const moduleFiles = fs.readdirSync('static/js/i18n')
                  .filter((file) => file.endsWith('.js') && file !== 'index.js')
                  .sort();
                const moduleSrc = moduleFiles
                  .map((file) => fs.readFileSync(`static/js/i18n/${file}`, 'utf8'))
                  .join('\\n');
                const indexSrc = fs.readFileSync('static/js/i18n/index.js', 'utf8');

                const sandbox = { window: {} };
                sandbox.window = sandbox;

                vm.runInNewContext(moduleSrc, sandbox);
                vm.runInNewContext(indexSrc, sandbox);

                const locale = sandbox.window.BlackSeaI18N[LANG];
                const home = locale.home;
                const common = locale.common;
                console.log(JSON.stringify({
                  homeTitle: home.homeTitle,
                  homePrimaryCta: home.homePrimaryCta,
                  navApply: common.navApply
                }));
                """
            ).replace("LANG", json.dumps(lang))
            result = subprocess.run(
                ["node", "-e", script],
                cwd=repo_root,
                check=True,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
            )
            return json.loads(result.stdout.strip())

        expectations = {
            "bg": {
                "homeTitle": "Оперативният кокпит за собственици и крайбрежни оператори.",
                "homePrimaryCta": "Виж платформата",
                "navApply": "Кандидатстване",
            },
            "en": {
                "homeTitle": "The operational cockpit for owners and coastal operators.",
                "homePrimaryCta": "View platform",
                "navApply": "Apply",
            },
            "fr": {
                "homeTitle": "Le cockpit opérationnel pour les propriétaires et les opérateurs côtiers.",
                "homePrimaryCta": "Voir la plateforme",
                "navApply": "Candidature",
            },
            "ru": {
                "homeTitle": "Операционный кокпит для владельцев и прибрежных операторов.",
                "homePrimaryCta": "Посмотреть платформу",
                "navApply": "Заявка",
            },
        }

        for lang, expected in expectations.items():
            with self.subTest(lang=lang):
                actual = load_home_translation(lang)
                self.assertEqual(actual["homeTitle"], expected["homeTitle"])
                self.assertEqual(actual["homePrimaryCta"], expected["homePrimaryCta"])
                self.assertEqual(actual["navApply"], expected["navApply"])

    def test_owner_service_request_creation_saves_and_emails(self):
        self._login_owner_via_magic()
        FakeSMTP.sent_messages.clear()

        with patch.dict(os.environ, self.SMTP_ENV, clear=True), patch("app.Thread", ImmediateThread), patch("app.smtplib.SMTP", FakeSMTP), patch("app.smtplib.SMTP_SSL", FakeSMTP):
            response = self.client.post("/owners/request-service", data=self._service_request_payload())

        self.assertEqual(response.status_code, 302)
        self.assertIn("/owners/dashboard", response.headers["Location"])
        self.assertIn("lang=bg", response.headers["Location"])

        records = self._read_jsonl("service_requests.jsonl")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["request_source"], "owner")
        self.assertEqual(records[0]["status"], "new")
        self.assertEqual(records[0]["timeline"][0]["type"], "SERVICE_REQUEST_CREATED")
        self.assertEqual(len(FakeSMTP.sent_messages), 2)
        subjects = {message["Subject"] for message in FakeSMTP.sent_messages}
        self.assertIn("[BlackSeaConnect] Service request received", subjects)
        self.assertIn("[BlackSeaConnect] New owner service request", subjects)

    def test_admin_assignment_updates_status_and_notifies_owner(self):
        self._seed_jsonl("professional_applications.jsonl", [{
            "id": "pro-1",
            "created_at": "2026-06-10T10:00:00Z",
            "status": "converted",
            "full_name": "Approved Concierge",
            "email": "pro@example.com",
            "phone": "+359888999000",
            "city": "Varna",
            "country": "Bulgaria",
            "professional_category": "Concierge",
            "languages": "Bulgarian, English",
            "experience": "5 years",
            "short_bio": "Approved profile.",
            "owner": "",
            "notes": "",
            "internal_notes": "",
            "timeline": [],
        }])
        self._seed_jsonl("service_requests.jsonl", [self._demo_owner_request()])

        with patch.dict(os.environ, {**self.ADMIN_ENV, **self.SMTP_ENV}, clear=True), patch("app.Thread", ImmediateThread), patch("app.smtplib.SMTP", FakeSMTP), patch("app.smtplib.SMTP_SSL", FakeSMTP):
            detail = self.client.get("/admin/service-requests/owner-request-1", headers=self._auth_headers())
            self.assertEqual(detail.status_code, 200)
            self.assertIn("Approved Concierge", detail.get_data(as_text=True))

            response = self.client.post(
                "/admin/service-requests/owner-request-1/update",
                data={
                    "status": "assigned",
                    "assigned_provider_id": "pro-1",
                    "internal_notes": "Assigned to concierge.",
                },
                headers=self._auth_headers(),
            )

        self.assertEqual(response.status_code, 302)
        updated = self._read_jsonl("service_requests.jsonl")[0]
        self.assertEqual(updated["status"], "assigned")
        self.assertEqual(updated["assigned_provider_company"], "Approved Concierge")
        self.assertTrue(any(event["type"] == "SERVICE_REQUEST_PROFESSIONAL_ASSIGNED" for event in updated["timeline"]))
        self.assertTrue(any(event["type"] == "SERVICE_REQUEST_STATUS_UPDATED" for event in updated["timeline"]))
        self.assertGreaterEqual(len(FakeSMTP.sent_messages), 1)
        self.assertTrue(any("Professional assigned" in message["Subject"] or "status updated" in message["Subject"] for message in FakeSMTP.sent_messages))

