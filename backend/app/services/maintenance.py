"""Database backup, restore, and cleanup for the self-hosted SQLite deployment (RD FR-3.6.6).

Backups use SQLite's online backup API, so they are consistent even while the
server is running. Reporter IDs inside a backup are encrypted: keep a copy of
``DATA_ENCRYPTION_KEY`` somewhere safe, or the backup can't be fully read.
"""

import sqlite3
from contextlib import closing
from datetime import timedelta
from pathlib import Path

from flask import current_app

from ..extensions import db
from ..models import RevokedToken, User, VerificationCode, utcnow

BACKUP_PREFIX = "reportsdstate-"


def database_path() -> Path:
    url = db.engine.url
    if url.get_backend_name() != "sqlite" or not url.database or url.database == ":memory:":
        raise RuntimeError("Backups are only supported for a file-based SQLite database.")
    return Path(url.database)


def _copy(source: Path, target: Path) -> None:
    with closing(sqlite3.connect(source)) as src, closing(sqlite3.connect(target)) as dst:
        src.backup(dst)


def backup_database(dest_dir: Path, keep: int) -> Path:
    """Write a timestamped copy to ``dest_dir`` and delete all but the newest ``keep``."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    target = dest_dir / f"{BACKUP_PREFIX}{utcnow():%Y%m%d-%H%M%S}.db"
    _copy(database_path(), target)
    backups = sorted(dest_dir.glob(f"{BACKUP_PREFIX}*.db"))
    for old in backups[:-keep] if keep > 0 else []:
        old.unlink()
    return target


def _check_backup(path: Path) -> None:
    if not path.is_file():
        raise RuntimeError(f"Backup not found: {path}")
    with closing(sqlite3.connect(f"file:{path}?mode=ro", uri=True)) as conn:
        if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("Backup failed SQLite integrity check.")
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master")}
    if "users" not in tables or "alembic_version" not in tables:
        raise RuntimeError("That file doesn't look like a ReportSDState database backup.")


def restore_database(backup_file: Path, safety_dir: Path) -> Path:
    """Replace the live database with ``backup_file``.

    The current database is first copied to ``safety_dir`` so the restore itself can be
    undone. Returns the path of that safety copy.
    """
    _check_backup(backup_file)
    safety_dir.mkdir(parents=True, exist_ok=True)
    safety_copy = safety_dir / f"pre-restore-{utcnow():%Y%m%d-%H%M%S}.db"
    live = database_path()
    _copy(live, safety_copy)
    db.session.remove()
    db.engine.dispose()
    _copy(backup_file, live)
    return safety_copy


def prune_expired(unverified_after_days: int = 7) -> dict[str, int]:
    """Delete data the app no longer needs (data minimization, RD FR-3.7.4)."""
    now = utcnow()
    removed = {
        "revoked_tokens": db.session.execute(
            db.delete(RevokedToken).where(RevokedToken.expires_at < now)
        ).rowcount,
        "verification_codes": db.session.execute(
            db.delete(VerificationCode).where(VerificationCode.expires_at < now - timedelta(days=1))
        ).rowcount,
    }
    stale = db.session.scalars(
        db.select(User).where(
            User.email_verified_at.is_(None),
            User.created_at < now - timedelta(days=unverified_after_days),
        )
    ).all()
    for user in stale:
        db.session.delete(user)
    removed["unverified_users"] = len(stale)
    db.session.commit()
    current_app.logger.info("Pruned expired data: %s", removed)
    return removed
