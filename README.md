# Job Application Orchestrator

API Flask + Playwright pour l'auto-postulation sur plusieurs plateformes, sans intervention humaine.
Le projet inclut maintenant une authentification utilisateur via MongoDB (`register` / `login`).

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

3. Configurer MongoDB (optionnel si local par defaut):

```bash
export MONGODB_URI="mongodb://127.0.0.1:27017"
export MONGODB_DB_NAME="job_orchestrator"
```

4. Run the API:

```bash
python run.py
```

5. Test endpoints:

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
    "user_id": "USER_ID_FROM_REGISTER"
  }'
```

- Register utilisateur:

```bash
curl -X POST http://127.0.0.1:5000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "full_name": "Jean User",
    "email": "jean@example.com",
    "password": "Password123",
    "filters": ["cdi", "stage"]
  }'
```

- Login utilisateur:

```bash
curl -X POST http://127.0.0.1:5000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "jean@example.com",
    "password": "Password123"
  }'
```

- Lancer l'orchestration (payload minimal):

- Ajouter/configurer une plateforme pour l'utilisateur:

```bash
curl -X POST http://127.0.0.1:5000/users/platform-config \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "USER_ID_FROM_REGISTER",
    "platform": "asako",
    "auth": {
      "email": "jean@example.com",
      "password": "Password123"
    }
  }'
```

- Mettre a jour le profil utilisateur (filtres):

```bash
curl -X POST http://127.0.0.1:5000/users/profile \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "USER_ID_FROM_REGISTER",
    "filters": ["cdi", "stage"]
  }'
```

- Lancer l'orchestration (payload minimal):

```bash
curl -X POST http://127.0.0.1:5000/orchestrate \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "asako",
    "user_id": "USER_ID_FROM_REGISTER"
  }'
```

## Notes

- Pas d'inscription: uniquement authentification (`token` ou `email/password`).
- Inscription et configuration plateforme sont separees.
- `full_name`/`email` proviennent du compte utilisateur (pas de `profile` par plateforme).
- `filters` sont stockes dans le profil utilisateur, sous forme de tableau (`["cdi", "stage"]`).
- Plateformes actives: `asako`, `getyourjob` (alias accepte `getyourjob.pro`).
- Au premier login reussi, `session_storage` est enregistre en base pour reutilisation automatique.

## Postman

Des fichiers Postman sont disponibles dans le dossier `postman`:

- `postman/job-application-orchestrator.postman_collection.json`
- `postman/job-application-orchestrator.local.postman_environment.json`

Importez les deux fichiers dans Postman, puis lancez les requetes dans cet ordre:
1. `Auth - Register` (met automatiquement `user_id` en variable de collection)
2. `Users - Save Platform Config`
3. `Orchestrate - Asako`
