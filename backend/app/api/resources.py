"""Public resource directory: ``/api/v1/resources``.

No sign-in required: crisis and emergency information must stay reachable even
if the user is signed out (RD FR-3.3.1 exception handling).
"""

from flask import Blueprint, request

from ..errors import ValidationError
from ..models import ResourceCategory
from ..services import resources as service

bp = Blueprint("resources", __name__, url_prefix="/resources")


@bp.get("")
def list_resources():
    category = None
    if raw := request.args.get("category"):
        try:
            category = ResourceCategory(raw)
        except ValueError:
            allowed = ", ".join(c.value for c in ResourceCategory)
            raise ValidationError({"category": f"Must be one of: {allowed}."}) from None
    query = request.args.get("q", "")[:100] or None
    rows = service.search_resources(category, query)
    return {
        "resources": [service.resource_to_dict(r) for r in rows],
        "categories": [c.value for c in ResourceCategory],
    }
