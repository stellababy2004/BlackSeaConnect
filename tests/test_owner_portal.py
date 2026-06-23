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

    def _login_owner_via_magic(self, email="owner@blackseaconnect.com", seed_property=True):
        self._seed_owner_account(email=email)
        if seed_property:
            self._seed_owner_property(owner_id="owner-1", owner_email=email)
        response = self.client.post("/owners/login", data={"email": email})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/owners/login?magic_sent=1")

        tokens = self._read_jsonl("owner_magic_tokens.jsonl")
        self.assertTrue(tokens)
        token = tokens[-1]["token"]

        login_response = self.client.get(f"/auth/owner-magic/{token}")
        self.assertEqual(login_response.status_code, 302)
        self.assertEqual(login_response.headers["Location"], "/owners/dashboard")
        return login_response

    def _request_owner_magic_link(self, email="owner@blackseaconnect.com", seed_property=False):
        self._seed_owner_account(email=email)
        if seed_property:
            self._seed_owner_property(owner_id="owner-1", owner_email=email)
        response = self.client.post("/owners/login", data={"email": email})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/owners/login?magic_sent=1")

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

    def _seed_owner_account(self, email="owner@blackseaconnect.com"):
        self._seed_jsonl("owner_accounts.jsonl", [{
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
        }])

    def test_owner_registration_creates_account_and_sends_magic_flow(self):
        with patch.dict(os.environ, self.SMTP_ENV, clear=True), patch("app.Thread", ImmediateThread), patch("app.smtplib.SMTP", FakeSMTP), patch("app.smtplib.SMTP_SSL", FakeSMTP):
            response = self.client.post("/owners/register", data=self._owner_payload())

        self.assertEqual(response.status_code, 302)
        self.assertIn("/owners/login?registered=1&magic_sent=1", response.headers["Location"])

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
        self.assertEqual(len(FakeSMTP.sent_messages), 1)
        message = FakeSMTP.sent_messages[0]
        self.assertEqual(message["Subject"], "BlackSea Connect — Вход в портала за собственици")
        self.assertTrue(message.is_multipart())
        html_part = message.get_body(preferencelist=("html",))
        self.assertIsNotNone(html_part)
        self.assertIn("Влезте в портала", html_part.get_content())

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
        self.assertEqual(response.headers["Location"], "/owners/dashboard?property_added=1")

        properties = self._read_jsonl("owner_properties.jsonl")
        self.assertEqual(len(properties), 1)
        self.assertEqual(properties[0]["name"], "Sea View Villa")
        self.assertEqual(properties[0]["location"], "Varna, Bulgaria")
        self.assertEqual(properties[0]["operating_mode"], "year-round")

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
        self._login_owner_via_magic(seed_property=False)

        response = self.client.get("/owners/dashboard")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Sea View Villa", html)
        self.assertIn("Marina Apartment", html)
        self.assertIn("Sveti Vlas", html)
        self.assertIn("seasonal", html.lower())

    def test_owner_dashboard_shows_onboarding_progress_after_first_property(self):
        self._seed_owner_account()
        self._seed_owner_property()
        self._login_owner_via_magic(seed_property=False)

        response = self.client.get("/owners/dashboard")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("ownerOnboardingProgressTitle", html)
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
            'data-i18n="ownerDashboardLogout"',
        ]:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, html)
        self.assertIn('body class="owner-portal-page owner-portal-dashboard-page owner-dashboard-page"', html)
        self.assertIn("owner-dashboard-page", html)
        self.assertIn("owner-dashboard-masthead", html)
        self.assertIn("owner-dashboard-main", html)
        self.assertIn("owner-dashboard-section", html)
        self.assertIn("owner-kpi-card--summary", html)
        self.assertIn("owner-portal-card--performance", html)
        self.assertIn("owner-timeline-item", html)
        self.assertIn("owner-request-1", html)
        self.assertNotRegex(html, r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")

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
                    self.assertIn('body class="owner-portal-page owner-property-new-page"', html, msg=path)
                elif path == "/owners/dashboard":
                    self.assertIn('data-i18n="ownerDashboardPropertyOverview"', html, msg=path)
                    self.assertIn('body class="owner-portal-page owner-portal-dashboard-page owner-dashboard-page"', html, msg=path)
                elif path == "/owners/request-service":
                    self.assertIn('data-i18n="ownerRequestServiceCategoryLabel"', html, msg=path)
                    self.assertIn('body class="owner-portal-page owner-request-service-page"', html, msg=path)

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

        self.assertEqual(response.status_code, 400)
        html = response.get_data(as_text=True)
        self.assertIn('data-i18n="ownerAccountNotFoundError"', html)
        self.assertIn('body class="owner-portal-page owner-login-page"', html)

    def test_owner_login_sends_magic_flow(self):
        self._seed_owner_account()
        with patch.dict(os.environ, self.SMTP_ENV, clear=True), patch("app.Thread", ImmediateThread), patch("app.smtplib.SMTP", FakeSMTP), patch("app.smtplib.SMTP_SSL", FakeSMTP):
            response = self.client.post("/owners/login", data=self._demo_login_payload())

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/owners/login?magic_sent=1")

        tokens = self._read_jsonl("owner_magic_tokens.jsonl")
        self.assertEqual(len(tokens), 1)
        self.assertEqual(tokens[0]["email"], "owner@blackseaconnect.com")
        self.assertEqual(len(FakeSMTP.sent_messages), 1)

    def test_owner_magic_link_logs_user_in(self):
        _, token = self._request_owner_magic_link()

        response = self.client.get(f"/auth/owner-magic/{token}")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/owners/dashboard")
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
        self.assertEqual(response.headers["Location"], "/owners/login?expired_token=1")
        self.assertEqual(self._read_jsonl("owner_magic_tokens.jsonl"), [])

    def test_owner_magic_link_rejects_invalid_token(self):
        self._seed_owner_account()

        response = self.client.get("/auth/owner-magic/does-not-exist")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/owners/login?invalid_token=1")

    def test_owner_logout_clears_session(self):
        self._login_owner_via_magic()

        response = self.client.get("/owners/logout")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/owners/login")
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
            "Започнете с един имот, един портал за собственици и един доверен местен работен поток.",
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

        with patch.dict(os.environ, self.SMTP_ENV, clear=True), patch("app.Thread", ImmediateThread), patch("app.smtplib.SMTP", FakeSMTP), patch("app.smtplib.SMTP_SSL", FakeSMTP):
            response = self.client.post("/owners/request-service", data=self._service_request_payload())

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/owners/dashboard")

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
