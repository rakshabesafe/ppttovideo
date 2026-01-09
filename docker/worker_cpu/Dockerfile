# This Dockerfile assumes you have already built the base image:
# docker build -t ppttovideo-cpu-base:latest -f docker/base-images/Dockerfile.cpu-base .

# Use the pre-built CPU base image
FROM ppttovideo-cpu-base:latest

# Set the working directory
WORKDIR /

# Copy the application code into the container
COPY ./app /app

# Command to run the Celery worker
# The queue 'cpu_tasks' will be for CPU-intensive tasks like video processing
CMD ["celery", "-A", "app.workers.celery_app_cpu:app", "worker", "--loglevel=info", "-Q", "cpu_tasks"]