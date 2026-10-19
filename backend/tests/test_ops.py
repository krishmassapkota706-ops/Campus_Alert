"""Operations: migrations, backup/restore, pruning, security headers (FR-3.6.6, FR-3.7.4)."""

import sqlite3
from contextlib import closing
from datetime import timedelta

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from flask_migrate import upgrade

from app import create_app
from app.config import TestingConfig
from app.extensions import db as _db
from app.models import RevokedToken, User, VerificationCode, utcnow
from app.services.maintenance import backup_database, prune_expired, restore_database


@pytest.fixture
def file_app(tmp_path):
    """An app backed by a real SQLite file, built with the Alembic migrations."""

    class FileConfig(TestingConfig):
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{tmp_path / 'live.db'}"
        BACKUP_DIR = str(tmp_path / "backups")

    app = create_app(FileConfig)
    with app.app_context():
        upgrade()
        yield app
        _db.session.remove()
        _db.engine.dispose()


def add_user(email):
    user = User(email=email, name="Test", email_verified_at=utcnow())
    user.set_password("Password1234")
    _db.session.add(user)
    _db.session.commit()
    return user


def user_emails():
    return sorted(_db.session.scalars(_db.select(User.email)))


def test_migrations_match_models(file_app):
    with _db.engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), _db.metadata)
    assert diff == []


def test_backup_and_restore_round_trip(file_app, tmp_path):
    add_user("before@jacks.sdstate.edu")
    backup = backup_database(tmp_path / "backups", keep=5)
    assert backup.exists()

    add_user("after@jacks.sdstate.edu")
    assert user_emails() == ["after@jacks.sdstate.edu", "before@jacks.sdstate.edu"]

    safety = restore_database(backup, tmp_path / "backups")
    assert user_emails() == ["before@jacks.sdstate.edu"]
    with closing(sqlite3.connect(safety)) as conn:
        assert conn.execute("SELECT count(*) FROM users").fetchone()[0] == 2


def test_backup_keeps_only_newest(file_app, tmp_path, monkeypatch):
    dest = tmp_path / "backups"
    times = iter(utcnow() + timedelta(seconds=i) for i in range(5))
    monkeypatch.setattr("app.services.maintenance.utcnow", lambda: next(times))
    for _ in range(5):
        backup_database(dest, keep=3)
    assert len(list(dest.glob("reportsdstate-*.db"))) == 3


def test_restore_rejects_files_that_are_not_backups(file_app, tmp_path):
    bogus = tmp_path / "bogus.db"
    with closing(sqlite3.connect(bogus)) as conn:
        conn.execute("CREATE TABLE something (id INTEGER)")
    with pytest.raises(RuntimeError, match="doesn't look like"):
        restore_database(bogus, tmp_path / "backups")


def test_backup_requires_file_database(app, tmp_path):
    with pytest.raises(RuntimeError, match="file-based SQLite"):
        backup_database(tmp_path, keep=1)


def test_cli_backup_command(file_app, tmp_path):
    result = file_app.test_cli_runner().invoke(args=["backup-db", "--keep", "2"])
    assert result.exit_code == 0, result.output
    assert list((tmp_path / "backups").glob("reportsdstate-*.db"))


def test_prune_removes_expired_and_unverified(db):
    now = utcnow()
    old_unverified = User(
        email="old@jacks.sdstate.edu", name="Old", created_at=now - timedelta(days=8)
    )
    new_unverified = User(email="new@jacks.sdstate.edu", name="New")
    verified = User(email="ok@jacks.sdstate.edu", name="Ok", created_at=now - timedelta(days=30))
    verified.email_verified_at = now
    for user in (old_unverified, new_unverified, verified):
        user.set_password("Password1234")
        db.session.add(user)
    db.session.flush()
    db.session.add_all(
        [
            RevokedToken(jti="expired", expires_at=now - timedelta(minutes=1)),
            RevokedToken(jti="active", expires_at=now + timedelta(days=1)),
            VerificationCode(
                user_id=verified.id,
                purpose="reset_password",
                code_hash="x",
                expires_at=now - timedelta(days=2),
            ),
        ]
    )
    db.session.commit()

    assert prune_expired() == {"revoked_tokens": 1, "verification_codes": 1, "unverified_users": 1}
    assert sorted(db.session.scalars(db.select(User.email))) == [
        "new@jacks.sdstate.edu",
        "ok@jacks.sdstate.edu",
    ]
    assert db.session.scalars(db.select(RevokedToken.jti)).all() == ["active"]


def test_security_headers(client):
    headers = client.get("/api/v1/health").headers
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
    assert headers["Cache-Control"] == "no-store"
    assert "Strict-Transport-Security" not in headers  # only in production


def test_proxy_fix_uses_forwarded_client_ip():
    class ProxiedConfig(TestingConfig):
        TRUSTED_PROXIES = 1

    app = create_app(ProxiedConfig)

    @app.get("/whoami")
    def whoami():
        from flask import request

        return {"ip": request.remote_addr}

    res = app.test_client().get("/whoami", headers={"X-Forwarded-For": "203.0.113.7"})
    assert res.get_json()["ip"] == "203.0.113.7"


def test_proxy_fix_with_two_proxies_picks_client_not_spoofed_value():
    """Cloudflare Tunnel -> Caddy -> API: the client IP is second from the right."""

    class TwoProxyConfig(TestingConfig):
        TRUSTED_PROXIES = 2

    app = create_app(TwoProxyConfig)

    @app.get("/whoami")
    def whoami():
        from flask import request

        return {"ip": request.remote_addr, "scheme": request.scheme}

    res = app.test_client().get(
        "/whoami",
        headers={
            "X-Forwarded-For": "6.6.6.6, 203.0.113.7, 172.18.0.4",  # spoofed, real, cloudflared
            "X-Forwarded-Proto": "https",
        },
    )
    assert res.get_json() == {"ip": "203.0.113.7", "scheme": "https"}
