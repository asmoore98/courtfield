"""jobs to the field: crews, crew and start date, on site, site walk, reports, task progress, material requests and checks

Revision ID: d3a8f5c1e9b2
Revises: c7e19a4d2b55
Create Date: 2026-11-05 09:30:00
"""
from alembic import op
import sqlalchemy as sa


revision = 'd3a8f5c1e9b2'
down_revision = 'c7e19a4d2b55'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing jobs have no crew lead yet; the GM sends them out from the Jobs tab.
    op.add_column('jobs', sa.Column('crew_lead_id', sa.String(length=36), nullable=True))
    op.add_column('jobs', sa.Column('start_date', sa.Date(), nullable=True))
    op.add_column('jobs', sa.Column('started_at', sa.DateTime(), nullable=True))
    op.add_column('jobs', sa.Column('site_walk_at', sa.DateTime(), nullable=True))
    op.add_column('jobs', sa.Column('scope_text', sa.Text(), server_default='', nullable=False))
    # Where each task stands, as the crew lead marks it.
    op.add_column('job_tasks', sa.Column('progress', sa.String(length=10), server_default='', nullable=False))
    op.add_column('job_tasks', sa.Column('progress_pct', sa.Integer(), nullable=True))
    op.add_column('job_tasks', sa.Column('progress_note', sa.Text(), server_default='', nullable=False))
    op.add_column('job_tasks', sa.Column('progress_at', sa.DateTime(), nullable=True))
    op.add_column('job_tasks', sa.Column('progress_by_id', sa.String(length=36), nullable=True))
    op.create_foreign_key('fk_job_tasks_progress_by', 'job_tasks', 'users', ['progress_by_id'], ['id'])
    op.create_foreign_key('fk_jobs_crew_lead', 'jobs', 'users', ['crew_lead_id'], ['id'])
    op.create_index('ix_jobs_crew_lead_id', 'jobs', ['crew_lead_id'])
    op.create_table('job_crew',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('company_id', sa.String(length=36), nullable=False),
        sa.Column('job_id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], name='fk_job_crew_company'),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], name='fk_job_crew_job', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_job_crew_user'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('job_id', 'user_id', name='uq_job_crew'),
    )
    op.create_index('ix_job_crew_company_id', 'job_crew', ['company_id'])
    op.create_index('ix_job_crew_job_id', 'job_crew', ['job_id'])
    op.create_table('job_reports',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('company_id', sa.String(length=36), nullable=False),
        sa.Column('job_id', sa.String(length=36), nullable=False),
        sa.Column('kind', sa.String(length=20), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('created_by_id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('resolved_by_id', sa.String(length=36), nullable=True),
        sa.Column('resolution', sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], name='fk_job_reports_company'),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], name='fk_job_reports_job'),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], name='fk_job_reports_created_by'),
        sa.ForeignKeyConstraint(['resolved_by_id'], ['users.id'], name='fk_job_reports_resolved_by'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_job_reports_company_id', 'job_reports', ['company_id'])
    op.create_index('ix_job_reports_job_id', 'job_reports', ['job_id'])
    op.create_table('material_requests',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('company_id', sa.String(length=36), nullable=False),
        sa.Column('job_id', sa.String(length=36), nullable=False),
        sa.Column('item_id', sa.String(length=36), nullable=True),
        sa.Column('description', sa.String(length=200), nullable=False),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('unit', sa.String(length=20), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('requested_by_id', sa.String(length=36), nullable=False),
        sa.Column('signed_name', sa.String(length=200), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('status', sa.String(length=10), nullable=False),
        sa.Column('handled_by_id', sa.String(length=36), nullable=True),
        sa.Column('handled_at', sa.DateTime(), nullable=True),
        sa.Column('handled_note', sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], name='fk_material_requests_company'),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], name='fk_material_requests_job'),
        sa.ForeignKeyConstraint(['item_id'], ['stock_items.id'], name='fk_material_requests_item', ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['requested_by_id'], ['users.id'], name='fk_material_requests_by'),
        sa.ForeignKeyConstraint(['handled_by_id'], ['users.id'], name='fk_material_requests_handled_by'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_material_requests_company_id', 'material_requests', ['company_id'])
    op.create_index('ix_material_requests_job_id', 'material_requests', ['job_id'])
    # The shop checking the truck is loaded, and the crew lead checking it's all on site.
    op.create_table('material_checks',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('company_id', sa.String(length=36), nullable=False),
        sa.Column('job_id', sa.String(length=36), nullable=False),
        sa.Column('kind', sa.String(length=10), nullable=False),
        sa.Column('all_here', sa.Boolean(), nullable=False),
        sa.Column('items', sa.Text(), nullable=False),
        sa.Column('note', sa.Text(), nullable=False),
        sa.Column('checked_by_id', sa.String(length=36), nullable=False),
        sa.Column('checked_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], name='fk_material_checks_company'),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], name='fk_material_checks_job'),
        sa.ForeignKeyConstraint(['checked_by_id'], ['users.id'], name='fk_material_checks_by'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_material_checks_company_id', 'material_checks', ['company_id'])
    op.create_index('ix_material_checks_job_id', 'material_checks', ['job_id'])
    # Each crew lead's usual crew, set up on the Team tab.
    op.create_table('crews',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('company_id', sa.String(length=36), nullable=False),
        sa.Column('lead_id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], name='fk_crews_company'),
        sa.ForeignKeyConstraint(['lead_id'], ['users.id'], name='fk_crews_lead'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_id', 'lead_id', name='uq_crew_lead'),
    )
    op.create_index('ix_crews_company_id', 'crews', ['company_id'])
    op.create_table('crew_members',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('company_id', sa.String(length=36), nullable=False),
        sa.Column('crew_id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], name='fk_crew_members_company'),
        sa.ForeignKeyConstraint(['crew_id'], ['crews.id'], name='fk_crew_members_crew', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_crew_members_user'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_id', 'user_id', name='uq_crew_member'),
    )
    op.create_index('ix_crew_members_company_id', 'crew_members', ['company_id'])
    op.create_index('ix_crew_members_crew_id', 'crew_members', ['crew_id'])


def downgrade() -> None:
    op.drop_index('ix_crew_members_crew_id', table_name='crew_members')
    op.drop_index('ix_crew_members_company_id', table_name='crew_members')
    op.drop_table('crew_members')
    op.drop_index('ix_crews_company_id', table_name='crews')
    op.drop_table('crews')
    op.drop_index('ix_material_checks_job_id', table_name='material_checks')
    op.drop_index('ix_material_checks_company_id', table_name='material_checks')
    op.drop_table('material_checks')
    op.drop_index('ix_material_requests_job_id', table_name='material_requests')
    op.drop_index('ix_material_requests_company_id', table_name='material_requests')
    op.drop_table('material_requests')
    for col in ('progress_by_id', 'progress_at', 'progress_note', 'progress_pct', 'progress'):
        op.drop_column('job_tasks', col)
    op.drop_column('jobs', 'scope_text')
    op.drop_column('jobs', 'site_walk_at')
    op.drop_index('ix_job_reports_job_id', table_name='job_reports')
    op.drop_index('ix_job_reports_company_id', table_name='job_reports')
    op.drop_table('job_reports')
    op.drop_index('ix_job_crew_job_id', table_name='job_crew')
    op.drop_index('ix_job_crew_company_id', table_name='job_crew')
    op.drop_table('job_crew')
    op.drop_index('ix_jobs_crew_lead_id', table_name='jobs')
    op.drop_column('jobs', 'started_at')
    op.drop_column('jobs', 'start_date')
    op.drop_column('jobs', 'crew_lead_id')  # takes its foreign key with it
