# Use a base image with CUDA and PyTorch pre-installed
FROM pytorch/pytorch:2.1.0-cuda12.1-cudnn8-runtime

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libsndfile1 \
    git \
    curl \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Install OpenVoice and its dependencies
RUN git clone https://github.com/myshell-ai/OpenVoice.git /app/OpenVoice
COPY requirements.txt .
# Install MeloTTS from git and other requirements
RUN pip install --no-cache-dir -r requirements.txt
# Install OpenVoice from the cloned repo
RUN cd /app/OpenVoice && pip install -e .
# Download dictionary for Japanese tokenization
RUN python -m unidic download

# Download and extract OpenVoice V2 checkpoints
RUN curl -L -o checkpoints_v2.zip "https://myshell-public-repo-host.s3.amazonaws.com/openvoice/checkpoints_v2_0417.zip" && \
    unzip checkpoints_v2.zip -d checkpoints_v2 && \
    rm checkpoints_v2.zip

# Copy application code
COPY ./app /app

# Command to run the Celery worker for GPU tasks
CMD ["celery", "-A", "workers.celery_app:app", "worker", "--loglevel=info", "-Q", "gpu_tasks", "-c", "1"]
