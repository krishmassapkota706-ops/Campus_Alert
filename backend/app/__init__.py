"""ReportSDState backend: Flask application factory."""

import os

from flask import Flask
from flask_cors import CORS

from . import models  # noqa: F401  (register tables with SQLAlchemy)
from .api import API_PREFIX, register_blueprints
from .cli import register_cli
from .config import Config, get_config
from .errors import register_error_handlers
from .extensions import db, limiter
from .security.auth import init_jwt
from .security.crypto import FieldCipher
from .services.mailer import init_mailer


def create_app(config: type[Config] | None = None) -> Flask:
    config = config or get_config()
    config.validate()

    app = Flask(__name__)
    app.config.from_object(config)
    app.json.sort_keys = False
    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)
    app.extensions["field_cipher"] = FieldCipher(
        app.config["DATA_ENCRYPTION_KEY"], app.config["DATA_HMAC_KEY"]
    )
    init_jwt(app)
    limiter.init_app(app)
    init_mailer(app)
    CORS(app, resources={API_PREFIX + "/*": {"origins": app.config["CORS_ORIGINS"]}})

    register_error_handlers(app)
    register_blueprints(app)
    register_cli(app)
    return app
