"""Shared route helpers."""

from __future__ import annotations

from flask import abort, g

from ..models import Program
from ..utils import get_setting, parse_int


def current_user():
    return g.app_user


def active_program() -> Program | None:
    user = current_user()
    preferred_id = parse_int(get_setting(user.id, "active_program_id"))
    if preferred_id:
        program = Program.query.filter_by(id=preferred_id, user_id=user.id, status="active").first()
        if program:
            return program
    return Program.query.filter_by(user_id=user.id, status="active").order_by(Program.created_at.desc()).first()


def owned(model, object_id: int, user_id: int | None = None):
    """Fetch a user-owned row or abort with 404."""
    row = model.query.get_or_404(object_id)
    user_id = user_id or current_user().id
    owner_id = getattr(row, "user_id", None)
    if owner_id is not None and owner_id != user_id:
        abort(404)
    return row
