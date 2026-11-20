"""열람실 테이블을 studyroom 스키마에 둔다.

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

SCHEMA = "studyroom"
# FK 가 readingrooms 를 가리키므로 readingrooms 를 먼저 옮긴다.
TABLES = ("readingrooms", "readingroom_observations", "collector_state")


def _public_tables_exist() -> bool:
    found = op.get_bind().scalar(sa.text("SELECT to_regclass('public.readingrooms')"))
    return found is not None


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")
    # alembic 도입 전 create_all 로 public 에 만든 테이블은 데이터째 옮긴다.
    if _public_tables_exist():
        for table in TABLES:
            op.execute(f"ALTER TABLE public.{table} SET SCHEMA {SCHEMA}")
        return

    op.create_table(
        "readingrooms",
        sa.Column("code", sa.String(length=2), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.PrimaryKeyConstraint("code", name=op.f("pk_readingrooms")),
        schema=SCHEMA,
    )
    op.create_table(
        "readingroom_observations",
        sa.Column("readingroom_code", sa.String(length=2), nullable=False),
        sa.Column("observed_minute", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("used", sa.Integer(), nullable=False),
        sa.Column("available", sa.Integer(), nullable=False),
        sa.Column("is_open", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "date_trunc('minute', observed_at AT TIME ZONE 'UTC') "
            "= observed_minute AT TIME ZONE 'UTC'",
            name=op.f("ck_readingroom_observations_minute_matches_observed_at"),
        ),
        sa.CheckConstraint(
            "available >= 0",
            name=op.f("ck_readingroom_observations_available_nonnegative"),
        ),
        sa.CheckConstraint(
            "total > 0", name=op.f("ck_readingroom_observations_total_positive")
        ),
        sa.CheckConstraint(
            "used + available = total",
            name=op.f("ck_readingroom_observations_capacity_balances"),
        ),
        sa.CheckConstraint(
            "used >= 0", name=op.f("ck_readingroom_observations_used_nonnegative")
        ),
        sa.ForeignKeyConstraint(
            ["readingroom_code"],
            [f"{SCHEMA}.readingrooms.code"],
            name=op.f("fk_readingroom_observations_readingroom_code_readingrooms"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "readingroom_code",
            "observed_minute",
            name=op.f("pk_readingroom_observations"),
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_readingroom_observations_observed_minute",
        "readingroom_observations",
        ["observed_minute"],
        schema=SCHEMA,
    )
    op.create_table(
        "collector_state",
        sa.Column("id", sa.SmallInteger(), server_default=sa.text("1"), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_stored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=64), nullable=True),
        sa.Column("last_cleanup_date", sa.Date(), nullable=True),
        sa.Column("last_cleanup_error_code", sa.String(length=64), nullable=True),
        sa.CheckConstraint("id = 1", name=op.f("ck_collector_state_singleton_id")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_collector_state")),
        schema=SCHEMA,
    )


def downgrade() -> None:
    # alembic 도입 전 배치로 되돌린다. 데이터는 그대로 따라간다.
    for table in TABLES:
        op.execute(f"ALTER TABLE {SCHEMA}.{table} SET SCHEMA public")
    op.execute(f"DROP SCHEMA {SCHEMA}")
