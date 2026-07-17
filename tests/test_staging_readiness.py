import io
import logging
from pathlib import Path

import pytest

import app as app_module
from config import ConfigurationError, load_settings


def _protected_environment(tmp_path, environment="staging"):
    live = environment == "production"
    return {
        "APP_ENV": environment,
        "SITE_URL": f"https://{environment}.example.com",
        "SECRET_KEY": "a-secure-random-secret-value-over-32-characters",
        "DATABASE_PATH": str(tmp_path / "application.db"),
        "STRIPE_MODE": "live" if live else "test",
        "STRIPE_CONNECT_ENABLED": "1",
        "STRIPE_SECRET_KEY": "sk_live_not_real" if live else "sk_test_not_real",
        "STRIPE_PUBLISHABLE_KEY": "pk_live_not_real" if live else "pk_test_not_real",
        "STRIPE_WEBHOOK_SECRET": "whsec_not_real",
        "MANUAL_FINANCE_ENABLED": "0",
        "LOG_LEVEL": "INFO",
        "TRUST_PROXY_HEADERS": "1",
        "SESSION_COOKIE_SECURE": "1",
        "SESSION_COOKIE_SAMESITE": "Lax",
    }


def test_development_defaults_are_safe_and_local():
    settings = load_settings({})
    assert settings.environment == "development"
    assert settings.site_url == "http://localhost:5010"
    assert settings.stripe_mode == "test"
    assert not settings.stripe_connect_enabled
    assert not settings.session_cookie_secure


def test_staging_missing_required_variables_fails_safely():
    with pytest.raises(ConfigurationError) as raised:
        load_settings({"APP_ENV": "staging", "STRIPE_SECRET_KEY": "sk_test_do_not_echo"})
    assert "missing required variable" in str(raised.value)
    assert "sk_test_do_not_echo" not in str(raised.value)


def test_staging_rejects_live_secret_key(tmp_path):
    environment = _protected_environment(tmp_path)
    environment["STRIPE_SECRET_KEY"] = "sk_live_do_not_use"
    with pytest.raises(ConfigurationError, match="Stripe secret key mode"):
        load_settings(environment)


def test_production_rejects_test_secret_key(tmp_path):
    environment = _protected_environment(tmp_path, "production")
    environment["STRIPE_SECRET_KEY"] = "sk_test_do_not_use"
    with pytest.raises(ConfigurationError, match="Stripe secret key mode"):
        load_settings(environment)


def test_production_rejects_insecure_site_url(tmp_path):
    environment = _protected_environment(tmp_path, "production")
    environment["SITE_URL"] = "http://production.example.com"
    with pytest.raises(ConfigurationError, match="HTTPS"):
        load_settings(environment)


def test_production_rejects_weak_secret_key(tmp_path):
    environment = _protected_environment(tmp_path, "production")
    environment["SECRET_KEY"] = "too-short"
    with pytest.raises(ConfigurationError, match="at least 32"):
        load_settings(environment)


def test_manual_finance_must_be_disabled_in_production(tmp_path):
    environment = _protected_environment(tmp_path, "production")
    environment["MANUAL_FINANCE_ENABLED"] = "1"
    with pytest.raises(ConfigurationError, match="MANUAL_FINANCE_ENABLED"):
        load_settings(environment)


@pytest.fixture
def readiness_client(tmp_path):
    application = app_module.app
    original = {
        "DATABASE_PATH": application.config["DATABASE_PATH"],
        "TESTING": application.config.get("TESTING", False),
        "PROPAGATE_EXCEPTIONS": application.config.get("PROPAGATE_EXCEPTIONS"),
    }
    application.config.update(DATABASE_PATH=str(tmp_path / "ready.db"), TESTING=True)
    with app_module._owner_db_connection() as connection:
        app_module._ensure_owner_db_schema(connection)
    yield application.test_client()
    application.config.update(original)


def test_health_live_returns_200(readiness_client):
    response = readiness_client.get("/health/live")
    assert response.status_code == 200
    assert response.get_json() == {"status": "live"}


def test_health_ready_returns_200_when_valid(readiness_client):
    response = readiness_client.get("/health/ready")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ready"
    assert all(response.get_json()["checks"].values())


