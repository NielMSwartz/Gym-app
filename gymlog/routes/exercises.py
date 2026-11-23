"""Exercise library CRUD."""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import Exercise, ProgramExercise, WorkoutExercise
from ..utils import parse_bool
from .helpers import current_user, owned

bp = Blueprint("exercises", __name__)


@bp.route("/exercises")
def library():
    user = current_user()
    search = request.args.get("q", "").strip()
    muscle = request.args.get("muscle", "").strip()
    show_archived = request.args.get("archived") == "1"

    query = Exercise.query.filter_by(user_id=user.id)
    if not show_archived:
        query = query.filter_by(is_archived=False)
    if search:
        like = f"%{search}%"
        query = query.filter(
            db.or_(Exercise.name.ilike(like), Exercise.equipment.ilike(like), Exercise.technique_notes.ilike(like))
        )
    if muscle:
        query = query.filter(Exercise.muscle_group == muscle)
    exercises = query.order_by(Exercise.name.asc()).all()
    muscle_groups = [
        row[0]
        for row in db.session.query(Exercise.muscle_group)
        .filter(Exercise.user_id == user.id)
        .distinct()
        .order_by(Exercise.muscle_group.asc())
        .all()
    ]
    return render_template(
        "exercises/library.html",
        exercises=exercises,
        search=search,
        muscle=muscle,
        muscle_groups=muscle_groups,
        show_archived=show_archived,
    )


@bp.route("/exercises/new", methods=["GET", "POST"])
def new_exercise():
    if request.method == "POST":
        exercise = Exercise(user_id=current_user().id)
        try:
            _apply_form(exercise)
        except ValueError as exc:
            flash(str(exc), "error")
            return render_template("exercises/form.html", exercise=exercise), 400
        db.session.add(exercise)
        db.session.commit()
        flash(f"“{exercise.name}” added to your library.", "success")
        return redirect(url_for("exercises.library"))
    return render_template("exercises/form.html", exercise=None)


@bp.route("/exercises/<int:exercise_id>/edit", methods=["GET", "POST"])
def edit_exercise(exercise_id: int):
    exercise = owned(Exercise, exercise_id, current_user().id)
    if request.method == "POST":
        try:
            _apply_form(exercise)
        except ValueError as exc:
            flash(str(exc), "error")
            return render_template("exercises/form.html", exercise=exercise), 400
        db.session.commit()
        flash("Exercise updated. Past workouts were not altered.", "success")
        return redirect(url_for("exercises.library"))
    return render_template("exercises/form.html", exercise=exercise)


@bp.post("/exercises/<int:exercise_id>/archive")
def archive_exercise(exercise_id: int):
    exercise = owned(Exercise, exercise_id, current_user().id)
    exercise.is_archived = not exercise.is_archived
    db.session.commit()
    flash("Exercise archived." if exercise.is_archived else "Exercise restored.", "success")
    return redirect(request.referrer or url_for("exercises.library"))


@bp.post("/exercises/<int:exercise_id>/delete")
def delete_exercise(exercise_id: int):
    exercise = owned(Exercise, exercise_id, current_user().id)
    used_in_plan = ProgramExercise.query.filter_by(exercise_id=exercise.id).count()
    if used_in_plan:
        flash("This exercise is used in a program. Archive it instead of deleting it.", "error")
        return redirect(url_for("exercises.library"))
    try:
        WorkoutExercise.query.filter_by(exercise_id=exercise.id).update({"exercise_id": None})
        db.session.delete(exercise)
        db.session.commit()
        flash("Exercise deleted. Historical workout snapshots were preserved.", "success")
    except IntegrityError:
        db.session.rollback()
        flash("This exercise could not be deleted because it is still referenced.", "error")
    return redirect(url_for("exercises.library"))


def _apply_form(exercise: Exercise) -> None:
    name = request.form.get("name", "").strip()
    if not name:
        raise ValueError("Exercise name is required.")
    exercise.name = name[:120]
    exercise.muscle_group = request.form.get("muscle_group", "Full body").strip()[:80] or "Full body"
    exercise.category = request.form.get("category", "Compound").strip()[:40] or "Compound"
    exercise.equipment = request.form.get("equipment", "Barbell").strip()[:80] or "Barbell"
    exercise.description = request.form.get("description", "")[:5000]
    exercise.technique_notes = request.form.get("technique_notes", "")[:5000]
    exercise.is_bodyweight = parse_bool(request.form.get("is_bodyweight", False))
    exercise.is_archived = parse_bool(request.form.get("is_archived", False))
