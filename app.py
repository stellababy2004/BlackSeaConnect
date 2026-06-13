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
from threading import Thread
from uuid import uuid4

from flask import Flask, Response, jsonify, redirect, render_template, request, url_for

app = Flask(__name__)
app.json.ensure_ascii = False

PILOT_STATUS_VALUES = ("new", "contacted", "qualified", "converted", "lost")
PILOT_STATUS_ALIASES = {
    "rejected": "lost",
}


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


def _send_internal_pilot_notification(record, admin_detail_url):
    resend_api_key = os.getenv("RESEND_API_KEY", "").strip()
    from_email = os.getenv("FROM_EMAIL", "").strip() or "BlackSea Connect <onboarding@resend.dev>"
    admin_email = os.getenv("ADMIN_EMAIL", "").strip()

    if not resend_api_key:
        app.logger.warning("Internal pilot notification skipped: RESEND_API_KEY is missing.")
        return False, "resend_not_configured"

    if not admin_email:
        app.logger.warning("Internal pilot notification skipped: ADMIN_EMAIL is missing.")
        return False, "admin_email_missing"

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
    except Exception as exc:
        app.logger.warning("Internal pilot notification send failed via Resend: %s", exc)
        return False, "resend_send_failed"

    return True, None


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


def _build_admin_dashboard():
    pilot_requests = _load_pilot_requests()
    concierge_requests = _load_concierge_requests()
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
        "pipeline": [
            {"key": "new", "label": "New", "count": pilot_counts["new"]},
            {"key": "contacted", "label": "Contacted", "count": pilot_counts["contacted"]},
            {"key": "qualified", "label": "Qualified", "count": pilot_counts["qualified"]},
            {"key": "converted", "label": "Converted", "count": pilot_counts["converted"]},
            {"key": "lost", "label": "Lost", "count": pilot_counts["lost"]},
        ],
        "recent_activity": _admin_pilot_activity_feed(pilot_requests, concierge_requests),
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

@app.get("/admin")
@admin_required
def admin_home():
    dashboard = _build_admin_dashboard()
    return render_template("admin_home.html", **dashboard)
if __name__ == "__main__":
    app.run(debug=True, port=5010)




