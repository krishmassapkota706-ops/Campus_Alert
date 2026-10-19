import secrets
from datetime import datetime
from enum import StrEnum

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..extensions import db
from .types import UTCDateTime, isoformat, str_enum, utcnow

# No 0/O/1/I so reference IDs are easy to read back over the phone.
_REFERENCE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


class ReportCategory(StrEnum):
    EMERGENCY = "emergency"
    MAINTENANCE = "maintenance"
    CRIME = "crime"
    OTHER = "other"


class ReportStatus(StrEnum):
    SUBMITTED = "submitted"
    IN_REVIEW = "in_review"
    RESOLVED = "resolved"


def new_reference_id(category: ReportCategory) -> str:
    prefix = "EMG" if category is ReportCategory.EMERGENCY else "RPT"
    suffix = "".join(secrets.choice(_REFERENCE_ALPHABET) for _ in range(6))
    return f"{prefix}-{suffix}"


class Report(db.Model):
    """A submitted report. The reporter is stored only in encrypted / blind-indexed form."""

    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    reference_id: Mapped[str] = mapped_column(String(12), unique=True)
    category: Mapped[ReportCategory] = mapped_column(str_enum(ReportCategory))
    status: Mapped[ReportStatus] = mapped_column(
        str_enum(ReportStatus), default=ReportStatus.SUBMITTED
    )
    location_text: Mapped[str] = mapped_column(String(200))
    details: Mapped[str] = mapped_column(Text)

    # See app/security/crypto.py. Never store the plain user ID here.
    reporter_ref_enc: Mapped[str] = mapped_column(Text)
    reporter_ref_idx: Mapped[str] = mapped_column(String(64), index=True)

    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "reference_id": self.reference_id,
            "category": self.category.value,
            "status": self.status.value,
            "location": self.location_text,
            "details": self.details,
            "created_at": isoformat(self.created_at),
        }
