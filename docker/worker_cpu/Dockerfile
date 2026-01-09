# This Dockerfile assumes you have already built the base image:
# docker build -t ppttovideo-cpu-base:latest -f docker/base-images/Dockerfile.cpu-base .

# Use the pre-built CPU base image
FROM ppttovideo-cpu-base:latest
WORKDIR /

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    espeak-ng \
    cmake \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /

# Copy the application code into the container
COPY ./app /app
COPY ./neutts-air /neutts-air
RUN pip install -r /neutts-air/requirements.txt

COPY ./fish-speech /fish-speech
RUN pip install /fish-speech

COPY ./chatterbox /chatterbox
RUN pip install /chatterbox

# Set PYTHONPATH
ENV PYTHONPATH="${PYTHONPATH}:/neutts-air:/fish-speech:/chatterbox"

# Command to run the Celery worker
# The queue 'cpu_tasks' will be for CPU-intensive tasks like video processing
CMD ["celery", "-A", "app.workers.celery_app_cpu:app", "worker", "--loglevel=info", "-Q", "cpu_tasks"]