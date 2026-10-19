# Deploying the backend (home server)

The proposal hosts the API and SQLite database on a team member's home server for development and the demo. This guide covers a single machine running Windows or Linux without containers.

**Using Docker?** Use [`deploy/README.md`](../deploy/README.md) instead. It runs the site, the API, and a Cloudflare Tunnel as one Compose project with resource limits.

## 1. Install

```bash
git clone https://github.com/krishmassapkota706-ops/Campus_Alert.git
cd Campus_Alert/backend
python -m venv .venv
# Windows: .venv\Scripts\activate    Linux: source .venv/bin/activate
pip install -r requirements.txt
```

## 2. Configure

Copy `.env.example` to `.env` and set at least:

| Variable | Value |
|---|---|
| `APP_ENV` | `production` |
| `SECRET_KEY`, `JWT_SECRET_KEY`, `DATA_HMAC_KEY` | Each `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `DATA_ENCRYPTION_KEY` | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `CORS_ORIGINS` | The app/web origins that call the API |
| `MAIL_BACKEND`, `SMTP_*`, `MAIL_FROM` | SMTP account for verification emails (or `console` for a closed demo) |
| `DEMO_MODE` | `true` for grading/demos (no real calls or texts) |
| `DEMO_CALL_NUMBER` | A phone the team controls |
| `TRUSTED_PROXIES` | `1` when behind Caddy/nginx/Cloudflare Tunnel |

The app refuses to start in production if any required secret is missing.

**Store `DATA_ENCRYPTION_KEY` and `DATA_HMAC_KEY` somewhere outside the server** (a password manager). Without them, reporter IDs in the database and in every backup can't be decrypted.

## 3. Create the database

```bash
flask --app wsgi init-db
flask --app wsgi seed-resources
# Demo only: flask --app wsgi seed-db
```

## 4. Run

```bash
python serve.py        # listens on HOST:PORT, default 127.0.0.1:5000
```

Keep `HOST=127.0.0.1` and put HTTPS in front. Two easy options:

**Caddy** (automatic HTTPS, needs ports 80/443 forwarded to the server):
```
api.example.com {
    reverse_proxy 127.0.0.1:5000
}
```

**Cloudflare Tunnel** (no port forwarding):
```bash
cloudflared tunnel --url http://127.0.0.1:5000
```

In both cases set `TRUSTED_PROXIES=1` so rate limits see the real client IP.

To keep the server running after reboots, use a Windows scheduled task ("At startup", run `.venv\Scripts\python.exe serve.py` in `backend\`) or a systemd service on Linux.

## 5. Backups (RD FR-3.6.6)

Schedule a daily backup and weekly cleanup.

Windows (Task Scheduler, run in `backend\`):
```
.venv\Scripts\flask.exe --app wsgi backup-db --keep 14
.venv\Scripts\flask.exe --app wsgi prune-db
```

Linux (crontab):
```
0 3 * * *  cd /srv/Campus_Alert/backend && .venv/bin/flask --app wsgi backup-db --keep 14
30 3 * * 0 cd /srv/Campus_Alert/backend && .venv/bin/flask --app wsgi prune-db
```

Copy `instance/backups/` off the machine regularly (cloud drive or USB). One server is a single point of failure (Risk R6).

## 6. Restore

1. Stop the server.
2. `flask --app wsgi restore-db instance/backups/reportsdstate-YYYYMMDD-HHMMSS.db`
   - The file is integrity-checked first, and the current database is saved as `instance/backups/pre-restore-*.db`.
3. `flask --app wsgi init-db` (applies any migrations newer than the backup).
4. Start the server and check `GET /api/v1/health`.

Test a restore at least once before the demo (TC-BACKUP-01).

## 7. Redeploy after merging changes

```bash
git pull
pip install -r requirements.txt
flask --app wsgi backup-db
flask --app wsgi init-db
# restart serve.py
python scripts/perf_check.py https://api.example.com
```
