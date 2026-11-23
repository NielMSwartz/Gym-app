"""WSGI entry point used by Gunicorn, Render and the Flask CLI."""

from __future__ import annotations

import logging
import os

from gymlog import create_app

app = create_app()

if not app.debug:
    # Gunicorn owns stderr on Render. Reuse its handlers when present so
    # application logs land in the same stream as access and error logs.
    gunicorn_logger = logging.getLogger("gunicorn.error")
    if gunicorn_logger.handlers:
        app.logger.handlers = gunicorn_logger.handlers
        app.logger.setLevel(gunicorn_logger.level)
    else:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        )
        app.logger.setLevel(logging.INFO)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
