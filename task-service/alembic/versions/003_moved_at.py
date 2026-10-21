"""hide moved task rows after an owner transfer"""

from alembic import op
import sqlalchemy as sa

revision = "003_moved_at"
down_revision = "002_outbox"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("moved_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("tasks", "moved_at")
