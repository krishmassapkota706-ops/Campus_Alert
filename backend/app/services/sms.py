"""Outbound SMS behind a small interface so the provider can be swapped (RD NFR-3.2.14).

* ``mock`` (default) - records the message in ``sender.sent`` and logs a redacted line.
  Always used while ``DEMO_MODE`` is on, so no real text is sent during grading.
* ``twilio`` - sends through the Twilio REST API using ``TWILIO_*`` credentials.

Message bodies can contain a location, so they are never written to the log.
"""

import base64
import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Protocol

from flask import Flask, current_app


class SmsError(Exception):
    """The provider could not accept the message."""


@dataclass
class SentSms:
    to: str
    body: str
    simulated: bool
    provider_id: str | None = None


class SmsSender(Protocol):
    simulated: bool

    def send(self, to: str, body: str) -> SentSms: ...


def redact(phone: str) -> str:
    return phone[:-4].rstrip() + "****" if len(phone) > 4 else "****"


class MockSmsSender:
    simulated = True

    def __init__(self):
        self.sent: list[SentSms] = []

    def send(self, to: str, body: str) -> SentSms:
        message = SentSms(to=to, body=body, simulated=True)
        self.sent.append(message)
        current_app.logger.info("[mock sms] to=%s (%d chars, not sent)", redact(to), len(body))
        return message


class TwilioSmsSender:
    simulated = False
    API = "https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"

    def __init__(self, account_sid: str, auth_token: str, from_number: str):
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.from_number = from_number

    def send(self, to: str, body: str) -> SentSms:
        data = urllib.parse.urlencode({"To": to, "From": self.from_number, "Body": body}).encode()
        request = urllib.request.Request(  # noqa: S310 (fixed https URL)
            self.API.format(sid=self.account_sid), data=data, method="POST"
        )
        credentials = base64.b64encode(f"{self.account_sid}:{self.auth_token}".encode()).decode()
        request.add_header("Authorization", f"Basic {credentials}")
        try:
            with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310
                payload = json.loads(response.read())
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            raise SmsError(type(exc).__name__) from exc
        current_app.logger.info("[twilio sms] to=%s sid=%s", redact(to), payload.get("sid"))
        return SentSms(to=to, body=body, simulated=False, provider_id=payload.get("sid"))


def init_sms(app: Flask) -> None:
    mode = app.config["SMS_MODE"]
    if app.config["DEMO_MODE"] or mode == "mock":
        sender: SmsSender = MockSmsSender()
    elif mode == "twilio":
        sender = TwilioSmsSender(
            app.config["TWILIO_ACCOUNT_SID"],
            app.config["TWILIO_AUTH_TOKEN"],
            app.config["TWILIO_FROM_NUMBER"],
        )
    else:
        raise RuntimeError(f"Unknown SMS_MODE '{mode}'")
    app.extensions["sms_sender"] = sender


def get_sms_sender() -> SmsSender:
    return current_app.extensions["sms_sender"]
