# This Dockerfile assumes you have already built the base image:
# docker build -t ppttovideo-gpu-base:latest -f docker/base-images/Dockerfile.gpu-base .

# Use the pre-built GPU base image
FROM ppttovideo-gpu-base:latest

# Set the working directory
WORKDIR /

# Copy the application code into the container
COPY ./app /app

# Command to run the Celery worker for GPU tasks
CMD ["celery", "-A", "app.workers.celery_app_gpu:app", "worker", "--loglevel=info", "-Q", "gpu_tasks", "-c", "1"]