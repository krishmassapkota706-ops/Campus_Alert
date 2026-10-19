"""Auth tests. Names reference RD test cases (TC-REG-01, TC-LOGIN-01, ...)."""

from datetime import timedelta

import pytest
from conftest import PASSWORD, auth_header, last_code
from flask import Blueprint

from app import create_app
from app.config import TestingConfig
from app.extensions import db as _db
from app.models import Role, User, VerificationCode, utcnow
from app.security.auth import role_required
from app.services.mailer import MailError, get_mailer

REGISTER = "/api/v1/auth/register"
VERIFY = "/api/v1/auth/verify-email"
LOGIN = "/api/v1/auth/login"
EMAIL = "jack@jacks.sdstate.edu"


def register(client, email=EMAIL, password=PASSWORD, name="Jack Rabbit"):
    return client.post(REGISTER, json={"email": email, "password": password, "name": name})


def login(client, email=EMAIL, password=PASSWORD):
    return client.post(LOGIN, json={"email": email, "password": password})


# ---- TC-REG-01 / TC-VERIFY-01: registration with SDSU email ----


def test_register_creates_unverified_user_and_emails_code(client, db, outbox):
    res = register(client, email="  Jack@Jacks.SDState.edu ")
    assert res.status_code == 201
    body = res.get_json()
    assert body["user"]["email"] == EMAIL
    assert body["user"]["email_verified"] is False
    assert len(outbox) == 1 and outbox[0].to == EMAIL
    assert len(last_code(outbox)) == 6

    user = db.session.scalar(db.select(User))
    assert user.check_password(PASSWORD)
    code_row = db.session.scalar(db.select(VerificationCode))
    assert last_code(outbox) not in code_row.code_hash


@pytest.mark.parametrize(
    "email", ["jack@gmail.com", "jack@sdstate.edu.evil.com", "jack@", "not-an-email"]
)
def test_register_rejects_non_sdsu_email(client, email):
    res = register(client, email=email)
    assert res.status_code == 422
    assert "email" in res.get_json()["error"]["fields"]


@pytest.mark.parametrize("password", ["short1", "onlyletterslong", "1234567890123"])
def test_register_enforces_password_rules(client, password):
    res = register(client, password=password)
    assert res.status_code == 422
    assert "password" in res.get_json()["error"]["fields"]


def test_register_rejects_duplicate_email(client):
    register(client)
    res = register(client, email=EMAIL.upper())
    assert res.status_code == 409


def test_register_saves_nothing_when_email_cannot_be_sent(client, db, monkeypatch):
    def fail(_message):
        raise MailError("smtp down")

    monkeypatch.setattr(get_mailer(), "send", fail)
    res = register(client)
    assert res.status_code == 503
    assert res.get_json()["error"]["code"] == "email_unavailable"
    assert db.session.scalar(db.select(db.func.count()).select_from(User)) == 0


def test_verify_email_returns_tokens(client, outbox):
    register(client)
    res = client.post(VERIFY, json={"email": EMAIL, "code": last_code(outbox)})
    assert res.status_code == 200
    body = res.get_json()
    assert body["user"]["email_verified"] is True
    assert body["access_token"] and body["refresh_token"]
    assert body["token_type"] == "Bearer"


def test_verify_email_wrong_code_is_rejected_and_counted(client, db, outbox):
    register(client)
    wrong = "000000" if last_code(outbox) != "000000" else "111111"
    res = client.post(VERIFY, json={"email": EMAIL, "code": wrong})
    assert res.status_code == 400
    assert res.get_json()["error"]["code"] == "invalid_code"
    assert db.session.scalar(db.select(VerificationCode)).attempts == 1


def test_verify_email_locks_after_max_attempts(client, app, outbox):
    register(client)
    code = last_code(outbox)
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(app.config["VERIFICATION_MAX_ATTEMPTS"]):
        client.post(VERIFY, json={"email": EMAIL, "code": wrong})
    res = client.post(VERIFY, json={"email": EMAIL, "code": code})
    assert res.status_code == 400


def test_verify_email_rejects_expired_code(client, db, outbox):
    register(client)
    row = db.session.scalar(db.select(VerificationCode))
    row.expires_at = utcnow() - timedelta(seconds=1)
    db.session.commit()
    res = client.post(VERIFY, json={"email": EMAIL, "code": last_code(outbox)})
    assert res.status_code == 400


def test_resend_verification_replaces_old_code(client, outbox):
    register(client)
    old = last_code(outbox)
    res = client.post("/api/v1/auth/resend-verification", json={"email": EMAIL})
    assert res.status_code == 202
    new = last_code(outbox)
    if old != new:
        assert client.post(VERIFY, json={"email": EMAIL, "code": old}).status_code == 400
    assert client.post(VERIFY, json={"email": EMAIL, "code": new}).status_code == 200


def test_resend_verification_is_silent_for_unknown_email(client, outbox):
    res = client.post(
        "/api/v1/auth/resend-verification", json={"email": "nobody@jacks.sdstate.edu"}
    )
    assert res.status_code == 202
    assert outbox == []


# ---- TC-LOGIN-01: login ----


def test_login_succeeds_for_verified_user(client, signup):
    signup()
    res = login(client)
    assert res.status_code == 200
    assert res.get_json()["user"]["email"] == EMAIL


