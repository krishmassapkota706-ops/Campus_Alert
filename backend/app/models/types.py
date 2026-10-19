from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum
from sqlalchemy.types import TypeDecorator


def utcnow() -> datetime:
    return datetime.now(UTC)


class UTCDateTime(TypeDecorator):
    """Stores datetimes as UTC and always returns timezone-aware values.

    SQLite has no timezone support, so values come back naive; this re-attaches UTC.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("Naive datetimes are not allowed; use timezone-aware UTC.")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect):
        return value.replace(tzinfo=UTC) if value is not None else None


def isoformat(value: datetime | None) -> str | None:
    return value.isoformat().replace("+00:00", "Z") if value else None


def str_enum(enum_cls: type[StrEnum]) -> Enum:
    """Store a StrEnum by value in a VARCHAR column (portable across databases)."""
    return Enum(
        enum_cls, native_enum=False, length=20, values_callable=lambda e: [m.value for m in e]
    )
