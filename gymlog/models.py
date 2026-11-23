"""Relational models for the gym logbook.

Design rules:
- Reusable exercise definitions are separate from planned assignments and
  actual workout records.
- Workout records carry snapshots so editing programs or deleting library
  exercises never rewrites history.
- Planned and actual values are stored in different tables.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Index, UniqueConstraint

from .extensions import db


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    display_name = db.Column(db.String(80), nullable=False, default="Trainee")
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    programs = db.relationship("Program", back_populates="user", cascade="all, delete-orphan")
    exercises = db.relationship("Exercise", back_populates="user", cascade="all, delete-orphan")
    workouts = db.relationship("WorkoutSession", back_populates="user", cascade="all, delete-orphan")
    records = db.relationship("PersonalRecord", back_populates="user", cascade="all, delete-orphan")
    settings = db.relationship("AppSetting", back_populates="user", cascade="all, delete-orphan")


class AppSetting(db.Model):
    __tablename__ = "app_settings"
    __table_args__ = (UniqueConstraint("user_id", "key", name="uq_app_setting_user_key"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    key = db.Column(db.String(64), nullable=False)
    value = db.Column(db.Text, nullable=False, default="")
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    user = db.relationship("User", back_populates="settings")


class Program(db.Model):
    __tablename__ = "programs"
    __table_args__ = (
        Index("ix_programs_user_status", "user_id", "status"),
        Index("ix_programs_user_start", "user_id", "start_date"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=False, default="")
    start_date = db.Column(db.Date, nullable=False)
    duration_weeks = db.Column(db.Integer, nullable=False, default=8)
    status = db.Column(db.String(20), nullable=False, default="active")
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    user = db.relationship("User", back_populates="programs")
    weeks = db.relationship(
        "ProgramWeek",
        back_populates="program",
        cascade="all, delete-orphan",
        order_by="ProgramWeek.week_number",
    )

    @property
    def is_active(self) -> bool:
        return self.status == "active"

    @property
    def total_planned_sessions(self) -> int:
        return sum(
            1
            for week in self.weeks
            for day in week.days
            if not day.is_rest
        )


class ProgramWeek(db.Model):
    __tablename__ = "program_weeks"
    __table_args__ = (
        UniqueConstraint("program_id", "week_number", name="uq_program_week_number"),
        Index("ix_program_weeks_program", "program_id"),
    )

    id = db.Column(db.Integer, primary_key=True)
    program_id = db.Column(db.Integer, db.ForeignKey("programs.id", ondelete="CASCADE"), nullable=False)
    week_number = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(80), nullable=False, default="")
    notes = db.Column(db.Text, nullable=False, default="")

    program = db.relationship("Program", back_populates="weeks")
    days = db.relationship(
        "TrainingDay",
        back_populates="week",
        cascade="all, delete-orphan",
        order_by="TrainingDay.day_of_week, TrainingDay.id",
    )


class TrainingDay(db.Model):
    __tablename__ = "training_days"
    __table_args__ = (
        UniqueConstraint("week_id", "day_of_week", name="uq_training_day_week_day"),
        Index("ix_training_days_week", "week_id"),
    )

    id = db.Column(db.Integer, primary_key=True)
    week_id = db.Column(db.Integer, db.ForeignKey("program_weeks.id", ondelete="CASCADE"), nullable=False)
    day_of_week = db.Column(db.Integer, nullable=False)  # 0 = Monday
    label = db.Column(db.String(80), nullable=False, default="")
    is_rest = db.Column(db.Boolean, nullable=False, default=False)
    notes = db.Column(db.Text, nullable=False, default="")

    week = db.relationship("ProgramWeek", back_populates="days")
    exercises = db.relationship(
        "ProgramExercise",
        back_populates="training_day",
        cascade="all, delete-orphan",
        order_by="ProgramExercise.order_index, ProgramExercise.id",
    )

    @property
    def display_label(self) -> str:
        return self.label or DAY_NAMES[self.day_of_week]


DAY_NAMES = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)
DAY_SHORT = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


class Exercise(db.Model):
    __tablename__ = "exercises"
    __table_args__ = (
        Index("ix_exercises_user_name", "user_id", "name"),
        Index("ix_exercises_user_muscle", "user_id", "muscle_group"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    muscle_group = db.Column(db.String(80), nullable=False, default="Full body")
    category = db.Column(db.String(40), nullable=False, default="Compound")
    equipment = db.Column(db.String(80), nullable=False, default="Barbell")
    description = db.Column(db.Text, nullable=False, default="")
    technique_notes = db.Column(db.Text, nullable=False, default="")
    is_bodyweight = db.Column(db.Boolean, nullable=False, default=False)
    is_archived = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    user = db.relationship("User", back_populates="exercises")
    assignments = db.relationship("ProgramExercise", back_populates="exercise")


class ProgramExercise(db.Model):
    __tablename__ = "program_exercises"
    __table_args__ = (Index("ix_program_exercises_day", "training_day_id"),)

    id = db.Column(db.Integer, primary_key=True)
    training_day_id = db.Column(
        db.Integer, db.ForeignKey("training_days.id", ondelete="CASCADE"), nullable=False
    )
    exercise_id = db.Column(
        db.Integer, db.ForeignKey("exercises.id", ondelete="RESTRICT"), nullable=False
    )
    order_index = db.Column(db.Integer, nullable=False, default=0)
    notes = db.Column(db.Text, nullable=False, default="")
    progression_notes = db.Column(db.Text, nullable=False, default="")

    training_day = db.relationship("TrainingDay", back_populates="exercises")
    exercise = db.relationship("Exercise", back_populates="assignments")
    planned_sets = db.relationship(
        "PlannedSet",
        back_populates="program_exercise",
        cascade="all, delete-orphan",
        order_by="PlannedSet.set_number, PlannedSet.id",
    )


class PlannedSet(db.Model):
    __tablename__ = "planned_sets"
    __table_args__ = (Index("ix_planned_sets_exercise", "program_exercise_id"),)

    id = db.Column(db.Integer, primary_key=True)
    program_exercise_id = db.Column(
        db.Integer, db.ForeignKey("program_exercises.id", ondelete="CASCADE"), nullable=False
    )
    set_number = db.Column(db.Integer, nullable=False)
    target_reps = db.Column(db.Integer, nullable=False, default=8)
    target_weight_kg = db.Column(db.Float, nullable=True)
    target_rpe = db.Column(db.Float, nullable=True)
    rest_seconds = db.Column(db.Integer, nullable=True)
    notes = db.Column(db.Text, nullable=False, default="")

    program_exercise = db.relationship("ProgramExercise", back_populates="planned_sets")


class WorkoutSession(db.Model):
    __tablename__ = "workout_sessions"
    __table_args__ = (
        UniqueConstraint("client_uuid", name="uq_workout_client_uuid"),
        Index("ix_workouts_user_status_started", "user_id", "status", "started_at"),
        Index("ix_workouts_user_program_week", "user_id", "program_id", "week_number"),
    )

    id = db.Column(db.Integer, primary_key=True)
    client_uuid = db.Column(db.String(64), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Snapshots keep history intact when programs or exercises change.
    program_id = db.Column(db.Integer, db.ForeignKey("programs.id", ondelete="SET NULL"), nullable=True)
    program_name_snapshot = db.Column(db.String(120), nullable=False, default="Freestyle session")
    week_number = db.Column(db.Integer, nullable=True)
    training_day_id = db.Column(
        db.Integer, db.ForeignKey("training_days.id", ondelete="SET NULL"), nullable=True
    )
    training_day_name_snapshot = db.Column(db.String(80), nullable=False, default="Training session")

    started_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="in_progress")
    notes = db.Column(db.Text, nullable=False, default="")
    sync_status = db.Column(db.String(20), nullable=False, default="synced")
    version = db.Column(db.Integer, nullable=False, default=1)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    user = db.relationship("User", back_populates="workouts")
    program = db.relationship("Program")
    training_day = db.relationship("TrainingDay")
    exercises = db.relationship(
        "WorkoutExercise",
        back_populates="workout",
        cascade="all, delete-orphan",
        order_by="WorkoutExercise.order_index, WorkoutExercise.id",
    )

    @property
    def is_complete(self) -> bool:
        return self.status == "completed"

    @property
    def title(self) -> str:
        if self.week_number:
            return f"{self.training_day_name_snapshot} · Week {self.week_number}"
        return self.training_day_name_snapshot


class WorkoutExercise(db.Model):
    __tablename__ = "workout_exercises"
    __table_args__ = (Index("ix_workout_exercises_workout", "workout_session_id"),)

    id = db.Column(db.Integer, primary_key=True)
    workout_session_id = db.Column(
        db.Integer, db.ForeignKey("workout_sessions.id", ondelete="CASCADE"), nullable=False
    )
    exercise_id = db.Column(
        db.Integer, db.ForeignKey("exercises.id", ondelete="SET NULL"), nullable=True
    )
    exercise_name_snapshot = db.Column(db.String(120), nullable=False)
    muscle_group_snapshot = db.Column(db.String(80), nullable=False, default="")
    is_bodyweight_snapshot = db.Column(db.Boolean, nullable=False, default=False)
    order_index = db.Column(db.Integer, nullable=False, default=0)
    notes = db.Column(db.Text, nullable=False, default="")

    workout = db.relationship("WorkoutSession", back_populates="exercises")
    exercise = db.relationship("Exercise")
    sets = db.relationship(
        "ActualSet",
        back_populates="workout_exercise",
        cascade="all, delete-orphan",
        order_by="ActualSet.set_number, ActualSet.id",
    )

    @property
    def exercise_key(self) -> str:
        return str(self.exercise_id) if self.exercise_id else f"name:{self.exercise_name_snapshot}"


class ActualSet(db.Model):
    __tablename__ = "actual_sets"
    __table_args__ = (Index("ix_actual_sets_workout_exercise", "workout_exercise_id"),)

    id = db.Column(db.Integer, primary_key=True)
    workout_exercise_id = db.Column(
        db.Integer, db.ForeignKey("workout_exercises.id", ondelete="CASCADE"), nullable=False
    )
    set_number = db.Column(db.Integer, nullable=False)
    actual_reps = db.Column(db.Integer, nullable=True)
    actual_weight_kg = db.Column(db.Float, nullable=True)
    rpe = db.Column(db.Float, nullable=True)
    rir = db.Column(db.Float, nullable=True)
    is_completed = db.Column(db.Boolean, nullable=False, default=False)
    notes = db.Column(db.Text, nullable=False, default="")
    completed_at = db.Column(db.DateTime, nullable=True)

    workout_exercise = db.relationship("WorkoutExercise", back_populates="sets")


class PersonalRecord(db.Model):
    __tablename__ = "personal_records"
    __table_args__ = (
        Index("ix_records_user_type", "user_id", "record_type"),
        Index("ix_records_user_exercise", "user_id", "exercise_key"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    record_type = db.Column(db.String(40), nullable=False)
    exercise_key = db.Column(db.String(160), nullable=False)
    exercise_name_snapshot = db.Column(db.String(120), nullable=False)
    comparison_key = db.Column(db.String(80), nullable=False, default="all")
    value = db.Column(db.Float, nullable=False)
    reps = db.Column(db.Integer, nullable=True)
    weight_kg = db.Column(db.Float, nullable=True)
    achieved_at = db.Column(db.DateTime, nullable=False)
    workout_session_id = db.Column(
        db.Integer, db.ForeignKey("workout_sessions.id", ondelete="SET NULL"), nullable=True
    )
    actual_set_id = db.Column(
        db.Integer, db.ForeignKey("actual_sets.id", ondelete="SET NULL"), nullable=True
    )
    details = db.Column(db.Text, nullable=False, default="")
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    user = db.relationship("User", back_populates="records")
    workout = db.relationship("WorkoutSession")


class SyncEvent(db.Model):
    __tablename__ = "sync_events"
    __table_args__ = (UniqueConstraint("client_uuid", name="uq_sync_event_client_uuid"),)

    id = db.Column(db.Integer, primary_key=True)
    client_uuid = db.Column(db.String(64), nullable=False)
    entity_type = db.Column(db.String(40), nullable=False, default="workout_session")
    action = db.Column(db.String(20), nullable=False, default="upsert")
    payload = db.Column(db.JSON, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="applied")
    server_workout_id = db.Column(db.Integer, nullable=True)
    error = db.Column(db.Text, nullable=False, default="")
    received_at = db.Column(db.DateTime, nullable=False, default=utcnow)
