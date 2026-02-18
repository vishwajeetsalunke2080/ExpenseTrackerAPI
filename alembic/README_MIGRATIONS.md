# Database Migrations

This directory contains Alembic database migrations for the Expense Tracking API.

## Migration Files

### 5cec0924b80e - Initial migration with all tables
Creates all database tables:
- `expenses` - Expense transaction records
- `income` - Income transaction records
- `categories` - Category classifications for expenses and income
- `account_types` - Payment method types
- `budgets` - Budget limits for spending control

All tables include appropriate indexes for query optimization.

### 3782e2f68be2 - Add default categories and account types
Inserts default data:

**Default Expense Categories:**
- Food
- Travel
- Groceries
- Shopping
- Other

**Default Income Categories:**
- Salary
- Cash
- Other Income

**Default Account Types:**
- Cash
- Card
- UPI

## Running Migrations

### Apply all pending migrations
```cmd
.\Scripts\alembic.exe upgrade head
```

### Rollback one migration
```cmd
.\Scripts\alembic.exe downgrade -1
```

### View migration history
```cmd
.\Scripts\alembic.exe history
```

### View current migration version
```cmd
.\Scripts\alembic.exe current
```

## Creating New Migrations

### Auto-generate migration from model changes
```cmd
.\Scripts\alembic.exe revision --autogenerate -m "Description of changes"
```

### Create empty migration for data changes
```cmd
.\Scripts\alembic.exe revision -m "Description of changes"
```

## Notes

- The database URL is configured in `app/config.py` via environment variables
- Alembic automatically converts async SQLAlchemy URLs to sync for migrations
- All default data is marked with `is_default = 1` for easy identification
- Downgrade operations properly clean up default data
