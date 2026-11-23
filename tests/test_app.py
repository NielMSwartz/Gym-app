"""End-to-end smoke and regression tests for the Gym Logbook app."""

from __future__ import annotations

import json
from datetime import timedelta

from gymlog.extensions import db
from gymlog.models import (
    Exercise,
    PersonalRecord,
    Program,
    ProgramWeek,
    TrainingDay,
    User,
    WorkoutSession,
    utcnow,
)
from gymlog.services import blank_program_payload, program_to_dict
from gymlog.utils import get_float_setting, get_setting


def _exercise_ids(app):
    with app.app_context():
        return {row.name: row.id for row in Exercise.query.all()}


def _create_program(client, app, name="Test Block", with_day=False):
    exercise_ids = _exercise_ids(app)
    payload = blank_program_payload(exercise_ids, 8)
    payload["name"] = name
    if with_day:
        payload["weeks"][0]["days"] = [
            {
                "day_of_week": 0,
                "label": "Push",
                "is_rest": False,
                "notes": "",
                "exercises": [
                    {
                        "exercise_id": exercise_ids["Barbell Bench Press"],
                        "notes": "",
                        "progression_notes": "",
                        "sets": [
                            {"target_reps": 8, "target_weight_kg": None, "target_rpe": None, "rest_seconds": 90, "notes": ""}
                            for _ in range(3)
                        ],
                    }
                ],
            }
        ]
    response = client.post("/programs/new", data={"payload": json.dumps(payload)})
    assert response.status_code == 302
    with app.app_context():
        program = Program.query.filter_by(name=name).first()
        assert program is not None
        return program.id


def _first_training_day(app, program_id):
    with app.app_context():
        return next(
            day
            for day in TrainingDay.query.join(ProgramWeek).filter(
                ProgramWeek.program_id == program_id
            )
            if not day.is_rest
        ).id


def _start_workout(client, day_id):
    response = client.post("/workouts/start", data={"day_id": str(day_id)})
    assert response.status_code == 302
    return int(response.headers["Location"].rstrip("/").split("/")[-1])


def test_main_pages_render(client):
    for path in [
        "/",
        "/programs",
        "/exercises",
        "/workouts/active",
        "/logbook",
        "/logbook/progress",
        "/statistics",
        "/records",
        "/settings",
        "/manifest.webmanifest",
        "/sw.js",
        "/offline",
    ]:
        assert client.get(path).status_code == 200, path
    dashboard_html = client.get("/").get_data(as_text=True)
    assert 'id="install-button"' not in dashboard_html
    assert client.get("/planner").status_code == 302


def test_program_builder_creates_eight_weeks(client, app):
    program_id = _create_program(client, app, "Eight Week Block")
    with app.app_context():
        program = Program.query.get(program_id)
        assert program.duration_weeks == 8
        assert len(program.weeks) == 8
        assert [week.week_number for week in program.weeks] == list(range(1, 9))
        assert all(not week.days for week in program.weeks)
        assert program.total_planned_sessions == 0
        assert get_setting(User.query.first().id, "active_program_id") == str(program_id)
    assert client.get(f"/planner/program/{program_id}").status_code == 200


def test_program_and_exercise_edits_preserve_workout_history(client, app):
    program_id = _create_program(client, app, "History Block", with_day=True)
    day_id = _first_training_day(app, program_id)
    workout_id = _start_workout(client, day_id)

    with app.app_context():
        workout = WorkoutSession.query.get(workout_id)
        exercise = workout.exercises[0]
        exercise_id = exercise.exercise_id
        set_id = exercise.sets[0].id
        original_name = exercise.exercise_name_snapshot
        original_program = workout.program_name_snapshot

    assert client.post(
        f"/workouts/{workout_id}/sets/{set_id}",
        json={"actual_reps": 8, "actual_weight_kg": 82.5, "is_completed": True},
    ).status_code == 200
    assert client.post(f"/workouts/{workout_id}/complete", json={}).status_code == 200

    rename = {
        "name": "Renamed Press",
        "muscle_group": "Chest",
        "category": "Compound",
        "equipment": "Barbell",
        "description": "",
        "technique_notes": "",
    }
    assert client.post(f"/exercises/{exercise_id}/edit", data=rename).status_code == 302

    with app.app_context():
        payload = program_to_dict(Program.query.get(program_id))
        payload["weeks"][0]["title"] = "Deload week"
        payload["name"] = "Renamed Block"
    assert client.post(f"/programs/{program_id}/edit", data={"payload": json.dumps(payload)}).status_code == 302

    with app.app_context():
        workout = WorkoutSession.query.get(workout_id)
        assert workout.exercises[0].exercise_name_snapshot == original_name
        assert workout.program_name_snapshot == original_program
        assert workout.exercises[0].sets[0].actual_weight_kg == 82.5
        assert workout.is_complete
    assert client.get(f"/logbook/{workout_id}").status_code == 200


