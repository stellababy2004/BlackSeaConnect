from datetime import datetime, timezone
from email.message import EmailMessage
import hashlib
import csv
import io
import hmac
from functools import wraps
from pathlib import Path
import json
import os
import smtplib
import urllib.error
import urllib.request
import urllib.parse
from threading import Thread
from uuid import uuid4

from flask import Flask, Response, jsonify, redirect, render_template, request, url_for

app = Flask(__name__)
app.json.ensure_ascii = False

PILOT_STATUS_VALUES = ("new", "contacted", "qualified", "converted", "lost")
PILOT_STATUS_ALIASES = {
    "rejected": "lost",
}
PROFESSIONAL_STATUS_VALUES = ("pending", "approved", "rejected")
PROFESSIONAL_SERVICE_CATEGORIES = (
    "Cleaning",
    "Maintenance",
    "Plumbing",
    "Electrical",
    "Laundry",
    "Airport transfer",
    "Concierge",
    "Property management",
    "Photography",
    "Real estate support",
)
PROFESSIONAL_SERVICE_CATEGORY_TRANSLATION_KEYS = {
    "Cleaning": "professionals.professionalsServiceCleaning",
    "Maintenance": "professionals.professionalsServiceMaintenance",
    "Plumbing": "professionals.professionalsServicePlumbing",
    "Electrical": "professionals.professionalsServiceElectrical",
    "Laundry": "professionals.professionalsServiceLaundry",
    "Airport transfer": "professionals.professionalsServiceAirportTransfer",
    "Concierge": "professionals.professionalsServiceConcierge",
    "Property management": "professionals.professionalsServicePropertyManagement",
    "Photography": "professionals.professionalsServicePhotography",
    "Real estate support": "professionals.professionalsServiceRealEstateSupport",
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


def _professional_service_category_items():
    return [
        {
            "label": category,
            "key": PROFESSIONAL_SERVICE_CATEGORY_TRANSLATION_KEYS[category],
        }
        for category in PROFESSIONAL_SERVICE_CATEGORIES
    ]


def _network_service_category_items():
    return [
        {
            "label": category,
            "key": NETWORK_SERVICE_CATEGORY_TRANSLATION_KEYS[category],
        }
        for category in NETWORK_SERVICE_CATEGORIES
    ]


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
    provider["display_badges"] = [badge for badge in ([provider["category"]] + provider["badges"] + (["Featured"] if provider.get("featured") else [])) if badge]
    provider["short_description"] = _shorten_public_description(provider.get("description", ""))
    return provider


def _load_network_providers():
    providers = []
    for record in _load_professional_applications():
        if _normalize_professional_status(record.get("status")) != "approved":
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


@app.after_request
def force_utf8_charset(response):
    mimetype = response.mimetype or ""
    if mimetype.startswith("text/") or mimetype == "application/json" or mimetype == "application/javascript":
        if "charset=" not in (response.headers.get("Content-Type", "") or "").lower():
            response.headers["Content-Type"] = f"{mimetype}; charset=utf-8"
    return response


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/guest/a-302")
def guest_portal_a302():
    return render_template("guest_portal.html")


@app.route("/services")
def services():
    return render_template("services.html")


@app.route("/demo/operations")
def demo_operations():
    return render_template("demo_operations.html")


@app.route("/partners")
def partners():
    return render_template("partners.html")


@app.route("/pilot-access")
def pilot_access():
    return render_template("pilot_access.html")


@app.route("/professionals")
def professionals():
    return render_template(
        "professionals.html",
        service_categories=_professional_service_category_items(),
    )


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
        "company_name": "",
        "service_type": "",
        "city": "",
        "phone": "",
        "email": "",
        "languages": "",
        "experience_years": "",
        "description": "",
        "website_or_social": "",
        "consent": False,
    }
    errors = {}

    if request.method == "POST":
        form_values.update({
            "full_name": str(request.form.get("full_name", "")).strip(),
            "company_name": str(request.form.get("company_name", "")).strip(),
            "service_type": str(request.form.get("service_type", "")).strip(),
            "city": str(request.form.get("city", "")).strip(),
            "phone": str(request.form.get("phone", "")).strip(),
            "email": str(request.form.get("email", "")).strip(),
            "languages": str(request.form.get("languages", "")).strip(),
            "experience_years": str(request.form.get("experience_years", "")).strip(),
            "description": str(request.form.get("description", "")).strip(),
            "website_or_social": str(request.form.get("website_or_social", "")).strip(),
            "consent": request.form.get("consent") in {"1", "on", "true", "yes"},
        })

        required_field_error_keys = {
            "full_name": "fullNameRequiredError",
            "company_name": "companyNameRequiredError",
            "service_type": "serviceTypeRequiredError",
            "city": "cityRequiredError",
            "phone": "phoneRequiredError",
            "email": "emailRequiredError",
            "languages": "languagesRequiredError",
            "experience_years": "experienceRequiredError",
            "description": "descriptionRequiredError",
        }

        for field, error_key in required_field_error_keys.items():
            if not form_values[field]:
                errors[field] = error_key

        if form_values["service_type"] and form_values["service_type"] not in PROFESSIONAL_SERVICE_CATEGORIES:
            errors["service_type"] = "serviceTypeInvalidError"

        if form_values["experience_years"] and not form_values["experience_years"].isdigit():
            errors["experience_years"] = "experienceInvalidError"

        if not form_values["consent"]:
            errors["consent"] = "consentRequiredError"

        if not errors:
            try:
                experience_years = int(form_values["experience_years"])
            except ValueError:
                experience_years = form_values["experience_years"]

            record = {
                "id": uuid4().hex,
                "created_at": _utc_now_iso(),
                "status": "pending",
                "full_name": form_values["full_name"],
                "company_name": form_values["company_name"],
                "service_type": form_values["service_type"],
                "city": form_values["city"],
                "phone": form_values["phone"],
                "email": form_values["email"],
                "languages": form_values["languages"],
                "experience_years": experience_years,
                "description": form_values["description"],
                "website_or_social": form_values["website_or_social"],
                "consent": True,
                "internal_notes": "",
                "timeline": [],
            }
            _append_professional_timeline_event(
                record,
                "PROFESSIONAL_APPLICATION_CREATED",
                f"Professional application created: {record.get('full_name') or record.get('company_name') or 'Unnamed application'}",
                f"{record.get('service_type', '')} · {record.get('city', '')}",
                status="pending",
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
            _queue_professional_application_notification(record, admin_detail_url)

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


def _normalize_professional_status(status):
    normalized = str(status or "").strip().lower()
    return normalized if normalized in PROFESSIONAL_STATUS_VALUES else "pending"


def _professional_status_label(status):
    return _normalize_professional_status(status).upper()


def _normalize_professional_application_timeline(timeline):
    if not isinstance(timeline, list):
        return []

    normalized_timeline = []
    for entry in timeline:
        if not isinstance(entry, dict):
            continue

        normalized_entry = dict(entry)
        normalized_entry["type"] = str(normalized_entry.get("type", "")).strip() or "PROFESSIONAL_APPLICATION_CREATED"
        normalized_entry["created_at"] = str(normalized_entry.get("created_at", "")).strip()
        normalized_entry["title"] = str(normalized_entry.get("title", "")).strip()
        normalized_entry["detail"] = str(normalized_entry.get("detail", "")).strip()
        if "status" in normalized_entry:
            normalized_entry["status"] = _normalize_professional_status(normalized_entry.get("status"))
        else:
            normalized_entry["status"] = ""
        normalized_timeline.append(normalized_entry)

    return normalized_timeline


def _append_professional_timeline_event(record, event_type, title, detail="", status=None):
    timeline = list(record.get("timeline") or [])
    timeline.append({
        "type": event_type,
        "created_at": _utc_now_iso(),
        "title": title,
        "detail": detail,
        "status": _normalize_professional_status(status or record.get("status", "pending")),
    })
    record["timeline"] = timeline


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
        "detail": f"{record.get('service_type', '')} · {record.get('city', '')}",
        "status": _normalize_professional_status(record.get("status", "pending")),
    }]


