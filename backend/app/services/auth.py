"""Account registration, email verification, login, and password reset."""

import hashlib
import hmac
import re
import secrets
from datetime import UTC, datetime, timedelta

from flask import current_app
from flask_jwt_extended import create_access_token, create_refresh_token, decode_token
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from ..errors import APIError, Conflict
from ..extensions import db
from ..models import CodePurpose, RevokedToken, User, VerificationCode, utcnow
from .mailer import MailError, send_mail

_LOCAL_PART = re.compile(r"^[A-Za-z0-9._%+-]+$")

# Compared against when the email is unknown, so login takes the same time either way.
_DUMMY_PASSWORD_HASH = generate_password_hash("not-a-real-password")

PASSWORD_MIN_LENGTH = 10
PASSWORD_MAX_LENGTH = 128


class InvalidCode(APIError):
    def __init__(self):
        super().__init__(400, "invalid_code", "The code is invalid or has expired.")


class InvalidCredentials(APIError):
    def __init__(self):
        super().__init__(401, "invalid_credentials", "Email or password is incorrect.")


class EmailNotVerified(APIError):
    def __init__(self):
        super().__init__(403, "email_not_verified", "Verify your SDSU email before signing in.")


class EmailUnavailable(APIError):
    def __init__(self):
        super().__init__(
            503,
            "email_unavailable",
            "We couldn't send the email right now. Please try again in a few minutes.",
        )


# ---- Validation rules (used by the request schemas) ----


def normalize_email(email: str) -> str:
    return email.strip().lower()


def check_sdsu_email(email: str) -> str:
    """Return the normalised email or raise ValueError if it isn't an allowed SDSU address."""
    email = normalize_email(email)
    local, sep, domain = email.rpartition("@")
    if not sep or not local or not _LOCAL_PART.match(local):
        raise ValueError("Enter a valid email address.")
    allowed = current_app.config["ALLOWED_EMAIL_DOMAINS"]
    if domain not in allowed:
        raise ValueError(f"Use your SDSU school email (@{allowed[0]}).")
    return email


def check_password_rules(password: str) -> str:
    if len(password) < PASSWORD_MIN_LENGTH:
        raise ValueError(f"Password must be at least {PASSWORD_MIN_LENGTH} characters.")
    if len(password) > PASSWORD_MAX_LENGTH:
        raise ValueError(f"Password must be at most {PASSWORD_MAX_LENGTH} characters.")
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        raise ValueError("Password must contain at least one letter and one number.")
    return password


# ---- One-time codes ----


def _hash_code(user_id: int, purpose: CodePurpose, code: str) -> str:
    key = current_app.config["SECRET_KEY"].encode()
    return hmac.new(key, f"{user_id}:{purpose}:{code}".encode(), hashlib.sha256).hexdigest()


def issue_code(user: User, purpose: CodePurpose) -> str:
    """Create a new 6-digit code, invalidating any earlier unused code for the same purpose."""
    now = utcnow()
    db.session.execute(
        db.update(VerificationCode)
        .where(
            VerificationCode.user_id == user.id,
            VerificationCode.purpose == purpose,
            VerificationCode.used_at.is_(None),
        )
        .values(used_at=now)
    )
    code = f"{secrets.randbelow(1_000_000):06d}"
    ttl = timedelta(minutes=current_app.config["VERIFICATION_CODE_TTL_MINUTES"])
    db.session.add(
        VerificationCode(
            user_id=user.id,
            purpose=purpose,
            code_hash=_hash_code(user.id, purpose, code),
            expires_at=now + ttl,
        )
    )
    return code


def consume_code(user: User, purpose: CodePurpose, code: str) -> None:
    """Mark the user's active code as used, or raise ``InvalidCode``.

    Wrong guesses are counted and committed even though the request fails, so the
    attempt limit can't be bypassed by retrying.
    """
    record = db.session.scalar(
        db.select(VerificationCode)
        .where(
            VerificationCode.user_id == user.id,
            VerificationCode.purpose == purpose,
            VerificationCode.used_at.is_(None),
        )
        .order_by(VerificationCode.id.desc())
        .limit(1)
    )
    max_attempts = current_app.config["VERIFICATION_MAX_ATTEMPTS"]
    if record is None or record.expires_at <= utcnow() or record.attempts >= max_attempts:
        raise InvalidCode()
    if not hmac.compare_digest(record.code_hash, _hash_code(user.id, purpose, code)):
        record.attempts += 1
        db.session.commit()
        raise InvalidCode()
    record.used_at = utcnow()


