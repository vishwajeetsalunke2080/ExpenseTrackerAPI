# Quick Start Guide

Get the Expense Tracking API up and running in 5 minutes!

## Prerequisites

- Python 3.12+
- Redis (optional, for caching)
- Groq API key (for natural language analytics)

## Installation Steps

### 1. Install Dependencies

```bash
cd FastAPI
pip install -r requirements.txt
```

### 2. Configure Environment

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env` and add your Groq API key:

```env
GROQ_API_KEY=your_actual_groq_api_key_here
```

Get your free Groq API key from: https://console.groq.com

### 3. Initialize Database

```bash
alembic upgrade head
```

### 4. Start Redis (Optional)

If you have Redis installed:

```bash
redis-server
```

If not, the app will work without caching.

### 5. Run the Application

```bash
uvicorn main:app --reload
```

The API will be available at: http://localhost:8000

## Quick Test

### View API Documentation

Open your browser: http://localhost:8000/docs

### Create Your First Expense

```bash
curl -X POST "http://localhost:8000/expenses" \
  -H "Content-Type: application/json" \
  -d '{
    "date": "2026-02-17",
    "amount": 50.00,
    "category": "Food",
    "account": "Card",
    "notes": "Lunch"
  }'
```

### Create a Budget

```bash
curl -X POST "http://localhost:8000/budgets" \
  -H "Content-Type: application/json" \
  -d '{
    "category": "Food",
    "amount_limit": 500.00
  }'
```

### Try Natural Language Query

```bash
curl -X POST "http://localhost:8000/analytics/query?query=What%20are%20my%20total%20expenses%20this%20month"
```

## Database Options

### SQLite (Default - Development)

Already configured! No additional setup needed.

```env
DATABASE_URL=sqlite+aiosqlite:///./expense_tracker.db
```

### PostgreSQL (Production)

See [POSTGRESQL_SETUP.md](POSTGRESQL_SETUP.md) for detailed instructions.

Quick setup:

```bash
# Install driver
pip install asyncpg psycopg2-binary

# Update .env
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/expense_tracker

# Run migrations
alembic upgrade head
```

## Common Commands

### Development

```bash
# Start server with auto-reload
uvicorn main:app --reload

# Run tests
pytest

# Run tests with coverage
pytest --cov=app

# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head
```

### Production

```bash
# Start with multiple workers
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4

# With environment variables
DATABASE_URL=postgresql://... uvicorn main:app --workers 4
```

## Troubleshooting

### Port Already in Use

```bash
# Change port
uvicorn main:app --port 8001
```

### Redis Connection Error

The app will work without Redis, but caching will be disabled. To fix:

```bash
# Start Redis
redis-server

# Or update REDIS_URL in .env
REDIS_URL=redis://your-redis-host:6379/0
```

### Database Migration Error

```bash
# Reset database (WARNING: deletes all data)
rm expense_tracker.db
alembic upgrade head
```

### Groq API Error

Make sure your API key is valid:

```bash
# Test your key
curl https://api.groq.com/openai/v1/models \
  -H "Authorization: Bearer YOUR_API_KEY"
```

## Next Steps

1. **Read the full documentation**: [README.md](README.md)
2. **Explore API endpoints**: http://localhost:8000/docs
3. **Set up PostgreSQL**: [POSTGRESQL_SETUP.md](POSTGRESQL_SETUP.md)
4. **Deploy to production**: [DEPLOYMENT.md](DEPLOYMENT.md)
5. **Review API usage examples**: [API_USAGE_GUIDE.md](API_USAGE_GUIDE.md)

## Need Help?

- Check the [README.md](README.md) for detailed documentation
- Review [API_USAGE_GUIDE.md](API_USAGE_GUIDE.md) for examples
- Open an issue on the repository

## Key Features to Try

1. **Expense Tracking**: Create, update, and filter expenses
2. **Budget Management**: Set monthly budgets and track usage
3. **Balance Carryforward**: Automatically save monthly surplus
4. **Natural Language Analytics**: Ask questions about your finances
5. **Income Tracking**: Record and categorize income

Enjoy using the Expense Tracking API! 🚀
