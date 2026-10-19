#!/bin/sh
# Bring the database schema up to date and load the resource directory (only if empty),
# then start the server. Both steps are safe to run on every start.
set -e

export FLASK_APP=wsgi
flask init-db
flask seed-resources

exec "$@"
