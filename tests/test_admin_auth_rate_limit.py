import base64
from concurrent.futures import ThreadPoolExecutor

import pytest
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

import app as app_module


def auth_headers(password="wrong", username="admin"):
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


@pytest.fixture
def auth_app(monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret")
    monkeypatch.delenv("ADMIN_SUPER_USERNAME", raising=False)
    monkeypatch.delenv("ADMIN_SUPER_PASSWORD", raising=False)
    monkeypatch.setattr(app_module, "_ADMIN_AUTH_RATE_LIMITS", {})
    monkeypatch.setattr(app_module, "_PUBLIC_FORM_RATE_LIMITS", {})
    test_app = Flask(__name__)
    test_app.config["TESTING"] = True
    test_app.add_url_rule("/admin", view_func=app_module.admin_required(lambda: "ok"))
    return test_app


def attempt(client, password="wrong", ip="192.0.2.1", headers=None):
    return client.get(
        "/admin", headers=auth_headers(password) if headers is None else headers,
        environ_overrides={"REMOTE_ADDR": ip},
    )


def test_wrong_attempts_are_counted(auth_app):
    client = auth_app.test_client()
    for count in range(1, app_module.ADMIN_AUTH_RATE_LIMIT_MAX_FAILURES):
        response = attempt(client)
        assert response.status_code == 401
        assert "WWW-Authenticate" in response.headers
        assert len(app_module._ADMIN_AUTH_RATE_LIMITS["192.0.2.1"]) == count


def test_threshold_blocks_even_correct_credentials(auth_app):
    client = auth_app.test_client()
    for _ in range(app_module.ADMIN_AUTH_RATE_LIMIT_MAX_FAILURES - 1):
        assert attempt(client).status_code == 401
    assert attempt(client).status_code == 429
    assert attempt(client).status_code == 429
    assert attempt(client, "secret").status_code == 429
    assert len(app_module._ADMIN_AUTH_RATE_LIMITS["192.0.2.1"]) == 5


def test_success_before_threshold_resets_failures(auth_app):
    client = auth_app.test_client()
    for _ in range(4):
        assert attempt(client).status_code == 401
    assert attempt(client, "secret").status_code == 200
    assert "192.0.2.1" not in app_module._ADMIN_AUTH_RATE_LIMITS
    for _ in range(4):
        assert attempt(client).status_code == 401
    assert attempt(client).status_code == 429


def test_successful_requests_do_not_consume_limit(auth_app):
    client = auth_app.test_client()
    for _ in range(8):
        assert attempt(client, "secret").status_code == 200
    assert app_module._ADMIN_AUTH_RATE_LIMITS == {}


def test_ips_have_independent_counters(auth_app):
    client = auth_app.test_client()
    for _ in range(5):
        attempt(client)
    assert attempt(client, ip="192.0.2.2").status_code == 401
    assert attempt(client, "secret", ip="192.0.2.2").status_code == 200
    assert attempt(client).status_code == 429


def test_window_expires_without_blocked_requests_extending_it(auth_app, monkeypatch):
    client = auth_app.test_client()
    now = [1000.0]
    monkeypatch.setattr(app_module.time, "monotonic", lambda: now[0])
    for _ in range(5):
        attempt(client)
    now[0] += app_module.ADMIN_AUTH_RATE_LIMIT_WINDOW_SECONDS - 1
    assert attempt(client).status_code == 429
    now[0] += 1
    assert attempt(client, "secret").status_code == 200
    assert app_module._ADMIN_AUTH_RATE_LIMITS == {}


def test_unconfigured_auth_stays_503_without_counting(auth_app, monkeypatch):
    monkeypatch.delenv("ADMIN_PASSWORD")
    for _ in range(6):
        assert attempt(auth_app.test_client()).status_code == 503
    assert app_module._ADMIN_AUTH_RATE_LIMITS == {}


def test_initial_basic_challenge_is_not_a_failed_login(auth_app):
    for _ in range(6):
        assert attempt(auth_app.test_client(), headers={}).status_code == 401
    assert app_module._ADMIN_AUTH_RATE_LIMITS == {}


@pytest.mark.parametrize("authorization", ["Basic !!!", "Bearer invalid", "Basic YWRtaW46"])
def test_invalid_authorization_is_counted(auth_app, authorization):
    response = attempt(auth_app.test_client(), headers={"Authorization": authorization})
    assert response.status_code == 401
    assert len(app_module._ADMIN_AUTH_RATE_LIMITS["192.0.2.1"]) == 1


def test_forwarded_header_cannot_bypass_limit_without_proxyfix(auth_app):
    for index in range(5):
        headers = {**auth_headers(), "X-Forwarded-For": f"198.51.100.{index}"}
        response = attempt(auth_app.test_client(), headers=headers)
    assert response.status_code == 429
    assert set(app_module._ADMIN_AUTH_RATE_LIMITS) == {"192.0.2.1"}


def test_configured_proxyfix_resolves_client_ip(auth_app):
    auth_app.wsgi_app = ProxyFix(auth_app.wsgi_app, x_for=1)
    headers = {**auth_headers(), "X-Forwarded-For": "198.51.100.1"}
    assert attempt(auth_app.test_client(), headers=headers).status_code == 401
    assert set(app_module._ADMIN_AUTH_RATE_LIMITS) == {"198.51.100.1"}


def test_super_admin_success_resets_same_counter(auth_app, monkeypatch):
    monkeypatch.setenv("ADMIN_SUPER_USERNAME", "super")
    monkeypatch.setenv("ADMIN_SUPER_PASSWORD", "super-secret")
    client = auth_app.test_client()
    assert attempt(client).status_code == 401
    assert attempt(client, headers=auth_headers("super-secret", "super")).status_code == 200
    assert app_module._ADMIN_AUTH_RATE_LIMITS == {}


def test_public_form_limiter_remains_independent(auth_app):
    app_module._PUBLIC_FORM_RATE_LIMITS["pilot::192.0.2.1"] = [123.0]
    for _ in range(5):
        attempt(auth_app.test_client())
    assert app_module._PUBLIC_FORM_RATE_LIMITS == {"pilot::192.0.2.1": [123.0]}
    with auth_app.test_request_context("/", environ_base={"REMOTE_ADDR": "192.0.2.1"}):
        assert app_module._public_form_rate_limited("pilot") is False
    assert attempt(auth_app.test_client()).status_code == 429


def test_concurrent_failures_respect_threshold(auth_app):
    def request_once(_):
        return attempt(auth_app.test_client()).status_code

    with ThreadPoolExecutor(max_workers=8) as pool:
        statuses = list(pool.map(request_once, range(12)))
    assert statuses.count(401) == 4
    assert statuses.count(429) == 8
    assert len(app_module._ADMIN_AUTH_RATE_LIMITS["192.0.2.1"]) == 5


def test_attachment_admin_auth_shares_limit(auth_app, monkeypatch):
    monkeypatch.setattr(app_module, "_find_operations_task_by_canonical_id", lambda _: {"id": "task"})
    monkeypatch.setattr(app_module, "_find_operations_task_attachment", lambda *_: {"id": "file"})
    monkeypatch.setattr(app_module, "_enterprise_user_identity", lambda: (None, None, None, None))
    auth_app.add_url_rule(
        "/operations/tasks/<task_id>/attachments/<attachment_id>",
        view_func=app_module.operations_task_attachment_file,
    )
    client = auth_app.test_client()
    for _ in range(4):
        response = client.get(
            "/operations/tasks/task/attachments/file", headers=auth_headers(),
            environ_overrides={"REMOTE_ADDR": "192.0.2.1"},
        )
        assert response.status_code == 404
    assert attempt(client).status_code == 429
    response = client.get(
        "/operations/tasks/task/attachments/file", headers=auth_headers("secret"),
        environ_overrides={"REMOTE_ADDR": "192.0.2.1"},
    )
    assert response.status_code == 429
