# Use a base image with CUDA and PyTorch pre-installed
FROM pytorch/pytorch:2.1.0-cuda12.1-cudnn8-runtime

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
    && rm -rf /var/lib/apt/lists/*

# Copy requirements.txt first
COPY requirements.txt .
# Install MeloTTS from git and other requirements
RUN pip install --no-cache-dir -r requirements.txt

# Install unidic dictionary for MeloTTS/MeCab
RUN python -m unidic download

# Download required NLTK data for MeloTTS
RUN python -c "import nltk; nltk.download('averaged_perceptron_tagger_eng'); nltk.download('averaged_perceptron_tagger'); nltk.download('cmudict')"

# Pre-download BERT model for MeloTTS to prevent runtime hanging
RUN python -c "from transformers import BertTokenizer, BertModel; BertTokenizer.from_pretrained('bert-base-uncased'); BertModel.from_pretrained('bert-base-uncased'); print('BERT model cached successfully')"

# Install OpenVoice and its dependencies  
RUN git clone https://github.com/myshell-ai/OpenVoice.git /OpenVoice && \
    cd /OpenVoice && \
    ls -la && \
    pip install -e . && \
    python -c "import openvoice; print('OpenVoice installed successfully')"

# Download and extract OpenVoice V2 checkpoints
RUN curl -L -o checkpoints_v2.zip "https://myshell-public-repo-host.s3.amazonaws.com/openvoice/checkpoints_v2_0417.zip" && \
    unzip checkpoints_v2.zip -d checkpoints_v2 && \
    rm checkpoints_v2.zip

# Copy application code
COPY ./app /app

# Set PYTHONPATH to include OpenVoice directory
ENV PYTHONPATH="${PYTHONPATH}:/OpenVoice"

# Command to run the Celery worker for GPU tasks
CMD ["celery", "-A", "app.workers.celery_app_gpu:app", "worker", "--loglevel=info", "-Q", "gpu_tasks", "-c", "1"]
