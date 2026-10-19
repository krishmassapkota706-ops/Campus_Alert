"""The signed-in user's own account: ``/api/v1/me``."""

from flask import Blueprint
from flask_jwt_extended import current_user, jwt_required
from pydantic import Field, field_validator

from ..errors import ValidationError
from ..extensions import db, limiter
from ..services import auth as auth_service
from ..validation import PhoneNumber, Schema, parse_body

bp = Blueprint("me", __name__, url_prefix="/me")


class ProfilePatch(Schema):
    """Email and role can't be changed here: email is tied to SDSU verification."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    phone: PhoneNumber | None = None


class PasswordChange(Schema):
    current_password: str = Field(min_length=1, max_length=auth_service.PASSWORD_MAX_LENGTH)
    new_password: str

    @field_validator("new_password")
    @classmethod
    def _password(cls, value: str) -> str:
        return auth_service.check_password_rules(value)


@bp.get("")
@jwt_required()
def get_me():
    return current_user.to_dict()


@bp.patch("")
@jwt_required()
def update_me():
    changes = parse_body(ProfilePatch).model_dump(exclude_unset=True)
    if "name" in changes and changes["name"] is None:
        raise ValidationError({"name": "This field can't be empty."})
    for field, value in changes.items():
        setattr(current_user, field, value)  # phone may be null to remove it
    db.session.commit()
    return current_user.to_dict()


@bp.post("/password")
@jwt_required()
@limiter.limit("5 per minute")
def change_password():
    body = parse_body(PasswordChange)
    if not current_user.check_password(body.current_password):
        raise ValidationError({"current_password": "Current password is incorrect."})
    current_user.set_password(body.new_password)
    current_user.token_version += 1  # end other sessions
    db.session.commit()
    # Keep this device signed in with fresh tokens.
    return auth_service.issue_tokens(current_user)
