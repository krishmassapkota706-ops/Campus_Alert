"""Resources and emergency workflow (US-07, US-08, US-09, US-14, US-15; TC-RES-01, TC-UPD-01,
TC-CRISIS-01, TC-EMERG-02, TC-EMERG-03)."""

import json

import pytest
from conftest import auth_header

from app.models import EmergencyEvent, Resource, User
from app.services.resources import RESOURCES_FILE, load_resources

DEMO_NUMBER = "+16055550100"


@pytest.fixture
def resources(db):
    load_resources()


@pytest.fixture
def headers(signup):
    return auth_header(signup()["access_token"])


@pytest.fixture
def live_mode(app):
    app.config["DEMO_MODE"] = False
    yield
    app.config["DEMO_MODE"] = True


# ---- Resources ----


def test_resource_file_is_valid_and_has_sources():
    entries = json.loads(RESOURCES_FILE.read_text(encoding="utf-8"))["resources"]
    assert entries
    for entry in entries:
        assert entry["name"] and entry["category"]
        assert entry.get("source_url", "").startswith("https://")
        assert entry.get("phone") or entry.get("url")


def test_resources_are_public(client, resources):
    res = client.get("/api/v1/resources")
    assert res.status_code == 200
    body = res.get_json()
    assert len(body["resources"]) == len(
        json.loads(RESOURCES_FILE.read_text(encoding="utf-8"))["resources"]
    )
    assert "crisis" in body["categories"]


def test_resources_filter_by_category(client, resources):
    body = client.get("/api/v1/resources?category=crisis").get_json()
    assert body["resources"]
    assert {r["category"] for r in body["resources"]} == {"crisis"}


def test_resources_search(client, resources):
    names = [r["name"] for r in client.get("/api/v1/resources?q=escort").get_json()["resources"]]
    assert names == ["UPD Safety Escort"]


def test_resources_reject_unknown_category(client, resources):
    assert client.get("/api/v1/resources?category=parties").status_code == 422


def test_resources_dial_test_number_in_demo_mode(client, resources):
    for r in client.get("/api/v1/resources").get_json()["resources"]:
        if r["phone"]:
            assert r["dial_number"] == DEMO_NUMBER


def test_resources_dial_real_number_when_live(client, resources, live_mode):
    upd = client.get("/api/v1/resources?q=University Police Department").get_json()["resources"][0]
    assert upd["dial_number"] == upd["phone"] == "+16056885117"


def test_load_resources_is_idempotent_unless_replacing(db, resources):
    count = db.session.scalar(db.select(db.func.count()).select_from(Resource))
    assert load_resources() == 0
    assert load_resources(replace=True) == count
    assert db.session.scalar(db.select(db.func.count()).select_from(Resource)) == count


# ---- Emergency config ----


def test_emergency_config_is_public_and_says_not_911(client):
    body = client.get("/api/v1/emergency/config").get_json()
    assert "does not replace 911" in body["notice"]
    assert body["demo_mode"] is True
    assert body["demo_notice"]
    assert body["campus_police"]["phone"] == "+16056885117"
    for target in ("campus_police", "emergency_services", "crisis_line"):
        assert body[target]["dial_number"] == DEMO_NUMBER


def test_emergency_config_live_mode(client, live_mode):
    body = client.get("/api/v1/emergency/config").get_json()
    assert body["demo_mode"] is False and body["demo_notice"] is None
    assert body["emergency_services"]["dial_number"] == "911"
    assert body["crisis_line"]["dial_number"] == "988"


# ---- Emergency events ----


def test_emergency_event_requires_auth(client):
    assert client.post("/api/v1/emergency/events", json={"action": "call_911"}).status_code == 401


@pytest.mark.parametrize("action", ["call_campus_police", "call_911", "call_crisis_line"])
def test_emergency_event_in_demo_mode_dials_test_number(client, db, headers, action):
    res = client.post("/api/v1/emergency/events", json={"action": action}, headers=headers)
    assert res.status_code == 201
    body = res.get_json()
    assert body["dial_number"] == DEMO_NUMBER
    assert body["event"]["simulated"] is True
    assert "No real emergency call" in body["message"]

    event = db.session.scalar(db.select(EmergencyEvent))
    user = db.session.scalar(db.select(User))
    assert str(user.id) not in (event.user_ref_enc, event.user_ref_idx)


def test_emergency_event_live_mode_dials_real_number(client, headers, live_mode):
    res = client.post(
        "/api/v1/emergency/events", json={"action": "call_campus_police"}, headers=headers
    )
    assert res.get_json()["dial_number"] == "+16056885117"
    assert res.get_json()["event"]["simulated"] is False


def test_call_contact_uses_own_contact_only(client, signup, headers, live_mode):
    contact = client.post(
        "/api/v1/contacts", json={"name": "Mom", "phone": "605-555-0199"}, headers=headers
    ).get_json()
    res = client.post(
        "/api/v1/emergency/events",
        json={"action": "call_contact", "contact_id": contact["id"]},
        headers=headers,
    )
    assert res.status_code == 201
    assert res.get_json()["dial_number"] == "+16055550199"

    other = auth_header(signup(email="other@jacks.sdstate.edu")["access_token"])
    res = client.post(
        "/api/v1/emergency/events",
        json={"action": "call_contact", "contact_id": contact["id"]},
        headers=other,
    )
    assert res.status_code == 404


@pytest.mark.parametrize(
    "body, field",
    [
        ({"action": "call_contact"}, "contact_id"),
        ({"action": "call_911", "contact_id": 1}, "contact_id"),
        ({"action": "launch_missiles"}, "action"),
        ({"action": "call_911", "latitude": 44.3}, "latitude"),
    ],
)
def test_emergency_event_validation(client, headers, body, field):
    res = client.post("/api/v1/emergency/events", json=body, headers=headers)
    assert res.status_code == 422
    assert field in res.get_json()["error"]["fields"]
