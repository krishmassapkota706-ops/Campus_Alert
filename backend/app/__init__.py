"""ReportSDState backend: Flask application factory."""

from flask import Flask
from flask_cors import CORS

from .api import API_PREFIX, register_blueprints
from .config import Config, get_config
from .errors import register_error_handlers


def create_app(config: type[Config] | None = None) -> Flask:
    config = config or get_config()
    config.validate()

    app = Flask(__name__)
    app.config.from_object(config)
    app.json.sort_keys = False

    CORS(app, resources={API_PREFIX + "/*": {"origins": app.config["CORS_ORIGINS"]}})

    register_error_handlers(app)
    register_blueprints(app)
    return app
