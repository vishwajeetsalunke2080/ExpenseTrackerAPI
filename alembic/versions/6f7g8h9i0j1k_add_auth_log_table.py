"""add auth_log table

Revision ID: 6f7g8h9i0j1k
Revises: 4a5b6c7d8e9f
Create Date: 2026-02-17

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6f7g8h9i0j1k'
down_revision = '4a5b6c7d8e9f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create auth_logs table for security auditing."""
    op.create_table(
        'auth_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('success', sa.Boolean(), nullable=False),
        sa.Column('ip_address', sa.String(length=45), nullable=False),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index(op.f('ix_auth_logs_user_id'), 'auth_logs', ['user_id'], unique=False)
    op.create_index(op.f('ix_auth_logs_email'), 'auth_logs', ['email'], unique=False)
    op.create_index(op.f('ix_auth_logs_action'), 'auth_logs', ['action'], unique=False)
    op.create_index(op.f('ix_auth_logs_success'), 'auth_logs', ['success'], unique=False)
    op.create_index(op.f('ix_auth_logs_created_at'), 'auth_logs', ['created_at'], unique=False)
    
    # Create composite indexes for common query patterns
    op.create_index('ix_auth_logs_user_action', 'auth_logs', ['user_id', 'action'], unique=False)
    op.create_index('ix_auth_logs_email_action', 'auth_logs', ['email', 'action'], unique=False)
    op.create_index('ix_auth_logs_success_created', 'auth_logs', ['success', 'created_at'], unique=False)


def downgrade() -> None:
    """Drop auth_logs table."""
    # Drop composite indexes
    op.drop_index('ix_auth_logs_success_created', table_name='auth_logs')
    op.drop_index('ix_auth_logs_email_action', table_name='auth_logs')
    op.drop_index('ix_auth_logs_user_action', table_name='auth_logs')
    
    # Drop single column indexes
    op.drop_index(op.f('ix_auth_logs_created_at'), table_name='auth_logs')
    op.drop_index(op.f('ix_auth_logs_success'), table_name='auth_logs')
    op.drop_index(op.f('ix_auth_logs_action'), table_name='auth_logs')
    op.drop_index(op.f('ix_auth_logs_email'), table_name='auth_logs')
    op.drop_index(op.f('ix_auth_logs_user_id'), table_name='auth_logs')
    
    # Drop table
    op.drop_table('auth_logs')
