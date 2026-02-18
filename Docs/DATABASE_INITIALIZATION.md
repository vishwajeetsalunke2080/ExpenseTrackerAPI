# Database Initialization Functions

This document describes the database initialization functions for setting up default categories and account types.

## Overview

The expense tracking API requires default categories and account types to be available for users. These defaults are:

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

## Functions

### `initialize_default_categories(db: AsyncSession)`

Initializes default expense and income categories in the database.

**Features:**
- Creates all default categories if they don't exist
- Idempotent: Can be called multiple times without creating duplicates
- Checks for existing categories by name before inserting
- Marks all default categories with `is_default=True`

**Usage:**
```python
from app.database import AsyncSessionLocal, initialize_default_categories

async with AsyncSessionLocal() as session:
    await initialize_default_categories(session)
```

**Requirements:** 11.6, 11.7

### `initialize_default_account_types(db: AsyncSession)`

Initializes default account types in the database.

**Features:**
- Creates all default account types if they don't exist
- Idempotent: Can be called multiple times without creating duplicates
- Checks for existing account types by name before inserting
- Marks all default account types with `is_default=True`

**Usage:**
```python
from app.database import AsyncSessionLocal, initialize_default_account_types

async with AsyncSessionLocal() as session:
    await initialize_default_account_types(session)
```

**Requirements:** 12.6

## Application Startup Integration

The initialization functions are automatically called during application startup using FastAPI's lifespan context manager in `Test.py`:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database with defaults on startup."""
    from app.database import AsyncSessionLocal, initialize_default_categories, initialize_default_account_types
    
    async with AsyncSessionLocal() as session:
        await initialize_default_categories(session)
        await initialize_default_account_types(session)
    
    yield

app = FastAPI(lifespan=lifespan)
```

This ensures that:
1. Default categories and account types are available immediately when the application starts
2. The initialization is idempotent, so restarting the application won't create duplicates
3. If defaults already exist (e.g., from migrations), they won't be duplicated

## Database Migrations

Note that the same default data is also included in the Alembic migration file:
- `alembic/versions/3782e2f68be2_add_default_categories_and_account_types.py`

The migration ensures defaults exist when setting up a new database, while the initialization functions provide programmatic access for services and can be used for:
- Testing (creating defaults in test databases)
- Manual initialization if needed
- Future service layer operations that need to ensure defaults exist

## Testing

Comprehensive unit tests are available in:
- `tests/test_database_initialization.py` - Tests for the initialization functions
- `tests/test_startup_initialization.py` - Integration tests for startup behavior

Run tests with:
```bash
.\Scripts\pytest.exe tests/test_database_initialization.py -v
```

## Implementation Details

Both functions follow the same pattern:
1. Define the list of default items
2. For each item, check if it already exists in the database
3. If it doesn't exist, create it with `is_default=True`
4. Commit all changes to the database

This approach ensures:
- No duplicate entries
- Existing data is preserved
- Safe to call multiple times
- Efficient (only inserts what's needed)
