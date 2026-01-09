# This Dockerfile assumes you have already built the base image:
# docker build -t ppttovideo-cpu-base:latest -f docker/base-images/Dockerfile.cpu-base .

# Use the pre-built CPU base image
FROM ppttovideo-cpu-base:latest
# Set the working directory in the container
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

# Copy templates directory
COPY ./templates /templates

# Command to run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]