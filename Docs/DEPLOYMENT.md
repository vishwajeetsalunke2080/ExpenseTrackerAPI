# Deployment Guide

This guide covers deploying the Expense Tracking API to production.

## Pre-Deployment Checklist

- [ ] All tests passing (`pytest`)
- [ ] Environment variables configured
- [ ] Database migrations applied
- [ ] Redis server configured and running
- [ ] Groq API key obtained and configured
- [ ] Security review completed
- [ ] API documentation reviewed

## Environment Setup

### 1. Production Environment Variables

Create a `.env` file with production values:

```env
# Database - Use PostgreSQL for production
DATABASE_URL=postgresql+asyncpg://user:password@localhost/expense_tracker

# Redis Cache
REDIS_URL=redis://localhost:6379/0
CACHE_TTL_MINUTES=15

# Groq AI
GROQ_API_KEY=your_production_groq_api_key
GROQ_MODEL=llama-3.3-70b-versatile

# API
API_TITLE=Expense Tracking API
API_VERSION=1.0.0
```

### 2. Database Setup

For production, consider using PostgreSQL instead of SQLite:

```bash
# Install PostgreSQL driver
pip install asyncpg psycopg2-binary

# Update DATABASE_URL in .env
DATABASE_URL=postgresql+asyncpg://user:password@localhost/expense_tracker

# Run migrations
alembic upgrade head
```

## Deployment Options

### Option 1: Docker Deployment

Create a `Dockerfile`:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY main.py .
COPY alembic.ini .

# Expose port
EXPOSE 8000

# Run application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:password@db/expense_tracker
      - REDIS_URL=redis://redis:6379/0
      - GROQ_API_KEY=${GROQ_API_KEY}
    depends_on:
      - db
      - redis

  db:
    image: postgres:15
    environment:
      - POSTGRES_DB=expense_tracker
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
```

Deploy:
```bash
docker-compose up -d
```

### Option 2: Traditional Server Deployment

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure systemd service** (`/etc/systemd/system/expense-api.service`):
   ```ini
   [Unit]
   Description=Expense Tracking API
   After=network.target

   [Service]
   Type=notify
   User=www-data
   Group=www-data
   WorkingDirectory=/var/www/expense-api
   Environment="PATH=/var/www/expense-api/bin"
   ExecStart=/var/www/expense-api/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```

3. **Start service**
   ```bash
   sudo systemctl enable expense-api
   sudo systemctl start expense-api
   ```

### Option 3: Cloud Platform Deployment

#### Heroku
```bash
# Create Procfile
echo "web: uvicorn main:app --host 0.0.0.0 --port \$PORT" > Procfile

# Deploy
heroku create expense-tracking-api
git push heroku main
```

#### AWS Elastic Beanstalk
```bash
# Install EB CLI
pip install awsebcli

# Initialize
eb init -p python-3.12 expense-api

# Create environment
eb create expense-api-env

# Deploy
eb deploy
```

#### Google Cloud Run
```bash
# Build container
gcloud builds submit --tag gcr.io/PROJECT_ID/expense-api

# Deploy
gcloud run deploy expense-api \
  --image gcr.io/PROJECT_ID/expense-api \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

## Nginx Reverse Proxy

Configure Nginx as a reverse proxy:

```nginx
server {
    listen 80;
    server_name api.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## SSL/TLS Configuration

Use Let's Encrypt for free SSL certificates:

```bash
# Install certbot
sudo apt-get install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d api.yourdomain.com

# Auto-renewal is configured automatically
```

## Monitoring and Logging

### Application Logging

Add logging to `main.py`:

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
```

### Health Check Endpoint

The API includes a health check at `/`:

```bash
curl http://localhost:8000/
```

### Monitoring Tools

Consider using:
- **Prometheus + Grafana**: Metrics and dashboards
- **Sentry**: Error tracking
- **DataDog**: Full-stack monitoring
- **New Relic**: Application performance monitoring

## Performance Optimization

### 1. Enable Gzip Compression

Add to `main.py`:
```python
from fastapi.middleware.gzip import GZipMiddleware
app.add_middleware(GZipMiddleware, minimum_size=1000)
```

### 2. Configure Workers

For production, use multiple workers:
```bash
uvicorn main:app --workers 4 --host 0.0.0.0 --port 8000
```

### 3. Database Connection Pooling

Already configured in `database.py` with SQLAlchemy.

### 4. Redis Caching

Already implemented for frequently accessed data.

## Security Hardening

### 1. Add CORS Middleware

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 2. Rate Limiting

Install and configure:
```bash
pip install slowapi
```

### 3. API Authentication

Consider adding:
- JWT tokens
- OAuth2
- API keys

### 4. Input Validation

Already implemented with Pydantic schemas.

## Backup Strategy

### Database Backups

```bash
# PostgreSQL backup
pg_dump expense_tracker > backup_$(date +%Y%m%d).sql

# Automated daily backups
0 2 * * * /usr/bin/pg_dump expense_tracker > /backups/expense_$(date +\%Y\%m\%d).sql
```

### Redis Backups

Redis automatically saves snapshots to disk (RDB files).

## Rollback Procedure

### Database Rollback

```bash
# Rollback one migration
alembic downgrade -1

# Rollback to specific version
alembic downgrade <revision_id>
```

### Application Rollback

```bash
# Docker
docker-compose down
docker-compose up -d --build

# Git
git revert <commit_hash>
git push
```

## Troubleshooting

### Check Logs

```bash
# Application logs
tail -f app.log

# Systemd service logs
journalctl -u expense-api -f

# Docker logs
docker-compose logs -f api
```

### Common Issues

1. **Database connection errors**: Check DATABASE_URL and network connectivity
2. **Redis connection errors**: Ensure Redis is running and accessible
3. **Groq API errors**: Verify API key and rate limits
4. **Port already in use**: Change port or stop conflicting service

## Maintenance

### Regular Tasks

- Update dependencies monthly
- Review and rotate API keys quarterly
- Monitor disk space and database size
- Review application logs for errors
- Test backup restoration procedures

### Updating the Application

```bash
# Pull latest code
git pull origin main

# Install new dependencies
pip install -r requirements.txt

# Run migrations
alembic upgrade head

# Restart service
sudo systemctl restart expense-api
```

## Support

For deployment issues, check:
- Application logs
- Database logs
- Redis logs
- Nginx/reverse proxy logs

Contact: [Your Support Email]