def _send_code(user: User, purpose: CodePurpose, code: str) -> None:
    minutes = current_app.config["VERIFICATION_CODE_TTL_MINUTES"]
    if purpose is CodePurpose.VERIFY_EMAIL:
        subject = "Your ReportSDState verification code"
        intro = "Use this code to finish creating your ReportSDState account:"
    else:
        subject = "Reset your ReportSDState password"
        intro = "Use this code to reset your ReportSDState password:"
    body = (
        f"{intro}\n\n    {code}\n\nThe code expires in {minutes} minutes. "
        "If you didn't request this, you can ignore this email."
    )
    try:
        send_mail(user.email, subject, body)
    except MailError:
        current_app.logger.exception("Failed to send %s email", purpose)
        raise EmailUnavailable() from None


def _find_user(email: str) -> User | None:
    return db.session.scalar(db.select(User).filter_by(email=normalize_email(email)))


# ---- Registration and verification ----


def register(email: str, password: str, name: str) -> User:
    """Create an unverified account and email a verification code.

    The account can't sign in until the code is confirmed. If the email can't be
    sent, nothing is saved (RD FR-3.1.1 exception handling).
    """
    if _find_user(email):
        raise Conflict("An account with this email already exists.")
    user = User(email=email, name=name)
    user.set_password(password)
    db.session.add(user)
    db.session.flush()
    code = issue_code(user, CodePurpose.VERIFY_EMAIL)
    try:
        _send_code(user, CodePurpose.VERIFY_EMAIL, code)
    except EmailUnavailable:
        db.session.rollback()
        raise
    try:
        db.session.commit()
    except IntegrityError:  # lost a race with a concurrent registration
        db.session.rollback()
        raise Conflict("An account with this email already exists.") from None
    return user


def verify_email(email: str, code: str) -> User:
    user = _find_user(email)
    if user is None or user.is_verified:
        raise InvalidCode()
    consume_code(user, CodePurpose.VERIFY_EMAIL, code)
    user.email_verified_at = utcnow()
    db.session.commit()
    return user


def resend_verification(email: str) -> None:
    """Send a fresh code if the account exists and is unverified. Silent otherwise."""
    user = _find_user(email)
    if user is None or user.is_verified:
        return
    code = issue_code(user, CodePurpose.VERIFY_EMAIL)
    _send_code(user, CodePurpose.VERIFY_EMAIL, code)
    db.session.commit()


# ---- Login, tokens, logout ----


def authenticate(email: str, password: str) -> User:
    user = _find_user(email)
    if user is None:
        check_password_hash(_DUMMY_PASSWORD_HASH, password)
        raise InvalidCredentials()
    if not user.check_password(password):
        raise InvalidCredentials()
    if not user.is_verified:
        raise EmailNotVerified()
    return user


def _expires_in() -> int:
    return int(current_app.config["JWT_ACCESS_TOKEN_EXPIRES"].total_seconds())


def issue_tokens(user: User) -> dict:
    refresh_token = create_refresh_token(identity=user)
    refresh_jti = decode_token(refresh_token)["jti"]
    return {
        "access_token": create_access_token(identity=user, additional_claims={"rjti": refresh_jti}),
        "refresh_token": refresh_token,
        "token_type": "Bearer",
        "expires_in": _expires_in(),
    }


def refresh_access_token(user: User, refresh_jti: str) -> dict:
    return {
        "access_token": create_access_token(identity=user, additional_claims={"rjti": refresh_jti}),
        "token_type": "Bearer",
        "expires_in": _expires_in(),
    }


def revoke_token(jti: str, expires_at_epoch: int) -> None:
    if is_revoked(jti):
        return
    expires_at = datetime.fromtimestamp(expires_at_epoch, UTC)
    db.session.add(RevokedToken(jti=jti, expires_at=expires_at))


def is_revoked(jti: str) -> bool:
    return db.session.scalar(db.select(RevokedToken.id).filter_by(jti=jti)) is not None


def logout(claims: dict) -> None:
    """Revoke the presented token and the refresh token it belongs to."""
    revoke_token(claims["jti"], claims["exp"])
    if claims.get("type") == "access" and claims.get("rjti"):
        refresh_ttl = current_app.config["JWT_REFRESH_TOKEN_EXPIRES"]
        revoke_token(claims["rjti"], claims["iat"] + int(refresh_ttl.total_seconds()))
    db.session.commit()


# ---- Password reset ----


def request_password_reset(email: str) -> None:
    """Email a reset code if the account exists. Silent otherwise (no account enumeration)."""
    user = _find_user(email)
    if user is None or not user.is_verified:
        return
    code = issue_code(user, CodePurpose.RESET_PASSWORD)
    _send_code(user, CodePurpose.RESET_PASSWORD, code)
    db.session.commit()


def reset_password(email: str, code: str, new_password: str) -> None:
    user = _find_user(email)
    if user is None:
        raise InvalidCode()
    consume_code(user, CodePurpose.RESET_PASSWORD, code)
    user.set_password(new_password)
    user.token_version += 1  # signs out every existing session
    db.session.commit()
