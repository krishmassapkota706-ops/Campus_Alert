"""One-time location sharing: ``/api/v1/location``."""

from flask import Blueprint
from flask_jwt_extended import current_user, get_jwt_identity, jwt_required, verify_jwt_in_request
from flask_limiter.util import get_remote_address
from pydantic import Field, StrictBool, field_validator

from ..extensions import limiter
from ..services import contacts as contacts_service
from ..services import location as service
from ..validation import Schema, parse_body

bp = Blueprint("location", __name__, url_prefix="/location")


def _per_user() -> str:
    verify_jwt_in_request(optional=True)
    identity = get_jwt_identity()
    return f"user:{identity}" if identity else get_remote_address()


class ShareBody(Schema):
    contact_id: int
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    # Must be JSON true (not 1 or "yes"): the app shows the recipient and the user taps "Send".
    confirmed: StrictBool

    @field_validator("confirmed")
    @classmethod
    def _must_confirm(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("Confirm the recipient before sending your location.")
        return value


@bp.post("/share")
@jwt_required()
@limiter.limit("5 per minute;20 per hour", key_func=_per_user)
def share():
    body = parse_body(ShareBody)
    contact = contacts_service.get_contact(current_user, body.contact_id)
    return service.share_location(current_user, contact, body.latitude, body.longitude)
