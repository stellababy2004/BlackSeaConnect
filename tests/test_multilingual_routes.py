import json
import os
import re
import sqlite3
import subprocess
import shutil
import textwrap
import unittest
import html as html_lib
import sys
from pathlib import Path
from unittest.mock import patch

from app import app, _load_network_providers


class FakeSMTP:
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
        return None


class MultilingualRouteTests(unittest.TestCase):
    @staticmethod
    def _visible_text(rendered_html):
        visible = re.sub(
            r"<script\b[^>]*>.*?</script>",
            " ",
            rendered_html,
            flags=re.IGNORECASE | re.DOTALL,
        )
        visible = re.sub(
            r"<style\b[^>]*>.*?</style>",
            " ",
            visible,
            flags=re.IGNORECASE | re.DOTALL,
        )
        visible = re.sub(
            r"<head\b[^>]*>.*?</head>",
            " ",
            visible,
            flags=re.IGNORECASE | re.DOTALL,
        )
        visible = re.sub(r"<[^>]+>", " ", visible)
        return re.sub(r"\s+", " ", html_lib.unescape(visible)).strip()

    def setUp(self):
        self._cwd = os.getcwd()
        self._tmpdir = Path(self._cwd) / f".tmp_multilingual_routes_tests_{id(self)}"
        self._tmpdir.mkdir(exist_ok=True)
        os.chdir(self._tmpdir)
        self.owner_db_path = self._tmpdir / "data" / "blacksea_owner.db"
        self._env_patcher = patch.dict(
            os.environ,
            {"OWNER_DB_PATH": str(self.owner_db_path)},
        )
        self._env_patcher.start()
        app.config["TESTING"] = True
        self.client = app.test_client()

    def tearDown(self):
        self._env_patcher.stop()
        os.chdir(self._cwd)
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def _i18n_module_loader_js(self):
        return textwrap.dedent(
            """
            globalThis.window = sandbox.window;
            globalThis.document = sandbox.document || globalThis.document || {};
            const moduleFiles = fs.readdirSync('static/js/i18n')
              .filter((file) => file.endsWith('.js') && file !== 'index.js')
              .sort();
            const moduleSrc = moduleFiles
              .map((file) => fs.readFileSync(`static/js/i18n/${file}`, 'utf8'))
              .join('\\n');
            eval(moduleSrc);
            eval(fs.readFileSync('static/js/i18n/index.js', 'utf8'));
            """
        )

    def _login_owner(self):
        data_dir = Path("data")
        data_dir.mkdir(exist_ok=True)
        (data_dir / "owner_accounts.jsonl").write_text(
            json.dumps(
                {
                    "id": "owner-1",
                    "created_at": "2026-06-15T10:00:00Z",
                    "full_name": "Elena Petrova",
                    "email": "owner@example.com",
                    "phone": "+359888111222",
                    "property_type": "Villa",
                    "city": "Varna",
                    "property_name": "Sea View Villa",
                    "number_of_units": 2,
                    "notes": "",
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        smtp_env = {
            "SMTP_HOST": "smtp.example.com",
            "SMTP_PORT": "587",
            "SMTP_FROM": "BlackSea Connect <concierge@blackseaconnect.com>",
            "SMTP_USERNAME": "smtp-user",
            "SMTP_PASSWORD": "smtp-pass",
            "OWNER_DB_PATH": str(self.owner_db_path),
        }
        with patch.dict(os.environ, smtp_env, clear=True), patch("app.smtplib.SMTP", FakeSMTP), patch("app.smtplib.SMTP_SSL", FakeSMTP):
            self.client.post("/owners/login", data={"email": "owner@example.com"})
        conn = sqlite3.connect(self.owner_db_path)
        try:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT token FROM owner_magic_tokens ORDER BY created_at DESC, token DESC LIMIT 1"
            ).fetchone()
            token = row["token"]
        finally:
            conn.close()
        return self.client.get(f"/auth/owner-magic/{token}")

    def test_supported_routes_return_200_and_language_controls(self):
        routes = {
            "/": "homeLanguageSwitcherLabel",
            "/services": "languageSwitcherLabel",
            "/demo/operations": "languageSwitcherLabel",
            "/guest/a-302": "languageSwitcherLabel",
            "/partners": "languageSwitcherLabel",
            "/professionals": "languageSwitcherLabel",
            "/professionals/apply": "languageSwitcherLabel",
            "/pilot-access": "languageSwitcherLabel",
            "/network": "languageSwitcherLabel",
            "/owners/login": "languageSwitcherLabel",
            "/owners/dashboard": "languageSwitcherLabel",
            "/owners/property/new": "languageSwitcherLabel",
            "/owners/properties": "languageSwitcherLabel",
            "/owners/request-service": "languageSwitcherLabel",
        }

        owner_routes = {"/owners/dashboard", "/owners/property/new", "/owners/properties", "/owners/request-service"}

        for path, switcher_key in routes.items():
            for lang in ("bg", "en", "fr", "ru"):
                with self.subTest(path=path, lang=lang):
                    if path in owner_routes:
                        self._login_owner()

                    response = self.client.get(f"{path}?lang={lang}")
                    self.assertEqual(response.status_code, 200)
                    html = response.get_data(as_text=True)
                    self.assertIn(f'<html lang="{lang}">', html)
                    self.assertIn('<a class="language-switcher__button', html)
                    expected_href = f'href="{path if path != "/" else "/"}?lang={lang}"'
                    self.assertIn(expected_href, html)
                    self.assertIn('data-lang-switch="bg"', html)
                    self.assertIn('data-lang-switch="en"', html)
                    self.assertIn('data-lang-switch="fr"', html)
                    self.assertIn('data-lang-switch="ru"', html)
                    self.assertIn(f"data-i18n-attr=\"aria-label:{switcher_key}\"", html)
                    self.assertIn("/static/js/translations.js", html)
                    self.assertIn("/static/js/i18n.js", html)

    def test_owner_login_feature_badges_and_cta_follow_selected_language(self):
        expected = {
            "bg": {
                "chips": [
                    "Поверителен портал",
                    "Спокойна видимост на имота",
                    "Заявки за услуги на едно място",
                ],
                "cta": "Изпрати защитен линк",
                "nav": ["Начало", "Собственици", "Заяви услуга"],
            },
            "en": {
                "chips": [
                    "Confidential portal",
                    "Calm property visibility",
                    "Service requests in one place",
                ],
                "cta": "Send secure link",
                "nav": ["Home", "Owners", "Request service"],
            },
            "fr": {
                "chips": [
                    "Portail confidentiel",
                    "Visibilité sereine du bien",
                    "Demandes de service au même endroit",
                ],
                "cta": "Envoyer le lien sécurisé",
                "nav": ["Accueil", "Propriétaires", "Demander un service"],
            },
            "ru": {
                "chips": [
                    "Конфиденциальный портал",
                    "Спокойный обзор объекта",
                    "Запросы услуг в одном месте",
                ],
                "cta": "Отправить защищённую ссылку",
                "nav": ["Главная", "Владельцы", "Запросить услугу"],
            },
        }

        for lang, values in expected.items():
            with self.subTest(lang=lang):
                response = self.client.get(f"/owners/login?lang={lang}")
                self.assertEqual(response.status_code, 200)
                html = response.get_data(as_text=True)

                self.assertIn(f'<html lang="{lang}">', html)
                for chip in values["chips"]:
                    self.assertIn(chip, html)
                self.assertIn(values["cta"], html)
                for nav_label in values["nav"]:
                    self.assertIn(nav_label, html)

                other_languages = {code: data for code, data in expected.items() if code != lang}
                for data in other_languages.values():
                    for chip in data["chips"]:
                        self.assertNotIn(chip, html)

    def test_professionals_landing_page_follows_selected_language(self):
        expected = {
            "bg": {
                "title": "Присъединете се към професионалната мрежа на BlackSeaConnect",
                "cta": "Отвори формата за регистрация",
                "chips": [
                    "Ранният достъп е безплатен",
                    "Записване в пилотната фаза",
                    "Доверени местни професионалисти",
                    "Българското Черноморие",
                ],
            },
            "en": {
                "title": "Join the BlackSeaConnect Professional Network",
                "cta": "Open registration form",
                "chips": [
                    "Early access is free",
                    "Pilot phase enrollment",
                    "Trusted local professionals",
                    "Bulgarian Black Sea coast",
                ],
            },
            "fr": {
                "title": "Rejoignez le réseau professionnel BlackSeaConnect",
                "cta": "Ouvrir le formulaire d'inscription",
                "chips": [
                    "L'accès anticipé est gratuit",
                    "Inscription pendant la phase pilote",
                    "Professionnels locaux de confiance",
                    "Côte bulgare de la mer Noire",
                ],
            },
            "ru": {
                "title": "Присоединяйтесь к профессиональной сети BlackSeaConnect",
                "cta": "Открыть форму регистрации",
                "chips": [
                    "Ранний доступ бесплатный",
                    "Регистрация во время пилотной фазы",
                    "Надёжные местные профессионалы",
                    "Болгарское Черноморье",
                ],
            },
        }

        for lang, values in expected.items():
            with self.subTest(lang=lang):
                response = self.client.get(f"/professionals?lang={lang}")
                self.assertEqual(response.status_code, 200)
                html = html_lib.unescape(response.get_data(as_text=True))

                self.assertIn(f'<html lang="{lang}">', html)
                self.assertIn(values["title"], html)
                self.assertIn(values["cta"], html)
                for chip in values["chips"]:
                    self.assertIn(chip, html)

                for other_lang, other_values in expected.items():
                    if other_lang == lang:
                        continue
                    self.assertNotIn(other_values["title"], html)

    def test_top_navigation_uses_shared_horizontal_wrapper_markup(self):
        services_html = self.client.get("/services?lang=en").get_data(as_text=True)
        demo_html = self.client.get("/demo/operations?lang=en").get_data(as_text=True)

        self.assertIn('<div class="topbar__actions">', services_html)
        self.assertIn('<div class="topbar__actions operations-topbar__actions">', demo_html)

        for html in (services_html, demo_html):
            for snippet in [
                '<nav class="site-nav" aria-label="Site">',
                '<a class="site-nav__link"',
                '<div class="language-switcher"',
                'data-lang-switch="bg"',
                'data-lang-switch="en"',
                'data-lang-switch="fr"',
                'data-lang-switch="ru"',
            ]:
                with self.subTest(snippet=snippet, html=html[:40]):
                    self.assertIn(snippet, html)

    def test_phase_one_target_routes_have_no_mojibake(self):
        target_routes = [
            "/services",
            "/demo/operations",
            "/pilot-access",
            "/guest/a-302",
            "/partners",
            "/professionals",
            "/network",
            "/owners/login",
            "/owners/dashboard",
            "/owners/property/new",
            "/owners/properties",
            "/owners/request-service",
        ]

        for path in target_routes:
            for lang in ("bg", "en", "fr", "ru"):
                with self.subTest(path=path, lang=lang):
                    if path.startswith("/owners/"):
                        self._login_owner()
                    response = self.client.get(f"{path}?lang={lang}")
                    self.assertEqual(response.status_code, 200)
                    html = response.get_data(as_text=True)
                    for mojibake in ("Ð", "Ñ", "Â"): 
                        self.assertNotIn(mojibake, html)

    def test_phase_a_listed_templates_have_no_mojibake_markers(self):
        repo_root = Path(__file__).resolve().parents[1]
        template_paths = [
            "templates/admin_home.html",
            "templates/admin_properties.html",
            "templates/admin_property_detail.html",
            "templates/admin_operations.html",
            "templates/admin_operations_detail.html",
            "templates/admin_service_request_detail.html",
            "templates/network.html",
            "templates/network_detail.html",
            "templates/owners_register.html",
            "templates/owners_property_new.html",
            "templates/owners_properties.html",
            "templates/owners_property_detail.html",
            "templates/owners_request_service.html",
            "templates/partners.html",
            "templates/professionals.html",
            "templates/professionals_apply.html",
            "templates/request_service.html",
        ]

        for rel_path in template_paths:
            with self.subTest(path=rel_path):
                content = (repo_root / rel_path).read_text(encoding="utf-8")
                for marker in ("Â", "Ð", "Ñ", "�"):
                    self.assertNotIn(marker, content)

    def test_phase_a_rendered_routes_have_no_mojibake_markers(self):
        providers = _load_network_providers()
        routes = [
            "/owners/register",
            "/owners/property/new",
            "/owners/properties",
            "/owners/request-service",
            "/professionals/apply",
            "/request-service",
            "/partners",
            "/professionals",
            "/network",
        ]

        if providers:
            provider_id = str(providers[0].get("id", "")).strip()
            if provider_id:
                routes.append(f"/network/{provider_id}")

        for path in routes:
            for lang in ("bg", "en", "fr", "ru"):
                with self.subTest(path=path, lang=lang):
                    if path.startswith("/owners/") and path != "/owners/register":
                        self._login_owner()
                    response = self.client.get(f"{path}?lang={lang}")
                    self.assertEqual(response.status_code, 200)
                    html = response.get_data(as_text=True)
                    for marker in ("Â", "Ð", "Ñ", "�"):
                        self.assertNotIn(marker, html)

    def test_partners_and_professionals_bg_pages_do_not_mix_english_fallbacks(self):
        checks = {
            "/partners?lang=bg": [
                "Request pilot access",
                "Approved network",
                "Converted partner applications visible to the public.",
                "No approved partners yet.",
                "Converted partner applications will appear here once reviewed by the admin team.",
            ],
            "/professionals?lang=bg": [
                "Need help for your property?",
                "Approved network",
                "Converted professional applications visible to the public.",
                "No approved professionals yet.",
                "Converted professional applications will appear here once reviewed by the admin team.",
            ],
        }

        for path, forbidden_values in checks.items():
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                html = response.get_data(as_text=True)
                self.assertIn('<html lang="bg">', html)
                for forbidden in forbidden_values:
                    self.assertNotIn(forbidden, html)
                for mojibake in ("Ð", "Ñ", "Â", "�"):
                    self.assertNotIn(mojibake, html)

    def test_partners_bg_runtime_translation_uses_shared_common_nav_labels(self):
        repo_root = Path(__file__).resolve().parents[1]
        script = textwrap.dedent(
            """
            const fs = require('fs');
            const vm = require('vm');

            function createNode(tagName, key, text) {
              return {
                tagName,
                textContent: text,
                attributes: { 'data-i18n': key },
                classList: { toggle() {} },
                getAttribute(name) {
                  return Object.prototype.hasOwnProperty.call(this.attributes, name) ? this.attributes[name] : null;
                },
                setAttribute(name, value) {
                  this.attributes[name] = value;
                }
              };
            }

            const navHome = createNode('A', 'partners.navHome', 'Home');
            const navServices = createNode('A', 'partners.navServices', 'Services');
            const requestPilot = createNode('A', 'partners.requestPilotCta', 'Request pilot access');
            const title = createNode('H1', 'partners.partnersTitle', 'Trusted partners');
            const nodes = [navHome, navServices, requestPilot, title];

            const document = {
              readyState: 'complete',
              documentElement: { lang: '' },
              querySelectorAll(selector) {
                if (selector === '[data-i18n]:not([data-i18n-html])') {
                  return nodes;
                }
                if (selector === '[data-i18n-html]') {
                  return [];
                }
                if (selector === '[data-i18n-attr]') {
                  return [];
                }
                if (selector === 'title[data-i18n]') {
                  return null;
                }
                return [];
              },
              querySelector() {
                return null;
              },
              addEventListener() {}
            };

            const window = {
              document,
              location: { href: 'https://example.com/partners?lang=bg', search: '?lang=bg', hostname: 'example.com', pathname: '/partners' },
              history: { replaceState() {} },
              dispatchEvent() {},
              setTimeout(fn) {
                if (typeof fn === 'function') {
                  fn();
                }
                return 0;
              },
              clearTimeout() {},
              console: { log() {}, warn() {}, error() {} },
              CustomEvent: function CustomEvent(type, init) {
                return { type, detail: init && init.detail };
              }
            };

            window.window = window;
            const sandbox = { window, document, fs, vm, console: window.console, URLSearchParams, CustomEvent: window.CustomEvent };
            globalThis.window = window;
            globalThis.document = document;
            __MODULE_LOADER__
            vm.runInNewContext(fs.readFileSync('static/js/i18n.js', 'utf8'), sandbox);

            console.log(JSON.stringify({
              htmlLang: document.documentElement.lang,
              navHome: navHome.textContent,
              navServices: navServices.textContent,
              requestPilot: requestPilot.textContent,
              title: title.textContent
            }));
            """
        )
        script = script.replace("__MODULE_LOADER__", self._i18n_module_loader_js())
        result = subprocess.run(
            ["node", "-e", script],
            cwd=repo_root,
            check=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
        )
        payload = json.loads(result.stdout)

        self.assertEqual(payload["htmlLang"], "bg")
        self.assertEqual(payload["navHome"], "Начало")
        self.assertEqual(payload["navServices"], "Услуги")
        self.assertEqual(payload["requestPilot"], "Заяви пилотен достъп")
        self.assertEqual(payload["title"], "Надеждни партньори за крайбрежни операции, подкрепа на гости и ежедневна координация.")

    def test_language_links_preserve_existing_query_parameters(self):
        self._login_owner()

        response = self.client.get("/owners/request-service?category=maintenance&utm_source=nav&lang=en")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)

        for lang in ("bg", "en", "fr", "ru"):
            with self.subTest(lang=lang):
                self.assertIn("category=maintenance", html)
                self.assertIn("utm_source=nav", html)
                self.assertIn(f"lang={lang}", html)
                self.assertIn(f'href="/owners/request-service?category=maintenance&amp;utm_source=nav&amp;lang={lang}"', html)

    def test_internal_links_preserve_current_language_across_key_pages(self):
        home_html = self.client.get("/?lang=en").get_data(as_text=True)
        for href in [
            'href="/services?lang=en"',
            'href="/demo/operations?lang=en"',
            'href="/pilot-access?lang=en"',
            'href="/owners/login?lang=en"',
        ]:
            with self.subTest(page="home", href=href):
                self.assertIn(href, home_html)

        services_html = self.client.get("/services?lang=fr").get_data(as_text=True)
        for href in [
            'href="/?lang=fr"',
            'href="/demo/operations?lang=fr"',
            'href="/pilot-access?lang=fr"',
            'href="/owners/register?lang=fr"',
        ]:
            with self.subTest(page="services", href=href):
                self.assertIn(href, services_html)

        pilot_html = self.client.get("/pilot-access?lang=ru").get_data(as_text=True)
        for href in [
            'href="/services?lang=ru"',
            'href="/partners?lang=ru"',
            'href="/owners/register?lang=ru"',
            'href="/pilot-access?lang=ru#pilot-form"',
        ]:
            with self.subTest(page="pilot", href=href):
                self.assertIn(href, pilot_html)

        self._login_owner()
        dashboard_html = self.client.get("/owners/dashboard?lang=fr").get_data(as_text=True)
        for href in [
            'href="/owners/property/new?lang=fr"',
            'href="/owners/logout?lang=fr"',
        ]:
            with self.subTest(page="owner-dashboard", href=href):
                self.assertIn(href, dashboard_html)

        property_html = self.client.get("/owners/property/new?lang=fr").get_data(as_text=True)
        for href in [
            'href="/owners/dashboard?lang=fr"',
            'href="/owners/logout?lang=fr"',
        ]:
            with self.subTest(page="owner-property", href=href):
                self.assertIn(href, property_html)
        self.assertIn('name="lang" value="fr"', property_html)

        guest_html = self.client.get("/guest/a-302?lang=ru").get_data(as_text=True)
        for href in [
            'href="/services?lang=ru"',
            'href="/partners?lang=ru"',
            'href="/professionals?lang=ru"',
            'href="/pilot-access?lang=ru"',
        ]:
            with self.subTest(page="guest", href=href):
                self.assertIn(href, guest_html)

        partners_html = self.client.get("/partners?lang=en").get_data(as_text=True)
        for href in [
            'href="/services?lang=en"',
            'href="/guest/a-302?lang=en"',
            'href="/pilot-access?lang=en"',
        ]:
            with self.subTest(page="partners", href=href):
                self.assertIn(href, partners_html)

    def test_internal_links_preserve_existing_query_params_on_owner_flows(self):
        self._login_owner()
        response = self.client.get("/owners/request-service?category=cleaning&utm_source=nav&lang=fr")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)

        for href in [
            'href="/services?category=cleaning&amp;utm_source=nav&amp;lang=fr"',
            'href="/partners?category=cleaning&amp;utm_source=nav&amp;lang=fr"',
            'href="/pilot-access?category=cleaning&amp;utm_source=nav&amp;lang=fr"',
            'href="/owners/dashboard?category=cleaning&amp;utm_source=nav&amp;lang=fr"',
            'href="/owners/login?category=cleaning&amp;utm_source=nav&amp;lang=fr"',
            ]:
            with self.subTest(href=href):
                self.assertIn(href, html)

    def test_owner_request_service_page_follows_selected_language(self):
        self._login_owner()

        expected = {
            "bg": [
                "Кажете ни каква помощ ви трябва.",
                "Започни заявка",
                "Насочва се към одобрен изпълнител",
            ],
            "en": [
                "Tell us what help you need.",
                "Start request",
                "Routed to an approved service provider",
            ],
            "fr": [
                "Dites-nous de quelle aide vous avez besoin.",
                "Commencer la demande",
                "Transmise à un prestataire agréé",
            ],
            "ru": [
                "Расскажите, какая помощь вам нужна.",
                "Создать заявку",
                "Передаётся проверенному исполнителю",
            ],
        }

        forbidden = {
            "bg": ["Tell us what help you need.", "Dites-nous de quelle aide vous avez besoin.", "Расскажите, какая помощь вам нужна."],
            "en": ["Кажете ни каква помощ ви трябва.", "Dites-nous de quelle aide vous avez besoin.", "Расскажите, какая помощь вам нужна."],
            "fr": ["Кажете ни каква помощ ви трябва.", "Tell us what help you need.", "Расскажите, какая помощь вам нужна."],
            "ru": ["Кажете ни каква помощ ви трябва.", "Tell us what help you need.", "Dites-nous de quelle aide vous avez besoin."],
        }

        for lang, snippets in expected.items():
            with self.subTest(lang=lang):
                response = self.client.get(f"/owners/request-service?lang={lang}")
                self.assertEqual(response.status_code, 200)
                html = html_lib.unescape(response.get_data(as_text=True))
                self.assertIn(f'<html lang="{lang}">', html)
                for snippet in snippets:
                    self.assertIn(snippet, html)
                for leak in forbidden[lang]:
                    self.assertNotIn(leak, html)

    def test_external_and_mailto_links_remain_untouched(self):
        html = self.client.get("/guest/a-302?lang=en").get_data(as_text=True)
        self.assertIn('href="https://wa.me/359899111019?', html)
        self.assertIn('href="mailto:concierge@blackseaconnect.com"', html)
        self.assertNotIn('mailto:concierge@blackseaconnect.com?lang=', html)

    def test_guest_bg_mode_uses_bulgarian_copy_only(self):
        response = self.client.get("/guest/a-302?lang=bg")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)

        self.assertIn('<html lang="bg">', html)
        for forbidden in [
            "Портал гостя",
            "Спокойный companion portal",
            "Панель пребывания",
            "Запросить помощь",
            "Смотреть демо",
        ]:
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, html)

        repo_root = Path(__file__).resolve().parents[1]
        script = textwrap.dedent(
            """
            const fs = require('fs');
            const vm = require('vm');
            const sandbox = {
              window: { BlackSeaI18N: {} },
              fs,
              vm,
              console: { log() {}, warn() {}, error() {} }
            };

            sandbox.window.window = sandbox.window;
            __MODULE_LOADER__
            console.log(JSON.stringify(sandbox.window.BlackSeaI18N.bg.guest));
            """
        )
        script = script.replace("__MODULE_LOADER__", self._i18n_module_loader_js())
        result = subprocess.run(
            ["node", "-e", script],
            cwd=repo_root,
            check=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
        )
        bg_guest = json.loads(result.stdout)

        self.assertEqual(bg_guest["pageTitle"], "BlackSea Connect | Портал за гости за A-302")
        self.assertEqual(bg_guest["guestTitle"], "Апартамент A-302")
        self.assertEqual(bg_guest["guestIntro"], "Спокоен портал-спътник за вашето пристигане, достъп и консиерж поддръжка.")
        self.assertEqual(bg_guest["actionWhatsApp"], "WhatsApp консиерж")
        self.assertEqual(bg_guest["actionDashboard"], "Панел за престоя")
        self.assertEqual(bg_guest["actionRequest"], "Поискай съдействие")
        self.assertEqual(bg_guest["actionHelper"], "Бързи действия за госта · без инсталиране, директно от телефона.")

    def test_guest_and_partners_routes_render_the_selected_language(self):
        guest_en = self.client.get("/guest/a-302?lang=en").get_data(as_text=True)
        guest_en_hero = guest_en.split('<div class="hero__copy guest-hero__copy">', 1)[1].split('<div class="hero__cta">', 1)[0]
        self.assertIn("A calm companion portal for your arrival, access and concierge support.", guest_en_hero)
        self.assertNotIn("Спокоен портал-спътник за вашето пристигане, достъп и консиерж поддръжка.", guest_en_hero)

        guest_ru = self.client.get("/guest/a-302?lang=ru").get_data(as_text=True)
        guest_ru_hero = guest_ru.split('<div class="hero__copy guest-hero__copy">', 1)[1].split('<div class="hero__cta">', 1)[0]
        self.assertIn("Спокойный портал-спутник для прибытия, доступа и помощи консьержа.", guest_ru_hero)
        self.assertNotIn("A calm companion portal for your arrival, access and concierge support.", guest_ru_hero)

        partners_bg = self.client.get("/partners?lang=bg").get_data(as_text=True)
        partners_bg_hero = partners_bg.split('<div class="hero__copy">', 1)[1].split('<div class="hero__cta">', 1)[0]
        self.assertIn("Надеждни партньори за крайбрежни операции, подкрепа на гости и ежедневна координация.", partners_bg_hero)
        self.assertNotIn("Contact:", partners_bg)
        self.assertNotIn("Trusted partners for coastal operations, guest support and daily follow-up.", partners_bg)

    def test_language_switcher_preserves_next_parameter(self):
        response = self.client.get("/guest/a-302?lang=en&next=%2Fowners%2Fdashboard")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)

        for lang in ("bg", "en", "fr", "ru"):
            with self.subTest(lang=lang):
                self.assertIn("next=%2Fowners%2Fdashboard", html)
                self.assertIn(f"lang={lang}", html)
                self.assertIn(f'href="/guest/a-302?next=%2Fowners%2Fdashboard&amp;lang={lang}"', html)

    def test_professional_login_page_respects_selected_language_and_links(self):
        expected = {
            "bg": ("Портал за професионалисти", "Обратно към професионалистите", "Кандидатствай като професионалист"),
            "en": ("Professional portal", "Back to professionals", "Apply as professional"),
            "fr": ("Portail professionnel", "Retour aux professionnels", "Candidater comme professionnel"),
            "ru": ("Портал профессионалов", "Назад к профессионалам", "Подать заявку как профессионал"),
        }

        for lang, (eyebrow, back_link, apply_link) in expected.items():
            with self.subTest(lang=lang):
                response = self.client.get(f"/professionals/login?lang={lang}")
                self.assertEqual(response.status_code, 200)
                html = response.get_data(as_text=True)
                self.assertIn(f'<html lang="{lang}">', html)
                self.assertIn(eyebrow, html)
                self.assertIn(back_link, html)
                self.assertIn(apply_link, html)
                self.assertIn(f'action="/professionals/login?lang={lang}"', html)
                self.assertIn(f'href="/professionals?lang={lang}"', html)
                self.assertIn(f'href="/professionals/apply?lang={lang}"', html)

    def test_missing_translation_falls_back_to_english(self):
        repo_root = Path(__file__).resolve().parents[1]
        script = textwrap.dedent(
            """
            const fs = require('fs');
            const vm = require('vm');

            function createNode(tagName, key, text) {
              return {
                tagName,
                textContent: text,
                attributes: { 'data-i18n': key },
                classList: { toggle() {} },
                getAttribute(name) {
                  return Object.prototype.hasOwnProperty.call(this.attributes, name) ? this.attributes[name] : null;
                },
                setAttribute(name, value) {
                  this.attributes[name] = value;
                }
              };
            }

            const node = createNode('P', 'common.fallbackKey', 'Bulgarian fallback');
            const document = {
              readyState: 'complete',
              documentElement: { lang: '' },
              querySelectorAll(selector) {
                if (selector === '[data-i18n]:not([data-i18n-html])') {
                  return [node];
                }
                if (selector === '[data-i18n-html]') {
                  return [];
                }
                if (selector === '[data-i18n-attr]') {
                  return [];
                }
                if (selector === 'title[data-i18n]') {
                  return null;
                }
                return [];
              },
              querySelector() {
                return null;
              },
              addEventListener() {}
            };

            const window = {
              document,
              location: { href: 'https://example.com/?lang=bg', search: '?lang=bg', hostname: 'example.com', pathname: '/' },
              history: { replaceState() {} },
              dispatchEvent() {},
              setTimeout(fn) {
                if (typeof fn === 'function') {
                  fn();
                }
                return 0;
              },
              clearTimeout() {},
              console: { log() {}, warn() {}, error() {} },
              CustomEvent: function CustomEvent(type, init) {
                return { type, detail: init && init.detail };
              },
              BlackSeaI18N: {
                bg: { common: {} },
                en: { common: { fallbackKey: 'English fallback' } }
              }
            };

            window.window = window;
            const sandbox = { window, document, fs, vm, console: window.console, URLSearchParams, CustomEvent: window.CustomEvent };
            globalThis.window = window;
            globalThis.document = document;
            __MODULE_LOADER__
            vm.runInNewContext(fs.readFileSync('static/js/i18n.js', 'utf8'), sandbox);

            console.log(JSON.stringify({
              htmlLang: document.documentElement.lang,
              text: node.textContent
            }));
            """
        )
        script = script.replace("__MODULE_LOADER__", self._i18n_module_loader_js())
        result = subprocess.run(
            ["node", "-e", script],
            cwd=repo_root,
            check=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
        )
        payload = json.loads(result.stdout)

        self.assertEqual(payload["htmlLang"], "bg")
        self.assertEqual(payload["text"], "English fallback")

    def test_modular_i18n_bundle_exposes_expected_namespaces_and_keys(self):
        repo_root = Path(__file__).resolve().parents[1]
        module_dir = repo_root / "static" / "js" / "i18n"

        for filename in [
            "common.js",
            "home.js",
            "services.js",
            "demo.js",
            "pilot.js",
            "guest.js",
            "owners.js",
            "partners.js",
            "professionals.js",
            "network.js",
            "request-service.js",
            "index.js",
        ]:
            with self.subTest(filename=filename):
                content = (module_dir / filename).read_text(encoding="utf-8")
                for mojibake in ("Ð", "Ñ", "Â", "�"):
                    self.assertNotIn(mojibake, content)

        expected_keys = {
            "common.js": ["languageSwitcherLabel", "navHome", "footerDescription"],
            "pilot.js": ["pilotAccessConciergeLabel", "pilotAccessFloatLabel", "pilotRequestReceivedTitle", "pilotFormSending"],
            "guest.js": ["guestConciergeSending", "guestConciergeSuccess", "guestConciergeValidationError", "guestConciergeError"],
            "partners.js": ["partnersApprovedEyebrow", "partnersApprovedTitle", "partnersApprovedEmptyTitle", "partnersApprovedEmptyCopy"],
            "professionals.js": ["professionalsApprovedEyebrow", "professionalsApprovedTitle", "professionalsApprovedEmptyTitle", "professionalsApprovedEmptyCopy"],
            "owners-request-service.js": ["ownerRequestServiceScheduled", "ownerRequestServiceSuggested", "ownerRequestServiceSuccessTitle"],
        }

        for filename, keys in expected_keys.items():
            content = (module_dir / filename).read_text(encoding="utf-8")
            for key in keys:
                with self.subTest(filename=filename, key=key):
                    self.assertIn(key, content)

        script = textwrap.dedent(
            f"""
            const fs = require('fs');
            const vm = require('vm');

            const document = {{
              documentElement: {{ lang: 'bg' }},
              querySelectorAll() {{ return []; }},
              querySelector() {{ return null; }},
              addEventListener() {{}}
            }};

            const window = {{
              document,
              location: {{ search: '', hostname: 'localhost', pathname: '/' }},
              history: {{ replaceState() {{}} }},
              setTimeout(fn) {{
                if (typeof fn === 'function') {{
                  fn();
                }}
                return 0;
              }},
              clearTimeout() {{}},
              CustomEvent: function() {{}},
              console: {{ log() {{}}, warn() {{}}, error() {{}} }}
            }};

            window.window = window;
            document.defaultView = window;

            const sandbox = {{
              window,
              document,
              location: window.location,
              history: window.history,
              setTimeout: window.setTimeout,
              clearTimeout: window.clearTimeout,
              CustomEvent: window.CustomEvent,
              console: window.console,
              URLSearchParams,
              fs,
              vm
            }};
            sandbox.globalThis = sandbox;

            {self._i18n_module_loader_js()}

            console.log(JSON.stringify({{
              hasBgServices: !!window.BlackSeaI18N.bg.services,
              hasEnServices: !!window.BlackSeaI18N.en.services,
              hasBgDemo: !!window.BlackSeaI18N.bg.demo
            }}));
            """
        )
        result = subprocess.run(
            ["node", "-e", script],
            cwd=repo_root,
            check=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
        )
        payload = json.loads(result.stdout.strip())
        self.assertTrue(payload["hasBgServices"])
        self.assertTrue(payload["hasEnServices"])
        self.assertTrue(payload["hasBgDemo"])

    def test_pilot_access_uses_url_language_only(self):
        repo_root = Path(__file__).resolve().parents[1]
        i18n = (repo_root / "static" / "js" / "i18n.js").read_text(encoding="utf-8")

        self.assertIn('const DEFAULT_LANG = "bg";', i18n)
        self.assertNotIn('const DEFAULT_LANG = "fr";', i18n)
        self.assertNotIn("localStorage", i18n)
        self.assertNotIn("navigator.language", i18n)
        self.assertIn("URLSearchParams(window.location.search)", i18n)

        default_response = self.client.get("/pilot-access")
        default_html = default_response.get_data(as_text=True)
        self.assertEqual(default_response.status_code, 200)
        self.assertIn('<html lang="bg">', default_html)
        self.assertIn("Виж демото", default_html)
        self.assertNotIn("Смотреть демо", default_html)
        self.assertIn("Заявете спокоен пилот", default_html)
        for mojibake in ("Ð", "Ñ", "Â"):
            with self.subTest(mojibake=mojibake):
                self.assertNotIn(mojibake, default_html)
        self.assertRegex(
            default_html,
            r'<a class="language-switcher__button [^"]*is-active[^"]*" href="/pilot-access\?lang=bg" data-lang-switch="bg">BG</a>',
        )

        ru_response = self.client.get("/pilot-access?lang=ru")
        ru_html = ru_response.get_data(as_text=True)
        self.assertEqual(ru_response.status_code, 200)
        self.assertIn('<html lang="ru">', ru_html)
        self.assertRegex(
            ru_html,
            r'<a class="language-switcher__button [^"]*is-active[^"]*" href="/pilot-access\?lang=ru" data-lang-switch="ru">RU</a>',
        )

        def render(path, lang, key):
            script = textwrap.dedent(
                f"""
                const fs = require('fs');
                const vm = require('vm');
                const i18nSrc = fs.readFileSync('static/js/i18n.js', 'utf8');

                const bodyNode = {{
                  tagName: 'DIV',
                  attrs: {{ 'data-i18n': {json.dumps(key)} }},
                  textContent: '',
                  getAttribute(name) {{ return this.attrs[name] ?? null; }},
                  setAttribute() {{}},
                  classList: {{ toggle() {{}} }}
                }};

                const titleNode = {{
                  tagName: 'TITLE',
                  attrs: {{ 'data-i18n': 'pageTitle' }},
                  textContent: '',
                  getAttribute(name) {{ return this.attrs[name] ?? null; }},
                  setAttribute() {{}},
                  classList: {{ toggle() {{}} }}
                }};

                const document = {{
                  readyState: 'complete',
                  documentElement: {{ lang: 'bg' }},
                  querySelectorAll(selector) {{
                    if (selector === '[data-i18n]:not([data-i18n-html])') {{
                      return [bodyNode, titleNode];
                    }}
                    if (selector === '[data-i18n-html]') {{
                      return [];
                    }}
                    if (selector === '[data-i18n-attr]') {{
                      return [];
                    }}
                    return [];
                  }},
                  querySelector(selector) {{
                    if (selector === 'title[data-i18n]') {{
                      return titleNode;
                    }}
                    return null;
                  }},
                  addEventListener() {{}}
                }};

                const window = {{
                  location: {{
                    pathname: {json.dumps(path)},
                    search: {json.dumps('' if not lang else '?lang=' + lang)},
                    href: {json.dumps('http://example.test' + path + ('' if not lang else '?lang=' + lang))}
                  }},
                  history: {{ replaceState() {{}} }},
                  document,
                  localStorage: {{ getItem() {{ return null; }}, setItem() {{}}, removeItem() {{}} }},
                  CustomEvent: function() {{}},
                  console: {{ log() {{}}, warn() {{}}, error() {{}} }},
                  dispatchEvent() {{}}
                }};

                window.window = window;
                const sandbox = {{ window, document, localStorage: window.localStorage, URLSearchParams, console: window.console, CustomEvent: window.CustomEvent, fs, vm }};

                {self._i18n_module_loader_js()}
                vm.runInNewContext(i18nSrc, sandbox);

                console.log(JSON.stringify({{
                  body: bodyNode.textContent,
                  title: titleNode.textContent,
                  htmlLang: document.documentElement.lang
                }}));
                """
            )
            result = subprocess.run(
                ["node", "-e", script],
                cwd=repo_root,
                check=True,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
            )
            return json.loads(result.stdout.strip())

        bg_expected = render("/pilot-access", "bg", "formName")
        ru_expected = render("/pilot-access", "ru", "formName")
        bg_demo_cta = render("/pilot-access", "bg", "pilotDemoCta")
        ru_demo_cta = render("/pilot-access", "ru", "pilotDemoCta")

        default_result = render("/pilot-access", "", "formName")
        self.assertEqual(default_result["htmlLang"], "bg")
        self.assertEqual(default_result["body"], bg_expected["body"])
        self.assertEqual(default_result["title"], bg_expected["title"])
        self.assertNotEqual(default_result["body"], ru_expected["body"])
        self.assertNotEqual(default_result["title"], ru_expected["title"])
        self.assertEqual(bg_demo_cta["body"], "Виж демото")
        self.assertEqual(ru_demo_cta["body"], "Смотреть демо")

        ru_result = render("/pilot-access", "ru", "formName")
        self.assertEqual(ru_result["htmlLang"], "ru")
        self.assertEqual(ru_result["body"], ru_expected["body"])
        self.assertEqual(ru_result["title"], ru_expected["title"])

    def test_pilot_access_bg_mode_has_no_french_form_strings(self):
        response = self.client.get("/pilot-access?lang=bg")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)

        self.assertIn('<html lang="bg">', html)
        self.assertRegex(
            html,
            r'<a class="language-switcher__button [^"]*is-active[^"]*" href="/pilot-access\?lang=bg" data-lang-switch="bg">BG</a>',
        )
        for forbidden in [
            "Type de bien",
            "Choisissez un type de bien",
            "Besoins de conciergerie",
            "Adresse e-mail",
        ]:
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, html)

    def test_services_en_mode_has_no_cyrillic_fallback_strings(self):
        repo_root = Path(__file__).resolve().parents[1]
        script = textwrap.dedent(
            """
            const fs = require('fs');
            const vm = require('vm');
            const sandbox = {
              window: { BlackSeaI18N: {} },
              fs,
              vm,
              console: { log() {}, warn() {}, error() {} }
            };

            sandbox.window.window = sandbox.window;
            __MODULE_LOADER__
            console.log(JSON.stringify(sandbox.window.BlackSeaI18N.en.services));
            """
        )
        script = script.replace("__MODULE_LOADER__", self._i18n_module_loader_js())
        result = subprocess.run(
            ["node", "-e", script],
            cwd=repo_root,
            check=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
        )
        en_services = json.loads(result.stdout)

        self.assertIsInstance(en_services, dict)
        self.assertIn("servicesTitle", en_services)
        self.assertNotRegex(json.dumps(en_services, ensure_ascii=False), r"[Ѐ-Яа-яЁё]")

    def test_services_ru_runtime_translation_uses_russian_copy(self):
        repo_root = Path(__file__).resolve().parents[1]
        script = textwrap.dedent(
            """
            const fs = require('fs');
            const vm = require('vm');
            const sandbox = {
              window: { BlackSeaI18N: {} },
              document: {
                documentElement: { lang: 'bg' },
                querySelectorAll() { return []; },
                querySelector() { return null; },
                addEventListener() {}
              },
              fs,
              vm,
              console: { log() {}, warn() {}, error() {} }
            };

            sandbox.window.window = sandbox.window;
            __MODULE_LOADER__
            console.log(JSON.stringify(sandbox.window.BlackSeaI18N.ru.services));
            """
        )
        script = script.replace("__MODULE_LOADER__", self._i18n_module_loader_js())
        result = subprocess.run(
            ["node", "-e", script],
            cwd=repo_root,
            check=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
        )
        payload = json.loads(result.stdout)

        self.assertIsInstance(payload, dict)
        self.assertEqual(payload["servicesTitle"], "Операционные услуги для проживания, команд и проверенных местных партнёров.")
        self.assertEqual(payload["servicesNextSecondary"], "Посмотреть демо")
        self.assertEqual(payload["service1Title"], "Координация гостей")
        for forbidden in [
            "Оперативни услуги",
            "Виж демото",
            "Координация на гости",
        ]:
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, json.dumps(payload, ensure_ascii=False))

    def test_demo_operations_bg_and_ru_render_expected_language(self):
        bg_response = self.client.get("/demo/operations?lang=bg")
        self.assertEqual(bg_response.status_code, 200)
        bg_html = bg_response.get_data(as_text=True)

        self.assertIn('<html lang="bg">', bg_html)
        self.assertRegex(
            bg_html,
            r'<a class="language-switcher__button [^"]*is-active[^"]*" href="/demo/operations\?lang=bg" data-lang-switch="bg">BG</a>',
        )
        self.assertIn("Координация на гости, имоти и услуги в един спокоен изглед.", bg_html)
        for forbidden in [
            "Type de bien",
            "Choisissez un type de bien",
            "Besoins de conciergerie",
            "Adresse e-mail",
            "Portefeuille mixte",
            "investor-grade",
            "luxury hospitality",
            "live feed",
            "next step",
            "pickup",
            "handoff",
            "Операции у моря",
            "Сегодня",
            "местное время",
            "Стабильная смена",
            "Запросить пилотный доступ",
        ]:
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, bg_html)

        ru_response = self.client.get("/demo/operations?lang=ru")
        self.assertEqual(ru_response.status_code, 200)
        ru_html = ru_response.get_data(as_text=True)

        self.assertIn('<html lang="ru">', ru_html)
        self.assertRegex(
            ru_html,
            r'<a class="language-switcher__button [^"]*is-active[^"]*" href="/demo/operations\?lang=ru" data-lang-switch="ru">RU</a>',
        )
        self.assertIn('data-i18n="demo.heroTitle"', ru_html)

    def test_demo_bg_namespace_has_no_russian_fallback_strings(self):
        repo_root = Path(__file__).resolve().parents[1]
        script = textwrap.dedent(
            """
            const fs = require('fs');
            const vm = require('vm');
            const sandbox = {
              window: { BlackSeaI18N: {} },
              fs,
              vm,
              console: { log() {}, warn() {}, error() {} }
            };

            sandbox.window.window = sandbox.window;
            __MODULE_LOADER__
            console.log(JSON.stringify(sandbox.window.BlackSeaI18N.bg.demo));
            """
        )
        script = script.replace("__MODULE_LOADER__", self._i18n_module_loader_js())
        result = subprocess.run(
            ["node", "-e", script],
            cwd=repo_root,
            check=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
        )
        bg_demo = result.stdout

        for forbidden in [
            "Операции у моря",
            "Сегодня",
            "местное время",
            "Стабильная смена",
            "Запросить пилотный доступ",
        ]:
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, bg_demo)

    def test_demo_bg_namespace_has_no_obvious_english_leaks(self):
        repo_root = Path(__file__).resolve().parents[1]
        script = textwrap.dedent(
            """
            const fs = require('fs');
            const vm = require('vm');
            const sandbox = {
              window: { BlackSeaI18N: {} },
              fs,
              vm,
              console: { log() {}, warn() {}, error() {} }
            };

            sandbox.window.window = sandbox.window;
            __MODULE_LOADER__
            console.log(JSON.stringify(sandbox.window.BlackSeaI18N.bg.demo));
            """
        )
        script = script.replace("__MODULE_LOADER__", self._i18n_module_loader_js())
        result = subprocess.run(
            ["node", "-e", script],
            cwd=repo_root,
            check=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
        )
        bg_demo = result.stdout

        for forbidden in [
            "investor-grade",
            "luxury hospitality",
            "live feed",
            "next step",
            "pickup",
            "handoff",
            "lounge",
            "pairing",
            "private chef",
            "on-site",
            "Turnaround",
            "fit",
        ]:
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, bg_demo)

    def test_services_bg_namespace_has_no_russian_fallback_strings(self):
        repo_root = Path(__file__).resolve().parents[1]
        script = textwrap.dedent(
            """
            const fs = require('fs');
            const vm = require('vm');
            const sandbox = {
              window: { BlackSeaI18N: {} },
              fs,
              vm,
              console: { log() {}, warn() {}, error() {} }
            };

            sandbox.window.window = sandbox.window;
            __MODULE_LOADER__
            console.log(JSON.stringify(sandbox.window.BlackSeaI18N.bg.services));
            """
        )
        script = script.replace("__MODULE_LOADER__", self._i18n_module_loader_js())
        result = subprocess.run(
            ["node", "-e", script],
            cwd=repo_root,
            check=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
        )
        bg_services = result.stdout

        for forbidden in [
            "Премиальные гостиничные услуги",
            "Операционные услуги",
            "Координация гостей",
            "Координация уборки",
            "Запросить пилотный доступ",
        ]:
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, bg_services)

    def test_active_translation_bindings_are_complete(self):
        repo_root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [sys.executable, "scripts/check_i18n.py"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_homepage_hero_and_owner_preview_are_fully_localized(self):
        expected = {
            "bg": ("Вашият имот е в сигурни ръце.", "Моят имот днес", "Почистването приключи", "Всичко протича нормално"),
            "en": ("Your property, cared for.", "My property today", "Cleaning completed", "Everything is running normally"),
            "fr": ("Votre propriété, entre de bonnes mains.", "Ma propriété aujourd’hui", "Ménage terminé", "Tout se déroule normalement"),
            "ru": ("О вашей недвижимости заботятся.", "Моя недвижимость сегодня", "Уборка завершена", "Всё идёт нормально"),
        }
        forbidden_by_language = {
            "bg": ("Уборка", "Завершено", "Следующий гость", "Завтра", "Подтверждено", "Моя недвижимость сегодня", "Всё идёт нормально", "Demain", "Ménage", "Tomorrow", "Cleaning completed"),
            "en": ("Почистване", "Моят имот днес", "Уборка", "Моя недвижимость сегодня", "Ménage", "Ma propriété aujourd’hui"),
            "fr": ("Почистване", "Моят имот днес", "Cleaning completed", "My property today", "Уборка", "Моя недвижимость сегодня"),
            "ru": ("Почистване", "Моят имот днес", "Cleaning completed", "My property today", "Ménage", "Ma propriété aujourd’hui"),
        }
        forbidden_markers = ("[MISSING:", "undefined", ">null<", "data-i18n-missing")
        for lang, phrases in expected.items():
            with self.subTest(lang=lang):
                response = self.client.get(f"/?lang={lang}")
                self.assertEqual(response.status_code, 200)
                html = response.get_data(as_text=True)
                visible_text = self._visible_text(html)
                for phrase in phrases:
                    self.assertIn(phrase, visible_text)
                for marker in forbidden_markers:
                    self.assertNotIn(marker, visible_text)
                for foreign_text in forbidden_by_language[lang]:
                    self.assertNotIn(foreign_text, visible_text)
                self.assertNotIn("`n", html)

    def test_homepage_carousel_dataset_contains_keys_not_localized_sentences(self):
        source = (Path(__file__).resolve().parents[1] / "templates" / "index.html").read_text(encoding="utf-8")
        match = re.search(r"const slides\s*=\s*\[(.*?)\];", source, re.DOTALL)
        self.assertIsNotNone(match)
        slide_source = match.group(1)
        self.assertNotRegex(slide_source, r"[А-Яа-яЁё]{3,}")
        self.assertNotRegex(slide_source, r"\b(?:your|property|guest|work|photos)\b.*[.!?]")
        self.assertNotRegex(slide_source, r"\b(?:votre|propriété|travail|photos|voyageur)\b.*[.!?]")
        for key_field in (
            "propertyKey",
            "cityKey",
            "ownerKey",
            "statusKey",
            "testimonialQuoteKey",
            "testimonialCopyKey",
        ):
            self.assertIn(f"{key_field}:", slide_source)
        self.assertNotIn("`n", source)



