"""Environment configuration and sanitized startup validation."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import sqlite3
import tempfile
from typing import Mapping
from urllib.parse import urlparse


ENVIRONMENTS = {"development", "test", "staging", "production"}
DEFAULT_DEVELOPMENT_SECRET = "blacksea-connect-development-only"
_TRUE = {"1", "true", "yes", "on", "enabled"}
_FALSE = {"0", "false", "no", "off", "disabled"}


class ConfigurationError(RuntimeError):
    """Raised with sanitized configuration failures only."""

    def __init__(self, issues: list[str] | tuple[str, ...]):
        self.issues = tuple(issues)
        super().__init__("Invalid application configuration: " + "; ".join(self.issues))


def _boolean(source: Mapping[str, str], name: str, default: bool) -> bool:
    raw = str(source.get(name, "") or "").strip().lower()
    if not raw:
        return default
    if raw in _TRUE:
        return True
    if raw in _FALSE:
        return False
    raise ConfigurationError([f"{name} must be an explicit boolean"])


@dataclass(frozen=True)
class AppSettings:
    environment: str
    site_url: str
    secret_key: str
    database_path: Path
    stripe_secret_key: str
    stripe_publishable_key: str
    stripe_webhook_secret: str
    stripe_mode: str
    stripe_connect_enabled: bool
    manual_finance_enabled: bool
    log_level: str
    trust_proxy_headers: bool
    session_cookie_secure: bool
    session_cookie_samesite: str
    proxy_headers_explicit: bool

    def flask_mapping(self) -> dict[str, object]:
        return {
            "APP_ENV": self.environment,
            "SITE_URL": self.site_url,
            "SECRET_KEY": self.secret_key,
            "DATABASE_PATH": str(self.database_path),
            "STRIPE_MODE": self.stripe_mode,
            "STRIPE_CONNECT_ENABLED": self.stripe_connect_enabled,
            "MANUAL_FINANCE_ENABLED": self.manual_finance_enabled,
            "LOG_LEVEL": self.log_level,
            "TRUST_PROXY_HEADERS": self.trust_proxy_headers,
            "SESSION_COOKIE_SECURE": self.session_cookie_secure,
            "SESSION_COOKIE_SAMESITE": self.session_cookie_samesite,
        }

    def diagnostics(self) -> dict[str, object]:
        return {
            "environment": self.environment,
            "https": urlparse(self.site_url).scheme == "https",
            "database_configured": bool(str(self.database_path)),
            "stripe_connect_enabled": self.stripe_connect_enabled,
            "stripe_mode": self.stripe_mode if self.stripe_mode in {"test", "live"} else "invalid",
            "stripe_secret_configured": bool(self.stripe_secret_key),
            "stripe_publishable_configured": bool(self.stripe_publishable_key),
            "stripe_webhook_configured": bool(self.stripe_webhook_secret),
            "manual_finance_enabled": self.manual_finance_enabled,
            "secure_session_cookie": self.session_cookie_secure,
            "proxy_headers_explicit": self.proxy_headers_explicit,
        }


def load_settings(environ: Mapping[str, str] | None = None) -> AppSettings:
    source = os.environ if environ is None else environ
    environment = str(source.get("APP_ENV", "development") or "development").strip().lower()
    if environment == "prod":
        environment = "production"
    if environment not in ENVIRONMENTS:
        raise ConfigurationError(["APP_ENV must be development, test, staging, or production"])

    protected = environment in {"staging", "production"}
    if environment == "test":
        default_database = Path(tempfile.gettempdir()) / f"blackseaconnect-test-{os.getpid()}.db"
    else:
        default_database = Path("data") / "blacksea_owner.db"

    defaults = {
        "SITE_URL": "http://localhost:5010" if environment != "test" else "http://test.local",
        "SECRET_KEY": DEFAULT_DEVELOPMENT_SECRET if environment != "test" else "test-only-secret-key-not-for-deployment",
        "DATABASE_PATH": str(default_database),
        "STRIPE_MODE": "test",
        "LOG_LEVEL": "DEBUG" if environment == "development" else "INFO",
        "SESSION_COOKIE_SAMESITE": "Lax",
    }
    required = ["SITE_URL", "SECRET_KEY", "DATABASE_PATH", "STRIPE_MODE", "TRUST_PROXY_HEADERS"]
    missing = [name for name in required if protected and not str(source.get(name, "") or "").strip()]
    if missing:
        raise ConfigurationError([f"missing required variable: {name}" for name in missing])

    def value(name: str) -> str:
        return str(source.get(name, defaults.get(name, "")) or "").strip()

    settings = AppSettings(
        environment=environment,
        site_url=value("SITE_URL").rstrip("/"),
        secret_key=value("SECRET_KEY"),
        database_path=Path(value("DATABASE_PATH")),
        stripe_secret_key=value("STRIPE_SECRET_KEY"),
        stripe_publishable_key=value("STRIPE_PUBLISHABLE_KEY"),
        stripe_webhook_secret=value("STRIPE_WEBHOOK_SECRET"),
        stripe_mode=value("STRIPE_MODE").lower(),
        stripe_connect_enabled=_boolean(source, "STRIPE_CONNECT_ENABLED", False),
        manual_finance_enabled=_boolean(source, "MANUAL_FINANCE_ENABLED", environment == "development"),
        log_level=value("LOG_LEVEL").upper(),
        trust_proxy_headers=_boolean(source, "TRUST_PROXY_HEADERS", False),
        session_cookie_secure=_boolean(source, "SESSION_COOKIE_SECURE", protected),
        session_cookie_samesite=value("SESSION_COOKIE_SAMESITE") or "Lax",
        proxy_headers_explicit="TRUST_PROXY_HEADERS" in source and bool(str(source.get("TRUST_PROXY_HEADERS", "")).strip()),
    )
    validate_settings(settings, check_database=protected)
    return settings


def _database_issues(database_path: Path) -> list[str]:
    issues: list[str] = []
    parent = database_path.parent
    if not parent.exists() or not parent.is_dir():
        return ["database directory does not exist"]
    try:
        with tempfile.NamedTemporaryFile(prefix=".write-check-", dir=parent, delete=True):
            pass
    except OSError:
        issues.append("database directory is not writable")
    if database_path.exists():
        try:
            connection = sqlite3.connect(str(database_path), timeout=2)
            connection.execute("SELECT name FROM sqlite_master LIMIT 1").fetchall()
            connection.execute("BEGIN IMMEDIATE")
            connection.rollback()
            connection.close()
        except (OSError, sqlite3.Error):
            issues.append("database is not readable and writable")
    return issues


def validate_settings(settings: AppSettings, *, check_database: bool = True) -> None:
    issues: list[str] = []
    protected = settings.environment in {"staging", "production"}
    parsed_url = urlparse(settings.site_url)
    if protected and (parsed_url.scheme != "https" or not parsed_url.netloc):
        issues.append("SITE_URL must be an absolute HTTPS URL")
    if settings.environment == "production" and settings.site_url != "https://blackseaconnect.com":
        issues.append("production SITE_URL must be https://blackseaconnect.com")
    if protected and (
        len(settings.secret_key) < 32
        or settings.secret_key == DEFAULT_DEVELOPMENT_SECRET
        or "change-me" in settings.secret_key.lower()
        or "placeholder" in settings.secret_key.lower()
    ):
        issues.append("SECRET_KEY must be a non-default value of at least 32 characters")
    if settings.stripe_mode not in {"test", "live"}:
        issues.append("STRIPE_MODE must be test or live")
    if settings.environment == "staging" and settings.stripe_mode != "test":
        issues.append("staging requires STRIPE_MODE=test")
    if settings.environment == "production" and settings.stripe_mode != "live":
        issues.append("production requires STRIPE_MODE=live")

    expected_secret = "sk_test_" if settings.environment != "production" else "sk_live_"
    expected_public = "pk_test_" if settings.environment != "production" else "pk_live_"
    if settings.stripe_secret_key and not settings.stripe_secret_key.startswith(expected_secret):
        issues.append("Stripe secret key mode does not match APP_ENV")
    if settings.stripe_publishable_key and not settings.stripe_publishable_key.startswith(expected_public):
        issues.append("Stripe publishable key mode does not match APP_ENV")
    if settings.stripe_connect_enabled:
        if not settings.stripe_secret_key:
            issues.append("STRIPE_SECRET_KEY is required when Stripe Connect is enabled")
        if not settings.stripe_publishable_key:
            issues.append("STRIPE_PUBLISHABLE_KEY is required when Stripe Connect is enabled")
        if not settings.stripe_webhook_secret.startswith("whsec_"):
            issues.append("STRIPE_WEBHOOK_SECRET is required when Stripe Connect is enabled")
    if settings.environment == "production" and settings.manual_finance_enabled:
        issues.append("MANUAL_FINANCE_ENABLED must be disabled in production")
    if settings.environment == "production" and not settings.session_cookie_secure:
        issues.append("SESSION_COOKIE_SECURE must be enabled in production")
    if protected and not settings.proxy_headers_explicit:
        issues.append("TRUST_PROXY_HEADERS must be explicitly configured")
    if settings.session_cookie_samesite.lower() not in {"lax", "strict", "none"}:
        issues.append("SESSION_COOKIE_SAMESITE must be Lax, Strict, or None")
    if settings.log_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        issues.append("LOG_LEVEL is invalid")
    if check_database:
        issues.extend(_database_issues(settings.database_path))
    if issues:
        raise ConfigurationError(issues)


if __name__ == "__main__":
    current = load_settings()
    print(f"configuration valid for {current.environment}")
