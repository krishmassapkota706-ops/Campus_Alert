from datetime import date
from enum import StrEnum

from sqlalchemy import Date, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..extensions import db
from .types import str_enum


class ResourceCategory(StrEnum):
    EMERGENCY = "emergency"
    CRISIS = "crisis"
    HEALTH = "health"
    SAFETY = "safety"
    HOUSING = "housing"
    CAMPUS = "campus"


class Resource(db.Model):
    """Public contact information for an SDSU or community resource."""

    __tablename__ = "resources"

    id: Mapped[int] = mapped_column(primary_key=True)
    category: Mapped[ResourceCategory] = mapped_column(str_enum(ResourceCategory), index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    phone: Mapped[str | None] = mapped_column(String(20))
    sms: Mapped[str | None] = mapped_column(String(20))
    url: Mapped[str | None] = mapped_column(String(500))
    available_24_7: Mapped[bool] = mapped_column(default=False)
    sort_order: Mapped[int] = mapped_column(default=0)
    # Where the information came from and when someone last checked it.
    source_url: Mapped[str | None] = mapped_column(String(500))
    verified_on: Mapped[date | None] = mapped_column(Date)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "category": self.category.value,
            "name": self.name,
            "description": self.description,
            "phone": self.phone,
            "sms": self.sms,
            "url": self.url,
            "available_24_7": self.available_24_7,
            "verified_on": self.verified_on.isoformat() if self.verified_on else None,
        }
