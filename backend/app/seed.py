"""Synthetic development data. Never put real student information here."""

import os

from .extensions import db
from .models import EmergencyContact, Report, ReportCategory, Role, User, new_reference_id, utcnow
from .security.crypto import get_cipher

# Test-only credentials for the seeded accounts. Override with SEED_DEMO_PASSWORD.
DEFAULT_DEMO_PASSWORD = "Jackrabbit-Demo-2026"  # noqa: S105 (synthetic test account)

DEMO_STUDENT_EMAIL = "demo.student@jacks.sdstate.edu"
DEMO_MAINTAINER_EMAIL = "demo.maintainer@jacks.sdstate.edu"


def seed_demo_data() -> dict[str, int]:
    """Insert demo users, contacts and reports. Idempotent: skips users that already exist."""
    password = os.environ.get("SEED_DEMO_PASSWORD") or DEFAULT_DEMO_PASSWORD
    created = {"users": 0, "contacts": 0, "reports": 0}

    student = _get_or_create_user(
        DEMO_STUDENT_EMAIL, "Demo Student", "+16055550142", Role.STUDENT, password, created
    )
    _get_or_create_user(
        DEMO_MAINTAINER_EMAIL, "Demo Maintainer", None, Role.MAINTAINER, password, created
    )

    if not student.contacts:
        student.contacts.append(
            EmergencyContact(name="Demo Contact", phone="+16055550199", relationship_label="Parent")
        )
        created["contacts"] += 1

    cipher = get_cipher()
    index = cipher.blind_index(str(student.id))
    if not db.session.scalar(db.select(Report).filter_by(reporter_ref_idx=index).limit(1)):
        samples = [
            (ReportCategory.MAINTENANCE, "Hansen Hall, Room 214", "Heater not working."),
            (ReportCategory.CRIME, "Lot near the Union", "Bike lock cut overnight."),
        ]
        for category, location, details in samples:
            db.session.add(
                Report(
                    reference_id=new_reference_id(category),
                    category=category,
                    location_text=location,
                    details=details,
                    reporter_ref_enc=cipher.encrypt(str(student.id)),
                    reporter_ref_idx=index,
                )
            )
            created["reports"] += 1

    db.session.commit()
    return created


def _get_or_create_user(email, name, phone, role, password, created) -> User:
    user = db.session.scalar(db.select(User).filter_by(email=email))
    if user:
        return user
    user = User(email=email, name=name, phone=phone, role=role, email_verified_at=utcnow())
    user.set_password(password)
    db.session.add(user)
    db.session.flush()  # assign user.id for the blind index
    created["users"] += 1
    return user
