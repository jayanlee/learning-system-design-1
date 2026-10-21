"""outbox and processed events"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "002_outbox"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "outbox",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("locked_by", sa.String(100), nullable=True),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_outbox_event_id", "outbox", ["event_id"], unique=True)
    op.create_table(
        "processed_events",
        sa.Column("event_id", sa.Uuid(), primary_key=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("processed_events")
    op.drop_table("outbox")
