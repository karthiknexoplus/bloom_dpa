# Flask Weighment Receiver

This project exposes an endpoint to receive weighment payloads from an external source, stores every record in SQLite, and displays all data on a styled dashboard.

## API Endpoint

- Method: `POST`
- URL: `http://localhost:5000/api/weighment`
- Content-Type: `application/json`

Expected payload:

```json
{
  "cha_agent_name": "RCC Limited",
  "material_name": "Gypsum",
  "importer_name": "Parag Vinimay",
  "vessel_no": "Mv Lucky Anna",
  "vehicle_no": "GJ12CT8755",
  "tare_weight": 8200,
  "gross_weight": 16680,
  "net_weight": 8480,
  "weighment_datetime": "2026-04-23T07:45:10.000Z"
}
```

## Run Locally

1. Create and activate virtual environment:
   - macOS/Linux:
     - `python3 -m venv .venv`
     - `source .venv/bin/activate`
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Start server:
   - `python app.py`
4. Open dashboard:
   - `http://localhost:5000/login`

## Authentication

- Login URL: `http://localhost:5000/login`
- Default credentials:
  - Username: `admin`
  - Password: `admin123`
- Override with env vars:
  - `APP_USER`
  - `APP_PASSWORD`
  - `FLASK_SECRET_KEY`

## Database

- SQLite file: `weighment.db`
- Table: `weighments`
- Every successful `POST /api/weighment` is inserted into this table.
- Additional audit table: `incoming_requests` (stores raw payload + status + timestamp for every incoming API call)

## UI Tabs

- `Dashboard`: Shows stored weighment records
- `Incoming Data`: Shows API request audit trail with timestamp and payload

## Login Background Image

- Login page background is served from:
  - `csm_harbour-intercom-header_188d0b7581.png`
- Route used by CSS:
  - `/login-background`

## Linux Service + Logs (systemd)

### Single-file manager (recommended on GCP)

Use:

```bash
sudo bash bloom_manager.sh install
```

This one script installs apt packages, python dependencies, initializes SQLite, configures systemd + nginx, and starts the app.

Other commands:

```bash
sudo bash bloom_manager.sh status
sudo bash bloom_manager.sh restart
sudo bash bloom_manager.sh logs
```

It creates:

- Service: `bloom-weighment.service`
- Env file: `/etc/bloom-weighment.env`
- Logs: `/var/log/bloom_dpa/app.log`, `/var/log/bloom_dpa/error.log`, `/var/log/bloom_dpa/access.log`

### Manual service files (optional)

Service templates are also available in `deploy/systemd/`:

- `bloom-weighment.service`
- `bloom-weighment.env`
- `setup_service.sh`

Run setup on Linux server:

```bash
cd /opt/bloom_dpa
sudo bash deploy/systemd/setup_service.sh
```

Check logs:

```bash
tail -f /var/log/bloom_dpa/app.log
tail -f /var/log/bloom_dpa/error.log
```

## Test With cURL

```bash
curl -X POST http://localhost:5000/api/weighment \
  -H "Content-Type: application/json" \
  -d '{
    "cha_agent_name": "RCC Limited",
    "material_name": "Gypsum",
    "importer_name": "Parag Vinimay",
    "vessel_no": "Mv Lucky Anna",
    "vehicle_no": "GJ12CT8755",
    "tare_weight": 8200,
    "gross_weight": 16680,
    "net_weight": 8480,
    "weighment_datetime": "2026-04-23T07:45:10.000Z"
  }'
```
