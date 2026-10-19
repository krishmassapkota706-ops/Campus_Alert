"""Authentication endpoints: ``/api/v1/auth/*``."""

from flask import Blueprint
from flask_jwt_extended import current_user, get_jwt, jwt_required
from pydantic import Field, field_validator

from ..extensions import limiter
from ..services import auth as service
from ..validation import Schema, parse_body

bp = Blueprint("auth", __name__, url_prefix="/auth")

# Brute-force protection on every unauthenticated endpoint (per client IP).
STRICT = "5 per minute;20 per hour"
NORMAL = "10 per minute;100 per hour"


class _EmailBody(Schema):
    email: str = Field(max_length=254)

    @field_validator("email")
    @classmethod
    def _normalize(cls, value: str) -> str:
        return service.normalize_email(value)


class RegisterBody(Schema):
    email: str = Field(max_length=254)
    password: str
    name: str = Field(min_length=1, max_length=100)

    @field_validator("email")
    @classmethod
    def _sdsu_email(cls, value: str) -> str:
        return service.check_sdsu_email(value)

    @field_validator("password")
    @classmethod
    def _password(cls, value: str) -> str:
        return service.check_password_rules(value)


class CodeBody(_EmailBody):
    code: str = Field(pattern=r"^\d{6}$")


class LoginBody(_EmailBody):
    password: str = Field(min_length=1, max_length=service.PASSWORD_MAX_LENGTH)


class ResetBody(CodeBody):
    new_password: str

    @field_validator("new_password")
    @classmethod
    def _password(cls, value: str) -> str:
        return service.check_password_rules(value)


@bp.post("/register")
@limiter.limit(STRICT)
def register():
    body = parse_body(RegisterBody)
    user = service.register(body.email, body.password, body.name)
    return {
        "user": user.to_dict(),
        "message": f"We sent a 6-digit verification code to {user.email}.",
    }, 201


@bp.post("/verify-email")
@limiter.limit(NORMAL)
def verify_email():
    body = parse_body(CodeBody)
    user = service.verify_email(body.email, body.code)
    return {**service.issue_tokens(user), "user": user.to_dict()}


@bp.post("/resend-verification")
@limiter.limit(STRICT)
def resend_verification():
    body = parse_body(_EmailBody)
    service.resend_verification(body.email)
    return {"message": "If that account still needs verification, we sent a new code."}, 202


@bp.post("/login")
@limiter.limit(NORMAL)
def login():
    body = parse_body(LoginBody)
    user = service.authenticate(body.email, body.password)
    return {**service.issue_tokens(user), "user": user.to_dict()}


@bp.post("/refresh")
@jwt_required(refresh=True)
def refresh():
    return service.refresh_access_token(current_user, get_jwt()["jti"])


@bp.post("/logout")
@jwt_required(verify_type=False)
def logout():
    service.logout(get_jwt())
    return "", 204


@bp.post("/forgot-password")
@limiter.limit(STRICT)
def forgot_password():
    body = parse_body(_EmailBody)
    service.request_password_reset(body.email)
    return {"message": "If an account exists for that email, we sent a reset code."}, 202


@bp.post("/reset-password")
@limiter.limit(NORMAL)
def reset_password():
    body = parse_body(ResetBody)
    service.reset_password(body.email, body.code, body.new_password)
    return {"message": "Password updated. Please sign in again."}
