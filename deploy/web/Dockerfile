# Static site + reverse proxy. Build context is the repository root (see docker-compose.yml);
# only the three site files are copied, never the backend source or .git.
FROM caddy:2.8.4-alpine

COPY deploy/web/Caddyfile /etc/caddy/Caddyfile
COPY index.html app.js style.css /srv/site/
