# PostgreSQL Setup Guide

This guide will help you switch from SQLite to PostgreSQL for production use.

## Why PostgreSQL?

- Better performance for concurrent users
- ACID compliance
- Advanced features (JSON support, full-text search, etc.)
- Better for production environments
- Supports multiple connections

## Installation

### Windows

1. Download PostgreSQL from https://www.postgresql.org/download/windows/
2. Run the installer
3. Remember the password you set for the `postgres` user
4. Default port is `5432`

### Linux (Ubuntu/Debian)

```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
```

### macOS

```bash
brew install postgresql
brew services start postgresql
```

## Database Setup

### 1. Create Database

Connect to PostgreSQL:

```bash
# Windows
psql -U postgres

# Linux/Mac
sudo -u postgres psql
```

Create the database:

```sql
CREATE DATABASE expense_tracker;
CREATE USER expense_user WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE expense_tracker TO expense_user;
\q
```

### 2. Install Python PostgreSQL Driver

```bash
# Activate your virtual environment first
FastAPI\Scripts\activate.bat  # Windows
source FastAPI/bin/activate   # Linux/Mac

# Install the driver
pip install asyncpg psycopg2-binary
```

### 3. Update .env File

Open `FastAPI/.env` and update the `DATABASE_URL`:

```env
# Comment out SQLite
# DATABASE_URL=sqlite+aiosqlite:///./expense_tracker.db

# Add PostgreSQL connection
DATABASE_URL=postgresql+asyncpg://expense_user:your_secure_password@localhost:5432/expense_tracker
```

**Connection String Format:**
```
postgresql+asyncpg://username:password@host:port/database_name
```

**Examples:**

Local PostgreSQL:
```
DATABASE_URL=postgresql+asyncpg://expense_user:mypassword@localhost:5432/expense_tracker
```

Remote PostgreSQL:
```
DATABASE_URL=postgresql+asyncpg://user:pass@db.example.com:5432/expense_tracker
```

Docker PostgreSQL:
```
DATABASE_URL=postgresql+asyncpg://postgres:password@postgres:5432/expense_tracker
```

Cloud PostgreSQL (e.g., AWS RDS):
```
DATABASE_URL=postgresql+asyncpg://admin:pass@mydb.abc123.us-east-1.rds.amazonaws.com:5432/expense_tracker
```

### 4. Run Migrations

The application will automatically create tables using Alembic migrations:

```bash
# Make sure you're in the FastAPI directory
cd FastAPI

# Run migrations
alembic upgrade head
```

### 5. Verify Connection

Start your application:

```bash
uvicorn main:app --reload
```

Check the logs - you should see successful database connections.

## Configuration Details

### Connection Pool Settings

The application is already configured with optimal connection pool settings in `app/database.py`:

```python
engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_size=5,          # Number of connections to maintain
    max_overflow=10,      # Additional connections when needed
    pool_pre_ping=True,   # Verify connections before using
    pool_recycle=3600     # Recycle connections after 1 hour
)
```

### For High-Traffic Applications

If you expect high traffic, you can adjust these settings by modifying `app/database.py`:

```python
engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_size=20,         # Increase for more concurrent users
    max_overflow=40,      # Allow more overflow connections
    pool_pre_ping=True,
    pool_recycle=3600
)
```

## Migrating Data from SQLite to PostgreSQL

If you have existing data in SQLite that you want to migrate:

### Option 1: Using pgloader (Recommended)

```bash
# Install pgloader
sudo apt install pgloader  # Linux
brew install pgloader      # macOS

# Create migration script
cat > migrate.load << EOF
LOAD DATABASE
    FROM sqlite://expense_tracker.db
    INTO postgresql://expense_user:password@localhost/expense_tracker
    WITH include drop, create tables, create indexes, reset sequences
    SET work_mem to '16MB', maintenance_work_mem to '512 MB';
EOF

# Run migration
pgloader migrate.load
```

### Option 2: Manual Export/Import

```bash
# Export from SQLite
sqlite3 expense_tracker.db .dump > dump.sql

# Import to PostgreSQL (requires manual SQL adjustments)
psql -U expense_user -d expense_tracker -f dump.sql
```

### Option 3: Using Python Script

Create a migration script to copy data:

```python
import sqlite3
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

async def migrate_data():
    # Connect to SQLite
    sqlite_conn = sqlite3.connect('expense_tracker.db')
    sqlite_cursor = sqlite_conn.cursor()
    
    # Connect to PostgreSQL
    pg_engine = create_async_engine(
        'postgresql+asyncpg://expense_user:password@localhost/expense_tracker'
    )
    
    # Migrate each table
    # ... (implement migration logic)
    
    await pg_engine.dispose()
    sqlite_conn.close()

asyncio.run(migrate_data())
```

