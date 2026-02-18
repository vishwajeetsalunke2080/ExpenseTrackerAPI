# Expense Tracking and Analytics API - Usage Guide

## Table of Contents
1. [Getting Started](#getting-started)
2. [Authentication & Configuration](#authentication--configuration)
3. [API Endpoints Overview](#api-endpoints-overview)
4. [Categories Management](#categories-management)
5. [Account Types Management](#account-types-management)
6. [Expense Management](#expense-management)
7. [Income Management](#income-management)
8. [Budget Management](#budget-management)
9. [Natural Language Analytics](#natural-language-analytics)
10. [Error Handling](#error-handling)
11. [Examples & Use Cases](#examples--use-cases)

---

## Getting Started

### Prerequisites
- Python 3.12 or higher
- PostgreSQL database
- Redis server
- OpenAI API key (for analytics features)

### Installation

1. **Activate the virtual environment:**
```cmd
FastAPI\Scripts\activate.bat
```

2. **Configure environment variables:**
Create a `.env` file in the `FastAPI/` directory:
```env
# Database Configuration
DATABASE_URL=postgresql+asyncpg://username:password@localhost:5432/expense_db

# Redis Configuration
REDIS_URL=redis://localhost:6379/0

# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here

# API Configuration
API_TITLE=Expense Tracking API
API_VERSION=1.0.0
```

3. **Run the application:**
```cmd
FastAPI\Scripts\uvicorn.exe Test:app --reload
```

The API will be available at `http://localhost:8000`

### Interactive Documentation
- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

---

## Authentication & Configuration

Currently, the API does not require authentication. For production use, consider adding:
- JWT token authentication
- API key authentication
- OAuth2 integration

---

## API Endpoints Overview

### Base URL
```
http://localhost:8000
```

### Available Endpoints

| Endpoint | Methods | Description |
|----------|---------|-------------|
| `/` | GET | Health check |
| `/categories` | GET, POST | Manage expense/income categories |
| `/categories/{id}` | PUT, DELETE | Update/delete specific category |
| `/accounts` | GET, POST | Manage account types |
| `/accounts/{id}` | PUT, DELETE | Update/delete specific account |
| `/expenses` | GET, POST | Manage expenses |
| `/expenses/{id}` | GET, PUT, DELETE | Manage specific expense |
| `/income` | GET, POST | Manage income records |
| `/income/{id}` | GET, PUT, DELETE | Manage specific income |
| `/budgets` | GET, POST | Manage budgets |
| `/budgets/{id}` | GET, PUT, DELETE | Manage specific budget |
| `/analytics/query` | POST | Natural language analytics |

### Health Check
```http
GET /
```

**Response:**
```json
{
  "message": "Expense Tracking API is running",
  "version": "1.0.0",
  "status": "healthy"
}
```

---

## Categories Management

Categories help organize expenses and income into meaningful groups.

### Default Categories
- **Expense Categories:** Food, Travel, Groceries, Shopping, Other
- **Income Categories:** Salary, Cash, Other Income

### List All Categories
```http
GET /categories?type=expense
```

**Query Parameters:**
- `type` (optional): Filter by type (`expense` or `income`)

**Example Request:**
```bash
curl http://localhost:8000/categories?type=expense
```

**Response:**
```json
[
  {
    "id": 1,
    "name": "Food",
    "type": "expense"
  },
  {
    "id": 2,
    "name": "Travel",
    "type": "expense"
  }
]
```

### Create Category
```http
POST /categories
```

**Request Body:**
```json
{
  "name": "Entertainment",
  "type": "expense"
}
```

**Response:** `201 Created`

### Update Category
```http
PUT /categories/{id}
```

**Request Body:**
```json
{
  "name": "Entertainment & Leisure"
}
```

### Delete Category
```http
DELETE /categories/{id}
```

**Note:** Default categories cannot be deleted.

---

## Account Types Management

Account types represent payment methods used for expenses.

### Default Account Types
Cash, Card, UPI

### List All Account Types
```http
GET /accounts
```

### Create Account Type
```http
POST /accounts
```

**Request Body:**
```json
{
  "name": "Bank Transfer"
}
```

---

## Expense Management

### Create Expense
```http
POST /expenses
```

**Request Body:**
```json
{
  "date": "2024-02-15",
  "amount": "150.50",
  "category": "Food",
  "account": "Card",
  "notes": "Dinner at restaurant"
}
```

**Response:** `201 Created`
```json
{
  "id": 1,
  "date": "2024-02-15",
  "amount": "150.50",
  "category": "Food",
  "account": "Card",
  "notes": "Dinner at restaurant",
  "created_at": "2024-02-15",
  "updated_at": "2024-02-15"
}
```

### Get Expense by ID
```http
GET /expenses/{id}
```

### List Expenses with Filtering
```http
GET /expenses
```

**Query Parameters:**
- `start_date`: Filter by start date (YYYY-MM-DD)
- `end_date`: Filter by end date (YYYY-MM-DD)
- `categories`: Comma-separated list
- `accounts`: Comma-separated list
- `min_amount`: Minimum amount
- `max_amount`: Maximum amount
- `page`: Page number (default: 1)
- `page_size`: Items per page (default: 50, max: 100)

**Examples:**

```bash
# Get all expenses for November 2024
curl "http://localhost:8000/expenses?start_date=2024-11-01&end_date=2024-11-30"

# Get Food and Travel expenses
curl "http://localhost:8000/expenses?categories=Food,Travel"

# Get Card expenses between $50 and $200
curl "http://localhost:8000/expenses?accounts=Card&min_amount=50&max_amount=200"
```

### Update Expense
```http
PUT /expenses/{id}
```

### Delete Expense
```http
DELETE /expenses/{id}
```

---

## Income Management

### Create Income
```http
POST /income
```

**Request Body:**
```json
{
  "date": "2024-02-01",
  "amount": "5000.00",
  "category": "Salary",
  "notes": "Monthly salary"
}
```

### List Income with Filtering
```http
GET /income?start_date=2024-01-01&end_date=2024-12-31
```

---

## Budget Management

### Create Budget
```http
POST /budgets
```

**Request Body:**
```json
{
  "category": "Food",
  "amount_limit": "500.00",
  "start_date": "2024-02-01",
  "end_date": "2024-02-29"
}
```

**Response includes real-time usage:**
```json
{
  "id": 1,
  "category": "Food",
  "amount_limit": "500.00",
  "start_date": "2024-02-01",
  "end_date": "2024-02-29",
  "usage": {
    "amount_spent": "150.50",
    "percentage_used": 30.1,
    "is_over_budget": false
  }
}
```

### Get Budget by ID
```http
GET /budgets/{id}
```

### List Budgets
```http
GET /budgets?category=Food
```

---

## Natural Language Analytics

Ask questions about your spending in plain English.

### Query Analytics
```http
POST /analytics/query?query=YOUR_QUESTION
```

### Example Queries

**1. Category Breakdown:**
```
What are the spends for November separated by categories?
```

**2. Total Spending:**
```
What is my total spending for December?
```

**3. Account Analysis:**
```
How much did I spend using Card in November?
```

**4. Monthly Trends:**
```
Show me monthly spending breakdown for 2024
```

**5. Specific Categories:**
```
Show me total spending on Food and Travel
```

**Response Format:**
```json
{
  "query": "Your question",
  "summary": "Human-readable summary",
  "breakdown": "Detailed breakdown",
  "data": {
    "aggregation_type": "by_category",
    "expenses": {...},
    "total_expenses": 1250.00
  }
}
```

---

## Error Handling

### Validation Errors (422)
```json
{
  "detail": "Validation error",
  "error_code": "VALIDATION_ERROR",
  "field_errors": {
    "amount": ["Input should be greater than 0"]
  }
}
```

### Not Found (404)
```json
{
  "detail": "Expense with id 999 not found"
}
```

### Bad Request (400)
```json
{
  "detail": "Unable to parse query. Please try rephrasing..."
}
```

---

## Examples & Use Cases

### Use Case 1: Monthly Expense Tracking

```bash
# 1. Create expenses
curl -X POST http://localhost:8000/expenses \
  -H "Content-Type: application/json" \
  -d '{"date":"2024-02-15","amount":"50.00","category":"Food","account":"Card","notes":"Lunch"}'

# 2. View all expenses for the month
curl "http://localhost:8000/expenses?start_date=2024-02-01&end_date=2024-02-29"

# 3. Ask analytics
curl -X POST "http://localhost:8000/analytics/query?query=What%20are%20my%20expenses%20for%20February?"
```

### Use Case 2: Budget Management

```bash
# 1. Create a budget
curl -X POST http://localhost:8000/budgets \
  -H "Content-Type: application/json" \
  -d '{"category":"Food","amount_limit":"500.00","start_date":"2024-02-01","end_date":"2024-02-29"}'

# 2. Check budget status
curl http://localhost:8000/budgets/1

# 3. Get all budgets
curl http://localhost:8000/budgets
```

### Use Case 3: Income vs Expenses Analysis

```bash
# 1. Add income
curl -X POST http://localhost:8000/income \
  -H "Content-Type: application/json" \
  -d '{"date":"2024-02-01","amount":"5000.00","category":"Salary","notes":"Monthly"}'

# 2. Ask for analysis
curl -X POST "http://localhost:8000/analytics/query?query=Show%20me%20income%20vs%20expenses%20for%20February"
```

---

## Tips & Best Practices

1. **Use Filtering:** Take advantage of query parameters to filter expenses by date, category, and amount
2. **Budget Tracking:** Set up budgets at the start of each month to track spending
3. **Natural Language:** The analytics endpoint understands various phrasings - experiment with different questions
4. **Caching:** The API caches responses for 15 minutes for better performance
5. **Pagination:** Use `page` and `page_size` parameters for large datasets

---

## Support & Documentation

- **Interactive API Docs:** http://localhost:8000/docs
- **Alternative Docs:** http://localhost:8000/redoc
- **Health Check:** http://localhost:8000/

For issues or questions, refer to the API documentation or check the application logs.
