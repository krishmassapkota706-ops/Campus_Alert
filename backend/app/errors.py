"""Uniform JSON error responses.

Every error the API returns has the shape::

    {"error": {"code": "validation_error", "message": "...", "fields": {...}}}

``fields`` is only present for validation errors. Internal details (stack traces,
SQL, exception messages) are logged server-side and never returned to the client.
"""

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException


class APIError(Exception):
    """An error that is safe to show to the client."""

    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        fields: dict[str, str] | None = None,
        extra: dict | None = None,
    ):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.fields = fields
        self.extra = extra or {}

    def to_response(self):
        body = {"code": self.code, "message": self.message, **self.extra}
        if self.fields:
            body["fields"] = self.fields
        return jsonify(error=body), self.status


class ValidationError(APIError):
    def __init__(self, fields: dict[str, str], message: str = "Some fields are invalid."):
        super().__init__(422, "validation_error", message, fields)


class NotFound(APIError):
    def __init__(self, message: str = "Resource not found."):
        super().__init__(404, "not_found", message)


class Conflict(APIError):
    def __init__(self, message: str):
        super().__init__(409, "conflict", message)


class Unauthorized(APIError):
    def __init__(self, message: str = "Authentication is required."):
        super().__init__(401, "unauthorized", message)


class Forbidden(APIError):
    def __init__(self, message: str = "You do not have permission to do that."):
        super().__init__(403, "forbidden", message)


def _http_code(exc: HTTPException) -> str:
    return (exc.name or "error").lower().replace(" ", "_")


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(APIError)
    def handle_api_error(exc: APIError):
        return exc.to_response()

    @app.errorhandler(HTTPException)
    def handle_http_error(exc: HTTPException):
        status = exc.code or 500
        return jsonify(error={"code": _http_code(exc), "message": exc.description}), status

    @app.errorhandler(Exception)
    def handle_unexpected_error(exc: Exception):
        app.logger.exception("Unhandled error")
        return (
            jsonify(error={"code": "internal_error", "message": "Something went wrong."}),
            500,
        )
