"""Program builder and eight-week training planner."""

from __future__ import annotations

import json

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from ..extensions import db
from ..models import Exercise, Program, TrainingDay
from ..services import (
    blank_program_payload,
    copy_week,
    duplicate_program,
    program_to_dict,
    save_program_from_payload,
    week_payload,
)
from ..utils import get_setting, set_setting
from .helpers import active_program, current_user, owned

bp = Blueprint("programs", __name__)


def _exercise_choices(user_id: int) -> list[dict]:
    rows = (
        Exercise.query.filter_by(user_id=user_id, is_archived=False)
        .order_by(Exercise.name.asc())
        .all()
    )
    return [
        {
            "id": row.id,
            "name": row.name,
            "muscle_group": row.muscle_group,
            "equipment": row.equipment,
            "is_bodyweight": row.is_bodyweight,
        }
        for row in rows
    ]


def _parse_payload() -> dict:
    raw = request.form.get("payload", "")
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("The program configuration could not be read. Please try again.") from exc
    if not isinstance(payload, dict):
        raise ValueError("Invalid program configuration.")
    return payload


@bp.route("/programs")
def list_programs():
    user = current_user()
    programs = Program.query.filter_by(user_id=user.id).order_by(Program.created_at.desc()).all()
    active = active_program()
    return render_template("programs/list.html", programs=programs, active=active)


@bp.route("/programs/new", methods=["GET", "POST"])
def new_program():
    user = current_user()
    choices = _exercise_choices(user.id)
    if request.method == "POST":
        try:
            program = save_program_from_payload(user.id, _parse_payload())
        except ValueError as exc:
            flash(str(exc), "error")
            return render_template(
                "programs/builder.html",
                program=None,
                payload=request.form.get("payload", ""),
                payload_obj=_safe_payload(request.form.get("payload", "")),
                exercises=choices,
                editing_week=False,
            ), 400
        db.session.commit()
        set_setting(user.id, "active_program_id", str(program.id))
        db.session.commit()
        flash(f"Program “{program.name}” has been saved.", "success")
        return redirect(url_for("programs.planner", program_id=program.id))
    names = {row["name"]: row["id"] for row in choices}
    payload = blank_program_payload(names, 8)
    return render_template(
        "programs/builder.html",
        program=None,
        payload=json.dumps(payload),
        payload_obj=payload,
        exercises=choices,
        editing_week=False,
    )


@bp.route("/programs/<int:program_id>/edit", methods=["GET", "POST"])
def edit_program(program_id: int):
    user = current_user()
    program = owned(Program, program_id, user.id)
    choices = _exercise_choices(user.id)
    if request.method == "POST":
        try:
            save_program_from_payload(user.id, _parse_payload(), program)
        except ValueError as exc:
            flash(str(exc), "error")
            return render_template(
                "programs/builder.html",
                program=program,
                payload=request.form.get("payload", ""),
                payload_obj=_safe_payload(request.form.get("payload", "")),
                exercises=choices,
                editing_week=False,
            ), 400
        db.session.commit()
        flash("Program updated. Your logged workouts remain untouched.", "success")
        return redirect(url_for("programs.planner", program_id=program.id))
    payload = program_to_dict(program)
    return render_template(
        "programs/builder.html",
        program=program,
        payload=json.dumps(payload),
        payload_obj=payload,
        exercises=choices,
        editing_week=False,
    )


