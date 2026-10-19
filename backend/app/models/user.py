from datetime import datetime
from enum import StrEnum

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import db
from .types import UTCDateTime, isoformat, str_enum, utcnow


class Role(StrEnum):
    STUDENT = "student"
    MAINTAINER = "maintainer"


class User(db.Model):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str | None] = mapped_column(String(20))
    role: Mapped[Role] = mapped_column(str_enum(Role), default=Role.STUDENT)
    email_verified_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    # Bumped on password reset; tokens carrying an older version are rejected.
    token_version: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)

    contacts: Mapped[list["EmergencyContact"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="EmergencyContact.id",
    )

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def is_verified(self) -> bool:
        return self.email_verified_at is not None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "phone": self.phone,
            "role": self.role.value,
            "email_verified": self.is_verified,
            "created_at": isoformat(self.created_at),
        }


class EmergencyContact(db.Model):
    __tablename__ = "emergency_contacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str] = mapped_column(String(20))  # E.164, e.g. +16055550199
    relationship_label: Mapped[str | None] = mapped_column("relationship", String(50))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    user: Mapped[User] = relationship(back_populates="contacts")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "phone": self.phone,
            "relationship": self.relationship_label,
        }
