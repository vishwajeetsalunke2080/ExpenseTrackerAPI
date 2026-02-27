"""add user isolation to financial entities

Revision ID: 7k8l9m0n1o2p
Revises: 8f29941f06d6
Create Date: 2026-02-28

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7k8l9m0n1o2p'
down_revision = '8f29941f06d6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add user_id columns to all financial entities and enforce user isolation."""
    
    # Step 1: Add user_id columns as nullable initially
    with op.batch_alter_table('expenses', schema=None) as batch_op:
        batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=True))
    
    with op.batch_alter_table('income', schema=None) as batch_op:
        batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=True))
    
    with op.batch_alter_table('budgets', schema=None) as batch_op:
        batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=True))
    
    with op.batch_alter_table('categories', schema=None) as batch_op:
        batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=True))
    
    with op.batch_alter_table('account_types', schema=None) as batch_op:
        batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=True))
    
    # Step 2: Handle existing data
    # Check if any users exist and assign existing data to the first user
    # If no users exist, this is a fresh install and we can skip data migration
    conn = op.get_bind()
    result = conn.execute(sa.text("SELECT id FROM users ORDER BY id LIMIT 1"))
    first_user = result.fetchone()
    
    if first_user:
        # Assign all existing data to the first user
        default_user_id = first_user[0]
        conn.execute(sa.text(f"UPDATE expenses SET user_id = {default_user_id} WHERE user_id IS NULL"))
        conn.execute(sa.text(f"UPDATE income SET user_id = {default_user_id} WHERE user_id IS NULL"))
        conn.execute(sa.text(f"UPDATE budgets SET user_id = {default_user_id} WHERE user_id IS NULL"))
        conn.execute(sa.text(f"UPDATE categories SET user_id = {default_user_id} WHERE user_id IS NULL"))
        conn.execute(sa.text(f"UPDATE account_types SET user_id = {default_user_id} WHERE user_id IS NULL"))
    
    # Step 3: Make user_id NOT NULL, add foreign keys, and create indexes
    # Use batch mode for SQLite compatibility
    with op.batch_alter_table('expenses', schema=None) as batch_op:
        batch_op.alter_column('user_id', nullable=False)
        batch_op.create_foreign_key('fk_expenses_user', 'users', ['user_id'], ['id'], ondelete='CASCADE')
        batch_op.create_index(batch_op.f('ix_expenses_user_id'), ['user_id'], unique=False)
        batch_op.create_index('ix_expenses_user_date', ['user_id', 'date'], unique=False)
        batch_op.create_index('ix_expenses_user_category', ['user_id', 'category'], unique=False)
        batch_op.create_index('ix_expenses_user_account', ['user_id', 'account'], unique=False)
        batch_op.create_index('ix_expenses_user_date_category', ['user_id', 'date', 'category'], unique=False)
    
    with op.batch_alter_table('income', schema=None) as batch_op:
        batch_op.alter_column('user_id', nullable=False)
        batch_op.create_foreign_key('fk_income_user', 'users', ['user_id'], ['id'], ondelete='CASCADE')
        batch_op.create_index(batch_op.f('ix_income_user_id'), ['user_id'], unique=False)
        batch_op.create_index('ix_income_user_date', ['user_id', 'date'], unique=False)
        batch_op.create_index('ix_income_user_category', ['user_id', 'category'], unique=False)
        batch_op.create_index('ix_income_user_date_category', ['user_id', 'date', 'category'], unique=False)
    
    with op.batch_alter_table('budgets', schema=None) as batch_op:
        batch_op.alter_column('user_id', nullable=False)
        batch_op.create_foreign_key('fk_budgets_user', 'users', ['user_id'], ['id'], ondelete='CASCADE')
        batch_op.create_index(batch_op.f('ix_budgets_user_id'), ['user_id'], unique=False)
        batch_op.create_index('ix_budgets_user_category', ['user_id', 'category'], unique=False)
        # Create new composite unique constraint
        batch_op.create_unique_constraint('uq_budgets_user_category', ['user_id', 'category'])
    
    with op.batch_alter_table('categories', schema=None) as batch_op:
        batch_op.alter_column('user_id', nullable=False)
        batch_op.create_foreign_key('fk_categories_user', 'users', ['user_id'], ['id'], ondelete='CASCADE')
        batch_op.create_index(batch_op.f('ix_categories_user_id'), ['user_id'], unique=False)
        batch_op.create_index('ix_categories_user_name', ['user_id', 'name'], unique=False)
        batch_op.create_index('ix_categories_user_type', ['user_id', 'type'], unique=False)
        # Drop old unique index and create new composite unique constraint
        batch_op.drop_index('ix_categories_name')
        batch_op.create_unique_constraint('uq_categories_user_name', ['user_id', 'name'])
    
    with op.batch_alter_table('account_types', schema=None) as batch_op:
        batch_op.alter_column('user_id', nullable=False)
        batch_op.create_foreign_key('fk_account_types_user', 'users', ['user_id'], ['id'], ondelete='CASCADE')
        batch_op.create_index(batch_op.f('ix_account_types_user_id'), ['user_id'], unique=False)
        batch_op.create_index('ix_account_types_user_name', ['user_id', 'name'], unique=False)
        # Drop old unique index and create new composite unique constraint
        batch_op.drop_index('ix_account_types_name')
        batch_op.create_unique_constraint('uq_account_types_user_name', ['user_id', 'name'])


