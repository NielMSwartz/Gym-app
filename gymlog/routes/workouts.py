"""Workout logging, resuming and completion."""

from __future__ import annotations

from datetime import date, timedelta

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for

from ..extensions import db
from ..models import ActualSet, Program, TrainingDay, WorkoutExercise, WorkoutSession
from ..services import recalculate_prs, serialize_workout, start_freestyle_workout, start_workout_from_day
from ..utils import current_week_number, get_float_setting, parse_bool, parse_float, parse_int, utcnow
from .helpers import active_program, current_user, owned

bp = Blueprint("workouts", __name__)


@bp.route("/workouts/active")
def active_workouts():
    user = current_user()
    in_progress = (
        WorkoutSession.query.filter_by(user_id=user.id, status="in_progress")
        .order_by(WorkoutSession.started_at.desc())
        .all()
    )
    program = active_program()
    options = []
    if program:
        week_no = current_week_number(program)
        week = next((w for w in program.weeks if w.week_number == week_no), None)
        if week:
            for day in week.days:
                if not day.is_rest:
                    options.append(day)
    return render_template("workouts/active.html", in_progress=in_progress, program=program, options=options, week_no=week_no if program else 0)


@bp.post("/workouts/start")
def start_workout():
    user = current_user()
    day_id = parse_int(request.form.get("day_id"))
    if day_id:
        day = TrainingDay.query.get_or_404(day_id)
        if day.week.program.user_id != user.id:
            abort(404)
        existing = (
            WorkoutSession.query.filter_by(user_id=user.id, status="in_progress", training_day_id=day.id)
            .order_by(WorkoutSession.started_at.desc())
            .first()
        )
        if existing:
            flash("Resuming your unfinished session.", "info")
            return redirect(url_for("workouts.workout_detail", workout_id=existing.id))
        session = start_workout_from_day(day, user.id)
    else:
        label = request.form.get("label", "Freestyle session").strip() or "Freestyle session"
        session = start_freestyle_workout(user.id, label)
    db.session.commit()
    flash("Workout started. Log each set as you go.", "success")
    return redirect(url_for("workouts.workout_detail", workout_id=session.id))


@bp.route("/workouts/<int:workout_id>")
def workout_detail(workout_id: int):
    session = owned(WorkoutSession, workout_id, current_user().id)
    previous = _previous_sessions(session)
    comparisons = {}
    for we in session.exercises:
        prior = previous.get(we.exercise_key)
        if prior:
            completed = [s for s in prior.sets if s.is_completed]
            comparisons[we.id] = {
                "session_id": prior.workout_session_id,
                "session_date": prior.workout.started_at.date().isoformat(),
                "best_set": max(
                    completed,
                    key=lambda s: ((s.actual_weight_kg or 0), s.actual_reps or 0),
                    default=None,
                ),
                "set_count": len(completed),
            }
    return render_template(
        "workouts/workout.html",
        workout=session,
        comparisons=comparisons,
        bodyweight=get_float_setting(current_user().id, "bodyweight_kg", 75.0),
    )


@bp.route("/workouts/<int:workout_id>/payload")
def workout_payload(workout_id: int):
    session = owned(WorkoutSession, workout_id, current_user().id)
    payload = serialize_workout(session)
    payload["base_updated_at"] = payload["updated_at"]
    return jsonify(payload)


