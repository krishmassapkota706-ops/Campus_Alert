"""Database management commands: ``flask --app wsgi <command>``."""

import click
from flask import Flask

from .extensions import db
from .seed import seed_demo_data
from .services.resources import load_resources


def register_cli(app: Flask) -> None:
    @app.cli.command("init-db")
    @click.option("--drop", is_flag=True, help="Drop all tables first (destroys data).")
    def init_db(drop: bool) -> None:
        """Create any missing tables."""
        if drop:
            click.confirm("This deletes every row in the database. Continue?", abort=True)
            db.drop_all()
        db.create_all()
        click.echo("Database tables are ready.")

    @app.cli.command("seed-db")
    def seed_db() -> None:
        """Insert synthetic demo users, contacts and reports, plus the resource directory."""
        db.create_all()
        created = seed_demo_data()
        created["resources"] = load_resources()
        click.echo(", ".join(f"{count} {name}" for name, count in created.items()) + " created.")

    @app.cli.command("seed-resources")
    @click.option("--replace", is_flag=True, help="Delete existing resources and reload the file.")
    def seed_resources(replace: bool) -> None:
        """Load the SDSU resource directory from app/data/resources.json."""
        db.create_all()
        count = load_resources(replace=replace)
        click.echo(f"{count} resources loaded." if count else "Resources already loaded.")
