"""WSGI entry point: ``flask --app wsgi run`` or any WSGI server (``wsgi:app``)."""

from dotenv import load_dotenv

load_dotenv()

from app import create_app  # noqa: E402  (load .env before config is read)

app = create_app()
