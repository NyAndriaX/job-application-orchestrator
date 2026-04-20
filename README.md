# Job Application Orchestrator

This project initializes a Python stack with Flask + Playwright for future multi-platform job automation.

For now, it only does one action:
- Navigate to `https://asako.mg/`.

## Stack

- Python
- Flask (API)
- Playwright (browser automation)

## Project structure

```text
job-application-orchestrator/
├── app/
│   ├── __init__.py
│   ├── routes.py
│   └── services/
│       └── browser_service.py
├── requirements.txt
└── run.py
```

## Quick start

1. Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
playwright install chromium
```

3. Run the API:

```bash
python run.py
```

4. Test endpoints:

- Health check:

```bash
curl http://127.0.0.1:5055/
```

- Trigger Asako navigation:

```bash
curl -X POST http://127.0.0.1:5055/navigate/asako
```

## Notes

- There is no UI design yet, only API endpoints.
- Browser logic is isolated in `app/services/browser_service.py` so you can extend it later for other platforms.
