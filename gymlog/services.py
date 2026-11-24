"""Business logic: program persistence, workout persistence, PR calculation."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Any

from .extensions import db
from .models import (
    ActualSet,
    PersonalRecord,
    PlannedSet,
    Program,
    ProgramExercise,
    ProgramWeek,
    SyncEvent,
    TrainingDay,
    WorkoutExercise,
    WorkoutSession,
    utcnow,
)
from .utils import (
    epley_1rm,
    format_number,
    get_float_setting,
    iso,
    parse_bool,
    parse_date,
    parse_float,
    parse_int,
    parse_iso,
    set_load_kg,
    set_volume_kg,
)


# ---------------------------------------------------------------------------
# Programs
# ---------------------------------------------------------------------------


def _tidy_text(value: Any, limit: int) -> str:
    """Normalise user-typed labels without changing their meaning."""
    return " ".join(str(value or "").split())[:limit]


def blank_program_payload(duration: int = 8) -> dict[str, Any]:
    """Return an empty week structure the user fills in themselves.

    No days, exercises or targets are pre-filled. Exercise names are typed
    manually in the builder; nothing is selected from the exercise library.
    """
    weeks = []
    for week_number in range(1, duration + 1):
        weeks.append({"week_number": week_number, "title": f"Week {week_number}", "notes": "", "days": []})
    return {
        "name": "",
        "description": "",
        "start_date": date.today().isoformat(),
        "duration_weeks": duration,
        "weeks": weeks,
    }


def week_payload(week: ProgramWeek) -> dict[str, Any]:
    return program_to_dict(week.program)["weeks"][week.week_number - 1]


def program_to_dict(program: Program) -> dict[str, Any]:
    weeks = []
    for week in program.weeks:
        days = []
        for day in week.days:
            exercises = []
            for assignment in day.exercises:
                exercises.append(
                    {
                        "id": assignment.id,
                        "exercise_id": assignment.exercise_id,
                        "exercise_name": assignment.exercise_name_snapshot or (assignment.exercise.name if assignment.exercise else ""),
                        "muscle_group": assignment.muscle_group_snapshot,
                        "is_bodyweight": assignment.is_bodyweight_snapshot,
                        "notes": assignment.notes,
                        "progression_notes": assignment.progression_notes,
                        "sets": [
                            {
                                "id": planned.id,
                                "target_reps": planned.target_reps,
                                "target_weight_kg": planned.target_weight_kg,
                                "target_rpe": planned.target_rpe,
                                "rest_seconds": planned.rest_seconds,
                                "notes": planned.notes,
                            }
                            for planned in assignment.planned_sets
                        ],
                    }
                )
            days.append(
                {
                    "id": day.id,
                    "day_of_week": day.day_of_week,
                    "label": day.label,
                    "is_rest": day.is_rest,
                    "notes": day.notes,
                    "exercises": exercises,
                }
            )
        weeks.append(
            {
                "id": week.id,
                "week_number": week.week_number,
                "title": week.title,
                "notes": week.notes,
                "days": days,
            }
        )
    return {
        "id": program.id,
        "name": program.name,
        "description": program.description,
        "start_date": program.start_date.isoformat(),
        "duration_weeks": program.duration_weeks,
        "weeks": weeks,
    }


def save_program_from_payload(user_id: int, payload: dict[str, Any], program: Program | None = None) -> Program:
    name = str(payload.get("name", "")).strip()
    if not name:
        raise ValueError("Program name is required.")
    start_date = parse_date(payload.get("start_date"))
    if not start_date:
        raise ValueError("A valid start date is required.")
    duration = parse_int(payload.get("duration_weeks"), 8) or 8
    if not 1 <= duration <= 52:
        raise ValueError("Duration must be between 1 and 52 weeks.")

    weeks_payload = payload.get("weeks") or []
    if not isinstance(weeks_payload, list):
        raise ValueError("Invalid week configuration.")
    seen_week_numbers: set[int] = set()

    program = program or Program(user_id=user_id)
    program.name = name[:120]
    program.description = str(payload.get("description", ""))[:5000]
    program.start_date = start_date
    program.duration_weeks = duration
    if program.status not in {"active", "archived"}:
        program.status = "active"
    db.session.add(program)
    # Rebuild the plan atomically. Workout history keeps snapshots + SET NULL FKs.
    for old_week in list(program.weeks):
        db.session.delete(old_week)
    program.weeks = []
    # Flush removals before inserting rebuilt weeks to avoid transient
    # violations of the unique (program_id, week_number) constraint.
    db.session.flush()

    for week_data in weeks_payload:
        week_number = parse_int(week_data.get("week_number"), 0) or 0
        if not 1 <= week_number <= duration or week_number in seen_week_numbers:
            raise ValueError(f"Invalid or duplicated week number: {week_number}")
        seen_week_numbers.add(week_number)
        week = ProgramWeek(
            program=program,
            week_number=week_number,
            title=str(week_data.get("title", ""))[:80],
            notes=str(week_data.get("notes", ""))[:5000],
        )
        db.session.add(week)

        seen_days: set[int] = set()
        for day_data in week_data.get("days", []):
            if not isinstance(day_data, dict):
                continue
            day_of_week = parse_int(day_data.get("day_of_week"), -1)
            if day_of_week is None or not 0 <= day_of_week <= 6:
                raise ValueError("Training days must use a weekday from Monday to Sunday.")
            if day_of_week in seen_days:
                raise ValueError("A week cannot contain the same weekday twice.")
            seen_days.add(day_of_week)
            day = TrainingDay(
                week=week,
                day_of_week=day_of_week,
                label=str(day_data.get("label", ""))[:80],
                is_rest=parse_bool(day_data.get("is_rest", False)),
                notes=str(day_data.get("notes", ""))[:5000],
            )
            db.session.add(day)

            for order_index, ex_data in enumerate(day_data.get("exercises", [])):
                if not isinstance(ex_data, dict) or day.is_rest:
                    continue
                exercise_name = _tidy_text(
                    ex_data.get("exercise_name") or ex_data.get("name"), 120
                )
                if not exercise_name:
                    raise ValueError("Enter a name for every exercise, or remove the empty exercise.")
                assignment = ProgramExercise(
                    training_day=day,
                    exercise_id=None,
                    exercise_name_snapshot=exercise_name,
                    muscle_group_snapshot=_tidy_text(ex_data.get("muscle_group"), 80),
                    is_bodyweight_snapshot=parse_bool(ex_data.get("is_bodyweight", False)),
                    order_index=order_index,
                    notes=str(ex_data.get("notes", ""))[:2000],
                    progression_notes=str(ex_data.get("progression_notes", ""))[:2000],
                )
                db.session.add(assignment)
                sets_data = ex_data.get("sets") or []
                if not isinstance(sets_data, list):
                    sets_data = []
                for set_index, set_data in enumerate(sets_data):
                    if not isinstance(set_data, dict):
                        continue
                    db.session.add(
                        PlannedSet(
                            program_exercise=assignment,
                            set_number=parse_int(set_data.get("set_number"), set_index + 1) or set_index + 1,
                            target_reps=max(1, parse_int(set_data.get("target_reps"), 8) or 8),
                            target_weight_kg=parse_float(set_data.get("target_weight_kg")),
                            target_rpe=parse_float(set_data.get("target_rpe")),
                            rest_seconds=parse_int(set_data.get("rest_seconds")),
                            notes=str(set_data.get("notes", ""))[:1000],
                        )
                    )

    if not seen_week_numbers:
        raise ValueError("A program needs at least one training week.")
    missing = set(range(1, duration + 1)) - seen_week_numbers
    if missing:
        raise ValueError("Every week in the program must be configured.")

    db.session.flush()
    return program


def duplicate_program(program: Program, user_id: int, new_name: str | None = None) -> Program:
    payload = program_to_dict(program)
    payload["name"] = new_name or f"{program.name} (copy)"
    payload["description"] = program.description
    payload["start_date"] = date.today().isoformat()
    copy = save_program_from_payload(user_id, payload)
    copy.status = "active"
    db.session.flush()
    return copy


def copy_week(source: ProgramWeek, target: ProgramWeek) -> None:
    for old_day in list(target.days):
        db.session.delete(old_day)
    target.days = []
    for source_day in source.days:
        day = TrainingDay(
            week=target,
            day_of_week=source_day.day_of_week,
            label=source_day.label,
            is_rest=source_day.is_rest,
            notes=source_day.notes,
        )
        db.session.add(day)
        for source_assignment in source_day.exercises:
            assignment = ProgramExercise(
                training_day=day,
                exercise_id=None,
                exercise_name_snapshot=source_assignment.exercise_name_snapshot,
                muscle_group_snapshot=source_assignment.muscle_group_snapshot,
                is_bodyweight_snapshot=source_assignment.is_bodyweight_snapshot,
                order_index=source_assignment.order_index,
                notes=source_assignment.notes,
                progression_notes=source_assignment.progression_notes,
            )
            db.session.add(assignment)
            for planned in source_assignment.planned_sets:
                db.session.add(
                    PlannedSet(
                        program_exercise=assignment,
                        set_number=planned.set_number,
                        target_reps=planned.target_reps,
                        target_weight_kg=planned.target_weight_kg,
                        target_rpe=planned.target_rpe,
                        rest_seconds=planned.rest_seconds,
                        notes=planned.notes,
                    )
                )
    db.session.flush()


# ---------------------------------------------------------------------------
# Workouts
# ---------------------------------------------------------------------------


def start_workout_from_day(day: TrainingDay, user_id: int) -> WorkoutSession:
    program = day.week.program
    session = WorkoutSession(
        client_uuid=str(uuid.uuid4()),
        user_id=user_id,
        program_id=program.id,
        program_name_snapshot=program.name,
        week_number=day.week.week_number,
        training_day_id=day.id,
        training_day_name_snapshot=day.display_label,
        started_at=utcnow(),
        status="in_progress",
        sync_status="synced",
    )
    db.session.add(session)
    for order_index, assignment in enumerate(day.exercises):
        workout_exercise = WorkoutExercise(
            workout=session,
            exercise_id=None,
            exercise_name_snapshot=assignment.exercise_name_snapshot,
            muscle_group_snapshot=assignment.muscle_group_snapshot,
            is_bodyweight_snapshot=assignment.is_bodyweight_snapshot,
            order_index=order_index,
            notes=assignment.notes,
        )
        db.session.add(workout_exercise)
        for planned in assignment.planned_sets:
            db.session.add(
                ActualSet(
                    workout_exercise=workout_exercise,
                    set_number=planned.set_number,
                    actual_reps=planned.target_reps,
                    actual_weight_kg=planned.target_weight_kg,
                    rpe=planned.target_rpe,
                    is_completed=False,
                    notes=planned.notes,
                )
            )
    db.session.flush()
    return session


def start_freestyle_workout(user_id: int, day_label: str = "Freestyle session") -> WorkoutSession:
    session = WorkoutSession(
        client_uuid=str(uuid.uuid4()),
        user_id=user_id,
        program_name_snapshot="Freestyle",
        training_day_name_snapshot=day_label[:80],
        started_at=utcnow(),
        status="in_progress",
        sync_status="synced",
    )
    db.session.add(session)
    db.session.flush()
    return session


def serialize_workout(session: WorkoutSession) -> dict[str, Any]:
    return {
        "client_uuid": session.client_uuid,
        "program_name": session.program_name_snapshot,
        "week_number": session.week_number,
        "training_day_name": session.training_day_name_snapshot,
        "started_at": iso(session.started_at),
        "completed_at": iso(session.completed_at),
        "status": session.status,
        "notes": session.notes,
        "version": session.version,
        "updated_at": iso(session.updated_at),
        "exercises": [
            {
                "id": we.id,
                "exercise_id": we.exercise_id,
                "name": we.exercise_name_snapshot,
                "muscle_group": we.muscle_group_snapshot,
                "is_bodyweight": we.is_bodyweight_snapshot,
                "notes": we.notes,
                "sets": [
                    {
                        "id": actual.id,
                        "set_number": actual.set_number,
                        "actual_reps": actual.actual_reps,
                        "actual_weight_kg": actual.actual_weight_kg,
                        "rpe": actual.rpe,
                        "rir": actual.rir,
                        "is_completed": actual.is_completed,
                        "notes": actual.notes,
                    }
                    for actual in we.sets
                ],
            }
            for we in session.exercises
        ],
    }


def apply_workout_payload(payload: dict[str, Any], user_id: int) -> tuple[dict[str, Any], WorkoutSession | None]:
    """Apply an idempotent workout upsert. Returns (result, session)."""
    client_uuid = str(payload.get("client_uuid", "")).strip()
    if not client_uuid or len(client_uuid) > 64:
        return {"status": "error", "message": "A valid client_uuid is required."}, None

    existing_event = SyncEvent.query.filter_by(client_uuid=client_uuid).first()
    if existing_event and existing_event.status == "applied" and existing_event.payload == payload:
        session = WorkoutSession.query.get(existing_event.server_workout_id)
        if session:
            return {
                "status": "applied",
                "workout_id": session.id,
                "updated_at": iso(session.updated_at),
                "duplicate": True,
            }, session

    session = WorkoutSession.query.filter_by(client_uuid=client_uuid).first()
    base_updated_at = parse_iso(payload.get("base_updated_at"))
    if session and base_updated_at and session.updated_at and session.updated_at > base_updated_at + timedelta(seconds=1):
        _record_sync_event(client_uuid, payload, "conflict", session.id, "Server record is newer than the offline copy.")
        return {
            "status": "conflict",
            "message": "This workout changed on the server after your offline copy was saved.",
            "server": serialize_workout(session),
        }, session

    if not session:
        session = WorkoutSession(client_uuid=client_uuid, user_id=user_id)
        db.session.add(session)

    session.user_id = user_id
    session.program_name_snapshot = str(payload.get("program_name", "Freestyle session"))[:120]
    session.week_number = parse_int(payload.get("week_number"))
    session.training_day_name_snapshot = str(payload.get("training_day_name", "Training session"))[:80]
    status = str(payload.get("status", "in_progress"))
    session.status = "completed" if status == "completed" else "in_progress"
    session.completed_at = parse_iso(payload.get("completed_at")) if session.is_complete else None
    session.notes = str(payload.get("notes", ""))[:5000]
    session.started_at = parse_iso(payload.get("started_at")) or session.started_at or utcnow()
    session.sync_status = "synced"
    session.version = (session.version or 0) + 1
    session.updated_at = utcnow()

    for old_exercise in list(session.exercises):
        db.session.delete(old_exercise)
    session.exercises = []

    exercises_payload = payload.get("exercises")
    if not isinstance(exercises_payload, list):
        exercises_payload = []
    for order_index, ex_data in enumerate(exercises_payload):
        if not isinstance(ex_data, dict):
            continue
        name = _tidy_text(ex_data.get("name"), 120)
        if not name:
            continue
        workout_exercise = WorkoutExercise(
            workout=session,
            exercise_id=parse_int(ex_data.get("exercise_id")),
            exercise_name_snapshot=name,
            muscle_group_snapshot=str(ex_data.get("muscle_group", ""))[:80],
            is_bodyweight_snapshot=parse_bool(ex_data.get("is_bodyweight", False)),
            order_index=parse_int(ex_data.get("order_index"), order_index) or order_index,
            notes=str(ex_data.get("notes", ""))[:2000],
        )
        db.session.add(workout_exercise)
        sets_payload = ex_data.get("sets")
        if not isinstance(sets_payload, list):
            sets_payload = []
        for set_index, set_data in enumerate(sets_payload):
            if not isinstance(set_data, dict):
                continue
            db.session.add(
                ActualSet(
                    workout_exercise=workout_exercise,
                    set_number=parse_int(set_data.get("set_number"), set_index + 1) or set_index + 1,
                    actual_reps=parse_int(set_data.get("actual_reps")),
                    actual_weight_kg=parse_float(set_data.get("actual_weight_kg")),
                    rpe=parse_float(set_data.get("rpe")),
                    rir=parse_float(set_data.get("rir")),
                    is_completed=parse_bool(set_data.get("is_completed", False)),
                    notes=str(set_data.get("notes", ""))[:1000],
                    completed_at=parse_iso(set_data.get("completed_at")) if parse_bool(set_data.get("is_completed", False)) else None,
                )
            )

    db.session.flush()
    _record_sync_event(client_uuid, payload, "applied", session.id, "")
    if session.is_complete:
        recalculate_prs(user_id)
    db.session.flush()
    return {
        "status": "applied",
        "workout_id": session.id,
        "updated_at": iso(session.updated_at),
        "duplicate": False,
    }, session


def _record_sync_event(client_uuid: str, payload: dict, status: str, workout_id: int | None, error: str) -> None:
    event = SyncEvent.query.filter_by(client_uuid=client_uuid).first()
    if not event:
        event = SyncEvent(client_uuid=client_uuid, entity_type="workout_session")
        db.session.add(event)
    event.payload = payload
    event.action = "upsert"
    event.status = status
    event.server_workout_id = workout_id
    event.error = error
    event.received_at = utcnow()


# ---------------------------------------------------------------------------
# Personal records
# ---------------------------------------------------------------------------


def recalculate_prs(user_id: int) -> None:
    """Rebuild PRs from completed workouts only, using consistent comparisons."""
    for record in PersonalRecord.query.filter_by(user_id=user_id).all():
        db.session.delete(record)
    db.session.flush()

    bodyweight = get_float_setting(user_id, "bodyweight_kg", 75.0)
    bests: dict[tuple[str, str, str], dict[str, Any]] = {}
    weekly_volume: dict[str, float] = {}

    sessions = (
        WorkoutSession.query.filter_by(user_id=user_id, status="completed")
        .order_by(WorkoutSession.completed_at.asc(), WorkoutSession.id.asc())
        .all()
    )

    def consider(
        record_type: str,
        exercise_key: str,
        exercise_name: str,
        comparison_key: str,
        value: float,
        session: WorkoutSession,
        set_row: ActualSet | None = None,
        reps: int | None = None,
        weight: float | None = None,
        details: str = "",
    ) -> None:
        key = (exercise_key, record_type, comparison_key)
        current = bests.get(key)
        if current is None or value > current["value"] + 1e-9:
            bests[key] = {
                "exercise_key": exercise_key,
                "exercise_name": exercise_name,
                "record_type": record_type,
                "comparison_key": comparison_key,
                "value": round(float(value), 2),
                "reps": reps,
                "weight_kg": weight,
                "session_id": session.id,
                "set_id": set_row.id if set_row else None,
                "achieved_at": session.completed_at or session.started_at,
                "details": details,
            }

    for session in sessions:
        session_volume = 0.0
        for we in session.exercises:
            for actual in we.sets:
                if not actual.is_completed:
                    continue
                load = set_load_kg(actual.actual_weight_kg, we.is_bodyweight_snapshot, bodyweight)
                volume = set_volume_kg(load, actual.actual_reps)
                session_volume += volume
                exercise_key = we.exercise_key
                exercise_name = we.exercise_name_snapshot
                reps = actual.actual_reps
                if load > 0:
                    consider(
                        "heaviest_load", exercise_key, exercise_name, "all", load,
                        session, actual, reps, load,
                        f"{reps or 0} reps at {format_number(load)} kg total load",
                    )
                if reps and reps > 0 and load > 0:
                    comparison = f"{load:g}"
                    consider(
                        "most_reps_at_weight", exercise_key, exercise_name, comparison, reps,
                        session, actual, reps, load,
                        f"{reps} reps at {format_number(load)} kg total load",
                    )
                    estimate = epley_1rm(load, reps)
                    if estimate:
                        consider(
                            "estimated_1rm", exercise_key, exercise_name, "epley", estimate,
                            session, actual, reps, load,
                            f"Epley estimate from {reps} reps at {format_number(load)} kg",
                        )

        if session_volume > 0:
            consider(
                "session_volume", "ALL", "All exercises", "session", session_volume,
                session, None, None, None,
                "Total volume in a single completed session",
            )
            monday = (session.completed_at or session.started_at).date() - timedelta(
                days=(session.completed_at or session.started_at).weekday()
            )
            weekly_volume[monday.isoformat()] = weekly_volume.get(monday.isoformat(), 0.0) + session_volume

    for week_key, volume in weekly_volume.items():
        # Highest weekly volume is awarded once against the week that achieved it.
        # Find a representative session in that week for the date/record link.
        representative = next(
            (
                s for s in sessions
                if (s.completed_at or s.started_at)
                and ((s.completed_at or s.started_at).date() - timedelta(days=(s.completed_at or s.started_at).weekday())).isoformat() == week_key
            ),
            None,
        )
        if representative and volume > 0:
            consider(
                "weekly_volume", "ALL", "All exercises", week_key, volume,
                representative, None, None, None,
                f"Total volume in week beginning {week_key}",
            )

    for item in bests.values():
        db.session.add(
            PersonalRecord(
                user_id=user_id,
                record_type=item["record_type"],
                exercise_key=item["exercise_key"],
                exercise_name_snapshot=item["exercise_name"],
                comparison_key=item["comparison_key"],
                value=item["value"],
                reps=item["reps"],
                weight_kg=item["weight_kg"],
                achieved_at=item["achieved_at"],
                workout_session_id=item["session_id"],
                actual_set_id=item["set_id"],
                details=item["details"],
            )
        )
    db.session.flush()
