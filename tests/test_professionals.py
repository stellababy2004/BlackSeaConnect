import base64
import json
import os
import shutil
import unittest
from email.message import EmailMessage
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


class ApplicationWorkflowTests(unittest.TestCase):
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
    }

    def setUp(self):
        self._cwd = os.getcwd()
        self._tmpdir = Path(self._cwd) / f".tmp_application_tests_{uuid.uuid4().hex}"
        self._tmpdir.mkdir(exist_ok=True)
        os.chdir(self._tmpdir)
        app.config["TESTING"] = True
        self.client = app.test_client()

    def tearDown(self):
        os.chdir(self._cwd)
        shutil.rmtree(self._tmpdir, ignore_errors=True)
        FakeSMTP.sent_messages.clear()

    def _auth_headers(self):
        token = base64.b64encode(f"{self.ADMIN_ENV['ADMIN_USERNAME']}:{self.ADMIN_ENV['ADMIN_PASSWORD']}".encode("utf-8")).decode("ascii")
        return {"Authorization": f"Basic {token}"}

    def _read_jsonl(self, filename):
        path = Path("data") / filename
        if not path.exists():
            return []

        records = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line))
        return records

    def _seed_jsonl(self, filename, records):
        data_dir = Path("data")
        data_dir.mkdir(exist_ok=True)
        path = data_dir / filename
        with path.open("w", encoding="utf-8") as f:
            for record in records:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _partner_payload(self):
        return {
            "company_name": "Sea Breeze Partners",
            "contact_person": "Elena Petrova",
            "email": "partners@example.com",
            "phone": "+359888123456",
            "website": "https://example.com",
            "city": "Varna",
            "country": "Bulgaria",
            "service_category": "Transfers",
            "description": "Trusted transfer coverage for coastal arrivals and departures.",
            "years_in_business": "8",
        }

    def _professional_payload(self):
        return {
            "full_name": "Nikolay Ivanov",
            "email": "professionals@example.com",
            "phone": "+359888654321",
            "city": "Burgas",
            "country": "Bulgaria",
            "professional_category": "Concierge",
            "languages": "Bulgarian, English",
            "experience": "7 years",
            "short_bio": "Guest-facing operations specialist for premium coastal stays.",
        }

    def test_partner_application_submission_saves_and_emails(self):
        with patch.dict(os.environ, self.SMTP_ENV, clear=True), patch("app.Thread", ImmediateThread), patch("app.smtplib.SMTP", FakeSMTP), patch("app.smtplib.SMTP_SSL", FakeSMTP):
            response = self.client.post("/partners/apply", data=self._partner_payload())

        self.assertEqual(response.status_code, 200)
        records = self._read_jsonl("partner_applications.jsonl")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["status"], "new")
        self.assertEqual(records[0]["company_name"], "Sea Breeze Partners")
        self.assertEqual(records[0]["timeline"][0]["type"], "PARTNER_APPLICATION_CREATED")

        self.assertEqual(len(FakeSMTP.sent_messages), 1)
        message = FakeSMTP.sent_messages[0]
        self.assertIsInstance(message, EmailMessage)
        self.assertEqual(message["Subject"], "[BlackSeaConnect] New Partner Application")
        self.assertEqual(message["To"], "concierge@blackseaconnect.com")
        self.assertIn("Sea Breeze Partners", message.get_content())
        self.assertIn("Transfers", message.get_content())
        self.assertIn("/admin/partners/", message.get_content())

    def test_professional_application_submission_saves_and_emails(self):
        with patch.dict(os.environ, self.SMTP_ENV, clear=True), patch("app.Thread", ImmediateThread), patch("app.smtplib.SMTP", FakeSMTP), patch("app.smtplib.SMTP_SSL", FakeSMTP):
            response = self.client.post("/professionals/apply", data=self._professional_payload())

        self.assertEqual(response.status_code, 200)
        records = self._read_jsonl("professional_applications.jsonl")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["status"], "new")
        self.assertEqual(records[0]["full_name"], "Nikolay Ivanov")
        self.assertEqual(records[0]["timeline"][0]["type"], "PROFESSIONAL_APPLICATION_CREATED")

        self.assertEqual(len(FakeSMTP.sent_messages), 1)
        message = FakeSMTP.sent_messages[0]
        self.assertIsInstance(message, EmailMessage)
        self.assertEqual(message["Subject"], "[BlackSeaConnect] New Professional Application")
        self.assertEqual(message["To"], "concierge@blackseaconnect.com")
        self.assertIn("Nikolay Ivanov", message.get_content())
        self.assertIn("Concierge", message.get_content())
        self.assertIn("/admin/professionals/", message.get_content())

    def test_professional_apply_page_uses_i18n_hooks_for_supported_locales(self):
        for lang in ("bg", "fr", "ru"):
            response = self.client.get("/professionals/apply", query_string={"lang": lang})
            self.assertEqual(response.status_code, 200)

            html = response.get_data(as_text=True)
            self.assertIn('<body class="professionals-apply-page">', html)
            self.assertIn('data-i18n="pageTitle"', html)
            self.assertIn('data-i18n-attr="content:heroIntro"', html)
            self.assertIn('data-i18n="navPartners"', html)
            self.assertIn('data-i18n="navProfessionals"', html)
            self.assertIn('data-i18n="navPilotAccess"', html)
            self.assertIn('data-i18n="navApply"', html)
            self.assertIn('data-i18n="backToProfessionals"', html)
            self.assertIn('<div class="language-switcher" aria-label="Language switcher" data-i18n-attr="aria-label:languageSwitcherLabel">', html)
            self.assertIn('data-lang-switch="bg"', html)
            self.assertIn('data-lang-switch="en"', html)
            self.assertIn('data-lang-switch="fr"', html)
            self.assertIn('data-lang-switch="ru"', html)
            self.assertIn('data-i18n="heroEyebrow"', html)
            self.assertIn('data-i18n="heroTitle"', html)
            self.assertIn('data-i18n="heroPrimaryCta"', html)
            self.assertIn('data-i18n="heroSecondaryCta"', html)
            self.assertIn('data-i18n="formEyebrow"', html)
            self.assertIn('data-i18n="professionalCategoryLabel"', html)
            self.assertIn('data-i18n="countryLabel"', html)
            self.assertIn('data-i18n="shortBioLabel"', html)
            self.assertIn('data-i18n="submitCta"', html)
            self.assertIn('data-i18n="submitHint"', html)
            self.assertIn('/static/js/translations.js', html)
            self.assertIn('/static/js/i18n.js', html)

        ru_response = self.client.get("/professionals/apply", query_string={"lang": "ru"})
        self.assertEqual(ru_response.status_code, 200)
        ru_html = ru_response.get_data(as_text=True)
        self.assertIn('data-i18n="pageTitle"', ru_html)
        self.assertIn('data-lang-switch="ru"', ru_html)

    def test_status_updates_store_history_and_notes(self):
        partner_record = {
            "id": "partner-1",
            "created_at": "2026-06-01T10:00:00Z",
            "status": "new",
            "company_name": "Bay Transfers",
            "contact_person": "Maria Dimitrova",
            "email": "partner1@example.com",
            "phone": "+359888000111",
            "website": "",
            "city": "Varna",
            "country": "Bulgaria",
            "service_category": "Transfers",
            "description": "Airport and marina transfers.",
            "years_in_business": 5,
            "owner": "",
            "notes": "",
            "internal_notes": "",
            "timeline": [],
        }
        professional_record = {
            "id": "professional-1",
            "created_at": "2026-06-02T10:00:00Z",
            "status": "new",
            "full_name": "Elena Georgieva",
            "email": "pro1@example.com",
            "phone": "+359888000222",
            "city": "Burgas",
            "country": "Bulgaria",
            "professional_category": "Guest Relations",
            "languages": "Bulgarian, English",
            "experience": "4 years",
            "short_bio": "Guest relations support for short-stay properties.",
            "owner": "",
            "notes": "",
            "internal_notes": "",
            "timeline": [],
        }
        self._seed_jsonl("partner_applications.jsonl", [partner_record])
        self._seed_jsonl("professional_applications.jsonl", [professional_record])

        with patch.dict(os.environ, self.ADMIN_ENV, clear=True):
            partner_response = self.client.post(
                "/admin/partners/partner-1/update",
                data={"status": "converted", "owner": "Alex", "notes": "Converted after call."},
                headers=self._auth_headers(),
            )
            professional_response = self.client.post(
                "/admin/professionals/professional-1/update",
                data={"status": "qualified", "owner": "Alex", "notes": "Schedule a follow-up."},
                headers=self._auth_headers(),
            )

        self.assertEqual(partner_response.status_code, 302)
        self.assertEqual(professional_response.status_code, 302)

        updated_partner = self._read_jsonl("partner_applications.jsonl")[0]
        updated_professional = self._read_jsonl("professional_applications.jsonl")[0]
        self.assertEqual(updated_partner["status"], "converted")
        self.assertEqual(updated_partner["owner"], "Alex")
        self.assertEqual(updated_partner["notes"], "Converted after call.")
        self.assertTrue(any(event["type"] == "APPLICATION_STATUS_UPDATED" for event in updated_partner["timeline"]))
        self.assertTrue(any(event["type"] == "APPLICATION_OWNER_ASSIGNED" for event in updated_partner["timeline"]))
        self.assertTrue(any(event["type"] == "APPLICATION_NOTE_ADDED" for event in updated_partner["timeline"]))

        self.assertEqual(updated_professional["status"], "qualified")
        self.assertEqual(updated_professional["owner"], "Alex")
        self.assertEqual(updated_professional["notes"], "Schedule a follow-up.")
        self.assertTrue(any(event["type"] == "APPLICATION_STATUS_UPDATED" for event in updated_professional["timeline"]))

    def test_approved_entries_appear_publicly(self):
        self._seed_jsonl("partner_applications.jsonl", [
            {
                "id": "partner-approved",
                "created_at": "2026-06-03T10:00:00Z",
                "status": "converted",
                "company_name": "Approved Transfers",
                "contact_person": "Ivan Petrov",
                "email": "approved-partner@example.com",
                "phone": "+359888333444",
                "website": "",
                "city": "Varna",
                "country": "Bulgaria",
                "service_category": "Transfers",
                "description": "Approved partner entry.",
                "years_in_business": 10,
                "owner": "",
                "notes": "",
                "internal_notes": "",
                "timeline": [],
            },
            {
                "id": "partner-hidden",
                "created_at": "2026-06-04T10:00:00Z",
                "status": "new",
                "company_name": "Hidden Partner",
                "contact_person": "Hidden Person",
                "email": "hidden@example.com",
                "phone": "+359888555666",
                "website": "",
                "city": "Burgas",
                "country": "Bulgaria",
                "service_category": "Cleaning",
                "description": "Not yet approved.",
                "years_in_business": 2,
                "owner": "",
                "notes": "",
                "internal_notes": "",
                "timeline": [],
            },
        ])
        self._seed_jsonl("professional_applications.jsonl", [
            {
                "id": "professional-approved",
                "created_at": "2026-06-05T10:00:00Z",
                "status": "converted",
                "full_name": "Approved Professional",
                "email": "approved-pro@example.com",
                "phone": "+359888777888",
                "city": "Nessebar",
                "country": "Bulgaria",
                "professional_category": "Concierge",
                "languages": "Bulgarian, English",
                "experience": "6 years",
                "short_bio": "Approved bio.",
                "owner": "",
                "notes": "",
                "internal_notes": "",
                "timeline": [],
            },
            {
                "id": "professional-hidden",
                "created_at": "2026-06-06T10:00:00Z",
                "status": "qualified",
                "full_name": "Hidden Professional",
                "email": "hidden-pro@example.com",
                "phone": "+359888999000",
                "city": "Varna",
                "country": "Bulgaria",
                "professional_category": "Maintenance",
                "languages": "Bulgarian",
                "experience": "3 years",
                "short_bio": "Still in review.",
                "owner": "",
                "notes": "",
                "internal_notes": "",
                "timeline": [],
            },
        ])

        partner_response = self.client.get("/partners")
        professional_response = self.client.get("/professionals")

        self.assertEqual(partner_response.status_code, 200)
        partner_html = partner_response.get_data(as_text=True)
        self.assertIn('<body class="partners-page">', partner_html)
        self.assertIn('data-i18n-attr="aria-label:languageSwitcherLabel"', partner_html)
        self.assertIn('data-i18n="partnersApprovedEyebrow"', partner_html)
        self.assertIn('data-i18n="partnersApprovedTitle"', partner_html)
        self.assertIn("Approved Transfers", partner_html)
        self.assertNotIn("Hidden Partner", partner_html)

        self.assertEqual(professional_response.status_code, 200)
        professional_html = professional_response.get_data(as_text=True)
        self.assertIn('<body class="professionals-page">', professional_html)
        self.assertIn('data-i18n-attr="aria-label:languageSwitcherLabel"', professional_html)
        self.assertIn('data-i18n="professionalsApprovedEyebrow"', professional_html)
        self.assertIn('data-i18n="professionalsApprovedTitle"', professional_html)
        self.assertIn("Approved Professional", professional_html)
        self.assertNotIn("Hidden Professional", professional_html)

    def test_csv_exports_work_for_both_application_types(self):
        self._seed_jsonl("partner_applications.jsonl", [{
            "id": "partner-csv",
            "created_at": "2026-06-07T10:00:00Z",
            "status": "contacted",
            "company_name": "CSV Partner",
            "contact_person": "CSV Contact",
            "email": "csv-partner@example.com",
            "phone": "+359888101010",
            "website": "",
            "city": "Varna",
            "country": "Bulgaria",
            "service_category": "Hospitality",
            "description": "CSV export check.",
            "years_in_business": 4,
            "owner": "Owner One",
            "notes": "",
            "internal_notes": "",
            "timeline": [],
        }])
        self._seed_jsonl("professional_applications.jsonl", [{
            "id": "professional-csv",
            "created_at": "2026-06-08T10:00:00Z",
            "status": "qualified",
            "full_name": "CSV Professional",
            "email": "csv-pro@example.com",
            "phone": "+359888202020",
            "city": "Burgas",
            "country": "Bulgaria",
            "professional_category": "Guest Relations",
            "languages": "English",
            "experience": "9 years",
            "short_bio": "CSV export check.",
            "owner": "Owner Two",
            "notes": "",
            "internal_notes": "",
            "timeline": [],
        }])

        with patch.dict(os.environ, self.ADMIN_ENV, clear=True):
            partner_response = self.client.get("/admin/partners/export", headers=self._auth_headers())
            professional_response = self.client.get("/admin/professionals/export", headers=self._auth_headers())

        self.assertEqual(partner_response.status_code, 200)
        self.assertIn("company_name", partner_response.get_data(as_text=True))
        self.assertIn("CSV Partner", partner_response.get_data(as_text=True))

        self.assertEqual(professional_response.status_code, 200)
        self.assertIn("full_name", professional_response.get_data(as_text=True))
        self.assertIn("CSV Professional", professional_response.get_data(as_text=True))

    def test_admin_dashboard_shows_application_kpis(self):
        self._seed_jsonl("partner_applications.jsonl", [{
            "id": "partner-kpi",
            "created_at": "2026-06-09T10:00:00Z",
            "status": "new",
            "company_name": "KPI Partner",
            "contact_person": "KPI Contact",
            "email": "kpi-partner@example.com",
            "phone": "+359888303030",
            "website": "",
            "city": "Varna",
            "country": "Bulgaria",
            "service_category": "Transfers",
            "description": "KPI check.",
            "years_in_business": 3,
            "owner": "",
            "notes": "",
            "internal_notes": "",
            "timeline": [],
        }])
        self._seed_jsonl("professional_applications.jsonl", [{
            "id": "professional-kpi",
            "created_at": "2026-06-10T10:00:00Z",
            "status": "converted",
            "full_name": "KPI Professional",
            "email": "kpi-pro@example.com",
            "phone": "+359888404040",
            "city": "Burgas",
            "country": "Bulgaria",
            "professional_category": "Concierge",
            "languages": "English",
            "experience": "2 years",
            "short_bio": "KPI check.",
            "owner": "",
            "notes": "",
            "internal_notes": "",
            "timeline": [],
        }])

        with patch.dict(os.environ, self.ADMIN_ENV, clear=True):
            response = self.client.get("/admin", headers=self._auth_headers())

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Partner Applications", html)
        self.assertIn("Professional Applications", html)
