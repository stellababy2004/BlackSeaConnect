from types import SimpleNamespace

import pytest
from flask import Response

import app as app_module


REPORT_ONLY = "Content-Security-Policy-Report-Only"
BASELINE_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "SAMEORIGIN",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


def directives(response):
    parts = [part.strip().split() for part in response.headers[REPORT_ONLY].split(";")]
    assert len(parts) == len({part[0] for part in parts})
    return {part[0]: set(part[1:]) for part in parts}


@pytest.mark.parametrize("path,status", [
    ("/", 200),
    ("/health/live", 200),
    ("/static/js/analytics.js", 200),
    ("/service-worker.js", 200),
    ("/static/site.webmanifest", 200),
    ("/missing-csp-audit-page", 404),
    ("/admin/pilot-requests", 503),
])
def test_report_only_header_on_real_responses(monkeypatch, path, status):
    monkeypatch.delenv("ADMIN_USERNAME", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    response = app_module.app.test_client().get(path)
    assert response.status_code == status
    assert len(response.headers.getlist(REPORT_ONLY)) == 1
    assert "Content-Security-Policy" not in response.headers
    for name, value in BASELINE_HEADERS.items():
        assert response.headers[name] == value


def test_csp_sources_match_current_resource_types():
    response = app_module.app.test_client().get("/health/live")
    policy = directives(response)
    assert policy == {
        "default-src": {"'self'"},
        "base-uri": {"'self'"},
        "object-src": {"'none'"},
        "frame-ancestors": {"'self'"},
        "script-src": {
            "'self'", "'unsafe-inline'", "https://www.googletagmanager.com", "https://*.clarity.ms",
        },
        "style-src": {"'self'", "'unsafe-inline'"},
        # Provider photos/logos are dynamic HTTPS URLs; upload previews use blobs.
        "img-src": {"'self'", "blob:", "https:"},
        "font-src": {"'self'"},
        "connect-src": {
            "'self'", "https://www.googletagmanager.com", "https://*.google-analytics.com",
            "https://*.google.com", "https://*.clarity.ms", "https://c.bing.com",
        },
        # Local POSTs redirect to hosted Stripe Checkout/Connect.
        "form-action": {"'self'", "https://checkout.stripe.com", "https://connect.stripe.com"},
        "frame-src": {"'self'"},
        "worker-src": {"'self'"},
        "manifest-src": {"'self'"},
    }
    assert "unsafe-eval" not in response.headers[REPORT_ONLY]
    assert "data:" not in response.headers[REPORT_ONLY]
    assert {name for name, sources in policy.items() if "'unsafe-inline'" in sources} == {
        "script-src", "style-src",
    }


@pytest.mark.parametrize("environment,site_url,hsts", [
    ("development", "http://localhost:5010", False),
    ("staging", "https://staging.example.com", False),
    ("production", "http://example.com", False),
    ("production", "https://blackseaconnect.com", True),
])
def test_existing_hsts_conditions_are_unchanged(monkeypatch, environment, site_url, hsts):
    monkeypatch.setattr(app_module, "SETTINGS", SimpleNamespace(environment=environment))
    monkeypatch.setattr(app_module, "SITE_URL", site_url)
    response = app_module._apply_security_headers(Response("ok"))
    assert ("Strict-Transport-Security" in response.headers) is hsts
    if hsts:
        assert response.headers["Strict-Transport-Security"] == "max-age=31536000; includeSubDomains"
    for name, value in BASELINE_HEADERS.items():
        assert response.headers[name] == value
    assert REPORT_ONLY in response.headers
    assert "Content-Security-Policy" not in response.headers


def test_security_hook_preserves_explicit_header_values():
    headers = {**{name: "custom-value" for name in BASELINE_HEADERS}, REPORT_ONLY: "default-src 'none'"}
    response = app_module._apply_security_headers(Response("ok", headers=headers))
    for name, value in headers.items():
        assert response.headers[name] == value


def test_report_only_header_on_redirect_and_error_statuses():
    for status in (302, 401, 429, 500):
        response = app_module._apply_security_headers(Response(status=status))
        assert response.status_code == status
        assert REPORT_ONLY in response.headers
        assert "Content-Security-Policy" not in response.headers
