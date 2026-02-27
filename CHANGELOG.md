# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2024-02-28

### Added
- User data isolation feature - complete separation of user financial data
- User-scoped unique constraints for categories and account types
- Composite database indexes for optimized user-filtered queries
- User onboarding service with default categories and account types
- CASCADE delete for user data cleanup
- Support for both RS256 (production) and HS256 (testing) JWT algorithms

### Changed
- All financial entity services now require current_user parameter
- Database queries now filter by user_id at the database level
- Unauthorized access returns 404 instead of 403 to prevent information leakage
- Category names updated to avoid duplicates ("Other Expenses" and "Other Income")
- Settings class now supports optional JWT secret key for HS256

### Security
- Enhanced data isolation - users cannot access other users' data
- All database queries enforce user ownership at query level
- Improved security by returning 404 for unauthorized access attempts

## [1.0.0] - 2024-01-15

### Added
- User authentication with JWT (RS256)
- Email verification for new users
- Password reset functionality
- OAuth integration (Google and GitHub)
- User profile management
- Expense tracking (CRUD operations)
- Income tracking (CRUD operations)
- Budget management
- Category management
- Account type management
- AI-powered analytics with natural language queries
- Rate limiting for authentication endpoints
- Audit logging for authentication events
- Comprehensive test suite (unit, integration, property-based)
- Database migrations with Alembic
- Docker support
- API documentation (Swagger/ReDoc)

### Security
- Bcrypt password hashing (cost factor 12)
- JWT token-based authentication
- Rate limiting on login attempts
- Account lockout after failed attempts
- Secure password reset flow
- Email verification requirement
- CORS configuration

## [0.1.0] - 2023-12-01

### Added
- Initial project setup
- Basic FastAPI application structure
- Database configuration
- Environment variable management
