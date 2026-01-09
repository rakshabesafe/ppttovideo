# This Dockerfile assumes you have already built the base image:
# docker build -t ppttovideo-cpu-base:latest -f docker/base-images/Dockerfile.cpu-base .

# Use the pre-built CPU base image
FROM ppttovideo-cpu-base:latest

# Set the working directory
WORKDIR /

# Copy the application code into the container
COPY ./app /app

# Copy templates directory
COPY ./templates /templates

# Command to run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]