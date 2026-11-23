"""PWA manifest, service worker and offline shell routes."""

from __future__ import annotations

import json
from pathlib import Path

from flask import Blueprint, current_app, Response, render_template

bp = Blueprint("pwa", __name__)


@bp.route("/manifest.webmanifest")
def manifest():
    base_url = current_app.config["PUBLIC_BASE_URL"]
    data = {
        "name": "Gym Logbook — Strength Tracker",
        "short_name": "GymLog",
        "description": "A clean strength-training logbook and progression tracker.",
        "id": "/",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "display_override": ["standalone", "minimal-ui"],
        "orientation": "portrait-primary",
        "background_color": "#0f1115",
        "theme_color": "#b42334",
        "categories": ["health", "fitness", "lifestyle"],
        "icons": [
            {"src": "/static/icons/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": "/static/icons/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
            {"src": "/static/icons/icon-maskable-192.png", "sizes": "192x192", "type": "image/png", "purpose": "maskable"},
            {"src": "/static/icons/icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ],
        "screenshots": [],
        "shortcuts": [
            {"name": "Active workout", "short_name": "Workout", "url": "/workouts/active", "icons": [{"src": "/static/icons/icon-192.png", "sizes": "192x192"}]},
            {"name": "Logbook", "short_name": "Logbook", "url": "/logbook", "icons": [{"src": "/static/icons/icon-192.png", "sizes": "192x192"}]},
        ],
    }
    if base_url and base_url.startswith("https://"):
        data["screenshots"] = []
    return Response(json.dumps(data, indent=2), mimetype="application/manifest+json")


@bp.route("/sw.js")
def service_worker():
    path = Path(current_app.root_path) / "static" / "sw.js"
    return Response(path.read_text(encoding="utf-8"), mimetype="application/javascript", headers={"Cache-Control": "no-cache, no-store, must-revalidate"})


@bp.route("/offline")
def offline():
    return render_template("pwa/offline.html")
