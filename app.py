from datetime import datetime
from typing import Any, Dict, List

from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

# Simple in-memory store for received payloads.
records: List[Dict[str, Any]] = []

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


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html", records=reversed(records))


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
    records.append(record)

    return jsonify({"message": "Payload received successfully", "record": record}), 201


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
