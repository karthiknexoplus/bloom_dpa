import os
import sqlite3
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urlencode

from flask import Flask, flash, g, jsonify, redirect, render_template, request, send_file, session, url_for

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "change-me-in-production")
app.config["DATABASE"] = str(Path(__file__).resolve().parent / "weighment.db")
app.config["APP_TITLE"] = "Bloom Weighment"
app.config["APP_USER"] = os.getenv("APP_USER", "admin")
app.config["APP_PASSWORD"] = os.getenv("APP_PASSWORD", "admin123")
app.config["LOGIN_BG_PATH"] = str(Path(__file__).resolve().parent / "csm_harbour-intercom-header_188d0b7581.png")

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


def log_incoming_request(
    db: sqlite3.Connection,
    status: str,
    payload_raw: str,
    error_message: str = "",
) -> None:
    db.execute(
        """
        INSERT INTO incoming_requests (endpoint, method, remote_addr, user_agent, payload_raw, status, error_message, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            request.path,
            request.method,
            request.remote_addr,
            request.user_agent.string if request.user_agent else "",
            payload_raw,
            status,
            error_message,
            datetime.utcnow().isoformat() + "Z",
        ),
    )


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
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS incoming_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            endpoint TEXT NOT NULL,
            method TEXT NOT NULL,
            remote_addr TEXT,
            user_agent TEXT,
            payload_raw TEXT,
            status TEXT NOT NULL,
            error_message TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS cgp_receipts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cgp_no TEXT,
            vehicle_regd_no TEXT,
            status_name TEXT,
            operation_type TEXT,
            requesting_party_name TEXT,
            cgp_approved_dt TEXT,
            payload_raw TEXT NOT NULL,
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


def parse_pagination() -> tuple[int, int]:
    page = request.args.get("page", default=1, type=int) or 1
    per_page = request.args.get("per_page", default=25, type=int) or 25
    if page < 1:
        page = 1
    if per_page < 1:
        per_page = 25
    if per_page > 100:
        per_page = 100
    return page, per_page


def date_range_filters(from_date: str, to_date: str, column_name: str) -> tuple[List[str], List[Any]]:
    clauses: List[str] = []
    params: List[Any] = []
    if from_date:
        clauses.append(f"{column_name} >= ?")
        params.append(f"{from_date}T00:00:00Z")
    if to_date:
        clauses.append(f"{column_name} <= ?")
        params.append(f"{to_date}T23:59:59.999999Z")
    return clauses, params


def pagination_links(base_endpoint: str, page: int, total_pages: int, params: Dict[str, Any]) -> Dict[str, str | None]:
    def build_url(target_page: int) -> str:
        q = dict(params)
        q["page"] = target_page
        return f"{url_for(base_endpoint)}?{urlencode(q)}"

    return {
        "prev": build_url(page - 1) if page > 1 else None,
        "next": build_url(page + 1) if page < total_pages else None,
    }


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
    cgp_rows = db.execute(
        """
        SELECT id, cgp_no, vehicle_regd_no, status_name, operation_type, requesting_party_name, received_at
        FROM cgp_receipts
        ORDER BY id DESC
        LIMIT 10
        """
    ).fetchall()
    counts = db.execute(
        """
        SELECT
          (SELECT COUNT(*) FROM weighments) AS weighment_count,
          (SELECT COUNT(*) FROM cgp_receipts) AS cgp_count
        """
    ).fetchone()
    return render_template(
        "dashboard.html",
        records=rows,
        cgp_records=cgp_rows,
        weighment_count=counts["weighment_count"],
        cgp_count=counts["cgp_count"],
        app_title=app.config["APP_TITLE"],
    )


@app.route("/incoming-requests", methods=["GET"])
@login_required
def incoming_requests():
    db = get_db()
    page, per_page = parse_pagination()
    from_date = (request.args.get("from_date") or "").strip()
    to_date = (request.args.get("to_date") or "").strip()
    status = (request.args.get("status") or "").strip()

    clauses, params = date_range_filters(from_date, to_date, "created_at")
    if status:
        clauses.append("status = ?")
        params.append(status)

    where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    total = db.execute(
        f"SELECT COUNT(*) FROM incoming_requests {where_clause}",
        tuple(params),
    ).fetchone()[0]
    total_pages = max(1, (total + per_page - 1) // per_page)
    if page > total_pages:
        page = total_pages
    offset = (page - 1) * per_page

    rows = db.execute(
        f"""
        SELECT id, endpoint, method, remote_addr, user_agent, payload_raw, status, error_message, created_at
        FROM incoming_requests
        {where_clause}
        ORDER BY id DESC
        LIMIT ? OFFSET ?
        """,
        (*params, per_page, offset),
    ).fetchall()
    query_params = {
        "from_date": from_date,
        "to_date": to_date,
        "status": status,
        "per_page": per_page,
    }
    links = pagination_links("incoming_requests", page, total_pages, query_params)
    return render_template(
        "incoming_requests.html",
        records=rows,
        app_title=app.config["APP_TITLE"],
        filters=query_params,
        page=page,
        per_page=per_page,
        total=total,
        total_pages=total_pages,
        prev_url=links["prev"],
        next_url=links["next"],
    )


@app.route("/cgp-records", methods=["GET"])
@login_required
def cgp_records():
    db = get_db()
    page, per_page = parse_pagination()
    from_date = (request.args.get("from_date") or "").strip()
    to_date = (request.args.get("to_date") or "").strip()
    search = (request.args.get("search") or "").strip()

    clauses, params = date_range_filters(from_date, to_date, "received_at")
    if search:
        clauses.append("(cgp_no LIKE ? OR vehicle_regd_no LIKE ? OR requesting_party_name LIKE ?)")
        like = f"%{search}%"
        params.extend([like, like, like])

    where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    total = db.execute(
        f"SELECT COUNT(*) FROM cgp_receipts {where_clause}",
        tuple(params),
    ).fetchone()[0]
    total_pages = max(1, (total + per_page - 1) // per_page)
    if page > total_pages:
        page = total_pages
    offset = (page - 1) * per_page

    rows = db.execute(
        f"""
        SELECT id, cgp_no, vehicle_regd_no, status_name, operation_type, requesting_party_name,
               cgp_approved_dt, payload_raw, received_at
        FROM cgp_receipts
        {where_clause}
        ORDER BY id DESC
        LIMIT ? OFFSET ?
        """,
        (*params, per_page, offset),
    ).fetchall()
    query_params = {
        "from_date": from_date,
        "to_date": to_date,
        "search": search,
        "per_page": per_page,
    }
    links = pagination_links("cgp_records", page, total_pages, query_params)
    return render_template(
        "cgp_records.html",
        records=rows,
        app_title=app.config["APP_TITLE"],
        filters=query_params,
        page=page,
        per_page=per_page,
        total=total,
        total_pages=total_pages,
        prev_url=links["prev"],
        next_url=links["next"],
    )


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


@app.route("/login-background", methods=["GET"])
def login_background():
    bg_path = Path(app.config["LOGIN_BG_PATH"])
    if not bg_path.exists():
        return ("Background image not found", 404)
    return send_file(bg_path)


@app.route("/api/weighment", methods=["POST"])
def receive_weighment():
    db = get_db()
    payload_raw = request.get_data(cache=True, as_text=True) or ""
    payload = request.get_json(silent=True)
    if not payload:
        log_incoming_request(db, "invalid_json", payload_raw, "Invalid or missing JSON payload")
        db.commit()
        return jsonify({"error": "Invalid or missing JSON payload"}), 400

    missing_fields = [field for field in REQUIRED_FIELDS if field not in payload]
    if missing_fields:
        log_incoming_request(
            db,
            "missing_fields",
            payload_raw,
            "Missing required fields: " + ",".join(missing_fields),
        )
        db.commit()
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
    log_incoming_request(db, "success", payload_raw)
    db.commit()

    return jsonify({"message": "Payload received successfully", "record": record}), 201


@app.route("/ebs/cgp", methods=["POST"])
def receive_cgp():
    db = get_db()
    payload_raw = request.get_data(cache=True, as_text=True) or ""
    payload = request.get_json(silent=True)
    if not payload:
        log_incoming_request(db, "invalid_json", payload_raw, "Invalid or missing JSON payload")
        db.commit()
        return jsonify({"error": "Invalid or missing JSON payload"}), 400

    cgp_details = payload.get("CGPDetails")
    if not isinstance(cgp_details, dict):
        log_incoming_request(db, "missing_cgpdetails", payload_raw, "CGPDetails object is required")
        db.commit()
        return jsonify({"error": "CGPDetails object is required"}), 400

    received_at = datetime.utcnow().isoformat() + "Z"
    db.execute(
        """
        INSERT INTO cgp_receipts (
            cgp_no, vehicle_regd_no, status_name, operation_type, requesting_party_name,
            cgp_approved_dt, payload_raw, received_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            cgp_details.get("CGPNo"),
            cgp_details.get("VehicleRegdNo"),
            cgp_details.get("StatusName"),
            cgp_details.get("OperationType"),
            cgp_details.get("RequestingPartyName"),
            cgp_details.get("CGPApprovedDT"),
            payload_raw,
            received_at,
        ),
    )
    log_incoming_request(db, "success", payload_raw)
    db.commit()

    return jsonify({"message": "CGP payload received successfully", "received_at": received_at}), 201


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
