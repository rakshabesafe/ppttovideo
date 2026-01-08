FROM python:3.11-slim

WORKDIR /

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    espeak-ng \
    cmake \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY ./app /app
COPY ./neutts-air /neutts-air
RUN pip install -r /neutts-air/requirements.txt

COPY ./fish-speech /fish-speech
RUN pip install /fish-speech

# Set PYTHONPATH
ENV PYTHONPATH="${PYTHONPATH}:/neutts-air:/fish-speech"

# Command to run the Celery worker
# The queue 'cpu_tasks' will be for CPU-intensive tasks like video processing
CMD ["celery", "-A", "app.workers.celery_app_cpu:app", "worker", "--loglevel=info", "-Q", "cpu_tasks"]
