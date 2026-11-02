"""task units, production rates and the site checklist

Revision ID: b41d7e2c9a10
Revises: 69c6e867ba75
Create Date: 2026-10-29 19:10:00
"""
from alembic import op
import sqlalchemy as sa


revision = 'b41d7e2c9a10'
down_revision = '69c6e867ba75'
branch_labels = None
depends_on = None

UNIT_COLUMNS = ("quantity", "coats", "production_rate", "unit_price")


def upgrade() -> None:
    # Existing tasks are hourly, as they were.
    for table in ("job_tasks", "task_templates"):
        op.add_column(table, sa.Column('unit', sa.String(length=10), server_default='hr', nullable=False))
        for col in UNIT_COLUMNS:
            if table == "task_templates" and col == "quantity":
                continue
            op.add_column(table, sa.Column(col, sa.Float(), nullable=True))
    op.add_column('leads', sa.Column('survey', sa.Text(), server_default='', nullable=False))


def downgrade() -> None:
    op.drop_column('leads', 'survey')
    for table in ("job_tasks", "task_templates"):
        for col in UNIT_COLUMNS:
            if table == "task_templates" and col == "quantity":
                continue
            op.drop_column(table, col)
        op.drop_column(table, 'unit')