def test_statistics_and_prs_use_completed_sets_only(client, app):
    program_id = _create_program(client, app, "Stats Block", with_day=True)
    workout_id = _start_workout(client, _first_training_day(app, program_id))
    with app.app_context():
        set_ids = [row.id for row in WorkoutSession.query.get(workout_id).exercises[0].sets][:2]

    assert client.post(
        f"/workouts/{workout_id}/sets/{set_ids[0]}",
        json={"actual_reps": 5, "actual_weight_kg": 100, "is_completed": True},
    ).status_code == 200
    assert client.post(
        f"/workouts/{workout_id}/sets/{set_ids[1]}",
        json={"actual_reps": 20, "actual_weight_kg": 999, "is_completed": False},
    ).status_code == 200
    assert client.post(f"/workouts/{workout_id}/complete", json={}).status_code == 200

    with app.app_context():
        records = {row.record_type: row.value for row in PersonalRecord.query.all()}
        assert records["heaviest_load"] == 100
        assert records["most_reps_at_weight"] == 5
        assert records["estimated_1rm"] == 116.67
        assert records["session_volume"] == 500

    payload = client.get("/api/stats").get_json()
    assert payload["has_data"] is True
    assert payload["summary"]["logged_sets"] == 1
    assert payload["summary"]["total_volume"] == 500
    assert payload["summary"]["best_5rm"] == 100
    assert client.get("/statistics").status_code == 200
    assert client.get("/records").status_code == 200


def test_progress_log_shows_completed_history(client, app):
    program_id = _create_program(client, app, "Progress Block", with_day=True)
    workout_id = _start_workout(client, _first_training_day(app, program_id))
    with app.app_context():
        set_id = WorkoutSession.query.get(workout_id).exercises[0].sets[0].id

    assert client.post(
        f"/workouts/{workout_id}/sets/{set_id}",
        json={"actual_reps": 10, "actual_weight_kg": 60, "is_completed": True},
    ).status_code == 200
    assert client.post(f"/workouts/{workout_id}/complete", json={}).status_code == 200

    response = client.get("/logbook/progress")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Progress Log" in html
    assert "Training journal" in html
    assert "Barbell Bench Press" in html


def test_offline_sync_is_idempotent_and_detects_conflicts(client, app):
    payload = {
        "client_uuid": "offline-workout-1",
        "program_name": "Offline Block",
        "training_day_name": "Push",
        "started_at": "2026-11-23T10:00:00Z",
        "status": "completed",
        "notes": "first sync",
        "exercises": [
            {
                "name": "Barbell Bench Press",
                "muscle_group": "Chest",
                "is_bodyweight": False,
                "sets": [
                    {
                        "set_number": 1,
                        "actual_reps": 6,
                        "actual_weight_kg": 80,
                        "is_completed": True,
                    }
                ],
            }
        ],
    }

    first = client.post("/api/sync/workouts", json=payload)
    assert first.status_code == 200
    result = first.get_json()
    assert result["status"] == "applied"
    assert result["duplicate"] is False
    workout_id = result["workout_id"]

    second = client.post("/api/sync/workouts", json=payload)
    assert second.status_code == 200
    assert second.get_json()["duplicate"] is True
    assert second.get_json()["workout_id"] == workout_id

    with app.app_context():
        workout = WorkoutSession.query.get(workout_id)
        workout.updated_at = utcnow() + timedelta(seconds=5)
        db.session.commit()

    stale = dict(payload)
    stale["notes"] = "stale offline edit"
    stale["base_updated_at"] = result["updated_at"]
    conflict = client.post("/api/sync/workouts", json=stale)
    assert conflict.status_code == 409
    assert conflict.get_json()["status"] == "conflict"

    with app.app_context():
        assert WorkoutSession.query.filter_by(client_uuid=payload["client_uuid"]).count() == 1


def test_settings_are_saved(client, app):
    response = client.post(
        "/settings",
        data={
            "display_name": "Hero",
            "bodyweight_kg": "82.5",
            "rest_timer_seconds": "120",
            "include_partial_in_stats": "1",
        },
    )
    assert response.status_code == 302
    with app.app_context():
        user = User.query.first()
        assert get_float_setting(user.id, "bodyweight_kg", 75) == 82.5
        assert get_setting(user.id, "rest_timer_seconds") == "120"
        assert get_setting(user.id, "include_partial_in_stats") == "true"


def test_error_page_renders_without_a_bootstrapped_user(app):
    with app.test_request_context("/"):
        from flask import render_template

        html = render_template("errors/500.html", db_error=True)
        assert "database temporarily unavailable" in html.lower()


def test_pwa_manifest_and_icons_are_served(client):
    manifest = client.get("/manifest.webmanifest")
    assert manifest.mimetype == "application/manifest+json"
    assert manifest.get_json()["display"] == "standalone"
    assert client.get("/sw.js").mimetype == "application/javascript"
    assert client.get("/static/icons/icon-192.png").status_code == 200
