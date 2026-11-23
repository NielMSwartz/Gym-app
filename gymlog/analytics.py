"""Read-only analytics derived from actual workout records."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta
from typing import Iterable

from .models import ActualSet, PersonalRecord, Program, WorkoutExercise, WorkoutSession
from .utils import epley_1rm, get_float_setting, set_load_kg, set_volume_kg


def filtered_sessions(
    user_id: int,
    *,
    program_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    include_partial: bool = False,
) -> list[WorkoutSession]:
    query = WorkoutSession.query.filter(WorkoutSession.user_id == user_id)
    if not include_partial:
        query = query.filter(WorkoutSession.status == "completed")
    if program_id:
        query = query.filter(WorkoutSession.program_id == program_id)
    if start_date:
        query = query.filter(WorkoutSession.started_at >= datetime.combine(start_date, time.min))
    if end_date:
        query = query.filter(WorkoutSession.started_at < datetime.combine(end_date + timedelta(days=1), time.min))
    return query.order_by(WorkoutSession.started_at.asc()).all()


def completed_set_rows(sessions: Iterable[WorkoutSession], bodyweight_kg: float) -> list[dict]:
    rows = []
    for session in sessions:
        for we in session.exercises:
            for actual in we.sets:
                if not actual.is_completed:
                    continue
                load = set_load_kg(actual.actual_weight_kg, we.is_bodyweight_snapshot, bodyweight_kg)
                rows.append(
                    {
                        "session": session,
                        "exercise": we,
                        "set": actual,
                        "load": load,
                        "volume": set_volume_kg(load, actual.actual_reps),
                        "e1rm": epley_1rm(load, actual.actual_reps),
                        "date": (session.completed_at or session.started_at).date(),
                    }
                )
    return rows


def strength_series(rows: list[dict], exercise_key: str) -> list[dict]:
    points = []
    for row in rows:
        key = row["exercise"].exercise_key
        if key != exercise_key:
            continue
        points.append(
            {
                "date": row["date"].isoformat(),
                "weight": row["load"],
                "reps": row["set"].actual_reps,
                "e1rm": row["e1rm"],
                "session_id": row["session"].id,
            }
        )
    return points


def volume_by_workout(rows: list[dict]) -> list[dict]:
    totals: dict[int, dict] = {}
    for row in rows:
        session = row["session"]
        entry = totals.setdefault(
            session.id,
            {
                "date": (session.completed_at or session.started_at).date().isoformat(),
                "label": session.training_day_name_snapshot[:18],
                "volume": 0.0,
                "reps": 0,
            },
        )
        entry["volume"] += row["volume"]
        entry["reps"] += row["set"].actual_reps or 0
    result = list(totals.values())
    for item in result:
        item["volume"] = round(item["volume"], 1)
    return result


def volume_by_week(rows: list[dict]) -> list[dict]:
    totals: dict[str, float] = defaultdict(float)
    for row in rows:
        monday = row["date"] - timedelta(days=row["date"].weekday())
        totals[monday.isoformat()] += row["volume"]
    return [{"week": key, "volume": round(value, 1)} for key, value in sorted(totals.items())]


def volume_by_muscle(rows: list[dict]) -> list[dict]:
    totals: dict[str, float] = defaultdict(float)
    for row in rows:
        muscle = row["exercise"].muscle_group_snapshot or "Other"
        totals[muscle] += row["volume"]
    return [{"label": key, "volume": round(value, 1)} for key, value in sorted(totals.items(), key=lambda x: -x[1])]


def volume_by_exercise(rows: list[dict]) -> list[dict]:
    totals: dict[str, dict] = {}
    for row in rows:
        we = row["exercise"]
        key = we.exercise_key
        entry = totals.setdefault(key, {"label": we.exercise_name_snapshot, "volume": 0.0})
        entry["volume"] += row["volume"]
    return [{"label": v["label"], "volume": round(v["volume"], 1)} for v in sorted(totals.values(), key=lambda x: -x["volume"])]


def consistency_data(user_id: int, program: Program | None = None, weeks: int = 8) -> dict:
    """Completed vs. planned sessions for recent weeks of the selected program."""
    today = date.today()
    this_monday = today - timedelta(days=today.weekday())
    labels = []
    completed = []
    planned = []

    if program:
        week_map: dict[str, int] = defaultdict(int)
        for week in program.weeks:
            monday = program.start_date + timedelta(days=(week.week_number - 1) * 7)
            week_map[monday.isoformat()] = sum(1 for day in week.days if not day.is_rest)
    else:
        week_map = defaultdict(int)

    sessions = WorkoutSession.query.filter(
        WorkoutSession.user_id == user_id,
        WorkoutSession.status == "completed",
        WorkoutSession.started_at >= datetime.combine(this_monday - timedelta(weeks=weeks - 1), time.min),
    ).all()
    completed_map: dict[str, int] = defaultdict(int)
    for session in sessions:
        day = session.started_at.date()
        monday = day - timedelta(days=day.weekday())
        completed_map[monday.isoformat()] += 1

    for index in range(weeks - 1, -1, -1):
        monday = (this_monday - timedelta(weeks=index)).isoformat()
        labels.append(monday)
        completed.append(completed_map.get(monday, 0))
        planned.append(week_map.get(monday, 0))

    program_completion = 0
    if program and program.total_planned_sessions:
        done = WorkoutSession.query.filter(
            WorkoutSession.user_id == user_id,
            WorkoutSession.program_id == program.id,
            WorkoutSession.status == "completed",
        ).count()
        program_completion = min(100, round(done / program.total_planned_sessions * 100))

    return {
        "labels": labels,
        "completed": completed,
        "planned": planned,
        "program_completion": program_completion,
    }


def best_weight_for_reps(rows: list[dict], reps: int) -> float | None:
    values = [row["load"] for row in rows if row["set"].actual_reps == reps and row["load"] > 0]
    return max(values) if values else None


def latest_personal_records(user_id: int, limit: int = 5) -> list[PersonalRecord]:
    return (
        PersonalRecord.query.filter_by(user_id=user_id)
        .order_by(PersonalRecord.achieved_at.desc(), PersonalRecord.id.desc())
        .limit(limit)
        .all()
    )
