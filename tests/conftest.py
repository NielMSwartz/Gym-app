"""Shared test fixtures using an isolated in-memory SQLite database."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import Config  # noqa: E402
from gymlog import DEFAULT_EXERCISES, _ensure_bootstrap, create_app  # noqa: E402
from gymlog.extensions import db  # noqa: E402
from gymlog.models import Exercise, Program, User  # noqa: E402


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret-key"
    APP_PASSWORD = ""
    PUBLIC_BASE_URL = "http://localhost"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_ENGINE_OPTIONS = {"connect_args": {"check_same_thread": False}}


@pytest.fixture()
def app():
    application = create_app(TestConfig)
    with application.app_context():
        db.create_all()
        _ensure_bootstrap()
        user = User.query.first()
        for name, muscle, category, equipment, is_bodyweight in DEFAULT_EXERCISES:
            db.session.add(
                Exercise(
                    user_id=user.id,
                    name=name,
                    muscle_group=muscle,
                    category=category,
                    equipment=equipment,
                    is_bodyweight=is_bodyweight,
                )
            )
        db.session.commit()
    yield application
    with application.app_context():
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def make_program(client, app, name: str = "Test Block"):
    """Create an eight-week program through the real builder endpoint."""
    from gymlog.services import blank_program_payload

    payload = blank_program_payload(8)
    payload["name"] = name
    response = client.post("/programs/new", data={"payload": json.dumps(payload)})
    assert response.status_code == 302
    with app.app_context():
        program = Program.query.filter_by(name=name).first()
        assert program is not None
        return program.id
