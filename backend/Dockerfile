# Use Microsoft's official Playwright Python image — Chromium + all deps pre-installed
FROM mcr.microsoft.com/playwright/python:v1.49.0-noble

WORKDIR /app

# System deps for lxml / psycopg2
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    libxml2-dev \
    libxslt-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright browsers already in base image — just link them
RUN playwright install chromium

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
