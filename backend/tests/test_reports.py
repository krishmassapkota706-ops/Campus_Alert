"""Reports (US-12, US-13, US-16, US-17; TC-MAINT-01, TC-CRIME-01, TC-CONF-01, TC-DB-02)."""

import pytest
from conftest import auth_header

from app.models import Report, Role, User
from app.security.crypto import get_cipher

REPORTS = "/api/v1/reports"
ADMIN = "/api/v1/admin/reports"


@pytest.fixture
def headers(signup):
    return auth_header(signup()["access_token"])


@pytest.fixture
def other_headers(signup):
    return auth_header(signup(email="other@jacks.sdstate.edu")["access_token"])


@pytest.fixture
def maintainer_headers(signup, db):
    tokens = signup(email="staff@jacks.sdstate.edu")
    user = db.session.scalar(db.select(User).filter_by(email="staff@jacks.sdstate.edu"))
    user.role = Role.MAINTAINER
    db.session.commit()
    return auth_header(tokens["access_token"])


def submit(client, headers, **overrides):
    body = {
        "category": "maintenance",
        "location": "Hansen Hall 214",
        "details": "Heater broken",
        **overrides,
    }
    return client.post(REPORTS, json=body, headers=headers)


def test_reports_require_auth(client):
    assert client.post(REPORTS, json={}).status_code == 401
    assert client.get(REPORTS).status_code == 401


@pytest.mark.parametrize("category", ["maintenance", "crime", "emergency", "other"])
def test_submit_report_returns_confirmation(client, headers, category):
    res = submit(client, headers, category=category)
    assert res.status_code == 201
    body = res.get_json()
    report = body["report"]
    assert report["category"] == category
    assert report["status"] == "submitted"
    assert report["reference_id"] in body["message"]
    prefix = "EMG-" if category == "emergency" else "RPT-"
    assert report["reference_id"].startswith(prefix)


@pytest.mark.parametrize(
    "overrides, field",
    [
        ({"category": "health"}, "category"),
        ({"location": ""}, "location"),
        ({"details": "x" * 1001}, "details"),
        ({"reporter": "someone else"}, "reporter"),
    ],
)
def test_submit_report_validates_fields(client, headers, overrides, field):
    res = submit(client, headers, **overrides)
    assert res.status_code == 422
    assert field in res.get_json()["error"]["fields"]


def test_missing_fields_are_listed(client, headers):
    res = client.post(REPORTS, json={}, headers=headers)
    assert set(res.get_json()["error"]["fields"]) == {"category", "location", "details"}


def test_stored_report_does_not_contain_plain_user_id(client, db, headers):
    submit(client, headers)
    user = db.session.scalar(db.select(User))
    report = db.session.scalar(db.select(Report))
    assert str(user.id) not in (report.reporter_ref_enc, report.reporter_ref_idx)
    assert get_cipher().decrypt(report.reporter_ref_enc) == str(user.id)


def test_history_lists_only_own_reports_newest_first(client, headers, other_headers):
    first = submit(client, headers, details="first").get_json()["report"]
    second = submit(client, headers, category="crime", details="second").get_json()["report"]
    submit(client, other_headers, details="not mine")

    body = client.get(REPORTS, headers=headers).get_json()
    assert body["total"] == 2
    assert [r["reference_id"] for r in body["reports"]] == [
        second["reference_id"],
        first["reference_id"],
    ]

    crime_only = client.get(f"{REPORTS}?category=crime", headers=headers).get_json()
    assert [r["details"] for r in crime_only["reports"]] == ["second"]


def test_history_pagination(client, headers):
    for i in range(3):
        submit(client, headers, details=f"r{i}")
    body = client.get(f"{REPORTS}?page=2&per_page=2", headers=headers).get_json()
    assert body["total"] == 3 and body["page"] == 2
    assert [r["details"] for r in body["reports"]] == ["r0"]


@pytest.mark.parametrize(
    "query", ["page=0", "per_page=500", "page=abc", "category=nope", "category=health"]
)
def test_history_rejects_bad_query_params(client, headers, query):
    assert client.get(f"{REPORTS}?{query}", headers=headers).status_code == 422


def test_get_own_report_by_reference_id(client, headers, other_headers):
    ref = submit(client, headers).get_json()["report"]["reference_id"]
    assert client.get(f"{REPORTS}/{ref.lower()}", headers=headers).status_code == 200
    assert client.get(f"{REPORTS}/{ref}", headers=other_headers).status_code == 404


# ---- Maintainer access (TC-ROLE-01) ----


def test_students_cannot_use_admin_endpoints(client, headers):
    assert client.get(ADMIN, headers=headers).status_code == 403


def test_maintainer_sees_all_reports_and_reporter(
    client, headers, other_headers, maintainer_headers
):
    ref = submit(client, headers).get_json()["report"]["reference_id"]
    submit(client, other_headers, category="crime")

    listing = client.get(ADMIN, headers=maintainer_headers).get_json()
    assert listing["total"] == 2
    assert "reporter" not in listing["reports"][0]

    detail = client.get(f"{ADMIN}/{ref}", headers=maintainer_headers).get_json()
    assert detail["reporter"]["email"] == "jack@jacks.sdstate.edu"


def test_maintainer_updates_status_and_student_sees_it(client, headers, maintainer_headers):
    ref = submit(client, headers).get_json()["report"]["reference_id"]
    res = client.patch(f"{ADMIN}/{ref}", json={"status": "in_review"}, headers=maintainer_headers)
    assert res.status_code == 200
    assert client.get(f"{REPORTS}/{ref}", headers=headers).get_json()["status"] == "in_review"

    filtered = client.get(f"{ADMIN}?status=in_review", headers=maintainer_headers).get_json()
    assert [r["reference_id"] for r in filtered["reports"]] == [ref]


def test_maintainer_status_must_be_valid(client, headers, maintainer_headers):
    ref = submit(client, headers).get_json()["report"]["reference_id"]
    res = client.patch(f"{ADMIN}/{ref}", json={"status": "deleted"}, headers=maintainer_headers)
    assert res.status_code == 422


def test_reference_id_collision_is_retried(client, headers, monkeypatch):
    first = submit(client, headers).get_json()["report"]["reference_id"]
    ids = iter([first, "RPT-ZZZZZZ"])
    monkeypatch.setattr("app.services.reports.new_reference_id", lambda _category: next(ids))
    res = submit(client, headers)
    assert res.status_code == 201
    assert res.get_json()["report"]["reference_id"] == "RPT-ZZZZZZ"
