from flask import Flask, jsonify, render_template

app = Flask(__name__)


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
