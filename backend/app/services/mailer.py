"""Outbound email behind a small interface so the provider can be swapped.

``MAIL_BACKEND`` selects the implementation:

* ``console`` (default) - writes the message to the server log. Development only.
* ``memory`` - keeps messages in ``mailer.outbox``. Used by the test suite.
* ``smtp`` - sends through ``SMTP_HOST`` with STARTTLS.
"""

import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Protocol

from flask import Flask, current_app


class MailError(Exception):
    """The message could not be handed to the mail provider."""


@dataclass
class Message:
    to: str
    subject: str
    body: str


class Mailer(Protocol):
    def send(self, message: Message) -> None: ...


class ConsoleMailer:
    def send(self, message: Message) -> None:
        current_app.logger.info(
            "[console mail] to=%s subject=%s\n%s", message.to, message.subject, message.body
        )


class MemoryMailer:
    def __init__(self):
        self.outbox: list[Message] = []

    def send(self, message: Message) -> None:
        self.outbox.append(message)


class SmtpMailer:
    def __init__(self, host: str, port: int, username: str, password: str, sender: str):
        self.host, self.port = host, port
        self.username, self.password = username, password
        self.sender = sender

    def send(self, message: Message) -> None:
        email = EmailMessage()
        email["From"] = self.sender
        email["To"] = message.to
        email["Subject"] = message.subject
        email.set_content(message.body)
        try:
            with smtplib.SMTP(self.host, self.port, timeout=10) as smtp:
                smtp.starttls()
                if self.username:
                    smtp.login(self.username, self.password)
                smtp.send_message(email)
        except (OSError, smtplib.SMTPException) as exc:
            raise MailError(str(exc)) from exc


def init_mailer(app: Flask) -> None:
    backend = app.config["MAIL_BACKEND"]
    if backend == "console":
        mailer: Mailer = ConsoleMailer()
    elif backend == "memory":
        mailer = MemoryMailer()
    elif backend == "smtp":
        mailer = SmtpMailer(
            app.config["SMTP_HOST"],
            app.config["SMTP_PORT"],
            app.config["SMTP_USERNAME"],
            app.config["SMTP_PASSWORD"],
            app.config["MAIL_FROM"],
        )
    else:
        raise RuntimeError(f"Unknown MAIL_BACKEND '{backend}'")
    app.extensions["mailer"] = mailer


def get_mailer() -> Mailer:
    return current_app.extensions["mailer"]


def send_mail(to: str, subject: str, body: str) -> None:
    get_mailer().send(Message(to=to, subject=subject, body=body))
