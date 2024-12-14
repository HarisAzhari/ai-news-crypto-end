# Use Python 3.11 as base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    chromium \
    chromium-driver \
    build-essential \
    python3-dev \
    sqlite3 \
    libsqlite3-dev \
    && rm -rf /var/lib/apt/lists/*

# Set Chrome environment variables
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver
ENV PYTHONUNBUFFERED=1

# Copy requirements first
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# Create and set permissions for data directory
RUN mkdir -p /app/data && chmod 777 /app/data

# Set environment variables
ENV DB_PATH=/app/data/crypto_news.db

# Expose port
EXPOSE 8000

# Command to run the application
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "--timeout", "120", "news-ai:app"]