"""Permanent workout logbook and exercise history."""

from __future__ import annotations

from datetime import datetime, time, timedelta

from flask import Blueprint, abort, render_template, request

from ..analytics import filtered_sessions, progress_logbook_data
from ..models import WorkoutExercise, WorkoutSession
from ..utils import get_bool_setting, get_float_setting, parse_date
from .helpers import current_user, owned

bp = Blueprint("logbook", __name__)


@bp.route("/logbook")
def index():
    user = current_user()
    include_partial = request.args.get("include_partial")
    if include_partial is None:
        include_partial = get_bool_setting(user.id, "include_partial_in_stats", False)
    else:
        include_partial = include_partial == "1"

    query = WorkoutSession.query.filter_by(user_id=user.id)
    if not include_partial:
        query = query.filter_by(status="completed")
    program_id = request.args.get("program_id", type=int)
    if program_id:
        query = query.filter_by(program_id=program_id)
    start = parse_date(request.args.get("from"))
    end = parse_date(request.args.get("to"))
    if start:
        query = query.filter(WorkoutSession.started_at >= datetime.combine(start, time.min))
    if end:
        query = query.filter(WorkoutSession.started_at < datetime.combine(end + timedelta(days=1), time.min))

    workouts = query.order_by(WorkoutSession.started_at.desc()).all()
    return render_template(
        "logbook/index.html",
        workouts=workouts,
        include_partial=include_partial,
        program_id=program_id,
        date_from=request.args.get("from", ""),
        date_to=request.args.get("to", ""),
    )


@bp.route("/logbook/progress")
def progress():
    """A journal-style view of completed training with per-exercise progress."""
    user = current_user()
    bodyweight = get_float_setting(user.id, "bodyweight_kg", 75.0)
    sessions = filtered_sessions(user.id, include_partial=False)
    summary, journal, exercise_progress = progress_logbook_data(sessions, bodyweight)
    return render_template(
        "logbook/progress.html",
        summary=summary,
        journal=journal,
        exercise_progress=exercise_progress,
    )


@bp.route("/logbook/<int:workout_id>")
def detail(workout_id: int):
    workout = owned(WorkoutSession, workout_id, current_user().id)
    completed_sets = sum(
        1 for we in workout.exercises for actual in we.sets if actual.is_completed
    )
    return render_template("logbook/detail.html", workout=workout, completed_sets=completed_sets)


@bp.route("/logbook/exercise/<path:exercise_key>")
def exercise_history(exercise_key: str):
    user = current_user()
    rows = (
        WorkoutExercise.query.join(WorkoutSession)
        .filter(
            WorkoutSession.user_id == user.id,
            WorkoutSession.status == "completed",
        )
        .order_by(WorkoutSession.started_at.asc())
        .all()
    )
    history = []
    for we in rows:
        if we.exercise_key != exercise_key:
            continue
        completed_sets = [s for s in we.sets if s.is_completed]
        if not completed_sets:
            continue
        best = max(completed_sets, key=lambda s: ((s.actual_weight_kg or 0), s.actual_reps or 0))
        history.append(
            {
                "session": we.workout,
                "sets": completed_sets,
                "best": best,
                "volume": sum((s.actual_reps or 0) * (s.actual_weight_kg or 0) for s in completed_sets),
            }
        )
    history.reverse()
    if not history:
        abort(404)
    summary = {
        "best_weight": max((entry["best"].actual_weight_kg or 0 for entry in history), default=0),
        "most_reps": max((entry["best"].actual_reps or 0 for entry in history), default=0),
    }
    return render_template(
        "logbook/exercise_history.html",
        exercise_name=history[0]["sets"][0].workout_exercise.exercise_name_snapshot,
        exercise_key=exercise_key,
        history=history,
        summary=summary,
    )
