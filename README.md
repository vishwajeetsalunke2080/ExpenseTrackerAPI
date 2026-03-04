# Expense Tracking API

A production-ready FastAPI-based REST API for expense tracking with user authentication, OAuth integration, and AI-powered analytics.

## Features

- 🔐 **User Authentication**: JWT-based authentication with RS256 signing
- 📧 **Email Verification**: Email verification for new user registrations
- 🔑 **Password Reset**: Secure password reset flow with time-limited tokens
- 🌐 **OAuth Integration**: Google and GitHub OAuth support
- 💰 **Expense Management**: Full CRUD operations for expenses, income, and budgets
- 📊 **AI-Powered Analytics**: Natural language queries powered by Groq LLM
- 🏷️ **Categories & Account Types**: Customizable categories and payment methods
- 👤 **User Data Isolation**: Complete data isolation between users
- 🔒 **Rate Limiting**: Protection against brute force attacks
- 📝 **Audit Logging**: Comprehensive authentication event logging

## Tech Stack

- **Framework**: FastAPI 0.115+
- **Database**: PostgreSQL with async SQLAlchemy
- **Authentication**: JWT with RS256 (RSA keys)
- **ORM**: SQLAlchemy 2.0+ (async)
- **Migrations**: Alembic
- **Testing**: Pytest with property-based testing (Hypothesis)
- **LLM**: Groq API (Llama 3.3)
- **Email**: SMTP (Gmail)

## Prerequisites

- Python 3.12+
- PostgreSQL 14+ (or SQLite for development)
- SMTP server credentials (for email)
- Groq API key (for analytics)

## Installation

### 1. Clone the repository

```bash
git clone <repository-url>
cd FastAPI
```

### 2. Create virtual environment

```bash
python -m venv .
# On Windows
Scripts\activate.bat
# On Linux/Mac
source bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Copy `.env.example` to `.env` and update with your values:

```bash
cp .env.example .env
```

Required environment variables:
- `DATABASE_URL`: PostgreSQL connection string
- `GROQ_API_KEY`: Groq API key for analytics
- `SMTP_USERNAME` & `SMTP_PASSWORD`: Email service credentials
- OAuth credentials (optional): Google and GitHub client IDs and secrets

### 5. Generate RSA keys for JWT

```bash
python generate_rsa_keys.py
```

This creates `private_key.pem` and `public_key.pem` for JWT signing.

### 6. Run database migrations

```bash
alembic upgrade head
```

### 7. Start the server

```bash
# Development
uvicorn main:app --reload

# Production
uvicorn main:app --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

## API Documentation

Once the server is running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

## Project Structure

```
FastAPI/
├── app/
│   ├── api/              # API route handlers
│   │   ├── auth.py       # Authentication endpoints
│   │   ├── users.py      # User profile endpoints
│   │   ├── expenses.py   # Expense endpoints
│   │   ├── income.py     # Income endpoints
│   │   ├── budgets.py    # Budget endpoints
│   │   ├── categories.py # Category endpoints
│   │   ├── accounts.py   # Account type endpoints
│   │   ├── analytics.py  # Analytics endpoints
│   │   └── oauth.py      # OAuth endpoints
│   ├── models/           # SQLAlchemy models
│   ├── schemas/          # Pydantic schemas
│   ├── services/         # Business logic layer
│   ├── middleware/       # Custom middleware
│   ├── exceptions/       # Custom exceptions
│   ├── config.py         # Configuration management
│   └── database.py       # Database connection
├── alembic/              # Database migrations
├── tests/                # Test suite
├── main.py               # Application entry point
├── requirements.txt      # Python dependencies
└── .env.example          # Environment variables template
```

## Database Migrations

### Create a new migration

```bash
alembic revision --autogenerate -m "Description of changes"
```

### Apply migrations

```bash
alembic upgrade head
```

### Rollback migration

```bash
alembic downgrade -1
```

## Testing

Run the test suite:

```bash
# All tests
pytest

# With coverage
pytest --cov=app --cov-report=html

# Specific test file
pytest tests/unit/test_auth_service.py

# Property-based tests only
pytest tests/property/
```

## Security Features

### Authentication
- JWT tokens with RS256 signing (RSA keys)
- Access tokens: 15-minute expiration
- Refresh tokens: 7-day expiration
- Token revocation support

### Rate Limiting
- Login attempts: 5 attempts per 15 minutes
- Account lockout: 15 minutes after max attempts
- Password reset: 3 attempts per hour

### Data Protection
- Bcrypt password hashing (cost factor 12)
- User data isolation at database level
- 404 responses for unauthorized access (prevents enumeration)
- CORS configuration for frontend integration

## API Endpoints

### Authentication
- `POST /auth/signup` - Register new user
- `POST /auth/signin` - Login
- `POST /auth/signout` - Logout
- `POST /auth/refresh` - Refresh access token
- `POST /auth/verify-email` - Verify email address
- `POST /auth/forgot-password` - Initiate password reset
- `POST /auth/reset-password` - Complete password reset

### OAuth
- `GET /auth/oauth/{provider}` - Initiate OAuth flow
- `GET /auth/oauth/{provider}/callback` - OAuth callback

### User Profile
- `GET /users/me` - Get current user profile
- `PUT /users/me` - Update profile
- `POST /users/me/change-password` - Change password
- `POST /users/me/revoke-sessions` - Revoke all sessions

### Expenses
- `POST /expenses` - Create expense
- `GET /expenses` - List expenses (with filters)
- `GET /expenses/{id}` - Get expense by ID
- `PUT /expenses/{id}` - Update expense
- `DELETE /expenses/{id}` - Delete expense

### Income
- `POST /income` - Create income
- `GET /income` - List income (with filters)
- `GET /income/{id}` - Get income by ID
- `PUT /income/{id}` - Update income
- `DELETE /income/{id}` - Delete income

### Budgets
- `POST /budgets` - Create budget
- `GET /budgets` - List budgets
- `GET /budgets/{id}` - Get budget by ID
- `PUT /budgets/{id}` - Update budget
- `DELETE /budgets/{id}` - Delete budget

### Categories
- `POST /categories` - Create category
- `GET /categories` - List categories
- `GET /categories/{id}` - Get category by ID
- `PUT /categories/{id}` - Update category
- `DELETE /categories/{id}` - Delete category

### Account Types
- `POST /accounts` - Create account type
- `GET /accounts` - List account types
- `GET /accounts/{id}` - Get account type by ID
- `PUT /accounts/{id}` - Update account type
- `DELETE /accounts/{id}` - Delete account type

### Analytics
- `GET /analytics/query` - Natural language analytics query

## Deployment

### Docker

Build and run with Docker:

```bash
docker build -t expense-api .
docker run -p 8000:8000 --env-file .env expense-api
```

### Environment Variables for Production

Ensure these are set in production:
- `DATABASE_URL`: Production database connection
- `API_BASEURL`: Your production API URL
- `FRONTEND_URL`: Your frontend URL (for CORS)
- `JWT_ALGORITHM=RS256`: Use RSA keys in production
- Generate new RSA keys for production (don't reuse development keys)

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License.

## Support

For issues and questions, please open an issue on GitHub.
