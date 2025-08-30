# Use a stable Debian image
FROM debian:bullseye

# Install LibreOffice and other dependencies
RUN apt-get update && apt-get install -y \
    libreoffice-writer \
    libreoffice-impress \
    libreoffice-calc \
    poppler-utils \
    python3-pip \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip3 install Flask minio

# Set up the working directory
WORKDIR /app

# Copy the converter application into the container
COPY app/services/libreoffice_converter.py .

# Command to run the Flask application
CMD ["python3", "libreoffice_converter.py"]
