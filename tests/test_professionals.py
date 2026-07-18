import base64
import html as html_module
import io
import json
import os
import re
import shutil
import unittest
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
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
        app_module._PUBLIC_FORM_RATE_LIMITS.clear()
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

    def _email_plaintext(self, message):
        body = message.get_body(preferencelist=("plain",))
        return body.get_content() if body else message.get_content()

    def _seed_professional_application(self, *, full_name, email, status, professional_category="Concierge", company="", phone="+359888000000"):
        self._seed_jsonl("professional_applications.jsonl", [{
            "id": f"professional-{re.sub(r'[^a-z0-9]+', '-', email.lower()).strip('-')}",
            "created_at": "2026-06-10T10:00:00Z",
            "status": status,
            "full_name": full_name,
            "email": email,
            "phone": phone,
            "city": "Varna",
            "country": "Bulgaria",
            "company_name": company,
            "professional_category": professional_category,
            "languages": "Bulgarian, English",
            "experience": "5 years",
            "short_bio": "Professional portal test profile.",
            "owner": "",
            "notes": "",
            "internal_notes": "",
            "timeline": [],
        }])

    def _seed_professional_account(self, *, full_name, email, status="ACTIVE", professional_category="Concierge", company="", phone="+359888000000", account_id=None):
        payload = {
            "id": account_id or f"professional-{re.sub(r'[^a-z0-9]+', '-', email.lower()).strip('-')}",
            "created_at": "2026-06-10T10:00:00Z",
            "full_name": full_name,
            "email": email,
            "phone": phone,
            "company": company,
            "service_categories": professional_category,
            "status": status,
            "last_login_at": "",
        }
        with app.app_context():
            return app_module._upsert_professional_account(payload)

    def _seed_operations_task(self, task_id, **overrides):
        payload = {
            "id": task_id,
            "request_id": task_id,
            "source_id": task_id,
            "source_type": "TEST",
            "created_at": "2026-06-10T10:00:00Z",
            "updated_at": "2026-06-10T10:00:00Z",
            "title": "Test task",
            "category": "MAINTENANCE",
            "owner_id": "owner-1",
            "owner_name": "Owner One",
            "owner_email": "owner@example.com",
            "property_id": "property-1",
            "property_name": "Sea View Villa",
            "property_location": "Varna",
            "assigned_to": "",
            "assigned_professional_id": "",
            "priority": "NORMAL",
            "status": "NEW",
            "due_date": datetime.now(timezone.utc).date().isoformat(),
            "notes": "",
            "admin_notes": "",
        }
        payload.update(overrides)
        with app.app_context():
            return app_module._upsert_operations_task_from_source(payload)

    def _login_professional_via_magic(self, email):
        with patch.dict(os.environ, self.SMTP_ENV, clear=True), patch("app.smtplib.SMTP", FakeSMTP), patch("app.smtplib.SMTP_SSL", FakeSMTP):
            response = self.client.post("/professionals/login", data={"email": email})

        self.assertEqual(response.status_code, 302)
        self.assertIn("/professionals/login?magic_sent=1", response.headers["Location"])
        self.assertGreaterEqual(len(FakeSMTP.sent_messages), 1)
        message = FakeSMTP.sent_messages[-1]
        login_body = self._email_plaintext(message)
        token_match = re.search(r"/auth/professional-magic/([^\s]+)", login_body)
        self.assertIsNotNone(token_match)
        token = token_match.group(1)
        login_response = self.client.get(f"/auth/professional-magic/{token}")
        self.assertEqual(login_response.status_code, 302)
        self.assertIn("/professionals/dashboard", login_response.headers["Location"])
        return login_response

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

    def test_partner_application_honeypot_blocks_save_and_emails(self):
        payload = {
            **self._partner_payload(),
            "company_website": "https://example.com",
            "website": "https://spam.example.com",
        }

        with patch.dict(os.environ, self.SMTP_ENV, clear=True), patch("app.Thread", ImmediateThread), patch("app.smtplib.SMTP", FakeSMTP), patch("app.smtplib.SMTP_SSL", FakeSMTP):
            response = self.client.post("/partners/apply", data=payload)

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Application received", html)
        self.assertEqual(self._read_jsonl("partner_applications.jsonl"), [])
        self.assertEqual(FakeSMTP.sent_messages, [])

    def test_partner_application_invalid_email_is_rejected_normally(self):
        payload = {
            **self._partner_payload(),
            "company_website": "https://example.com",
            "email": "not-an-email",
            "website": "",
        }

        with patch.dict(os.environ, self.SMTP_ENV, clear=True), patch("app.Thread", ImmediateThread), patch("app.smtplib.SMTP", FakeSMTP), patch("app.smtplib.SMTP_SSL", FakeSMTP):
            response = self.client.post("/partners/apply", data=payload)

        self.assertEqual(response.status_code, 400)
        self.assertIn("This field is required.", response.get_data(as_text=True))
        self.assertEqual(self._read_jsonl("partner_applications.jsonl"), [])
        self.assertEqual(FakeSMTP.sent_messages, [])

    def test_partner_application_rate_limit_blocks_after_threshold(self):
        payload = {
            **self._partner_payload(),
            "company_website": "https://example.com",
            "website": "",
        }

        with patch.dict(os.environ, self.SMTP_ENV, clear=True), patch("app.Thread", ImmediateThread), patch("app.smtplib.SMTP", FakeSMTP), patch("app.smtplib.SMTP_SSL", FakeSMTP):
            for _ in range(5):
                response = self.client.post("/partners/apply", data=payload)
                self.assertEqual(response.status_code, 200)

            blocked_response = self.client.post("/partners/apply", data=payload)

        self.assertEqual(blocked_response.status_code, 200)
        self.assertIn("Application received", blocked_response.get_data(as_text=True))
        self.assertEqual(len(self._read_jsonl("partner_applications.jsonl")), 5)
        self.assertEqual(len(FakeSMTP.sent_messages), 5)

    def test_professional_application_submission_saves_and_emails(self):
        with patch.dict(os.environ, self.SMTP_ENV, clear=True), patch("app.Thread", ImmediateThread), patch("app.smtplib.SMTP", FakeSMTP), patch("app.smtplib.SMTP_SSL", FakeSMTP):
            response = self.client.post("/professionals/apply", data=self._professional_payload())

        self.assertEqual(response.status_code, 200)
        records = self._read_jsonl("professional_applications.jsonl")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["status"], "new")
        self.assertEqual(records[0]["full_name"], "Nikolay Ivanov")
        self.assertEqual(records[0]["professional_category"], "Concierge")
        self.assertEqual(records[0]["timeline"][0]["type"], "PROFESSIONAL_APPLICATION_CREATED")

        self.assertEqual(len(FakeSMTP.sent_messages), 1)
        message = FakeSMTP.sent_messages[0]
        self.assertIsInstance(message, EmailMessage)
        self.assertEqual(message["Subject"], "[BlackSeaConnect] New Professional Application")
        self.assertEqual(message["To"], "concierge@blackseaconnect.com")
        self.assertIn("Nikolay Ivanov", message.get_content())
        self.assertIn("Concierge", message.get_content())
        self.assertIn("/admin/professionals/", message.get_content())

    def test_professional_application_honeypot_blocks_save_and_emails(self):
        payload = {
            **self._professional_payload(),
            "website": "https://spam.example.com",
        }

        with patch.dict(os.environ, self.SMTP_ENV, clear=True), patch("app.Thread", ImmediateThread), patch("app.smtplib.SMTP", FakeSMTP), patch("app.smtplib.SMTP_SSL", FakeSMTP):
            response = self.client.post("/professionals/apply", data=payload)

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Заявлението е получено", html)
        self.assertEqual(self._read_jsonl("professional_applications.jsonl"), [])
        self.assertEqual(FakeSMTP.sent_messages, [])

    def test_professional_application_url_heavy_spam_is_blocked(self):
        payload = {
            **self._professional_payload(),
            "short_bio": "Visit http://a.example.com https://b.example.com https://c.example.com for more.",
        }

        with patch.dict(os.environ, self.SMTP_ENV, clear=True), patch("app.Thread", ImmediateThread), patch("app.smtplib.SMTP", FakeSMTP), patch("app.smtplib.SMTP_SSL", FakeSMTP):
            response = self.client.post("/professionals/apply", data=payload)

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Заявлението е получено", html)
        self.assertEqual(self._read_jsonl("professional_applications.jsonl"), [])
        self.assertEqual(FakeSMTP.sent_messages, [])

    def test_professional_application_crypto_transfer_spam_is_blocked(self):
        payload = {
            **self._professional_payload(),
            "short_bio": "Send USDT or BTC for urgent wire transfer and investment returns.",
        }

        with patch.dict(os.environ, self.SMTP_ENV, clear=True), patch("app.Thread", ImmediateThread), patch("app.smtplib.SMTP", FakeSMTP), patch("app.smtplib.SMTP_SSL", FakeSMTP):
            response = self.client.post("/professionals/apply", data=payload)

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Заявлението е получено", html)
        self.assertEqual(self._read_jsonl("professional_applications.jsonl"), [])
        self.assertEqual(FakeSMTP.sent_messages, [])

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

    def test_professional_category_options_are_localized_without_changing_values(self):
        expected_values = (
            "Concierge",
            "Property Manager",
            "Guest Relations",
            "Maintenance",
            "Hospitality Consultant",
            "Real Estate Professional",
            "Other",
        )
        expected_labels = {
            "bg": (
                "Консиерж",
                "Управител на имоти",
                "Връзки с гости",
                "Поддръжка",
                "Консултант по гостоприемство",
                "Специалист по недвижими имоти",
                "Друго",
            ),
            "en": expected_values,
            "fr": (
                "Conciergerie",
                "Gestionnaire immobilier",
                "Relations clients",
                "Maintenance",
                "Consultant en hôtellerie",
                "Professionnel de l'immobilier",
                "Autre",
            ),
            "ru": (
                "Консьерж",
                "Управляющий недвижимостью",
                "Работа с гостями",
                "Техническое обслуживание",
                "Консультант по гостеприимству",
                "Специалист по недвижимости",
                "Другое",
            ),
        }

        for lang, labels in expected_labels.items():
            response = self.client.get("/professionals/apply", query_string={"lang": lang})
            self.assertEqual(response.status_code, 200)
            page_html = response.get_data(as_text=True)
            options = [
                (html_module.unescape(value), html_module.unescape(label.strip()))
                for value, label in re.findall(
                    r'<option value="([^"]*)"[^>]*>([^<]*)</option>',
                    page_html,
                )
                if value
            ]

            with self.subTest(lang=lang):
                self.assertEqual(tuple(value for value, _ in options), expected_values)
                self.assertEqual(tuple(label for _, label in options), labels)
                if lang in {"bg", "ru"}:
                    self.assertTrue(set(expected_values).isdisjoint(label for _, label in options))

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

    def test_approved_professional_can_log_in_and_see_dashboard_counts(self):
        self._seed_professional_account(
            full_name="Approved Professional",
            email="approved-pro@example.com",
            status="ACTIVE",
            professional_category="Concierge",
            account_id="professional-approved-pro-example-com",
        )
        today = datetime.now(timezone.utc).date()
        tomorrow = today + timedelta(days=1)
        self._seed_operations_task(
            "task-today",
            title="Today task",
            due_date=today.isoformat(),
            status="ASSIGNED",
            assigned_professional_id="professional-approved-pro-example-com",
            assigned_to="Approved Professional",
        )
        self._seed_operations_task(
            "task-upcoming",
            title="Upcoming task",
            due_date=tomorrow.isoformat(),
            status="ASSIGNED",
            assigned_professional_id="professional-approved-pro-example-com",
            assigned_to="Approved Professional",
        )
        self._seed_operations_task(
            "task-completed",
            title="Completed task",
            due_date=today.isoformat(),
            status="DONE",
            assigned_professional_id="professional-approved-pro-example-com",
            assigned_to="Approved Professional",
        )

        self._login_professional_via_magic("approved-pro@example.com")

        dashboard = self.client.get("/professionals/dashboard?lang=en")
        self.assertEqual(dashboard.status_code, 200)
        html = dashboard.get_data(as_text=True)
        self.assertIn("Approved Professional", html)
        self.assertIn("Today task", html)
        self.assertIn("Upcoming task", html)
        self.assertIn("Completed", html)
        self.assertRegex(html, r"Today</span>\s*<strong>1</strong>")
        self.assertRegex(html, r"Upcoming</span>\s*<strong>1</strong>")
        self.assertRegex(html, r"Completed</span>\s*<strong>1</strong>")

    def test_professional_portal_pages_respect_selected_language_and_preserve_links(self):
        self._seed_professional_account(
            full_name="Localized Professional",
            email="localized-pro@example.com",
            status="ACTIVE",
            professional_category="Maintenance",
            company="Localized Coastal Ops",
            account_id="professional-localized-pro-example-com",
        )
        account = app_module._find_professional_account_by_email("localized-pro@example.com")
        self.assertIsNotNone(account)

        today = datetime.now(timezone.utc).date().isoformat()
        self._seed_operations_task(
            "task-localized",
            title="Смяна на филтър",
            category="MAINTENANCE",
            due_date=today,
            status="ASSIGNED",
            priority="HIGH",
            assigned_professional_id=account["id"],
            assigned_to="Localized Professional",
            property_name="Вила Море",
            property_location="Варна",
            owner_name="Собственик",
            owner_email="owner@example.com",
            created_at=f"{today}T09:00:00Z",
            updated_at=f"{today}T09:00:00Z",
        )

        self._login_professional_via_magic("localized-pro@example.com")

        expectations = {
            "bg": {
                "portal": "Портал за професионалисти",
                "tasks": "Задачи",
                "search": "Търси",
                "back": "Обратно към задачите",
                "accept": "Приеми задачата",
                "complete": "Приключи работата",
                "status": "Назначена",
                "priority": "Висок",
                "category": "Поддръжка",
                "no_notifications": "Няма скорошни известия.",
                "no_attachments": "Все още няма качени доказателства.",
            },
            "en": {
                "portal": "Professional portal",
                "tasks": "Tasks",
                "search": "Search",
                "back": "Back to tasks",
                "accept": "Accept task",
                "complete": "Complete work",
                "status": "Assigned",
                "priority": "High",
                "category": "Maintenance",
                "no_notifications": "No recent notifications.",
                "no_attachments": "No evidence uploaded yet.",
            },
            "fr": {
                "portal": "Portail professionnel",
                "tasks": "Tâches",
                "search": "Rechercher",
                "back": "Retour aux tâches",
                "accept": "Accepter la tâche",
                "complete": "Terminer le travail",
                "status": "Attribuée",
                "priority": "Élevée",
                "category": "Maintenance",
                "no_notifications": "Aucune notification récente.",
                "no_attachments": "Aucune preuve téléversée pour le moment.",
            },
            "ru": {
                "portal": "Портал профессионалов",
                "tasks": "Задачи",
                "search": "Поиск",
                "back": "Назад к задачам",
                "accept": "Принять задачу",
                "complete": "Завершить работу",
                "status": "Назначена",
                "priority": "Высокий",
                "category": "Обслуживание",
                "no_notifications": "Недавних уведомлений нет.",
                "no_attachments": "Подтверждения пока не загружены.",
            },
        }

        for lang, expected in expectations.items():
            with self.subTest(lang=lang):
                dashboard = self.client.get(f"/professionals/dashboard?lang={lang}")
                self.assertEqual(dashboard.status_code, 200)
                dashboard_html = dashboard.get_data(as_text=True)
                self.assertIn(f'<html lang="{lang}">', dashboard_html)
                self.assertIn(expected["portal"], dashboard_html)
                self.assertIn(expected["no_notifications"], dashboard_html)
                self.assertIn(expected["status"], dashboard_html)
                self.assertIn(expected["priority"], dashboard_html)
                self.assertIn(expected["category"], dashboard_html)
                self.assertIn(f'href="/professionals/tasks?lang={lang}"', dashboard_html)
                self.assertIn(f'href="/professionals/logout?lang={lang}"', dashboard_html)

                tasks = self.client.get(f"/professionals/tasks?lang={lang}")
                self.assertEqual(tasks.status_code, 200)
                tasks_html = tasks.get_data(as_text=True)
                self.assertIn(f'<html lang="{lang}">', tasks_html)
                self.assertIn(expected["tasks"], tasks_html)
                self.assertIn(expected["search"], tasks_html)
                self.assertIn(expected["status"], tasks_html)
                self.assertIn(expected["priority"], tasks_html)
                self.assertIn(f'href="/professionals/dashboard?lang={lang}"', tasks_html)
                self.assertIn(f'href="/professionals/logout?lang={lang}"', tasks_html)
                self.assertIn(f'href="/professionals/tasks/task-localized?lang={lang}"', tasks_html)
                self.assertIn('input.addEventListener("input", filterCards)', tasks_html)

                localized_status_search = self.client.get(
                    "/professionals/tasks",
                    query_string={"lang": lang, "q": expected["status"]},
                )
                self.assertIn("task-localized", localized_status_search.get_data(as_text=True))
                owner_search = self.client.get(
                    "/professionals/tasks",
                    query_string={"lang": lang, "q": "Собственик"},
                )
                self.assertIn("task-localized", owner_search.get_data(as_text=True))

                detail = self.client.get(f"/professionals/tasks/task-localized?lang={lang}")
                self.assertEqual(detail.status_code, 200)
                detail_html = detail.get_data(as_text=True)
                self.assertIn(f'<html lang="{lang}">', detail_html)
                self.assertIn(expected["back"], detail_html)
                self.assertIn(expected["accept"], detail_html)
                self.assertNotIn(f">{expected['complete']}<", detail_html)
                self.assertIn(expected["status"], detail_html)
                self.assertIn(expected["priority"], detail_html)
                self.assertIn(expected["category"], detail_html)
                self.assertIn(expected["no_attachments"], detail_html)
                self.assertIn(f'href="/professionals/tasks?lang={lang}"', detail_html)
                self.assertIn(f'href="/professionals/dashboard?lang={lang}"', detail_html)
                self.assertIn(f'href="/admin/operations/task-localized?lang={lang}"', detail_html)
                self.assertIn('data-navigation data-address=', detail_html)
                self.assertIn("https://maps.apple.com/", detail_html)
                self.assertIn('name="issue_category"', detail_html)
                self.assertIn('name="issue_severity"', detail_html)

                if lang != "en":
                    for forbidden in [
                        "Professional portal",
                        "View tasks",
                        "No recent notifications.",
                        "Search by property, category, or title",
                        "Back to tasks",
                        "Accept task",
                        "Complete work",
                    ]:
                        self.assertNotIn(forbidden, dashboard_html)
                        self.assertNotIn(forbidden, tasks_html)
                        self.assertNotIn(forbidden, detail_html)

    def test_pending_professional_is_blocked_from_task_views(self):
        self._seed_professional_account(
            full_name="Pending Professional",
            email="pending-pro@example.com",
            status="PENDING",
            professional_category="Maintenance",
            account_id="professional-pending-pro-example-com",
        )
        pending_account = app_module._find_professional_account_by_email("pending-pro@example.com")
        self.assertIsNotNone(pending_account)

        with self.client.session_transaction() as session:
            session["professional_logged_in"] = True
            session["professional_id"] = pending_account["id"]
            session["professional_email"] = pending_account["email"]
            session["professional_name"] = pending_account["full_name"]

        response = self.client.get("/professionals/dashboard")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/professionals/login", response.headers["Location"])
        self.assertIn("access=denied", response.headers["Location"])

        with self.client.session_transaction() as session:
            self.assertFalse(session.get("professional_logged_in"))

    def test_admin_can_assign_task_and_professional_sees_only_assigned_work(self):
        self._seed_professional_account(
            full_name="Assigned Professional",
            email="assigned-pro@example.com",
            status="ACTIVE",
            professional_category="Concierge",
            account_id="professional-assigned-pro-example-com",
        )
        self._seed_professional_account(
            full_name="Other Professional",
            email="other-pro@example.com",
            status="ACTIVE",
            professional_category="Cleaning",
            account_id="professional-other-pro-example-com",
        )
        assigned_account = app_module._find_professional_account_by_email("assigned-pro@example.com")
        other_account = app_module._find_professional_account_by_email("other-pro@example.com")
        self.assertIsNotNone(assigned_account)
        self.assertIsNotNone(other_account)

        today = datetime.now(timezone.utc).date().isoformat()
        self._seed_operations_task("task-assignable", title="Assignable task", due_date=today)
        self._seed_operations_task(
            "task-unassigned",
            title="Other task",
            due_date=today,
            status="ASSIGNED",
            assigned_professional_id=other_account["id"],
            assigned_to="Other Professional",
        )

        with patch.dict(os.environ, {**self.ADMIN_ENV, **self.SMTP_ENV}, clear=True), patch("app.smtplib.SMTP", FakeSMTP), patch("app.smtplib.SMTP_SSL", FakeSMTP):
            response = self.client.post(
                "/admin/operations/task-assignable",
                data={
                    "status": "NEW",
                    "assigned_to": "Assigned Professional",
                    "assigned_professional_id": assigned_account["id"],
                    "priority": "NORMAL",
                    "due_date": today,
                    "admin_notes": "Assign to the approved professional.",
                },
                headers=self._auth_headers(),
            )

        self.assertEqual(response.status_code, 302)
        updated_task = app_module._find_operations_task("task-assignable")
        self.assertEqual(updated_task["assigned_professional_id"], assigned_account["id"])
        self.assertEqual(updated_task["assigned_to"], "Assigned Professional")
        self.assertTrue(any(event["event_type"] == "professional_assigned" for event in app_module._load_operations_task_events("task-assignable")))
        self.assertTrue(FakeSMTP.sent_messages)
        self.assertEqual(FakeSMTP.sent_messages[-1]["To"], "assigned-pro@example.com")

        self._login_professional_via_magic("assigned-pro@example.com")
        tasks_response = self.client.get("/professionals/tasks")
        self.assertEqual(tasks_response.status_code, 200)
        tasks_html = tasks_response.get_data(as_text=True)
        self.assertIn("Assignable task", tasks_html)
        self.assertNotIn("Other task", tasks_html)
        detail_response = self.client.get("/professionals/tasks/task-assignable?lang=en")
        self.assertEqual(detail_response.status_code, 200)
        self.assertIn("Accept task", detail_response.get_data(as_text=True))

        with patch.dict(os.environ, {**self.ADMIN_ENV, **self.SMTP_ENV}, clear=True), patch("app.smtplib.SMTP", FakeSMTP), patch("app.smtplib.SMTP_SSL", FakeSMTP):
            reassigned = self.client.post(
                "/admin/operations/task-assignable",
                data={
                    "status": "ASSIGNED",
                    "assigned_professional_id": other_account["id"],
                    "priority": "NORMAL",
                    "due_date": today,
                    "admin_notes": "Reassigned for availability.",
                },
                headers=self._auth_headers(),
            )
        self.assertEqual(reassigned.status_code, 302)
        reassigned_task = app_module._find_operations_task("task-assignable")
        self.assertEqual(reassigned_task["status"], "ASSIGNED")
        self.assertEqual(reassigned_task["assigned_professional_id"], other_account["id"])
        self.assertEqual(reassigned_task["assigned_to"], "Other Professional")
        self.assertEqual(self.client.get("/professionals/tasks/task-assignable").status_code, 404)

    def test_professional_lifecycle_updates_timeline_calendar_and_admin_notifications(self):
        self._seed_professional_account(
            full_name="Lifecycle Professional",
            email="lifecycle-pro@example.com",
            status="ACTIVE",
            professional_category="Maintenance",
            account_id="professional-lifecycle-pro-example-com",
        )
        account = app_module._find_professional_account_by_email("lifecycle-pro@example.com")
        self.assertIsNotNone(account)
        today = datetime.now(timezone.utc).date().isoformat()
        self._seed_operations_task(
            "task-lifecycle",
            title="Lifecycle task",
            due_date=today,
            status="ASSIGNED",
            assigned_professional_id=account["id"],
            assigned_to="Lifecycle Professional",
        )

        self._login_professional_via_magic("lifecycle-pro@example.com")
        FakeSMTP.sent_messages.clear()

        with patch.dict(os.environ, {**self.SMTP_ENV, "ADMIN_NOTIFICATION_EMAIL": "ops@example.com"}, clear=True), patch("app.smtplib.SMTP", FakeSMTP), patch("app.smtplib.SMTP_SSL", FakeSMTP):
            self.assertEqual(self.client.post("/professionals/tasks/task-lifecycle", data={"task_action": "accept"}).status_code, 302)
            invalid_start = self.client.post("/professionals/tasks/task-lifecycle", data={"task_action": "start"})
            self.assertIn("error=transition_invalid", invalid_start.headers["Location"])
            self.assertEqual(app_module._find_operations_task("task-lifecycle")["status"], "ACCEPTED")
            self.assertEqual(self.client.post("/professionals/tasks/task-lifecycle", data={"task_action": "on_the_way"}).status_code, 302)
            self.assertEqual(self.client.post("/professionals/tasks/task-lifecycle", data={"task_action": "arrived"}).status_code, 302)
            self.assertEqual(self.client.post("/professionals/tasks/task-lifecycle", data={"task_action": "start"}).status_code, 302)
            for index, (checklist_key, _label) in enumerate(app_module.OPERATIONS_TASK_CHECKLIST_ITEMS):
                checklist_response = self.client.post(
                    "/professionals/tasks/task-lifecycle",
                    data={"task_action": "checklist", "checklist_key": checklist_key, "checked": "1"},
                    headers={"X-Requested-With": "XMLHttpRequest"} if index == 0 else {},
                )
                if index == 0:
                    self.assertEqual(checklist_response.status_code, 200)
                    self.assertEqual(checklist_response.get_json()["checked_count"], 1)
                    self.assertEqual(checklist_response.get_json()["progress"], 11)
                    checklist_events = len([
                        event for event in app_module._load_operations_task_events("task-lifecycle")
                        if event["event_type"] == "checklist_updated"
                    ])
                    duplicate_response = self.client.post(
                        "/professionals/tasks/task-lifecycle",
                        data={"task_action": "checklist", "checklist_key": checklist_key, "checked": "1"},
                        headers={"X-Requested-With": "XMLHttpRequest"},
                    )
                    self.assertTrue(duplicate_response.get_json()["ok"])
                    self.assertEqual(len([
                        event for event in app_module._load_operations_task_events("task-lifecycle")
                        if event["event_type"] == "checklist_updated"
                    ]), checklist_events)
                else:
                    self.assertEqual(checklist_response.status_code, 302)
            evidence_response = self.client.post(
                "/professionals/tasks/task-lifecycle",
                data={
                    "task_action": "attachment",
                    "attachment_category": "after_photos",
                    "attachment_file": (io.BytesIO(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=")), "after.png"),
                },
                content_type="multipart/form-data",
            )
            self.assertIn("notice=evidence_uploaded", evidence_response.headers["Location"])
            self.assertEqual(self.client.post("/professionals/tasks/task-lifecycle", data={"task_action": "comment", "note": "Checked keys and refreshed access."}).status_code, 302)
            edited_comment = self.client.post(
                "/professionals/tasks/task-lifecycle",
                data={"task_action": "edit_comment", "note": "Checked keys, refreshed access, and verified the lock."},
            )
            self.assertIn("notice=comment_edited", edited_comment.headers["Location"])
            missing_note = self.client.post(
                "/professionals/tasks/task-lifecycle",
                data={"task_action": "complete", "completed_work": "Guest-ready and cleaned."},
            )
            self.assertIn("error=completion_note_required", missing_note.headers["Location"])
            self.assertEqual(app_module._find_operations_task("task-lifecycle")["status"], "IN_PROGRESS")
            complete_response = self.client.post("/professionals/tasks/task-lifecycle", data={
                "task_action": "complete",
                "completed_work": "Guest-ready and cleaned.",
                "completion_notes": "Guest-ready and cleaned.",
                "note": "Guest-ready and cleaned.",
            })

        self.assertEqual(complete_response.status_code, 302)
        task_record = app_module._find_operations_task("task-lifecycle")
        self.assertIn(task_record["status"], {"DONE", "COMPLETED"})
        events = app_module._load_operations_task_events("task-lifecycle")
        event_types = [event["event_type"] for event in events]
        self.assertIn("professional_accepted", event_types)
        self.assertIn("professional_started", event_types)
        self.assertIn("professional_completed", event_types)
        self.assertIn("professional_comment_added", event_types)
        self.assertIn("professional_comment_edited", event_types)
        self.assertTrue(any(comment.get("edited_at") for comment in task_record["comments"]))

        calendar_events = [event for event in app_module._load_calendar_events() if event.get("operation_task_id") == "task-lifecycle"]
        self.assertTrue(calendar_events)
        self.assertIn(calendar_events[0]["status"], {"DONE", "COMPLETED"})

        notifications = app_module._load_operations_notifications()
        self.assertTrue(any(row["metadata"] == "professional_completion" for row in notifications))
        self.assertTrue(any(message["To"] == "ops@example.com" for message in FakeSMTP.sent_messages))

    def test_professional_issue_validation_and_timeline(self):
        self._seed_professional_account(
            full_name="Issue Professional",
            email="issue-pro@example.com",
            status="ACTIVE",
            professional_category="Maintenance",
            account_id="professional-issue-pro-example-com",
        )
        account = app_module._find_professional_account_by_email("issue-pro@example.com")
        self._seed_operations_task(
            "task-issue",
            title="Issue task",
            status="IN_PROGRESS",
            assigned_professional_id=account["id"],
            assigned_to="Issue Professional",
        )
        self._login_professional_via_magic("issue-pro@example.com")

        empty_comment = self.client.post("/professionals/tasks/task-issue", data={"task_action": "comment", "note": "   "})
        self.assertIn("error=comment_required", empty_comment.headers["Location"])
        self.assertEqual(app_module._find_operations_task("task-issue")["comments"], [])

        blocked_completion = self.client.post(
            "/professionals/tasks/task-issue",
            data={"task_action": "complete", "completed_work": "Done"},
        )
        self.assertIn("error=completion_checklist_required", blocked_completion.headers["Location"])
        self.assertEqual(app_module._find_operations_task("task-issue")["status"], "IN_PROGRESS")

        missing_category = self.client.post(
            "/professionals/tasks/task-issue",
            data={"task_action": "issue", "issue_description": "The supply valve is leaking."},
        )
        self.assertIn("error=issue_category_required", missing_category.headers["Location"])

        reported = self.client.post(
            "/professionals/tasks/task-issue",
            data={
                "task_action": "issue",
                "issue_category": "damage",
                "issue_severity": "high",
                "issue_description": "The supply valve is leaking.\nWater is isolated.",
                "issue_photos": (io.BytesIO(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=")), "issue.png"),
            },
            content_type="multipart/form-data",
        )
        self.assertIn("notice=issue_reported", reported.headers["Location"])
        task_record = app_module._find_operations_task("task-issue")
        self.assertEqual(task_record["status"], "WAITING_OPERATIONS")
        self.assertTrue(any(comment["type"] == "Issue" and "[DAMAGE · HIGH]" in comment["comment"] for comment in task_record["comments"]))
        self.assertTrue(any(item["category"] == "issue_photo" for item in task_record["attachments"]))
        self.assertTrue(any(event["event_type"] == "professional_issue_reported" for event in app_module._load_operations_task_events("task-issue")))

    def test_professional_arrival_workflow_completion_report_and_evidence(self):
        self._seed_professional_account(
            full_name="Workflow Professional",
            email="workflow-pro@example.com",
            status="ACTIVE",
            professional_category="Maintenance",
            account_id="professional-workflow-pro-example-com",
        )
        account = app_module._find_professional_account_by_email("workflow-pro@example.com")
        self.assertIsNotNone(account)
        today = datetime.now(timezone.utc).date().isoformat()
        self._seed_operations_task(
            "task-workflow",
            title="Workflow task",
            due_date=today,
            status="ASSIGNED",
            assigned_professional_id=account["id"],
            assigned_to="Workflow Professional",
        )

        self._login_professional_via_magic("workflow-pro@example.com")
        FakeSMTP.sent_messages.clear()

        with patch.dict(os.environ, {**self.SMTP_ENV, "ADMIN_NOTIFICATION_EMAIL": "ops@example.com"}, clear=True), patch("app.smtplib.SMTP", FakeSMTP), patch("app.smtplib.SMTP_SSL", FakeSMTP):
            self.assertEqual(self.client.post("/professionals/tasks/task-workflow", data={"task_action": "accept"}).status_code, 302)
            self.assertEqual(self.client.post("/professionals/tasks/task-workflow", data={"task_action": "on_the_way"}).status_code, 302)
            self.assertEqual(self.client.post("/professionals/tasks/task-workflow", data={"task_action": "arrived"}).status_code, 302)
            self.assertEqual(self.client.post("/professionals/tasks/task-workflow", data={"task_action": "start"}).status_code, 302)
            self.assertEqual(self.client.post("/professionals/tasks/task-workflow", data={"task_action": "pause", "note": "Waiting for a spare key."}).status_code, 302)
            self.assertEqual(self.client.post("/professionals/tasks/task-workflow", data={"task_action": "resume"}).status_code, 302)
            for checklist_key, _label in app_module.OPERATIONS_TASK_CHECKLIST_ITEMS:
                self.assertEqual(self.client.post(
                    "/professionals/tasks/task-workflow",
                    data={"task_action": "checklist", "checklist_key": checklist_key, "checked": "1"},
                ).status_code, 302)
            upload_response = self.client.post(
                "/professionals/tasks/task-workflow",
                data={
                    "task_action": "attachment",
                    "attachment_category": "after_photos",
                    "attachment_files": [
                        (io.BytesIO(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=")), "after-one.png"),
                        (io.BytesIO(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=")), "after-two.png"),
                    ],
                },
                content_type="multipart/form-data",
            )
            self.assertIn("notice=evidence_uploaded", upload_response.headers["Location"])
            self.assertEqual(self.client.post(
                "/professionals/tasks/task-workflow",
                data={
                    "task_action": "complete",
                    "completed_work": "Replaced the filter and verified the unit.",
                    "materials_used": "Filter cartridge, cleaning spray",
                    "time_spent_minutes": "95",
                    "recommendations": "Schedule a follow-up inspection next month.",
                    "follow_up_needed": "None",
                    "completion_notes": "Closeout notes saved.",
                },
            ).status_code, 302)

        task_record = app_module._find_operations_task("task-workflow")
        self.assertEqual(task_record["status"], "COMPLETED")
        self.assertEqual(task_record["completion_report"]["completed_work"], "Replaced the filter and verified the unit.")
        self.assertEqual(task_record["completion_report"]["materials_used"], "Filter cartridge, cleaning spray")
        self.assertEqual(task_record["completion_report"]["time_spent_minutes"], "95")
        self.assertEqual(task_record["completion_report"]["recommendations"], "Schedule a follow-up inspection next month.")
        self.assertEqual(task_record["completion_report"]["follow_up_needed"], "None")
        self.assertEqual(sum(1 for item in task_record["attachments"] if item.get("category") == "after_photos"), 2)
        evidence = next(item for item in task_record["attachments"] if item.get("category") == "after_photos")
        evidence_response = self.client.get(evidence["url"])
        self.assertEqual(evidence_response.status_code, 200)
        self.assertEqual(evidence_response.mimetype, "image/png")
        evidence_response.close()

        events = app_module._load_operations_task_events("task-workflow")
        event_types = [event["event_type"] for event in events]
        self.assertIn("professional_accepted", event_types)
        self.assertIn("professional_on_the_way", event_types)
        self.assertIn("professional_arrived", event_types)
        self.assertIn("professional_paused", event_types)
        self.assertIn("professional_resumed", event_types)
        self.assertIn("professional_completed", event_types)
        self.assertIn("attachment_added", event_types)
        self.assertIn("completion_report_updated", event_types)
        self.assertNotIn("workflow_transitioned", event_types)

        calendar_events = [event for event in app_module._load_calendar_events() if event.get("operation_task_id") == "task-workflow"]
        self.assertTrue(calendar_events)
        self.assertEqual(calendar_events[0]["status"], "COMPLETED")

        notifications = app_module._load_operations_notifications()
        self.assertTrue(any(row["metadata"] == "professional_workflow" for row in notifications))
        self.assertTrue(any(row["metadata"] == "professional_completion" for row in notifications))
        self.assertTrue(any(message["To"] == "ops@example.com" for message in FakeSMTP.sent_messages))

        detail_html = self.client.get("/professionals/tasks/task-workflow?lang=en").get_data(as_text=True)
        self.assertLess(detail_html.index("Professional completed task"), detail_html.index("Professional accepted task"))
        self.assertIn("data-evidence-form", detail_html)
        self.assertIn("new DataTransfer()", detail_html)
        self.assertIn('xhr.upload.addEventListener("progress"', detail_html)

    def test_admin_created_operation_end_to_end_is_secure_idempotent_and_owner_visible(self):
        owner = app_module._upsert_owner_account({
            "id": "owner-lifecycle",
            "created_at": "2026-07-18T08:00:00Z",
            "full_name": "Lifecycle Owner",
            "email": "lifecycle-owner@example.com",
            "phone": "+359888111111",
            "property_type": "Villa",
            "city": "Varna",
            "property_name": "Lifecycle Villa",
            "number_of_units": 1,
            "status": "ACTIVE",
            "language": "en",
        })
        other_owner = app_module._upsert_owner_account({
            "id": "owner-unrelated",
            "created_at": "2026-07-18T08:01:00Z",
            "full_name": "Unrelated Owner",
            "email": "unrelated-owner@example.com",
            "phone": "+359888222222",
            "property_type": "Apartment",
            "city": "Burgas",
            "property_name": "Other Home",
            "number_of_units": 1,
            "status": "ACTIVE",
            "language": "en",
        })
        self.assertIsNotNone(owner)
        self.assertIsNotNone(other_owner)
        self.assertTrue(app_module._save_owner_properties([{
            "id": "property-lifecycle",
            "owner_id": owner["id"],
            "created_at": "2026-07-18T08:02:00Z",
            "name": "Lifecycle Villa",
            "property_type": "Villa",
            "location": "Varna",
            "bedrooms": 2,
            "bathrooms": 2,
            "guest_capacity": 4,
            "operating_mode": "year-round",
            "status": "ACTIVE",
        }]))
        professional = self._seed_professional_account(
            full_name="Lifecycle E2E Professional",
            email="lifecycle-e2e-pro@example.com",
            status="ACTIVE",
            professional_category="Maintenance",
            account_id="professional-lifecycle-e2e",
        )
        other_professional = self._seed_professional_account(
            full_name="Unrelated Professional",
            email="unrelated-e2e-pro@example.com",
            status="ACTIVE",
            professional_category="Cleaning",
            account_id="professional-unrelated-e2e",
        )

        with patch.dict(os.environ, self.ADMIN_ENV, clear=True):
            self.client.get("/admin/operations/new", headers=self._auth_headers())
            with self.client.session_transaction() as session_data:
                csrf_token = session_data["_admin_csrf_token"]
            created_response = self.client.post(
                "/admin/operations/new",
                data={
                    "csrf_token": csrf_token,
                    "property_id": "property-lifecycle",
                    "category": "MAINTENANCE",
                    "title": "Canonical lifecycle operation",
                    "priority": "HIGH",
                    "due_date": datetime.now(timezone.utc).date().isoformat(),
                    "assigned_professional_id": professional["id"],
                    "notes": "Internal admin note that owners must not receive.",
                },
                headers=self._auth_headers(),
            )
        self.assertEqual(created_response.status_code, 302)
        task_id = created_response.headers["Location"].rstrip("/").rsplit("/", 1)[-1]
        self.assertEqual(app_module._find_operations_task(task_id)["status"], "ASSIGNED")
        with patch.dict(os.environ, self.ADMIN_ENV, clear=True):
            invalid_admin_transition = self.client.post(
                f"/admin/operations/{task_id}/status",
                json={"status": "IN_PROGRESS"},
                headers=self._auth_headers(),
            )
        self.assertEqual(invalid_admin_transition.status_code, 409)
        self.assertEqual(invalid_admin_transition.get_json()["error"], "transition_invalid")
        self.assertEqual(app_module._find_operations_task(task_id)["status"], "ASSIGNED")

        with self.client.session_transaction() as session_data:
            session_data[app_module.PROFESSIONAL_SESSION_LOGGED_IN_KEY] = True
            session_data[app_module.PROFESSIONAL_SESSION_ID_KEY] = other_professional["id"]
            session_data[app_module.PROFESSIONAL_SESSION_EMAIL_KEY] = other_professional["email"]
        unauthorized = self.client.post(
            f"/professionals/tasks/{task_id}",
            data={"task_action": "accept"},
        )
        self.assertEqual(unauthorized.status_code, 404)
        self.assertEqual(app_module._find_operations_task(task_id)["status"], "ASSIGNED")

        self._login_professional_via_magic(professional["email"])
        visible_tasks = self.client.get("/professionals/tasks?lang=en").get_data(as_text=True)
        self.assertIn("Canonical lifecycle operation", visible_tasks)
        invalid_transition = self.client.post(
            f"/professionals/tasks/{task_id}",
            data={"task_action": "start"},
        )
        self.assertIn("error=transition_invalid", invalid_transition.headers["Location"])

        for action in ("accept", "on_the_way", "arrived", "start"):
            response = self.client.post(
                f"/professionals/tasks/{task_id}",
                data={"task_action": action},
            )
            self.assertEqual(response.status_code, 302)

        incomplete = self.client.post(
            f"/professionals/tasks/{task_id}",
            data={
                "task_action": "complete",
                "completed_work": "Maintenance completed.",
                "completion_notes": "Verified safe operation.",
            },
        )
        self.assertIn("error=completion_checklist_required", incomplete.headers["Location"])
        self.assertEqual(app_module._find_operations_task(task_id)["status"], "IN_PROGRESS")

        for checklist_key, _label in app_module.OPERATIONS_TASK_CHECKLIST_ITEMS:
            self.client.post(
                f"/professionals/tasks/{task_id}",
                data={"task_action": "checklist", "checklist_key": checklist_key, "checked": "1"},
            )
        upload = self.client.post(
            f"/professionals/tasks/{task_id}",
            data={
                "task_action": "attachment",
                "attachment_category": "after_photos",
                "attachment_file": (
                    io.BytesIO(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=")),
                    "completed.png",
                ),
            },
            content_type="multipart/form-data",
        )
        self.assertIn("notice=evidence_uploaded", upload.headers["Location"])
        completion_payload = {
            "task_action": "complete",
            "completed_work": "Maintenance completed and tested.",
            "materials_used": "Replacement part",
            "time_spent_minutes": "60",
            "recommendations": "No follow-up required.",
            "follow_up_needed": "None",
            "completion_notes": "Verified safe operation.",
        }
        completed = self.client.post(f"/professionals/tasks/{task_id}", data=completion_payload)
        self.assertIn("notice=task_completed", completed.headers["Location"])
        task = app_module._find_operations_task(task_id)
        self.assertEqual(task["status"], "COMPLETED")

        event_types = [event["event_type"] for event in app_module._load_operations_task_events(task_id)]
        for event_type in (
            "professional_assigned",
            "professional_accepted",
            "professional_on_the_way",
            "professional_arrived",
            "professional_started",
            "professional_completed",
        ):
            self.assertEqual(event_types.count(event_type), 1)
        self.assertNotIn("completed", event_types)

        event_count = len(event_types)
        notification_count = len(app_module._load_operations_notifications())
        duplicate = self.client.post(f"/professionals/tasks/{task_id}", data=completion_payload)
        self.assertIn("notice=task_completed", duplicate.headers["Location"])
        self.assertEqual(len(app_module._load_operations_task_events(task_id)), event_count)
        self.assertEqual(len(app_module._load_operations_notifications()), notification_count)

        with patch.dict(os.environ, self.ADMIN_ENV, clear=True):
            board_html = self.client.get("/admin/operations", headers=self._auth_headers()).get_data(as_text=True)
        self.assertRegex(board_html, r"Completed Tasks</span>\s*<strong>1</strong>")
        owner_events = app_module._load_owner_activity_events(owner["id"])
        property_events = app_module._load_property_activity_events("property-lifecycle")
        self.assertEqual(sum(event["event_type"] == "operation_completed" for event in owner_events), 1)
        self.assertEqual(sum(event["event_type"] == "operation_completed" for event in property_events), 1)
        self.assertNotIn("Internal admin note", " ".join(event["detail"] for event in property_events))

        evidence = task["attachments"][0]
        with self.client.session_transaction() as session_data:
            session_data.clear()
            session_data[app_module.OWNER_SESSION_LOGGED_IN_KEY] = True
            session_data[app_module.OWNER_SESSION_ID_KEY] = owner["id"]
            session_data[app_module.OWNER_SESSION_EMAIL_KEY] = owner["email"]
        for language, heading, completion_label in (
            ("bg", "Последни оперативни актуализации", "Операцията е завършена"),
            ("en", "Recent operational updates", "Operation completed"),
            ("fr", "Mises à jour opérationnelles récentes", "Opération terminée"),
        ):
            owner_property_html = self.client.get(
                f"/owners/properties/property-lifecycle?lang={language}"
            ).get_data(as_text=True)
            self.assertIn(heading, owner_property_html)
            self.assertIn(completion_label, owner_property_html)
            self.assertNotIn("Internal admin note", owner_property_html)

        with self.client.session_transaction() as session_data:
            session_data.clear()
            session_data[app_module.OWNER_SESSION_LOGGED_IN_KEY] = True
            session_data[app_module.OWNER_SESSION_ID_KEY] = other_owner["id"]
            session_data[app_module.OWNER_SESSION_EMAIL_KEY] = other_owner["email"]
        self.assertEqual(
            self.client.get("/owners/properties/property-lifecycle?lang=en").status_code,
            404,
        )
        self.assertEqual(self.client.get(evidence["url"]).status_code, 404)

    def test_operations_task_evidence_admin_upload_metadata_timeline_and_delete(self):
        self._seed_operations_task("task-admin-evidence")
        png_bytes = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=")
        pdf_bytes = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\n%%EOF"
        with patch.dict(os.environ, self.ADMIN_ENV, clear=True):
            upload = self.client.post(
                "/admin/operations/task-admin-evidence",
                data={
                    "task_action": "attachment",
                    "attachment_category": "inspection_report",
                    "evidence_photos": [(io.BytesIO(png_bytes), "before.png"), (io.BytesIO(png_bytes), "after.png")],
                    "evidence_documents": [(io.BytesIO(pdf_bytes), "inspection.pdf")],
                },
                headers=self._auth_headers(),
                content_type="multipart/form-data",
            )
            self.assertEqual(upload.status_code, 302)
            self.assertIn("evidence_notice=uploaded", upload.headers["Location"])

            task = app_module._find_operations_task("task-admin-evidence")
            self.assertEqual(len(task["attachments"]), 3)
            required_fields = {
                "task_id", "operation_id", "property_id", "uploader_id", "uploader_role",
                "category", "filename", "original_filename", "mime_type", "file_size", "upload_timestamp",
            }
            for attachment in task["attachments"]:
                self.assertTrue(required_fields.issubset(attachment))
                self.assertEqual(attachment["task_id"], "task-admin-evidence")
                self.assertEqual(attachment["operation_id"], "task-admin-evidence")
                self.assertEqual(attachment["property_id"], "property-1")
                self.assertEqual(attachment["uploader_role"], "admin")
                self.assertGreater(attachment["file_size"], 0)

            events = [event for event in app_module._load_operations_task_events("task-admin-evidence") if event["event_type"] == "attachment_added"]
            self.assertEqual(events[0]["title"], "3 files uploaded")
            self.assertEqual(events[0]["detail"], "Attachment count: 3")

            image_attachment = next(item for item in task["attachments"] if item["mime_type"] == "image/png")
            pdf_attachment = next(item for item in task["attachments"] if item["mime_type"] == "application/pdf")
            image_preview = self.client.get(image_attachment["url"], headers=self._auth_headers())
            self.assertEqual(image_preview.status_code, 200)
            self.assertEqual(image_preview.mimetype, "image/png")
            image_preview.close()
            pdf_download = self.client.get(pdf_attachment["download_url"], headers=self._auth_headers())
            self.assertEqual(pdf_download.status_code, 200)
            self.assertEqual(pdf_download.mimetype, "application/pdf")
            self.assertIn("attachment", pdf_download.headers.get("Content-Disposition", ""))
            pdf_download.close()

            invalid = self.client.post(
                "/admin/operations/task-admin-evidence",
                data={"task_action": "attachment", "attachment_category": "other", "evidence_documents": (io.BytesIO(b"plain text"), "notes.txt")},
                headers=self._auth_headers(),
                content_type="multipart/form-data",
            )
            self.assertIn("evidence_error=evidence_invalid_type", invalid.headers["Location"])

            french_detail = self.client.get("/admin/operations/task-admin-evidence?lang=fr", headers=self._auth_headers()).get_data(as_text=True)
            self.assertIn("Pièce jointe au rapport de clôture", french_detail)
            self.assertIn("inspection.pdf", french_detail)

            with self.client.session_transaction() as session_data:
                session_data["_admin_csrf_token"] = "evidence-csrf"
            deleted = self.client.post(
                f"/admin/operations/task-admin-evidence/attachments/{pdf_attachment['id']}/delete",
                data={"csrf_token": "evidence-csrf"},
                headers=self._auth_headers(),
            )
            self.assertEqual(deleted.status_code, 302)
            self.assertEqual(len(app_module._find_operations_task("task-admin-evidence")["attachments"]), 2)

            heic_bytes = b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00heicmif1"
            heic_upload = self.client.post(
                "/admin/operations/task-admin-evidence",
                data={
                    "task_action": "attachment",
                    "attachment_category": "damage_evidence",
                    "evidence_photos": (io.BytesIO(heic_bytes), "mobile-camera.heic", "image/heic"),
                },
                headers=self._auth_headers(),
                content_type="multipart/form-data",
            )
            self.assertIn("evidence_notice=uploaded", heic_upload.headers["Location"])
            self.assertTrue(any(item["mime_type"] == "image/heic" for item in app_module._find_operations_task("task-admin-evidence")["attachments"]))

    def test_operations_task_evidence_professional_ownership_and_owner_read_only(self):
        professional = self._seed_professional_account(
            full_name="Evidence Professional",
            email="evidence-pro@example.com",
            account_id="professional-evidence",
        )
        self._seed_operations_task(
            "task-evidence-permissions",
            assigned_professional_id=professional["id"],
            assigned_to="Evidence Professional",
        )
        png_bytes = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=")
        with patch.dict(os.environ, self.ADMIN_ENV, clear=True):
            self.client.post(
                "/admin/operations/task-evidence-permissions",
                data={"task_action": "attachment", "attachment_category": "invoice", "evidence_photos": (io.BytesIO(png_bytes), "admin.png")},
                headers=self._auth_headers(),
                content_type="multipart/form-data",
            )
        admin_attachment = app_module._find_operations_task("task-evidence-permissions")["attachments"][0]

        with app.app_context():
            owner = app_module._upsert_owner_account({
                "id": "owner-1", "email": "owner@example.com", "full_name": "Owner One", "phone": "+359888111111",
                "property_type": "Apartment", "city": "Varna", "property_name": "Sea View Villa", "number_of_units": 1,
                "notes": "", "status": "ACTIVE", "language": "en",
            })
        with self.client.session_transaction() as session_data:
            session_data[app_module.OWNER_SESSION_LOGGED_IN_KEY] = True
            session_data[app_module.OWNER_SESSION_ID_KEY] = owner["id"]
            session_data[app_module.OWNER_SESSION_EMAIL_KEY] = owner["email"]
        owner_preview = self.client.get(admin_attachment["url"])
        self.assertEqual(owner_preview.status_code, 200)
        owner_preview.close()
        with patch.dict(os.environ, self.ADMIN_ENV, clear=True):
            self.assertEqual(self.client.post(f"/admin/operations/task-evidence-permissions/attachments/{admin_attachment['id']}/delete").status_code, 401)

        with self.client.session_transaction() as session_data:
            session_data.clear()
            session_data[app_module.PROFESSIONAL_SESSION_LOGGED_IN_KEY] = True
            session_data[app_module.PROFESSIONAL_SESSION_ID_KEY] = professional["id"]
            session_data[app_module.PROFESSIONAL_SESSION_EMAIL_KEY] = professional["email"]
        forbidden = self.client.post(f"/professionals/tasks/task-evidence-permissions/attachments/{admin_attachment['id']}/delete")
        self.assertEqual(forbidden.status_code, 403)

        own_upload = self.client.post(
            "/professionals/tasks/task-evidence-permissions",
            data={"task_action": "attachment", "attachment_category": "after_photos", "attachment_file": (io.BytesIO(png_bytes), "professional.png")},
            content_type="multipart/form-data",
        )
        self.assertIn("notice=evidence_uploaded", own_upload.headers["Location"])
        task = app_module._find_operations_task("task-evidence-permissions")
        own_attachment = next(item for item in task["attachments"] if item["uploader_id"] == professional["id"])
        own_delete = self.client.post(f"/professionals/tasks/task-evidence-permissions/attachments/{own_attachment['id']}/delete")
        self.assertIn("notice=evidence_deleted", own_delete.headers["Location"])
        remaining_ids = {item["id"] for item in app_module._find_operations_task("task-evidence-permissions")["attachments"]}
        self.assertNotIn(own_attachment["id"], remaining_ids)
        self.assertIn(admin_attachment["id"], remaining_ids)
