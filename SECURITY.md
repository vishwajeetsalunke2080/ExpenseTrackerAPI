# Security Policy

## Supported Versions

We release patches for security vulnerabilities for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 1.1.x   | :white_check_mark: |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

We take the security of our software seriously. If you believe you have found a security vulnerability, please report it to us as described below.

### Please do NOT:

- Open a public GitHub issue
- Disclose the vulnerability publicly before it has been addressed

### Please DO:

1. **Email us directly** at security@yourapp.com (replace with your actual security contact)
2. **Provide detailed information** including:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

### What to expect:

- **Acknowledgment**: We will acknowledge receipt of your vulnerability report within 48 hours
- **Assessment**: We will assess the vulnerability and determine its severity
- **Fix**: We will work on a fix and keep you updated on progress
- **Disclosure**: Once fixed, we will coordinate disclosure timing with you
- **Credit**: We will credit you in our security advisory (unless you prefer to remain anonymous)

## Security Best Practices

### For Developers

1. **Never commit sensitive data**
   - API keys, passwords, tokens
   - Use `.env` files (excluded from git)
   - Use environment variables

2. **Keep dependencies updated**
   ```bash
   pip list --outdated
   pip install --upgrade package-name
   ```

3. **Use security scanning tools**
   ```bash
   bandit -r app/
   safety check
   ```

4. **Follow secure coding practices**
   - Input validation
   - SQL injection prevention (use ORM)
   - XSS prevention
   - CSRF protection

### For Deployment

1. **Use HTTPS only**
   - Configure SSL/TLS certificates
   - Redirect HTTP to HTTPS

2. **Secure environment variables**
   - Use secret management services
   - Never log sensitive data

3. **Database security**
   - Use strong passwords
   - Enable SSL connections
   - Restrict network access
   - Regular backups

4. **JWT Security**
   - Use RS256 in production
   - Keep private keys secure
   - Rotate keys periodically
   - Set appropriate token expiration

5. **Rate limiting**
   - Configure appropriate limits
   - Monitor for abuse
   - Implement IP blocking for repeated violations

6. **Monitoring**
   - Set up error tracking (Sentry)
   - Monitor authentication failures
   - Alert on suspicious activity

## Known Security Features

### Authentication
- JWT with RS256 (RSA keys)
- Bcrypt password hashing (cost factor 12)
- Email verification required
- Rate limiting on login attempts
- Account lockout after failed attempts

### Authorization
- User data isolation at database level
- 404 responses for unauthorized access
- Token revocation support

### Data Protection
- Password reset with time-limited tokens
- Secure session management
- CORS configuration

## Security Updates

Security updates will be released as patch versions (e.g., 1.1.1) and announced via:
- GitHub Security Advisories
- Release notes
- Email notifications (if subscribed)

## Compliance

This application implements security best practices aligned with:
- OWASP Top 10
- GDPR data protection requirements
- Industry standard authentication practices

## Contact

For security concerns, contact: security@yourapp.com

For general questions, open a GitHub issue.
