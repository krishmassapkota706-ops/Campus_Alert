"""Request-body validation with pydantic, mapped onto the API error format."""

import pydantic
from flask import request

from .errors import ValidationError


class Schema(pydantic.BaseModel):
    """Base class for request schemas: strips whitespace and rejects unknown fields."""

    model_config = pydantic.ConfigDict(str_strip_whitespace=True, extra="forbid")


def _field_name(loc: tuple) -> str:
    return ".".join(str(part) for part in loc) or "body"


def parse_body[T: pydantic.BaseModel](schema: type[T]) -> T:
    """Validate the JSON request body against ``schema`` or raise ``ValidationError``."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValidationError({"body": "Request body must be a JSON object."})
    try:
        return schema.model_validate(data)
    except pydantic.ValidationError as exc:
        fields: dict[str, str] = {}
        for err in exc.errors():
            message = err["msg"].removeprefix("Value error, ")
            fields.setdefault(_field_name(err["loc"]), message)
        raise ValidationError(fields) from None
