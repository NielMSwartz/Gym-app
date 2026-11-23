# Gym Logbook — Strength Tracker

Gym Logbook is a single-user, installable strength-training logbook built with Flask, SQLAlchemy, Neon PostgreSQL, Chart.js and a clean grey/red UI.

It keeps **plans** separate from **permanent workout history**: editing a program, renaming an exercise or deleting a library movement never rewrites completed sessions.

## Features

- **Dashboard** — current program week, today's planned session, recent workouts, records and volume trend.
- **Eight-week planner** — labelled week columns, per-day sessions, reusable templates, custom single-week editing, week-to-week copying, and a stacked mobile week selector.
- **Program builder** — starts completely empty; add/edit/duplicate/archive programs and configure exercises, planned sets, reps, load, RPE and notes yourself.
- **Exercise library** — seeded compound/isolation movements plus custom exercises, search, filtering, archive and safe delete.
- **Workout logging** — start programmed or freestyle sessions, resume drafts, copy previous values, record actual reps/load/RPE/RIR/completion/notes, add sets/exercises, rest timer.
- **Permanent logbook** — date/program filters, partial-session option, workout details and per-exercise history.
- **Progress Log** — a journal-style chronological view with session entries, volume, streaks and first/latest/estimated-1RM changes per exercise.
- **Statistics** — completed-set-only volume by week, muscle and exercise; strength progression; consistency; session volume; estimated 1RM clearly labelled as an **Epley estimate**, not a tested max.
- **Personal records** — automatic heaviest load, most reps at a weight, estimated 1RM, session volume and weekly volume, rebuilt from completed workouts.
- **PWA** — manifest, install button in Settings only when supported, service worker app-shell cache, offline page, generated icons, and an IndexedDB workout queue.
- **Offline sync** — idempotent `client_uuid` upserts, `base_updated_at` conflict detection, pending/conflict indicators, and no silent overwrites or duplicates.
- **Deployment** — Gunicorn, Render Blueprint, Neon pooled/direct connection split, health check, error handlers and structured logging.

## Architecture

| Layer | Technology |
| --- | --- |
| Web | Flask 3, Jinja templates, vanilla HTML/CSS/JS |
| Data | SQLAlchemy 2 + Flask-SQLAlchemy, Alembic/Flask-Migrate |
| Database | Neon Lakebase PostgreSQL (pooled for app, direct for migrations) |
| Charts | Locally vendored Chart.js 4 |
| PWA | Web manifest, service worker, IndexedDB sync queue |
| Production | Gunicorn behind Render HTTPS |

### Data model principles

- `Exercise` is a reusable definition.
- `ProgramExercise` and `PlannedSet` hold planned assignments.
- `WorkoutSession`, `WorkoutExercise` and `ActualSet` hold actual records.
- Workout rows carry snapshots (`program_name_snapshot`, `exercise_name_snapshot`, etc.) and nullable FKs with `SET NULL` where appropriate.
- Offline sync uses `SyncEvent.client_uuid` for idempotency and `base_updated_at` for conflict detection.

## Local setup

Requires Python 3.11+ and a Neon project. The repo's Neon CLI context is linked to the `gym-app-dev` branch; production `main` is left untouched until explicitly deployed.

```bash
# 1. Install dependencies
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux
pip install -r requirements-dev.txt

# 2. Configure secrets (never commit .env)
copy .env.example .env         # Windows
# cp .env.example .env         # macOS/Linux

# Pull the Neon development branch connection strings, or edit .env manually.
neon link --project-id <project-id> --branch gym-app-dev -y --no-env-pull
neon env pull --file .env

# 3. Migrate and seed (migrations use DATABASE_URL_UNPOOLED)
$env:FLASK_APP = "wsgi.py"     # Windows PowerShell
# export FLASK_APP=wsgi.py     # macOS/Linux
flask db upgrade
flask seed-exercises

# 4. Run locally
flask run --debug
```

Open <http://localhost:5000>.

Without `DATABASE_URL`, the app falls back to a local `sqlite:///gymlog.db`. This is convenient for quick experiments but Neon PostgreSQL is the intended data store.

### Optional access password

Set `APP_PASSWORD` in `.env` to gate the deployed app behind a single password. Leave it blank for local development. The health endpoint (`/api/health`), static files, manifest, service worker and offline shell remain reachable without the password so PWA installation and Render health checks still work.

## Common commands

```bash
# Tests
python -m pytest

# Create a migration after model changes
$env:FLASK_APP = "wsgi.py"
flask db migrate -m "describe change"
flask db upgrade

# Check registered routes
python -c "from wsgi import app; print(len(list(app.url_map.iter_rules())))"
```

## Pages

| Path | Purpose |
| --- | --- |
| `/` | Dashboard |
| `/programs` | Program list |
| `/programs/new` | Program builder |
| `/planner` | Active eight-week planner |
| `/exercises` | Exercise library |
| `/workouts/active` | Start/resume workouts |
| `/workouts/<id>` | Active workout logger |
| `/logbook` | Workout history |
| `/logbook/progress` | Progress journal and per-exercise changes |
| `/statistics` | Charts and analytics |
| `/records` | Personal records |
| `/settings` | Preferences and PWA info |
| `/api/health` | Render health check |
| `/manifest.webmanifest`, `/sw.js`, `/offline` | PWA endpoints |

## Offline behaviour

- Static app shell assets and the offline page are cached by the service worker.
- While offline, set edits and workout completion are queued in IndexedDB and shown as **pending sync**.
- On reconnection, queued workouts POST to `/api/sync/workouts`.
- Retrying the same `client_uuid` returns the existing workout instead of creating a duplicate.
- If the server copy is newer than the offline base version, a **conflict** is shown; the server is never silently overwritten.

## Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for the full Neon + Render checklist. The included `render.yaml` provisions the web service, migrations, seed command, health check, Gunicorn logging and environment variables.

## Security notes

- `.env`, `.neon`, local databases and caches are ignored by Git.
- Generate a unique `SECRET_KEY` for every deployment.
- Use Neon's pooled URL for application traffic and the direct URL for migrations.
- Keep `APP_PASSWORD` set on any public deployment unless you intentionally want an open logbook.
- No image generation service is required; PWA icons are generated locally by `scripts/make_icons.py`.
