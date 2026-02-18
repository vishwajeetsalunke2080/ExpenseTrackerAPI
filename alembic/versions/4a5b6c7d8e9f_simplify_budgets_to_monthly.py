"""simplify budgets to monthly recurring

Revision ID: 4a5b6c7d8e9f
Revises: 3782e2f68be2
Create Date: 2026-02-17

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4a5b6c7d8e9f'
down_revision = '3782e2f68be2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Use batch mode for SQLite
    with op.batch_alter_table('budgets', schema=None) as batch_op:
        # Drop old columns (indexes will be dropped automatically)
        batch_op.drop_column('start_date')
        batch_op.drop_column('end_date')
        
        # Make category unique (one budget per category)
        batch_op.create_unique_constraint('uq_budgets_category', ['category'])


def downgrade() -> None:
    # Use batch mode for SQLite
    with op.batch_alter_table('budgets', schema=None) as batch_op:
        # Drop unique constraint
        batch_op.drop_constraint('uq_budgets_category', type_='unique')
        
        # Add back columns
        batch_op.add_column(sa.Column('start_date', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('end_date', sa.Date(), nullable=True))
    
    # Populate with current month dates
    op.execute("""
        UPDATE budgets 
        SET start_date = date('now', 'start of month'),
            end_date = date('now', 'start of month', '+1 month', '-1 day')
    """)
    
    # Make columns non-nullable and recreate indexes
    with op.batch_alter_table('budgets', schema=None) as batch_op:
        batch_op.alter_column('start_date', nullable=False)
        batch_op.alter_column('end_date', nullable=False)
        
        # Recreate indexes
        batch_op.create_index('ix_budgets_start_date', ['start_date'])
        batch_op.create_index('ix_budgets_end_date', ['end_date'])
        batch_op.create_index('ix_budgets_category_dates', ['category', 'start_date', 'end_date'])