def _fallback_professional_application_id(record):
    parts = [
        str(record.get("created_at", "")),
        str(record.get("email", "")),
        str(record.get("company_name", "")),
        str(record.get("service_type", "")),
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
    normalized["status"] = _normalize_professional_status(normalized.get("status", "pending"))

    for field in (
        "full_name",
        "company_name",
        "service_type",
        "city",
        "phone",
        "email",
        "languages",
        "description",
        "website_or_social",
        "internal_notes",
    ):
        normalized[field] = str(normalized.get(field, "")).strip()

    experience_years = normalized.get("experience_years", "")
    if isinstance(experience_years, str):
        experience_years = experience_years.strip()
        normalized["experience_years"] = int(experience_years) if experience_years.isdigit() else experience_years
    elif isinstance(experience_years, (int, float)):
        normalized["experience_years"] = int(experience_years)
    else:
        normalized["experience_years"] = str(experience_years).strip()

    consent_value = normalized.get("consent", False)
    normalized["consent"] = _normalize_bool_field(consent_value)

    normalized["featured"] = _normalize_bool_field(normalized.get("featured", False))
    normalized["badges"] = _normalize_professional_badges(normalized.get("badges", []))
    normalized["photo_url"] = str(normalized.get("photo_url", "")).strip()
    normalized["logo_url"] = str(normalized.get("logo_url", "")).strip()

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
    counts = {status: 0 for status in PROFESSIONAL_STATUS_VALUES}
    for record in applications:
        status = _normalize_professional_status(record.get("status", "pending"))
        if status in counts:
            counts[status] += 1
    return counts


def _admin_professional_activity_feed(applications):
    events = []
    for record in applications:
        timeline_events = _professional_application_timeline_events(record)
        if timeline_events:
            events.extend(timeline_events)

    events.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return events[:10]


def _build_professional_telegram_text(record, admin_detail_url):
    lines = [
        "New Professional Application",
        f"full_name: {record.get('full_name', '')}",
        f"company_name: {record.get('company_name', '')}",
        f"service_type: {record.get('service_type', '')}",
        f"city: {record.get('city', '')}",
        f"phone: {record.get('phone', '')}",
        f"email: {record.get('email', '')}",
        f"status: {_normalize_professional_status(record.get('status', 'pending')).upper()}",
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


def _admin_activity_feed(pilot_requests, concierge_requests, professional_applications):
    events = []
    events.extend(_admin_pilot_activity_feed(pilot_requests, concierge_requests))
    events.extend(_admin_professional_activity_feed(professional_applications))
    events.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return events[:10]


def _build_admin_dashboard():
    pilot_requests = _load_pilot_requests()
    concierge_requests = _load_concierge_requests()
    professional_applications = _load_professional_applications()
    pilot_counts = _pilot_status_counts(pilot_requests)

    return {
        "total_leads": len(pilot_requests),
        "total_pilot_requests": len(pilot_requests),
        "new_leads": pilot_counts["new"],
        "contacted_leads": pilot_counts["contacted"],
        "qualified_leads": pilot_counts["qualified"],
        "converted_leads": pilot_counts["converted"],
        "lost_leads": pilot_counts["lost"],
        "concierge_requests": len(concierge_requests),
        "professional_applications": len(professional_applications),
        "pipeline": [
            {"key": "new", "label": "New", "count": pilot_counts["new"]},
            {"key": "contacted", "label": "Contacted", "count": pilot_counts["contacted"]},
            {"key": "qualified", "label": "Qualified", "count": pilot_counts["qualified"]},
            {"key": "converted", "label": "Converted", "count": pilot_counts["converted"]},
            {"key": "lost", "label": "Lost", "count": pilot_counts["lost"]},
        ],
        "recent_activity": _admin_activity_feed(pilot_requests, concierge_requests, professional_applications),
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


@app.get("/admin/professionals/<application_id>")
@admin_required
def admin_professional_detail(application_id):
    record = _find_professional_application(application_id)
    if not record:
        return jsonify({"ok": False, "error": "not_found"}), 404

    return render_template(
        "admin_professional_detail.html",
        item=record,
        status_options=[{"value": status, "label": _professional_status_label(status)} for status in PROFESSIONAL_STATUS_VALUES],
        timeline=list(reversed(_professional_application_timeline_events(record))),
    )


@app.post("/admin/professionals/<application_id>/update")
@admin_required
def admin_professional_update(application_id):
    applications = _load_professional_applications()
    updated = False

    for record in applications:
        if str(record.get("id", "")) != str(application_id):
            continue

        raw_status = str(request.form.get("status", "")).strip()
        original_status = _normalize_professional_status(record.get("status", "pending"))
        if raw_status:
            new_status = _normalize_professional_status(raw_status)
            if new_status != raw_status.lower():
                return jsonify({"ok": False, "error": "invalid_status"}), 400
        else:
            new_status = original_status

        original_notes = str(record.get("internal_notes", "")).strip()
        new_notes = str(request.form.get("internal_notes", original_notes)).strip()
        original_badges = _normalize_professional_badges(record.get("badges", []))
        original_photo_url = str(record.get("photo_url", "")).strip()
        original_logo_url = str(record.get("logo_url", "")).strip()
        new_featured = request.form.get("featured") in {"1", "true", "yes", "on"}
        new_badges = _normalize_professional_badges(request.form.get("badges", original_badges))
        new_photo_url = str(request.form.get("photo_url", original_photo_url)).strip()
        new_logo_url = str(request.form.get("logo_url", original_logo_url)).strip()

        if new_status != original_status:
            record["status"] = new_status
            _append_professional_timeline_event(
                record,
                "PROFESSIONAL_APPLICATION_STATUS_UPDATED",
                f"Status changed from {_professional_status_label(original_status)} to {_professional_status_label(new_status)}",
                new_notes or record.get("email", ""),
                status=new_status,
            )

        record["internal_notes"] = new_notes
        record["featured"] = new_featured
        record["badges"] = new_badges
        record["photo_url"] = new_photo_url
        record["logo_url"] = new_logo_url
        updated = True
        break

    if not updated:
        return jsonify({"ok": False, "error": "not_found"}), 404

    _save_professional_applications(applications)
    return redirect(url_for("admin_professional_detail", application_id=application_id))

@app.get("/admin")
@admin_required
def admin_home():
    dashboard = _build_admin_dashboard()
    return render_template("admin_home.html", **dashboard)
if __name__ == "__main__":
    app.run(debug=True, port=5010)




