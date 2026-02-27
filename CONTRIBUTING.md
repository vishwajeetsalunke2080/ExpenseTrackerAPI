# Contributing to Expense Tracking API

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## Development Setup

1. Fork and clone the repository
2. Create a virtual environment and install dependencies
3. Set up your `.env` file based on `.env.example`
4. Generate RSA keys: `python generate_rsa_keys.py`
5. Run migrations: `alembic upgrade head`
6. Run tests to ensure everything works: `pytest`

## Code Style

- Follow PEP 8 style guidelines
- Use type hints for all function parameters and return values
- Write docstrings for all public functions and classes
- Keep functions focused and single-purpose
- Use async/await for I/O operations

## Testing

- Write tests for all new features
- Maintain or improve code coverage
- Run the full test suite before submitting PR: `pytest`
- Include both unit tests and integration tests where appropriate

### Test Structure

```
tests/
├── unit/           # Unit tests for individual components
├── integration/    # Integration tests for workflows
├── property/       # Property-based tests with Hypothesis
└── e2e/           # End-to-end tests
```

## Commit Messages

Use clear, descriptive commit messages:

```
feat: Add user profile update endpoint
fix: Resolve token expiration issue
docs: Update API documentation
test: Add tests for budget service
refactor: Simplify expense query logic
```

## Pull Request Process

1. Create a feature branch from `main`
2. Make your changes with clear commits
3. Update documentation if needed
4. Add tests for new functionality
5. Ensure all tests pass
6. Update CHANGELOG.md if applicable
7. Submit PR with clear description

### PR Description Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
Describe testing performed

## Checklist
- [ ] Tests pass locally
- [ ] Code follows style guidelines
- [ ] Documentation updated
- [ ] No breaking changes (or documented)
```

## Database Migrations

When making database changes:

1. Create migration: `alembic revision --autogenerate -m "Description"`
2. Review generated migration file
3. Test upgrade: `alembic upgrade head`
4. Test downgrade: `alembic downgrade -1`
5. Include migration in your PR

## Security

- Never commit sensitive data (API keys, passwords, etc.)
- Use environment variables for configuration
- Follow security best practices
- Report security vulnerabilities privately

## Questions?

Open an issue for questions or discussions.
