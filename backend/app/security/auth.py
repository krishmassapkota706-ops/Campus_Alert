"""JWT configuration and authorization helpers.

Protect a route with ``@jwt_required()`` (any signed-in user) or
``@role_required(Role.MAINTAINER)``. Inside the route, ``current_user`` is the
``User`` row for the token.
"""

from functools import wraps

from flask import Flask, jsonify
from flask_jwt_extended import current_user, verify_jwt_in_request

from ..errors import Forbidden
from ..extensions import db, jwt
from ..models import Role, User
from ..services.auth import is_revoked


def _error(status: int, code: str, message: str):
    return jsonify(error={"code": code, "message": message}), status


def init_jwt(app: Flask) -> None:
    jwt.init_app(app)

    @jwt.user_identity_loader
    def _identity(user: User) -> str:
        return str(user.id)

    @jwt.additional_claims_loader
    def _claims(user: User) -> dict:
        return {"ver": user.token_version, "role": user.role.value}

    @jwt.user_lookup_loader
    def _lookup(_header, payload) -> User | None:
        return db.session.get(User, int(payload["sub"]))

    @jwt.token_in_blocklist_loader
    def _blocked(_header, payload) -> bool:
        user = db.session.get(User, int(payload["sub"]))
        if user is None or payload.get("ver") != user.token_version:
            return True
        if is_revoked(payload["jti"]):
            return True
        return bool(payload.get("rjti")) and is_revoked(payload["rjti"])

    @jwt.unauthorized_loader
    def _missing(_reason):
        return _error(401, "unauthorized", "Authentication is required.")

    @jwt.invalid_token_loader
    def _invalid(_reason):
        return _error(401, "invalid_token", "The access token is invalid.")

    @jwt.expired_token_loader
    def _expired(_header, _payload):
        return _error(401, "token_expired", "The access token has expired.")

    @jwt.revoked_token_loader
    def _revoked(_header, _payload):
        return _error(401, "token_revoked", "This session has ended. Please sign in again.")

    @jwt.user_lookup_error_loader
    def _no_user(_header, _payload):
        return _error(401, "invalid_token", "The access token is invalid.")


def role_required(*roles: Role):
    """Require a signed-in user whose role is one of ``roles``."""

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            if current_user.role not in roles:
                raise Forbidden()
            return fn(*args, **kwargs)

        return wrapper

    return decorator
