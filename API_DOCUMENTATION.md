# API Documentation

Complete API reference for the Expense Tracking API.

## Base URL

```
Production: https://your-domain.com
Development: http://localhost:8000
```

## Authentication

Most endpoints require authentication using JWT tokens.

### Headers

```http
Authorization: Bearer <access_token>
Content-Type: application/json
```

### Token Lifecycle

- **Access Token**: 15 minutes expiration
- **Refresh Token**: 7 days expiration

## Response Format

### Success Response

```json
{
  "data": { ... },
  "message": "Success message"
}
```

### Error Response

```json
{
  "detail": "Error message",
  "error_code": "ERROR_CODE"
}
```

## Endpoints

### Authentication

#### POST /auth/signup

Register a new user account.

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "SecurePass123",
  "full_name": "John Doe"
}
```

**Response:** `201 Created`
```json
{
  "id": 1,
  "email": "user@example.com",
  "full_name": "John Doe",
  "is_verified": false,
  "created_at": "2024-02-28T10:00:00Z"
}
```

**Errors:**
- `400`: Email already registered
- `422`: Validation error

---

#### POST /auth/signin

Login with email and password.

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "SecurePass123"
}
```

**Response:** `200 OK`
```json
{
  "access_token": "eyJhbGc...",
  "refresh_token": "eyJhbGc...",
  "token_type": "bearer",
  "expires_in": 900
}
```

**Errors:**
- `401`: Invalid credentials
- `403`: Account locked or not verified
- `422`: Validation error

---

#### POST /auth/signout

Logout and revoke current refresh token.

**Headers:** Requires authentication

**Response:** `204 No Content`

---

#### POST /auth/refresh

Refresh access token using refresh token.

**Request Body:**
```json
{
  "refresh_token": "eyJhbGc..."
}
```

**Response:** `200 OK`
```json
{
  "access_token": "eyJhbGc...",
  "token_type": "bearer",
  "expires_in": 900
}
```

---

#### POST /auth/verify-email

Verify email address with token.

**Request Body:**
```json
{
  "token": "verification_token_here"
}
```

**Response:** `200 OK`
```json
{
  "message": "Email verified successfully"
}
```

---

#### POST /auth/forgot-password

Initiate password reset flow.

**Request Body:**
```json
{
  "email": "user@example.com"
}
```

**Response:** `200 OK`
```json
{
  "message": "Password reset email sent"
}
```

---

#### POST /auth/reset-password

Complete password reset with token.

**Request Body:**
```json
{
  "token": "reset_token_here",
  "new_password": "NewSecurePass123"
}
```

**Response:** `200 OK`
```json
{
  "message": "Password reset successfully"
}
```

---

### OAuth

#### GET /auth/oauth/{provider}

Initiate OAuth flow (provider: google or github).

**Response:** `307 Temporary Redirect` to OAuth provider

---

#### GET /auth/oauth/{provider}/callback

OAuth callback endpoint (handled automatically).

---

### User Profile

#### GET /users/me

Get current user profile.

**Headers:** Requires authentication

**Response:** `200 OK`
```json
{
  "id": 1,
  "email": "user@example.com",
  "full_name": "John Doe",
  "is_verified": true,
  "created_at": "2024-02-28T10:00:00Z",
  "last_login_at": "2024-02-28T12:00:00Z"
}
```

---

#### PUT /users/me

Update user profile.

**Headers:** Requires authentication

**Request Body:**
```json
{
  "full_name": "Jane Doe",
  "email": "newemail@example.com"
}
```

**Response:** `200 OK`

---

#### POST /users/me/change-password

Change password.

**Headers:** Requires authentication

**Request Body:**
```json
{
  "current_password": "OldPass123",
  "new_password": "NewPass123"
}
```

**Response:** `200 OK`

---

### Expenses

#### POST /expenses

Create a new expense.

**Headers:** Requires authentication

**Request Body:**
```json
{
  "date": "2024-02-28",
  "amount": 50.00,
  "category": "Food & Dining",
  "account": "Credit Card",
  "notes": "Lunch at restaurant"
}
```