@bp.route("/programs/<int:program_id>/weeks/<int:week_number>/edit", methods=["GET", "POST"])
def edit_week(program_id: int, week_number: int):
    user = current_user()
    program = owned(Program, program_id, user.id)
    week = next((w for w in program.weeks if w.week_number == week_number), None)
    if not week:
        abort(404)
    choices = _exercise_choices(user.id)
    if request.method == "POST":
        try:
            incoming = _parse_payload()
            full = program_to_dict(program)
            incoming_week = (incoming.get("weeks") or [None])[0]
            if not isinstance(incoming_week, dict):
                raise ValueError("Invalid week configuration.")
            incoming_week["week_number"] = week_number
            full["weeks"][week_number - 1] = incoming_week
            save_program_from_payload(user.id, full, program)
        except (ValueError, IndexError) as exc:
            flash(str(exc), "error")
            return redirect(url_for("programs.edit_week", program_id=program_id, week_number=week_number))
        db.session.commit()
        flash(f"Week {week_number} has been customised.", "success")
        return redirect(url_for("programs.planner", program_id=program_id))
    payload = {"weeks": [week_payload(week)]}
    return render_template(
        "programs/builder.html",
        program=program,
        payload=json.dumps(payload),
        payload_obj=payload,
        exercises=choices,
        editing_week=True,
        week_number=week_number,
    )


@bp.post("/programs/<int:program_id>/delete")
def delete_program(program_id: int):
    user = current_user()
    program = owned(Program, program_id, user.id)
    db.session.delete(program)
    if get_setting(user.id, "active_program_id") == str(program_id):
        set_setting(user.id, "active_program_id", "")
    db.session.commit()
    flash("Program deleted. Completed workouts remain in your logbook.", "success")
    return redirect(url_for("programs.list_programs"))


@bp.post("/programs/<int:program_id>/duplicate")
def duplicate(program_id: int):
    user = current_user()
    program = owned(Program, program_id, user.id)
    copy = duplicate_program(program, user.id)
    db.session.commit()
    flash(f"Duplicated as “{copy.name}”.", "success")
    return redirect(url_for("programs.edit_program", program_id=copy.id))


@bp.post("/programs/<int:program_id>/archive")
def archive(program_id: int):
    program = owned(Program, program_id, current_user().id)
    program.status = "archived"
    db.session.commit()
    flash("Program archived.", "success")
    return redirect(url_for("programs.list_programs"))


@bp.post("/programs/<int:program_id>/activate")
def activate(program_id: int):
    user = current_user()
    owned(Program, program_id, user.id)
    set_setting(user.id, "active_program_id", str(program_id))
    db.session.commit()
    flash("Active program changed.", "success")
    return redirect(url_for("programs.list_programs"))


@bp.route("/planner")
def planner():
    program = active_program()
    if not program:
        first = Program.query.filter_by(user_id=current_user().id).order_by(Program.created_at.desc()).first()
        if first:
            return redirect(url_for("programs.planner", program_id=first.id))
        flash("Create a program before opening the training planner.", "info")
        return redirect(url_for("programs.new_program"))
    return redirect(url_for("programs.planner", program_id=program.id))


@bp.route("/planner/program/<int:program_id>")
def planner_program(program_id: int):
    user = current_user()
    program = owned(Program, program_id, user.id)
    all_programs = Program.query.filter_by(user_id=user.id).order_by(Program.created_at.desc()).all()
    return render_template("programs/planner.html", program=program, all_programs=all_programs)


@bp.route("/planner/session/<int:day_id>")
def session_detail(day_id: int):
    day = TrainingDay.query.get_or_404(day_id)
    if day.week.program.user_id != current_user().id:
        abort(404)
    return render_template("programs/session_detail.html", day=day)


@bp.post("/planner/weeks/<int:week_id>/copy")
def copy_week_route(week_id: int):
    from ..models import ProgramWeek

    target = ProgramWeek.query.get_or_404(week_id)
    if target.program.user_id != current_user().id:
        abort(404)
    source_number = int(request.form.get("source_week", 0))
    source = next((w for w in target.program.weeks if w.week_number == source_number), None)
    if not source or source.id == target.id:
        flash("Choose a different source week.", "error")
    else:
        copy_week(source, target)
        db.session.commit()
        flash(f"Week {source_number} copied into week {target.week_number}.", "success")
    return redirect(url_for("programs.planner", program_id=target.program_id))


def _safe_payload(raw: str):
    try:
        value = json.loads(raw)
        return value if isinstance(value, dict) else None
    except (TypeError, ValueError):
        return None
