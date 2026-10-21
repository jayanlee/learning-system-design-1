"""processed events and audit log"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "002_consumer"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "processed_events",
        sa.Column("event_id", sa.Uuid(), primary_key=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("task_id", sa.Uuid(), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_log_event_id", "audit_log", ["event_id"], unique=True)


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("processed_events")
