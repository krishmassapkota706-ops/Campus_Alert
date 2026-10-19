"""The signed-in user's own account: ``/api/v1/me``."""

from flask import Blueprint
from flask_jwt_extended import current_user, jwt_required

bp = Blueprint("me", __name__, url_prefix="/me")


@bp.get("")
@jwt_required()
def get_me():
    return current_user.to_dict()
