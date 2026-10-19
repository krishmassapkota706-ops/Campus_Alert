# ReportSDState Backend

Flask REST API for the ReportSDState / CampusAlert prototype. The mobile app talks to it over JSON at `/api/v1`.

## Quick start

Requires Python 3.12+.

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
flask --app wsgi init-db      # create tables in backend/instance/reportsdstate.db
flask --app wsgi seed-db      # optional: synthetic demo accounts and reports
flask --app wsgi run --debug
```

Seeded accounts (synthetic, development only): `demo.student@jacks.sdstate.edu` and `demo.maintainer@jacks.sdstate.edu`, password from `SEED_DEMO_PASSWORD` in `.env`.

Check it's running: <http://localhost:5000/api/v1/health>

## Tests and linting

```bash
pytest
ruff check . && ruff format --check .
```

CI runs both on every pull request that touches `backend/` (see `.github/workflows/backend-ci.yml`).

## Project layout

```
backend/
  app/
    __init__.py     create_app() application factory
    config.py       settings read from environment variables
    errors.py       JSON error format + error handlers
    validation.py   pydantic request-body validation
    extensions.py   SQLAlchemy instance (SQLite foreign keys enabled)
    models/         users, emergency_contacts, reports
    security/       field-level encryption for reporter IDs
    cli.py          init-db / seed-db commands
    seed.py         synthetic demo data
    api/            versioned blueprints, mounted under /api/v1
  tests/            pytest suite
  wsgi.py           entry point (loads .env, builds the app)
```

## Error format

Every error response has the same shape:

```json
{ "error": { "code": "validation_error", "message": "Some fields are invalid.", "fields": { "email": "..." } } }
```

`fields` is only present on validation errors (HTTP 422). Unexpected errors return a generic `internal_error` and are logged server-side only.

## Configuration

All configuration comes from environment variables (see `.env.example`). In production (`APP_ENV=production`) the app refuses to start if a required secret is missing. Never commit `.env`.

## Data model

| Table | Purpose | Notes |
|---|---|---|
| `users` | Student / maintainer accounts | Passwords hashed (werkzeug scrypt). `role` is `student` or `maintainer`. |
| `emergency_contacts` | A user's saved contacts | Deleted with the user. Phone stored as E.164. |
| `reports` | Submitted reports | Reporter stored only as `reporter_ref_enc` (Fernet ciphertext) and `reporter_ref_idx` (HMAC blind index for "my reports"). No plain user ID. |

All timestamps are stored in UTC and returned as ISO-8601 with a `Z` suffix.
