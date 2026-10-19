# Docker deployment

Runs the site and the API on one Linux machine, each in its own container, and publishes them through this project's own Cloudflare Tunnel.

```
internet ──HTTPS──> Cloudflare ──tunnel──> campus-alert-tunnel ──> campus-alert-web (Caddy) ─┬─ /          static site
                                                                                             └─ /api/*   campus-alert-api (Flask + SQLite)
```

- Compose project name `campus-alert`; containers are prefixed `campus-alert-`; network `campus-alert_default`.
- Nothing listens publicly. The only host port is `127.0.0.1:8100` (change with `WEB_PORT`), for checks from the machine itself.
- Resource limits: API 512 MB / 0.5 CPU, web 128 MB / 0.25 CPU, tunnel 128 MB / 0.25 CPU.
- Logs rotate at 10 MB × 3 per container.

## Folder layout

Secrets and data stay **outside** the git checkout, so `git pull` never touches them:

```
<base>/
  app/        git clone of this repo   (compose file: app/deploy/docker-compose.yml)
  secrets/    backend.env, tunnel.env  (chmod 600)
  data/       reportsdstate.db, backups/
```

## secrets/backend.env

Generate on the server. Never paste keys into chat or commit them.

```bash
( umask 077; f=secrets/backend.env; if [ -e "$f" ]; then echo "$f exists, not overwriting"; else cat > "$f" <<EOF
APP_ENV=production
SECRET_KEY=$(openssl rand -hex 32)
JWT_SECRET_KEY=$(openssl rand -hex 32)
DATA_HMAC_KEY=$(openssl rand -hex 32)
DATA_ENCRYPTION_KEY=$(openssl rand -base64 32 | tr '+/' '-_')
MAIL_BACKEND=console
DEMO_MODE=true
DEMO_CALL_NUMBER=+16055550100
TRUSTED_PROXIES=2
CORS_ORIGINS=https://your-hostname.example.com
EOF
echo "created $f"; fi; ls -l secrets )
```

`TRUSTED_PROXIES=2` matches the two hops (cloudflared, then Caddy), so rate limits see the real client IP.

**Back up `DATA_ENCRYPTION_KEY` and `DATA_HMAC_KEY`** somewhere off the server. Without them, reporter IDs in the database and backups can't be read.

## secrets/tunnel.env

Create a **new** tunnel for this project in the Cloudflare dashboard (Zero Trust → Networks → Tunnels → Create → Cloudflared → Docker). Add a public hostname that points to `http://web:80`. Copy the token into the file with an editor (not on the command line):

```
TUNNEL_TOKEN=<token>
```

## Start / update

```bash
cd <base>/app/deploy
HOST_UID=$(id -u) HOST_GID=$(id -g) docker compose up -d --build
docker compose ps
curl -s http://127.0.0.1:8100/api/v1/health
```

Update after new commits on `main`:

```bash
cd <base>/app && git pull --ff-only && cd deploy && \
  docker compose exec -T api flask --app wsgi backup-db && \
  HOST_UID=$(id -u) HOST_GID=$(id -g) docker compose up -d --build
```

The API container runs migrations and loads the resource directory on every start (both are safe to repeat).

## Backups

```bash
docker compose -p campus-alert exec -T api flask --app wsgi backup-db --keep 14   # -> data/backups/
docker compose -p campus-alert exec -T api flask --app wsgi prune-db
```

Restore: stop the API (`docker compose stop api`), then run
`docker compose run --rm api flask --app wsgi restore-db /app/instance/backups/<file> --yes`,
then `docker compose up -d api`.

## Remove everything

```bash
cd <base>/app/deploy && docker compose down
docker image rm campus-alert-api:latest campus-alert-web:latest
# then delete <base> (app, secrets, data) and any cron lines for this project
```
