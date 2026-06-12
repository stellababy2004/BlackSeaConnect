from datetime import datetime, timezone
from email.message import EmailMessage
import hashlib
import hmac
from functools import wraps
from pathlib import Path
import json
import os
import smtplib
from threading import Thread
from uuid import uuid4

from flask import Flask, Response, jsonify, redirect, render_template, request, url_for

app = Flask(__name__)
app.json.ensure_ascii = False


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


def _send_pilot_request_email(record):
    smtp_host = os.getenv("SMTP_HOST", "").strip()
    smtp_port_raw = os.getenv("SMTP_PORT", "").strip()
    smtp_username = os.getenv("SMTP_USERNAME", "").strip()
    smtp_password = os.getenv("SMTP_PASSWORD", "").strip()
    smtp_from = os.getenv("SMTP_FROM", "").strip()
    smtp_to = os.getenv("PILOT_REQUEST_TO", "").strip() or "concierge@blackseaconnect.com"

    if not smtp_host or not smtp_port_raw or not smtp_from:
        app.logger.warning("Pilot request email skipped: SMTP configuration is missing.")
        return False, "smtp_not_configured"

    try:
        smtp_port = int(smtp_port_raw)
    except ValueError:
        app.logger.warning("Pilot request email skipped: SMTP_PORT is invalid.")
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
        app.logger.warning("Pilot request email send failed: %s", exc)
        return False, "smtp_send_failed"

    return True, None


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
    normalized["status"] = str(normalized.get("status", "")).strip() or "new"
    normalized.setdefault("name", "")
    normalized.setdefault("email", "")
    normalized.setdefault("property_type", "")
    normalized.setdefault("apartment_count", "")
    normalized.setdefault("city", normalized.get("location", ""))
    normalized.setdefault("concierge_needs", normalized.get("needs", ""))
    normalized.setdefault("current_language", "")
    normalized.setdefault("submitted_from", "")
    normalized.setdefault("created_at", "")
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
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "name": _clean_payload_value(payload, "name"),
        "email": _clean_payload_value(payload, "email"),
        "property_type": _clean_payload_value(payload, "property_type"),
        "apartment_count": _clean_payload_value(payload, "apartment_count"),
        "city": _clean_payload_value(payload, "city", "location", "region"),
        "concierge_needs": _clean_payload_value(payload, "concierge_needs", "needs"),
        "current_language": _clean_payload_value(payload, "current_language"),
        "submitted_from": request.referrer or request.headers.get("Referer", "") or request.path,
        "status": "new",
    }
    record["location"] = record["city"]
    record["needs"] = record["concierge_needs"]

    required = ["property_type", "apartment_count", "city", "concierge_needs", "email"]
    missing = [field for field in required if not record.get(field, "").strip()]

    if missing:
        return jsonify({"ok": False, "error": "missing_fields"}), 400

    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)

    try:
        with (data_dir / "pilot_requests.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        app.logger.exception("Pilot request save failed.")
        return jsonify({"ok": False, "error": "save_failed"}), 500

    _queue_pilot_request_email(record)

    return jsonify({"ok": True}), 200


@app.get("/admin/pilot-requests")
@admin_required
def admin_pilot_requests():
    return render_template("admin_pilot_requests.html", requests=_load_pilot_requests())


@app.get("/admin/pilot-requests/<request_id>")
@admin_required
def admin_pilot_request_detail(request_id):
    record = _find_pilot_request(request_id)
    if not record:
        return jsonify({"ok": False, "error": "not_found"}), 404

    return render_template("admin_pilot_request_detail.html", item=record)


@app.post("/admin/pilot-requests/<request_id>/status")
@admin_required
def admin_pilot_request_status(request_id):
    allowed_statuses = {"new", "contacted", "qualified", "rejected", "converted"}
    status = str(request.form.get("status", "")).strip()

    if status not in allowed_statuses:
        return jsonify({"ok": False, "error": "invalid_status"}), 400

    requests_list = _load_pilot_requests()
    updated = False

    for record in requests_list:
        if str(record.get("id", "")) == str(request_id):
            record["status"] = status
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
    path = Path("data") / "concierge_requests.jsonl"
    requests_list = []

    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    requests_list.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    requests_list = list(reversed(requests_list))

    return render_template("admin_concierge_requests.html", requests=requests_list)

@app.get("/admin")
@admin_required
def admin_home():
    return render_template("admin_home.html")
if __name__ == "__main__":
    app.run(debug=True, port=5010)