@bp.post("/workouts/<int:workout_id>/sets/<int:set_id>")
def update_set(workout_id: int, set_id: int):
    session = owned(WorkoutSession, workout_id, current_user().id)
    actual = ActualSet.query.get_or_404(set_id)
    if actual.workout_exercise.workout_session_id != session.id:
        abort(404)
    data = request.get_json(silent=True) or request.form
    if "actual_reps" in data:
        actual.actual_reps = max(0, parse_int(data.get("actual_reps"), 0) or 0)
    if "actual_weight_kg" in data:
        actual.actual_weight_kg = max(0.0, parse_float(data.get("actual_weight_kg"), 0.0) or 0.0)
    if "rpe" in data:
        value = parse_float(data.get("rpe"))
        actual.rpe = min(10.0, max(1.0, value)) if value is not None else None
    if "rir" in data:
        value = parse_float(data.get("rir"))
        actual.rir = max(0.0, value) if value is not None else None
    if "notes" in data:
        actual.notes = str(data.get("notes", ""))[:1000]
    if "is_completed" in data:
        actual.is_completed = parse_bool(data.get("is_completed"))
        actual.completed_at = utcnow() if actual.is_completed else None
    session.updated_at = utcnow()
    session.version += 1
    db.session.commit()
    return jsonify({"ok": True, "set": _serialize_set(actual), "updated_at": session.updated_at.isoformat() + "Z"})


@bp.post("/workouts/<int:workout_id>/exercises")
def add_exercise(workout_id: int):
    session = owned(WorkoutSession, workout_id, current_user().id)
    name = " ".join(str(request.values.get("name", "")).split())[:120]
    if not name:
        flash("Enter an exercise name to add it to this workout.", "error")
        return redirect(url_for("workouts.workout_detail", workout_id=session.id))
    last_index = max((we.order_index for we in session.exercises), default=-1)
    we = WorkoutExercise(
        workout=session,
        exercise_id=None,
        exercise_name_snapshot=name,
        muscle_group_snapshot=" ".join(str(request.values.get("muscle_group", "")).split())[:80],
        is_bodyweight_snapshot=parse_bool(request.values.get("is_bodyweight", False)),
        order_index=last_index + 1,
    )
    db.session.add(we)
    for number in range(1, 4):
        db.session.add(ActualSet(workout_exercise=we, set_number=number, actual_reps=8, is_completed=False))
    session.updated_at = utcnow()
    session.version += 1
    db.session.commit()
    flash(f"{name} added to this workout.", "success")
    return redirect(url_for("workouts.workout_detail", workout_id=session.id))


@bp.post("/workouts/<int:workout_id>/exercises/<int:we_id>/delete")
def remove_exercise(workout_id: int, we_id: int):
    session = owned(WorkoutSession, workout_id, current_user().id)
    we = WorkoutExercise.query.get_or_404(we_id)
    if we.workout_session_id != session.id:
        abort(404)
    db.session.delete(we)
    session.updated_at = utcnow()
    session.version += 1
    db.session.commit()
    return jsonify({"ok": True})


@bp.post("/workouts/<int:workout_id>/sets")
def add_set(workout_id: int):
    session = owned(WorkoutSession, workout_id, current_user().id)
    exercise_id = parse_int(request.values.get("workout_exercise_id"))
    we = WorkoutExercise.query.get_or_404(exercise_id)
    if we.workout_session_id != session.id:
        abort(404)
    last_number = max((s.set_number for s in we.sets), default=0)
    previous = we.sets[-1] if we.sets else None
    new_set = ActualSet(
        workout_exercise=we,
        set_number=last_number + 1,
        actual_reps=previous.actual_reps if previous else 8,
        actual_weight_kg=previous.actual_weight_kg if previous else None,
        rpe=previous.rpe if previous else None,
        is_completed=False,
    )
    db.session.add(new_set)
    session.updated_at = utcnow()
    session.version += 1
    db.session.commit()
    return jsonify({"ok": True, "set": _serialize_set(new_set)})


@bp.post("/workouts/<int:workout_id>/sets/<int:set_id>/delete")
def delete_set(workout_id: int, set_id: int):
    session = owned(WorkoutSession, workout_id, current_user().id)
    actual = ActualSet.query.get_or_404(set_id)
    if actual.workout_exercise.workout_session_id != session.id:
        abort(404)
    db.session.delete(actual)
    session.updated_at = utcnow()
    session.version += 1
    db.session.commit()
    return jsonify({"ok": True})


