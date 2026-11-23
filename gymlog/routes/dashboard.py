"""Training headquarters dashboard."""

from __future__ import annotations

from datetime import date

from flask import Blueprint, render_template

from ..analytics import (
    consistency_data,
    latest_personal_records,
    volume_by_week,
    completed_set_rows,
    filtered_sessions,
)
from ..models import WorkoutSession
from ..utils import current_week_number, get_float_setting, percent
from .helpers import active_program, current_user

bp = Blueprint("dashboard", __name__)


@bp.route("/")
def index():
    user = current_user()
    program = active_program()
    today = date.today()
    week_number = current_week_number(program, today) if program else 0
    week = next((w for w in program.weeks if w.week_number == week_number), None) if program else None

    todays_day = None
    if week:
        todays_day = next((d for d in week.days if d.day_of_week == today.weekday() and not d.is_rest), None)
        if not todays_day:
            todays_day = next((d for d in week.days if not d.is_rest), None)

    in_progress = (
        WorkoutSession.query.filter_by(user_id=user.id, status="in_progress")
        .order_by(WorkoutSession.started_at.desc())
        .first()
    )
    recent_workouts = (
        WorkoutSession.query.filter_by(user_id=user.id)
        .order_by(WorkoutSession.started_at.desc())
        .limit(6)
        .all()
    )
    records = latest_personal_records(user.id, 5)

    bodyweight = get_float_setting(user.id, "bodyweight_kg", 75.0)
    rows = completed_set_rows(filtered_sessions(user.id, include_partial=False), bodyweight)
    weekly = volume_by_week(rows)[-6:]
    consistency = consistency_data(user.id, program, weeks=8)
    completed_sessions = len([s for s in recent_workouts if s.is_complete])

    progress = percent(week_number - 1, program.duration_weeks) if program else 0
    if program and program.total_planned_sessions:
        done = WorkoutSession.query.filter_by(user_id=user.id, program_id=program.id, status="completed").count()
        progress = percent(done, program.total_planned_sessions)

    return render_template(
        "dashboard.html",
        program=program,
        week_number=week_number,
        week=week,
        todays_day=todays_day,
        in_progress=in_progress,
        recent_workouts=recent_workouts,
        records=records,
        weekly_volume=weekly,
        consistency=consistency,
        progress=progress,
        completed_sessions=completed_sessions,
    )
