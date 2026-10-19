"""Emergency contacts for the signed-in user: ``/api/v1/contacts``."""

from flask import Blueprint
from flask_jwt_extended import current_user, jwt_required
from pydantic import Field

from ..errors import ValidationError
from ..services import contacts as service
from ..validation import PhoneNumber, Schema, parse_body

bp = Blueprint("contacts", __name__, url_prefix="/contacts")


class ContactBody(Schema):
    name: str = Field(min_length=1, max_length=100)
    phone: PhoneNumber
    relationship: str | None = Field(default=None, max_length=50)


class ContactPatch(Schema):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    phone: PhoneNumber | None = None
    relationship: str | None = Field(default=None, max_length=50)


@bp.get("")
@jwt_required()
def list_contacts():
    return {"contacts": [c.to_dict() for c in service.list_contacts(current_user)]}


@bp.post("")
@jwt_required()
def add_contact():
    body = parse_body(ContactBody)
    contact = service.add_contact(current_user, body.name, body.phone, body.relationship)
    return contact.to_dict(), 201


@bp.get("/<int:contact_id>")
@jwt_required()
def get_contact(contact_id: int):
    return service.get_contact(current_user, contact_id).to_dict()


@bp.patch("/<int:contact_id>")
@jwt_required()
def update_contact(contact_id: int):
    contact = service.get_contact(current_user, contact_id)
    changes = parse_body(ContactPatch).model_dump(exclude_unset=True)
    for required in ("name", "phone"):
        if required in changes and changes[required] is None:
            raise ValidationError({required: "This field can't be empty."})
    return service.update_contact(contact, changes).to_dict()


@bp.delete("/<int:contact_id>")
@jwt_required()
def delete_contact(contact_id: int):
    service.delete_contact(service.get_contact(current_user, contact_id))
    return "", 204
