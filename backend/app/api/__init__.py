"""Versioned REST API. Every blueprint is mounted under ``/api/v1``."""

from flask import Blueprint, Flask

from . import health

API_PREFIX = "/api/v1"


def register_blueprints(app: Flask) -> None:
    api = Blueprint("api", __name__, url_prefix=API_PREFIX)
    api.register_blueprint(health.bp)
    app.register_blueprint(api)
