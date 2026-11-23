"""JSON APIs used by offline sync and PWA clients."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from ..extensions import db
from ..services import apply_workout_payload
from .helpers import current_user

bp = Blueprint("api", __name__)


@bp.get("/api/health")
def health():
    return jsonify({"ok": True, "service": "iron-oath"})


@bp.post("/api/sync/workouts")
def sync_workout():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"status": "error", "message": "A JSON workout payload is required."}), 400
    result, _session = apply_workout_payload(payload, current_user().id)
    if result["status"] == "error":
        return jsonify(result), 400
    if result["status"] == "conflict":
        db.session.commit()
        return jsonify(result), 409
    db.session.commit()
    return jsonify(result)
