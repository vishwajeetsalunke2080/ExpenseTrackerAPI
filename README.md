# Expense Tracking API

A production-ready FastAPI application for tracking personal expenses, income, and budgets with natural language analytics powered by AI.

## Features

- **Expense Management**: Track expenses with categories, accounts, and notes
- **Income Tracking**: Record income from various sources
- **Budget Management**: Set monthly budgets per category with automatic usage tracking
- **Balance Carryforward**: Automatically carry forward monthly savings to the next month
- **Natural Language Analytics**: Query your financial data using natural language (powered by Groq AI)
- **RESTful API**: Clean, well-documented API endpoints
- **Database Migrations**: Alembic for database version control
- **Caching**: Redis integration for improved performance

## Tech Stack

- **Framework**: FastAPI 0.115.6
- **Database**: SQLite with SQLAlchemy ORM (async)
- **Cache**: Redis
- **AI/LLM**: Groq (llama-3.3-70b-versatile)
- **Migrations**: Alembic
- **Testing**: Pytest with async support

## Project Structure

```
FastAPI/
├── app/
│   ├── api/              # API route handlers
│   ├── models/           # SQLAlchemy models
│   ├── schemas/          # Pydantic schemas
│   ├── services/         # Business logic layer
│   ├── config.py         # Configuration management
│   ├── database.py       # Database connection
│   └── cache.py          # Redis cache setup
├── alembic/              # Database migrations
├── tests/                # Test suite
│   ├── unit/            # Unit tests
│   └── property/        # Property-based tests
├── main.py              # Application entry point
├── requirements.txt     # Python dependencies
├── .env                 # Environment variables (not in git)
└── README.md           # This file
```

## Installation

### Prerequisites

- Python 3.12+
- Redis server (for caching)

### Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd FastAPI
   ```

2. **Create virtual environment**
   ```bash
   python -m venv .
   ```

3. **Activate virtual environment**
   - Windows CMD: `Scripts\activate.bat`
   - Windows PowerShell: `Scripts\Activate.ps1`
   - Linux/Mac: `source bin/activate`

4. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

5. **Configure environment variables**
   
   Create a `.env` file in the FastAPI directory:
   ```env
   # Database
   DATABASE_URL=sqlite+aiosqlite:///./expense_tracker.db
   
   # Redis Cache
   REDIS_URL=redis://localhost:6379/0
   CACHE_TTL_MINUTES=15
   
   # Groq AI (Get your API key from https://console.groq.com)
   GROQ_API_KEY=your_groq_api_key_here
   GROQ_MODEL=llama-3.3-70b-versatile
   
   # API
   API_TITLE=Expense Tracking API
   API_VERSION=1.0.0
   ```

6. **Run database migrations**
   ```bash
   alembic upgrade head
   ```

7. **Start Redis server**
   ```bash
   redis-server
   ```

## Running the Application

### Development Server

```bash
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`

### Production Server

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

## API Documentation

Once the server is running, visit:

- **Interactive API docs (Swagger UI)**: http://localhost:8000/docs
- **Alternative API docs (ReDoc)**: http://localhost:8000/redoc
- **OpenAPI schema**: http://localhost:8000/openapi.json

## API Endpoints

### Categories
- `GET /categories` - List all categories
- `POST /categories` - Create a new category
- `GET /categories/{id}` - Get category by ID
- `PUT /categories/{id}` - Update category
- `DELETE /categories/{id}` - Delete category

### Account Types
- `GET /accounts` - List all account types
- `POST /accounts` - Create account type
- `GET /accounts/{id}` - Get account type
- `PUT /accounts/{id}` - Update account type
- `DELETE /accounts/{id}` - Delete account type

### Expenses
- `GET /expenses` - List expenses (with filters)
- `POST /expenses` - Create expense
- `GET /expenses/{id}` - Get expense
- `PUT /expenses/{id}` - Update expense
- `DELETE /expenses/{id}` - Delete expense

### Income
- `GET /income` - List income records
- `POST /income` - Create income record
- `GET /income/{id}` - Get income record
- `PUT /income/{id}` - Update income record
- `DELETE /income/{id}` - Delete income record

### Budgets
- `GET /budgets` - List budgets
- `POST /budgets` - Create monthly budget
- `GET /budgets/{id}` - Get budget with usage
- `PUT /budgets/{id}` - Update budget
- `DELETE /budgets/{id}` - Delete budget

### Balance Carryforward
- `POST /balance/carryforward` - Carry forward balance from specific month
- `POST /balance/carryforward/auto` - Auto carry forward from previous month
- `GET /balance/monthly-summary` - Get monthly balance summary

### Analytics (Natural Language)
- `POST /analytics/query` - Query financial data using natural language

## Usage Examples

### Create an Expense
```bash
curl -X POST "http://localhost:8000/expenses" \
  -H "Content-Type: application/json" \
  -d '{
    "date": "2026-02-17",
    "amount": 50.00,
    "category": "Food",
    "account": "Card",
    "notes": "Lunch at restaurant"
  }'
```

### Create a Monthly Budget
```bash
curl -X POST "http://localhost:8000/budgets" \
  -H "Content-Type: application/json" \
  -d '{
    "category": "Food",
    "amount_limit": 500.00
  }'
```

### Natural Language Query
```bash
curl -X POST "http://localhost:8000/analytics/query?query=What%20are%20my%20total%20expenses%20for%20February%202026"
```

### Carryforward Monthly Balance
```bash
curl -X POST "http://localhost:8000/balance/carryforward/auto"
```

## Testing

Run the test suite:

```bash
# All tests
pytest

# With coverage
pytest --cov=app --cov-report=html

# Specific test file
pytest tests/unit/test_expenses.py

# Property-based tests
pytest tests/property/
```

## Database Migrations

### Create a new migration
```bash
alembic revision --autogenerate -m "description of changes"
```

### Apply migrations
```bash
alembic upgrade head
```

### Rollback migration
```bash
alembic downgrade -1
```

## Configuration

All configuration is managed through environment variables in the `.env` file:

- `DATABASE_URL`: Database connection string
- `REDIS_URL`: Redis connection string
- `CACHE_TTL_MINUTES`: Cache time-to-live in minutes
- `GROQ_API_KEY`: Groq AI API key for natural language queries
- `GROQ_MODEL`: Groq model to use
- `API_TITLE`: API title for documentation
- `API_VERSION`: API version

## Security Notes

- Never commit `.env` file to version control
- Use strong API keys in production
- Consider adding authentication/authorization for production use
- Use HTTPS in production
- Regularly update dependencies for security patches

## License

MIT License

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Support

For issues and questions, please open an issue on the repository.
