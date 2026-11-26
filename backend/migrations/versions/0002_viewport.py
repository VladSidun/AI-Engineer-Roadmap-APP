"""Persist the world map camera for each learner and campaign."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "viewport",
        sa.Column("learner_id", sa.Uuid(), sa.ForeignKey("learner.id"), primary_key=True),
        sa.Column("campaign_id", sa.String(32), primary_key=True),
        sa.Column("x", sa.Float()),
        sa.Column("y", sa.Float()),
        sa.Column("zoom", sa.Float()),
        sa.Column("selection", sa.String(32)),
        sa.Column("last_stage_id", sa.String(32)),
    )


def downgrade() -> None:
    op.drop_table("viewport")
