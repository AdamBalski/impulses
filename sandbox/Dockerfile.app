FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY server/requirements.txt server/requirements.txt
RUN pip install --no-cache-dir -r server/requirements.txt

# Copy application code
COPY . .

# Create data storage directory
RUN mkdir -p /app/server/data-store
# Expose port
EXPOSE 8000

# Run migrations and start server
CMD ["sh", "-c", "bash ./ops/db_migrate.sh && cd server && python -m src.run"]
