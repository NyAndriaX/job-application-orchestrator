# Job Application Orchestrator

API Flask + Playwright pour l'auto-postulation sur plusieurs plateformes, sans intervention humaine.

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
│   ├── platforms/
│   │   ├── base.py
│   │   ├── registry.py
│   │   ├── asako/
│   │   │   ├── adapter.py
│   │   │   └── scraper.py
│   │   └── getyourjob/
│   │       ├── adapter.py
│   │       └── scraper.py
│   └── services/
│       └── orchestrator_service.py
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
curl http://127.0.0.1:5000/
```

- Lancer l'auto-postulation:

```bash
curl -X POST http://127.0.0.1:5000/orchestrate \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "asako",
    "mode": "auto_apply",
    "auth": { "email": "user@example.com", "password": "secret" },
    "profile": { "name": "Candidate", "email": "user@example.com" },
    "filters": { "job_type": "cdi" }
  }'
```

## Notes

- Pas d'inscription: uniquement authentification (`token` ou `email/password`).
- Plateformes actives: `asako`, `getyourjob` (alias accepte `getyourjob.pro`).
