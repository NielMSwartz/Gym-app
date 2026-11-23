"""User settings."""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..extensions import db
from ..utils import parse_bool, parse_float, set_setting
from .helpers import current_user

bp = Blueprint("settings", __name__)


@bp.route("/settings", methods=["GET", "POST"])
def index():
    user = current_user()
    if request.method == "POST":
        display_name = request.form.get("display_name", "").strip()
        if display_name:
            user.display_name = display_name[:80]
        bodyweight = parse_float(request.form.get("bodyweight_kg"), 75.0) or 75.0
        rest = parse_float(request.form.get("rest_timer_seconds"), 90) or 90
        set_setting(user.id, "bodyweight_kg", str(max(1.0, min(400.0, bodyweight))))
        set_setting(user.id, "rest_timer_seconds", str(max(15, min(600, int(rest)))))
        set_setting(user.id, "include_partial_in_stats", "true" if parse_bool(request.form.get("include_partial_in_stats")) else "false")
        db.session.commit()
        flash("Settings saved.", "success")
        return redirect(url_for("settings.index"))
    return render_template("settings/index.html", user=user)