def downgrade() -> None:
    """Remove user isolation from financial entities."""
    
    # Use batch mode for SQLite compatibility
    with op.batch_alter_table('account_types', schema=None) as batch_op:
        # Drop composite unique constraint and recreate old unique index
        batch_op.drop_constraint('uq_account_types_user_name', type_='unique')
        batch_op.create_index('ix_account_types_name', ['name'], unique=True)
        # Drop composite indexes
        batch_op.drop_index('ix_account_types_user_name')
        # Drop single-column index
        batch_op.drop_index(batch_op.f('ix_account_types_user_id'))
        # Drop foreign key
        batch_op.drop_constraint('fk_account_types_user', type_='foreignkey')
        # Drop user_id column
        batch_op.drop_column('user_id')
    
    with op.batch_alter_table('categories', schema=None) as batch_op:
        # Drop composite unique constraint and recreate old unique index
        batch_op.drop_constraint('uq_categories_user_name', type_='unique')
        batch_op.create_index('ix_categories_name', ['name'], unique=True)
        # Drop composite indexes
        batch_op.drop_index('ix_categories_user_type')
        batch_op.drop_index('ix_categories_user_name')
        # Drop single-column index
        batch_op.drop_index(batch_op.f('ix_categories_user_id'))
        # Drop foreign key
        batch_op.drop_constraint('fk_categories_user', type_='foreignkey')
        # Drop user_id column
        batch_op.drop_column('user_id')
    
    with op.batch_alter_table('budgets', schema=None) as batch_op:
        # Drop composite unique constraint (don't recreate old one since it didn't exist)
        batch_op.drop_constraint('uq_budgets_user_category', type_='unique')
        # Drop composite indexes
        batch_op.drop_index('ix_budgets_user_category')
        # Drop single-column index
        batch_op.drop_index(batch_op.f('ix_budgets_user_id'))
        # Drop foreign key
        batch_op.drop_constraint('fk_budgets_user', type_='foreignkey')
        # Drop user_id column
        batch_op.drop_column('user_id')
    
    with op.batch_alter_table('income', schema=None) as batch_op:
        # Drop composite indexes
        batch_op.drop_index('ix_income_user_date_category')
        batch_op.drop_index('ix_income_user_category')
        batch_op.drop_index('ix_income_user_date')
        # Drop single-column index
        batch_op.drop_index(batch_op.f('ix_income_user_id'))
        # Drop foreign key
        batch_op.drop_constraint('fk_income_user', type_='foreignkey')
        # Drop user_id column
        batch_op.drop_column('user_id')
    
    with op.batch_alter_table('expenses', schema=None) as batch_op:
        # Drop composite indexes
        batch_op.drop_index('ix_expenses_user_date_category')
        batch_op.drop_index('ix_expenses_user_account')
        batch_op.drop_index('ix_expenses_user_category')
        batch_op.drop_index('ix_expenses_user_date')
        # Drop single-column index
        batch_op.drop_index(batch_op.f('ix_expenses_user_id'))
        # Drop foreign key
        batch_op.drop_constraint('fk_expenses_user', type_='foreignkey')
        # Drop user_id column
        batch_op.drop_column('user_id')
