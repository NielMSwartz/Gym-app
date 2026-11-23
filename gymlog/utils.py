"""Small, reusable helpers shared by routes, services and templates."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Iterable

from .models import AppSetting, Program, DAY_NAMES, utcnow


def parse_date(value: str | None, default: date | None = None) -> date | None:
    if not value:
        return default
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return default


def parse_float(value, default=None):
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_int(value, default=None):
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def parse_bool(value, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def iso(dt: datetime | None) -> str | None:
    if not dt:
        return None
    return dt.isoformat() + "Z"


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        cleaned = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)
        if dt.tzinfo:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except (TypeError, ValueError):
        return None


def weekday_name(index: int) -> str:
    if 0 <= index < len(DAY_NAMES):
        return DAY_NAMES[index]
    return "Unknown day"


def current_week_number(program: Program, on_date: date | None = None) -> int:
    on_date = on_date or date.today()
    elapsed = (on_date - program.start_date).days
    if elapsed < 0:
        return 1
    return min(program.duration_weeks, elapsed // 7 + 1)


def week_start_date(program: Program, week_number: int) -> date:
    return program.start_date + timedelta(days=(week_number - 1) * 7)


def week_end_date(program: Program, week_number: int) -> date:
    return week_start_date(program, week_number) + timedelta(days=6)


def epley_1rm(weight_kg: float | None, reps: int | None) -> float | None:
    """Epley formula estimate. Returns None for invalid/1RM inputs."""
    if weight_kg is None or reps is None:
        return None
    if weight_kg <= 0 or reps < 1:
        return None
    return round(weight_kg * (1 + reps / 30.0), 2)


def set_load_kg(additional_weight: float | None, is_bodyweight: bool, bodyweight_kg: float) -> float:
    """Total load used for volume and 1RM comparisons."""
    extra = additional_weight or 0.0
    return round(extra + (bodyweight_kg if is_bodyweight else 0.0), 2)


def set_volume_kg(load_kg: float, reps: int | None) -> float:
    return round((reps or 0) * load_kg, 2)


def get_setting(user_id: int, key: str, default: str = "") -> str:
    row = AppSetting.query.filter_by(user_id=user_id, key=key).first()
    return row.value if row else default


def get_float_setting(user_id: int, key: str, default: float) -> float:
    return parse_float(get_setting(user_id, key, ""), default) or default


def get_bool_setting(user_id: int, key: str, default: bool = False) -> bool:
    value = get_setting(user_id, key, "")
    return parse_bool(value) if value != "" else default


def set_setting(user_id: int, key: str, value: str) -> None:
    from .extensions import db

    row = AppSetting.query.filter_by(user_id=user_id, key=key).first()
    if row:
        row.value = str(value)
        row.updated_at = utcnow()
    else:
        db.session.add(AppSetting(user_id=user_id, key=key, value=str(value)))


def percent(part: float, total: float) -> int:
    if not total:
        return 0
    return min(100, max(0, round((part / total) * 100)))


def group_by_week(dates: Iterable[date]) -> dict[str, int]:
    buckets: dict[str, int] = {}
    for value in dates:
        monday = value - timedelta(days=value.weekday())
        key = monday.isoformat()
        buckets[key] = buckets.get(key, 0) + 1
    return buckets


def format_number(value: float | int | None, digits: int = 1) -> str:
    if value is None:
        return "—"
    number = float(value)
    if number.is_integer():
        return str(int(number))
    return f"{number:.{digits}f}".rstrip("0").rstrip(".")
