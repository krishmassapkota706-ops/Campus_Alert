from flask import Blueprint, current_app

bp = Blueprint("health", __name__)


@bp.get("/health")
def health():
    return {"status": "ok", "environment": current_app.config["APP_ENV"]}
