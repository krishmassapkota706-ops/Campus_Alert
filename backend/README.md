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
flask --app wsgi seed-db      # synthetic demo accounts/reports + SDSU resource directory
flask --app wsgi run --debug
```

Seeded accounts (synthetic, development only): `demo.student@jacks.sdstate.edu` and `demo.maintainer@jacks.sdstate.edu`, password from `SEED_DEMO_PASSWORD` in `.env`.

Check it's running: <http://localhost:5000/api/v1/health>

In development, verification and password-reset emails are printed to the server log (`MAIL_BACKEND=console`) so you can copy the code.

See [API.md](API.md) for every endpoint, request body, and response.

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
    security/       JWT setup, role_required, field-level encryption
    services/       business logic (auth, mailer) called by the API routes
    data/           resources.json (SDSU resource directory, with sources)
    cli.py          init-db / seed-db / seed-resources commands
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
| `verification_codes` | Email-verification and password-reset codes | Only a keyed hash of the code is stored. 15-minute expiry, 5 attempts. |
| `revoked_tokens` | JWT IDs revoked by logout | Safe to prune after `expires_at`. |
| `resources` | Public SDSU and crisis contacts | Loaded from `app/data/resources.json`; each entry records its source URL and date checked. |
| `emergency_events` | An emergency call button was used | Action + timestamp only; user stored encrypted. No location. |
| `reports` | Submitted reports | Reporter stored only as `reporter_ref_enc` (Fernet ciphertext) and `reporter_ref_idx` (HMAC blind index for "my reports"). No plain user ID. |

All timestamps are stored in UTC and returned as ISO-8601 with a `Z` suffix.

## Demo mode

`DEMO_MODE=true` (the default) swaps every number the app would dial for `DEMO_CALL_NUMBER`, so no real call reaches UPD, 911, or 988 during grading. Displayed numbers stay real. Set `DEMO_CALL_NUMBER` to a phone the team controls.

To update the resource directory, edit `app/data/resources.json` and run `flask --app wsgi seed-resources --replace`.
