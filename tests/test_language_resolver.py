"""Global language policy, real route rendering, and browser boot regressions."""
import base64
import json
from pathlib import Path
import subprocess
import shutil
from uuid import uuid4

import pytest
from flask import session

import app as application
from config import ConfigurationError, load_settings


@pytest.fixture
def client(monkeypatch):
    # Match the existing portal fixtures; pytest's mode-0700 tmp_path is not
    # accessible in the managed Windows workspace.
    root = Path.cwd()
    directory = root / f".tmp_language_tests_{uuid4().hex}"
    directory.mkdir()
    monkeypatch.chdir(directory)
    monkeypatch.setenv("OWNER_DB_PATH", str(directory / "owners.db"))
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret")
    monkeypatch.setitem(application.app.config, "TESTING", True)
    monkeypatch.setitem(application.app.config, "TRUSTED_COUNTRY_HEADER", "CF-IPCountry")
    try:
        yield application.app.test_client()
    finally:
        monkeypatch.chdir(root)
        shutil.rmtree(directory)


@pytest.mark.parametrize("language", ["bg", "en", "fr", "ru"])
def test_manual_selection_and_navigation(client, language):
    response = client.get(f"/services?lang={language}", headers={"CF-IPCountry": "FR"})
    assert f'<html lang="{language}">' in response.text
    for path in ("/owners/login", "/professionals/login", "/", "/concierge-bulgaria"):
        response = client.get(path, headers={"CF-IPCountry": "BG"}, follow_redirects=True)
        assert response.status_code == 200
        assert f'<html lang="{language}">' in response.text
    with client.session_transaction() as state:
        assert state[application.SITE_LANGUAGE_SESSION_KEY] == language


@pytest.mark.parametrize("country,language", [
    ("BG", "bg"), ("FR", "fr"), ("RU", "ru"), ("DE", "en"), ("US", "en"),
    ("", "en"), ("XX", "en"), ("T1", "en"), ("France", "en"),
    ("FR,BG", "en"), ("FRA", "en"), (" fr ", "fr"),
])
@pytest.mark.parametrize("path", ["/", "/services", "/owners/login", "/professionals/login", "/concierge-bulgaria"])
def test_country_on_public_and_portal_entry_pages(client, country, language, path):
    response = client.get(path, headers={"CF-IPCountry": country} if country else {})
    assert response.status_code == 200
    assert f'<html lang="{language}">' in response.text
    assert "CF-IPCountry" in response.vary
    with client.session_transaction() as state:
        assert application.SITE_LANGUAGE_SESSION_KEY not in state


def test_automatic_choice_does_not_become_manual(client):
    for country, language in [("FR", "fr"), ("BG", "bg"), ("", "en")]:
        assert f'<html lang="{language}">' in client.get("/services", headers={"CF-IPCountry": country}).text


@pytest.mark.parametrize("header", ["", "CF-IPCountry", "CloudFront-Viewer-Country", "X-Vercel-IP-Country"])
def test_only_configured_country_header_is_trusted(client, monkeypatch, header):
    monkeypatch.setitem(application.app.config, "TRUSTED_COUNTRY_HEADER", header)
    headers = {"CF-IPCountry": "BG", "CloudFront-Viewer-Country": "FR", "X-Vercel-IP-Country": "RU"}
    expected = {"": "en", "CF-IPCountry": "bg", "CloudFront-Viewer-Country": "fr", "X-Vercel-IP-Country": "ru"}[header]
    assert f'<html lang="{expected}">' in client.get("/services", headers=headers).text


@pytest.mark.parametrize("remembered,expected", [(None, "fr"), ("ru", "ru"), ("de", "fr")])
def test_unsupported_query_does_not_poison_session(client, remembered, expected):
    if remembered is not None:
        with client.session_transaction() as state:
            state[application.SITE_LANGUAGE_SESSION_KEY] = remembered
    response = client.get("/?lang=de", headers={"CF-IPCountry": "FR"})
    assert f'<html lang="{expected}">' in response.text
    with client.session_transaction() as state:
        assert state.get(application.SITE_LANGUAGE_SESSION_KEY) == remembered


def test_ip_and_browser_language_are_not_country_signals(client):
    response = client.get("/services", headers={
        "X-Forwarded-For": "France", "X-Real-IP": "BG", "Accept-Language": "ru",
    })
    assert '<html lang="en">' in response.text


def test_query_precedes_form_and_valid_form_language_is_manual(client):
    with application.app.test_request_context("/?lang=ru", method="POST", data={"lang": "bg"}):
        assert application._resolve_current_language() == "ru"
        assert session[application.SITE_LANGUAGE_SESSION_KEY] == "ru"

    with application.app.test_request_context("/", method="POST", data={"lang": "bg"}, headers={"CF-IPCountry": "FR"}):
        assert application._resolve_current_language() == "bg"
        assert session[application.SITE_LANGUAGE_SESSION_KEY] == "bg"


