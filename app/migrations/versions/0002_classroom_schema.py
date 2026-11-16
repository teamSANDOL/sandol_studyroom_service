"""강의실 테이블을 classroom 스키마에 만든다.

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS classroom")
    op.create_table(
        "buildings",
        sa.Column("id", sa.SmallInteger(), nullable=False),
        sa.Column("name", sa.String(length=20), nullable=False),
        sa.Column(
            "aliases",
            sa.ARRAY(sa.String(length=20)),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_buildings")),
        sa.UniqueConstraint("name", name=op.f("uq_buildings_name")),
        schema="classroom",
    )
    op.create_table(
        "lectures",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("course_code", sa.String(length=16), nullable=False),
        sa.Column("division", sa.String(length=8), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("professor", sa.String(length=50), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lectures")),
        sa.UniqueConstraint(
            "course_code", "division", name=op.f("uq_lectures_course_code")
        ),
        schema="classroom",
    )
    op.create_table(
        "classrooms",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("building_id", sa.SmallInteger(), nullable=False),
        sa.Column("room", sa.String(length=20), nullable=False),
        sa.ForeignKeyConstraint(
            ["building_id"],
            ["classroom.buildings.id"],
            name=op.f("fk_classrooms_building_id_buildings"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_classrooms")),
        sa.UniqueConstraint(
            "building_id", "room", name=op.f("uq_classrooms_building_id")
        ),
        schema="classroom",
    )
    op.create_table(
        "lecture_slots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("lecture_id", sa.Integer(), nullable=False),
        sa.Column("classroom_id", sa.Integer(), nullable=True),
        sa.Column("day", sa.SmallInteger(), nullable=False),
        sa.Column("start_minute", sa.SmallInteger(), nullable=False),
        sa.Column("end_minute", sa.SmallInteger(), nullable=False),
        sa.Column("period_start", sa.SmallInteger(), nullable=True),
        sa.Column("period_end", sa.SmallInteger(), nullable=True),
        sa.CheckConstraint(
            "0 <= start_minute AND start_minute < end_minute AND end_minute <= 1440",
            name=op.f("ck_lecture_slots_minute_range"),
        ),
        sa.CheckConstraint(
            "day BETWEEN 0 AND 6", name=op.f("ck_lecture_slots_day_range")
        ),
        sa.ForeignKeyConstraint(
            ["classroom_id"],
            ["classroom.classrooms.id"],
            name=op.f("fk_lecture_slots_classroom_id_classrooms"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["lecture_id"],
            ["classroom.lectures.id"],
            name=op.f("fk_lecture_slots_lecture_id_lectures"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lecture_slots")),
        schema="classroom",
    )
    op.create_index(
        "ix_lecture_slots_classroom_id_day",
        "lecture_slots",
        ["classroom_id", "day"],
        unique=False,
        schema="classroom",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_lecture_slots_classroom_id_day",
        table_name="lecture_slots",
        schema="classroom",
    )
    op.drop_table("lecture_slots", schema="classroom")
    op.drop_table("classrooms", schema="classroom")
    op.drop_table("lectures", schema="classroom")
    op.drop_table("buildings", schema="classroom")
    op.execute("DROP SCHEMA classroom")
