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


def _week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def current_streak_weeks(sessions: Iterable[WorkoutSession]) -> int:
    """Count consecutive weeks with at least one completed session."""
    active_weeks = {
        _week_start((session.completed_at or session.started_at).date())
        for session in sessions
    }
    if not active_weeks:
        return 0

    cursor = _week_start(date.today())
    # A streak from last week is still valid until this week is over.
    if cursor not in active_weeks:
        cursor -= timedelta(weeks=1)

    streak = 0
    while cursor in active_weeks:
        streak += 1
        cursor -= timedelta(weeks=1)
    return streak


def progress_logbook_data(
    sessions: Iterable[WorkoutSession], bodyweight_kg: float
) -> tuple[dict, list[dict], list[dict]]:
    """Build a chronological training journal and per-exercise progress table."""
    sessions = list(sessions)
    rows = completed_set_rows(sessions, bodyweight_kg)
    rows_by_session: dict[int, list[dict]] = defaultdict(list)
    rows_by_exercise: dict[str, list[dict]] = defaultdict(list)

    for row in rows:
        rows_by_session[row["session"].id].append(row)
        rows_by_exercise[row["exercise"].exercise_key].append(row)

    journal: list[dict] = []
    for session in sorted(sessions, key=lambda s: s.started_at, reverse=True):
        session_rows = rows_by_session.get(session.id, [])
        if not session_rows:
            continue

        by_exercise: dict[str, list[dict]] = defaultdict(list)
        for row in session_rows:
            by_exercise[row["exercise"].exercise_key].append(row)

        exercises = []
        for key, ex_rows in by_exercise.items():
            best = max(
                ex_rows,
                key=lambda r: (r["e1rm"] or 0, r["load"], r["set"].actual_reps or 0),
            )
            exercises.append(
                {
                    "key": key,
                    "name": ex_rows[0]["exercise"].exercise_name_snapshot,
                    "sets": len(ex_rows),
                    "best_load": round(max(r["load"] for r in ex_rows), 1),
                    "best_reps": max(r["set"].actual_reps or 0 for r in ex_rows),
                    "best_e1rm": round(best["e1rm"] or 0, 1),
                }
            )
        exercises.sort(key=lambda item: item["best_e1rm"], reverse=True)

        entry_date = (session.completed_at or session.started_at).date()
        journal.append(
            {
                "session": session,
                "date": entry_date,
                "month": entry_date.strftime("%B %Y"),
                "volume": round(sum(r["volume"] for r in session_rows), 1),
                "sets": len(session_rows),
                "exercises": exercises,
                "notes": session.notes or "",
            }
        )

    exercise_progress: list[dict] = []
    for key, ex_rows in rows_by_exercise.items():
        ex_rows.sort(key=lambda r: r["date"])
        first, last = ex_rows[0], ex_rows[-1]
        best = max(
            ex_rows,
            key=lambda r: (r["e1rm"] or 0, r["load"], r["set"].actual_reps or 0),
        )
        first_e1rm = round(first["e1rm"] or 0, 1)
        last_e1rm = round(last["e1rm"] or 0, 1)
        delta = round(last_e1rm - first_e1rm, 1)
        trend = "up" if delta > 0.05 else "down" if delta < -0.05 else "flat"

        exercise_progress.append(
            {
                "key": key,
                "name": first["exercise"].exercise_name_snapshot,
                "sessions": len({r["session"].id for r in ex_rows}),
                "sets": len(ex_rows),
                "first_date": first["date"],
                "last_date": last["date"],
                "first_load": round(first["load"], 1),
                "last_load": round(last["load"], 1),
                "best_load": round(max(r["load"] for r in ex_rows), 1),
                "first_e1rm": first_e1rm,
                "last_e1rm": last_e1rm,
                "delta": delta,
                "trend": trend,
            }
        )
    exercise_progress.sort(key=lambda item: (item["last_date"], item["sessions"]), reverse=True)

    summary = {
        "sessions": len(journal),
        "sets": len(rows),
        "volume": round(sum(r["volume"] for r in rows), 1),
        "streak": current_streak_weeks(sessions),
        "exercises": len(exercise_progress),
    }
    return summary, journal, exercise_progress