@pytest.mark.parametrize("country,language", [("BG", "bg"), ("FR", "fr"), ("RU", "ru"), ("US", "en")])
def test_authenticated_portals_admin_and_workspace(client, country, language):
    owner = application._upsert_owner_account({"id": "owner-language", "email": "owner@example.com", "full_name": "Owner"})
    professional = application._upsert_professional_account({"id": "pro-language", "email": "pro@example.com", "full_name": "Professional", "status": "ACTIVE"})
    with client.session_transaction() as state:
        state[application.OWNER_SESSION_LOGGED_IN_KEY] = True
        state[application.OWNER_SESSION_ID_KEY] = owner["id"]
        state[application.OWNER_SESSION_EMAIL_KEY] = owner["email"]
        state[application.PROFESSIONAL_SESSION_LOGGED_IN_KEY] = True
        state[application.PROFESSIONAL_SESSION_ID_KEY] = professional["id"]
        state[application.PROFESSIONAL_SESSION_EMAIL_KEY] = professional["email"]
    headers = {"CF-IPCountry": country, "Authorization": "Basic " + base64.b64encode(b"admin:secret").decode()}
    user = application._upsert_user({"id": "language-admin", "email": "admin-language@example.com", "full_name": "Admin"})
    with client.session_transaction() as state:
        state[application.ENTERPRISE_SESSION_USER_ID_KEY] = user["id"]
        state[application.ENTERPRISE_SESSION_ROLE_KEY] = application.ROLE_PLATFORM_ADMIN
    for path in ("/owners/dashboard", "/professionals/dashboard", "/admin", "/workspace"):
        response = client.get(path, headers=headers)
        assert response.status_code == 200, (path, response.status_code)
        assert f'<html lang="{language}">' in response.text, path
        manual = "bg" if language == "ru" else "ru"
        assert f'<html lang="{manual}">' in client.get(f"{path}?lang={manual}", headers=headers).text
        assert f'<html lang="{manual}">' in client.get(path, headers=headers).text
        with client.session_transaction() as state:
            state.pop(application.SITE_LANGUAGE_SESSION_KEY)


def test_configuration_is_opt_in_and_validated():
    assert load_settings({"APP_ENV": "test"}).trusted_country_header == ""
    assert load_settings({"APP_ENV": "test", "TRUSTED_COUNTRY_HEADER": "CF-IPCountry"}).flask_mapping()["TRUSTED_COUNTRY_HEADER"] == "CF-IPCountry"
    with pytest.raises(ConfigurationError, match="TRUSTED_COUNTRY_HEADER"):
        load_settings({"APP_ENV": "test", "TRUSTED_COUNTRY_HEADER": "X-Forwarded-For"})


@pytest.mark.parametrize("path,selected,expected", [
    ("/services", "fr", {"prevented": True, "fetches": 1, "reloads": 0, "bound": True}),
    ("/services", "ru", {"prevented": True, "fetches": 1, "reloads": 0, "bound": True}),
    ("/owners/dashboard", "ru", {"prevented": True, "fetches": 0, "reloads": 1, "bound": True}),
    ("/admin", "ru", {"prevented": False, "fetches": 0, "reloads": 0, "bound": False}),
])
def test_browser_manual_switch_preserves_navigation_contract(path, selected, expected):
    script = r'''
const fs = require('fs'), vm = require('vm');
const [path, selected] = process.argv.slice(1);
let handler, delegated, prevented = false, fetches = 0, reloads = 0;
const control = {
  tagName: 'A', dataset: {}, classList: {toggle() {}},
  getAttribute(name) { return name === 'data-lang-switch' ? selected : path + '?lang=' + selected; },
  setAttribute() {}, addEventListener(type, fn) { handler = fn; }, closest() { return control; }
};
const document = {
  readyState: 'complete', documentElement: {lang: 'fr'},
  querySelector: () => null,
  querySelectorAll: selector => selector === '[data-lang-switch], [data-lang]' ? [control] : [],
  addEventListener(type, fn) { if (type === 'click') delegated = fn; }
};
const window = {
  document, BlackSeaI18N: {bg: {}, en: {}, fr: {}, ru: {}},
  location: {href: 'https://example.com' + path, origin: 'https://example.com', search: '', pathname: path, hostname: 'example.com', assign() { reloads++; }},
  history: {replaceState() {}}, dispatchEvent() {},
  fetch(url, options) { if (!url.includes('lang=' + selected) || options.credentials !== 'same-origin') throw Error('Invalid persistence'); fetches++; return Promise.resolve(); }
};
vm.runInNewContext(fs.readFileSync('static/js/i18n.js', 'utf8'), {
  window, document, URL, URLSearchParams, console, CustomEvent: function() {}
});
(handler || delegated)({currentTarget: control, target: control, preventDefault() { prevented = true; }});
console.log(JSON.stringify({prevented, fetches, reloads, bound: Boolean(handler)}));
'''
    result = subprocess.run(["node", "-e", script, path, selected], cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, check=True)
    assert json.loads(result.stdout) == expected


@pytest.mark.parametrize("language", ["bg", "en", "fr", "ru"])
def test_browser_preserves_server_language_even_without_bundle(language):
    script = r'''
const fs = require('fs'), vm = require('vm');
const language = process.argv[1];
const document = {
  readyState: 'complete', documentElement: {lang: language},
  querySelector: () => null, querySelectorAll: () => [], addEventListener() {}
};
const window = {
  document, BlackSeaI18N: {en: {home: {}}},
  location: {href: 'https://example.com/?lang=bg', search: '?lang=bg', pathname: '/', hostname: 'example.com'},
  history: {replaceState() {}}, dispatchEvent() {}
};
vm.runInNewContext(fs.readFileSync('static/js/i18n.js', 'utf8'), {
  window, document, URL, URLSearchParams, console, CustomEvent: function() {}
});
console.log(JSON.stringify(document.documentElement.lang));
'''
    result = subprocess.run(["node", "-e", script, language], cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, check=True)
    assert json.loads(result.stdout) == language