**Response:** `201 Created`
```json
{
  "id": 1,
  "date": "2024-02-28",
  "amount": 50.00,
  "category": "Food & Dining",
  "account": "Credit Card",
  "notes": "Lunch at restaurant",
  "created_at": "2024-02-28T12:00:00Z",
  "updated_at": "2024-02-28T12:00:00Z"
}
```

---

#### GET /expenses

List expenses with optional filters.

**Headers:** Requires authentication

**Query Parameters:**
- `start_date` (optional): Filter by start date (YYYY-MM-DD)
- `end_date` (optional): Filter by end date (YYYY-MM-DD)
- `category` (optional): Filter by category
- `account` (optional): Filter by account
- `min_amount` (optional): Minimum amount
- `max_amount` (optional): Maximum amount
- `skip` (optional): Pagination offset (default: 0)
- `limit` (optional): Pagination limit (default: 100)

**Response:** `200 OK`
```json
{
  "items": [
    {
      "id": 1,
      "date": "2024-02-28",
      "amount": 50.00,
      "category": "Food & Dining",
      "account": "Credit Card",
      "notes": "Lunch"
    }
  ],
  "total": 1,
  "skip": 0,
  "limit": 100
}
```

---

#### GET /expenses/{id}

Get expense by ID.

**Headers:** Requires authentication

**Response:** `200 OK` or `404 Not Found`

---

#### PUT /expenses/{id}

Update expense.

**Headers:** Requires authentication

**Request Body:** Same as create (all fields optional)

**Response:** `200 OK` or `404 Not Found`

---

#### DELETE /expenses/{id}

Delete expense.

**Headers:** Requires authentication

**Response:** `204 No Content` or `404 Not Found`

---

### Income

Similar endpoints as Expenses:
- `POST /income`
- `GET /income`
- `GET /income/{id}`
- `PUT /income/{id}`
- `DELETE /income/{id}`

**Note:** Income doesn't have `account` field.

---

### Budgets

#### POST /budgets

Create a budget.

**Headers:** Requires authentication

**Request Body:**
```json
{
  "category": "Food & Dining",
  "amount_limit": 500.00
}
```

**Response:** `201 Created`

---

#### GET /budgets

List budgets.

**Headers:** Requires authentication

**Query Parameters:**
- `category` (optional): Filter by category

**Response:** `200 OK`

---

### Categories

#### POST /categories

Create a category.

**Headers:** Requires authentication

**Request Body:**
```json
{
  "name": "Custom Category",
  "type": "expense"
}
```

**Response:** `201 Created`

---

#### GET /categories

List categories.

**Headers:** Requires authentication

**Query Parameters:**
- `type` (optional): Filter by type (expense or income)

**Response:** `200 OK`

---

### Account Types

#### POST /accounts

Create account type.

**Headers:** Requires authentication

**Request Body:**
```json
{
  "name": "PayPal"
}
```

**Response:** `201 Created`

---

#### GET /accounts

List account types.

**Headers:** Requires authentication

**Response:** `200 OK`

---

### Analytics

#### GET /analytics/query

Natural language analytics query.

**Headers:** Requires authentication

**Query Parameters:**
- `query` (required): Natural language query

**Example:**
```
GET /analytics/query?query=Show me total expenses in November by category
```

**Response:** `200 OK`
```json
{
  "query": "Show me total expenses in November by category",
  "results": [
    {
      "category": "Food & Dining",
      "total": 450.00
    },
    {
      "category": "Transportation",
      "total": 200.00
    }
  ],
  "formatted_response": "Here are your expenses for November..."
}
```

---

## Error Codes

| Code | Description |
|------|-------------|
| 400 | Bad Request |
| 401 | Unauthorized |
| 403 | Forbidden |
| 404 | Not Found |
| 422 | Validation Error |
| 429 | Too Many Requests |
| 500 | Internal Server Error |

## Rate Limits

- Login attempts: 5 per 15 minutes
- Password reset: 3 per hour
- General API: 100 requests per minute

## Pagination

List endpoints support pagination:
- `skip`: Number of items to skip (default: 0)
- `limit`: Maximum items to return (default: 100, max: 1000)

## Date Formats

All dates use ISO 8601 format: `YYYY-MM-DD`

All timestamps use ISO 8601 with timezone: `YYYY-MM-DDTHH:MM:SSZ`

## Testing

Use the interactive API documentation:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
