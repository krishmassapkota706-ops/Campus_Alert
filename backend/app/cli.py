"""Management commands: ``flask --app wsgi <command>``.

Schema changes go through Alembic (``flask --app wsgi db migrate -m "..."``), and
``init-db`` applies every migration.
"""

from pathlib import Path

import click
from flask import Flask, current_app
from flask_migrate import upgrade

from .seed import seed_demo_data
from .services.maintenance import backup_database, prune_expired, restore_database
from .services.resources import load_resources


def _backup_dir() -> Path:
    return Path(current_app.config["BACKUP_DIR"] or Path(current_app.instance_path) / "backups")


def register_cli(app: Flask) -> None:
    @app.cli.command("init-db")
    def init_db() -> None:
        """Create or upgrade the database schema to the latest migration."""
        upgrade()
        click.echo("Database schema is up to date.")

    @app.cli.command("seed-db")
    def seed_db() -> None:
        """Insert synthetic demo users, contacts and reports, plus the resource directory."""
        upgrade()
        created = seed_demo_data()
        created["resources"] = load_resources()
        click.echo(", ".join(f"{count} {name}" for name, count in created.items()) + " created.")

    @app.cli.command("seed-resources")
    @click.option("--replace", is_flag=True, help="Delete existing resources and reload the file.")
    def seed_resources(replace: bool) -> None:
        """Load the SDSU resource directory from app/data/resources.json."""
        count = load_resources(replace=replace)
        click.echo(f"{count} resources loaded." if count else "Resources already loaded.")

    @app.cli.command("backup-db")
    @click.option("--dest", type=click.Path(path_type=Path), help="Backup folder.")
    @click.option("--keep", default=14, show_default=True, help="How many backups to keep.")
    def backup_db(dest: Path | None, keep: int) -> None:
        """Copy the live database to a timestamped backup file."""
        path = backup_database(dest or _backup_dir(), keep)
        click.echo(f"Backup written to {path}")

    @app.cli.command("restore-db")
    @click.argument("backup_file", type=click.Path(path_type=Path, exists=True, dir_okay=False))
    @click.option("--yes", is_flag=True, help="Don't ask for confirmation.")
    def restore_db(backup_file: Path, yes: bool) -> None:
        """Replace the live database with BACKUP_FILE. Stop the server first."""
        if not yes:
            click.confirm(
                "This replaces the live database (a safety copy is kept). Continue?", abort=True
            )
        safety = restore_database(backup_file, _backup_dir())
        click.echo(f"Restored {backup_file}. Previous database saved to {safety}")

    @app.cli.command("prune-db")
    @click.option("--unverified-days", default=7, show_default=True)
    def prune_db(unverified_days: int) -> None:
        """Delete expired tokens and codes, and accounts never verified."""
        removed = prune_expired(unverified_days)
        click.echo(", ".join(f"{count} {name}" for name, count in removed.items()) + " removed.")
