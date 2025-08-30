FROM python:3.9-slim

WORKDIR /

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY ./app /app

# Command to run the Celery worker
# The queue 'cpu_tasks' will be for CPU-intensive tasks like video processing
CMD ["celery", "-A", "app.workers.celery_app:app", "worker", "--loglevel=info", "-Q", "cpu_tasks"]
