"""Store the latest published learning activity separately from map selection."""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("viewport", sa.Column("last_activity_id", sa.String(32), nullable=True))


def downgrade() -> None:
    op.drop_column("viewport", "last_activity_id")
