"""Emergency configuration and the prototype-safe emergency action workflow.

In demo mode (the default) every number the app would dial is swapped for
``DEMO_CALL_NUMBER``, so no real emergency call can be placed during grading or a
demonstration (RD US-07, NFR-3.2.13). Displayed numbers stay real so the screens
are accurate.
"""

from flask import current_app

from ..extensions import db
from ..models import EmergencyAction, EmergencyEvent, User
from ..security.crypto import get_cipher

NOT_911_NOTICE = (
    "ReportSDState does not replace 911. If you or someone else is in immediate danger, call 911."
)
DEMO_NOTICE = (
    "Demo mode: call buttons dial a test number, not University Police, 911, or a crisis line."
)


def is_demo() -> bool:
    return bool(current_app.config["DEMO_MODE"])


def dial_number(real_number: str) -> str:
    return current_app.config["DEMO_CALL_NUMBER"] if is_demo() else real_number


def _target(name: str, real_number: str) -> dict:
    return {"name": name, "phone": real_number, "dial_number": dial_number(real_number)}


def _action_numbers() -> dict[EmergencyAction, str]:
    cfg = current_app.config
    return {
        EmergencyAction.CALL_CAMPUS_POLICE: cfg["CAMPUS_POLICE_NUMBER"],
        EmergencyAction.CALL_911: "911",
        EmergencyAction.CALL_CRISIS_LINE: cfg["CRISIS_LINE_NUMBER"],
    }


def emergency_config() -> dict:
    cfg = current_app.config
    demo = is_demo()
    return {
        "demo_mode": demo,
        "notice": NOT_911_NOTICE,
        "demo_notice": DEMO_NOTICE if demo else None,
        "campus_police": _target("SDSU University Police", cfg["CAMPUS_POLICE_NUMBER"]),
        "emergency_services": _target("Emergency Services", "911"),
        "crisis_line": _target("988 Suicide & Crisis Lifeline", cfg["CRISIS_LINE_NUMBER"]),
        "sos_hold_seconds": 2,
    }


def record_event(user: User, action: EmergencyAction, contact_phone: str | None = None) -> dict:
    """Log that an emergency action started and tell the app what to dial."""
    cipher = get_cipher()
    event = EmergencyEvent(
        action=action,
        simulated=is_demo(),
        user_ref_enc=cipher.encrypt(str(user.id)),
        user_ref_idx=cipher.blind_index(str(user.id)),
    )
    db.session.add(event)
    db.session.commit()

    real = contact_phone if action is EmergencyAction.CALL_CONTACT else _action_numbers()[action]
    return {
        "event": event.to_dict(),
        "dial_number": dial_number(real),
        "message": (
            "Demo mode: dialing the test number. No real emergency call is placed."
            if event.simulated
            else "Connecting your call."
        ),
    }
