from datetime import datetime, timezone
from datetime import timedelta
from email.message import EmailMessage
from email.utils import formataddr, parseaddr
import hashlib
import csv
import io
import hmac
from functools import wraps
from contextlib import contextmanager
from pathlib import Path
import json
import os
import sqlite3
import smtplib
import urllib.error
import urllib.request
import urllib.parse
from threading import Thread
from uuid import uuid4

from flask import Flask, Response, g, jsonify, redirect, render_template, request, session, url_for

from seo_pages import SEO_LANDING_PAGE_ORDER, SEO_LANDING_PAGES, SEO_SUPPORTED_LANGS, resolve_seo_landing_page

app = Flask(__name__)
app.json.ensure_ascii = False
app.secret_key = os.getenv("SECRET_KEY", "blacksea-connect-dev-secret")
SITE_URL = os.environ.get("SITE_URL", "https://blackseaconnect.com").rstrip("/")
PUBLIC_SITEMAP_PATHS = (
    "/",
    "/services",
    "/demo/operations",
    "/guest/a-302",
    "/partners",
    "/partners/apply",
    "/professionals",
    "/professionals/apply",
    "/network",
    "/request-service",
    "/owners/register",
    "/pilot-access",
    *SEO_LANDING_PAGE_ORDER,
)

CRM_PIPELINE_STATUS_VALUES = ("new", "contacted", "qualified", "converted", "lost")
CRM_PIPELINE_STATUS_ALIASES = {
    "pending": "new",
    "approved": "converted",
    "rejected": "lost",
}
PILOT_STATUS_VALUES = ("new", "contacted", "qualified", "converted", "lost")
PILOT_STATUS_ALIASES = {
    "rejected": "lost",
}
PARTNER_STATUS_VALUES = CRM_PIPELINE_STATUS_VALUES
PROFESSIONAL_STATUS_VALUES = CRM_PIPELINE_STATUS_VALUES
PARTNER_SERVICE_CATEGORIES = (
    "Transfers",
    "Cleaning",
    "Property Maintenance",
    "Concierge",
    "Real Estate",
    "Hospitality",
    "Other",
)
PARTNER_SERVICE_CATEGORY_TRANSLATION_KEYS = {
    "Transfers": "partners.partnerServiceTransfers",
    "Cleaning": "partners.partnerServiceCleaning",
    "Property Maintenance": "partners.partnerServicePropertyMaintenance",
    "Concierge": "partners.partnerServiceConcierge",
    "Real Estate": "partners.partnerServiceRealEstate",
    "Hospitality": "partners.partnerServiceHospitality",
    "Other": "partners.partnerServiceOther",
}
PROFESSIONAL_SERVICE_CATEGORIES = (
    "Concierge",
    "Property Manager",
    "Guest Relations",
    "Maintenance",
    "Hospitality Consultant",
    "Real Estate Professional",
    "Other",
)
PROFESSIONAL_SERVICE_CATEGORY_TRANSLATION_KEYS = {
    "Concierge": "professionals.professionalCategoryConcierge",
    "Property Manager": "professionals.professionalCategoryPropertyManager",
    "Guest Relations": "professionals.professionalCategoryGuestRelations",
    "Maintenance": "professionals.professionalCategoryMaintenance",
    "Hospitality Consultant": "professionals.professionalCategoryHospitalityConsultant",
    "Real Estate Professional": "professionals.professionalCategoryRealEstateProfessional",
    "Other": "professionals.professionalCategoryOther",
}
NETWORK_SERVICE_CATEGORIES = (
    "Cleaning",
    "Property Management",
    "Concierge",
    "Transfers",
    "Laundry",
    "Plumbing",
    "Electrical",
    "Photography",
)
NETWORK_SERVICE_CATEGORY_TRANSLATION_KEYS = {
    "Cleaning": "network.networkCategoryCleaning",
    "Property Management": "network.networkCategoryPropertyManagement",
    "Concierge": "network.networkCategoryConcierge",
    "Transfers": "network.networkCategoryTransfers",
    "Laundry": "network.networkCategoryLaundry",
    "Plumbing": "network.networkCategoryPlumbing",
    "Electrical": "network.networkCategoryElectrical",
    "Photography": "network.networkCategoryPhotography",
}
SERVICE_REQUESTS_JSONL_PATH = Path("data") / "service_requests.jsonl"
OWNER_ACCOUNTS_JSONL_PATH = Path("data") / "owner_accounts.jsonl"
OWNER_PROPERTIES_JSONL_PATH = Path("data") / "owner_properties.jsonl"
OWNER_MAGIC_TOKENS_PATH = Path("data") / "owner_magic_tokens.jsonl"
OWNER_MAGIC_EMAIL_EVENTS_PATH = Path("data") / "owner_magic_email_events.jsonl"
OWNER_MAGIC_LINK_TTL_MINUTES = 30
SITE_LANGUAGE_SESSION_KEY = "site_lang"
SUPPORTED_LANGUAGES = {"bg", "en", "fr", "ru"}
OWNER_STATUS_VALUES = {"PILOT", "ACTIVE", "INACTIVE", "VIP"}
OWNER_STATUS_DEFAULT = "PILOT"
OWNER_LANGUAGE_DEFAULT = "bg"
OWNER_SESSION_ID_KEY = "owner_id"
OWNER_SESSION_EMAIL_KEY = "owner_email"
OWNER_SESSION_NAME_KEY = "owner_name"
OWNER_SESSION_LOGGED_IN_KEY = "owner_logged_in"
OWNER_DEMO_LOGIN_EMAIL = "owner@blackseaconnect.com"
OWNER_DEMO_LOGIN_PASSWORD = "demo1234"
OWNER_DEMO_PROFILE = {
    "id": "owner-demo",
    "full_name": "Elena Petrova",
    "email": "owner@blackseaconnect.com",
    "phone": "+359888111222",
    "property_type": "Villa",
    "city": "Varna",
    "property_name": "Sea View Villa",
    "number_of_units": 2,
    "notes": "Demo owner profile for local testing.",
}
OWNER_SERVICE_CATEGORIES = (
    "Cleaning",
    "Inspection",
    "Maintenance",
    "Airport Transfer",
    "Concierge Support",
    "Guest Issue",
    "Seasonal Preparation",
    "Other",
)
OWNER_SERVICE_CATEGORY_TRANSLATION_KEYS = {
    "Cleaning": "owners.ownerCategoryCleaning",
    "Inspection": "owners.ownerCategoryInspection",
    "Maintenance": "owners.ownerCategoryMaintenance",
    "Airport Transfer": "owners.ownerCategoryAirportTransfer",
    "Concierge Support": "owners.ownerCategoryConciergeSupport",
    "Guest Issue": "owners.ownerCategoryGuestIssue",
    "Seasonal Preparation": "owners.ownerCategorySeasonalPreparation",
    "Other": "owners.ownerCategoryOther",
}
OWNER_SERVICE_CATEGORY_MATCHES = {
    "Cleaning": "Cleaning",
    "Inspection": "Property Management",
    "Maintenance": "Property Management",
    "Airport Transfer": "Transfers",
    "Concierge Support": "Concierge",
    "Guest Issue": "Concierge",
    "Seasonal Preparation": "Property Management",
    "Other": "",
}
OWNER_SERVICE_CATEGORY_ALIASES = {
    "cleaning": "Cleaning",
    "inspection": "Inspection",
    "property inspection": "Inspection",
    "maintenance": "Maintenance",
    "airport transfer": "Airport Transfer",
    "airport transfers": "Airport Transfer",
    "concierge support": "Concierge Support",
    "concierge": "Concierge Support",
    "guest issue": "Guest Issue",
    "seasonal preparation": "Seasonal Preparation",
    "seasonal prep": "Seasonal Preparation",
    "other": "Other",
}
SERVICE_REQUEST_STATUS_VALUES = ("new", "assigned", "in_progress", "completed", "cancelled")
SERVICE_REQUEST_STATUS_ALIASES = {
    "in progress": "in_progress",
    "in-progress": "in_progress",
    "done": "completed",
    "canceled": "cancelled",
    "cancelled": "cancelled",
}


def _professional_service_category_items():
    return [
        {
            "label": category,
            "key": PROFESSIONAL_SERVICE_CATEGORY_TRANSLATION_KEYS[category],
        }
        for category in PROFESSIONAL_SERVICE_CATEGORIES
    ]


def _partner_service_category_items():
    return [
        {
            "label": category,
            "key": PARTNER_SERVICE_CATEGORY_TRANSLATION_KEYS[category],
        }
        for category in PARTNER_SERVICE_CATEGORIES
    ]


def _network_service_category_items():
    return [
        {
            "label": category,
            "key": NETWORK_SERVICE_CATEGORY_TRANSLATION_KEYS[category],
        }
        for category in NETWORK_SERVICE_CATEGORIES
    ]


def _owner_service_category_items():
    return [
        {
            "label": category,
            "key": OWNER_SERVICE_CATEGORY_TRANSLATION_KEYS[category],
        }
        for category in OWNER_SERVICE_CATEGORIES
    ]


def _normalize_owner_service_category(category):
    normalized = str(category or "").strip()
    if not normalized:
        return ""
    if normalized in OWNER_SERVICE_CATEGORIES:
        return normalized
    lowered = normalized.lower()
    if lowered in OWNER_SERVICE_CATEGORY_ALIASES:
        return OWNER_SERVICE_CATEGORY_ALIASES[lowered]
    title_case = normalized.title()
    return title_case if title_case in OWNER_SERVICE_CATEGORIES else ""


def _normalize_application_status(status):
    normalized = str(status or "").strip().lower()
    normalized = CRM_PIPELINE_STATUS_ALIASES.get(normalized, normalized)
    return normalized if normalized in CRM_PIPELINE_STATUS_VALUES else "new"


def _application_status_label(status):
    return _normalize_application_status(status).upper()


def _normalize_application_timeline(timeline, default_type):
    if not isinstance(timeline, list):
        return []

    normalized_timeline = []
    for entry in timeline:
        if not isinstance(entry, dict):
            continue

        normalized_entry = dict(entry)
        normalized_entry["type"] = str(normalized_entry.get("type", "")).strip() or default_type
        normalized_entry["created_at"] = str(normalized_entry.get("created_at", "")).strip()
        normalized_entry["title"] = str(normalized_entry.get("title", "")).strip()
        normalized_entry["detail"] = str(normalized_entry.get("detail", "")).strip()
        if "status" in normalized_entry:
            normalized_entry["status"] = _normalize_application_status(normalized_entry.get("status"))
        else:
            normalized_entry["status"] = ""
        normalized_timeline.append(normalized_entry)

    return normalized_timeline


def _append_application_timeline_event(record, event_type, title, detail="", status=None):
    timeline = list(record.get("timeline") or [])
    timeline.append({
        "type": event_type,
        "created_at": _utc_now_iso(),
        "title": title,
        "detail": detail,
        "status": _normalize_application_status(status or record.get("status", "new")),
    })
    record["timeline"] = timeline


def _application_status_counts(applications):
    counts = {status: 0 for status in CRM_PIPELINE_STATUS_VALUES}
    for record in applications:
        status = _normalize_application_status(record.get("status", "new"))
        if status in counts:
            counts[status] += 1
    return counts


def _service_request_fallback_id(record):
    parts = [
        str(record.get("created_at", "")),
        str(record.get("email", "")),
        str(record.get("name", "")),
        str(record.get("property_city", "")),
        str(record.get("service_category", "")),
    ]
    digest = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()
    return f"service-request-{digest[:16]}"


def _normalize_professional_badges(raw_badges):
    if isinstance(raw_badges, list):
        items = raw_badges
    elif isinstance(raw_badges, str):
        items = raw_badges.replace("\r", "\n").replace("|", "\n").replace(",", "\n").split("\n")
    else:
        items = []

    badges = []
    for item in items:
        badge = str(item or "").strip()
        if badge and badge not in badges:
            badges.append(badge)
    return badges


def _normalize_bool_field(value):
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _normalize_network_service_category(service_type):
    normalized = str(service_type or "").strip().lower()
    if normalized in {"cleaning"}:
        return "Cleaning"
    if normalized in {"property management", "maintenance", "real estate support"}:
        return "Property Management"
    if normalized in {"concierge"}:
        return "Concierge"
    if normalized in {"airport transfer", "transfer", "transfers"}:
        return "Transfers"
    if normalized in {"laundry"}:
        return "Laundry"
    if normalized in {"plumbing"}:
        return "Plumbing"
    if normalized in {"electrical"}:
        return "Electrical"
    if normalized in {"photography"}:
        return "Photography"
    return "Property Management"


