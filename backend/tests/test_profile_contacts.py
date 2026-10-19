"""Profile and emergency contacts (US-04, US-05; TC-PROFILE-01, TC-CONTACT-01)."""

import pytest
from conftest import PASSWORD, auth_header

from app.services.contacts import MAX_CONTACTS

CONTACTS = "/api/v1/contacts"


@pytest.fixture
def headers(signup):
    return auth_header(signup()["access_token"])


@pytest.fixture
def other_headers(signup):
    return auth_header(signup(email="other@jacks.sdstate.edu")["access_token"])


# ---- Profile ----


def test_update_profile_name_and_phone(client, headers):
    res = client.patch(
        "/api/v1/me", json={"name": "Jack R.", "phone": "(605) 555-0142"}, headers=headers
    )
    assert res.status_code == 200
    assert res.get_json()["name"] == "Jack R."
    assert res.get_json()["phone"] == "+16055550142"
    assert client.get("/api/v1/me", headers=headers).get_json()["phone"] == "+16055550142"


def test_profile_phone_can_be_cleared(client, headers):
    client.patch("/api/v1/me", json={"phone": "605-555-0142"}, headers=headers)
    res = client.patch("/api/v1/me", json={"phone": None}, headers=headers)
    assert res.get_json()["phone"] is None


@pytest.mark.parametrize(
    "body, field",
    [
        ({"phone": "12"}, "phone"),
        ({"name": ""}, "name"),
        ({"name": None}, "name"),
        ({"email": "new@jacks.sdstate.edu"}, "email"),
        ({"role": "maintainer"}, "role"),
    ],
)
def test_profile_rejects_invalid_or_forbidden_fields(client, headers, body, field):
    res = client.patch("/api/v1/me", json=body, headers=headers)
    assert res.status_code == 422
    assert field in res.get_json()["error"]["fields"]


def test_change_password_returns_new_tokens_and_ends_old_session(client, headers):
    res = client.post(
        "/api/v1/me/password",
        json={"current_password": PASSWORD, "new_password": "EvenBetterPass42"},
        headers=headers,
    )
    assert res.status_code == 200
    new_headers = auth_header(res.get_json()["access_token"])
    assert client.get("/api/v1/me", headers=headers).status_code == 401
    assert client.get("/api/v1/me", headers=new_headers).status_code == 200


def test_change_password_requires_current_password(client, headers):
    res = client.post(
        "/api/v1/me/password",
        json={"current_password": "nope", "new_password": "EvenBetterPass42"},
        headers=headers,
    )
    assert res.status_code == 422
    assert "current_password" in res.get_json()["error"]["fields"]


# ---- Emergency contacts ----


def add(client, headers, **overrides):
    body = {"name": "Mom", "phone": "605-555-0199", "relationship": "Parent", **overrides}
    return client.post(CONTACTS, json=body, headers=headers)


def test_contacts_require_auth(client):
    assert client.get(CONTACTS).status_code == 401


def test_add_list_update_delete_contact(client, headers):
    res = add(client, headers)
    assert res.status_code == 201
    contact = res.get_json()
    assert contact == {
        "id": contact["id"],
        "name": "Mom",
        "phone": "+16055550199",
        "relationship": "Parent",
    }

    listed = client.get(CONTACTS, headers=headers).get_json()["contacts"]
    assert listed == [contact]

    url = f"{CONTACTS}/{contact['id']}"
    res = client.patch(
        url, json={"phone": "+1 605 555 0100", "relationship": None}, headers=headers
    )
    assert res.status_code == 200
    assert res.get_json()["phone"] == "+16055550100"
    assert res.get_json()["relationship"] is None
    assert res.get_json()["name"] == "Mom"

    assert client.delete(url, headers=headers).status_code == 204
    assert client.get(url, headers=headers).status_code == 404
    assert client.get(CONTACTS, headers=headers).get_json()["contacts"] == []


@pytest.mark.parametrize("phone", ["", "abc", "555", "+1 000 000 0000"])
def test_invalid_phone_numbers_are_rejected(client, headers, phone):
    res = add(client, headers, phone=phone)
    assert res.status_code == 422
    assert "phone" in res.get_json()["error"]["fields"]


def test_patch_cannot_blank_required_fields(client, headers):
    contact_id = add(client, headers).get_json()["id"]
    res = client.patch(f"{CONTACTS}/{contact_id}", json={"name": None}, headers=headers)
    assert res.status_code == 422


def test_contact_limit(client, headers):
    for i in range(MAX_CONTACTS):
        assert add(client, headers, name=f"Contact {i}").status_code == 201
    res = add(client, headers, name="One too many")
    assert res.status_code == 409
    assert res.get_json()["error"]["code"] == "contact_limit"


def test_users_cannot_see_or_change_each_others_contacts(client, headers, other_headers):
    contact_id = add(client, headers).get_json()["id"]
    url = f"{CONTACTS}/{contact_id}"

    assert client.get(CONTACTS, headers=other_headers).get_json()["contacts"] == []
    assert client.get(url, headers=other_headers).status_code == 404
    assert client.patch(url, json={"name": "Hacked"}, headers=other_headers).status_code == 404
    assert client.delete(url, headers=other_headers).status_code == 404
    assert client.get(url, headers=headers).get_json()["name"] == "Mom"
