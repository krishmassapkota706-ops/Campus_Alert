import re

import pytest

from app import create_app
from app.config import TestingConfig
from app.extensions import db as _db
from app.services.mailer import get_mailer

PASSWORD = "Jackrabbits2026"


@pytest.fixture
def app():
    app = create_app(TestingConfig)
    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db(app):
    return _db


@pytest.fixture
def outbox(app):
    return get_mailer().outbox


def last_code(outbox) -> str:
    return re.search(r"\b(\d{6})\b", outbox[-1].body).group(1)


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def signup(client, outbox):
    """Register and verify an account; returns the verify-email response JSON."""

    def _signup(email="jack@jacks.sdstate.edu", password=PASSWORD, name="Jack Rabbit"):
        res = client.post(
            "/api/v1/auth/register", json={"email": email, "password": password, "name": name}
        )
        assert res.status_code == 201, res.get_json()
        res = client.post(
            "/api/v1/auth/verify-email", json={"email": email, "code": last_code(outbox)}
        )
        assert res.status_code == 200, res.get_json()
        return res.get_json()

    return _signup
