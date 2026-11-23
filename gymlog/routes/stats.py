"""Statistics and progression charts."""

from __future__ import annotations

from flask import Blueprint, jsonify, render_template, request

from ..analytics import (
    best_weight_for_reps,
    completed_set_rows,
    consistency_data,
    filtered_sessions,
    strength_series,
    volume_by_exercise,
    volume_by_muscle,
    volume_by_week,
    volume_by_workout,
)
from ..models import Exercise, Program, WorkoutExercise, WorkoutSession
from ..utils import get_bool_setting, get_float_setting, parse_date
from .helpers import active_program, current_user

bp = Blueprint("stats", __name__)


def _filters(user_id: int) -> dict:
    include_partial = request.args.get("include_partial")
    if include_partial is None:
        include_partial = get_bool_setting(user_id, "include_partial_in_stats", False)
    else:
        include_partial = include_partial == "1"
    return {
        "exercise_key": request.args.get("exercise", "").strip(),
        "program_id": request.args.get("program_id", type=int),
        "date_from": request.args.get("from", ""),
        "date_to": request.args.get("to", ""),
        "include_partial": include_partial,
    }


def _exercise_options(user_id: int) -> list[dict]:
    rows = (
        WorkoutExercise.query.join(WorkoutSession)
        .filter(WorkoutSession.user_id == user_id)
        .order_by(WorkoutExercise.exercise_name_snapshot.asc())
        .all()
    )
    seen = {}
    for we in rows:
        seen.setdefault(we.exercise_key, we.exercise_name_snapshot)
    return [{"key": key, "name": name} for key, name in sorted(seen.items(), key=lambda item: item[1])]


def build_stats_payload(user_id: int, filters: dict) -> dict:
    bodyweight = get_float_setting(user_id, "bodyweight_kg", 75.0)
    sessions = filtered_sessions(
        user_id,
        program_id=filters.get("program_id"),
        start_date=parse_date(filters.get("date_from")),
        end_date=parse_date(filters.get("date_to")),
        include_partial=filters.get("include_partial", False),
    )
    rows = completed_set_rows(sessions, bodyweight)
    exercise_key = filters.get("exercise_key")

    if exercise_key:
        scoped_rows = [row for row in rows if row["exercise"].exercise_key == exercise_key]
    else:
        scoped_rows = rows

    series = strength_series(scoped_rows, exercise_key) if exercise_key else []
    program = None
    if filters.get("program_id"):
        program = Program.query.get(filters["program_id"])

    consistency = consistency_data(user_id, program, weeks=8)
    best_8 = best_weight_for_reps(rows, 8)
    best_5 = best_weight_for_reps(rows, 5)
    best_3 = best_weight_for_reps(rows, 3)

    return {
        "filters": filters,
        "strength": series,
        "e1rm": [{"date": p["date"], "value": p["e1rm"]} for p in series if p["e1rm"] is not None],
        "volume_by_workout": volume_by_workout(scoped_rows),
        "volume_by_week": volume_by_week(scoped_rows),
        "volume_by_muscle": volume_by_muscle(scoped_rows),
        "volume_by_exercise": volume_by_exercise(scoped_rows),
        "consistency": consistency,
        "summary": {
            "completed_sessions": len([s for s in sessions if s.is_complete]),
            "logged_sets": len(scoped_rows),
            "total_volume": round(sum(r["volume"] for r in scoped_rows), 1),
            "best_8rm": best_8,
            "best_5rm": best_5,
            "best_3rm": best_3,
        },
        "has_data": bool(scoped_rows),
    }


@bp.route("/statistics")
def index():
    user = current_user()
    filters = _filters(user.id)
    programs = Program.query.filter_by(user_id=user.id).order_by(Program.created_at.desc()).all()
    if not filters["program_id"]:
        active = active_program()
        filters["program_id"] = active.id if active else None
    payload = build_stats_payload(user.id, filters)
    return render_template(
        "statistics/index.html",
        payload=payload,
        programs=programs,
        exercises=_exercise_options(user.id),
        filters=filters,
    )


@bp.get("/api/stats")
def api_stats():
    user = current_user()
    return jsonify(build_stats_payload(user.id, _filters(user.id)))