def test_health_ready_returns_503_for_invalid_database(tmp_path):
    application = app_module.app
    previous = application.config["DATABASE_PATH"]
    application.config["DATABASE_PATH"] = str(tmp_path / "missing" / "application.db")
    try:
        response = application.test_client().get("/health/ready")
    finally:
        application.config["DATABASE_PATH"] = previous
    assert response.status_code == 503
    assert response.get_json()["checks"]["database"] is False


def test_health_ready_returns_503_for_invalid_configuration(readiness_client, monkeypatch):
    exception_detail = "configuration validation rejected at startup"

    def reject_configuration(*args, **kwargs):
        raise ConfigurationError([exception_detail])

    monkeypatch.setattr(app_module, "validate_settings", reject_configuration)
    response = readiness_client.get("/health/ready")
    output = response.get_data(as_text=True)
    payload = response.get_json()

    assert response.status_code == 503
    assert payload["status"] == "not_ready"
    assert payload["checks"]["configuration"] is False
    assert exception_detail not in output
    assert "ConfigurationError" not in output
    assert "Traceback" not in output
    assert app_module.SETTINGS.secret_key not in output
    assert str(app_module.app.config["DATABASE_PATH"]) not in output
    assert "sk_live_" not in output
    assert "whsec_" not in output
    assert "token" not in output.lower()


def test_health_output_never_contains_secrets(readiness_client):
    response = readiness_client.get("/health/ready")
    output = response.get_data(as_text=True)
    assert app_module.SETTINGS.secret_key not in output
    assert "sk_test_" not in output
    assert "whsec_" not in output
    assert str(Path(app_module.app.config["DATABASE_PATH"])) not in output


def test_request_id_is_generated_and_returned(readiness_client):
    response = readiness_client.get("/health/live")
    assert app_module.REQUEST_ID_PATTERN.fullmatch(response.headers["X-Request-ID"])


def test_safe_incoming_request_id_is_accepted(readiness_client):
    response = readiness_client.get("/health/live", headers={"X-Request-ID": "deploy-check:123"})
    assert response.headers["X-Request-ID"] == "deploy-check:123"


def test_sensitive_headers_are_not_logged(readiness_client):
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(app_module._JsonLogFormatter())
    app_module.app.logger.addHandler(handler)
    try:
        readiness_client.get(
            "/health/live",
            headers={
                "Authorization": "Bearer super-secret-token",
                "Cookie": "session=private-cookie",
                "Stripe-Signature": "whsec_private-signature",
            },
        )
    finally:
        app_module.app.logger.removeHandler(handler)
    logs = stream.getvalue()
    assert "super-secret-token" not in logs
    assert "private-cookie" not in logs
    assert "whsec_private-signature" not in logs


def test_500_handler_hides_exception_internals(readiness_client):
    application = app_module.app
    original_view = application.view_functions["health_live"]
    original_testing = application.config["TESTING"]
    original_propagation = application.config.get("PROPAGATE_EXCEPTIONS")

    def broken_health():
        raise RuntimeError("private-internal-detail")

    application.view_functions["health_live"] = broken_health
    application.config.update(TESTING=False, PROPAGATE_EXCEPTIONS=False)
    try:
        response = application.test_client().get("/health/live")
    finally:
        application.view_functions["health_live"] = original_view
        application.config.update(TESTING=original_testing, PROPAGATE_EXCEPTIONS=original_propagation)
    assert response.status_code == 500
    assert "private-internal-detail" not in response.get_data(as_text=True)
    assert "Internal server error" in response.get_data(as_text=True)


def test_docker_context_excludes_secrets_databases_and_artifacts():
    dockerignore = Path(".dockerignore").read_text(encoding="utf-8")
    for pattern in (".env", "*.db", "*.sqlite", "*.log", ".git", ".pytest_cache", "artifacts"):
        assert pattern in dockerignore
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")
    assert "FROM python:3.12-slim" in dockerfile
    assert "USER blacksea" in dockerfile


def test_env_example_contains_placeholders_only():
    example = Path(".env.example").read_text(encoding="utf-8")
    assert "sk_live_" not in example
    assert "pk_live_" not in example
    assert "blackseaconnect.com" not in example
    assert "replace" in example
