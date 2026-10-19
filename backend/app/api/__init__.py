"""Versioned REST API. Every blueprint is mounted under ``/api/v1``."""

from flask import Blueprint, Flask

from . import auth, contacts, health, me

API_PREFIX = "/api/v1"


def register_blueprints(app: Flask) -> None:
    api = Blueprint("api", __name__, url_prefix=API_PREFIX)
    for module in (health, auth, me, contacts):
        api.register_blueprint(module.bp)
    app.register_blueprint(api)
