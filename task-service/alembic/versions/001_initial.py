"""task tables"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_directory",
        sa.Column("user_id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_user_directory_email", "user_directory", ["email"], unique=True)
    op.create_table(
        "tasks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("assignee_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('todo', 'in_progress', 'done')", name="ck_tasks_status"),
    )
    op.create_index("ix_tasks_owner_id", "tasks", ["owner_id"])
    op.create_index("ix_tasks_assignee_id", "tasks", ["assignee_id"])
    op.create_table(
        "idempotency_keys",
        sa.Column("user_id", sa.Uuid(), primary_key=True),
        sa.Column("key", sa.String(200), primary_key=True),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=False),
        sa.Column("response_body", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("idempotency_keys")
    op.drop_table("tasks")
    op.drop_table("user_directory")
