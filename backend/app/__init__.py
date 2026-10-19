"""ReportSDState backend: Flask application factory."""

import os

from flask import Flask
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix

from . import models  # noqa: F401  (register tables with SQLAlchemy)
from .api import API_PREFIX, register_blueprints
from .cli import register_cli
from .config import Config, get_config
from .errors import register_error_handlers
from .extensions import db, limiter, migrate
from .models.types import render_alembic_item
from .security.auth import init_jwt
from .security.crypto import FieldCipher
from .services.mailer import init_mailer
from .services.sms import init_sms


def create_app(config: type[Config] | None = None) -> Flask:
    config = config or get_config()
    config.validate()

    app = Flask(__name__)
    app.config.from_object(config)
    app.json.sort_keys = False
    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)
    # Batch mode lets Alembic alter SQLite tables (it copies and recreates them).
    migrate.init_app(app, db, render_as_batch=True, render_item=render_alembic_item)
    app.extensions["field_cipher"] = FieldCipher(
        app.config["DATA_ENCRYPTION_KEY"], app.config["DATA_HMAC_KEY"]
    )
    init_jwt(app)
    limiter.init_app(app)
    init_mailer(app)
    init_sms(app)
    CORS(app, resources={API_PREFIX + "/*": {"origins": app.config["CORS_ORIGINS"]}})

    register_error_handlers(app)
    register_blueprints(app)
    register_cli(app)
    _add_security_headers(app)

    if proxies := app.config["TRUSTED_PROXIES"]:
        # Each proxy appends to X-Forwarded-For, so trust that many hops. Proto and host are
        # passed through unchanged by the chain, so only the last value is used.
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=proxies, x_proto=1, x_host=1)
    return app


def _add_security_headers(app: Flask) -> None:
    production = app.config["APP_ENV"] == "production"

    @app.after_request
    def set_headers(response):
        headers = response.headers
        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("X-Frame-Options", "DENY")
        headers.setdefault("Referrer-Policy", "no-referrer")
        headers.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
        # API responses can contain personal data; don't let devices or proxies cache them.
        headers.setdefault("Cache-Control", "no-store")
        if production:
            headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response
