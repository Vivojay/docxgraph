"""add case urgency

Revision ID: 0003_case_urgency
Revises: 0002_enterprise_alignment
Create Date: 2026-05-04 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "0003_case_urgency"
down_revision = "0002_enterprise_alignment"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("cases") as batch_op:
        batch_op.add_column(sa.Column("urgency", sa.String(length=32), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("cases") as batch_op:
        batch_op.drop_column("urgency")
