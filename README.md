# Flask Weighment Receiver

This project exposes an endpoint to receive weighment payloads from an external source and displays all received data on a web page.

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
   - `http://localhost:5000`

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
