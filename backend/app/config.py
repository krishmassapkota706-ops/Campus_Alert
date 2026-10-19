"""Application configuration, read from environment variables.

Secrets are never hard-coded for production: ``ProductionConfig.validate`` refuses
to start the app when a required secret is missing.
"""

import os

_DEV_ONLY = "dev-only-insecure-"


def _csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


class Config:
    APP_ENV = "development"
    TESTING = False

    SECRET_KEY = os.environ.get("SECRET_KEY") or _DEV_ONLY + "secret-key"
    CORS_ORIGINS = _csv(os.environ.get("CORS_ORIGINS", "http://localhost:8081"))

    # Secrets that must be provided through the environment in production.
    REQUIRED_SECRETS: tuple[str, ...] = ("SECRET_KEY",)

    @classmethod
    def validate(cls) -> None:
        """Hook for environment-specific checks. Raises RuntimeError on bad config."""


class DevelopmentConfig(Config):
    pass


class TestingConfig(Config):
    APP_ENV = "testing"
    TESTING = True
    SECRET_KEY = "test-secret-key"  # noqa: S105 (test-only value)


class ProductionConfig(Config):
    APP_ENV = "production"

    @classmethod
    def validate(cls) -> None:
        missing = [
            name
            for name in cls.REQUIRED_SECRETS
            if not os.environ.get(name) or str(getattr(cls, name, "")).startswith(_DEV_ONLY)
        ]
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
