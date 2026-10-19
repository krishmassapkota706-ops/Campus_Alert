"""SDSU resource directory, loaded from ``app/data/resources.json``."""

import json
from datetime import date
from pathlib import Path

from ..extensions import db
from ..models import Resource, ResourceCategory
from .emergency import dial_number

RESOURCES_FILE = Path(__file__).resolve().parent.parent / "data" / "resources.json"


def load_resources(replace: bool = False, path: Path = RESOURCES_FILE) -> int:
    """Insert resources from the JSON file. With ``replace``, existing rows are removed first.

    Returns the number of rows inserted (0 if the table already had data and
    ``replace`` is false).
    """
    if replace:
        db.session.execute(db.delete(Resource))
    elif db.session.scalar(db.select(Resource.id).limit(1)):
        return 0
    entries = json.loads(path.read_text(encoding="utf-8"))["resources"]
    for order, entry in enumerate(entries):
        db.session.add(
            Resource(
                category=ResourceCategory(entry["category"]),
                name=entry["name"],
                description=entry.get("description", ""),
                phone=entry.get("phone"),
                sms=entry.get("sms"),
                url=entry.get("url"),
                available_24_7=entry.get("available_24_7", False),
                sort_order=order,
                source_url=entry.get("source_url"),
                verified_on=date.fromisoformat(entry["verified_on"])
                if entry.get("verified_on")
                else None,
            )
        )
    db.session.commit()
    return len(entries)


def search_resources(
    category: ResourceCategory | None = None, query: str | None = None
) -> list[Resource]:
    stmt = db.select(Resource)
    if category:
        stmt = stmt.filter_by(category=category)
    if query:
        pattern = f"%{query.strip()}%"
        stmt = stmt.where(Resource.name.ilike(pattern) | Resource.description.ilike(pattern))
    return list(db.session.scalars(stmt.order_by(Resource.sort_order, Resource.name)))


def resource_to_dict(resource: Resource) -> dict:
    """Public shape. ``dial_number`` is what the app should call (a test number in demo mode)."""
    body = resource.to_dict()
    body["dial_number"] = dial_number(resource.phone) if resource.phone else None
    return body
