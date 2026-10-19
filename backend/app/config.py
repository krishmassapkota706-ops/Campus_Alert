"""Application configuration, read from environment variables.

Secrets are never hard-coded for production: ``ProductionConfig.validate`` refuses
to start the app when a required secret is missing.
"""

import os
from datetime import timedelta

from .security.crypto import derive_dev_key

_DEV_ONLY = "dev-only-insecure-"


def _csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


class Config:
    APP_ENV = "development"
    TESTING = False

    SECRET_KEY = os.environ.get("SECRET_KEY") or _DEV_ONLY + "secret-key"
    CORS_ORIGINS = _csv(os.environ.get("CORS_ORIGINS", "http://localhost:8081"))

    # Relative sqlite paths resolve inside backend/instance/.
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///reportsdstate.db")

    # Field-level encryption for reporter IDs (see app/security/crypto.py).
    DATA_ENCRYPTION_KEY = os.environ.get("DATA_ENCRYPTION_KEY") or derive_dev_key("encryption")
    DATA_HMAC_KEY = os.environ.get("DATA_HMAC_KEY") or _DEV_ONLY + "hmac-key"

    # Auth tokens (flask-jwt-extended). Sent as "Authorization: Bearer <token>".
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY") or _DEV_ONLY + "jwt-secret"
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=int(os.environ.get("JWT_ACCESS_MINUTES", "15")))
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=int(os.environ.get("JWT_REFRESH_DAYS", "30")))
    JWT_TOKEN_LOCATION = ["headers"]

    # Only these email domains can register (RD US-01).
    ALLOWED_EMAIL_DOMAINS = _csv(os.environ.get("ALLOWED_EMAIL_DOMAINS", "jacks.sdstate.edu"))
    VERIFICATION_CODE_TTL_MINUTES = 15
    VERIFICATION_MAX_ATTEMPTS = 5

    # Outbound email: console | smtp | memory (see app/services/mailer.py).
    MAIL_BACKEND = os.environ.get("MAIL_BACKEND", "console")
    MAIL_FROM = os.environ.get("MAIL_FROM", "ReportSDState <no-reply@reportsdstate.local>")
    SMTP_HOST = os.environ.get("SMTP_HOST", "")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
    SMTP_USERNAME = os.environ.get("SMTP_USERNAME", "")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")

    # Rate limiting (Flask-Limiter). Use a shared store such as redis:// with >1 worker.
    RATELIMIT_ENABLED = True
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_HEADERS_ENABLED = True

    # Emergency workflow. In demo mode every call button dials DEMO_CALL_NUMBER instead of
    # the real number, so no real emergency call is placed (RD US-07, NFR-3.2.13).
    DEMO_MODE = os.environ.get("DEMO_MODE", "true").lower() in ("1", "true", "yes")
    DEMO_CALL_NUMBER = os.environ.get("DEMO_CALL_NUMBER", "+16055550100")  # fictional 555 number
    CAMPUS_POLICE_NUMBER = os.environ.get("CAMPUS_POLICE_NUMBER", "+16056885117")
    CRISIS_LINE_NUMBER = os.environ.get("CRISIS_LINE_NUMBER", "988")

    # Location-sharing SMS: mock | twilio. DEMO_MODE always forces mock.
    SMS_MODE = os.environ.get("SMS_MODE", "mock")
    TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
    TWILIO_FROM_NUMBER = os.environ.get("TWILIO_FROM_NUMBER", "")

    # Where `flask backup-db` writes. Empty means backend/instance/backups/.
    BACKUP_DIR = os.environ.get("BACKUP_DIR", "")

    # Number of reverse proxies in front of the app (Caddy, nginx, Cloudflare Tunnel).
    # Needed so rate limits see the real client IP. 0 = the app is exposed directly.
    TRUSTED_PROXIES = int(os.environ.get("TRUSTED_PROXIES", "0"))

    # Secrets that must be provided through the environment in production.
    REQUIRED_SECRETS: tuple[str, ...] = (
        "SECRET_KEY",
        "JWT_SECRET_KEY",
        "DATA_ENCRYPTION_KEY",
        "DATA_HMAC_KEY",
    )

    @classmethod
    def validate(cls) -> None:
        """Hook for environment-specific checks. Raises RuntimeError on bad config."""


class DevelopmentConfig(Config):
    pass


class TestingConfig(Config):
    APP_ENV = "testing"
    TESTING = True
    SECRET_KEY = "test-secret-key"  # noqa: S105 (test-only value)
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    DATA_ENCRYPTION_KEY = derive_dev_key("testing")
    DATA_HMAC_KEY = "test-hmac-key"  # noqa: S105 (test-only value)
    JWT_SECRET_KEY = "test-jwt-secret-key-that-is-long-enough"  # noqa: S105 (test-only value)
    MAIL_BACKEND = "memory"
    RATELIMIT_ENABLED = False
    # Fast, weak hashing so the suite runs quickly. Never use outside tests.
    DEMO_MODE = True
    DEMO_CALL_NUMBER = "+16055550100"
    PASSWORD_HASH_METHOD = "pbkdf2:sha256:1000"  # noqa: S105 (algorithm name)


class ProductionConfig(Config):
    APP_ENV = "production"
    MAIL_BACKEND = os.environ.get("MAIL_BACKEND", "smtp")

    @classmethod
    def validate(cls) -> None:
        required = list(cls.REQUIRED_SECRETS)
        if cls.SMS_MODE == "twilio" and not cls.DEMO_MODE:
            required += ["TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_FROM_NUMBER"]
        missing = [name for name in required if not os.environ.get(name)]
        if missing:
            raise RuntimeError(
                "Missing required environment variables for production: " + ", ".join(missing)
            )


CONFIGS: dict[str, type[Config]] = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def get_config(name: str | None = None) -> type[Config]:
    name = name or os.environ.get("APP_ENV", "development")
    try:
        return CONFIGS[name]
    except KeyError as exc:
        raise RuntimeError(f"Unknown APP_ENV '{name}'. Expected one of {sorted(CONFIGS)}") from exc