def test_login_rejects_wrong_password_and_unknown_email_identically(client, signup):
    signup()
    wrong_pw = login(client, password="WrongPassword1")
    unknown = login(client, email="ghost@jacks.sdstate.edu")
    assert wrong_pw.status_code == unknown.status_code == 401
    assert wrong_pw.get_json() == unknown.get_json()


def test_login_blocks_unverified_account(client):
    register(client)
    res = login(client)
    assert res.status_code == 403
    assert res.get_json()["error"]["code"] == "email_not_verified"


# ---- TC-AUTHZ-01 / TC-SESSION-01: protected endpoints and sessions ----


def test_me_requires_token(client):
    res = client.get("/api/v1/me")
    assert res.status_code == 401
    assert res.get_json()["error"]["code"] == "unauthorized"


def test_me_rejects_garbage_token(client):
    res = client.get("/api/v1/me", headers=auth_header("not.a.jwt"))
    assert res.status_code == 401
    assert res.get_json()["error"]["code"] == "invalid_token"


def test_me_returns_current_user(client, signup):
    tokens = signup()
    res = client.get("/api/v1/me", headers=auth_header(tokens["access_token"]))
    assert res.status_code == 200
    assert res.get_json()["email"] == EMAIL


def test_refresh_token_cannot_call_protected_routes(client, signup):
    tokens = signup()
    res = client.get("/api/v1/me", headers=auth_header(tokens["refresh_token"]))
    assert res.status_code == 401


def test_refresh_issues_new_access_token(client, signup):
    tokens = signup()
    res = client.post("/api/v1/auth/refresh", headers=auth_header(tokens["refresh_token"]))
    assert res.status_code == 200
    new_access = res.get_json()["access_token"]
    assert client.get("/api/v1/me", headers=auth_header(new_access)).status_code == 200


def test_logout_revokes_access_and_refresh_tokens(client, signup):
    tokens = signup()
    res = client.post("/api/v1/auth/logout", headers=auth_header(tokens["access_token"]))
    assert res.status_code == 204

    me = client.get("/api/v1/me", headers=auth_header(tokens["access_token"]))
    assert me.status_code == 401
    assert me.get_json()["error"]["code"] == "token_revoked"
    refresh = client.post("/api/v1/auth/refresh", headers=auth_header(tokens["refresh_token"]))
    assert refresh.status_code == 401


# ---- TC-PW-01: password reset ----


def test_password_reset_flow_signs_out_old_sessions(client, signup, outbox):
    tokens = signup()
    res = client.post("/api/v1/auth/forgot-password", json={"email": EMAIL})
    assert res.status_code == 202

    new_password = "BrandNewPass99"
    res = client.post(
        "/api/v1/auth/reset-password",
        json={"email": EMAIL, "code": last_code(outbox), "new_password": new_password},
    )
    assert res.status_code == 200

    assert login(client).status_code == 401
    assert login(client, password=new_password).status_code == 200
    old_session = client.get("/api/v1/me", headers=auth_header(tokens["access_token"]))
    assert old_session.status_code == 401


def test_password_reset_code_cannot_be_reused(client, signup, outbox):
    signup()
    client.post("/api/v1/auth/forgot-password", json={"email": EMAIL})
    payload = {"email": EMAIL, "code": last_code(outbox), "new_password": "BrandNewPass99"}
    assert client.post("/api/v1/auth/reset-password", json=payload).status_code == 200
    payload["new_password"] = "AnotherPass123"
    assert client.post("/api/v1/auth/reset-password", json=payload).status_code == 400


def test_verification_code_cannot_reset_password(client, outbox):
    register(client)
    res = client.post(
        "/api/v1/auth/reset-password",
        json={"email": EMAIL, "code": last_code(outbox), "new_password": "BrandNewPass99"},
    )
    assert res.status_code == 400


def test_forgot_password_is_silent_for_unknown_email(client, outbox):
    res = client.post("/api/v1/auth/forgot-password", json={"email": "ghost@jacks.sdstate.edu"})
    assert res.status_code == 202
    assert outbox == []


# ---- TC-ROLE-01: role-based authorization ----


def test_role_required_blocks_students():
    app = create_app(TestingConfig)
    bp = Blueprint("role_test", __name__)

    @bp.get("/admin-only")
    @role_required(Role.MAINTAINER)
    def admin_only():
        return {"ok": True}

    app.register_blueprint(bp)
    with app.app_context():
        _db.create_all()
        client = app.test_client()
        client.post(REGISTER, json={"email": EMAIL, "password": PASSWORD, "name": "Jack"})
        code = last_code(get_mailer().outbox)
        tokens = client.post(VERIFY, json={"email": EMAIL, "code": code}).get_json()

        res = client.get("/admin-only", headers=auth_header(tokens["access_token"]))
        assert res.status_code == 403

        user = _db.session.scalar(_db.select(User))
        user.role = Role.MAINTAINER
        _db.session.commit()
        res = client.get("/admin-only", headers=auth_header(tokens["access_token"]))
        assert res.status_code == 200
        _db.drop_all()


# ---- Brute-force protection ----


def test_login_is_rate_limited():
    class LimitedConfig(TestingConfig):
        RATELIMIT_ENABLED = True

    app = create_app(LimitedConfig)
    with app.app_context():
        _db.create_all()
        client = app.test_client()
        statuses = [login(client).status_code for _ in range(11)]
        assert statuses[:10] == [401] * 10
        assert statuses[10] == 429
        _db.drop_all()
