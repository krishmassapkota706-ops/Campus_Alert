"""Emergency contacts. Every query is scoped to the owning user."""

from ..errors import APIError, NotFound
from ..extensions import db
from ..models import EmergencyContact, User

MAX_CONTACTS = 5


def list_contacts(user: User) -> list[EmergencyContact]:
    return list(user.contacts)


def get_contact(user: User, contact_id: int) -> EmergencyContact:
    """Return the user's contact. Someone else's contact is a 404, not a 403."""
    contact = db.session.scalar(
        db.select(EmergencyContact).filter_by(id=contact_id, user_id=user.id)
    )
    if contact is None:
        raise NotFound("Emergency contact not found.")
    return contact


def add_contact(user: User, name: str, phone: str, relationship: str | None) -> EmergencyContact:
    if len(user.contacts) >= MAX_CONTACTS:
        raise APIError(
            409, "contact_limit", f"You can save up to {MAX_CONTACTS} emergency contacts."
        )
    contact = EmergencyContact(name=name, phone=phone, relationship_label=relationship)
    user.contacts.append(contact)
    db.session.commit()
    return contact


def update_contact(contact: EmergencyContact, changes: dict) -> EmergencyContact:
    if "relationship" in changes:
        changes["relationship_label"] = changes.pop("relationship")
    for field, value in changes.items():
        setattr(contact, field, value)
    db.session.commit()
    return contact


def delete_contact(contact: EmergencyContact) -> None:
    db.session.delete(contact)
    db.session.commit()
