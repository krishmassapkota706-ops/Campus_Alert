"""Emergency configuration and actions: ``/api/v1/emergency``."""

from flask import Blueprint
from flask_jwt_extended import current_user, jwt_required

from ..errors import ValidationError
from ..models import EmergencyAction
from ..services import contacts as contacts_service
from ..services import emergency as service
from ..validation import Schema, parse_body

bp = Blueprint("emergency", __name__, url_prefix="/emergency")


class EventBody(Schema):
    action: EmergencyAction
    contact_id: int | None = None


@bp.get("/config")
def config():
    """Public: numbers, the 911 notice, and whether demo mode is on."""
    return service.emergency_config()


@bp.post("/events")
@jwt_required()
def create_event():
    body = parse_body(EventBody)
    contact_phone = None
    if body.action is EmergencyAction.CALL_CONTACT:
        if body.contact_id is None:
            raise ValidationError({"contact_id": "Choose which emergency contact to call."})
        contact_phone = contacts_service.get_contact(current_user, body.contact_id).phone
    elif body.contact_id is not None:
        raise ValidationError({"contact_id": "Only used with call_contact."})
    return service.record_event(current_user, body.action, contact_phone), 201
