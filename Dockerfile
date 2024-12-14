# Use Python 3.11 as base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies including sqlite3
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    build-essential \
    python3-dev \
    sqlite3 \
    libsqlite3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# Create volume for the database
VOLUME /app/data

# Expose the port the app runs on
EXPOSE 8000

# Set environment variables
ENV DB_PATH=/app/data/crypto_news.db

# Command to run the application
CMD ["python", "news-ai.py"]