@bp.post("/workouts/<int:workout_id>/copy-previous")
def copy_previous(workout_id: int):
    session = owned(WorkoutSession, workout_id, current_user().id)
    previous = _previous_sessions(session)
    copied = 0
    for we in session.exercises:
        prior = previous.get(we.exercise_key)
        if not prior:
            continue
        prior_sets = [s for s in prior.sets if s.is_completed]
        for index, target in enumerate(sorted(we.sets, key=lambda s: s.set_number)):
            if index >= len(prior_sets):
                continue
            source = prior_sets[index]
            target.actual_reps = source.actual_reps
            target.actual_weight_kg = source.actual_weight_kg
            target.rpe = source.rpe
            target.rir = source.rir
            copied += 1
    session.updated_at = utcnow()
    session.version += 1
    db.session.commit()
    return jsonify({"ok": True, "copied": copied})


@bp.post("/workouts/<int:workout_id>/notes")
def save_notes(workout_id: int):
    session = owned(WorkoutSession, workout_id, current_user().id)
    data = request.get_json(silent=True) or request.form
    session.notes = str(data.get("notes", ""))[:5000]
    session.updated_at = utcnow()
    session.version += 1
    db.session.commit()
    return jsonify({"ok": True})


@bp.post("/workouts/<int:workout_id>/complete")
def complete_workout(workout_id: int):
    session = owned(WorkoutSession, workout_id, current_user().id)
    data = request.get_json(silent=True) or {}
    session.notes = str(data.get("notes", session.notes))[:5000]
    session.status = "completed"
    session.completed_at = utcnow()
    session.updated_at = utcnow()
    session.version += 1
    for we in session.exercises:
        for actual in we.sets:
            if parse_bool(data.get(f"complete_set_{actual.id}"), actual.is_completed):
                actual.is_completed = True
                actual.completed_at = actual.completed_at or utcnow()
    db.session.flush()
    recalculate_prs(current_user().id)
    db.session.commit()
    if request.accept_mimetypes.best == "application/json" or request.is_json:
        return jsonify({"ok": True, "redirect": url_for("logbook.detail", workout_id=session.id)})
    flash("Workout complete. Your records have been updated.", "success")
    return redirect(url_for("logbook.detail", workout_id=session.id))


@bp.post("/workouts/<int:workout_id>/delete")
def delete_workout(workout_id: int):
    session = owned(WorkoutSession, workout_id, current_user().id)
    if session.is_complete:
        flash("Completed workouts cannot be deleted from here. They are permanent history.", "error")
        return redirect(url_for("logbook.detail", workout_id=session.id))
    db.session.delete(session)
    db.session.commit()
    flash("Unfinished workout discarded.", "success")
    return redirect(url_for("workouts.active_workouts"))


def _previous_sessions(session: WorkoutSession) -> dict[str, WorkoutExercise]:
    """Most recent completed workout exercise per exercise before this session."""
    result: dict[str, WorkoutExercise] = {}
    rows = (
        WorkoutExercise.query.join(WorkoutSession)
        .filter(
            WorkoutSession.user_id == session.user_id,
            WorkoutSession.status == "completed",
            WorkoutSession.started_at < session.started_at,
        )
        .order_by(WorkoutSession.started_at.desc(), WorkoutExercise.id.desc())
        .all()
    )
    for we in rows:
        if any(s.is_completed for s in we.sets):
            result.setdefault(we.exercise_key, we)
    return result


def _serialize_set(actual: ActualSet) -> dict:
    return {
        "id": actual.id,
        "set_number": actual.set_number,
        "actual_reps": actual.actual_reps,
        "actual_weight_kg": actual.actual_weight_kg,
        "rpe": actual.rpe,
        "rir": actual.rir,
        "is_completed": actual.is_completed,
        "notes": actual.notes,
    }
