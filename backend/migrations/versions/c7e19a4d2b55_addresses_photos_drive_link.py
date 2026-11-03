"""address parts, photos, Drive folder link, fee lines, leads sent to estimating

Revision ID: c7e19a4d2b55
Revises: b41d7e2c9a10
Create Date: 2026-11-03 15:40:00
"""
from alembic import op
import sqlalchemy as sa


revision = 'c7e19a4d2b55'
down_revision = 'b41d7e2c9a10'
branch_labels = None
depends_on = None

PARTS = {"street": 200, "city": 100, "state": 40, "zip": 10}
TABLES = {"jobs": "site", "leads": "site", "clients": "billing"}


def upgrade() -> None:
    # Permit and city fees: their own kind of cost line. Postgres can add an enum
    # value but not remove one, so downgrade leaves it (harmless if unused).
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TYPE costcategory ADD VALUE IF NOT EXISTS 'fee'")
        op.execute("ALTER TYPE tasktype ADD VALUE IF NOT EXISTS 'building'")
    op.add_column('job_tasks', sa.Column('crew_size', sa.Integer(), nullable=True))
    op.add_column('leads', sa.Column('sent_at', sa.DateTime(), nullable=True))
    op.add_column('leads', sa.Column('sent_by_id', sa.String(length=36), nullable=True))
    op.create_foreign_key('fk_leads_sent_by', 'leads', 'users', ['sent_by_id'], ['id'])
    # Existing addresses stay as one line; the forms split them the first time they're edited.
    for table, prefix in TABLES.items():
        for part, size in PARTS.items():
            op.add_column(table, sa.Column(f"{prefix}_{part}", sa.String(length=size), server_default="", nullable=False))
    op.add_column('companies', sa.Column('drive_folder_url', sa.String(length=500), server_default='', nullable=False))
    op.create_table('photos',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('company_id', sa.String(length=36), nullable=False),
        sa.Column('kind', sa.String(length=20), nullable=False),
        sa.Column('subject_id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('caption', sa.String(length=500), nullable=False),
        sa.Column('content_type', sa.String(length=40), nullable=False),
        sa.Column('size', sa.Integer(), nullable=False),
        sa.Column('storage', sa.String(length=10), nullable=False),
        sa.Column('data', sa.LargeBinary(), nullable=True),
        sa.Column('thumb', sa.LargeBinary(), nullable=True),
        sa.Column('drive_file_id', sa.String(length=100), nullable=False),
        sa.Column('created_by_id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('removed_at', sa.DateTime(), nullable=True),
        sa.Column('removed_by_id', sa.String(length=36), nullable=True),
        sa.Column('removed_reason', sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], name='fk_photos_company'),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], name='fk_photos_created_by'),
        sa.ForeignKeyConstraint(['removed_by_id'], ['users.id'], name='fk_photos_removed_by'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_photos_company_id', 'photos', ['company_id'])
    op.create_index('ix_photos_subject_id', 'photos', ['subject_id'])


def downgrade() -> None:
    op.drop_column('job_tasks', 'crew_size')
    op.drop_column('leads', 'sent_by_id')  # takes its foreign key with it
    op.drop_column('leads', 'sent_at')
    op.drop_index('ix_photos_subject_id', table_name='photos')
    op.drop_index('ix_photos_company_id', table_name='photos')
    op.drop_table('photos')
    op.drop_column('companies', 'drive_folder_url')
    for table, prefix in TABLES.items():
        for part in PARTS:
            op.drop_column(table, f"{prefix}_{part}")
