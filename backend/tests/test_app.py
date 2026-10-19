import pytest
from flask import Blueprint

from app import create_app
from app.config import ProductionConfig, TestingConfig
from app.errors import Conflict
from app.validation import Schema, parse_body


def test_health(client):
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    assert res.get_json() == {"status": "ok", "environment": "testing"}


def test_unknown_route_returns_json_404(client):
    res = client.get("/api/v1/does-not-exist")
    assert res.status_code == 404
    assert res.get_json()["error"]["code"] == "not_found"


def test_wrong_method_returns_json_405(client):
    res = client.post("/api/v1/health")
    assert res.status_code == 405
    assert res.get_json()["error"]["code"] == "method_not_allowed"


class _EchoSchema(Schema):
    name: str
    age: int


def _app_with_test_routes():
    app = create_app(TestingConfig)
    bp = Blueprint("test_routes", __name__)

    @bp.post("/echo")
    def echo():
        return parse_body(_EchoSchema).model_dump()

    @bp.get("/boom")
    def boom():
        raise RuntimeError("secret internal detail")

    @bp.get("/conflict")
    def conflict():
        raise Conflict("Already exists.")

    app.register_blueprint(bp)
    return app.test_client()


def test_parse_body_accepts_valid_json():
    res = _app_with_test_routes().post("/echo", json={"name": "  Jack  ", "age": 20})
    assert res.status_code == 200
    assert res.get_json() == {"name": "Jack", "age": 20}


def test_parse_body_reports_field_errors():
    res = _app_with_test_routes().post("/echo", json={"age": "old", "extra": 1})
    assert res.status_code == 422
    error = res.get_json()["error"]
    assert error["code"] == "validation_error"
    assert set(error["fields"]) == {"name", "age", "extra"}


def test_parse_body_rejects_non_object():
    res = _app_with_test_routes().post("/echo", data="nope", content_type="application/json")
    assert res.status_code == 422
    assert res.get_json()["error"]["fields"] == {"body": "Request body must be a JSON object."}


def test_api_error_is_returned_as_is():
    res = _app_with_test_routes().get("/conflict")
    assert res.status_code == 409
    assert res.get_json() == {"error": {"code": "conflict", "message": "Already exists."}}


def test_unexpected_error_does_not_leak_details():
    res = _app_with_test_routes().get("/boom")
    assert res.status_code == 500
    assert "secret internal detail" not in res.get_data(as_text=True)
    assert res.get_json()["error"]["code"] == "internal_error"


def test_production_refuses_to_start_without_secrets(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app(ProductionConfig)
