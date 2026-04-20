"""add topic report prompt hint

Revision ID: 0002_topic_prompt_hint
Revises: 0001_initial
Create Date: 2026-04-17 10:45:00
"""

import sqlalchemy as sa
from alembic import op

revision = "0002_topic_prompt_hint"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("topics", sa.Column("report_prompt_hint", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("topics", "report_prompt_hint")
