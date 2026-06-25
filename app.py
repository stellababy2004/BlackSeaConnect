from datetime import datetime, timezone
from datetime import timedelta
from email.message import EmailMessage
from email.utils import formataddr, parseaddr
import hashlib
import csv
import io
import hmac
import re
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

from flask import Flask, Response, g, jsonify, redirect, render_template, render_template_string, request, session, url_for

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
PUBLIC_FORM_RATE_LIMIT_WINDOW_SECONDS = 15 * 60
PUBLIC_FORM_RATE_LIMIT_MAX_SUBMISSIONS = 5
PUBLIC_FORM_AUDIT_EVENTS_PATH = Path("data") / "public_form_audit_events.jsonl"
_PUBLIC_FORM_RATE_LIMITS = {}
_OWNER_DB_SCHEMA_INITIALIZING = False
_OWNER_DB_BACKFILL_SUPPRESSED = False
DEMO_DATA_MANIFEST_PATH = Path("data") / "demo_data_engine.json"
DEMO_SCENARIO = "BlackSea Connect Pilot"
DEMO_SEASON = "Summer 2026"
DEMO_BATCH_ID = "blacksea-connect-pilot-summer-2026"

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
PROFESSIONAL_MAGIC_LINK_TTL_MINUTES = 30
SITE_LANGUAGE_SESSION_KEY = "site_lang"
SUPPORTED_LANGUAGES = {"bg", "en", "fr", "ru"}
OWNER_STATUS_VALUES = {"PILOT", "ACTIVE", "INACTIVE", "VIP"}
OWNER_STATUS_DEFAULT = "PILOT"
OWNER_LANGUAGE_DEFAULT = "bg"
OWNER_PROPERTY_STATUS_VALUES = {"SETUP", "ACTIVE", "SEASONAL", "INACTIVE"}
OWNER_PROPERTY_STATUS_DEFAULT = "SETUP"
OWNER_PROPERTY_CHECKLIST_FIELDS = (
    "guest_guide_ready",
    "access_instructions_ready",
    "emergency_contact_ready",
    "cleaning_partner_ready",
)
OWNER_PROPERTY_ACTIVITY_EVENT_VALUES = {
    "property_created",
    "owner_assigned",
    "status_changed",
    "checklist_updated",
    "service_request_submitted",
    "service_request_completed",
    "note_added",
}
OWNER_SESSION_ID_KEY = "owner_id"
OWNER_SESSION_EMAIL_KEY = "owner_email"
OWNER_SESSION_NAME_KEY = "owner_name"
OWNER_SESSION_LOGGED_IN_KEY = "owner_logged_in"
PROFESSIONAL_SESSION_ID_KEY = "professional_id"
PROFESSIONAL_SESSION_EMAIL_KEY = "professional_email"
PROFESSIONAL_SESSION_NAME_KEY = "professional_name"
PROFESSIONAL_SESSION_LOGGED_IN_KEY = "professional_logged_in"
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
OPERATIONS_TASK_STATUS_VALUES = (
    "NEW",
    "ASSIGNED",
    "ACCEPTED",
    "ON_THE_WAY",
    "ARRIVED",
    "IN_PROGRESS",
    "PAUSED",
    "WAITING_OWNER",
    "WAITING_OPERATIONS",
    "COMPLETED",
    "ARCHIVED",
)
OPERATIONS_TASK_STATUS_ALIASES = {
    "new": "NEW",
    "assigned": "ASSIGNED",
    "accepted": "ACCEPTED",
    "on the way": "ON_THE_WAY",
    "on_the_way": "ON_THE_WAY",
    "on-my-way": "ON_THE_WAY",
    "on my way": "ON_THE_WAY",
    "arrived": "ARRIVED",
    "in progress": "IN_PROGRESS",
    "in_progress": "IN_PROGRESS",
    "started": "IN_PROGRESS",
    "paused": "PAUSED",
    "waiting owner": "WAITING_OWNER",
    "waiting_owner": "WAITING_OWNER",
    "waiting operations": "WAITING_OPERATIONS",
    "waiting_operations": "WAITING_OPERATIONS",
    "waiting provider": "WAITING_OPERATIONS",
    "waiting_provider": "WAITING_OPERATIONS",
    "done": "COMPLETED",
    "completed": "COMPLETED",
    "archived": "ARCHIVED",
    "cancelled": "ARCHIVED",
    "canceled": "ARCHIVED",
}
OPERATIONS_TASK_PRIORITY_VALUES = ("LOW", "NORMAL", "HIGH", "URGENT")
OPERATIONS_TASK_PRIORITY_ALIASES = {
    "low": "LOW",
    "normal": "NORMAL",
    "standard": "NORMAL",
    "medium": "NORMAL",
    "high": "HIGH",
    "urgent": "URGENT",
}
OPERATIONS_TASK_EVENT_VALUES = {
    "task_created",
    "assigned",
    "status_changed",
    "completed",
    "audit_logged",
    "workflow_transitioned",
    "note_added",
    "checklist_updated",
    "comment_added",
    "comment_added_internal",
    "attachment_added",
    "completion_report_updated",
    "professional_assigned",
    "professional_accepted",
    "professional_started",
    "professional_on_the_way",
    "professional_arrived",
    "professional_paused",
    "professional_resumed",
    "professional_completed",
    "professional_comment_added",
}
RESERVATION_STATUS_VALUES = (
    "PENDING",
    "CONFIRMED",
    "CHECKED_IN",
    "CHECKED_OUT",
    "CANCELLED",
    "NO_SHOW",
)
RESERVATION_STATUS_ALIASES = {
    "pending": "PENDING",
    "confirmed": "CONFIRMED",
    "checked in": "CHECKED_IN",
    "checkin": "CHECKED_IN",
    "checked_in": "CHECKED_IN",
    "checked out": "CHECKED_OUT",
    "checkout": "CHECKED_OUT",
    "checked_out": "CHECKED_OUT",
    "cancelled": "CANCELLED",
    "canceled": "CANCELLED",
    "no show": "NO_SHOW",
    "no-show": "NO_SHOW",
    "noshow": "NO_SHOW",
}
RESERVATION_SOURCE_VALUES = (
    "Manual",
    "CSV",
    "iCal",
    "Airbnb",
    "Booking.com",
    "Vrbo",
    "Direct Website",
)
RESERVATION_SOURCE_ALIASES = {
    "manual": "Manual",
    "manual reservation": "Manual",
    "direct booking": "Direct Website",
    "direct website": "Direct Website",
    "website": "Direct Website",
    "csv": "CSV",
    "csv import": "CSV",
    "ical": "iCal",
    "google calendar": "iCal",
    "airbnb": "Airbnb",
    "booking.com": "Booking.com",
    "booking": "Booking.com",
    "vrbo": "Vrbo",
}
CALENDAR_EVENT_TYPE_VALUES = (
    "Check-in",
    "Check-out",
    "Reservation",
    "Cleaning",
    "Inspection",
    "Maintenance",
    "Airport Transfer",
    "Concierge",
    "Professional Visit",
    "Guest Issue",
    "Seasonal Preparation",
    "Blocked Dates",
    "Personal Stay",
    "Owner Meeting",
    "Other",
)
CALENDAR_EVENT_TYPE_ALIASES = {
    "check in": "Check-in",
    "check-in": "Check-in",
    "checkin": "Check-in",
    "check out": "Check-out",
    "check-out": "Check-out",
    "checkout": "Check-out",
    "reservation": "Reservation",
    "clean": "Cleaning",
    "cleaning": "Cleaning",
    "arrival cleaning": "Cleaning",
    "departure cleaning": "Cleaning",
    "mid-stay cleaning": "Cleaning",
    "mid stay cleaning": "Cleaning",
    "check-in preparation": "Check-in",
    "checkin preparation": "Check-in",
    "welcome pack": "Concierge",
    "guest inspection": "Inspection",
    "checkout inspection": "Inspection",
    "inspection": "Inspection",
    "maintenance review": "Maintenance",
    "maintenance": "Maintenance",
    "airport": "Airport Transfer",
    "airport transfer": "Airport Transfer",
    "airport transfers": "Airport Transfer",
    "concierge": "Concierge",
    "professional visit": "Professional Visit",
    "guest issue": "Guest Issue",
    "seasonal preparation": "Seasonal Preparation",
    "seasonal prep": "Seasonal Preparation",
    "blocked dates": "Blocked Dates",
    "blocked date": "Blocked Dates",
    "personal stay": "Personal Stay",
    "owner meeting": "Owner Meeting",
    "meeting": "Owner Meeting",
    "other": "Other",
}
CALENDAR_EVENT_STATUS_VALUES = (
    "SCHEDULED",
    "IN_PROGRESS",
    "COMPLETED",
    "CANCELLED",
    "BLOCKED",
)
CALENDAR_OWNER_EVENT_TYPES = {"Blocked Dates", "Personal Stay"}
CALENDAR_EXTERNAL_INTEGRATION_POINTS = (
    "Airbnb iCal",
    "Booking.com iCal",
    "VRBO",
    "Google Calendar",
    "Apple Calendar",
    "Outlook",
)
CALENDAR_EVENT_COLOR_BY_TYPE = {
    "Reservation": "blue",
    "Cleaning": "green",
    "Inspection": "blue",
    "Maintenance": "orange",
    "Guest Issue": "red",
    "Airport Transfer": "purple",
    "Concierge": "turquoise",
    "Blocked Dates": "grey",
    "Personal Stay": "turquoise",
    "Professional Visit": "blue",
    "Check-in": "purple",
    "Check-out": "purple",
    "Seasonal Preparation": "orange",
    "Owner Meeting": "blue",
    "Other": "grey",
}
CALENDAR_EVENT_COLOR_BY_STATUS = {
    "COMPLETED": "dark-green",
    "CANCELLED": "grey",
    "BLOCKED": "grey",
}

OPERATIONS_NOTIFICATION_EVENT_VALUES = {
    "notification_sent",
    "notification_failed",
    "overdue_detected",
    "daily_overdue_report_sent",
    "daily_overdue_report_failed",
}

OPERATIONS_NOTIFICATION_CHANNEL_VALUES = {
    "EMAIL",
    "TELEGRAM",
    "SYSTEM",
}

OPERATIONS_TASK_SOURCE_TYPES = (
    "PILOT_REQUEST",
    "OWNER_REGISTRATION",
    "PROFESSIONAL_APPLICATION",
    "PARTNER_APPLICATION",
    "CONCIERGE_REQUEST",
    "SERVICE_REQUEST",
    "OWNER_SERVICE_REQUEST",
    "RESERVATION",
)
OPERATIONS_TASK_CHECKLIST_ITEMS = (
    ("cleaning", "Cleaning"),
    ("inspection", "Inspection"),
    ("keys", "Keys"),
    ("welcome_pack", "Welcome Pack"),
    ("photos", "Photos"),
    ("utilities", "Utilities"),
    ("wifi", "Wi-Fi"),
    ("parking", "Parking"),
    ("inventory", "Inventory"),
)
OPERATIONS_TASK_BOARD_STATUSES = (
    "NEW",
    "ASSIGNED",
    "ACCEPTED",
    "ON_THE_WAY",
    "ARRIVED",
    "IN_PROGRESS",
    "PAUSED",
    "WAITING_OWNER",
    "WAITING_OPERATIONS",
    "COMPLETED",
    "ARCHIVED",
)
OPERATIONS_TASK_STATUS_LABELS = {
    "NEW": "New",
    "ASSIGNED": "Assigned",
    "ACCEPTED": "Accepted",
    "ON_THE_WAY": "On the Way",
    "ARRIVED": "Arrived",
    "IN_PROGRESS": "In Progress",
    "PAUSED": "Paused",
    "WAITING_OWNER": "Waiting Owner",
    "WAITING_OPERATIONS": "Waiting Operations",
    "COMPLETED": "Completed",
    "ARCHIVED": "Archived",
}
OPERATIONS_TASK_STATUS_TONES = {
    "NEW": "new",
    "ASSIGNED": "assigned",
    "ACCEPTED": "assigned",
    "ON_THE_WAY": "in-progress",
    "ARRIVED": "in-progress",
    "IN_PROGRESS": "in-progress",
    "PAUSED": "waiting-provider",
    "WAITING_OWNER": "waiting-owner",
    "WAITING_OPERATIONS": "waiting-provider",
    "COMPLETED": "done",
    "ARCHIVED": "archived",
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


def _normalize_operations_task_status(status):
    normalized = str(status or "").strip().lower()
    normalized = OPERATIONS_TASK_STATUS_ALIASES.get(normalized, normalized.upper())
    return normalized if normalized in OPERATIONS_TASK_STATUS_VALUES else "NEW"


def _normalize_operations_task_priority(priority):
    normalized = str(priority or "").strip().lower()
    normalized = OPERATIONS_TASK_PRIORITY_ALIASES.get(normalized, normalized.upper())
    return normalized if normalized in OPERATIONS_TASK_PRIORITY_VALUES else "NORMAL"


def _normalize_operations_task_checklist(checklist_value):
    checklist = {}
    if isinstance(checklist_value, str):
        raw_value = checklist_value.strip()
        if not raw_value:
            return {key: False for key, _ in OPERATIONS_TASK_CHECKLIST_ITEMS}
        try:
            checklist_value = json.loads(raw_value)
        except json.JSONDecodeError:
            checklist_value = {}

    if isinstance(checklist_value, list):
        for item in checklist_value:
            if isinstance(item, dict):
                key = str(item.get("key", "")).strip()
                if key:
                    checklist[key] = bool(item.get("checked"))
            elif isinstance(item, str):
                checklist[item.strip()] = True
    elif isinstance(checklist_value, dict):
        for key, value in checklist_value.items():
            normalized_key = str(key or "").strip()
            if normalized_key:
                checklist[normalized_key] = bool(value)

    normalized_checklist = {}
    for key, _label in OPERATIONS_TASK_CHECKLIST_ITEMS:
        normalized_checklist[key] = bool(checklist.get(key, False))
    return normalized_checklist


def _operations_task_checklist_items(checklist_value=None):
    normalized = _normalize_operations_task_checklist(checklist_value)
    return [
        {
            "key": key,
            "label": label,
            "checked": bool(normalized.get(key, False)),
        }
        for key, label in OPERATIONS_TASK_CHECKLIST_ITEMS
    ]


def _operations_task_comments(comments_value):
    if isinstance(comments_value, str):
        raw_value = comments_value.strip()
        if not raw_value:
            return []
        try:
            comments_value = json.loads(raw_value)
        except json.JSONDecodeError:
            comments_value = []

    if not isinstance(comments_value, list):
        return []

    comments = []
    for item in comments_value:
        if not isinstance(item, dict):
            continue
        comments.append({
            "created_at": str(item.get("created_at", "")).strip(),
            "operator": str(item.get("operator", "")).strip(),
            "comment": str(item.get("comment", "")).strip(),
            "type": str(item.get("type", "General")).strip() or "General",
            "visibility": str(item.get("visibility", "internal")).strip() or "internal",
            "author_role": str(item.get("author_role", "")).strip(),
        })
    comments.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return comments


def _operations_task_attachments(attachments_value):
    if isinstance(attachments_value, str):
        raw_value = attachments_value.strip()
        if not raw_value:
            return []
        try:
            attachments_value = json.loads(raw_value)
        except json.JSONDecodeError:
            attachments_value = []

    if not isinstance(attachments_value, list):
        return []

    attachments = []
    for item in attachments_value:
        if not isinstance(item, dict):
            continue
        attachments.append({
            "created_at": str(item.get("created_at", "")).strip(),
            "name": str(item.get("name", "")).strip(),
            "url": str(item.get("url", "")).strip(),
            "uploaded_by": str(item.get("uploaded_by", "")).strip(),
            "category": str(item.get("category", "")).strip(),
            "slot": str(item.get("slot", "")).strip(),
            "mime_type": str(item.get("mime_type", "")).strip(),
        })
    attachments.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return attachments


def _operations_task_completion_report(report_value):
    if isinstance(report_value, str):
        raw_value = report_value.strip()
        if not raw_value:
            return {
                "completed_work": "",
                "materials_used": "",
                "time_spent_minutes": "",
                "recommendations": "",
                "follow_up_needed": "",
                "notes": "",
            }
        try:
            report_value = json.loads(raw_value)
        except json.JSONDecodeError:
            report_value = {}

    if not isinstance(report_value, dict):
        report_value = {}

    return {
        "completed_work": str(report_value.get("completed_work", "")).strip(),
        "materials_used": str(report_value.get("materials_used", "")).strip(),
        "time_spent_minutes": str(report_value.get("time_spent_minutes", "")).strip(),
        "recommendations": str(report_value.get("recommendations", "")).strip(),
        "follow_up_needed": str(report_value.get("follow_up_needed", "")).strip(),
        "notes": str(report_value.get("notes", "")).strip(),
    }


def _service_request_status_to_operations_status(status):
    normalized = _normalize_service_request_status(status)
    return {
        "new": "NEW",
        "assigned": "ASSIGNED",
        "in_progress": "IN_PROGRESS",
        "completed": "COMPLETED",
        "cancelled": "ARCHIVED",
    }.get(normalized, "NEW")


def _operations_status_to_service_request_status(status):
    normalized = _normalize_operations_task_status(status)
    return {
        "NEW": "new",
        "ASSIGNED": "assigned",
        "ACCEPTED": "in_progress",
        "ON_THE_WAY": "in_progress",
        "ARRIVED": "in_progress",
        "IN_PROGRESS": "in_progress",
        "PAUSED": "in_progress",
        "WAITING_OWNER": "in_progress",
        "WAITING_OPERATIONS": "in_progress",
        "COMPLETED": "completed",
        "ARCHIVED": "cancelled",
    }.get(normalized, "new")


def _operations_task_status_label(status):
    normalized = _normalize_operations_task_status(status)
    return OPERATIONS_TASK_STATUS_LABELS.get(normalized, normalized.replace("_", " ").title())


def _operations_task_board_status_label(status):
    return _operations_task_status_label(status)


def _operations_task_status_tone(status):
    normalized = _normalize_operations_task_status(status)
    return OPERATIONS_TASK_STATUS_TONES.get(normalized, "new")


def _operations_task_priority_label(priority):
    return _normalize_operations_task_priority(priority).title()


def _operations_task_priority_tone(priority):
    normalized = _normalize_operations_task_priority(priority)
    if normalized == "URGENT":
        return "urgent"
    if normalized == "HIGH":
        return "high"
    if normalized == "LOW":
        return "low"
    return "normal"


def _operations_task_status_event(status):
    normalized = _normalize_operations_task_status(status)
    return {
        "NEW": ("status_changed", "Status changed to New"),
        "ASSIGNED": ("assigned", "Assigned"),
        "ACCEPTED": ("status_changed", "Status changed to Accepted"),
        "ON_THE_WAY": ("status_changed", "Status changed to On the way"),
        "ARRIVED": ("status_changed", "Status changed to Arrived"),
        "IN_PROGRESS": ("status_changed", "Status changed to In progress"),
        "PAUSED": ("status_changed", "Status changed to Paused"),
        "WAITING_OWNER": ("status_changed", "Status changed to Waiting owner"),
        "WAITING_OPERATIONS": ("status_changed", "Status changed to Waiting operations"),
        "COMPLETED": ("completed", "Completed"),
        "ARCHIVED": ("status_changed", "Status changed to Archived"),
    }.get(normalized, ("task_created", "Task created"))


def _operations_task_priority_from_request(record):
    urgency = str((record or {}).get("urgency", "")).strip().lower()
    preferred_date = str((record or {}).get("preferred_date", "")).strip()
    created_at = _parse_iso_datetime(str((record or {}).get("created_at", "")).strip())
    preferred_dt = None
    if preferred_date:
        try:
            preferred_dt = datetime.fromisoformat(preferred_date)
        except ValueError:
            preferred_dt = None

    if urgency in {"urgent", "emergency", "asap"}:
        return "URGENT"
    if urgency in {"high", "priority"}:
        return "HIGH"
    if preferred_dt and preferred_dt.date() <= datetime.now(timezone.utc).date():
        return "HIGH"
    if created_at and datetime.now(timezone.utc) - created_at > timedelta(days=7):
        return "HIGH"
    if _normalize_service_request_status((record or {}).get("status", "new")) in {"completed", "cancelled"}:
        return "LOW"
    return "NORMAL"


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


def _normalize_owner_property_status(status):
    normalized = str(status or "").strip().upper()
    return normalized if normalized in OWNER_PROPERTY_STATUS_VALUES else OWNER_PROPERTY_STATUS_DEFAULT


def _normalize_owner_property_checklist_value(value):
    if isinstance(value, bool):
        return 1 if value else 0
    normalized = str(value or "").strip().lower()
    return 1 if normalized in {"1", "true", "yes", "on", "checked"} else 0


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


def _ensure_owner_property_schema(conn):
    existing_columns = _owner_table_columns(conn, "owner_properties")
    required_columns = {
        "status": f"TEXT NOT NULL DEFAULT '{OWNER_PROPERTY_STATUS_DEFAULT}'",
        "guest_guide_ready": "INTEGER NOT NULL DEFAULT 0",
        "access_instructions_ready": "INTEGER NOT NULL DEFAULT 0",
        "emergency_contact_ready": "INTEGER NOT NULL DEFAULT 0",
        "cleaning_partner_ready": "INTEGER NOT NULL DEFAULT 0",
        "admin_notes": "TEXT NOT NULL DEFAULT ''",
    }
    for column_name, column_sql in required_columns.items():
        if column_name not in existing_columns:
            conn.execute(f"ALTER TABLE owner_properties ADD COLUMN {column_name} {column_sql}")


def _ensure_owner_property_activity_schema(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS owner_property_activity_events (
            sequence INTEGER PRIMARY KEY AUTOINCREMENT,
            id TEXT NOT NULL UNIQUE,
            property_id TEXT NOT NULL,
            owner_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            event_type TEXT NOT NULL,
            title TEXT NOT NULL,
            detail TEXT NOT NULL DEFAULT ''
        )
        """
    )


def _ensure_operations_task_schema(conn):
    existing_columns = _owner_table_columns(conn, "operations_tasks")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS operations_tasks (
                id TEXT PRIMARY KEY,
                request_id TEXT NOT NULL DEFAULT '',
                source_type TEXT NOT NULL DEFAULT '',
                source_id TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                title TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT '',
                owner_name TEXT NOT NULL DEFAULT '',
                owner_email TEXT NOT NULL DEFAULT '',
                property_id TEXT NOT NULL DEFAULT '',
                property_name TEXT NOT NULL DEFAULT '',
                assigned_to TEXT NOT NULL DEFAULT '',
                assigned_professional_id TEXT NOT NULL DEFAULT '',
                due_date TEXT NOT NULL DEFAULT '',
                priority TEXT NOT NULL DEFAULT 'NORMAL',
                status TEXT NOT NULL DEFAULT 'NEW',
            notes TEXT NOT NULL DEFAULT '',
            completed_at TEXT NOT NULL DEFAULT '',
            completion_report_json TEXT NOT NULL DEFAULT '',
            owner_id TEXT NOT NULL DEFAULT '',
            property_location TEXT NOT NULL DEFAULT '',
            admin_notes TEXT NOT NULL DEFAULT '',
            request_status TEXT NOT NULL DEFAULT 'new',
            checklist_json TEXT NOT NULL DEFAULT '',
            attachments_json TEXT NOT NULL DEFAULT '',
            comments_json TEXT NOT NULL DEFAULT ''
        )
        """
    )
    existing_columns = _owner_table_columns(conn, "operations_tasks")
    required_columns = {
        "id": "TEXT NOT NULL DEFAULT ''",
        "request_id": "TEXT NOT NULL DEFAULT ''",
        "source_type": "TEXT NOT NULL DEFAULT ''",
        "source_id": "TEXT NOT NULL DEFAULT ''",
        "created_at": "TEXT NOT NULL DEFAULT ''",
        "updated_at": "TEXT NOT NULL DEFAULT ''",
        "title": "TEXT NOT NULL DEFAULT ''",
        "category": "TEXT NOT NULL DEFAULT ''",
        "owner_name": "TEXT NOT NULL DEFAULT ''",
        "owner_email": "TEXT NOT NULL DEFAULT ''",
        "property_id": "TEXT NOT NULL DEFAULT ''",
        "property_name": "TEXT NOT NULL DEFAULT ''",
        "assigned_to": "TEXT NOT NULL DEFAULT ''",
        "assigned_professional_id": "TEXT NOT NULL DEFAULT ''",
        "priority": "TEXT NOT NULL DEFAULT 'NORMAL'",
        "status": "TEXT NOT NULL DEFAULT 'NEW'",
        "due_date": "TEXT NOT NULL DEFAULT ''",
        "notes": "TEXT NOT NULL DEFAULT ''",
        "completed_at": "TEXT NOT NULL DEFAULT ''",
        "completion_report_json": "TEXT NOT NULL DEFAULT ''",
        "owner_id": "TEXT NOT NULL DEFAULT ''",
        "property_location": "TEXT NOT NULL DEFAULT ''",
        "admin_notes": "TEXT NOT NULL DEFAULT ''",
        "request_status": "TEXT NOT NULL DEFAULT 'new'",
        "checklist_json": "TEXT NOT NULL DEFAULT ''",
        "attachments_json": "TEXT NOT NULL DEFAULT ''",
        "comments_json": "TEXT NOT NULL DEFAULT ''",
    }
    for column_name, column_sql in required_columns.items():
        if column_name not in existing_columns:
            conn.execute(f"ALTER TABLE operations_tasks ADD COLUMN {column_name} {column_sql}")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS operations_task_events (
            sequence INTEGER PRIMARY KEY AUTOINCREMENT,
            id TEXT NOT NULL UNIQUE,
            task_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            event_type TEXT NOT NULL,
            title TEXT NOT NULL,
            detail TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'NEW'
        )
        """
    )
    _ensure_operations_notification_schema(conn)


def _ensure_operations_notification_schema(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS operations_notifications (
            sequence INTEGER PRIMARY KEY AUTOINCREMENT,
            id TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            event_type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT '',
            title TEXT NOT NULL,
            detail TEXT NOT NULL DEFAULT '',
            task_id TEXT NOT NULL DEFAULT '',
            source_type TEXT NOT NULL DEFAULT '',
            source_id TEXT NOT NULL DEFAULT '',
            channel TEXT NOT NULL DEFAULT '',
            recipient TEXT NOT NULL DEFAULT '',
            operator_key TEXT NOT NULL DEFAULT '',
            metadata TEXT NOT NULL DEFAULT ''
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS operations_notification_preferences (
            operator_key TEXT PRIMARY KEY,
            operator_name TEXT NOT NULL DEFAULT '',
            email_enabled INTEGER NOT NULL DEFAULT 1,
            telegram_enabled INTEGER NOT NULL DEFAULT 1,
            updated_at TEXT NOT NULL
        )
        """
    )


def _ensure_calendar_event_schema(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS calendar_events (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            property_id TEXT NOT NULL DEFAULT '',
            owner_id TEXT NOT NULL DEFAULT '',
            operation_task_id TEXT NOT NULL DEFAULT '',
            event_type TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            start_datetime TEXT NOT NULL,
            end_datetime TEXT NOT NULL,
            all_day INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'SCHEDULED',
            assigned_professional TEXT NOT NULL DEFAULT '',
            created_by TEXT NOT NULL DEFAULT '',
            color TEXT NOT NULL DEFAULT 'grey',
            metadata_json TEXT NOT NULL DEFAULT '{}'
        )
        """
    )


def _normalize_calendar_event_type(event_type):
    normalized = str(event_type or "").strip()
    if not normalized:
        return "Other"
    lookup_key = normalized.lower().replace("_", " ").replace("-", " ")
    canonical = CALENDAR_EVENT_TYPE_ALIASES.get(lookup_key)
    if canonical:
        return canonical
    if normalized in CALENDAR_EVENT_TYPE_VALUES:
        return normalized
    title_case = normalized.title()
    return title_case if title_case in CALENDAR_EVENT_TYPE_VALUES else "Other"


def _normalize_calendar_event_status(status):
    normalized = str(status or "").strip().upper()
    if not normalized:
        return "SCHEDULED"
    aliases = {
        "NEW": "SCHEDULED",
        "ASSIGNED": "SCHEDULED",
        "WAITING_OWNER": "SCHEDULED",
        "WAITING_OPERATIONS": "IN_PROGRESS",
        "WAITING_PROVIDER": "IN_PROGRESS",
        "ACCEPTED": "IN_PROGRESS",
        "ON_THE_WAY": "IN_PROGRESS",
        "ARRIVED": "IN_PROGRESS",
        "PAUSED": "IN_PROGRESS",
        "DONE": "COMPLETED",
        "COMPLETED": "COMPLETED",
        "ARCHIVED": "CANCELLED",
        "INPROGRESS": "IN_PROGRESS",
        "IN-PROGRESS": "IN_PROGRESS",
    }
    normalized = aliases.get(normalized, normalized)
    return normalized if normalized in CALENDAR_EVENT_STATUS_VALUES else "SCHEDULED"


def _calendar_event_color(event_type, status):
    normalized_status = _normalize_calendar_event_status(status)
    if normalized_status in CALENDAR_EVENT_COLOR_BY_STATUS:
        return CALENDAR_EVENT_COLOR_BY_STATUS[normalized_status]
    normalized_type = _normalize_calendar_event_type(event_type)
    return CALENDAR_EVENT_COLOR_BY_TYPE.get(normalized_type, "grey")


def _calendar_parse_datetime(value):
    raw_value = str(value or "").strip()
    if not raw_value:
        return None, False
    try:
        if len(raw_value) == 10:
            parsed = datetime.fromisoformat(raw_value).replace(tzinfo=timezone.utc)
            return parsed, True
        parsed = datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc), False
    except ValueError:
        return None, False


def _calendar_event_bounds(start_value, end_value="", all_day=False):
    start_dt, start_all_day = _calendar_parse_datetime(start_value)
    end_dt, end_all_day = _calendar_parse_datetime(end_value)
    if start_dt is None:
        start_dt = datetime.now(timezone.utc)
    if all_day or start_all_day or end_all_day:
        start_dt = start_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        if end_dt is None or end_dt.date() < start_dt.date():
            end_dt = start_dt + timedelta(days=1) - timedelta(seconds=1)
        else:
            end_dt = end_dt.replace(hour=23, minute=59, second=59, microsecond=0)
        return start_dt.isoformat(), end_dt.isoformat(), True
    if end_dt is None or end_dt < start_dt:
        end_dt = start_dt + timedelta(hours=1)
    return start_dt.isoformat(), end_dt.isoformat(), False


def _calendar_task_event_type(task_record):
    task = task_record or {}
    category = str(task.get("category", "")).strip()
    source_type = str(task.get("source_type", "")).strip().upper()
    title = str(task.get("title", "")).strip().lower()
    notes = str(task.get("notes", "")).strip().lower()
    property_name = str(task.get("property_name", "")).strip()
    category_map = {
        "SERVICE": "Other",
        "LEAD": "Professional Visit",
        "OWNER": "Owner Meeting",
        "PROFESSIONAL": "Professional Visit",
        "PARTNER": "Professional Visit",
        "CONCIERGE": "Concierge",
    }
    if source_type in {"SERVICE_REQUEST", "OWNER_SERVICE_REQUEST"}:
        service_category = str(task.get("category", "")).strip() or str(task.get("title", "")).strip()
        normalized = _normalize_calendar_event_type(service_category)
        if normalized != "Other":
            return normalized
    if "check in" in title or "check-in" in title or "arrival" in title:
        return "Check-in"
    if "check out" in title or "check-out" in title or "departure" in title:
        return "Check-out"
    if "clean" in title or "clean" in notes:
        return "Cleaning"
    if "inspect" in title or "inspection" in notes:
        return "Inspection"
    if "maint" in title or "maint" in notes:
        return "Maintenance"
    if property_name and category in category_map:
        return category_map.get(category, "Other")
    return _normalize_calendar_event_type(category or task.get("title", "") or task.get("source_type", "Other"))


def _calendar_task_status(task_record):
    status = _normalize_operations_task_status((task_record or {}).get("status", "NEW"))
    status_map = {
        "NEW": "SCHEDULED",
        "ASSIGNED": "SCHEDULED",
        "ACCEPTED": "IN_PROGRESS",
        "ON_THE_WAY": "IN_PROGRESS",
        "ARRIVED": "IN_PROGRESS",
        "IN_PROGRESS": "IN_PROGRESS",
        "PAUSED": "IN_PROGRESS",
        "WAITING_OWNER": "SCHEDULED",
        "WAITING_OPERATIONS": "IN_PROGRESS",
        "WAITING_PROVIDER": "IN_PROGRESS",
        "DONE": "COMPLETED",
        "COMPLETED": "COMPLETED",
        "ARCHIVED": "CANCELLED",
    }
    return status_map.get(status, "SCHEDULED")


def _calendar_event_payload_from_task(task_record):
    task = task_record or {}
    task_id = str(task.get("id", "")).strip()
    if not task_id:
        return None

    event_type = _calendar_task_event_type(task)
    status = _calendar_task_status(task)
    due_date = str(task.get("due_date", "")).strip()
    created_at = str(task.get("created_at", "")).strip()
    updated_at = str(task.get("updated_at", "")).strip() or _utc_now_iso()
    start_source = due_date or created_at or updated_at
    start_datetime, end_datetime, all_day = _calendar_event_bounds(start_source, task.get("completed_at", ""), due_date and len(due_date) == 10)
    metadata = {
        "source": "operations_task",
        "source_type": str(task.get("source_type", "")).strip(),
        "task_status": str(task.get("status", "")).strip(),
        "priority": str(task.get("priority", "")).strip(),
        "request_status": str(task.get("request_status", "")).strip(),
        "property_name": str(task.get("property_name", "")).strip(),
        "property_location": str(task.get("property_location", "")).strip(),
        "owner_name": str(task.get("owner_name", "")).strip(),
        "owner_email": str(task.get("owner_email", "")).strip(),
    }
    return {
        "id": task_id,
        "created_at": created_at or updated_at,
        "updated_at": updated_at,
        "property_id": str(task.get("property_id", "")).strip(),
        "owner_id": str(task.get("owner_id", "")).strip(),
        "operation_task_id": task_id,
        "event_type": event_type,
        "title": str(task.get("title", "")).strip() or event_type,
        "description": str(task.get("notes", "")).strip() or str(task.get("admin_notes", "")).strip(),
        "start_datetime": start_datetime,
        "end_datetime": end_datetime,
        "all_day": all_day,
        "status": status,
        "assigned_professional": str(task.get("assigned_to", "")).strip(),
        "created_by": "system:operations",
        "color": _calendar_event_color(event_type, status),
        "metadata_json": json.dumps(metadata, ensure_ascii=False, separators=(",", ":")),
    }


def _calendar_event_payload_from_owner_form(owner_account, property_record, form_values):
    owner_account = owner_account or {}
    property_record = property_record or {}
    event_type = _normalize_calendar_event_type(form_values.get("event_type", ""))
    if event_type not in CALENDAR_OWNER_EVENT_TYPES:
        return None

    title = str(form_values.get("title", "")).strip() or event_type
    description = str(form_values.get("description", "")).strip()
    all_day = bool(form_values.get("all_day"))
    start_datetime, end_datetime, all_day = _calendar_event_bounds(
        form_values.get("start_datetime", ""),
        form_values.get("end_datetime", ""),
        all_day,
    )
    status = "BLOCKED" if event_type == "Blocked Dates" else "SCHEDULED"
    metadata = {
        "source": "owner_calendar",
        "property_name": str(property_record.get("name", "")).strip(),
        "property_location": str(property_record.get("location", "")).strip(),
        "owner_name": str(owner_account.get("full_name", "")).strip(),
        "owner_email": str(owner_account.get("email", "")).strip(),
    }
    return {
        "id": uuid4().hex,
        "created_at": _utc_now_iso(),
        "updated_at": _utc_now_iso(),
        "property_id": str(property_record.get("id", "")).strip(),
        "owner_id": str(owner_account.get("id", "")).strip(),
        "operation_task_id": "",
        "event_type": event_type,
        "title": title,
        "description": description,
        "start_datetime": start_datetime,
        "end_datetime": end_datetime,
        "all_day": all_day,
        "status": status,
        "assigned_professional": "",
        "created_by": f"owner:{str(owner_account.get('id', '')).strip()}",
        "color": _calendar_event_color(event_type, status),
        "metadata_json": json.dumps(metadata, ensure_ascii=False, separators=(",", ":")),
    }


def _calendar_event_from_row(row):
    if row is None:
        return None

    metadata_json = str(row["metadata_json"]) if "metadata_json" in row.keys() else ""
    try:
        metadata = json.loads(metadata_json) if metadata_json else {}
    except json.JSONDecodeError:
        metadata = {}

    return {
        "id": str(row["id"]),
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
        "property_id": str(row["property_id"]) if "property_id" in row.keys() else "",
        "owner_id": str(row["owner_id"]) if "owner_id" in row.keys() else "",
        "operation_task_id": str(row["operation_task_id"]) if "operation_task_id" in row.keys() else "",
        "event_type": _normalize_calendar_event_type(row["event_type"] if "event_type" in row.keys() else "Other"),
        "title": str(row["title"]),
        "description": str(row["description"]) if "description" in row.keys() else "",
        "start_datetime": str(row["start_datetime"]) if "start_datetime" in row.keys() else "",
        "end_datetime": str(row["end_datetime"]) if "end_datetime" in row.keys() else "",
        "all_day": bool(int(row["all_day"] or 0)) if "all_day" in row.keys() else False,
        "status": _normalize_calendar_event_status(row["status"] if "status" in row.keys() else "SCHEDULED"),
        "assigned_professional": str(row["assigned_professional"]) if "assigned_professional" in row.keys() else "",
        "created_by": str(row["created_by"]) if "created_by" in row.keys() else "",
        "color": str(row["color"]) if "color" in row.keys() and str(row["color"]).strip() else _calendar_event_color(row["event_type"], row["status"]),
        "metadata_json": metadata_json or "{}",
        "metadata": metadata,
    }


def _persist_calendar_event(conn, payload):
    if not payload:
        return None

    conn.execute(
        """
        INSERT INTO calendar_events (
            id, created_at, updated_at, property_id, owner_id, operation_task_id, event_type, title, description,
            start_datetime, end_datetime, all_day, status, assigned_professional, created_by, color, metadata_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            created_at = excluded.created_at,
            updated_at = excluded.updated_at,
            property_id = excluded.property_id,
            owner_id = excluded.owner_id,
            operation_task_id = excluded.operation_task_id,
            event_type = excluded.event_type,
            title = excluded.title,
            description = excluded.description,
            start_datetime = excluded.start_datetime,
            end_datetime = excluded.end_datetime,
            all_day = excluded.all_day,
            status = excluded.status,
            assigned_professional = excluded.assigned_professional,
            created_by = excluded.created_by,
            color = excluded.color,
            metadata_json = excluded.metadata_json
        """,
        (
            payload["id"],
            payload["created_at"],
            payload["updated_at"],
            payload["property_id"],
            payload["owner_id"],
            payload["operation_task_id"],
            payload["event_type"],
            payload["title"],
            payload["description"],
            payload["start_datetime"],
            payload["end_datetime"],
            1 if payload["all_day"] else 0,
            payload["status"],
            payload["assigned_professional"],
            payload["created_by"],
            payload["color"],
            payload["metadata_json"],
        ),
    )
    return payload


def _upsert_calendar_event_from_task(task_record):
    payload = _calendar_event_payload_from_task(task_record)
    if not payload:
        return None

    try:
        with _owner_db_connection() as conn:
            _ensure_owner_db_schema(conn)
            _migrate_owner_jsonl_backups(conn)
            _persist_calendar_event(conn, payload)
    except Exception as exc:
        app.logger.warning("Calendar event sync failed for task %s: %s", str((task_record or {}).get("id", "")).strip(), type(exc).__name__)
        return None
    return payload


def _create_calendar_event_from_owner(owner_account, property_record, form_values):
    payload = _calendar_event_payload_from_owner_form(owner_account, property_record, form_values)
    if not payload:
        return None

    try:
        with _owner_db_connection() as conn:
            _ensure_owner_db_schema(conn)
            _migrate_owner_jsonl_backups(conn)
            _persist_calendar_event(conn, payload)
    except Exception as exc:
        app.logger.warning("Owner calendar event creation failed for %s: %s", payload.get("id", ""), type(exc).__name__)
        return None
    return payload


def _load_calendar_events(*, owner_id=None, property_ids=None):
    with _owner_db_connection() as conn:
        _ensure_owner_db_schema(conn)
        _migrate_owner_jsonl_backups(conn)
        rows = conn.execute(
            """
            SELECT id, created_at, updated_at, property_id, owner_id, operation_task_id, event_type, title, description,
                   start_datetime, end_datetime, all_day, status, assigned_professional, created_by, color, metadata_json
            FROM calendar_events
            ORDER BY start_datetime ASC, end_datetime ASC, updated_at DESC, id ASC
            """
        ).fetchall()

    events = [_calendar_event_from_row(row) for row in rows]
    events.extend(_demo_records("calendar_events"))
    if owner_id is not None:
        target_owner_id = str(owner_id or "").strip()
        events = [
            event
            for event in events
            if str(event.get("owner_id", "")).strip() == target_owner_id
            or (target_owner_id and str(event.get("metadata", {}).get("owner_id", "")).strip() == target_owner_id)
        ]
    if property_ids is not None:
        allowed_ids = {str(property_id).strip() for property_id in property_ids if str(property_id).strip()}
        events = [event for event in events if not allowed_ids or str(event.get("property_id", "")).strip() in allowed_ids]
    events.sort(key=_calendar_event_sort_key)
    return events


def _normalize_reservation_status(status):
    normalized = str(status or "").strip().lower()
    normalized = RESERVATION_STATUS_ALIASES.get(normalized, normalized.upper())
    return normalized if normalized in RESERVATION_STATUS_VALUES else "PENDING"


def _normalize_reservation_source(source):
    normalized = str(source or "").strip()
    if not normalized:
        return "Manual"
    lookup = RESERVATION_SOURCE_ALIASES.get(normalized.lower())
    if lookup:
        return lookup
    return normalized if normalized in RESERVATION_SOURCE_VALUES else "Manual"


def _normalize_reservation_channel_status(status):
    normalized = str(status or "").strip().upper()
    if not normalized:
        return "SYNCED"
    aliases = {
        "MANUAL": "MANUAL",
        "PENDING": "PENDING",
        "SYNCING": "SYNCING",
        "SYNCED": "SYNCED",
        "FAILED": "FAILED",
        "ERROR": "FAILED",
        "ARCHIVED": "ARCHIVED",
        "UNKNOWN": "UNKNOWN",
    }
    return aliases.get(normalized, normalized if normalized in {"MANUAL", "PENDING", "SYNCING", "SYNCED", "FAILED", "ARCHIVED", "UNKNOWN"} else "SYNCED")


def _reservation_status_label(status):
    return _normalize_reservation_status(status).replace("_", " ").title()


def _reservation_status_tone(status):
    normalized = _normalize_reservation_status(status)
    if normalized in {"CONFIRMED", "CHECKED_IN"}:
        return "success"
    if normalized == "PENDING":
        return "warning"
    if normalized in {"CANCELLED", "NO_SHOW"}:
        return "danger"
    if normalized == "CHECKED_OUT":
        return "neutral"
    return "info"


def _reservation_calendar_status(status, *, kind="reservation"):
    normalized_status = _normalize_reservation_status(status)
    if kind == "blocked_dates":
        return "BLOCKED"
    if normalized_status in {"CHECKED_IN"}:
        return "IN_PROGRESS"
    if normalized_status in {"CHECKED_OUT"}:
        return "COMPLETED"
    if normalized_status in {"CANCELLED", "NO_SHOW"}:
        return "CANCELLED"
    return "SCHEDULED"


def _reservation_event_type(metadata=None):
    metadata = metadata or {}
    if str(metadata.get("kind", "")).strip() == "blocked_dates":
        return "Blocked Dates"
    return "Reservation"


def _reservation_guest_name(reservation):
    first_name = str((reservation or {}).get("guest_first_name", "")).strip()
    last_name = str((reservation or {}).get("guest_last_name", "")).strip()
    return " ".join(part for part in [first_name, last_name] if part).strip()


def _safe_json_loads(value, default=None):
    if default is None:
        default = {}
    text = str(value or "").strip()
    if not text:
        return default
    try:
        return json.loads(text)
    except (TypeError, json.JSONDecodeError):
        return default


def _reservation_metadata_from_row(row):
    metadata_json = str(row["metadata_json"]) if row and "metadata_json" in row.keys() else ""
    return _safe_json_loads(metadata_json, {})


def _reservation_external_payload_from_row(row):
    if row is None:
        return {}
    if "external_payload" in row.keys():
        payload = _safe_json_loads(str(row["external_payload"]), {})
        if payload:
            return payload
    return _safe_json_loads(str(row["source_metadata_json"]) if "source_metadata_json" in row.keys() else "", {})


def _reservation_channel_name_from_row(row, reservation_source):
    if row is not None and "channel_name" in row.keys():
        return _normalize_reservation_source(row["channel_name"])
    return _normalize_reservation_source(reservation_source)


def _reservation_channel_status_from_row(row):
    if row is not None and "channel_status" in row.keys():
        return _normalize_reservation_channel_status(row["channel_status"])
    if row is not None and "sync_status" in row.keys():
        return _normalize_reservation_channel_status(row["sync_status"])
    return "SYNCED"


def _reservation_from_row(row):
    if row is None:
        return None

    metadata = _reservation_metadata_from_row(row)
    reservation_source = _normalize_reservation_source(row["reservation_source"] if "reservation_source" in row.keys() else "Manual")
    reservation_reference = str(row["reservation_reference"]) if "reservation_reference" in row.keys() else ""
    if not reservation_reference:
        reservation_reference = str(row["external_reference"]) if "external_reference" in row.keys() else ""
    last_sync = str(row["last_sync"]) if "last_sync" in row.keys() else ""
    if not last_sync:
        last_sync = str(row["external_last_sync"]) if "external_last_sync" in row.keys() else ""
    external_payload = _reservation_external_payload_from_row(row)
    return {
        "id": str(row["id"]),
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
        "property_id": str(row["property_id"]) if "property_id" in row.keys() else "",
        "reservation_source": reservation_source,
        "reservation_reference": reservation_reference,
        "channel_name": _reservation_channel_name_from_row(row, reservation_source),
        "channel_status": _reservation_channel_status_from_row(row),
        "last_sync": last_sync,
        "external_payload": external_payload,
        "external_reference": reservation_reference,
        "external_last_sync": last_sync,
        "import_batch_id": str(row["import_batch_id"]) if "import_batch_id" in row.keys() else "",
        "sync_status": str(row["sync_status"]) if "sync_status" in row.keys() else "IDLE",
        "source_metadata_json": str(row["source_metadata_json"]) if "source_metadata_json" in row.keys() else json.dumps(external_payload, ensure_ascii=False, separators=(",", ":")) if external_payload else "{}",
        "guest_first_name": str(row["guest_first_name"]) if "guest_first_name" in row.keys() else "",
        "guest_last_name": str(row["guest_last_name"]) if "guest_last_name" in row.keys() else "",
        "guest_email": str(row["guest_email"]) if "guest_email" in row.keys() else "",
        "guest_phone": str(row["guest_phone"]) if "guest_phone" in row.keys() else "",
        "adults": int(row["adults"] or 0) if "adults" in row.keys() else 0,
        "children": int(row["children"] or 0) if "children" in row.keys() else 0,
        "infants": int(row["infants"] or 0) if "infants" in row.keys() else 0,
        "pets": int(row["pets"] or 0) if "pets" in row.keys() else 0,
        "arrival_datetime": str(row["arrival_datetime"]) if "arrival_datetime" in row.keys() else "",
        "departure_datetime": str(row["departure_datetime"]) if "departure_datetime" in row.keys() else "",
        "status": _normalize_reservation_status(row["status"] if "status" in row.keys() else "PENDING"),
        "notes": str(row["notes"]) if "notes" in row.keys() else "",
        "language": str(row["language"]) if "language" in row.keys() else "en",
        "created_by": str(row["created_by"]) if "created_by" in row.keys() else "",
        "metadata_json": str(row["metadata_json"]) if "metadata_json" in row.keys() else "{}",
        "metadata": metadata,
        "source_metadata": _safe_json_loads(str(row["source_metadata_json"])) if "source_metadata_json" in row.keys() else external_payload,
    }


def _load_reservations(*, owner_id=None, property_ids=None, filters=None):
    with _owner_db_connection() as conn:
        _ensure_owner_db_schema(conn)
        _migrate_owner_jsonl_backups(conn)
        rows = conn.execute(
            """
            SELECT id, created_at, updated_at, property_id, reservation_source, reservation_reference, channel_name,
                   channel_status, last_sync, external_payload, external_reference, guest_first_name, external_last_sync,
                   import_batch_id, sync_status, source_metadata_json, guest_last_name, guest_email, guest_phone, adults,
                   children, infants, pets, arrival_datetime, departure_datetime, status, notes, language, created_by,
                   metadata_json
            FROM reservations
            ORDER BY arrival_datetime ASC, updated_at DESC, id ASC
            """
        ).fetchall()

    reservations = [_reservation_from_row(row) for row in rows]
    reservations.extend(_demo_records("reservations"))
    property_map = {str(property_record.get("id", "")).strip(): property_record for property_record in _load_owner_properties()}
    owner_map = {str(account.get("id", "")).strip(): account for account in _load_owner_accounts()}
    enriched = []
    for reservation in reservations:
        property_record = property_map.get(str(reservation.get("property_id", "")).strip(), {})
        owner_account = owner_map.get(str(property_record.get("owner_id", "")).strip(), {})
        reservation_copy = {
            **reservation,
            "property_name": str(property_record.get("name", "")).strip(),
            "property_location": str(property_record.get("location", "")).strip(),
            "owner_id": str(property_record.get("owner_id", "")).strip(),
            "owner_name": str(owner_account.get("full_name", "")).strip(),
            "owner_email": str(owner_account.get("email", "")).strip(),
            "guest_name": _reservation_guest_name(reservation),
            "guest_label": _reservation_guest_name(reservation) or "Blocked dates",
            "property_label": str(property_record.get("name", "")).strip() or reservation.get("property_id", ""),
            "timeline": list(reversed(_reservation_timeline_events(reservation))),
            "comments": _reservation_comments(reservation, owner_view=False),
            "linked_operations": _reservation_linked_operations(reservation),
        }
        reservation_copy["calendar_event"] = _reservation_calendar_event(reservation_copy)
        reservation_copy["property_status"] = _reservation_property_status(property_record, reservations)
        enriched.append(reservation_copy)

    target_owner_id = str(owner_id or "").strip()
    if target_owner_id:
        enriched = [reservation for reservation in enriched if str(reservation.get("owner_id", "")).strip() == target_owner_id]

    allowed_ids = {str(property_id).strip() for property_id in (property_ids or []) if str(property_id).strip()}
    if allowed_ids:
        enriched = [reservation for reservation in enriched if str(reservation.get("property_id", "")).strip() in allowed_ids]

    filters = filters or {}
    property_filter = str(filters.get("property", "")).strip()
    owner_filter = str(filters.get("owner", "")).strip()
    guest_filter = str(filters.get("guest", "")).strip().lower()
    status_filter = _normalize_reservation_status(filters.get("status", "")) if str(filters.get("status", "")).strip() else ""
    source_filter = str(filters.get("source", "")).strip().lower()
    arrival_filter = str(filters.get("arrival", "")).strip()
    departure_filter = str(filters.get("departure", "")).strip()
    search = str(filters.get("search", "")).strip().lower()

    def _matches(reservation):
        if property_filter and property_filter not in {str(reservation.get("property_id", "")).strip(), str(reservation.get("property_name", "")).strip()}:
            return False
        if owner_filter and owner_filter not in {str(reservation.get("owner_id", "")).strip(), str(reservation.get("owner_name", "")).strip()}:
            return False
        guest_name = str(reservation.get("guest_name", "")).strip().lower()
        if guest_filter and guest_filter not in guest_name:
            return False
        if status_filter and _normalize_reservation_status(reservation.get("status", "")) != status_filter:
            return False
        if source_filter and source_filter not in " ".join([
            str(reservation.get("reservation_source", "")).strip().lower(),
            str(reservation.get("channel_name", "")).strip().lower(),
        ]):
            return False
        if arrival_filter and not str(reservation.get("arrival_datetime", "")).startswith(arrival_filter):
            return False
        if departure_filter and not str(reservation.get("departure_datetime", "")).startswith(departure_filter):
            return False
        if search:
            haystack = " ".join([
                reservation.get("guest_name", ""),
                reservation.get("guest_email", ""),
                reservation.get("property_name", ""),
                reservation.get("property_location", ""),
                reservation.get("reservation_source", ""),
                reservation.get("channel_name", ""),
                reservation.get("external_reference", ""),
                reservation.get("reservation_reference", ""),
                reservation.get("notes", ""),
            ]).lower()
            if search not in haystack:
                return False
        return True

    enriched = [reservation for reservation in enriched if _matches(reservation)]
    enriched.sort(key=lambda item: (str(item.get("arrival_datetime", "")), str(item.get("departure_datetime", "")), str(item.get("id", ""))))
    return enriched


def _find_reservation(reservation_id):
    target_id = str(reservation_id or "").strip()
    if not target_id:
        return None
    with _owner_db_connection() as conn:
        _ensure_owner_db_schema(conn)
        _migrate_owner_jsonl_backups(conn)
        row = conn.execute(
            """
            SELECT id, created_at, updated_at, property_id, reservation_source, reservation_reference, channel_name,
                   channel_status, last_sync, external_payload, external_reference, guest_first_name, external_last_sync,
                   import_batch_id, sync_status, source_metadata_json, guest_last_name, guest_email, guest_phone, adults,
                   children, infants, pets, arrival_datetime, departure_datetime, status, notes, language, created_by,
                   metadata_json
            FROM reservations
            WHERE id = ?
            """,
            (target_id,),
        ).fetchone()
    if row:
        return _reservation_from_row(row)
    return _demo_reservation_by_id(target_id)


def _reservation_status_timeline_title(status):
    normalized = _normalize_reservation_status(status)
    return {
        "PENDING": "Reservation created",
        "CONFIRMED": "Confirmed",
        "CHECKED_IN": "Guest checked in",
        "CHECKED_OUT": "Guest checked out",
        "CANCELLED": "Reservation cancelled",
        "NO_SHOW": "No show recorded",
    }.get(normalized, _reservation_status_label(normalized))


def _reservation_status_timeline_detail(status, reservation=None):
    reservation = reservation or {}
    normalized = _normalize_reservation_status(status)
    source = _normalize_reservation_source(reservation.get("reservation_source", "Manual"))
    reference = str(reservation.get("reservation_reference", reservation.get("external_reference", ""))).strip()
    parts = []
    if source:
        parts.append(source)
    if reference:
        parts.append(f"Ref {reference}")
    if normalized in {"CHECKED_IN", "CHECKED_OUT"}:
        arrival = str(reservation.get("arrival_datetime", "")).strip()
        departure = str(reservation.get("departure_datetime", "")).strip()
        if arrival:
            parts.append(f"Arrival {arrival}")
        if departure:
            parts.append(f"Departure {departure}")
    return " · ".join(part for part in parts if part)


def _reservation_seed_timeline_events(reservation):
    reservation = reservation or {}
    created_at = str(reservation.get("created_at", "")).strip()
    updated_at = str(reservation.get("updated_at", "")).strip() or created_at
    last_sync = str(reservation.get("last_sync", reservation.get("external_last_sync", ""))).strip()
    source = _normalize_reservation_source(reservation.get("reservation_source", "Manual"))
    status = _normalize_reservation_status(reservation.get("status", "PENDING"))
    metadata = reservation.get("metadata") if isinstance(reservation.get("metadata"), dict) else {}
    kind = str(metadata.get("kind", "reservation")).strip().lower() or "reservation"
    arrival_dt, _ = _calendar_parse_datetime(reservation.get("arrival_datetime", ""))
    departure_dt, _ = _calendar_parse_datetime(reservation.get("departure_datetime", ""))
    reference = str(reservation.get("reservation_reference", reservation.get("external_reference", ""))).strip()
    seed_events = []

    if created_at:
        seed_events.append({
            "type": "reservation_created" if kind != "blocked_dates" else "blocked_dates_created",
            "created_at": created_at,
            "title": "Reservation created" if kind != "blocked_dates" else "Blocked dates created",
            "detail": _reservation_status_timeline_detail(status, reservation),
            "status": status,
            "visibility": "public",
            "author": str(reservation.get("created_by", "")).strip() or "system",
        })

    if source and source != "Manual":
        seed_events.append({
            "type": "reservation_imported",
            "created_at": last_sync or updated_at or created_at,
            "title": f"Imported from {source}",
            "detail": reference or _reservation_status_timeline_detail(status, reservation),
            "status": status,
            "visibility": "public",
            "author": "system",
        })

    if status in {"CONFIRMED", "CHECKED_IN", "CHECKED_OUT", "CANCELLED", "NO_SHOW"}:
        state_event_time = updated_at or last_sync or created_at or _utc_now_iso()
        if status == "CHECKED_IN" and arrival_dt:
            state_event_time = arrival_dt.isoformat()
        elif status in {"CHECKED_OUT", "NO_SHOW"} and departure_dt:
            state_event_time = departure_dt.isoformat()
        seed_events.append({
            "type": "reservation_status_changed",
            "created_at": state_event_time,
            "title": _reservation_status_timeline_title(status),
            "detail": _reservation_status_timeline_detail(status, reservation),
            "status": status,
            "visibility": "public",
            "author": str(reservation.get("created_by", "")).strip() or "system",
        })

    return seed_events


def _reservation_timeline_events(reservation):
    metadata = (reservation or {}).get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    timeline = metadata.get("timeline") if isinstance(metadata.get("timeline"), list) else []
    normalized = []
    for entry in timeline:
        if not isinstance(entry, dict):
            continue
        normalized.append({
            "type": str(entry.get("type", "")).strip() or "reservation_event",
            "created_at": str(entry.get("created_at", "")).strip() or str((reservation or {}).get("created_at", "")).strip(),
            "title": str(entry.get("title", "")).strip(),
            "detail": str(entry.get("detail", "")).strip(),
            "status": _normalize_reservation_status(entry.get("status", (reservation or {}).get("status", "PENDING"))),
            "visibility": str(entry.get("visibility", "public")).strip().lower() or "public",
            "author": str(entry.get("author", "")).strip(),
        })
    seeded = _reservation_seed_timeline_events(reservation)
    merged = []
    seen = set()
    for entry in normalized + seeded:
        signature = (
            str(entry.get("type", "")).strip(),
            str(entry.get("created_at", "")).strip(),
            str(entry.get("title", "")).strip(),
            str(entry.get("detail", "")).strip(),
        )
        if signature in seen:
            continue
        seen.add(signature)
        merged.append(entry)
    merged.sort(key=lambda item: str(item.get("created_at", "")))
    return merged


def _reservation_comments(reservation, owner_view=False):
    metadata = (reservation or {}).get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    comments = metadata.get("comments") if isinstance(metadata.get("comments"), list) else []
    normalized = []
    for entry in comments:
        if not isinstance(entry, dict):
            continue
        visibility = str(entry.get("visibility", "public")).strip().lower() or "public"
        if owner_view and visibility != "public":
            continue
        normalized.append({
            "created_at": str(entry.get("created_at", "")).strip(),
            "author": str(entry.get("author", "")).strip() or "system",
            "visibility": visibility,
            "body": str(entry.get("body", "")).strip(),
        })
    return normalized


def _reservation_write_metadata(reservation_id, metadata, *, status=None, updated_at=None):
    if not reservation_id:
        return None
    reservation_id = str(reservation_id).strip()
    metadata = metadata if isinstance(metadata, dict) else {}
    metadata_json = json.dumps(metadata, ensure_ascii=False, separators=(",", ":"))
    updated_at = updated_at or _utc_now_iso()
    with _owner_db_connection() as conn:
        _ensure_owner_db_schema(conn)
        _migrate_owner_jsonl_backups(conn)
        conn.execute(
            """
            UPDATE reservations
            SET metadata_json = ?, updated_at = ?, status = COALESCE(?, status)
            WHERE id = ?
            """,
            (metadata_json, updated_at, status or "", reservation_id),
        )
    return _find_reservation(reservation_id)


def _reservation_append_timeline_event(reservation_id, event_type, title, detail="", status=None, *, visibility="public", author="system"):
    reservation = _find_reservation(reservation_id)
    if not reservation:
        return None
    metadata = reservation.get("metadata") if isinstance(reservation.get("metadata"), dict) else {}
    timeline = list(metadata.get("timeline") or [])
    timeline.append({
        "type": event_type,
        "created_at": _utc_now_iso(),
        "title": title,
        "detail": detail,
        "status": _normalize_reservation_status(status or reservation.get("status", "PENDING")),
        "visibility": str(visibility).strip().lower() or "public",
        "author": author,
    })
    metadata["timeline"] = timeline
    return _reservation_write_metadata(reservation_id, metadata, status=status or reservation.get("status", "PENDING"))


def _reservation_append_comment(reservation_id, comment, *, author="operations", visibility="internal"):
    comment_text = str(comment or "").strip()
    if not comment_text:
        return None
    reservation = _find_reservation(reservation_id)
    if not reservation:
        return None
    metadata = reservation.get("metadata") if isinstance(reservation.get("metadata"), dict) else {}
    comments = list(metadata.get("comments") or [])
    comments.append({
        "created_at": _utc_now_iso(),
        "author": author,
        "visibility": str(visibility).strip().lower() or "internal",
        "body": comment_text,
    })
    metadata["comments"] = comments
    updated = _reservation_write_metadata(reservation_id, metadata)
    _reservation_append_timeline_event(
        reservation_id,
        "comment_added",
        "Comment added",
        comment_text,
        status=reservation.get("status", "PENDING"),
        visibility=visibility,
        author=author,
    )
    return updated


def _reservation_calendar_event(reservation):
    reservation = reservation or {}
    metadata = reservation.get("metadata") if isinstance(reservation.get("metadata"), dict) else {}
    kind = str(metadata.get("kind", "reservation")).strip().lower() or "reservation"
    event_type = _reservation_event_type(metadata)
    calendar_status = _reservation_calendar_status(reservation.get("status", "PENDING"), kind=kind)
    arrival = str(reservation.get("arrival_datetime", "")).strip()
    departure = str(reservation.get("departure_datetime", "")).strip()
    if not arrival:
        arrival = reservation.get("created_at", "") or _utc_now_iso()
    if not departure:
        departure = arrival
    if kind == "blocked_dates":
        calendar_status = "BLOCKED"
    start_datetime, end_datetime, all_day = _calendar_event_bounds(arrival, departure, False)
    title = str(metadata.get("title", "")).strip() or _reservation_guest_name(reservation) or "Blocked dates"
    description = str(reservation.get("notes", "")).strip()
    property_name = str(reservation.get("property_name", "")).strip()
    owner_name = str(reservation.get("owner_name", "")).strip()
    payload_metadata = {
        "source": "reservation",
        "reservation_id": str(reservation.get("id", "")).strip(),
        "reservation_source": str(reservation.get("reservation_source", "")).strip(),
        "reservation_reference": str(reservation.get("reservation_reference", reservation.get("external_reference", ""))).strip(),
        "channel_name": str(reservation.get("channel_name", "")).strip(),
        "channel_status": str(reservation.get("channel_status", "")).strip(),
        "last_sync": str(reservation.get("last_sync", reservation.get("external_last_sync", ""))).strip(),
        "external_reference": str(reservation.get("external_reference", "")).strip(),
        "guest_name": _reservation_guest_name(reservation),
        "guest_email": str(reservation.get("guest_email", "")).strip(),
        "property_name": property_name,
        "property_location": str(reservation.get("property_location", "")).strip(),
        "owner_name": owner_name,
        "owner_email": str(reservation.get("owner_email", "")).strip(),
        "kind": kind,
    }
    return {
        "id": str(reservation.get("id", "")).strip(),
        "created_at": str(reservation.get("created_at", "")).strip(),
        "updated_at": str(reservation.get("updated_at", "")).strip() or _utc_now_iso(),
        "property_id": str(reservation.get("property_id", "")).strip(),
        "owner_id": str(reservation.get("owner_id", "")).strip(),
        "operation_task_id": str(reservation.get("id", "")).strip(),
        "event_type": event_type,
        "title": title,
        "description": description,
        "start_datetime": start_datetime,
        "end_datetime": end_datetime,
        "all_day": all_day,
        "status": calendar_status,
        "assigned_professional": "",
        "created_by": f"system:reservation:{str(reservation.get('created_by', '')).strip() or 'manual'}",
        "color": _calendar_event_color(event_type, calendar_status),
        "metadata_json": json.dumps(payload_metadata, ensure_ascii=False, separators=(",", ":")),
    }


def _upsert_reservation_calendar_event(reservation):
    payload = _reservation_calendar_event(reservation)
    if not payload:
        return None
    try:
        with _owner_db_connection() as conn:
            _ensure_owner_db_schema(conn)
            _migrate_owner_jsonl_backups(conn)
            _persist_calendar_event(conn, payload)
    except Exception as exc:
        app.logger.warning("Reservation calendar sync failed for %s: %s", str((reservation or {}).get("id", "")).strip(), type(exc).__name__)
        return None
    return payload


def _reservation_task_due_date(value, fallback=""):
    parsed, _all_day = _calendar_parse_datetime(value)
    if parsed:
        return parsed.date().isoformat()
    fallback_text = str(fallback or "").strip()
    return fallback_text[:10] if fallback_text else ""


def _reservation_operations_task_payloads(reservation):
    reservation = reservation or {}
    metadata = reservation.get("metadata") if isinstance(reservation.get("metadata"), dict) else {}
    if str(metadata.get("kind", "")).strip().lower() == "blocked_dates":
        return []

    reservation_id = str(reservation.get("id", "")).strip()
    property_name = str(reservation.get("property_name", "")).strip()
    property_location = str(reservation.get("property_location", "")).strip()
    guest_name = _reservation_guest_name(reservation) or "Guest"
    guest_label = guest_name or "Guest"
    status = _normalize_reservation_status(reservation.get("status", "PENDING"))
    arrival_due = _reservation_task_due_date(reservation.get("arrival_datetime", ""), reservation.get("created_at", ""))
    departure_due = _reservation_task_due_date(reservation.get("departure_datetime", ""), reservation.get("created_at", ""))
    arrival_dt, departure_dt = None, None
    parsed_arrival, _ = _calendar_parse_datetime(reservation.get("arrival_datetime", ""))
    parsed_departure, _ = _calendar_parse_datetime(reservation.get("departure_datetime", ""))
    arrival_dt = parsed_arrival
    departure_dt = parsed_departure
    stay_days = 0
    if arrival_dt and departure_dt:
        stay_days = max((departure_dt.date() - arrival_dt.date()).days, 0)
    midpoint_due = ""
    if arrival_dt and departure_dt and stay_days > 2:
        midpoint_due = (arrival_dt + ((departure_dt - arrival_dt) / 2)).date().isoformat()

    templates = [
        ("arrival-cleaning", "Arrival Cleaning", "Arrival cleaning", arrival_due, "cleaning"),
        ("checkin-preparation", "Check-in Preparation", "Check-in preparation", arrival_due, "preparation"),
        ("welcome-pack", "Welcome Pack", "Welcome pack", arrival_due, "welcome"),
        ("guest-inspection", "Guest Inspection", "Guest inspection", arrival_due, "inspection"),
    ]
    if status in {"CHECKED_IN", "CHECKED_OUT"} and midpoint_due:
        templates.append(("midstay-cleaning", "Mid-stay Cleaning", "Mid-stay cleaning", midpoint_due, "cleaning"))
    if status in {"CHECKED_OUT"}:
        templates.extend([
            ("checkout-inspection", "Checkout Inspection", "Checkout inspection", departure_due, "inspection"),
            ("departure-cleaning", "Departure Cleaning", "Departure cleaning", departure_due, "cleaning"),
            ("maintenance-review", "Maintenance Review", "Maintenance review", departure_due, "maintenance"),
        ])

    payloads = []
    for suffix, category, label, due_date, phase in templates:
        payloads.append({
            "id": f"{reservation_id}:{suffix}",
            "request_id": reservation_id,
            "source_type": "RESERVATION",
            "source_id": reservation_id,
            "created_at": reservation.get("created_at", "") or _utc_now_iso(),
            "updated_at": _utc_now_iso(),
            "title": f"{guest_label} {label}".strip(),
            "category": category,
            "owner_name": str(reservation.get("owner_name", "")).strip(),
            "owner_email": str(reservation.get("owner_email", "")).strip(),
            "property_id": str(reservation.get("property_id", "")).strip(),
            "property_name": property_name,
            "assigned_to": "",
            "assigned_professional_id": "",
            "priority": "NORMAL",
            "status": "NEW",
            "due_date": str(due_date or "").strip(),
            "notes": str(reservation.get("notes", "")).strip(),
            "completed_at": "",
            "owner_id": str(reservation.get("owner_id", "")).strip(),
            "property_location": property_location,
            "admin_notes": f"Reservation source: {reservation.get('reservation_source', 'Manual')}",
            "request_status": "new",
            "timeline_detail": f"{guest_label} · {property_name or property_location}".strip(" ·"),
            "phase": phase,
            "reservation_status": status,
        })
    return payloads


def _ensure_reservation_operations_tasks(reservation):
    payloads = _reservation_operations_task_payloads(reservation)
    created_tasks = []
    for payload in payloads:
        existing_task = _find_operations_task(payload["id"])
        if existing_task:
            created_tasks.append(existing_task)
            continue
        created = _upsert_operations_task(payload, append_created_event=True, status_override="NEW", notify=False)
        if created:
            created_tasks.append(created)
    return created_tasks


def _reservation_sync_derived_state(reservation, *, append_timeline_event=None):
    reservation = reservation or {}
    reservation_id = str(reservation.get("id", "")).strip()
    if not reservation_id:
        return None

    refreshed = _find_reservation(reservation_id) or reservation
    _upsert_reservation_calendar_event(refreshed)
    linked_tasks = _ensure_reservation_operations_tasks(refreshed)
    metadata = refreshed.get("metadata") if isinstance(refreshed.get("metadata"), dict) else {}
    metadata["linked_operations"] = [task.get("id", "") for task in linked_tasks if task]
    _reservation_write_metadata(reservation_id, metadata, status=refreshed.get("status", "PENDING"))
    refreshed = _find_reservation(reservation_id) or refreshed

    if append_timeline_event:
        event_type, title, detail, status, author, visibility = append_timeline_event
        _reservation_append_timeline_event(
            reservation_id,
            event_type,
            title,
            detail,
            status=status or refreshed.get("status", "PENDING"),
            author=author or "system",
            visibility=visibility or "public",
        )
        refreshed = _find_reservation(reservation_id) or refreshed

    return refreshed


def _reservation_transition_timeline_event(status, reservation=None):
    normalized = _normalize_reservation_status(status)
    event_type = {
        "CONFIRMED": "reservation_confirmed",
        "CHECKED_IN": "reservation_checked_in",
        "CHECKED_OUT": "reservation_checked_out",
        "CANCELLED": "reservation_cancelled",
        "NO_SHOW": "reservation_no_show",
    }.get(normalized, "reservation_updated")
    title = _reservation_status_timeline_title(normalized)
    detail = _reservation_status_timeline_detail(normalized, reservation)
    return event_type, title, detail


def _update_reservation_status(reservation_id, status, *, author="system", detail=""):
    reservation = _find_reservation(reservation_id)
    if not reservation:
        return None
    current_status = _normalize_reservation_status(reservation.get("status", "PENDING"))
    new_status = _normalize_reservation_status(status)
    if new_status == current_status:
        return _reservation_sync_derived_state(reservation)

    updated_at = _utc_now_iso()
    with _owner_db_connection() as conn:
        _ensure_owner_db_schema(conn)
        _migrate_owner_jsonl_backups(conn)
        conn.execute(
            """
            UPDATE reservations
            SET status = ?, updated_at = ?
            WHERE id = ?
            """,
            (new_status, updated_at, str(reservation_id).strip()),
        )

    updated_reservation = _find_reservation(reservation_id)
    event_type, title, default_detail = _reservation_transition_timeline_event(new_status, updated_reservation)
    return _reservation_sync_derived_state(
        updated_reservation,
        append_timeline_event=(
            event_type,
            title,
            str(detail or default_detail).strip(),
            new_status,
            author,
            "public",
        ),
    )


def _reservation_operation_event_from_task(task, status):
    category = str((task or {}).get("category", "")).strip()
    normalized_status = _normalize_operations_task_status(status)
    category_lower = category.lower()
    if normalized_status == "COMPLETED":
        if "clean" in category_lower:
            return "cleaning_completed", "Cleaning completed"
        if "checkout" in category_lower or "check-out" in category_lower:
            return "checkout_completed", "Checkout completed"
        if "inspection" in category_lower:
            return "inspection_completed", "Inspection completed"
        if "maintenance" in category_lower:
            return "maintenance_review_completed", "Maintenance review completed"
        return "operation_completed", "Operation completed"
    return "operation_updated", f"{category or 'Operation'} updated"


def _sync_reservation_from_operation_task(task, status):
    task = task or {}
    if str(task.get("source_type", "")).strip().upper() != "RESERVATION":
        return None
    reservation_id = str(task.get("source_id", "") or task.get("request_id", "")).strip()
    reservation = _find_reservation(reservation_id)
    if not reservation:
        return None
    event_type, title = _reservation_operation_event_from_task(task, status)
    return _reservation_append_timeline_event(
        reservation_id,
        event_type,
        title,
        str(task.get("title", "")).strip() or str(task.get("category", "")).strip(),
        status=reservation.get("status", "PENDING"),
        visibility="public",
        author="system:operations",
    )


def _create_reservation(reservation_payload, *, created_by="system"):
    reservation_id = str((reservation_payload or {}).get("id", "")).strip() or uuid4().hex
    property_id = str((reservation_payload or {}).get("property_id", "")).strip()
    if not property_id:
        return None
    property_record = _find_owner_property(property_id)
    if not property_record:
        return None
    owner_id = str(property_record.get("owner_id", "")).strip()
    owner_account = _find_owner_account(owner_id)
    created_at = str((reservation_payload or {}).get("created_at", "")).strip() or _utc_now_iso()
    updated_at = str((reservation_payload or {}).get("updated_at", "")).strip() or created_at
    metadata = reservation_payload.get("metadata", {}) if isinstance(reservation_payload, dict) else {}
    if not isinstance(metadata, dict):
        metadata = {}
    metadata.setdefault("timeline", [])
    metadata.setdefault("comments", [])
    metadata.setdefault("kind", str((reservation_payload or {}).get("kind", "reservation")).strip().lower() or "reservation")
    metadata.setdefault("title", str((reservation_payload or {}).get("title", "")).strip())
    reservation_source = _normalize_reservation_source((reservation_payload or {}).get("reservation_source", "Manual Reservation"))
    reservation_reference = str((reservation_payload or {}).get("reservation_reference", "")).strip()
    if not reservation_reference:
        reservation_reference = str((reservation_payload or {}).get("external_reference", "")).strip()
    channel_name = _normalize_reservation_source((reservation_payload or {}).get("channel_name", reservation_source))
    channel_status = _normalize_reservation_channel_status((reservation_payload or {}).get("channel_status", (reservation_payload or {}).get("sync_status", "SYNCED")))
    last_sync = str((reservation_payload or {}).get("last_sync", "")).strip()
    if not last_sync:
        last_sync = str((reservation_payload or {}).get("external_last_sync", "")).strip()
    external_payload_value = (reservation_payload or {}).get("external_payload")
    if external_payload_value is None:
        external_payload_value = _safe_json_loads(str((reservation_payload or {}).get("source_metadata_json", "{}")), {})
    if isinstance(external_payload_value, str):
        external_payload_json = external_payload_value if external_payload_value.strip() else "{}"
    else:
        external_payload_json = json.dumps(external_payload_value or {}, ensure_ascii=False, separators=(",", ":"))
    status = _normalize_reservation_status((reservation_payload or {}).get("status", "PENDING"))
    if metadata.get("kind") == "blocked_dates":
        status = "CONFIRMED"
    record = {
        "id": reservation_id,
        "created_at": created_at,
        "updated_at": updated_at,
        "property_id": property_id,
        "reservation_source": reservation_source,
        "reservation_reference": reservation_reference,
        "channel_name": channel_name,
        "channel_status": channel_status,
        "last_sync": last_sync,
        "external_payload": external_payload_json,
        "external_reference": reservation_reference,
        "external_last_sync": last_sync,
        "import_batch_id": str((reservation_payload or {}).get("import_batch_id", "")).strip(),
        "sync_status": str((reservation_payload or {}).get("sync_status", "IDLE")).strip() or "IDLE",
        "source_metadata_json": external_payload_json,
        "guest_first_name": str((reservation_payload or {}).get("guest_first_name", "")).strip(),
        "guest_last_name": str((reservation_payload or {}).get("guest_last_name", "")).strip(),
        "guest_email": str((reservation_payload or {}).get("guest_email", "")).strip(),
        "guest_phone": str((reservation_payload or {}).get("guest_phone", "")).strip(),
        "adults": int(reservation_payload.get("adults", 1) or 1),
        "children": int(reservation_payload.get("children", 0) or 0),
        "infants": int(reservation_payload.get("infants", 0) or 0),
        "pets": int(reservation_payload.get("pets", 0) or 0),
        "arrival_datetime": str((reservation_payload or {}).get("arrival_datetime", "")).strip(),
        "departure_datetime": str((reservation_payload or {}).get("departure_datetime", "")).strip(),
        "status": status,
        "notes": str((reservation_payload or {}).get("notes", "")).strip(),
        "language": str((reservation_payload or {}).get("language", "en")).strip() or "en",
        "created_by": str((reservation_payload or {}).get("created_by", created_by)).strip() or created_by,
        "metadata_json": json.dumps(metadata, ensure_ascii=False, separators=(",", ":")),
    }

    with _owner_db_connection() as conn:
        _ensure_owner_db_schema(conn)
        _migrate_owner_jsonl_backups(conn)
        conn.execute(
            """
            INSERT INTO reservations (
                id, created_at, updated_at, property_id, reservation_source, reservation_reference, channel_name,
                channel_status, last_sync, external_payload, external_reference, external_last_sync,
                import_batch_id, sync_status, source_metadata_json, guest_first_name, guest_last_name, guest_email,
                guest_phone, adults, children, infants, pets, arrival_datetime, departure_datetime, status, notes,
                language, created_by, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                created_at = excluded.created_at,
                updated_at = excluded.updated_at,
                property_id = excluded.property_id,
                reservation_source = excluded.reservation_source,
                reservation_reference = excluded.reservation_reference,
                channel_name = excluded.channel_name,
                channel_status = excluded.channel_status,
                last_sync = excluded.last_sync,
                external_payload = excluded.external_payload,
                external_reference = excluded.external_reference,
                external_last_sync = excluded.external_last_sync,
                import_batch_id = excluded.import_batch_id,
                sync_status = excluded.sync_status,
                source_metadata_json = excluded.source_metadata_json,
                guest_first_name = excluded.guest_first_name,
                guest_last_name = excluded.guest_last_name,
                guest_email = excluded.guest_email,
                guest_phone = excluded.guest_phone,
                adults = excluded.adults,
                children = excluded.children,
                infants = excluded.infants,
                pets = excluded.pets,
                arrival_datetime = excluded.arrival_datetime,
                departure_datetime = excluded.departure_datetime,
                status = excluded.status,
                notes = excluded.notes,
                language = excluded.language,
                created_by = excluded.created_by,
                metadata_json = excluded.metadata_json
            """,
            (
                record["id"],
                record["created_at"],
                record["updated_at"],
                record["property_id"],
                record["reservation_source"],
                record["reservation_reference"],
                record["channel_name"],
                record["channel_status"],
                record["last_sync"],
                record["external_payload"],
                record["external_reference"],
                record["external_last_sync"],
                record["import_batch_id"],
                record["sync_status"],
                record["source_metadata_json"],
                record["guest_first_name"],
                record["guest_last_name"],
                record["guest_email"],
                record["guest_phone"],
                record["adults"],
                record["children"],
                record["infants"],
                record["pets"],
                record["arrival_datetime"],
                record["departure_datetime"],
                record["status"],
                record["notes"],
                record["language"],
                record["created_by"],
                record["metadata_json"],
            ),
        )

    reservation = _find_reservation(reservation_id)
    if reservation:
        reservation = _reservation_sync_derived_state(
            reservation,
            append_timeline_event=(
                "reservation_created",
                "Reservation created" if reservation.get("metadata", {}).get("kind", "reservation") != "blocked_dates" else "Blocked dates created",
                f"{_reservation_guest_name(reservation) or 'Blocked dates'} · {reservation.get('property_name', '')}",
                reservation.get("status", "PENDING"),
                str(created_by).strip() or "system",
                "public",
            ),
        )
        _append_operations_notification(
            "reservation_created",
            "Reservation created",
            f"{_reservation_guest_name(reservation) or 'Blocked dates'} · {reservation.get('property_name', '')}",
            task_id=reservation_id,
            source_type="RESERVATION",
            source_id=reservation_id,
            status=reservation.get("status", "PENDING"),
            channel="SYSTEM",
            recipient=str(owner_account.get("email", "")).strip(),
            metadata=json.dumps({
                "reservation_id": reservation_id,
                "property_id": property_id,
                "kind": metadata.get("kind", "reservation"),
            }, ensure_ascii=False, separators=(",", ":")),
        )
    return reservation


def _reservation_property_status(property_record, reservations=None):
    property_record = property_record or {}
    reservations = reservations or []
    property_id = str(property_record.get("id", "")).strip()
    today = datetime.now(timezone.utc)
    blocked_calendar_events = [
        event for event in _load_calendar_events(property_ids=[property_id])
        if _normalize_calendar_event_type(event.get("event_type", "")) in {"Blocked Dates", "Personal Stay"} and _calendar_parse_datetime(event.get("start_datetime", ""))[0]
    ]

    current_reservation = None
    upcoming_reservation = None
    for reservation in reservations:
        if str(reservation.get("property_id", "")).strip() != property_id:
            continue
        if _normalize_reservation_status(reservation.get("status", "PENDING")) in {"CANCELLED", "NO_SHOW"}:
            continue
        arrival_dt, _ = _calendar_parse_datetime(reservation.get("arrival_datetime", ""))
        departure_dt, _ = _calendar_parse_datetime(reservation.get("departure_datetime", ""))
        if str((reservation.get("metadata") or {}).get("kind", "")).strip().lower() == "blocked_dates" and arrival_dt and departure_dt and arrival_dt <= today <= departure_dt:
            return "Blocked"
        if arrival_dt and departure_dt and arrival_dt <= today <= departure_dt:
            current_reservation = reservation
            break
        if arrival_dt and arrival_dt > today and upcoming_reservation is None:
            upcoming_reservation = reservation

    if current_reservation:
        return "Occupied"
    if blocked_calendar_events:
        return "Blocked"
    active_tasks = [
        event for event in _load_operations_tasks()
        if str(event.get("property_id", "")).strip() == property_id
        and _normalize_operations_task_status(event.get("status", "NEW")) in {"NEW", "ASSIGNED", "ACCEPTED", "ON_THE_WAY", "ARRIVED", "IN_PROGRESS"}
    ]
    if any("maint" in str(event.get("category", "")).lower() for event in active_tasks):
        return "Maintenance"
    if any("clean" in str(event.get("category", "")).lower() for event in active_tasks):
        return "Cleaning"
    if any("preparation" in str(event.get("category", "")).lower() or "welcome" in str(event.get("category", "")).lower() for event in active_tasks):
        return "Preparation"
    if upcoming_reservation:
        return "Ready" if _normalize_reservation_status(upcoming_reservation.get("status", "PENDING")) in {"CONFIRMED", "CHECKED_IN"} else "Available"
    return "Available"


def _reservation_is_stay(reservation):
    metadata = (reservation or {}).get("metadata") if isinstance((reservation or {}).get("metadata"), dict) else {}
    return str(metadata.get("kind", "reservation")).strip().lower() != "blocked_dates"


def _reservation_date_bounds(reservation):
    arrival_dt, _ = _calendar_parse_datetime((reservation or {}).get("arrival_datetime", ""))
    departure_dt, _ = _calendar_parse_datetime((reservation or {}).get("departure_datetime", ""))
    return arrival_dt, departure_dt


def _reservation_is_occupying(reservation, target_date=None):
    if not _reservation_is_stay(reservation):
        return False
    if _normalize_reservation_status((reservation or {}).get("status", "PENDING")) not in {"CONFIRMED", "CHECKED_IN", "CHECKED_OUT"}:
        return False
    arrival_dt, departure_dt = _reservation_date_bounds(reservation)
    if not arrival_dt or not departure_dt:
        return False
    target_date = target_date or datetime.now(timezone.utc).date()
    return arrival_dt.date() <= target_date < departure_dt.date()


def _reservation_occupancy_engine(reservations, *, property_ids=None, days=30):
    today = datetime.now(timezone.utc).date()
    target_property_ids = {str(property_id).strip() for property_id in (property_ids or []) if str(property_id).strip()}
    if not target_property_ids:
        target_property_ids = {str(reservation.get("property_id", "")).strip() for reservation in reservations if str(reservation.get("property_id", "")).strip()}
    total_property_days = max(len(target_property_ids), 1) * max(days, 1)
    occupied_days = 0
    blocked_days = 0

    for offset in range(days):
        day = today + timedelta(days=offset)
        for property_id in target_property_ids:
            property_reservations = [reservation for reservation in reservations if str(reservation.get("property_id", "")).strip() == property_id]
            if any(_reservation_is_occupying(reservation, day) for reservation in property_reservations):
                occupied_days += 1
                continue
            if any(str((reservation.get("metadata") or {}).get("kind", "")).strip().lower() == "blocked_dates" and _reservation_date_bounds(reservation)[0] and _reservation_date_bounds(reservation)[1] and _reservation_date_bounds(reservation)[0].date() <= day < _reservation_date_bounds(reservation)[1].date() for reservation in property_reservations):
                blocked_days += 1

    available_days = max(total_property_days - occupied_days - blocked_days, 0)
    return {
        "occupied_days": occupied_days,
        "available_days": available_days,
        "blocked_days": blocked_days,
        "occupancy_percent": int(round((occupied_days / total_property_days) * 100)) if total_property_days else 0,
        "availability_percent": int(round((available_days / total_property_days) * 100)) if total_property_days else 0,
    }


def _property_availability_engine(property_record, reservations=None, operations_tasks=None):
    property_record = property_record or {}
    property_id = str(property_record.get("id", "")).strip()
    reservations = [reservation for reservation in (reservations or _load_reservations(property_ids=[property_id])) if str(reservation.get("property_id", "")).strip() == property_id]
    operations_tasks = operations_tasks or _load_operations_tasks()
    today = datetime.now(timezone.utc).date()
    active_reservations = [
        reservation for reservation in reservations
        if _reservation_is_stay(reservation)
        and _normalize_reservation_status(reservation.get("status", "PENDING")) not in {"CANCELLED", "NO_SHOW"}
    ]
    current_guest = next((reservation for reservation in active_reservations if _reservation_is_occupying(reservation, today)), None)
    upcoming_arrivals = sorted(
        [reservation for reservation in active_reservations if (arrival := _reservation_date_bounds(reservation)[0]) and arrival.date() >= today],
        key=lambda reservation: str(reservation.get("arrival_datetime", "")),
    )
    upcoming_departures = sorted(
        [reservation for reservation in active_reservations if (departure := _reservation_date_bounds(reservation)[1]) and departure.date() >= today],
        key=lambda reservation: str(reservation.get("departure_datetime", "")),
    )
    active_property_tasks = [
        task for task in operations_tasks
        if str(task.get("property_id", "")).strip() == property_id
        and _normalize_operations_task_status(task.get("status", "NEW")) in {"NEW", "ASSIGNED", "ACCEPTED", "ON_THE_WAY", "ARRIVED", "IN_PROGRESS", "WAITING_OPERATIONS"}
    ]
    cleaning_required = any("clean" in str(task.get("category", "")).lower() for task in active_property_tasks)
    occupancy = _reservation_occupancy_engine(reservations, property_ids=[property_id])
    days_free = occupancy["available_days"]
    return {
        "property_id": property_id,
        "state": _reservation_property_status(property_record, reservations),
        "availability_percent": occupancy["availability_percent"],
        "occupancy_percent": occupancy["occupancy_percent"],
        "upcoming_arrival": upcoming_arrivals[0] if upcoming_arrivals else None,
        "upcoming_departure": upcoming_departures[0] if upcoming_departures else None,
        "current_guest": current_guest,
        "days_free": days_free,
        "cleaning_required": cleaning_required,
        "maintenance_required": any("maint" in str(task.get("category", "")).lower() for task in active_property_tasks),
        "preparation_required": any("preparation" in str(task.get("category", "")).lower() or "welcome" in str(task.get("category", "")).lower() for task in active_property_tasks),
    }


def _reservation_dashboard_widgets(reservations, *, scope="owner"):
    reservations = reservations or []
    now = datetime.now(timezone.utc)
    today = now.date()
    tomorrow = today + timedelta(days=1)
    property_ids = {str(reservation.get("property_id", "")).strip() for reservation in reservations if str(reservation.get("property_id", "")).strip()}
    occupancy_engine = _reservation_occupancy_engine(reservations, property_ids=property_ids)
    operations_tasks = _load_operations_tasks()
    open_operations = [
        task for task in operations_tasks
        if (not property_ids or str(task.get("property_id", "")).strip() in property_ids)
        and _normalize_operations_task_status(task.get("status", "NEW")) in {"NEW", "ASSIGNED", "ACCEPTED", "ON_THE_WAY", "ARRIVED", "IN_PROGRESS", "WAITING_OPERATIONS"}
    ]
    todays_operations = [
        task for task in open_operations
        if str(task.get("due_date", "")).strip()[:10] == today.isoformat()
    ]
    late_operations = [
        task for task in open_operations
        if str(task.get("due_date", "")).strip()[:10] and str(task.get("due_date", "")).strip()[:10] < today.isoformat()
    ]

    def _reservation_date(value):
        return _calendar_parse_datetime(value)[0]

    if scope == "owner":
        current_guests = [
            reservation for reservation in reservations
            if _normalize_reservation_status(reservation.get("status", "PENDING")) in {"CONFIRMED", "CHECKED_IN"}
            and _reservation_date(reservation.get("arrival_datetime", "")) and _reservation_date(reservation.get("departure_datetime", ""))
            and _reservation_date(reservation.get("arrival_datetime", "")).date() <= today <= _reservation_date(reservation.get("departure_datetime", "")).date()
        ]
        upcoming_arrivals = [
            reservation for reservation in reservations
            if _reservation_date(reservation.get("arrival_datetime", "")) and _reservation_date(reservation.get("arrival_datetime", "")).date() >= today
            and _normalize_reservation_status(reservation.get("status", "PENDING")) in {"PENDING", "CONFIRMED"}
        ]
        upcoming_departures = [
            reservation for reservation in reservations
            if _reservation_date(reservation.get("departure_datetime", "")) and _reservation_date(reservation.get("departure_datetime", "")).date() >= today
            and _normalize_reservation_status(reservation.get("status", "PENDING")) in {"CHECKED_IN", "CONFIRMED"}
        ]
        next_cleaning = next((reservation for reservation in reservations if str((reservation.get("metadata") or {}).get("kind", "")).strip() != "blocked_dates" and _reservation_date(reservation.get("departure_datetime", "")) and _reservation_date(reservation.get("departure_datetime", "")).date() >= today), None)
        return {
            "upcoming_arrivals": upcoming_arrivals[:5],
            "upcoming_departures": upcoming_departures[:5],
            "current_guests": current_guests[:5],
            "todays_operations": todays_operations[:5],
            "next_cleaning": next_cleaning,
            "occupancy": occupancy_engine,
            "revenue_placeholder": "Pending channel revenue sync",
            "stats": {
                "upcoming_arrivals": len(upcoming_arrivals),
                "upcoming_departures": len(upcoming_departures),
                "current_guests": len(current_guests),
                "todays_operations": len(todays_operations),
                "next_cleaning": 1 if next_cleaning else 0,
                "occupancy": occupancy_engine["occupancy_percent"],
                "availability": occupancy_engine["availability_percent"],
                "revenue": 0,
            },
        }

    todays_check_ins = [
        reservation for reservation in reservations
        if _reservation_date(reservation.get("arrival_datetime", "")) and _reservation_date(reservation.get("arrival_datetime", "")).date() == today
    ]
    todays_check_outs = [
        reservation for reservation in reservations
        if _reservation_date(reservation.get("departure_datetime", "")) and _reservation_date(reservation.get("departure_datetime", "")).date() == today
    ]
    current_guests = [
        reservation for reservation in reservations
        if _normalize_reservation_status(reservation.get("status", "PENDING")) in {"CONFIRMED", "CHECKED_IN"}
        and _reservation_date(reservation.get("arrival_datetime", "")) and _reservation_date(reservation.get("departure_datetime", ""))
        and _reservation_date(reservation.get("arrival_datetime", "")).date() <= today <= _reservation_date(reservation.get("departure_datetime", "")).date()
    ]
    cleaning_queue = [
        reservation for reservation in reservations
        if str((reservation.get("metadata") or {}).get("kind", "")).strip() != "blocked_dates"
        and _reservation_date(reservation.get("departure_datetime", "")) and _reservation_date(reservation.get("departure_datetime", "")).date() >= today
    ]
    inspections = [
        reservation for reservation in reservations
        if _reservation_date(reservation.get("departure_datetime", "")) and _reservation_date(reservation.get("departure_datetime", "")).date() >= today
        and _normalize_reservation_status(reservation.get("status", "PENDING")) in {"CONFIRMED", "CHECKED_IN"}
    ]
    cleaning_today = [task for task in todays_operations if "clean" in str(task.get("category", "")).lower()]
    checkins = [reservation for reservation in todays_check_ins if _normalize_reservation_status(reservation.get("status", "PENDING")) in {"PENDING", "CONFIRMED", "CHECKED_IN"}]
    return {
        "todays_check_ins": todays_check_ins[:5],
        "todays_check_outs": todays_check_outs[:5],
        "current_guests": current_guests[:5],
        "cleaning_queue": cleaning_queue[:5],
        "inspections": inspections[:5],
        "todays_operations": todays_operations[:5],
        "late_operations": late_operations[:5],
        "property_occupancy": occupancy_engine,
        "cleaning_today": cleaning_today[:5],
        "checkins": checkins[:5],
        "revenue_placeholder": "Pending channel revenue sync",
        "stats": {
            "todays_check_ins": len(todays_check_ins),
            "todays_check_outs": len(todays_check_outs),
            "occupancy": occupancy_engine["occupancy_percent"],
            "availability": occupancy_engine["availability_percent"],
            "cleaning_queue": len(cleaning_queue),
            "inspections": len(inspections),
            "arrivals_today": len(todays_check_ins),
            "departures_today": len(todays_check_outs),
            "cleaning_today": len(cleaning_today),
            "checkins": len(checkins),
            "late_operations": len(late_operations),
            "todays_operations": len(todays_operations),
            "revenue": 0,
        },
    }


def _reservation_list_context(*, owner_account=None, scope="admin", filters=None):
    owner_account = owner_account or {}
    if scope == "owner":
        owner_properties = _owner_properties_for_account(owner_account.get("id", ""))
        property_ids = [property_record.get("id", "") for property_record in owner_properties]
        reservations = _load_reservations(owner_id=owner_account.get("id", ""), property_ids=property_ids, filters=filters)
    else:
        reservations = _load_reservations(filters=filters)
        owner_properties = _load_owner_properties()

    calendar_events = _load_calendar_events(property_ids=[reservation.get("property_id", "") for reservation in reservations] if reservations else None)
    calendar_map = {str(event.get("metadata", {}).get("reservation_id", "")).strip() or str(event.get("operation_task_id", "")).strip(): event for event in calendar_events}
    property_map = {str(property_record.get("id", "")).strip(): property_record for property_record in _load_owner_properties()}
    owner_map = {str(account.get("id", "")).strip(): account for account in _load_owner_accounts()}
    operations_tasks = _load_operations_tasks()
    for reservation in reservations:
        reservation["calendar_event"] = calendar_map.get(reservation.get("id", ""), _reservation_calendar_event(reservation))
        reservation["linked_operations"] = _reservation_linked_operations(reservation)
        property_record = property_map.get(str(reservation.get("property_id", "")).strip(), {})
        owner_account_record = owner_map.get(str(property_record.get("owner_id", "")).strip(), {})
        reservation["owner_name"] = str(owner_account_record.get("full_name", "")).strip()
        reservation["owner_email"] = str(owner_account_record.get("email", "")).strip()
        reservation["property_name"] = str(property_record.get("name", "")).strip()
        reservation["property_location"] = str(property_record.get("location", "")).strip()
        reservation["property_status"] = _reservation_property_status(property_record, reservations)
        reservation["property_availability"] = _property_availability_engine(property_record, reservations, operations_tasks)
    return {
        "reservations": reservations,
        "filters": filters or {},
        "property_options": sorted({reservation.get("property_name", "") for reservation in reservations if reservation.get("property_name", "")}),
        "owner_options": sorted({reservation.get("owner_name", "") for reservation in reservations if reservation.get("owner_name", "")}),
        "guest_options": sorted({reservation.get("guest_name", "") for reservation in reservations if reservation.get("guest_name", "")}),
        "source_options": list(RESERVATION_SOURCE_VALUES),
        "status_options": list(RESERVATION_STATUS_VALUES),
        "widgets": _reservation_dashboard_widgets(reservations, scope=scope),
        "calendar_summary": _calendar_widget_summary(_load_calendar_events(property_ids=[reservation.get("property_id", "") for reservation in reservations] if reservations else None)),
        "scope": scope,
        "owner_properties": owner_properties,
    }


def _reservation_linked_operations(reservation):
    reservation_id = str((reservation or {}).get("id", "")).strip()
    if not reservation_id:
        return []
    linked = []
    for task in _load_operations_tasks():
        if str(task.get("source_type", "")).strip().upper() != "RESERVATION":
            continue
        if str(task.get("source_id", "")).strip() != reservation_id:
            continue
        linked.append({
            **task,
            "status_label": _operations_task_status_label(task.get("status", "NEW")),
            "status_tone": _operations_task_status_tone(task.get("status", "NEW")),
        })
    return linked


def _reservation_detail_context(reservation, *, scope="admin", owner_account=None):
    reservation = reservation or {}
    owner_account = owner_account or {}
    property_record = _find_owner_property(reservation.get("property_id", ""))
    property_reservations = _load_reservations(property_ids=[reservation.get("property_id", "")])
    owner_account_record = _find_owner_account(str((property_record or {}).get("owner_id", "")).strip()) if property_record else {}
    calendar_events = _load_calendar_events(property_ids=[reservation.get("property_id", "")])
    operations_tasks = _load_operations_tasks()
    linked_operations = _reservation_linked_operations(reservation)
    timeline_events = _reservation_timeline_events(reservation)
    if scope == "owner":
        timeline_events = [event for event in timeline_events if str(event.get("visibility", "public")).strip().lower() == "public"]
    reservation_event = _reservation_calendar_event({
        **reservation,
        "property_name": str((property_record or {}).get("name", "")).strip(),
        "property_location": str((property_record or {}).get("location", "")).strip(),
        "owner_name": str((owner_account_record or {}).get("full_name", "")).strip(),
        "owner_email": str((owner_account_record or {}).get("email", "")).strip(),
    })
    calendar_event = next(
        (event for event in calendar_events if str(event.get("metadata", {}).get("reservation_id", "")).strip() == str(reservation.get("id", "")).strip()),
        reservation_event,
    )
    enriched_reservation = {
        **reservation,
        "property_name": str((property_record or {}).get("name", "")).strip(),
        "property_location": str((property_record or {}).get("location", "")).strip(),
        "owner_id": str((property_record or {}).get("owner_id", "")).strip(),
        "owner_name": str((owner_account_record or {}).get("full_name", "")).strip(),
        "owner_email": str((owner_account_record or {}).get("email", "")).strip(),
        "guest_name": _reservation_guest_name(reservation) or "Blocked dates",
        "timeline": list(reversed(timeline_events)),
        "comments": _reservation_comments(reservation, owner_view=(scope == "owner")),
        "linked_operations": linked_operations,
        "calendar_event": calendar_event,
        "property_status": _reservation_property_status(property_record, property_reservations),
        "property_availability": _property_availability_engine(property_record, property_reservations, operations_tasks),
    }
    return {
        "reservation": enriched_reservation,
        "property_record": property_record or {},
        "owner_account": owner_account_record or owner_account or {},
        "linked_operations": linked_operations,
        "calendar_event": calendar_event,
        "calendar_events": calendar_events,
        "timeline": enriched_reservation["timeline"],
        "comments": enriched_reservation["comments"],
        "property_status": enriched_reservation["property_status"],
        "property_availability": enriched_reservation["property_availability"],
        "can_view_internal_comments": scope == "admin",
        "status_options": [{"value": status, "label": _reservation_status_label(status)} for status in RESERVATION_STATUS_VALUES],
    }


def _reservation_import_batch_id():
    return uuid4().hex


def _reservation_import_normalize_text(value):
    return str(value or "").strip()


def _reservation_import_split_guest_name(value):
    text = _reservation_import_normalize_text(value)
    if not text:
        return "", ""
    if "," in text:
        parts = [part.strip() for part in text.split(",", 1)]
        return parts[1] if len(parts) > 1 else "", parts[0]
    parts = text.split()
    if len(parts) == 1:
        return parts[0], ""
    return " ".join(parts[:-1]).strip(), parts[-1].strip()


def _reservation_import_interval_overlaps(start_a, end_a, start_b, end_b):
    if not all([start_a, end_a, start_b, end_b]):
        return False
    return start_a < end_b and start_b < end_a


def _reservation_import_parse_date(value):
    parsed, _all_day = _calendar_parse_datetime(value)
    return parsed


def _reservation_import_property_candidates():
    properties = _load_owner_properties()
    return [{
        **property_record,
        "normalized_name": _reservation_import_normalize_text(property_record.get("name", "")).lower(),
    } for property_record in properties]


def _reservation_import_match_property(item, context=None):
    context = context or {}
    manual_property_id = _reservation_import_normalize_text(context.get("manual_property_id", ""))
    property_map = context.get("property_map") if isinstance(context.get("property_map"), dict) else {}
    property_name = _reservation_import_normalize_text(item.get("property_name", "")).lower()
    external_reference = _reservation_import_normalize_text(item.get("external_reference", "")).lower()

    if external_reference:
        for reservation in _load_reservations():
            if _reservation_import_normalize_text(reservation.get("external_reference", "")).lower() != external_reference:
                continue
            property_record = _find_owner_property(reservation.get("property_id", ""))
            if property_record:
                return property_record

    if manual_property_id:
        property_record = _find_owner_property(manual_property_id)
        if property_record:
            return property_record

    if property_name in property_map:
        property_record = _find_owner_property(property_map[property_name])
        if property_record:
            return property_record

    for property_record in _reservation_import_property_candidates():
        if property_name and property_record.get("normalized_name") == property_name:
            return property_record

    return None


def _reservation_import_overlap_conflicts(property_id, arrival_dt, departure_dt, *, reservation_id="", source_reference="", guest_email=""):
    conflicts = []
    if not property_id or not arrival_dt or not departure_dt:
        return conflicts
    for reservation in _load_reservations(property_ids=[property_id]):
        existing_id = str(reservation.get("id", "")).strip()
        if reservation_id and existing_id == reservation_id:
            continue
        if _normalize_reservation_status(reservation.get("status", "PENDING")) == "CANCELLED":
            continue
        existing_arrival = _reservation_import_parse_date(reservation.get("arrival_datetime", ""))
        existing_departure = _reservation_import_parse_date(reservation.get("departure_datetime", ""))
        if not existing_arrival or not existing_departure:
            continue
        if source_reference and _reservation_import_normalize_text(reservation.get("external_reference", "")).lower() == source_reference.lower():
            conflicts.append({
                "type": "duplicate",
                "reservation_id": existing_id,
                "property_id": property_id,
                "reason": "duplicate external reference",
            })
            continue
        if guest_email and _reservation_import_normalize_text(reservation.get("guest_email", "")).lower() == guest_email.lower() and _reservation_import_interval_overlaps(arrival_dt, departure_dt, existing_arrival, existing_departure):
            conflicts.append({
                "type": "duplicate",
                "reservation_id": existing_id,
                "property_id": property_id,
                "reason": "duplicate guest stay",
            })
            continue
        if _reservation_import_interval_overlaps(arrival_dt, departure_dt, existing_arrival, existing_departure):
            conflicts.append({
                "type": "conflict",
                "reservation_id": existing_id,
                "property_id": property_id,
                "reason": "date overlap",
            })
    return conflicts


def _reservation_import_build_preview_item(item, *, adapter_key, batch_id, context=None, source_metadata=None, imported_source=""):
    context = context or {}
    source_metadata = source_metadata or {}
    normalized_item = dict(item or {})
    normalized_item["reservation_source"] = _normalize_reservation_source(imported_source or normalized_item.get("reservation_source", "Manual Reservation"))
    normalized_item["reservation_reference"] = _reservation_import_normalize_text(normalized_item.get("reservation_reference", normalized_item.get("external_reference", "")))
    normalized_item["external_reference"] = _reservation_import_normalize_text(normalized_item.get("external_reference", normalized_item["reservation_reference"]))
    normalized_item["channel_name"] = _normalize_reservation_source(normalized_item.get("channel_name", normalized_item["reservation_source"]))
    normalized_item["channel_status"] = _normalize_reservation_channel_status(normalized_item.get("channel_status", "SYNCED"))
    normalized_item["last_sync"] = ""
    normalized_item["import_batch_id"] = batch_id
    normalized_item["source_metadata_json"] = json.dumps(source_metadata, ensure_ascii=False, separators=(",", ":"))
    normalized_item["external_payload"] = json.dumps(source_metadata, ensure_ascii=False, separators=(",", ":"))
    normalized_item["sync_status"] = "PREVIEW"
    normalized_item["external_last_sync"] = ""
    normalized_item["created_by"] = _reservation_import_normalize_text(context.get("created_by", "")) or "system"
    if not normalized_item.get("guest_first_name") and normalized_item.get("guest_name"):
        first_name, last_name = _reservation_import_split_guest_name(normalized_item.get("guest_name", ""))
        normalized_item["guest_first_name"] = first_name
        normalized_item["guest_last_name"] = last_name
    matched_property = _reservation_import_match_property(normalized_item, context=context)
    if matched_property:
        normalized_item["property_id"] = str(matched_property.get("id", "")).strip()
        normalized_item["property_name"] = str(matched_property.get("name", "")).strip()
        normalized_item["owner_id"] = str(matched_property.get("owner_id", "")).strip()

    arrival_dt = _reservation_import_parse_date(normalized_item.get("arrival_datetime", ""))
    departure_dt = _reservation_import_parse_date(normalized_item.get("departure_datetime", ""))
    normalized_item["arrival_parsed"] = arrival_dt.isoformat() if arrival_dt else ""
    normalized_item["departure_parsed"] = departure_dt.isoformat() if departure_dt else ""
    normalized_item["validation_errors"] = []
    normalized_item["validation_warnings"] = []
    normalized_item["validation_state"] = "new"
    normalized_item["matched_property"] = {
        "id": normalized_item.get("property_id", ""),
        "name": normalized_item.get("property_name", ""),
        "owner_id": normalized_item.get("owner_id", ""),
    } if normalized_item.get("property_id") else {}
    if not normalized_item.get("property_id"):
        normalized_item["validation_errors"].append("missing_property")
    if normalized_item.get("property_name") and not matched_property:
        normalized_item["validation_errors"].append("unknown_property")
    if not arrival_dt or not departure_dt or departure_dt <= arrival_dt:
        normalized_item["validation_errors"].append("invalid_dates")
    if arrival_dt and arrival_dt.tzinfo is None:
        normalized_item["validation_warnings"].append("timezone_issue")

    existing_reservation = None
    if normalized_item.get("external_reference"):
        for reservation in _load_reservations(property_ids=[normalized_item.get("property_id", "")]):
            if _reservation_import_normalize_text(reservation.get("external_reference", "")).lower() == _reservation_import_normalize_text(normalized_item.get("external_reference", "")).lower():
                existing_reservation = reservation
                break

    if existing_reservation:
        normalized_item["validation_state"] = "updated"
        normalized_item["existing_reservation_id"] = existing_reservation.get("id", "")
    else:
        normalized_item["existing_reservation_id"] = ""

    conflicts = _reservation_import_overlap_conflicts(
        normalized_item.get("property_id", ""),
        arrival_dt,
        departure_dt,
        reservation_id=normalized_item.get("existing_reservation_id", ""),
        source_reference=normalized_item.get("external_reference", ""),
        guest_email=normalized_item.get("guest_email", ""),
    )
    normalized_item["validation_conflicts"] = conflicts
    normalized_item["validation_state"] = "conflict" if any(conflict.get("type") == "conflict" for conflict in conflicts) else normalized_item["validation_state"]
    if any(conflict.get("type") == "duplicate" for conflict in conflicts):
        normalized_item["validation_state"] = "duplicate"

    if normalized_item["validation_errors"]:
        normalized_item["validation_state"] = "error"
    return normalized_item


class ReservationImportAdapter:
    adapter_key = "base"
    source_label = "Manual"

    def parse(self, payload, *, context=None):
        raise NotImplementedError


class ManualReservationAdapter(ReservationImportAdapter):
    adapter_key = "manual"
    source_label = "Manual"

    def parse(self, payload, *, context=None):
        context = context or {}
        item = {
            "property_name": _reservation_import_normalize_text(payload.get("property_name", "")),
            "property_id": _reservation_import_normalize_text(payload.get("property_id", "")),
            "guest_first_name": _reservation_import_normalize_text(payload.get("guest_first_name", "")),
            "guest_last_name": _reservation_import_normalize_text(payload.get("guest_last_name", "")),
            "guest_email": _reservation_import_normalize_text(payload.get("guest_email", "")),
            "guest_phone": _reservation_import_normalize_text(payload.get("guest_phone", "")),
            "adults": int(str(payload.get("adults", 1)).strip() or 1),
            "children": int(str(payload.get("children", 0)).strip() or 0),
            "infants": int(str(payload.get("infants", 0)).strip() or 0),
            "pets": int(str(payload.get("pets", 0)).strip() or 0),
            "arrival_datetime": _reservation_import_normalize_text(payload.get("arrival_datetime", "")),
            "departure_datetime": _reservation_import_normalize_text(payload.get("departure_datetime", "")),
            "external_reference": _reservation_import_normalize_text(payload.get("external_reference", "")),
            "notes": _reservation_import_normalize_text(payload.get("notes", "")),
            "status": _normalize_reservation_status(payload.get("status", "PENDING")),
            "guest_name": _reservation_import_normalize_text(payload.get("guest_name", "")),
        }
        batch_id = context.get("batch_id") or _reservation_import_batch_id()
        preview_item = _reservation_import_build_preview_item(item, adapter_key=self.adapter_key, batch_id=batch_id, context=context, source_metadata={"adapter": self.adapter_key}, imported_source=self.source_label)
        return {
            "adapter": self.adapter_key,
            "source": self.source_label,
            "batch_id": batch_id,
            "items": [preview_item],
        }


class CSVReservationAdapter(ReservationImportAdapter):
    adapter_key = "csv"
    source_label = "CSV"

    def parse(self, payload, *, context=None):
        context = context or {}
        csv_text = _reservation_import_normalize_text(payload.get("csv_text", ""))
        if not csv_text:
            raise ValueError("missing_csv")
        batch_id = context.get("batch_id") or _reservation_import_batch_id()
        rows = []
        reader = csv.DictReader(io.StringIO(csv_text))
        for index, row in enumerate(reader, start=1):
            normalized_row = {str(key or "").strip().lower(): str(value or "").strip() for key, value in row.items()}
            guest_name = normalized_row.get("guest", "")
            guest_first_name = normalized_row.get("guest_first_name", "")
            guest_last_name = normalized_row.get("guest_last_name", "")
            if guest_name and not (guest_first_name or guest_last_name):
                guest_first_name, guest_last_name = _reservation_import_split_guest_name(guest_name)
            item = {
                "property_name": normalized_row.get("property", "") or normalized_row.get("property_name", ""),
                "guest_first_name": guest_first_name,
                "guest_last_name": guest_last_name,
                "guest_email": normalized_row.get("email", "") or normalized_row.get("guest_email", ""),
                "guest_phone": normalized_row.get("phone", "") or normalized_row.get("guest_phone", ""),
                "adults": int(normalized_row.get("adults", "1") or 1),
                "children": int(normalized_row.get("children", "0") or 0),
                "infants": int(normalized_row.get("infants", "0") or 0),
                "pets": int(normalized_row.get("pets", "0") or 0),
                "arrival_datetime": normalized_row.get("arrival", "") or normalized_row.get("arrival_datetime", ""),
                "departure_datetime": normalized_row.get("departure", "") or normalized_row.get("departure_datetime", ""),
                "external_reference": normalized_row.get("external_reference", "") or normalized_row.get("external reference", ""),
                "notes": normalized_row.get("notes", ""),
                "status": _normalize_reservation_status(normalized_row.get("status", "PENDING")),
            }
            preview_item = _reservation_import_build_preview_item(item, adapter_key=self.adapter_key, batch_id=batch_id, context={**context, "created_by": context.get("created_by", "")}, source_metadata={"adapter": self.adapter_key, "row_number": index, "headers": list(row.keys())}, imported_source=self.source_label)
            rows.append(preview_item)
        return {"adapter": self.adapter_key, "source": self.source_label, "batch_id": batch_id, "items": rows}


class ICalReservationAdapter(ReservationImportAdapter):
    adapter_key = "ical"
    source_label = "iCal"

    def parse(self, payload, *, context=None):
        context = context or {}
        batch_id = context.get("batch_id") or _reservation_import_batch_id()
        ics_text = _reservation_import_normalize_text(payload.get("ics_text", ""))
        ics_url = _reservation_import_normalize_text(payload.get("ics_url", ""))
        if not ics_text and ics_url:
            with urllib.request.urlopen(ics_url, timeout=10) as response:
                ics_text = response.read().decode("utf-8", errors="replace")
        if not ics_text:
            raise ValueError("missing_ics")

        lines = []
        for line in str(ics_text).splitlines():
            stripped = line.rstrip("\r\n")
            if not stripped:
                continue
            if stripped[:1] in {" ", "\t"} and lines:
                lines[-1] += stripped[1:]
            else:
                lines.append(stripped)

        events = []
        current = None
        for line in lines:
            if line == "BEGIN:VEVENT":
                current = {}
                continue
            if line == "END:VEVENT":
                if current:
                    events.append(current)
                current = None
                continue
            if current is None or ":" not in line:
                continue
            head, value = line.split(":", 1)
            key = head.split(";", 1)[0].strip().upper()
            current[key] = value.strip()

        items = []
        for index, event in enumerate(events, start=1):
            summary = event.get("SUMMARY", "")
            description = event.get("DESCRIPTION", "")
            location = event.get("LOCATION", "")
            status = event.get("STATUS", "PENDING")
            start_value = event.get("DTSTART", "")
            end_value = event.get("DTEND", "")
            item = {
                "property_name": location or summary,
                "guest_name": summary,
                "notes": description,
                "arrival_datetime": start_value,
                "departure_datetime": end_value,
                "external_reference": event.get("UID", ""),
                "status": "CANCELLED" if str(status).upper() == "CANCELLED" else "CONFIRMED",
            }
            preview_item = _reservation_import_build_preview_item(item, adapter_key=self.adapter_key, batch_id=batch_id, context=context, source_metadata={"adapter": self.adapter_key, "uid": event.get("UID", ""), "summary": summary, "description": description, "location": location, "status": status}, imported_source=self.source_label)
            items.append(preview_item)
        return {"adapter": self.adapter_key, "source": self.source_label, "batch_id": batch_id, "items": items}


class GoogleCalendarReservationAdapter(ICalReservationAdapter):
    adapter_key = "google_calendar"
    source_label = "iCal"


class OTAReservationAdapter(ICalReservationAdapter):
    adapter_key = "ota"
    source_label = "Direct Website"


class ReservationImporter:
    def __init__(self, adapters=None):
        adapters = adapters or []
        self.adapters = {adapter.adapter_key: adapter for adapter in adapters}

    def get_adapter(self, adapter_key):
        return self.adapters.get(str(adapter_key or "").strip())

    def preview(self, adapter_key, payload, *, context=None):
        context = context or {}
        adapter = self.get_adapter(adapter_key)
        if not adapter:
            raise ValueError("unknown_adapter")
        parsed = adapter.parse(payload or {}, context=context)
        items = parsed.get("items", [])
        report = {
            "new_reservations": [],
            "updated_reservations": [],
            "duplicates": [],
            "conflicts": [],
            "errors": [],
            "warnings": [],
        }
        signature_index = set()
        for item in items:
            signature = "|".join([
                _reservation_import_normalize_text(item.get("property_id", "")).lower(),
                _reservation_import_normalize_text(item.get("external_reference", "")).lower(),
                _reservation_import_normalize_text(item.get("arrival_datetime", "")),
                _reservation_import_normalize_text(item.get("departure_datetime", "")),
                _reservation_import_normalize_text(item.get("guest_email", "")).lower(),
            ])
            if signature in signature_index:
                item["validation_state"] = "duplicate"
                item["validation_errors"].append("duplicate_in_batch")
            else:
                signature_index.add(signature)
            report["warnings"].extend(item.get("validation_warnings", []))
            if item["validation_state"] == "updated":
                report["updated_reservations"].append(item)
            elif item["validation_state"] == "duplicate":
                report["duplicates"].append(item)
            elif item["validation_state"] == "conflict":
                report["conflicts"].append(item)
            elif item["validation_state"] == "error":
                report["errors"].append(item)
            else:
                report["new_reservations"].append(item)
        report["ready_to_import"] = not (report["errors"] or report["duplicates"] or report["conflicts"])
        return {
            "adapter": parsed.get("adapter", adapter_key),
            "source": parsed.get("source", adapter.source_label),
            "batch_id": parsed.get("batch_id") or _reservation_import_batch_id(),
            "items": items,
            "report": report,
            "context": context,
        }

    def import_preview(self, preview_payload, *, created_by="system"):
        if isinstance(preview_payload, str):
            preview_payload = json.loads(preview_payload)
        preview_payload = preview_payload if isinstance(preview_payload, dict) else {}
        report = preview_payload.get("report") if isinstance(preview_payload.get("report"), dict) else {}
        if report.get("errors") or report.get("duplicates") or report.get("conflicts"):
            return {"ok": False, "preview": preview_payload, "created": [], "updated": [], "errors": report}

        created_records = []
        updated_records = []
        for item in preview_payload.get("items", []):
            if not isinstance(item, dict):
                continue
            metadata = {
                "kind": "reservation",
                "title": item.get("guest_name", "") or item.get("property_name", "") or "Imported reservation",
                "timeline": [],
                "comments": [],
                "import_batch_id": preview_payload.get("batch_id", ""),
                "source_adapter": preview_payload.get("adapter", ""),
                "source_label": preview_payload.get("source", ""),
                "source_metadata": item.get("source_metadata_json", "{}"),
                "sync_status": "IMPORTED",
            }
            reservation_payload = {
                "id": item.get("existing_reservation_id", "") or uuid4().hex,
                "created_at": _utc_now_iso(),
                "updated_at": _utc_now_iso(),
                "property_id": item.get("property_id", ""),
                "reservation_source": preview_payload.get("source", item.get("reservation_source", "Manual Reservation")),
                "reservation_reference": item.get("reservation_reference", item.get("external_reference", "")),
                "channel_name": item.get("channel_name", preview_payload.get("source", item.get("reservation_source", "Manual Reservation"))),
                "channel_status": "SYNCED",
                "last_sync": _utc_now_iso(),
                "external_payload": item.get("external_payload", item.get("source_metadata_json", "{}")),
                "external_reference": item.get("external_reference", ""),
                "external_last_sync": _utc_now_iso(),
                "import_batch_id": preview_payload.get("batch_id", ""),
                "sync_status": "IMPORTED",
                "source_metadata_json": item.get("source_metadata_json", "{}"),
                "guest_first_name": item.get("guest_first_name", ""),
                "guest_last_name": item.get("guest_last_name", ""),
                "guest_email": item.get("guest_email", ""),
                "guest_phone": item.get("guest_phone", ""),
                "adults": int(item.get("adults", 1) or 1),
                "children": int(item.get("children", 0) or 0),
                "infants": int(item.get("infants", 0) or 0),
                "pets": int(item.get("pets", 0) or 0),
                "arrival_datetime": item.get("arrival_datetime", ""),
                "departure_datetime": item.get("departure_datetime", ""),
                "status": item.get("status", "PENDING"),
                "notes": item.get("notes", ""),
                "language": item.get("language", "en"),
                "created_by": created_by,
                "metadata": metadata,
                "kind": "reservation",
                "title": metadata["title"],
            }
            existing_id = item.get("existing_reservation_id", "")
            saved = _create_reservation(reservation_payload, created_by=created_by)
            if existing_id:
                updated_records.append(saved)
            else:
                created_records.append(saved)
        return {
            "ok": True,
            "preview": preview_payload,
            "created": created_records,
            "updated": updated_records,
            "errors": {},
        }


_RESERVATION_IMPORTER = ReservationImporter([
    ManualReservationAdapter(),
    CSVReservationAdapter(),
    ICalReservationAdapter(),
    GoogleCalendarReservationAdapter(),
    OTAReservationAdapter(),
])


def _reservation_importer():
    return _RESERVATION_IMPORTER


def _reservation_import_request_payload(source_key):
    source_key = str(source_key or "").strip().lower()
    if source_key == "manual":
        return {
            "property_id": str(request.form.get("property_id", "")).strip(),
            "property_name": str(request.form.get("property_name", "")).strip(),
            "guest_name": str(request.form.get("guest_name", "")).strip(),
            "guest_first_name": str(request.form.get("guest_first_name", "")).strip(),
            "guest_last_name": str(request.form.get("guest_last_name", "")).strip(),
            "guest_email": str(request.form.get("guest_email", "")).strip(),
            "guest_phone": str(request.form.get("guest_phone", "")).strip(),
            "adults": str(request.form.get("adults", "1")).strip() or "1",
            "children": str(request.form.get("children", "0")).strip() or "0",
            "infants": str(request.form.get("infants", "0")).strip() or "0",
            "pets": str(request.form.get("pets", "0")).strip() or "0",
            "arrival_datetime": str(request.form.get("arrival_datetime", "")).strip(),
            "departure_datetime": str(request.form.get("departure_datetime", "")).strip(),
            "external_reference": str(request.form.get("external_reference", "")).strip(),
            "notes": str(request.form.get("notes", "")).strip(),
            "status": str(request.form.get("status", "PENDING")).strip(),
        }
    if source_key == "csv":
        uploaded_file = request.files.get("csv_file")
        csv_text = ""
        if uploaded_file and uploaded_file.filename:
            csv_text = uploaded_file.read().decode("utf-8-sig", errors="replace")
        else:
            csv_text = str(request.form.get("csv_text", "")).strip()
        return {
            "csv_text": csv_text,
        }
    if source_key in {"ical", "google_calendar", "ota"}:
        uploaded_file = request.files.get("ics_file")
        ics_text = ""
        if uploaded_file and uploaded_file.filename:
            ics_text = uploaded_file.read().decode("utf-8-sig", errors="replace")
        return {
            "ics_text": ics_text,
            "ics_url": str(request.form.get("ics_url", "")).strip(),
        }
    return {}


def _reservation_import_page_context(*, scope="admin", current_source="manual", preview=None, validation_error="", import_result=None):
    properties = _load_owner_properties()
    return {
        "page_title": "Reservation import",
        "page_meta": "Reservation import wizard",
        "scope": scope,
        "current_source": current_source,
        "import_sources": [
            {"key": "manual", "label": "Manual"},
            {"key": "csv", "label": "CSV"},
            {"key": "ical", "label": "iCal"},
            {"key": "google_calendar", "label": "Google Calendar"},
            {"key": "ota", "label": "OTA"},
            {"key": "direct_booking", "label": "Direct Booking"},
            {"key": "api", "label": "API"},
        ],
        "property_options": properties,
        "preview": preview or {},
        "validation_error": validation_error,
        "import_result": import_result or {},
    }
def _seed_owner_property_activity_backfill(conn):
    property_rows = conn.execute(
        """
        SELECT id, owner_id, created_at, name, location
        FROM owner_properties
        ORDER BY created_at ASC, id ASC
        """
    ).fetchall()

    for row in property_rows:
        property_id = str(row["id"]).strip()
        owner_id = str(row["owner_id"]).strip()
        if not property_id or not owner_id:
            continue

        existing_count = conn.execute(
            "SELECT COUNT(*) AS count FROM owner_property_activity_events WHERE property_id = ?",
            (property_id,),
        ).fetchone()["count"]
        if int(existing_count or 0):
            continue

        created_at = str(row["created_at"]).strip() or _utc_now_iso()
        property_name = str(row["name"]).strip()
        location = str(row["location"]).strip()
        conn.execute(
            """
            INSERT INTO owner_property_activity_events (
                id, property_id, owner_id, created_at, event_type, title, detail
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"{property_id}-created",
                property_id,
                owner_id,
                created_at,
                "property_created",
                "Property created",
                f"{property_name} · {location}".strip(" ·"),
            ),
        )
        conn.execute(
            """
            INSERT INTO owner_property_activity_events (
                id, property_id, owner_id, created_at, event_type, title, detail
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"{property_id}-owner-assigned",
                property_id,
                owner_id,
                created_at,
                "owner_assigned",
                "Owner assigned",
                owner_id,
                ),
            )


def _seed_operations_task_backfill(conn):
    if _OWNER_DB_BACKFILL_SUPPRESSED:
        return

    existing_task_keys = {
        (str(row["source_type"]).strip(), str(row["source_id"]).strip())
        for row in conn.execute("SELECT source_type, source_id FROM operations_tasks").fetchall()
    }

    def _has_task(source_type, source_id):
        return (str(source_type or "").strip(), str(source_id or "").strip()) in existing_task_keys

    for record in _load_pilot_requests():
        source_id = str(record.get("id", "")).strip()
        if not source_id or _has_task("PILOT_REQUEST", source_id):
            continue
        _upsert_operations_task_from_source(
            {
                "id": source_id,
                "request_id": source_id,
                "source_type": "PILOT_REQUEST",
                "source_id": source_id,
                "created_at": str(record.get("created_at", "")).strip() or _utc_now_iso(),
                "updated_at": str(record.get("created_at", "")).strip() or _utc_now_iso(),
                "title": str(record.get("name", "")).strip() or str(record.get("email", "")).strip() or "Pilot request",
                "category": "LEAD",
                "owner_name": str(record.get("name", "")).strip(),
                "owner_email": str(record.get("email", "")).strip(),
                "property_id": "",
                "property_name": str(record.get("city", "")).strip() or str(record.get("property_type", "")).strip(),
                "assigned_to": "",
                "priority": "NORMAL",
                "status": "NEW",
                "due_date": "",
                "notes": str(record.get("concierge_needs", "")).strip(),
                "completed_at": "",
                "owner_id": "",
                "property_location": str(record.get("city", "")).strip(),
                "admin_notes": "",
                "request_status": "new",
                "timeline_detail": str(record.get("concierge_needs", "")).strip(),
            },
            append_created_event=True,
            force_create=True,
        )

    for record in _load_owner_accounts():
        source_id = str(record.get("id", "")).strip()
        if not source_id or _has_task("OWNER_REGISTRATION", source_id):
            continue
        _upsert_operations_task_from_source(
            {
                "id": source_id,
                "request_id": source_id,
                "source_type": "OWNER_REGISTRATION",
                "source_id": source_id,
                "created_at": str(record.get("created_at", "")).strip() or _utc_now_iso(),
                "updated_at": str(record.get("created_at", "")).strip() or _utc_now_iso(),
                "title": str(record.get("full_name", "")).strip() or str(record.get("email", "")).strip() or "Owner registration",
                "category": "OWNER",
                "owner_name": str(record.get("full_name", "")).strip(),
                "owner_email": str(record.get("email", "")).strip(),
                "property_id": "",
                "property_name": str(record.get("property_name", "")).strip() or str(record.get("city", "")).strip(),
                "assigned_to": "",
                "priority": "NORMAL",
                "status": "NEW",
                "due_date": "",
                "notes": str(record.get("notes", "")).strip(),
                "completed_at": "",
                "owner_id": source_id,
                "property_location": str(record.get("city", "")).strip(),
                "admin_notes": "",
                "request_status": "new",
                "timeline_detail": str(record.get("city", "")).strip(),
            },
            append_created_event=True,
            force_create=True,
        )

    for record in _load_partner_applications():
        source_id = str(record.get("id", "")).strip()
        if not source_id or _has_task("PARTNER_APPLICATION", source_id):
            continue
        _upsert_operations_task_from_source(
            {
                "id": source_id,
                "request_id": source_id,
                "source_type": "PARTNER_APPLICATION",
                "source_id": source_id,
                "created_at": str(record.get("created_at", "")).strip() or _utc_now_iso(),
                "updated_at": str(record.get("created_at", "")).strip() or _utc_now_iso(),
                "title": str(record.get("company_name", "")).strip() or str(record.get("contact_person", "")).strip() or "Partner application",
                "category": "PARTNER",
                "owner_name": str(record.get("contact_person", "")).strip() or str(record.get("company_name", "")).strip(),
                "owner_email": str(record.get("email", "")).strip(),
                "property_id": "",
                "property_name": str(record.get("company_name", "")).strip() or str(record.get("city", "")).strip(),
                "assigned_to": "",
                "priority": "NORMAL",
                "status": "NEW",
                "due_date": "",
                "notes": str(record.get("description", "")).strip(),
                "completed_at": "",
                "owner_id": "",
                "property_location": str(record.get("city", "")).strip(),
                "admin_notes": "",
                "request_status": "new",
                "timeline_detail": str(record.get("service_category", "")).strip(),
            },
            append_created_event=True,
            force_create=True,
        )

    for record in _load_professional_applications():
        source_id = str(record.get("id", "")).strip()
        if not source_id or _has_task("PROFESSIONAL_APPLICATION", source_id):
            continue
        _upsert_operations_task_from_source(
            {
                "id": source_id,
                "request_id": source_id,
                "source_type": "PROFESSIONAL_APPLICATION",
                "source_id": source_id,
                "created_at": str(record.get("created_at", "")).strip() or _utc_now_iso(),
                "updated_at": str(record.get("created_at", "")).strip() or _utc_now_iso(),
                "title": str(record.get("full_name", "")).strip() or str(record.get("email", "")).strip() or "Professional application",
                "category": "PROFESSIONAL",
                "owner_name": str(record.get("full_name", "")).strip(),
                "owner_email": str(record.get("email", "")).strip(),
                "property_id": "",
                "property_name": str(record.get("city", "")).strip(),
                "assigned_to": "",
                "priority": "NORMAL",
                "status": "NEW",
                "due_date": "",
                "notes": str(record.get("short_bio", "")).strip(),
                "completed_at": "",
                "owner_id": "",
                "property_location": str(record.get("city", "")).strip(),
                "admin_notes": "",
                "request_status": "new",
                "timeline_detail": str(record.get("professional_category", "")).strip(),
            },
            append_created_event=True,
            force_create=True,
        )

    for record in _load_concierge_requests():
        source_id = str(record.get("id", "")).strip()
        if not source_id or _has_task("CONCIERGE_REQUEST", source_id):
            continue
        _upsert_operations_task_from_source(
            {
                "id": source_id,
                "request_id": source_id,
                "source_type": "CONCIERGE_REQUEST",
                "source_id": source_id,
                "created_at": str(record.get("created_at", "")).strip() or _utc_now_iso(),
                "updated_at": str(record.get("created_at", "")).strip() or _utc_now_iso(),
                "title": str(record.get("message", "")).strip() or str(record.get("name", "")).strip() or "Concierge request",
                "category": "CONCIERGE",
                "owner_name": str(record.get("name", "")).strip(),
                "owner_email": str(record.get("email", "")).strip(),
                "property_id": "",
                "property_name": str(record.get("service_type", "")).strip(),
                "assigned_to": "",
                "priority": "NORMAL",
                "status": "NEW",
                "due_date": "",
                "notes": str(record.get("message", "")).strip(),
                "completed_at": "",
                "owner_id": "",
                "property_location": "",
                "admin_notes": "",
                "request_status": "new",
                "timeline_detail": str(record.get("service_type", "")).strip(),
            },
            append_created_event=True,
            force_create=True,
        )

    for record in _load_service_requests():
        source_id = str(record.get("id", "")).strip()
        if not source_id:
            continue
        source_type = "OWNER_SERVICE_REQUEST" if str(record.get("request_source", "public")).lower() == "owner" else "CONCIERGE_REQUEST"
        if _has_task(source_type, source_id):
            continue
        _upsert_operations_task_from_service_request(record, source_type=source_type, force_create=True)


def _seed_calendar_event_backfill(conn):
    existing_event_ids = {
        str(row["id"]).strip()
        for row in conn.execute("SELECT id FROM calendar_events").fetchall()
    }

    rows = conn.execute(
        """
        SELECT id, request_id, source_type, source_id, owner_id, property_id, created_at, updated_at, title,
                   category, property_name, property_location, owner_name, owner_email, assigned_to, priority, status,
                   due_date, notes, completed_at, owner_id, property_location, admin_notes, request_status,
                   checklist_json, attachments_json, comments_json
        FROM operations_tasks
        """
    ).fetchall()

    for row in rows:
        task_record = _operations_task_from_row(row)
        if not task_record:
            continue

        payload = _calendar_event_payload_from_task(task_record)
        if not payload or payload["id"] in existing_event_ids:
            continue

        conn.execute(
            """
            INSERT INTO calendar_events (
                id, created_at, updated_at, property_id, owner_id, operation_task_id, event_type, title, description,
                start_datetime, end_datetime, all_day, status, assigned_professional, created_by, color, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                created_at = excluded.created_at,
                updated_at = excluded.updated_at,
                property_id = excluded.property_id,
                owner_id = excluded.owner_id,
                operation_task_id = excluded.operation_task_id,
                event_type = excluded.event_type,
                title = excluded.title,
                description = excluded.description,
                start_datetime = excluded.start_datetime,
                end_datetime = excluded.end_datetime,
                all_day = excluded.all_day,
                status = excluded.status,
                assigned_professional = excluded.assigned_professional,
                created_by = excluded.created_by,
                color = excluded.color,
                metadata_json = excluded.metadata_json
            """,
            (
                payload["id"],
                payload["created_at"],
                payload["updated_at"],
                payload["property_id"],
                payload["owner_id"],
                payload["operation_task_id"],
                payload["event_type"],
                payload["title"],
                payload["description"],
                payload["start_datetime"],
                payload["end_datetime"],
                1 if payload["all_day"] else 0,
                payload["status"],
                payload["assigned_professional"],
                payload["created_by"],
                payload["color"],
                payload["metadata_json"],
            ),
        )


def _ensure_owner_db_schema(conn):
    global _OWNER_DB_SCHEMA_INITIALIZING
    if _OWNER_DB_SCHEMA_INITIALIZING:
        return

    _OWNER_DB_SCHEMA_INITIALIZING = True
    try:
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
                notes TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'SETUP',
                guest_guide_ready INTEGER NOT NULL DEFAULT 0,
                access_instructions_ready INTEGER NOT NULL DEFAULT 0,
                emergency_contact_ready INTEGER NOT NULL DEFAULT 0,
                cleaning_partner_ready INTEGER NOT NULL DEFAULT 0,
                admin_notes TEXT NOT NULL DEFAULT ''
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reservations (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                property_id TEXT NOT NULL,
                reservation_source TEXT NOT NULL DEFAULT 'Manual',
                reservation_reference TEXT NOT NULL DEFAULT '',
                channel_name TEXT NOT NULL DEFAULT 'Manual',
                channel_status TEXT NOT NULL DEFAULT 'SYNCED',
                last_sync TEXT NOT NULL DEFAULT '',
                external_payload TEXT NOT NULL DEFAULT '{}',
                external_reference TEXT NOT NULL DEFAULT '',
                external_last_sync TEXT NOT NULL DEFAULT '',
                import_batch_id TEXT NOT NULL DEFAULT '',
                sync_status TEXT NOT NULL DEFAULT 'IDLE',
                source_metadata_json TEXT NOT NULL DEFAULT '{}',
                guest_first_name TEXT NOT NULL DEFAULT '',
                guest_last_name TEXT NOT NULL DEFAULT '',
                guest_email TEXT NOT NULL DEFAULT '',
                guest_phone TEXT NOT NULL DEFAULT '',
                adults INTEGER NOT NULL DEFAULT 1,
                children INTEGER NOT NULL DEFAULT 0,
                infants INTEGER NOT NULL DEFAULT 0,
                pets INTEGER NOT NULL DEFAULT 0,
                arrival_datetime TEXT NOT NULL DEFAULT '',
                departure_datetime TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'PENDING',
                notes TEXT NOT NULL DEFAULT '',
                language TEXT NOT NULL DEFAULT 'en',
                created_by TEXT NOT NULL DEFAULT '',
                metadata_json TEXT NOT NULL DEFAULT '{}'
            )
            """
        )
        existing_reservation_columns = _owner_table_columns(conn, "reservations")
        reservation_required_columns = {
            "reservation_source": "TEXT NOT NULL DEFAULT 'Manual'",
            "reservation_reference": "TEXT NOT NULL DEFAULT ''",
            "channel_name": "TEXT NOT NULL DEFAULT 'Manual'",
            "channel_status": "TEXT NOT NULL DEFAULT 'SYNCED'",
            "last_sync": "TEXT NOT NULL DEFAULT ''",
            "external_payload": "TEXT NOT NULL DEFAULT '{}'",
            "external_reference": "TEXT NOT NULL DEFAULT ''",
            "external_last_sync": "TEXT NOT NULL DEFAULT ''",
            "import_batch_id": "TEXT NOT NULL DEFAULT ''",
            "sync_status": "TEXT NOT NULL DEFAULT 'IDLE'",
            "source_metadata_json": "TEXT NOT NULL DEFAULT '{}'",
        }
        for column_name, column_sql in reservation_required_columns.items():
            if column_name not in existing_reservation_columns:
                conn.execute(f"ALTER TABLE reservations ADD COLUMN {column_name} {column_sql}")
        _ensure_owner_property_activity_schema(conn)
        _ensure_operations_task_schema(conn)
        _ensure_calendar_event_schema(conn)
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
            CREATE TABLE IF NOT EXISTS professional_accounts (
                email TEXT PRIMARY KEY COLLATE NOCASE,
                id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                full_name TEXT NOT NULL,
                phone TEXT NOT NULL,
                company TEXT NOT NULL DEFAULT '',
                service_categories TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'PENDING',
                last_login_at TEXT NOT NULL DEFAULT ''
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS professional_magic_tokens (
                token TEXT PRIMARY KEY,
                email TEXT NOT NULL,
                created_at TEXT NOT NULL
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
        _ensure_owner_property_schema(conn)
        _seed_owner_property_activity_backfill(conn)
        _seed_operations_task_backfill(conn)
        _seed_calendar_event_backfill(conn)
    finally:
        _OWNER_DB_SCHEMA_INITIALIZING = False


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


def _owner_property_from_row(row):
    return {
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
        "status": _normalize_owner_property_status(row["status"] if "status" in row.keys() else OWNER_PROPERTY_STATUS_DEFAULT),
        "guest_guide_ready": bool(int(row["guest_guide_ready"] or 0)) if "guest_guide_ready" in row.keys() else False,
        "access_instructions_ready": bool(int(row["access_instructions_ready"] or 0)) if "access_instructions_ready" in row.keys() else False,
        "emergency_contact_ready": bool(int(row["emergency_contact_ready"] or 0)) if "emergency_contact_ready" in row.keys() else False,
        "cleaning_partner_ready": bool(int(row["cleaning_partner_ready"] or 0)) if "cleaning_partner_ready" in row.keys() else False,
        "admin_notes": str(row["admin_notes"]) if "admin_notes" in row.keys() else "",
    }


def _property_activity_from_row(row):
    return {
        "id": str(row["id"]),
        "property_id": str(row["property_id"]),
        "owner_id": str(row["owner_id"]),
        "created_at": str(row["created_at"]),
        "event_type": str(row["event_type"]),
        "title": str(row["title"]),
        "detail": str(row["detail"]),
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

    events = [
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
    events.extend(_demo_records("owner_activity_events"))
    if target_owner_id:
        events = [event for event in events if str(event.get("owner_id", "")).strip() == target_owner_id]
    events.sort(key=lambda item: (str(item.get("created_at", "")), str(item.get("id", ""))), reverse=True)
    return events


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


def _load_property_activity_events(property_id=None):
    with _owner_db_connection() as conn:
        _ensure_owner_db_schema(conn)
        _migrate_owner_jsonl_backups(conn)
        query = """
            SELECT id, property_id, owner_id, created_at, event_type, title, detail
            FROM owner_property_activity_events
        """
        params = []
        target_property_id = str(property_id or "").strip()
        if target_property_id:
            query += " WHERE property_id = ?"
            params.append(target_property_id)
        query += " ORDER BY created_at DESC, sequence DESC"
        rows = conn.execute(query, params).fetchall()
    events = [_property_activity_from_row(row) for row in rows]
    events.extend(_demo_records("property_activity_events"))
    if target_property_id:
        events = [event for event in events if str(event.get("property_id", "")).strip() == target_property_id]
    events.sort(key=lambda item: (str(item.get("created_at", "")), str(item.get("id", ""))), reverse=True)
    return events


def _append_property_activity_event(property_id, owner_id, event_type, title, detail=""):
    target_property_id = str(property_id or "").strip()
    target_owner_id = str(owner_id or "").strip()
    if not target_property_id or not target_owner_id:
        return None

    normalized_event_type = str(event_type or "").strip()
    normalized_title = str(title or "").strip()
    if not normalized_event_type or not normalized_title:
        return None

    event = {
        "id": uuid4().hex,
        "property_id": target_property_id,
        "owner_id": target_owner_id,
        "created_at": _utc_now_iso(),
        "event_type": normalized_event_type,
        "title": normalized_title,
        "detail": str(detail or "").strip(),
    }

    try:
        with _owner_db_connection() as conn:
            _ensure_owner_db_schema(conn)
            _migrate_owner_jsonl_backups(conn)
            conn.execute(
                """
                INSERT INTO owner_property_activity_events (
                    id, property_id, owner_id, created_at, event_type, title, detail
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event["id"],
                    event["property_id"],
                    event["owner_id"],
                    event["created_at"],
                    event["event_type"],
                    event["title"],
                    event["detail"],
                ),
            )
    except Exception as exc:
        app.logger.warning("Property activity event append failed for %s: %s", target_property_id, type(exc).__name__)
        return None
    return event


def _operations_task_json_dumps(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _operations_task_update_json_fields(task_id, *, checklist_json=None, attachments_json=None, comments_json=None, completion_report_json=None, updated_at=None):
    target_task_id = str(task_id or "").strip()
    if not target_task_id:
        return None

    updated_at_value = str(updated_at or "").strip() or _utc_now_iso()
    set_clauses = ["updated_at = ?"]
    params = [updated_at_value]

    if checklist_json is not None:
        set_clauses.append("checklist_json = ?")
        params.append(str(checklist_json))
    if attachments_json is not None:
        set_clauses.append("attachments_json = ?")
        params.append(str(attachments_json))
    if comments_json is not None:
        set_clauses.append("comments_json = ?")
        params.append(str(comments_json))
    if completion_report_json is not None:
        set_clauses.append("completion_report_json = ?")
        params.append(str(completion_report_json))

    params.extend([target_task_id, target_task_id, target_task_id])

    try:
        with _owner_db_connection() as conn:
            _ensure_owner_db_schema(conn)
            _migrate_owner_jsonl_backups(conn)
            conn.execute(
                f"""
                UPDATE operations_tasks
                SET {", ".join(set_clauses)}
                WHERE id = ? OR request_id = ? OR source_id = ?
                """,
                params,
            )
    except Exception as exc:
        app.logger.warning("Operations task metadata update failed for %s: %s", target_task_id, type(exc).__name__)
        return None

    return _find_operations_task(target_task_id)


def _operations_task_append_checklist_event(task_id, checklist_items):
    checklist_detail = ", ".join(
        item["label"]
        for item in checklist_items
        if item.get("checked")
    ) or "Checklist updated"
    _append_operations_task_event(
        task_id,
        "checklist_updated",
        "Checklist updated",
        checklist_detail,
        status=_find_operations_task(task_id).get("status", "NEW") if _find_operations_task(task_id) else "NEW",
    )


def _append_operations_task_comment(task_id, operator, comment, comment_type="General"):
    target_task_id = str(task_id or "").strip()
    normalized_comment = str(comment or "").strip()
    if not target_task_id or not normalized_comment:
        return None

    comment_entry = {
        "created_at": _utc_now_iso(),
        "operator": str(operator or "").strip() or _current_admin_operator_key(),
        "comment": normalized_comment,
        "type": str(comment_type or "").strip() or "General",
        "visibility": "internal",
        "author_role": "operations",
    }

    task = _find_operations_task(target_task_id)
    current_comments = list((task or {}).get("comments") or [])
    current_comments.append(comment_entry)
    updated_task = _operations_task_update_json_fields(
        target_task_id,
        comments_json=_operations_task_json_dumps(current_comments),
    )
    if not updated_task:
        return None

    _append_operations_task_event(
        target_task_id,
        "comment_added_internal",
        "Comment added",
        normalized_comment,
        status=updated_task.get("status", "NEW"),
    )
    return comment_entry


def _append_operations_task_attachment(task_id, *, name, uploaded_by="", category="", slot="", mime_type="", url=""):
    target_task_id = str(task_id or "").strip()
    normalized_name = str(name or "").strip()
    if not target_task_id or not normalized_name:
        return None

    attachment_entry = {
        "created_at": _utc_now_iso(),
        "name": normalized_name,
        "url": str(url or "").strip(),
        "uploaded_by": str(uploaded_by or "").strip() or _current_admin_operator_key(),
        "category": str(category or "").strip(),
        "slot": str(slot or "").strip(),
        "mime_type": str(mime_type or "").strip(),
    }

    task = _find_operations_task(target_task_id)
    current_attachments = list((task or {}).get("attachments") or [])
    current_attachments.append(attachment_entry)
    updated_task = _operations_task_update_json_fields(
        target_task_id,
        attachments_json=_operations_task_json_dumps(current_attachments),
    )
    if not updated_task:
        return None

    _append_operations_task_event(
        target_task_id,
        "attachment_added",
        "Attachment added",
        f"{attachment_entry['slot'] or attachment_entry['category'] or 'Attachment'} · {normalized_name}",
        status=updated_task.get("status", "NEW"),
    )
    return attachment_entry


def _update_operations_task_completion_report(task_id, report_data):
    target_task_id = str(task_id or "").strip()
    if not target_task_id:
        return None

    report_entry = _operations_task_completion_report(report_data)
    updated_task = _operations_task_update_json_fields(
        target_task_id,
        completion_report_json=_operations_task_json_dumps(report_entry),
    )
    if not updated_task:
        return None

    _append_operations_task_event(
        target_task_id,
        "completion_report_updated",
        "Completion report updated",
        report_entry.get("completed_work", "") or "Completion report saved",
        status=updated_task.get("status", "NEW"),
    )
    return report_entry


def _append_professional_workflow_notification(task, event_type, title, detail, status, recipient="", metadata=""):
    _append_operations_notification(
        event_type,
        title,
        detail,
        task_id=task.get("id", ""),
        source_type=task.get("source_type", ""),
        source_id=task.get("source_id", ""),
        status=status,
        channel="SYSTEM",
        recipient=recipient,
        operator_key=_current_admin_operator_key(),
        metadata=metadata,
    )
    _append_operations_task_event(
        task.get("id", ""),
        event_type,
        title,
        detail,
        status=status,
    )


def _professional_task_transition(task, professional_account, action, *, note_text="", report_data=None, attachment_data=None):
    task_id = str((task or {}).get("id", "")).strip()
    if not task_id:
        return None

    current_status = _normalize_operations_task_status((task or {}).get("status", "NEW"))
    action = str(action or "").strip().lower()
    target_status = None
    event_type = None
    event_title = None
    event_detail = ""

    if action == "accept" and current_status in {"NEW", "ASSIGNED"}:
        target_status = "ACCEPTED"
        event_type = "professional_accepted"
        event_title = "Professional accepted task"
        event_detail = _professional_account_display_label(professional_account)
    elif action == "on_the_way" and current_status in {"ACCEPTED", "ASSIGNED"}:
        target_status = "ON_THE_WAY"
        event_type = "professional_on_the_way"
        event_title = "Professional on the way"
        event_detail = _professional_account_display_label(professional_account)
    elif action == "arrived" and current_status in {"ON_THE_WAY", "ACCEPTED"}:
        target_status = "ARRIVED"
        event_type = "professional_arrived"
        event_title = "Professional arrived"
        event_detail = _professional_account_display_label(professional_account)
    elif action == "start" and current_status in {"ACCEPTED", "ON_THE_WAY", "ARRIVED", "PAUSED"}:
        target_status = "IN_PROGRESS"
        event_type = "professional_started"
        event_title = "Professional started task"
        event_detail = _professional_account_display_label(professional_account)
    elif action == "pause" and current_status in {"IN_PROGRESS", "ARRIVED"}:
        target_status = "PAUSED"
        event_type = "professional_paused"
        event_title = "Professional paused task"
        event_detail = note_text or _professional_account_display_label(professional_account)
    elif action == "resume" and current_status == "PAUSED":
        target_status = "IN_PROGRESS"
        event_type = "professional_resumed"
        event_title = "Professional resumed task"
        event_detail = _professional_account_display_label(professional_account)
    elif action == "complete":
        target_status = "COMPLETED"
        event_type = "professional_completed"
        event_title = "Professional completed task"
        event_detail = note_text or _professional_account_display_label(professional_account)

    if attachment_data:
        slot = str(attachment_data.get("slot", "")).strip()
        category = str(attachment_data.get("category", "")).strip()
        filename = str(attachment_data.get("filename", "")).strip()
        mime_type = str(attachment_data.get("mime_type", "")).strip()
        if slot or category or filename:
            _append_operations_task_attachment(
                task_id,
                name=filename or f"{slot or category or 'attachment'} placeholder",
                uploaded_by=_professional_account_display_label(professional_account),
                category=category,
                slot=slot,
                mime_type=mime_type,
            )

    if note_text:
        _append_operations_task_comment(
            task_id,
            _professional_account_display_label(professional_account),
            note_text,
        )

    if report_data is not None:
        _update_operations_task_completion_report(task_id, report_data)

    if target_status is None:
        return _find_operations_task(task_id)

    updated_task = _update_operations_task_details(
        task_id,
        status=target_status,
        assigned_to=(task or {}).get("assigned_to", ""),
        assigned_professional_id=(professional_account or {}).get("id", ""),
        source="professional",
    )
    if not updated_task:
        return None

    _append_operations_task_event(
        task_id,
        event_type,
        event_title,
        event_detail,
        status=target_status,
    )
    _append_operations_notification(
        event_type,
        event_title,
        event_detail,
        task_id=task_id,
        source_type=updated_task.get("source_type", ""),
        source_id=updated_task.get("source_id", ""),
        status=target_status,
        channel="SYSTEM",
        recipient=(professional_account or {}).get("email", ""),
        operator_key=_current_admin_operator_key(),
        metadata="professional_workflow",
    )

    return _find_operations_task(task_id)


def _operations_task_from_row(row):
    if row is None:
        return None

    task_id = str(row["id"] if "id" in row.keys() and row["id"] else row["request_id"]).strip()
    request_id = str(row["request_id"] if "request_id" in row.keys() and row["request_id"] else task_id).strip()
    source_type = str(row["source_type"]) if "source_type" in row.keys() else ""
    source_id = str(row["source_id"]) if "source_id" in row.keys() else request_id
    notes = str(row["notes"]) if "notes" in row.keys() else ""
    admin_notes = str(row["admin_notes"]) if "admin_notes" in row.keys() else ""
    if not notes:
        notes = admin_notes
    if not admin_notes:
        admin_notes = notes
    completed_at = str(row["completed_at"]) if "completed_at" in row.keys() else ""
    checklist_json = str(row["checklist_json"]) if "checklist_json" in row.keys() else ""
    attachments_json = str(row["attachments_json"]) if "attachments_json" in row.keys() else ""
    comments_json = str(row["comments_json"]) if "comments_json" in row.keys() else ""
    completion_report_json = str(row["completion_report_json"]) if "completion_report_json" in row.keys() else ""

    return {
        "id": task_id,
        "request_id": request_id,
        "source_type": source_type,
        "source_id": source_id,
        "owner_id": str(row["owner_id"]) if "owner_id" in row.keys() else "",
        "property_id": str(row["property_id"]) if "property_id" in row.keys() else "",
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
        "title": str(row["title"]),
        "category": str(row["category"]) if "category" in row.keys() else "",
        "property_name": str(row["property_name"]) if "property_name" in row.keys() else "",
        "property_location": str(row["property_location"]) if "property_location" in row.keys() else "",
        "owner_name": str(row["owner_name"]) if "owner_name" in row.keys() else "",
        "owner_email": str(row["owner_email"]) if "owner_email" in row.keys() else "",
        "assigned_to": str(row["assigned_to"]) if "assigned_to" in row.keys() else "",
        "assigned_professional_id": str(row["assigned_professional_id"]) if "assigned_professional_id" in row.keys() else "",
        "priority": _normalize_operations_task_priority(row["priority"] if "priority" in row.keys() else "NORMAL"),
        "status": _normalize_operations_task_status(row["status"] if "status" in row.keys() else "NEW"),
        "due_date": str(row["due_date"]) if "due_date" in row.keys() else "",
        "notes": notes,
        "completed_at": completed_at,
        "completion_report_json": completion_report_json,
        "completion_report": _operations_task_completion_report(completion_report_json),
        "admin_notes": admin_notes,
        "request_status": _normalize_service_request_status(row["request_status"] if "request_status" in row.keys() else "new"),
        "checklist_json": checklist_json,
        "checklist_items": _operations_task_checklist_items(checklist_json),
        "attachments_json": attachments_json,
        "attachments": _operations_task_attachments(attachments_json),
        "comments_json": comments_json,
        "comments": _operations_task_comments(comments_json),
    }


def _load_operations_tasks():
    with _owner_db_connection() as conn:
        _ensure_owner_db_schema(conn)
        _migrate_owner_jsonl_backups(conn)
        rows = conn.execute(
            """
            SELECT id, request_id, source_type, source_id, owner_id, property_id, created_at, updated_at, title,
                   category, property_name, property_location, owner_name, owner_email, assigned_to, assigned_professional_id, priority, status,
                   due_date, notes, completed_at, completion_report_json, admin_notes, request_status, checklist_json, attachments_json, comments_json
            FROM operations_tasks
            ORDER BY updated_at DESC, created_at DESC, id DESC
            """
        ).fetchall()

    tasks = [_operations_task_from_row(row) for row in rows]
    tasks.extend(_demo_records("operations_tasks"))
    tasks.sort(key=lambda item: (str(item.get("updated_at", "")), str(item.get("created_at", "")), str(item.get("id", ""))), reverse=True)
    return tasks


def _find_operations_task(task_id):
    target_task_id = str(task_id or "").strip()
    if not target_task_id:
        return None

    with _owner_db_connection() as conn:
        _ensure_owner_db_schema(conn)
        _migrate_owner_jsonl_backups(conn)
        row = conn.execute(
            """
            SELECT id, request_id, source_type, source_id, owner_id, property_id, created_at, updated_at, title,
                   category, property_name, property_location, owner_name, owner_email, assigned_to, assigned_professional_id, priority, status,
                   due_date, notes, completed_at, completion_report_json, admin_notes, request_status, checklist_json, attachments_json, comments_json
            FROM operations_tasks
            WHERE id = ? OR request_id = ? OR source_id = ?
            LIMIT 1
            """,
            (target_task_id, target_task_id, target_task_id),
        ).fetchone()

    if row:
        return _operations_task_from_row(row)
    return _demo_operations_task_by_id(target_task_id)


def _load_operations_task_events(task_id=None):
    with _owner_db_connection() as conn:
        _ensure_owner_db_schema(conn)
        _migrate_owner_jsonl_backups(conn)
        query = """
            SELECT id, task_id, created_at, event_type, title, detail, status
            FROM operations_task_events
        """
        params = []
        target_task_id = str(task_id or "").strip()
        if target_task_id:
            query += " WHERE task_id = ?"
            params.append(target_task_id)
        query += " ORDER BY created_at DESC, sequence DESC"
        rows = conn.execute(query, params).fetchall()

    events = [
        {
            "id": str(row["id"]),
            "task_id": str(row["task_id"]),
            "created_at": str(row["created_at"]),
            "event_type": str(row["event_type"]),
            "title": str(row["title"]),
            "detail": str(row["detail"]),
            "status": _normalize_operations_task_status(row["status"]),
        }
        for row in rows
    ]
    events.extend(_demo_records("operations_task_events"))
    if target_task_id:
        events = [event for event in events if str(event.get("task_id", "")).strip() == target_task_id]
    events.sort(key=lambda item: (str(item.get("created_at", "")), str(item.get("id", ""))), reverse=True)
    return events


def _append_operations_task_event(task_id, event_type, title, detail="", status=None):
    target_task_id = str(task_id or "").strip()
    if not target_task_id:
        return None

    normalized_event_type = str(event_type or "").strip()
    normalized_title = str(title or "").strip()
    if not normalized_event_type or not normalized_title:
        return None

    event = {
        "id": uuid4().hex,
        "task_id": target_task_id,
        "created_at": _utc_now_iso(),
        "event_type": normalized_event_type,
        "title": normalized_title,
        "detail": str(detail or "").strip(),
        "status": _normalize_operations_task_status(status or "NEW"),
    }

    try:
        with _owner_db_connection() as conn:
            _ensure_owner_db_schema(conn)
            _migrate_owner_jsonl_backups(conn)
            conn.execute(
                """
                INSERT INTO operations_task_events (id, task_id, created_at, event_type, title, detail, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event["id"],
                    event["task_id"],
                    event["created_at"],
                    event["event_type"],
                    event["title"],
                    event["detail"],
                    event["status"],
                ),
            )
    except Exception as exc:
        app.logger.warning("Operations task event append failed for %s: %s", target_task_id, type(exc).__name__)
        return None
    return event


def _operations_notification_from_row(row):
    if row is None:
        return None

    return {
        "id": str(row["id"]),
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
        "event_type": str(row["event_type"]),
        "status": str(row["status"]),
        "title": str(row["title"]),
        "detail": str(row["detail"]),
        "task_id": str(row["task_id"]),
        "source_type": str(row["source_type"]),
        "source_id": str(row["source_id"]),
        "channel": str(row["channel"]),
        "recipient": str(row["recipient"]),
        "operator_key": str(row["operator_key"]),
        "metadata": str(row["metadata"]),
    }


def _load_operations_notifications(limit=100, event_type=None, status=None):
    query = """
        SELECT id, created_at, updated_at, event_type, status, title, detail, task_id, source_type, source_id, channel, recipient, operator_key, metadata
        FROM operations_notifications
    """
    params = []
    clauses = []
    if event_type:
        clauses.append("event_type = ?")
        params.append(str(event_type).strip())
    if status:
        clauses.append("status = ?")
        params.append(str(status).strip())
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY created_at DESC, sequence DESC"
    if limit is not None:
        query += " LIMIT ?"
        params.append(int(limit))

    with _owner_db_connection() as conn:
        _ensure_owner_db_schema(conn)
        _migrate_owner_jsonl_backups(conn)
        rows = conn.execute(query, params).fetchall()

    return [_operations_notification_from_row(row) for row in rows]


def _current_admin_operator_key():
    auth = getattr(request, "authorization", None)
    username = str(getattr(auth, "username", "") or "").strip()
    if username:
        return username
    return str(os.getenv("ADMIN_USERNAME", "")).strip() or "admin"


def _normalize_operations_notification_flag(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on", "enabled"}


def _operations_notification_preference_from_row(row):
    if row is None:
        return None

    return {
        "operator_key": str(row["operator_key"]),
        "operator_name": str(row["operator_name"]),
        "email_enabled": bool(int(row["email_enabled"] or 0)),
        "telegram_enabled": bool(int(row["telegram_enabled"] or 0)),
        "updated_at": str(row["updated_at"]),
    }


def _load_operations_notification_preferences(operator_key=None, create_default=False):
    with _owner_db_connection() as conn:
        _ensure_owner_db_schema(conn)
        _migrate_owner_jsonl_backups(conn)
        query = """
            SELECT operator_key, operator_name, email_enabled, telegram_enabled, updated_at
            FROM operations_notification_preferences
        """
        params = []
        target_operator_key = str(operator_key or "").strip()
        if target_operator_key:
            query += " WHERE operator_key = ?"
            params.append(target_operator_key)
        query += " ORDER BY operator_key ASC"
        rows = conn.execute(query, params).fetchall()
        if not rows and create_default:
            default_operator_key = target_operator_key or str(os.getenv("ADMIN_USERNAME", "")).strip() or "admin"
            default_operator_name = default_operator_key
            updated_at = _utc_now_iso()
            conn.execute(
                """
                INSERT INTO operations_notification_preferences (
                    operator_key, operator_name, email_enabled, telegram_enabled, updated_at
                ) VALUES (?, ?, 1, 1, ?)
                ON CONFLICT(operator_key) DO UPDATE SET
                    operator_name = excluded.operator_name,
                    email_enabled = excluded.email_enabled,
                    telegram_enabled = excluded.telegram_enabled,
                    updated_at = excluded.updated_at
                """,
                (default_operator_key, default_operator_name, updated_at),
            )
            rows = conn.execute(query, params).fetchall()

    preferences = [_operations_notification_preference_from_row(row) for row in rows]
    if preferences:
        return preferences

    fallback_key = str(operator_key or "").strip() or str(os.getenv("ADMIN_USERNAME", "")).strip() or "admin"
    return [{
        "operator_key": fallback_key,
        "operator_name": fallback_key,
        "email_enabled": True,
        "telegram_enabled": True,
        "updated_at": _utc_now_iso(),
    }]


def _set_operations_notification_preferences(operator_key, *, operator_name=None, email_enabled=True, telegram_enabled=True):
    target_operator_key = str(operator_key or "").strip()
    if not target_operator_key:
        return None

    updated_at = _utc_now_iso()
    target_operator_name = str(operator_name or "").strip() or target_operator_key

    with _owner_db_connection() as conn:
        _ensure_owner_db_schema(conn)
        _migrate_owner_jsonl_backups(conn)
        conn.execute(
            """
            INSERT INTO operations_notification_preferences (
                operator_key, operator_name, email_enabled, telegram_enabled, updated_at
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(operator_key) DO UPDATE SET
                operator_name = excluded.operator_name,
                email_enabled = excluded.email_enabled,
                telegram_enabled = excluded.telegram_enabled,
                updated_at = excluded.updated_at
            """,
            (
                target_operator_key,
                target_operator_name,
                1 if email_enabled else 0,
                1 if telegram_enabled else 0,
                updated_at,
            ),
        )

    return _load_operations_notification_preferences(target_operator_key, create_default=True)[0]


def _append_operations_notification(event_type, title, detail="", *, task_id="", source_type="", source_id="", status="", channel="", recipient="", operator_key="", metadata=""):
    normalized_event_type = str(event_type or "").strip()
    normalized_title = str(title or "").strip()
    if not normalized_event_type or not normalized_title:
        return None

    created_at = _utc_now_iso()
    notification = {
        "id": uuid4().hex,
        "created_at": created_at,
        "updated_at": created_at,
        "event_type": normalized_event_type,
        "status": str(status or "").strip(),
        "title": normalized_title,
        "detail": str(detail or "").strip(),
        "task_id": str(task_id or "").strip(),
        "source_type": str(source_type or "").strip(),
        "source_id": str(source_id or "").strip(),
        "channel": str(channel or "").strip(),
        "recipient": str(recipient or "").strip(),
        "operator_key": str(operator_key or "").strip(),
        "metadata": str(metadata or "").strip(),
    }

    try:
        with _owner_db_connection() as conn:
            _ensure_owner_db_schema(conn)
            _migrate_owner_jsonl_backups(conn)
            conn.execute(
                """
                INSERT INTO operations_notifications (
                    id, created_at, updated_at, event_type, status, title, detail, task_id, source_type,
                    source_id, channel, recipient, operator_key, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    notification["id"],
                    notification["created_at"],
                    notification["updated_at"],
                    notification["event_type"],
                    notification["status"],
                    notification["title"],
                    notification["detail"],
                    notification["task_id"],
                    notification["source_type"],
                    notification["source_id"],
                    notification["channel"],
                    notification["recipient"],
                    notification["operator_key"],
                    notification["metadata"],
                ),
            )
    except Exception as exc:
        app.logger.warning("Operations notification append failed for %s: %s", normalized_event_type, type(exc).__name__)
        return None

    return notification


def _build_operations_notification_summary(task_record):
    created_at = _format_owner_portal_timestamp(task_record.get("created_at", "")) or str(task_record.get("created_at", "")).strip()
    return {
        "title": str(task_record.get("title", "")).strip() or "Operations task",
        "category": str(task_record.get("category", "")).strip() or "n/a",
        "owner": str(task_record.get("owner_name", "")).strip() or str(task_record.get("owner_email", "")).strip() or "n/a",
        "property": str(task_record.get("property_name", "")).strip() or str(task_record.get("property_location", "")).strip() or "n/a",
        "created_at": created_at,
    }


def _build_operations_notification_body(task_record, admin_detail_url):
    summary = _build_operations_notification_summary(task_record)
    lines = [
        f"Task title: {summary['title']}",
        f"Category: {summary['category']}",
        f"Owner: {summary['owner']}",
        f"Property: {summary['property']}",
        f"Created date: {summary['created_at']}",
        f"Admin URL: {admin_detail_url}",
    ]
    return "\n".join(lines)


def _build_operations_notification_telegram_text(task_record, admin_detail_url):
    summary = _build_operations_notification_summary(task_record)
    return "\n".join([
        "Operations task created",
        f"Task title: {summary['title']}",
        f"Category: {summary['category']}",
        f"Owner: {summary['owner']}",
        f"Property: {summary['property']}",
        f"Created date: {summary['created_at']}",
        f"Admin URL: {admin_detail_url}",
    ])


def _send_operations_notification_via_email(task_record, admin_detail_url, recipient_email):
    smtp_host = os.getenv("SMTP_HOST", "").strip()
    smtp_port_raw = os.getenv("SMTP_PORT", "").strip()
    smtp_username = os.getenv("SMTP_USERNAME", "").strip()
    smtp_password = os.getenv("SMTP_PASSWORD", "").strip()
    smtp_from = os.getenv("SMTP_FROM", "").strip()

    if not smtp_host or not smtp_port_raw or not smtp_from or not recipient_email:
        return False, "smtp_not_configured"

    try:
        smtp_port = int(smtp_port_raw)
    except ValueError:
        return False, "smtp_invalid_port"

    message = EmailMessage()
    message["Subject"] = "[BlackSeaConnect] Operations task notification"
    message["From"] = smtp_from
    message["To"] = recipient_email
    message.set_content(_build_operations_notification_body(task_record, admin_detail_url))

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as client:
            client.ehlo()
            try:
                client.starttls()
                client.ehlo()
            except smtplib.SMTPException:
                pass
            if smtp_username and smtp_password:
                client.login(smtp_username, smtp_password)
            client.send_message(message)
    except Exception as exc:
        app.logger.warning("Operations notification email send failed: %s", type(exc).__name__)
        return False, "smtp_send_failed"

    return True, None


def _send_plaintext_email(recipient_email, subject, body):
    smtp_host = os.getenv("SMTP_HOST", "").strip()
    smtp_port_raw = os.getenv("SMTP_PORT", "").strip()
    smtp_username = os.getenv("SMTP_USERNAME", "").strip()
    smtp_password = os.getenv("SMTP_PASSWORD", "").strip()
    smtp_from = os.getenv("SMTP_FROM", "").strip()

    if not smtp_host or not smtp_port_raw or not smtp_from or not recipient_email:
        return False, "smtp_not_configured"

    try:
        smtp_port = int(smtp_port_raw)
    except ValueError:
        return False, "smtp_invalid_port"

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = smtp_from
    message["To"] = recipient_email
    message.set_content(body)

    try:
        smtp_factory = smtplib.SMTP_SSL if smtp_port == 465 else smtplib.SMTP
        with smtp_factory(smtp_host, smtp_port, timeout=15) as client:
            client.ehlo()
            if smtp_port != 465:
                try:
                    client.starttls()
                    client.ehlo()
                except smtplib.SMTPException:
                    pass
            if smtp_username and smtp_password:
                client.login(smtp_username, smtp_password)
            client.send_message(message)
    except Exception as exc:
        app.logger.warning("Plaintext email send failed for %s: %s", _mask_email(recipient_email), type(exc).__name__)
        return False, "smtp_send_failed"

    return True, None


def _send_operations_notification_via_telegram(task_record, admin_detail_url, telegram_bot_token, telegram_chat_id):
    telegram_text = _build_operations_notification_telegram_text(task_record, admin_detail_url)
    telegram_url = f"https://api.telegram.org/bot{telegram_bot_token}/sendMessage"
    payload = {
        "chat_id": telegram_chat_id,
        "text": telegram_text,
        "disable_web_page_preview": "true",
    }
    data = urllib.parse.urlencode(payload).encode("utf-8")
    request_obj = urllib.request.Request(telegram_url, data=data, method="POST")
    request_obj.add_header("Content-Type", "application/x-www-form-urlencoded")

    try:
        with urllib.request.urlopen(request_obj, timeout=15) as response:
            response_status = getattr(response, "status", response.getcode())
            if response_status and 200 <= int(response_status) < 300:
                return True, None
            app.logger.warning("Operations notification send failed via Telegram: unexpected status %s.", response_status)
            return False, "telegram_bad_status"
    except Exception as exc:
        app.logger.warning("Operations notification send failed via Telegram: %s", type(exc).__name__)
        return False, "telegram_send_failed"


def _dispatch_operations_notification(task_record, admin_detail_url, notification_type="task_created"):
    if not task_record:
        return False, []

    admin_email = os.getenv("ADMIN_NOTIFICATION_EMAIL", "").strip()
    telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    preferences = _load_operations_notification_preferences(create_default=True)
    operator_key = preferences[0]["operator_key"] if preferences else _current_admin_operator_key()
    channels = {
        "EMAIL": any(pref.get("email_enabled") for pref in preferences),
        "TELEGRAM": any(pref.get("telegram_enabled") for pref in preferences),
    }
    results = []
    any_success = False

    if not admin_email:
        return False, results

    admin_detail_url = str(admin_detail_url or "").strip()

    if channels["EMAIL"] and admin_email:
        email_ok, email_reason = _send_operations_notification_via_email(task_record, admin_detail_url, admin_email)
        results.append(("EMAIL", email_ok, email_reason))
        notification = _append_operations_notification(
            "notification_sent" if email_ok else "notification_failed",
            "Task notification email sent" if email_ok else "Task notification email failed",
            _build_operations_notification_body(task_record, admin_detail_url),
            task_id=task_record.get("id", ""),
            source_type=task_record.get("source_type", ""),
            source_id=task_record.get("source_id", ""),
            status="sent" if email_ok else "failed",
            channel="EMAIL",
            recipient=admin_email,
            operator_key=operator_key,
            metadata=notification_type,
        )
        if notification:
            _append_operations_task_event(
                task_record.get("id", ""),
                "notification_sent" if email_ok else "notification_failed",
                "Notification sent" if email_ok else "Notification failed",
                f"EMAIL · {notification['title']}" if email_ok else f"EMAIL · {email_reason or 'smtp_send_failed'}",
                status=task_record.get("status", "NEW"),
            )
        any_success = any_success or email_ok
    elif channels["EMAIL"]:
        results.append(("EMAIL", False, "email_not_configured"))
        _append_operations_notification(
            "notification_failed",
            "Task notification email failed",
            _build_operations_notification_body(task_record, admin_detail_url),
            task_id=task_record.get("id", ""),
            source_type=task_record.get("source_type", ""),
            source_id=task_record.get("source_id", ""),
            status="failed",
            channel="EMAIL",
            recipient=admin_email,
            operator_key=operator_key,
            metadata=notification_type,
        )
        _append_operations_task_event(
            task_record.get("id", ""),
            "notification_failed",
            "Notification failed",
            "EMAIL · smtp_not_configured",
            status=task_record.get("status", "NEW"),
        )

    if channels["TELEGRAM"] and telegram_bot_token and telegram_chat_id:
        telegram_ok, telegram_reason = _send_operations_notification_via_telegram(
            task_record,
            admin_detail_url,
            telegram_bot_token,
            telegram_chat_id,
        )
        results.append(("TELEGRAM", telegram_ok, telegram_reason))
        notification = _append_operations_notification(
            "notification_sent" if telegram_ok else "notification_failed",
            "Task notification telegram sent" if telegram_ok else "Task notification telegram failed",
            _build_operations_notification_body(task_record, admin_detail_url),
            task_id=task_record.get("id", ""),
            source_type=task_record.get("source_type", ""),
            source_id=task_record.get("source_id", ""),
            status="sent" if telegram_ok else "failed",
            channel="TELEGRAM",
            recipient=telegram_chat_id,
            operator_key=operator_key,
            metadata=notification_type,
        )
        if notification:
            _append_operations_task_event(
                task_record.get("id", ""),
                "notification_sent" if telegram_ok else "notification_failed",
                "Notification sent" if telegram_ok else "Notification failed",
                f"TELEGRAM · {notification['title']}" if telegram_ok else f"TELEGRAM · {telegram_reason or 'telegram_send_failed'}",
                status=task_record.get("status", "NEW"),
            )
        any_success = any_success or telegram_ok
    elif channels["TELEGRAM"]:
        results.append(("TELEGRAM", False, "telegram_not_configured"))
        _append_operations_notification(
            "notification_failed",
            "Task notification telegram failed",
            _build_operations_notification_body(task_record, admin_detail_url),
            task_id=task_record.get("id", ""),
            source_type=task_record.get("source_type", ""),
            source_id=task_record.get("source_id", ""),
            status="failed",
            channel="TELEGRAM",
            recipient=telegram_chat_id,
            operator_key=operator_key,
            metadata=notification_type,
        )
        _append_operations_task_event(
            task_record.get("id", ""),
            "notification_failed",
            "Notification failed",
            "TELEGRAM · telegram_not_configured",
            status=task_record.get("status", "NEW"),
        )

    return any_success, results


def _operations_overdue_scan_meta_key():
    return "operations_notifications_overdue_scan_date"


def _build_operations_overdue_report(overdue_tasks):
    open_overdue_tasks = len(overdue_tasks)
    assigned_overdue_tasks = sum(1 for task in overdue_tasks if _normalize_operations_task_status(task.get("status", "NEW")) == "ASSIGNED")
    high_priority_overdue_tasks = sum(1 for task in overdue_tasks if _normalize_operations_task_priority(task.get("priority", "NORMAL")) in {"HIGH", "URGENT"})
    return {
        "open_overdue_tasks": open_overdue_tasks,
        "assigned_overdue_tasks": assigned_overdue_tasks,
        "high_priority_overdue_tasks": high_priority_overdue_tasks,
        "total_overdue_tasks": open_overdue_tasks,
    }


def _send_operations_overdue_report(report, admin_detail_url):
    summary_lines = [
        "Daily overdue tasks report",
        f"Open overdue tasks: {report['open_overdue_tasks']}",
        f"Assigned overdue tasks: {report['assigned_overdue_tasks']}",
        f"High priority overdue tasks: {report['high_priority_overdue_tasks']}",
        f"Admin URL: {admin_detail_url}",
    ]
    summary_body = "\n".join(summary_lines)
    telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    admin_email = os.getenv("ADMIN_NOTIFICATION_EMAIL", "").strip()
    preferences = _load_operations_notification_preferences(create_default=True)
    operator_key = preferences[0]["operator_key"] if preferences else _current_admin_operator_key()

    results = []
    any_success = False

    if not admin_email:
        return False, results, summary_body

    if any(pref.get("email_enabled") for pref in preferences) and admin_email:
        email_ok = False
        email_reason = "smtp_send_failed"
        smtp_host = os.getenv("SMTP_HOST", "").strip()
        smtp_port_raw = os.getenv("SMTP_PORT", "").strip()
        smtp_username = os.getenv("SMTP_USERNAME", "").strip()
        smtp_password = os.getenv("SMTP_PASSWORD", "").strip()
        smtp_from = os.getenv("SMTP_FROM", "").strip()
        if smtp_host and smtp_port_raw and smtp_from:
            try:
                smtp_port = int(smtp_port_raw)
            except ValueError:
                smtp_reason = "smtp_invalid_port"
                smtp_port = None
            else:
                smtp_reason = ""

            if smtp_port is not None:
                message = EmailMessage()
                message["Subject"] = "[BlackSeaConnect] Daily overdue tasks report"
                message["From"] = smtp_from
                message["To"] = admin_email
                message.set_content(summary_body)
                try:
                    with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as client:
                        client.ehlo()
                        try:
                            client.starttls()
                            client.ehlo()
                        except smtplib.SMTPException:
                            pass
                        if smtp_username and smtp_password:
                            client.login(smtp_username, smtp_password)
                        client.send_message(message)
                    email_ok = True
                    email_reason = None
                except Exception as exc:
                    app.logger.warning("Operations overdue report email send failed: %s", type(exc).__name__)
                    email_reason = "smtp_send_failed"
            else:
                email_reason = smtp_reason
        else:
            email_reason = "smtp_not_configured"

        results.append(("EMAIL", email_ok, email_reason))
        _append_operations_notification(
            "notification_sent" if email_ok else "notification_failed",
            "Daily overdue report sent" if email_ok else "Daily overdue report failed",
            summary_body,
            source_type="SYSTEM",
            source_id="daily-overdue-report",
            status="sent" if email_ok else "failed",
            channel="EMAIL",
            recipient=admin_email,
            operator_key=operator_key,
            metadata=json.dumps(report, ensure_ascii=False),
        )
        any_success = any_success or email_ok
    elif any(pref.get("email_enabled") for pref in preferences):
        results.append(("EMAIL", False, "email_not_configured"))

    if any(pref.get("telegram_enabled") for pref in preferences) and telegram_bot_token and telegram_chat_id:
        telegram_text = summary_body
        telegram_url = f"https://api.telegram.org/bot{telegram_bot_token}/sendMessage"
        payload = {
            "chat_id": telegram_chat_id,
            "text": telegram_text,
            "disable_web_page_preview": "true",
        }
        data = urllib.parse.urlencode(payload).encode("utf-8")
        request_obj = urllib.request.Request(telegram_url, data=data, method="POST")
        request_obj.add_header("Content-Type", "application/x-www-form-urlencoded")
        try:
            with urllib.request.urlopen(request_obj, timeout=15) as response:
                response_status = getattr(response, "status", response.getcode())
                if response_status and 200 <= int(response_status) < 300:
                    telegram_ok = True
                    telegram_reason = None
                else:
                    app.logger.warning("Operations overdue report send failed via Telegram: unexpected status %s.", response_status)
                    telegram_ok = False
                    telegram_reason = "telegram_bad_status"
        except Exception as exc:
            app.logger.warning("Operations overdue report send failed via Telegram: %s", type(exc).__name__)
            telegram_ok = False
            telegram_reason = "telegram_send_failed"
        results.append(("TELEGRAM", telegram_ok, telegram_reason))
        _append_operations_notification(
            "notification_sent" if telegram_ok else "notification_failed",
            "Daily overdue report sent" if telegram_ok else "Daily overdue report failed",
            summary_body,
            source_type="SYSTEM",
            source_id="daily-overdue-report",
            status="sent" if telegram_ok else "failed",
            channel="TELEGRAM",
            recipient=telegram_chat_id,
            operator_key=operator_key,
            metadata=json.dumps(report, ensure_ascii=False),
        )
        any_success = any_success or telegram_ok
    elif any(pref.get("telegram_enabled") for pref in preferences):
        results.append(("TELEGRAM", False, "telegram_not_configured"))

    return any_success, results, summary_body


def _run_operations_overdue_monitor(force=False):
    today = datetime.now(timezone.utc).date().isoformat()
    with _owner_db_connection() as conn:
        _ensure_owner_db_schema(conn)
        _migrate_owner_jsonl_backups(conn)
        meta_key = _operations_overdue_scan_meta_key()
        if not force and _owner_db_meta_get(conn, meta_key) == today:
            return {
                "ran": False,
                "report": {
                    "open_overdue_tasks": 0,
                    "assigned_overdue_tasks": 0,
                    "high_priority_overdue_tasks": 0,
                    "total_overdue_tasks": 0,
                },
                "sent": False,
                "results": [],
            }

        tasks = [
            task
            for task in _load_operations_tasks()
            if _admin_operations_task_is_overdue(task)
        ]
        for task in tasks:
            overdue_detail = f"Due date: {task.get('due_date', '')}"
            _append_operations_task_event(
                task.get("id", ""),
                "overdue_detected",
                "Task overdue detected",
                overdue_detail,
                status=task.get("status", "NEW"),
            )
            _append_operations_notification(
                "overdue_detected",
                "Task overdue detected",
                overdue_detail,
                task_id=task.get("id", ""),
                source_type=task.get("source_type", ""),
                source_id=task.get("source_id", ""),
                status="logged",
                channel="SYSTEM",
                operator_key=_current_admin_operator_key(),
                metadata=task.get("category", ""),
            )

        report = _build_operations_overdue_report(tasks)
        admin_detail_url = url_for("admin_notifications", _external=True)
        sent, results, summary_body = _send_operations_overdue_report(report, admin_detail_url)

        _owner_db_meta_set(conn, meta_key, today)

    return {
        "ran": True,
        "report": report,
        "sent": sent,
        "results": results,
        "summary": summary_body,
    }


def _upsert_operations_task(task_payload, *, append_created_event=False, status_override=None, note_event=False, notify=False):
    task_id = str((task_payload or {}).get("id", "")).strip()
    if not task_id:
        return None

    existing_task = _find_operations_task(task_id)
    created_at = str((task_payload or {}).get("created_at", "")).strip() or (existing_task or {}).get("created_at", "") or _utc_now_iso()
    updated_at = str((task_payload or {}).get("updated_at", "")).strip() or _utc_now_iso()
    status = _normalize_operations_task_status(
        status_override
        or (task_payload or {}).get("status")
        or (existing_task or {}).get("status", "NEW")
    )
    if status in {"COMPLETED", "ARCHIVED"}:
        completed_at = str((task_payload or {}).get("completed_at", "")).strip() or str((existing_task or {}).get("completed_at", "")).strip() or updated_at
    else:
        completed_at = str((task_payload or {}).get("completed_at", "")).strip() or str((existing_task or {}).get("completed_at", "")).strip()

    merged_task = {
        "id": task_id,
        "request_id": str((task_payload or {}).get("request_id", "")).strip() or task_id,
        "source_type": str((task_payload or {}).get("source_type", "")).strip() or str((existing_task or {}).get("source_type", "")).strip(),
        "source_id": str((task_payload or {}).get("source_id", "")).strip() or task_id,
        "created_at": created_at,
        "updated_at": updated_at,
        "title": str((task_payload or {}).get("title", "")).strip() or str((existing_task or {}).get("title", "")).strip() or "Task",
        "category": str((task_payload or {}).get("category", "")).strip() or str((existing_task or {}).get("category", "")).strip(),
        "owner_name": str((task_payload or {}).get("owner_name", "")).strip() or str((existing_task or {}).get("owner_name", "")).strip(),
        "owner_email": str((task_payload or {}).get("owner_email", "")).strip() or str((existing_task or {}).get("owner_email", "")).strip(),
        "property_id": str((task_payload or {}).get("property_id", "")).strip() or str((existing_task or {}).get("property_id", "")).strip(),
        "property_name": str((task_payload or {}).get("property_name", "")).strip() or str((existing_task or {}).get("property_name", "")).strip(),
        "assigned_to": str((task_payload or {}).get("assigned_to", "")).strip() or str((existing_task or {}).get("assigned_to", "")).strip(),
        "assigned_professional_id": str((task_payload or {}).get("assigned_professional_id", "")).strip() or str((existing_task or {}).get("assigned_professional_id", "")).strip(),
        "priority": _normalize_operations_task_priority((task_payload or {}).get("priority", (existing_task or {}).get("priority", "NORMAL"))),
        "status": status,
        "due_date": str((task_payload or {}).get("due_date", "")).strip() or str((existing_task or {}).get("due_date", "")).strip(),
        "notes": str((task_payload or {}).get("notes", "")).strip() or str((task_payload or {}).get("admin_notes", "")).strip() or str((existing_task or {}).get("notes", "")).strip() or str((existing_task or {}).get("admin_notes", "")).strip(),
        "completed_at": completed_at,
        "completion_report_json": str((task_payload or {}).get("completion_report_json", "")).strip() or str((existing_task or {}).get("completion_report_json", "")).strip() or _operations_task_json_dumps(_operations_task_completion_report({})),
        "owner_id": str((task_payload or {}).get("owner_id", "")).strip() or str((existing_task or {}).get("owner_id", "")).strip(),
        "property_location": str((task_payload or {}).get("property_location", "")).strip() or str((existing_task or {}).get("property_location", "")).strip(),
        "admin_notes": str((task_payload or {}).get("admin_notes", "")).strip() or str((task_payload or {}).get("notes", "")).strip() or str((existing_task or {}).get("admin_notes", "")).strip() or str((existing_task or {}).get("notes", "")).strip(),
        "request_status": _normalize_service_request_status((task_payload or {}).get("request_status", (existing_task or {}).get("request_status", "new"))),
        "checklist_json": str((task_payload or {}).get("checklist_json", "")).strip() or str((existing_task or {}).get("checklist_json", "")).strip() or _operations_task_json_dumps(_operations_task_checklist_items()),
        "attachments_json": str((task_payload or {}).get("attachments_json", "")).strip() or str((existing_task or {}).get("attachments_json", "")).strip() or _operations_task_json_dumps([]),
        "comments_json": str((task_payload or {}).get("comments_json", "")).strip() or str((existing_task or {}).get("comments_json", "")).strip() or _operations_task_json_dumps([]),
    }

    try:
        with _owner_db_connection() as conn:
            _ensure_owner_db_schema(conn)
            _migrate_owner_jsonl_backups(conn)
            conn.execute(
                """
                INSERT INTO operations_tasks (
                    id, request_id, source_type, source_id, created_at, updated_at, title, category,
                    owner_name, owner_email, property_id, property_name, assigned_to, assigned_professional_id, priority, status,
                    due_date, notes, completed_at, completion_report_json, owner_id, property_location, admin_notes, request_status,
                    checklist_json, attachments_json, comments_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    request_id = excluded.request_id,
                    source_type = excluded.source_type,
                    source_id = excluded.source_id,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at,
                    title = excluded.title,
                    category = excluded.category,
                    owner_name = excluded.owner_name,
                    owner_email = excluded.owner_email,
                    property_id = excluded.property_id,
                    property_name = excluded.property_name,
                    assigned_to = excluded.assigned_to,
                    assigned_professional_id = excluded.assigned_professional_id,
                    priority = excluded.priority,
                    status = excluded.status,
                    due_date = excluded.due_date,
                    notes = excluded.notes,
                    completed_at = excluded.completed_at,
                    completion_report_json = excluded.completion_report_json,
                    owner_id = excluded.owner_id,
                    property_location = excluded.property_location,
                    admin_notes = excluded.admin_notes,
                    request_status = excluded.request_status,
                    checklist_json = excluded.checklist_json,
                    attachments_json = excluded.attachments_json,
                    comments_json = excluded.comments_json
                """,
                (
                    merged_task["id"],
                    merged_task["request_id"],
                    merged_task["source_type"],
                    merged_task["source_id"],
                    merged_task["created_at"],
                    merged_task["updated_at"],
                    merged_task["title"],
                    merged_task["category"],
                    merged_task["owner_name"],
                    merged_task["owner_email"],
                    merged_task["property_id"],
                    merged_task["property_name"],
                    merged_task["assigned_to"],
                    merged_task["assigned_professional_id"],
                    merged_task["priority"],
                    merged_task["status"],
                    merged_task["due_date"],
                    merged_task["notes"],
                    merged_task["completed_at"],
                    merged_task["completion_report_json"],
                    merged_task["owner_id"],
                    merged_task["property_location"],
                    merged_task["admin_notes"],
                    merged_task["request_status"],
                    merged_task["checklist_json"],
                    merged_task["attachments_json"],
                    merged_task["comments_json"],
                ),
            )
    except Exception as exc:
        app.logger.warning("Operations task upsert failed for %s: %s", task_id, type(exc).__name__)
        return None

    if existing_task is None and append_created_event:
        _append_operations_task_event(
            task_id,
            "task_created",
            "Task created",
            str(task_payload.get("timeline_detail", "")).strip() or f"{merged_task['title']} · {merged_task['property_name'] or merged_task['property_location']}".strip(" ·"),
            status="NEW",
        )
        if notify and merged_task.get("source_type") in {
            "PILOT_REQUEST",
            "OWNER_REGISTRATION",
            "PROFESSIONAL_APPLICATION",
            "PARTNER_APPLICATION",
            "CONCIERGE_REQUEST",
            "OWNER_SERVICE_REQUEST",
        }:
            admin_detail_url = url_for("admin_operations_detail", task_id=task_id, _external=True)
            _dispatch_operations_notification(merged_task, admin_detail_url, notification_type="task_created")
    elif note_event:
        _append_operations_task_event(
            task_id,
            "note_added",
            "Note added",
            merged_task["notes"],
            status=merged_task["status"],
        )

    synced_task = _find_operations_task(task_id) or merged_task
    _upsert_calendar_event_from_task(synced_task)
    return synced_task


def _upsert_operations_task_from_source(task_payload, append_created_event=False, force_create=False, status_override=None, notify=False):
    global _OWNER_DB_BACKFILL_SUPPRESSED
    previous_state = _OWNER_DB_BACKFILL_SUPPRESSED
    _OWNER_DB_BACKFILL_SUPPRESSED = True
    try:
        return _upsert_operations_task(task_payload, append_created_event=append_created_event, status_override=status_override, notify=notify)
    finally:
        _OWNER_DB_BACKFILL_SUPPRESSED = previous_state


def _operations_task_payload_from_source(source_type, source_record, status="NEW"):
    record = source_record or {}
    normalized_source_type = str(source_type or "").strip().upper()
    source_id = str(record.get("id", "") or record.get("request_id", "")).strip()
    if not normalized_source_type or not source_id:
        return None

    created_at = str(record.get("created_at", "")).strip() or _utc_now_iso()
    updated_at = str(record.get("updated_at", "")).strip() or str(record.get("last_update_at", "")).strip() or created_at
    source_category = {
        "PILOT_REQUEST": "LEAD",
        "OWNER_REGISTRATION": "OWNER",
        "PROFESSIONAL_APPLICATION": "PROFESSIONAL",
        "PARTNER_APPLICATION": "PARTNER",
        "CONCIERGE_REQUEST": "CONCIERGE",
        "SERVICE_REQUEST": "SERVICE",
        "OWNER_SERVICE_REQUEST": "SERVICE",
    }.get(normalized_source_type, str(record.get("service_category", "")).strip() or str(record.get("category", "")).strip())
    title = {
        "PILOT_REQUEST": str(record.get("name", "")).strip() or str(record.get("email", "")).strip() or "Pilot request",
        "OWNER_REGISTRATION": str(record.get("full_name", "")).strip() or str(record.get("email", "")).strip() or "Owner registration",
        "PROFESSIONAL_APPLICATION": str(record.get("full_name", "")).strip() or str(record.get("email", "")).strip() or "Professional application",
        "PARTNER_APPLICATION": str(record.get("company_name", "")).strip() or str(record.get("contact_person", "")).strip() or "Partner application",
        "CONCIERGE_REQUEST": str(record.get("description", "")).strip() or str(record.get("name", "")).strip() or str(record.get("property_city", "")).strip() or "Concierge request",
        "SERVICE_REQUEST": str(record.get("description", "")).strip() or str(record.get("property", "")).strip() or str(record.get("property_city", "")).strip() or "Service request",
        "OWNER_SERVICE_REQUEST": str(record.get("description", "")).strip() or str(record.get("property", "")).strip() or str(record.get("property_city", "")).strip() or "Owner service request",
    }.get(normalized_source_type, str(record.get("title", "")).strip() or "Task")
    owner_name = {
        "PILOT_REQUEST": str(record.get("name", "")).strip(),
        "OWNER_REGISTRATION": str(record.get("full_name", "")).strip(),
        "PROFESSIONAL_APPLICATION": str(record.get("full_name", "")).strip(),
        "PARTNER_APPLICATION": str(record.get("contact_person", "")).strip() or str(record.get("company_name", "")).strip(),
        "CONCIERGE_REQUEST": str(record.get("name", "")).strip(),
        "SERVICE_REQUEST": str(record.get("owner_name", "")).strip() or str(record.get("name", "")).strip(),
        "OWNER_SERVICE_REQUEST": str(record.get("owner_name", "")).strip() or str(record.get("name", "")).strip(),
    }.get(normalized_source_type, str(record.get("owner_name", "")).strip())
    owner_email = {
        "PILOT_REQUEST": str(record.get("email", "")).strip(),
        "OWNER_REGISTRATION": str(record.get("email", "")).strip(),
        "PROFESSIONAL_APPLICATION": str(record.get("email", "")).strip(),
        "PARTNER_APPLICATION": str(record.get("email", "")).strip(),
        "CONCIERGE_REQUEST": str(record.get("email", "")).strip(),
        "SERVICE_REQUEST": str(record.get("owner_email", "")).strip() or str(record.get("email", "")).strip(),
        "OWNER_SERVICE_REQUEST": str(record.get("owner_email", "")).strip() or str(record.get("email", "")).strip(),
    }.get(normalized_source_type, str(record.get("owner_email", "")).strip())
    property_id = str(record.get("property_id", "")).strip()
    property_name = {
        "PILOT_REQUEST": str(record.get("city", "")).strip() or str(record.get("property_type", "")).strip(),
        "OWNER_REGISTRATION": str(record.get("property_name", "")).strip() or str(record.get("city", "")).strip() or str(record.get("property_type", "")).strip(),
        "PROFESSIONAL_APPLICATION": str(record.get("city", "")).strip() or str(record.get("country", "")).strip(),
        "PARTNER_APPLICATION": str(record.get("company_name", "")).strip() or str(record.get("city", "")).strip(),
        "CONCIERGE_REQUEST": str(record.get("service_type", "")).strip() or str(record.get("property_city", "")).strip(),
        "SERVICE_REQUEST": str(record.get("property", "")).strip() or str(record.get("property_city", "")).strip(),
        "OWNER_SERVICE_REQUEST": str(record.get("property", "")).strip() or str(record.get("property_city", "")).strip(),
    }.get(normalized_source_type, str(record.get("property_name", "")).strip())
    property_location = {
        "PILOT_REQUEST": str(record.get("city", "")).strip(),
        "OWNER_REGISTRATION": str(record.get("city", "")).strip(),
        "PROFESSIONAL_APPLICATION": str(record.get("city", "")).strip(),
        "PARTNER_APPLICATION": str(record.get("city", "")).strip(),
        "CONCIERGE_REQUEST": str(record.get("property_city", "")).strip(),
        "SERVICE_REQUEST": str(record.get("property_city", "")).strip(),
        "OWNER_SERVICE_REQUEST": str(record.get("property_city", "")).strip(),
    }.get(normalized_source_type, str(record.get("property_location", "")).strip())
    notes = {
        "PILOT_REQUEST": str(record.get("concierge_needs", "")).strip(),
        "OWNER_REGISTRATION": str(record.get("notes", "")).strip(),
        "PROFESSIONAL_APPLICATION": str(record.get("short_bio", "")).strip() or str(record.get("description", "")).strip(),
        "PARTNER_APPLICATION": str(record.get("description", "")).strip(),
        "CONCIERGE_REQUEST": str(record.get("message", "")).strip(),
        "SERVICE_REQUEST": str(record.get("notes", "")).strip() or str(record.get("description", "")).strip(),
        "OWNER_SERVICE_REQUEST": str(record.get("notes", "")).strip() or str(record.get("description", "")).strip(),
    }.get(normalized_source_type, str(record.get("notes", "")).strip())
    admin_notes = str(record.get("admin_notes", "")).strip() or str(record.get("internal_notes", "")).strip()
    if not notes:
        notes = admin_notes
    if not admin_notes:
        admin_notes = notes

    priority = _normalize_operations_task_priority(record.get("priority", "NORMAL"))
    if normalized_source_type in {"SERVICE_REQUEST", "OWNER_SERVICE_REQUEST"}:
        priority = _operations_task_priority_from_request(record)

    task_status = _normalize_operations_task_status(status or record.get("status", "NEW"))
    due_date = str(record.get("due_date", "")).strip() or str(record.get("preferred_date", "")).strip()
    owner_id = {
        "OWNER_REGISTRATION": str(record.get("id", "")).strip(),
        "SERVICE_REQUEST": str(record.get("owner_id", "")).strip() or str(record.get("request_source", "")).strip() or "public",
        "OWNER_SERVICE_REQUEST": str(record.get("owner_id", "")).strip() or str(record.get("request_source", "")).strip() or "public",
    }.get(normalized_source_type, str(record.get("owner_id", "")).strip())

    return {
        "id": source_id,
        "request_id": source_id,
        "source_type": normalized_source_type,
        "source_id": source_id,
        "created_at": created_at,
        "updated_at": updated_at,
        "title": title,
        "category": source_category,
        "owner_name": owner_name,
        "owner_email": owner_email,
        "property_id": property_id,
        "property_name": property_name,
        "assigned_to": str(record.get("assigned_to", "")).strip(),
        "assigned_professional_id": str(record.get("assigned_professional_id", "")).strip(),
        "priority": priority,
        "status": task_status,
        "due_date": due_date,
        "notes": notes,
        "completed_at": str(record.get("completed_at", "")).strip(),
        "owner_id": owner_id,
        "property_location": property_location,
        "admin_notes": admin_notes,
        "request_status": _normalize_service_request_status(record.get("status", "new")),
        "timeline_detail": str(record.get("timeline_detail", "")).strip() or source_category or title,
    }


def _upsert_operations_task_from_service_request(request_record, status_override=None, note_event=False, source_type=None, force_create=False, notify=False):
    request_id = str((request_record or {}).get("id", "")).strip()
    if not request_id:
        return None

    request_status = _normalize_service_request_status((request_record or {}).get("status", "new"))
    source_kind = source_type or ("OWNER_SERVICE_REQUEST" if str((request_record or {}).get("request_source", "public")).lower() == "owner" else "CONCIERGE_REQUEST")
    source_payload = _operations_task_payload_from_source(source_kind, request_record, status_override or _service_request_status_to_operations_status(request_status))
    if not source_payload:
        return None

    source_payload["status"] = _normalize_operations_task_status(status_override or _service_request_status_to_operations_status(request_status))
    source_payload["priority"] = _operations_task_priority_from_request(request_record)
    source_payload["request_status"] = request_status

    global _OWNER_DB_BACKFILL_SUPPRESSED
    previous_state = _OWNER_DB_BACKFILL_SUPPRESSED
    _OWNER_DB_BACKFILL_SUPPRESSED = True
    try:
        created = _find_operations_task(request_id) is None
        updated_task = _upsert_operations_task(
            source_payload,
            append_created_event=created or force_create,
            status_override=source_payload["status"] if status_override is not None else None,
            note_event=note_event,
            notify=notify,
        )
    finally:
        _OWNER_DB_BACKFILL_SUPPRESSED = previous_state
    if created and status_override is not None and updated_task:
        event_type, event_title = _operations_task_status_event(source_payload["status"])
        _append_operations_task_event(
            request_id,
            event_type,
            event_title,
            source_payload["timeline_detail"],
            status=source_payload["status"],
        )
    return updated_task


def _update_operations_task_details(task_id, *, status=None, assigned_to=None, assigned_professional_id=None, notes=None, due_date=None, priority=None, source="detail"):
    task = _find_operations_task(task_id)
    if not task:
        return None

    task_id = str(task_id or "").strip()
    new_status = _normalize_operations_task_status(status if status is not None else task.get("status", "NEW"))
    new_assigned_professional_id = str(assigned_professional_id if assigned_professional_id is not None else task.get("assigned_professional_id", "")).strip()
    current_assigned_professional_id = str(task.get("assigned_professional_id", "")).strip()
    professional_account = _find_professional_account(new_assigned_professional_id) if new_assigned_professional_id else None
    if new_assigned_professional_id and not professional_account:
        return None
    if professional_account and _normalize_professional_account_status(professional_account.get("status", "PENDING")) not in {"APPROVED", "ACTIVE"}:
        return None
    new_assigned_to = _professional_account_display_label(professional_account) if professional_account else str(assigned_to if assigned_to is not None else task.get("assigned_to", "")).strip()
    new_notes = str(notes if notes is not None else task.get("admin_notes", "")).strip()
    new_due_date = str(due_date if due_date is not None else task.get("due_date", "")).strip()
    new_priority = _normalize_operations_task_priority(priority if priority is not None else task.get("priority", "NORMAL"))
    current_status = _normalize_operations_task_status(task.get("status", "NEW"))
    current_assigned_to = str(task.get("assigned_to", "")).strip()
    current_assigned_professional = str(task.get("assigned_professional_id", "")).strip()
    current_notes = str(task.get("admin_notes", "")).strip()
    current_due_date = str(task.get("due_date", "")).strip()
    current_priority = _normalize_operations_task_priority(task.get("priority", "NORMAL"))

    if new_assigned_professional_id and new_status == current_status and current_status == "NEW":
        new_status = "ASSIGNED"

    if (
        new_status == current_status
        and new_assigned_to == current_assigned_to
        and new_assigned_professional_id == current_assigned_professional
        and new_notes == current_notes
        and new_due_date == current_due_date
        and new_priority == current_priority
    ):
        return task

    completed_at = str(task.get("completed_at", "")).strip()
    if new_status in {"COMPLETED", "ARCHIVED"} and current_status not in {"COMPLETED", "ARCHIVED"} and not completed_at:
        completed_at = _utc_now_iso()
    if new_status not in {"COMPLETED", "ARCHIVED"}:
        completed_at = "" if current_status not in {"COMPLETED", "ARCHIVED"} else completed_at

    updated_at = _utc_now_iso()

    try:
        with _owner_db_connection() as conn:
            _ensure_owner_db_schema(conn)
            _migrate_owner_jsonl_backups(conn)
            conn.execute(
                """
                UPDATE operations_tasks
                SET status = ?, assigned_to = ?, assigned_professional_id = ?, admin_notes = ?, due_date = ?, priority = ?, completed_at = ?, updated_at = ?
                WHERE id = ? OR request_id = ? OR source_id = ?
                """,
                (new_status, new_assigned_to, new_assigned_professional_id, new_notes, new_due_date, new_priority, completed_at, updated_at, task_id, task_id, task_id),
            )
    except Exception as exc:
        app.logger.warning("Operations task update failed for %s: %s", task_id, type(exc).__name__)
        return None

    if new_assigned_to and new_assigned_to != current_assigned_to:
        _append_operations_task_event(
            task_id,
            "assigned",
            "Task assigned",
            new_assigned_to,
            status=new_status,
        )

    if new_assigned_professional_id and new_assigned_professional_id != current_assigned_professional:
        _append_operations_task_event(
            task_id,
            "professional_assigned",
            "Professional assigned",
            new_assigned_to or new_assigned_professional_id,
            status=new_status,
        )
        if professional_account:
            assignment_body = "\n".join([
                "BlackSea Connect task assignment",
                "",
                f"Task: {task.get('title', '')}",
                f"Property: {task.get('property_name', '') or task.get('property_location', '')}",
                f"Due date: {new_due_date or 'n/a'}",
                f"Status: {new_status}",
                f"Admin notes: {new_notes or 'n/a'}",
                f"Task URL: {url_for('professionals_task_detail', task_id=task_id, _external=True)}",
            ])
            _send_plaintext_email(
                professional_account.get("email", ""),
                "[BlackSeaConnect] New task assignment",
                assignment_body,
            )
            _append_operations_notification(
                "professional_assigned",
                "Professional task assigned",
                assignment_body,
                task_id=task_id,
                source_type=task.get("source_type", ""),
                source_id=task.get("source_id", ""),
                status="sent",
                channel="EMAIL",
                recipient=professional_account.get("email", ""),
                operator_key=_current_admin_operator_key(),
                metadata="professional_assignment",
            )

    if new_status != current_status:
        event_type = "completed" if new_status == "COMPLETED" else "status_changed"
        event_title = "Task completed" if new_status == "COMPLETED" else f"Status changed to {new_status.replace('_', ' ').title()}"
        _append_operations_task_event(
            task_id,
            event_type,
            event_title,
            f"{current_status.replace('_', ' ').title()} -> {new_status.replace('_', ' ').title()}",
            status=new_status,
        )
        _sync_reservation_from_operation_task({**task, "id": task_id, "status": new_status}, new_status)
        request_record = _find_service_request(task_id)
        if request_record:
            request_record["status"] = _operations_status_to_service_request_status(new_status)
            request_record["last_update_at"] = updated_at
            _append_service_request_timeline_event(
                request_record,
                "SERVICE_REQUEST_STATUS_UPDATED",
                f"Operations board moved task to {new_status.replace('_', ' ').title()}",
                str(task.get("category", "")).strip() or str(task.get("title", "")).strip(),
                status=request_record["status"],
            )
            requests_list = _load_service_requests()
            for index, record in enumerate(requests_list):
                if str(record.get("id", "")) == task_id:
                    requests_list[index] = request_record
                    break
            _save_service_requests(requests_list)

    if new_status == "COMPLETED" and current_status != "COMPLETED":
        admin_email = os.getenv("ADMIN_NOTIFICATION_EMAIL", "").strip() or os.getenv("ADMIN_EMAIL", "").strip()
        owner_email = str(task.get("owner_email", "")).strip()
        completion_body = "\n".join([
            "BlackSea Connect task completed",
            "",
            f"Task: {task.get('title', '')}",
            f"Professional: {new_assigned_to or new_assigned_professional_id or 'n/a'}",
            f"Property: {task.get('property_name', '') or task.get('property_location', '')}",
            f"Completion note: {new_notes or 'n/a'}",
            f"Task URL: {url_for('admin_operations_detail', task_id=task_id, _external=True)}",
        ])
        _append_operations_notification(
            "professional_completed",
            "Professional completed task",
            completion_body,
            task_id=task_id,
            source_type=task.get("source_type", ""),
            source_id=task.get("source_id", ""),
            status="sent",
            channel="EMAIL",
            recipient=owner_email or admin_email,
            operator_key=_current_admin_operator_key(),
            metadata="professional_completion",
        )
        _append_operations_task_event(
            task_id,
            "workflow_transitioned",
            "Ready for owner review",
            f"{task.get('title', '')} is ready for owner review",
            status=new_status,
        )
        if owner_email:
            owner_body = "\n".join([
                "BlackSea Connect work completed",
                "",
                f"Task: {task.get('title', '')}",
                f"Property: {task.get('property_name', '') or task.get('property_location', '')}",
                f"Professional: {new_assigned_to or new_assigned_professional_id or 'n/a'}",
                f"Status: {new_status}",
                f"Review link: {url_for('owners_dashboard', _external=True)}",
            ])
            _send_plaintext_email(
                owner_email,
                "[BlackSeaConnect] Work completed on your property",
                owner_body,
            )
        if admin_email:
            _send_plaintext_email(
                admin_email,
                "[BlackSeaConnect] Task completed",
                completion_body,
            )

    if new_notes != current_notes:
        _append_operations_task_event(
            task_id,
            "note_added",
            "Note added",
            new_notes,
            status=new_status,
        )

        request_record = _find_service_request(task_id)
        if request_record:
            request_record["last_update_at"] = updated_at
            request_record["internal_notes"] = new_notes
            requests_list = _load_service_requests()
            for index, record in enumerate(requests_list):
                if str(record.get("id", "")) == task_id:
                    requests_list[index] = request_record
                    break
            _save_service_requests(requests_list)

    if new_due_date != current_due_date or new_priority != current_priority:
        request_record = _find_service_request(task_id)
        if request_record:
            request_record["last_update_at"] = updated_at
            requests_list = _load_service_requests()
            for index, record in enumerate(requests_list):
                if str(record.get("id", "")) == task_id:
                    requests_list[index] = request_record
                    break
            _save_service_requests(requests_list)

    updated_task = _find_operations_task(task_id)
    _upsert_calendar_event_from_task(updated_task or task)
    return updated_task


def _update_operations_task_checklist(task_id, checklist_selection):
    task = _find_operations_task(task_id)
    if not task:
        return None

    normalized_checklist = _normalize_operations_task_checklist(checklist_selection)
    checklist_items = [
        {
            "key": key,
            "label": label,
            "checked": bool(normalized_checklist.get(key, False)),
        }
        for key, label in OPERATIONS_TASK_CHECKLIST_ITEMS
    ]
    updated_task = _operations_task_update_json_fields(
        task_id,
        checklist_json=_operations_task_json_dumps(checklist_items),
    )
    if not updated_task:
        return None

    _append_operations_task_event(
        task_id,
        "checklist_updated",
        "Checklist updated",
        ", ".join(item["label"] for item in checklist_items if item["checked"]) or "Checklist updated",
        status=updated_task.get("status", "NEW"),
    )
    return updated_task


def _update_operations_task_status(request_id, status, source="board"):
    return _update_operations_task_details(request_id, status=status, source=source)


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
                    id, owner_id, created_at, name, property_type, location, bedrooms, bathrooms, guest_capacity, operating_mode, notes, status, guest_guide_ready, access_instructions_ready, emergency_contact_ready, cleaning_partner_ready, admin_notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    notes = excluded.notes,
                    status = excluded.status,
                    guest_guide_ready = excluded.guest_guide_ready,
                    access_instructions_ready = excluded.access_instructions_ready,
                    emergency_contact_ready = excluded.emergency_contact_ready,
                    cleaning_partner_ready = excluded.cleaning_partner_ready,
                    admin_notes = excluded.admin_notes
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
                    normalized["status"],
                    normalized["guest_guide_ready"],
                    normalized["access_instructions_ready"],
                    normalized["emergency_contact_ready"],
                    normalized["cleaning_partner_ready"],
                    normalized["admin_notes"],
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

    accounts = [_owner_account_from_row(row) for row in rows]
    accounts.extend(_demo_records("owner_accounts"))
    accounts.sort(key=lambda item: (str(item.get("created_at", "")), str(item.get("email", ""))), reverse=True)
    return accounts


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
    return _demo_owner_account_by_email(target_email)


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
    return _demo_record_index("owner_accounts").get(target_account_id)


def _upsert_owner_account(record):
    normalized = _normalize_owner_account(record)
    if not normalized:
        return None

    target_email = str(normalized.get("email", "")).strip().lower()
    global _OWNER_DB_BACKFILL_SUPPRESSED
    previous_state = _OWNER_DB_BACKFILL_SUPPRESSED
    _OWNER_DB_BACKFILL_SUPPRESSED = True
    try:
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
    finally:
        _OWNER_DB_BACKFILL_SUPPRESSED = previous_state


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
    normalized["status"] = _normalize_owner_property_status(normalized.get("status", OWNER_PROPERTY_STATUS_DEFAULT))
    for field in OWNER_PROPERTY_CHECKLIST_FIELDS:
        normalized[field] = _normalize_owner_property_checklist_value(normalized.get(field, 0))
    normalized["admin_notes"] = str(normalized.get("admin_notes", "")).strip()
    return normalized


def _load_owner_properties():
    with _owner_db_connection() as conn:
        _ensure_owner_db_schema(conn)
        _migrate_owner_jsonl_backups(conn)
        rows = conn.execute(
            """
            SELECT id, owner_id, created_at, name, property_type, location, bedrooms, bathrooms, guest_capacity, operating_mode, notes, status, guest_guide_ready, access_instructions_ready, emergency_contact_ready, cleaning_partner_ready, admin_notes
            FROM owner_properties
            ORDER BY created_at DESC, id DESC
            """
        ).fetchall()

    properties = [_owner_property_from_row(row) for row in rows]
    properties.extend(_demo_records("owner_properties"))
    properties.sort(key=lambda item: (str(item.get("created_at", "")), str(item.get("id", ""))), reverse=True)
    return properties


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
                        id, owner_id, created_at, name, property_type, location, bedrooms, bathrooms, guest_capacity, operating_mode, notes, status, guest_guide_ready, access_instructions_ready, emergency_contact_ready, cleaning_partner_ready, admin_notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                        normalized["status"],
                        normalized["guest_guide_ready"],
                        normalized["access_instructions_ready"],
                        normalized["emergency_contact_ready"],
                        normalized["cleaning_partner_ready"],
                        normalized["admin_notes"],
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
                    id, owner_id, created_at, name, property_type, location, bedrooms, bathrooms, guest_capacity, operating_mode, notes, status, guest_guide_ready, access_instructions_ready, emergency_contact_ready, cleaning_partner_ready, admin_notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    notes = excluded.notes,
                    status = excluded.status,
                    guest_guide_ready = excluded.guest_guide_ready,
                    access_instructions_ready = excluded.access_instructions_ready,
                    emergency_contact_ready = excluded.emergency_contact_ready,
                    cleaning_partner_ready = excluded.cleaning_partner_ready,
                    admin_notes = excluded.admin_notes
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
                    normalized["status"],
                    normalized["guest_guide_ready"],
                    normalized["access_instructions_ready"],
                    normalized["emergency_contact_ready"],
                    normalized["cleaning_partner_ready"],
                    normalized["admin_notes"],
                ),
            )
    except Exception as exc:
        app.logger.warning("Owner property write failed for %s: %s", normalized.get("owner_id", ""), type(exc).__name__)
        return None
    return normalized


def _find_owner_property(property_id):
    target_property_id = str(property_id or "").strip()
    if not target_property_id:
        return None

    with _owner_db_connection() as conn:
        _ensure_owner_db_schema(conn)
        _migrate_owner_jsonl_backups(conn)
        row = conn.execute(
            """
            SELECT id, owner_id, created_at, name, property_type, location, bedrooms, bathrooms, guest_capacity, operating_mode, notes, status, guest_guide_ready, access_instructions_ready, emergency_contact_ready, cleaning_partner_ready, admin_notes
            FROM owner_properties
            WHERE id = ?
            LIMIT 1
            """,
            (target_property_id,),
        ).fetchone()

    if row:
        return _owner_property_from_row(row)
    return _demo_property_by_id(target_property_id)


def _owner_properties_for_account(owner_id):
    target_owner_id = str(owner_id or "").strip()
    if not target_owner_id:
        return []
    return [
        property_record
        for property_record in _load_owner_properties()
        if str(property_record.get("owner_id", "")).strip() == target_owner_id
    ]


def _owner_property_checklist_completion(property_record):
    completed = sum(1 for field in OWNER_PROPERTY_CHECKLIST_FIELDS if bool(property_record.get(field)))
    return completed, len(OWNER_PROPERTY_CHECKLIST_FIELDS)


def _owner_property_status_label(status):
    normalized = _normalize_owner_property_status(status)
    return normalized.title()


def _owner_property_status_tone(status):
    normalized = _normalize_owner_property_status(status)
    if normalized == "ACTIVE":
        return "active"
    if normalized == "SEASONAL":
        return "seasonal"
    if normalized == "INACTIVE":
        return "paused"
    return "setup"


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


def _professional_magic_link_email_message(email, login_url):
    subject = "BlackSea Connect - Professional Portal secure sign-in link"
    text_body = "\n".join([
        "Hello,",
        "",
        "Use the link below to access your Professional Portal.",
        "",
        login_url,
        "",
        "This link expires in 30 minutes.",
        "",
        "BlackSea Connect",
    ])
    html_body = "\n".join([
        "<!doctype html>",
        "<html lang=\"en\">",
        "<body style=\"margin:0;padding:0;background:#f6f0df;font-family:Arial,Helvetica,sans-serif;color:#1e1b16;\">",
        '<div style="max-width:640px;margin:0 auto;padding:32px 20px;">',
        '<div style="background:#fffaf0;border:1px solid #ead6a6;border-radius:20px;padding:32px;box-shadow:0 16px 40px rgba(0,0,0,0.08);">',
        '<div style="font-size:14px;letter-spacing:.16em;text-transform:uppercase;color:#9b7b2f;font-weight:700;">BlackSea Connect</div>',
        '<h1 style="margin:16px 0 12px;font-size:28px;line-height:1.2;color:#1f2937;">Hello,</h1>',
        '<p style="margin:0 0 24px;font-size:16px;line-height:1.7;">Use the link below to access your Professional Portal.</p>',
        f'<a href="{login_url}" style="display:inline-block;background:#9b7b2f;color:#fff;text-decoration:none;padding:14px 22px;border-radius:999px;font-weight:700;">Access Professional Portal</a>',
        f'<p style="margin:20px 0 8px;font-size:14px;line-height:1.7;color:#4b5563;">If the button does not work, copy this link:</p>',
        f'<p style="margin:0;font-size:14px;line-height:1.7;word-break:break-all;"><a href="{login_url}" style="color:#9b7b2f;">{login_url}</a></p>',
        '<p style="margin:24px 0 0;font-size:14px;line-height:1.7;color:#4b5563;">This link expires in 30 minutes.</p>',
        '<p style="margin:16px 0 0;font-size:13px;line-height:1.6;color:#6b7280;">You are receiving this email because you requested access to your BlackSea Connect professional portal.</p>',
        "</div>",
        "</div>",
        "</body>",
        "</html>",
    ])
    return subject, text_body, html_body


def _send_professional_magic_link(email, login_url):
    smtp_host, smtp_port_raw, smtp_from = _service_request_smtp_settings()
    if not smtp_host or not smtp_port_raw or not smtp_from or not email:
        app.logger.warning("Professional magic link email skipped for %s: SMTP configuration missing.", _mask_email(email))
        return {"ok": False, "reason": "smtp_not_configured"}

    try:
        smtp_port = int(smtp_port_raw)
    except ValueError:
        app.logger.warning("Professional magic link email skipped for %s: SMTP_PORT is invalid.", _mask_email(email))
        return {"ok": False, "reason": "smtp_invalid_port"}

    subject, text_body, html_body = _professional_magic_link_email_message(email, login_url)
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = smtp_from
    message["To"] = email
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
                    pass
            smtp_username = os.getenv("SMTP_USERNAME", "").strip()
            smtp_password = os.getenv("SMTP_PASSWORD", "").strip()
            if smtp_username or smtp_password:
                smtp.login(smtp_username, smtp_password)
            smtp.send_message(message)
    except Exception as exc:
        app.logger.warning("Professional magic link email send failed for %s: %s", _mask_email(email), type(exc).__name__)
        return {"ok": False, "reason": "smtp_send_failed"}

    return {"ok": True, "reason": "sent"}


def _create_professional_magic_token(email):
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
                INSERT INTO professional_magic_tokens (token, email, created_at)
                VALUES (?, ?, ?)
                ON CONFLICT(token) DO UPDATE SET
                    email = excluded.email,
                    created_at = excluded.created_at
                """,
                (token_record["token"], token_record["email"], token_record["created_at"]),
            )
    except Exception as exc:
        app.logger.warning("Professional magic token write failed for %s: %s", _mask_email(email), type(exc).__name__)
        return None
    return token_record


def _find_professional_magic_token(token):
    target_token = str(token or "").strip()
    if not target_token:
        return None

    with _owner_db_connection() as conn:
        _ensure_owner_db_schema(conn)
        _migrate_owner_jsonl_backups(conn)
        row = conn.execute(
            """
            SELECT token, email, created_at
            FROM professional_magic_tokens
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


def _consume_professional_magic_token(token):
    target_token = str(token or "").strip()
    if not target_token:
        return False

    try:
        with _owner_db_connection() as conn:
            _ensure_owner_db_schema(conn)
            _migrate_owner_jsonl_backups(conn)
            cursor = conn.execute("DELETE FROM professional_magic_tokens WHERE token = ?", (target_token,))
            return cursor.rowcount > 0
    except Exception as exc:
        app.logger.warning("Professional magic token consume failed for %s: %s", target_token, type(exc).__name__)
        return False


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


_PUBLIC_I18N_CACHE = {}


def _load_public_i18n_bundle(namespace):
    namespace = str(namespace or "").strip()
    if not namespace:
        return {}

    bundle_name = re.sub(r"(?<!^)(?=[A-Z])", "-", namespace).lower()

    cached = _PUBLIC_I18N_CACHE.get(namespace)
    if cached is not None:
        return cached

    bundle_path = Path(app.root_path) / "static" / "js" / "i18n" / f"{bundle_name}.js"
    if not bundle_path.exists():
        _PUBLIC_I18N_CACHE[namespace] = {}
        return {}

    try:
        bundle_text = bundle_path.read_text(encoding="utf-8")
        marker = f'window.BlackSeaI18NModules["{namespace}"] = '
        marker_index = bundle_text.find(marker)
        if marker_index == -1:
            raise ValueError(f"Missing bundle marker for {namespace}")
        object_start = bundle_text.find("{", marker_index)
        object_end = bundle_text.rfind("};")
        if object_start == -1 or object_end == -1 or object_end <= object_start:
            raise ValueError(f"Missing bundle payload for {namespace}")
        bundle = json.loads(bundle_text[object_start:object_end + 1])
    except Exception as exc:
        app.logger.warning("Failed to load public i18n bundle %s: %s", namespace, type(exc).__name__)
        bundle = {}

    _PUBLIC_I18N_CACHE[namespace] = bundle
    return bundle


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

    def public_i18n(namespace, key, fallback=""):
        bundle = _load_public_i18n_bundle(namespace)
        if not bundle:
            return fallback

        lang_candidates = [current_lang]
        if "en" not in lang_candidates:
            lang_candidates.append("en")

        for lang in lang_candidates:
            namespace_copy = bundle.get(lang, {}).get(namespace, {})
            if isinstance(namespace_copy, dict) and key in namespace_copy:
                value = namespace_copy.get(key)
                if value is not None and value != "":
                    return value

        return fallback

    return {
        "site_url": SITE_URL,
        "language_switch_url": language_switch_url,
        "localized_url": localized_url,
        "page_lang": current_page_language(),
        "public_i18n": public_i18n,
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


def _current_professional_account():
    professional_account = getattr(g, "professional_account", None)
    if professional_account:
        return professional_account

    professional_id = str(session.get(PROFESSIONAL_SESSION_ID_KEY, "")).strip()
    professional_email = str(session.get(PROFESSIONAL_SESSION_EMAIL_KEY, "")).strip()
    if professional_id:
        professional_account = _find_professional_account(professional_id)
    if not professional_account and professional_email:
        professional_account = _find_professional_account_by_email(professional_email)

    if professional_account:
        g.professional_account = professional_account
    return professional_account


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
    raw_status = str(property_record.get("status", "")).strip().upper()
    if raw_status in OWNER_PROPERTY_STATUS_VALUES:
        status_map = {
            "SETUP": ("setup", dashboard_copy["status_setup"], "ownerDashboardPropertyStatusOnboarding", "setup", dashboard_copy["status_note_setup"]),
            "ACTIVE": ("active", dashboard_copy["status_active"], "ownerDashboardPropertyStatusActive", "active", dashboard_copy["status_note_active"]),
            "SEASONAL": ("seasonal", dashboard_copy["status_seasonal"], "ownerDashboardPropertyStatusSeasonal", "seasonal", dashboard_copy["status_note_seasonal"]),
            "INACTIVE": ("paused", dashboard_copy["status_paused"], "ownerDashboardPropertyStatusPaused", "paused", dashboard_copy["status_note_paused"]),
        }
        return status_map[raw_status]

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

    checklist_completed, checklist_total = _owner_property_checklist_completion(property_record)
    availability = _property_availability_engine(property_record, _load_reservations(property_ids=[property_record.get("id", "")]))

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
        "checklist_completed": checklist_completed,
        "checklist_total": checklist_total,
        "availability": availability,
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


def _calendar_event_sort_key(event):
    start_dt, _ = _calendar_parse_datetime(event.get("start_datetime", ""))
    end_dt, _ = _calendar_parse_datetime(event.get("end_datetime", ""))
    fallback_dt, _ = _calendar_parse_datetime(event.get("created_at", ""))
    return (
        start_dt or fallback_dt or datetime.now(timezone.utc),
        end_dt or start_dt or fallback_dt or datetime.now(timezone.utc),
        str(event.get("updated_at", "")),
        str(event.get("id", "")),
    )


def _calendar_event_display_label(event):
    start_dt, _ = _calendar_parse_datetime(event.get("start_datetime", ""))
    end_dt, _ = _calendar_parse_datetime(event.get("end_datetime", ""))
    if start_dt is None:
        return str(event.get("start_datetime", "")).strip() or str(event.get("created_at", "")).strip()
    if event.get("all_day"):
        return start_dt.strftime("%d %b %Y")
    if end_dt and end_dt.date() != start_dt.date():
        return f"{start_dt.strftime('%d %b %Y %H:%M')} - {end_dt.strftime('%d %b %Y %H:%M')}"
    return f"{start_dt.strftime('%d %b %Y %H:%M')}"


def _calendar_event_day_label(event):
    start_dt, _ = _calendar_parse_datetime(event.get("start_datetime", ""))
    if start_dt is None:
        return "Unscheduled"
    return start_dt.strftime("%A, %d %B %Y")


def _calendar_event_week_label(event):
    start_dt, _ = _calendar_parse_datetime(event.get("start_datetime", ""))
    if start_dt is None:
        return "Unscheduled"
    year, week, _ = start_dt.isocalendar()
    return f"Week {week:02d}, {year}"


def _calendar_event_search_text(event):
    metadata = event.get("metadata", {}) or {}
    parts = [
        event.get("title", ""),
        event.get("description", ""),
        event.get("event_type", ""),
        event.get("status", ""),
        event.get("assigned_professional", ""),
        metadata.get("property_name", ""),
        metadata.get("property_location", ""),
        metadata.get("owner_name", ""),
        metadata.get("owner_email", ""),
        metadata.get("priority", ""),
        metadata.get("task_status", ""),
    ]
    return " ".join(str(part or "") for part in parts).lower()


def _calendar_enrich_event(event, property_map=None, owner_map=None, task_map=None):
    property_map = property_map or {}
    owner_map = owner_map or {}
    task_map = task_map or {}
    metadata = dict(event.get("metadata", {}) or {})
    task_record = task_map.get(str(event.get("operation_task_id", "")).strip())
    property_record = property_map.get(str(event.get("property_id", "")).strip())
    owner_account = owner_map.get(str(event.get("owner_id", "")).strip())
    if task_record:
        metadata.setdefault("priority", str(task_record.get("priority", "")).strip())
        metadata.setdefault("task_status", str(task_record.get("status", "")).strip())
        metadata.setdefault("source_type", str(task_record.get("source_type", "")).strip())
    if property_record:
        metadata.setdefault("property_name", str(property_record.get("name", "")).strip())
        metadata.setdefault("property_location", str(property_record.get("location", "")).strip())
    if owner_account:
        metadata.setdefault("owner_name", str(owner_account.get("full_name", "")).strip())
        metadata.setdefault("owner_email", str(owner_account.get("email", "")).strip())

    start_dt, _ = _calendar_parse_datetime(event.get("start_datetime", ""))
    end_dt, _ = _calendar_parse_datetime(event.get("end_datetime", ""))
    if start_dt is None:
        start_dt = datetime.now(timezone.utc)
    if end_dt is None:
        end_dt = start_dt
    today = datetime.now(timezone.utc).date()
    overdue = bool(start_dt.date() < today and _normalize_calendar_event_status(event.get("status", "")) not in {"COMPLETED", "CANCELLED"})

    priority = str(metadata.get("priority", "")).strip().upper() or _normalize_operations_task_priority((task_record or {}).get("priority", "NORMAL")) if task_record else ""
    city = str(metadata.get("property_location", "")).strip() or str((property_record or {}).get("location", "")).strip()
    property_label = str(metadata.get("property_name", "")).strip() or str((property_record or {}).get("name", "")).strip() or str(event.get("property_id", "")).strip()
    owner_label = str(metadata.get("owner_name", "")).strip() or str((owner_account or {}).get("full_name", "")).strip()
    owner_email = str(metadata.get("owner_email", "")).strip() or str((owner_account or {}).get("email", "")).strip()
    professional = str(event.get("assigned_professional", "")).strip()
    if not professional and task_record:
        professional = str(task_record.get("assigned_to", "")).strip()

    enriched = {
        **event,
        "metadata": metadata,
        "property_record": property_record,
        "owner_account": owner_account,
        "task_record": task_record,
        "property_label": property_label,
        "owner_label": owner_label,
        "owner_email": owner_email,
        "professional": professional,
        "priority": priority or "",
        "city": city,
        "display_label": _calendar_event_display_label(event),
        "day_label": _calendar_event_day_label(event),
        "week_label": _calendar_event_week_label(event),
        "search_text": _calendar_event_search_text({**event, "metadata": metadata}),
        "is_overdue": overdue,
    }
    return enriched


def _calendar_filter_events(events, filters):
    filters = filters or {}
    search_query = str(filters.get("search", "")).strip().lower()
    search_tokens = [token for token in search_query.split() if token]
    property_filter = str(filters.get("property", "")).strip()
    owner_filter = str(filters.get("owner", "")).strip()
    professional_filter = str(filters.get("professional", "")).strip()
    category_filter = _normalize_calendar_event_type(filters.get("category", "")) if str(filters.get("category", "")).strip() else ""
    priority_filter = str(filters.get("priority", "")).strip().upper()
    status_filter = _normalize_calendar_event_status(filters.get("status", "")) if str(filters.get("status", "")).strip() else ""
    city_filter = str(filters.get("city", "")).strip()

    filtered = []
    for event in events:
        event_text = event.get("search_text", "")
        if search_tokens and not all(token in event_text for token in search_tokens):
            continue
        if property_filter:
            property_values = {
                str(event.get("property_id", "")).strip(),
                str(event.get("property_label", "")).strip().lower(),
                str((event.get("metadata", {}) or {}).get("property_name", "")).strip().lower(),
            }
            if property_filter.strip().lower() not in property_values and _admin_property_query_value(property_filter) not in {_admin_property_query_value(value) for value in property_values}:
                continue
        if owner_filter:
            owner_values = {
                str(event.get("owner_id", "")).strip(),
                str(event.get("owner_label", "")).strip().lower(),
                str(event.get("owner_email", "")).strip().lower(),
            }
            if owner_filter.strip().lower() not in owner_values and _admin_property_query_value(owner_filter) not in {_admin_property_query_value(value) for value in owner_values}:
                continue
        if professional_filter and _admin_property_query_value(event.get("professional", "")) != _admin_property_query_value(professional_filter):
            continue
        if category_filter and _normalize_calendar_event_type(event.get("event_type", "")) != category_filter:
            continue
        if priority_filter and str(event.get("priority", "")).strip().upper() != priority_filter:
            continue
        if status_filter and _normalize_calendar_event_status(event.get("status", "")) != status_filter:
            continue
        if city_filter and _admin_property_query_value(event.get("city", "")) != _admin_property_query_value(city_filter):
            continue
        filtered.append(event)
    return filtered


def _calendar_group_events(events, calendar_view):
    grouped = []
    if calendar_view == "timeline":
        return [{"label": "Timeline", "events": events}]

    group_key = None
    current_group = None
    for event in events:
        if calendar_view == "month":
            key = _calendar_parse_datetime(event.get("start_datetime", ""))[0]
            label = key.strftime("%B %Y") if key else "Unscheduled"
        elif calendar_view == "week":
            key = _calendar_parse_datetime(event.get("start_datetime", ""))[0]
            label = _calendar_event_week_label(event)
        else:
            key = _calendar_parse_datetime(event.get("start_datetime", ""))[0]
            label = _calendar_event_day_label(event)

        if label != group_key:
            current_group = {"label": label, "events": []}
            grouped.append(current_group)
            group_key = label
        current_group["events"].append(event)

    return grouped


def _calendar_widget_summary(events):
    today = datetime.now(timezone.utc).date()
    tomorrow = today + timedelta(days=1)
    week_end = today + timedelta(days=6)
    def _matches_date(event, target_date):
        start_dt, _ = _calendar_parse_datetime(event.get("start_datetime", ""))
        return bool(start_dt and start_dt.date() == target_date)

    return {
        "today": sum(1 for event in events if _matches_date(event, today)),
        "tomorrow": sum(1 for event in events if _matches_date(event, tomorrow)),
        "this_week": sum(1 for event in events if (start := _calendar_parse_datetime(event.get("start_datetime", ""))[0]) and today <= start.date() <= week_end),
        "completed": sum(1 for event in events if _normalize_calendar_event_status(event.get("status", "")) == "COMPLETED"),
        "overdue": sum(1 for event in events if event.get("is_overdue")),
    }


def _calendar_dashboard_widget(events, scope="admin"):
    sorted_events = sorted(events, key=_calendar_event_sort_key)
    summary = _calendar_widget_summary(sorted_events)
    today = datetime.now(timezone.utc).date()
    if scope == "admin":
        def _event_date(event):
            return _calendar_parse_datetime(event.get("start_datetime", ""))[0]

        summary.update({
            "todays_operations": sum(1 for event in sorted_events if _event_date(event) and _event_date(event).date() == today and _normalize_calendar_event_status(event.get("status", "")) not in {"COMPLETED", "CANCELLED"}),
            "upcoming_check_ins": sum(1 for event in sorted_events if _normalize_calendar_event_type(event.get("event_type", "")) == "Check-in" and _event_date(event) and _event_date(event).date() >= today),
            "upcoming_check_outs": sum(1 for event in sorted_events if _normalize_calendar_event_type(event.get("event_type", "")) == "Check-out" and _event_date(event) and _event_date(event).date() >= today),
            "todays_cleaning": sum(1 for event in sorted_events if _normalize_calendar_event_type(event.get("event_type", "")) == "Cleaning" and _event_date(event) and _event_date(event).date() == today),
            "overdue_events": summary["overdue"],
        })
    if scope == "owner":
        headline = "Upcoming events"
        supporting_title = "Owner schedule"
    else:
        headline = "Today's operations"
        supporting_title = "Unified schedule"
    return {
        "headline": headline,
        "supporting_title": supporting_title,
        "summary": summary,
        "upcoming_events": sorted_events[:5],
        "sorted_events": sorted_events,
    }


def _calendar_property_sections(events):
    sorted_events = sorted(events, key=_calendar_event_sort_key)
    upcoming_events = [event for event in sorted_events if _calendar_parse_datetime(event.get("start_datetime", ""))[0] and _calendar_parse_datetime(event.get("start_datetime", ""))[0] >= datetime.now(timezone.utc)][:6]
    cleaning_schedule = [event for event in sorted_events if _normalize_calendar_event_type(event.get("event_type", "")) == "Cleaning"][:6]
    maintenance_schedule = [event for event in sorted_events if _normalize_calendar_event_type(event.get("event_type", "")) == "Maintenance"][:6]
    blocked_dates = [event for event in sorted_events if _normalize_calendar_event_type(event.get("event_type", "")) in {"Blocked Dates", "Personal Stay"}][:6]
    mini_calendar = []
    today = datetime.now(timezone.utc).date()
    for offset in range(7):
        day = today + timedelta(days=offset)
        day_events = []
        for event in sorted_events:
            start_dt, _ = _calendar_parse_datetime(event.get("start_datetime", ""))
            if start_dt and start_dt.date() == day:
                day_events.append(event)
        mini_calendar.append({
            "date": day.isoformat(),
            "label": day.strftime("%a"),
            "day": day.day,
            "count": len(day_events),
            "events": day_events[:3],
        })
    return {
        "mini_calendar": mini_calendar,
        "upcoming_events": upcoming_events,
        "cleaning_schedule": cleaning_schedule,
        "maintenance_schedule": maintenance_schedule,
        "blocked_dates": blocked_dates,
        "all_events": sorted_events,
    }


def _build_calendar_page_context(scope, owner_account=None):
    owner_account = owner_account or {}
    calendar_view = str(request.args.get("view", "")).strip().lower()
    allowed_views = {"month", "week", "day"} if scope == "owner" else {"month", "week", "day", "timeline"}
    if calendar_view not in allowed_views:
        calendar_view = "month" if scope == "owner" else "timeline"

    filters = {
        "property": str(request.args.get("property", "")).strip(),
        "owner": str(request.args.get("owner", "")).strip(),
        "professional": str(request.args.get("professional", "")).strip(),
        "category": str(request.args.get("category", "")).strip(),
        "priority": str(request.args.get("priority", "")).strip(),
        "status": str(request.args.get("status", "")).strip(),
        "city": str(request.args.get("city", "")).strip(),
        "search": str(request.args.get("q", "")).strip(),
    }

    owner_properties = []
    if scope == "owner":
        owner_properties = _owner_properties_for_account(owner_account.get("id", ""))
        property_ids = [property_record.get("id", "") for property_record in owner_properties]
        events = _load_calendar_events(owner_id=owner_account.get("id", ""), property_ids=property_ids)
    else:
        events = _load_calendar_events()
        owner_properties = _load_owner_properties()

    property_map = {str(property_record.get("id", "")).strip(): property_record for property_record in _load_owner_properties()}
    owner_map = {str(account.get("id", "")).strip(): account for account in _load_owner_accounts()}
    task_map = {str(task.get("id", "")).strip(): task for task in _load_operations_tasks()}
    enriched_events = [_calendar_enrich_event(event, property_map, owner_map, task_map) for event in events]
    filtered_events = _calendar_filter_events(enriched_events, filters)
    filtered_events.sort(key=_calendar_event_sort_key)
    groups = _calendar_group_events(filtered_events, calendar_view)

    property_options = sorted({event.get("property_label", "") for event in enriched_events if event.get("property_label", "")})
    owner_options = sorted({event.get("owner_label", "") for event in enriched_events if event.get("owner_label", "")})
    professional_options = sorted({event.get("professional", "") for event in enriched_events if event.get("professional", "")})
    category_options = sorted({event.get("event_type", "") for event in enriched_events if event.get("event_type", "")})
    city_options = sorted({event.get("city", "") for event in enriched_events if event.get("city", "")})
    status_options = sorted({event.get("status", "") for event in enriched_events if event.get("status", "")})

    return {
        "calendar_scope": scope,
        "calendar_view": calendar_view,
        "calendar_views": [view for view in ["month", "week", "day", "timeline"] if view in allowed_views],
        "calendar_filters": filters,
        "calendar_groups": groups,
        "calendar_events": filtered_events,
        "calendar_total_count": len(enriched_events),
        "calendar_filtered_count": len(filtered_events),
        "calendar_summary": _calendar_widget_summary(filtered_events),
        "calendar_property_options": property_options,
        "calendar_owner_options": owner_options,
        "calendar_professional_options": professional_options,
        "calendar_category_options": category_options,
        "calendar_city_options": city_options,
        "calendar_status_options": status_options,
        "calendar_priority_options": ["LOW", "NORMAL", "HIGH", "URGENT"],
        "calendar_owner_properties": owner_properties,
        "calendar_can_create": scope == "owner",
        "calendar_scope_label": "Owner Calendar" if scope == "owner" else "Admin Calendar",
        "calendar_scope_description": "Only your properties" if scope == "owner" else "All properties",
        "calendar_external_integration_points": CALENDAR_EXTERNAL_INTEGRATION_POINTS,
    }


def _owner_portal_dashboard_context(owner_account, owner_requests, current_lang):
    dashboard_copy = _owner_dashboard_copy(current_lang)
    owner_properties = [
        property_record
        for property_record in _owner_properties_for_account(owner_account.get("id", ""))
        if str(property_record.get("owner_id", "")).strip() == str(owner_account.get("id", "")).strip()
    ]
    owner_reservations = _load_reservations(owner_id=owner_account.get("id", ""), property_ids=[property_record.get("id", "") for property_record in owner_properties])
    owner_calendar_context = _build_calendar_page_context("owner", owner_account)
    calendar_widget = _calendar_dashboard_widget(owner_calendar_context["calendar_events"], scope="owner")
    reservation_widget = _reservation_dashboard_widgets(owner_reservations, scope="owner")
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
        "calendar_widget": calendar_widget,
        "reservation_widget": reservation_widget,
        "summary_line": dashboard_copy["hero_summary_line"],
        "status_note_key": status_note_key,
        "last_completed_task_key": last_completed_task_key,
        "ui": dashboard_copy,
    }

    return owner_portal


def _property_calendar_context(property_record, owner_account=None):
    property_record = property_record or {}
    owner_account = owner_account or {}
    property_id = str(property_record.get("id", "")).strip()
    owner_id = str(property_record.get("owner_id", "")).strip() or str(owner_account.get("id", "")).strip()
    if not property_id:
        return _calendar_property_sections([])

    property_map = {property_id: property_record}
    owner_map = {}
    if owner_account:
        owner_map[owner_id] = owner_account
    elif owner_id:
        owner_map[owner_id] = _find_owner_account(owner_id) or {}
    task_map = {str(task.get("id", "")).strip(): task for task in _load_operations_tasks()}
    events = _load_calendar_events(owner_id=owner_id or None, property_ids=[property_id])
    enriched_events = [_calendar_enrich_event(event, property_map, owner_map, task_map) for event in events]
    return _calendar_property_sections(enriched_events)


def _owner_property_service_requests(owner_account, property_record):
    owner_id = str((owner_account or {}).get("id", "")).strip()
    property_id = str((property_record or {}).get("id", "")).strip()
    property_name = str((property_record or {}).get("name", "")).strip().lower()
    property_location = str((property_record or {}).get("location", "")).strip().lower()
    if not owner_id or not property_id:
        return []

    matched_requests = []
    for record in _load_service_requests():
        if str(record.get("request_source", "public")).lower() != "owner":
            continue
        if str(record.get("owner_id", "")).strip() != owner_id:
            continue

        request_property_id = str(record.get("property_id", "")).strip()
        request_property_name = str(record.get("property", "")).strip().lower()
        request_location = str(record.get("property_city", "")).strip().lower()

        if request_property_id and request_property_id == property_id:
            matched_requests.append(record)
            continue
        if property_name and request_property_name == property_name:
            matched_requests.append(record)
            continue
        if property_location and request_location and request_location == property_location:
            matched_requests.append(record)
    matched_requests.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return matched_requests


def _owner_property_management_context(owner_account):
    owner_properties = _owner_properties_for_account(owner_account.get("id", ""))
    property_cards = []
    for property_record in owner_properties:
        status = _normalize_owner_property_status(property_record.get("status", OWNER_PROPERTY_STATUS_DEFAULT))
        checklist_completed, checklist_total = _owner_property_checklist_completion(property_record)
        property_cards.append({
            **property_record,
            "status": status,
            "status_label": _owner_property_status_label(status),
            "status_tone": _owner_property_status_tone(status),
            "checklist_completed": checklist_completed,
            "checklist_total": checklist_total,
            "checklist_percent": int(round((checklist_completed / checklist_total) * 100)) if checklist_total else 0,
        })
    property_cards.sort(key=lambda item: (str(item.get("created_at", "")), str(item.get("id", ""))), reverse=True)
    return property_cards


def _owner_property_detail_context(owner_account, property_record):
    status = _normalize_owner_property_status(property_record.get("status", OWNER_PROPERTY_STATUS_DEFAULT))
    checklist_items = [
        {
            "key": "guest_guide_ready",
            "label": "Guest guide",
            "ready": bool(property_record.get("guest_guide_ready")),
        },
        {
            "key": "access_instructions_ready",
            "label": "Access instructions",
            "ready": bool(property_record.get("access_instructions_ready")),
        },
        {
            "key": "emergency_contact_ready",
            "label": "Emergency contact",
            "ready": bool(property_record.get("emergency_contact_ready")),
        },
        {
            "key": "cleaning_partner_ready",
            "label": "Cleaning partner",
            "ready": bool(property_record.get("cleaning_partner_ready")),
        },
    ]
    checklist_completed, checklist_total = _owner_property_checklist_completion(property_record)
    service_requests = _owner_property_service_requests(owner_account, property_record)
    calendar = _property_calendar_context(property_record, owner_account)
    property_reservations = _load_reservations(owner_id=owner_account.get("id", ""), property_ids=[property_record.get("id", "")])
    availability = _property_availability_engine(property_record, property_reservations)
    return {
        "property": {
            **property_record,
            "status": status,
            "status_label": _owner_property_status_label(status),
            "status_tone": _owner_property_status_tone(status),
            "checklist_completed": checklist_completed,
            "checklist_total": checklist_total,
            "checklist_percent": int(round((checklist_completed / checklist_total) * 100)) if checklist_total else 0,
            "availability": availability,
        },
        "checklist_items": checklist_items,
        "service_requests": service_requests,
        "calendar": calendar,
        "availability": availability,
        "history_count": len(service_requests),
    }


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


def professional_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get(PROFESSIONAL_SESSION_LOGGED_IN_KEY):
            return redirect(url_for("professionals_login", next=request.path))
        professional_account = _current_professional_account()
        if not professional_account or _normalize_professional_account_status(professional_account.get("status", "PENDING")) not in {"APPROVED", "ACTIVE"}:
            session.pop(PROFESSIONAL_SESSION_LOGGED_IN_KEY, None)
            session.pop(PROFESSIONAL_SESSION_ID_KEY, None)
            session.pop(PROFESSIONAL_SESSION_EMAIL_KEY, None)
            session.pop(PROFESSIONAL_SESSION_NAME_KEY, None)
            return redirect(url_for("professionals_login", next=request.path, access="denied"))
        g.professional_account = professional_account
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
            "website": str(request.form.get("website", "")).strip(),
        })

        if _public_form_honeypot_filled(form_values["website"]):
            _public_form_audit_event("owner_register", "spam_submission_blocked", "spam_honeypot_blocked")
            return redirect(url_for("owners_login", magic_sent="1", delivery="generic", lang=current_lang))

        if _public_form_rate_limited("owner_register"):
            _public_form_audit_event("owner_register", "rate_limit_blocked", "rate_limit_blocked")
            return redirect(url_for("owners_login", magic_sent="1", delivery="generic", lang=current_lang))

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

        if form_values["full_name"] and not _public_form_has_plausible_name(form_values["full_name"]):
            errors["full_name"] = "fullNameRequiredError"

        if form_values["email"] and not _public_form_has_valid_email(form_values["email"]):
            errors["email"] = "emailRequiredError"

        if form_values["phone"] and not _public_form_has_minimum_digits(form_values["phone"]):
            errors["phone"] = "phoneRequiredError"

        if form_values["city"] and not _public_form_has_plausible_location(form_values["city"]):
            errors["city"] = "cityRequiredError"

        if form_values["property_type"] and not _public_form_has_plausible_name(form_values["property_type"]):
            errors["property_type"] = "propertyTypeRequiredError"

        if form_values["property_name"] and _public_form_text_is_spam(form_values["property_name"]):
            errors["property_name"] = "propertyTypeRequiredError"

        if form_values["notes"] and _public_form_text_is_spam(form_values["notes"]):
            _public_form_audit_event("owner_register", "spam_submission_blocked", "content_spam_detected")
            return redirect(url_for("owners_login", magic_sent="1", delivery="generic", lang=current_lang))

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
                _send_owner_registration_notification_email(saved_account, request.url, current_lang)
                global _OWNER_DB_BACKFILL_SUPPRESSED
                previous_state = _OWNER_DB_BACKFILL_SUPPRESSED
                _OWNER_DB_BACKFILL_SUPPRESSED = True
                try:
                    if not existing_account:
                        _append_owner_activity_event(
                            saved_account["id"],
                            "owner_registered",
                            "Owner registered",
                            saved_account.get("full_name", ""),
                        )
                    _upsert_operations_task_from_source(
                        _operations_task_payload_from_source("OWNER_REGISTRATION", saved_account),
                        append_created_event=True,
                        notify=False,
                    )
                finally:
                    _OWNER_DB_BACKFILL_SUPPRESSED = previous_state
                _dispatch_operations_notification(
                    _operations_task_payload_from_source("OWNER_REGISTRATION", saved_account),
                    url_for("admin_operations_detail", task_id=saved_account["id"], _external=True),
                    notification_type="task_created",
                )
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
                "status": OWNER_PROPERTY_STATUS_DEFAULT,
                "guest_guide_ready": 0,
                "access_instructions_ready": 0,
                "emergency_contact_ready": 0,
                "cleaning_partner_ready": 0,
            })
            if saved_property:
                app.logger.info("Owner property created for %s: %s", owner_account.get("email", ""), saved_property["name"])
                _append_owner_activity_event(
                    owner_account["id"],
                    "property_added",
                    "Property added",
                    f"{saved_property.get('name', '')} · {saved_property.get('location', '')}",
                )
                _append_property_activity_event(
                    saved_property["id"],
                    owner_account["id"],
                    "property_created",
                    "Property created",
                    f"{saved_property.get('name', '')} · {saved_property.get('location', '')}",
                )
                _append_property_activity_event(
                    saved_property["id"],
                    owner_account["id"],
                    "owner_assigned",
                    "Owner assigned",
                    owner_account.get("full_name", ""),
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


@app.route("/owners/calendar", methods=["GET", "POST"])
@owner_required
def owners_calendar():
    current_lang = _resolve_current_language()
    owner_account = _current_owner_account()
    if request.method == "POST":
        property_record = _find_owner_property(request.form.get("property_id", ""))
        if not property_record or str(property_record.get("owner_id", "")).strip() != str(owner_account.get("id", "")).strip():
            return Response("Property not found.", status=404, mimetype="text/plain")
        form_values = {
            "event_type": _normalize_calendar_event_type(request.form.get("event_type", "")),
            "title": str(request.form.get("title", "")).strip(),
            "description": str(request.form.get("description", "")).strip(),
            "start_datetime": str(request.form.get("start_datetime", "")).strip(),
            "end_datetime": str(request.form.get("end_datetime", "")).strip(),
            "all_day": bool(request.form.get("all_day")),
        }
        if form_values["event_type"] not in CALENDAR_OWNER_EVENT_TYPES:
            return Response("Unsupported owner calendar event.", status=400, mimetype="text/plain")
        created_event = _create_calendar_event_from_owner(owner_account, property_record, form_values)
        if not created_event:
            return Response("Failed to create calendar event.", status=400, mimetype="text/plain")
        return redirect(url_for("owners_calendar", view=request.args.get("view", "month"), lang=current_lang))

    context = _build_calendar_page_context("owner", owner_account)
    return render_template(
        "calendar.html",
        current_lang=current_lang,
        owner_account=owner_account,
        **context,
    )


@app.route("/owners/reservations", methods=["GET", "POST"])
@owner_required
def owners_reservations():
    current_lang = _resolve_current_language()
    owner_account = _current_owner_account()
    owner_properties = _owner_properties_for_account(owner_account.get("id", ""))
    if request.method == "POST":
        property_id = str(request.form.get("property_id", "")).strip()
        property_record = _find_owner_property(property_id)
        if not property_record or str(property_record.get("owner_id", "")).strip() != str(owner_account.get("id", "")).strip():
            return Response("Property not found.", status=404, mimetype="text/plain")

        reservation_kind = str(request.form.get("reservation_kind", "reservation")).strip().lower()
        metadata_kind = "blocked_dates" if reservation_kind == "blocked_dates" else "reservation"
        reservation_payload = {
            "id": "",
            "property_id": property_id,
            "reservation_source": str(request.form.get("reservation_source", "Manual Reservation")).strip() or "Manual Reservation",
            "reservation_reference": str(request.form.get("reservation_reference", request.form.get("external_reference", ""))).strip(),
            "external_reference": str(request.form.get("external_reference", "")).strip(),
            "channel_name": str(request.form.get("channel_name", request.form.get("reservation_source", "Manual Reservation"))).strip(),
            "channel_status": str(request.form.get("channel_status", "SYNCED")).strip(),
            "last_sync": str(request.form.get("last_sync", "")).strip(),
            "external_payload": {
                "kind": metadata_kind,
                "title": str(request.form.get("title", "")).strip(),
                "notes": str(request.form.get("notes", "")).strip(),
                "source": str(request.form.get("reservation_source", "Manual Reservation")).strip(),
            },
            "guest_first_name": str(request.form.get("guest_first_name", "")).strip(),
            "guest_last_name": str(request.form.get("guest_last_name", "")).strip(),
            "guest_email": str(request.form.get("guest_email", "")).strip(),
            "guest_phone": str(request.form.get("guest_phone", "")).strip(),
            "adults": int(str(request.form.get("adults", "1")).strip() or 1),
            "children": int(str(request.form.get("children", "0")).strip() or 0),
            "infants": int(str(request.form.get("infants", "0")).strip() or 0),
            "pets": int(str(request.form.get("pets", "0")).strip() or 0),
            "arrival_datetime": str(request.form.get("arrival_datetime", "")).strip(),
            "departure_datetime": str(request.form.get("departure_datetime", "")).strip(),
            "status": "CONFIRMED" if metadata_kind == "blocked_dates" else _normalize_reservation_status(request.form.get("status", "PENDING")),
            "notes": str(request.form.get("notes", "")).strip(),
            "language": current_lang,
            "created_by": f"owner:{owner_account.get('id', '')}",
            "metadata": {
                "kind": metadata_kind,
                "title": str(request.form.get("title", "")).strip(),
                "notes": str(request.form.get("notes", "")).strip(),
            },
            "kind": metadata_kind,
            "title": str(request.form.get("title", "")).strip(),
        }
        created_reservation = _create_reservation(reservation_payload, created_by=f"owner:{owner_account.get('id', '')}")
        if not created_reservation:
            return Response("Failed to create reservation.", status=400, mimetype="text/plain")
        return redirect(url_for("owner_reservation_detail", reservation_id=created_reservation["id"], lang=current_lang))

    filters = {
        "property": str(request.args.get("property", "")).strip(),
        "owner": str(request.args.get("owner", "")).strip(),
        "guest": str(request.args.get("guest", "")).strip(),
        "status": str(request.args.get("status", "")).strip(),
        "arrival": str(request.args.get("arrival", "")).strip(),
        "departure": str(request.args.get("departure", "")).strip(),
        "source": str(request.args.get("source", "")).strip(),
        "search": str(request.args.get("q", "")).strip(),
    }
    context = _reservation_list_context(owner_account=owner_account, scope="owner", filters=filters)
    context.update({
        "current_lang": current_lang,
        "owner_account": owner_account,
        "owner_properties": owner_properties,
        "page_title": "Reservations",
        "page_meta": "Owner reservation workspace",
        "create_allowed": True,
        "filters": filters,
    })
    return render_template("reservations_dashboard.html", **context)


@app.get("/owners/reservations/<reservation_id>")
@owner_required
def owner_reservation_detail(reservation_id):
    current_lang = _resolve_current_language()
    owner_account = _current_owner_account()
    reservation = _find_reservation(reservation_id)
    if not reservation:
        return Response("Reservation not found.", status=404, mimetype="text/plain")
    property_record = _find_owner_property(reservation.get("property_id", ""))
    if not property_record or str(property_record.get("owner_id", "")).strip() != str(owner_account.get("id", "")).strip():
        return Response("Reservation not found.", status=404, mimetype="text/plain")

    context = _reservation_detail_context(reservation, scope="owner", owner_account=owner_account)
    context.update({
        "current_lang": current_lang,
        "owner_account": owner_account,
        "page_title": "Reservation detail",
        "page_meta": "Owner reservation detail",
    })
    return render_template("reservation_detail.html", **context)


@app.route("/owners/properties", methods=["GET"])
@owner_required
def owners_properties():
    current_lang = _resolve_current_language()
    owner_account = _current_owner_account()
    property_cards = _owner_property_management_context(owner_account)
    return render_template(
        "owners_properties.html",
        owner_account=owner_account,
        current_lang=current_lang,
        property_cards=property_cards,
        property_count=len(property_cards),
    )


@app.route("/owners/properties/<property_id>", methods=["GET", "POST"])
@owner_required
def owners_property_detail(property_id):
    current_lang = _resolve_current_language()
    owner_account = _current_owner_account()
    property_record = _find_owner_property(property_id)
    if not property_record or str(property_record.get("owner_id", "")).strip() != str(owner_account.get("id", "")).strip():
        return Response("Property not found.", status=404, mimetype="text/plain")

    if request.method == "POST":
        previous_status = _normalize_owner_property_status(property_record.get("status", OWNER_PROPERTY_STATUS_DEFAULT))
        previous_notes = str(property_record.get("notes", "")).strip()
        updated_property = {
            **property_record,
            "status": _normalize_owner_property_status(request.form.get("status", property_record.get("status", OWNER_PROPERTY_STATUS_DEFAULT))),
            "notes": str(request.form.get("notes", property_record.get("notes", ""))).strip(),
            "guest_guide_ready": _normalize_owner_property_checklist_value(request.form.get("guest_guide_ready")),
            "access_instructions_ready": _normalize_owner_property_checklist_value(request.form.get("access_instructions_ready")),
            "emergency_contact_ready": _normalize_owner_property_checklist_value(request.form.get("emergency_contact_ready")),
            "cleaning_partner_ready": _normalize_owner_property_checklist_value(request.form.get("cleaning_partner_ready")),
        }
        saved_property = _append_owner_property(updated_property)
        if saved_property:
            if saved_property["status"] != previous_status:
                _append_owner_activity_event(
                    owner_account["id"],
                    "status_changed",
                    "Status changed",
                    f"{saved_property.get('name', '')}: {previous_status} -> {saved_property['status']}",
                )
                _append_property_activity_event(
                    saved_property["id"],
                    owner_account["id"],
                    "status_changed",
                    "Status changed",
                    f"Status changed: {previous_status} -> {saved_property['status']}",
                )
            if any(bool(saved_property.get(field)) != bool(property_record.get(field)) for field in OWNER_PROPERTY_CHECKLIST_FIELDS):
                _append_property_activity_event(
                    saved_property["id"],
                    owner_account["id"],
                    "checklist_updated",
                    "Checklist updated",
                    "Readiness checklist changed.",
                )
            if saved_property.get("notes", "").strip() != previous_notes:
                _append_owner_activity_event(
                    owner_account["id"],
                    "note_added",
                    "Property notes updated",
                    saved_property.get("notes", ""),
                )
                _append_property_activity_event(
                    saved_property["id"],
                    owner_account["id"],
                    "note_added",
                    "Note added",
                    saved_property.get("notes", ""),
                )
        return redirect(url_for("owners_property_detail", property_id=property_id, lang=current_lang))

    context = _owner_property_detail_context(owner_account, property_record)
    return render_template(
        "owners_property_detail.html",
        owner_account=owner_account,
        current_lang=current_lang,
        property_context=context,
    )


@app.route("/owners/request-service", methods=["GET", "POST"])
@owner_required
def owners_request_service():
    current_lang = _resolve_current_language()
    owner_account = _current_owner_account()
    selected_property = _find_owner_property(request.args.get("property_id", ""))
    if selected_property and str(selected_property.get("owner_id", "")).strip() != str(owner_account.get("id", "")).strip():
        selected_property = None
    form_values = {
        "category": _normalize_owner_service_category(request.args.get("category", "")),
        "preferred_date": "",
        "property_id": selected_property.get("id", "") if selected_property else "",
        "property": selected_property.get("name", "") if selected_property else owner_account.get("property_name", "") or owner_account.get("property_type", ""),
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
            "property_id": str(request.form.get("property_id", "")).strip(),
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
            property_record = _find_owner_property(form_values["property_id"]) if form_values["property_id"] else None
            if property_record and str(property_record.get("owner_id", "")).strip() != str(owner_account.get("id", "")).strip():
                property_record = None
            if property_record and not form_values["property"]:
                form_values["property"] = property_record.get("name", "")

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
                "property_id": property_record.get("id", "") if property_record else "",
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

            global _OWNER_DB_BACKFILL_SUPPRESSED
            previous_state = _OWNER_DB_BACKFILL_SUPPRESSED
            _OWNER_DB_BACKFILL_SUPPRESSED = True
            try:
                _append_owner_activity_event(
                    owner_account["id"],
                    "service_request_submitted",
                    "Service request submitted",
                    f"{request_record.get('service_category', '')} · {request_record.get('property', '')}",
                )
                if property_record:
                    _append_property_activity_event(
                        property_record["id"],
                        owner_account["id"],
                        "service_request_submitted",
                        "Service request submitted",
                        f"{request_record.get('service_category', '')} · {request_record.get('property', '')}",
                    )
                _upsert_operations_task_from_source(
                    _operations_task_payload_from_source("OWNER_SERVICE_REQUEST", request_record),
                    append_created_event=True,
                    notify=False,
                )
            finally:
                _OWNER_DB_BACKFILL_SUPPRESSED = previous_state
            _dispatch_operations_notification(
                _operations_task_payload_from_source("OWNER_SERVICE_REQUEST", request_record),
                url_for("admin_operations_detail", task_id=request_record["id"], _external=True),
                notification_type="task_created",
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
            "website": str(request.form.get("company_website", request.form.get("website", ""))).strip(),
            "city": str(request.form.get("city", "")).strip(),
            "country": str(request.form.get("country", "")).strip(),
            "service_category": str(request.form.get("service_category", "")).strip(),
            "description": str(request.form.get("description", "")).strip(),
            "years_in_business": str(request.form.get("years_in_business", "")).strip(),
        })

        website_honeypot = str(request.form.get("website", "")).strip() if "company_website" in request.form else ""

        if _public_form_honeypot_filled(website_honeypot):
            _public_form_audit_event("partner_application", "spam_submission_blocked", "spam_honeypot_blocked")
            return render_template(
                "partners_apply.html",
                service_categories=_partner_service_category_items(),
                submitted=True,
                application_id="",
                form_values={**form_values, "website": ""},
                errors={},
                save_error=False,
            )

        if _public_form_rate_limited("partner_application"):
            _public_form_audit_event("partner_application", "rate_limit_blocked", "rate_limit_blocked")
            return render_template(
                "partners_apply.html",
                service_categories=_partner_service_category_items(),
                submitted=True,
                application_id="",
                form_values={**form_values, "website": ""},
                errors={},
                save_error=False,
            )

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

        if form_values["company_name"] and not _public_form_has_plausible_name(form_values["company_name"]):
            errors["company_name"] = "companyNameRequiredError"

        if form_values["contact_person"] and not _public_form_has_plausible_name(form_values["contact_person"]):
            errors["contact_person"] = "contactPersonRequiredError"

        if form_values["email"] and not _public_form_has_valid_email(form_values["email"]):
            errors["email"] = "emailRequiredError"

        if form_values["phone"] and not _public_form_has_minimum_digits(form_values["phone"]):
            errors["phone"] = "phoneRequiredError"

        if form_values["city"] and not _public_form_has_plausible_location(form_values["city"]):
            errors["city"] = "cityRequiredError"

        if form_values["country"] and not _public_form_has_plausible_location(form_values["country"]):
            errors["country"] = "countryRequiredError"

        if form_values["service_category"] and form_values["service_category"] not in PARTNER_SERVICE_CATEGORIES:
            errors["service_category"] = "serviceCategoryInvalidError"

        if form_values["years_in_business"] and not form_values["years_in_business"].isdigit():
            errors["years_in_business"] = "yearsInBusinessInvalidError"

        if form_values["description"] and _public_form_text_is_spam(form_values["description"]):
            _public_form_audit_event("partner_application", "spam_submission_blocked", "content_spam_detected")
            return render_template(
                "partners_apply.html",
                service_categories=_partner_service_category_items(),
                submitted=True,
                application_id="",
                form_values={**form_values, "website": ""},
                errors={},
                save_error=False,
            )

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
            _upsert_operations_task_from_source(
                _operations_task_payload_from_source("PARTNER_APPLICATION", record),
                append_created_event=True,
                notify=True,
            )
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
            "website": str(request.form.get("website", "")).strip(),
        })

        if _public_form_honeypot_filled(form_values["website"]):
            _public_form_audit_event("service_request", "spam_submission_blocked", "spam_honeypot_blocked")
            submitted = True
            request_record = {"status": "new", "property_city": "", "service_category": ""}
            return render_template(
                "request_service.html",
                form_values={**form_values, "website": ""},
                errors={},
                service_categories=_network_service_category_items(),
                matching_providers=_service_request_matching_providers(form_values["service_category"]),
                submitted=True,
                request_record=request_record,
            )

        if _public_form_rate_limited("service_request"):
            _public_form_audit_event("service_request", "rate_limit_blocked", "rate_limit_blocked")
            submitted = True
            request_record = {"status": "new", "property_city": "", "service_category": ""}
            return render_template(
                "request_service.html",
                form_values={**form_values, "website": ""},
                errors={},
                service_categories=_network_service_category_items(),
                matching_providers=_service_request_matching_providers(form_values["service_category"]),
                submitted=True,
                request_record=request_record,
            )

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

        if form_values["name"] and not _public_form_has_plausible_name(form_values["name"]):
            errors["name"] = "nameRequiredError"

        if form_values["email"] and not _public_form_has_valid_email(form_values["email"]):
            errors["email"] = "emailRequiredError"

        if form_values["phone"] and not _public_form_has_minimum_digits(form_values["phone"]):
            errors["phone"] = "phoneRequiredError"

        if form_values["property_city"] and not _public_form_has_plausible_location(form_values["property_city"]):
            errors["property_city"] = "propertyCityRequiredError"

        if form_values["property_type"] and not _public_form_has_plausible_name(form_values["property_type"]):
            errors["property_type"] = "propertyTypeRequiredError"

        if form_values["service_category"] and form_values["service_category"] not in NETWORK_SERVICE_CATEGORIES:
            errors["service_category"] = "serviceCategoryInvalidError"

        if form_values["description"] and _public_form_text_is_spam(form_values["description"]):
            _public_form_audit_event("service_request", "spam_submission_blocked", "content_spam_detected")
            submitted = True
            request_record = {"status": "new", "property_city": "", "service_category": ""}
            return render_template(
                "request_service.html",
                form_values={**form_values, "website": ""},
                errors={},
                service_categories=_network_service_category_items(),
                matching_providers=_service_request_matching_providers(form_values["service_category"]),
                submitted=True,
                request_record=request_record,
            )

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
            _upsert_operations_task_from_source(
                _operations_task_payload_from_source("CONCIERGE_REQUEST", request_record),
                append_created_event=True,
                notify=True,
            )
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
            "website": str(request.form.get("website", "")).strip(),
        })

        if _public_form_honeypot_filled(form_values["website"]):
            _public_form_audit_event("professional_application", "spam_submission_blocked", "spam_honeypot_blocked")
            return render_template(
                "professionals_apply.html",
                service_categories=_professional_service_category_items(),
                submitted=True,
                application_id="",
                form_values={**form_values, "website": ""},
                errors={},
                save_error=False,
            )

        if _public_form_rate_limited("professional_application"):
            _public_form_audit_event("professional_application", "rate_limit_blocked", "rate_limit_blocked")
            return render_template(
                "professionals_apply.html",
                service_categories=_professional_service_category_items(),
                submitted=True,
                application_id="",
                form_values={**form_values, "website": ""},
                errors={},
                save_error=False,
            )

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

        if form_values["full_name"] and not _public_form_has_plausible_name(form_values["full_name"]):
            errors["full_name"] = "fullNameRequiredError"

        if form_values["email"] and not _public_form_has_valid_email(form_values["email"]):
            errors["email"] = "emailRequiredError"

        if form_values["phone"] and not _public_form_has_minimum_digits(form_values["phone"]):
            errors["phone"] = "phoneRequiredError"

        if form_values["city"] and not _public_form_has_plausible_location(form_values["city"]):
            errors["city"] = "cityRequiredError"

        if form_values["country"] and not _public_form_has_plausible_location(form_values["country"]):
            errors["country"] = "countryRequiredError"

        if form_values["professional_category"] and form_values["professional_category"] not in PROFESSIONAL_SERVICE_CATEGORIES:
            errors["professional_category"] = "categoryInvalidError"

        if form_values["short_bio"] and _public_form_text_is_spam(form_values["short_bio"]):
            _public_form_audit_event("professional_application", "spam_submission_blocked", "content_spam_detected")
            return render_template(
                "professionals_apply.html",
                service_categories=_professional_service_category_items(),
                submitted=True,
                application_id="",
                form_values={**form_values, "website": ""},
                errors={},
                save_error=False,
            )

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
            _upsert_operations_task_from_source(
                _operations_task_payload_from_source("PROFESSIONAL_APPLICATION", record),
                append_created_event=True,
                notify=True,
            )
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


@app.route("/professionals/login", methods=["GET", "POST"])
def professionals_login():
    form_values = {"email": ""}
    errors = {}
    if request.method == "POST":
        raw_email = str(request.form.get("email", "")).strip()
        form_values["email"] = raw_email
        if not raw_email:
            errors["email"] = "emailRequiredError"
        else:
            professional_account = _find_professional_account_by_email(raw_email)
            if not professional_account:
                return redirect(url_for("professionals_login", magic_sent="1"))

            magic_token = _create_professional_magic_token(professional_account["email"])
            if not magic_token:
                return redirect(url_for("professionals_login", magic_sent="0"))

            login_url = f"{SITE_URL}{url_for('professional_magic_login', token=magic_token['token'])}"
            send_result = _send_professional_magic_link(professional_account["email"], login_url)
            if not send_result.get("ok"):
                _consume_professional_magic_token(magic_token["token"])
                return redirect(url_for("professionals_login", magic_sent="0"))

            return redirect(url_for("professionals_login", magic_sent="1"))

    return render_template("professionals_login.html", form_values=form_values, errors=errors), (400 if errors else 200)


@app.get("/auth/professional-magic/<token>")
def professional_magic_login(token):
    token_record = _find_professional_magic_token(token)
    if not token_record:
        return redirect(url_for("professionals_login", invalid_token="1"))

    professional_account = _find_professional_account_by_email(token_record.get("email", ""))
    if not professional_account:
        _consume_professional_magic_token(token)
        return redirect(url_for("professionals_login", invalid_token="1"))

    created_at = _parse_iso_datetime(token_record.get("created_at", ""))
    if not created_at or datetime.now(timezone.utc) >= created_at + timedelta(minutes=PROFESSIONAL_MAGIC_LINK_TTL_MINUTES):
        _consume_professional_magic_token(token)
        return redirect(url_for("professionals_login", expired_token="1"))

    session[PROFESSIONAL_SESSION_LOGGED_IN_KEY] = True
    session[PROFESSIONAL_SESSION_ID_KEY] = professional_account.get("id", "")
    session[PROFESSIONAL_SESSION_EMAIL_KEY] = professional_account.get("email", "")
    session[PROFESSIONAL_SESSION_NAME_KEY] = professional_account.get("full_name", "")
    _upsert_professional_account({
        **professional_account,
        "last_login_at": _utc_now_iso(),
    })
    _consume_professional_magic_token(token)
    return redirect(url_for("professionals_dashboard"))


@app.get("/professionals/logout")
def professionals_logout():
    session.pop(PROFESSIONAL_SESSION_LOGGED_IN_KEY, None)
    session.pop(PROFESSIONAL_SESSION_ID_KEY, None)
    session.pop(PROFESSIONAL_SESSION_EMAIL_KEY, None)
    session.pop(PROFESSIONAL_SESSION_NAME_KEY, None)
    return redirect(url_for("professionals_login"))


@app.get("/professionals/dashboard")
@professional_required
def professionals_dashboard():
    professional_account = _current_professional_account()
    context = _professional_dashboard_context(professional_account)
    return render_template("professionals_dashboard.html", **context)


@app.get("/professionals/tasks")
@professional_required
def professionals_tasks():
    professional_account = _current_professional_account()
    context = _professional_dashboard_context(professional_account)
    search_query = str(request.args.get("q", "")).strip().lower()
    tasks = context["assigned_tasks"]
    if search_query:
        tasks = [
            task
            for task in tasks
            if search_query in " ".join([
                str(task.get("title", "")).lower(),
                str(task.get("property_name", "")).lower(),
                str(task.get("property_location", "")).lower(),
                str(task.get("category", "")).lower(),
            ])
        ]
    return render_template("professionals_tasks.html", **context, tasks=tasks, search_query=request.args.get("q", ""))


@app.route("/professionals/tasks/<task_id>", methods=["GET", "POST"])
@professional_required
def professionals_task_detail(task_id):
    professional_account = _current_professional_account()
    task_record = _find_operations_task(task_id)
    if not task_record or not _professional_task_matches_account(task_record, professional_account):
        return Response("Task not found.", status=404, mimetype="text/plain")

    if request.method == "POST":
        action = str(request.form.get("task_action", "")).strip().lower()
        note_text = str(request.form.get("note", "")).strip()
        report_data = {
            "completed_work": str(request.form.get("completed_work", "")).strip(),
            "materials_used": str(request.form.get("materials_used", "")).strip(),
            "time_spent_minutes": str(request.form.get("time_spent_minutes", "")).strip(),
            "recommendations": str(request.form.get("recommendations", "")).strip(),
            "follow_up_needed": str(request.form.get("follow_up_needed", "")).strip(),
            "notes": str(request.form.get("completion_notes", "")).strip(),
        }
        attachment_slot = str(request.form.get("attachment_slot", "")).strip()
        attachment_category = str(request.form.get("attachment_category", "")).strip()
        attachment_name = str(request.form.get("attachment_name", "")).strip()
        attachment_file = request.files.get("attachment_file")
        attachment_data = None
        if action == "attachment" or attachment_slot or attachment_category or attachment_name or attachment_file:
            attachment_data = {
                "slot": attachment_slot,
                "category": attachment_category,
                "filename": attachment_name or (attachment_file.filename if attachment_file and attachment_file.filename else ""),
                "mime_type": attachment_file.mimetype if attachment_file else "",
            }
        if action == "accept":
            _professional_task_transition(task_record, professional_account, "accept")
        elif action in {"on_the_way", "ontheway"}:
            _professional_task_transition(task_record, professional_account, "on_the_way")
        elif action == "arrived":
            _professional_task_transition(task_record, professional_account, "arrived")
        elif action == "start":
            _professional_task_transition(task_record, professional_account, "start")
        elif action == "pause":
            _professional_task_transition(task_record, professional_account, "pause", note_text=note_text)
        elif action == "resume":
            _professional_task_transition(task_record, professional_account, "resume")
        elif action == "complete":
            _professional_task_transition(task_record, professional_account, "complete", note_text=note_text, report_data=report_data, attachment_data=attachment_data)
        elif action == "comment" and note_text:
            _append_operations_task_comment(task_id, _professional_account_display_label(professional_account), note_text)
            _append_operations_task_event(task_id, "professional_comment_added", "Professional comment added", note_text, status=_normalize_operations_task_status(task_record.get("status", "NEW")))
            _append_operations_notification(
                "professional_comment_added",
                "Professional comment added",
                note_text,
                task_id=task_id,
                source_type=task_record.get("source_type", ""),
                source_id=task_record.get("source_id", ""),
                status=_normalize_operations_task_status(task_record.get("status", "NEW")),
                channel="SYSTEM",
                recipient=str(os.getenv("ADMIN_NOTIFICATION_EMAIL", "")).strip() or _current_admin_operator_key(),
                operator_key=_current_admin_operator_key(),
                metadata="professional_comment",
            )
        elif action == "attachment":
            if attachment_data:
                attachment_entry = _append_operations_task_attachment(
                    task_id,
                    name=attachment_data.get("filename", "") or f"{attachment_data.get('slot', '') or attachment_data.get('category', '') or 'attachment'} placeholder",
                    uploaded_by=_professional_account_display_label(professional_account),
                    category=attachment_data.get("category", ""),
                    slot=attachment_data.get("slot", ""),
                    mime_type=attachment_data.get("mime_type", ""),
                )
                if attachment_entry:
                    _append_operations_notification(
                        "attachment_added",
                        "Professional attachment placeholder added",
                        f"{attachment_entry.get('slot', '') or attachment_entry.get('category', '') or 'Attachment'} · {attachment_entry.get('name', '')}",
                        task_id=task_id,
                        source_type=task_record.get("source_type", ""),
                        source_id=task_record.get("source_id", ""),
                        status=_normalize_operations_task_status(task_record.get("status", "NEW")),
                        channel="SYSTEM",
                        recipient=str(os.getenv("ADMIN_NOTIFICATION_EMAIL", "")).strip() or _current_admin_operator_key(),
                        operator_key=_current_admin_operator_key(),
                        metadata="professional_attachment",
                    )
        return redirect(url_for("professionals_task_detail", task_id=task_id))

    refreshed_task = _find_operations_task(task_id) or task_record
    timeline_events = [
        event
        for event in _load_operations_task_events(refreshed_task.get("request_id", ""))
        if str(event.get("event_type", "")).strip() in {"assigned", "status_changed", "completed", "workflow_transitioned", "note_added", "comment_added", "comment_added_internal", "attachment_added", "completion_report_updated", "professional_assigned", "professional_accepted", "professional_on_the_way", "professional_arrived", "professional_started", "professional_paused", "professional_resumed", "professional_completed", "professional_comment_added"}
    ]
    return render_template(
        "professionals_task_detail.html",
        task={
            **refreshed_task,
            "status_label": _operations_task_status_label(refreshed_task.get("status", "NEW")),
            "status_tone": _operations_task_status_tone(refreshed_task.get("status", "NEW")),
            "priority_label": _operations_task_priority_label(refreshed_task.get("priority", "NORMAL")),
            "priority_tone": _operations_task_priority_tone(refreshed_task.get("priority", "NORMAL")),
            "assigned_professional_label": _professional_account_display_label(professional_account),
        },
        professional_account=professional_account,
        timeline=list(reversed(timeline_events)),
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


def _admin_property_query_value(value):
    return str(value or "").strip().lower()


def _admin_property_owner_map():
    return {str(account.get("id", "")).strip(): account for account in _load_owner_accounts()}


def _admin_property_owner_label(owner_account):
    if not owner_account:
        return "Unassigned owner"
    full_name = str(owner_account.get("full_name", "")).strip()
    email = str(owner_account.get("email", "")).strip()
    if full_name and email:
        return f"{full_name} · {email}"
    return full_name or email or "Unassigned owner"


def _admin_property_service_requests(property_record, owner_account=None):
    property_id = str((property_record or {}).get("id", "")).strip()
    if not property_id:
        return []

    owner_account = owner_account or _find_owner_account(str((property_record or {}).get("owner_id", "")).strip())
    if owner_account:
        return _owner_property_service_requests(owner_account, property_record)

    property_name = str((property_record or {}).get("name", "")).strip().lower()
    property_location = str((property_record or {}).get("location", "")).strip().lower()
    matched_requests = []
    for record in _load_service_requests():
        if str(record.get("request_source", "public")).lower() != "owner":
            continue
        request_property_id = str(record.get("property_id", "")).strip()
        request_property_name = str(record.get("property", "")).strip().lower()
        request_location = str(record.get("property_city", "")).strip().lower()
        if request_property_id and request_property_id == property_id:
            matched_requests.append(record)
            continue
        if property_name and request_property_name == property_name:
            matched_requests.append(record)
            continue
        if property_location and request_location and request_location == property_location:
            matched_requests.append(record)
    matched_requests.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return matched_requests


def _admin_property_activity_timeline(property_record, owner_account=None, service_requests=None, property_events=None):
    owner_account = owner_account or _find_owner_account(str((property_record or {}).get("owner_id", "")).strip())
    service_requests = list(service_requests or [])
    property_events = list(property_events or [])

    timeline = []
    for event in property_events:
        event_type = str(event.get("event_type", "")).strip()
        title = str(event.get("title", "")).strip()
        detail = str(event.get("detail", "")).strip()
        if event_type in OWNER_PROPERTY_ACTIVITY_EVENT_VALUES and title:
            timeline.append({
                "created_at": str(event.get("created_at", "")),
                "type": event_type,
                "title": title,
                "detail": detail,
            })

    if not property_events:
        created_at = str((property_record or {}).get("created_at", "")).strip()
        if created_at:
            timeline.append({
                "created_at": created_at,
                "type": "property_created",
                "title": "Property created",
                "detail": f"{property_record.get('name', '')} · {property_record.get('location', '')}",
            })
            if owner_account:
                timeline.append({
                    "created_at": created_at,
                    "type": "owner_assigned",
                    "title": "Owner assigned",
                    "detail": _admin_property_owner_label(owner_account),
                })

    for request_record in service_requests:
        request_created_at = str(request_record.get("created_at", "")).strip()
        if not request_created_at:
            continue
        timeline.append({
            "created_at": request_created_at,
            "type": "service_request_submitted",
            "title": "Service request submitted",
            "detail": f"{request_record.get('service_category', '')} · {request_record.get('property', '')}",
        })
        if _normalize_service_request_status(request_record.get("status", "new")) == "completed":
            timeline.append({
                "created_at": str(request_record.get("last_update_at", request_created_at)).strip() or request_created_at,
                "type": "service_request_completed",
                "title": "Service request completed",
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


def _admin_properties_list_context():
    owner_accounts = _admin_property_owner_map()
    properties = _load_owner_properties()
    total_properties = len(properties)
    current_month = datetime.now(timezone.utc).strftime("%Y-%m")
    active_count = 0
    seasonal_count = 0
    inactive_count = 0
    property_types = set()
    property_rows = []

    for property_record in properties:
        status = _normalize_owner_property_status(property_record.get("status", OWNER_PROPERTY_STATUS_DEFAULT))
        if status == "ACTIVE":
            active_count += 1
        elif status == "SEASONAL":
            seasonal_count += 1
        elif status == "INACTIVE":
            inactive_count += 1

        property_type = str(property_record.get("property_type", "")).strip()
        if property_type:
            property_types.add(property_type)

        owner_account = owner_accounts.get(str(property_record.get("owner_id", "")).strip()) or _find_owner_account(property_record.get("owner_id", ""))
        property_service_requests = _admin_property_service_requests(property_record, owner_account)
        property_rows.append({
            **property_record,
            "status": status,
            "status_label": _owner_property_status_label(status),
            "status_tone": _owner_property_status_tone(status),
            "owner_label": _admin_property_owner_label(owner_account),
            "owner_name": owner_account.get("full_name", "") if owner_account else "",
            "owner_email": owner_account.get("email", "") if owner_account else "",
            "service_request_count": len(property_service_requests),
            "last_service_request_at": property_service_requests[0].get("created_at", "") if property_service_requests else "",
        })

    return {
        "properties": property_rows,
        "total_count": total_properties,
        "active_count": active_count,
        "seasonal_count": seasonal_count,
        "inactive_count": inactive_count,
        "property_type_options": sorted(property_types),
        "status_options": sorted(OWNER_PROPERTY_STATUS_VALUES),
    }


def _admin_property_detail_context(property_record):
    owner_accounts = _admin_property_owner_map()
    owner_account = owner_accounts.get(str(property_record.get("owner_id", "")).strip()) or _find_owner_account(property_record.get("owner_id", ""))
    property_service_requests = _admin_property_service_requests(property_record, owner_account)
    property_events = _load_property_activity_events(property_record.get("id", ""))
    timeline = _admin_property_activity_timeline(property_record, owner_account, property_service_requests, property_events)
    calendar = _property_calendar_context(property_record, owner_account)
    property_reservations = _load_reservations(property_ids=[property_record.get("id", "")])
    availability = _property_availability_engine(property_record, property_reservations)

    checklist_items = [
        {
            "key": "guest_guide_ready",
            "label": "Guest guide",
            "ready": bool(property_record.get("guest_guide_ready")),
        },
        {
            "key": "access_instructions_ready",
            "label": "Access instructions",
            "ready": bool(property_record.get("access_instructions_ready")),
        },
        {
            "key": "emergency_contact_ready",
            "label": "Emergency contact",
            "ready": bool(property_record.get("emergency_contact_ready")),
        },
        {
            "key": "cleaning_partner_ready",
            "label": "Cleaning partner",
            "ready": bool(property_record.get("cleaning_partner_ready")),
        },
    ]
    checklist_completed, checklist_total = _owner_property_checklist_completion(property_record)
    latest_service_requests = property_service_requests[:5]

    return {
        "property": {
            **property_record,
            "status": _normalize_owner_property_status(property_record.get("status", OWNER_PROPERTY_STATUS_DEFAULT)),
            "status_label": _owner_property_status_label(property_record.get("status", OWNER_PROPERTY_STATUS_DEFAULT)),
            "status_tone": _owner_property_status_tone(property_record.get("status", OWNER_PROPERTY_STATUS_DEFAULT)),
            "checklist_completed": checklist_completed,
            "checklist_total": checklist_total,
            "checklist_percent": int(round((checklist_completed / checklist_total) * 100)) if checklist_total else 0,
        },
        "owner_account": owner_account,
        "owner_label": _admin_property_owner_label(owner_account),
        "checklist_items": checklist_items,
        "service_requests": latest_service_requests,
        "timeline": timeline,
        "property_events": property_events,
        "calendar": calendar,
        "availability": availability,
        "service_request_count": len(property_service_requests),
        "activity_count": len(timeline),
    }


def _admin_operations_task_is_overdue(task_record):
    status = _normalize_operations_task_status((task_record or {}).get("status", "NEW"))
    if status in {"COMPLETED", "ARCHIVED"}:
        return False

    due_date = str((task_record or {}).get("due_date", "")).strip()
    if due_date:
        try:
            due_dt = datetime.fromisoformat(due_date)
        except ValueError:
            due_dt = None
        if due_dt and due_dt.date() < datetime.now(timezone.utc).date():
            return True

    request_record = _find_service_request((task_record or {}).get("request_id", ""))
    preferred_date = str((request_record or {}).get("preferred_date", "")).strip()
    if preferred_date:
        try:
            preferred_dt = datetime.fromisoformat(preferred_date)
        except ValueError:
            preferred_dt = None
        if preferred_dt and preferred_dt.date() < datetime.now(timezone.utc).date():
            return True

    created_at = _parse_iso_datetime(str((task_record or {}).get("created_at", "")).strip())
    if created_at and datetime.now(timezone.utc) - created_at > timedelta(days=3):
        return True
    return False


def _format_task_deadline_remaining(task_record):
    due_date = str((task_record or {}).get("due_date", "")).strip()
    if not due_date:
        return "No due date"

    due_dt = None
    try:
        due_dt = datetime.fromisoformat(due_date)
    except ValueError:
        try:
            due_dt = datetime.fromisoformat(f"{due_date}T23:59:59+00:00")
        except ValueError:
            due_dt = None

    if due_dt is None:
        return due_date

    if due_dt.tzinfo is None:
        due_dt = due_dt.replace(tzinfo=timezone.utc)

    remaining = due_dt - datetime.now(timezone.utc)
    if remaining.total_seconds() <= 0:
        return "Overdue"

    total_minutes = int(remaining.total_seconds() // 60)
    days, remainder_minutes = divmod(total_minutes, 60 * 24)
    hours, minutes = divmod(remainder_minutes, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if not parts:
        parts.append(f"{minutes}m")
    return " ".join(parts) + " remaining"


def _admin_operations_task_context(task_record):
    owner_account = _find_owner_account(task_record.get("owner_id", ""))
    property_record = _find_owner_property(task_record.get("property_id", "")) if task_record.get("property_id") else None
    professional_account = _find_professional_account(task_record.get("assigned_professional_id", ""))
    linked_reservation = None
    if str(task_record.get("source_type", "")).strip().upper() == "RESERVATION":
        linked_reservation = _find_reservation(task_record.get("source_id", "")) or _find_reservation(task_record.get("request_id", ""))
    checklist_items = task_record.get("checklist_items", _operations_task_checklist_items(task_record.get("checklist_json", "")))
    checklist_completed_count = sum(1 for item in checklist_items if item.get("checked"))
    checklist_total_count = len(checklist_items)
    checklist_percentage = int(round((checklist_completed_count / checklist_total_count) * 100)) if checklist_total_count else 0
    property_readiness_percent = None
    if property_record:
        readiness_completed, readiness_total = _owner_property_checklist_completion(property_record)
        if readiness_total:
            property_readiness_percent = int(round((readiness_completed / readiness_total) * 100))
    related_requests = []
    if property_record:
        related_requests = _admin_property_service_requests(property_record, owner_account)[:5]
    else:
        request_record = _find_service_request(task_record.get("request_id", ""))
        if request_record:
            related_requests = [request_record]

    timeline_events = _load_operations_task_events(task_record.get("request_id", ""))
    assignment_history = [
        event
        for event in timeline_events
        if str(event.get("event_type", "")).strip() in {"assigned", "status_changed", "completed", "workflow_transitioned", "professional_assigned", "professional_accepted", "professional_on_the_way", "professional_arrived", "professional_started", "professional_paused", "professional_resumed", "professional_completed", "professional_comment_added", "comment_added_internal", "attachment_added", "completion_report_updated"}
    ]
    assignable_professionals = [
        account
        for account in _load_professional_accounts()
        if _normalize_professional_account_status(account.get("status", "PENDING")) in {"APPROVED", "ACTIVE"}
    ]
    return {
        "task": {
            **task_record,
            "status_label": _operations_task_status_label(task_record.get("status", "NEW")),
            "status_tone": _operations_task_status_tone(task_record.get("status", "NEW")),
            "priority_label": _operations_task_priority_label(task_record.get("priority", "NORMAL")),
            "priority_tone": _operations_task_priority_tone(task_record.get("priority", "NORMAL")),
            "overdue": _admin_operations_task_is_overdue(task_record),
            "assigned_professional_label": _professional_account_display_label(professional_account) if professional_account else str(task_record.get("assigned_to", "")).strip(),
        },
        "owner_account": owner_account,
        "property_record": property_record,
        "property_readiness_percent": property_readiness_percent,
        "assigned_professional_account": professional_account,
        "linked_reservation": linked_reservation,
        "sla_time_remaining": _format_task_deadline_remaining(task_record),
        "related_requests": related_requests,
        "timeline": list(reversed(timeline_events)),
        "assignment_history": list(reversed(assignment_history)),
        "professional_accounts": assignable_professionals,
        "checklist_items": checklist_items,
        "checklist_completed_count": checklist_completed_count,
        "checklist_total_count": checklist_total_count,
        "checklist_percentage": checklist_percentage,
        "attachments": task_record.get("attachments", _operations_task_attachments(task_record.get("attachments_json", ""))),
        "comments": task_record.get("comments", _operations_task_comments(task_record.get("comments_json", ""))),
        "completion_report": task_record.get("completion_report", _operations_task_completion_report(task_record.get("completion_report_json", ""))),
    }


def _admin_operations_board_context():
    overdue_monitor = _run_operations_overdue_monitor()
    owner_accounts = _admin_property_owner_map()
    property_map = {str(property_record.get("id", "")).strip(): property_record for property_record in _load_owner_properties()}
    tasks = []
    for task_record in _load_operations_tasks():
        owner_account = owner_accounts.get(str(task_record.get("owner_id", "")).strip()) or _find_owner_account(task_record.get("owner_id", ""))
        property_record = property_map.get(str(task_record.get("property_id", "")).strip()) or _find_owner_property(task_record.get("property_id", ""))
        tasks.append({
            **task_record,
            "owner_label": _admin_property_owner_label(owner_account),
            "owner_name": owner_account.get("full_name", "") if owner_account else task_record.get("owner_name", ""),
            "owner_email": owner_account.get("email", "") if owner_account else task_record.get("owner_email", ""),
            "property_label": property_record.get("name", "") if property_record else task_record.get("property_name", "") or task_record.get("property_location", ""),
            "property_location": property_record.get("location", "") if property_record else task_record.get("property_location", ""),
            "property_type": property_record.get("property_type", "") if property_record else "",
            "assigned_professional_label": _professional_account_display_label(_find_professional_account(task_record.get("assigned_professional_id", ""))) if str(task_record.get("assigned_professional_id", "")).strip() else str(task_record.get("assigned_to", "")).strip(),
            "status_label": _operations_task_status_label(task_record.get("status", "NEW")),
            "status_tone": _operations_task_status_tone(task_record.get("status", "NEW")),
            "priority_label": _operations_task_priority_label(task_record.get("priority", "NORMAL")),
            "priority_tone": _operations_task_priority_tone(task_record.get("priority", "NORMAL")),
            "overdue": _admin_operations_task_is_overdue(task_record),
        })

    search_query = str(request.args.get("q", "")).strip()
    property_filter = str(request.args.get("property", "")).strip()
    owner_filter = str(request.args.get("owner", "")).strip()
    professional_filter = str(request.args.get("professional", "")).strip()
    category_filter = str(request.args.get("category", "")).strip()
    priority_filter = str(request.args.get("priority", "")).strip().upper()
    requested_status = str(request.args.get("status", "")).strip()
    status_filter = _normalize_operations_task_status(requested_status) if requested_status else ""
    date_filter = str(request.args.get("date", "")).strip()

    search_tokens = [token for token in search_query.lower().split() if token]
    filtered_tasks = []
    for task in tasks:
        searchable_text = " ".join(
            [
                task.get("title", ""),
                task.get("property_label", ""),
                task.get("owner_label", ""),
                task.get("owner_email", ""),
                task.get("category", ""),
                task.get("property_location", ""),
                task.get("assigned_to", ""),
            ]
        ).lower()
        if search_tokens and not all(token in searchable_text for token in search_tokens):
            continue
        if property_filter and _admin_property_query_value(task.get("property_label", "")) != _admin_property_query_value(property_filter):
            continue
        if owner_filter and _admin_property_query_value(task.get("owner_name", "")) != _admin_property_query_value(owner_filter) and _admin_property_query_value(task.get("owner_email", "")) != _admin_property_query_value(owner_filter):
            continue
        if professional_filter and _admin_property_query_value(task.get("assigned_to", "")) != _admin_property_query_value(professional_filter):
            continue
        if category_filter and _admin_property_query_value(task.get("category", "")) != _admin_property_query_value(category_filter):
            continue
        if priority_filter and _normalize_operations_task_priority(task.get("priority", "NORMAL")) != priority_filter:
            continue
        if status_filter and _normalize_operations_task_status(task.get("status", "NEW")) != status_filter:
            continue
        if date_filter:
            task_date_candidates = {
                str(task.get("created_at", "")).strip()[:10],
                str(task.get("due_date", "")).strip()[:10],
            }
            if date_filter not in task_date_candidates:
                continue
        filtered_tasks.append(task)

    columns = {status: [] for status in OPERATIONS_TASK_BOARD_STATUSES}
    for task in filtered_tasks:
        columns.setdefault(_normalize_operations_task_status(task.get("status", "NEW")), []).append(task)

    for status in columns:
        columns[status].sort(key=lambda item: (item.get("overdue", False), item.get("updated_at", ""), item.get("created_at", "")), reverse=True)

    open_tasks = sum(1 for task in tasks if _normalize_operations_task_status(task.get("status", "NEW")) in {"NEW", "ASSIGNED", "ACCEPTED", "ON_THE_WAY", "ARRIVED", "IN_PROGRESS", "PAUSED", "WAITING_OWNER", "WAITING_OPERATIONS"})
    assigned_tasks = sum(1 for task in tasks if _normalize_operations_task_status(task.get("status", "NEW")) == "ASSIGNED")
    in_progress_tasks = sum(1 for task in tasks if _normalize_operations_task_status(task.get("status", "NEW")) == "IN_PROGRESS")
    waiting_owner_tasks = sum(1 for task in tasks if _normalize_operations_task_status(task.get("status", "NEW")) == "WAITING_OWNER")
    waiting_provider_tasks = sum(1 for task in tasks if _normalize_operations_task_status(task.get("status", "NEW")) == "WAITING_OPERATIONS")
    completed_today = sum(1 for task in tasks if _normalize_operations_task_status(task.get("status", "NEW")) in {"COMPLETED", "ARCHIVED"} and str(task.get("completed_at", "")).strip()[:10] == datetime.now(timezone.utc).date().isoformat())
    overdue_tasks = sum(1 for task in tasks if _admin_operations_task_is_overdue(task))
    archived_tasks = sum(1 for task in tasks if _normalize_operations_task_status(task.get("status", "NEW")) == "ARCHIVED")

    property_options = sorted({task.get("property_label", "") for task in tasks if task.get("property_label", "")})
    owner_options = sorted({task.get("owner_name", "") for task in tasks if task.get("owner_name", "")})
    professional_options = sorted({task.get("assigned_to", "") for task in tasks if task.get("assigned_to", "")})
    category_options = sorted({task.get("category", "") for task in tasks if task.get("category", "")})
    priority_options = [("LOW", "Low"), ("NORMAL", "Normal"), ("HIGH", "High"), ("URGENT", "Urgent")]

    return {
        "tasks": filtered_tasks,
        "columns": columns,
        "counts": {
            "open_tasks": open_tasks,
            "assigned_tasks": assigned_tasks,
            "in_progress_tasks": in_progress_tasks,
            "waiting_owner_tasks": waiting_owner_tasks,
            "waiting_provider_tasks": waiting_provider_tasks,
            "completed_today": completed_today,
            "completed_tasks": completed_today,
            "overdue_tasks": overdue_tasks,
            "archived_tasks": archived_tasks,
        },
        "filters": {
            "search_query": search_query,
            "property_filter": property_filter,
            "owner_filter": owner_filter,
            "professional_filter": professional_filter,
            "category_filter": category_filter,
            "priority_filter": priority_filter,
            "status_filter": status_filter,
            "date_filter": date_filter,
        },
        "property_options": property_options,
        "owner_options": owner_options,
        "professional_options": professional_options,
        "category_options": category_options,
        "priority_options": priority_options,
        "status_options": [{"value": status, "label": _operations_task_status_label(status)} for status in OPERATIONS_TASK_BOARD_STATUSES],
        "overdue_monitor": overdue_monitor,
    }


def _admin_notifications_context():
    overdue_monitor = _run_operations_overdue_monitor()
    current_operator_key = _current_admin_operator_key()
    preferences = _load_operations_notification_preferences(current_operator_key, create_default=True)
    notifications = _load_operations_notifications(limit=100)
    return {
        "current_operator_key": current_operator_key,
        "preferences": preferences,
        "recent_alerts": notifications[:20],
        "overdue_alerts": [notification for notification in notifications if notification.get("event_type") == "overdue_detected"],
        "failed_notifications": [notification for notification in notifications if notification.get("event_type") == "notification_failed"],
        "overdue_monitor": overdue_monitor,
    }


def _admin_executive_alert_tone(severity):
    normalized = str(severity or "").strip().lower()
    return {
        "critical": "danger",
        "high": "danger",
        "medium": "warning",
        "low": "info",
        "info": "info",
    }.get(normalized, "neutral")


def _admin_executive_risk_band(score):
    normalized = max(0, min(100, int(score or 0)))
    if normalized <= 20:
        return {"label": "Excellent", "tone": "success"}
    if normalized <= 40:
        return {"label": "Normal", "tone": "neutral"}
    if normalized <= 60:
        return {"label": "Attention", "tone": "warning"}
    if normalized <= 80:
        return {"label": "High Risk", "tone": "danger"}
    return {"label": "Critical", "tone": "danger"}


def _admin_executive_timestamp_display(value):
    dt = value if isinstance(value, datetime) else _parse_iso_datetime(value)
    if not dt:
        return ""
    return dt.astimezone(timezone.utc).strftime("%d.%m.%Y · %H:%M UTC")


def _admin_executive_record_alert(*, severity, category, property_label="", reservation_label="", operation_label="", created_at=None, recommended_action="", detail="", link=""):
    alert_dt = created_at if isinstance(created_at, datetime) else _parse_iso_datetime(created_at) or datetime.now(timezone.utc)
    return {
        "severity": str(severity or "medium").strip().lower(),
        "category": str(category or "").strip(),
        "property": str(property_label or "").strip(),
        "reservation": str(reservation_label or "").strip(),
        "operation": str(operation_label or "").strip(),
        "created_at": alert_dt.astimezone(timezone.utc).isoformat(),
        "created_at_display": _admin_executive_timestamp_display(alert_dt),
        "recommended_action": str(recommended_action or "").strip(),
        "detail": str(detail or "").strip(),
        "link": str(link or "").strip(),
        "tone": _admin_executive_alert_tone(severity),
    }


def _admin_executive_record_timeline_event(*, timestamp, icon, event_type, property_label="", summary="", actor="", link="", tone="neutral"):
    event_dt = timestamp if isinstance(timestamp, datetime) else _parse_iso_datetime(timestamp) or datetime.now(timezone.utc)
    return {
        "timestamp": event_dt.astimezone(timezone.utc).isoformat(),
        "timestamp_display": _admin_executive_timestamp_display(event_dt),
        "icon": str(icon or "").strip(),
        "type": str(event_type or "").strip(),
        "property": str(property_label or "").strip(),
        "summary": str(summary or "").strip(),
        "actor": str(actor or "").strip(),
        "link": str(link or "").strip(),
        "tone": str(tone or "neutral").strip(),
    }


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


@app.get("/admin/properties")
@admin_required
def admin_properties():
    search_query = request.args.get("q", "").strip()
    requested_status = str(request.args.get("status", "")).strip().upper()
    status_filter = requested_status if requested_status in OWNER_PROPERTY_STATUS_VALUES else ""
    requested_property_type = str(request.args.get("property_type", "")).strip()
    property_type_filter = requested_property_type.lower()

    context = _admin_properties_list_context()
    search_tokens = [token for token in search_query.lower().split() if token]
    filtered_properties = []
    for property_record in context["properties"]:
        searchable_parts = [
            property_record.get("name", ""),
            property_record.get("owner_name", ""),
            property_record.get("owner_email", ""),
            property_record.get("location", ""),
            property_record.get("property_type", ""),
        ]
        searchable_text = " ".join(searchable_parts).lower()
        if search_tokens and not all(token in searchable_text for token in search_tokens):
            continue
        if status_filter and _normalize_owner_property_status(property_record.get("status", "")) != status_filter:
            continue
        if property_type_filter and _admin_property_query_value(property_record.get("property_type", "")) != property_type_filter:
            continue
        filtered_properties.append(property_record)

    return render_template(
        "admin_properties.html",
        properties=filtered_properties,
        properties_count=len(filtered_properties),
        properties_total_count=context["total_count"],
        total_properties=context["total_count"],
        active_properties=context["active_count"],
        seasonal_properties=context["seasonal_count"],
        inactive_properties=context["inactive_count"],
        search_query=search_query,
        status_filter=status_filter,
        property_type_filter=requested_property_type,
        status_options=context["status_options"],
        property_type_options=context["property_type_options"],
        property_tones={status: _owner_property_status_tone(status) for status in OWNER_PROPERTY_STATUS_VALUES},
    )


@app.route("/admin/properties/<property_id>", methods=["GET", "POST"])
@admin_required
def admin_property_detail(property_id):
    property_record = _find_owner_property(property_id)
    if not property_record:
        return Response("Property not found.", status=404, mimetype="text/plain")

    if request.method == "POST":
        previous_notes = str(property_record.get("admin_notes", "")).strip()
        new_notes = str(request.form.get("admin_notes", previous_notes)).strip()
        if new_notes != previous_notes:
            saved_property = _append_owner_property({
                **property_record,
                "admin_notes": new_notes,
            })
            if saved_property:
                _append_property_activity_event(
                    saved_property["id"],
                    saved_property.get("owner_id", ""),
                    "note_added",
                    "Note added",
                    new_notes,
                )
        return redirect(url_for("admin_property_detail", property_id=property_id))

    context = _admin_property_detail_context(property_record)
    return render_template(
        "admin_property_detail.html",
        **context,
    )


@app.route("/admin/calendar")
@admin_required
def admin_calendar():
    context = _build_calendar_page_context("admin")
    return render_template(
        "calendar.html",
        **context,
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


def _demo_manifest_default():
    return {
        "batch_id": DEMO_BATCH_ID,
        "scenario": f"{DEMO_SCENARIO} | {DEMO_SEASON}",
        "seed_date": "",
        "created_by": "demo_engine",
        "records": {
            "owner_accounts": [],
            "owner_properties": [],
            "reservations": [],
            "operations_tasks": [],
            "calendar_events": [],
            "professional_accounts": [],
            "owner_activity_events": [],
            "property_activity_events": [],
            "operations_task_events": [],
        },
    }


def _load_demo_manifest():
    if not DEMO_DATA_MANIFEST_PATH.exists():
        return None

    try:
        with DEMO_DATA_MANIFEST_PATH.open("r", encoding="utf-8") as f:
            manifest = json.load(f)
    except Exception:
        return None

    if not isinstance(manifest, dict):
        return None

    default_manifest = _demo_manifest_default()
    records = manifest.get("records") if isinstance(manifest.get("records"), dict) else {}
    default_manifest.update({
        "batch_id": str(manifest.get("batch_id", default_manifest["batch_id"])).strip() or default_manifest["batch_id"],
        "scenario": str(manifest.get("scenario", default_manifest["scenario"])).strip() or default_manifest["scenario"],
        "seed_date": str(manifest.get("seed_date", "")).strip(),
        "created_by": str(manifest.get("created_by", default_manifest["created_by"])).strip() or default_manifest["created_by"],
    })
    for key in default_manifest["records"]:
        value = records.get(key, [])
        default_manifest["records"][key] = value if isinstance(value, list) else []
    return default_manifest


def _save_demo_manifest(manifest):
    DEMO_DATA_MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with DEMO_DATA_MANIFEST_PATH.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
        f.write("\n")


def _clear_demo_manifest():
    if DEMO_DATA_MANIFEST_PATH.exists():
        try:
            DEMO_DATA_MANIFEST_PATH.unlink()
        except PermissionError:
            DEMO_DATA_MANIFEST_PATH.write_text("", encoding="utf-8")


def _demo_records(kind):
    manifest = _load_demo_manifest()
    if not manifest:
        return []
    records = manifest.get("records", {})
    value = records.get(kind, [])
    return list(value) if isinstance(value, list) else []


def _demo_record_index(kind):
    index = {}
    for record in _demo_records(kind):
        record_id = str(record.get("id", "")).strip()
        if record_id:
            index[record_id] = record
    return index


def _demo_owner_account_by_email(email):
    target = str(email or "").strip().lower()
    if not target:
        return None
    for record in _demo_records("owner_accounts"):
        if str(record.get("email", "")).strip().lower() == target:
            return record
    return None


def _demo_professional_account_by_email(email):
    target = str(email or "").strip().lower()
    if not target:
        return None
    for record in _demo_records("professional_accounts"):
        if str(record.get("email", "")).strip().lower() == target:
            return record
    return None


def _demo_reservation_by_id(reservation_id):
    target = str(reservation_id or "").strip()
    if not target:
        return None
    return _demo_record_index("reservations").get(target)


def _demo_property_by_id(property_id):
    target = str(property_id or "").strip()
    if not target:
        return None
    return _demo_record_index("owner_properties").get(target)


def _demo_operations_task_by_id(task_id):
    target = str(task_id or "").strip()
    if not target:
        return None
    for record in _demo_records("operations_tasks"):
        if target in {
            str(record.get("id", "")).strip(),
            str(record.get("request_id", "")).strip(),
            str(record.get("source_id", "")).strip(),
        }:
            return record
    return None


def _demo_professional_by_id(professional_id):
    target = str(professional_id or "").strip()
    if not target:
        return None
    return _demo_record_index("professional_accounts").get(target)


def _demo_manifest_summary():
    manifest = _load_demo_manifest() or _demo_manifest_default()
    records = manifest["records"]
    return {
        "batch_id": manifest.get("batch_id", DEMO_BATCH_ID),
        "scenario": manifest.get("scenario", f"{DEMO_SCENARIO} | {DEMO_SEASON}"),
        "seed_date": manifest.get("seed_date", ""),
        "record_counts": {key: len(value) for key, value in records.items()},
    }


def _demo_operation_event(task_id, created_at, event_type, title, detail="", status="NEW"):
    return {
        "id": f"demo-ops-event-{uuid4().hex}",
        "task_id": task_id,
        "created_at": created_at,
        "event_type": event_type,
        "title": title,
        "detail": detail,
        "status": _normalize_operations_task_status(status),
    }


def _demo_reservation_timeline(created_at, title, detail, status):
    return {
        "id": f"demo-res-event-{uuid4().hex}",
        "created_at": created_at,
        "event_type": "demo_activity",
        "title": title,
        "detail": detail,
        "status": _normalize_reservation_status(status),
        "visibility": "public",
    }


def _build_demo_data_manifest():
    batch_id = DEMO_BATCH_ID
    scenario = f"{DEMO_SCENARIO} | {DEMO_SEASON}"
    seed_dt = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    seed_iso = seed_dt.isoformat().replace("+00:00", "Z")

    owners = [
        {"id": "demo-owner-stella", "full_name": "Stella Stoyanova", "email": "stella.stoyanova@blackseaconnect.com", "phone": "+359888100001", "property_type": "Villa", "city": "Sveti Vlas", "property_name": "Marina Horizon", "number_of_units": 4, "notes": "Investor owner with premium seasonal villas."},
        {"id": "demo-owner-elena", "full_name": "Elena Petrova", "email": "elena.petrova@blackseaconnect.com", "phone": "+359888100002", "property_type": "Apartment", "city": "Sunny Beach", "property_name": "Sunrise Collection", "number_of_units": 3, "notes": "Mixed portfolio focused on short stays."},
        {"id": "demo-owner-ivan", "full_name": "Ivan Dimitrov", "email": "ivan.dimitrov@blackseaconnect.com", "phone": "+359888100003", "property_type": "Penthouse", "city": "Nessebar", "property_name": "Old Town Residences", "number_of_units": 2, "notes": "High-touch owner with frequent guest changeovers."},
        {"id": "demo-owner-michael", "full_name": "Michael Brown", "email": "michael.brown@blackseaconnect.com", "phone": "+359888100004", "property_type": "Studio", "city": "Varna", "property_name": "Coastal Studio Group", "number_of_units": 5, "notes": "International owner with direct web bookings."},
    ]
    owner_rows = []
    for index, owner in enumerate(owners, start=1):
        owner_rows.append({
            "id": owner["id"],
            "created_at": seed_iso,
            "full_name": owner["full_name"],
            "email": owner["email"],
            "phone": owner["phone"],
            "property_type": owner["property_type"],
            "city": owner["city"],
            "property_name": owner["property_name"],
            "number_of_units": owner["number_of_units"],
            "notes": owner["notes"],
            "status": "VIP" if index == 1 else "ACTIVE",
            "language": "en" if index == 4 else "bg",
            "last_login_at": "",
            "internal_notes": f"demo_batch_id={batch_id}; demo_scenario={scenario}; created_by=demo_engine",
            "demo_batch_id": batch_id,
            "is_demo": True,
            "demo_scenario": scenario,
            "created_by": "demo_engine",
        })

    property_specs = [
        ("Marina Pearl 1", "Luxury Apartment", "Sveti Vlas", 2, 2, 4, "year-round", "ACTIVE"),
        ("Marina Pearl Studio", "Studio", "Sveti Vlas", 1, 1, 2, "seasonal", "SEASONAL"),
        ("Sunset Bay Villa", "Villa", "Sunny Beach", 4, 3, 8, "seasonal", "ACTIVE"),
        ("Sunset Bay Penthouse", "Penthouse", "Sunny Beach", 3, 3, 6, "year-round", "ACTIVE"),
        ("Old Town Sea View", "Sea View Apartment", "Nessebar", 2, 2, 4, "seasonal", "ACTIVE"),
        ("Old Town Family Suite", "Family Apartment", "Nessebar", 3, 2, 6, "year-round", "ACTIVE"),
        ("Port Marina Residence", "Marina Apartment", "Burgas", 2, 2, 4, "seasonal", "SEASONAL"),
        ("Port Marina Studio", "Studio", "Burgas", 1, 1, 2, "year-round", "ACTIVE"),
        ("Golden Sands Villa", "Villa", "Varna", 5, 4, 10, "seasonal", "ACTIVE"),
        ("Golden Sands Loft", "Luxury Apartment", "Varna", 2, 2, 4, "year-round", "ACTIVE"),
        ("Blue Horizon Penthouse", "Penthouse", "Sozopol", 3, 2, 5, "seasonal", "ACTIVE"),
        ("Blue Horizon Family", "Family Apartment", "Sozopol", 3, 2, 6, "year-round", "ACTIVE"),
    ]
    property_rows = []
    for index, spec in enumerate(property_specs, start=1):
        owner = owners[(index - 1) % len(owners)]
        property_id = f"demo-property-{index:02d}"
        occupied = index % 3 == 0
        readiness_score = 74 + (index % 5) * 4
        next_arrival_dt = seed_dt + timedelta(days=(index % 6) - 1, hours=14 + (index % 3))
        next_departure_dt = next_arrival_dt + timedelta(days=3 + (index % 4))
        occupied_percent = 92 if occupied else 48 + (index % 4) * 10
        property_rows.append({
            "id": property_id,
            "owner_id": owner["id"],
            "created_at": (seed_dt - timedelta(days=index)).isoformat().replace("+00:00", "Z"),
            "name": spec[0],
            "property_type": spec[1],
            "location": spec[2],
            "bedrooms": spec[3],
            "bathrooms": spec[4],
            "guest_capacity": spec[5],
            "operating_mode": spec[6],
            "notes": f"{spec[0]} operational profile for summer pilot.",
            "status": spec[7],
            "guest_guide_ready": int(index % 2 == 0),
            "access_instructions_ready": 1,
            "emergency_contact_ready": int(index % 4 != 0),
            "cleaning_partner_ready": int(index % 3 != 0),
            "admin_notes": f"demo_batch_id={batch_id}; readiness={readiness_score}; created_by=demo_engine",
            "readiness": readiness_score,
            "health_score": min(98, readiness_score + (8 if occupied else 3)),
            "next_arrival": next_arrival_dt.isoformat().replace("+00:00", "Z"),
            "next_departure": next_departure_dt.isoformat().replace("+00:00", "Z"),
            "occupancy": occupied_percent,
            "owner": owner["full_name"],
            "demo_batch_id": batch_id,
            "is_demo": True,
            "demo_scenario": scenario,
            "created_by": "demo_engine",
        })

    reservation_sources = ["Airbnb", "Booking.com", "Vrbo", "Direct Website", "Manual", "iCal"]
    reservation_statuses = ["CONFIRMED", "CHECKED_IN", "CHECKED_OUT", "CANCELLED", "NO_SHOW", "PENDING"]
    reservation_rows = []
    reservation_events = []
    for index in range(40):
        property_record = property_rows[index % len(property_rows)]
        owner_record = next(owner for owner in owner_rows if owner["id"] == property_record["owner_id"])
        source = reservation_sources[index % len(reservation_sources)]
        status = reservation_statuses[index % len(reservation_statuses)]
        guest_first = ["Nadia", "Martin", "Daria", "Hristo", "Sofia", "Peter", "Kristina", "Daniel"][index % 8]
        guest_last = ["Ivanova", "Petrov", "Georgieva", "Brown", "Dimitrova", "Kolev", "Popova", "Smith"][index % 8]
        arrival_offset = -4 if index < 4 else 0 if index < 8 else 1 if index < 14 else 3 if index < 22 else 8 if index < 30 else 12
        stay_length = 2 + (index % 5)
        arrival_dt = seed_dt + timedelta(days=arrival_offset, hours=15 + (index % 3))
        departure_dt = arrival_dt + timedelta(days=stay_length)
        if index < 4:
            status = "CHECKED_IN"
        elif index < 8:
            status = "CONFIRMED"
        elif index < 14:
            status = "CONFIRMED"
        elif index < 22:
            status = "PENDING"
        elif index < 30:
            status = "CHECKED_OUT"
            arrival_dt = seed_dt - timedelta(days=stay_length + 1, hours=3)
            departure_dt = seed_dt - timedelta(days=1)
        elif index < 35:
            status = "CANCELLED" if index % 2 == 0 else "NO_SHOW"
            arrival_dt = seed_dt + timedelta(days=5 + (index % 4))
            departure_dt = arrival_dt + timedelta(days=stay_length)
        else:
            status = "CONFIRMED"
            arrival_dt = seed_dt + timedelta(days=10 + (index % 6))
            departure_dt = arrival_dt + timedelta(days=stay_length)

        guest_name = f"{guest_first} {guest_last}"
        reference = f"BSC-S26-{index + 1:04d}"
        timeline = [
            _demo_reservation_timeline((arrival_dt - timedelta(days=4)).isoformat().replace("+00:00", "Z"), "Reservation imported", f"{source} reservation received for {property_record['name']}", "PENDING"),
            _demo_reservation_timeline((arrival_dt - timedelta(days=3)).isoformat().replace("+00:00", "Z"), "Reservation confirmed", f"{guest_name} confirmed for {property_record['name']}", "CONFIRMED"),
            _demo_reservation_timeline((arrival_dt - timedelta(hours=10)).isoformat().replace("+00:00", "Z"), "Professional assigned", f"{owner_record['full_name']} ownership team notified", "CONFIRMED"),
            _demo_reservation_timeline(arrival_dt.isoformat().replace("+00:00", "Z"), "Guest checked in", f"{guest_name} arrived at {property_record['name']}", "CHECKED_IN"),
            _demo_reservation_timeline(departure_dt.isoformat().replace("+00:00", "Z"), "Guest checked out", f"{guest_name} departed {property_record['name']}", "CHECKED_OUT"),
        ]
        reservation_rows.append({
            "id": f"demo-reservation-{index + 1:03d}",
            "created_at": (arrival_dt - timedelta(days=7)).isoformat().replace("+00:00", "Z"),
            "updated_at": seed_iso,
            "property_id": property_record["id"],
            "reservation_source": source,
            "reservation_reference": reference,
            "channel_name": source,
            "channel_status": "SYNCED",
            "last_sync": seed_iso,
            "external_payload": {"reference": reference, "source": source, "demo_batch_id": batch_id, "is_demo": True, "demo_scenario": scenario, "created_by": "demo_engine"},
            "external_reference": reference,
            "external_last_sync": seed_iso,
            "import_batch_id": batch_id,
            "sync_status": "IDLE",
            "source_metadata_json": json.dumps({"demo_batch_id": batch_id, "is_demo": True, "demo_scenario": scenario, "created_by": "demo_engine"}, ensure_ascii=False),
            "source_metadata": {"demo_batch_id": batch_id, "is_demo": True, "demo_scenario": scenario, "created_by": "demo_engine"},
            "guest_first_name": guest_first,
            "guest_last_name": guest_last,
            "guest_email": f"{guest_first.lower()}.{guest_last.lower()}@example.com",
            "guest_phone": f"+35988{100000 + index:06d}",
            "adults": 2 + (index % 4),
            "children": index % 3,
            "infants": index % 2,
            "pets": 1 if index % 7 == 0 else 0,
            "arrival_datetime": arrival_dt.isoformat().replace("+00:00", "Z"),
            "departure_datetime": departure_dt.isoformat().replace("+00:00", "Z"),
            "status": status,
            "notes": f"Pilot reservation {reference} for {property_record['name']} via {source}.",
            "language": "en",
            "created_by": "demo_engine",
            "metadata_json": json.dumps({
                "demo_batch_id": batch_id,
                "is_demo": True,
                "demo_scenario": scenario,
                "created_by": "demo_engine",
                "timeline": timeline,
            }, ensure_ascii=False),
            "metadata": {
                "demo_batch_id": batch_id,
                "is_demo": True,
                "demo_scenario": scenario,
                "created_by": "demo_engine",
                "timeline": timeline,
            },
            "guest_name": guest_name,
            "property_name": property_record["name"],
            "property_location": property_record["location"],
            "owner_id": property_record["owner_id"],
            "owner_name": owner_record["full_name"],
            "owner_email": owner_record["email"],
            "channel_label": source,
            "timeline": timeline,
            "demo_batch_id": batch_id,
            "is_demo": True,
            "demo_scenario": scenario,
        })
        reservation_events.extend(timeline)

    professional_specs = [
        ("Cleaning", "Nadia Ivanova", "cleaning"),
        ("Cleaning", "Martin Petrov", "cleaning"),
        ("Maintenance", "Daria Georgieva", "maintenance"),
        ("Electrical", "Hristo Brown", "maintenance"),
        ("Plumbing", "Sofia Koleva", "maintenance"),
        ("Guest Relations", "Peter Popov", "guest relations"),
        ("Airport Transfer", "Kristina Smith", "transfer"),
        ("Laundry", "Daniel Ivanov", "laundry"),
        ("Photography", "Mila Petrova", "media"),
        ("Pool", "Victor Dimitrov", "pool"),
        ("Garden", "Elena Brown", "garden"),
        ("Cleaning", "Teodora Georgieva", "cleaning"),
        ("Maintenance", "Nikolay Petrov", "maintenance"),
        ("Guest Relations", "Iva Stoyanova", "guest relations"),
        ("Laundry", "Tanya Ivanova", "laundry"),
    ]
    professional_rows = []
    for index, (category, name, company_hint) in enumerate(professional_specs, start=1):
        email = f"{name.lower().replace(' ', '.')}@blackseaconnect.com"
        assigned_open_tasks = 4 + (index % 3)
        completed_tasks = 9 + (index % 5)
        professional_rows.append({
            "id": f"demo-professional-{index:02d}",
            "created_at": (seed_dt - timedelta(days=index + 3)).isoformat().replace("+00:00", "Z"),
            "full_name": name,
            "email": email,
            "phone": f"+35988{200000 + index:06d}",
            "company": f"{company_hint.title()} Crew {index}",
            "service_categories": category,
            "status": "ACTIVE",
            "last_login_at": (seed_dt - timedelta(hours=index)).isoformat().replace("+00:00", "Z"),
            "availability": "Weekdays 08:00-18:00" if index % 2 else "Daily 08:00-20:00",
            "assigned_operations": assigned_open_tasks,
            "completed_operations": completed_tasks,
            "rating": round(4.4 + ((index % 5) * 0.1), 1),
            "workload": f"{assigned_open_tasks}/{completed_tasks + assigned_open_tasks}",
            "demo_batch_id": batch_id,
            "is_demo": True,
            "demo_scenario": scenario,
            "created_by": "demo_engine",
        })

    categories = [
        "Arrival Cleaning",
        "Departure Cleaning",
        "Deep Cleaning",
        "Maintenance",
        "Check-in Preparation",
        "Checkout Inspection",
        "Guest Inspection",
        "Transfer",
        "Welcome Pack",
        "Pool Inspection",
        "Laundry",
        "Emergency Maintenance",
    ]
    operation_statuses = [
        "NEW",
        "ASSIGNED",
        "ACCEPTED",
        "IN_PROGRESS",
        "WAITING_OWNER",
        "WAITING_PROFESSIONAL",
        "COMPLETED",
        "OVERDUE",
    ]
    operations_rows = []
    operations_events = []
    for index in range(80):
        reservation = reservation_rows[index % len(reservation_rows)]
        property_record = property_rows[index % len(property_rows)]
        owner_record = next(owner for owner in owner_rows if owner["id"] == property_record["owner_id"])
        professional = professional_rows[index % len(professional_rows)]
        category = categories[index % len(categories)]
        status = operation_statuses[index % len(operation_statuses)]
        created_at = seed_dt - timedelta(days=2 + (index % 10), hours=index % 5)
        due_dt = seed_dt + timedelta(days=(index % 6) - 2, hours=9 + (index % 4))
        if index < 18:
            due_dt = seed_dt
        if index % 11 == 0:
            due_dt = seed_dt - timedelta(days=1)
            status = "OVERDUE"
        if index % 7 == 0:
            status = "WAITING_OWNER"
        elif index % 9 == 0:
            status = "WAITING_PROFESSIONAL"
        elif index % 5 == 0:
            status = "IN_PROGRESS"
        elif index % 4 == 0:
            status = "ASSIGNED"
        if index % 6 == 0:
            status = "COMPLETED"
        completed_at = (due_dt + timedelta(hours=2)).isoformat().replace("+00:00", "Z") if status in {"COMPLETED", "ARCHIVED"} else ""
        task_id = f"demo-task-{index + 1:03d}"
        title = f"{category} - {property_record['name']}"
        request_status = "completed" if status in {"COMPLETED", "ARCHIVED"} else "assigned" if status not in {"NEW", "WAITING_OWNER"} else "new"
        operations_rows.append({
            "id": task_id,
            "request_id": task_id,
            "source_type": "DEMO_ENGINE",
            "source_id": task_id,
            "created_at": created_at.isoformat().replace("+00:00", "Z"),
            "updated_at": seed_iso,
            "title": title,
            "category": category,
            "owner_name": owner_record["full_name"],
            "owner_email": owner_record["email"],
            "property_id": property_record["id"],
            "property_name": property_record["name"],
            "assigned_to": professional["full_name"] if status != "NEW" else "",
            "assigned_professional_id": professional["id"] if status != "NEW" else "",
            "priority": "HIGH" if status in {"OVERDUE", "WAITING_OWNER"} else "NORMAL",
            "status": status,
            "due_date": due_dt.isoformat().replace("+00:00", "Z"),
            "notes": f"{category} for {property_record['name']} managed through the demo engine.",
            "completed_at": completed_at,
            "completion_report_json": _operations_task_json_dumps(_operations_task_completion_report({"summary": f"{category} completed for {property_record['name']}"} if status in {"COMPLETED", "ARCHIVED"} else {})),
            "owner_id": owner_record["id"],
            "property_location": property_record["location"],
            "admin_notes": f"demo_batch_id={batch_id}; demo_scenario={scenario}; created_by=demo_engine",
            "request_status": request_status,
            "checklist_json": _operations_task_json_dumps([
                {"label": "Verify keys", "checked": True},
                {"label": "Confirm access", "checked": status in {"ASSIGNED", "ACCEPTED", "IN_PROGRESS", "COMPLETED", "WAITING_OWNER", "WAITING_PROFESSIONAL"}},
                {"label": "Close out task", "checked": status in {"COMPLETED", "ARCHIVED"}},
            ]),
            "attachments_json": _operations_task_json_dumps([]),
            "comments_json": _operations_task_json_dumps([
                {"author": "demo_engine", "created_at": seed_iso, "body": f"{category} tracked for {property_record['name']}."}
            ] if status in {"COMPLETED", "ARCHIVED"} else []),
            "demo_batch_id": batch_id,
            "is_demo": True,
            "demo_scenario": scenario,
            "created_by": "demo_engine",
        })
        operations_events.extend([
            _demo_operation_event(task_id, (created_at + timedelta(minutes=5)).isoformat().replace("+00:00", "Z"), "task_created", "Task created", property_record["name"], "NEW"),
            _demo_operation_event(task_id, (created_at + timedelta(minutes=25)).isoformat().replace("+00:00", "Z"), "assigned", "Professional assigned", professional["full_name"], "ASSIGNED"),
            _demo_operation_event(task_id, (due_dt - timedelta(minutes=45)).isoformat().replace("+00:00", "Z"), "started", "Work started", category, "IN_PROGRESS"),
            _demo_operation_event(task_id, (due_dt + timedelta(minutes=30)).isoformat().replace("+00:00", "Z"), "completed", "Work completed", property_record["name"], "COMPLETED"),
        ])

    calendar_rows = []
    calendar_events = []
    for index, reservation in enumerate(reservation_rows, start=1):
        start_dt = _parse_iso_datetime(reservation["arrival_datetime"]) or seed_dt
        end_dt = _parse_iso_datetime(reservation["departure_datetime"]) or (start_dt + timedelta(days=3))
        calendar_rows.append({
            "id": f"demo-calendar-reservation-{index:03d}",
            "created_at": (start_dt - timedelta(days=5)).isoformat().replace("+00:00", "Z"),
            "updated_at": seed_iso,
            "property_id": reservation["property_id"],
            "owner_id": reservation["owner_id"],
            "operation_task_id": "",
            "event_type": "Reservation",
            "title": reservation["guest_name"],
            "description": f"{reservation['reservation_source']} booking {reservation['reservation_reference']}",
            "start_datetime": reservation["arrival_datetime"],
            "end_datetime": reservation["departure_datetime"],
            "all_day": 0,
            "status": "SCHEDULED" if reservation["status"] in {"CONFIRMED", "PENDING"} else "COMPLETED" if reservation["status"] == "CHECKED_OUT" else "CANCELLED" if reservation["status"] in {"CANCELLED", "NO_SHOW"} else "IN_PROGRESS",
            "assigned_professional": "",
            "created_by": "demo_engine",
            "color": "arrival" if reservation["status"] in {"CONFIRMED", "CHECKED_IN"} else "neutral",
            "metadata_json": json.dumps({
                "demo_batch_id": batch_id,
                "is_demo": True,
                "demo_scenario": scenario,
                "created_by": "demo_engine",
                "reservation_id": reservation["id"],
                "kind": "reservation",
                "property_name": reservation["property_name"],
                "owner_id": reservation["owner_id"],
            }, ensure_ascii=False),
            "metadata": {
                "demo_batch_id": batch_id,
                "is_demo": True,
                "demo_scenario": scenario,
                "created_by": "demo_engine",
                "reservation_id": reservation["id"],
                "kind": "reservation",
                "property_name": reservation["property_name"],
                "owner_id": reservation["owner_id"],
            },
            "demo_batch_id": batch_id,
            "is_demo": True,
            "demo_scenario": scenario,
            "created_by": "demo_engine",
        })
        calendar_events.append({
            "id": f"demo-calendar-checkin-{index:03d}",
            "created_at": reservation["created_at"],
            "updated_at": seed_iso,
            "property_id": reservation["property_id"],
            "owner_id": reservation["owner_id"],
            "operation_task_id": "",
            "event_type": "Check-in" if reservation["status"] != "CHECKED_OUT" else "Check-out",
            "title": f"{reservation['guest_name']} arrival" if reservation["status"] != "CHECKED_OUT" else f"{reservation['guest_name']} departure",
            "description": reservation["reservation_reference"],
            "start_datetime": reservation["arrival_datetime"],
            "end_datetime": reservation["departure_datetime"],
            "all_day": 0,
            "status": "SCHEDULED",
            "assigned_professional": "",
            "created_by": "demo_engine",
            "color": "arrival",
            "metadata_json": json.dumps({
                "demo_batch_id": batch_id,
                "is_demo": True,
                "demo_scenario": scenario,
                "created_by": "demo_engine",
                "reservation_id": reservation["id"],
                "kind": "checkin",
            }, ensure_ascii=False),
            "metadata": {
                "demo_batch_id": batch_id,
                "is_demo": True,
                "demo_scenario": scenario,
                "created_by": "demo_engine",
                "reservation_id": reservation["id"],
                "kind": "checkin",
            },
            "demo_batch_id": batch_id,
            "is_demo": True,
            "demo_scenario": scenario,
            "created_by": "demo_engine",
        })

    for index, task in enumerate(operations_rows, start=1):
        due_dt = _parse_iso_datetime(task["due_date"]) or seed_dt
        calendar_events.append({
            "id": f"demo-calendar-task-{index:03d}",
            "created_at": task["created_at"],
            "updated_at": seed_iso,
            "property_id": task["property_id"],
            "owner_id": task["owner_id"],
            "operation_task_id": task["id"],
            "event_type": task["category"],
            "title": task["title"],
            "description": task["notes"],
            "start_datetime": task["due_date"],
            "end_datetime": (due_dt + timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
            "all_day": 0,
            "status": "SCHEDULED" if task["status"] not in {"COMPLETED", "ARCHIVED"} else "COMPLETED",
            "assigned_professional": task["assigned_to"],
            "created_by": "demo_engine",
            "color": _calendar_event_color(task["category"], task["status"]),
            "metadata_json": json.dumps({
                "demo_batch_id": batch_id,
                "is_demo": True,
                "demo_scenario": scenario,
                "created_by": "demo_engine",
                "task_id": task["id"],
                "kind": "operations_task",
                "property_name": task["property_name"],
                "property_location": task["property_location"],
                "priority": task["priority"],
            }, ensure_ascii=False),
            "metadata": {
                "demo_batch_id": batch_id,
                "is_demo": True,
                "demo_scenario": scenario,
                "created_by": "demo_engine",
                "task_id": task["id"],
                "kind": "operations_task",
                "property_name": task["property_name"],
                "property_location": task["property_location"],
                "priority": task["priority"],
            },
            "demo_batch_id": batch_id,
            "is_demo": True,
            "demo_scenario": scenario,
            "created_by": "demo_engine",
        })

    owner_activity_events = []
    property_activity_events = []
    for index, owner in enumerate(owner_rows, start=1):
        owner_activity_events.extend([
            {
                "id": f"demo-owner-activity-{index:03d}-1",
                "owner_id": owner["id"],
                "created_at": (seed_dt - timedelta(days=index)).isoformat().replace("+00:00", "Z"),
                "event_type": "owner_registered",
                "title": "Owner profile active",
                "detail": owner["full_name"],
                "demo_batch_id": batch_id,
                "is_demo": True,
                "demo_scenario": scenario,
                "created_by": "demo_engine",
            },
            {
                "id": f"demo-owner-activity-{index:03d}-2",
                "owner_id": owner["id"],
                "created_at": (seed_dt - timedelta(days=index - 1)).isoformat().replace("+00:00", "Z"),
                "event_type": "status_changed",
                "title": "Portfolio ready",
                "detail": owner["property_name"],
                "demo_batch_id": batch_id,
                "is_demo": True,
                "demo_scenario": scenario,
                "created_by": "demo_engine",
            },
        ])

    for index, property_record in enumerate(property_rows, start=1):
        property_activity_events.extend([
            {
                "id": f"demo-property-activity-{index:03d}-1",
                "property_id": property_record["id"],
                "owner_id": property_record["owner_id"],
                "created_at": (seed_dt - timedelta(days=index // 2)).isoformat().replace("+00:00", "Z"),
                "event_type": "property_created",
                "title": "Property added to pilot",
                "detail": property_record["name"],
                "demo_batch_id": batch_id,
                "is_demo": True,
                "demo_scenario": scenario,
                "created_by": "demo_engine",
            },
            {
                "id": f"demo-property-activity-{index:03d}-2",
                "property_id": property_record["id"],
                "owner_id": property_record["owner_id"],
                "created_at": (seed_dt - timedelta(hours=index * 3)).isoformat().replace("+00:00", "Z"),
                "event_type": "checklist_updated",
                "title": "Readiness checklist updated",
                "detail": f"Readiness {property_record['readiness']}%",
                "demo_batch_id": batch_id,
                "is_demo": True,
                "demo_scenario": scenario,
                "created_by": "demo_engine",
            },
        ])

    manifest = {
        "batch_id": batch_id,
        "scenario": scenario,
        "seed_date": seed_iso,
        "created_by": "demo_engine",
        "records": {
            "owner_accounts": owner_rows,
            "owner_properties": property_rows,
            "reservations": reservation_rows,
            "operations_tasks": operations_rows,
            "calendar_events": calendar_rows,
            "professional_accounts": professional_rows,
            "owner_activity_events": owner_activity_events,
            "property_activity_events": property_activity_events,
            "operations_task_events": operations_events,
        },
    }
    return manifest


def _seed_demo_data_manifest():
    manifest = _load_demo_manifest()
    if manifest:
        return manifest, False

    manifest = _build_demo_data_manifest()
    _save_demo_manifest(manifest)
    return manifest, True


def _clear_demo_data_manifest():
    existed = DEMO_DATA_MANIFEST_PATH.exists()
    _clear_demo_manifest()
    return existed


def _clean_payload_value(payload, *keys):
    for key in keys:
        value = payload.get(key, "")
        text = str(value).strip()
        if text:
            return text
    return ""


def _utc_now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _public_form_client_ip():
    forwarded_for = str(request.headers.get("X-Forwarded-For", "")).strip()
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip() or "unknown"
    remote_addr = str(request.remote_addr or "").strip()
    return remote_addr or "unknown"


def _public_form_rate_limit_key(form_name):
    return f"{str(form_name or '').strip().lower()}::{_public_form_client_ip()}"


def _public_form_rate_limited(form_name):
    now = datetime.now(timezone.utc).timestamp()
    cutoff = now - PUBLIC_FORM_RATE_LIMIT_WINDOW_SECONDS
    key = _public_form_rate_limit_key(form_name)
    timestamps = [timestamp for timestamp in _PUBLIC_FORM_RATE_LIMITS.get(key, []) if timestamp >= cutoff]
    if len(timestamps) >= PUBLIC_FORM_RATE_LIMIT_MAX_SUBMISSIONS:
        _PUBLIC_FORM_RATE_LIMITS[key] = timestamps
        return True

    timestamps.append(now)
    _PUBLIC_FORM_RATE_LIMITS[key] = timestamps
    return False


def _public_form_audit_event(form_name, event, reason):
    if not PUBLIC_FORM_AUDIT_EVENTS_PATH.exists():
        return None

    timestamp = _utc_now_iso()
    record = {
        "id": uuid4().hex,
        "created_at": timestamp,
        "timestamp": timestamp,
        "event": str(event or "").strip(),
        "form": str(form_name or "").strip(),
        "reason": str(reason or "").strip(),
        "ip_bucket": hashlib.sha256(_public_form_client_ip().encode("utf-8")).hexdigest()[:12],
        "path": request.path,
    }

    try:
        with PUBLIC_FORM_AUDIT_EVENTS_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as exc:
        app.logger.warning("Public form audit append failed for %s: %s", str(form_name or "").strip() or "unknown", type(exc).__name__)
        return None

    return record


_PUBLIC_FORM_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PUBLIC_FORM_URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
_PUBLIC_FORM_SCAM_RE = re.compile(
    r"(?i)\b("
    r"crypto|bitcoin|btc|usdt|wallet|seed phrase|wire transfer|bank transfer|transfer now|urgent payment|"
    r"gift card|investment|roi|trc20|binance|coinbase"
    r")\b"
)


def _public_form_has_valid_email(value):
    email_value = str(value or "").strip()
    if not email_value or len(email_value) > 254:
        return False

    parsed_name, parsed_email = parseaddr(email_value)
    candidate = parsed_email or email_value
    if parsed_name and parsed_email and parsed_name.strip() and parsed_name.strip() == candidate:
        candidate = parsed_email
    return bool(_PUBLIC_FORM_EMAIL_RE.match(candidate))


def _public_form_has_minimum_digits(value, minimum=6):
    return sum(1 for character in str(value or "") if character.isdigit()) >= minimum


def _public_form_has_plausible_name(value, minimum_chars=2):
    text = str(value or "").strip()
    if len(text) < minimum_chars:
        return False
    return any(character.isalpha() for character in text)


def _public_form_has_plausible_location(value):
    text = str(value or "").strip()
    if len(text) < 2:
        return False

    letters = sum(1 for character in text if character.isalpha())
    digits = sum(1 for character in text if character.isdigit())
    symbols = sum(1 for character in text if not character.isalnum() and not character.isspace())
    return letters >= 2 and digits <= 2 and symbols <= 4


def _public_form_text_is_spam(value):
    text = str(value or "").strip()
    if not text:
        return False

    url_count = len(_PUBLIC_FORM_URL_RE.findall(text))
    if url_count > 2:
        return True

    if "graf.org" in text.lower():
        return True

    if _PUBLIC_FORM_SCAM_RE.search(text):
        return True

    text_without_urls = _PUBLIC_FORM_URL_RE.sub(" ", text)
    compact_text = re.sub(r"\s+", "", text_without_urls)
    if len(compact_text) < 8:
        return True

    letters = sum(1 for character in compact_text if character.isalpha())
    if letters < 4:
        return True

    if compact_text and not any(character.isalpha() for character in compact_text):
        return True

    return False


def _public_form_honeypot_filled(value):
    return bool(str(value or "").strip())


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


def _normalize_professional_account_status(status):
    normalized = str(status or "").strip().upper()
    if normalized in {"PENDING", "APPROVED", "ACTIVE", "SUSPENDED"}:
        return normalized
    return "PENDING"


def _professional_account_status_from_application_status(status):
    normalized = _normalize_professional_status(status)
    if normalized == "converted":
        return "ACTIVE"
    if normalized == "qualified":
        return "APPROVED"
    if normalized in {"contacted", "new"}:
        return "PENDING"
    if normalized == "lost":
        return "SUSPENDED"
    return "PENDING"


def _professional_account_fallback_id(record):
    parts = [
        str(record.get("created_at", "")),
        str(record.get("email", "")),
        str(record.get("full_name", "")),
        str(record.get("company", "")),
    ]
    digest = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()
    return f"professional-account-{digest[:16]}"


def _normalize_professional_account(record):
    if not isinstance(record, dict):
        return None

    normalized = dict(record)
    normalized["id"] = str(normalized.get("id", "")).strip() or _professional_account_fallback_id(normalized)
    normalized["created_at"] = str(normalized.get("created_at", "")).strip()
    normalized["full_name"] = str(normalized.get("full_name", "")).strip()
    normalized["email"] = str(normalized.get("email", "")).strip()
    normalized["phone"] = str(normalized.get("phone", "")).strip()
    normalized["company"] = str(normalized.get("company", normalized.get("company_name", ""))).strip()
    service_categories = normalized.get("service_categories", normalized.get("professional_category", normalized.get("service_type", "")))
    if isinstance(service_categories, (list, tuple, set)):
        service_categories = ", ".join(str(item).strip() for item in service_categories if str(item).strip())
    normalized["service_categories"] = str(service_categories or "").strip()
    normalized["status"] = _normalize_professional_account_status(normalized.get("status", "PENDING"))
    normalized["last_login_at"] = str(normalized.get("last_login_at", "")).strip()
    return normalized


def _professional_account_from_row(row):
    return {
        "id": str(row["id"]),
        "created_at": str(row["created_at"]),
        "full_name": str(row["full_name"]),
        "email": str(row["email"]),
        "phone": str(row["phone"]),
        "company": str(row["company"]) if "company" in row.keys() else "",
        "service_categories": str(row["service_categories"]) if "service_categories" in row.keys() else "",
        "status": _normalize_professional_account_status(row["status"] if "status" in row.keys() else "PENDING"),
        "last_login_at": str(row["last_login_at"]) if "last_login_at" in row.keys() else "",
    }


def _sync_professional_accounts_from_applications(conn=None):
    if conn is None:
        return

    applications = _load_professional_applications()
    for record in applications:
        normalized = _normalize_professional_account({
            "id": record.get("id", ""),
            "created_at": record.get("created_at", ""),
            "full_name": record.get("full_name", ""),
            "email": record.get("email", ""),
            "phone": record.get("phone", ""),
            "company": record.get("company_name", record.get("company", "")),
            "service_categories": record.get("professional_category", record.get("service_type", "")),
            "status": _professional_account_status_from_application_status(record.get("status", "new")),
            "last_login_at": record.get("last_login_at", ""),
        })
        if not normalized or not normalized["email"]:
            continue
        conn.execute(
            """
            INSERT INTO professional_accounts (
                email, id, created_at, full_name, phone, company, service_categories, status, last_login_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(email) DO UPDATE SET
                id = excluded.id,
                created_at = excluded.created_at,
                full_name = excluded.full_name,
                phone = excluded.phone,
                company = excluded.company,
                service_categories = excluded.service_categories,
                status = excluded.status,
                last_login_at = excluded.last_login_at
            """,
            (
                normalized["email"],
                normalized["id"],
                normalized["created_at"],
                normalized["full_name"],
                normalized["phone"],
                normalized["company"],
                normalized["service_categories"],
                normalized["status"],
                normalized["last_login_at"],
            ),
        )


def _load_professional_accounts():
    with _owner_db_connection() as conn:
        _ensure_owner_db_schema(conn)
        _migrate_owner_jsonl_backups(conn)
        _sync_professional_accounts_from_applications(conn)
        rows = conn.execute(
            """
            SELECT email, id, created_at, full_name, phone, company, service_categories, status, last_login_at
            FROM professional_accounts
            ORDER BY created_at DESC, full_name ASC, email ASC
            """
        ).fetchall()

    accounts = [_professional_account_from_row(row) for row in rows]
    accounts.extend(_demo_records("professional_accounts"))
    accounts.sort(key=lambda item: (str(item.get("created_at", "")), str(item.get("full_name", "")), str(item.get("email", ""))), reverse=True)
    return accounts


def _find_professional_account_by_email(email):
    target_email = str(email or "").strip().lower()
    if not target_email:
        return None

    with _owner_db_connection() as conn:
        _ensure_owner_db_schema(conn)
        _migrate_owner_jsonl_backups(conn)
        _sync_professional_accounts_from_applications(conn)
        row = conn.execute(
            """
            SELECT email, id, created_at, full_name, phone, company, service_categories, status, last_login_at
            FROM professional_accounts
            WHERE email = ?
            LIMIT 1
            """,
            (target_email,),
        ).fetchone()

    if row:
        return _professional_account_from_row(row)
    return _demo_professional_account_by_email(target_email)


def _find_professional_account(professional_id):
    target_id = str(professional_id or "").strip()
    if not target_id:
        return None

    with _owner_db_connection() as conn:
        _ensure_owner_db_schema(conn)
        _migrate_owner_jsonl_backups(conn)
        _sync_professional_accounts_from_applications(conn)
        row = conn.execute(
            """
            SELECT email, id, created_at, full_name, phone, company, service_categories, status, last_login_at
            FROM professional_accounts
            WHERE id = ?
            LIMIT 1
            """,
            (target_id,),
        ).fetchone()

    if row:
        return _professional_account_from_row(row)
    return _demo_professional_by_id(target_id)


def _upsert_professional_account(account_record):
    normalized = _normalize_professional_account(account_record)
    if not normalized or not normalized["email"]:
        return None

    try:
        with _owner_db_connection() as conn:
            _ensure_owner_db_schema(conn)
            _migrate_owner_jsonl_backups(conn)
            conn.execute(
                """
                INSERT INTO professional_accounts (
                    email, id, created_at, full_name, phone, company, service_categories, status, last_login_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(email) DO UPDATE SET
                    id = excluded.id,
                    created_at = excluded.created_at,
                    full_name = excluded.full_name,
                    phone = excluded.phone,
                    company = excluded.company,
                    service_categories = excluded.service_categories,
                    status = excluded.status,
                    last_login_at = excluded.last_login_at
                """,
                (
                    normalized["email"],
                    normalized["id"],
                    normalized["created_at"],
                    normalized["full_name"],
                    normalized["phone"],
                    normalized["company"],
                    normalized["service_categories"],
                    normalized["status"],
                    normalized["last_login_at"],
                ),
            )
    except Exception as exc:
        app.logger.warning("Professional account upsert failed for %s: %s", _mask_email(normalized["email"]), type(exc).__name__)
        return None
    return _find_professional_account_by_email(normalized["email"])


def _professional_account_display_label(account_record):
    account = account_record or {}
    parts = [
        str(account.get("full_name", "")).strip(),
        str(account.get("company", "")).strip(),
    ]
    label = " / ".join(part for part in parts if part)
    return label or str(account.get("email", "")).strip() or "Professional"


def _professional_task_matches_account(task_record, professional_account):
    task = task_record or {}
    account = professional_account or {}
    target_id = str(account.get("id", "")).strip()
    if not target_id:
        return False
    return str(task.get("assigned_professional_id", "")).strip() == target_id


def _professional_tasks_for_account(professional_account):
    tasks = [task for task in _load_operations_tasks() if _professional_task_matches_account(task, professional_account)]
    tasks.sort(key=lambda item: (item.get("updated_at", ""), item.get("created_at", "")), reverse=True)
    return tasks


def _professional_task_assignment_events(task_id):
    return [
        event
        for event in _load_operations_task_events(task_id)
        if str(event.get("event_type", "")).strip() in {"assigned", "professional_assigned"}
    ]


def _professional_recent_notifications(professional_account, tasks):
    account = professional_account or {}
    recipient_email = str(account.get("email", "")).strip()
    task_ids = {str(task.get("id", "")).strip() for task in tasks if str(task.get("id", "")).strip()}
    notifications = []
    for notification in _load_operations_notifications(limit=50):
        if recipient_email and str(notification.get("recipient", "")).strip() == recipient_email:
            notifications.append(notification)
            continue
        if str(notification.get("task_id", "")).strip() in task_ids:
            notifications.append(notification)
    notifications.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return notifications[:6]


def _professional_average_completion_minutes(tasks):
    durations = []
    for task in tasks:
        if _normalize_operations_task_status(task.get("status", "NEW")) not in {"COMPLETED", "ARCHIVED"}:
            continue
        created_at = _parse_iso_datetime(str(task.get("created_at", "")).strip())
        completed_at = _parse_iso_datetime(str(task.get("completed_at", "")).strip())
        if not created_at or not completed_at or completed_at < created_at:
            continue
        durations.append(int((completed_at - created_at).total_seconds() / 60))
    if not durations:
        return None
    return int(round(sum(durations) / len(durations)))


def _professional_dashboard_context(professional_account):
    tasks = _professional_tasks_for_account(professional_account)
    today = datetime.now(timezone.utc).date()
    today_count = 0
    assigned_today_count = 0
    in_progress_count = 0
    waiting_owner_count = 0
    upcoming_tasks = []
    completed_tasks = []
    completion_today_count = 0
    professional_id = str((professional_account or {}).get("id", "")).strip()
    recent_notifications = _professional_recent_notifications(professional_account, tasks)
    average_completion_minutes = _professional_average_completion_minutes(tasks)
    for task in tasks:
        due_date = str(task.get("due_date", "")).strip()
        due_dt = None
        if due_date:
            try:
                due_dt = datetime.fromisoformat(due_date)
            except ValueError:
                due_dt = None
        status = _normalize_operations_task_status(task.get("status", "NEW"))
        if status in {"COMPLETED", "ARCHIVED"}:
            completed_tasks.append(task)
            if str(task.get("completed_at", "")).strip()[:10] == today.isoformat():
                completion_today_count += 1
            continue
        if due_dt and due_dt.date() == today:
            today_count += 1
        if due_dt and due_dt.date() > today:
            upcoming_tasks.append(task)
        if status in {"IN_PROGRESS", "PAUSED", "ARRIVED", "ON_THE_WAY"}:
            in_progress_count += 1
        if status == "WAITING_OWNER":
            waiting_owner_count += 1
        if professional_id and str(task.get("assigned_professional_id", "")).strip() == professional_id:
            if str(task.get("created_at", "")).strip()[:10] == today.isoformat():
                assigned_today_count += 1
                continue
            if any(str(event.get("created_at", "")).strip()[:10] == today.isoformat() for event in _professional_task_assignment_events(task.get("id", ""))):
                assigned_today_count += 1

    assigned_tasks = [task for task in tasks if _normalize_operations_task_status(task.get("status", "NEW")) not in {"COMPLETED", "ARCHIVED"}]
    return {
        "professional_account": professional_account,
        "assigned_tasks": assigned_tasks,
        "upcoming_tasks": upcoming_tasks,
        "completed_tasks": completed_tasks,
        "total_count": len(tasks),
        "assigned_count": len(assigned_tasks),
        "assigned_today_count": assigned_today_count,
        "today_count": today_count,
        "in_progress_count": in_progress_count,
        "waiting_owner_count": waiting_owner_count,
        "completed_today_count": completion_today_count,
        "upcoming_count": len(upcoming_tasks),
        "completed_count": len(completed_tasks),
        "average_completion_minutes": average_completion_minutes,
        "recent_notifications": recent_notifications,
        "display_name": _professional_account_display_label(professional_account),
    }


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
    owner_properties = _load_owner_properties()
    reservations = _load_reservations()
    operations_tasks = _load_operations_tasks()
    professional_accounts = _load_professional_accounts()
    calendar_events = _load_calendar_events()
    operations_notifications = _load_operations_notifications(limit=100)
    property_activity_events = _load_property_activity_events()
    owner_activity_events = _load_owner_activity_events()
    service_requests = _load_service_requests()
    pilot_counts = _pilot_status_counts(pilot_requests)
    partner_counts = _partner_application_status_counts(partner_applications)
    professional_counts = _professional_application_status_counts(professional_applications)
    service_request_counts = _service_request_status_counts(service_requests)
    property_map = {str(property_record.get("id", "")).strip(): property_record for property_record in owner_properties}
    owner_map = {str(account.get("id", "")).strip(): account for account in owner_accounts}
    task_map = {str(task.get("id", "")).strip(): task for task in operations_tasks}
    enriched_calendar_events = [_calendar_enrich_event(event, property_map, owner_map, task_map) for event in calendar_events]
    now = datetime.now(timezone.utc)
    current_month = datetime.now(timezone.utc).strftime("%Y-%m")
    today = datetime.now(timezone.utc).date()
    tomorrow = today + timedelta(days=1)
    week_end = today + timedelta(days=6)
    all_property_ids = [str(property_record.get("id", "")).strip() for property_record in owner_properties if str(property_record.get("id", "")).strip()]
    occupancy_engine = _reservation_occupancy_engine(reservations, property_ids=all_property_ids)
    requests_this_month = sum(1 for record in service_requests if str(record.get("created_at", "")).startswith(current_month))
    active_requests = sum(1 for record in service_requests if _normalize_service_request_status(record.get("status", "new")) in {"new", "assigned", "in_progress"})
    completed_requests = service_request_counts["completed"]
    property_status_counts = {status: 0 for status in OWNER_PROPERTY_STATUS_VALUES}
    property_status_cards = []
    property_health_scores = []
    occupied_today = 0
    available_today = 0
    upcoming_arrivals = 0
    upcoming_departures = 0
    reservations_this_month = 0
    for property_record in owner_properties:
        availability = _property_availability_engine(property_record, reservations=reservations, operations_tasks=operations_tasks)
        normalized_status = _normalize_owner_property_status(property_record.get("status", OWNER_PROPERTY_STATUS_DEFAULT))
        if normalized_status in property_status_counts:
            property_status_counts[normalized_status] += 1
        state = availability["state"]
        checklist_done, checklist_total = _owner_property_checklist_completion(property_record)
        checklist_ratio = checklist_done / max(checklist_total, 1)
        status_score_map = {
            "Occupied": 82,
            "Available": 90,
            "Preparing": 76,
            "Cleaning": 68,
            "Maintenance": 48,
            "Blocked": 35,
            "Ready": 96,
        }
        health_score = int(round(min(100, max(0, status_score_map.get(state, 72) + (checklist_ratio * 16) + (availability["occupancy_percent"] * 0.12)))))
        property_health_scores.append(health_score)
        property_status_cards.append({
            "id": property_record.get("id", ""),
            "name": property_record.get("name", "") or property_record.get("location", "") or property_record.get("id", ""),
            "location": property_record.get("location", ""),
            "state": state,
            "tone": _owner_property_status_tone(normalized_status),
            "health": health_score,
            "occupancy": availability["occupancy_percent"],
            "availability": availability["availability_percent"],
            "current_guest": availability.get("current_guest"),
            "next_arrival": availability.get("upcoming_arrival"),
            "next_departure": availability.get("upcoming_departure"),
            "cleaning_required": availability.get("cleaning_required", False),
            "maintenance_required": availability.get("maintenance_required", False),
            "preparation_required": availability.get("preparation_required", False),
            "checklist_done": checklist_done,
            "checklist_total": checklist_total,
        })

    reservation_groups = {"today": [], "tomorrow": [], "next_7_days": []}
    reservation_timeline_groups = [
        {"label": "Today", "items": []},
        {"label": "Tomorrow", "items": []},
        {"label": "Next 7 days", "items": []},
    ]
    reservation_timeline_items = []
    for reservation in reservations:
        arrival_dt, departure_dt = _reservation_date_bounds(reservation)
        if arrival_dt and today <= arrival_dt.date() <= week_end:
            if arrival_dt.date() == today:
                bucket = "today"
            elif arrival_dt.date() == tomorrow:
                bucket = "tomorrow"
            else:
                bucket = "next_7_days"
            reservation_groups[bucket].append(reservation)
            reservations_this_month += 1 if arrival_dt.strftime("%Y-%m") == current_month else 0
            upcoming_arrivals += 1 if arrival_dt.date() >= today else 0
        if departure_dt and departure_dt.date() >= today:
            upcoming_departures += 1
        if arrival_dt and arrival_dt.date() == today:
            occupied_today += 1 if _normalize_reservation_status(reservation.get("status", "PENDING")) in {"CONFIRMED", "CHECKED_IN"} else 0
        if not arrival_dt or not departure_dt:
            continue
        if arrival_dt.date() > today and _normalize_reservation_status(reservation.get("status", "PENDING")) in {"PENDING", "CONFIRMED", "CHECKED_IN"}:
            available_today += 1
        if arrival_dt.strftime("%Y-%m") == current_month:
            reservations_this_month += 0
        if arrival_dt.date() == today and _normalize_reservation_status(reservation.get("status", "PENDING")) in {"PENDING", "CONFIRMED", "CHECKED_IN"}:
            available_today += 0

        bucket = "today" if arrival_dt.date() == today else "tomorrow" if arrival_dt.date() == tomorrow else "next_7_days" if arrival_dt.date() <= week_end else ""
        if bucket:
            reservation_timeline_items.append({
                "bucket": bucket,
                "property": reservation.get("property_name", "") or reservation.get("property_label", "") or reservation.get("property_id", ""),
                "guest": reservation.get("guest_label", "") or reservation.get("guest_name", "") or "Guest",
                "arrival": arrival_dt,
                "departure": departure_dt,
                "status": _reservation_status_label(reservation.get("status", "PENDING")),
                "status_tone": _reservation_status_tone(reservation.get("status", "PENDING")),
                "channel": reservation.get("channel_name", "") or reservation.get("reservation_source", "Manual"),
            })

    for reservation_item in sorted(reservation_timeline_items, key=lambda item: (item["arrival"], item["departure"], item["property"], item["guest"])):
        reservation_timeline_groups[0 if reservation_item["bucket"] == "today" else 1 if reservation_item["bucket"] == "tomorrow" else 2]["items"].append({
            **reservation_item,
            "arrival_display": reservation_item["arrival"].astimezone(timezone.utc).strftime("%d.%m · %H:%M UTC"),
            "departure_display": reservation_item["departure"].astimezone(timezone.utc).strftime("%d.%m · %H:%M UTC"),
        })

    operations_events = []
    for event in enriched_calendar_events:
        start_dt = _parse_iso_datetime(event.get("start_datetime", ""))
        if not start_dt or start_dt.date() != today:
            continue
        category = _normalize_calendar_event_type(event.get("event_type", ""))
        if category not in {"Cleaning", "Check-in", "Check-out", "Inspection", "Maintenance", "Arrival", "Departure"}:
            continue
        operations_events.append({
            "time": start_dt,
            "time_label": start_dt.astimezone(timezone.utc).strftime("%H:%M"),
            "category": category,
            "title": event.get("title", "") or category,
            "detail": event.get("property_label", "") or event.get("owner_label", ""),
            "status": _normalize_calendar_event_status(event.get("status", "")),
            "tone": event.get("color", "") or "neutral",
            "property": event.get("property_label", ""),
            "owner": event.get("owner_label", ""),
        })
    for reservation in reservations:
        arrival_dt, departure_dt = _reservation_date_bounds(reservation)
        if arrival_dt and arrival_dt.date() == today:
            operations_events.append({
                "time": arrival_dt,
                "time_label": arrival_dt.astimezone(timezone.utc).strftime("%H:%M"),
                "category": "Check-in",
                "title": reservation.get("guest_label", "") or "Check-in",
                "detail": reservation.get("property_name", ""),
                "status": _reservation_status_label(reservation.get("status", "PENDING")),
                "tone": "arrival",
                "property": reservation.get("property_name", ""),
                "owner": reservation.get("owner_name", ""),
            })
        if departure_dt and departure_dt.date() == today:
            operations_events.append({
                "time": departure_dt,
                "time_label": departure_dt.astimezone(timezone.utc).strftime("%H:%M"),
                "category": "Check-out",
                "title": reservation.get("guest_label", "") or "Check-out",
                "detail": reservation.get("property_name", ""),
                "status": _reservation_status_label(reservation.get("status", "PENDING")),
                "tone": "departure",
                "property": reservation.get("property_name", ""),
                "owner": reservation.get("owner_name", ""),
            })

    operations_events.sort(key=lambda item: (item["time"], item["category"], item["property"], item["title"]))
    today_operations_groups = []
    current_time_label = None
    current_group = None
    for item in operations_events:
        if item["time_label"] != current_time_label:
            current_group = {"label": item["time_label"], "items": []}
            today_operations_groups.append(current_group)
            current_time_label = item["time_label"]
        current_group["items"].append(item)

    heatmap_counts = {}
    for event in enriched_calendar_events:
        start_dt = _parse_iso_datetime(event.get("start_datetime", ""))
        if not start_dt:
            continue
        day = start_dt.date()
        if today <= day <= week_end:
            heatmap_counts[day.isoformat()] = heatmap_counts.get(day.isoformat(), 0) + 1
    for task in operations_tasks:
        due_dt = _parse_iso_datetime(str(task.get("due_date", "")).strip())
        if due_dt and today <= due_dt.date() <= week_end:
            heatmap_counts[due_dt.date().isoformat()] = heatmap_counts.get(due_dt.date().isoformat(), 0) + 1

    operations_heatmap = []
    max_heat = max(heatmap_counts.values(), default=1)
    for offset in range(7):
        day = today + timedelta(days=offset)
        count = heatmap_counts.get(day.isoformat(), 0)
        operations_heatmap.append({
            "label": day.strftime("%A"),
            "short_label": day.strftime("%a"),
            "count": count,
            "width": max(12, int(round((count / max_heat) * 100))) if count else 12,
            "tone": "success" if count >= max_heat * 0.75 and count else "warning" if count else "muted",
        })

    open_operations = [
        task for task in operations_tasks
        if _normalize_operations_task_status(task.get("status", "NEW")) in {"NEW", "ASSIGNED", "ACCEPTED", "ON_THE_WAY", "ARRIVED", "IN_PROGRESS", "PAUSED", "WAITING_OWNER", "WAITING_OPERATIONS"}
    ]
    waiting_owner = [task for task in open_operations if _normalize_operations_task_status(task.get("status", "NEW")) == "WAITING_OWNER"]
    waiting_professional = [
        task for task in open_operations
        if _normalize_operations_task_status(task.get("status", "NEW")) in {"ASSIGNED", "ACCEPTED", "ON_THE_WAY", "ARRIVED", "IN_PROGRESS"} and str(task.get("assigned_professional_id", "")).strip()
    ]
    waiting_operations = [task for task in open_operations if _normalize_operations_task_status(task.get("status", "NEW")) == "WAITING_OPERATIONS"]
    completed_today = [
        task for task in operations_tasks
        if _normalize_operations_task_status(task.get("status", "NEW")) in {"COMPLETED", "ARCHIVED"}
        and str(task.get("completed_at", "")).strip()[:10] == today.isoformat()
    ]
    overdue_operations = [
        task for task in open_operations
        if str(task.get("due_date", "")).strip()[:10] and str(task.get("due_date", "")).strip()[:10] < today.isoformat()
    ]
    completion_minutes = []
    on_time_completed = 0
    completed_with_due = 0
    open_incidents = 0
    for task in operations_tasks:
        category_text = " ".join([
            str(task.get("category", "")),
            str(task.get("title", "")),
            str(task.get("notes", "")),
            str(task.get("admin_notes", "")),
        ]).lower()
        if any(marker in category_text for marker in ("incident", "issue", "problem", "emergency", "maintenance", "blocked")) and _normalize_operations_task_status(task.get("status", "NEW")) not in {"COMPLETED", "ARCHIVED"}:
            open_incidents += 1
        created_at = _parse_iso_datetime(task.get("created_at", ""))
        completed_at = _parse_iso_datetime(task.get("completed_at", ""))
        due_dt = _parse_iso_datetime(task.get("due_date", ""))
        if created_at and created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        if completed_at and completed_at.tzinfo is None:
            completed_at = completed_at.replace(tzinfo=timezone.utc)
        if due_dt and due_dt.tzinfo is None:
            due_dt = due_dt.replace(tzinfo=timezone.utc)
        if _normalize_operations_task_status(task.get("status", "NEW")) in {"COMPLETED", "ARCHIVED"} and created_at and completed_at and completed_at >= created_at:
            completion_minutes.append(int((completed_at - created_at).total_seconds() / 60))
        if completed_at and due_dt:
            completed_with_due += 1
            if completed_at <= due_dt:
                on_time_completed += 1
    average_completion_time = int(round(sum(completion_minutes) / len(completion_minutes))) if completion_minutes else None
    sla_health = int(round((on_time_completed / max(completed_with_due, 1)) * 100)) if completed_with_due else max(0, 100 - (len(overdue_operations) * 8))
    sla_health = max(0, min(100, sla_health))

    active_professionals = [professional for professional in professional_accounts if _normalize_professional_account_status(professional.get("status", "PENDING")) in {"ACTIVE", "APPROVED"}]
    busy_professional_ids = {
        str(task.get("assigned_professional_id", "")).strip()
        for task in open_operations
        if str(task.get("assigned_professional_id", "")).strip()
    }
    assigned_professionals = [professional for professional in active_professionals if str(professional.get("id", "")).strip() in busy_professional_ids]
    available_professionals = [professional for professional in active_professionals if str(professional.get("id", "")).strip() not in busy_professional_ids]
    assigned_today_tasks = [
        task for task in operations_tasks
        if str(task.get("assigned_professional_id", "")).strip()
        and str(task.get("created_at", "")).strip()[:10] == today.isoformat()
    ]
    completed_today_tasks = [
        task for task in operations_tasks
        if _normalize_operations_task_status(task.get("status", "NEW")) in {"COMPLETED", "ARCHIVED"}
        and str(task.get("completed_at", "")).strip()[:10] == today.isoformat()
    ]
    average_workload = round(len(open_operations) / max(len(active_professionals), 1), 1)

    operations_summary = {
        "late_operations": len(overdue_operations),
        "waiting_owner": len(waiting_owner),
        "waiting_professional": len(waiting_professional),
        "waiting_operations": len(waiting_operations),
        "completed_today": len(completed_today),
        "average_completion_time": _format_owner_portal_duration(average_completion_time) if average_completion_time is not None else "Pending",
        "open_incidents": open_incidents,
    }

    professional_summary = {
        "assigned_today": len(assigned_today_tasks),
        "completed_today": len(completed_today_tasks),
        "available": len(available_professionals),
        "busy": len(assigned_professionals),
        "average_workload": f"{average_workload:.1f} tasks/professional",
    }

    executive_kpis = [
        {"icon": "properties", "title": "Properties", "value": len(owner_properties), "trend": f"{property_status_counts.get('ACTIVE', 0)} active in scope", "tone": "neutral"},
        {"icon": "occupied", "title": "Occupied Today", "value": sum(1 for reservation in reservations if _reservation_is_occupying(reservation, today)), "trend": "Properties currently hosting guests", "tone": "success"},
        {"icon": "available", "title": "Available Today", "value": sum(1 for property_record in owner_properties if _property_availability_engine(property_record, reservations=reservations, operations_tasks=operations_tasks)["state"] in {"Available", "Ready"}), "trend": "Ready for assignment", "tone": "success"},
        {"icon": "arrivals", "title": "Upcoming Arrivals", "value": sum(1 for reservation in reservations if (arrival_dt := _reservation_date_bounds(reservation)[0]) and today <= arrival_dt.date() <= week_end), "trend": "Next 7 days", "tone": "info"},
        {"icon": "departures", "title": "Upcoming Departures", "value": sum(1 for reservation in reservations if (departure_dt := _reservation_date_bounds(reservation)[1]) and today <= departure_dt.date() <= week_end), "trend": "Next 7 days", "tone": "info"},
        {"icon": "bookings", "title": "Reservations This Month", "value": sum(1 for reservation in reservations if (arrival_dt := _reservation_date_bounds(reservation)[0]) and arrival_dt.strftime("%Y-%m") == current_month), "trend": "Arrival date basis", "tone": "neutral"},
        {"icon": "operations", "title": "Operations Open", "value": len(open_operations), "trend": f"{len(overdue_operations)} overdue", "tone": "warning"},
        {"icon": "waiting", "title": "Operations Waiting", "value": len(waiting_owner) + len(waiting_professional) + len(waiting_operations), "trend": "Owner + professional + operations", "tone": "warning"},
        {"icon": "overdue", "title": "Operations Overdue", "value": len(overdue_operations), "trend": "Past due date", "tone": "danger"},
        {"icon": "professionals", "title": "Professionals Assigned", "value": len(assigned_professionals), "trend": "Busy on open tasks", "tone": "info"},
        {"icon": "professionals", "title": "Professionals Available", "value": len(available_professionals), "trend": "Active and free", "tone": "success"},
        {"icon": "occupancy", "title": "Average Occupancy %", "value": occupancy_engine["occupancy_percent"], "trend": f"{occupancy_engine['available_days']} available days", "tone": "success" if occupancy_engine["occupancy_percent"] >= 75 else "warning"},
        {"icon": "health", "title": "Property Health Average", "value": int(round(sum(property_health_scores) / max(len(property_health_scores), 1))) if property_health_scores else 0, "trend": "Readiness and status blend", "tone": "info"},
        {"icon": "revenue", "title": "Revenue", "value": "Pending", "trend": "Channel sync placeholder", "tone": "neutral"},
        {"icon": "sla", "title": "SLA Health", "value": f"{sla_health}%", "trend": "On-time completion rate", "tone": "success" if sla_health >= 85 else "warning" if sla_health >= 60 else "danger"},
    ]

    unified_activity = []
    for reservation in reservations:
        for event in _reservation_timeline_events(reservation)[-3:]:
            parsed_at = _parse_iso_datetime(event.get("created_at", ""))
            if not parsed_at:
                continue
            unified_activity.append({
                "source": "reservation",
                "created_at": parsed_at,
                "title": event.get("title", "") or "Reservation event",
                "detail": event.get("detail", "") or reservation.get("property_name", ""),
                "tone": "arrival" if "check-in" in str(event.get("title", "")).lower() else "departure" if "check-out" in str(event.get("title", "")).lower() else "neutral",
            })

    for notification in operations_notifications[:20]:
        parsed_at = _parse_iso_datetime(notification.get("created_at", ""))
        if not parsed_at:
            continue
        unified_activity.append({
            "source": "operation",
            "created_at": parsed_at,
            "title": notification.get("title", "") or notification.get("event_type", "").replace("_", " ").title(),
            "detail": notification.get("detail", "") or notification.get("channel", ""),
            "tone": "danger" if notification.get("status") == "failed" else "success" if notification.get("status") == "sent" else "warning",
        })

    for event in enriched_calendar_events[:30]:
        parsed_at = _parse_iso_datetime(event.get("start_datetime", "")) or _parse_iso_datetime(event.get("created_at", ""))
        if not parsed_at:
            continue
        unified_activity.append({
            "source": "calendar",
            "created_at": parsed_at,
            "title": event.get("title", "") or event.get("event_type", "Calendar event"),
            "detail": event.get("property_label", "") or event.get("owner_label", ""),
            "tone": "info" if not event.get("is_overdue") else "warning",
        })

    for event in owner_activity_events[:20]:
        parsed_at = _parse_iso_datetime(event.get("created_at", ""))
        if not parsed_at:
            continue
        unified_activity.append({
            "source": "owner",
            "created_at": parsed_at,
            "title": event.get("title", "") or "Owner activity",
            "detail": event.get("detail", ""),
            "tone": "info",
        })

    for event in property_activity_events[:20]:
        parsed_at = _parse_iso_datetime(event.get("created_at", ""))
        if not parsed_at:
            continue
        unified_activity.append({
            "source": "property",
            "created_at": parsed_at,
            "title": event.get("title", "") or "Property activity",
            "detail": event.get("detail", ""),
            "tone": "neutral",
        })

    for record in professional_applications[:20]:
        for event in _professional_application_timeline_events(record)[-3:]:
            parsed_at = _parse_iso_datetime(event.get("created_at", ""))
            if not parsed_at:
                continue
            unified_activity.append({
                "source": "professional",
                "created_at": parsed_at,
                "title": event.get("title", "") or "Professional activity",
                "detail": event.get("detail", "") or record.get("city", ""),
                "tone": "success" if _normalize_professional_status(record.get("status")) == "converted" else "warning",
            })

    unified_activity.sort(key=lambda item: item["created_at"], reverse=True)
    recent_activity = [
        {
            "type": item["source"],
            "created_at": item["created_at"].astimezone(timezone.utc).strftime("%d.%m.%Y · %H:%M UTC"),
            "title": item["title"],
            "detail": item["detail"],
            "status": item["tone"],
        }
        for item in unified_activity[:12]
    ]

    overload_threshold_raw = os.getenv("EXECUTIVE_OVERLOAD_THRESHOLD", "5")
    try:
        overload_threshold = max(1, int(overload_threshold_raw))
    except ValueError:
        overload_threshold = 5

    open_task_statuses = {"NEW", "ASSIGNED", "ACCEPTED", "ON_THE_WAY", "ARRIVED", "IN_PROGRESS", "PAUSED", "WAITING_OWNER", "WAITING_OPERATIONS"}
    completed_task_statuses = {"COMPLETED", "ARCHIVED"}
    property_tasks_map = {}
    property_reservations_map = {}
    property_calendar_map = {}
    professional_task_counts = {}
    professional_labels = {}
    workload_by_city = {}
    workload_by_day = {}
    workload_by_category = {}
    workload_by_property = {}

    for task in operations_tasks:
        status = _normalize_operations_task_status(task.get("status", "NEW"))
        property_id = str(task.get("property_id", "")).strip()
        property_label = property_map.get(property_id, {}).get("name", "") or str(task.get("property_name", "")).strip() or str(task.get("property_location", "")).strip() or property_id or "Unknown property"
        property_location = property_map.get(property_id, {}).get("location", "") or str(task.get("property_location", "")).strip() or "Unknown city"
        assigned_professional_id = str(task.get("assigned_professional_id", "")).strip()
        assigned_professional_label = str(task.get("assigned_to", "")).strip() or assigned_professional_id or "Unassigned"
        if assigned_professional_id:
            professional_account = _find_professional_account(assigned_professional_id)
            if professional_account:
                assigned_professional_label = _professional_account_display_label(professional_account)
                professional_labels[assigned_professional_id] = assigned_professional_label
        property_tasks_map.setdefault(property_id, []).append(task)
        if property_id:
            workload_by_property[property_label] = workload_by_property.get(property_label, 0) + (1 if status in open_task_statuses else 0)
        if status in open_task_statuses:
            workload_by_city[property_location] = workload_by_city.get(property_location, 0) + 1
            workload_by_category[str(task.get("category", "")).strip() or "Uncategorised"] = workload_by_category.get(str(task.get("category", "")).strip() or "Uncategorised", 0) + 1
            due_dt = _parse_iso_datetime(str(task.get("due_date", "")).strip())
            if due_dt:
                workload_by_day[due_dt.date().isoformat()] = workload_by_day.get(due_dt.date().isoformat(), 0) + 1
            if assigned_professional_id:
                professional_task_counts[assigned_professional_id] = professional_task_counts.get(assigned_professional_id, 0) + 1
            else:
                professional_task_counts[assigned_professional_label] = professional_task_counts.get(assigned_professional_label, 0) + 1

    for reservation in reservations:
        property_id = str(reservation.get("property_id", "")).strip()
        if property_id:
            property_reservations_map.setdefault(property_id, []).append(reservation)

    for event in enriched_calendar_events:
        property_id = str(event.get("property_id", "")).strip()
        if property_id:
            property_calendar_map.setdefault(property_id, []).append(event)

    professional_task_cards = []
    for professional_account in active_professionals:
        professional_id = str(professional_account.get("id", "")).strip()
        professional_name = _professional_account_display_label(professional_account)
        task_count = professional_task_counts.get(professional_id, 0)
        professional_task_cards.append({
            "id": professional_id,
            "name": professional_name,
            "email": professional_account.get("email", ""),
            "company": professional_account.get("company", ""),
            "count": task_count,
            "tone": "danger" if task_count > overload_threshold else "warning" if task_count == overload_threshold else "info",
        })
    for label, task_count in professional_task_counts.items():
        if label in professional_labels:
            continue
        professional_task_cards.append({
            "id": label,
            "name": label,
            "email": "",
            "company": "",
            "count": task_count,
            "tone": "danger" if task_count > overload_threshold else "warning" if task_count == overload_threshold else "info",
        })
    professional_task_cards.sort(key=lambda item: (item["count"], item["name"]), reverse=True)

    workload_distribution = {
        "top_professionals": professional_task_cards[:5],
        "top_properties": [
            {"name": name, "count": count}
            for name, count in sorted(workload_by_property.items(), key=lambda item: (item[1], item[0]), reverse=True)[:5]
        ],
        "by_city": [
            {"name": name, "count": count}
            for name, count in sorted(workload_by_city.items(), key=lambda item: (item[1], item[0]), reverse=True)[:5]
        ],
        "by_day": [
            {
                "date": day.isoformat(),
                "label": day.strftime("%a"),
                "count": workload_by_day.get(day.isoformat(), 0),
            }
            for day in [today + timedelta(days=offset) for offset in range(7)]
        ],
        "by_category": [
            {"name": name, "count": count}
            for name, count in sorted(workload_by_category.items(), key=lambda item: (item[1], item[0]), reverse=True)[:8]
        ],
        "upcoming_workload": sum(1 for task in operations_tasks if _normalize_operations_task_status(task.get("status", "NEW")) in open_task_statuses and _parse_iso_datetime(str(task.get("due_date", "")).strip()) and today <= _parse_iso_datetime(str(task.get("due_date", "")).strip()).date() <= week_end),
        "late_workload": len(overdue_operations),
    }

    sla_assignment_minutes = []
    sla_response_minutes = []
    sla_completion_minutes = []
    reopened_tasks = 0
    tasks_with_due_dates = 0
    tasks_completed_on_time = 0
    tasks_waiting = 0
    for task in operations_tasks:
        task_created_at = _parse_iso_datetime(str(task.get("created_at", "")).strip())
        task_completed_at = _parse_iso_datetime(str(task.get("completed_at", "")).strip())
        task_due_at = _parse_iso_datetime(str(task.get("due_date", "")).strip())
        if task_created_at and task_created_at.tzinfo is None:
            task_created_at = task_created_at.replace(tzinfo=timezone.utc)
        if task_completed_at and task_completed_at.tzinfo is None:
            task_completed_at = task_completed_at.replace(tzinfo=timezone.utc)
        if task_due_at and task_due_at.tzinfo is None:
            task_due_at = task_due_at.replace(tzinfo=timezone.utc)
        task_status = _normalize_operations_task_status(task.get("status", "NEW"))
        if task_status in {"WAITING_OWNER", "WAITING_OPERATIONS"}:
            tasks_waiting += 1
        if task_due_at:
            tasks_with_due_dates += 1
        if task_status in completed_task_statuses and task_created_at and task_completed_at and task_completed_at >= task_created_at:
            sla_completion_minutes.append(int((task_completed_at - task_created_at).total_seconds() / 60))
            if task_due_at and task_completed_at <= task_due_at:
                tasks_completed_on_time += 1
        timeline_events = _load_operations_task_events(task.get("request_id", "") or task.get("id", ""))
        if task_created_at and timeline_events:
            parsed_events = [(_parse_iso_datetime(event.get("created_at", "")), str(event.get("event_type", "")).strip().lower()) for event in timeline_events]
            parsed_events = [(event_dt, event_type) for event_dt, event_type in parsed_events if event_dt and event_dt >= task_created_at]
            if parsed_events:
                first_event_dt = min(event_dt for event_dt, _ in parsed_events)
                sla_response_minutes.append(int((first_event_dt - task_created_at).total_seconds() / 60))
                assignment_events = [
                    event_dt for event_dt, event_type in parsed_events
                    if event_type in {"assigned", "professional_assigned", "professional_accepted", "status_changed"}
                ]
                if assignment_events:
                    sla_assignment_minutes.append(int((min(assignment_events) - task_created_at).total_seconds() / 60))
        if any(str(event.get("event_type", "")).strip().lower() == "reopened" for event in timeline_events):
            reopened_tasks += 1

    sla_monitoring = {
        "average_completion_time": _format_owner_portal_duration(int(round(sum(sla_completion_minutes) / len(sla_completion_minutes)))) if sla_completion_minutes else "Pending",
        "average_assignment_time": _format_owner_portal_duration(int(round(sum(sla_assignment_minutes) / len(sla_assignment_minutes)))) if sla_assignment_minutes else "Pending",
        "average_response_time": _format_owner_portal_duration(int(round(sum(sla_response_minutes) / len(sla_response_minutes)))) if sla_response_minutes else "Pending",
        "late_percent": int(round((len(overdue_operations) / max(len(open_operations), 1)) * 100)) if open_operations else 0,
        "completed_percent": int(round((sum(1 for task in operations_tasks if _normalize_operations_task_status(task.get("status", "NEW")) in completed_task_statuses) / max(len(operations_tasks), 1)) * 100)) if operations_tasks else 0,
        "waiting_percent": int(round((tasks_waiting / max(len(operations_tasks), 1)) * 100)) if operations_tasks else 0,
        "reopened_percent": int(round((reopened_tasks / max(len(operations_tasks), 1)) * 100)) if operations_tasks else 0,
    }

    executive_alerts = []
    property_risk_map = {}
    property_risk_cards = []

    for property_record in owner_properties:
        property_id = str(property_record.get("id", "")).strip()
        property_name = property_record.get("name", "") or property_record.get("location", "") or property_id or "Property"
        property_location = property_record.get("location", "")
        property_tasks = property_tasks_map.get(property_id, [])
        property_reservations = property_reservations_map.get(property_id, [])
        property_calendar_events = property_calendar_map.get(property_id, [])
        readiness_completed, readiness_total = _owner_property_checklist_completion(property_record)
        readiness_percent = int(round((readiness_completed / max(readiness_total, 1)) * 100)) if readiness_total else 0
        open_property_tasks = [task for task in property_tasks if _normalize_operations_task_status(task.get("status", "NEW")) in open_task_statuses]
        overdue_property_tasks = [task for task in open_property_tasks if _admin_operations_task_is_overdue(task)]
        unassigned_property_tasks = [task for task in open_property_tasks if not str(task.get("assigned_professional_id", "")).strip() and not str(task.get("assigned_to", "")).strip()]
        property_service_requests = [
            record for record in service_requests
            if str(record.get("property_id", "")).strip() == property_id
            or str(record.get("property", "")).strip().lower() == property_name.lower()
            or str(record.get("property_city", "")).strip().lower() == str(property_location).strip().lower()
        ]
        pending_owner_requests = []
        for record in property_service_requests:
            request_status = _normalize_service_request_status(record.get("status", "new"))
            created_at = _parse_iso_datetime(record.get("created_at", ""))
            if request_status in {"new", "assigned", "in_progress"} and created_at and now - created_at > timedelta(hours=48):
                pending_owner_requests.append(record)

        reservations_sorted = sorted(
            [
                reservation for reservation in property_reservations
                if _normalize_reservation_status(reservation.get("status", "PENDING")) not in {"CANCELLED", "NO_SHOW"}
            ],
            key=lambda reservation: (_reservation_date_bounds(reservation)[0] or datetime.max.replace(tzinfo=timezone.utc), _reservation_date_bounds(reservation)[1] or datetime.max.replace(tzinfo=timezone.utc)),
        )
        arrival_within_24h = []
        missing_cleaning = []
        calendar_conflicts = []
        overlapping_reservations = []

        for reservation in reservations_sorted:
            arrival_dt, departure_dt = _reservation_date_bounds(reservation)
            if arrival_dt and now <= arrival_dt <= now + timedelta(hours=24):
                arrival_within_24h.append(reservation)
            if arrival_dt and departure_dt:
                for calendar_event in property_calendar_events:
                    event_start = _parse_iso_datetime(calendar_event.get("start_datetime", ""))
                    event_end = _parse_iso_datetime(calendar_event.get("end_datetime", ""))
                    if not event_start:
                        continue
                    if not event_end:
                        event_end = event_start + timedelta(hours=1)
                    if event_start < departure_dt and event_end > arrival_dt and _normalize_calendar_event_type(calendar_event.get("event_type", "")) not in {"Blocked Dates"}:
                        calendar_conflicts.append(calendar_event)
                        break
            if arrival_dt and departure_dt:
                cleaning_tasks = [
                    task for task in open_property_tasks
                    if "clean" in f"{task.get('category', '')} {task.get('title', '')}".lower()
                ]
                if arrival_dt <= now + timedelta(hours=24) and not cleaning_tasks:
                    missing_cleaning.append(reservation)

        for previous_reservation, next_reservation in zip(reservations_sorted, reservations_sorted[1:]):
            previous_arrival, previous_departure = _reservation_date_bounds(previous_reservation)
            next_arrival, next_departure = _reservation_date_bounds(next_reservation)
            if previous_arrival and previous_departure and next_arrival and previous_departure > next_arrival:
                overlapping_reservations.append((previous_reservation, next_reservation))

        property_alert_created_at = now
        risk_score = 0
        risk_score += min(30, len(overdue_property_tasks) * 12)
        risk_score += min(15, len(unassigned_property_tasks) * 8)
        risk_score += min(20, len(overlapping_reservations) * 15)
        risk_score += min(10, len(calendar_conflicts) * 8)
        risk_score += min(10, len(pending_owner_requests) * 6)
        risk_score += min(10, len([task for task in open_property_tasks if not str(task.get("due_date", "")).strip()]) * 5)
        risk_score += min(10, max(0, 100 - readiness_percent))
        risk_score += min(10, len(missing_cleaning) * 8)
        risk_score += min(10, len(arrival_within_24h) * 4 if readiness_percent < 100 else 0)
        risk_score = max(0, min(100, risk_score))
        band = _admin_executive_risk_band(risk_score)
        property_risk_map[property_id] = {
            "risk_score": risk_score,
            "risk_label": band["label"],
            "risk_tone": band["tone"],
            "risk_badge": f"{risk_score} / 100",
            "risk_summary": f"{band['label']} risk",
        }
        property_risk_cards.append({
            "id": property_id,
            "name": property_name,
            "location": property_location,
            "score": risk_score,
            "tier": band["label"],
            "tone": band["tone"],
            "badge": f"{risk_score} / 100",
            "summary": f"{len(overdue_property_tasks)} overdue, {len(unassigned_property_tasks)} unassigned, {len(arrival_within_24h)} arrivals in 24h",
            "factors": [
                {"label": "Overdue operations", "count": len(overdue_property_tasks)},
                {"label": "Unassigned operations", "count": len(unassigned_property_tasks)},
                {"label": "Calendar conflicts", "count": len(calendar_conflicts)},
                {"label": "Overlapping reservations", "count": len(overlapping_reservations)},
                {"label": "Owner requests waiting", "count": len(pending_owner_requests)},
                {"label": "Missing cleaning", "count": len(missing_cleaning)},
            ],
        })

        if overdue_property_tasks:
            for task in overdue_property_tasks:
                executive_alerts.append(_admin_executive_record_alert(
                    severity="critical",
                    category="overdue_operations",
                    property_label=property_name,
                    operation_label=task.get("title", "") or task.get("category", "") or task.get("id", ""),
                    created_at=task.get("updated_at", task.get("created_at", now.isoformat())),
                    recommended_action=f"Complete overdue operation for {property_name}",
                    detail=str(task.get("notes", "")).strip() or str(task.get("admin_notes", "")).strip() or "Operation is past due",
                    link=f"/admin/operations/{task.get('id', '')}",
                ))

        for task in unassigned_property_tasks:
            executive_alerts.append(_admin_executive_record_alert(
                severity="high",
                category="unassigned_operations",
                property_label=property_name,
                operation_label=task.get("title", "") or task.get("category", "") or task.get("id", ""),
                created_at=task.get("updated_at", task.get("created_at", now.isoformat())),
                recommended_action=f"Assign a professional to {property_name}",
                detail="Operation has no assigned professional",
                link=f"/admin/operations/{task.get('id', '')}",
            ))

        for task in open_property_tasks:
            if str(task.get("due_date", "")).strip():
                continue
            executive_alerts.append(_admin_executive_record_alert(
                severity="medium",
                category="operations_without_due_dates",
                property_label=property_name,
                operation_label=task.get("title", "") or task.get("category", "") or task.get("id", ""),
                created_at=task.get("updated_at", task.get("created_at", now.isoformat())),
                recommended_action=f"Add a due date to {task.get('title', '') or property_name}",
                detail="Open operation is missing a due date",
                link=f"/admin/operations/{task.get('id', '')}",
            ))

        for request_record in pending_owner_requests:
            executive_alerts.append(_admin_executive_record_alert(
                severity="warning",
                category="owner_requests_waiting",
                property_label=property_name,
                reservation_label="",
                operation_label=str(request_record.get("name", "")).strip() or str(request_record.get("service_category", "")).strip() or request_record.get("id", ""),
                created_at=request_record.get("created_at", now.isoformat()),
                recommended_action=f"Follow up the owner request for {property_name}",
                detail="Owner request has been waiting longer than 48 hours",
                link="/admin/service-requests",
            ))

        if readiness_percent < 100:
            executive_alerts.append(_admin_executive_record_alert(
                severity="warning" if readiness_percent >= 60 else "high",
                category="properties_without_readiness",
                property_label=property_name,
                created_at=property_alert_created_at,
                recommended_action=f"Finish the readiness checklist for {property_name}",
                detail=f"Readiness is at {readiness_percent}%",
                link=f"/admin/properties/{property_id}",
            ))

        for reservation in arrival_within_24h:
            reservation_label = reservation.get("property_name", "") or reservation.get("guest_label", "") or reservation.get("id", "")
            executive_alerts.append(_admin_executive_record_alert(
                severity="critical" if readiness_percent < 70 else "high",
                category="reservations_arriving_within_24h_without_completed_preparation",
                property_label=property_name,
                reservation_label=reservation_label,
                created_at=reservation.get("updated_at", reservation.get("arrival_datetime", now.isoformat())),
                recommended_action=f"Prepare {property_name} before arrival",
                detail="Upcoming arrival still needs preparation",
                link=f"/admin/reservations/{reservation.get('id', '')}",
            ))

        for reservation in missing_cleaning:
            reservation_label = reservation.get("property_name", "") or reservation.get("guest_label", "") or reservation.get("id", "")
            executive_alerts.append(_admin_executive_record_alert(
                severity="warning",
                category="reservations_missing_assigned_cleaning",
                property_label=property_name,
                reservation_label=reservation_label,
                created_at=reservation.get("updated_at", reservation.get("arrival_datetime", now.isoformat())),
                recommended_action=f"Assign cleaning to {property_name}",
                detail="Reservation is approaching without an assigned cleaning task",
                link=f"/admin/reservations/{reservation.get('id', '')}",
            ))

        for calendar_event in calendar_conflicts:
            executive_alerts.append(_admin_executive_record_alert(
                severity="warning",
                category="calendar_conflicts",
                property_label=property_name,
                created_at=calendar_event.get("start_datetime", now.isoformat()),
                recommended_action=f"Resolve the calendar overlap for {property_name}",
                detail=calendar_event.get("title", "") or "Calendar event overlaps with a reservation",
                link="/admin/calendar",
            ))

        for previous_reservation, next_reservation in overlapping_reservations:
            executive_alerts.append(_admin_executive_record_alert(
                severity="critical",
                category="overlapping_reservations",
                property_label=property_name,
                reservation_label=f"{previous_reservation.get('id', '')} / {next_reservation.get('id', '')}",
                created_at=next_reservation.get("updated_at", next_reservation.get("arrival_datetime", now.isoformat())),
                recommended_action=f"Review overlapping reservations for {property_name}",
                detail="Reservations share overlapping occupancy windows",
                link=f"/admin/properties/{property_id}",
            ))

    for professional_account in active_professionals:
        professional_id = str(professional_account.get("id", "")).strip()
        task_count = professional_task_counts.get(professional_id, 0)
        if task_count <= overload_threshold:
            continue
        professional_name = _professional_account_display_label(professional_account)
        executive_alerts.append(_admin_executive_record_alert(
            severity="high" if task_count <= overload_threshold + 2 else "critical",
            category="professionals_overloaded",
            property_label="",
            operation_label=professional_name,
            created_at=professional_account.get("last_login_at", professional_account.get("created_at", now.isoformat())),
            recommended_action=f"Move work away from {professional_name}",
            detail=f"{task_count} open operations assigned",
            link="/admin/professionals",
        ))

    severity_rank = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}
    executive_alerts.sort(key=lambda item: (severity_rank.get(item["severity"], 0), item["created_at"]), reverse=True)
    executive_alerts = executive_alerts[:24]

    for card in property_status_cards:
        risk_data = property_risk_map.get(str(card.get("id", "")).strip(), {})
        if risk_data:
            card.update(risk_data)

    property_risk_cards.sort(key=lambda item: (item["score"], item["name"]), reverse=True)

    executive_timeline = []
    for reservation in reservations:
        property_id = str(reservation.get("property_id", "")).strip()
        property_label = property_map.get(property_id, {}).get("name", "") or reservation.get("property_name", "") or property_id
        link = f"/admin/reservations/{reservation.get('id', '')}"
        actor = reservation.get("guest_label", "") or reservation.get("guest_name", "") or reservation.get("created_by", "") or "Guest"
        for event in _reservation_timeline_events(reservation)[-4:]:
            parsed_at = _parse_iso_datetime(event.get("created_at", ""))
            if not parsed_at:
                continue
            executive_timeline.append(_admin_executive_record_timeline_event(
                timestamp=parsed_at,
                icon="RSV",
                event_type="Reservation",
                property_label=property_label,
                summary=event.get("title", "") or "Reservation event",
                actor=actor,
                link=link,
                tone="arrival" if "check-in" in str(event.get("title", "")).lower() else "departure" if "check-out" in str(event.get("title", "")).lower() else "info",
            ))

    for task in operations_tasks:
        link = f"/admin/operations/{task.get('id', '')}"
        property_id = str(task.get("property_id", "")).strip()
        property_label = property_map.get(property_id, {}).get("name", "") or task.get("property_name", "") or task.get("property_location", "") or property_id
        for event in _load_operations_task_events(task.get("request_id", "") or task.get("id", ""))[:4]:
            parsed_at = _parse_iso_datetime(event.get("created_at", ""))
            if not parsed_at:
                continue
            executive_timeline.append(_admin_executive_record_timeline_event(
                timestamp=parsed_at,
                icon="OPS",
                event_type="Operation",
                property_label=property_label,
                summary=event.get("title", "") or "Operation event",
                actor=task.get("assigned_to", "") or professional_labels.get(str(task.get("assigned_professional_id", "")).strip(), "") or "Operations",
                link=link,
                tone=_operations_task_status_tone(event.get("status", task.get("status", "NEW"))),
            ))

    for event in enriched_calendar_events:
        parsed_at = _parse_iso_datetime(event.get("start_datetime", "")) or _parse_iso_datetime(event.get("created_at", ""))
        if not parsed_at:
            continue
        property_id = str(event.get("property_id", "")).strip()
        property_label = property_map.get(property_id, {}).get("name", "") or event.get("property_label", "") or property_id
        executive_timeline.append(_admin_executive_record_timeline_event(
            timestamp=parsed_at,
            icon="CAL",
            event_type="Calendar",
            property_label=property_label,
            summary=event.get("title", "") or event.get("event_type", "") or "Calendar event",
            actor=event.get("created_by", "") or event.get("owner_label", "") or "Calendar",
            link="/admin/calendar",
            tone="warning" if event.get("is_overdue") else "info",
        ))

    for professional_account in professional_accounts:
        created_at = _parse_iso_datetime(professional_account.get("created_at", ""))
        if not created_at:
            continue
        executive_timeline.append(_admin_executive_record_timeline_event(
            timestamp=created_at,
            icon="PRO",
            event_type="Professional",
            property_label=str(professional_account.get("city", "")).strip(),
            summary=professional_account.get("full_name", "") or professional_account.get("company", "") or "Professional account",
            actor=professional_account.get("email", "") or professional_account.get("full_name", "") or "Professional",
            link="/admin/professionals",
            tone="success" if _normalize_professional_account_status(professional_account.get("status", "PENDING")) in {"ACTIVE", "APPROVED"} else "warning",
        ))

    for request_record in service_requests:
        for event in _service_request_timeline_events(request_record)[-4:]:
            parsed_at = _parse_iso_datetime(event.get("created_at", ""))
            if not parsed_at:
                continue
            property_id = str(request_record.get("property_id", "")).strip()
            property_label = property_map.get(property_id, {}).get("name", "") or request_record.get("property", "") or request_record.get("property_city", "") or property_id
            executive_timeline.append(_admin_executive_record_timeline_event(
                timestamp=parsed_at,
                icon="OWN",
                event_type="Owner request",
                property_label=property_label,
                summary=event.get("title", "") or "Owner request",
                actor=request_record.get("name", "") or request_record.get("owner_name", "") or request_record.get("email", "") or "Owner",
                link="/admin/service-requests",
                tone="warning" if _normalize_service_request_status(request_record.get("status", "new")) in {"new", "assigned"} else "info",
            ))

    for event in operations_notifications[:20]:
        parsed_at = _parse_iso_datetime(event.get("created_at", ""))
        if not parsed_at:
            continue
        executive_timeline.append(_admin_executive_record_timeline_event(
            timestamp=parsed_at,
            icon="SYS",
            event_type="System",
            property_label="",
            summary=event.get("title", "") or event.get("event_type", "") or "System event",
            actor=event.get("channel", "") or "System",
            link="/admin/notifications",
            tone="danger" if event.get("status") == "failed" else "info",
        ))

    for event in property_activity_events[:20]:
        parsed_at = _parse_iso_datetime(event.get("created_at", ""))
        if not parsed_at:
            continue
        property_id = str(event.get("property_id", "")).strip()
        property_label = property_map.get(property_id, {}).get("name", "") or event.get("title", "") or property_id
        executive_timeline.append(_admin_executive_record_timeline_event(
            timestamp=parsed_at,
            icon="PRP",
            event_type="Property",
            property_label=property_label,
            summary=event.get("title", "") or "Property event",
            actor=event.get("detail", "") or "System",
            link=f"/admin/properties/{property_id}" if property_id else "/admin/properties",
            tone="neutral",
        ))

    executive_timeline.sort(key=lambda item: item["timestamp"], reverse=True)
    executive_timeline = executive_timeline[:40]

    smart_recommendations = []
    recommendation_signatures = set()

    def _add_recommendation(title, detail, link):
        signature = (title, detail, link)
        if signature in recommendation_signatures:
            return
        recommendation_signatures.add(signature)
        smart_recommendations.append({
            "title": title,
            "detail": detail,
            "link": link,
        })

    for alert in executive_alerts[:12]:
        if alert["category"] == "unassigned_operations" and alert["property"]:
            _add_recommendation(
                f"Assign cleaner to {alert['property']}",
                alert["detail"] or "Operational task is waiting for assignment",
                alert["link"] or "/admin/operations",
            )
        elif alert["category"] == "reservations_arriving_within_24h_without_completed_preparation" and alert["property"]:
            _add_recommendation(
                f"Prepare {alert['property']} for arrival",
                "Arrival is less than 24 hours away",
                alert["link"] or "/admin/reservations",
            )
        elif alert["category"] == "professionals_overloaded" and alert["operation"]:
            _add_recommendation(
                f"Move operation to another team",
                f"{alert['operation']} is carrying too many open tasks",
                alert["link"] or "/admin/professionals",
            )
        elif alert["category"] == "operations_without_due_dates":
            _add_recommendation(
                "Add due dates to open operations",
                alert["operation"] or "An open operation is missing a due date",
                alert["link"] or "/admin/operations",
            )
        elif alert["category"] == "owner_requests_waiting" and alert["property"]:
            _add_recommendation(
                f"Follow up owner request for {alert['property']}",
                "The owner has been waiting too long for an update",
                alert["link"] or "/admin/service-requests",
            )

    for card in property_risk_cards[:8]:
        if card["score"] <= 40:
            continue
        _add_recommendation(
            f"Reduce risk on {card['name']}",
            card["summary"],
            f"/admin/properties/{card['id']}",
        )

    for property_record in owner_properties:
        property_id = str(property_record.get("id", "")).strip()
        property_name = property_record.get("name", "") or property_id or "Property"
        readiness_completed, readiness_total = _owner_property_checklist_completion(property_record)
        readiness_percent = int(round((readiness_completed / max(readiness_total, 1)) * 100)) if readiness_total else 0
        property_reservations = property_reservations_map.get(property_id, [])
        upcoming_pending = [
            reservation for reservation in property_reservations
            if _normalize_reservation_status(reservation.get("status", "PENDING")) in {"PENDING", "CONFIRMED"}
            and (_reservation_date_bounds(reservation)[0] and now <= _reservation_date_bounds(reservation)[0] <= now + timedelta(hours=48))
        ]
        if readiness_percent == 100 and not [task for task in property_tasks_map.get(property_id, []) if _normalize_operations_task_status(task.get("status", "NEW")) in open_task_statuses and _admin_operations_task_is_overdue(task)] and upcoming_pending:
            _add_recommendation(
                f"Reservation can now be confirmed for {property_name}",
                "Readiness is complete and the next reservation is clear to confirm",
                f"/admin/properties/{property_id}",
            )
        elif readiness_percent == 100 and not upcoming_pending and not property_tasks_map.get(property_id, []):
            _add_recommendation(
                f"Property ready for next reservation",
                property_name,
                f"/admin/properties/{property_id}",
            )

    smart_recommendations = smart_recommendations[:12]

    calendar_widget = _calendar_dashboard_widget(enriched_calendar_events, scope="admin")
    reservation_widget = {
        "todays_check_ins": [reservation for reservation in reservations if _reservation_date_bounds(reservation)[0] and _reservation_date_bounds(reservation)[0].date() == today][:5],
        "todays_check_outs": [reservation for reservation in reservations if _reservation_date_bounds(reservation)[1] and _reservation_date_bounds(reservation)[1].date() == today][:5],
        "current_guests": [reservation for reservation in reservations if _reservation_is_occupying(reservation, today)][:5],
        "cleaning_queue": [reservation for reservation in reservations if _reservation_date_bounds(reservation)[1] and _reservation_date_bounds(reservation)[1].date() >= today][:5],
        "inspections": [reservation for reservation in reservations if _reservation_date_bounds(reservation)[1] and _reservation_date_bounds(reservation)[1].date() >= today][:5],
        "todays_operations": [task for task in operations_tasks if str(task.get("due_date", "")).strip()[:10] == today.isoformat()][:5],
        "late_operations": overdue_operations[:5],
        "property_occupancy": occupancy_engine,
        "cleaning_today": [task for task in operations_tasks if str(task.get("due_date", "")).strip()[:10] == today.isoformat() and "clean" in str(task.get("category", "")).lower()][:5],
        "checkins": [reservation for reservation in reservations if _reservation_date_bounds(reservation)[0] and _reservation_date_bounds(reservation)[0].date() == today][:5],
        "revenue_placeholder": "Pending channel revenue sync",
        "stats": {
            "todays_check_ins": sum(1 for reservation in reservations if _reservation_date_bounds(reservation)[0] and _reservation_date_bounds(reservation)[0].date() == today),
            "todays_check_outs": sum(1 for reservation in reservations if _reservation_date_bounds(reservation)[1] and _reservation_date_bounds(reservation)[1].date() == today),
            "occupancy": occupancy_engine["occupancy_percent"],
            "availability": occupancy_engine["availability_percent"],
            "cleaning_queue": len([reservation for reservation in reservations if _reservation_date_bounds(reservation)[1] and _reservation_date_bounds(reservation)[1].date() >= today]),
            "inspections": len([reservation for reservation in reservations if _reservation_date_bounds(reservation)[1] and _reservation_date_bounds(reservation)[1].date() >= today]),
            "arrivals_today": sum(1 for reservation in reservations if _reservation_date_bounds(reservation)[0] and _reservation_date_bounds(reservation)[0].date() == today),
            "departures_today": sum(1 for reservation in reservations if _reservation_date_bounds(reservation)[1] and _reservation_date_bounds(reservation)[1].date() == today),
            "cleaning_today": len([task for task in operations_tasks if str(task.get("due_date", "")).strip()[:10] == today.isoformat() and "clean" in str(task.get("category", "")).lower()]),
            "checkins": sum(1 for reservation in reservations if _reservation_date_bounds(reservation)[0] and _reservation_date_bounds(reservation)[0].date() == today),
            "late_operations": len(overdue_operations),
            "todays_operations": len([task for task in operations_tasks if str(task.get("due_date", "")).strip()[:10] == today.isoformat()]),
            "revenue": 0,
        },
    }

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
        "property_total_count": len(owner_properties),
        "active_properties": property_status_counts.get("ACTIVE", 0),
        "seasonal_properties": property_status_counts.get("SEASONAL", 0),
        "inactive_properties": property_status_counts.get("INACTIVE", 0),
        "active_service_requests": active_requests,
        "completed_service_requests": completed_requests,
        "service_requests_this_month": requests_this_month,
        "partner_status_counts": partner_counts,
        "professional_status_counts": professional_counts,
        "executive_kpis": executive_kpis,
        "executive_alerts": executive_alerts,
        "property_risk_cards": property_risk_cards,
        "executive_timeline": executive_timeline,
        "workload_distribution": workload_distribution,
        "sla_monitoring": sla_monitoring,
        "smart_recommendations": smart_recommendations,
        "today_operations_groups": today_operations_groups,
        "operations_heatmap": operations_heatmap,
        "reservation_timeline_groups": reservation_timeline_groups,
        "property_status_cards": property_status_cards,
        "operations_summary": operations_summary,
        "professional_summary": professional_summary,
        "quick_actions": [
            {"label": "Create Reservation", "href": "/admin/reservations", "tone": "primary"},
            {"label": "Create Operation", "href": "/admin/operations", "tone": "secondary"},
            {"label": "Open Calendar", "href": "/admin/calendar", "tone": "secondary"},
            {"label": "Open Reservations", "href": "/admin/reservations", "tone": "secondary"},
            {"label": "Open Operations", "href": "/admin/operations", "tone": "secondary"},
            {"label": "Import Reservations", "href": "/admin/reservations/import", "tone": "secondary"},
            {"label": "Add Property", "href": "/admin/properties", "tone": "secondary"},
            {"label": "Add Professional", "href": "/admin/professionals", "tone": "secondary"},
        ],
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
        "calendar_widget": calendar_widget,
        "reservation_widget": reservation_widget,
        "recent_activity": recent_activity,
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
    if _public_form_honeypot_filled(payload.get("website")):
        _public_form_audit_event("pilot_request", "spam_submission_blocked", "spam_honeypot_blocked")
        return jsonify({"ok": True}), 200

    if _public_form_rate_limited("pilot_request"):
        _public_form_audit_event("pilot_request", "rate_limit_blocked", "rate_limit_blocked")
        return jsonify({"ok": True}), 200

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

    if record["name"] and not _public_form_has_plausible_name(record["name"]):
        return jsonify({"ok": False, "error": "invalid_name"}), 400

    if not _public_form_has_valid_email(record["email"]):
        return jsonify({"ok": False, "error": "invalid_email"}), 400

    if not _public_form_has_plausible_location(record["city"]):
        return jsonify({"ok": False, "error": "invalid_city"}), 400

    if _public_form_text_is_spam(record["concierge_needs"]):
        _public_form_audit_event("pilot_request", "spam_submission_blocked", "content_spam_detected")
        return jsonify({"ok": True}), 200

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
    _upsert_operations_task_from_source(
        _operations_task_payload_from_source("PILOT_REQUEST", record),
        append_created_event=True,
        notify=True,
    )
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
    updated_record = _find_professional_application(application_id)
    if updated_record:
        _upsert_professional_account({
            "id": updated_record.get("id", ""),
            "created_at": updated_record.get("created_at", ""),
            "full_name": updated_record.get("full_name", ""),
            "email": updated_record.get("email", ""),
            "phone": updated_record.get("phone", ""),
            "company": updated_record.get("company_name", ""),
            "service_categories": updated_record.get("professional_category", ""),
            "status": _professional_account_status_from_application_status(updated_record.get("status", "new")),
            "last_login_at": "",
        })
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
            property_id = str(record.get("property_id", "")).strip()
            if property_id:
                _append_property_activity_event(
                    property_id,
                    record.get("owner_id", ""),
                    "service_request_completed",
                    "Service request completed",
                    new_notes or record.get("assigned_provider_company", "") or record.get("service_category", ""),
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
    _upsert_operations_task_from_service_request(record)
    return redirect(url_for("admin_service_request_detail", request_id=request_id))


def _update_operations_task_notes(task_id, notes):
    return _update_operations_task_details(task_id, notes=notes)


@app.get("/admin/reservations")
@admin_required
def admin_reservations():
    filters = {
        "property": str(request.args.get("property", "")).strip(),
        "owner": str(request.args.get("owner", "")).strip(),
        "guest": str(request.args.get("guest", "")).strip(),
        "status": str(request.args.get("status", "")).strip(),
        "arrival": str(request.args.get("arrival", "")).strip(),
        "departure": str(request.args.get("departure", "")).strip(),
        "source": str(request.args.get("source", "")).strip(),
        "search": str(request.args.get("q", "")).strip(),
    }
    context = _reservation_list_context(scope="admin", filters=filters)
    context.update({
        "page_title": "Reservations",
        "page_meta": "Admin reservation workspace",
        "create_allowed": False,
        "filters": filters,
    })
    return render_template("reservations_dashboard.html", **context)


@app.route("/admin/reservations/import", methods=["GET", "POST"])
@admin_required
def admin_reservation_import():
    current_source = str(request.values.get("source", "manual")).strip().lower() or "manual"
    preview = {}
    import_result = {}
    validation_error = ""
    preview_payload_json = ""
    if request.method == "POST":
        action = str(request.form.get("import_action", "preview")).strip().lower() or "preview"
        payload = _reservation_import_request_payload(current_source)
        context = {
            "created_by": _current_admin_operator_key(),
            "manual_property_id": str(request.form.get("manual_property_id", "")).strip(),
        }
        try:
            if action == "import":
                preview_payload_json = str(request.form.get("preview_payload_json", "")).strip()
                if preview_payload_json:
                    preview = json.loads(preview_payload_json)
                else:
                    preview = _reservation_importer().preview(current_source, payload, context=context)
                import_result = _reservation_importer().import_preview(preview, created_by=_current_admin_operator_key())
                if import_result.get("ok"):
                    return redirect(url_for("admin_reservations", imported=1, lang=_resolve_current_language()))
                validation_error = "Import blocked by validation."
            else:
                preview = _reservation_importer().preview(current_source, payload, context=context)
        except (ValueError, json.JSONDecodeError) as exc:
            validation_error = str(exc) or "Import validation failed."
            preview = {}

    if preview and not preview_payload_json:
        preview_payload_json = json.dumps(preview, ensure_ascii=False)

    context = _reservation_import_page_context(
        scope="admin",
        current_source=current_source,
        preview=preview,
        validation_error=validation_error,
        import_result=import_result,
    )
    context["preview_payload_json"] = preview_payload_json
    context["current_lang"] = _resolve_current_language()
    return render_template("admin_reservation_import.html", **context)


@app.route("/admin/reservations/<reservation_id>", methods=["GET", "POST"])
@admin_required
def admin_reservation_detail(reservation_id):
    reservation = _find_reservation(reservation_id)
    if not reservation:
        return Response("Reservation not found.", status=404, mimetype="text/plain")

    if request.method == "POST":
        action = str(request.form.get("reservation_action", "comment")).strip().lower()
        if action == "comment":
            comment_text = str(request.form.get("comment", "")).strip()
            _reservation_append_comment(reservation_id, comment_text, author=_current_admin_operator_key(), visibility="internal")
        elif action == "status":
            status_value = str(request.form.get("status", "")).strip()
            if status_value:
                _update_reservation_status(
                    reservation_id,
                    status_value,
                    author=_current_admin_operator_key(),
                    detail=str(request.form.get("status_detail", "")).strip(),
                )
        return redirect(url_for("admin_reservation_detail", reservation_id=reservation_id))

    context = _reservation_detail_context(reservation, scope="admin")
    context.update({
        "page_title": "Reservation detail",
        "page_meta": "Admin reservation detail",
    })
    return render_template("reservation_detail.html", **context)


@app.get("/admin/operations")
@admin_required
def admin_operations():
    context = _admin_operations_board_context()
    return render_template("admin_operations.html", **context)


@app.route("/admin/notifications", methods=["GET", "POST"])
@admin_required
def admin_notifications():
    current_operator_key = _current_admin_operator_key()
    if request.method == "POST":
        email_enabled = _normalize_operations_notification_flag(request.form.get("email_enabled"))
        telegram_enabled = _normalize_operations_notification_flag(request.form.get("telegram_enabled"))
        _set_operations_notification_preferences(
            current_operator_key,
            operator_name=current_operator_key,
            email_enabled=email_enabled,
            telegram_enabled=telegram_enabled,
        )
        return redirect(url_for("admin_notifications"))

    context = _admin_notifications_context()
    return render_template("admin_notifications.html", **context)


@app.route("/admin/operations/<task_id>", methods=["GET", "POST"])
@admin_required
def admin_operations_detail(task_id):
    task_record = _find_operations_task(task_id)
    if not task_record:
        return Response("Task not found.", status=404, mimetype="text/plain")

    if request.method == "POST":
        task_action = str(request.form.get("task_action", "details")).strip().lower()
        if task_action == "checklist":
            checklist_selection = {
                key: request.form.get(f"checklist_{key}") == "on"
                for key, _label in OPERATIONS_TASK_CHECKLIST_ITEMS
            }
            _update_operations_task_checklist(task_id, checklist_selection)
        elif task_action == "comment":
            comment_text = str(request.form.get("comment", "")).strip()
            comment_type = str(request.form.get("comment_type", "General")).strip() or "General"
            _append_operations_task_comment(task_id, _current_admin_operator_key(), comment_text, comment_type=comment_type)
        else:
            status_value = str(request.form.get("status", task_record.get("status", "NEW"))).strip() or task_record.get("status", "NEW")
            assigned_to_value = str(request.form.get("assigned_to", task_record.get("assigned_to", ""))).strip()
            assigned_professional_id_value = str(request.form.get("assigned_professional_id", task_record.get("assigned_professional_id", ""))).strip()
            due_date_value = str(request.form.get("due_date", task_record.get("due_date", ""))).strip()
            priority_value = str(request.form.get("priority", task_record.get("priority", "NORMAL"))).strip() or task_record.get("priority", "NORMAL")
            notes_value = str(request.form.get("admin_notes", task_record.get("admin_notes", ""))).strip()
            _update_operations_task_details(
                task_id,
                status=status_value,
                assigned_to=assigned_to_value,
                assigned_professional_id=assigned_professional_id_value,
                notes=notes_value,
                due_date=due_date_value,
                priority=priority_value,
                source="detail",
            )
        return redirect(url_for("admin_operations_detail", task_id=task_id))

    context = _admin_operations_task_context(task_record)
    return render_template(
        "admin_operations_detail.html",
        **context,
        status_options=[{"value": status, "label": _operations_task_status_label(status)} for status in OPERATIONS_TASK_BOARD_STATUSES],
    )


@app.post("/admin/operations/<task_id>/status")
@admin_required
def admin_operations_status(task_id):
    payload = request.get_json(silent=True) or {}
    status_value = str(payload.get("status", request.form.get("status", ""))).strip()
    if not status_value:
        return jsonify({"ok": False, "error": "missing_status"}), 400

    updated_task = _update_operations_task_status(task_id, status_value, source="board")
    if not updated_task:
        return jsonify({"ok": False, "error": "not_found"}), 404

    return jsonify({
        "ok": True,
        "task": {
            "request_id": updated_task.get("request_id", ""),
            "status": _normalize_operations_task_status(updated_task.get("status", "NEW")),
            "status_label": _operations_task_status_label(updated_task.get("status", "NEW")),
            "status_tone": _operations_task_status_tone(updated_task.get("status", "NEW")),
            "updated_at": updated_task.get("updated_at", ""),
        },
    })


def _demo_timeline_event_count():
    count = len(_demo_records("owner_activity_events"))
    count += len(_demo_records("property_activity_events"))
    count += len(_demo_records("operations_task_events"))
    for reservation in _demo_records("reservations"):
        metadata = _safe_json_loads(reservation.get("metadata_json", ""), {})
        timeline = metadata.get("timeline") if isinstance(metadata.get("timeline"), list) else reservation.get("timeline", [])
        if isinstance(timeline, list):
            count += len(timeline)
    return count


def _demo_data_page_context():
    manifest = _load_demo_manifest()
    summary = _demo_manifest_summary()
    return {
        "manifest": manifest,
        "summary": summary,
        "counts": {
            "properties": len(_demo_records("owner_properties")),
            "reservations": len(_demo_records("reservations")),
            "operations": len(_demo_records("operations_tasks")),
            "professionals": len(_demo_records("professional_accounts")),
            "timeline_events": _demo_timeline_event_count(),
        },
        "seeded": bool(manifest),
    }


@app.route("/admin/demo-data", methods=["GET"])
@admin_required
def admin_demo_data():
    context = _demo_data_page_context()
    message = str(request.args.get("message", "")).strip()
    notice = {
        "seeded": "Demo data seeded.",
        "cleared": "Demo data cleared.",
        "exists": "Demo data is already seeded.",
    }.get(message, "")
    return render_template_string(
        """
        <!doctype html>
        <html lang="en">
        <head>
          <meta charset="utf-8">
          <meta name="viewport" content="width=device-width, initial-scale=1">
          <title>Enterprise Demo Manager · BlackSea Connect</title>
          <link rel="stylesheet" href="{{ url_for('static', filename='css/styles.css') }}">
          <style>
            body.admin-demo-page { margin: 0; background: linear-gradient(180deg, #08111f, #101b2d); color: #f8f4ea; font-family: "Aptos", "Segoe UI", Arial, sans-serif; }
            .admin-demo-shell { width: min(1240px, calc(100% - 32px)); margin: 0 auto; padding: 28px 0 48px; }
            .admin-demo-card, .admin-demo-panel { background: rgba(7, 16, 30, 0.75); border: 1px solid rgba(255,255,255,0.08); border-radius: 22px; padding: 22px; box-shadow: 0 20px 60px rgba(0,0,0,0.2); }
            .admin-demo-grid { display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); margin-top: 18px; }
            .admin-demo-stat { padding: 18px; border-radius: 18px; background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08); }
            .admin-demo-actions { display: flex; gap: 12px; flex-wrap: wrap; margin-top: 18px; }
            .admin-demo-actions form { margin: 0; }
            .admin-demo-muted { color: rgba(248,244,234,0.72); }
            .admin-demo-notice { margin-bottom: 16px; padding: 14px 16px; border-radius: 16px; background: rgba(217, 179, 108, 0.16); color: #f3d7a1; }
            .admin-demo-kicker { text-transform: uppercase; letter-spacing: 0.24em; font-size: 0.72rem; color: rgba(248,244,234,0.7); }
            .admin-demo-title { margin: 8px 0 0; font-size: clamp(2rem, 4vw, 3.6rem); line-height: 0.98; }
            .admin-demo-summary { display: grid; gap: 10px; margin-top: 16px; }
          </style>
        </head>
        <body class="admin-cockpit-page admin-demo-page">
          <main class="admin-demo-shell">
            {% if notice %}
              <div class="admin-demo-notice">{{ notice }}</div>
            {% endif %}
            <section class="admin-demo-card">
              <p class="admin-demo-kicker">Enterprise Demo Manager</p>
              <h1 class="admin-demo-title">Summer 2026 pilot data for the executive cockpit.</h1>
              <p class="admin-demo-muted">Seed and clear are optional. Demo records stay isolated in a manifest so production data is untouched.</p>
              <div class="admin-demo-actions">
                <form method="post" action="{{ url_for('admin_demo_data_seed') }}">
                  <button class="button button--primary" type="submit">Seed Demo</button>
                </form>
                <form method="post" action="{{ url_for('admin_demo_data_clear') }}">
                  <button class="button button--secondary" type="submit">Clear Demo</button>
                </form>
                <a class="button button--ghost" href="{{ url_for('admin_demo_data') }}">Refresh Dashboard</a>
                <a class="button button--ghost" href="{{ url_for('admin_home') }}">Back to Cockpit</a>
              </div>
            </section>

            <section class="admin-demo-grid">
              <article class="admin-demo-stat">
                <span class="admin-demo-muted">Scenario</span>
                <strong>{{ summary.scenario }}</strong>
              </article>
              <article class="admin-demo-stat">
                <span class="admin-demo-muted">Seed Date</span>
                <strong>{{ summary.seed_date or 'Not seeded yet' }}</strong>
              </article>
              <article class="admin-demo-stat">
                <span class="admin-demo-muted">Batch ID</span>
                <strong>{{ summary.batch_id }}</strong>
              </article>
              <article class="admin-demo-stat">
                <span class="admin-demo-muted">Properties</span>
                <strong>{{ counts.properties }}</strong>
              </article>
              <article class="admin-demo-stat">
                <span class="admin-demo-muted">Reservations</span>
                <strong>{{ counts.reservations }}</strong>
              </article>
              <article class="admin-demo-stat">
                <span class="admin-demo-muted">Operations</span>
                <strong>{{ counts.operations }}</strong>
              </article>
              <article class="admin-demo-stat">
                <span class="admin-demo-muted">Professionals</span>
                <strong>{{ counts.professionals }}</strong>
              </article>
              <article class="admin-demo-stat">
                <span class="admin-demo-muted">Timeline Events</span>
                <strong>{{ counts.timeline_events }}</strong>
              </article>
            </section>

            <section class="admin-demo-card" style="margin-top: 18px;">
              <div class="admin-demo-summary">
                <p class="admin-demo-muted">This page reports only demo-scoped records. Production rows are not modified or removed.</p>
                <p class="admin-demo-muted">Seed twice remains idempotent because the manifest uses a stable batch id and deterministic record ids.</p>
                <p class="admin-demo-muted">Clear removes the manifest only, which leaves real operational data untouched.</p>
              </div>
            </section>
          </main>
        </body>
        </html>
        """,
        **context,
        notice=notice,
    )


@app.post("/admin/demo-data/seed")
@admin_required
def admin_demo_data_seed():
    manifest, created = _seed_demo_data_manifest()
    message = "seeded" if created else "exists"
    if manifest:
        app.logger.info("Demo data manifest ready for batch %s", manifest.get("batch_id", DEMO_BATCH_ID))
    return redirect(url_for("admin_demo_data", message=message))


@app.post("/admin/demo-data/clear")
@admin_required
def admin_demo_data_clear():
    _clear_demo_data_manifest()
    return redirect(url_for("admin_demo_data", message="cleared"))


@app.get("/admin")
@admin_required
def admin_home():
    dashboard = _build_admin_dashboard()
    return render_template("admin_home_exec.html", **dashboard)
if __name__ == "__main__":
    app.run(debug=True, port=5010)





