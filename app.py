from datetime import datetime, timezone
from pathlib import Path
import json

from flask import Flask, jsonify, render_template, request

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


if __name__ == "__main__":
    app.run(debug=True, port=5010)

@app.post("/api/pilot-request")
def api_pilot_request():
    payload = request.get_json(silent=True) or {}

    required = ["name", "email", "property_type", "location", "apartment_count", "needs"]
    missing = [field for field in required if not str(payload.get(field, "")).strip()]

    if missing:
        return jsonify({"ok": False, "error": "missing_fields", "missing": missing}), 400

    record = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "name": payload.get("name", "").strip(),
        "email": payload.get("email", "").strip(),
        "property_type": payload.get("property_type", "").strip(),
        "location": payload.get("location", "").strip(),
        "apartment_count": payload.get("apartment_count", "").strip(),
        "needs": payload.get("needs", "").strip(),
    }

    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)

    with (data_dir / "pilot_requests.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return jsonify({"ok": True, "message": "Pilot request received"})

@app.get("/admin/pilot-requests")
def admin_pilot_requests():
    path = Path("data") / "pilot_requests.jsonl"
    requests_list = []

    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    requests_list.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    requests_list = list(reversed(requests_list))

    return render_template("admin_pilot_requests.html", requests=requests_list)

