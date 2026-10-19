from datetime import datetime
from enum import StrEnum

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..extensions import db
from .types import UTCDateTime, isoformat, str_enum, utcnow


class EmergencyAction(StrEnum):
    CALL_CAMPUS_POLICE = "call_campus_police"
    CALL_911 = "call_911"
    CALL_CRISIS_LINE = "call_crisis_line"
    CALL_CONTACT = "call_contact"


class EmergencyEvent(db.Model):
    """Record that an emergency action was started, for status feedback (RD FR-3.3.5).

    Deliberately minimal: no location and no free text. The user is stored the same
    way as on reports (encrypted + blind index).
    """

    __tablename__ = "emergency_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    action: Mapped[EmergencyAction] = mapped_column(str_enum(EmergencyAction))
    simulated: Mapped[bool] = mapped_column(default=True)
    user_ref_enc: Mapped[str] = mapped_column(Text)
    user_ref_idx: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "action": self.action.value,
            "simulated": self.simulated,
            "created_at": isoformat(self.created_at),
        }
