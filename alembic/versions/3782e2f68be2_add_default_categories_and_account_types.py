"""Add default categories and account types

Revision ID: 3782e2f68be2
Revises: 5cec0924b80e
Create Date: 2026-02-16 13:45:27.900048

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3782e2f68be2'
down_revision: Union[str, Sequence[str], None] = '5cec0924b80e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add default categories and account types."""
    # Insert default expense categories
    op.execute("""
        INSERT INTO categories (name, type, is_default) VALUES
        ('Food', 'EXPENSE', 1),
        ('Travel', 'EXPENSE', 1),
        ('Groceries', 'EXPENSE', 1),
        ('Shopping', 'EXPENSE', 1),
        ('Other', 'EXPENSE', 1)
    """)
    
    # Insert default income categories
    op.execute("""
        INSERT INTO categories (name, type, is_default) VALUES
        ('Salary', 'INCOME', 1),
        ('Cash', 'INCOME', 1),
        ('Other Income', 'INCOME', 1)
    """)
    
    # Insert default account types
    op.execute("""
        INSERT INTO account_types (name, is_default) VALUES
        ('Cash', 1),
        ('Card', 1),
        ('UPI', 1)
    """)


def downgrade() -> None:
    """Remove default categories and account types."""
    # Remove default account types
    op.execute("DELETE FROM account_types WHERE is_default = 1")
    
    # Remove default categories
    op.execute("DELETE FROM categories WHERE is_default = 1")
