FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
COPY generate_rsa_keys.py .
RUN pip install --no-cache-dir -r requirements.txt
RUN python3 generate_rsa_keys.py

# Copy application
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY main.py .
COPY alembic.ini .

# Expose port (Azure will override with PORT env var)
EXPOSE 8000

# Use environment variable for port with fallback to 8000
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}