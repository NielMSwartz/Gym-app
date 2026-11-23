"""Flask application factory."""

from __future__ import annotations

import os
from datetime import date
from functools import wraps

from flask import Flask, flash, g, redirect, render_template, request, session, url_for
from sqlalchemy.exc import SQLAlchemyError

from config import Config
from .extensions import db, migrate
from .models import AppSetting, User, utcnow
from .utils import get_setting, set_setting


DEFAULT_EXERCISES = [
    ("Barbell Bench Press", "Chest", "Compound", "Barbell", False),
    ("Incline Dumbbell Press", "Chest", "Compound", "Dumbbell", False),
    ("Chest Dips", "Chest", "Compound", "Bodyweight", True),
    ("Back Squat", "Quadriceps", "Compound", "Barbell", False),
    ("Romanian Deadlift", "Hamstrings", "Compound", "Barbell", False),
    ("Leg Curl", "Hamstrings", "Isolation", "Machine", False),
    ("Incline Bench Press", "Chest", "Compound", "Barbell", False),
    ("Overhead Press", "Shoulders", "Compound", "Barbell", False),
    ("Pull-Ups", "Back", "Compound", "Bodyweight", True),
    ("Barbell Rows", "Back", "Compound", "Barbell", False),
    ("Dumbbell Rows", "Back", "Compound", "Dumbbell", False),
    ("Lat Pulldowns", "Back", "Compound", "Cable", False),
    ("Deadlift", "Full body", "Compound", "Barbell", False),
    ("Lunge", "Quadriceps", "Compound", "Dumbbell", False),
    ("Bicep Curls", "Biceps", "Isolation", "Dumbbell", False),
    ("Triceps Pushdown", "Triceps", "Isolation", "Cable", False),
    ("Lateral Raise", "Shoulders", "Isolation", "Dumbbell", False),
    ("Plank", "Core", "Isolation", "Bodyweight", True),
    ("Hip Thrust", "Glutes", "Compound", "Barbell", False),
    ("Calf Raise", "Calves", "Isolation", "Machine", False),
]


def create_app(config_object=Config) -> Flask:
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config.from_object(config_object)

    db.init_app(app)
    migrate.init_app(app, db)

    from .routes import register_blueprints

    register_blueprints(app)

    @app.before_request
    def bootstrap_and_protect():
        _ensure_bootstrap()
        password = app.config.get("APP_PASSWORD", "")
        if not password:
            return None
        if request.endpoint in {
            "static",
            "auth.login",
            "api.health",
            "pwa.manifest",
            "pwa.service_worker",
            "pwa.offline",
        }:
            return None
        if session.get("authenticated"):
            return None
        if request.path.startswith("/api/"):
            return {"error": "Authentication required."}, 401
        return redirect(url_for("auth.login", next=request.full_path.rstrip("?")))

    @app.context_processor
    def inject_globals():
        user = getattr(g, "app_user", None)
        return {
            "app_user": user,
            "app_settings": {
                "bodyweight_kg": get_setting(user.id, "bodyweight_kg", "75") if user else "75",
                "rest_timer_seconds": get_setting(user.id, "rest_timer_seconds", "90") if user else "90",
            },
            "today": date.today(),
            "password_enabled": bool(app.config.get("APP_PASSWORD")),
        }

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(_error):
        db.session.rollback()
        return render_template("errors/500.html"), 500

    @app.errorhandler(SQLAlchemyError)
    def database_error(error):
        db.session.rollback()
        app.logger.error("Database error: %s", error)
        if request.path.startswith("/api/"):
            return {"error": "The database is temporarily unavailable."}, 503
        return render_template("errors/500.html", db_error=True), 503

    @app.cli.command("seed-exercises")
    def seed_exercises():
        """Seed the exercise library with common example exercises."""
        _ensure_bootstrap()
        user = g.get("app_user") or User.query.first()
        from .models import Exercise

        added = 0
        for name, muscle, category, equipment, is_bodyweight in DEFAULT_EXERCISES:
            exists = Exercise.query.filter_by(user_id=user.id, name=name).first()
            if exists:
                continue
            db.session.add(
                Exercise(
                    user_id=user.id,
                    name=name,
                    muscle_group=muscle,
                    category=category,
                    equipment=equipment,
                    is_bodyweight=is_bodyweight,
                    description=f"Example exercise: {name}.",
                    technique_notes="",
                )
            )
            added += 1
        db.session.commit()
        click_echo(f"Seeded {added} exercises for {user.display_name}.")

    return app


def _ensure_bootstrap() -> None:
    if getattr(g, "app_user", None) is not None:
        return
    user = User.query.order_by(User.id.asc()).first()
    if not user:
        user = User(display_name="Warrior", created_at=utcnow())
        db.session.add(user)
        db.session.flush()
        defaults = {
            "bodyweight_kg": "75",
            "rest_timer_seconds": "90",
            "include_partial_in_stats": "false",
            "theme": "iron",
        }
        for key, value in defaults.items():
            db.session.add(AppSetting(user_id=user.id, key=key, value=value))
        db.session.commit()
    g.app_user = user


def click_echo(message: str) -> None:
    import click

    click.echo(message)
