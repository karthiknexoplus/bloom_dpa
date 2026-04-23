import os
import sqlite3
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Any, Dict, List

from flask import Flask, flash, g, jsonify, redirect, render_template, request, session, url_for

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "change-me-in-production")
app.config["DATABASE"] = str(Path(__file__).resolve().parent / "weighment.db")
app.config["APP_TITLE"] = "Bloom Weighment"
app.config["APP_USER"] = os.getenv("APP_USER", "admin")
app.config["APP_PASSWORD"] = os.getenv("APP_PASSWORD", "admin123")

REQUIRED_FIELDS = [
    "cha_agent_name",
    "material_name",
    "importer_name",
    "vessel_no",
    "vehicle_no",
    "tare_weight",
    "gross_weight",
    "net_weight",
    "weighment_datetime",
]


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
    return g.db


def init_db() -> None:
    db = get_db()
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS weighments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cha_agent_name TEXT NOT NULL,
            material_name TEXT NOT NULL,
            importer_name TEXT NOT NULL,
            vessel_no TEXT NOT NULL,
            vehicle_no TEXT NOT NULL,
            tare_weight REAL NOT NULL,
            gross_weight REAL NOT NULL,
            net_weight REAL NOT NULL,
            weighment_datetime TEXT NOT NULL,
            received_at TEXT NOT NULL
        )
        """
    )
    db.commit()


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped_view


@app.before_request
def before_request() -> None:
    init_db()


@app.teardown_appcontext
def close_db(exception) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


@app.route("/", methods=["GET"])
@login_required
def index():
    db = get_db()
    rows = db.execute(
        """
        SELECT id, cha_agent_name, material_name, importer_name, vessel_no, vehicle_no,
               tare_weight, gross_weight, net_weight, weighment_datetime, received_at
        FROM weighments
        ORDER BY id DESC
        """
    ).fetchall()
    return render_template("dashboard.html", records=rows, app_title=app.config["APP_TITLE"])


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        if username == app.config["APP_USER"] and password == app.config["APP_PASSWORD"]:
            session["logged_in"] = True
            session["username"] = username
            return redirect(url_for("index"))
        flash("Invalid username or password.", "danger")
    return render_template("login.html", app_title=app.config["APP_TITLE"])


@app.route("/logout", methods=["GET"])
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/api/weighment", methods=["POST"])
def receive_weighment():
    payload = request.get_json(silent=True)
    if not payload:
        return jsonify({"error": "Invalid or missing JSON payload"}), 400

    missing_fields = [field for field in REQUIRED_FIELDS if field not in payload]
    if missing_fields:
        return (
            jsonify(
                {
                    "error": "Missing required fields",
                    "missing_fields": missing_fields,
                }
            ),
            400,
        )

    record = {field: payload.get(field) for field in REQUIRED_FIELDS}
    record["received_at"] = datetime.utcnow().isoformat() + "Z"
    db = get_db()
    db.execute(
        """
        INSERT INTO weighments (
            cha_agent_name, material_name, importer_name, vessel_no, vehicle_no,
            tare_weight, gross_weight, net_weight, weighment_datetime, received_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record["cha_agent_name"],
            record["material_name"],
            record["importer_name"],
            record["vessel_no"],
            record["vehicle_no"],
            record["tare_weight"],
            record["gross_weight"],
            record["net_weight"],
            record["weighment_datetime"],
            record["received_at"],
        ),
    )
    db.commit()

    return jsonify({"message": "Payload received successfully", "record": record}), 201


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
