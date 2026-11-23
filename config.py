"""Application configuration.

All secrets come from environment variables. A local SQLite database is used
only when DATABASE_URL is absent, which keeps tests and first-run development
simple. Production must provide a Neon PostgreSQL DATABASE_URL.
"""

from __future__ import annotations

import os
from dotenv import load_dotenv

load_dotenv()


def _database_uri() -> str:
    uri = os.environ.get("DATABASE_URL") or "sqlite:///gymlog.db"
    # SQLAlchemy 2.x uses psycopg 3 when the driver is named explicitly.
    if uri.startswith("postgres://"):
        uri = "postgresql+psycopg://" + uri[len("postgres://") :]
    elif uri.startswith("postgresql://"):
        uri = "postgresql+psycopg://" + uri[len("postgresql://") :]
    return uri


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or "dev-only-insecure-secret-change-me"
    SQLALCHEMY_DATABASE_URI = _database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = (
        {"pool_pre_ping": True, "pool_size": 5, "max_overflow": 10}
        if not SQLALCHEMY_DATABASE_URI.startswith("sqlite")
        else {"connect_args": {"check_same_thread": False}}
    )
    APP_PASSWORD = os.environ.get("APP_PASSWORD", "").strip()
    PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "http://localhost:5000").rstrip("/")
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024
    TEMPLATES_AUTO_RELOAD = True
    PREFERRED_URL_SCHEME = "https" if PUBLIC_BASE_URL.startswith("https://") else "http"
