"""built-up task prices: template parts and all-in; item coverage and starter prices; personal settings; suggestion box

Revision ID: f4c2a9b7e3d1
Revises: d3a8f5c1e9b2
Create Date: 2026-11-05 12:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = "f4c2a9b7e3d1"
down_revision = "d3a8f5c1e9b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # What a library task brings onto an estimate, and how it's priced.
    op.add_column('task_templates', sa.Column('all_in', sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column('task_templates', sa.Column('parts', sa.Text(), server_default='[]', nullable=False))
    # Coverage on coatings, and a flag on ballpark starter prices.
    op.add_column('stock_items', sa.Column('coverage_sf', sa.Float(), nullable=True))
    op.add_column('stock_items', sa.Column('starter_price', sa.Boolean(), server_default=sa.false(), nullable=False))
    # Each person's own settings.
    op.add_column('users', sa.Column('phone', sa.String(length=40), server_default='', nullable=False))
    op.add_column('users', sa.Column('prefs', sa.Text(), server_default='{}', nullable=False))
    # The suggestion box.
    op.create_table('feedback',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('company_id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('kind', sa.String(length=10), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('page', sa.String(length=100), nullable=False),
        sa.Column('device', sa.String(length=200), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('emailed_at', sa.DateTime(), nullable=True),
        sa.Column('email_error', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=10), nullable=False),
        sa.Column('reply', sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], name='fk_feedback_company'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_feedback_user'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_feedback_company_id', 'feedback', ['company_id'])


def downgrade() -> None:
    op.drop_index('ix_feedback_company_id', table_name='feedback')
    op.drop_table('feedback')
    op.drop_column('users', 'prefs')
    op.drop_column('users', 'phone')
    op.drop_column('stock_items', 'starter_price')
    op.drop_column('stock_items', 'coverage_sf')
    op.drop_column('task_templates', 'parts')
    op.drop_column('task_templates', 'all_in')
