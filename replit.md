# Job Application Orchestrator

## Overview
A Python Flask API for multi-platform job application automation using Playwright for browser control.

## Tech Stack
- **Language**: Python 3.12
- **Framework**: Flask
- **Browser Automation**: Playwright (Chromium, headless)

## Project Structure
```
├── app/
│   ├── __init__.py          # Flask app factory
│   ├── routes.py            # API route definitions
│   ├── platforms/           # Platform-specific adapters
│   │   ├── asako/
│   │   │   ├── adapter.py
│   │   │   └── scraper.py
│   │   └── getyourjob/
│   │       ├── adapter.py
│   │       └── scraper.py
│   └── services/
│       └── orchestrator_service.py # Auto-apply orchestration
├── run.py                   # Entry point (runs on port 5000)
├── requirements.txt         # Python dependencies
└── README.md
```

## API Endpoints
- `GET /` — Health check
- `POST /orchestrate` — Authenticates and runs automated apply flow

## Running the App
```bash
pip install -r requirements.txt
playwright install chromium
python run.py
```

The server starts on `http://0.0.0.0:5000`.

## Workflow
- **Start application**: `python run.py` on port 5000
- **Trigger auto-apply**: `POST /orchestrate` with `platform`, `auth`, `profile`, `filters`
