"""One-time location sharing with an emergency contact (RD US-10, US-11).

Rules enforced here:

* Nothing is sent unless the request carries ``confirmed: true`` for a recipient the
  user chose from their own contacts (FR-3.7.3).
* Coordinates are used to build one message and then discarded: they are never
  written to the database or the log, so there is no location history (FR-3.7.4).
* If the live SMS provider fails, the response says so and includes an ``sms:``
  link the phone can open to send the same text itself (FR-3.5.5).
"""

import urllib.parse

from flask import current_app

from ..errors import APIError
from ..models import EmergencyContact, User, utcnow
from .sms import SmsError, get_sms_sender


class SmsUnavailable(APIError):
    def __init__(self, sms_link: str):
        super().__init__(
            503,
            "sms_unavailable",
            "We couldn't send the text. Open your messaging app to send it yourself.",
            extra={"sms_link": sms_link},
        )


def map_link(latitude: float, longitude: float) -> str:
    return f"https://maps.google.com/?q={latitude:.5f},{longitude:.5f}"


def build_message(user: User, latitude: float, longitude: float) -> str:
    sent_at = utcnow().strftime("%H:%M UTC")
    prefix = "[DEMO - not a real alert] " if current_app.config["DEMO_MODE"] else ""
    return (
        f"{prefix}ReportSDState: {user.name} shared their current location with you at "
        f"{sent_at}: {map_link(latitude, longitude)} (one-time share)"
    )


def sms_link(phone: str, body: str) -> str:
    # "?&body=" works on both iOS and Android.
    return f"sms:{phone}?&body={urllib.parse.quote(body)}"


def share_location(
    user: User, contact: EmergencyContact, latitude: float, longitude: float
) -> dict:
    body = build_message(user, latitude, longitude)
    try:
        sent = get_sms_sender().send(contact.phone, body)
    except SmsError:
        current_app.logger.warning("Live SMS failed; returning device fallback link")
        raise SmsUnavailable(sms_link(contact.phone, body)) from None

    return {
        "status": "simulated" if sent.simulated else "sent",
        "recipient": {"id": contact.id, "name": contact.name, "phone": contact.phone},
        "message": (
            f"Demo mode: a text to {contact.name} was simulated. No real message was sent."
            if sent.simulated
            else f"Your location was sent to {contact.name}."
        ),
        "stored": False,
    }
