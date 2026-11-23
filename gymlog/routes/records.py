"""Personal records page."""

from __future__ import annotations

from flask import Blueprint, render_template, request

from ..models import PersonalRecord
from ..utils import format_number
from .helpers import current_user

bp = Blueprint("records", __name__)

RECORD_LABELS = {
    "heaviest_load": "Heaviest load",
    "most_reps_at_weight": "Most reps at a weight",
    "estimated_1rm": "Estimated 1RM (Epley)",
    "session_volume": "Session volume",
    "weekly_volume": "Weekly volume",
}


@bp.route("/records")
def index():
    user = current_user()
    record_type = request.args.get("type", "").strip()
    query = PersonalRecord.query.filter_by(user_id=user.id)
    if record_type:
        query = query.filter_by(record_type=record_type)
    records = query.order_by(PersonalRecord.achieved_at.desc(), PersonalRecord.id.desc()).all()

    grouped: dict[str, list] = {}
    for record in records:
        grouped.setdefault(record.record_type, []).append(record)
        record.display_value = _display_value(record)

    return render_template(
        "records/index.html",
        grouped=grouped,
        labels=RECORD_LABELS,
        record_type=record_type,
        total=len(records),
    )


def _display_value(record: PersonalRecord) -> str:
    if record.record_type == "most_reps_at_weight":
        return f"{record.value} reps"
    if record.record_type in {"estimated_1rm", "heaviest_load"}:
        return f"{format_number(record.value)} kg"
    return f"{format_number(record.value, 0)} kg volume"