## Troubleshooting

### Connection Refused

```
Error: connection refused
```

**Solution:**
- Ensure PostgreSQL is running: `sudo systemctl status postgresql` (Linux)
- Check if PostgreSQL is listening on the correct port: `netstat -an | grep 5432`
- Verify firewall settings

### Authentication Failed

```
Error: password authentication failed
```

**Solution:**
- Verify username and password in DATABASE_URL
- Check PostgreSQL authentication settings in `pg_hba.conf`
- Ensure the user has proper permissions

### Database Does Not Exist

```
Error: database "expense_tracker" does not exist
```

**Solution:**
- Create the database: `CREATE DATABASE expense_tracker;`
- Verify database name in DATABASE_URL

### SSL Connection Error

```
Error: SSL connection required
```

**Solution:**
Add SSL parameters to DATABASE_URL:
```
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db?ssl=require
```

### Too Many Connections

```
Error: too many connections
```

**Solution:**
- Reduce `pool_size` and `max_overflow` in `database.py`
- Increase PostgreSQL's `max_connections` setting
- Check for connection leaks in your code

## Performance Optimization

### 1. Create Indexes

The application already creates necessary indexes through migrations, but you can add custom indexes:

```sql
-- Index for date range queries
CREATE INDEX idx_expenses_date_range ON expenses(date DESC);

-- Index for category filtering
CREATE INDEX idx_expenses_category_date ON expenses(category, date);

-- Index for analytics queries
CREATE INDEX idx_income_date_category ON income(date, category);
```

### 2. Enable Query Logging (Development Only)

In `app/database.py`, set `echo=True`:

```python
engine = create_async_engine(
    settings.database_url,
    echo=True,  # Log all SQL queries
    ...
)
```

### 3. Vacuum and Analyze

Run periodically to maintain performance:

```sql
VACUUM ANALYZE;
```

### 4. Monitor Performance

```sql
-- Check slow queries
SELECT * FROM pg_stat_statements 
ORDER BY mean_exec_time DESC 
LIMIT 10;

-- Check table sizes
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

## Backup and Restore

### Backup

```bash
# Full database backup
pg_dump -U expense_user expense_tracker > backup.sql

# Compressed backup
pg_dump -U expense_user expense_tracker | gzip > backup.sql.gz

# Custom format (faster restore)
pg_dump -U expense_user -Fc expense_tracker > backup.dump
```

### Restore

```bash
# From SQL file
psql -U expense_user expense_tracker < backup.sql

# From compressed file
gunzip -c backup.sql.gz | psql -U expense_user expense_tracker

# From custom format
pg_restore -U expense_user -d expense_tracker backup.dump
```

### Automated Backups

Create a cron job (Linux/Mac):

```bash
# Edit crontab
crontab -e

# Add daily backup at 2 AM
0 2 * * * pg_dump -U expense_user expense_tracker | gzip > /backups/expense_$(date +\%Y\%m\%d).sql.gz
```

## Docker Setup

If you prefer using Docker for PostgreSQL:

```yaml
# docker-compose.yml
version: '3.8'

services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: expense_tracker
      POSTGRES_USER: expense_user
      POSTGRES_PASSWORD: your_secure_password
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U expense_user"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
```

Start PostgreSQL:
```bash
docker-compose up -d postgres
```

Update DATABASE_URL:
```env
DATABASE_URL=postgresql+asyncpg://expense_user:your_secure_password@localhost:5432/expense_tracker
```

## Production Considerations

### 1. Use Connection Pooling

Already configured in the application with SQLAlchemy's connection pool.

### 2. Enable SSL

For production, always use SSL:

```env
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db?ssl=require
```

### 3. Use Read Replicas

For high-traffic applications, consider read replicas:

```python
# In database.py
read_engine = create_async_engine(read_replica_url)
write_engine = create_async_engine(primary_url)
```

### 4. Monitor Connections

```sql
-- Check active connections
SELECT count(*) FROM pg_stat_activity;

-- Check connection details
SELECT * FROM pg_stat_activity WHERE datname = 'expense_tracker';
```

### 5. Set Up Regular Maintenance

```sql
-- Weekly vacuum
VACUUM ANALYZE;

-- Reindex if needed
REINDEX DATABASE expense_tracker;
```

## Support

For PostgreSQL-specific issues:
- PostgreSQL Documentation: https://www.postgresql.org/docs/
- PostgreSQL Community: https://www.postgresql.org/community/

For application issues:
- Check application logs
- Verify DATABASE_URL format
- Ensure migrations are up to date
