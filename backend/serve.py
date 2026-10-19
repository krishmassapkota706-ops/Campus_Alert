"""Production server: ``python serve.py`` (waitress works on Windows and Linux).

Reads HOST, PORT, and WAITRESS_THREADS from the environment. Put an HTTPS reverse
proxy (Caddy, nginx, or a Cloudflare Tunnel) in front and set TRUSTED_PROXIES=1.
"""

import logging
import os

from waitress import serve

from wsgi import app

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    serve(
        app,
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "5000")),
        threads=int(os.environ.get("WAITRESS_THREADS", "8")),
    )
