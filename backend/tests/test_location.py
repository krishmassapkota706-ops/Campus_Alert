"""Location sharing (US-10, US-11, US-18; TC-LOC-01..03, TC-SMS-01, TC-SMS-02, TC-PRIV-01)."""

import pytest
from conftest import auth_header

from app.extensions import db as _db
from app.services.sms import SmsError, TwilioSmsSender, get_sms_sender

SHARE = "/api/v1/location/share"
LAT, LNG = 44.31969, -96.78428  # Campanile, SDSU


@pytest.fixture
def headers(signup):
    return auth_header(signup()["access_token"])


@pytest.fixture
def contact(client, headers):
    return client.post(
        "/api/v1/contacts", json={"name": "Mom", "phone": "605-555-0199"}, headers=headers
    ).get_json()


def share(client, headers, contact_id, **overrides):
    body = {"contact_id": contact_id, "latitude": LAT, "longitude": LNG, "confirmed": True}
    return client.post(SHARE, json={**body, **overrides}, headers=headers)


def test_share_requires_auth(client):
    assert client.post(SHARE, json={}).status_code == 401


def test_share_sends_one_simulated_text_with_map_link(client, headers, contact):
    res = share(client, headers, contact["id"])
    assert res.status_code == 200
    body = res.get_json()
    assert body["status"] == "simulated"
    assert body["recipient"] == {"id": contact["id"], "name": "Mom", "phone": "+16055550199"}
    assert body["stored"] is False

    sent = get_sms_sender().sent
    assert len(sent) == 1
    assert sent[0].to == "+16055550199"
    assert "https://maps.google.com/?q=44.31969,-96.78428" in sent[0].body
    assert sent[0].body.startswith("[DEMO")
    assert "Jack Rabbit" in sent[0].body


@pytest.mark.parametrize("confirmed", [False, None, "yes", 1])
def test_share_requires_explicit_confirmation(client, headers, contact, confirmed):
    res = share(client, headers, contact["id"], confirmed=confirmed)
    assert res.status_code == 422
    assert "confirmed" in res.get_json()["error"]["fields"]
    assert get_sms_sender().sent == []


def test_share_without_confirmed_field_sends_nothing(client, headers, contact):
    res = client.post(
        SHARE,
        json={"contact_id": contact["id"], "latitude": LAT, "longitude": LNG},
        headers=headers,
    )
    assert res.status_code == 422
    assert get_sms_sender().sent == []


@pytest.mark.parametrize("field, value", [("latitude", 91), ("longitude", -181), ("latitude", "x")])
def test_share_validates_coordinates(client, headers, contact, field, value):
    res = share(client, headers, contact["id"], **{field: value})
    assert res.status_code == 422
    assert field in res.get_json()["error"]["fields"]


def test_share_only_to_own_contacts(client, signup, contact):
    other = auth_header(signup(email="other@jacks.sdstate.edu")["access_token"])
    res = share(client, other, contact["id"])
    assert res.status_code == 404
    assert get_sms_sender().sent == []


def test_location_is_never_stored_or_logged(client, headers, contact, caplog):
    caplog.set_level("DEBUG")
    share(client, headers, contact["id"])

    assert "44.31969" not in caplog.text and "96.78428" not in caplog.text
    with _db.engine.connect() as conn:
        dump = "\n".join(conn.connection.dbapi_connection.iterdump())
    assert "44.31969" not in dump and "96.78428" not in dump


def test_live_sms_failure_returns_device_fallback_link(app, client, headers, contact):
    class FailingSender:
        simulated = False

        def send(self, to, body):
            raise SmsError("timeout")

    app.extensions["sms_sender"] = FailingSender()
    res = share(client, headers, contact["id"])
    assert res.status_code == 503
    error = res.get_json()["error"]
    assert error["code"] == "sms_unavailable"
    assert error["sms_link"].startswith("sms:+16055550199?&body=")
    assert "maps.google.com" in error["sms_link"]


def test_live_sender_reports_sent(app, client, headers, contact):
    class FakeTwilio:
        simulated = False

        def send(self, to, body):
            from app.services.sms import SentSms

            return SentSms(to=to, body=body, simulated=False, provider_id="SM123")

    app.extensions["sms_sender"] = FakeTwilio()
    app.config["DEMO_MODE"] = False
    body = share(client, headers, contact["id"]).get_json()
    app.config["DEMO_MODE"] = True
    assert body["status"] == "sent"
    assert "sent to Mom" in body["message"]


def test_twilio_sender_wraps_network_errors(app, monkeypatch):
    import urllib.error

    def boom(*_args, **_kwargs):
        raise urllib.error.URLError("unreachable")

    monkeypatch.setattr("urllib.request.urlopen", boom)
    sender = TwilioSmsSender("AC123", "token", "+16055550000")
    with pytest.raises(SmsError):
        sender.send("+16055550199", "hi")


def test_share_is_rate_limited_per_user(signup):
    from app import create_app
    from app.config import TestingConfig

    class LimitedConfig(TestingConfig):
        RATELIMIT_ENABLED = True

    app = create_app(LimitedConfig)
    with app.app_context():
        _db.create_all()
        client = app.test_client()
        from conftest import PASSWORD, last_code

        from app.services.mailer import get_mailer

        email = "jack@jacks.sdstate.edu"
        client.post(
            "/api/v1/auth/register", json={"email": email, "password": PASSWORD, "name": "Jack"}
        )
        tokens = client.post(
            "/api/v1/auth/verify-email",
            json={"email": email, "code": last_code(get_mailer().outbox)},
        ).get_json()
        headers = auth_header(tokens["access_token"])
        contact_id = client.post(
            "/api/v1/contacts", json={"name": "Mom", "phone": "605-555-0199"}, headers=headers
        ).get_json()["id"]
        statuses = [share(client, headers, contact_id).status_code for _ in range(6)]
        assert statuses == [200] * 5 + [429]
        _db.drop_all()
