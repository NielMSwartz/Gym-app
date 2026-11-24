"""manual program exercise names

Revision ID: 9b2f1c7a4d6e
Revises: 3f76f40b59b9
Create Date: 2026-11-24 12:00:00.000000

Program exercises are now typed manually. Existing library-linked plans keep
their names as snapshots so workout history and the planner stay intact.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '9b2f1c7a4d6e'
down_revision = '3f76f40b59b9'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('program_exercises') as batch_op:
        batch_op.add_column(sa.Column('exercise_name_snapshot', sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column('muscle_group_snapshot', sa.String(length=80), nullable=True))
        batch_op.add_column(sa.Column('is_bodyweight_snapshot', sa.Boolean(), nullable=True))

    # Preserve existing planned exercises by copying their library labels.
    op.execute("""
        UPDATE program_exercises AS pe
        SET exercise_name_snapshot = e.name,
            muscle_group_snapshot = e.muscle_group,
            is_bodyweight_snapshot = e.is_bodyweight
        FROM exercises AS e
        WHERE pe.exercise_id = e.id
    """)
    op.execute("""
        UPDATE program_exercises
        SET exercise_name_snapshot = COALESCE(exercise_name_snapshot, ''),
            muscle_group_snapshot = COALESCE(muscle_group_snapshot, ''),
            is_bodyweight_snapshot = COALESCE(is_bodyweight_snapshot, FALSE)
    """)

    with op.batch_alter_table('program_exercises') as batch_op:
        batch_op.alter_column('exercise_id', existing_type=sa.Integer(), nullable=True)
        batch_op.alter_column('exercise_name_snapshot', existing_type=sa.String(length=120), nullable=False)
        batch_op.alter_column('muscle_group_snapshot', existing_type=sa.String(length=80), nullable=False)
        batch_op.alter_column('is_bodyweight_snapshot', existing_type=sa.Boolean(), nullable=False)


def downgrade():
    # Manual-only exercises cannot be represented by the old schema. Link any
    # that match a library exercise by name, then drop the rest.
    op.execute("""
        UPDATE program_exercises AS pe
        SET exercise_id = e.id
        FROM exercises AS e
        WHERE pe.exercise_id IS NULL
          AND LOWER(pe.exercise_name_snapshot) = LOWER(e.name)
    """)
    op.execute("DELETE FROM program_exercises WHERE exercise_id IS NULL")

    with op.batch_alter_table('program_exercises') as batch_op:
        batch_op.alter_column('exercise_id', existing_type=sa.Integer(), nullable=False)
        batch_op.drop_column('is_bodyweight_snapshot')
        batch_op.drop_column('muscle_group_snapshot')
        batch_op.drop_column('exercise_name_snapshot')
