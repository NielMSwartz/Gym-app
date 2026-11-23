"""Optional single-user password gate."""

from __future__ import annotations

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from urllib.parse import urlparse

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if not current_app.config.get("APP_PASSWORD"):
        return redirect(url_for("dashboard.index"))
    if request.method == "POST":
        if request.form.get("password", "") == current_app.config["APP_PASSWORD"]:
            session["authenticated"] = True
            target = request.form.get("next", "")
            if not target.startswith("/") or target.startswith("//"):
                target = url_for("dashboard.index")
            flash("Welcome back to the training hall.", "success")
            return redirect(target)
        flash("That password is not correct.", "error")
    next_url = request.args.get("next", "")
    if not next_url.startswith("/") or next_url.startswith("//"):
        next_url = urlparse(request.referrer or "").path or url_for("dashboard.index")
    return render_template("auth/login.html", next_url=next_url)


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have left the training hall.", "success")
    return redirect(url_for("auth.login") if current_app.config.get("APP_PASSWORD") else url_for("dashboard.index"))