def _shorten_public_description(description, limit=160):
    text = str(description or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def _build_network_provider(record):
    provider = dict(record)
    provider["category"] = _normalize_network_service_category(provider.get("service_type"))
    provider["category_key"] = NETWORK_SERVICE_CATEGORY_TRANSLATION_KEYS[provider["category"]]
    provider["badges"] = _normalize_professional_badges(provider.get("badges", []))
    provider["available_for_requests"] = _normalize_bool_field(provider.get("available_for_requests", True))
    provider["display_badges"] = [badge for badge in ([provider["category"]] + provider["badges"] + (["Featured"] if provider.get("featured") else [])) if badge]
    provider["short_description"] = _shorten_public_description(provider.get("description", ""))
    return provider


def _load_network_providers():
    providers = []
    for record in _load_professional_applications():
        if _normalize_professional_status(record.get("status")) != "converted":
            continue
        providers.append(_build_network_provider(record))
    providers.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    providers.sort(key=lambda item: bool(item.get("featured")), reverse=True)
    return providers


def _find_network_provider(provider_id):
    for record in _load_network_providers():
        if str(record.get("id", "")) == str(provider_id):
            return record
    return None


def _filter_network_providers(providers, city="", category=""):
    city_filter = str(city or "").strip().lower()
    category_filter = str(category or "").strip()
    filtered = []

    for provider in providers:
        if city_filter and city_filter not in str(provider.get("city", "")).strip().lower():
            continue
        if category_filter and provider.get("category") != category_filter:
            continue
        filtered.append(provider)

    return filtered


def _group_network_providers(providers):
    grouped = []
    for category in NETWORK_SERVICE_CATEGORIES:
        category_providers = [provider for provider in providers if provider.get("category") == category]
        grouped.append({
            "category": category,
            "providers": category_providers,
            "key": NETWORK_SERVICE_CATEGORY_TRANSLATION_KEYS[category],
        })
    return grouped


def _owner_account_fallback_id(record):
    parts = [
        str(record.get("created_at", "")),
        str(record.get("email", "")),
        str(record.get("full_name", "")),
        str(record.get("city", "")),
    ]
    digest = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()
    return f"owner-{digest[:16]}"


def _normalize_owner_account(record):
    if not isinstance(record, dict):
        return None

    normalized = dict(record)
    normalized["id"] = str(normalized.get("id", "")).strip() or _owner_account_fallback_id(normalized)
    normalized["created_at"] = str(normalized.get("created_at", "")).strip()

    for field in (
        "full_name",
        "email",
        "phone",
        "property_type",
        "city",
        "property_name",
        "notes",
        "internal_notes",
        "last_login_at",
    ):
        normalized[field] = str(normalized.get(field, "")).strip()

    number_of_units = str(normalized.get("number_of_units", "")).strip()
    normalized["number_of_units"] = int(number_of_units) if number_of_units.isdigit() else 0
    normalized["status"] = _normalize_owner_status(normalized.get("status", OWNER_STATUS_DEFAULT))
    normalized["language"] = _normalize_owner_language(normalized.get("language", OWNER_LANGUAGE_DEFAULT)) or OWNER_LANGUAGE_DEFAULT
    return normalized


def _normalize_owner_status(status):
    normalized = str(status or "").strip().upper()
    return normalized if normalized in OWNER_STATUS_VALUES else OWNER_STATUS_DEFAULT


def _normalize_owner_language(language):
    normalized = str(language or "").strip().lower()
    return normalized if normalized in SUPPORTED_LANGUAGES else ""


def _owner_db_path():
    return Path(os.getenv("OWNER_DB_PATH", str(Path("data") / "blacksea_owner.db")))


@contextmanager
def _owner_db_connection():
    db_path = _owner_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = MEMORY")
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _owner_table_columns(conn, table_name):
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {str(row["name"]) for row in rows}


def _ensure_owner_account_schema(conn):
    existing_columns = _owner_table_columns(conn, "owner_accounts")
    required_columns = {
        "status": f"TEXT NOT NULL DEFAULT '{OWNER_STATUS_DEFAULT}'",
        "language": f"TEXT NOT NULL DEFAULT '{OWNER_LANGUAGE_DEFAULT}'",
        "last_login_at": "TEXT NOT NULL DEFAULT ''",
        "internal_notes": "TEXT NOT NULL DEFAULT ''",
    }
    for column_name, column_sql in required_columns.items():
        if column_name not in existing_columns:
            conn.execute(f"ALTER TABLE owner_accounts ADD COLUMN {column_name} {column_sql}")


def _ensure_owner_db_schema(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS owner_db_meta (
            meta_key TEXT PRIMARY KEY,
            meta_value TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS owner_accounts (
            email TEXT PRIMARY KEY COLLATE NOCASE,
            id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            full_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            property_type TEXT NOT NULL,
            city TEXT NOT NULL,
            property_name TEXT NOT NULL,
            number_of_units INTEGER NOT NULL,
            notes TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'PILOT',
            language TEXT NOT NULL DEFAULT 'bg',
            last_login_at TEXT NOT NULL DEFAULT '',
            internal_notes TEXT NOT NULL DEFAULT ''
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS owner_properties (
            id TEXT PRIMARY KEY,
            owner_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            name TEXT NOT NULL,
            property_type TEXT NOT NULL,
            location TEXT NOT NULL,
            bedrooms INTEGER NOT NULL,
            bathrooms INTEGER NOT NULL,
            guest_capacity INTEGER NOT NULL,
            operating_mode TEXT NOT NULL,
            notes TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS owner_magic_tokens (
            token TEXT PRIMARY KEY,
            email TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS owner_magic_email_events (
            sequence INTEGER PRIMARY KEY AUTOINCREMENT,
            id TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            event TEXT NOT NULL,
            submitted_email TEXT NOT NULL,
            account_found INTEGER,
            delivery TEXT NOT NULL,
            email_masked TEXT NOT NULL,
            reason TEXT NOT NULL,
            source TEXT NOT NULL,
            language TEXT NOT NULL,
            smtp_message_id TEXT NOT NULL DEFAULT ''
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS owner_activity_events (
            sequence INTEGER PRIMARY KEY AUTOINCREMENT,
            id TEXT NOT NULL UNIQUE,
            owner_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            event_type TEXT NOT NULL,
            title TEXT NOT NULL,
            detail TEXT NOT NULL DEFAULT ''
        )
        """
    )
    _ensure_owner_account_schema(conn)


def _owner_jsonl_signature(path):
    try:
        stat = path.stat()
    except FileNotFoundError:
        return ""
    return f"{stat.st_mtime_ns}:{stat.st_size}"


def _owner_db_meta_get(conn, meta_key):
    row = conn.execute("SELECT meta_value FROM owner_db_meta WHERE meta_key = ?", (meta_key,)).fetchone()
    return str(row["meta_value"]) if row else ""


def _owner_db_meta_set(conn, meta_key, meta_value):
    conn.execute(
        """
        INSERT INTO owner_db_meta (meta_key, meta_value)
        VALUES (?, ?)
        ON CONFLICT(meta_key) DO UPDATE SET meta_value = excluded.meta_value
        """,
        (meta_key, meta_value),
    )


def _owner_account_from_row(row):
    return {
        "email": str(row["email"]),
        "id": str(row["id"]),
        "created_at": str(row["created_at"]),
        "full_name": str(row["full_name"]),
        "phone": str(row["phone"]),
        "property_type": str(row["property_type"]),
        "city": str(row["city"]),
        "property_name": str(row["property_name"]),
        "number_of_units": int(row["number_of_units"] or 0),
        "notes": str(row["notes"]),
        "status": _normalize_owner_status(row["status"] if "status" in row.keys() else OWNER_STATUS_DEFAULT),
        "language": _normalize_owner_language(row["language"] if "language" in row.keys() else OWNER_LANGUAGE_DEFAULT) or OWNER_LANGUAGE_DEFAULT,
        "last_login_at": str(row["last_login_at"]) if "last_login_at" in row.keys() else "",
        "internal_notes": str(row["internal_notes"]) if "internal_notes" in row.keys() else "",
    }


def _load_owner_activity_events(owner_id=None):
    with _owner_db_connection() as conn:
        _ensure_owner_db_schema(conn)
        _migrate_owner_jsonl_backups(conn)
        query = """
            SELECT id, owner_id, created_at, event_type, title, detail
            FROM owner_activity_events
        """
        params = []
        target_owner_id = str(owner_id or "").strip()
        if target_owner_id:
            query += " WHERE owner_id = ?"
            params.append(target_owner_id)
        query += " ORDER BY created_at DESC, sequence DESC"
        rows = conn.execute(query, params).fetchall()

    return [
        {
            "id": str(row["id"]),
            "owner_id": str(row["owner_id"]),
            "created_at": str(row["created_at"]),
            "event_type": str(row["event_type"]),
            "title": str(row["title"]),
            "detail": str(row["detail"]),
        }
        for row in rows
    ]


def _append_owner_activity_event(owner_id, event_type, title, detail=""):
    target_owner_id = str(owner_id or "").strip()
    if not target_owner_id:
        return None

    event = {
        "id": uuid4().hex,
        "owner_id": target_owner_id,
        "created_at": _utc_now_iso(),
        "event_type": str(event_type or "").strip(),
        "title": str(title or "").strip(),
        "detail": str(detail or "").strip(),
    }
    if not event["event_type"] or not event["title"]:
        return None

    try:
        with _owner_db_connection() as conn:
            _ensure_owner_db_schema(conn)
            _migrate_owner_jsonl_backups(conn)
            conn.execute(
                """
                INSERT INTO owner_activity_events (id, owner_id, created_at, event_type, title, detail)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event["id"],
                    event["owner_id"],
                    event["created_at"],
                    event["event_type"],
                    event["title"],
                    event["detail"],
                ),
            )
    except Exception as exc:
        app.logger.warning("Owner activity event append failed for %s: %s", target_owner_id, type(exc).__name__)
        return None
    return event


def _owner_login_event_detail(login_source, language):
    source = str(login_source or "").strip() or "magic link"
    lang = _normalize_owner_language(language) or OWNER_LANGUAGE_DEFAULT
    return f"Source: {source}; language: {lang}"


def _import_owner_accounts_jsonl(conn):
    path = OWNER_ACCOUNTS_JSONL_PATH
    if not path.exists():
        return

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            normalized = _normalize_owner_account(record)
            if not normalized:
                continue

            conn.execute(
                """
                INSERT INTO owner_accounts (
                    email, id, created_at, full_name, phone, property_type, city, property_name, number_of_units, notes, status, language, last_login_at, internal_notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(email) DO UPDATE SET
                    id = excluded.id,
                    created_at = excluded.created_at,
                    full_name = excluded.full_name,
                    phone = excluded.phone,
                    property_type = excluded.property_type,
                    city = excluded.city,
                    property_name = excluded.property_name,
                    number_of_units = excluded.number_of_units,
                    notes = excluded.notes,
                    status = excluded.status,
                    language = excluded.language,
                    last_login_at = excluded.last_login_at,
                    internal_notes = excluded.internal_notes
                """,
                (
                    normalized["email"],
                    normalized["id"],
                    normalized["created_at"],
                    normalized["full_name"],
                    normalized["phone"],
                    normalized["property_type"],
                    normalized["city"],
                    normalized["property_name"],
                    normalized["number_of_units"],
                    normalized["notes"],
                    normalized["status"],
                    normalized["language"],
                    normalized["last_login_at"],
                    normalized["internal_notes"],
                ),
            )


def _import_owner_properties_jsonl(conn):
    path = OWNER_PROPERTIES_JSONL_PATH
    if not path.exists():
        return

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            normalized = _normalize_owner_property(record)
            if not normalized:
                continue

            conn.execute(
                """
                INSERT INTO owner_properties (
                    id, owner_id, created_at, name, property_type, location, bedrooms, bathrooms, guest_capacity, operating_mode, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    owner_id = excluded.owner_id,
                    created_at = excluded.created_at,
                    name = excluded.name,
                    property_type = excluded.property_type,
                    location = excluded.location,
                    bedrooms = excluded.bedrooms,
                    bathrooms = excluded.bathrooms,
                    guest_capacity = excluded.guest_capacity,
                    operating_mode = excluded.operating_mode,
                    notes = excluded.notes
                """,
                (
                    normalized["id"],
                    normalized["owner_id"],
                    normalized["created_at"],
                    normalized["name"],
                    normalized["property_type"],
                    normalized["location"],
                    normalized["bedrooms"],
                    normalized["bathrooms"],
                    normalized["guest_capacity"],
                    normalized["operating_mode"],
                    normalized["notes"],
                ),
            )


def _import_owner_magic_tokens_jsonl(conn):
    path = OWNER_MAGIC_TOKENS_PATH
    if not path.exists():
        return

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            token = str(record.get("token", "")).strip()
            email = str(record.get("email", "")).strip()
            created_at = str(record.get("created_at", "")).strip()
            if not token or not email or not created_at:
                continue

            conn.execute(
                """
                INSERT INTO owner_magic_tokens (token, email, created_at)
                VALUES (?, ?, ?)
                ON CONFLICT(token) DO UPDATE SET
                    email = excluded.email,
                    created_at = excluded.created_at
                """,
                (token, email, created_at),
            )


def _import_owner_magic_email_events_jsonl(conn):
    path = OWNER_MAGIC_EMAIL_EVENTS_PATH
    if not path.exists():
        return

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            event = str(record.get("event", "")).strip()
            email_masked = str(record.get("email_masked", "")).strip()
            reason = str(record.get("reason", "")).strip()
            source = str(record.get("source", "")).strip()
            language = str(record.get("language", "")).strip().lower()
            created_at = str(record.get("created_at", "")).strip()
            event_id = str(record.get("id", "")).strip()
            timestamp = str(record.get("timestamp", created_at)).strip() or created_at
            if not event or not email_masked or not reason or not source or not language or not created_at or not event_id:
                continue

            account_found = record.get("account_found")
            if account_found is None:
                account_found_value = None
            else:
                account_found_value = 1 if bool(account_found) else 0

            conn.execute(
                """
                INSERT INTO owner_magic_email_events (
                    id, created_at, timestamp, event, submitted_email, account_found, delivery, email_masked, reason, source, language, smtp_message_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    created_at = excluded.created_at,
                    timestamp = excluded.timestamp,
                    event = excluded.event,
                    submitted_email = excluded.submitted_email,
                    account_found = excluded.account_found,
                    delivery = excluded.delivery,
                    email_masked = excluded.email_masked,
                    reason = excluded.reason,
                    source = excluded.source,
                    language = excluded.language,
                    smtp_message_id = excluded.smtp_message_id
                """,
                (
                    event_id,
                    created_at,
                    timestamp,
                    event,
                    str(record.get("submitted_email", "")).strip(),
                    account_found_value,
                    str(record.get("delivery", "")).strip(),
                    email_masked,
                    reason,
                    source,
                    language,
                    str(record.get("smtp_message_id", "")).strip(),
                ),
            )


def _migrate_owner_jsonl_backups(conn):
    migrations = (
        ("owner_accounts_jsonl_signature", OWNER_ACCOUNTS_JSONL_PATH, _import_owner_accounts_jsonl),
        ("owner_properties_jsonl_signature", OWNER_PROPERTIES_JSONL_PATH, _import_owner_properties_jsonl),
        ("owner_magic_tokens_jsonl_signature", OWNER_MAGIC_TOKENS_PATH, _import_owner_magic_tokens_jsonl),
        ("owner_magic_email_events_jsonl_signature", OWNER_MAGIC_EMAIL_EVENTS_PATH, _import_owner_magic_email_events_jsonl),
    )

    for meta_key, path, importer in migrations:
        signature = _owner_jsonl_signature(path)
        if not signature:
            continue

        if _owner_db_meta_get(conn, meta_key) == signature:
            continue

        importer(conn)
        _owner_db_meta_set(conn, meta_key, signature)


def _load_owner_accounts():
    with _owner_db_connection() as conn:
        _ensure_owner_db_schema(conn)
        _migrate_owner_jsonl_backups(conn)
        rows = conn.execute(
            """
            SELECT email, id, created_at, full_name, phone, property_type, city, property_name, number_of_units, notes, status, language, last_login_at, internal_notes
            FROM owner_accounts
            ORDER BY created_at DESC, email DESC
            """
        ).fetchall()

    return [_owner_account_from_row(row) for row in rows]


def _save_owner_accounts(accounts):
    try:
        with _owner_db_connection() as conn:
            _ensure_owner_db_schema(conn)
            _migrate_owner_jsonl_backups(conn)
            conn.execute("DELETE FROM owner_accounts")
            for record in accounts:
                normalized = _normalize_owner_account(record)
                if not normalized:
                    continue
                conn.execute(
                    """
                    INSERT INTO owner_accounts (
                        email, id, created_at, full_name, phone, property_type, city, property_name, number_of_units, notes, status, language, last_login_at, internal_notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        normalized["email"],
                        normalized["id"],
                        normalized["created_at"],
                        normalized["full_name"],
                        normalized["phone"],
                        normalized["property_type"],
                        normalized["city"],
                        normalized["property_name"],
                        normalized["number_of_units"],
                        normalized["notes"],
                        normalized["status"],
                        normalized["language"],
                        normalized["last_login_at"],
                        normalized["internal_notes"],
                    ),
                )
    except Exception as exc:
        app.logger.warning(
            "Owner accounts write failed for %s: %s",
            str(_owner_db_path().resolve()),
            type(exc).__name__,
        )
        return False

    return True


def _find_owner_account_by_email(email):
    target_raw = str(email or "")
    target_email = target_raw.strip().lower()
    if not target_email:
        return None

    with _owner_db_connection() as conn:
        _ensure_owner_db_schema(conn)
        _migrate_owner_jsonl_backups(conn)
        row = conn.execute(
            """
            SELECT email, id, created_at, full_name, phone, property_type, city, property_name, number_of_units, notes, status, language, last_login_at, internal_notes
            FROM owner_accounts
            WHERE email = ?
            LIMIT 1
            """,
            (target_email,),
        ).fetchone()

    if row:
        return _owner_account_from_row(row)
    return None


def _find_owner_account(account_id):
    target_account_id = str(account_id or "").strip()
    if not target_account_id:
        return None

    with _owner_db_connection() as conn:
        _ensure_owner_db_schema(conn)
        _migrate_owner_jsonl_backups(conn)
        row = conn.execute(
            """
            SELECT email, id, created_at, full_name, phone, property_type, city, property_name, number_of_units, notes, status, language, last_login_at, internal_notes
            FROM owner_accounts
            WHERE id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (target_account_id,),
        ).fetchone()

    if row:
        return _owner_account_from_row(row)
    return None


def _upsert_owner_account(record):
    normalized = _normalize_owner_account(record)
    if not normalized:
        return None

    target_email = str(normalized.get("email", "")).strip().lower()
    existing_account = _find_owner_account_by_email(target_email)
    created = not bool(existing_account)

    if existing_account:
        normalized["id"] = existing_account.get("id", normalized["id"])
        normalized["created_at"] = existing_account.get("created_at", normalized["created_at"])
        normalized["status"] = _normalize_owner_status(record.get("status", existing_account.get("status", OWNER_STATUS_DEFAULT)))
        normalized["language"] = _normalize_owner_language(record.get("language", existing_account.get("language", OWNER_LANGUAGE_DEFAULT))) or existing_account.get("language", OWNER_LANGUAGE_DEFAULT)
        normalized["last_login_at"] = str(record.get("last_login_at", existing_account.get("last_login_at", ""))).strip()
        normalized["internal_notes"] = str(record.get("internal_notes", existing_account.get("internal_notes", ""))).strip()
    else:
        normalized["status"] = _normalize_owner_status(normalized.get("status", OWNER_STATUS_DEFAULT))
        normalized["language"] = _normalize_owner_language(normalized.get("language", OWNER_LANGUAGE_DEFAULT)) or OWNER_LANGUAGE_DEFAULT
        normalized["last_login_at"] = str(normalized.get("last_login_at", "")).strip()
        normalized["internal_notes"] = str(normalized.get("internal_notes", "")).strip()

    try:
        with _owner_db_connection() as conn:
            _ensure_owner_db_schema(conn)
            _migrate_owner_jsonl_backups(conn)
            conn.execute(
                """
                INSERT INTO owner_accounts (
                    email, id, created_at, full_name, phone, property_type, city, property_name, number_of_units, notes, status, language, last_login_at, internal_notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(email) DO UPDATE SET
                    id = excluded.id,
                    created_at = excluded.created_at,
                    full_name = excluded.full_name,
                    phone = excluded.phone,
                    property_type = excluded.property_type,
                    city = excluded.city,
                    property_name = excluded.property_name,
                    number_of_units = excluded.number_of_units,
                    notes = excluded.notes,
                    status = excluded.status,
                    language = excluded.language,
                    last_login_at = excluded.last_login_at,
                    internal_notes = excluded.internal_notes
                """,
                (
                    normalized["email"],
                    normalized["id"],
                    normalized["created_at"],
                    normalized["full_name"],
                    normalized["phone"],
                    normalized["property_type"],
                    normalized["city"],
                    normalized["property_name"],
                    normalized["number_of_units"],
                    normalized["notes"],
                    normalized["status"],
                    normalized["language"],
                    normalized["last_login_at"],
                    normalized["internal_notes"],
                ),
            )
    except Exception as exc:
        app.logger.warning("Owner account write failed for %s: %s", _mask_email(target_email), type(exc).__name__)
        return None

    app.logger.info("Owner account created=%s for %s", created, _mask_email(target_email))
    persisted_account = _find_owner_account_by_email(target_email)
    if persisted_account:
        app.logger.info("Owner account persisted for %s", _mask_email(target_email))
    else:
        app.logger.warning("Owner account persistence verification failed for %s", _mask_email(target_email))
    return persisted_account


def _ensure_owner_account_exists(record):
    target_email = str(record.get("email", "")).strip().lower()
    if not target_email:
        return None

    existing_account = _find_owner_account_by_email(target_email)
    if existing_account:
        return existing_account

    return _upsert_owner_account(record)


def _seed_owner_account_if_missing(seed_record):
    target_email = str(seed_record.get("email", "")).strip().lower()
    if not target_email:
        return None, False

    existing_account = _find_owner_account_by_email(target_email)
    if existing_account:
        app.logger.info("Admin owner seed skipped; account already exists for %s", _mask_email(target_email))
        return existing_account, False

    seeded_account = _ensure_owner_account_exists(seed_record)
    if seeded_account:
        app.logger.info("Admin owner seed created account for %s", _mask_email(target_email))
    return seeded_account, True


def _owner_property_fallback_id(record):
    name = str(record.get("name", "")).strip().lower()
    location = str(record.get("location", "")).strip().lower()
    seed = f"{name}:{location}:{record.get('created_at', '')}"
    return f"property-{hashlib.sha256(seed.encode('utf-8')).hexdigest()[:16]}"


def _normalize_owner_property(record):
    if not isinstance(record, dict):
        return None

    normalized = dict(record)
    normalized["id"] = str(normalized.get("id", "")).strip() or _owner_property_fallback_id(normalized)
    normalized["owner_id"] = str(normalized.get("owner_id", "")).strip()
    normalized["created_at"] = str(normalized.get("created_at", "")).strip()
    normalized["name"] = str(normalized.get("name", "")).strip()
    normalized["property_type"] = str(normalized.get("property_type", "")).strip()
    normalized["location"] = str(normalized.get("location", "")).strip()
    normalized["notes"] = str(normalized.get("notes", "")).strip()

    for field in ("bedrooms", "bathrooms", "guest_capacity"):
        value = str(normalized.get(field, "")).strip()
        normalized[field] = int(value) if value.isdigit() else 0

    operating_mode = str(normalized.get("operating_mode", "")).strip().lower()
    normalized["operating_mode"] = "seasonal" if operating_mode == "seasonal" else "year-round"
    return normalized


def _load_owner_properties():
    with _owner_db_connection() as conn:
        _ensure_owner_db_schema(conn)
        _migrate_owner_jsonl_backups(conn)
        rows = conn.execute(
            """
            SELECT id, owner_id, created_at, name, property_type, location, bedrooms, bathrooms, guest_capacity, operating_mode, notes
            FROM owner_properties
            ORDER BY created_at DESC, id DESC
            """
        ).fetchall()

    return [
        {
            "id": str(row["id"]),
            "owner_id": str(row["owner_id"]),
            "created_at": str(row["created_at"]),
            "name": str(row["name"]),
            "property_type": str(row["property_type"]),
            "location": str(row["location"]),
            "bedrooms": int(row["bedrooms"] or 0),
            "bathrooms": int(row["bathrooms"] or 0),
            "guest_capacity": int(row["guest_capacity"] or 0),
            "operating_mode": str(row["operating_mode"]),
            "notes": str(row["notes"]),
        }
        for row in rows
    ]


def _save_owner_properties(properties):
    try:
        with _owner_db_connection() as conn:
            _ensure_owner_db_schema(conn)
            _migrate_owner_jsonl_backups(conn)
            conn.execute("DELETE FROM owner_properties")
            for record in properties:
                normalized = _normalize_owner_property(record)
                if not normalized:
                    continue
                conn.execute(
                    """
                    INSERT INTO owner_properties (
                        id, owner_id, created_at, name, property_type, location, bedrooms, bathrooms, guest_capacity, operating_mode, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        normalized["id"],
                        normalized["owner_id"],
                        normalized["created_at"],
                        normalized["name"],
                        normalized["property_type"],
                        normalized["location"],
                        normalized["bedrooms"],
                        normalized["bathrooms"],
                        normalized["guest_capacity"],
                        normalized["operating_mode"],
                        normalized["notes"],
                    ),
                )
    except Exception as exc:
        app.logger.warning(
            "Owner properties write failed for %s: %s",
            str(_owner_db_path().resolve()),
            type(exc).__name__,
        )
        return False
    return True


def _append_owner_property(record):
    normalized = _normalize_owner_property(record)
    if not normalized:
        return None

    try:
        with _owner_db_connection() as conn:
            _ensure_owner_db_schema(conn)
            _migrate_owner_jsonl_backups(conn)
            conn.execute(
                """
                INSERT INTO owner_properties (
                    id, owner_id, created_at, name, property_type, location, bedrooms, bathrooms, guest_capacity, operating_mode, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    owner_id = excluded.owner_id,
                    created_at = excluded.created_at,
                    name = excluded.name,
                    property_type = excluded.property_type,
                    location = excluded.location,
                    bedrooms = excluded.bedrooms,
                    bathrooms = excluded.bathrooms,
                    guest_capacity = excluded.guest_capacity,
                    operating_mode = excluded.operating_mode,
                    notes = excluded.notes
                """,
                (
                    normalized["id"],
                    normalized["owner_id"],
                    normalized["created_at"],
                    normalized["name"],
                    normalized["property_type"],
                    normalized["location"],
                    normalized["bedrooms"],
                    normalized["bathrooms"],
                    normalized["guest_capacity"],
                    normalized["operating_mode"],
                    normalized["notes"],
                ),
            )
    except Exception as exc:
        app.logger.warning("Owner property write failed for %s: %s", normalized.get("owner_id", ""), type(exc).__name__)
        return None
    return normalized


def _load_owner_magic_tokens():
    with _owner_db_connection() as conn:
        _ensure_owner_db_schema(conn)
        _migrate_owner_jsonl_backups(conn)
        rows = conn.execute(
            """
            SELECT token, email, created_at
            FROM owner_magic_tokens
            ORDER BY created_at DESC, token DESC
            """
        ).fetchall()

    return [
        {
            "token": str(row["token"]),
            "email": str(row["email"]),
            "created_at": str(row["created_at"]),
        }
        for row in rows
    ]


def _save_owner_magic_tokens(tokens):
    try:
        with _owner_db_connection() as conn:
            _ensure_owner_db_schema(conn)
            _migrate_owner_jsonl_backups(conn)
            conn.execute("DELETE FROM owner_magic_tokens")
            for record in tokens:
                token = str(record.get("token", "")).strip()
                email = str(record.get("email", "")).strip()
                created_at = str(record.get("created_at", "")).strip()
                if not token or not email or not created_at:
                    continue
                conn.execute(
                    """
                    INSERT INTO owner_magic_tokens (token, email, created_at)
                    VALUES (?, ?, ?)
                    """,
                    (token, email, created_at),
                )
    except Exception as exc:
        app.logger.warning(
            "Owner magic tokens write failed for %s: %s",
            str(_owner_db_path().resolve()),
            type(exc).__name__,
        )
        return False
    return True


def _create_owner_magic_token(email):
    token_record = {
        "token": uuid4().hex,
        "email": str(email or "").strip(),
        "created_at": _utc_now_iso(),
    }
    try:
        with _owner_db_connection() as conn:
            _ensure_owner_db_schema(conn)
            _migrate_owner_jsonl_backups(conn)
            conn.execute(
                """
                INSERT INTO owner_magic_tokens (token, email, created_at)
                VALUES (?, ?, ?)
                ON CONFLICT(token) DO UPDATE SET
                    email = excluded.email,
                    created_at = excluded.created_at
                """,
                (token_record["token"], token_record["email"], token_record["created_at"]),
            )
    except Exception as exc:
        app.logger.warning("Owner magic token write failed for %s: %s", _mask_email(email), type(exc).__name__)
        return None
    return token_record


def _find_owner_magic_token(token):
    target_token = str(token or "").strip()
    if not target_token:
        return None

    with _owner_db_connection() as conn:
        _ensure_owner_db_schema(conn)
        _migrate_owner_jsonl_backups(conn)
        row = conn.execute(
            """
            SELECT token, email, created_at
            FROM owner_magic_tokens
            WHERE token = ?
            LIMIT 1
            """,
            (target_token,),
        ).fetchone()

    if row:
        return {
            "token": str(row["token"]),
            "email": str(row["email"]),
            "created_at": str(row["created_at"]),
        }
    return None


def _consume_owner_magic_token(token):
    target_token = str(token or "").strip()
    if not target_token:
        return False

    try:
        with _owner_db_connection() as conn:
            _ensure_owner_db_schema(conn)
            _migrate_owner_jsonl_backups(conn)
            cursor = conn.execute("DELETE FROM owner_magic_tokens WHERE token = ?", (target_token,))
            return cursor.rowcount > 0
    except Exception as exc:
        app.logger.warning("Owner magic token consume failed for %s: %s", target_token, type(exc).__name__)
        return False


def _load_owner_magic_email_events():
    with _owner_db_connection() as conn:
        _ensure_owner_db_schema(conn)
        _migrate_owner_jsonl_backups(conn)
        rows = conn.execute(
            """
            SELECT id, created_at, timestamp, event, submitted_email, account_found, delivery, email_masked, reason, source, language, smtp_message_id
            FROM owner_magic_email_events
            ORDER BY sequence DESC
            """
        ).fetchall()

    events = []
    for row in rows:
        account_found_value = row["account_found"]
        if account_found_value is None:
            account_found = None
        else:
            account_found = bool(account_found_value)
        events.append({
            "id": str(row["id"]),
            "created_at": str(row["created_at"]),
            "timestamp": str(row["timestamp"]),
            "event": str(row["event"]),
            "submitted_email": str(row["submitted_email"]),
            "account_found": account_found,
            "delivery": str(row["delivery"]),
            "email_masked": str(row["email_masked"]),
            "reason": str(row["reason"]),
            "source": str(row["source"]),
            "language": str(row["language"]),
            "smtp_message_id": str(row["smtp_message_id"]),
        })
    return events


def _save_owner_magic_email_events(events):
    try:
        with _owner_db_connection() as conn:
            _ensure_owner_db_schema(conn)
            _migrate_owner_jsonl_backups(conn)
            conn.execute("DELETE FROM owner_magic_email_events")
            for record in events:
                event = str(record.get("event", "")).strip()
                email_masked = str(record.get("email_masked", "")).strip()
                reason = str(record.get("reason", "")).strip()
                source = str(record.get("source", "")).strip()
                language = str(record.get("language", "")).strip().lower()
                created_at = str(record.get("created_at", "")).strip()
                event_id = str(record.get("id", "")).strip()
                timestamp = str(record.get("timestamp", created_at)).strip() or created_at
                if not event or not email_masked or not reason or not source or not language or not created_at or not event_id:
                    continue
                account_found = record.get("account_found")
                account_found_value = None if account_found is None else (1 if bool(account_found) else 0)
                conn.execute(
                    """
                    INSERT INTO owner_magic_email_events (
                        id, created_at, timestamp, event, submitted_email, account_found, delivery, email_masked, reason, source, language, smtp_message_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event_id,
                        created_at,
                        timestamp,
                        event,
                        str(record.get("submitted_email", "")).strip(),
                        account_found_value,
                        str(record.get("delivery", "")).strip(),
                        email_masked,
                        reason,
                        source,
                        language,
                        str(record.get("smtp_message_id", "")).strip(),
                    ),
                )
    except Exception as exc:
        app.logger.warning(
            "Owner magic email events write failed for %s: %s",
            str(_owner_db_path().resolve()),
            type(exc).__name__,
        )
        return False
    return True


def _append_owner_magic_email_event(event, email, reason, source, language, smtp_message_id=""):
    timestamp = _utc_now_iso()
    event_record = {
        "id": uuid4().hex,
        "created_at": timestamp,
        "timestamp": timestamp,
        "event": str(event or "").strip(),
        "submitted_email": str(email or "").strip(),
        "account_found": None,
        "delivery": "",
        "email_masked": _mask_email(email),
        "reason": str(reason or "").strip(),
        "source": str(source or "").strip(),
        "language": str(language or "").strip().lower() or "bg",
        "smtp_message_id": str(smtp_message_id or "").strip(),
    }
    try:
        with _owner_db_connection() as conn:
            _ensure_owner_db_schema(conn)
            _migrate_owner_jsonl_backups(conn)
            conn.execute(
                """
                INSERT INTO owner_magic_email_events (
                    id, created_at, timestamp, event, submitted_email, account_found, delivery, email_masked, reason, source, language, smtp_message_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_record["id"],
                    event_record["created_at"],
                    event_record["timestamp"],
                    event_record["event"],
                    event_record["submitted_email"],
                    None,
                    event_record["delivery"],
                    event_record["email_masked"],
                    event_record["reason"],
                    event_record["source"],
                    event_record["language"],
                    event_record["smtp_message_id"],
                ),
            )
    except Exception as exc:
        app.logger.warning("Owner magic email event append failed for %s: %s", _mask_email(email), type(exc).__name__)
        return event_record
    return event_record


def _append_owner_magic_login_audit(submitted_email, account_found, delivery, reason, source, language):
    timestamp = _utc_now_iso()
    event_record = {
        "id": uuid4().hex,
        "created_at": timestamp,
        "timestamp": timestamp,
        "event": "owner_login_attempt",
        "submitted_email": str(submitted_email or "").strip(),
        "account_found": bool(account_found),
        "delivery": str(delivery or "").strip(),
        "email_masked": _mask_email(submitted_email),
        "reason": str(reason or "").strip(),
        "source": str(source or "").strip(),
        "language": str(language or "").strip().lower() or "bg",
    }
    try:
        with _owner_db_connection() as conn:
            _ensure_owner_db_schema(conn)
            _migrate_owner_jsonl_backups(conn)
            conn.execute(
                """
                INSERT INTO owner_magic_email_events (
                    id, created_at, timestamp, event, submitted_email, account_found, delivery, email_masked, reason, source, language, smtp_message_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_record["id"],
                    event_record["created_at"],
                    event_record["timestamp"],
                    event_record["event"],
                    event_record["submitted_email"],
                    1 if event_record["account_found"] else 0,
                    event_record["delivery"],
                    event_record["email_masked"],
                    event_record["reason"],
                    event_record["source"],
                    event_record["language"],
                    "",
                ),
            )
    except Exception as exc:
        app.logger.warning("Owner magic login audit append failed for %s: %s", _mask_email(submitted_email), type(exc).__name__)
    return event_record


def _mask_email(email):
    raw_email = str(email or "").strip()
    if not raw_email or "@" not in raw_email:
        return "unknown"

    local_part, domain_part = raw_email.split("@", 1)
    if not local_part or not domain_part:
        return "unknown"

    visible_prefix = local_part[0]
    masked_suffix = "*" * max(1, min(len(local_part) - 1, 7))
    return f"{visible_prefix}{masked_suffix}@{domain_part}"


def _normalize_service_request_status(status):
    normalized = str(status or "").strip().lower()
    normalized = SERVICE_REQUEST_STATUS_ALIASES.get(normalized, normalized)
    return normalized if normalized in SERVICE_REQUEST_STATUS_VALUES else "new"


def _normalize_service_request_timeline(timeline):
    if not isinstance(timeline, list):
        return []

    normalized_timeline = []
    for entry in timeline:
        if not isinstance(entry, dict):
            continue

        normalized_entry = dict(entry)
        normalized_entry["type"] = str(normalized_entry.get("type", "")).strip() or "SERVICE_REQUEST_CREATED"
        normalized_entry["created_at"] = str(normalized_entry.get("created_at", "")).strip()
        normalized_entry["title"] = str(normalized_entry.get("title", "")).strip()
        normalized_entry["detail"] = str(normalized_entry.get("detail", "")).strip()
        if "status" in normalized_entry:
            normalized_entry["status"] = _normalize_service_request_status(normalized_entry.get("status"))
        else:
            normalized_entry["status"] = ""
        normalized_timeline.append(normalized_entry)

    return normalized_timeline


def _service_request_status_label(status):
    return _normalize_service_request_status(status).upper()


def _service_request_category_match(service_category):
    category = _normalize_owner_service_category(service_category) or str(service_category or "").strip()
    if category in NETWORK_SERVICE_CATEGORIES:
        return category
    return OWNER_SERVICE_CATEGORY_MATCHES.get(category, "")


def _normalize_service_request(record):
    if not isinstance(record, dict):
        return None

    normalized = dict(record)
    normalized["id"] = str(normalized.get("id", "")).strip() or _service_request_fallback_id(normalized)
    normalized["created_at"] = str(normalized.get("created_at", "")).strip()
    normalized["status"] = _normalize_service_request_status(normalized.get("status", "new"))
    normalized["request_source"] = str(normalized.get("request_source", "public")).strip().lower() or "public"

    for field in (
        "name",
        "email",
        "phone",
        "property_city",
        "property_type",
        "property",
        "service_category",
        "preferred_date",
        "description",
        "assigned_provider_id",
        "assigned_provider_name",
        "assigned_provider_company",
        "assigned_professional_id",
        "assigned_professional_name",
        "assigned_professional_company",
        "internal_notes",
        "owner_id",
        "owner_email",
        "owner_name",
        "owner_phone",
    ):
        normalized[field] = str(normalized.get(field, "")).strip()

    normalized["last_update_at"] = str(normalized.get("last_update_at", normalized["created_at"])).strip()
    normalized["number_of_units"] = str(normalized.get("number_of_units", "")).strip()
    normalized["timeline"] = _normalize_service_request_timeline(normalized.get("timeline", []))
    return normalized


def _load_service_requests():
    path = SERVICE_REQUESTS_JSONL_PATH
    requests_list = []

    if not path.exists():
        app.logger.info("Loaded service requests: %s", len(requests_list))
        return requests_list

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            normalized = _normalize_service_request(record)
            if normalized:
                requests_list.append(normalized)

    requests_list.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    app.logger.info("Loaded service requests: %s", len(requests_list))
    return requests_list


def _save_service_requests(requests_list):
    data_dir = SERVICE_REQUESTS_JSONL_PATH.parent
    data_dir.mkdir(exist_ok=True)
    path = SERVICE_REQUESTS_JSONL_PATH
    with path.open("w", encoding="utf-8") as f:
        for record in requests_list:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _find_service_request(request_id):
    for record in _load_service_requests():
        if str(record.get("id", "")) == str(request_id):
            return record
    return None


def _service_request_status_counts(requests_list):
    counts = {status: 0 for status in SERVICE_REQUEST_STATUS_VALUES}
    for record in requests_list:
        status = _normalize_service_request_status(record.get("status", "new"))
        if status in counts:
            counts[status] += 1
    return counts


def _append_service_request_timeline_event(record, event_type, title, detail="", status=None):
    timeline = list(record.get("timeline") or [])
    timeline.append({
        "type": event_type,
        "created_at": _utc_now_iso(),
        "title": title,
        "detail": detail,
        "status": _normalize_service_request_status(status or record.get("status", "new")),
    })
    record["timeline"] = timeline


def _service_request_timeline_events(record):
    timeline = _normalize_service_request_timeline(record.get("timeline"))
    if timeline:
        return timeline

    created_at = str(record.get("created_at", "")).strip()
    if not created_at:
        return []

    return [{
        "type": "SERVICE_REQUEST_CREATED",
        "created_at": created_at,
        "title": f"Service request created: {record.get('name') or record.get('property') or record.get('property_city') or 'Unnamed request'}",
        "detail": f"{record.get('service_category', '')} · {record.get('property_city') or record.get('property', '')}",
        "status": _normalize_service_request_status(record.get("status", "new")),
    }]


def _service_request_matching_providers(service_category):
    category = _service_request_category_match(service_category)
    if category not in NETWORK_SERVICE_CATEGORIES:
        return []

    providers = [
        provider
        for provider in _load_network_providers()
        if provider.get("category") == category and _normalize_bool_field(provider.get("available_for_requests", True))
    ]
    providers.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    providers.sort(key=lambda item: bool(item.get("featured")), reverse=True)
    return providers


def _build_service_request_telegram_text(record, admin_detail_url):
    lines = [
        "New Service Request",
        f"name: {record.get('name', '')}",
        f"email: {record.get('email', '')}",
        f"phone: {record.get('phone', '')}",
        f"property_city: {record.get('property_city', '')}",
        f"property_type: {record.get('property_type', '')}",
        f"service_category: {record.get('service_category', '')}",
        f"preferred_date: {record.get('preferred_date', '')}",
        f"status: {_normalize_service_request_status(record.get('status', 'new')).upper()}",
        f"admin_detail_url: {admin_detail_url}",
    ]
    return "\n".join(lines)


def _send_service_request_via_telegram(record, admin_detail_url, telegram_bot_token, telegram_chat_id):
    telegram_text = _build_service_request_telegram_text(record, admin_detail_url)
    telegram_url = f"https://api.telegram.org/bot{telegram_bot_token}/sendMessage"
    payload = {
        "chat_id": telegram_chat_id,
        "text": telegram_text,
        "disable_web_page_preview": "true",
    }

    request = urllib.request.Request(
        telegram_url,
        data=urllib.parse.urlencode(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            response_status = getattr(response, "status", getattr(response, "code", None))
            if response_status not in (200, 201, 202):
                app.logger.warning("Service request notification send failed via Telegram: unexpected status %s.", response_status)
                return False, "telegram_bad_status"
    except urllib.error.HTTPError as exc:
        response_body = ""
        try:
            response_body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            response_body = "<unreadable>"
        app.logger.warning(
            "Service request notification send failed via Telegram: HTTP %s %s. Body: %s",
            exc.code,
            exc.reason,
            response_body,
        )
        return False, "telegram_send_failed"
    except Exception as exc:
        app.logger.warning("Service request notification send failed via Telegram: %s", type(exc).__name__)
        return False, "telegram_send_failed"

    return True, None


def _send_service_request_notification(record, admin_detail_url):
    telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    if not telegram_bot_token or not telegram_chat_id:
        return False, "telegram_not_configured"

    return _send_service_request_via_telegram(
        record,
        admin_detail_url,
        telegram_bot_token,
        telegram_chat_id,
    )


def _queue_service_request_notification(record, admin_detail_url):
    telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not telegram_bot_token or not telegram_chat_id:
        return

    Thread(
        target=_send_service_request_notification,
        args=(record, admin_detail_url),
        daemon=True,
    ).start()


def _service_request_smtp_settings():
    smtp_host = os.getenv("SMTP_HOST", "").strip()
    smtp_port_raw = os.getenv("SMTP_PORT", "").strip()
    smtp_from = os.getenv("SMTP_FROM", "").strip()
    return smtp_host, smtp_port_raw, smtp_from


def _service_request_email_body(record, recipient_label, admin_detail_url, event_label):
    assigned_professional = record.get("assigned_provider_company", "") or record.get("assigned_provider_name", "")
    lines = [
        f"Recipient: {recipient_label}",
        f"Event: {event_label}",
        f"Request ID: {record.get('id', '')}",
        f"Category: {record.get('service_category', '')}",
        f"Status: {_service_request_status_label(record.get('status', 'new'))}",
        f"Property: {record.get('property') or record.get('property_city', '')}",
        f"Preferred date: {record.get('preferred_date', '')}",
        f"Contact phone: {record.get('phone') or record.get('owner_phone', '')}",
        f"Assigned professional: {assigned_professional or 'n/a'}",
        f"Admin detail URL: {admin_detail_url}",
    ]
    return "\n".join(lines)


def _send_service_request_email(record, recipient_email, recipient_label, admin_detail_url, event_label, subject):
    smtp_host, smtp_port_raw, smtp_from = _service_request_smtp_settings()
    if not smtp_host or not smtp_port_raw or not smtp_from or not recipient_email:
        app.logger.warning(
            "Service request email skipped: SMTP configuration missing for %s.",
            recipient_label,
        )
        return False, "smtp_not_configured"

    try:
        smtp_port = int(smtp_port_raw)
    except ValueError:
        app.logger.warning("Service request email skipped: SMTP_PORT is invalid.")
        return False, "smtp_invalid_port"

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = smtp_from
    message["To"] = recipient_email
    message.set_content(_service_request_email_body(record, recipient_label, admin_detail_url, event_label))

    try:
        smtp_factory = smtplib.SMTP_SSL if smtp_port == 465 else smtplib.SMTP
        with smtp_factory(smtp_host, smtp_port, timeout=10) as smtp:
            smtp.ehlo()
            if smtp_port != 465:
                try:
                    smtp.starttls()
                    smtp.ehlo()
                except smtplib.SMTPException:
                    app.logger.warning("Service request email: SMTP STARTTLS was unavailable.")

            smtp_username = os.getenv("SMTP_USERNAME", "").strip()
            smtp_password = os.getenv("SMTP_PASSWORD", "").strip()
            if smtp_username or smtp_password:
                smtp.login(smtp_username, smtp_password)

            smtp.send_message(message)
    except Exception as exc:
        app.logger.warning("Service request email send failed for %s: %s", recipient_label, type(exc).__name__)
        return False, "smtp_send_failed"

    return True, None


def _queue_service_request_email(record, recipient_email, recipient_label, admin_detail_url, event_label, subject):
    Thread(
        target=_send_service_request_email,
        args=(record, recipient_email, recipient_label, admin_detail_url, event_label, subject),
        daemon=True,
    ).start()


def _send_owner_magic_link(email, login_url):
    return _send_owner_magic_link_with_language(email, login_url, "bg")


def _owner_magic_link_email_locale(language):
    normalized = str(language or "").strip().lower()
    return normalized if normalized in {"bg", "en", "fr", "ru"} else "bg"


def _owner_magic_link_email_message(email, login_url, language):
    lang = _owner_magic_link_email_locale(language)
    localized_copy = {
        "bg": {
            "subject": "BlackSea Connect — Вход в портала за собственици",
            "greeting": "Здравейте,",
            "intro": "Използвайте бутона по-долу за сигурен достъп до вашия портал.",
            "button_label": "Влезте в портала",
            "fallback_label": "Ако бутонът не работи, копирайте този линк:",
            "closing": "Този линк е валиден 30 минути.",
        },
        "en": {
            "subject": "BlackSea Connect — Owner Portal secure sign-in link",
            "greeting": "Hello,",
            "intro": "Use the button below for secure access to your Owner Portal.",
            "button_label": "Access Owner Portal",
            "fallback_label": "If the button does not work, copy this link:",
            "closing": "This link expires in 30 minutes.",
        },
        "fr": {
            "subject": "BlackSea Connect — Lien de connexion sécurisé au portail propriétaire",
            "greeting": "Bonjour,",
            "intro": "Utilisez le bouton ci-dessous pour accéder en toute sécurité à votre portail propriétaire.",
            "button_label": "Accéder au portail",
            "fallback_label": "Si le bouton ne fonctionne pas, copiez ce lien :",
            "closing": "Ce lien expire dans 30 minutes.",
        },
        "ru": {
            "subject": "BlackSea Connect — Безопасная ссылка для входа в портал владельца",
            "greeting": "Здравствуйте,",
            "intro": "Используйте кнопку ниже для безопасного доступа к вашему порталу владельца.",
            "button_label": "Войти в портал",
            "fallback_label": "Если кнопка не работает, скопируйте эту ссылку:",
            "closing": "Ссылка действует 30 минут.",
        },
    }
    copy = localized_copy.get(lang, localized_copy["bg"])
    footer = "You are receiving this email because you requested access to your BlackSea Connect owner portal."
    subject = copy["subject"]
    greeting = copy["greeting"]
    intro = copy["intro"]
    button_label = copy["button_label"]
    fallback_label = copy["fallback_label"]
    closing = copy["closing"]

    text_body = "\n".join([
        greeting,
        "",
        intro,
        "",
        login_url,
        "",
        closing,
        "",
        footer,
        "",
        "BlackSea Connect",
    ])
    html_body = "\n".join([
        "<!doctype html>",
        f'<html lang="{lang}">',
        "<body style=\"margin:0;padding:0;background:#f6f0df;font-family:Arial,Helvetica,sans-serif;color:#1e1b16;\">",
        '<div style="max-width:640px;margin:0 auto;padding:32px 20px;">',
        '<div style="background:#fffaf0;border:1px solid #ead6a6;border-radius:20px;padding:32px;box-shadow:0 16px 40px rgba(0,0,0,0.08);">',
        '<div style="font-size:14px;letter-spacing:.16em;text-transform:uppercase;color:#9b7b2f;font-weight:700;">BlackSea Connect</div>',
        f'<h1 style="margin:16px 0 12px;font-size:28px;line-height:1.2;color:#1f2937;">{greeting}</h1>',
        f'<p style="margin:0 0 24px;font-size:16px;line-height:1.7;">{intro}</p>',
        f'<a href="{login_url}" style="display:inline-block;background:#9b7b2f;color:#fff;text-decoration:none;padding:14px 22px;border-radius:999px;font-weight:700;">{button_label}</a>',
        f'<p style="margin:20px 0 8px;font-size:14px;line-height:1.7;color:#4b5563;">{fallback_label}</p>',
        f'<p style="margin:0;font-size:14px;line-height:1.7;word-break:break-all;"><a href="{login_url}" style="color:#9b7b2f;">{login_url}</a></p>',
        f'<p style="margin:24px 0 0;font-size:14px;line-height:1.7;color:#4b5563;">{closing}</p>',
        f'<p style="margin:16px 0 0;font-size:13px;line-height:1.6;color:#6b7280;">{footer}</p>',
        "</div>",
        "</div>",
        "</body>",
        "</html>",
    ])
    return subject, text_body, html_body


def _send_owner_magic_link_with_language(email, login_url, language):
    smtp_host, smtp_port_raw, smtp_from = _service_request_smtp_settings()
    if not smtp_host or not smtp_port_raw or not smtp_from or not email:
        app.logger.warning("Owner magic link email skipped for %s: SMTP configuration missing.", _mask_email(email))
        return {"ok": False, "reason": "smtp_not_configured"}

    try:
        smtp_port = int(smtp_port_raw)
    except ValueError:
        app.logger.warning("Owner magic link email skipped for %s: SMTP_PORT is invalid.", _mask_email(email))
        return {"ok": False, "reason": "smtp_invalid_port"}

    subject, text_body, html_body = _owner_magic_link_email_message(email, login_url, language)
    smtp_display_name = "BlackSea Connect Owner Portal"
    _, smtp_address = parseaddr(smtp_from)
    sender_email = smtp_address or smtp_from
    message_id = f"<{uuid4().hex}@blackseaconnect.com>"
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = formataddr((smtp_display_name, sender_email))
    message["To"] = email
    message["Reply-To"] = "concierge@blackseaconnect.com"
    message["List-Unsubscribe"] = "<mailto:concierge@blackseaconnect.com?subject=unsubscribe>"
    message["Message-ID"] = message_id
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")

    try:
        smtp_factory = smtplib.SMTP_SSL if smtp_port == 465 else smtplib.SMTP
        with smtp_factory(smtp_host, smtp_port, timeout=10) as smtp:
            smtp.ehlo()
            if smtp_port != 465:
                try:
                    smtp.starttls()
                    smtp.ehlo()
                except smtplib.SMTPException:
                    app.logger.warning("Owner magic link email: SMTP STARTTLS was unavailable.")

            smtp_username = os.getenv("SMTP_USERNAME", "").strip()
            smtp_password = os.getenv("SMTP_PASSWORD", "").strip()
            if smtp_username or smtp_password:
                smtp.login(smtp_username, smtp_password)

            smtp.send_message(message)
    except smtplib.SMTPAuthenticationError as exc:
        app.logger.warning("Owner magic link email login failed for %s: %s", _mask_email(email), type(exc).__name__)
        return {"ok": False, "reason": "smtp_login_failed"}
    except smtplib.SMTPRecipientsRefused as exc:
        app.logger.warning("Owner magic link email send failed for %s: %s", _mask_email(email), type(exc).__name__)
        return {"ok": False, "reason": "smtp_send_failed"}
    except smtplib.SMTPException as exc:
        app.logger.warning("Owner magic link email send failed for %s: %s", _mask_email(email), type(exc).__name__)
        return {"ok": False, "reason": "smtp_send_failed"}
    except Exception as exc:
        app.logger.warning("Owner magic link email failed for %s: %s", _mask_email(email), type(exc).__name__)
        return {"ok": False, "reason": "unexpected_error"}

    app.logger.info("Owner magic link email sent to %s", _mask_email(email))
    return {"ok": True, "reason": "sent", "message_id": message_id}


def _send_owner_magic_link_and_log(email, login_url, language, source):
    result = _send_owner_magic_link_with_language(email, login_url, language)
    event_name = "sent" if result.get("ok") else "failed"
    _append_owner_magic_email_event(event_name, email, result.get("reason", ""), source, language, result.get("message_id", ""))
    if result.get("ok") and str(source or "").strip().lower() == "login":
        owner_account = _find_owner_account_by_email(email)
        if owner_account:
            _append_owner_activity_event(
                owner_account["id"],
                "magic_link_sent",
                "Magic link sent",
                f"Source: {source}; language: {_normalize_owner_language(language) or OWNER_LANGUAGE_DEFAULT}",
            )
    return result


def _queue_owner_magic_link_email(email, login_url, language="bg"):
    Thread(
        target=_send_owner_magic_link_with_language,
        args=(email, login_url, language),
        daemon=True,
    ).start()


def _owner_property_new_copy(language):
    lang = _normalize_site_language(language) or "bg"
    copy = {
        "bg": {
            "page_title": "BlackSea Connect | Добавете имот",
            "meta": "Задайте първия имот и започнете оперативната подготовка.",
            "hero_eyebrow": "Портал за собственици",
            "hero_title": "Добре дошли в BlackSea Connect",
            "hero_intro": "Добавете първия си имот, за да започнем оперативната подготовка.",
            "next_eyebrow": "Какво следва?",
            "next_title": "Ще подготвим първия оперативен профил.",
            "next_copy": "Данните за имота ни помагат да планираме готовност, почистване и concierge setup.",
            "form_eyebrow": "Добавете имот",
            "form_title": "Въведете детайлите за първия си имот.",
            "form_copy": "Спокойно, ясно и подредено. Ще запишем основните данни и ще продължим оттам.",
            "name_label": "Име на имота",
            "type_label": "Тип имот",
            "location_label": "Локация",
            "bedrooms_label": "Спални",
            "bathrooms_label": "Бани",
            "guest_capacity_label": "Капацитет гости",
            "operating_mode_label": "Режим на работа",
            "year_round_label": "Целогодишен",
            "seasonal_label": "Сезонен",
            "notes_label": "Бележки",
            "notes_placeholder": "Има ли нещо важно, което екипът ни трябва да знае?",
            "submit_label": "Запази имота",
            "back_label": "Назад към таблото",
            "aside_title": "Подготовката започва от тук",
            "aside_copy": "Ще използваме данните, за да подготвим оперативен профил, да подредим приоритетите и да ускорим първите стъпки.",
            "aside_step_1": "Добавен имот",
            "aside_step_2": "Проверка на информацията",
            "aside_step_3": "Оперативна конфигурация",
            "aside_step_4": "Concierge готовност",
            "aside_detail_1": "Първият оперативен запис вече е подготвен.",
            "aside_detail_2": "Потвърждаваме данните и нормализираме профила.",
            "aside_detail_3": "Подготвяме почистване, готовност и concierge потока.",
            "aside_detail_4": "Имотът е готов за екипа.",
            "nav_dashboard_label": "Табло",
            "nav_properties_label": "Имот",
            "nav_logout_label": "Изход",
            "footer_description": "Спокойни оперативни решения за крайбрежни имоти.",
            "footer_meta": "Порталът за собственици събира видимостта, заявките и подготовката в един спокоен поток.",
            "aria_owner_portal": "Портал за собственици",
            "aria_summary": "Обобщение на първия имот",
            "aria_steps": "Стъпки по onboarding",
            "aria_guidance": "Напътствия за onboarding",
        },
        "en": {
            "page_title": "BlackSea Connect | Add property",
            "meta": "Set up your first property and begin operational onboarding.",
            "hero_eyebrow": "Owner portal",
            "hero_title": "Welcome to BlackSea Connect",
            "hero_intro": "Add your first property so we can start operational preparation.",
            "next_eyebrow": "What happens next?",
            "next_title": "We will prepare the first operational profile.",
            "next_copy": "Property details help us plan readiness, housekeeping, and concierge setup.",
            "form_eyebrow": "Add property",
            "form_title": "Enter the details for your first property.",
            "form_copy": "Calm, clear, and organized. We will capture the essentials and continue from there.",
            "name_label": "Property name",
            "type_label": "Property type",
            "location_label": "Location",
            "bedrooms_label": "Bedrooms",
            "bathrooms_label": "Bathrooms",
            "guest_capacity_label": "Guest capacity",
            "operating_mode_label": "Operating mode",
            "year_round_label": "Year-round",
            "seasonal_label": "Seasonal",
            "notes_label": "Notes",
            "notes_placeholder": "Anything important our team should know?",
            "submit_label": "Save property",
            "back_label": "Back to dashboard",
            "aside_title": "Preparation starts here",
            "aside_copy": "We will use these details to prepare the operational profile, organize priorities, and speed up the first steps.",
            "aside_step_1": "Property added",
            "aside_step_2": "Information reviewed",
            "aside_step_3": "Operations configured",
            "aside_step_4": "Concierge ready",
            "aside_detail_1": "The first operational record is now prepared.",
            "aside_detail_2": "We confirm the details and normalize the profile.",
            "aside_detail_3": "We prepare cleaning, readiness, and concierge flow.",
            "aside_detail_4": "The property is ready for the team.",
            "nav_dashboard_label": "Dashboard",
            "nav_properties_label": "Property",
            "nav_logout_label": "Logout",
            "footer_description": "Quiet operational software for coastal properties.",
            "footer_meta": "The owner portal keeps visibility, requests, and preparation in one calm flow.",
            "aria_owner_portal": "Owner portal",
            "aria_summary": "First property summary",
            "aria_steps": "Onboarding steps",
            "aria_guidance": "Onboarding guidance",
        },
        "fr": {
            "page_title": "BlackSea Connect | Ajouter un bien",
            "meta": "Renseignez votre premier bien pour lancer la préparation opérationnelle.",
            "hero_eyebrow": "Portail propriétaire",
            "hero_title": "Bienvenue chez BlackSea Connect",
            "hero_intro": "Ajoutez votre premier bien pour lancer la préparation opérationnelle.",
            "next_eyebrow": "Que se passe-t-il ensuite ?",
            "next_title": "Nous préparerons votre premier profil opérationnel.",
            "next_copy": "Les détails du bien nous aident à planifier la préparation, le ménage et la configuration concierge.",
            "form_eyebrow": "Ajouter un bien",
            "form_title": "Saisissez les détails de votre premier bien.",
            "form_copy": "Calme, clair et structuré. Nous enregistrons l'essentiel puis nous avançons.",
            "name_label": "Nom du bien",
            "type_label": "Type de bien",
            "location_label": "Localisation",
            "bedrooms_label": "Chambres",
            "bathrooms_label": "Salles de bain",
            "guest_capacity_label": "Capacité voyageurs",
            "operating_mode_label": "Mode d’exploitation",
            "year_round_label": "Toute l’année",
            "seasonal_label": "Saisonnier",
            "notes_label": "Notes",
            "notes_placeholder": "Y a-t-il quelque chose d'important à signaler ?",
            "submit_label": "Enregistrer le bien",
            "back_label": "Retour au tableau de bord",
            "aside_title": "La préparation commence ici",
            "aside_copy": "Nous utiliserons ces détails pour préparer le profil opérationnel, organiser les priorités et accélérer les premières étapes.",
            "aside_step_1": "Bien ajouté",
            "aside_step_2": "Informations vérifiées",
            "aside_step_3": "Opérations configurées",
            "aside_step_4": "Concierge prêt",
            "aside_detail_1": "Le premier enregistrement opérationnel est prêt.",
            "aside_detail_2": "Nous confirmons les détails et normalisons le profil.",
            "aside_detail_3": "Nous préparons le ménage, la préparation et le flux concierge.",
            "aside_detail_4": "Le bien est prêt pour l'équipe.",
            "nav_dashboard_label": "Tableau de bord",
            "nav_properties_label": "Bien",
            "nav_logout_label": "Déconnexion",
            "footer_description": "Logiciel opérationnel discret pour les biens côtiers.",
            "footer_meta": "Le portail propriétaire regroupe la visibilité, les demandes et la préparation dans un flux calme.",
            "aria_owner_portal": "Portail propriétaire",
            "aria_summary": "Résumé du premier bien",
            "aria_steps": "Étapes d'intégration",
            "aria_guidance": "Conseils d'intégration",
        },
        "ru": {
            "page_title": "BlackSea Connect | Добавить объект",
            "meta": "Укажите первый объект и начните операционную подготовку.",
            "hero_eyebrow": "Портал владельца",
            "hero_title": "Добро пожаловать в BlackSea Connect",
            "hero_intro": "Добавьте первый объект, и мы начнем операционную подготовку.",
            "next_eyebrow": "Что будет дальше?",
            "next_title": "Мы подготовим первый операционный профиль.",
            "next_copy": "Данные об объекте помогают нам спланировать готовность, уборку и настройку concierge.",
            "form_eyebrow": "Добавить объект",
            "form_title": "Введите данные вашего первого объекта.",
            "form_copy": "Спокойно, понятно и без лишнего шума. Мы зафиксируем главное и продолжим дальше.",
            "name_label": "Название объекта",
            "type_label": "Тип объекта",
            "location_label": "Локация",
            "bedrooms_label": "Спальни",
            "bathrooms_label": "Ванные",
            "guest_capacity_label": "Вместимость гостей",
            "operating_mode_label": "Режим работы",
            "year_round_label": "Круглый год",
            "seasonal_label": "Сезонный",
            "notes_label": "Заметки",
            "notes_placeholder": "Есть ли что-то важное для нашей команды?",
            "submit_label": "Сохранить объект",
            "back_label": "Назад к панели",
            "aside_title": "Подготовка начинается здесь",
            "aside_copy": "Мы используем эти данные, чтобы подготовить операционный профиль, расставить приоритеты и ускорить первые шаги.",
            "aside_step_1": "Объект добавлен",
            "aside_step_2": "Информация проверена",
            "aside_step_3": "Операции настроены",
            "aside_step_4": "Concierge готов",
            "aside_detail_1": "Первый операционный запис уже подготовлен.",
            "aside_detail_2": "Мы подтверждаем данные и нормализуем профиль.",
            "aside_detail_3": "Мы готовим уборку, готовность и поток concierge.",
            "aside_detail_4": "Объект готов для команды.",
            "nav_dashboard_label": "Панель",
            "nav_properties_label": "Объект",
            "nav_logout_label": "Выход",
            "footer_description": "Спокойное операционное ПО для прибрежной недвижимости.",
            "footer_meta": "Портал владельца объединяет видимость, запросы и подготовку в одном спокойном потоке.",
            "aria_owner_portal": "Портал владельца",
            "aria_summary": "Сводка по первому объекту",
            "aria_steps": "Шаги onboarding",
            "aria_guidance": "Подсказки onboarding",
        },
    }
    return copy.get(lang, copy["bg"])


def _normalize_site_language(language):
    normalized = str(language or "").strip().lower()
    return normalized if normalized in SUPPORTED_LANGUAGES else ""


def _resolve_current_language():
    for candidate in (
        request.values.get("lang"),
        request.args.get("lang"),
        session.get(SITE_LANGUAGE_SESSION_KEY),
    ):
        normalized = _normalize_site_language(candidate)
        if normalized:
            session[SITE_LANGUAGE_SESSION_KEY] = normalized
            return normalized

    session[SITE_LANGUAGE_SESSION_KEY] = "bg"
    return "bg"


def _build_home_counters():
    providers = _load_network_providers()
    service_requests = _load_service_requests()
    cities = {
        str(provider.get("city", "")).strip().lower()
        for provider in providers
        if str(provider.get("city", "")).strip()
    }
    return {
        "providers": len(providers),
        "cities": len(cities),
        "service_requests": len(service_requests),
    }


@app.context_processor
def inject_public_site_settings():
    current_lang = _resolve_current_language()

    def language_switch_url(lang):
        normalized_lang = _normalize_site_language(lang) or "bg"
        preserved_args = [(key, value) for key, value in request.args.items(multi=True) if key != "lang"]
        preserved_args.append(("lang", normalized_lang))
        query_string = urllib.parse.urlencode(preserved_args, doseq=True)
        return f"{request.path}?{query_string}" if query_string else request.path

    def current_page_language():
        return current_lang

    def localized_url(path_or_url):
        target = str(path_or_url or "").strip()
        if not target:
            return target

        lowered = target.lower()
        if lowered.startswith(("http://", "https://", "mailto:", "tel:", "javascript:")):
            return target
        if target.startswith("#") or target.startswith("//") or target.startswith("/static/"):
            return target

        parsed = urllib.parse.urlsplit(target)
        if parsed.scheme or parsed.netloc:
            return target

        current_args = {key: value for key, value in request.args.items() if key != "lang"}
        target_args = {
            key: value
            for key, value in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
            if key != "lang"
        }
        current_args.update(target_args)
        current_args["lang"] = current_lang
        query_string = urllib.parse.urlencode(current_args, doseq=True)
        rebuilt_path = parsed.path or target
        if query_string:
            rebuilt_path = f"{rebuilt_path}?{query_string}"
        if parsed.fragment:
            rebuilt_path = f"{rebuilt_path}#{parsed.fragment}"
        return rebuilt_path

    return {
        "site_url": SITE_URL,
        "language_switch_url": language_switch_url,
        "localized_url": localized_url,
        "page_lang": current_page_language(),
    }


@app.after_request
def force_utf8_charset(response):
    mimetype = response.mimetype or ""
    if mimetype.startswith("text/") or mimetype == "application/json" or mimetype == "application/javascript":
        if "charset=" not in (response.headers.get("Content-Type", "") or "").lower():
            response.headers["Content-Type"] = f"{mimetype}; charset=utf-8"
    return response


@app.route("/robots.txt")
def robots_txt():
    lines = [
        "User-agent: *",
        "Allow: /",
        f"Sitemap: {SITE_URL}/sitemap.xml",
        "",
    ]
    return Response("\n".join(lines), mimetype="text/plain")


@app.route("/sitemap.xml")
def sitemap_xml():
    urls = "\n".join(
        f"  <url><loc>{SITE_URL}{path}</loc></url>"
        for path in PUBLIC_SITEMAP_PATHS
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{urls}\n"
        "</urlset>\n"
    )
    return Response(xml, mimetype="application/xml")


def _render_seo_landing_page(path):
    lang = str(request.args.get("lang", "en")).strip().lower() or "en"
    if lang not in SEO_SUPPORTED_LANGS:
        lang = "en"
    page = resolve_seo_landing_page(path, lang)
    return render_template("seo_longform_page.html", page=page)


@app.route("/")
def home():
    return render_template("index.html", home_counters=_build_home_counters())


@app.route("/guest/a-302")
def guest_portal_a302():
    return render_template("guest_portal.html")


@app.route("/services")
def services():
    return render_template("services.html")


@app.route("/demo/operations")
def demo_operations():
    return render_template("demo_operations.html")


@app.route("/pilot-access")
def pilot_access():
    return render_template("pilot_access.html")


@app.route("/concierge-bulgaria")
def concierge_bulgaria():
    return _render_seo_landing_page("/concierge-bulgaria")


@app.route("/property-management-bulgaria")
def property_management_bulgaria():
    return _render_seo_landing_page("/property-management-bulgaria")


@app.route("/guest-experience-services")
def guest_experience_services():
    return _render_seo_landing_page("/guest-experience-services")


@app.route("/vacation-rental-operations")
def vacation_rental_operations():
    return _render_seo_landing_page("/vacation-rental-operations")


@app.route("/sveti-vlas-concierge-services")
def sveti_vlas_concierge_services():
    return _render_seo_landing_page("/sveti-vlas-concierge-services")


@app.route("/professionals")
def professionals():
    return render_template(
        "professionals.html",
        service_categories=_professional_service_category_items(),
        professionals=_load_public_professional_applications(),
    )


def _current_owner_account():
    owner_account = getattr(g, "owner_account", None)
    if owner_account:
        return owner_account

    owner_id = str(session.get(OWNER_SESSION_ID_KEY, "")).strip()
    owner_email = str(session.get(OWNER_SESSION_EMAIL_KEY, "")).strip()
    if owner_id:
        owner_account = _find_owner_account(owner_id)
    if not owner_account and owner_email:
        owner_account = _find_owner_account_by_email(owner_email)

    if owner_account:
        g.owner_account = owner_account
    return owner_account


def _parse_iso_datetime(value):
    raw_value = str(value or "").strip()
    if not raw_value:
        return None
    try:
        return datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _owner_portal_response_minutes(record):
    created_at = _parse_iso_datetime(record.get("created_at"))
    if not created_at:
        return None

    for event in _service_request_timeline_events(record):
        if event.get("type") not in {
            "SERVICE_REQUEST_PROFESSIONAL_ASSIGNED",
            "SERVICE_REQUEST_STATUS_UPDATED",
            "SERVICE_REQUEST_COMPLETED",
        }:
            continue

        event_at = _parse_iso_datetime(event.get("created_at"))
        if event_at:
            delta_minutes = int((event_at - created_at).total_seconds() // 60)
            if delta_minutes >= 0:
                return max(delta_minutes, 15)

    return None


def _format_owner_portal_duration(minutes):
    if minutes is None:
        return "Under 3h"

    if minutes < 60:
        return f"{minutes}m"

    hours = minutes // 60
    remaining_minutes = minutes % 60
    return f"{hours}h {remaining_minutes:02d}m"


def _format_owner_portal_timestamp(value):
    parsed_value = _parse_iso_datetime(value)
    if not parsed_value:
        return ""
    return parsed_value.astimezone(timezone.utc).strftime("%d.%m.%Y · %H:%M UTC")


def _owner_portal_metric_value(value, fallback_label):
    try:
        numeric_value = int(value)
    except (TypeError, ValueError):
        numeric_value = 0
    return str(numeric_value) if numeric_value > 0 else fallback_label


def _owner_portal_metric_value_with_key(value, fallback_label, fallback_key):
    rendered_value = _owner_portal_metric_value(value, fallback_label)
    return rendered_value, (fallback_key if rendered_value == fallback_label else "")


def _owner_dashboard_copy(lang):
    copy = {
        "bg": {
            "page_title": "BlackSea Connect | Табло на собственик",
            "page_meta": "Премиум табло за имотите, операциите и услугите ви.",
            "nav_portal": "Табло",
            "nav_request_service": "Заявка за услуга",
            "nav_logout": "Изход",
            "nav_home": "Обратно към сайта",
            "nav_services": "Услуги",
            "nav_partners": "Партньори",
            "nav_pilot_access": "Пилотен достъп",
            "profile_profile": "Профил",
            "profile_properties": "Имотите",
            "profile_logout": "Изход",
            "hero_eyebrow": "Портал за собственици",
            "hero_title": "Премиум поглед към имота.",
            "hero_copy": "Проследявайте имотите, задачите и оперативната готовност в един спокоен изглед.",
            "hero_summary_line": "Личен преглед на вашите оперативни процеси.",
            "hero_empty_hint": "Добавете първия си имот, за да започнем оперативната подготовка.",
            "empty_activity_copy": "Все още няма заявки за услуги. Таблото ще покаже всяка заявка веднага след изпращане.",
            "hero_primary_cta": "Заяви услуга",
            "hero_secondary_cta": "Изход",
            "property_status_label": "Статус на имота",
            "location_label": "Локация",
            "property_type_label": "Тип имот",
            "property_name_label": "Име на имота",
            "city_label": "Град",
            "status_label": "Статус",
            "bedrooms_label": "Спални",
            "bathrooms_label": "Бани",
            "capacity_label": "Капацитет",
            "units_label": "Единици",
            "operating_mode_label": "Режим на работа",
            "mode_year_round": "Целогодишен",
            "mode_seasonal": "Сезонен",
            "property_type_residence": "Крайбрежна резиденция",
            "location_pending": "Локацията предстои",
            "status_active": "Активен",
            "status_seasonal": "Сезонен",
            "status_setup": "Настройка",
            "status_paused": "Пауза",
            "status_maintenance": "Поддръжка",
            "status_note_active": "Активни оперативни обновления",
            "status_note_seasonal": "Спокойно сезонно наблюдение",
            "status_note_setup": "Подготвяме първите оперативни стъпки",
            "status_note_paused": "Обектът е временно поставен на пауза",
            "status_note_maintenance": "Проследяване на текуща поддръжка",
            "empty_state_title": "Добре дошли в BlackSea Connect",
            "empty_state_copy": "Добавете първия си имот, за да започнем оперативната подготовка.",
            "empty_state_cta": "Добавете имот",
            "onboarding_eyebrow": "Onboarding",
            "onboarding_title": "Подготвяме операциите на имота ви.",
            "onboarding_stage_property_added": "Имотът е добавен",
            "onboarding_stage_information_reviewed": "Информацията е прегледана",
            "onboarding_stage_operations_configured": "Операциите са конфигурирани",
            "onboarding_stage_concierge_ready": "Concierge е готов",
            "onboarding_pending": "В очакване",
            "onboarding_complete": "Готово",
            "ready": "Готово",
            "properties_eyebrow": "Имотите",
            "properties_title": "Вашите имоти",
            "summary_eyebrow": "Преглед на имота",
            "summary_title": "Всичко необходимо в един спокоен изглед.",
            "property_health_eyebrow": "Състояние на имота",
            "property_health_title": "Какво има нужда от внимание сега.",
            "trusted_local_team_eyebrow": "Доверен местен екип",
            "trusted_local_team_title": "Кой подкрепя имота.",
            "assigned_operator_label": "Назначен оператор",
            "assigned_operator_suffix": "операторски екип",
            "concierge_contact_label": "Контакт за консиерж",
            "service_partners_label": "Партньори за услуги",
            "monthly_summary_eyebrow": "Месечно резюме",
            "monthly_summary_title": "Кратък поглед към месеца.",
            "performance_snapshot_eyebrow": "Снимка на ефективността",
            "performance_snapshot_title": "Само оперативни индикатори.",
            "activity_timeline_eyebrow": "Хронология на активността",
            "activity_timeline_title": "Скорошна активност на имота.",
            "quick_actions_eyebrow": "Бързи действия",
            "quick_actions_title": "Действайте бързо, без да губите видимост.",
            "notification_center_eyebrow": "Център за известия",
            "notification_center_title": "Известия за имота, подготвени за бъдещето.",
            "recent_updates_eyebrow": "Последни актуализации",
            "recent_updates_title": "Последна сервисна активност.",
            "footer_description": "Спокойни оперативни решения за крайбрежни имоти.",
            "footer_meta": "Порталът за собственици събира видимостта на имота, заявките и обновленията в един спокоен поток.",
            "upcoming_arrivals_label": "Предстоящи пристигания",
            "upcoming_departures_label": "Предстоящи отпътувания",
            "cleaning_completed_label": "Извършени почиствания",
            "cleaning_pending_label": "Предстоящи почиствания",
            "open_guest_requests_label": "Отворени заявки",
            "maintenance_issues_label": "Проблеми за поддръжка",
            "pending_actions_label": "Очакват действия",
            "last_completed_task_label": "Последна завършена задача",
            "arrivals_this_month_label": "Пристигания този месец",
            "guest_requests_handled_label": "Обслужени заявки",
            "tasks_completed_label": "Завършени задачи",
            "average_response_time_label": "Средно време за реакция",
            "nights_booked_this_month_label": "Нощувки този месец",
            "upcoming_stays_label": "Предстоящи престои",
            "completed_turnovers_label": "Завършени смени",
            "request_cleaning": "Заяви почистване",
            "request_inspection": "Заяви инспекция",
            "request_maintenance": "Заяви поддръжка",
            "contact_concierge": "Свържете се с консиерж",
            "fast_turnover_support": "Бърза подкрепа за смяната",
            "check_readiness": "Проверете готовността",
            "keep_property_protected": "Поддържайте имота защитен",
            "private_local_contact": "Поверителен местен контакт",
            "projected": "Прогнозно",
            "verified": "Проверено",
            "open": "Отворено",
            "needs_attention": "Искат внимание",
            "service_review": "Преглед на услугата",
            "operator_follow_up": "Проследяване от оператора",
            "most_recent_closed_item": "Най-скорошна затворена задача",
            "property_movement": "Движение на имота",
            "live_resolved": "В реално време + приключени",
            "confirmed": "Потвърдено",
            "from_request_to_first_action": "От заявка до първо действие",
            "operational": "Оперативно",
            "next_arrivals": "Следващи пристигания",
            "resolved": "Решени",
            "today": "Днес",
            "yesterday": "Вчера",
            "this_week": "Тази седмица",
            "scheduled": "Планирано",
            "recently": "Наскоро",
            "timeline_cleaning_completed": "Почистването е приключено",
            "timeline_cleaning_completed_detail": "Последната смяна е затворена за вашия имот.",
            "timeline_guest_checked_in": "Гостът е настанен",
            "timeline_guest_checked_in_detail": "Координацията по пристигането е активна и готова.",
            "timeline_maintenance_resolved": "Заявка за поддръжка е решена",
            "timeline_maintenance_resolved_detail": "Местният екип приключи ремонтния прозорец.",
            "timeline_airport_transfer_confirmed": "Потвърден е трансфер от летище",
            "timeline_airport_transfer_confirmed_detail": "Подкрепата за посрещане е планирана и проследена.",
            "timeline_property_inspection_completed": "Проверката на имота е приключена",
            "timeline_property_inspection_completed_detail": "Оценката за готовност е одобрена.",
            "timeline_cleaning_scheduled": "Почистване е планирано",
            "timeline_cleaning_scheduled_detail": "Следващата смяна се подготвя внимателно.",
            "timeline_property_update": "Актуализация на имота",
            "timeline_property_update_detail": "Текущият статус се наблюдава.",
            "request_id_label": "ID на заявката:",
            "updated_label": "Обновено:",
            "new_arrival": "Ново пристигане",
            "welcome_coordination_ready": "Координацията за посрещане е готова.",
            "cleaning_completed_notification": "Почистването е приключило",
            "housekeeping_closed_latest_turn": "Екипът по почистването затвори последната смяна.",
            "guest_issue_reported": "Съобщен е проблем от гост",
            "concierge_can_step_in_immediately": "Консиержът може да реагира веднага.",
            "maintenance_completed": "Поддръжката е завършена",
            "local_team_wrapped_task": "Местният екип приключи задачата.",
            "owner_status_new": "Нова",
            "owner_status_assigned": "Назначена",
            "owner_status_in_progress": "В процес",
            "owner_status_completed": "Приключена",
            "owner_status_cancelled": "Отменена",
        },
        "en": {
            "page_title": "BlackSea Connect | Owner Dashboard",
            "page_meta": "Premium dashboard for your properties, operations, and services.",
            "nav_portal": "Dashboard",
            "nav_request_service": "Request service",
            "nav_logout": "Logout",
            "nav_home": "Back to site",
            "nav_services": "Services",
            "nav_partners": "Partners",
            "nav_pilot_access": "Pilot access",
            "profile_profile": "Profile",
            "profile_properties": "Properties",
            "profile_logout": "Logout",
            "hero_eyebrow": "Owner portal",
            "hero_title": "Premium property overview.",
            "hero_copy": "Track properties, tasks, and operational readiness in one calm view.",
            "hero_summary_line": "A private view of your property operations.",
            "hero_empty_hint": "Add your first property to begin operational preparation.",
            "empty_activity_copy": "There are no service requests yet. The dashboard will show each request as soon as it is submitted.",
            "hero_primary_cta": "Request service",
            "hero_secondary_cta": "Logout",
            "property_status_label": "Property status",
            "location_label": "Location",
            "property_type_label": "Property type",
            "property_name_label": "Property name",
            "city_label": "City",
            "status_label": "Status",
            "bedrooms_label": "Bedrooms",
            "bathrooms_label": "Bathrooms",
            "capacity_label": "Capacity",
            "units_label": "Units",
            "operating_mode_label": "Operating mode",
            "mode_year_round": "Year-round",
            "mode_seasonal": "Seasonal",
            "property_type_residence": "Coastal residence",
            "location_pending": "Location pending",
            "status_active": "Active",
            "status_seasonal": "Seasonal",
            "status_setup": "Setup",
            "status_paused": "Paused",
            "status_maintenance": "Maintenance",
            "status_note_active": "Live operational updates",
            "status_note_seasonal": "Quiet seasonal monitoring",
            "status_note_setup": "Preparing the first operational steps",
            "status_note_paused": "The property is temporarily paused",
            "status_note_maintenance": "Tracking an active maintenance window",
            "empty_state_title": "Welcome to BlackSea Connect",
            "empty_state_copy": "Add your first property to begin operational preparation.",
            "empty_state_cta": "Add property",
            "onboarding_eyebrow": "Onboarding",
            "onboarding_title": "Preparing your property operations.",
            "onboarding_stage_property_added": "Property added",
            "onboarding_stage_information_reviewed": "Information reviewed",
            "onboarding_stage_operations_configured": "Operations configured",
            "onboarding_stage_concierge_ready": "Concierge ready",
            "onboarding_pending": "Pending",
            "onboarding_complete": "Complete",
            "ready": "Ready",
            "properties_eyebrow": "Properties",
            "properties_title": "Your properties",
            "summary_eyebrow": "Property overview",
            "summary_title": "Everything you need in one calm view.",
            "property_health_eyebrow": "Property health",
            "property_health_title": "What needs attention now.",
            "trusted_local_team_eyebrow": "Trusted local team",
            "trusted_local_team_title": "Who is supporting the property.",
            "assigned_operator_label": "Assigned operator",
            "assigned_operator_suffix": "operator desk",
            "concierge_contact_label": "Concierge contact",
            "service_partners_label": "Service partners",
            "monthly_summary_eyebrow": "Monthly summary",
            "monthly_summary_title": "A concise view of the month.",
            "performance_snapshot_eyebrow": "Performance snapshot",
            "performance_snapshot_title": "Operational indicators only.",
            "activity_timeline_eyebrow": "Activity timeline",
            "activity_timeline_title": "Recent property activity.",
            "quick_actions_eyebrow": "Quick actions",
            "quick_actions_title": "Move quickly without losing visibility.",
            "notification_center_eyebrow": "Notification center",
            "notification_center_title": "Future-ready alerts for the property.",
            "recent_updates_eyebrow": "Recent updates",
            "recent_updates_title": "Latest service activity.",
            "footer_description": "Calm operational solutions for coastal properties.",
            "footer_meta": "The owner portal brings property visibility, requests, and updates into one calm flow.",
            "upcoming_arrivals_label": "Upcoming arrivals",
            "upcoming_departures_label": "Upcoming departures",
            "cleaning_completed_label": "Cleaning completed",
            "cleaning_pending_label": "Cleaning pending",
            "open_guest_requests_label": "Open guest requests",
            "maintenance_issues_label": "Maintenance issues",
            "pending_actions_label": "Pending actions",
            "last_completed_task_label": "Last completed task",
            "arrivals_this_month_label": "Arrivals this month",
            "guest_requests_handled_label": "Guest requests handled",
            "tasks_completed_label": "Tasks completed",
            "average_response_time_label": "Average response time",
            "nights_booked_this_month_label": "Nights booked this month",
            "upcoming_stays_label": "Upcoming stays",
            "completed_turnovers_label": "Completed turnovers",
            "request_cleaning": "Request cleaning",
            "request_inspection": "Request inspection",
            "request_maintenance": "Request maintenance",
            "contact_concierge": "Contact concierge",
            "fast_turnover_support": "Fast turnover support",
            "check_readiness": "Check readiness",
            "keep_property_protected": "Keep the property protected",
            "private_local_contact": "Private local contact",
            "projected": "Projected",
            "verified": "Verified",
            "open": "Open",
            "needs_attention": "Needs attention",
            "service_review": "Service review",
            "operator_follow_up": "Operator follow-up",
            "most_recent_closed_item": "Most recent closed item",
            "property_movement": "Property movement",
            "live_resolved": "Live + resolved",
            "confirmed": "Confirmed",
            "from_request_to_first_action": "From request to first action",
            "operational": "Operational",
            "next_arrivals": "Next arrivals",
            "resolved": "Resolved",
            "today": "Today",
            "yesterday": "Yesterday",
            "this_week": "This week",
            "scheduled": "Scheduled",
            "recently": "Recently",
            "timeline_cleaning_completed": "Cleaning completed",
            "timeline_cleaning_completed_detail": "The latest turnover was closed for your property.",
            "timeline_guest_checked_in": "Guest checked in",
            "timeline_guest_checked_in_detail": "Arrival coordination is active and ready.",
            "timeline_maintenance_resolved": "Maintenance request resolved",
            "timeline_maintenance_resolved_detail": "The local team finished the repair window.",
            "timeline_airport_transfer_confirmed": "Airport transfer confirmed",
            "timeline_airport_transfer_confirmed_detail": "Pickup support is scheduled and tracked.",
            "timeline_property_inspection_completed": "Property inspection completed",
            "timeline_property_inspection_completed_detail": "The readiness review has been signed off.",
            "timeline_cleaning_scheduled": "Cleaning scheduled",
            "timeline_cleaning_scheduled_detail": "The next turnover is being prepared with care.",
            "timeline_property_update": "Property update",
            "timeline_property_update_detail": "Current status is being monitored.",
            "request_id_label": "Request ID:",
            "updated_label": "Updated:",
            "new_arrival": "New arrival",
            "welcome_coordination_ready": "Welcome coordination is ready.",
            "cleaning_completed_notification": "Cleaning completed",
            "housekeeping_closed_latest_turn": "Housekeeping closed the latest turn.",
            "guest_issue_reported": "Guest issue reported",
            "concierge_can_step_in_immediately": "Concierge can step in immediately.",
            "maintenance_completed": "Maintenance completed",
            "local_team_wrapped_task": "The local team has wrapped the task.",
            "owner_status_new": "New",
            "owner_status_assigned": "Assigned",
            "owner_status_in_progress": "In progress",
            "owner_status_completed": "Completed",
            "owner_status_cancelled": "Cancelled",
        },
        "fr": {
            "page_title": "BlackSea Connect | Tableau de bord propriétaire",
            "page_meta": "Tableau premium pour vos biens, opérations et services.",
            "nav_portal": "Tableau de bord",
            "nav_request_service": "Demander un service",
            "nav_logout": "Déconnexion",
            "nav_home": "Retour au site",
            "nav_services": "Services",
            "nav_partners": "Partenaires",
            "nav_pilot_access": "Accès pilote",
            "profile_profile": "Profil",
            "profile_properties": "Biens",
            "profile_logout": "Déconnexion",
            "hero_eyebrow": "Espace propriétaire",
            "hero_title": "Aperçu premium du bien.",
            "hero_copy": "Suivez les biens, les tâches et la préparation opérationnelle dans une vue apaisée.",
            "hero_summary_line": "Une vue privée des opérations de votre bien.",
            "hero_empty_hint": "Ajoutez votre premier bien pour lancer la préparation opérationnelle.",
            "empty_activity_copy": "Aucune demande de service pour le moment. Le tableau affichera chaque demande dès son envoi.",
            "hero_primary_cta": "Demander un service",
            "hero_secondary_cta": "Déconnexion",
            "property_status_label": "Statut du bien",
            "location_label": "Localisation",
            "property_type_label": "Type de bien",
            "property_name_label": "Nom du bien",
            "city_label": "Ville",
            "status_label": "Statut",
            "bedrooms_label": "Chambres",
            "bathrooms_label": "Salles de bain",
            "capacity_label": "Capacité",
            "units_label": "Unités",
            "operating_mode_label": "Mode d’exploitation",
            "mode_year_round": "Toute l’année",
            "mode_seasonal": "Saisonnier",
            "property_type_residence": "Résidence côtière",
            "location_pending": "Localisation à renseigner",
            "status_active": "Actif",
            "status_seasonal": "Saisonnier",
            "status_setup": "Configuration",
            "status_paused": "En pause",
            "status_maintenance": "Maintenance",
            "status_note_active": "Mises à jour opérationnelles en direct",
            "status_note_seasonal": "Surveillance saisonnière calme",
            "status_note_setup": "Préparation des premières étapes opérationnelles",
            "status_note_paused": "Le bien est temporairement en pause",
            "status_note_maintenance": "Suivi d’une maintenance en cours",
            "empty_state_title": "Bienvenue chez BlackSea Connect",
            "empty_state_copy": "Ajoutez votre premier bien pour lancer la préparation opérationnelle.",
            "empty_state_cta": "Ajouter un bien",
            "onboarding_eyebrow": "Onboarding",
            "onboarding_title": "Préparation des opérations du bien.",
            "onboarding_stage_property_added": "Bien ajouté",
            "onboarding_stage_information_reviewed": "Informations vérifiées",
            "onboarding_stage_operations_configured": "Opérations configurées",
            "onboarding_stage_concierge_ready": "Concierge prêt",
            "onboarding_pending": "En attente",
            "onboarding_complete": "Terminé",
            "ready": "Prêt",
            "properties_eyebrow": "Biens",
            "properties_title": "Vos biens",
            "summary_eyebrow": "Aperçu du bien",
            "summary_title": "Tout ce qu’il faut dans une vue sereine.",
            "property_health_eyebrow": "État du bien",
            "property_health_title": "Ce qui demande de l’attention maintenant.",
            "trusted_local_team_eyebrow": "Équipe locale de confiance",
            "trusted_local_team_title": "Qui soutient le bien.",
            "assigned_operator_label": "Opérateur assigné",
            "assigned_operator_suffix": "bureau opérateur",
            "concierge_contact_label": "Contact concierge",
            "service_partners_label": "Partenaires de service",
            "monthly_summary_eyebrow": "Résumé mensuel",
            "monthly_summary_title": "Une vue concise du mois.",
            "performance_snapshot_eyebrow": "Vue d’ensemble des performances",
            "performance_snapshot_title": "Indicateurs opérationnels uniquement.",
            "activity_timeline_eyebrow": "Chronologie de l’activité",
            "activity_timeline_title": "Activité récente du bien.",
            "quick_actions_eyebrow": "Actions rapides",
            "quick_actions_title": "Agissez vite sans perdre en visibilité.",
            "notification_center_eyebrow": "Centre de notifications",
            "notification_center_title": "Alertes prêtes pour l’avenir.",
            "recent_updates_eyebrow": "Mises à jour récentes",
            "recent_updates_title": "Dernière activité de service.",
            "footer_description": "Solutions opérationnelles apaisées pour les biens côtiers.",
            "footer_meta": "Le portail propriétaire réunit la visibilité du bien, les demandes et les mises à jour dans un seul flux serein.",
            "upcoming_arrivals_label": "Arrivées à venir",
            "upcoming_departures_label": "Départs à venir",
            "cleaning_completed_label": "Ménages terminés",
            "cleaning_pending_label": "Ménages à venir",
            "open_guest_requests_label": "Demandes ouvertes",
            "maintenance_issues_label": "Problèmes de maintenance",
            "pending_actions_label": "Actions en attente",
            "last_completed_task_label": "Dernière tâche terminée",
            "arrivals_this_month_label": "Arrivées ce mois-ci",
            "guest_requests_handled_label": "Demandes traitées",
            "tasks_completed_label": "Tâches terminées",
            "average_response_time_label": "Temps de réponse moyen",
            "nights_booked_this_month_label": "Nuits réservées ce mois-ci",
            "upcoming_stays_label": "Séjours à venir",
            "completed_turnovers_label": "Rotations terminées",
            "request_cleaning": "Demander le ménage",
            "request_inspection": "Demander une inspection",
            "request_maintenance": "Demander une maintenance",
            "contact_concierge": "Contacter le concierge",
            "fast_turnover_support": "Soutien rapide à la rotation",
            "check_readiness": "Vérifier la préparation",
            "keep_property_protected": "Protéger le bien",
            "private_local_contact": "Contact local privé",
            "projected": "Prévu",
            "verified": "Vérifié",
            "open": "Ouvert",
            "needs_attention": "Nécessite de l’attention",
            "service_review": "Revue du service",
            "operator_follow_up": "Suivi de l’opérateur",
            "most_recent_closed_item": "Dernière tâche clôturée",
            "property_movement": "Mouvement du bien",
            "live_resolved": "En direct + résolu",
            "confirmed": "Confirmé",
            "from_request_to_first_action": "De la demande à la première action",
            "operational": "Opérationnel",
            "next_arrivals": "Prochaines arrivées",
            "resolved": "Résolu",
            "today": "Aujourd’hui",
            "yesterday": "Hier",
            "this_week": "Cette semaine",
            "scheduled": "Planifié",
            "recently": "Récemment",
            "timeline_cleaning_completed": "Ménage terminé",
            "timeline_cleaning_completed_detail": "La dernière rotation a été clôturée pour votre bien.",
            "timeline_guest_checked_in": "Arrivée du client confirmée",
            "timeline_guest_checked_in_detail": "La coordination d’arrivée est active et prête.",
            "timeline_maintenance_resolved": "Demande de maintenance résolue",
            "timeline_maintenance_resolved_detail": "L’équipe locale a terminé la fenêtre de réparation.",
            "timeline_airport_transfer_confirmed": "Transfert aéroport confirmé",
            "timeline_airport_transfer_confirmed_detail": "L’accompagnement à l’arrivée est planifié et suivi.",
            "timeline_property_inspection_completed": "Inspection du bien terminée",
            "timeline_property_inspection_completed_detail": "La revue de préparation a été validée.",
            "timeline_cleaning_scheduled": "Ménage planifié",
            "timeline_cleaning_scheduled_detail": "La prochaine rotation est préparée avec soin.",
            "timeline_property_update": "Mise à jour du bien",
            "timeline_property_update_detail": "Le statut actuel est surveillé.",
            "request_id_label": "ID de demande :",
            "updated_label": "Mis à jour :",
            "new_arrival": "Nouvelle arrivée",
            "welcome_coordination_ready": "La coordination d’accueil est prête.",
            "cleaning_completed_notification": "Ménage terminé",
            "housekeeping_closed_latest_turn": "Le ménage a clôturé la dernière rotation.",
            "guest_issue_reported": "Incident client signalé",
            "concierge_can_step_in_immediately": "Le concierge peut intervenir immédiatement.",
            "maintenance_completed": "Maintenance terminée",
            "local_team_wrapped_task": "L’équipe locale a terminé la tâche.",
            "owner_status_new": "Nouveau",
            "owner_status_assigned": "Attribué",
            "owner_status_in_progress": "En cours",
            "owner_status_completed": "Terminé",
            "owner_status_cancelled": "Annulé",
        },
        "ru": {
            "page_title": "BlackSea Connect | Панель владельца",
            "page_meta": "Премиальная панель для ваших объектов, операций и услуг.",
            "nav_portal": "Панель",
            "nav_request_service": "Запросить услугу",
            "nav_logout": "Выйти",
            "nav_home": "Вернуться на сайт",
            "nav_services": "Услуги",
            "nav_partners": "Партнёры",
            "nav_pilot_access": "Пилотный доступ",
            "profile_profile": "Профиль",
            "profile_properties": "Объекты",
            "profile_logout": "Выйти",
            "hero_eyebrow": "Портал владельца",
            "hero_title": "Премиальный обзор объекта.",
            "hero_copy": "Отслеживайте объекты, задачи и оперативную готовность в одном спокойном виде.",
            "hero_summary_line": "Приватный обзор операций вашего объекта.",
            "hero_empty_hint": "Добавьте первый объект, чтобы начать операционную подготовку.",
            "empty_activity_copy": "Пока нет сервисных запросов. Панель покажет каждый запрос сразу после отправки.",
            "hero_primary_cta": "Запросить услугу",
            "hero_secondary_cta": "Выйти",
            "property_status_label": "Статус объекта",
            "location_label": "Локация",
            "property_type_label": "Тип объекта",
            "property_name_label": "Название объекта",
            "city_label": "Город",
            "status_label": "Статус",
            "bedrooms_label": "Спальни",
            "bathrooms_label": "Ванные",
            "capacity_label": "Вместимость",
            "units_label": "Единицы",
            "operating_mode_label": "Режим работы",
            "mode_year_round": "Круглый год",
            "mode_seasonal": "Сезонный",
            "property_type_residence": "Курортная резиденция",
            "location_pending": "Локация уточняется",
            "status_active": "Активен",
            "status_seasonal": "Сезонный",
            "status_setup": "Настройка",
            "status_paused": "Приостановлен",
            "status_maintenance": "Обслуживание",
            "status_note_active": "Актуальные операционные обновления",
            "status_note_seasonal": "Спокойный сезонный мониторинг",
            "status_note_setup": "Подготавливаем первые операционные шаги",
            "status_note_paused": "Объект временно приостановлен",
            "status_note_maintenance": "Отслеживается активное окно обслуживания",
            "empty_state_title": "Добро пожаловать в BlackSea Connect",
            "empty_state_copy": "Добавьте первый объект, чтобы начать операционную подготовку.",
            "empty_state_cta": "Добавить объект",
            "onboarding_eyebrow": "Onboarding",
            "onboarding_title": "Подготовка операций объекта.",
            "onboarding_stage_property_added": "Объект добавлен",
            "onboarding_stage_information_reviewed": "Информация проверена",
            "onboarding_stage_operations_configured": "Операции настроены",
            "onboarding_stage_concierge_ready": "Консьерж готов",
            "onboarding_pending": "В ожидании",
            "onboarding_complete": "Готово",
            "ready": "Готово",
            "properties_eyebrow": "Объекты",
            "properties_title": "Ваши объекты",
            "summary_eyebrow": "Обзор объекта",
            "summary_title": "Всё необходимое в одном спокойном виде.",
            "property_health_eyebrow": "Состояние объекта",
            "property_health_title": "Что требует внимания сейчас.",
            "trusted_local_team_eyebrow": "Надёжная местная команда",
            "trusted_local_team_title": "Кто поддерживает объект.",
            "assigned_operator_label": "Назначенный оператор",
            "assigned_operator_suffix": "операторский отдел",
            "concierge_contact_label": "Контакт консьержа",
            "service_partners_label": "Партнёры по услугам",
            "monthly_summary_eyebrow": "Ежемесячная сводка",
            "monthly_summary_title": "Краткий обзор месяца.",
            "performance_snapshot_eyebrow": "Снимок эффективности",
            "performance_snapshot_title": "Только операционные индикаторы.",
            "activity_timeline_eyebrow": "Хронология активности",
            "activity_timeline_title": "Недавняя активность объекта.",
            "quick_actions_eyebrow": "Быстрые действия",
            "quick_actions_title": "Действуйте быстро, не теряя видимость.",
            "notification_center_eyebrow": "Центр уведомлений",
            "notification_center_title": "Уведомления, готовые к будущему.",
            "recent_updates_eyebrow": "Последние обновления",
            "recent_updates_title": "Последняя сервисная активность.",
            "footer_description": "Спокойные операционные решения для объектов у моря.",
            "footer_meta": "Портал владельца объединяет видимость объекта, запросы и обновления в один спокойный поток.",
            "upcoming_arrivals_label": "Предстоящие заезды",
            "upcoming_departures_label": "Предстоящие выезды",
            "cleaning_completed_label": "Завершённые уборки",
            "cleaning_pending_label": "Уборки в ожидании",
            "open_guest_requests_label": "Открытые запросы гостей",
            "maintenance_issues_label": "Проблемы обслуживания",
            "pending_actions_label": "Ожидают действий",
            "last_completed_task_label": "Последняя завершённая задача",
            "arrivals_this_month_label": "Заезды в этом месяце",
            "guest_requests_handled_label": "Обработанные запросы гостей",
            "tasks_completed_label": "Завершённые задачи",
            "average_response_time_label": "Среднее время отклика",
            "nights_booked_this_month_label": "Ночей забронировано в этом месяце",
            "upcoming_stays_label": "Предстоящие проживания",
            "completed_turnovers_label": "Завершённые смены",
            "request_cleaning": "Запросить уборку",
            "request_inspection": "Запросить инспекцию",
            "request_maintenance": "Запросить обслуживание",
            "contact_concierge": "Связаться с консьержем",
            "fast_turnover_support": "Быстрая поддержка смены",
            "check_readiness": "Проверить готовность",
            "keep_property_protected": "Сохранить объект защищённым",
            "private_local_contact": "Приватный местный контакт",
            "projected": "Прогноз",
            "verified": "Проверено",
            "open": "Открыто",
            "needs_attention": "Требует внимания",
            "service_review": "Проверка сервиса",
            "operator_follow_up": "Дальнейшая работа оператора",
            "most_recent_closed_item": "Последняя закрытая задача",
            "property_movement": "Движение объекта",
            "live_resolved": "В реальном времени + завершено",
            "confirmed": "Подтверждено",
            "from_request_to_first_action": "От запроса до первого действия",
            "operational": "Операционно",
            "next_arrivals": "Следующие заезды",
            "resolved": "Решено",
            "today": "Сегодня",
            "yesterday": "Вчера",
            "this_week": "На этой неделе",
            "scheduled": "Запланировано",
            "recently": "Недавно",
            "timeline_cleaning_completed": "Уборка завершена",
            "timeline_cleaning_completed_detail": "Последняя смена закрыта для вашего объекта.",
            "timeline_guest_checked_in": "Гость заселился",
            "timeline_guest_checked_in_detail": "Координация заезда активна и готова.",
            "timeline_maintenance_resolved": "Запрос на обслуживание решён",
            "timeline_maintenance_resolved_detail": "Местная команда завершила окно ремонта.",
            "timeline_airport_transfer_confirmed": "Трансфер из аэропорта подтверждён",
            "timeline_airport_transfer_confirmed_detail": "Поддержка встречи запланирована и отслеживается.",
            "timeline_property_inspection_completed": "Инспекция объекта завершена",
            "timeline_property_inspection_completed_detail": "Проверка готовности подтверждена.",
            "timeline_cleaning_scheduled": "Уборка запланирована",
            "timeline_cleaning_scheduled_detail": "Следующая смена готовится тщательно.",
            "timeline_property_update": "Обновление объекта",
            "timeline_property_update_detail": "Текущий статус находится под наблюдением.",
            "request_id_label": "ID запроса:",
            "updated_label": "Обновлено:",
            "new_arrival": "Новое прибытие",
            "welcome_coordination_ready": "Координация встречи готова.",
            "cleaning_completed_notification": "Уборка завершена",
            "housekeeping_closed_latest_turn": "Команда уборки закрыла последнюю смену.",
            "guest_issue_reported": "Сообщена проблема гостя",
            "concierge_can_step_in_immediately": "Консьерж может вмешаться немедленно.",
            "maintenance_completed": "Обслуживание завершено",
            "local_team_wrapped_task": "Местная команда завершила задачу.",
            "owner_status_new": "Новый",
            "owner_status_assigned": "Назначен",
            "owner_status_in_progress": "В процессе",
            "owner_status_completed": "Завершён",
            "owner_status_cancelled": "Отменён",
        },
    }
    return copy.get(lang, copy["bg"])


def _owner_property_status(property_record, has_owner_requests, dashboard_copy):
    operating_mode = str(property_record.get("operating_mode", "")).strip().lower()
    notes = str(property_record.get("notes", "")).strip().lower()

    if "paused" in notes:
        return "paused", dashboard_copy["status_paused"], "ownerDashboardPropertyStatusPaused", "paused", dashboard_copy["status_note_paused"]
    if operating_mode == "seasonal":
        return "seasonal", dashboard_copy["status_seasonal"], "ownerDashboardPropertyStatusSeasonal", "seasonal", dashboard_copy["status_note_seasonal"]
    if not has_owner_requests:
        return "setup", dashboard_copy["status_setup"], "ownerDashboardPropertyStatusOnboarding", "setup", dashboard_copy["status_note_setup"]
    return "active", dashboard_copy["status_active"], "ownerDashboardPropertyStatusActive", "active", dashboard_copy["status_note_active"]


def _owner_property_status_key(status):
    normalized = str(status or "").strip().lower()
    if normalized == "seasonal":
        return "ownerDashboardStatusSeasonal"
    if normalized == "setup":
        return "ownerDashboardStatusOnboarding"
    if normalized == "paused":
        return "ownerDashboardStatusPaused"
    if normalized == "maintenance":
        return "ownerDashboardStatusMaintenance"
    return "ownerDashboardStatusActive"


def _owner_property_card_context(property_record, has_owner_requests, dashboard_copy):
    status, status_label, status_key, status_tone, status_note = _owner_property_status(property_record, has_owner_requests, dashboard_copy)
    bedrooms = str(property_record.get("bedrooms", "")).strip() or "0"
    bathrooms = str(property_record.get("bathrooms", "")).strip() or "0"
    guest_capacity = str(property_record.get("guest_capacity", "")).strip() or "0"
    operating_mode = str(property_record.get("operating_mode", "")).strip().lower() or "year-round"
    operating_mode_label = dashboard_copy["mode_seasonal"] if operating_mode == "seasonal" else dashboard_copy["mode_year_round"]
    operating_mode_key = "ownerPropertyModeSeasonal" if operating_mode == "seasonal" else "ownerPropertyModeYearRound"
    if status == "paused":
        status_note_key = "ownerPropertyStatusNotePaused"
    elif status == "seasonal":
        status_note_key = "ownerPropertyStatusNoteSeasonal"
    elif status == "active":
        status_note_key = "ownerPropertyStatusNoteActive"
    else:
        status_note_key = "ownerPropertyStatusNoteOnboarding"

    return {
        "id": property_record.get("id", ""),
        "name": str(property_record.get("name", "")).strip() or dashboard_copy["property_type_residence"],
        "property_type": str(property_record.get("property_type", "")).strip() or dashboard_copy["property_type_residence"],
        "location": str(property_record.get("location", "")).strip() or dashboard_copy["location_pending"],
        "bedrooms": bedrooms,
        "bathrooms": bathrooms,
        "guest_capacity": guest_capacity,
        "operating_mode": operating_mode,
        "operating_mode_label": operating_mode_label,
        "operating_mode_key": operating_mode_key,
        "notes": str(property_record.get("notes", "")).strip(),
        "status": status,
        "status_label": status_label,
        "status_key": status_key,
        "status_tone": status_tone,
        "status_note": status_note,
        "status_note_key": status_note_key,
        "created_at": str(property_record.get("created_at", "")).strip(),
    }


def _owner_portal_activity_timeline(owner_requests, dashboard_copy):
    demo_items = [
        {
            "label": dashboard_copy["timeline_cleaning_completed"],
            "label_key": "ownerDashboardCleaningCompletedTimeline",
            "detail": dashboard_copy["timeline_cleaning_completed_detail"],
            "detail_key": "ownerDashboardCleaningCompletedTimelineDetail",
            "time": dashboard_copy["today"],
            "time_key": "ownerDashboardTimelineToday",
            "tone": "success",
        },
        {
            "label": dashboard_copy["timeline_guest_checked_in"],
            "label_key": "ownerDashboardGuestCheckedInTimeline",
            "detail": dashboard_copy["timeline_guest_checked_in_detail"],
            "detail_key": "ownerDashboardGuestCheckedInTimelineDetail",
            "time": dashboard_copy["yesterday"],
            "time_key": "ownerDashboardTimelineYesterday",
            "tone": "arrival",
        },
        {
            "label": dashboard_copy["timeline_maintenance_resolved"],
            "label_key": "ownerDashboardMaintenanceRequestResolvedTimeline",
            "detail": dashboard_copy["timeline_maintenance_resolved_detail"],
            "detail_key": "ownerDashboardMaintenanceRequestResolvedTimelineDetail",
            "time": dashboard_copy["this_week"],
            "time_key": "ownerDashboardTimelineThisWeek",
            "tone": "maintenance",
        },
        {
            "label": dashboard_copy["timeline_airport_transfer_confirmed"],
            "label_key": "ownerDashboardAirportTransferConfirmedTimeline",
            "detail": dashboard_copy["timeline_airport_transfer_confirmed_detail"],
            "detail_key": "ownerDashboardAirportTransferConfirmedTimelineDetail",
            "time": dashboard_copy["scheduled"],
            "time_key": "ownerDashboardTimelineScheduled",
            "tone": "transport",
        },
        {
            "label": dashboard_copy["timeline_property_inspection_completed"],
            "label_key": "ownerDashboardPropertyInspectionCompletedTimeline",
            "detail": dashboard_copy["timeline_property_inspection_completed_detail"],
            "detail_key": "ownerDashboardPropertyInspectionCompletedTimelineDetail",
            "time": dashboard_copy["recently"],
            "time_key": "ownerDashboardTimelineRecently",
            "tone": "inspection",
        },
    ]
    if not owner_requests:
        return demo_items

    timeline_items = []
    for record in owner_requests[:5]:
        category = str(record.get("service_category", "")).strip() or dashboard_copy["timeline_property_update"]
        status = _normalize_service_request_status(record.get("status", "new"))
        if "clean" in category.lower():
            label = dashboard_copy["timeline_cleaning_completed"] if status == "completed" else dashboard_copy["timeline_cleaning_scheduled"]
            label_key = "ownerDashboardCleaningCompletedTimeline" if status == "completed" else "ownerDashboardCleaningScheduledTimeline"
            detail = dashboard_copy["timeline_cleaning_completed_detail"] if status == "completed" else dashboard_copy["timeline_cleaning_scheduled_detail"]
            detail_key = "ownerDashboardCleaningCompletedTimelineDetail" if status == "completed" else "ownerDashboardCleaningScheduledTimelineDetail"
            tone = "success"
        elif "transfer" in category.lower():
            label = dashboard_copy["timeline_airport_transfer_confirmed"]
            label_key = "ownerDashboardAirportTransferConfirmedTimeline"
            detail = dashboard_copy["timeline_airport_transfer_confirmed_detail"]
            detail_key = "ownerDashboardAirportTransferConfirmedTimelineDetail"
            tone = "arrival"
        elif "inspect" in category.lower():
            label = dashboard_copy["timeline_property_inspection_completed"]
            label_key = "ownerDashboardPropertyInspectionCompletedTimeline"
            detail = dashboard_copy["timeline_property_inspection_completed_detail"]
            detail_key = "ownerDashboardPropertyInspectionCompletedTimelineDetail"
            tone = "inspection"
        elif "maint" in category.lower():
            label = dashboard_copy["timeline_maintenance_resolved"] if status == "completed" else dashboard_copy["timeline_property_update"]
            label_key = "ownerDashboardMaintenanceRequestResolvedTimeline" if status == "completed" else "ownerDashboardMaintenanceRequestInProgressTimeline"
            detail = dashboard_copy["timeline_maintenance_resolved_detail"] if status == "completed" else dashboard_copy["timeline_property_update_detail"]
            detail_key = "ownerDashboardMaintenanceRequestResolvedTimelineDetail" if status == "completed" else "ownerDashboardMaintenanceRequestInProgressTimelineDetail"
            tone = "maintenance"
        else:
            label = dashboard_copy["timeline_property_update"]
            label_key = "ownerDashboardPropertyUpdateTimeline"
            detail = dashboard_copy["timeline_property_update_detail"]
            detail_key = "ownerDashboardPropertyUpdateTimelineDetail"
            tone = "arrival"

        timeline_items.append({
            "label": label,
            "label_key": label_key,
            "detail": detail,
            "detail_key": detail_key,
            "time": _format_owner_portal_timestamp(record.get("last_update_at", record.get("created_at", ""))) or dashboard_copy["recently"],
            "time_key": "",
            "tone": tone,
        })

    while len(timeline_items) < 5:
        timeline_items.append(demo_items[len(timeline_items)])

    return timeline_items[:5]


def _owner_portal_dashboard_context(owner_account, owner_requests, current_lang):
    dashboard_copy = _owner_dashboard_copy(current_lang)
    owner_properties = [
        property_record
        for property_record in _load_owner_properties()
        if str(property_record.get("owner_id", "")).strip() == str(owner_account.get("id", "")).strip()
    ]
    has_properties = bool(owner_properties)
    property_cards = [_owner_property_card_context(property_record, bool(owner_requests), dashboard_copy) for property_record in owner_properties]
    primary_property = property_cards[0] if property_cards else None
    property_name = primary_property["name"] if primary_property else str(owner_account.get("property_name", "")).strip() or dashboard_copy["property_type_residence"]
    city = ""
    if primary_property:
        city = primary_property["location"]
    if not city:
        city = str(owner_account.get("city", "")).strip() or dashboard_copy["location_pending"]

    onboarding_stages = [
        {
            "label": dashboard_copy["onboarding_stage_property_added"],
            "label_key": "ownerOnboardingStagePropertyAdded",
            "complete": has_properties,
        },
        {
            "label": dashboard_copy["onboarding_stage_information_reviewed"],
            "label_key": "ownerOnboardingStageInformationReviewed",
            "complete": has_properties,
        },
        {
            "label": dashboard_copy["onboarding_stage_operations_configured"],
            "label_key": "ownerOnboardingStageOperationsConfigured",
            "complete": bool(owner_requests),
        },
        {
            "label": dashboard_copy["onboarding_stage_concierge_ready"],
            "label_key": "ownerOnboardingStageConciergeReady",
            "complete": bool(owner_requests and any(_normalize_service_request_status(request.get("status", "new")) in {"assigned", "in_progress", "completed"} for request in owner_requests)),
        },
    ]
    onboarding_completed = sum(1 for stage in onboarding_stages if stage["complete"])
    onboarding_percentage = int(round((onboarding_completed / len(onboarding_stages)) * 100)) if onboarding_stages else 0

    completed_requests = [
        request
        for request in owner_requests
        if _normalize_service_request_status(request.get("status", "new")) == "completed"
    ]
    open_requests = [
        request
        for request in owner_requests
        if _normalize_service_request_status(request.get("status", "new")) in {"new", "assigned", "in_progress"}
    ]
    current_month_prefix = datetime.now(timezone.utc).strftime("%Y-%m")
    current_month_requests = [
        request
        for request in owner_requests
        if str(request.get("created_at", "")).startswith(current_month_prefix)
    ]
    maintenance_requests = [
        request
        for request in owner_requests
        if any(keyword in str(request.get("service_category", "")).lower() for keyword in ("maintenance", "inspection", "plumb", "electr"))
    ]
    cleaning_requests = [
        request
        for request in owner_requests
        if "clean" in str(request.get("service_category", "")).lower()
    ]

    response_minutes = [
        minutes
        for minutes in (_owner_portal_response_minutes(request) for request in owner_requests)
        if minutes is not None
    ]
    average_response_minutes = (
        round(sum(response_minutes) / len(response_minutes))
        if response_minutes
        else None
    )

    upcoming_arrivals = len(current_month_requests) + (1 if owner_requests else 0)
    upcoming_departures = len([
        request
        for request in current_month_requests
        if _normalize_service_request_status(request.get("status", "new")) == "completed"
    ]) + (1 if owner_requests else 0)
    cleaning_completed = len([
        request
        for request in completed_requests
        if "clean" in str(request.get("service_category", "")).lower()
    ])
    cleaning_pending = len([
        request
        for request in open_requests
        if "clean" in str(request.get("service_category", "")).lower()
    ])
    open_guest_requests = len(open_requests)
    monthly_guest_requests = len(current_month_requests)
    tasks_completed = len(completed_requests)
    nights_booked_this_month = max(1, len(current_month_requests) + len(completed_requests))
    upcoming_stays = max(1, len(open_requests) or len(current_month_requests) or 1)
    completed_turnovers = max(1, cleaning_completed or tasks_completed)
    guest_requests_handled = max(1, len(owner_requests) + len(current_month_requests))

    property_status = dashboard_copy["status_active"]
    property_status_slug = "active"
    status_tone = "active"
    status_note = dashboard_copy["status_note_active"]
    if maintenance_requests and not open_requests:
        property_status = dashboard_copy["status_maintenance"]
        property_status_slug = "maintenance"
        status_tone = "maintenance"
        status_note = dashboard_copy["status_note_maintenance"]
        status_note_key = "ownerDashboardStatusNoteFollowUpInProgress"
    elif not owner_requests:
        property_status = dashboard_copy["status_seasonal"]
        property_status_slug = "seasonal"
        status_tone = "seasonal"
        status_note = dashboard_copy["status_note_seasonal"]
        status_note_key = "ownerDashboardStatusNoteQuietMonitoringMode"
    else:
        status_note_key = "ownerDashboardStatusNoteLiveOperationalUpdates"

    last_completed_task = dashboard_copy["last_completed_task_label"]
    last_completed_task_key = "ownerDashboardLastCompletedTaskWaiting"
    if completed_requests:
        latest_completed = max(completed_requests, key=lambda request: str(request.get("last_update_at", request.get("created_at", ""))))
        latest_category = str(latest_completed.get("service_category", "")).strip()
        last_completed_task = latest_category or latest_completed.get("description", "") or dashboard_copy["last_completed_task_label"]
        last_completed_task_key = OWNER_SERVICE_CATEGORY_TRANSLATION_KEYS.get(latest_category, "") if latest_category else ""

    owner_portal = {
        "empty_state": not has_properties,
        "has_properties": has_properties,
        "properties": property_cards,
        "primary_property": primary_property or {},
        "onboarding": {
            "percentage": onboarding_percentage,
            "stages": [
                {
                    **stage,
                    "label": dashboard_copy["onboarding_title"] if idx == 0 and not stage["complete"] else stage["label"],
                }
                for idx, stage in enumerate(onboarding_stages)
            ],
        },
        "property_overview": {
            "property_name": property_name,
            "city": city,
            "location": city,
            "status": primary_property["status_label"] if primary_property else property_status,
            "status_key": primary_property["status_key"] if primary_property else _owner_property_status_key(property_status_slug),
            "status_tone": primary_property["status_tone"] if primary_property else status_tone,
            "status_note": primary_property["status_note"] if primary_property else status_note,
            "status_note_key": primary_property["status_note_key"] if primary_property else status_note_key,
            "property_type": primary_property["property_type"] if primary_property else str(owner_account.get("property_type", "")).strip() or dashboard_copy["property_type_residence"],
            "property_type_key": "ownerDashboardPropertyTypeResidence",
            "units": primary_property["guest_capacity"] if primary_property else str(owner_account.get("number_of_units", "")).strip() or "1",
        },
        "operations_snapshot": [
            {"label": dashboard_copy["upcoming_arrivals_label"], "label_key": "ownerDashboardUpcomingArrivalsLabel", "value": _owner_portal_metric_value_with_key(upcoming_arrivals, "Scheduled", "ownerMetricScheduled")[0], "value_key": _owner_portal_metric_value_with_key(upcoming_arrivals, "Scheduled", "ownerMetricScheduled")[1], "support": dashboard_copy["projected"], "support_key": "ownerDashboardProjected"},
            {"label": dashboard_copy["upcoming_departures_label"], "label_key": "ownerDashboardUpcomingDeparturesLabel", "value": _owner_portal_metric_value_with_key(upcoming_departures, "Scheduled", "ownerMetricScheduled")[0], "value_key": _owner_portal_metric_value_with_key(upcoming_departures, "Scheduled", "ownerMetricScheduled")[1], "support": dashboard_copy["projected"], "support_key": "ownerDashboardProjected"},
            {"label": dashboard_copy["cleaning_completed_label"], "label_key": "ownerDashboardCleaningCompletedLabel", "value": _owner_portal_metric_value_with_key(cleaning_completed, "Growing", "ownerMetricGrowing")[0], "value_key": _owner_portal_metric_value_with_key(cleaning_completed, "Growing", "ownerMetricGrowing")[1], "support": dashboard_copy["verified"], "support_key": "ownerDashboardVerified"},
            {"label": dashboard_copy["cleaning_pending_label"], "label_key": "ownerDashboardCleaningPendingLabel", "value": _owner_portal_metric_value_with_key(cleaning_pending, "Ready", "ownerMetricReady")[0], "value_key": _owner_portal_metric_value_with_key(cleaning_pending, "Ready", "ownerMetricReady")[1], "support": dashboard_copy["open"], "support_key": "ownerDashboardOpen"},
            {"label": dashboard_copy["open_guest_requests_label"], "label_key": "ownerDashboardOpenGuestRequestsLabel", "value": _owner_portal_metric_value_with_key(open_guest_requests, "Building", "ownerMetricBuilding")[0], "value_key": _owner_portal_metric_value_with_key(open_guest_requests, "Building", "ownerMetricBuilding")[1], "support": dashboard_copy["needs_attention"], "support_key": "ownerDashboardServiceReview"},
        ],
        "property_health": [
            {"label": dashboard_copy["maintenance_issues_label"], "label_key": "ownerDashboardMaintenanceIssuesLabel", "value": _owner_portal_metric_value_with_key(len(maintenance_requests), "Pilot", "ownerMetricPilot")[0], "value_key": _owner_portal_metric_value_with_key(len(maintenance_requests), "Pilot", "ownerMetricPilot")[1], "support": dashboard_copy["service_review"], "support_key": "ownerDashboardServiceReview"},
            {"label": dashboard_copy["pending_actions_label"], "label_key": "ownerDashboardPendingActionsLabel", "value": _owner_portal_metric_value_with_key(open_guest_requests, "Scheduled", "ownerMetricScheduled")[0], "value_key": _owner_portal_metric_value_with_key(open_guest_requests, "Scheduled", "ownerMetricScheduled")[1], "support": dashboard_copy["operator_follow_up"], "support_key": "ownerDashboardOperatorFollowUp"},
            {"label": dashboard_copy["last_completed_task_label"], "label_key": "ownerDashboardLastCompletedTaskLabel", "value": last_completed_task, "value_key": last_completed_task_key, "support": dashboard_copy["most_recent_closed_item"], "support_key": "ownerDashboardMostRecentClosedItem"},
        ],
        "trusted_local_team": {
            "assigned_operator": f"{city} {dashboard_copy['assigned_operator_suffix']}",
            "assigned_operator_key": "ownerDashboardAssignedOperatorDesk",
            "concierge_contact": "concierge@blackseaconnect.com",
            "service_partners_count": str(max(4, len({str(request.get("assigned_professional", "")).strip() for request in owner_requests if str(request.get("assigned_professional", "")).strip()}))),
        },
        "monthly_summary": [
            {"label": dashboard_copy["arrivals_this_month_label"], "label_key": "ownerDashboardArrivalsThisMonthLabel", "value": _owner_portal_metric_value_with_key(max(1, monthly_guest_requests), "Growing", "ownerMetricGrowing")[0], "value_key": _owner_portal_metric_value_with_key(max(1, monthly_guest_requests), "Growing", "ownerMetricGrowing")[1], "support": dashboard_copy["property_movement"], "support_key": "ownerDashboardPropertyMovement"},
            {"label": dashboard_copy["guest_requests_handled_label"], "label_key": "ownerDashboardGuestRequestsHandledLabel", "value": _owner_portal_metric_value_with_key(guest_requests_handled, "Building", "ownerMetricBuilding")[0], "value_key": _owner_portal_metric_value_with_key(guest_requests_handled, "Building", "ownerMetricBuilding")[1], "support": dashboard_copy["live_resolved"], "support_key": "ownerDashboardLiveResolved"},
            {"label": dashboard_copy["tasks_completed_label"], "label_key": "ownerDashboardTasksCompletedLabel", "value": _owner_portal_metric_value_with_key(tasks_completed, "Pilot", "ownerMetricPilot")[0], "value_key": _owner_portal_metric_value_with_key(tasks_completed, "Pilot", "ownerMetricPilot")[1], "support": dashboard_copy["confirmed"], "support_key": "ownerDashboardConfirmed"},
            {"label": dashboard_copy["average_response_time_label"], "label_key": "ownerDashboardAverageResponseTimeLabel", "value": _format_owner_portal_duration(average_response_minutes) if average_response_minutes is not None else dashboard_copy["ready"], "value_key": "" if average_response_minutes is not None else "ownerMetricReady", "support": dashboard_copy["from_request_to_first_action"], "support_key": "ownerDashboardFromRequestToFirstAction"},
        ],
        "performance_snapshot": [
            {"label": dashboard_copy["nights_booked_this_month_label"], "label_key": "ownerDashboardNightsBookedThisMonthLabel", "value": _owner_portal_metric_value_with_key(nights_booked_this_month, "Pilot", "ownerMetricPilot")[0], "value_key": _owner_portal_metric_value_with_key(nights_booked_this_month, "Pilot", "ownerMetricPilot")[1], "support": dashboard_copy["operational"], "support_key": "ownerDashboardOperational"},
            {"label": dashboard_copy["upcoming_stays_label"], "label_key": "ownerDashboardUpcomingStaysLabel", "value": _owner_portal_metric_value_with_key(upcoming_stays, "Scheduled", "ownerMetricScheduled")[0], "value_key": _owner_portal_metric_value_with_key(upcoming_stays, "Scheduled", "ownerMetricScheduled")[1], "support": dashboard_copy["next_arrivals"], "support_key": "ownerDashboardNextArrivals"},
            {"label": dashboard_copy["completed_turnovers_label"], "label_key": "ownerDashboardCompletedTurnoversLabel", "value": _owner_portal_metric_value_with_key(completed_turnovers, "Growing", "ownerMetricGrowing")[0], "value_key": _owner_portal_metric_value_with_key(completed_turnovers, "Growing", "ownerMetricGrowing")[1], "support": dashboard_copy["verified"], "support_key": "ownerDashboardVerified"},
            {"label": dashboard_copy["guest_requests_handled_label"], "label_key": "ownerDashboardGuestRequestsHandledLabel", "value": _owner_portal_metric_value_with_key(guest_requests_handled, "Building", "ownerMetricBuilding")[0], "value_key": _owner_portal_metric_value_with_key(guest_requests_handled, "Building", "ownerMetricBuilding")[1], "support": dashboard_copy["resolved"], "support_key": "ownerDashboardResolved"},
            {"label": dashboard_copy["average_response_time_label"], "label_key": "ownerDashboardAverageResponseTimeLabel", "value": _format_owner_portal_duration(average_response_minutes) if average_response_minutes is not None else dashboard_copy["ready"], "value_key": "" if average_response_minutes is not None else "ownerMetricReady", "support": dashboard_copy["from_request_to_first_action"], "support_key": "ownerDashboardFromRequestToFirstAction"},
        ],
        "quick_actions": [
            {"label": dashboard_copy["request_cleaning"], "label_key": "ownerDashboardRequestCleaning", "href": "/owners/request-service?category=cleaning", "support": dashboard_copy["fast_turnover_support"], "support_key": "ownerDashboardFastTurnoverSupport"},
            {"label": dashboard_copy["request_inspection"], "label_key": "ownerDashboardRequestInspection", "href": "/owners/request-service?category=inspection", "support": dashboard_copy["check_readiness"], "support_key": "ownerDashboardCheckReadiness"},
            {"label": dashboard_copy["request_maintenance"], "label_key": "ownerDashboardRequestMaintenance", "href": "/owners/request-service?category=maintenance", "support": dashboard_copy["keep_property_protected"], "support_key": "ownerDashboardKeepPropertyProtected"},
            {"label": dashboard_copy["contact_concierge"], "label_key": "ownerDashboardContactConciergeAction", "href": "mailto:concierge@blackseaconnect.com", "support": dashboard_copy["private_local_contact"], "support_key": "ownerDashboardPrivateLocalContact"},
        ],
        "activity_timeline": _owner_portal_activity_timeline(owner_requests, dashboard_copy),
        "notifications": [
            {"label": dashboard_copy["new_arrival"], "label_key": "ownerDashboardNewArrival", "detail": dashboard_copy["welcome_coordination_ready"], "detail_key": "ownerDashboardWelcomeCoordinationReady", "tone": "arrival"},
            {"label": dashboard_copy["cleaning_completed_notification"], "label_key": "ownerDashboardCleaningCompletedNotification", "detail": dashboard_copy["housekeeping_closed_latest_turn"], "detail_key": "ownerDashboardHousekeepingClosedLatestTurn", "tone": "success"},
            {"label": dashboard_copy["guest_issue_reported"], "label_key": "ownerDashboardGuestIssueReported", "detail": dashboard_copy["concierge_can_step_in_immediately"], "detail_key": "ownerDashboardConciergeCanStepInImmediately", "tone": "alert"},
            {"label": dashboard_copy["maintenance_completed"], "label_key": "ownerDashboardMaintenanceCompleted", "detail": dashboard_copy["local_team_wrapped_task"], "detail_key": "ownerDashboardLocalTeamWrappedTask", "tone": "maintenance"},
        ],
        "recent_activity": [
            {
                **record,
                "last_update_display": _format_owner_portal_timestamp(record.get("last_update_at", record.get("created_at", ""))) or dashboard_copy["recently"],
            }
            for record in owner_requests[:3]
        ],
        "summary_line": dashboard_copy["hero_summary_line"],
        "status_note_key": status_note_key,
        "last_completed_task_key": last_completed_task_key,
        "ui": dashboard_copy,
    }

    return owner_portal


def owner_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        current_lang = _resolve_current_language()
        if not session.get(OWNER_SESSION_LOGGED_IN_KEY):
            return redirect(url_for("owners_login", next=request.path, lang=current_lang))
        owner_account = _current_owner_account()
        if not owner_account:
            session.pop(OWNER_SESSION_LOGGED_IN_KEY, None)
            session.pop(OWNER_SESSION_ID_KEY, None)
            session.pop(OWNER_SESSION_EMAIL_KEY, None)
            session.pop(OWNER_SESSION_NAME_KEY, None)
            return redirect(url_for("owners_login", next=request.path, lang=current_lang))
        g.owner_account = owner_account
        return view(*args, **kwargs)

    return wrapped


@app.route("/owners/register", methods=["GET", "POST"])
def owners_register():
    current_lang = _resolve_current_language()
    form_values = {
        "full_name": "",
        "email": "",
        "phone": "",
        "property_type": "",
        "city": "",
        "property_name": "",
        "number_of_units": "",
        "notes": "",
    }
    errors = {}
    submitted = False

    if request.method == "POST":
        form_values.update({
            "full_name": str(request.form.get("full_name", "")).strip(),
            "email": str(request.form.get("email", "")).strip(),
            "phone": str(request.form.get("phone", "")).strip(),
            "property_type": str(request.form.get("property_type", "")).strip(),
            "city": str(request.form.get("city", "")).strip(),
            "property_name": str(request.form.get("property_name", "")).strip(),
            "number_of_units": str(request.form.get("number_of_units", "")).strip(),
            "notes": str(request.form.get("notes", "")).strip(),
        })
        required_fields = {
            "full_name": "fullNameRequiredError",
            "email": "emailRequiredError",
            "phone": "phoneRequiredError",
            "property_type": "propertyTypeRequiredError",
            "city": "cityRequiredError",
            "number_of_units": "numberOfUnitsRequiredError",
        }

        for field, error_key in required_fields.items():
            if not form_values[field]:
                errors[field] = error_key

        if form_values["number_of_units"] and not form_values["number_of_units"].isdigit():
            errors["number_of_units"] = "numberOfUnitsInvalidError"

        if not errors:
            existing_account = _find_owner_account_by_email(form_values["email"])
            account = {
                "id": "",
                "created_at": _utc_now_iso(),
                "full_name": form_values["full_name"],
                "email": form_values["email"],
                "phone": form_values["phone"],
                "property_type": form_values["property_type"],
                "city": form_values["city"],
                "property_name": form_values["property_name"],
                "number_of_units": int(form_values["number_of_units"]),
                "notes": form_values["notes"],
                "language": current_lang,
                "status": OWNER_STATUS_DEFAULT,
            }
            saved_account = _upsert_owner_account(account)
            if saved_account:
                app.logger.info("Owner registration received for %s", _mask_email(saved_account["email"]))
                if not existing_account:
                    _append_owner_activity_event(
                        saved_account["id"],
                        "owner_registered",
                        "Owner registered",
                        saved_account.get("full_name", ""),
                    )
                    _send_owner_registration_notification_email(saved_account, request.url, current_lang)
                magic_token = _create_owner_magic_token(saved_account["email"])
                _append_owner_magic_email_event("token_created", saved_account["email"], "token_created", "register", current_lang)
                login_url = f"{SITE_URL}{url_for('owner_magic_login', token=magic_token['token'], lang=current_lang)}"
                email_language = _owner_magic_link_email_locale(current_lang)
                send_result = _send_owner_magic_link_and_log(saved_account["email"], login_url, email_language, "register")
                if not send_result.get("ok"):
                    _consume_owner_magic_token(magic_token["token"])
                    return redirect(url_for("owners_login", registered="1", magic_sent="0", delivery="failed", lang=current_lang))
                _append_owner_activity_event(
                    saved_account["id"],
                    "magic_link_sent",
                    "Magic link sent",
                    f"Source: register; language: {email_language}",
                )
                submitted = True
                return redirect(url_for("owners_login", registered="1", magic_sent="1", delivery="sent", magic_recipient=_mask_email(saved_account["email"]), lang=current_lang))

    return render_template(
        "owners_register.html",
        form_values=form_values,
        errors=errors,
        submitted=submitted,
        current_lang=current_lang,
    ), (400 if errors else 200)


@app.route("/owners/login", methods=["GET", "POST"])
def owners_login():
    current_lang = _resolve_current_language()
    form_values = {"email": ""}
    errors = {}

    if request.method == "POST":
        raw_email = str(request.form.get("email", ""))
        normalized_email = raw_email.strip().lower()
        form_values["email"] = raw_email.strip()
        if not form_values["email"]:
            errors["email"] = "emailRequiredError"
        if not errors:
            owner_account = _find_owner_account_by_email(raw_email)
            if not owner_account:
                _append_owner_magic_login_audit(form_values["email"], False, "generic", "unknown_email", "login", current_lang)
                _append_owner_magic_email_event("unknown_email", form_values["email"], "unknown_email", "login", current_lang)
                return redirect(url_for("owners_login", magic_sent="1", delivery="generic", lang=current_lang))
            else:
                magic_token = _create_owner_magic_token(owner_account["email"])
                _append_owner_magic_email_event("token_created", owner_account["email"], "token_created", "login", current_lang)
                login_url = f"{SITE_URL}{url_for('owner_magic_login', token=magic_token['token'], lang=current_lang)}"
                email_language = _owner_magic_link_email_locale(current_lang)
                send_result = _send_owner_magic_link_and_log(owner_account["email"], login_url, email_language, "login")
                if not send_result.get("ok"):
                    _append_owner_magic_login_audit(owner_account["email"], True, "failed", send_result.get("reason", "smtp_send_failed"), "login", current_lang)
                    _consume_owner_magic_token(magic_token["token"])
                    return redirect(url_for("owners_login", magic_sent="0", delivery="failed", lang=current_lang))
                return redirect(url_for("owners_login", magic_sent="1", delivery="sent", magic_recipient=_mask_email(owner_account["email"]), lang=current_lang))

    return render_template("owners_login.html", form_values=form_values, errors=errors, current_lang=current_lang), (400 if errors else 200)


@app.get("/auth/owner-magic/<token>")
def owner_magic_login(token):
    current_lang = _resolve_current_language()
    token_record = _find_owner_magic_token(token)
    if not token_record:
        return redirect(url_for("owners_login", invalid_token="1", lang=current_lang))

    owner_account = _find_owner_account_by_email(token_record.get("email", ""))
    if not owner_account:
        _consume_owner_magic_token(token)
        return redirect(url_for("owners_login", invalid_token="1", lang=current_lang))

    created_at = _parse_iso_datetime(token_record.get("created_at", ""))
    if not created_at:
        _consume_owner_magic_token(token)
        return redirect(url_for("owners_login", invalid_token="1", lang=current_lang))

    expires_at = created_at + timedelta(minutes=OWNER_MAGIC_LINK_TTL_MINUTES)
    if datetime.now(timezone.utc) >= expires_at:
        _consume_owner_magic_token(token)
        return redirect(url_for("owners_login", expired_token="1", lang=current_lang))

    session[OWNER_SESSION_LOGGED_IN_KEY] = True
    session[OWNER_SESSION_ID_KEY] = owner_account.get("id", "")
    session[OWNER_SESSION_EMAIL_KEY] = owner_account.get("email", "")
    session[OWNER_SESSION_NAME_KEY] = owner_account.get("full_name", "")
    _upsert_owner_account({
        **owner_account,
        "language": current_lang,
        "last_login_at": _utc_now_iso(),
    })
    _append_owner_activity_event(
        owner_account["id"],
        "magic_link_login",
        "Magic link login",
        _owner_login_event_detail("magic link", current_lang),
    )
    _consume_owner_magic_token(token)
    return redirect(url_for("owners_dashboard", lang=current_lang))


@app.route("/owners/property/new", methods=["GET", "POST"])
@owner_required
def owners_property_new():
    current_lang = _resolve_current_language()
    owner_account = _current_owner_account()
    form_values = {
        "name": "",
        "property_type": "",
        "location": "",
        "bedrooms": "",
        "bathrooms": "",
        "guest_capacity": "",
        "operating_mode": "year-round",
        "notes": "",
    }
    errors = {}

    if request.method == "POST":
        form_values.update({
            "name": str(request.form.get("name", "")).strip(),
            "property_type": str(request.form.get("property_type", "")).strip(),
            "location": str(request.form.get("location", "")).strip(),
            "bedrooms": str(request.form.get("bedrooms", "")).strip(),
            "bathrooms": str(request.form.get("bathrooms", "")).strip(),
            "guest_capacity": str(request.form.get("guest_capacity", "")).strip(),
            "operating_mode": str(request.form.get("operating_mode", "year-round")).strip().lower(),
            "notes": str(request.form.get("notes", "")).strip(),
        })

        required_fields = {
            "name": "ownerPropertyNameRequiredError",
            "property_type": "ownerPropertyTypeRequiredError",
            "location": "ownerPropertyLocationRequiredError",
            "bedrooms": "ownerPropertyBedroomsRequiredError",
            "bathrooms": "ownerPropertyBathroomsRequiredError",
            "guest_capacity": "ownerPropertyGuestCapacityRequiredError",
            "operating_mode": "ownerPropertyModeRequiredError",
        }
        for field, error_key in required_fields.items():
            if not form_values[field]:
                errors[field] = error_key

        numeric_fields = {
            "bedrooms": "ownerPropertyBedroomsInvalidError",
            "bathrooms": "ownerPropertyBathroomsInvalidError",
            "guest_capacity": "ownerPropertyGuestCapacityInvalidError",
        }
        for field, error_key in numeric_fields.items():
            value = form_values[field]
            if value and not value.isdigit():
                errors[field] = error_key

        if form_values["operating_mode"] not in {"seasonal", "year-round"}:
            errors["operating_mode"] = "ownerPropertyModeInvalidError"

        if not errors:
            saved_property = _append_owner_property({
                "id": "",
                "owner_id": owner_account.get("id", ""),
                "created_at": _utc_now_iso(),
                "name": form_values["name"],
                "property_type": form_values["property_type"],
                "location": form_values["location"],
                "bedrooms": int(form_values["bedrooms"]),
                "bathrooms": int(form_values["bathrooms"]),
                "guest_capacity": int(form_values["guest_capacity"]),
                "operating_mode": form_values["operating_mode"],
                "notes": form_values["notes"],
            })
            if saved_property:
                app.logger.info("Owner property created for %s: %s", owner_account.get("email", ""), saved_property["name"])
                _append_owner_activity_event(
                    owner_account["id"],
                    "property_added",
                    "Property added",
                    f"{saved_property.get('name', '')} · {saved_property.get('location', '')}",
                )
            return redirect(url_for("owners_dashboard", property_added="1", lang=current_lang))

    return render_template(
        "owners_property_new.html",
        owner_account=owner_account,
        form_values=form_values,
        errors=errors,
        current_lang=current_lang,
        property_page_copy=_owner_property_new_copy(current_lang),
    ), (400 if errors else 200)


@app.route("/owners/dashboard")
@owner_required
def owners_dashboard():
    current_lang = _resolve_current_language()
    owner_account = _current_owner_account()
    owner_requests = []
    for record in _load_service_requests():
        if str(record.get("request_source", "public")).lower() != "owner":
            continue
        if str(record.get("owner_email", "")).strip().lower() != str(owner_account.get("email", "")).strip().lower():
            continue

        timeline = _service_request_timeline_events(record)
        last_update_at = str(record.get("last_update_at", "")).strip()
        if timeline:
            last_update_at = timeline[-1].get("created_at", last_update_at)

        owner_requests.append({
            **record,
            "last_update_at": last_update_at or record.get("created_at", ""),
            "assigned_professional": record.get("assigned_provider_company", "") or record.get("assigned_provider_name", ""),
            "service_category_key": OWNER_SERVICE_CATEGORY_TRANSLATION_KEYS.get(
                str(record.get("service_category", "")).strip(),
                OWNER_SERVICE_CATEGORY_TRANSLATION_KEYS["Other"],
            ),
            "timeline": list(reversed(timeline)),
        })

    owner_requests.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    owner_portal = _owner_portal_dashboard_context(owner_account, owner_requests, current_lang)
    return render_template(
        "owners_dashboard.html",
        owner_account=owner_account,
        owner_requests=owner_requests,
        owner_portal=owner_portal,
        current_lang=current_lang,
    )


@app.route("/owners/request-service", methods=["GET", "POST"])
@owner_required
def owners_request_service():
    current_lang = _resolve_current_language()
    owner_account = _current_owner_account()
    form_values = {
        "category": _normalize_owner_service_category(request.args.get("category", "")),
        "preferred_date": "",
        "property": owner_account.get("property_name", "") or owner_account.get("property_type", ""),
        "description": "",
        "urgency": "Standard",
        "contact_preference": "Email",
    }
    errors = {}
    submitted = False

    if request.method == "POST":
        form_values.update({
            "category": _normalize_owner_service_category(request.form.get("category", "")),
            "preferred_date": str(request.form.get("preferred_date", "")).strip(),
            "property": str(request.form.get("property", "")).strip(),
            "description": str(request.form.get("notes", request.form.get("description", ""))).strip(),
            "urgency": str(request.form.get("urgency", "")).strip() or "Standard",
            "contact_preference": str(request.form.get("contact_preference", "")).strip() or "Email",
        })

        required_fields = {
            "category": "categoryRequiredError",
            "preferred_date": "preferredDateRequiredError",
            "property": "propertyRequiredError",
            "description": "descriptionRequiredError",
            "contact_preference": "contactPreferenceRequiredError",
        }

        for field, error_key in required_fields.items():
            if not form_values[field]:
                errors[field] = error_key

        if form_values["category"] and form_values["category"] not in OWNER_SERVICE_CATEGORIES:
            errors["category"] = "categoryInvalidError"

        if not errors:
            request_record = {
                "id": uuid4().hex,
                "created_at": _utc_now_iso(),
                "last_update_at": _utc_now_iso(),
                "status": "new",
                "request_source": "owner",
                "owner_id": owner_account.get("id", ""),
                "owner_email": owner_account.get("email", ""),
                "owner_name": owner_account.get("full_name", ""),
                "owner_phone": owner_account.get("phone", ""),
                "name": owner_account.get("full_name", ""),
                "email": owner_account.get("email", ""),
                "phone": owner_account.get("phone", ""),
                "property": form_values["property"],
                "property_city": owner_account.get("city", ""),
                "property_type": owner_account.get("property_type", ""),
                "number_of_units": owner_account.get("number_of_units", ""),
                "service_category": form_values["category"],
                "preferred_date": form_values["preferred_date"],
                "description": form_values["description"],
                "notes": form_values["description"],
                "urgency": form_values["urgency"],
                "contact_preference": form_values["contact_preference"],
                "assigned_provider_id": "",
                "assigned_provider_name": "",
                "assigned_provider_company": "",
                "assigned_professional_id": "",
                "assigned_professional_name": "",
                "assigned_professional_company": "",
                "internal_notes": "",
                "timeline": [],
            }
            _append_service_request_timeline_event(
                request_record,
                "SERVICE_REQUEST_CREATED",
                "Request created",
                f"{request_record.get('service_category', '')} · {request_record.get('property', '')}",
                status="new",
            )

            SERVICE_REQUESTS_JSONL_PATH.parent.mkdir(exist_ok=True)
            with SERVICE_REQUESTS_JSONL_PATH.open("a", encoding="utf-8") as f:
                f.write(json.dumps(request_record, ensure_ascii=False) + "\n")

            _append_owner_activity_event(
                owner_account["id"],
                "service_request_submitted",
                "Service request submitted",
                f"{request_record.get('service_category', '')} · {request_record.get('property', '')}",
            )

            admin_detail_url = url_for("admin_service_request_detail", request_id=request_record["id"], _external=True)
            _queue_service_request_email(
                request_record,
                owner_account.get("email", ""),
                "owner",
                admin_detail_url,
                "created",
                "[BlackSeaConnect] Service request received",
            )
            _queue_service_request_email(
                request_record,
                os.getenv("SERVICE_REQUEST_ADMIN_EMAIL", "").strip() or "concierge@blackseaconnect.com",
                "admin",
                admin_detail_url,
                "created",
                "[BlackSeaConnect] New owner service request",
            )
            submitted = True
            return redirect(url_for("owners_dashboard", lang=current_lang))

    return render_template(
        "owners_request_service.html",
        owner_account=owner_account,
        form_values=form_values,
        errors=errors,
        submitted=submitted,
        service_categories=_owner_service_category_items(),
        current_lang=current_lang,
    ), (400 if errors else 200)


@app.route("/owners/logout")
def owners_logout():
    current_lang = _resolve_current_language()
    session.pop(OWNER_SESSION_LOGGED_IN_KEY, None)
    session.pop(OWNER_SESSION_ID_KEY, None)
    session.pop(OWNER_SESSION_EMAIL_KEY, None)
    session.pop(OWNER_SESSION_NAME_KEY, None)
    return redirect(url_for("owners_login", lang=current_lang))


@app.route("/partners")
def partners():
    return render_template(
        "partners.html",
        service_categories=_partner_service_category_items(),
        partners=_load_public_partner_applications(),
    )


@app.route("/partners/apply", methods=["GET", "POST"])
def partners_apply():
    form_values = {
        "company_name": "",
        "contact_person": "",
        "email": "",
        "phone": "",
        "website": "",
        "city": "",
        "country": "",
        "service_category": "",
        "description": "",
        "years_in_business": "",
    }
    errors = {}
    submitted = False

    if request.method == "POST":
        form_values.update({
            "company_name": str(request.form.get("company_name", "")).strip(),
            "contact_person": str(request.form.get("contact_person", "")).strip(),
            "email": str(request.form.get("email", "")).strip(),
            "phone": str(request.form.get("phone", "")).strip(),
            "website": str(request.form.get("website", "")).strip(),
            "city": str(request.form.get("city", "")).strip(),
            "country": str(request.form.get("country", "")).strip(),
            "service_category": str(request.form.get("service_category", "")).strip(),
            "description": str(request.form.get("description", "")).strip(),
            "years_in_business": str(request.form.get("years_in_business", "")).strip(),
        })

        required_field_error_keys = {
            "company_name": "companyNameRequiredError",
            "contact_person": "contactPersonRequiredError",
            "email": "emailRequiredError",
            "phone": "phoneRequiredError",
            "city": "cityRequiredError",
            "country": "countryRequiredError",
            "service_category": "serviceCategoryRequiredError",
            "description": "descriptionRequiredError",
            "years_in_business": "yearsInBusinessRequiredError",
        }

        for field, error_key in required_field_error_keys.items():
            if not form_values[field]:
                errors[field] = error_key

        if form_values["service_category"] and form_values["service_category"] not in PARTNER_SERVICE_CATEGORIES:
            errors["service_category"] = "serviceCategoryInvalidError"

        if form_values["years_in_business"] and not form_values["years_in_business"].isdigit():
            errors["years_in_business"] = "yearsInBusinessInvalidError"

        if not errors:
            years_in_business = int(form_values["years_in_business"])
            record = {
                "id": uuid4().hex,
                "created_at": _utc_now_iso(),
                "status": "new",
                "company_name": form_values["company_name"],
                "contact_person": form_values["contact_person"],
                "email": form_values["email"],
                "phone": form_values["phone"],
                "website": form_values["website"],
                "city": form_values["city"],
                "country": form_values["country"],
                "service_category": form_values["service_category"],
                "description": form_values["description"],
                "years_in_business": years_in_business,
                "owner": "",
                "notes": "",
                "internal_notes": "",
                "timeline": [],
            }
            _append_partner_timeline_event(
                record,
                "PARTNER_APPLICATION_CREATED",
                f"Partner application created: {record.get('company_name') or record.get('contact_person') or 'Unnamed application'}",
                f"{record.get('service_category', '')} · {record.get('city', '')}",
                status="new",
            )

            data_dir = Path("data")
            data_dir.mkdir(exist_ok=True)

            try:
                with (data_dir / "partner_applications.jsonl").open("a", encoding="utf-8") as f:
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
            except OSError:
                app.logger.exception("Partner application save failed.")
                return render_template(
                    "partners_apply.html",
                    service_categories=_partner_service_category_items(),
                    form_values=form_values,
                    errors={},
                    submitted=False,
                    save_error=True,
                ), 500

            admin_detail_url = url_for("admin_partner_application_detail", application_id=record["id"], _external=True)
            _queue_partner_application_notification_email(record, admin_detail_url)
            submitted = True
            return render_template(
                "partners_apply.html",
                service_categories=_partner_service_category_items(),
                submitted=True,
                application_id=record["id"],
                form_values=form_values,
                errors={},
                save_error=False,
            )

        return render_template(
            "partners_apply.html",
            service_categories=_partner_service_category_items(),
            form_values=form_values,
            errors=errors,
            submitted=False,
            save_error=False,
        ), 400

    return render_template(
        "partners_apply.html",
        service_categories=_partner_service_category_items(),
        submitted=False,
        form_values=form_values,
        errors=errors,
        save_error=False,
    )


@app.route("/request-service", methods=["GET", "POST"])
def request_service():
    form_values = {
        "name": "",
        "email": "",
        "phone": "",
        "property_city": "",
        "property_type": "",
        "service_category": str(request.args.get("service_category", "")).strip(),
        "preferred_date": "",
        "description": "",
    }
    errors = {}
    request_record = None
    submitted = False

    if request.method == "POST":
        form_values.update({
            "name": str(request.form.get("name", "")).strip(),
            "email": str(request.form.get("email", "")).strip(),
            "phone": str(request.form.get("phone", "")).strip(),
            "property_city": str(request.form.get("property_city", "")).strip(),
            "property_type": str(request.form.get("property_type", "")).strip(),
            "service_category": str(request.form.get("service_category", "")).strip(),
            "preferred_date": str(request.form.get("preferred_date", "")).strip(),
            "description": str(request.form.get("description", "")).strip(),
        })

        required_fields = {
            "name": "nameRequiredError",
            "email": "emailRequiredError",
            "phone": "phoneRequiredError",
            "property_city": "propertyCityRequiredError",
            "property_type": "propertyTypeRequiredError",
            "service_category": "serviceCategoryRequiredError",
            "preferred_date": "preferredDateRequiredError",
            "description": "descriptionRequiredError",
        }

        for field, error_key in required_fields.items():
            if not form_values[field]:
                errors[field] = error_key

        if form_values["service_category"] and form_values["service_category"] not in NETWORK_SERVICE_CATEGORIES:
            errors["service_category"] = "serviceCategoryInvalidError"

        if not errors:
            request_record = {
                "id": uuid4().hex,
                "created_at": _utc_now_iso(),
                "last_update_at": _utc_now_iso(),
                "status": "new",
                "request_source": "public",
                "name": form_values["name"],
                "email": form_values["email"],
                "phone": form_values["phone"],
                "property_city": form_values["property_city"],
                "property_type": form_values["property_type"],
                "service_category": form_values["service_category"],
                "preferred_date": form_values["preferred_date"],
                "description": form_values["description"],
                "assigned_provider_id": "",
                "assigned_provider_name": "",
                "assigned_provider_company": "",
                "assigned_professional_id": "",
                "assigned_professional_name": "",
                "assigned_professional_company": "",
                "internal_notes": "",
                "timeline": [],
            }
            _append_service_request_timeline_event(
                request_record,
                "SERVICE_REQUEST_CREATED",
                f"Service request created: {request_record.get('name') or request_record.get('property_city') or 'Unnamed request'}",
                f"{request_record.get('service_category', '')} · {request_record.get('property_city', '')}",
                status="new",
            )

            SERVICE_REQUESTS_JSONL_PATH.parent.mkdir(exist_ok=True)
            try:
                with SERVICE_REQUESTS_JSONL_PATH.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(request_record, ensure_ascii=False) + "\n")
            except Exception:
                return render_template(
                    "request_service.html",
                    form_values=form_values,
                    errors={"general": "saveError"},
                    service_categories=_network_service_category_items(),
                    matching_providers=_service_request_matching_providers(form_values["service_category"]),
                    submitted=False,
                    request_record=None,
                ), 500

            submitted = True
            app.logger.info("Saved service request: %s", request_record["id"])
            admin_detail_url = url_for("admin_service_request_detail", request_id=request_record["id"], _external=True)
            _queue_service_request_notification(request_record, admin_detail_url)

    matching_providers = _service_request_matching_providers(form_values["service_category"])
    return render_template(
        "request_service.html",
        form_values=form_values,
        errors=errors,
        service_categories=_network_service_category_items(),
        matching_providers=matching_providers,
        submitted=submitted,
        request_record=request_record,
    ), (400 if errors else 200)


@app.route("/network")
def network_directory():
    city = str(request.args.get("city", "")).strip()
    category = str(request.args.get("category", "")).strip()
    valid_category = category if category in NETWORK_SERVICE_CATEGORIES else ""
    providers = _filter_network_providers(_load_network_providers(), city=city, category=valid_category)
    featured_providers = [provider for provider in providers if provider.get("featured")]
    grouped_providers = _group_network_providers(providers)
    return render_template(
        "network.html",
        providers=providers,
        featured_providers=featured_providers,
        grouped_providers=grouped_providers,
        service_categories=_network_service_category_items(),
        city_query=city,
        category_filter=valid_category,
        total_providers=len(providers),
    )


@app.route("/network/<provider_id>")
def network_provider_detail(provider_id):
    provider = _find_network_provider(provider_id)
    if not provider:
        return jsonify({"ok": False, "error": "not_found"}), 404

    return render_template(
        "network_detail.html",
        provider=provider,
        service_categories=_network_service_category_items(),
    )


@app.route("/professionals/apply", methods=["GET", "POST"])
def professionals_apply():
    form_values = {
        "full_name": "",
        "email": "",
        "phone": "",
        "city": "",
        "country": "",
        "professional_category": "",
        "languages": "",
        "experience": "",
        "short_bio": "",
    }
    errors = {}
    submitted = False

    if request.method == "POST":
        form_values.update({
            "full_name": str(request.form.get("full_name", "")).strip(),
            "email": str(request.form.get("email", "")).strip(),
            "phone": str(request.form.get("phone", "")).strip(),
            "city": str(request.form.get("city", "")).strip(),
            "country": str(request.form.get("country", "")).strip(),
            "professional_category": str(request.form.get("professional_category", "")).strip(),
            "languages": str(request.form.get("languages", "")).strip(),
            "experience": str(request.form.get("experience", "")).strip(),
            "short_bio": str(request.form.get("short_bio", "")).strip(),
        })

        required_field_error_keys = {
            "full_name": "fullNameRequiredError",
            "email": "emailRequiredError",
            "phone": "phoneRequiredError",
            "city": "cityRequiredError",
            "country": "countryRequiredError",
            "professional_category": "categoryRequiredError",
            "languages": "languagesRequiredError",
            "experience": "experienceRequiredError",
            "short_bio": "shortBioRequiredError",
        }

        for field, error_key in required_field_error_keys.items():
            if not form_values[field]:
                errors[field] = error_key

        if form_values["professional_category"] and form_values["professional_category"] not in PROFESSIONAL_SERVICE_CATEGORIES:
            errors["professional_category"] = "categoryInvalidError"

        if not errors:
            experience_value = form_values["experience"]

            record = {
                "id": uuid4().hex,
                "created_at": _utc_now_iso(),
                "status": "new",
                "full_name": form_values["full_name"],
                "email": form_values["email"],
                "phone": form_values["phone"],
                "city": form_values["city"],
                "country": form_values["country"],
                "professional_category": form_values["professional_category"],
                "service_type": form_values["professional_category"],
                "languages": form_values["languages"],
                "experience": experience_value,
                "experience_years": experience_value,
                "short_bio": form_values["short_bio"],
                "description": form_values["short_bio"],
                "website": "",
                "website_or_social": "",
                "internal_notes": "",
                "notes": "",
                "owner": "",
                "timeline": [],
            }
            _append_professional_timeline_event(
                record,
                "PROFESSIONAL_APPLICATION_CREATED",
                f"Professional application created: {record.get('full_name') or record.get('company_name') or 'Unnamed application'}",
                f"{record.get('professional_category', '')} · {record.get('city', '')}",
                status="new",
            )

            data_dir = Path("data")
            data_dir.mkdir(exist_ok=True)

            try:
                with (data_dir / "professional_applications.jsonl").open("a", encoding="utf-8") as f:
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
            except OSError:
                app.logger.exception("Professional application save failed.")
                return render_template(
                    "professionals_apply.html",
                    service_categories=_professional_service_category_items(),
                    form_values=form_values,
                    errors={},
                    submitted=False,
                    save_error=True,
                ), 500

            admin_detail_url = url_for("admin_professional_detail", application_id=record["id"], _external=True)
            _queue_professional_application_notification_email(record, admin_detail_url)
            submitted = True

            return render_template(
                "professionals_apply.html",
                service_categories=_professional_service_category_items(),
                submitted=True,
                application_id=record["id"],
                form_values=form_values,
                errors={},
                save_error=False,
            )

        return render_template(
            "professionals_apply.html",
            service_categories=_professional_service_category_items(),
            form_values=form_values,
            errors=errors,
            submitted=False,
            save_error=False,
        ), 400

    return render_template(
        "professionals_apply.html",
        service_categories=_professional_service_category_items(),
        submitted=False,
        form_values=form_values,
        errors=errors,
        save_error=False,
    )


@app.route("/health")
def health():
    return jsonify({"ok": True, "service": "blackseaconnect"})


def _admin_auth_response(status_code, message):
    response = Response(message, status=status_code, mimetype="text/plain")
    if status_code == 401:
        response.headers["WWW-Authenticate"] = 'Basic realm="BlackSea Connect Admin"'
    return response


def _admin_owner_accounts_query_value(value):
    return str(value or "").strip().lower()


def _admin_owner_account_properties(owner_id):
    target_owner_id = str(owner_id or "").strip()
    if not target_owner_id:
        return []
    return [
        property_record
        for property_record in _load_owner_properties()
        if str(property_record.get("owner_id", "")).strip() == target_owner_id
    ]


def _admin_owner_account_service_requests(owner_account):
    owner_email = str((owner_account or {}).get("email", "")).strip().lower()
    owner_id = str((owner_account or {}).get("id", "")).strip()
    if not owner_email and not owner_id:
        return []

    requests = []
    for record in _load_service_requests():
        if str(record.get("request_source", "public")).lower() != "owner":
            continue
        record_owner_email = str(record.get("owner_email", "")).strip().lower()
        record_owner_id = str(record.get("owner_id", "")).strip()
        if owner_email and record_owner_email == owner_email:
            requests.append(record)
            continue
        if owner_id and record_owner_id == owner_id:
            requests.append(record)
    return requests


def _admin_owner_account_timeline(owner_account, properties, service_requests, activity_events, magic_events):
    timeline = []
    owner_id = str(owner_account.get("id", "")).strip()
    owner_email = str(owner_account.get("email", "")).strip().lower()

    if owner_account.get("created_at"):
        timeline.append({
            "created_at": str(owner_account.get("created_at", "")),
            "type": "owner_registered",
            "title": "Owner registered",
            "detail": owner_account.get("full_name", ""),
        })

    for event in magic_events:
        event_name = str(event.get("event", "")).strip().lower()
        if event_name == "sent":
            timeline.append({
                "created_at": str(event.get("timestamp", event.get("created_at", ""))),
                "type": "magic_link_sent",
                "title": "Magic link sent",
                "detail": f"Source: {event.get('source', '')}",
            })
        elif event_name == "owner_registration_notification_failed":
            timeline.append({
                "created_at": str(event.get("timestamp", event.get("created_at", ""))),
                "type": "magic_link_send_failed",
                "title": "Magic link delivery failed",
                "detail": str(event.get("reason", "")),
            })

    for event in activity_events:
        event_type = str(event.get("event_type", "")).strip()
        detail = str(event.get("detail", "")).strip()
        if event_type == "magic_link_login":
            timeline.append({
                "created_at": str(event.get("created_at", "")),
                "type": event_type,
                "title": "Magic link login",
                "detail": detail,
            })
        elif event_type == "property_added":
            timeline.append({
                "created_at": str(event.get("created_at", "")),
                "type": event_type,
                "title": "Property added",
                "detail": detail,
            })
        elif event_type == "service_request_submitted":
            timeline.append({
                "created_at": str(event.get("created_at", "")),
                "type": event_type,
                "title": "Service request submitted",
                "detail": detail,
            })
        elif event_type == "note_added":
            timeline.append({
                "created_at": str(event.get("created_at", "")),
                "type": event_type,
                "title": "Note added",
                "detail": detail,
            })
        elif event_type == "status_changed":
            timeline.append({
                "created_at": str(event.get("created_at", "")),
                "type": event_type,
                "title": "Status changed",
                "detail": detail,
            })

    for property_record in properties:
        timeline.append({
            "created_at": str(property_record.get("created_at", "")),
            "type": "property_added",
            "title": "Property added",
            "detail": f"{property_record.get('name', '')} · {property_record.get('location', '')}",
        })

    for request_record in service_requests:
        timeline.append({
            "created_at": str(request_record.get("created_at", "")),
            "type": "service_request_submitted",
            "title": "Service request submitted",
            "detail": f"{request_record.get('service_category', '')} · {request_record.get('property', '')}",
        })

    deduped_timeline = []
    seen = set()
    for item in timeline:
        signature = (
            str(item.get("created_at", "")),
            str(item.get("type", "")),
            str(item.get("title", "")),
            str(item.get("detail", "")),
        )
        if signature in seen:
            continue
        seen.add(signature)
        deduped_timeline.append(item)

    deduped_timeline.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
    return deduped_timeline


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        admin_username = os.getenv("ADMIN_USERNAME", "").strip()
        admin_password = os.getenv("ADMIN_PASSWORD", "").strip()

        if not admin_username or not admin_password:
            app.logger.warning("Admin access disabled: ADMIN_USERNAME or ADMIN_PASSWORD is missing.")
            return _admin_auth_response(503, "Admin access is not configured.")

        auth = request.authorization
        if not auth or not auth.username or not auth.password:
            return _admin_auth_response(401, "Unauthorized")

        username_ok = hmac.compare_digest(str(auth.username), admin_username)
        password_ok = hmac.compare_digest(str(auth.password), admin_password)
        if not (username_ok and password_ok):
            return _admin_auth_response(401, "Unauthorized")

        return view(*args, **kwargs)

    return wrapped


@app.get("/admin/owner-magic-events")
@admin_required
def admin_owner_magic_events():
    events = _load_owner_magic_email_events()[:100]
    return render_template("admin_owner_magic_events.html", events=events)


@app.get("/admin/owner-accounts")
@admin_required
def admin_owner_accounts():
    owner_accounts = _load_owner_accounts()
    total_owner_accounts = len(owner_accounts)
    search_query = request.args.get("q", "").strip()
    requested_status = str(request.args.get("status", "")).strip().upper()
    status_filter = requested_status if requested_status in OWNER_STATUS_VALUES else ""
    requested_language = str(request.args.get("language", "")).strip().lower()
    language_filter = requested_language if requested_language in SUPPORTED_LANGUAGES else ""

    filtered_owner_accounts = []
    search_tokens = [token for token in search_query.lower().split() if token]
    for owner_account in owner_accounts:
        owner_properties = _admin_owner_account_properties(owner_account.get("id", ""))
        searchable_parts = [
            owner_account.get("full_name", ""),
            owner_account.get("email", ""),
            owner_account.get("city", ""),
            owner_account.get("property_name", ""),
            owner_account.get("property_type", ""),
        ]
        searchable_parts.extend(property_record.get("location", "") for property_record in owner_properties)
        searchable_text = " ".join(searchable_parts).lower()
        if search_tokens and not all(token in searchable_text for token in search_tokens):
            continue
        if status_filter and _normalize_owner_status(owner_account.get("status", "")) != status_filter:
            continue
        if language_filter and _normalize_owner_language(owner_account.get("language", "")) != language_filter:
            continue
        filtered_owner_accounts.append({
            **owner_account,
            "property_count": len(owner_properties),
        })

    return render_template(
        "admin_owner_accounts.html",
        owner_accounts=filtered_owner_accounts,
        owner_accounts_count=len(filtered_owner_accounts),
        owner_accounts_total_count=total_owner_accounts,
        owner_accounts_path=str(_owner_db_path().resolve()),
        search_query=search_query,
        status_filter=status_filter,
        language_filter=language_filter,
        owner_status_options=sorted(OWNER_STATUS_VALUES),
        owner_language_options=sorted(SUPPORTED_LANGUAGES),
    )


@app.route("/admin/owner-accounts/<owner_id>", methods=["GET", "POST"])
@admin_required
def admin_owner_account_detail(owner_id):
    owner_account = _find_owner_account(owner_id)
    if not owner_account:
        return Response("Owner account not found.", status=404, mimetype="text/plain")

    properties = _admin_owner_account_properties(owner_account.get("id", ""))
    service_requests = _admin_owner_account_service_requests(owner_account)
    activity_events = _load_owner_activity_events(owner_account.get("id", ""))
    magic_events = [
        event
        for event in _load_owner_magic_email_events()
        if str(event.get("submitted_email", "")).strip().lower() == str(owner_account.get("email", "")).strip().lower()
    ]

    if request.method == "POST":
        new_status = _normalize_owner_status(request.form.get("status", owner_account.get("status", OWNER_STATUS_DEFAULT)))
        new_notes = str(request.form.get("internal_notes", "")).strip()
        previous_status = _normalize_owner_status(owner_account.get("status", OWNER_STATUS_DEFAULT))
        previous_notes = str(owner_account.get("internal_notes", "")).strip()

        if new_status != previous_status or new_notes != previous_notes:
            updated_account = {
                **owner_account,
                "status": new_status,
                "internal_notes": new_notes,
            }
            saved_account = _upsert_owner_account(updated_account)
            if saved_account:
                if new_status != previous_status:
                    _append_owner_activity_event(
                        saved_account["id"],
                        "status_changed",
                        "Status changed",
                        f"{previous_status} -> {new_status}",
                    )
                if new_notes != previous_notes and new_notes:
                    _append_owner_activity_event(
                        saved_account["id"],
                        "note_added",
                        "Note added",
                        new_notes,
                    )
        return redirect(url_for("admin_owner_account_detail", owner_id=owner_id))

    owner_account = _find_owner_account(owner_id) or owner_account
    property_count = len(properties)
    owner_service_request_count = len(service_requests)
    owner_login_events = [
        event for event in activity_events if str(event.get("event_type", "")).strip() == "magic_link_login"
    ]
    owner_registration_events = [
        event for event in activity_events if str(event.get("event_type", "")).strip() == "owner_registered"
    ]
    owner_property_events = [
        event for event in activity_events if str(event.get("event_type", "")).strip() == "property_added"
    ]
    owner_service_request_events = [
        event for event in activity_events if str(event.get("event_type", "")).strip() == "service_request_submitted"
    ]
    owner_note_events = [
        event for event in activity_events if str(event.get("event_type", "")).strip() == "note_added"
    ]
    owner_status_events = [
        event for event in activity_events if str(event.get("event_type", "")).strip() == "status_changed"
    ]
    timeline = _admin_owner_account_timeline(owner_account, properties, service_requests, activity_events, magic_events)

    activity_counts = {
        "registrations": len(owner_registration_events) or 1,
        "magic_link_logins": len(owner_login_events),
        "property_creations": len(owner_property_events) or property_count,
        "service_requests": len(owner_service_request_events) or owner_service_request_count,
    }

    return render_template(
        "admin_owner_account_detail.html",
        owner_account=owner_account,
        properties=properties,
        property_count=property_count,
        service_requests=service_requests,
        activity_counts=activity_counts,
        timeline=timeline,
        owner_status_options=sorted(OWNER_STATUS_VALUES),
        owner_note_events=owner_note_events,
        owner_status_events=owner_status_events,
        owner_registration_events=owner_registration_events,
        owner_login_events=owner_login_events,
    )


@app.post("/admin/seed-owner")
@admin_required
def admin_seed_owner():
    seed_record = {
        "id": "",
        "created_at": _utc_now_iso(),
        "full_name": "Stella",
        "email": "stoyanova@orange.fr",
        "phone": "+35987927767",
        "property_type": "Apartment",
        "city": "Sveti Vlas",
        "property_name": "Stella Appart",
        "number_of_units": 1,
        "notes": "Seeded from admin probe.",
        "language": "bg",
        "status": OWNER_STATUS_DEFAULT,
    }
    owner_account, created = _seed_owner_account_if_missing(seed_record)
    if not owner_account:
        app.logger.warning("Admin owner seed failed for %s", _mask_email(seed_record["email"]))
        return _admin_auth_response(500, "Failed to seed owner account.")

    if created:
        _append_owner_activity_event(
            owner_account["id"],
            "owner_registered",
            "Owner registered",
            owner_account.get("full_name", ""),
        )

    app.logger.info("Admin owner seed completed for %s (created=%s)", _mask_email(seed_record["email"]), created)
    return redirect(url_for("admin_owner_accounts", seeded="1"))


def _clean_payload_value(payload, *keys):
    for key in keys:
        value = payload.get(key, "")
        text = str(value).strip()
        if text:
            return text
    return ""


def _utc_now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _normalize_pilot_status(status):
    normalized = str(status or "").strip().lower()
    normalized = PILOT_STATUS_ALIASES.get(normalized, normalized)
    return normalized if normalized in PILOT_STATUS_VALUES else "new"


def _normalize_pilot_timeline(timeline):
    if not isinstance(timeline, list):
        return []

    normalized_timeline = []
    for entry in timeline:
        if not isinstance(entry, dict):
            continue

        normalized_entry = dict(entry)
        normalized_entry["type"] = str(normalized_entry.get("type", "")).strip() or "lead_created"
        normalized_entry["created_at"] = str(normalized_entry.get("created_at", "")).strip()
        normalized_entry["title"] = str(normalized_entry.get("title", "")).strip()
        normalized_entry["detail"] = str(normalized_entry.get("detail", "")).strip()
        if "status" in normalized_entry:
            normalized_entry["status"] = _normalize_pilot_status(normalized_entry.get("status"))
        else:
            normalized_entry["status"] = ""
        normalized_timeline.append(normalized_entry)

    return normalized_timeline


def _pilot_status_label(status):
    return _normalize_pilot_status(status).upper()


def _append_pilot_timeline_event(record, event_type, title, detail="", status=None):
    timeline = list(record.get("timeline") or [])
    timeline.append({
        "type": event_type,
        "created_at": _utc_now_iso(),
        "title": title,
        "detail": detail,
        "status": _normalize_pilot_status(status or record.get("status", "new")),
    })
    record["timeline"] = timeline


def _pilot_request_timeline_events(record):
    timeline = _normalize_pilot_timeline(record.get("timeline"))
    if timeline:
        return timeline

    created_at = str(record.get("created_at", "")).strip()
    if not created_at:
        return []

    return [{
        "type": "lead_created",
        "created_at": created_at,
        "title": f"Lead created: {record.get('name') or record.get('email') or 'Anonymous request'}",
        "detail": f"{record.get('property_type', '')} · {record.get('city', '')}",
        "status": _normalize_pilot_status(record.get("status", "new")),
    }]


def _build_pilot_email_body(record):
    lines = [
        f"Property type: {record['property_type']}",
        f"Apartment count: {record['apartment_count']}",
        f"City / location: {record['city']}",
        f"Concierge needs: {record['concierge_needs']}",
        f"Email: {record['email']}",
    ]

    if record.get("name"):
        lines.append(f"Name: {record['name']}")

    lines.extend([
        f"Language: {record.get('current_language') or 'n/a'}",
        f"Submitted from: {record.get('submitted_from') or 'unknown'}",
        f"Timestamp: {record['created_at']}",
    ])
    return "\n".join(lines)


def _smtp_endpoint_label(smtp_host, smtp_port):
    return f"{smtp_host}:{smtp_port}"


def _send_pilot_request_email(record):
    smtp_host = os.getenv("SMTP_HOST", "").strip()
    smtp_port_raw = os.getenv("SMTP_PORT", "").strip()
    smtp_username = os.getenv("SMTP_USERNAME", "").strip()
    smtp_password = os.getenv("SMTP_PASSWORD", "").strip()
    smtp_from = os.getenv("SMTP_FROM", "").strip()
    smtp_to = os.getenv("PILOT_REQUEST_TO", "").strip() or "concierge@blackseaconnect.com"

    if not smtp_host or not smtp_port_raw or not smtp_from:
        app.logger.warning("Pilot request email skipped: SMTP configuration is missing for %s.", _smtp_endpoint_label(smtp_host or "unknown", smtp_port_raw or "unknown"))
        return False, "smtp_not_configured"

    try:
        smtp_port = int(smtp_port_raw)
    except ValueError:
        app.logger.warning("Pilot request email skipped: SMTP_PORT is invalid for %s.", _smtp_endpoint_label(smtp_host, smtp_port_raw))
        return False, "smtp_invalid_port"

    message = EmailMessage()
    message["Subject"] = "New BlackSea Connect pilot request"
    message["From"] = smtp_from
    message["To"] = smtp_to
    message.set_content(_build_pilot_email_body(record))

    try:
        smtp_factory = smtplib.SMTP_SSL if smtp_port == 465 else smtplib.SMTP
        with smtp_factory(smtp_host, smtp_port, timeout=10) as smtp:
            smtp.ehlo()
            if smtp_port != 465:
                try:
                    smtp.starttls()
                    smtp.ehlo()
                except smtplib.SMTPException:
                    app.logger.warning("Pilot request email: SMTP STARTTLS was unavailable.")

            if smtp_username or smtp_password:
                smtp.login(smtp_username, smtp_password)

            smtp.send_message(message)
    except Exception as exc:
        app.logger.warning("Pilot request email send failed for %s: %s", _smtp_endpoint_label(smtp_host, smtp_port), exc)
        return False, "smtp_send_failed"

    return True, None


def _build_internal_pilot_notification_body(record, admin_detail_url):
    lines = [
        f"Lead ID: {record.get('id', '')}",
        f"Created At: {record.get('created_at', '')}",
        f"Property Type: {record.get('property_type', '')}",
        f"Apartment Count: {record.get('apartment_count', '')}",
        f"City: {record.get('city', '')}",
        f"Concierge Needs: {record.get('concierge_needs', '')}",
        f"Email Address: {record.get('email', '')}",
        f"Language: {record.get('current_language') or 'n/a'}",
        f"Current CRM Status: {_normalize_pilot_status(record.get('status', 'new')).upper()}",
        f"Admin Detail URL: {admin_detail_url}",
    ]
    return "\n".join(lines)


def _build_internal_pilot_notification_payload(record, admin_detail_url):
    return {
        "subject": "[BlackSea Connect] New Pilot Lead Received",
        "lead_id": record.get("id", ""),
        "created_at": record.get("created_at", ""),
        "property_type": record.get("property_type", ""),
        "apartment_count": record.get("apartment_count", ""),
        "city": record.get("city", ""),
        "concierge_needs": record.get("concierge_needs", ""),
        "email": record.get("email", ""),
        "language": record.get("current_language") or "n/a",
        "status": _normalize_pilot_status(record.get("status", "new")).upper(),
        "admin_detail_url": admin_detail_url,
    }


def _build_internal_pilot_telegram_text(record, admin_detail_url):
    lines = [
        "New Pilot Lead",
        f"lead_id: {record.get('id', '')}",
        f"created_at: {record.get('created_at', '')}",
        f"property_type: {record.get('property_type', '')}",
        f"apartment_count: {record.get('apartment_count', '')}",
        f"city: {record.get('city', '')}",
        f"concierge_needs: {record.get('concierge_needs', '')}",
        f"email: {record.get('email', '')}",
        f"language: {record.get('current_language') or 'n/a'}",
        f"status: {_normalize_pilot_status(record.get('status', 'new')).upper()}",
        f"admin_detail_url: {admin_detail_url}",
    ]
    return "\n".join(lines)


def _send_internal_pilot_notification_via_resend(record, admin_detail_url, resend_api_key, from_email, admin_email):
    message = EmailMessage()
    message["Subject"] = "[BlackSea Connect] New Pilot Lead Received"
    message["From"] = from_email
    message["To"] = admin_email
    message["Reply-To"] = from_email
    message.set_content(_build_internal_pilot_notification_body(record, admin_detail_url))

    payload = {
        "from": from_email,
        "to": [admin_email],
        "subject": message["Subject"],
        "text": message.get_content(),
    }

    request = urllib.request.Request(
        "https://api.resend.com/emails",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {resend_api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            response_status = getattr(response, "status", getattr(response, "code", None))
            if response_status not in (200, 201, 202):
                app.logger.warning("Internal pilot notification send failed via Resend: unexpected status %s.", response_status)
                return False, "resend_bad_status"
    except urllib.error.HTTPError as exc:
        response_body = ""
        try:
            response_body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            response_body = "<unreadable>"
        app.logger.warning(
            "Internal pilot notification send failed via Resend: HTTP %s %s. Body: %s",
            exc.code,
            exc.reason,
            response_body,
        )
        return False, "resend_send_failed"
    except Exception as exc:
        app.logger.warning("Internal pilot notification send failed via Resend: %s", exc)
        return False, "resend_send_failed"

    return True, None


def _send_internal_pilot_notification_via_formspree(record, admin_detail_url, formspree_endpoint):
    payload = _build_internal_pilot_notification_payload(record, admin_detail_url)
    request = urllib.request.Request(
        formspree_endpoint,
        data=urllib.parse.urlencode(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            response_status = getattr(response, "status", getattr(response, "code", None))
            if response_status not in (200, 201, 202, 204):
                app.logger.warning("Internal pilot notification send failed via Formspree: unexpected status %s.", response_status)
                return False, "formspree_bad_status"
    except urllib.error.HTTPError as exc:
        response_body = ""
        try:
            response_body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            response_body = "<unreadable>"
        app.logger.warning(
            "Internal pilot notification send failed via Formspree: HTTP %s %s. Body: %s",
            exc.code,
            exc.reason,
            response_body,
        )
        return False, "formspree_send_failed"
    except Exception as exc:
        app.logger.warning("Internal pilot notification send failed via Formspree: %s", exc)
        return False, "formspree_send_failed"

    return True, None


def _send_internal_pilot_notification_via_telegram(record, admin_detail_url, telegram_bot_token, telegram_chat_id):
    telegram_text = _build_internal_pilot_telegram_text(record, admin_detail_url)
    telegram_url = f"https://api.telegram.org/bot{telegram_bot_token}/sendMessage"
    payload = {
        "chat_id": telegram_chat_id,
        "text": telegram_text,
        "disable_web_page_preview": "true",
    }

    request = urllib.request.Request(
        telegram_url,
        data=urllib.parse.urlencode(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            response_status = getattr(response, "status", getattr(response, "code", None))
            if response_status not in (200, 201, 202):
                app.logger.warning("Internal pilot notification send failed via Telegram: unexpected status %s.", response_status)
                return False, "telegram_bad_status"
    except urllib.error.HTTPError as exc:
        response_body = ""
        try:
            response_body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            response_body = "<unreadable>"
        app.logger.warning(
            "Internal pilot notification send failed via Telegram: HTTP %s %s. Body: %s",
            exc.code,
            exc.reason,
            response_body,
        )
        return False, "telegram_send_failed"
    except Exception as exc:
        app.logger.warning("Internal pilot notification send failed via Telegram: %s", type(exc).__name__)
        return False, "telegram_send_failed"

    return True, None


def _send_internal_pilot_notification(record, admin_detail_url):
    resend_api_key = os.getenv("RESEND_API_KEY", "").strip()
    from_email = os.getenv("FROM_EMAIL", "").strip() or "BlackSea Connect <concierge@blackseaconnect.com>"
    admin_email = os.getenv("ADMIN_EMAIL", "").strip()
    formspree_endpoint = os.getenv("FORMSPREE_ADMIN_ENDPOINT", "").strip()
    telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    resend_attempted = False
    resend_ok = False
    resend_reason = "resend_not_configured"

    if resend_api_key and admin_email:
        resend_attempted = True
        resend_ok, resend_reason = _send_internal_pilot_notification_via_resend(
            record,
            admin_detail_url,
            resend_api_key,
            from_email,
            admin_email,
        )
        if resend_ok:
            return True, None
    else:
        if not resend_api_key:
            app.logger.warning("Internal pilot notification skipped via Resend: RESEND_API_KEY is missing.")
        if not admin_email:
            app.logger.warning("Internal pilot notification skipped via Resend: ADMIN_EMAIL is missing.")
        resend_reason = "resend_not_configured" if not resend_api_key else "admin_email_missing"

    if formspree_endpoint:
        formspree_ok, formspree_reason = _send_internal_pilot_notification_via_formspree(
            record,
            admin_detail_url,
            formspree_endpoint,
        )
        if formspree_ok:
            return True, None
        if telegram_bot_token and telegram_chat_id:
            telegram_ok, telegram_reason = _send_internal_pilot_notification_via_telegram(
                record,
                admin_detail_url,
                telegram_bot_token,
                telegram_chat_id,
            )
            if telegram_ok:
                return True, None
            return False, telegram_reason
        return False, formspree_reason

    if resend_attempted and not resend_ok:
        if telegram_bot_token and telegram_chat_id:
            telegram_ok, telegram_reason = _send_internal_pilot_notification_via_telegram(
                record,
                admin_detail_url,
                telegram_bot_token,
                telegram_chat_id,
            )
            if telegram_ok:
                return True, None
            return False, telegram_reason

        return False, resend_reason

    app.logger.warning("Internal pilot notification skipped: FORMSPREE_ADMIN_ENDPOINT is missing.")
    if telegram_bot_token and telegram_chat_id:
        telegram_ok, telegram_reason = _send_internal_pilot_notification_via_telegram(
            record,
            admin_detail_url,
            telegram_bot_token,
            telegram_chat_id,
        )
        if telegram_ok:
            return True, None
        return False, telegram_reason

    return False, "formspree_not_configured"


def _queue_internal_pilot_notification(record, admin_detail_url):
    Thread(target=_send_internal_pilot_notification, args=(record, admin_detail_url), daemon=True).start()


def _queue_pilot_request_email(record):
    Thread(target=_send_pilot_request_email, args=(record,), daemon=True).start()


def _fallback_pilot_request_id(record):
    parts = [
        str(record.get("created_at", "")),
        str(record.get("email", "")),
        str(record.get("property_type", "")),
        str(record.get("apartment_count", "")),
        str(record.get("city", record.get("location", ""))),
        str(record.get("concierge_needs", record.get("needs", ""))),
    ]
    digest = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()
    return f"legacy-{digest[:16]}"


def _normalize_pilot_request(record):
    if not isinstance(record, dict):
        return None

    normalized = dict(record)
    normalized["id"] = str(normalized.get("id", "")).strip() or _fallback_pilot_request_id(normalized)
    normalized["status"] = _normalize_pilot_status(normalized.get("status", "new"))
    normalized.setdefault("name", "")
    normalized.setdefault("email", "")
    normalized.setdefault("property_type", "")
    normalized.setdefault("apartment_count", "")
    normalized.setdefault("city", normalized.get("location", ""))
    normalized.setdefault("concierge_needs", normalized.get("needs", ""))
    normalized.setdefault("notes", "")
    normalized.setdefault("owner", "")
    normalized.setdefault("current_language", "")
    normalized.setdefault("submitted_from", "")
    normalized.setdefault("created_at", "")
    normalized["notes"] = str(normalized.get("notes", "")).strip()
    normalized["owner"] = str(normalized.get("owner", "")).strip()
    normalized["timeline"] = _normalize_pilot_timeline(normalized.get("timeline", []))
    normalized["location"] = normalized.get("city", "")
    normalized["needs"] = normalized.get("concierge_needs", "")
    return normalized


def _load_pilot_requests():
    path = Path("data") / "pilot_requests.jsonl"
    requests_list = []

    if not path.exists():
        return requests_list

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            normalized = _normalize_pilot_request(record)
            if normalized:
                requests_list.append(normalized)

    requests_list.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return requests_list


def _load_concierge_requests():
    path = Path("data") / "concierge_requests.jsonl"
    requests_list = []

    if not path.exists():
        return requests_list

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            if isinstance(record, dict):
                requests_list.append(record)

    requests_list.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return requests_list


def _normalize_partner_application_timeline(timeline):
    return _normalize_application_timeline(timeline, "PARTNER_APPLICATION_CREATED")


def _append_partner_timeline_event(record, event_type, title, detail="", status=None):
    _append_application_timeline_event(record, event_type, title, detail=detail, status=status)


def _partner_application_timeline_events(record):
    timeline = _normalize_partner_application_timeline(record.get("timeline"))
    if timeline:
        return timeline

    created_at = str(record.get("created_at", "")).strip()
    if not created_at:
        return []

    return [{
        "type": "PARTNER_APPLICATION_CREATED",
        "created_at": created_at,
        "title": f"Partner application created: {record.get('company_name') or record.get('contact_person') or 'Unnamed application'}",
        "detail": f"{record.get('service_category', '')} · {record.get('city', '')}",
        "status": _normalize_application_status(record.get("status", "new")),
    }]


def _fallback_partner_application_id(record):
    parts = [
        str(record.get("created_at", "")),
        str(record.get("email", "")),
        str(record.get("company_name", "")),
        str(record.get("city", "")),
        str(record.get("service_category", "")),
    ]
    digest = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()
    return f"partner-{digest[:16]}"


def _normalize_partner_application(record):
    if not isinstance(record, dict):
        return None

    normalized = dict(record)
    normalized["id"] = str(normalized.get("id", "")).strip() or _fallback_partner_application_id(normalized)
    normalized["created_at"] = str(normalized.get("created_at", "")).strip()
    normalized["status"] = _normalize_application_status(normalized.get("status", "new"))

    normalized["company_name"] = str(normalized.get("company_name", "")).strip()
    normalized["contact_person"] = str(normalized.get("contact_person", "")).strip()
    normalized["email"] = str(normalized.get("email", "")).strip()
    normalized["phone"] = str(normalized.get("phone", "")).strip()
    normalized["website"] = str(normalized.get("website", "")).strip()
    normalized["city"] = str(normalized.get("city", "")).strip()
    normalized["country"] = str(normalized.get("country", "")).strip()
    normalized["service_category"] = str(normalized.get("service_category", "")).strip()
    normalized["description"] = str(normalized.get("description", "")).strip()

    years_in_business = normalized.get("years_in_business", "")
    if isinstance(years_in_business, str):
        years_in_business = years_in_business.strip()
        normalized["years_in_business"] = int(years_in_business) if years_in_business.isdigit() else years_in_business
    elif isinstance(years_in_business, (int, float)):
        normalized["years_in_business"] = int(years_in_business)
    else:
        normalized["years_in_business"] = str(years_in_business).strip()

    normalized["owner"] = str(normalized.get("owner", "")).strip()
    normalized["internal_notes"] = str(normalized.get("internal_notes", "")).strip()
    normalized["notes"] = str(normalized.get("notes") or normalized["internal_notes"]).strip()
    normalized["timeline"] = _normalize_partner_application_timeline(normalized.get("timeline", []))
    return normalized


def _load_partner_applications():
    path = Path("data") / "partner_applications.jsonl"
    applications = []

    if not path.exists():
        return applications

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            normalized = _normalize_partner_application(record)
            if normalized:
                applications.append(normalized)

    applications.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return applications


def _save_partner_applications(applications):
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    path = data_dir / "partner_applications.jsonl"
    with path.open("w", encoding="utf-8") as f:
        for record in applications:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _find_partner_application(application_id):
    for record in _load_partner_applications():
        if str(record.get("id", "")) == str(application_id):
            return record
    return None


def _partner_application_status_counts(applications):
    return _application_status_counts(applications)


def _admin_partner_activity_feed(applications):
    events = []
    for record in applications:
        timeline_events = _partner_application_timeline_events(record)
        if timeline_events:
            events.extend(timeline_events)

    events.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return events[:10]


def _load_public_partner_applications():
    approved_applications = []
    for record in _load_partner_applications():
        if _normalize_application_status(record.get("status")) != "converted":
            continue
        approved_applications.append(record)

    approved_applications.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return approved_applications


def _normalize_professional_status(status):
    return _normalize_application_status(status)


def _professional_status_label(status):
    return _application_status_label(status)


def _normalize_professional_application_timeline(timeline):
    return _normalize_application_timeline(timeline, "PROFESSIONAL_APPLICATION_CREATED")


def _append_professional_timeline_event(record, event_type, title, detail="", status=None):
    _append_application_timeline_event(record, event_type, title, detail=detail, status=status)


def _professional_application_timeline_events(record):
    timeline = _normalize_professional_application_timeline(record.get("timeline"))
    if timeline:
        return timeline

    created_at = str(record.get("created_at", "")).strip()
    if not created_at:
        return []

    return [{
        "type": "PROFESSIONAL_APPLICATION_CREATED",
        "created_at": created_at,
        "title": f"Professional application created: {record.get('full_name') or record.get('company_name') or 'Unnamed application'}",
        "detail": f"{record.get('professional_category') or record.get('service_type', '')} · {record.get('city', '')}",
        "status": _normalize_application_status(record.get("status", "new")),
    }]


def _fallback_professional_application_id(record):
    parts = [
        str(record.get("created_at", "")),
        str(record.get("email", "")),
        str(record.get("full_name", "")),
        str(record.get("professional_category", "")),
        str(record.get("city", "")),
    ]
    digest = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()
    return f"professional-{digest[:16]}"


def _normalize_professional_application(record):
    if not isinstance(record, dict):
        return None

    normalized = dict(record)
    normalized["id"] = str(normalized.get("id", "")).strip() or _fallback_professional_application_id(normalized)
    normalized["created_at"] = str(normalized.get("created_at", "")).strip()
    normalized["status"] = _normalize_professional_status(normalized.get("status", "new"))

    normalized["full_name"] = str(normalized.get("full_name") or normalized.get("company_name", "")).strip()
    normalized["email"] = str(normalized.get("email", "")).strip()
    normalized["phone"] = str(normalized.get("phone", "")).strip()
    normalized["city"] = str(normalized.get("city", "")).strip()
    normalized["country"] = str(normalized.get("country", "")).strip()
    normalized["professional_category"] = str(normalized.get("professional_category") or normalized.get("service_type", "")).strip()
    normalized["service_type"] = normalized["professional_category"]
    normalized["languages"] = str(normalized.get("languages", "")).strip()
    normalized["short_bio"] = str(normalized.get("short_bio") or normalized.get("description", "")).strip()
    normalized["description"] = normalized["short_bio"]
    normalized["website"] = str(normalized.get("website", "")).strip()
    normalized["owner"] = str(normalized.get("owner", "")).strip()
    normalized["internal_notes"] = str(normalized.get("internal_notes", "")).strip()
    normalized["notes"] = str(normalized.get("notes") or normalized["internal_notes"]).strip()

    experience_value = normalized.get("experience", normalized.get("experience_years", ""))
    if isinstance(experience_value, str):
        experience_value = experience_value.strip()
        normalized["experience"] = int(experience_value) if experience_value.isdigit() else experience_value
    elif isinstance(experience_value, (int, float)):
        normalized["experience"] = int(experience_value)
    else:
        normalized["experience"] = str(experience_value).strip()

    experience_years = normalized.get("experience_years", normalized.get("experience", ""))
    if isinstance(experience_years, str):
        experience_years = experience_years.strip()
        normalized["experience_years"] = int(experience_years) if experience_years.isdigit() else experience_years
    elif isinstance(experience_years, (int, float)):
        normalized["experience_years"] = int(experience_years)
    else:
        normalized["experience_years"] = str(experience_years).strip()

    normalized["featured"] = _normalize_bool_field(normalized.get("featured", False))
    normalized["badges"] = _normalize_professional_badges(normalized.get("badges", []))
    normalized["photo_url"] = str(normalized.get("photo_url", "")).strip()
    normalized["logo_url"] = str(normalized.get("logo_url", "")).strip()
    normalized["available_for_requests"] = _normalize_bool_field(normalized.get("available_for_requests", True))
    normalized["timeline"] = _normalize_professional_application_timeline(normalized.get("timeline", []))

    return normalized


def _load_professional_applications():
    path = Path("data") / "professional_applications.jsonl"
    applications = []

    if not path.exists():
        return applications

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            normalized = _normalize_professional_application(record)
            if normalized:
                applications.append(normalized)

    applications.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return applications


def _load_public_professional_applications():
    approved_applications = []
    for record in _load_professional_applications():
        if _normalize_professional_status(record.get("status")) != "converted":
            continue
        approved_applications.append(record)

    approved_applications.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return approved_applications


def _save_professional_applications(applications):
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    path = data_dir / "professional_applications.jsonl"
    with path.open("w", encoding="utf-8") as f:
        for record in applications:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _find_professional_application(application_id):
    for record in _load_professional_applications():
        if str(record.get("id", "")) == str(application_id):
            return record
    return None


def _professional_application_status_counts(applications):
    return _application_status_counts(applications)


def _admin_professional_activity_feed(applications):
    events = []
    for record in applications:
        timeline_events = _professional_application_timeline_events(record)
        if timeline_events:
            events.extend(timeline_events)

    events.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return events[:10]


def _build_application_notification_email_body(application_type, record, admin_detail_url):
    lines = [
        f"Name: {record.get('full_name') or record.get('company_name') or record.get('contact_person') or 'n/a'}",
        f"Email: {record.get('email', '')}",
        f"Category: {record.get('service_category') or record.get('professional_category') or record.get('service_type') or 'n/a'}",
        f"Date: {record.get('created_at', '')}",
        f"Status: {_application_status_label(record.get('status', 'new'))}",
        f"Admin Link: {admin_detail_url}",
    ]

    if application_type == "partner":
        lines.insert(1, f"Company: {record.get('company_name', '')}")
        lines.insert(3, f"Phone: {record.get('phone', '')}")
        lines.append(f"City: {record.get('city', '')}")
        lines.append(f"Country: {record.get('country', '')}")
    else:
        lines.insert(1, f"Phone: {record.get('phone', '')}")
        lines.append(f"City: {record.get('city', '')}")
        lines.append(f"Country: {record.get('country', '')}")

    return "\n".join(lines)


def _send_admin_application_notification_email(subject, body):
    smtp_host = os.getenv("SMTP_HOST", "").strip()
    smtp_port_raw = os.getenv("SMTP_PORT", "").strip()
    smtp_username = os.getenv("SMTP_USERNAME", "").strip()
    smtp_password = os.getenv("SMTP_PASSWORD", "").strip()
    smtp_from = os.getenv("SMTP_FROM", "").strip()
    smtp_to = "concierge@blackseaconnect.com"

    if not smtp_host or not smtp_port_raw or not smtp_from:
        app.logger.warning(
            "Admin application email skipped: SMTP configuration is missing for %s.",
            _smtp_endpoint_label(smtp_host or "unknown", smtp_port_raw or "unknown"),
        )
        return False, "smtp_not_configured"

    try:
        smtp_port = int(smtp_port_raw)
    except ValueError:
        app.logger.warning(
            "Admin application email skipped: SMTP_PORT is invalid for %s.",
            _smtp_endpoint_label(smtp_host, smtp_port_raw),
        )
        return False, "smtp_invalid_port"

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = smtp_from
    message["To"] = smtp_to
    message.set_content(body)

    try:
        smtp_factory = smtplib.SMTP_SSL if smtp_port == 465 else smtplib.SMTP
        with smtp_factory(smtp_host, smtp_port, timeout=10) as smtp:
            smtp.ehlo()
            if smtp_port != 465:
                try:
                    smtp.starttls()
                    smtp.ehlo()
                except smtplib.SMTPException:
                    app.logger.warning("Admin application email: SMTP STARTTLS was unavailable.")

            if smtp_username or smtp_password:
                smtp.login(smtp_username, smtp_password)

            smtp.send_message(message)
    except Exception as exc:
        app.logger.warning("Admin application email send failed for %s: %s", _smtp_endpoint_label(smtp_host, smtp_port), exc)
        return False, "smtp_send_failed"

    return True, None


def _queue_admin_application_notification_email(subject, body):
    Thread(target=_send_admin_application_notification_email, args=(subject, body), daemon=True).start()


def _build_owner_registration_notification_body(owner_account, language, source_url=None):
    lines = [
        "BlackSea Connect owner registration notification",
        "",
        f"Full name: {owner_account.get('full_name', '')}",
        f"Email: {owner_account.get('email', '')}",
        f"Phone: {owner_account.get('phone', '')}",
        f"Property name: {owner_account.get('property_name', '')}",
        f"Property type: {owner_account.get('property_type', '')}",
        f"City/location: {owner_account.get('city', '')}",
        f"Number of units: {owner_account.get('number_of_units', '')}",
        f"Language: {str(language or '').strip().lower() or 'bg'}",
        f"Created at: {owner_account.get('created_at', '')}",
    ]
    if source_url:
        lines.append(f"Source URL: {source_url}")
    return "\n".join(lines)


def _send_owner_registration_notification_email(owner_account, source_url, language):
    smtp_host, smtp_port_raw, smtp_from = _service_request_smtp_settings()
    admin_notification_email = os.getenv("ADMIN_NOTIFICATION_EMAIL", "").strip()
    recipient_email = admin_notification_email or smtp_from

    if not smtp_host or not smtp_port_raw or not smtp_from or not recipient_email:
        app.logger.warning(
            "Owner registration notification skipped for %s: SMTP configuration is missing.",
            _mask_email(owner_account.get("email", "")),
        )
        _append_owner_magic_email_event(
            "owner_registration_notification_failed",
            owner_account.get("email", ""),
            "smtp_not_configured",
            "register",
            language,
        )
        return {"ok": False, "reason": "smtp_not_configured"}

    try:
        smtp_port = int(smtp_port_raw)
    except ValueError:
        app.logger.warning(
            "Owner registration notification skipped for %s: SMTP_PORT is invalid.",
            _mask_email(owner_account.get("email", "")),
        )
        _append_owner_magic_email_event(
            "owner_registration_notification_failed",
            owner_account.get("email", ""),
            "smtp_invalid_port",
            "register",
            language,
        )
        return {"ok": False, "reason": "smtp_invalid_port"}

    smtp_username = os.getenv("SMTP_USERNAME", "").strip()
    smtp_password = os.getenv("SMTP_PASSWORD", "").strip()

    message = EmailMessage()
    message["Subject"] = "[BlackSea Owners] New owner registration"
    message["From"] = smtp_from
    message["To"] = recipient_email
    message.set_content(_build_owner_registration_notification_body(owner_account, language, source_url))

    try:
        smtp_factory = smtplib.SMTP_SSL if smtp_port == 465 else smtplib.SMTP
        with smtp_factory(smtp_host, smtp_port, timeout=10) as smtp:
            smtp.ehlo()
            if smtp_port != 465:
                try:
                    smtp.starttls()
                    smtp.ehlo()
                except smtplib.SMTPException:
                    app.logger.warning("Owner registration notification: SMTP STARTTLS was unavailable.")

            if smtp_username or smtp_password:
                smtp.login(smtp_username, smtp_password)

            smtp.send_message(message)
    except smtplib.SMTPAuthenticationError as exc:
        app.logger.warning(
            "Owner registration notification failed for %s: SMTPAuthenticationError",
            _mask_email(owner_account.get("email", "")),
        )
        _append_owner_magic_email_event(
            "owner_registration_notification_failed",
            owner_account.get("email", ""),
            "smtp_login_failed",
            "register",
            language,
        )
        return {"ok": False, "reason": "smtp_login_failed"}
    except smtplib.SMTPRecipientsRefused:
        app.logger.warning(
            "Owner registration notification failed for %s: SMTPRecipientsRefused",
            _mask_email(owner_account.get("email", "")),
        )
        _append_owner_magic_email_event(
            "owner_registration_notification_failed",
            owner_account.get("email", ""),
            "smtp_send_failed",
            "register",
            language,
        )
        return {"ok": False, "reason": "smtp_send_failed"}
    except smtplib.SMTPException:
        app.logger.warning(
            "Owner registration notification failed for %s: SMTPException",
            _mask_email(owner_account.get("email", "")),
        )
        _append_owner_magic_email_event(
            "owner_registration_notification_failed",
            owner_account.get("email", ""),
            "smtp_send_failed",
            "register",
            language,
        )
        return {"ok": False, "reason": "smtp_send_failed"}
    except Exception as exc:
        app.logger.warning(
            "Owner registration notification failed for %s: %s",
            _mask_email(owner_account.get("email", "")),
            type(exc).__name__,
        )
        _append_owner_magic_email_event(
            "owner_registration_notification_failed",
            owner_account.get("email", ""),
            "unexpected_error",
            "register",
            language,
        )
        return {"ok": False, "reason": "unexpected_error"}

    app.logger.info("Owner registration notification sent for %s", _mask_email(owner_account.get("email", "")))
    _append_owner_magic_email_event(
        "owner_registration_notification_sent",
        owner_account.get("email", ""),
        "sent",
        "register",
        language,
    )
    return {"ok": True, "reason": "sent"}


def _queue_partner_application_notification_email(record, admin_detail_url):
    subject = "[BlackSeaConnect] New Partner Application"
    body = _build_application_notification_email_body("partner", record, admin_detail_url)
    _queue_admin_application_notification_email(subject, body)


def _queue_professional_application_notification_email(record, admin_detail_url):
    subject = "[BlackSeaConnect] New Professional Application"
    body = _build_application_notification_email_body("professional", record, admin_detail_url)
    _queue_admin_application_notification_email(subject, body)


def _build_professional_telegram_text(record, admin_detail_url):
    lines = [
        "New Professional Application",
        f"full_name: {record.get('full_name', '')}",
        f"company_name: {record.get('company_name', '')}",
        f"service_type: {record.get('service_type', '')}",
        f"city: {record.get('city', '')}",
        f"phone: {record.get('phone', '')}",
        f"email: {record.get('email', '')}",
        f"status: {_normalize_professional_status(record.get('status', 'new')).upper()}",
        f"admin_detail_url: {admin_detail_url}",
    ]
    return "\n".join(lines)


def _send_professional_application_via_telegram(record, admin_detail_url, telegram_bot_token, telegram_chat_id):
    telegram_text = _build_professional_telegram_text(record, admin_detail_url)
    telegram_url = f"https://api.telegram.org/bot{telegram_bot_token}/sendMessage"
    payload = {
        "chat_id": telegram_chat_id,
        "text": telegram_text,
        "disable_web_page_preview": "true",
    }

    request = urllib.request.Request(
        telegram_url,
        data=urllib.parse.urlencode(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            response_status = getattr(response, "status", getattr(response, "code", None))
            if response_status not in (200, 201, 202):
                app.logger.warning("Professional application notification send failed via Telegram: unexpected status %s.", response_status)
                return False, "telegram_bad_status"
    except urllib.error.HTTPError as exc:
        response_body = ""
        try:
            response_body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            response_body = "<unreadable>"
        app.logger.warning(
            "Professional application notification send failed via Telegram: HTTP %s %s. Body: %s",
            exc.code,
            exc.reason,
            response_body,
        )
        return False, "telegram_send_failed"
    except Exception as exc:
        app.logger.warning("Professional application notification send failed via Telegram: %s", type(exc).__name__)
        return False, "telegram_send_failed"

    return True, None


def _send_professional_application_notification(record, admin_detail_url):
    telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    if not telegram_bot_token or not telegram_chat_id:
        return False, "telegram_not_configured"

    return _send_professional_application_via_telegram(
        record,
        admin_detail_url,
        telegram_bot_token,
        telegram_chat_id,
    )


def _queue_professional_application_notification(record, admin_detail_url):
    telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not telegram_bot_token or not telegram_chat_id:
        return

    Thread(
        target=_send_professional_application_notification,
        args=(record, admin_detail_url),
        daemon=True,
    ).start()


def _pilot_status_counts(requests_list):
    counts = {status: 0 for status in PILOT_STATUS_VALUES}
    for record in requests_list:
        status = _normalize_pilot_status(record.get("status", "new"))
        if status in counts:
            counts[status] += 1
    return counts


def _admin_pilot_activity_feed(pilot_requests, concierge_requests):
    events = []

    for record in pilot_requests:
        timeline_events = _pilot_request_timeline_events(record)
        if timeline_events:
            events.extend(timeline_events)

    for record in concierge_requests:
        events.append({
            "type": "concierge_request_received",
            "created_at": record.get("created_at", ""),
            "title": "Concierge request received",
            "detail": f"{record.get('name', '')} · {record.get('service_type', '')}",
            "status": "",
        })

    events.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return events[:10]


def _admin_activity_feed(pilot_requests, concierge_requests, partner_applications, professional_applications):
    events = []
    events.extend(_admin_pilot_activity_feed(pilot_requests, concierge_requests))
    events.extend(_admin_partner_activity_feed(partner_applications))
    events.extend(_admin_professional_activity_feed(professional_applications))
    events.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return events[:10]


def _build_admin_dashboard():
    pilot_requests = _load_pilot_requests()
    concierge_requests = _load_concierge_requests()
    partner_applications = _load_partner_applications()
    professional_applications = _load_professional_applications()
    owner_accounts = _load_owner_accounts()
    service_requests = _load_service_requests()
    pilot_counts = _pilot_status_counts(pilot_requests)
    partner_counts = _partner_application_status_counts(partner_applications)
    professional_counts = _professional_application_status_counts(professional_applications)
    service_request_counts = _service_request_status_counts(service_requests)
    current_month = datetime.now(timezone.utc).strftime("%Y-%m")
    requests_this_month = sum(1 for record in service_requests if str(record.get("created_at", "")).startswith(current_month))
    active_requests = sum(1 for record in service_requests if _normalize_service_request_status(record.get("status", "new")) in {"new", "assigned", "in_progress"})
    completed_requests = service_request_counts["completed"]

    return {
        "total_leads": len(pilot_requests),
        "total_pilot_requests": len(pilot_requests),
        "new_leads": pilot_counts["new"],
        "contacted_leads": pilot_counts["contacted"],
        "qualified_leads": pilot_counts["qualified"],
        "converted_leads": pilot_counts["converted"],
        "lost_leads": pilot_counts["lost"],
        "concierge_requests": len(concierge_requests),
        "partner_applications": len(partner_applications),
        "professional_applications": len(professional_applications),
        "owner_accounts": len(owner_accounts),
        "active_service_requests": active_requests,
        "completed_service_requests": completed_requests,
        "service_requests_this_month": requests_this_month,
        "partner_status_counts": partner_counts,
        "professional_status_counts": professional_counts,
        "pipeline": [
            {"key": "new", "label": "New", "count": pilot_counts["new"]},
            {"key": "contacted", "label": "Contacted", "count": pilot_counts["contacted"]},
            {"key": "qualified", "label": "Qualified", "count": pilot_counts["qualified"]},
            {"key": "converted", "label": "Converted", "count": pilot_counts["converted"]},
            {"key": "lost", "label": "Lost", "count": pilot_counts["lost"]},
        ],
        "partner_pipeline": [
            {"key": "new", "label": "New", "count": partner_counts["new"]},
            {"key": "contacted", "label": "Contacted", "count": partner_counts["contacted"]},
            {"key": "qualified", "label": "Qualified", "count": partner_counts["qualified"]},
            {"key": "converted", "label": "Converted", "count": partner_counts["converted"]},
            {"key": "lost", "label": "Lost", "count": partner_counts["lost"]},
        ],
        "professional_pipeline": [
            {"key": "new", "label": "New", "count": professional_counts["new"]},
            {"key": "contacted", "label": "Contacted", "count": professional_counts["contacted"]},
            {"key": "qualified", "label": "Qualified", "count": professional_counts["qualified"]},
            {"key": "converted", "label": "Converted", "count": professional_counts["converted"]},
            {"key": "lost", "label": "Lost", "count": professional_counts["lost"]},
        ],
        "recent_activity": _admin_activity_feed(pilot_requests, concierge_requests, partner_applications, professional_applications),
    }


def _export_pilot_requests_csv(requests_list):
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, delimiter=";", quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")
    writer.writerow([
        "id",
        "created_at",
        "status",
        "owner",
        "email",
        "property_type",
        "apartment_count",
        "city",
        "concierge_needs",
    ])

    for record in requests_list:
        writer.writerow([
            record.get("id", ""),
            record.get("created_at", ""),
            _normalize_pilot_status(record.get("status", "new")),
            record.get("owner", ""),
            record.get("email", ""),
            record.get("property_type", ""),
            record.get("apartment_count", ""),
            record.get("city", ""),
            record.get("concierge_needs", ""),
        ])

    return "\ufeff" + buffer.getvalue()


def _export_partner_applications_csv(applications):
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, delimiter=";", quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")
    writer.writerow([
        "id",
        "created_at",
        "status",
        "owner",
        "company_name",
        "contact_person",
        "email",
        "phone",
        "website",
        "city",
        "country",
        "service_category",
        "years_in_business",
        "description",
    ])

    for record in applications:
        writer.writerow([
            record.get("id", ""),
            record.get("created_at", ""),
            _normalize_application_status(record.get("status", "new")),
            record.get("owner", ""),
            record.get("company_name", ""),
            record.get("contact_person", ""),
            record.get("email", ""),
            record.get("phone", ""),
            record.get("website", ""),
            record.get("city", ""),
            record.get("country", ""),
            record.get("service_category", ""),
            record.get("years_in_business", ""),
            record.get("description", ""),
        ])

    return "\ufeff" + buffer.getvalue()


def _export_professional_applications_csv(applications):
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, delimiter=";", quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")
    writer.writerow([
        "id",
        "created_at",
        "status",
        "owner",
        "full_name",
        "email",
        "phone",
        "city",
        "country",
        "professional_category",
        "languages",
        "experience",
        "short_bio",
    ])

    for record in applications:
        writer.writerow([
            record.get("id", ""),
            record.get("created_at", ""),
            _normalize_application_status(record.get("status", "new")),
            record.get("owner", ""),
            record.get("full_name", ""),
            record.get("email", ""),
            record.get("phone", ""),
            record.get("city", ""),
            record.get("country", ""),
            record.get("professional_category", record.get("service_type", "")),
            record.get("languages", ""),
            record.get("experience", record.get("experience_years", "")),
            record.get("short_bio", record.get("description", "")),
        ])

    return "\ufeff" + buffer.getvalue()


def _save_pilot_requests(requests_list):
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    path = data_dir / "pilot_requests.jsonl"
    with path.open("w", encoding="utf-8") as f:
        for record in requests_list:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _find_pilot_request(request_id):
    for record in _load_pilot_requests():
        if str(record.get("id", "")) == str(request_id):
            return record
    return None


def _coerce_application_status_input(raw_status):
    normalized = str(raw_status or "").strip().lower()
    if not normalized:
        return None
    normalized = CRM_PIPELINE_STATUS_ALIASES.get(normalized, normalized)
    return normalized if normalized in CRM_PIPELINE_STATUS_VALUES else None


def _update_application_from_form(records, record_id):
    updated = False

    for record in records:
        if str(record.get("id", "")) != str(record_id):
            continue

        original_status = _normalize_application_status(record.get("status", "new"))
        raw_status = request.form.get("status", "").strip()
        if raw_status:
            new_status = _coerce_application_status_input(raw_status)
            if new_status is None:
                return None, jsonify({"ok": False, "error": "invalid_status"}), 400
        else:
            new_status = original_status

        original_owner = str(record.get("owner", "")).strip()
        new_owner = str(request.form.get("owner", original_owner)).strip()
        original_notes = str(record.get("internal_notes", record.get("notes", ""))).strip()
        new_notes = str(request.form.get("notes", request.form.get("internal_notes", original_notes))).strip()

        if new_status != original_status:
            record["status"] = new_status
            _append_application_timeline_event(
                record,
                "APPLICATION_STATUS_UPDATED",
                f"Status changed from {_application_status_label(original_status)} to {_application_status_label(new_status)}",
                new_notes or record.get("email", ""),
                status=new_status,
            )

        if new_owner != original_owner:
            record["owner"] = new_owner
            if new_owner:
                _append_application_timeline_event(
                    record,
                    "APPLICATION_OWNER_ASSIGNED",
                    f"Owner assigned: {new_owner}",
                    original_owner or "Unassigned",
                    status=record.get("status", "new"),
                )

        if new_notes != original_notes:
            record["internal_notes"] = new_notes
            record["notes"] = new_notes
            if new_notes:
                _append_application_timeline_event(
                    record,
                    "APPLICATION_NOTE_ADDED",
                    "Note added",
                    new_notes,
                    status=record.get("status", "new"),
                )

        updated = True
        break

    if not updated:
        return None, jsonify({"ok": False, "error": "not_found"}), 404

    return records, None, None


@app.post("/api/pilot-request")
def api_pilot_request():
    payload = request.get_json(silent=True) or {}

    record = {
        "id": uuid4().hex,
        "created_at": _utc_now_iso(),
        "name": _clean_payload_value(payload, "name"),
        "email": _clean_payload_value(payload, "email"),
        "property_type": _clean_payload_value(payload, "property_type"),
        "apartment_count": _clean_payload_value(payload, "apartment_count"),
        "city": _clean_payload_value(payload, "city", "location", "region"),
        "concierge_needs": _clean_payload_value(payload, "concierge_needs", "needs"),
        "current_language": _clean_payload_value(payload, "current_language"),
        "submitted_from": request.referrer or request.headers.get("Referer", "") or request.path,
        "status": "new",
        "notes": "",
        "owner": "",
        "timeline": [],
    }
    record["location"] = record["city"]
    record["needs"] = record["concierge_needs"]

    required = ["property_type", "apartment_count", "city", "concierge_needs", "email"]
    missing = [field for field in required if not record.get(field, "").strip()]

    if missing:
        return jsonify({"ok": False, "error": "missing_fields"}), 400

    _append_pilot_timeline_event(
        record,
        "lead_created",
        f"Lead created: {record.get('name') or record.get('email') or 'Anonymous request'}",
        f"{record.get('property_type', '')} · {record.get('city', '')}",
        status="new",
    )

    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)

    try:
        with (data_dir / "pilot_requests.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        app.logger.exception("Pilot request save failed.")
        return jsonify({"ok": False, "error": "save_failed"}), 500

    admin_detail_url = url_for("admin_pilot_request_detail", request_id=record["id"], _external=True)
    _queue_pilot_request_email(record)
    _queue_internal_pilot_notification(record, admin_detail_url)

    return jsonify({"ok": True}), 200


@app.get("/admin/pilot-requests")
@admin_required
def admin_pilot_requests():
    requests_list = _load_pilot_requests()
    return render_template(
        "admin_pilot_requests.html",
        requests=requests_list,
        pipeline=_build_admin_dashboard()["pipeline"],
    )


@app.get("/admin/pilot-requests/export")
@admin_required
def admin_pilot_requests_export():
    csv_data = _export_pilot_requests_csv(_load_pilot_requests())
    response = Response(csv_data, mimetype="text/csv")
    response.headers["Content-Disposition"] = 'attachment; filename="pilot_requests.csv"'
    return response


@app.get("/admin/pilot-requests/<request_id>")
@admin_required
def admin_pilot_request_detail(request_id):
    record = _find_pilot_request(request_id)
    if not record:
        return jsonify({"ok": False, "error": "not_found"}), 404

    return render_template(
        "admin_pilot_request_detail.html",
        item=record,
        status_options=[{"value": status, "label": _pilot_status_label(status)} for status in PILOT_STATUS_VALUES],
        timeline=list(reversed(_pilot_request_timeline_events(record))),
    )


@app.post("/admin/pilot-requests/<request_id>/status")
@admin_required
def admin_pilot_request_status(request_id):
    return _update_pilot_request_from_form(request_id, update_notes=False, update_owner=False, require_status=True)


@app.post("/admin/pilot-requests/<request_id>/update")
@admin_required
def admin_pilot_request_update(request_id):
    return _update_pilot_request_from_form(request_id, update_notes=True, update_owner=True, require_status=False)


def _coerce_pilot_status_input(raw_status):
    normalized = str(raw_status or "").strip().lower()
    if not normalized:
        return None

    normalized = PILOT_STATUS_ALIASES.get(normalized, normalized)
    return normalized if normalized in PILOT_STATUS_VALUES else None


def _update_pilot_request_from_form(request_id, update_notes, update_owner, require_status):
    requests_list = _load_pilot_requests()
    updated = False

    for record in requests_list:
        if str(record.get("id", "")) != str(request_id):
            continue

        original_status = _normalize_pilot_status(record.get("status", "new"))
        raw_status = request.form.get("status", "").strip()
        if raw_status:
            new_status = _coerce_pilot_status_input(raw_status)
            if new_status is None:
                return jsonify({"ok": False, "error": "invalid_status"}), 400
        else:
            new_status = original_status

        if require_status and not raw_status:
            return jsonify({"ok": False, "error": "invalid_status"}), 400

        original_owner = str(record.get("owner", "")).strip()
        new_owner = original_owner
        original_notes = str(record.get("notes", "")).strip()
        new_notes = original_notes

        if new_status != original_status:
            record["status"] = new_status
            _append_pilot_timeline_event(
                record,
                "status_changed",
                f"Status changed from {_pilot_status_label(original_status)} to {_pilot_status_label(new_status)}",
                record.get("email", ""),
                status=new_status,
            )

        if update_owner:
            new_owner = str(request.form.get("owner", original_owner)).strip()
            if new_owner != original_owner:
                record["owner"] = new_owner
                if new_owner:
                    _append_pilot_timeline_event(
                        record,
                        "owner_assigned",
                        f"Owner assigned: {new_owner}",
                        original_owner or "Unassigned",
                        status=record.get("status", "new"),
                    )

        if update_notes:
            new_notes = str(request.form.get("notes", original_notes)).strip()
            if new_notes != original_notes:
                record["notes"] = new_notes
                if new_notes:
                    _append_pilot_timeline_event(
                        record,
                        "note_added",
                        "Note added",
                        new_notes,
                        status=record.get("status", "new"),
                    )

        updated = True
        break

    if not updated:
        return jsonify({"ok": False, "error": "not_found"}), 404

    _save_pilot_requests(requests_list)
    return redirect(url_for("admin_pilot_request_detail", request_id=request_id))
# create concierge endpoint
@app.route("/api/concierge", methods=["POST"])
def api_concierge():
    payload = request.get_json(silent=True) or {}

    required = ["name", "email", "service_type", "message"]
    missing = [field for field in required if not str(payload.get(field, "")).strip()]

    if missing:
        return jsonify({"ok": False, "error": "missing_fields", "missing": missing}), 400

    allowed_services = {
        "airport_transfer",
        "cleaning",
        "maintenance",
        "restaurant_booking",
        "local_recommendation",
        "other",
    }

    service_type = payload.get("service_type", "").strip()

    if service_type not in allowed_services:
        return jsonify({"ok": False, "error": "invalid_service_type"}), 400

    record = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "name": payload.get("name", "").strip(),
        "email": payload.get("email", "").strip(),
        "service_type": service_type,
        "message": payload.get("message", "").strip(),
    }

    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)

    with (data_dir / "concierge_requests.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return jsonify({"ok": True, "message": "Concierge request received"})


@app.get("/admin/concierge-requests")
@admin_required
def admin_concierge_requests():
    return render_template("admin_concierge_requests.html", requests=_load_concierge_requests())


@app.get("/admin/partners")
@admin_required
def admin_partners():
    applications = _load_partner_applications()
    counts = _partner_application_status_counts(applications)
    return render_template(
        "admin_partners.html",
        applications=applications,
        counts=counts,
    )


@app.get("/admin/partners/export")
@admin_required
def admin_partners_export():
    csv_data = _export_partner_applications_csv(_load_partner_applications())
    response = Response(csv_data, mimetype="text/csv")
    response.headers["Content-Disposition"] = 'attachment; filename="partner_applications.csv"'
    return response


@app.get("/admin/partners/<application_id>")
@admin_required
def admin_partner_application_detail(application_id):
    record = _find_partner_application(application_id)
    if not record:
        return jsonify({"ok": False, "error": "not_found"}), 404

    return render_template(
        "admin_partner_detail.html",
        item=record,
        status_options=[{"value": status, "label": _application_status_label(status)} for status in CRM_PIPELINE_STATUS_VALUES],
        timeline=list(reversed(_partner_application_timeline_events(record))),
    )


@app.post("/admin/partners/<application_id>/update")
@admin_required
def admin_partner_application_update(application_id):
    applications = _load_partner_applications()
    applications, error_response, status_code = _update_application_from_form(applications, application_id)
    if error_response is not None:
        return error_response, status_code

    _save_partner_applications(applications)
    return redirect(url_for("admin_partner_application_detail", application_id=application_id))


@app.get("/admin/professionals")
@admin_required
def admin_professionals():
    applications = _load_professional_applications()
    counts = _professional_application_status_counts(applications)
    return render_template(
        "admin_professionals.html",
        applications=applications,
        counts=counts,
    )


@app.get("/admin/professionals/export")
@admin_required
def admin_professionals_export():
    csv_data = _export_professional_applications_csv(_load_professional_applications())
    response = Response(csv_data, mimetype="text/csv")
    response.headers["Content-Disposition"] = 'attachment; filename="professional_applications.csv"'
    return response


@app.get("/admin/professionals/<application_id>")
@admin_required
def admin_professional_detail(application_id):
    record = _find_professional_application(application_id)
    if not record:
        return jsonify({"ok": False, "error": "not_found"}), 404

    return render_template(
        "admin_professional_detail.html",
        item=record,
        status_options=[{"value": status, "label": _application_status_label(status)} for status in CRM_PIPELINE_STATUS_VALUES],
        timeline=list(reversed(_professional_application_timeline_events(record))),
    )


@app.post("/admin/professionals/<application_id>/update")
@admin_required
def admin_professional_update(application_id):
    applications = _load_professional_applications()
    applications, error_response, status_code = _update_application_from_form(applications, application_id)
    if error_response is not None:
        return error_response, status_code

    _save_professional_applications(applications)
    return redirect(url_for("admin_professional_detail", application_id=application_id))


@app.get("/admin/service-requests")
@admin_required
def admin_service_requests():
    requests_list = _load_service_requests()
    counts = _service_request_status_counts(requests_list)
    return render_template(
        "admin_service_requests.html",
        requests=requests_list,
        counts=counts,
    )


@app.get("/admin/service-requests/<request_id>")
@admin_required
def admin_service_request_detail(request_id):
    record = _find_service_request(request_id)
    if not record:
        return jsonify({"ok": False, "error": "not_found"}), 404

    matching_providers = _service_request_matching_providers(record.get("service_category"))
    return render_template(
        "admin_service_request_detail.html",
        item=record,
        matching_providers=matching_providers,
        status_options=[{"value": status, "label": status.upper()} for status in SERVICE_REQUEST_STATUS_VALUES],
        timeline=list(reversed(_service_request_timeline_events(record))),
    )


@app.post("/admin/service-requests/<request_id>/update")
@admin_required
def admin_service_request_update(request_id):
    requests_list = _load_service_requests()
    updated = False

    for record in requests_list:
        if str(record.get("id", "")) != str(request_id):
            continue

        raw_status = str(request.form.get("status", "")).strip()
        original_status = _normalize_service_request_status(record.get("status", "new"))
        if raw_status:
            new_status = _normalize_service_request_status(raw_status)
            if new_status != raw_status.lower():
                return jsonify({"ok": False, "error": "invalid_status"}), 400
        else:
            new_status = original_status

        original_notes = str(record.get("internal_notes", "")).strip()
        new_notes = str(request.form.get("internal_notes", original_notes)).strip()
        original_provider_id = str(record.get("assigned_provider_id", "")).strip()
        selected_provider_id = str(request.form.get("assigned_provider_id", original_provider_id)).strip()

        selected_provider = None
        if selected_provider_id:
            for provider in _load_network_providers():
                if str(provider.get("id", "")) == selected_provider_id:
                    selected_provider = provider
                    break

        if new_status == "assigned" and selected_provider_id and not selected_provider:
            return jsonify({"ok": False, "error": "invalid_provider"}), 400

        status_changed = new_status != original_status
        provider_changed = selected_provider_id != original_provider_id
        completed = new_status == "completed"

        if selected_provider:
            record["assigned_provider_id"] = selected_provider_id
            record["assigned_provider_name"] = selected_provider.get("full_name", "")
            record["assigned_provider_company"] = selected_provider.get("company_name", "") or selected_provider.get("full_name", "")
            record["assigned_professional_id"] = selected_provider_id
            record["assigned_professional_name"] = selected_provider.get("full_name", "")
            record["assigned_professional_company"] = selected_provider.get("company_name", "") or selected_provider.get("full_name", "")

        record["internal_notes"] = new_notes
        record["last_update_at"] = _utc_now_iso()

        if status_changed:
            record["status"] = new_status
            _append_service_request_timeline_event(
                record,
                "SERVICE_REQUEST_STATUS_UPDATED",
                f"Status changed from {original_status.upper()} to {new_status.upper()}",
                new_notes or record.get("service_category", ""),
                status=new_status,
            )

        if provider_changed and selected_provider:
            _append_service_request_timeline_event(
                record,
                "SERVICE_REQUEST_PROFESSIONAL_ASSIGNED",
                "Professional assigned",
                f"{selected_provider.get('company_name', '') or selected_provider.get('full_name', '')}",
                status=record.get("status", "new"),
            )

        if completed:
            _append_service_request_timeline_event(
                record,
                "SERVICE_REQUEST_COMPLETED",
                "Service request completed",
                new_notes or record.get("assigned_provider_company", "") or record.get("service_category", ""),
                status=new_status,
            )

        owner_recipient = str(record.get("owner_email", "")).strip() or str(record.get("email", "")).strip()
        if owner_recipient and (status_changed or provider_changed or completed):
            event_label = "completed" if completed else "assigned" if provider_changed else "status_changed"
            subject = {
                "completed": "[BlackSeaConnect] Service request completed",
                "assigned": "[BlackSeaConnect] Professional assigned to your service request",
                "status_changed": "[BlackSeaConnect] Service request status updated",
            }[event_label]
            admin_detail_url = url_for("admin_service_request_detail", request_id=request_id, _external=True)
            _queue_service_request_email(
                record,
                owner_recipient,
                "owner",
                admin_detail_url,
                event_label,
                subject,
            )

        updated = True
        break

    if not updated:
        return jsonify({"ok": False, "error": "not_found"}), 404

    _save_service_requests(requests_list)
    return redirect(url_for("admin_service_request_detail", request_id=request_id))

@app.get("/admin")
@admin_required
def admin_home():
    dashboard = _build_admin_dashboard()
    return render_template("admin_home.html", **dashboard)
if __name__ == "__main__":
    app.run(debug=True, port=5010)





