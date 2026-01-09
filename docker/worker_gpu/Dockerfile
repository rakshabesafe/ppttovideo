# This Dockerfile assumes you have already built the base image:
# docker build -t ppttovideo-gpu-base:latest -f docker/base-images/Dockerfile.gpu-base .

# Use the pre-built GPU base image
FROM ppttovideo-gpu-base:latest
WORKDIR /

# Install system dependencies including MeCab for MeloTTS
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libsndfile1 \
    git \
    curl \
    unzip \
    mecab \
    libmecab-dev \
    mecab-ipadic-utf8 \
    espeak-ng \
    cmake \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements.txt first
COPY requirements.txt .
# Install MeloTTS from git and other requirements
RUN pip install --no-cache-dir -r requirements.txt

# Install unidic dictionary for MeloTTS/MeCab
RUN python -m unidic download

# Download required NLTK data for MeloTTS
RUN python -c "import nltk; nltk.download('averaged_perceptron_tagger_eng'); nltk.download('averaged_perceptron_tagger'); nltk.download('cmudict')"

# Set the working directory
WORKDIR /

# Copy the application code into the container
COPY ./app /app

# Copy NeuTTS Air code
COPY ./neutts-air /neutts-air
RUN pip install -r /neutts-air/requirements.txt

# Copy Fish Speech code
COPY ./fish-speech /fish-speech
RUN pip install /fish-speech

# Copy Chatterbox code (patched)
COPY ./chatterbox /chatterbox
RUN pip install /chatterbox

# Set PYTHONPATH to include OpenVoice, NeuTTS Air, Fish Speech and Chatterbox directories
ENV PYTHONPATH="${PYTHONPATH}:/OpenVoice:/neutts-air:/fish-speech:/chatterbox"

# Command to run the Celery worker for GPU tasks
CMD ["celery", "-A", "app.workers.celery_app_gpu:app", "worker", "--loglevel=info", "-Q", "gpu_tasks", "-c", "1"]