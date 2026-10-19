"""Versioned REST API. Every blueprint is mounted under ``/api/v1``."""

from flask import Blueprint, Flask

from . import auth, contacts, emergency, health, location, me, reports, resources

API_PREFIX = "/api/v1"


def register_blueprints(app: Flask) -> None:
    api = Blueprint("api", __name__, url_prefix=API_PREFIX)
    for module in (health, auth, me, contacts, reports, resources, emergency, location):
        api.register_blueprint(module.bp)
    api.register_blueprint(reports.admin_bp)
    app.register_blueprint(api)
